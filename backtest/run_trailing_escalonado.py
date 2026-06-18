#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TRAILING ESCALONADO (18/06) — ideia do Marcelo: "cavalgar a alta".
Apertado no comeco (protege o win, igual hoje); quando o lucro passa de P_LOOSE pt,
ALARGA o trailing pra W_LOOSE pt -> deixa o trade correr ate 50/80 e trava progressivo.

Compara com baseline (trail fixo 1,75). Engine = identica a run_segunda_domingo.py
(producao, modo DOM-NOITE): 5 MNQ, tol 20t, chase 15pt, stop 12,5, alvo 60, stop/dia $750.
So muda a regra de trailing apos o breakeven.
"""
import glob, os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
MNQ_PV = 2.0; RT_PER = 1.20
META = 1500.0; DD = 1500.0; MIN_DIAS = 7
TICK = 0.25; N_CONTR = 5
PTS_SL = 12.5; PTS_BE_TRIG = 3.75; PTS_BE_LOCK = 2.5; PTS_TRAIL = 1.75
TOL_TICKS = 20; TP = 60.0; MAX_DIST = 15.0
ENTRADA_FIM = 16*60; FLATTEN = 16*60+55; ENTRADA_INI = 9*60+30
STOP_DIA = 750.0


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


def bt(bars, dom_map, p_loose=None, w_loose=None):
    """p_loose/w_loose = None -> baseline (trail fixo 1,75).
    senao: enquanto lucro<p_loose usa trail 1,75; lucro>=p_loose usa trail w_loose (mais largo)."""
    pv = MNQ_PV * N_CONTR; rt = RT_PER * N_CONTR
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False
    realized = 0.0; trades = []
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None
    aprov = reprov = 0; d2a = []; pnl_d0 = 0.0; block = False; dia_k = None
    seg_hoje = None

    def fecha(p):
        nonlocal pos, realized
        if pos == 0: return
        g = (p - entry) * pos * pv - rt
        realized += g; trades.append(g); pos = 0

    def tdist(profit_pts):
        if p_loose is None: return PTS_TRAIL
        return w_loose if profit_pts >= p_loose else PTS_TRAIL

    for b in bars:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d'); wd = dt.weekday()
        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = cur_lo = None
            seg_hoje = dom_map[d] if (wd == 0 and d in dom_map) else None
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
                    if be_done:
                        td = tdist(fav - entry)
                        stop = max(stop, entry + PTS_BE_LOCK, fav - td)
                else:
                    fav = min(fav, b['l'])
                    if not be_done and (entry - fav) >= PTS_BE_TRIG:
                        stop = min(stop, entry - PTS_BE_LOCK); be_done = True
                    if be_done:
                        td = tdist(entry - fav)
                        stop = min(stop, entry - PTS_BE_LOCK, fav + td)
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
        if m >= FLATTEN:
            if pos != 0: fecha(b['c'])
            continue
        niv_hi = seg_hoje[0] if seg_hoje else pd_hi
        niv_lo = seg_hoje[1] if seg_hoje else pd_lo
        if not block and pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM and niv_hi is not None:
            tol = TOL_TICKS * TICK; h, l, c = b['h'], b['l'], b['c']; lado = 0
            if h >= niv_hi - tol and c < niv_hi:
                if MAX_DIST == 0 or (niv_hi - c) <= MAX_DIST: lado = -1
            elif l <= niv_lo + tol and c > niv_lo:
                if MAX_DIST == 0 or (c - niv_lo) <= MAX_DIST: lado = 1
            if lado != 0:
                entry = c; pos = lado; fav = c; be_done = False
                stop = c - lado * PTS_SL; target = c + lado * TP; dias.add(d)
    if pos != 0: fecha(bars[-1]['c'])

    wins = [t for t in trades if t > 0]; n = len(trades); tot = aprov + reprov
    gw = sum(wins); gl = abs(sum(t for t in trades if t <= 0))
    ds = sorted(d2a); med = ds[len(ds)//2] if ds else 0
    avg_win = gw / len(wins) if wins else 0
    big = [t for t in wins if t > 200]  # wins "grandes" (>$200 = >20pt) -> mede se cavalgou
    return {
        'n': n, 'wr': 100 * len(wins) / n if n else 0,
        'pf': gw / gl if gl > 0 else 99,
        'net': sum(trades), 'aprov': aprov, 'reprov': reprov, 'tot': tot,
        'taxa': 100 * aprov / tot if tot else 0, 'dmediana': med,
        'avg_win': avg_win, 'big': len(big), 'max_win': max(wins) if wins else 0,
    }


def linha(label, r):
    print(f"  {label:>26s} {r['taxa']:>4.0f}% {r['aprov']:>3}/{r['tot']:<3} {r['dmediana']:>4.0f}d "
          f"{r['wr']:>4.0f}% {r['pf']:>5.2f} {r['avg_win']:>7.0f} {r['big']:>5} {r['max_win']:>7.0f} {r['net']:>11,.0f}")


if __name__ == '__main__':
    print("Carregando NQ 1-min..."); bars = carregar('NQ_dados')
    dom = domingo_ranges(bars)
    meio = bars[len(bars)//2]['dt']
    b1 = [b for b in bars if b['dt'] < meio]; b2 = [b for b in bars if b['dt'] >= meio]
    print(f"{len(bars):,} barras | objetivo: tua ideia de 'cavalgar a alta' bate o baseline?\n")

    print("=" * 100)
    print("  TRAILING ESCALONADO (aperta ate P_LOOSE pt, depois alarga p/ W_LOOSE) vs BASELINE")
    print("=" * 100)
    print(f"  {'config':>26s} {'taxa':>5s} {'aprov':>7s} {'dmed':>5s} {'WR':>5s} {'PF':>5s} "
          f"{'avgWin':>7s} {'#>$200':>6s} {'maxWin':>7s} {'PnL$':>11s}")
    print("-" * 100)
    base = bt(bars, dom)
    linha("BASELINE (trail 1,75)", base)
    print()
    melhores = []
    for p in [15, 20, 30]:
        for w in [6, 10, 15]:
            r = bt(bars, dom, p_loose=p, w_loose=w)
            linha(f"esc P{p}/W{w}", r)
            melhores.append((p, w, r))
        print()

    print("=" * 100)
    print("  LEITURA: avgWin sobe? #wins>$200 (cavalgou) aumenta? E a TAXA/PnL aguentam?")
    print("=" * 100)
    ranked = sorted(melhores, key=lambda x: (-x[2]['taxa'], x[2]['dmediana'], -x[2]['net']))
    print(f"  baseline -> taxa {base['taxa']:.0f}% | PnL ${base['net']:,.0f} | avgWin ${base['avg_win']:.0f} | "
          f"wins>$200: {base['big']} | maxWin ${base['max_win']:.0f}")
    bp, bw, br = ranked[0]
    print(f"  melhor escalonado (P{bp}/W{bw}) -> taxa {br['taxa']:.0f}% | PnL ${br['net']:,.0f} | "
          f"avgWin ${br['avg_win']:.0f} | wins>$200: {br['big']} | maxWin ${br['max_win']:.0f}")

    print("\n  ROBUSTEZ OOS do melhor escalonado vs baseline (1a | 2a metade):")
    for label, p, w in [("BASELINE", None, None), (f"esc P{bp}/W{bw}", bp, bw)]:
        r1 = bt(b1, dom, p, w); r2 = bt(b2, dom, p, w)
        print(f"    {label:>14s}  {r1['taxa']:>3.0f}% PF {r1['pf']:.2f} ${r1['net']:>9,.0f}  |  "
              f"{r2['taxa']:>3.0f}% PF {r2['pf']:.2f} ${r2['net']:>9,.0f}")
