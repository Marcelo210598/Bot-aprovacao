#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Candidata C — gap de abertura (Globex close -> RTH open).
Probe rapido (02/09) depois que a candidata B (event 8h30) reprovou.

Achado do probe: gap-FILL (fade) e' catastrofico no MNQ 2022-2026 (PF ~0,2 — o
indice TENDE, nao volta pro close). Mas gap-and-GO (gap medio que segura os 1os
15 min -> vai a favor) deu PF ~1,23 IS 2022-2025 E ~1,27 no holdout 2026 — 1a coisa
da exploracao toda com IS/OOS consistente.

Regras: RTH open = 9h30 ET; prior RTH close = 16h00 ET do dia anterior.
Bracket fixo, slippage 3-5t, 5 MNQ, custo $6,50 RT. IS 2022-2025, holdout 2026.
Corte pra .cs: PF > 1,3 IS com custo+slippage + OOS consistente.

Dado: dados_databento/MNQ_1min_2022_2026.txt (UTC, front-month).
"""
import os
from collections import defaultdict

import run_event_830 as base

TICK = 0.25
PV = 2.0 * 5
RT = 1.30 * 5
OPEN = 9 * 60 + 30
CLOSE = 16 * 60


def por_dia(bars):
    d = defaultdict(dict)
    for dt, o, h, l, c, v in bars:
        d[dt.strftime("%Y-%m-%d")][dt.hour * 60 + dt.minute] = (o, h, l, c, v)
    return d


def bt(pd, modo, slip_ticks, rr, flat_min, gap_lo, gap_hi, hold_min=15):
    slip = slip_ticks * TICK
    dias = sorted(pd)
    trades = []
    for i in range(1, len(dias)):
        d, dp = dias[i], dias[i - 1]
        m, mp = pd[d], pd[dp]
        bo = m.get(OPEN)
        bpc = mp.get(CLOSE) or mp.get(CLOSE - 1)
        if not bo or not bpc:
            continue
        pc, op = bpc[3], bo[0]
        gap = op - pc
        if not (gap_lo <= abs(gap) <= gap_hi):
            continue
        w = [m[k] for k in range(OPEN, OPEN + hold_min) if k in m]
        if len(w) < hold_min - 3:
            continue
        whi = max(x[1] for x in w)
        wlo = min(x[2] for x in w)

        if modo == "fill":
            lado = -1 if gap > 0 else 1
            entry = op + lado * slip
            risco = max((whi - op) if gap > 0 else (op - wlo), 10.0)
            stop = entry - lado * risco
            target = pc
            ini = OPEN + 1
        else:  # go
            bH = m.get(OPEN + hold_min)
            if not bH:
                continue
            held = (bH[3] > pc) if gap > 0 else (bH[3] < pc)
            if not held:
                continue
            lado = 1 if gap > 0 else -1
            entry = bH[3] + lado * slip
            risco = max(abs(bH[3] - (wlo if gap > 0 else whi)), 10.0)
            stop = entry - lado * risco
            target = entry + lado * rr * risco
            ini = OPEN + hold_min + 1

        saida = None
        for k in range(ini, flat_min + 1):
            b = m.get(k)
            if not b:
                continue
            _, bh, bl, bc, _ = b
            if lado == 1:
                if bl <= stop:
                    saida = stop - slip
                    break
                if bh >= target:
                    saida = target - slip
                    break
            else:
                if bh >= stop:
                    saida = stop + slip
                    break
                if bl <= target:
                    saida = target + slip
                    break
        if saida is None:
            bf = m.get(flat_min) or m.get(flat_min - 1)
            saida = bf[3] if bf else entry
        trades.append((d, lado, ((saida - entry) * lado) * PV - RT, risco))
    return trades


def rep(lbl, tr):
    isr = base.stats([t for t in tr if t[0] < "2026"])
    oo = base.stats([t for t in tr if t[0] >= "2026"])
    if not isr:
        print(f"  {lbl:<44} sem trades")
        return
    mk = "  <<<" if (isr["pf"] >= 1.3 and oo and oo["pf"] >= 1.1) else ""
    o = f" | 26: PF {oo['pf']:.2f} ${oo['net']:,.0f} n{oo['n']}" if oo else ""
    print(f"  {lbl:<44} n{isr['n']:>4} WR{isr['wr']:>4.0f}% PF {isr['pf']:>4.2f} "
          f"net ${isr['net']:>8,.0f} avg ${isr['avg']:>5.0f} DD ${isr['mdd']:>8,.0f}{o}{mk}")


if __name__ == "__main__":
    bars = base.carrega()
    pd = por_dia(bars)
    print(f"{len(pd)} dias | IS 2022-2025, holdout 2026\n")

    print("=== FILL (fade gap, alvo = prior close) ===")
    for glo, ghi in ((5, 40), (10, 60), (15, 80)):
        rep(f"fill gap {glo}-{ghi}pt slip3 flat12h", bt(pd, "fill", 3, 0, 12 * 60, glo, ghi))

    print("\n=== GO (gap segura 15min -> a favor, bracket fixo) ===")
    for glo, ghi in ((20, 150), (30, 200), (30, 120), (40, 250)):
        for rr in (1.5, 2.0, 3.0):
            for flat in (12 * 60, 13 * 60):
                rep(f"go {glo}-{ghi}pt slip5 {rr}:1 flat{flat//60}h",
                    bt(pd, "go", 5, rr, flat, glo, ghi))

    print("\n=== GO — best band, por ano (slip5, 2:1, flat13h, gap 30-200) ===")
    tr = bt(pd, "go", 5, 2.0, 13 * 60, 30, 200)
    d = defaultdict(list)
    for t in tr:
        d[t[0][:4]].append(t)
    for a, v in sorted(d.items()):
        s = base.stats(v)
        print(f"    {a}: n{s['n']:>3} WR {s['wr']:>4.0f}% PF {s['pf']:>4.2f} "
              f"net ${s['net']:>8,.0f} avg ${s['avg']:>5.0f} maxDD ${s['mdd']:>8,.0f}")
