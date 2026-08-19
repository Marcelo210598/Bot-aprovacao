#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Triagem rapida de 3 conceitos de entrada NOVOS (nao reversao em nivel unico),
usando o mesmo teste barato ja validado em edge_estrutural.py: corrida simetrica
ate 12,5pt + MFE/MAE vs. aleatorio. Objetivo: ver qual conceito tem edge real
ANTES de investir em motor de saida completo pra cada um."""
import sys, os, csv
sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp
import edge_estrutural as ee

ANO_INICIO, ANO_FIM = ee.ANO_INICIO, ee.ANO_FIM


def coleta_gap_fill(bars5m, limiar_pts=15.0):
    """CONCEITO A: no 1o candle RTH do dia (nao o 1o candle do dia calendario --
    esse pode ser barra de overnight), se abriu > limiar_pts do close RTH de
    ontem, aposta no fechamento parcial do gap (fade).
    BUG CORRIGIDO 18/08: usava 'd != dia' (1a barra do dia calendario, quase
    sempre overnight) em vez de rastrear a 1a barra DENTRO da sessao RTH -- por
    isso so achava 10 sinais no ano inteiro em vez de ~235."""
    sinais = []
    dia = None; ultimo_close_dia = None; pd_close = None; sessao_iniciada = False
    for idx, b in enumerate(bars5m):
        dt = b['dt']; d = dt.strftime('%Y-%m-%d'); m = dp.mins(dt)
        em_sessao = dp.SESSAO_INICIO <= m < dp.ENTRADA_FIM
        if d != dia:
            if ultimo_close_dia is not None:
                pd_close = ultimo_close_dia
            dia = d; sessao_iniciada = False
        if em_sessao:
            primeira_rth = not sessao_iniciada
            sessao_iniciada = True
            if primeira_rth and pd_close is not None and ANO_INICIO <= d <= ANO_FIM:
                gap = b['o'] - pd_close
                if abs(gap) >= limiar_pts:
                    lado = 'SHORT' if gap > 0 else 'LONG'
                    sinais.append({'idx': idx, 'lado': lado, 'entry': b['o'], 'data': d})
            ultimo_close_dia = b['c']
    return sinais


def coleta_momentum(bars5m, janela_bars=6, min_move_pts=15.0, min_bars_direcao=4):
    """CONCEITO B: primeiros `janela_bars` candles RTH do dia -- se moveu forte
    e consistente numa direcao, entra na continuacao ao fim dessa janela."""
    sinais = []
    dia = None; bars_do_dia = []
    for idx, b in enumerate(bars5m):
        dt = b['dt']; d = dt.strftime('%Y-%m-%d'); m = dp.mins(dt)
        em_sessao = dp.SESSAO_INICIO <= m < dp.ENTRADA_FIM
        if d != dia:
            dia = d; bars_do_dia = []
        if not em_sessao or not (ANO_INICIO <= d <= ANO_FIM):
            continue
        bars_do_dia.append(b)
        if len(bars_do_dia) == janela_bars:
            primeiro = bars_do_dia[0]; ultimo = bars_do_dia[-1]
            move = ultimo['c'] - primeiro['o']
            pos = sum(1 for bb in bars_do_dia if bb['c'] >= bb['o'])
            consistente = pos >= min_bars_direcao or (janela_bars - pos) >= min_bars_direcao
            if abs(move) >= min_move_pts and consistente:
                lado = 'LONG' if move > 0 else 'SHORT'
                sinais.append({'idx': idx, 'lado': lado, 'entry': ultimo['c'], 'data': d})
    return sinais


def coleta_squeeze(bars5m, janela_canal=12, limiar_range_pts=20.0):
    """CONCEITO C: canal das ultimas `janela_canal` barras RTH -- se range < limiar
    (compressao), entra na direcao do rompimento quando sair do canal."""
    sinais = []
    dia = None; bars_do_dia = []
    for idx, b in enumerate(bars5m):
        dt = b['dt']; d = dt.strftime('%Y-%m-%d'); m = dp.mins(dt)
        em_sessao = dp.SESSAO_INICIO <= m < dp.ENTRADA_FIM
        if d != dia:
            dia = d; bars_do_dia = []
        if not em_sessao or not (ANO_INICIO <= d <= ANO_FIM):
            continue
        bars_do_dia.append(b)
        if len(bars_do_dia) > janela_canal:
            canal = bars_do_dia[-(janela_canal + 1):-1]
            c_hi = max(x['h'] for x in canal); c_lo = min(x['l'] for x in canal)
            if (c_hi - c_lo) <= limiar_range_pts:
                if b['h'] > c_hi:
                    sinais.append({'idx': idx, 'lado': 'LONG', 'entry': b['c'], 'data': d})
                elif b['l'] < c_lo:
                    sinais.append({'idx': idx, 'lado': 'SHORT', 'entry': b['c'], 'data': d})
    return sinais


def main():
    print("Carregando dados ...")
    bars1m = dp.carregar_1min(dp.PASTA_DADOS)
    bars5m = dp.resample_5min(bars1m)
    print(f"  {len(bars5m):,} candles de 5min\n")

    # limiares recalibrados 18/08 pela distribuicao REAL desse dataset (gaps aqui
    # rodam bem maiores que NQ real -- mediana de gap ~85pt, nao ~15pt)
    conceitos = {
        'A) Gap Fill (fade > 85pt, mediana)': coleta_gap_fill(bars5m, limiar_pts=85.0),
        'B) Momentum 30min (>15pt, 4/6 barras)': coleta_momentum(bars5m),
        'C) Squeeze 1h (range<40pt) breakout': coleta_squeeze(bars5m, limiar_range_pts=40.0),
    }

    print(f"{'Conceito':<42}{'N sinais':<10}{'Corrida R':<11}{'Corrida Rnd':<12}"
          f"{'Diff pp':<9}{'MFE med':<9}{'MAE med':<9}{'Razao'}")
    linhas = []
    for nome, sinais in conceitos.items():
        n = len(sinais)
        if n < 20:
            print(f"{nome:<42}{n:<10}(poucos sinais, nao da p/ testar com confianca)")
            continue
        rand = ee.coleta_sinais_aleatorios(bars5m, n, seed=42)
        r_real = ee.corrida_simetrica(bars5m, sinais)
        r_rand = ee.corrida_simetrica(bars5m, rand)
        m_real = ee.mfe_mae(bars5m, sinais)
        diff = r_real['taxa_ganho'] - r_rand['taxa_ganho']
        print(f"{nome:<42}{n:<10}{r_real['taxa_ganho']:<11.1f}{r_rand['taxa_ganho']:<12.1f}"
              f"{diff:<+9.1f}{m_real['mfe_medio']:<9.1f}{m_real['mae_medio']:<9.1f}"
              f"{m_real['razao_mfe_mae']:.2f}")
        linhas.append({'conceito': nome, 'n': n, 'corrida_real': r_real['taxa_ganho'],
                        'corrida_random': r_rand['taxa_ganho'], 'diff_pp': diff,
                        'mfe_medio': m_real['mfe_medio'], 'mae_medio': m_real['mae_medio'],
                        'razao_mfe_mae': m_real['razao_mfe_mae']})

    # referencia: a estrategia atual, mesmo teste
    sinais_atual = ee.coleta_sinais_reais(bars5m)
    r_atual = ee.corrida_simetrica(bars5m, sinais_atual)
    rand_atual = ee.coleta_sinais_aleatorios(bars5m, len(sinais_atual), seed=42)
    r_rand_atual = ee.corrida_simetrica(bars5m, rand_atual)
    print(f"\n{'(referencia) Estrategia atual':<42}{len(sinais_atual):<10}"
          f"{r_atual['taxa_ganho']:<11.1f}{r_rand_atual['taxa_ganho']:<12.1f}"
          f"{r_atual['taxa_ganho']-r_rand_atual['taxa_ganho']:+.1f}")

    csv_path = os.path.join(os.path.dirname(__file__), 'screening_novas_entradas.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        if linhas:
            w = csv.DictWriter(f, fieldnames=list(linhas[0].keys())); w.writeheader(); w.writerows(linhas)
    print(f"\nCSV: {csv_path}")

if __name__ == '__main__':
    main()
