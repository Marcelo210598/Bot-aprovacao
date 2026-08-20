#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FILTROS DE QUALIDADE DE ENTRADA (20/08) — teste isolado de 2 achados do
diagnostico_mfe_mae.py: (1) dist_nivel mais apertado, (2) so operar sexta-feira.

Motor reaproveitado de run_melhorias_sweep.py (DD real $1000, MaxTradesDia,
slippage 2 ticks, nivel de domingo, consistencia Apex 4.0) -- config atual de
producao (MaxTradesDia=12) como baseline fixo. NAO e' otimizacao: testa cada
filtro ISOLADO contra o baseline, ano inteiro + OOS (1a metade x 2a metade).
"""
import glob, os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
MNQ_PV = 2.0; RT_PER = 1.20
MIN_DIAS = 7
TICK = 0.25
PTS_SL = 12.5; PTS_BE_TRIG = 3.75; PTS_BE_LOCK = 2.5; PTS_TRAIL = 1.75
TOL_TICKS = 20; TP = 60.0
ENTRADA_INI = 9*60+30; ENTRADA_FIM = 16*60; FLATTEN = 16*60+55
SLIP_BASE = 2.0
CONSIST = 0.50


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
    dom = {}
    for b in bars:
        dt = b['dt']; wd = dt.weekday(); m = mins(dt)
        if wd == 6 and m >= 18*60:
            seg = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
            if seg not in dom: dom[seg] = [b['h'], b['l']]
            else: dom[seg][0] = max(dom[seg][0], b['h']); dom[seg][1] = min(dom[seg][1], b['l'])
    return {k: tuple(v) for k, v in dom.items()}


def bt(bars, dom_map=None, meta=1500.0, dd=1000.0, stop_dia=750.0,
       max_trades=12, slip_ticks=SLIP_BASE, n_contr=5, max_dist=15.0, only_dow=None):
    """DIURNA only. max_dist: filtro de proximidade (pt). only_dow: set de
    weekdays permitidos p/ ENTRAR (None = todos; {4} = so sexta)."""
    pv = MNQ_PV * n_contr; rt = RT_PER * n_contr
    slip = slip_ticks * TICK
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False
    realized = 0.0; trades = []
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None
    aprov = reprov = 0; d2a = []; pnl_d0 = 0.0; block = False; dia_k = None
    seg_hoje = None; trades_hoje = 0
    cycle_days = {}
    aprov_valida = 0; ratios = []

    def fecha(p, d):
        nonlocal pos, realized
        if pos == 0: return
        g = ((p - entry) * pos - 2 * slip) * pv - rt
        realized += g; trades.append(g)
        cycle_days[d] = cycle_days.get(d, 0.0) + g
        pos = 0

    def checa_consist(total):
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
        lim_ok = (max_trades == 0 or trades_hoje < max_trades)
        dow_ok = (only_dow is None or wd in only_dow)
        if not block and lim_ok and dow_ok and pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
            niv_hi = seg_hoje[0] if seg_hoje else pd_hi
            niv_lo = seg_hoje[1] if seg_hoje else pd_lo
            if niv_hi is not None:
                tol = TOL_TICKS * TICK; h, l, c = b['h'], b['l'], b['c']; lado = 0
                if h >= niv_hi - tol and c < niv_hi:
                    if max_dist == 0 or (niv_hi - c) <= max_dist: lado = -1
                elif l <= niv_lo + tol and c > niv_lo:
                    if max_dist == 0 or (c - niv_lo) <= max_dist: lado = 1
                if lado != 0:
                    entry = c; pos = lado; fav = c; be_done = False
                    stop = c - lado * PTS_SL; target = c + lado * TP
                    dias.add(d); trades_hoje += 1

    if pos != 0: fecha(bars[-1]['c'], dia)

    w = [t for t in trades if t > 0]; n = len(trades)
    gw = sum(w); gl = abs(sum(t for t in trades if t <= 0))
    tot = aprov + reprov; ds = sorted(d2a); med = ds[len(ds)//2] if ds else 0
    return {'n': n, 'wr': 100*len(w)/n if n else 0, 'pf': gw/gl if gl > 0 else 99,
            'net': sum(trades), 'aprov': aprov, 'reprov': reprov, 'tot': tot,
            'taxa': 100*aprov/tot if tot else 0, 'dmediana': med,
            'trd_dia': n/220}


def linha(label, r):
    print(f"  {label:>26s} {r['taxa']:>4.0f}% {r['aprov']:>3}/{r['tot']:<3} {r['dmediana']:>4.0f}d "
          f"{r['n']:>5} {r['trd_dia']:>4.1f} {r['wr']:>3.0f}% {r['pf']:>5.2f} {r['net']:>9,.0f}")


if __name__ == '__main__':
    print("Carregando NQ 1-min real..."); bars = carregar('NQ_dados')
    dom = domingo_ranges(bars)
    meio = bars[len(bars)//2]['dt']
    b1 = [b for b in bars if b['dt'] < meio]; b2 = [b for b in bars if b['dt'] >= meio]
    dom1 = domingo_ranges(b1); dom2 = domingo_ranges(b2)
    print(f"{len(bars):,} barras | DIURNA only | slippage 2t | 5 MNQ | DD real $1000 | MaxTradesDia=12\n")
    H = f"  {'cenario':>26s} {'taxa':>5s} {'aprov':>7s} {'d.med':>5s} {'trds':>5s} {'t/d':>4s} {'WR':>4s} {'PF':>5s} {'PnL$':>9s}"

    print("=" * 90)
    print("  FILTRO 1 — dist_nivel mais apertado (baseline max_dist=15pt)")
    print("=" * 90); print(H); print("-" * 90)
    cfgs_dist = [("max_dist=15 (ATUAL)", 15.0), ("max_dist=10", 10.0), ("max_dist=5", 5.0)]
    for lbl, md in cfgs_dist:
        linha(lbl, bt(bars, dom, max_dist=md))
    print("-" * 90)
    print("  OOS (1a metade x 2a metade):")
    for lbl, md in cfgs_dist:
        r1 = bt(b1, dom1, max_dist=md); r2 = bt(b2, dom2, max_dist=md)
        print(f"  {lbl:>26s}  1a: {r1['aprov']:>2}/{r1['tot']:<3}({r1['taxa']:>3.0f}%) PF{r1['pf']:>5.2f} "
              f"med{r1['dmediana']:>3.0f}d   2a: {r2['aprov']:>2}/{r2['tot']:<3}({r2['taxa']:>3.0f}%) PF{r2['pf']:>5.2f} med{r2['dmediana']:>3.0f}d")
    print("=" * 90 + "\n")

    print("=" * 90)
    print("  FILTRO 2 — so operar sexta-feira (dow=4)")
    print("=" * 90); print(H); print("-" * 90)
    cfgs_dow = [("todos os dias (ATUAL)", None), ("so sexta", {4}), ("sem sexta (controle)", {0,1,2,3})]
    for lbl, dw in cfgs_dow:
        linha(lbl, bt(bars, dom, only_dow=dw))
    print("-" * 90)
    print("  OOS (1a metade x 2a metade):")
    for lbl, dw in cfgs_dow:
        r1 = bt(b1, dom1, only_dow=dw); r2 = bt(b2, dom2, only_dow=dw)
        print(f"  {lbl:>26s}  1a: {r1['aprov']:>2}/{r1['tot']:<3}({r1['taxa']:>3.0f}%) PF{r1['pf']:>5.2f} "
              f"med{r1['dmediana']:>3.0f}d   2a: {r2['aprov']:>2}/{r2['tot']:<3}({r2['taxa']:>3.0f}%) PF{r2['pf']:>5.2f} med{r2['dmediana']:>3.0f}d")
    print("=" * 90)
