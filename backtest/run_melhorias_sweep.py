#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VARREDURA DAS MELHORIAS FALTANTES (23/06)
=========================================
Pedido do Marcelo: testar TODAS as sugestoes que dao pra medir, p/ saber o que
vale implementar e o que e furada (igual o news filter). Tudo DIURNA-ONLY
(noturna desligada) + SLIPPAGE 2 TICKS (baseline realista).

Itens medidos:
  #7  DD real (1000 vs 1500) x stop diario (500/750/1000)  -> a realidade da conta
  #4  MaxTradesDia (0/6/8/10/12)                           -> corta overtrading?
  #5  Regra de consistencia 50% Apex 4.0                   -> nossas aprovacoes valem?
  #6  Conta $50K (DD 2000 / meta 3000) vs $25K             -> conta maior aprova +?

Itens NAO medidos aqui:
  #8 ORB = estrategia nova (ver optimize_orb.py)   #9 MCL = sem dados de crude
  #3 VPS = infra (nao e backtest)

REGRA DE CONSISTENCIA (Apex 4.0): nenhum dia pode ser > 50% do lucro total. Aqui
medimos, em cada ciclo que APROVOU, se o melhor dia passou de 50% do lucro do ciclo
-> se passou, aquela aprovacao NAO valeria de verdade. Mostra aprov "naive" vs "valida".
"""
import glob, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
MNQ_PV = 2.0; RT_PER = 1.20
MIN_DIAS = 7
TICK = 0.25
PTS_SL = 12.5; PTS_BE_TRIG = 3.75; PTS_BE_LOCK = 2.5; PTS_TRAIL = 1.75
TOL_TICKS = 20; TP = 60.0; MAX_DIST = 15.0
ENTRADA_INI = 9*60+30; ENTRADA_FIM = 16*60; FLATTEN = 16*60+55
SLIP_BASE = 2.0
CONSIST = 0.50   # limite de consistencia Apex 4.0 (50%)


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


def bt(bars, dom_map=None, meta=1500.0, dd=1500.0, stop_dia=750.0,
       max_trades=0, slip_ticks=SLIP_BASE, n_contr=5):
    """DIURNA only. Rastreia consistencia 50% por ciclo de aprovacao."""
    pv = MNQ_PV * n_contr; rt = RT_PER * n_contr
    slip = slip_ticks * TICK
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False
    realized = 0.0; trades = []
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None
    aprov = reprov = 0; d2a = []; pnl_d0 = 0.0; block = False; dia_k = None
    seg_hoje = None; trades_hoje = 0
    cycle_days = {}            # dia -> pnl realizado no ciclo atual (p/ consistencia)
    aprov_valida = 0; ratios = []   # consistencia: aprovacoes que passam no 50%

    def fecha(p, d):
        nonlocal pos, realized
        if pos == 0: return
        g = ((p - entry) * pos - 2 * slip) * pv - rt
        realized += g; trades.append(g)
        cycle_days[d] = cycle_days.get(d, 0.0) + g
        pos = 0

    def checa_consist(total):
        # melhor dia POSITIVO vs lucro total do ciclo
        if total <= 0: return False, 1.0
        pos_days = [v for v in cycle_days.values() if v > 0]
        if not pos_days: return False, 1.0
        biggest = max(pos_days)
        ratio = biggest / total
        return ratio <= CONSIST, ratio

    for b in bars:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d'); wd = dt.weekday()

        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = cur_lo = None
            seg_hoje = dom_map[d] if (dom_map and wd == 0 and d in dom_map) else None
        if ENTRADA_INI <= m < 16*60:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
        if d != dia_k:
            dia_k = d; pnl_d0 = realized; block = False; trades_hoje = 0
        if ini_aval is None: ini_aval = dt

        if pos != 0:
            saiu = False
            if pos > 0:
                if b['l'] <= stop: fecha(stop, d); saiu = True
                elif b['h'] >= target: fecha(target, d); saiu = True
            else:
                if b['h'] >= stop: fecha(stop, d); saiu = True
                elif b['l'] <= target: fecha(target, d); saiu = True
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
        if stop_dia > 0 and (realized - pnl_d0 + ua) <= -stop_dia:
            block = True
            if pos != 0: fecha(b['c'], d)
        if pr + ua <= pico - dd:
            fecha(b['c'], d); reprov += 1
            r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt; cycle_days = {}
        elif pr >= meta and len(dias) >= MIN_DIAS:
            fecha(b['c'], d); aprov += 1
            ok, ratio = checa_consist(realized - r_ini)
            if ok: aprov_valida += 1
            ratios.append(ratio)
            d2a.append((dt - ini_aval).days)
            r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt; cycle_days = {}

        if m >= FLATTEN and pos != 0:
            fecha(b['c'], d)
        # entrada diurna (respeita limite de trades/dia)
        lim_ok = (max_trades == 0 or trades_hoje < max_trades)
        if not block and lim_ok and pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
            niv_hi = seg_hoje[0] if seg_hoje else pd_hi
            niv_lo = seg_hoje[1] if seg_hoje else pd_lo
            if niv_hi is not None:
                tol = TOL_TICKS * TICK; h, l, c = b['h'], b['l'], b['c']; lado = 0
                if h >= niv_hi - tol and c < niv_hi:
                    if MAX_DIST == 0 or (niv_hi - c) <= MAX_DIST: lado = -1
                elif l <= niv_lo + tol and c > niv_lo:
                    if MAX_DIST == 0 or (c - niv_lo) <= MAX_DIST: lado = 1
                if lado != 0:
                    entry = c; pos = lado; fav = c; be_done = False
                    stop = c - lado * PTS_SL; target = c + lado * TP
                    dias.add(d); trades_hoje += 1

    if pos != 0: fecha(bars[-1]['c'], dia)

    w = [t for t in trades if t > 0]; n = len(trades)
    gw = sum(w); gl = abs(sum(t for t in trades if t <= 0))
    tot = aprov + reprov; ds = sorted(d2a); med = ds[len(ds)//2] if ds else 0
    avg_ratio = sum(ratios)/len(ratios) if ratios else 0
    max_ratio = max(ratios) if ratios else 0
    return {'n': n, 'wr': 100*len(w)/n if n else 0, 'pf': gw/gl if gl > 0 else 99,
            'net': sum(trades), 'aprov': aprov, 'reprov': reprov, 'tot': tot,
            'taxa': 100*aprov/tot if tot else 0, 'dmediana': med,
            'aprov_valida': aprov_valida,
            'taxa_valida': 100*aprov_valida/tot if tot else 0,
            'avg_ratio': avg_ratio, 'max_ratio': max_ratio,
            'trd_dia': n/220}


def linha(label, r):
    print(f"  {label:>28s} {r['taxa']:>4.0f}% {r['aprov']:>3}/{r['tot']:<3} {r['dmediana']:>4.0f}d "
          f"{r['n']:>5} {r['trd_dia']:>4.1f} {r['wr']:>3.0f}% {r['pf']:>5.2f} {r['net']:>9,.0f}")


if __name__ == '__main__':
    print("Carregando NQ 1-min real..."); bars = carregar('NQ_dados')
    dom = domingo_ranges(bars)
    print(f"{len(bars):,} barras | DIURNA only | slippage {SLIP_BASE:.0f} ticks | 5 MNQ\n")
    H = f"  {'cenario':>28s} {'taxa':>5s} {'aprov':>7s} {'d.med':>5s} {'trds':>5s} {'t/d':>4s} {'WR':>4s} {'PF':>5s} {'PnL$':>9s}"

    # ===== #7 — DD REAL x STOP DIARIO =====
    print("=" * 92)
    print("  #7 — REALIDADE DA CONTA: drawdown (DD) x stop diario (com slippage 2 ticks)")
    print("=" * 92); print(H); print("-" * 92)
    cfgs = [
        ("DD1500 / stop750 (baseline atual)", 1500, 750),
        ("DD1500 / stop500", 1500, 500),
        ("DD1000 / stop750 (DD real EOD)", 1000, 750),
        ("DD1000 / stop500 (real + stop curto)", 1000, 500),
        ("DD1000 / stop1000", 1000, 1000),
    ]
    for lbl, dd, sd in cfgs:
        linha(lbl, bt(bars, dom, meta=1500.0, dd=dd, stop_dia=sd))
    print("=" * 92)
    print("  >> Se DD1000 derruba a taxa vs DD1500, a conta EOD e mais dificil que o backtest assumia.\n")

    # ===== #4 — MAX TRADES/DIA (na config real DD1000/stop750) =====
    print("=" * 92)
    print("  #4 — LIMITE DE TRADES/DIA (corta overtrading?) — base DD1000 / stop750")
    print("=" * 92); print(H); print("-" * 92)
    for mt in [0, 6, 8, 10, 12]:
        lbl = "sem limite (atual)" if mt == 0 else f"max {mt} trades/dia"
        linha(lbl, bt(bars, dom, meta=1500.0, dd=1000, stop_dia=750, max_trades=mt))
    print("=" * 92)
    print("  >> Se um limite SOBE ou empata a taxa cortando trades, vale (menos exposicao).\n")

    # ===== #5 — CONSISTENCIA 50% =====
    print("=" * 92)
    print("  #5 — REGRA DE CONSISTENCIA 50% (Apex 4.0) — nossas aprovacoes valem?")
    print("=" * 92)
    print(f"  {'cenario':>28s} {'aprov':>6s} {'valida50%':>10s} {'taxa_val':>9s} "
          f"{'pior dia%':>9s} {'media dia%':>10s}")
    print("-" * 92)
    for lbl, dd, sd in [("DD1500 / stop750", 1500, 750), ("DD1000 / stop750", 1000, 750)]:
        r = bt(bars, dom, meta=1500.0, dd=dd, stop_dia=sd)
        print(f"  {lbl:>28s} {r['aprov']:>4}   {r['aprov_valida']:>6}     "
              f"{r['taxa_valida']:>6.0f}%   {r['max_ratio']*100:>6.0f}%    {r['avg_ratio']*100:>7.0f}%")
    print("=" * 92)
    print("  >> 'valida50%' = aprovacoes onde NENHUM dia passou de 50% do lucro. Se for << aprov,")
    print("     o bot concentra lucro em poucos dias e violaria a consistencia da Apex.\n")

    # ===== #6 — CONTA $50K =====
    print("=" * 92)
    print("  #6 — CONTA $50K (DD2000 / meta3000) vs $25K — vale a conta maior?")
    print("=" * 92); print(H); print("-" * 92)
    linha("$25K DD1000 meta1500 (5MNQ)", bt(bars, dom, meta=1500, dd=1000, stop_dia=750, n_contr=5))
    linha("$50K DD2000 meta3000 (5MNQ)", bt(bars, dom, meta=3000, dd=2000, stop_dia=750, n_contr=5))
    linha("$50K DD2000 meta3000 (10MNQ)", bt(bars, dom, meta=3000, dd=2000, stop_dia=1500, n_contr=10))
    print("=" * 92)
    print("  >> $50K com 5 MNQ = mais gordura, meta 2x (demora +). 10 MNQ = escala risco junto.")
    print("     Compare taxa de aprovacao e dias-mediana p/ ver se compensa.\n")
