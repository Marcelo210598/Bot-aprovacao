#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Candidata A — momentum continuation (02/09).

Tese (docs/estrategia-nova-2026-09.md): o MNQ TENDE (foi o que matou a reversao).
Entao opere a favor: dia com 1a hora direcional forte -> entra nos pullbacks na
direcao da tendencia, deixa correr 2-3R.

Regra tosca:
  - 1a hora RTH = 9h30-10h29 ET. Mede range, direcao (close vs open), forca
    (|close-open| / range) e range/ATR14.
  - So opera se: forca >= FORCA_MIN E range/ATR >= RNG_ATR_MIN (dia que "abriu andando").
  - Bias = direcao da 1a hora. Espera pullback: preco retrai PB_FRAC do range da 1a
    hora a partir do extremo.
  - Entrada: 1a barra apos o pullback que RETOMA (close volta alem do extremo da
    barra anterior na direcao do bias).
  - Stop = extremo do pullback +/- buffer. Alvo = RR x risco (fixo). Flat 15h30 ET.
  - 1 trade/dia, slippage 5t, 5 MNQ, custo $6,50 RT.

IS 2022-2025, holdout 2026. Corte pra .cs: PF > 1,3 IS com custo+slippage.
"""
import statistics as st
from collections import defaultdict

import run_event_830 as base
from run_gap_open_v2 import prep

TICK = 0.25
PV = 2.0 * 5
RT = 1.30 * 5
OPEN = 9 * 60 + 30
H1END = OPEN + 60          # fim da 1a hora
FLAT = 15 * 60 + 30


def bt(pd, dias, atr, forca_min, rng_atr_min, pb_frac, rr, slip_ticks=5,
       buf_ticks=4, flat_min=FLAT):
    slip = slip_ticks * TICK
    buf = buf_ticks * TICK
    trades = []
    for d in dias:
        if d not in atr:
            continue
        m = pd[d]
        h1 = [m[k] for k in range(OPEN, H1END) if k in m]
        if len(h1) < 50:
            continue
        o1 = h1[0][0]
        hi1 = max(x[1] for x in h1)
        lo1 = min(x[2] for x in h1)
        c1 = h1[-1][3]
        rng = hi1 - lo1
        if rng <= 0:
            continue
        forca = abs(c1 - o1) / rng
        if forca < forca_min or rng / atr[d] < rng_atr_min:
            continue
        bias = 1 if c1 > o1 else -1
        ext = hi1 if bias == 1 else lo1
        gatilho_pb = ext - bias * pb_frac * rng   # nivel de pullback

        # varre a tarde: espera pullback, depois retomada
        pb_ok = False
        pb_ext = None
        entry = None
        prev = None
        for k in range(H1END, flat_min + 1):
            b = m.get(k)
            if not b:
                continue
            bo, bh, bl, bc, bv = b
            if not pb_ok:
                if (bias == 1 and bl <= gatilho_pb) or (bias == -1 and bh >= gatilho_pb):
                    pb_ok = True
                    pb_ext = bl if bias == 1 else bh
                prev = b
                continue
            # depois do pullback: atualiza extremo do pullback e busca retomada
            pb_ext = min(pb_ext, bl) if bias == 1 else max(pb_ext, bh)
            if prev is not None:
                if bias == 1 and bc > prev[1]:
                    entry = bc + slip
                    ke = k
                    break
                if bias == -1 and bc < prev[2]:
                    entry = bc - slip
                    ke = k
                    break
            prev = b
        if entry is None:
            continue

        risco = abs(entry - pb_ext) + buf
        risco = max(risco, 5.0)
        stop = entry - bias * risco
        target = entry + bias * rr * risco

        saida = None
        for k in range(ke + 1, flat_min + 1):
            b = m.get(k)
            if not b:
                continue
            _, bh, bl, bc, _ = b
            if bias == 1:
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
        trades.append((d, bias, ((saida - entry) * bias) * PV - RT, risco))
    return trades


def rep(lbl, tr):
    isr = base.stats([t for t in tr if t[0] < "2026"])
    oo = base.stats([t for t in tr if t[0] >= "2026"])
    if not isr or isr["n"] < 20:
        print(f"  {lbl:<44} n={isr['n'] if isr else 0} (amostra pequena)")
        return
    mk = "  <<<" if (isr["pf"] >= 1.3 and (not oo or oo["pf"] >= 1.1)) else ""
    o = f" | 26: PF {oo['pf']:.2f} ${oo['net']:,.0f} n{oo['n']}" if oo else ""
    print(f"  {lbl:<44} n{isr['n']:>4} WR{isr['wr']:>4.0f}% PF {isr['pf']:>4.2f} "
          f"net ${isr['net']:>8,.0f} avg ${isr['avg']:>5.0f} DD ${isr['mdd']:>7,.0f}{o}{mk}")


if __name__ == "__main__":
    bars = base.carrega()
    pd, dias, rth_cl, atr, ret_prev = prep(bars)
    print(f"{len(dias)} dias | ATR14 em {len(atr)} | IS 2022-2025 / holdout 2026\n")

    print("=== momentum continuation: 1a hora forte -> pullback -> retomada ===")
    for fm in (0.45, 0.55, 0.65):
        for ra in (0.6, 0.8, 1.0):
            for pb in (0.33, 0.5):
                for rr in (2.0, 3.0):
                    rep(f"forca>={fm} rng/atr>={ra} pb{pb} {rr}:1",
                        bt(pd, dias, atr, fm, ra, pb, rr))
        print()

    print("=== ano a ano (forca>=0.55, rng/atr>=0.8, pb0.5, 2:1) ===")
    tr = bt(pd, dias, atr, 0.55, 0.8, 0.5, 2.0)
    d = defaultdict(list)
    for t in tr:
        d[t[0][:4]].append(t)
    for a, v in sorted(d.items()):
        s = base.stats(v)
        print(f"    {a}: n{s['n']:>3} WR {s['wr']:>4.0f}% PF {s['pf']:>4.2f} "
              f"net ${s['net']:>8,.0f} avg ${s['avg']:>5.0f} maxDD ${s['mdd']:>8,.0f}")
