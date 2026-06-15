#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VARREDURA STOP DIARIO (14/06): qual o stop diario ideal?
Config atual: 15pt filter, tol 20t, TP 60, trail 1.75, janela 16h.
Varre valores de stop diario de $125 ate $750.
"""
import glob, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
MNQ_PV = 2.0; RT_PER = 1.20
META = 1500.0; DD = 1500.0; MIN_DIAS = 7
TICK = 0.25; N_CONTR = 5
PTS_SL = 12.5; PTS_BE_TRIG = 3.75; PTS_BE_LOCK = 2.5; PTS_TRAIL = 1.75
TOL_TICKS = 20; TP = 60.0; TRAIL = 1.75; MAX_DIST = 15.0
ENTRADA_FIM = 16*60; FLATTEN = 16*60+55; ENTRADA_INI = 9*60+30


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


def bt(bars, stop_dia_dolar):
    pv = MNQ_PV * N_CONTR; rt = RT_PER * N_CONTR
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False
    realized = 0.0; trades = []; dias_bloqueados = 0
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None
    aprov = reprov = 0; d2a = []; pnl_d0 = 0.0; block = False; dia_k = None

    def fecha(p):
        nonlocal pos, realized
        if pos == 0: return
        realized += (p - entry) * pos * pv - rt
        trades.append((p - entry) * pos * pv - rt)
        pos = 0

    for b in bars:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d')
        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = cur_lo = None
        if ENTRADA_INI <= m < 16*60:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
        if d != dia_k:
            if block: dias_bloqueados += 1
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
        if stop_dia_dolar > 0 and (realized - pnl_d0 + ua) <= -stop_dia_dolar:
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
        if not block and pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM and pd_hi is not None:
            tol = TOL_TICKS * TICK; h, l, c = b['h'], b['l'], b['c']; lado = 0
            if h >= pd_hi - tol and c < pd_hi:
                if MAX_DIST == 0 or (pd_hi - c) <= MAX_DIST: lado = -1
            elif l <= pd_lo + tol and c > pd_lo:
                if MAX_DIST == 0 or (c - pd_lo) <= MAX_DIST: lado = 1
            if lado != 0:
                entry = c; pos = lado; fav = c; be_done = False
                stop = c - lado * PTS_SL; target = c + lado * TP; dias.add(d)
    if pos != 0: fecha(bars[-1]['c'])

    wins = [t for t in trades if t > 0]; n = len(trades); tot = aprov + reprov
    gw = sum(wins); gl = abs(sum(t for t in trades if t <= 0))
    ds = sorted(d2a); med = ds[len(ds)//2] if ds else 0
    return {
        'n': n, 'wr': 100 * len(wins) / n if n else 0,
        'pf': gw / gl if gl > 0 else 99,
        'net': sum(trades), 'aprov': aprov, 'reprov': reprov, 'tot': tot,
        'taxa': 100 * aprov / tot if tot else 0,
        'dmed': sum(d2a) / len(d2a) if d2a else 0, 'dmediana': med,
        'trd_dia': n / 220, 'dias_bloq': dias_bloqueados
    }


if __name__ == '__main__':
    print("Carregando NQ 1-min..."); bars = carregar('NQ_dados')
    meio = bars[len(bars)//2]['dt']
    b1 = [b for b in bars if b['dt'] < meio]; b2 = [b for b in bars if b['dt'] >= meio]
    print(f"{len(bars):,} barras | 5 MNQ, tol 20t, TP 60, maxDist 15pt, janela 16h\n")

    # ~$127 por stop (12.5pt x $10 + $1.20 RT)
    CENARIOS = [
        ("$125  (~1 stop)", 125),
        ("$250  (~2 stops)", 250),
        ("$375  (~3 stops)", 375),
        ("$500  (~4 stops)", 500),
        ("$625  (~5 stops)", 625),
        ("$750  (~6 stops)", 750),
        ("$1000 (~8 stops)", 1000),
    ]

    print("=" * 115)
    print("  VARREDURA STOP DIARIO (config completa: tol 20t + maxDist 15pt + janela 16h)")
    print("=" * 115)
    print(f"  {'stop/dia':>16s} {'taxa':>5s} {'aprov':>6s} {'reprov':>7s} {'d.med':>6s} "
          f"{'trades':>7s} {'trd/dia':>7s} {'dias bloq':>9s} {'WR':>4s} {'PF':>5s} {'PnL$/ano':>10s}")
    print("-" * 115)
    for label, sd in CENARIOS:
        r = bt(bars, sd)
        marca = "  <- ATUAL" if sd == 750 else ""
        print(f"  {label:>16s} {r['taxa']:>4.0f}% {r['aprov']:>6} {r['reprov']:>7} "
              f"{r['dmediana']:>5.0f}d {r['n']:>7} {r['trd_dia']:>6.1f} "
              f"{r['dias_bloq']:>9} {r['wr']:>3.0f}% {r['pf']:>5.2f} {r['net']:>10,.0f}{marca}")
    print("-" * 115)

    print("\n" + "=" * 115)
    print("  ROBUSTEZ OUT-OF-SAMPLE")
    print("=" * 115)
    print(f"  {'stop/dia':>16s} {'1a metade':>30s} {'2a metade':>30s}")
    print("-" * 115)
    for label, sd in CENARIOS:
        r1 = bt(b1, sd); r2 = bt(b2, sd)
        print(f"  {label:>16s} "
              f"{r1['aprov']:>3}/{r1['tot']:<3} ({r1['taxa']:>3.0f}%) PF {r1['pf']:>4.2f} med {r1['dmediana']:>3.0f}d   "
              f"{r2['aprov']:>3}/{r2['tot']:<3} ({r2['taxa']:>3.0f}%) PF {r2['pf']:>4.2f} med {r2['dmediana']:>3.0f}d")
    print("-" * 115)
