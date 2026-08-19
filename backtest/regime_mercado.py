#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
INVESTIGACAO DE REGIME DE MERCADO (18/08/2026)

NAO otimiza nada. Caracteriza o mercado (volatilidade, estrutura do dia,
comportamento dos niveis, sinais) nos 5 blocos cronologicos JA definidos na
auditoria anterior (sem reotimizar cortes), pra ver o que mudou entre o
periodo ruim (bloco 2, 9,1% aprov) e o bom (bloco 5, 70,6% aprov).
"""
import sys, os, csv
from datetime import timedelta
sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp
import filtro_adx as fa

BLOCOS = [
    ('B1', '2025-06-13', '2025-08-12', 51.5),
    ('B2', '2025-08-13', '2025-11-05', 9.1),
    ('B3', '2025-11-06', '2026-01-27', 54.5),
    ('B4', '2026-01-28', '2026-04-10', 48.5),
    ('B5', '2026-04-13', '2026-06-11', 70.6),
]

bars = dp.carregar_1min(dp.PASTA_DADOS)
print(f"{len(bars):,} candles carregados\n")


def media(xs): return sum(xs)/len(xs) if xs else 0
def mediana(xs):
    xs = sorted(xs); m = len(xs)
    return xs[m//2] if m % 2 else (xs[m//2-1]+xs[m//2])/2
def pctl(xs, p):
    xs = sorted(xs); return xs[int(len(xs)*p)] if xs else 0


# ===================== FEATURES DIARIAS (volatilidade + estrutura) =====================
dbars = fa.bars_diarios_rth(bars)  # 1 OHLC por dia, RTH
tr_diario = {}
for i in range(1, len(dbars)):
    h, l, cp = dbars[i]['h'], dbars[i]['l'], dbars[i-1]['c']
    tr_diario[dbars[i]['data']] = max(h-l, abs(h-cp), abs(l-cp))

atr14_diario = {}
datas_dbars = [d['data'] for d in dbars]
for i, d in enumerate(datas_dbars):
    if i < 14: continue
    trs = [tr_diario.get(datas_dbars[k], 0) for k in range(i-13, i+1)]
    atr14_diario[d] = media(trs)

# range primeiros 30/60/120min + toques totais/falso rompimento/OPEROU por dia
idxs_por_dia = {}
for i, b in enumerate(bars):
    idxs_por_dia.setdefault(b['dt'].strftime('%Y-%m-%d'), []).append(i)

range_dia = {}; range30 = {}; range60 = {}; range120 = {}
open_dia = {}; close_dia = {}
tol_pts = 20 * dp.TICK; MAX_DIST = 15.0
cur_hi = cur_lo = None; pd_hi = pd_lo = None; dia_ant = None
on_key = None; on_hi = on_lo = None
toques_por_dia = {}; p2_por_dia = {}; p3_por_dia = {}; operou_por_dia = {}

for idx, b in enumerate(bars):
    dt = b['dt']; d = dt.strftime('%Y-%m-%d'); m = dp.mins(dt); dow = dt.weekday()
    em_sessao = dp.SESSAO_INICIO <= m < dp.ENTRADA_FIM
    if d != dia_ant:
        if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
        dia_ant = d; cur_hi = b['h'] if em_sessao else None; cur_lo = b['l'] if em_sessao else None
        toques_por_dia[d] = 0; p2_por_dia[d] = 0; p3_por_dia[d] = 0; operou_por_dia[d] = 0
    elif em_sessao:
        cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
        cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
    chave_seg = None
    if dow == 6 and m >= dp.DOM_NOITE_INICIO: chave_seg = (dt+timedelta(days=1)).strftime('%Y-%m-%d')
    elif dow == 0 and m < dp.SESSAO_INICIO: chave_seg = d
    if chave_seg is not None:
        if chave_seg != on_key: on_key, on_hi, on_lo = chave_seg, b['h'], b['l']
        else: on_hi = max(on_hi, b['h']); on_lo = min(on_lo, b['l'])

    if em_sessao:
        range_dia[d] = (cur_hi, cur_lo)
        if m == dp.SESSAO_INICIO: open_dia[d] = b['o']
        close_dia[d] = b['c']
        if m < dp.SESSAO_INICIO + 30: range30.setdefault(d, [b['h'], b['l']]); range30[d] = [max(range30[d][0], b['h']), min(range30[d][1], b['l'])]
        if m < dp.SESSAO_INICIO + 60: range60.setdefault(d, [b['h'], b['l']]); range60[d] = [max(range60[d][0], b['h']), min(range60[d][1], b['l'])]
        if m < dp.SESSAO_INICIO + 120: range120.setdefault(d, [b['h'], b['l']]); range120[d] = [max(range120[d][0], b['h']), min(range120[d][1], b['l'])]

        if pd_hi is not None:
            if dow == 0 and on_key == d and on_hi: n_hi, n_lo = on_hi, on_lo
            else: n_hi, n_lo = pd_hi, pd_lo
            ev = dp.avalia_bar(b, n_hi, n_lo, tol_pts, MAX_DIST)
            if ev is not None:
                toques_por_dia[d] += 1
                if ev['cat'] == 'P2_ROMPEU': p2_por_dia[d] += 1
                elif ev['cat'] == 'P3_CHASE': p3_por_dia[d] += 1
                elif ev['cat'] == 'OPEROU': operou_por_dia[d] += 1

# ===================== CARREGA SINAIS (ja calculados, 2466, ano inteiro) =====================
sinais = []
with open('backtest/qualidade_entrada_ano.csv') as f:
    for r in csv.DictReader(f):
        for k in ['dist_nivel','range_5c','range_15c','atr14','excesso_sobre_nivel','hora_min_et','mfe60','mae60']:
            r[k] = float(r[k])
        sinais.append(r)
print(f"{len(sinais)} sinais carregados de qualidade_entrada_ano.csv\n")


def dias_do_bloco(ini, fim):
    return [d for d in range_dia if ini <= d <= fim]

def sinais_do_bloco(ini, fim):
    return [s for s in sinais if ini <= s['data'] <= fim]

# ===================== TABELA 1: VOLATILIDADE E ESTRUTURA POR BLOCO =====================
print("=" * 130)
print("TABELA 1 — VOLATILIDADE E ESTRUTURA DO DIA POR BLOCO")
print("=" * 130)
print(f"{'Bloco':<6}{'Aprov%(ref)':<12}{'ATR14d_med':<12}{'RangeDia_med':<13}{'Range30m_med':<13}"
      f"{'Range60m_med':<13}{'Range120m_med':<14}{'%Tendencial':<12}{'RangeDia/ATR'}")
dados_bloco = {}
for nome, ini, fim, aprov_ref in BLOCOS:
    dias = dias_do_bloco(ini, fim)
    atrs = [atr14_diario[d] for d in dias if d in atr14_diario]
    ranges = [range_dia[d][0]-range_dia[d][1] for d in dias]
    r30 = [range30[d][0]-range30[d][1] for d in dias if d in range30]
    r60 = [range60[d][0]-range60[d][1] for d in dias if d in range60]
    r120 = [range120[d][0]-range120[d][1] for d in dias if d in range120]
    tendencial = [d for d in dias if d in open_dia and d in close_dia and (range_dia[d][0]-range_dia[d][1])>0
                  and abs(close_dia[d]-open_dia[d])/(range_dia[d][0]-range_dia[d][1]) > 0.5]
    pct_tend = len(tendencial)/len(dias)*100 if dias else 0
    ratio_range_atr = media(ranges)/media(atrs) if atrs and media(atrs) else 0
    print(f"{nome:<6}{aprov_ref:<12.1f}{media(atrs):<12.2f}{media(ranges):<13.2f}{media(r30):<13.2f}"
          f"{media(r60):<13.2f}{media(r120):<14.2f}{pct_tend:<12.1f}{ratio_range_atr:.2f}")
    dados_bloco[nome] = {'dias': dias, 'atrs': atrs, 'ranges': ranges, 'r30': r30, 'r60': r60,
                          'r120': r120, 'pct_tend': pct_tend, 'aprov_ref': aprov_ref}

print("\n(mediana / P25 / P75 do ATR14 diario e Range do dia, pra ver se e' outlier ou estrutural)")
for nome, ini, fim, aprov_ref in BLOCOS:
    atrs = dados_bloco[nome]['atrs']; ranges = dados_bloco[nome]['ranges']
    print(f"  {nome}: ATR mediana={mediana(atrs):.2f} P25={pctl(atrs,.25):.2f} P75={pctl(atrs,.75):.2f} | "
          f"RangeDia mediana={mediana(ranges):.2f} P25={pctl(ranges,.25):.2f} P75={pctl(ranges,.75):.2f}")

# ===================== TABELA 2: COMPORTAMENTO DOS NIVEIS =====================
print("\n" + "=" * 130)
print("TABELA 2 — COMPORTAMENTO DOS NIVEIS (toque, falso rompimento, MFE/MAE apos toque)")
print("=" * 130)
print(f"{'Bloco':<6}{'ToquesMed/dia':<15}{'%FalsoRomp(P2)':<16}{'%Chase(P3)':<12}{'%Operou':<10}"
      f"{'MFEmed':<9}{'MFEmediana':<12}{'MAEmed':<9}{'MAEmediana':<12}{'MFE/MAE'}")
for nome, ini, fim, aprov_ref in BLOCOS:
    dias = dados_bloco[nome]['dias']
    toques = [toques_por_dia[d] for d in dias]
    p2 = sum(p2_por_dia[d] for d in dias); p3 = sum(p3_por_dia[d] for d in dias)
    op = sum(operou_por_dia[d] for d in dias); tot = sum(toques_por_dia[d] for d in dias)
    sb = sinais_do_bloco(ini, fim)
    mfes = [s['mfe60'] for s in sb]; maes = [s['mae60'] for s in sb]
    print(f"{nome:<6}{media(toques):<15.2f}{p2/tot*100 if tot else 0:<16.1f}{p3/tot*100 if tot else 0:<12.1f}"
          f"{op/tot*100 if tot else 0:<10.1f}{media(mfes):<9.2f}{mediana(mfes):<12.2f}"
          f"{media(maes):<9.2f}{mediana(maes):<12.2f}{media(mfes)/media(maes) if media(maes) else 0:.2f}")
    dados_bloco[nome]['mfes'] = mfes; dados_bloco[nome]['maes'] = maes
    dados_bloco[nome]['excessos'] = [s['excesso_sobre_nivel'] for s in sb]

# ===================== TABELA 3: SINAIS (freq, LONG/SHORT) =====================
print("\n" + "=" * 130)
print("TABELA 3 — SINAIS POR BLOCO")
print("=" * 130)
print(f"{'Bloco':<6}{'SinaisTotal':<13}{'Sinais/dia':<12}{'%LONG':<8}{'%SHORT':<9}"
      f"{'MFE_LONG':<10}{'MFE_SHORT':<10}{'WR aprox LONG':<14}{'WR aprox SHORT'}")
for nome, ini, fim, aprov_ref in BLOCOS:
    sb = sinais_do_bloco(ini, fim)
    dias = dados_bloco[nome]['dias']
    longs = [s for s in sb if s['lado'] == 'LONG']; shorts = [s for s in sb if s['lado'] == 'SHORT']
    pct_l = len(longs)/len(sb)*100 if sb else 0; pct_s = len(shorts)/len(sb)*100 if sb else 0
    mfe_l = media([s['mfe60'] for s in longs]); mfe_s = media([s['mfe60'] for s in shorts])
    wr_l = sum(1 for s in longs if s['mfe60']>=3.75)/len(longs)*100 if longs else 0
    wr_s = sum(1 for s in shorts if s['mfe60']>=3.75)/len(shorts)*100 if shorts else 0
    print(f"{nome:<6}{len(sb):<13}{len(sb)/len(dias) if dias else 0:<12.2f}{pct_l:<8.1f}{pct_s:<9.1f}"
          f"{mfe_l:<10.2f}{mfe_s:<10.2f}{wr_l:<14.1f}{wr_s:.1f}")

# ===================== TABELA 4: DISTRIBUICAO HORARIA =====================
print("\n" + "=" * 130)
print("TABELA 4 — DISTRIBUICAO HORARIA DOS SINAIS (% por bloco)")
print("=" * 130)
horas = list(range(9, 16))
print(f"{'Bloco':<6}" + "".join(f"{h:02d}h{'':<5}" for h in horas))
for nome, ini, fim, aprov_ref in BLOCOS:
    sb = sinais_do_bloco(ini, fim)
    total = len(sb)
    linha = f"{nome:<6}"
    for h in horas:
        n_h = sum(1 for s in sb if int(s['hora_min_et'])//60 == h)
        pct = n_h/total*100 if total else 0
        linha += f"{pct:<9.1f}"
    print(linha)

# ===================== TABELA 5: RANKING DAS DIFERENCAS (RUIM=B2 vs BOM=B5) =====================
print("\n" + "=" * 130)
print("TABELA 5 — RANKING: PERIODO RUIM (B2, 9,1%) vs PERIODO BOM (B5, 70,6%)")
print("=" * 130)
b2 = dados_bloco['B2']; b5 = dados_bloco['B5']
feats = [
    ('ATR14 diario', media(b2['atrs']), media(b5['atrs']), 'A-antes'),
    ('Range do dia', media(b2['ranges']), media(b5['ranges']), 'A-antes'),
    ('Range primeiros 30min', media(b2['r30']), media(b5['r30']), 'A-antes'),
    ('% dias tendenciais', b2['pct_tend'], b5['pct_tend'], 'A-antes'),
    ('MFE (60min pos-toque)', media(b2['mfes']), media(b5['mfes']), 'C-so depois'),
    ('MAE (60min pos-toque)', media(b2['maes']), media(b5['maes']), 'C-so depois'),
    ('MFE/MAE', media(b2['mfes'])/media(b2['maes']), media(b5['mfes'])/media(b5['maes']), 'C-so depois'),
    ('Excesso sobre nivel', media(b2['excessos']), media(b5['excessos']), 'B-durante(no toque)'),
]
ranking = []
for nome, v1, v2, tipo in feats:
    diff_pct = (v2-v1)/abs(v1)*100 if v1 else 0
    ranking.append((nome, v1, v2, diff_pct, tipo))
ranking.sort(key=lambda x: -abs(x[3]))
print(f"{'Feature':<25}{'Ruim(B2)':<12}{'Bom(B5)':<12}{'Diff%':<10}{'Tipo (quando e conhecida)'}")
for nome, v1, v2, diff_pct, tipo in ranking:
    print(f"{nome:<25}{v1:<12.2f}{v2:<12.2f}{diff_pct:<+10.1f}{tipo}")

# ===================== ITEM 5: CORRELACAO POR JANELA DE 30 DIAS =====================
print("\n" + "=" * 130)
print("ITEM 5 — CORRELACAO ENTRE FEATURES DE MERCADO E PERFORMANCE, POR JANELA DE 30 DIAS")
print("=" * 130)

import gargalo_fase1_3 as g1
trades = g1.simula_com_duracao_hora(bars)
pnl_dia = {}
for t in trades: pnl_dia[t['data']] = pnl_dia.get(t['data'], 0.0) + t['pnl_usd']
datas_ord = sorted(pnl_dia)
from datetime import datetime
dts = [datetime.strptime(d, '%Y-%m-%d') for d in datas_ord]
META = 1500.0; DD_LIM = 1000.0; MIN_DIAS = 7

sinais_por_dia = {}
for s in sinais: sinais_por_dia.setdefault(s['data'], []).append(s)

janelas5 = []
for i, d0 in enumerate(dts):
    fim = d0 + timedelta(days=29)
    acumulado = 0.0; pico = 0.0; dd_max = 0.0; dias_op = 0
    n_trades = 0; wins = 0; ganho_soma = 0.0; perda_soma = 0.0; resultado = None
    dias_janela = []
    for j in range(i, len(dts)):
        dj = dts[j]
        if dj > fim: break
        d = datas_ord[j]; dias_janela.append(d)
        acumulado += pnl_dia[d]; dias_op += 1
        pico = max(pico, acumulado); dd_max = max(dd_max, pico - acumulado)
        if dd_max > DD_LIM: resultado = 'BUST'; break
        if acumulado >= META and dias_op >= MIN_DIAS: resultado = 'APROVOU'; break
    if resultado is None: resultado = 'INCOMPLETA'

    atrs_j = [atr14_diario[d] for d in dias_janela if d in atr14_diario]
    sinais_j = [s for d in dias_janela for s in sinais_por_dia.get(d, [])]
    mfes_j = [s['mfe60'] for s in sinais_j]
    maes_j = [s['mae60'] for s in sinais_j]
    toques_j = [toques_por_dia.get(d, 0) for d in dias_janela]

    janelas5.append({
        'aprovou': 1 if resultado == 'APROVOU' else 0,
        'pnl': acumulado,
        'atr_med': media(atrs_j) if atrs_j else 0,
        'mfe_med': media(mfes_j) if mfes_j else 0,
        'mae_med': media(maes_j) if maes_j else 0,
        'mfe_mae_ratio': media(mfes_j)/media(maes_j) if maes_j and media(maes_j) else 0,
        'sinais_dia': len(sinais_j)/len(dias_janela) if dias_janela else 0,
        'toques_dia': media(toques_j),
    })

def pearson(xs, ys):
    n = len(xs); mx = sum(xs)/n; my = sum(ys)/n
    cov = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
    vx = sum((x-mx)**2 for x in xs); vy = sum((y-my)**2 for y in ys)
    return cov/((vx*vy)**0.5) if vx > 0 and vy > 0 else 0

ap = [j['aprovou'] for j in janelas5]
pnl = [j['pnl'] for j in janelas5]
print(f"{'Feature':<20}{'corr x aprovou(0/1)':<22}{'corr x PnL da janela'}")
for feat in ['atr_med', 'mfe_med', 'mae_med', 'mfe_mae_ratio', 'sinais_dia', 'toques_dia']:
    xs = [j[feat] for j in janelas5]
    print(f"{feat:<20}{pearson(xs, ap):<+22.3f}{pearson(xs, pnl):+.3f}")
