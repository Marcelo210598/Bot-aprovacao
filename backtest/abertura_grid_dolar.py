#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GRID SEARCH — modo v7 do AberturaExplosao.cs (espera N s, LE O CAMINHO desde o
open, SEGUE/FADA, gestao em $: StopDolar fixo + TrailDolar ratchet apos Respiro).

Replica bit-a-bit a ordem de checagem do OnMarketData (secao 4 e 5 do .cs):
  1) espera EsperaSegundos, olha o CLOSE do bar de 1s vs open, dispara se
     |disp| >= GatilhoTicks (dentro da JanelaLeituraSeg).
  2) gestao por bar, ADVERSO primeiro (conservador, mesma convencao do
     abertura_harness.py): checa stop/trail (nivel da barra ANTERIOR) contra o
     pior preco do bar; so' depois checa alvo contra o melhor preco do bar; so'
     DEPOIS atualiza hwm/trailing pro proximo bar.

Dado: 1s OHLC Databento (2024/2025/2026ago, ~700+ pregoes) -> MUITO mais amostra
que os 6-9 dias olhados a olho no NT8 ontem (10/09). Mesma ressalva de sempre:
granularidade 1s, nao bit-exact com tick replay -> validar os melhores achados
no NT8 antes de ir pra conta real.

Uso: python3 backtest/abertura_grid_dolar.py
"""
import importlib.util
import itertools
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('h', os.path.join(HERE, 'abertura_harness.py'))
H = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(H)

TICK = H.TICK
PV = H.POINT_VALUE
QTY = 6
COMM = 1.24
JANELA = 180


def simula(day, gat, espera, alvo, stopd, traild, respiro, inverter):
    o, h, l, c, sod = day['o'], day['h'], day['l'], day['c'], day['sod']
    n = len(o)
    t0 = sod[0]
    open_px = o[0]

    trig_i = -1
    direction = 0
    for i in range(n):
        decorrido = sod[i] - t0
        if decorrido < espera:
            continue
        if decorrido > espera + JANELA:
            break
        disp = c[i] - open_px
        if disp >= gat * TICK:
            direction = 1
            trig_i = i
            break
        elif disp <= -gat * TICK:
            direction = -1
            trig_i = i
            break
    if trig_i < 0:
        return None
    if inverter:
        direction = -direction

    entry = c[trig_i]
    entry_sod = sod[trig_i]
    hwm = 0.0
    stop_lock = -stopd
    saida = None
    motivo = None
    SLIP = TICK * PV * QTY  # 1 tick de slippage no fill do stop sintetico (referencia)

    for i in range(trig_i + 1, n):
        if direction == 1:
            op_px, lo_px, hi_px = o[i], l[i], h[i]
        else:
            op_px, lo_px, hi_px = o[i], h[i], l[i]
        op_dollar = (op_px - entry) * direction * PV * QTY
        pnl_lo = (lo_px - entry) * direction * PV * QTY
        pnl_hi = (hi_px - entry) * direction * PV * QTY

        if pnl_lo <= stop_lock:
            # GAP: se o bar ja ABRE alem do nivel do stop, o fill (ordem a mercado)
            # enche no preco de abertura do bar (ou pior), nao no nivel calculado.
            # Mesma convencao do abertura_harness.py (fill_stop). Sem isso o sim
            # ignora reversao violenta e fica otimista demais (bug achado 11/09
            # comparando com o Replay real do NT8 - AbBe que devia ser ~0 encheu
            # a -$283 no dia 01/06 real).
            fill = op_dollar if op_dollar < stop_lock else stop_lock - SLIP
            saida = max(fill, pnl_lo)   # nunca pior que o extremo real do bar
            motivo = 'STOP' if stop_lock < -1e-6 else ('BE' if stop_lock < traild else 'TRAIL')
            break
        if alvo > 0 and pnl_hi >= alvo:
            saida = alvo
            motivo = 'ALVO'
            break
        if pnl_hi > hwm:
            hwm = pnl_hi
        if (sod[i] - entry_sod) >= respiro and hwm > 0:
            cand = hwm - traild
            if cand > stop_lock:
                stop_lock = cand

    if saida is None:
        saida = (c[-1] - entry) * direction * PV * QTY
        motivo = 'FLATTEN'

    return saida - COMM * QTY, motivo


def roda_config(all_days, gat, espera, alvo, stopd, traild, respiro, inverter):
    net = []
    motivos = {}
    for d in all_days:
        r = simula(d, gat, espera, alvo, stopd, traild, respiro, inverter)
        if r is None:
            continue
        pnl, mot = r
        net.append(pnl)
        motivos[mot] = motivos.get(mot, 0) + 1
    if not net:
        return None
    a = np.array(net)
    eq = np.cumsum(a)
    maxdd = -(eq - np.maximum.accumulate(eq)).min()
    streak = worst = 0.0
    for x in a:
        streak = streak + x if x < 0 else 0.0
        worst = min(worst, streak)
    return dict(n=len(a), wr=(a > 0).mean(), media=a.mean(), total=a.sum(),
                maxdd=maxdd, streak=worst, motivos=motivos)


def main():
    print("carregando dados 1s (2024/2025/2026ago)...")
    all_days = []
    for label, fn in H.BLOCOS:
        all_days += H.load_days(fn)
    print(f"  {len(all_days)} pregoes carregados\n")

    # ---------------- grid ----------------
    esperas = [0, 5, 10, 15, 30, 60, 90]
    stops = [50, 75, 100, 150, 200, 250]
    trails = [15, 25, 40, 60, 100]
    respiros = [0, 10, 20]
    gatilhos = [3]
    alvos = [500]
    inverters = [False, True]

    combos = list(itertools.product(gatilhos, esperas, alvos, stops, trails, respiros, inverters))
    print(f"testando {len(combos)} configs x {len(all_days)} pregoes...\n")

    resultados = []
    for gat, espera, alvo, stopd, traild, respiro, inverter in combos:
        if traild >= stopd:
            continue  # trail mais largo que o stop nao faz sentido
        r = roda_config(all_days, gat, espera, alvo, stopd, traild, respiro, inverter)
        if r is None or r['n'] < 30:
            continue
        r.update(gat=gat, espera=espera, alvo=alvo, stopd=stopd, traild=traild,
                  respiro=respiro, inverter=inverter)
        resultados.append(r)

    print(f"{len(resultados)} configs com n>=30\n")

    def linha(r):
        dirlabel = 'FADA' if r['inverter'] else 'SEGUE'
        return (f"{dirlabel:<5} espera={r['espera']:>3}s stop=${r['stopd']:>3} trail=${r['traild']:>3} "
                f"respiro={r['respiro']:>2}s alvo=${r['alvo']:<4} | n={r['n']:>4} wr={r['wr']:>4.0%} "
                f"$/trade={r['media']:>+7.2f} total={r['total']:>+8.0f} maxDD={r['maxdd']:>6.0f} "
                f"streak={r['streak']:>+6.0f}")

    print("=" * 20, "TOP 25 por TOTAL ($)", "=" * 20)
    for r in sorted(resultados, key=lambda x: -x['total'])[:25]:
        print(linha(r))

    print()
    print("=" * 20, "TOP 25 por $/TRADE (n>=50)", "=" * 20)
    for r in sorted([x for x in resultados if x['n'] >= 50], key=lambda x: -x['media'])[:25]:
        print(linha(r))

    print()
    print("=" * 20, "PIOR 10 por TOTAL (referencia)", "=" * 20)
    for r in sorted(resultados, key=lambda x: x['total'])[:10]:
        print(linha(r))

    pos = sum(1 for r in resultados if r['total'] > 0)
    print(f"\n{pos}/{len(resultados)} configs deram total positivo ({pos/len(resultados):.0%})")


if __name__ == '__main__':
    main()
