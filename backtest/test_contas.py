#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Niveis (config robusta BE$75/trail$50, R:R 2:1) testada em 25K / 50K / 100K.
Mostra como a taxa de aprovacao sobe com conta maior (DD mais folgado) — caminho
LEGITIMO p/ taxa maior, sem travar o bot. + robustez por metade.
"""
import glob, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
PV = 20.0; TICK = 0.25; RT_COST = 5.0; MIN_DIAS = 7
TP_USD = 500.0; SL_USD = 250.0; BE_TRIG = 75.0; TRAIL = 50.0; BE_LOCK = 50.0

CONTAS = {'25K': (1500, 1500), '50K': (3000, 2500), '100K': (6000, 3000)}


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


def bt(bars, meta, dd):
    pts_tp = TP_USD/PV; pts_sl = SL_USD/PV; pts_trail = TRAIL/PV; pts_lock = BE_LOCK/PV
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False
    realized = 0.0; trades = []
    vpv = vv = vwap = 0.0; pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    r_ini = 0.0; pico = 0.0; dias = set()
    aprov = reprov = 0; pnl_d0 = 0.0; block = False; dia_k = None

    def fecha(p):
        nonlocal pos, realized
        if pos == 0: return
        realized += (p-entry)*pos*PV - RT_COST; trades.append((p-entry)*pos*PV - RT_COST); pos = 0

    for b in bars:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d')
        sess = 9*60+30 <= m < 16*60
        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = cur_lo = None
        if sess:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
        if m == 9*60+30: vpv = vv = 0.0
        if sess:
            tp = (b['h']+b['l']+b['c'])/3.0; vpv += tp*b['v']; vv += b['v']
            vwap = vpv/vv if vv > 0 else b['c']
        if d != dia_k: dia_k = d; pnl_d0 = realized; block = False
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
                    if not be_done and (fav-entry)*PV >= BE_TRIG: stop = max(stop, entry+pts_lock); be_done = True
                    if be_done: stop = max(stop, fav-pts_trail)
                else:
                    fav = min(fav, b['l'])
                    if not be_done and (entry-fav)*PV >= BE_TRIG: stop = min(stop, entry-pts_lock); be_done = True
                    if be_done: stop = min(stop, fav+pts_trail)
        if True:
            pr = realized - r_ini
            ua = uf = 0.0
            if pos > 0: ua = (b['l']-entry)*PV; uf = (b['h']-entry)*PV
            elif pos < 0: ua = (entry-b['h'])*PV; uf = (entry-b['l'])*PV
            if pr+uf > pico: pico = pr+uf
            if (realized-pnl_d0+ua) <= -(dd*0.5):
                block = True
                if pos != 0: fecha(b['c'])
            if pr+ua <= pico - dd:
                fecha(b['c']); reprov += 1; r_ini = realized; pico = 0.0; dias = set()
            elif pr >= meta and len(dias) >= MIN_DIAS:
                fecha(b['c']); aprov += 1; r_ini = realized; pico = 0.0; dias = set()
        if m >= 15*60+55:
            if pos != 0: fecha(b['c'])
            continue
        if not block and pos == 0 and 9*60+30 <= m < 15*60 and pd_hi is not None:
            tol = 6*TICK; h, l, c = b['h'], b['l'], b['c']; lado = 0
            if h >= pd_hi-tol and c < pd_hi: lado = -1
            elif l <= pd_lo+tol and c > pd_lo: lado = 1
            if lado != 0:
                entry = c; pos = lado; fav = c; be_done = False
                stop = c - lado*pts_sl; target = c + lado*pts_tp; dias.add(d)
    if pos != 0: fecha(bars[-1]['c'])
    n = len(trades); wins = [t for t in trades if t > 0]
    gw = sum(wins); gl = abs(sum(t for t in trades if t <= 0)); tot = aprov+reprov
    return {'n': n, 'wr': 100*len(wins)/n if n else 0, 'pf': (gw/gl if gl > 0 else 99),
            'net': sum(trades), 'aprov': aprov, 'reprov': reprov, 'tot': tot,
            'taxa': 100*aprov/tot if tot else 0}


if __name__ == '__main__':
    bars = carregar('NQ_dados')
    meio = bars[len(bars)//2]['dt']
    b1 = [b for b in bars if b['dt'] < meio]; b2 = [b for b in bars if b['dt'] >= meio]
    print("Niveis BE$75/trail$50 (R:R 2:1) — taxa de aprovacao por tamanho de conta\n")
    print(f"  {'conta':6s} {'meta$':>6s} {'DD$':>5s} {'trd':>5s} {'WR':>5s} {'PF':>5s} "
          f"{'PnL$/ano':>10s} {'aprov':>6s} {'reprov':>7s} {'taxa':>6s}")
    print("  " + "-"*74)
    for nome, (meta, dd) in CONTAS.items():
        r = bt(bars, meta, dd)
        print(f"  {nome:6s} {meta:>6.0f} {dd:>5.0f} {r['n']:>5} {r['wr']:>4.0f}% {r['pf']:>5.2f} "
              f"{r['net']:>10,.0f} {r['aprov']:>6} {r['reprov']:>7} {r['taxa']:>5.0f}%")
    print("\n  ROBUSTEZ por metade:")
    for nome, (meta, dd) in CONTAS.items():
        r1 = bt(b1, meta, dd); r2 = bt(b2, meta, dd)
        print(f"  {nome:6s}  1a: {r1['aprov']}/{r1['tot']} ({r1['taxa']:.0f}%) PF {r1['pf']:.2f}  |  "
              f"2a: {r2['aprov']}/{r2['tot']} ({r2['taxa']:.0f}%) PF {r2['pf']:.2f}")
