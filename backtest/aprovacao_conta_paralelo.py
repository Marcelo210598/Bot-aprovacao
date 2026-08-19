#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
25K vs 50K vs CONTAS EM PARALELO (18/08/2026)

Usa os trades reais do baseline ja validado (1min, slippage 2 ticks, config
producao) pra simular janelas de 30 dias corridos, rolando por todo o ano
disponivel, e medir taxa de aprovacao real -- nao estimativa solta.

$50K com MESMOS 5 contratos (so DD/meta dobram, ritmo de operacao igual) e
$50K com 10 contratos (escala tudo 2x, ritmo dobra junto) -- as duas variantes,
porque tem efeito bem diferente.
"""
import sys, os
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp
import grid_trailing_alvo as gta

bars1m = dp.carregar_1min(dp.PASTA_DADOS)
print(f"{len(bars1m):,} candles 1min carregados\n")

trades = gta.simula(bars1m, 1.75, 60.0)   # config producao, ja validada
print(f"{len(trades)} trades no ano (baseline 1min c/ slippage)\n")

# PnL diario (data -> soma do dia)
pnl_dia = {}
for t in trades:
    pnl_dia[t['data']] = pnl_dia.get(t['data'], 0.0) + t['pnl_usd']

datas_ord = sorted(pnl_dia)
dt_datas = [datetime.strptime(d, '%Y-%m-%d') for d in datas_ord]


def simula_janelas(escala, meta, dd, min_dias=7):
    """Rola uma janela de 30 dias CORRIDOS a partir de cada dia de dado
    disponivel. 'escala' multiplica o PnL de cada trade (2x = dobrar contratos,
    exato pois RT e PV escalam linear com contratos)."""
    aprovadas = estouradas = incompletas = 0
    for i, d0 in enumerate(dt_datas):
        fim = d0 + timedelta(days=29)
        acumulado = 0.0; pico = 0.0; dias_op = 0
        resultado = None
        for j in range(i, len(dt_datas)):
            dj = dt_datas[j]
            if dj > fim:
                break
            pnl = pnl_dia[datas_ord[j]] * escala
            acumulado += pnl
            dias_op += 1
            pico = max(pico, acumulado)
            if pico - acumulado > dd:
                resultado = 'BUST'; break
            if acumulado >= meta and dias_op >= min_dias:
                resultado = 'APROVADA'; break
        if resultado == 'APROVADA': aprovadas += 1
        elif resultado == 'BUST': estouradas += 1
        else: incompletas += 1
    total = aprovadas + estouradas + incompletas
    return aprovadas, estouradas, incompletas, total


print("=" * 90)
print("TAXA DE APROVACAO REAL POR JANELA DE 30 DIAS CORRIDOS (rolando o ano todo)")
print("=" * 90)
configs = [
    ('25K atual (5 MNQ, meta $1.500, DD $1.000)', 1.0, 1500.0, 1000.0),
    ('50K MESMOS 5 MNQ (meta $3.000, DD $2.000)', 1.0, 3000.0, 2000.0),
    ('50K com 10 MNQ (meta $3.000, DD $2.000, escala 2x)', 2.0, 3000.0, 2000.0),
]
resultados = {}
for nome, escala, meta, dd in configs:
    ap, bu, inc, tot = simula_janelas(escala, meta, dd)
    resultados[nome] = ap / tot
    print(f"\n{nome}")
    print(f"  Janelas testadas: {tot}")
    print(f"  Aprovadas: {ap} ({ap/tot*100:.1f}%)")
    print(f"  Estouradas: {bu} ({bu/tot*100:.1f}%)")
    print(f"  Incompletas (nem aprovou nem estourou): {inc} ({inc/tot*100:.1f}%)")

print("\n" + "=" * 90)
print("EFEITO DE RODAR CONTAS $25K EM PARALELO (mesma janela de 30 dias, N contas independentes)")
print("=" * 90)
p25 = resultados['25K atual (5 MNQ, meta $1.500, DD $1.000)']
print(f"Taxa de aprovacao de 1 conta $25K sozinha: {p25*100:.1f}%\n")
print(f"{'N contas paralelas':<22}{'P(pelo menos 1 aprova)':<26}{'Custo eval (aprox $50/conta)'}")
for n in [1, 2, 3, 4, 5, 6, 8, 10]:
    p_pelo_menos_1 = 1 - (1 - p25) ** n
    print(f"{n:<22}{p_pelo_menos_1*100:<26.1f}${n*50}")
