#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FASE 2-3: classificacao das janelas de 30d (A-E) e mecanismo de falha.
Testa diretamente a hipotese da Fase 1: aprovacao depende de pegar um trade
de cauda (top decile) dentro da janela?"""
import sys, os
from datetime import timedelta, datetime
sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp
import gargalo_fase1_3 as g1

bars = dp.carregar_1min(dp.PASTA_DADOS)
trades = g1.simula_com_duracao_hora(bars)
n = len(trades)

META = 1500.0; DD_LIM = 1000.0; MIN_DIAS = 7

# threshold do "trade de cauda" = top 10% (decidido na Fase 1, nao reotimizado aqui)
trades_ord = sorted(trades, key=lambda t: -t['pnl_usd'])
limiar_cauda = trades_ord[int(n*0.10)]['pnl_usd']
print(f"Limiar de 'trade de cauda' (top 10%, ja definido na Fase 1): PnL >= ${limiar_cauda:.1f}\n")

pnl_dia = {}
trades_por_dia = {}
for t in trades:
    pnl_dia[t['data']] = pnl_dia.get(t['data'], 0.0) + t['pnl_usd']
    trades_por_dia.setdefault(t['data'], []).append(t)

datas_ord = sorted(pnl_dia)
dts = [datetime.strptime(d, '%Y-%m-%d') for d in datas_ord]

janelas = []
for i, d0 in enumerate(dts):
    fim = d0 + timedelta(days=29)
    acumulado = 0.0; pico = 0.0; dd_max = 0.0; dias_op = 0
    max_dist_meta = META; equity = []  # (dia_idx, acumulado)
    dias_sem_progresso = 0; pico_prev = 0.0
    n_trades_janela = 0; teve_cauda = False; sequencia_perdas_janela = 0; max_seq_janela = 0
    idx_aprovou = None; pico_antes_aprovar = 0.0; dd_antes_aprovar = 0.0
    resultado = None
    trades_janela = []

    for j in range(i, len(dts)):
        dj = dts[j]
        if dj > fim: break
        pnl_do_dia = pnl_dia[datas_ord[j]]
        acumulado += pnl_do_dia
        dias_op += 1
        n_trades_janela += len(trades_por_dia[datas_ord[j]])
        trades_janela.extend(trades_por_dia[datas_ord[j]])
        for t in trades_por_dia[datas_ord[j]]:
            if t['pnl_usd'] >= limiar_cauda: teve_cauda = True
            if t['pnl_usd'] < 0: sequencia_perdas_janela += 1; max_seq_janela = max(max_seq_janela, sequencia_perdas_janela)
            else: sequencia_perdas_janela = 0

        pico = max(pico, acumulado)
        dd_max = max(dd_max, pico - acumulado)
        max_dist_meta = min(max_dist_meta, META - acumulado)
        if pnl_do_dia <= 0: dias_sem_progresso += 1
        equity.append(acumulado)

        if dd_max > DD_LIM:
            resultado = 'BUST'; break
        if acumulado >= META and dias_op >= MIN_DIAS:
            resultado = 'APROVOU'; idx_aprovou = j - i
            pico_antes_aprovar = pico; dd_antes_aprovar = dd_max
            break

    if resultado is None:
        resultado = 'INCOMPLETA'

    # classificacao A-E
    frac_meta = acumulado / META
    if resultado == 'BUST':
        classe = 'E) falhou por DD'
    elif resultado == 'APROVOU':
        classe = 'A) aprovou com folga' if idx_aprovou is not None and idx_aprovou <= 20 else 'B) aprovou no limite'
    elif frac_meta >= 0.7:
        classe = 'C) chegou perto mas nao aprovou'
    else:
        classe = 'D) terminou muito abaixo da meta'

    janelas.append({
        'inicio': datas_ord[i], 'resultado': resultado, 'classe': classe,
        'pnl_final': acumulado, 'dd_max': dd_max, 'n_trades': n_trades_janela,
        'teve_cauda': teve_cauda, 'max_seq_perdas': max_seq_janela,
        'dias_op': dias_op, 'dias_sem_progresso': dias_sem_progresso,
        'max_dist_meta': max_dist_meta, 'tempo_ate_meta': idx_aprovou,
        'trades_janela': trades_janela,
    })

print("=" * 100)
print("FASE 2 — CLASSIFICACAO DAS JANELAS (A-E)")
print("=" * 100)
from collections import Counter
c = Counter(j['classe'] for j in janelas)
print(f"Total de janelas: {len(janelas)}\n")
for classe in ['A) aprovou com folga', 'B) aprovou no limite', 'C) chegou perto mas nao aprovou',
                'D) terminou muito abaixo da meta', 'E) falhou por DD']:
    grupo = [j for j in janelas if j['classe'] == classe]
    if not grupo:
        print(f"{classe}: 0 janelas"); continue
    pnl_med = sum(j['pnl_final'] for j in grupo)/len(grupo)
    dd_med = sum(j['dd_max'] for j in grupo)/len(grupo)
    trades_med = sum(j['n_trades'] for j in grupo)/len(grupo)
    seq_med = sum(j['max_seq_perdas'] for j in grupo)/len(grupo)
    cauda_pct = sum(1 for j in grupo if j['teve_cauda'])/len(grupo)*100
    print(f"{classe}: N={len(grupo)} ({len(grupo)/len(janelas)*100:.1f}%)")
    print(f"   PnL medio=${pnl_med:.1f} | DD medio=${dd_med:.1f} | Trades medio={trades_med:.1f} | "
          f"MaxSeqPerdas medio={seq_med:.1f}")
    print(f"   % de janelas que TIVERAM um trade de cauda (top 10%): {cauda_pct:.1f}%")

print("\n" + "=" * 100)
print("TESTE DIRETO DA HIPOTESE DA FASE 1: aprovacao depende de pegar 1 trade de cauda?")
print("=" * 100)
aprovou_com_cauda = sum(1 for j in janelas if j['resultado']=='APROVOU' and j['teve_cauda'])
aprovou_sem_cauda = sum(1 for j in janelas if j['resultado']=='APROVOU' and not j['teve_cauda'])
nao_aprovou_com_cauda = sum(1 for j in janelas if j['resultado']!='APROVOU' and j['teve_cauda'])
nao_aprovou_sem_cauda = sum(1 for j in janelas if j['resultado']!='APROVOU' and not j['teve_cauda'])
total_com_cauda = aprovou_com_cauda + nao_aprovou_com_cauda
total_sem_cauda = aprovou_sem_cauda + nao_aprovou_sem_cauda
print(f"Janelas COM pelo menos 1 trade de cauda (top 10%): {total_com_cauda}")
print(f"  -> Aprovaram: {aprovou_com_cauda} ({aprovou_com_cauda/total_com_cauda*100:.1f}%)")
print(f"Janelas SEM nenhum trade de cauda: {total_sem_cauda}")
print(f"  -> Aprovaram: {aprovou_sem_cauda} ({aprovou_sem_cauda/total_sem_cauda*100:.1f}%)" if total_sem_cauda else "  -> Aprovaram: 0 (N=0)")

print("\n" + "=" * 100)
print("FASE 3 — MECANISMO: por que janelas com expectancy positiva nao atingem a meta?")
print("=" * 100)
d_incompletas = [j for j in janelas if j['classe'] in ('C) chegou perto mas nao aprovou', 'D) terminou muito abaixo da meta')]
print(f"Janelas que NAO aprovaram nem estouraram: {len(d_incompletas)} ({len(d_incompletas)/len(janelas)*100:.1f}%)")
print(f"  PnL medio nessas: ${sum(j['pnl_final'] for j in d_incompletas)/len(d_incompletas):.1f} "
      f"({sum(j['pnl_final'] for j in d_incompletas)/len(d_incompletas)/META*100:.1f}% da meta)")
print(f"  % que tiveram trade de cauda: {sum(1 for j in d_incompletas if j['teve_cauda'])/len(d_incompletas)*100:.1f}%")
print(f"  Dias sem progresso (medio): {sum(j['dias_sem_progresso'] for j in d_incompletas)/len(d_incompletas):.1f} de ~21 dias uteis")

# janelas aprovadas: tempo ate meta
aprovadas = [j for j in janelas if j['resultado']=='APROVOU']
tempos = sorted(j['tempo_ate_meta'] for j in aprovadas)
print(f"\nJanelas aprovadas: tempo ate a meta (dias corridos desde inicio da janela)")
print(f"  mediana={tempos[len(tempos)//2]} | min={tempos[0]} | max={tempos[-1]}")
