#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VARREDURA DE SLIPPAGE REALISTA (23/06)
======================================
Pergunta do Marcelo (pos-pesquisa): nossos backtests rodam com slippage ZERO.
A comunidade (Reddit/forum NT8) recomenda 2-4 ticks de slippage no MNQ pra
aproximar backtest da realidade ao vivo. Quanto isso muda o resultado?

Engine = COPIA FIEL de run_diurna_noturna.py (config de producao combinada:
diurna Niveis + noturna canal 19-21h BR, conta 25K / 5 MNQ). UNICA diferenca:
parametro slip_ticks que piora CADA fill (entrada E saida) contra o trader.

MODELO DE SLIPPAGE (conservador e correto):
  - Entrada a mercado: preenche PIOR que o sinal (long entra + alto, short + baixo).
  - Saida a mercado (stop/trailing/alvo sintetico/flatten): preenche PIOR.
  - Cada trade paga 2x slip (entrada + saida).
  - 1 tick = 0.25pt. Com 5 MNQ ($10/pt): 1 tick = $2.50/trade de cada lado.
    -> 2 ticks de slip = $10/trade de atrito alem da comissao ($6).

Por que aplicar nos DOIS lados: no nosso bot ate o ALVO e saida sintetica a
mercado (fecha quando a barra cruza o nivel), nao ordem limite em repouso. Logo
o alvo TAMBEM desliza. Stops sempre deslizam contra. Modelo realista.

Roda: 0, 1, 2, 3, 4 ticks de slippage para SO DIURNA | SO NOTURNA | COMBINADO,
+ robustez OOS (1a metade x 2a metade) no nivel 2-ticks recomendado.
"""
import glob, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); BR = ZoneInfo('America/Sao_Paulo'); UTC = timezone.utc
MNQ_PV = 2.0; RT_PER = 1.20
META = 1500.0; DD = 1500.0; MIN_DIAS = 7
TICK = 0.25; N_CONTR = 5
PTS_SL = 12.5; PTS_BE_TRIG = 3.75; PTS_BE_LOCK = 2.5; PTS_TRAIL = 1.75

# --- DIURNA (config de producao) ---
TOL_TICKS = 20; TP = 60.0; MAX_DIST = 15.0
ENTRADA_INI = 9*60+30; ENTRADA_FIM = 16*60; FLATTEN = 16*60+55
STOP_DIA = 750.0

# --- NOTURNA (Nomads Noite) ---
NOITE_INI_BR = 19*60; NOITE_FIM_BR = 21*60
NOITE_WARMUP_BR = 19*60+15; NOITE_FLATTEN_BR = 22*60
FIB_VENDA = 0.764; FIB_COMPRA = 0.236
RANGE_MIN = 40.0          # canal minimo de PRODUCAO (CanalMinPontos=40 no .cs)
REJ_PAVIO = 0.5
REJ_DOJI = 0.3
GATILHO_BARRAS = 4
TP_NOITE = 60.0


def carregar(pasta):
    vistos = {}
    for f in sorted(glob.glob(os.path.join(pasta, '*.txt'))):
        with open(f, encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                line = line.strip()
                if not line: continue
                try:
                    dtp, rest = line.split(';', 1); data, hora = dtp.split()
                    o, h, l, c, v = rest.split(';')
                    dt = datetime(int(data[:4]), int(data[4:6]), int(data[6:8]),
                                  int(hora[:2]), int(hora[2:4]), tzinfo=UTC)
                    o, h, l, c, v = float(o), float(h), float(l), float(c), float(v)
                except Exception: continue
                h = max(h, o, c); l = min(l, o, c)
                if dt not in vistos:
                    vistos[dt] = (dt.astimezone(ET), dt.astimezone(BR), o, h, l, c, v)
    return [{'dt': vistos[k][0], 'br': vistos[k][1], 'o': vistos[k][2], 'h': vistos[k][3],
             'l': vistos[k][4], 'c': vistos[k][5], 'v': vistos[k][6]} for k in sorted(vistos)]


def mins(dt): return dt.hour*60 + dt.minute


def domingo_ranges(bars):
    from datetime import timedelta
    dom = {}
    for b in bars:
        dt = b['dt']; wd = dt.weekday(); m = mins(dt)
        if wd == 6 and m >= 18*60:
            seg = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
            if seg not in dom: dom[seg] = [b['h'], b['l']]
            else: dom[seg][0] = max(dom[seg][0], b['h']); dom[seg][1] = min(dom[seg][1], b['l'])
    return {k: tuple(v) for k, v in dom.items()}


def eh_rejeicao_alta(b):
    rng = b['h'] - b['l']
    if rng <= 0: return False
    corpo = abs(b['c'] - b['o']); pav_sup = b['h'] - max(b['o'], b['c'])
    return pav_sup >= REJ_PAVIO * rng or corpo <= REJ_DOJI * rng


def eh_rejeicao_baixa(b):
    rng = b['h'] - b['l']
    if rng <= 0: return False
    corpo = abs(b['c'] - b['o']); pav_inf = min(b['o'], b['c']) - b['l']
    return pav_inf >= REJ_PAVIO * rng or corpo <= REJ_DOJI * rng


def bt(bars, usar_diurna=True, usar_noturna=True, dom_map=None, sl_not=PTS_SL, tp_not=TP_NOITE,
       max_not=99, rng_min=RANGE_MIN, pular_dom=True, slip_ticks=0.0):
    """slip_ticks: ticks de slippage por LADO (entrada e saida). pular_dom=True = producao."""
    pv = MNQ_PV * N_CONTR; rt = RT_PER * N_CONTR
    slip = slip_ticks * TICK   # slippage em PONTOS, por lado
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False; origem = None
    realized = 0.0; trades = []
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None
    aprov = reprov = 0; d2a = []; pnl_d0 = 0.0; block = False; dia_k = None
    seg_hoje = None
    noite_dia = None; noite_hi = noite_lo = None; pend = None
    not_trades_dia = 0
    t_diur = []; t_not = []; trade_org = None

    def fecha(p):
        # Slippage: cada trade paga 2x slip (entrada+saida) SEMPRE contra o trader.
        # (p - entry)*pos - 2*slip  (porque pos^2=1; ver docstring do arquivo)
        nonlocal pos, realized
        if pos == 0: return
        g = ((p - entry) * pos - 2 * slip) * pv - rt
        realized += g; trades.append(g)
        if trade_org == 'D': t_diur.append(g)
        elif trade_org == 'N': t_not.append(g)
        pos = 0

    for b in bars:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d'); wd = dt.weekday()
        mbr = mins(b['br']); dbr = b['br'].strftime('%Y-%m-%d')

        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = cur_lo = None
            seg_hoje = dom_map[d] if (dom_map and wd == 0 and d in dom_map) else None
        if ENTRADA_INI <= m < 16*60:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
        if d != dia_k:
            dia_k = d; pnl_d0 = realized; block = False
        if ini_aval is None: ini_aval = dt

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
        if pos > 0: ua = (b['l'] - entry) * pv; uf = (b['h'] - entry) * pv
        elif pos < 0: ua = (entry - b['h']) * pv; uf = (entry - b['l']) * pv
        if pr + uf > pico: pico = pr + uf
        if STOP_DIA > 0 and (realized - pnl_d0 + ua) <= -STOP_DIA:
            block = True
            if pos != 0: fecha(b['c'])
        if pr + ua <= pico - DD:
            fecha(b['c']); reprov += 1; r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt
        elif pr >= META and len(dias) >= MIN_DIAS:
            fecha(b['c']); aprov += 1; d2a.append((dt - ini_aval).days)
            r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt

        if usar_diurna:
            if m >= FLATTEN and pos != 0 and origem == 'D':
                fecha(b['c'])
            if not block and pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
                niv_hi = seg_hoje[0] if seg_hoje else pd_hi
                niv_lo = seg_hoje[1] if seg_hoje else pd_lo
                if niv_hi is not None:
                    tol = TOL_TICKS * TICK; h, l, c = b['h'], b['l'], b['c']; lado = 0
                    if h >= niv_hi - tol and c < niv_hi:
                        if MAX_DIST == 0 or (niv_hi - c) <= MAX_DIST: lado = -1
                    elif l <= niv_lo + tol and c > niv_lo:
                        if MAX_DIST == 0 or (c - niv_lo) <= MAX_DIST: lado = 1
                    if lado != 0:
                        entry = c; pos = lado; fav = c; be_done = False; origem = 'D'; trade_org = 'D'
                        stop = c - lado * PTS_SL; target = c + lado * TP; dias.add(d)

        if usar_noturna:
            na_janela = (NOITE_INI_BR <= mbr < NOITE_FIM_BR
                         and not (pular_dom and b['br'].weekday() == 6))
            if na_janela:
                if dbr != noite_dia:
                    noite_dia = dbr; noite_hi = b['h']; noite_lo = b['l']; pend = None; not_trades_dia = 0
                else:
                    noite_hi = max(noite_hi, b['h']); noite_lo = min(noite_lo, b['l'])
            if mbr >= NOITE_FLATTEN_BR and pos != 0 and origem == 'N':
                fecha(b['c'])
            pode = (na_janela and mbr >= NOITE_WARMUP_BR and noite_hi is not None
                    and (noite_hi - noite_lo) >= rng_min)
            if pode and not block and not_trades_dia < max_not:
                rng = noite_hi - noite_lo
                z_venda = noite_lo + FIB_VENDA * rng
                z_compra = noite_lo + FIB_COMPRA * rng
                if pos == 0 and pend is not None:
                    lado, nivel, rest = pend
                    if lado == -1 and b['l'] <= nivel:
                        entry = min(nivel, b['o']); pos = -1; fav = entry; be_done = False
                        origem = 'N'; trade_org = 'N'; not_trades_dia += 1
                        stop = entry + sl_not; target = entry - tp_not; dias.add(d); pend = None
                    elif lado == 1 and b['h'] >= nivel:
                        entry = max(nivel, b['o']); pos = 1; fav = entry; be_done = False
                        origem = 'N'; trade_org = 'N'; not_trades_dia += 1
                        stop = entry - sl_not; target = entry + tp_not; dias.add(d); pend = None
                    else:
                        rest -= 1; pend = None if rest <= 0 else (lado, nivel, rest)
                if pos == 0 and pend is None:
                    if b['h'] >= z_venda and eh_rejeicao_alta(b):
                        pend = (-1, b['l'], GATILHO_BARRAS)
                    elif b['l'] <= z_compra and eh_rejeicao_baixa(b):
                        pend = (1, b['h'], GATILHO_BARRAS)
            elif not na_janela:
                pend = None

    if pos != 0: fecha(bars[-1]['c'])

    def stats(ts):
        w = [t for t in ts if t > 0]; n = len(ts)
        gw = sum(w); gl = abs(sum(t for t in ts if t <= 0))
        return {'n': n, 'wr': 100*len(w)/n if n else 0,
                'pf': gw/gl if gl > 0 else (99 if gw > 0 else 0), 'net': sum(ts)}

    g = stats(trades); tot = aprov + reprov
    ds = sorted(d2a); med = ds[len(ds)//2] if ds else 0
    g.update({'aprov': aprov, 'reprov': reprov, 'tot': tot,
              'taxa': 100*aprov/tot if tot else 0,
              'dmediana': med, 'trd_dia': g['n']/220,
              'diur': stats(t_diur), 'not': stats(t_not)})
    return g


def linha(label, r):
    print(f"  {label:>16s} {r['taxa']:>4.0f}% {r['aprov']:>4}/{r['tot']:<3} {r['dmediana']:>4.0f}d "
          f"{r['n']:>5} {r['trd_dia']:>5.1f} {r['wr']:>3.0f}% {r['pf']:>5.2f} {r['net']:>10,.0f}")


if __name__ == '__main__':
    print("Carregando NQ 1-min real..."); bars = carregar('NQ_dados')
    dom = domingo_ranges(bars)
    meio = bars[len(bars)//2]['dt']
    b1 = [b for b in bars if b['dt'] < meio]; b2 = [b for b in bars if b['dt'] >= meio]
    print(f"{len(bars):,} barras | conta 25K / 5 MNQ | meta ${META:.0f} DD ${DD:.0f}")
    print(f"Config PRODUCAO: canal>=40pt, pular domingo, SL 12.5 / TP 60 / trail 1.75")
    print(f"1 tick = 0.25pt = ${TICK*MNQ_PV*N_CONTR:.2f}/trade por lado (5 MNQ)\n")

    SLIP_GRID = [0.0, 1.0, 2.0, 3.0, 4.0]

    print("=" * 84)
    print("  IMPACTO DA SLIPPAGE — config de producao (canal>=40, pula domingo)")
    print("=" * 84)
    print(f"  {'cenario':>16s} {'taxa':>5s} {'aprov':>8s} {'d.med':>5s} {'trds':>5s} "
          f"{'t/dia':>5s} {'WR':>4s} {'PF':>6s} {'PnL$/ano':>10s}")

    for slip in SLIP_GRID:
        print("-" * 84)
        print(f"  >>> SLIPPAGE = {slip:.0f} tick(s) ({slip*TICK:.2f}pt/lado = "
              f"${slip*TICK*MNQ_PV*N_CONTR*2:.0f}/trade ida+volta)")
        rd = bt(bars, True, False, dom, slip_ticks=slip)
        rn = bt(bars, False, True, dom, slip_ticks=slip)
        rc = bt(bars, True, True, dom, slip_ticks=slip)
        linha("SO DIURNA", rd)
        linha("SO NOTURNA", rn)
        linha("COMBINADO", rc)
    print("=" * 84)

    print("\n" + "=" * 84)
    print("  ROBUSTEZ OOS no nivel RECOMENDADO (2 ticks) — 1a metade | 2a metade")
    print("=" * 84)
    for label, ud, un in [("SO DIURNA", True, False), ("SO NOTURNA", False, True),
                          ("COMBINADO", True, True)]:
        r1 = bt(b1, ud, un, dom, slip_ticks=2.0); r2 = bt(b2, ud, un, dom, slip_ticks=2.0)
        print(f"  {label:>12s}  {r1['aprov']:>2}/{r1['tot']:<2} ({r1['taxa']:>3.0f}%) PF {r1['pf']:>4.2f} "
              f"med {r1['dmediana']:>3.0f}d  |  {r2['aprov']:>2}/{r2['tot']:<2} ({r2['taxa']:>3.0f}%) "
              f"PF {r2['pf']:>4.2f} med {r2['dmediana']:>3.0f}d")
    print("=" * 84)

    print("\n  RESUMO: compare a coluna PnL$/ano de 0 vs 2 vs 4 ticks acima.")
    print("  Se a taxa de aprovacao aguenta 2-3 ticks, o bot e robusto pra operar ao vivo.")
    print("  Se desaba ja em 1-2 ticks, o backtest estava otimista demais.\n")
