#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FIX: robustez por bloco calculada CORRETAMENTE -- constroi as 166 janelas
completas (sem truncar no limite do bloco) e DEPOIS agrupa pela data de
INICIO da janela, exatamente como na auditoria estatistica original."""
import sys, os
from datetime import timedelta, datetime
sys.path.insert(0, os.path.dirname(__file__))
import saidas_parciais_completo as spc

bars = spc.bars
trades = spc.trades
META=1500.0; DD_LIM=1000.0; MIN_DIAS=7
BLOCOS = [('B1','2025-06-13','2025-08-12'), ('B2','2025-08-13','2025-11-05'),
          ('B3','2025-11-06','2026-01-27'), ('B4','2026-01-28','2026-04-10'),
          ('B5','2026-04-13','2026-06-11')]

def constroi_janelas(trs):
    pnl_dia={}
    for t in trs: pnl_dia[t['data']]=pnl_dia.get(t['data'],0.0)+t['pnl_usd']
    datas_ord=sorted(pnl_dia)
    dts=[datetime.strptime(d,'%Y-%m-%d') for d in datas_ord]
    janelas=[]
    for i,d0 in enumerate(dts):
        fim=d0+timedelta(days=29)
        acumulado=0.0; pico=0.0; dd_max=0.0; dias_op=0; resultado=None
        for j in range(i,len(dts)):
            dj=dts[j]
            if dj>fim: break
            acumulado+=pnl_dia[datas_ord[j]]; dias_op+=1
            pico=max(pico,acumulado); dd_max=max(dd_max,pico-acumulado)
            if dd_max>DD_LIM: resultado='BUST'; break
            if acumulado>=META and dias_op>=MIN_DIAS: resultado='APROVOU'; break
        if resultado is None: resultado='INCOMPLETA'
        janelas.append({'inicio':datas_ord[i], 'aprovou':resultado=='APROVOU'})
    return janelas

candidatos = {
    'A (baseline)': [{'pnl_usd': t['pnl_usd'], 'data': t['data']} for t in trades],
    'D(3+2)@15pt': [{'pnl_usd': spc.pnl_parcial(t, 15.0, 3, 2), 'data': t['data']} for t in trades],
    'E(4+1)@15pt': [{'pnl_usd': spc.pnl_parcial(t, 15.0, 4, 1), 'data': t['data']} for t in trades],
    'D(3+2)@20pt': [{'pnl_usd': spc.pnl_parcial(t, 20.0, 3, 2), 'data': t['data']} for t in trades],
    'E(4+1)@20pt': [{'pnl_usd': spc.pnl_parcial(t, 20.0, 4, 1), 'data': t['data']} for t in trades],
}

print("=" * 110)
print("ROBUSTEZ TEMPORAL CORRIGIDA -- janelas completas (166), agrupadas por bloco de INICIO")
print("=" * 110)
print(f"{'Modelo':<16}" + "".join(f"{b[0]:<9}" for b in BLOCOS) + "1a met.   2a met.")
for nome, trs in candidatos.items():
    janelas = constroi_janelas(trs)
    n = len(janelas)
    linha = f"{nome:<16}"
    for bnome, ini, fim in BLOCOS:
        grupo = [j for j in janelas if ini <= j['inicio'] <= fim]
        taxa = sum(1 for j in grupo if j['aprovou'])/len(grupo)*100 if grupo else 0
        linha += f"{taxa:<9.1f}"
    meio_idx = n // 2
    metade1 = janelas[:meio_idx]; metade2 = janelas[meio_idx:]
    t1 = sum(1 for j in metade1 if j['aprovou'])/len(metade1)*100 if metade1 else 0
    t2 = sum(1 for j in metade2 if j['aprovou'])/len(metade2)*100 if metade2 else 0
    linha += f"{t1:<9.1f}{t2:.1f}"
    print(linha)
