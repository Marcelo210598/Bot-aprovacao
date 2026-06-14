#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FILTRO DE PROXIMIDADE (14/06): so entra se o Close estiver dentro de MAX_DIST pontos
da linha. Filtra entradas "chase" onde o preco ja foi longe da linha antes de fechar.
Resto da config fixo (tol 20t, TP 60, trail 1.75, stop dia $750, janela 9h30-16h00).
"""
import glob, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
MNQ_PV = 2.0; RT_PER = 1.20
META = 1500.0; DD = 1500.0; MIN_DIAS = 7
TICK = 0.25; N_CONTR = 5
PTS_SL = 12.5; PTS_BE_TRIG = 3.75; PTS_BE_LOCK = 2.5; PTS_TRAIL = 1.75
TOL_TICKS = 20; TP = 60.0; TRAIL = 1.75; STOP_DIA_PT = 75.0


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

ENTRADA_FIM = 16*60; FLATTEN = 16*60+55; ENTRADA_INI = 9*60+30

def bt(bars, max_dist, tol_ticks=TOL_TICKS, pts_tp=TP, pts_trail=TRAIL, pts_stop_dia=STOP_DIA_PT):
    pv = MNQ_PV * N_CONTR; rt = RT_PER * N_CONTR; stop_dia = pts_stop_dia * pv
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False
    realized = 0.0; trades = []
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None
    aprov = reprov = 0; d2a = []; pnl_d0 = 0.0; block = False; dia_k = None
    filtradas = 0  # entradas bloqueadas pelo filtro

    def fecha(p):
        nonlocal pos, realized
        if pos == 0: return
        realized += (p-entry)*pos*pv - rt; trades.append((p-entry)*pos*pv - rt); pos = 0

    for b in bars:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d')
        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = cur_lo = None
        if ENTRADA_INI <= m < 16*60:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
        if d != dia_k: dia_k = d; pnl_d0 = realized; block = False
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
                    if be_done: stop = max(stop, fav-pts_trail)
                else:
                    fav = min(fav, b['l'])
                    if not be_done and (entry-fav) >= PTS_BE_TRIG: stop = min(stop, entry-PTS_BE_LOCK); be_done = True
                    if be_done: stop = min(stop, fav+pts_trail)
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
        if m >= FLATTEN:
            if pos != 0: fecha(b['c'])
            continue
        if not block and pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM and pd_hi is not None:
            tol = tol_ticks*TICK; h, l, c = b['h'], b['l'], b['c']; lado = 0
            if h >= pd_hi-tol and c < pd_hi:
                dist = pd_hi - c
                if max_dist == 0 or dist <= max_dist:
                    lado = -1
                else:
                    filtradas += 1
            elif l <= pd_lo+tol and c > pd_lo:
                dist = c - pd_lo
                if max_dist == 0 or dist <= max_dist:
                    lado = 1
                else:
                    filtradas += 1
            if lado != 0:
                entry = c; pos = lado; fav = c; be_done = False
                stop = c - lado*PTS_SL; target = c + lado*pts_tp; dias.add(d)
    if pos != 0: fecha(bars[-1]['c'])

    wins = [t for t in trades if t > 0]; n = len(trades); tot = aprov+reprov
    gw = sum(wins); gl = abs(sum(t for t in trades if t <= 0))
    ds = sorted(d2a); med = ds[len(ds)//2] if ds else 0
    return {'n': n, 'wr': 100*len(wins)/n if n else 0, 'pf': (gw/gl if gl > 0 else 99),
            'net': sum(trades), 'aprov': aprov, 'reprov': reprov, 'tot': tot,
            'taxa': 100*aprov/tot if tot else 0,
            'dmed': sum(d2a)/len(d2a) if d2a else 0, 'dmediana': med,
            'trd_dia': n/220, 'filtradas': filtradas}


if __name__ == '__main__':
    print("Carregando NQ 1-min..."); bars = carregar('NQ_dados')
    meio = bars[len(bars)//2]['dt']
    b1 = [b for b in bars if b['dt'] < meio]; b2 = [b for b in bars if b['dt'] >= meio]
    print(f"{len(bars):,} barras | 5 MNQ, tol 20t, TP 60, trail 1.75, stop dia $750, janela 16h\n")

    CENARIOS = [
        ("SEM filtro",  0),
        ("max 10pt",   10),
        ("max 15pt",   15),
        ("max 20pt",   20),
        ("max 25pt",   25),
        ("max 30pt",   30),
        ("max 40pt",   40),
        ("max 50pt",   50),
    ]

    print("="*110)
    print("  FILTRO DE PROXIMIDADE: close deve estar dentro de X pontos da linha")
    print("="*110)
    print(f"  {'filtro':>10s} {'taxa':>5s} {'aprov':>6s} {'reprov':>7s} {'d.med':>6s} {'trades':>7s} "
          f"{'trd/dia':>7s} {'filtradas':>9s} {'WR':>4s} {'PF':>5s} {'PnL$/ano':>10s}")
    print("-"*110)
    for label, md in CENARIOS:
        r = bt(bars, md)
        marca = "  <- ATUAL" if md == 0 else ""
        print(f"  {label:>10s} {r['taxa']:>4.0f}% {r['aprov']:>6} {r['reprov']:>7} "
              f"{r['dmediana']:>5.0f}d {r['n']:>7} {r['trd_dia']:>6.1f} "
              f"{r['filtradas']:>9} {r['wr']:>3.0f}% {r['pf']:>5.2f} {r['net']:>10,.0f}{marca}")
    print("-"*110)

    print("\n" + "="*110)
    print("  ROBUSTEZ OUT-OF-SAMPLE (1a metade x 2a metade)")
    print("="*110)
    print(f"  {'filtro':>10s} {'1a metade':>30s} {'2a metade':>30s}")
    print("-"*110)
    for label, md in CENARIOS:
        r1 = bt(b1, md); r2 = bt(b2, md)
        print(f"  {label:>10s} "
              f"{r1['aprov']:>3}/{r1['tot']:<3} ({r1['taxa']:>3.0f}%) PF {r1['pf']:>4.2f} med {r1['dmediana']:>3.0f}d   "
              f"{r2['aprov']:>3}/{r2['tot']:<3} ({r2['taxa']:>3.0f}%) PF {r2['pf']:>4.2f} med {r2['dmediana']:>3.0f}d")
    print("-"*110)
