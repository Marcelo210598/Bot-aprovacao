#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Candidata B (event 8h30 ET) — REFINO (item 3 do plano 02/09).

O breakout tosco (run_event_830.py) deu PF <= 0,98 em TODA config no IS 2022-2025
(reprova o corte PF>1,3). Antes de matar a hipotese, testa variantes:

  A) FADE  — a barra 8h30 rompe e reverte ("head fake"). Entra CONTRA o rompimento.
  B) DELAY — deixa o fake-out acontecer: forma o range das barras 8h30+8h31,
     entra no rompimento desse range na barra 8h32/8h33 (pega o 2o movimento).
  C) FILTRO VOL — so opera eventos com spike >= Nx (os grandes de verdade: NFP/CPI top).
  D) direcao pelo range: rompe pra cima do range 8h25-30 = so LONG, etc. (ja e o default)

Bracket fixo, slippage 3-5t, flat 9h00 ET, 5 MNQ, custo $6,50 RT.
Corte: PF > 1,3 em 2022-2025 com custo+slippage.
"""
import os
import statistics as st
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import run_event_830 as base   # reaproveita carrega() / detecta_eventos() / stats()

ET = ZoneInfo("America/New_York")
TICK = 0.25
PV = 2.0 * 5
RT = 1.30 * 5
REL = 8 * 60 + 30
RANGE_INI = 8 * 60 + 25
FLAT = 9 * 60


def simula(m, lado, entry, stop, target, slip, ini_k):
    for k in range(ini_k, FLAT + 1):
        b = m.get(k)
        if not b:
            continue
        _, bh, bl, bc, _ = b
        if lado == 1:
            if bl <= stop:
                return stop - slip
            if bh >= target:
                return target - slip
        else:
            if bh >= stop:
                return stop + slip
            if bl <= target:
                return target + slip
    bflat = m.get(FLAT) or m.get(FLAT - 1)
    return bflat[3] if bflat else entry


def bt(eventos, por_dia, modo, slip_ticks, rr, sl_pts=0, vol_min=0):
    slip = slip_ticks * TICK
    trades = []
    for dia in sorted(eventos):
        if vol_min and eventos[dia]["mult"] < vol_min:
            continue
        m = por_dia[dia]
        ref = [m[k] for k in range(RANGE_INI, REL) if k in m]
        b830 = m.get(REL)
        b831 = m.get(REL + 1)
        if len(ref) < 3 or not b830:
            continue
        rhi = max(b[1] for b in ref)
        rlo = min(b[2] for b in ref)
        go, gh, gl, gc, gv = b830

        if modo in ("breakout", "fade"):
            if gc > rhi:
                dir_bo = 1
            elif gc < rlo:
                dir_bo = -1
            else:
                continue
            lado = dir_bo if modo == "breakout" else -dir_bo
            entry = gc + lado * slip
            risco = sl_pts if sl_pts else max(gh - gl, 2 * TICK)
            ini_k = REL + 1
        elif modo == "delay":
            if not b831:
                continue
            # range das barras 8h30+8h31; entra no rompimento na 8h32+
            dhi = max(gh, b831[1])
            dlo = min(gl, b831[2])
            b832 = m.get(REL + 2)
            if not b832:
                continue
            if b832[3] > dhi:
                lado = 1
            elif b832[3] < dlo:
                lado = -1
            else:
                continue
            entry = b832[3] + lado * slip
            risco = sl_pts if sl_pts else max(dhi - dlo, 2 * TICK)
            ini_k = REL + 3
        else:
            raise ValueError(modo)

        stop = entry - lado * risco
        target = entry + lado * rr * risco
        saida = simula(m, lado, entry, stop, target, slip, ini_k)
        pnl = ((saida - entry) * lado) * PV - RT
        trades.append((dia, lado, pnl, risco))
    return trades


def linha(lbl, tr):
    is_ = base.stats([t for t in tr if t[0] < "2026"])
    oo = base.stats([t for t in tr if t[0] >= "2026"])
    if not is_:
        print(f"  {lbl:<34} (sem trades)")
        return
    mark = " <<<" if is_["pf"] >= 1.3 else ""
    o = f"| 26: PF {oo['pf']:.2f} ${oo['net']:,.0f}" if oo else ""
    print(f"  {lbl:<34} n{is_['n']:>4}  WR {is_['wr']:>4.0f}%  PF {is_['pf']:>4.2f}  "
          f"net ${is_['net']:>8,.0f}  avg ${is_['avg']:>5.0f}  DD ${is_['mdd']:>8,.0f}  {o}{mark}")


if __name__ == "__main__":
    bars = base.carrega()
    eventos, por_dia = base.detecta_eventos(bars)
    print(f"{len(eventos)} eventos | IS = 2022-2025, holdout = 2026\n")

    print("=== A) FADE (entra contra o rompimento da barra 8h30) ===")
    for slip in (3, 5):
        for rr in (1.0, 1.5, 2.0):
            for sl in (0, 15, 25):
                linha(f"fade slip{slip} SL{'barra' if not sl else sl} {rr}:1",
                      bt(eventos, por_dia, "fade", slip, rr, sl))
    print("\n=== B) DELAY (range 8h30+31, entra rompimento na 8h32+) ===")
    for slip in (3, 5):
        for rr in (1.5, 2.0, 3.0):
            for sl in (0, 15, 25):
                linha(f"delay slip{slip} SL{'barra' if not sl else sl} {rr}:1",
                      bt(eventos, por_dia, "delay", slip, rr, sl))
    print("\n=== C) BREAKOUT so nos eventos GRANDES (spike >= Nx) ===")
    for vmin in (5, 7, 10):
        for rr in (1.5, 2.0):
            linha(f"break vol>={vmin}x slip5 barra {rr}:1",
                  bt(eventos, por_dia, "breakout", 5, rr, 0, vmin))
    print("\n=== C2) FADE so nos eventos GRANDES ===")
    for vmin in (5, 7, 10):
        for rr in (1.0, 1.5):
            linha(f"fade vol>={vmin}x slip5 barra {rr}:1",
                  bt(eventos, por_dia, "fade", 5, rr, 0, vmin))
