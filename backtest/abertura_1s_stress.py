#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STRESS da estrategia de abertura (1s real).
  1) mes a mes em 2024  -> consistente ou 1-2 meses carregam?
  2) slippage 2t entrada + 2t stop -> aguenta?
  3) SEM SINAL: entra sempre LONG as 09:30:30 e usa a mesma gestao.
     se der parecido -> o "sinal da explosao" nao vale nada, e so colher vol.
  4) SEM SINAL aleatorio (long/short 50/50 fixo por dia).
"""
import os
import numpy as np
import pandas as pd

TICK = 0.25
DPT = 0.50
COMM_RT = 1.24
HERE = os.path.dirname(__file__)
DAT = os.path.join(HERE, '..', 'dados_databento')
OPEN_SOD = 9 * 3600 + 30 * 60
FILES = {'2024_fraco': 'MNQ_1s_2024.txt', '2025': 'MNQ_1s_2025.txt',
         '2026ago': 'MNQ_1s_2026ago.txt'}
_C = {}


def load_days(fn):
    if fn in _C:
        return _C[fn]
    df = pd.read_csv(os.path.join(DAT, fn), sep=';', header=None,
                     names=['ts', 'o', 'h', 'l', 'c', 'v'], dtype={'ts': str})
    t = pd.to_datetime(df['ts'], format='%Y%m%d %H%M%S')
    df['date'] = t.dt.normalize()
    df['sod'] = (t.dt.hour * 3600 + t.dt.minute * 60 + t.dt.second).astype(np.int32)
    out = []
    for d, g in df.groupby('date', sort=True):
        sod = g['sod'].values
        i0 = np.searchsorted(sod, OPEN_SOD)
        if i0 >= len(sod) or sod[i0] != OPEN_SOD:
            continue
        s = slice(i0, None)
        out.append(dict(date=pd.Timestamp(d),
                        o=g['o'].values[s].astype(float), h=g['h'].values[s].astype(float),
                        l=g['l'].values[s].astype(float), c=g['c'].values[s].astype(float),
                        sod=g['sod'].values[s].astype(np.int32)))
    _C[fn] = out
    return out


def trade(day, N, W, S, be_trig, trail_dist, slip_e, slip_s, forced_dir=0):
    o, h, l, c, sod = day['o'], day['h'], day['l'], day['c'], day['sod']
    n = len(o)
    open_px = o[0]
    t0 = sod[0]
    direction = 0
    trig_i = -1
    if forced_dir != 0:
        # entra na 1a barra >= 30s apos abertura (deixa formar um pouco)
        direction = forced_dir
        for i in range(n):
            if sod[i] - t0 >= 30:
                trig_i = i
                break
        if trig_i < 0:
            return None
        entry = c[trig_i] + direction * slip_e * TICK
    else:
        up = open_px + N * TICK
        dn = open_px - N * TICK
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
                direction = 1; trig_i = i; break
            if hd:
                direction = -1; trig_i = i; break
        if trig_i < 0:
            return None
        entry = (up if direction == 1 else dn) + direction * slip_e * TICK

    stop_fav = -S * 1.0
    hwm = 0.0
    be_done = False
    for i in range(trig_i + 1, n):
        if direction == 1:
            hi_fav = (h[i] - entry) / TICK; lo_fav = (l[i] - entry) / TICK
            op_fav = (o[i] - entry) / TICK
        else:
            hi_fav = (entry - l[i]) / TICK; lo_fav = (entry - h[i]) / TICK
            op_fav = (entry - o[i]) / TICK
        if lo_fav <= stop_fav:
            fill = op_fav if op_fav < stop_fav else stop_fav - slip_s
            return max(fill, lo_fav)
        if hi_fav > hwm:
            hwm = hi_fav
        if not be_done and hwm >= be_trig * S:
            stop_fav = max(stop_fav, 0.0); be_done = True
        if be_done and trail_dist > 0:
            stop_fav = max(stop_fav, hwm - trail_dist * S)
    return (c[-1] - entry) / TICK * direction


def resumo(pnls, label):
    a = np.array(pnls)
    if len(a) == 0:
        print(f"  {label}: sem trades"); return
    net = a * DPT - COMM_RT
    print(f"  {label:<26} n={len(a):>3}  wr={ (a>0).mean():.2f}  "
          f"exp_liq=${net.mean():+5.2f}  tot=${net.sum():+7.0f}  med={np.median(a):+5.1f}t")


CFG = dict(N=4, W=180, S=6, be_trig=1.0, trail_dist=1.0)   # config de destaque


def main():
    print("="*84)
    print(f"CONFIG: gatilho {CFG['N']}t / stop {CFG['S']}t / BE +{CFG['be_trig']}S / "
          f"trail {CFG['trail_dist']}S / sem alvo")
    print("="*84)

    for tag, fn in FILES.items():
        days = load_days(fn)
        print(f"\n### {tag}  ({len(days)} dias) ###")

        # 1) base, slippage 1/1
        p = [trade(d, CFG['N'], CFG['W'], CFG['S'], CFG['be_trig'], CFG['trail_dist'], 1, 1)
             for d in days]
        resumo([x for x in p if x is not None], "sinal, slip 1t/1t")

        # 2) slippage 2/2
        p = [trade(d, CFG['N'], CFG['W'], CFG['S'], CFG['be_trig'], CFG['trail_dist'], 2, 2)
             for d in days]
        resumo([x for x in p if x is not None], "sinal, slip 2t/2t")

        # 3) slippage 3/3
        p = [trade(d, CFG['N'], CFG['W'], CFG['S'], CFG['be_trig'], CFG['trail_dist'], 3, 3)
             for d in days]
        resumo([x for x in p if x is not None], "sinal, slip 3t/3t")

        # 4) SEM sinal: sempre long
        p = [trade(d, 0, 0, CFG['S'], CFG['be_trig'], CFG['trail_dist'], 1, 1, forced_dir=1)
             for d in days]
        resumo([x for x in p if x is not None], "SEM sinal, sempre LONG")

        # 5) SEM sinal: sempre short
        p = [trade(d, 0, 0, CFG['S'], CFG['be_trig'], CFG['trail_dist'], 1, 1, forced_dir=-1)
             for d in days]
        resumo([x for x in p if x is not None], "SEM sinal, sempre SHORT")

    # mes a mes 2024 + 2025
    print("\n" + "="*84)
    print("MES A MES 2024+2025 (sinal, slip 2t/2t)")
    print("="*84)
    bym = {}
    for fn in ('MNQ_1s_2024.txt', 'MNQ_1s_2025.txt'):
        for d in load_days(fn):
            r = trade(d, CFG['N'], CFG['W'], CFG['S'], CFG['be_trig'], CFG['trail_dist'], 2, 2)
            if r is not None:
                bym.setdefault(d['date'].strftime('%Y-%m'), []).append(r)
    pos = 0
    for m in sorted(bym):
        a = np.array(bym[m]); net = a * DPT - COMM_RT
        if net.mean() > 0:
            pos += 1
        resumo(bym[m], m)
    print(f"\n  meses com exp_liq > 0: {pos}/{len(bym)}")


if __name__ == '__main__':
    main()
