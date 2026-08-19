#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUDITORIA ESTATISTICA FINAL (18/08/2026)

Nao otimiza nada. So observa: os 47% de aprovacao sao estaveis no tempo ou e'
media de algo que varia muito? Unidade estatistica = JANELA de 30 dias
(nao trade), conforme pedido -- bootstrap e blocos rodam sobre as 166 janelas.
"""
import sys, os, random
from datetime import timedelta, datetime
sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp
import gargalo_fase1_3 as g1

random.seed(42)

bars = dp.carregar_1min(dp.PASTA_DADOS)
trades = g1.simula_com_duracao_hora(bars)
n_total = len(trades)
print(f"{n_total} trades no ano\n")

META = 1500.0; DD_LIM = 1000.0; MIN_DIAS = 7

trades_ord = sorted(trades, key=lambda t: -t['pnl_usd'])
limiar_cauda = trades_ord[int(n_total*0.10)]['pnl_usd']

pnl_dia = {}; trades_por_dia = {}
for t in trades:
    pnl_dia[t['data']] = pnl_dia.get(t['data'], 0.0) + t['pnl_usd']
    trades_por_dia.setdefault(t['data'], []).append(t)
datas_ord = sorted(pnl_dia)
dts = [datetime.strptime(d, '%Y-%m-%d') for d in datas_ord]

# ---------- constroi as 166 janelas com todas as metricas ----------
janelas = []
for i, d0 in enumerate(dts):
    fim = d0 + timedelta(days=29)
    acumulado = 0.0; pico = 0.0; dd_max = 0.0; dias_op = 0
    n_trades = 0; wins = 0; ganho_soma = 0.0; perda_soma = 0.0
    n_cauda = 0; pnl_cauda = 0.0; pnl_resto = 0.0
    resultado = None
    for j in range(i, len(dts)):
        dj = dts[j]
        if dj > fim: break
        for t in trades_por_dia[datas_ord[j]]:
            acumulado += t['pnl_usd']; n_trades += 1
            if t['pnl_usd'] > 0: wins += 1; ganho_soma += t['pnl_usd']
            else: perda_soma += t['pnl_usd']
            if t['pnl_usd'] >= limiar_cauda: n_cauda += 1; pnl_cauda += t['pnl_usd']
            else: pnl_resto += t['pnl_usd']
        dias_op += 1
        pico = max(pico, acumulado); dd_max = max(dd_max, pico - acumulado)
        if dd_max > DD_LIM: resultado = 'BUST'; break
        if acumulado >= META and dias_op >= MIN_DIAS: resultado = 'APROVOU'; break
    if resultado is None: resultado = 'INCOMPLETA'

    wr = wins/n_trades*100 if n_trades else 0
    gm = ganho_soma/wins if wins else 0
    n_loss = n_trades - wins
    pm = perda_soma/n_loss if n_loss else 0
    ratio = gm/abs(pm) if pm else 0
    pf = ganho_soma/abs(perda_soma) if perda_soma else 0
    exp = acumulado/n_trades if n_trades else 0

    janelas.append({
        'idx': i, 'data_inicio': datas_ord[i], 'aprovou': resultado == 'APROVOU',
        'resultado': resultado, 'pnl': acumulado, 'dd': dd_max, 'n_trades': n_trades,
        'wr': wr, 'ratio': ratio, 'pf': pf, 'exp': exp, 'n_cauda': n_cauda,
        'pnl_cauda': pnl_cauda, 'pnl_resto': pnl_resto,
    })

n = len(janelas)
print(f"{n} janelas de 30 dias corridos construidas\n")

def media(xs): return sum(xs)/len(xs) if xs else 0
def mediana(xs):
    xs = sorted(xs); m = len(xs)
    return xs[m//2] if m % 2 else (xs[m//2-1]+xs[m//2])/2
def pctl(xs, p):
    xs = sorted(xs); return xs[int(len(xs)*p)] if xs else 0

# ===================== 1. ESTABILIDADE TEMPORAL (5 blocos de 20%) =====================
print("=" * 130)
print("1. ESTABILIDADE TEMPORAL — 5 blocos cronologicos de 20%")
print("=" * 130)
bloco_tam = n // 5
blocos = []
for b in range(5):
    ini = b * bloco_tam
    fim_b = (b + 1) * bloco_tam if b < 4 else n
    blocos.append(janelas[ini:fim_b])

print(f"{'Bloco':<10}{'N':<6}{'Aprov%':<9}{'PnLmed':<10}{'Exp$':<8}{'WR%':<7}{'Ratio':<8}{'PF':<6}"
      f"{'DDmed':<9}{'TradesMed':<11}{'NcaudaMed':<11}{'PnLcaudaMed':<13}{'PnLresto90Med'}")
for b, bl in enumerate(blocos):
    print(f"{b+1:<10}{len(bl):<6}{media([1 if j['aprovou'] else 0 for j in bl])*100:<9.1f}"
          f"${media([j['pnl'] for j in bl]):<9.1f}${media([j['exp'] for j in bl]):<7.1f}"
          f"{media([j['wr'] for j in bl]):<7.1f}{media([j['ratio'] for j in bl]):<8.2f}"
          f"{media([j['pf'] for j in bl]):<6.2f}${media([j['dd'] for j in bl]):<8.1f}"
          f"{media([j['n_trades'] for j in bl]):<11.1f}{media([j['n_cauda'] for j in bl]):<11.2f}"
          f"${media([j['pnl_cauda'] for j in bl]):<12.1f}${media([j['pnl_resto'] for j in bl]):.1f}")
    print(f"    (periodo: {bl[0]['data_inicio']} a {bl[-1]['data_inicio']})")

# ===================== 2. ROLLING WINDOW =====================
print("\n" + "=" * 130)
print("2. TAXA DE APROVACAO EM ROLLING WINDOW (sobre a sequencia das 166 janelas)")
print("=" * 130)
outcomes = [1 if j['aprovou'] else 0 for j in janelas]
for tam in [20, 30, 40]:
    print(f"\n--- Rolling de {tam} janelas ---")
    vals = []
    for i in range(0, n - tam + 1, max(1, tam // 4)):
        sub = outcomes[i:i+tam]
        taxa = media(sub) * 100
        vals.append((janelas[i]['data_inicio'], janelas[i+tam-1]['data_inicio'], taxa))
    for d0, d1, taxa in vals:
        barra = '#' * int(taxa / 2)
        print(f"  {d0} a {d1}: {taxa:5.1f}%  {barra}")
    taxas_only = [v[2] for v in vals]
    print(f"  -> min={min(taxas_only):.1f}% max={max(taxas_only):.1f}% "
          f"amplitude={max(taxas_only)-min(taxas_only):.1f}pp")

# ===================== 3. DISTRIBUICAO DA EXPECTANCY POR JANELA =====================
print("\n" + "=" * 130)
print("3. DISTRIBUICAO DA EXPECTANCY POR JANELA (aprovadas vs nao aprovadas)")
print("=" * 130)
exp_all = [j['exp'] for j in janelas]
exp_aprov = [j['exp'] for j in janelas if j['aprovou']]
exp_nao = [j['exp'] for j in janelas if not j['aprovou']]

for nome, xs in [('TODAS', exp_all), ('APROVADAS', exp_aprov), ('NAO APROVADAS', exp_nao)]:
    print(f"{nome:<16} N={len(xs):<5} media=${media(xs):<8.2f} mediana=${mediana(xs):<8.2f} "
          f"P25=${pctl(xs,.25):<8.2f} P75=${pctl(xs,.75):<8.2f} min=${min(xs):<9.2f} max=${max(xs):.2f}")

pnl_aprov = [j['pnl'] for j in janelas if j['aprovou']]
pnl_nao = [j['pnl'] for j in janelas if not j['aprovou']]
dd_aprov = [j['dd'] for j in janelas if j['aprovou']]
dd_nao = [j['dd'] for j in janelas if not j['aprovou']]
print(f"\nPnL da janela  -> aprovadas: media=${media(pnl_aprov):.1f} dp~={((sum((x-media(pnl_aprov))**2 for x in pnl_aprov)/len(pnl_aprov))**0.5):.1f}")
print(f"               -> nao aprov: media=${media(pnl_nao):.1f} dp~={((sum((x-media(pnl_nao))**2 for x in pnl_nao)/len(pnl_nao))**0.5):.1f}")
print(f"DD da janela   -> aprovadas: media=${media(dd_aprov):.1f} | nao aprov: media=${media(dd_nao):.1f}")

# ===================== 4. BOOTSTRAP POR JANELA =====================
print("\n" + "=" * 130)
print("4. BOOTSTRAP DAS 166 JANELAS (unidade = janela, nao trade)")
print("=" * 130)
B = 5000
taxas_boot = []
for _ in range(B):
    amostra = [random.choice(outcomes) for _ in range(n)]
    taxas_boot.append(media(amostra) * 100)
taxas_boot.sort()
ic_baixo = taxas_boot[int(B*0.025)]; ic_alto = taxas_boot[int(B*0.975)]
print(f"Taxa observada: 47,0%")
print(f"IC 95% (bootstrap percentil, {B} reamostragens): [{ic_baixo:.1f}%, {ic_alto:.1f}%]")
print(f"  -> 47% +/- ~{(ic_alto-ic_baixo)/2:.1f} pontos percentuais")
print("\n⚠️ AVISO: as 166 janelas SE SOBREPOEM (janela i e i+1 compartilham 29 dos 30 dias).")
print("   Esse bootstrap trata como se fossem independentes -- SUBESTIMA a incerteza real.")
print("   Contraprova com janelas genuinamente NAO sobrepostas (a cada ~29 dias):")
nao_sobrepostas = [janelas[i] for i in range(0, n, 29)]
outc_ns = [1 if j['aprovou'] else 0 for j in nao_sobrepostas]
print(f"   N={len(nao_sobrepostas)} janelas independentes | taxa observada = {media(outc_ns)*100:.1f}%")
if len(nao_sobrepostas) > 1:
    taxas_boot_ns = []
    for _ in range(B):
        amostra = [random.choice(outc_ns) for _ in range(len(outc_ns))]
        taxas_boot_ns.append(media(amostra)*100)
    taxas_boot_ns.sort()
    print(f"   IC 95% (so com janelas independentes): [{taxas_boot_ns[int(B*0.025)]:.1f}%, {taxas_boot_ns[int(B*0.975)]:.1f}%]")
    print("   (amostra pequena, IC bem mais largo -- mas mais honesto)")

# ===================== 5. SENSIBILIDADE A AMOSTRA =====================
print("\n" + "=" * 130)
print("5. SENSIBILIDADE A AMOSTRA (mesmos parametros, so muda o recorte temporal)")
print("=" * 130)
def recorte(lo, hi):
    ini = int(n*lo); fim_r = int(n*hi)
    sub = janelas[ini:fim_r]
    return sub

cortes = [('Primeiros 50%', 0, 0.5), ('Ultimos 50%', 0.5, 1.0),
          ('Primeiros 70%', 0, 0.7), ('Ultimos 30%', 0.7, 1.0)]
for nome, lo, hi in cortes:
    sub = recorte(lo, hi)
    taxa = media([1 if j['aprovou'] else 0 for j in sub])*100
    print(f"{nome:<16} N={len(sub):<5} periodo {sub[0]['data_inicio']} a {sub[-1]['data_inicio']:<12} "
          f"Aprov={taxa:.1f}% Exp med=${media([j['exp'] for j in sub]):.1f}")

# ===================== 6. ESTACIONARIEDADE (reusa os blocos da parte 1) =====================
print("\n" + "=" * 130)
print("6. ESTACIONARIEDADE — WR/ratio/expectancy/freq de sinal ao longo dos 5 blocos")
print("=" * 130)
print(f"{'Bloco':<8}{'WR%':<8}{'Ratio':<8}{'Exp$':<8}{'TradesMed(freq)':<17}{'PnLtop10%Med':<14}{'PnLresto90Med'}")
for b, bl in enumerate(blocos):
    print(f"{b+1:<8}{media([j['wr'] for j in bl]):<8.1f}{media([j['ratio'] for j in bl]):<8.2f}"
          f"${media([j['exp'] for j in bl]):<7.1f}{media([j['n_trades'] for j in bl]):<17.1f}"
          f"${media([j['pnl_cauda'] for j in bl]):<13.1f}${media([j['pnl_resto'] for j in bl]):.1f}")
print("\nVariacao WR: min={:.1f}% max={:.1f}% (amplitude {:.1f}pp)".format(
    min(media([j['wr'] for j in bl]) for bl in blocos), max(media([j['wr'] for j in bl]) for bl in blocos),
    max(media([j['wr'] for j in bl]) for bl in blocos) - min(media([j['wr'] for j in bl]) for bl in blocos)))
print("Variacao Ratio: min={:.2f} max={:.2f}".format(
    min(media([j['ratio'] for j in bl]) for bl in blocos), max(media([j['ratio'] for j in bl]) for bl in blocos)))
print("Variacao Expectancy: min=${:.1f} max=${:.1f}".format(
    min(media([j['exp'] for j in bl]) for bl in blocos), max(media([j['exp'] for j in bl]) for bl in blocos)))
