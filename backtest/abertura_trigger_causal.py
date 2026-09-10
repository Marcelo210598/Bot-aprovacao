#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIAGNOSTICO (10/09/2026): o edge da ABERTURA depende de look-ahead intra-segundo.

Pergunta: em quantos pregoes o 1o bar de 1s (09:30:00) toca OS DOIS lados
(open+3t E open-3t) no mesmo segundo? E de quem depende o resultado?

Achado:
  - ~65% dos pregoes: o 1o segundo pos-abertura toca +3t E -3t (whipsaw).
    OHLC de 1s NAO diz qual lado veio primeiro.
  - O harness/sim de ontem resolvia isso pela COR do bar (close>=open => long).
    Isso e' escolher a direcao que o mercado ACABOU indo naquele segundo = look-ahead.
  - Removendo o look-ahead:
      * entrar so quando um bar de 1s FECHA alem do nivel (causal, mas persegue):
        wr ~22%, -$11/trade (6 MNQ) — IGUAL ao controle "sempre long".
      * so operar dias em que o 1o bar toca UM lado so, entrada no nivel:
        wr ~62%, +$35/trade — MAS so 91 trades (26% dos dias), amostra fina.

Conclusao: o dado de 1s do Databento nao tem resolucao pra validar essa estrategia.
Precisa de tick/trades real (ordem dos toques) OU forward test no NT8 (tick replay).

Uso: python3 backtest/abertura_trigger_causal.py
"""
import importlib.util
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('h', os.path.join(HERE, 'abertura_harness.py'))
H = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(H)

TICK = H.TICK
PV = 2.0
QTY = 6
COMM = 1.24
N = 3
S = 6


def _gestao(o, hh, ll, c, ti, direction, entry):
    stop_fav = -float(S)
    hwm = 0.0
    be = False
    for i in range(ti + 1, len(o)):
        if direction == 1:
            hi = (hh[i] - entry) / TICK
            lo = (ll[i] - entry) / TICK
            op = (o[i] - entry) / TICK
        else:
            hi = (entry - ll[i]) / TICK
            lo = (entry - hh[i]) / TICK
            op = (entry - o[i]) / TICK
        if lo <= stop_fav:
            fill = op if op < stop_fav else stop_fav - 1
            return max(fill, lo)
        if hi > hwm:
            hwm = hi
        if not be and hwm >= S:
            stop_fav = max(stop_fav, 0.0)
            be = True
        if be:
            stop_fav = max(stop_fav, hwm - S)
    return (c[-1] - entry) / TICK * direction


def modo_lookahead(d):
    """como ontem: 1o toque de wick; se toca os 2 lados no msm bar, cor do bar."""
    o, hh, ll, c, sod = d['o'], d['h'], d['l'], d['c'], d['sod']
    up = o[0] + N * TICK
    dn = o[0] - N * TICK
    t0 = sod[0]
    for i in range(len(o)):
        if sod[i] - t0 > 180:
            return None
        hu = hh[i] >= up
        hd = ll[i] <= dn
        if hu and hd:
            direction = 1 if c[i] >= o[i] else -1
        elif hu:
            direction = 1
        elif hd:
            direction = -1
        else:
            continue
        entry = (up if direction == 1 else dn) + direction * TICK
        return _gestao(o, hh, ll, c, i, direction, entry) * TICK * PV * QTY - COMM * QTY
    return None


def modo_fecha_alem(d):
    """causal: entra quando um bar de 1s FECHA alem do nivel; entrada no close."""
    o, hh, ll, c, sod = d['o'], d['h'], d['l'], d['c'], d['sod']
    up = o[0] + N * TICK
    dn = o[0] - N * TICK
    t0 = sod[0]
    for i in range(len(o)):
        if sod[i] - t0 > 180:
            return None
        if c[i] >= up:
            direction = 1
        elif c[i] <= dn:
            direction = -1
        else:
            continue
        entry = c[i] + direction * TICK
        return _gestao(o, hh, ll, c, i, direction, entry) * TICK * PV * QTY - COMM * QTY
    return None


def modo_dias_limpos(d):
    """causal: so opera se o 1o bar (09:30:00) toca UM lado so. entrada no nivel."""
    o, hh, ll, c = d['o'], d['h'], d['l'], d['c']
    up = o[0] + N * TICK
    dn = o[0] - N * TICK
    hu = hh[0] >= up
    hd = ll[0] <= dn
    if hu == hd:
        return None
    direction = 1 if hu else -1
    entry = (up if direction == 1 else dn) + direction * TICK
    return _gestao(o, hh, ll, c, 0, direction, entry) * TICK * PV * QTY - COMM * QTY


def main():
    modos = [('look-ahead (ontem)', modo_lookahead),
             ('causal: fecha-alem', modo_fecha_alem),
             ('causal: dias limpos', modo_dias_limpos)]
    print(f"{'bloco':<12} {'modo':<22} {'n':>4} {'wr':>5} {'$/trade':>9} {'total':>8}")
    for label, fn in H.BLOCOS:
        days = H.load_days(fn)
        for nome, fnmod in modos:
            a = np.array([x for x in (fnmod(d) for d in days) if x is not None])
            if len(a) == 0:
                continue
            print(f"{label:<12} {nome:<22} {len(a):>4} {(a > 0).mean():>4.0%} "
                  f"{a.mean():>+9.2f} {a.sum():>+8.0f}")
        print()

    # quantos dias sao ambiguos
    print("--- ambiguidade do 1o segundo ---")
    for label, fn in H.BLOCOS:
        days = H.load_days(fn)
        amb = sum(1 for d in days
                  if (d['h'][0] >= d['o'][0] + N * TICK) and (d['l'][0] <= d['o'][0] - N * TICK))
        print(f"  {label:<12} {amb}/{len(days)} dias o 1o bar toca +{N}t E -{N}t no mesmo segundo "
              f"({amb / len(days):.0%})")


if __name__ == '__main__':
    main()
