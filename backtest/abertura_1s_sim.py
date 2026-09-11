#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ABERTURA NY — simulacao INTRABAR (1 segundo real, Databento) da explosao da 1a vela.

Logica:
  - open_px = open da barra 09:30:00 ET
  - a partir de 09:30:00, 1o toque de +-N ticks define direcao; entra no nivel do gatilho
    (+ SLIP_ENTRY ticks de slippage adverso). Se nao tocar em W segundos -> sem trade.
  - stop inicial S ticks. alvo fixo T ticks (0 = sem alvo).
  - trailing: BE em +BE_TRIG*S de maxima; depois trail a TRAIL_DIST*S atras da maxima.
  - flat as FLAT_SOD (segundo-do-dia; 0 = sem flat por tempo).
  - custo: SLIP_* ticks + COMM_RT dolares.
  - dentro da mesma barra de 1s: assume ADVERSO primeiro (stop antes de alvo).

Datasets SEPARADOS (2024 fraco / 2026ago forte). Carrega 1x, cacheia arrays por dia.
"""
import os
import sys
import numpy as np
import pandas as pd

TICK = 0.25
DPT = 0.50
SLIP_ENTRY = 1.0
SLIP_STOP = 1.0
COMM_RT = 1.24

HERE = os.path.dirname(__file__)
DAT = os.path.join(HERE, '..', 'dados_databento')
OPEN_SOD = (9 * 3600) + (30 * 60)
FILES = {'2024_fraco': 'MNQ_1s_2024.txt', '2026ago_forte': 'MNQ_1s_2026ago.txt'}

_CACHE = {}


def load_days(fn):
    if fn in _CACHE:
        return _CACHE[fn]
    df = pd.read_csv(os.path.join(DAT, fn), sep=';', header=None,
                     names=['ts', 'o', 'h', 'l', 'c', 'v'], dtype={'ts': str})
    t = pd.to_datetime(df['ts'], format='%Y%m%d %H%M%S')
    df['date'] = t.dt.normalize()
    df['sod'] = (t.dt.hour * 3600 + t.dt.minute * 60 + t.dt.second).astype(np.int32)
    days = []
    for d, g in df.groupby('date', sort=True):
        sod = g['sod'].values
        i0 = np.searchsorted(sod, OPEN_SOD)
        if i0 >= len(sod) or sod[i0] != OPEN_SOD:
            continue
        s = slice(i0, None)
        days.append(dict(
            date=d,
            o=g['o'].values[s].astype(np.float64),
            h=g['h'].values[s].astype(np.float64),
            l=g['l'].values[s].astype(np.float64),
            c=g['c'].values[s].astype(np.float64),
            sod=g['sod'].values[s].astype(np.int32),
        ))
    _CACHE[fn] = days
    return days


def sim_day(day, N, W, S, T, be_trig, trail_dist, flat_sod):
    o, h, l, c, sod = day['o'], day['h'], day['l'], day['c'], day['sod']
    n = len(o)
    open_px = o[0]
    up = open_px + N * TICK
    dn = open_px - N * TICK
    t0 = sod[0]

    trig_i = -1
    direction = 0
    for i in range(n):
        if sod[i] - t0 > W:
            break
        hu = h[i] >= up
        hd = l[i] <= dn
        if hu and hd:
            direction = 1 if c[i] >= o[i] else -1
            trig_i = i
            break
        if hu:
            direction = 1
            trig_i = i
            break
        if hd:
            direction = -1
            trig_i = i
            break
    if trig_i < 0:
        return None

    entry = (up if direction == 1 else dn) + direction * SLIP_ENTRY * TICK
    stop_fav = -S * 1.0                      # nivel do stop, em ticks a favor
    hwm = 0.0
    be_done = False

    # comeca a andar DEPOIS da barra do gatilho (a barra do gatilho tem low/high
    # de antes da entrada — contar ela stopa/alveja de mentira)
    for i in range(trig_i + 1, n):
        if flat_sod and sod[i] >= flat_sod:
            return (c[i] - entry) / TICK * direction
        if direction == 1:
            hi_fav = (h[i] - entry) / TICK
            lo_fav = (l[i] - entry) / TICK
            op_fav = (o[i] - entry) / TICK
        else:
            hi_fav = (entry - l[i]) / TICK
            lo_fav = (entry - h[i]) / TICK
            op_fav = (entry - o[i]) / TICK
        if lo_fav <= stop_fav:
            # fill conservador: se a barra ABRIU abaixo do stop, atravessou -> fill no
            # open (pior); senao no stop menos slippage. Nunca melhor que a minima.
            fill = op_fav if op_fav < stop_fav else stop_fav - SLIP_STOP
            return max(fill, lo_fav)
        if T > 0 and hi_fav >= T:
            return float(T)
        if hi_fav > hwm:
            hwm = hi_fav
        if not be_done and hwm >= be_trig * S:
            stop_fav = max(stop_fav, 0.0)
            be_done = True
        if be_done and trail_dist > 0:
            stop_fav = max(stop_fav, hwm - trail_dist * S)
    return (c[-1] - entry) / TICK * direction


def rodar(cfgs, titulo):
    print(f"\n{'='*120}\n{titulo}\n{'='*120}")
    print(f"{'N':>3} {'W':>4} {'S':>4} {'T':>5} {'BE':>4} {'trl':>5} {'flat':>6} | "
          f"{'dataset':>14} {'n':>4} {'%d':>4} {'wr':>5} "
          f"{'exp_t':>6} {'exp$g':>7} {'exp$n':>7} {'tot$n':>8} {'med_t':>6} {'win_t':>6} {'los_t':>6}")
    for (N, W, S, T, be, tr, flat) in cfgs:
        for label, fn in FILES.items():
            days = load_days(fn)
            pnls = [r for r in (sim_day(d, N, W, S, T, be, tr, flat) for d in days) if r is not None]
            if not pnls:
                continue
            a = np.array(pnls)
            g = a * DPT
            net = g - COMM_RT
            fl = f"{flat//3600}:{(flat%3600)//60:02d}" if flat else "-"
            print(f"{N:>3} {W:>4} {S:>4} {T:>5} {be:>4.1f} {tr:>5.2f} {fl:>6} | "
                  f"{label:>14} {len(a):>4} {len(a)/len(days)*100:>3.0f}% {(a>0).mean():>5.2f} "
                  f"{a.mean():>6.1f} {g.mean():>7.2f} {net.mean():>7.2f} {net.sum():>8.0f} "
                  f"{np.median(a):>6.1f} {(a[a>0].mean() if (a>0).any() else 0):>6.1f} "
                  f"{(-a[a<0].mean() if (a<0).any() else 0):>6.1f}")


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'baseline'

    if mode == 'baseline':
        cfgs = []
        for N in (3, 4, 6, 8, 10, 12, 16):
            for W in (60, 180):
                for S in (max(N, 4), 2 * N):
                    for T in (2 * S, 3 * S):
                        cfgs.append((N, W, S, T, 99.0, 0.0, 0))
        rodar(cfgs, "BASELINE — entrada + stop fixo + alvo fixo (sem trailing, sem flat)")

    elif mode == 'trailing':
        cfgs = []
        for (N, W) in ((4, 180), (6, 180), (8, 180), (10, 180)):
            for S in (max(N, 6), 2 * N):
                for be in (1.0, 1.5, 2.0):
                    for tr in (0.5, 1.0, 1.5):
                        cfgs.append((N, W, S, 0, be, tr, 0))
        rodar(cfgs, "TRAILING — sem alvo + BE + trail escalonado")

    elif mode == 'flat':
        cfgs = []
        for flat in (0, 10*3600+30*60, 11*3600, 12*3600-1):
            for (N, W, S, be, tr) in ((6, 180, 8, 1.5, 1.0), (8, 180, 8, 1.5, 1.0)):
                cfgs.append((N, W, S, 0, be, tr, flat))
        rodar(cfgs, "FLAT POR TEMPO")
