#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HARNESS deterministico da estrategia ABERTURA DE NY (breakout direcional da
explosao da 1a vela). Lado Python — CONTRATO MATEMATICO CONGELADO.

Nao e medida de rentabilidade real. E a referencia logica que o
src/AberturaExplosao.cs (NinjaScript) tem que reproduzir BIT A BIT
(molde: onfade_harness.py <-> OnFadeNative.cs).

--------------------------------------------------------------------------------
CONTRATO CONGELADO (v1 — 10/09/2026)
--------------------------------------------------------------------------------
  instrumento     MNQ   (TICK=0.25 pt, POINT_VALUE=$2.0/pt)
  contratos       QTY   (default 6 — parametro; cliente escolhe quando o bot for vendido)
  gatilho         1o toque de +-N ticks do OPEN da barra 09:30:00 ET
                  N default 3   (parametro)
  janela leitura  W segundos apos 09:30:00 (default 180). Nao tocou -> sem trade.
  direcao         tocou os 2 lados na mesma barra -> cor da barra (close>=open => LONG)
  entrada         NIVEL do gatilho (open +- N ticks) + SLIP_ENTRY ticks adverso
  stop inicial    S ticks (default 6)
  breakeven       trava stop em 0 quando a maxima a favor >= BE_TRIG*S  (default 1.0 => +6t)
  trailing        depois do BE: stop = maxima_favor - TRAIL_DIST*S  (default 1.0 => 6t atras)
                  so sobe, nunca desce
  take-profit     +ALVO_DOLAR de P&L NA POSICAO (default 500, FIXO — nao por contrato)
                  => TP_TICKS = ceil(ALVO_DOLAR / (TICK*POINT_VALUE*QTY))
                  ALVO_DOLAR=0 desliga o alvo (deixa so o trailing levar)
  trades/dia      1   |   1 posicao por vez   |   nao reentra apos saida
  flatten         fim do RTH (16:00 ET). NOTA: o dado 1s vai so ate ~12:00 ET,
                  entao na pratica o harness fecha no ultimo bar do dia (~11:59:59).
                  O .cs usa 15:55 ET real.
  ordem intrabar  ADVERSO primeiro: dentro do mesmo bar de 1s checa stop/trail
                  ANTES do alvo (conservador).
  fill stop       se o bar ABRIU alem do stop -> fill no open (gap, pior);
                  senao fill = stop - SLIP_STOP ticks; nunca melhor que a minima do bar.
  fill alvo       LIMIT: fill no nivel do alvo, sem slippage.
  slippage/comiss SLIP_* e COMM_RT sao referencia interna. O veredito real vem do
                  NT8 Strategy Analyzer / Market Replay (o .cs NAO coda slippage).

Saidas:
  <out>/trades_abertura_slip{N}.csv   — 1 linha por trade, colunas p/ reconciliacao
  stdout                              — resumo por bloco + combinado + DD/pior dia/streak

Uso:
  python3 backtest/abertura_harness.py                       # default: QTY 6, N 3, alvo 500
  python3 backtest/abertura_harness.py --qty 6 --alvo 500 --n 3 --slip 1
  python3 backtest/abertura_harness.py --out /tmp/abertura --csv
"""
import argparse
import math
import os
import sys

import numpy as np
import pandas as pd

# ---------------- contrato congelado ----------------
TICK = 0.25
POINT_VALUE = 2.0
OPEN_SOD = 9 * 3600 + 30 * 60          # 09:30:00 em segundos-do-dia ET

DEF_QTY = 6
DEF_N = 3
DEF_W = 180
DEF_S = 6
DEF_BE_TRIG = 1.0
DEF_TRAIL_DIST = 1.0
DEF_ALVO_DOLAR = 500.0
DEF_SLIP_ENTRY = 1
DEF_SLIP_STOP = 1
DEF_COMM_RT = 1.24                     # por contrato, round-turn (referencia)

HERE = os.path.dirname(os.path.abspath(__file__))
DAT = os.path.join(HERE, '..', 'dados_databento')
BLOCOS = [
    ('2024_fraco', 'MNQ_1s_2024.txt'),
    ('2025_h1',    'MNQ_1s_2025.txt'),
    ('2026ago',    'MNQ_1s_2026ago.txt'),
]
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
            date=pd.Timestamp(d),
            o=g['o'].values[s].astype(np.float64),
            h=g['h'].values[s].astype(np.float64),
            l=g['l'].values[s].astype(np.float64),
            c=g['c'].values[s].astype(np.float64),
            sod=g['sod'].values[s].astype(np.int32),
        ))
    _CACHE[fn] = days
    return days


def tp_ticks(alvo_dolar, qty):
    """$ na posicao -> ticks a favor. ceil: so dispara quando cruza de fato os $500."""
    if alvo_dolar <= 0:
        return None
    return math.ceil(alvo_dolar / (TICK * POINT_VALUE * qty))


def sim_day(day, cfg):
    """Retorna dict do trade (ou None se nao houve trade). PnL em ticks-favor cru
    em 'saida_ticks_fav'; o $ e derivado fora (depende de QTY)."""
    o, h, l, c, sod = day['o'], day['h'], day['l'], day['c'], day['sod']
    n = len(o)
    N, W, S = cfg['n'], cfg['w'], cfg['s']
    be_trig, trail_dist = cfg['be_trig'], cfg['trail_dist']
    slip_e, slip_s = cfg['slip_entry'], cfg['slip_stop']
    tpt = cfg['tp_ticks']

    open_px = o[0]
    t0 = sod[0]
    up = open_px + N * TICK
    dn = open_px - N * TICK

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

    entry = (up if direction == 1 else dn) + direction * slip_e * TICK
    stop_fav = -S * 1.0
    hwm = 0.0
    be_done = False
    saida_ticks = None
    saida_motivo = None
    saida_i = None

    # anda DEPOIS da barra do gatilho (a barra do gatilho tem high/low de antes da entrada)
    for i in range(trig_i + 1, n):
        if direction == 1:
            hi_fav = (h[i] - entry) / TICK
            lo_fav = (l[i] - entry) / TICK
            op_fav = (o[i] - entry) / TICK
        else:
            hi_fav = (entry - l[i]) / TICK
            lo_fav = (entry - h[i]) / TICK
            op_fav = (entry - o[i]) / TICK

        # 1) ADVERSO primeiro: stop / trail
        if lo_fav <= stop_fav:
            fill = op_fav if op_fav < stop_fav else stop_fav - slip_s
            saida_ticks = max(fill, lo_fav)
            saida_motivo = 'STOP' if stop_fav <= -S * 1.0 + 1e-9 else ('BE' if abs(stop_fav) < 1e-9 else 'TRAIL')
            saida_i = i
            break
        # 2) alvo (limit, sem slippage)
        if tpt is not None and hi_fav >= tpt:
            saida_ticks = float(tpt)
            saida_motivo = 'ALVO'
            saida_i = i
            break
        # 3) atualiza trailing
        if hi_fav > hwm:
            hwm = hi_fav
        if not be_done and hwm >= be_trig * S:
            stop_fav = max(stop_fav, 0.0)
            be_done = True
        if be_done and trail_dist > 0:
            stop_fav = max(stop_fav, hwm - trail_dist * S)

    if saida_ticks is None:
        saida_ticks = (c[-1] - entry) / TICK * direction
        saida_motivo = 'FLATTEN'
        saida_i = n - 1

    def hhmmss(x):
        return f"{x//3600:02d}:{(x%3600)//60:02d}:{x%60:02d}"

    return dict(
        data_pregao=str(day['date'].date()),
        direcao='LONG' if direction == 1 else 'SHORT',
        bar_gatilho_et=hhmmss(int(sod[trig_i])),
        open_0930=round(open_px, 4),
        nivel_gatilho=round(up if direction == 1 else dn, 4),
        entrada_preco_efetivo=round(entry, 4),
        slip_entrada_ticks=slip_e,
        stop_inicial_ticks=S,
        bar_saida_et=hhmmss(int(sod[saida_i])),
        saida_motivo=saida_motivo,
        saida_ticks_fav=round(saida_ticks, 4),
        hwm_ticks=round(hwm, 4),
    )


def stats_bloco(label, days, cfg, qty, comm_rt):
    rows = [sim_day(d, cfg) for d in days]
    rows = [r for r in rows if r is not None]
    if not rows:
        print(f"  {label:<12} sem trades")
        return rows
    tk = np.array([r['saida_ticks_fav'] for r in rows])
    gross = tk * TICK * POINT_VALUE * qty
    net = gross - comm_rt * qty
    for r, g, nn in zip(rows, gross, net):
        r['pnl_bruto'] = round(float(g), 2)
        r['pnl_liquido'] = round(float(nn), 2)

    eq = np.cumsum(net)
    dd = eq - np.maximum.accumulate(eq)
    maxdd = -dd.min()
    streak = worst = 0.0
    for x in net:
        streak = streak + x if x < 0 else 0.0
        worst = min(worst, streak)
    mot = {}
    for r in rows:
        mot[r['saida_motivo']] = mot.get(r['saida_motivo'], 0) + 1
    mot_s = ' '.join(f"{k}:{v}" for k, v in sorted(mot.items()))

    print(f"  {label:<12} n={len(rows):>3} ({len(rows)/len(days)*100:>3.0f}%d)  "
          f"wr={(tk>0).mean():>4.0%}  $/trade={net.mean():>+7.2f}  tot={net.sum():>+7.0f}  "
          f"maxDD={maxdd:>6.0f}  piorDia={net.min():>+6.0f}  streak={worst:>+6.0f}  | {mot_s}")
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--qty', type=int, default=DEF_QTY)
    ap.add_argument('--n', type=int, default=DEF_N, help='gatilho em ticks')
    ap.add_argument('--w', type=int, default=DEF_W, help='janela de leitura (s)')
    ap.add_argument('--s', type=int, default=DEF_S, help='stop em ticks')
    ap.add_argument('--alvo', type=float, default=DEF_ALVO_DOLAR, help='$ na posicao (0=sem alvo)')
    ap.add_argument('--slip', type=int, default=None, help='slippage entrada=stop (ticks); default 1')
    ap.add_argument('--comm', type=float, default=DEF_COMM_RT)
    ap.add_argument('--out', default='/tmp/abertura')
    ap.add_argument('--csv', action='store_true', help='grava trades_abertura_slip{N}.csv')
    ap.add_argument('--compara-n', action='store_true', help='roda N=3 e N=4 lado a lado')
    a = ap.parse_args()

    slip = DEF_SLIP_ENTRY if a.slip is None else a.slip
    tpt = tp_ticks(a.alvo, a.qty)

    def make_cfg(N):
        return dict(n=N, w=a.w, s=a.s, be_trig=DEF_BE_TRIG, trail_dist=DEF_TRAIL_DIST,
                    slip_entry=slip, slip_stop=slip, tp_ticks=tpt)

    print('=' * 108)
    print(f"HARNESS ABERTURA NY  —  QTY={a.qty}  gatilho={a.n}t  W={a.w}s  stop={a.s}t  "
          f"BE +{DEF_BE_TRIG:g}S  trail {DEF_TRAIL_DIST:g}S  "
          f"alvo=${a.alvo:g} ({tpt if tpt else '-'}t)  slip={slip}t/{slip}t  comm=${a.comm:g}/ct")
    print('=' * 108)

    ns = [3, 4] if a.compara_n else [a.n]
    all_rows_by_n = {}
    for N in ns:
        cfg = make_cfg(N)
        if len(ns) > 1:
            print(f"\n--- gatilho {N}t ---")
        all_rows = []
        for label, fn in BLOCOS:
            rows = stats_bloco(label, load_days(fn), cfg, a.qty, a.comm)
            for r in rows:
                r['bloco'] = label
            all_rows += rows
        # combinado cronologico
        all_rows.sort(key=lambda r: (r['data_pregao'], r['bar_gatilho_et']))
        net = np.array([r['pnl_liquido'] for r in all_rows])
        tk = np.array([r['saida_ticks_fav'] for r in all_rows])
        eq = np.cumsum(net)
        maxdd = -(eq - np.maximum.accumulate(eq)).min()
        streak = worst = 0.0
        for x in net:
            streak = streak + x if x < 0 else 0.0
            worst = min(worst, streak)
        print(f"  {'COMBINADO':<12} n={len(all_rows):>3}          wr={(tk>0).mean():>4.0%}  "
              f"$/trade={net.mean():>+7.2f}  tot={net.sum():>+7.0f}  maxDD={maxdd:>6.0f}  "
              f"piorDia={net.min():>+6.0f}  streak={worst:>+6.0f}")
        all_rows_by_n[N] = all_rows

    if a.csv:
        os.makedirs(a.out, exist_ok=True)
        rows = all_rows_by_n[a.n if a.n in all_rows_by_n else ns[0]]
        cols = ['bloco', 'data_pregao', 'direcao', 'bar_gatilho_et', 'open_0930',
                'nivel_gatilho', 'entrada_preco_efetivo', 'slip_entrada_ticks',
                'stop_inicial_ticks', 'bar_saida_et', 'saida_motivo', 'saida_ticks_fav',
                'hwm_ticks', 'pnl_bruto', 'pnl_liquido']
        p = os.path.join(a.out, f"trades_abertura_slip{slip}.csv")
        pd.DataFrame(rows)[cols].to_csv(p, index=False)
        print(f"\n  csv: {p}  ({len(rows)} trades)")


if __name__ == '__main__':
    main()
