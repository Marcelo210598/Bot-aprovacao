#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FASE 4 — SIZING. Reescala o baseline de 5 MNQ pra 1-8 contratos (linear,
ja provado exato: PV e RT escalam com N_CONTR) MANTENDO meta $1.500 e
DD $1.000 fixos (nao escalados) -- testa se o tamanho da aposta por trade
tem um ponto ótimo pra ESSA meta/DD especifica, nao pra maximizar PnL."""
import sys, os
from datetime import timedelta, datetime
sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp
import gargalo_fase1_3 as g1

bars = dp.carregar_1min(dp.PASTA_DADOS)
trades_base = g1.simula_com_duracao_hora(bars)  # 5 MNQ (baseline)
print(f"{len(trades_base)} trades base (5 MNQ)\n")

META = 1500.0; DD_LIM = 1000.0; MIN_DIAS = 7
CONTR_BASE = 5

def escala(trades, n_contr):
    fator = n_contr / CONTR_BASE
    return [{'pnl_usd': t['pnl_usd']*fator, 'data': t['data']} for t in trades]


def simula_janelas(trades, meta, dd_lim, min_dias=7):
    pnl_dia = {}
    for t in trades: pnl_dia[t['data']] = pnl_dia.get(t['data'], 0.0) + t['pnl_usd']
    datas_ord = sorted(pnl_dia)
    dts = [datetime.strptime(d, '%Y-%m-%d') for d in datas_ord]
    aprovadas = estouradas = 0
    pnls = []; dds = []; seqs = []; tempos_meta = []
    for i, d0 in enumerate(dts):
        fim = d0 + timedelta(days=29)
        acumulado = 0.0; pico = 0.0; dd_max = 0.0; dias_op = 0
        seq = maxseq = 0; resultado = None
        for j in range(i, len(dts)):
            dj = dts[j]
            if dj > fim: break
            pnl_do_dia = pnl_dia[datas_ord[j]]
            acumulado += pnl_do_dia; dias_op += 1
            if pnl_do_dia < 0: seq += 1; maxseq = max(maxseq, seq)
            else: seq = 0
            pico = max(pico, acumulado); dd_max = max(dd_max, pico - acumulado)
            if dd_max > dd_lim: resultado = 'BUST'; break
            if acumulado >= meta and dias_op >= min_dias:
                resultado = 'APROVOU'; tempos_meta.append(j - i); break
        if resultado is None: resultado = 'INCOMPLETA'
        if resultado == 'APROVOU': aprovadas += 1
        elif resultado == 'BUST': estouradas += 1
        pnls.append(acumulado); dds.append(dd_max); seqs.append(maxseq)
    total = len(dts)
    return {'total': total, 'aprovadas': aprovadas, 'estouradas': estouradas,
            'taxa': aprovadas/total*100, 'taxa_bust': estouradas/total*100,
            'pnl_med': sum(pnls)/total, 'pnl_mediana': sorted(pnls)[total//2],
            'dd_med': sum(dds)/total, 'maxseq_med': sum(seqs)/total,
            'tempo_med_meta': sum(tempos_meta)/len(tempos_meta) if tempos_meta else None}


print("=" * 110)
print(f"SIZING 1-8 MNQ, meta ${META:.0f} / DD ${DD_LIM:.0f} FIXOS (nao escalados)")
print("=" * 110)
print(f"{'Contratos':<11}{'RiscoPorSL':<12}{'Aprov%':<9}{'Bust%':<8}{'PnLmed':<10}{'PnLmediana':<12}"
      f"{'DDmed':<9}{'MaxSeqMed':<11}{'TempoMedMeta'}")
for nc in range(1, 9):
    trades_sc = escala(trades_base, nc)
    r = simula_janelas(trades_sc, META, DD_LIM, MIN_DIAS)
    risco_sl = 12.5 * 2.0 * nc  # StopPontos * MNQ_PV * contratos
    valido = "" if risco_sl < DD_LIM else " ⚠️ risco/trade > DD"
    print(f"{nc:<11}${risco_sl:<11.1f}{r['taxa']:<9.1f}{r['taxa_bust']:<8.1f}${r['pnl_med']:<9.1f}"
          f"${r['pnl_mediana']:<11.1f}${r['dd_med']:<8.1f}{r['maxseq_med']:<11.1f}"
          f"{r['tempo_med_meta']:.1f}d{valido}" if r['tempo_med_meta'] else f"... N/A{valido}")
