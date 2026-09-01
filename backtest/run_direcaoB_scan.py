#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIRECAO B — varredura de "e se repensarmos do zero".

A decisao estrategica aberta (23/08) tem duas saidas:
  A) aceitar ~50% e escalar avaliacoes em paralelo
  B) repensar instrumento / formato de avaliacao / hipotese

Este script destrincha B no que da pra medir COM O DADO QUE TEMOS (NQ 1min, 12
meses). Nao inventa dado que nao existe (ES/MES/ouro exigem baixar historico).

Eixos testados aqui:
  (1) TAMANHO DE CONTA / DD — a mesma reversao em Apex 25K/50K/100K/150K/250K,
      varrendo nro de contratos. Pergunta: "B" e' so comprar conta maior?
  (2) FORMATO DE DRAWDOWN — a mesma reversao sob 3 modelos de DD:
      - intraday trailing (Apex, o que usamos: pico conta lucro nao-realizado)
      - EOD trailing (pico so atualiza no fim do dia — varias prop firms)
      - static (limite fixo desde o inicio — Tradeify/MFFU tem opcao assim)
      Pergunta: o teto de ~50% e' da estrategia ou do DD trailing intradiario?
  (3) HIPOTESES NOVAS de entrada no proprio NQ, no mesmo motor:
      - GAP FADE na abertura RTH (o classico "gap tende a fechar" — estava
        pendente por bug no harness antigo)
      - FADE do range overnight (Globex) durante o RTH

Motor: janela 30d corridos, retry imediato, MaxTradesDia=12, slippage 2 ticks,
gestao SL12,5/BE3,75-2,5/trail1,75/alvo60 (a mesma de tudo no projeto).
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from run_estrategias_comparativo import (
    carregar, domingo_ranges, Estado, sinal_reversao,
    MNQ_PV, RT_PER, TICK, PTS_SL, PTS_BE_TRIG, PTS_BE_LOCK, PTS_TRAIL, TP,
    ENTRADA_INI, ENTRADA_FIM, FLATTEN, SLIP_BASE, STOP_DIA, MAX_TRADES, MIN_DIAS, mins,
)

JANELA = 30

# --- tiers Apex (meta, dd trailing) ---
TIERS = {
    '25K':  (1500.0, 1000.0),   # DD real confirmado no dashboard (23/06)
    '50K':  (3000.0, 2500.0),
    '100K': (6000.0, 3000.0),
    '150K': (9000.0, 5000.0),
    '250K': (15000.0, 6500.0),
}


# ============================ sinais novos ============================

def _prep_dia(st, bars, i):
    """guarda close RTH de ontem e o open RTH de hoje / range overnight."""
    pass


def sinal_gap_fade(bars, i, st, dom_map):
    """Gap de abertura RTH vs close RTH de ontem -> fade em direcao ao close.
    So dispara UMA vez por dia, na 1a hora, se |gap| >= limiar."""
    b = bars[i]; m = mins(b['dt'])
    if not (ENTRADA_INI <= m < ENTRADA_INI + 60): return 0
    if getattr(st, 'gap_usou', False): return 0
    pdc = getattr(st, 'pd_close', None); orth = getattr(st, 'open_rth', None)
    if pdc is None or orth is None: return 0
    gap = orth - pdc
    if abs(gap) < st.gap_min: return 0
    # so entra se o preco ja andou um pouco na direcao do fade (confirmacao minima)
    st.gap_usou = True
    if gap > 0 and b['c'] < orth: return -1
    if gap < 0 and b['c'] > orth: return 1
    return 0


def sinal_on_range_fade(bars, i, st, dom_map):
    """Fade dos extremos do range overnight (Globex 18h ontem -> 9h30 hoje)
    durante o RTH: toca o topo ON e fecha abaixo -> short; toca o fundo e fecha
    acima -> long. Tolerancia de 5pt, filtro anti-chase de 15pt (igual REV)."""
    b = bars[i]; m = mins(b['dt'])
    if not (ENTRADA_INI <= m < ENTRADA_FIM): return 0
    hi = getattr(st, 'on_hi', None); lo = getattr(st, 'on_lo', None)
    if hi is None or lo is None: return 0
    tol = 5.0; maxd = 15.0
    if b['h'] >= hi - tol and b['c'] < hi and (hi - b['c']) <= maxd: return -1
    if b['l'] <= lo + tol and b['c'] > lo and (b['c'] - lo) <= maxd: return 1
    return 0


def sinal_rev_mais_on(bars, i, st, dom_map):
    """MESCLA: reversao PDH/PDL primeiro; se muda, tenta o fade do range
    overnight. Levels diferentes -> operam dias diferentes."""
    l = sinal_reversao(bars, i, st, dom_map)
    if l != 0: return l
    return sinal_on_range_fade(bars, i, st, dom_map)


SINAIS = {
    'REV': sinal_reversao,
    'GAPFADE': sinal_gap_fade,
    'ONFADE': sinal_on_range_fade,
    'REV+ON': sinal_rev_mais_on,
}


# ============================ motor 30d parametrizado ============================

def roda(bars, dom, fonte, meta, dd, n_contr, dd_mode='intraday',
         gap_min=20.0):
    pv = MNQ_PV * n_contr; rt = RT_PER * n_contr; slip = SLIP_BASE * TICK
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False
    realized = 0.0
    r_ini = 0.0; pico = 0.0; pico_eod = 0.0; dias = set(); ini = None
    pnl_d0 = 0.0; block = False; dia_k = None; th = 0
    st = Estado(); st.gap_min = gap_min
    # extras de estado p/ os sinais novos
    st.pd_close = None; st.open_rth = None; st.gap_usou = False
    st.on_hi = st.on_lo = None
    cur_rth_close = None; on_hi_acc = on_lo_acc = None
    res = []; trades = []
    sig = SINAIS[fonte]

    def fecha(p):
        nonlocal pos, realized
        if pos == 0: return
        realized += ((p - entry) * pos - 2 * slip) * pv - rt
        trades.append(realized); pos = 0

    def nova(dt):
        nonlocal r_ini, pico, pico_eod, dias, ini
        r_ini = realized; pico = 0.0; pico_eod = 0.0; dias = set(); ini = dt

    for i, b in enumerate(bars):
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d'); wd = dt.weekday()
        if ini is None: nova(dt)

        if d != st.dia:
            if st.cur_hi is not None: st.pd_hi, st.pd_lo = st.cur_hi, st.cur_lo
            # fecha o dia anterior p/ os sinais novos
            if cur_rth_close is not None: st.pd_close = cur_rth_close
            st.dia = d; st.cur_hi = st.cur_lo = None
            st.seg_hoje = dom[d] if (dom and wd == 0 and d in dom) else None
            st.open_rth = None; st.gap_usou = False
            # trava range overnight acumulado ate agora (18h ontem -> agora)
            st.on_hi = on_hi_acc; st.on_lo = on_lo_acc
            on_hi_acc = on_lo_acc = None

        # acumula range overnight: das 18:00 ET ate 9:30 ET
        if m >= 18*60 or m < ENTRADA_INI:
            on_hi_acc = b['h'] if on_hi_acc is None else max(on_hi_acc, b['h'])
            on_lo_acc = b['l'] if on_lo_acc is None else min(on_lo_acc, b['l'])

        if ENTRADA_INI <= m < 16*60:
            st.cur_hi = b['h'] if st.cur_hi is None else max(st.cur_hi, b['h'])
            st.cur_lo = b['l'] if st.cur_lo is None else min(st.cur_lo, b['l'])
            if st.open_rth is None: st.open_rth = b['o']
            cur_rth_close = b['c']

        if d != dia_k:
            # fecha o dia: atualiza pico EOD
            if dia_k is not None and dd_mode == 'eod':
                pico_eod = max(pico_eod, realized - r_ini)
            dia_k = d; pnl_d0 = realized; block = False; th = 0

        if pos != 0:
            saiu = False
            if pos > 0:
                if b['l'] <= stop: fecha(stop); saiu = True
                elif b['h'] >= target: fecha(target); saiu = True
            else:
                if b['h'] >= stop: fecha(stop); saiu = True
                elif b['l'] <= target: fecha(target); saiu = True
            if not saiu and pos != 0:
                if pos > 0:
                    fav = max(fav, b['h'])
                    if not be_done and (fav - entry) >= PTS_BE_TRIG:
                        stop = max(stop, entry + PTS_BE_LOCK); be_done = True
                    if be_done: stop = max(stop, fav - PTS_TRAIL)
                else:
                    fav = min(fav, b['l'])
                    if not be_done and (entry - fav) >= PTS_BE_TRIG:
                        stop = min(stop, entry - PTS_BE_LOCK); be_done = True
                    if be_done: stop = min(stop, fav + PTS_TRAIL)

        pr = realized - r_ini
        ua = uf = 0.0
        if pos > 0: ua = (b['l']-entry)*pv; uf = (b['h']-entry)*pv
        elif pos < 0: ua = (entry-b['h'])*pv; uf = (entry-b['l'])*pv

        # ---- modelo de drawdown ----
        if dd_mode == 'intraday':
            if pr + uf > pico: pico = pr + uf
            ref = pico
        elif dd_mode == 'eod':
            ref = max(pico_eod, 0.0)     # so o que fechou dia conta como pico
        else:  # static
            ref = 0.0

        if STOP_DIA > 0 and (realized - pnl_d0 + ua) <= -STOP_DIA:
            block = True
            if pos != 0: fecha(b['c'])

        decidiu = False
        if pr + ua <= ref - dd:
            fecha(b['c']); res.append(('ESTOUROU', (dt - ini).days)); decidiu = True
        elif pr >= meta and len(dias) >= MIN_DIAS:
            fecha(b['c']); res.append(('APROVOU', (dt - ini).days)); decidiu = True
        elif (dt - ini).days >= JANELA:
            fecha(b['c']); res.append(('EXPIROU', (dt - ini).days)); decidiu = True
        if decidiu: nova(dt)

        if m >= FLATTEN and pos != 0: fecha(b['c'])
        if not block and th < MAX_TRADES and pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
            lado = sig(bars, i, st, dom)
            if lado != 0:
                entry = b['c']; pos = lado; fav = entry; be_done = False
                stop = entry - lado * PTS_SL; target = entry + lado * TP
                dias.add(d); th += 1

    tot = len(res); ap = sum(1 for s, _ in res if s == 'APROVOU')
    es = sum(1 for s, _ in res if s == 'ESTOUROU'); ex = tot - ap - es
    dda = sorted(x for s, x in res if s == 'APROVOU')
    dmed = dda[len(dda)//2] if dda else 0
    n = len(trades)
    difs = [trades[k] - (trades[k-1] if k else 0.0) for k in range(n)]
    w = [x for x in difs if x > 0]
    gw = sum(w); gl = abs(sum(x for x in difs if x <= 0))
    return dict(taxa=100*ap/tot if tot else 0, ap=ap, es=es, ex=ex, tot=tot,
               dmed=dmed, n=n, wr=100*len(w)/n if n else 0,
               pf=gw/gl if gl else 99)


def pl(label, r):
    print(f"  {label:<40s} {r['taxa']:>4.0f}%  {r['ap']:>3}ap /{r['es']:>3}es /{r['ex']:>3}ex   "
          f"d{r['dmed']:<3} n={r['n']:<5} WR{r['wr']:>3.0f}% PF{r['pf']:>4.2f}")


if __name__ == '__main__':
    bars = carregar('NQ_dados'); dom = domingo_ranges(bars)
    meio = len(bars)//2; b1, b2 = bars[:meio], bars[meio:]
    dom1, dom2 = domingo_ranges(b1), domingo_ranges(b2)
    print(f"{len(bars):,} barras NQ 1min | {bars[0]['dt'].date()} -> {bars[-1]['dt'].date()}")
    print("motor 30d corridos | Max12/dia | slip 2t | gestao SL12,5/BE/trail1,75/alvo60\n")

    print("="*100)
    print("  (1) MESMA REVERSAO, conta maior — varrendo nro de contratos por tier Apex")
    print("      (DD intraday trailing, como a Apex de verdade)")
    print("="*100)
    for tier, (meta, dd) in TIERS.items():
        print(f"  --- Apex {tier}  (meta ${meta:,.0f} / DD trailing ${dd:,.0f}) ---")
        best = None
        for nc in (2, 3, 5, 8, 10, 14, 20):
            r = roda(bars, dom, 'REV', meta, dd, nc, dd_mode='intraday')
            pl(f'{nc} MNQ', r)
            if best is None or r['taxa'] > best[1]: best = (nc, r['taxa'])
        print()

    print("="*100)
    print("  (2) MESMA REVERSAO (Apex 25K, 5 MNQ) sob 3 MODELOS DE DRAWDOWN")
    print("      pergunta: o teto de ~50% e' da estrategia ou do DD trailing intradiario?")
    print("="*100)
    for mode, desc in [('intraday', 'Apex (trailing intradiario, conta lucro aberto)'),
                        ('eod', 'EOD trailing (pico so no fim do dia) — varias prop firms'),
                        ('static', 'DD fixo desde o inicio (Tradeify/MFFU opcao static)')]:
        r = roda(bars, dom, 'REV', 1500.0, 1000.0, 5, dd_mode=mode)
        pl(f'{desc}', r)
    print("  -- e o mesmo, mas com DD $2.000 (conta 50K-ish) em cada modelo --")
    for mode in ('intraday', 'eod', 'static'):
        r = roda(bars, dom, 'REV', 3000.0, 2000.0, 5, dd_mode=mode)
        pl(f'DD $2000 / meta $3000 / {mode}', r)

    print("\n" + "="*100)
    print("  (3) HIPOTESES NOVAS de entrada no proprio NQ (Apex 25K, 5 MNQ, DD intraday)")
    print("="*100)
    for gm in (15.0, 25.0, 40.0):
        r = roda(bars, dom, 'GAPFADE', 1500.0, 1000.0, 5, gap_min=gm)
        pl(f'GAP FADE abertura RTH (|gap|>={gm:.0f}pt)', r)
    r = roda(bars, dom, 'ONFADE', 1500.0, 1000.0, 5)
    pl('FADE range overnight (Globex) no RTH', r)

    print("\n" + "="*100)
    print("  (4) MESCLA reversao PDH/PDL + fade do range overnight, nos 3 modelos de DD")
    print("      (levels diferentes -> operam dias diferentes -> mais dias operados)")
    print("="*100)
    for mode in ('intraday', 'eod', 'static'):
        r = roda(bars, dom, 'REV+ON', 1500.0, 1000.0, 5, dd_mode=mode)
        pl(f'REV+ON / {mode}', r)

    print("\n" + "="*100)
    print("  (5) OOS das coisas que deram sinal de vida")
    print("="*100)
    def oos(label, fonte, meta, dd, nc, mode='intraday', gm=20.0):
        r1 = roda(b1, dom1, fonte, meta, dd, nc, dd_mode=mode, gap_min=gm)
        r2 = roda(b2, dom2, fonte, meta, dd, nc, dd_mode=mode, gap_min=gm)
        print(f"  {label:<40s} 1a:{r1['ap']:>3}ap/{r1['es']:>3}es({r1['taxa']:>3.0f}%)  "
              f"2a:{r2['ap']:>3}ap/{r2['es']:>3}es({r2['taxa']:>3.0f}%)")
    oos('REV 25K 5MNQ intraday (baseline)', 'REV', 1500, 1000, 5)
    oos('REV 50K 14MNQ intraday', 'REV', 3000, 2500, 14)
    oos('REV 25K 5MNQ EOD', 'REV', 1500, 1000, 5, mode='eod')
    oos('REV 25K 5MNQ static', 'REV', 1500, 1000, 5, mode='static')
    oos('REV+ON 25K 5MNQ intraday', 'REV+ON', 1500, 1000, 5)
    oos('REV+ON 25K 5MNQ EOD', 'REV+ON', 1500, 1000, 5, mode='eod')
    oos('REV+ON 25K 5MNQ static', 'REV+ON', 1500, 1000, 5, mode='static')
    print("="*100)
