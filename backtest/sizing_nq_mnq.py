#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SIZING: 10/20/30/40 MNQ (= 1/2/3/4 NQ), confirmado permitido pela Apex.
Mesma sequencia cronologica dos 1084 trades, mesmo motor de saida (SL12,5/
TP60/BE3,75-2,5/trail1,75), mesmo modelo de DD (EOD, ja confirmado identico
ao unico modelo usado o dia inteiro), meta $1.500 / DD $1.000 FIXOS.
Escala linear ja provada exata (PV e RT escalam com N_CONTR).
"""
import sys, os
from datetime import timedelta, datetime
sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp
import gargalo_fase1_3 as g1

bars = dp.carregar_1min(dp.PASTA_DADOS)
trades_base = g1.simula_com_duracao_hora(bars)  # 5 MNQ (baseline de producao)
print(f"{len(trades_base)} trades base (5 MNQ)\n")

META = 1500.0; DD_LIM = 1000.0; MIN_DIAS = 7
CONTR_BASE = 5

BLOCOS = [
    ('B1', '2025-06-13', '2025-08-12'),
    ('B2', '2025-08-13', '2025-11-05'),
    ('B3', '2025-11-06', '2026-01-27'),
    ('B4', '2026-01-28', '2026-04-10'),
    ('B5', '2026-04-13', '2026-06-11'),
]

def escala(trades, n_contr):
    fator = n_contr / CONTR_BASE
    return [{'pnl_usd': t['pnl_usd']*fator, 'data': t['data']} for t in trades]

def media(xs): return sum(xs)/len(xs) if xs else 0
def mediana(xs):
    xs = sorted(xs); m = len(xs)
    return xs[m//2] if m%2 else (xs[m//2-1]+xs[m//2])/2

def simula_janelas(trades, meta, dd_lim, min_dias=7, filtro_data=None):
    pnl_dia = {}
    for t in trades: pnl_dia[t['data']] = pnl_dia.get(t['data'], 0.0) + t['pnl_usd']
    datas_ord = sorted(pnl_dia)
    if filtro_data:
        datas_ord = [d for d in datas_ord if filtro_data[0] <= d <= filtro_data[1]]
    if not datas_ord: return None
    dts = [datetime.strptime(d, '%Y-%m-%d') for d in datas_ord]
    trades_por_dia = {}
    for t in trades:
        if t['data'] in pnl_dia and (not filtro_data or filtro_data[0]<=t['data']<=filtro_data[1]):
            trades_por_dia.setdefault(t['data'], []).append(t)

    aprovadas=estouradas=0; pnls=[]; dds=[]; trades_n=[]; dias_n=[]; tempos_meta=[]
    for i, d0 in enumerate(dts):
        fim = d0 + timedelta(days=29)
        acumulado=0.0; pico=0.0; dd_max=0.0; dias_op=0; nt=0; resultado=None
        for j in range(i, len(dts)):
            dj = dts[j]
            if dj > fim: break
            acumulado += pnl_dia[datas_ord[j]]; dias_op += 1
            nt += len(trades_por_dia.get(datas_ord[j], []))
            pico = max(pico, acumulado); dd_max = max(dd_max, pico-acumulado)
            if dd_max > dd_lim: resultado='BUST'; break
            if acumulado >= meta and dias_op >= min_dias:
                resultado='APROVOU'; tempos_meta.append(j-i); break
        if resultado is None: resultado='INCOMPLETA'
        if resultado=='APROVOU': aprovadas+=1
        elif resultado=='BUST': estouradas+=1
        pnls.append(acumulado); dds.append(dd_max); trades_n.append(nt); dias_n.append(dias_op)
    total = len(dts)
    return {'total':total,'aprovadas':aprovadas,'estouradas':estouradas,
            'taxa':aprovadas/total*100,'taxa_bust':estouradas/total*100,
            'pnl_med':media(pnls),'pnl_mediana':mediana(pnls),
            'dd_med':media(dds),'dd_max':max(dds) if dds else 0,
            'trades_med':media(trades_n),'dias_med':media(dias_n),
            'tempo_med':media(tempos_meta) if tempos_meta else None,
            'tempo_mediana':mediana(tempos_meta) if tempos_meta else None}

SIZINGS = [(10,'1 NQ'), (20,'2 NQ'), (30,'3 NQ'), (40,'4 NQ')]

print("=" * 130)
print(f"TABELA PRINCIPAL — meta ${META:.0f} / DD ${DD_LIM:.0f} FIXOS, ano inteiro")
print("=" * 130)
print(f"{'MNQ':<6}{'NQequiv':<9}{'Aprov%':<9}{'Bust%':<8}{'PnLmed':<10}{'PnLmediana':<12}{'DDmed':<9}{'DDmax':<9}"
      f"{'TempoMed':<10}{'TempoMediana':<13}{'TradesMed':<11}{'DiasMed'}")
resultados_full = {}
for mnq, nome in SIZINGS:
    tr = escala(trades_base, mnq)
    r = simula_janelas(tr, META, DD_LIM, MIN_DIAS)
    resultados_full[mnq] = (tr, r)
    tm = f"{r['tempo_med']:.1f}d" if r['tempo_med'] else "N/A"
    tmed = f"{r['tempo_mediana']:.1f}d" if r['tempo_mediana'] else "N/A"
    print(f"{mnq:<6}{nome:<9}{r['taxa']:<9.1f}{r['taxa_bust']:<8.1f}${r['pnl_med']:<9.1f}"
          f"${r['pnl_mediana']:<11.1f}${r['dd_med']:<8.1f}${r['dd_max']:<8.1f}{tm:<10}{tmed:<13}"
          f"{r['trades_med']:<11.1f}{r['dias_med']:.1f}")

print(f"\n(referencia) 5 MNQ atual: Aprov=47,0% Bust=2,4% -- ja calculado antes, config de producao")

print("\n" + "=" * 130)
print("APROVACAO POR BLOCO CRONOLOGICO (mesmos 5 blocos ja definidos, sem reotimizar)")
print("=" * 130)
print(f"{'MNQ':<6}" + "".join(f"{b[0]:<9}" for b in BLOCOS))
for mnq, nome in SIZINGS:
    tr, _ = resultados_full[mnq]
    linha = f"{mnq:<6}"
    for bnome, ini, fim in BLOCOS:
        rb = simula_janelas(tr, META, DD_LIM, MIN_DIAS, filtro_data=(ini, fim))
        taxa = rb['taxa'] if rb else 0
        linha += f"{taxa:<9.1f}"
    print(linha)

print("\n" + "=" * 130)
print("PRIMEIRA METADE vs SEGUNDA METADE (robustez temporal)")
print("=" * 130)
todas_datas = sorted({t['data'] for t in trades_base})
meio = todas_datas[len(todas_datas)//2]
print(f"{'MNQ':<6}{'Aprov 1a metade':<18}{'Aprov 2a metade'}")
for mnq, nome in SIZINGS:
    tr, _ = resultados_full[mnq]
    r1 = simula_janelas(tr, META, DD_LIM, MIN_DIAS, filtro_data=(todas_datas[0], meio))
    r2 = simula_janelas(tr, META, DD_LIM, MIN_DIAS, filtro_data=(meio, todas_datas[-1]))
    t1 = r1['taxa'] if r1 else 0; t2 = r2['taxa'] if r2 else 0
    print(f"{mnq:<6}{t1:<18.1f}{t2:.1f}")
