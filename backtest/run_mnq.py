#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Estrategia 94 (Niveis 25K) rodada no MNQ (Micro Nasdaq) com os dados reais de NQ.
MNQ = 1/10 do NQ -> valor do ponto = $2 (NQ = $20). Mesmo grafico, mesmo sinal.
A estrategia em PONTOS e identica a vencedora; so muda o tamanho do contrato.
Varremos o numero de contratos MNQ (1..10) p/ achar o sizing ideal numa conta 25K.

  10 MNQ == 1 NQ (sanity check: deve reproduzir os ~94% do NQ, com custo um pouco maior).
"""
import glob, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc

# --- contrato MNQ ---
MNQ_PV = 2.0            # $/ponto por contrato MNQ (NQ = 20)
RT_PER = 1.20          # custo round-turn por contrato MNQ (comissao + slippage estimado)

# --- conta Apex 25K (em dolares, independe do instrumento) ---
META = 1500.0; DD = 1500.0; MIN_DIAS = 7
TICK = 0.25

# --- estrategia 94 EM PONTOS (config vencedora do NQ) ---
PTS_TP = 25.0          # alvo  (500/20)
PTS_SL = 12.5          # stop  (250/20)
PTS_BE_TRIG = 3.75     # gatilho breakeven (75/20)
PTS_BE_LOCK = 2.5      # trava breakeven   (50/20)
PTS_TRAIL = 1.75       # trailing          (35/20)
PTS_STOP_DIA = 37.5    # stop diario       (750/20)
MAX_TRADES = 3


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
                if dt not in vistos: vistos[dt] = (dt.astimezone(ET), o, h, l, c, v)
    return [{'dt': vistos[k][0], 'o': vistos[k][1], 'h': vistos[k][2],
             'l': vistos[k][3], 'c': vistos[k][4], 'v': vistos[k][5]} for k in sorted(vistos)]


def mins(dt): return dt.hour*60 + dt.minute


def bt(bars, n_contr):
    """Roda a estrategia 94 no MNQ com n_contr contratos. P&L = pontos * MNQ_PV * n_contr."""
    pv = MNQ_PV * n_contr            # $/ponto da posicao
    rt = RT_PER * n_contr            # custo round-turn da posicao
    stop_dia = PTS_STOP_DIA * pv     # stop diario em $ (escala com sizing)
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False
    realized = 0.0; trades = []
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None
    aprov = reprov = 0; d2a = []; pnl_d0 = 0.0; block = False; dia_k = None; trades_dia = 0

    def fecha(p):
        nonlocal pos, realized
        if pos == 0: return
        pnl = (p-entry)*pos*pv - rt
        realized += pnl; trades.append(pnl); pos = 0

    for b in bars:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d')
        sess = 9*60+30 <= m < 16*60
        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = cur_lo = None
        if sess:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
        if d != dia_k: dia_k = d; pnl_d0 = realized; block = False; trades_dia = 0
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
                    if not be_done and (fav-entry) >= PTS_BE_TRIG: stop = max(stop, entry+PTS_BE_LOCK); be_done = True
                    if be_done: stop = max(stop, fav-PTS_TRAIL)
                else:
                    fav = min(fav, b['l'])
                    if not be_done and (entry-fav) >= PTS_BE_TRIG: stop = min(stop, entry-PTS_BE_LOCK); be_done = True
                    if be_done: stop = min(stop, fav+PTS_TRAIL)
        pr = realized - r_ini
        ua = uf = 0.0
        if pos > 0: ua = (b['l']-entry)*pv; uf = (b['h']-entry)*pv
        elif pos < 0: ua = (entry-b['h'])*pv; uf = (entry-b['l'])*pv
        if pr+uf > pico: pico = pr+uf
        if stop_dia > 0 and (realized - pnl_d0 + ua) <= -stop_dia:
            block = True
            if pos != 0: fecha(b['c'])
        if pr+ua <= pico - DD:
            fecha(b['c']); reprov += 1; r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt
        elif pr >= META and len(dias) >= MIN_DIAS:
            fecha(b['c']); aprov += 1; d2a.append((dt-ini_aval).days)
            r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt
        if m >= 15*60+55:
            if pos != 0: fecha(b['c'])
            continue
        if not block and pos == 0 and trades_dia < MAX_TRADES and 9*60+30 <= m < 15*60 and pd_hi is not None:
            tol = 6*TICK; h, l, c = b['h'], b['l'], b['c']; lado = 0
            if h >= pd_hi-tol and c < pd_hi: lado = -1
            elif l <= pd_lo+tol and c > pd_lo: lado = 1
            if lado != 0:
                entry = c; pos = lado; fav = c; be_done = False
                stop = c - lado*PTS_SL; target = c + lado*PTS_TP; dias.add(d); trades_dia += 1
    if pos != 0: fecha(bars[-1]['c'])

    wins = [t for t in trades if t > 0]; losses = [t for t in trades if t <= 0]
    n = len(trades); tot = aprov+reprov
    gw = sum(wins); gl = abs(sum(losses))
    return {'n': n, 'wr': 100*len(wins)/n if n else 0, 'pf': (gw/gl if gl > 0 else 99),
            'net': sum(trades), 'aprov': aprov, 'reprov': reprov, 'tot': tot,
            'taxa': 100*aprov/tot if tot else 0,
            'd2a': sum(d2a)/len(d2a) if d2a else 0,
            'avg_win': sum(wins)/len(wins) if wins else 0,
            'avg_loss': sum(losses)/len(losses) if losses else 0,
            'exp': sum(trades)/n if n else 0}


if __name__ == '__main__':
    print("Carregando NQ 1-min real (mesmo grafico do MNQ)...")
    bars = carregar('NQ_dados')
    print(f"{len(bars):,} barras\n")
    meio = bars[len(bars)//2]['dt']
    b1 = [b for b in bars if b['dt'] < meio]; b2 = [b for b in bars if b['dt'] >= meio]

    print("="*92)
    print("  ESTRATEGIA 94 NO MNQ (Micro Nasdaq, $2/ponto) — conta Apex 25K")
    print(f"  Custo {RT_PER}/contrato RT | meta ${META:,.0f} | DD ${DD:,.0f} | mesmo sinal do NQ")
    print("="*92)
    print(f"  {'MNQ':>4s} {'risco/trd':>9s} {'trades':>6s} {'WR':>5s} {'PF':>5s} "
          f"{'PnL$/ano':>9s} {'aprov':>6s} {'reprov':>7s} {'taxa':>6s} {'dias/aprov':>10s}")
    print("-"*92)
    for nc in (1, 2, 3, 5, 7, 10):
        r = bt(bars, nc)
        risco = PTS_SL * MNQ_PV * nc   # perda max por trade ($)
        print(f"  {nc:>4} {('$'+format(risco,',.0f')):>9s} {r['n']:>6} {r['wr']:>4.0f}% "
              f"{r['pf']:>5.2f} {r['net']:>9,.0f} {r['aprov']:>6} {r['reprov']:>7} "
              f"{r['taxa']:>5.0f}% {r['d2a']:>9.0f}d")
    print("-"*92)

    print("\n  DETALHE + ROBUSTEZ (out-of-sample) por sizing:")
    for nc in (3, 5, 7, 10):
        r = bt(bars, nc); r1 = bt(b1, nc); r2 = bt(b2, nc)
        print(f"\n  --- {nc} MNQ (risco ${PTS_SL*MNQ_PV*nc:,.0f}/trade) ---")
        print(f"    Ano inteiro: {r['aprov']}/{r['tot']} ({r['taxa']:.0f}%) | "
              f"WR {r['wr']:.0f}% | PF {r['pf']:.2f} | PnL ${r['net']:,.0f} | "
              f"ganho medio ${r['avg_win']:,.0f} / perda ${r['avg_loss']:,.0f} | exp ${r['exp']:,.1f}/trade")
        print(f"    1a metade:   {r1['aprov']}/{r1['tot']} ({r1['taxa']:.0f}%) | PF {r1['pf']:.2f}")
        print(f"    2a metade:   {r2['aprov']}/{r2['tot']} ({r2['taxa']:.0f}%) | PF {r2['pf']:.2f}")
    print("="*92)
