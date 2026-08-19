#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TESTE DE EDGE ESTRUTURAL DA ENTRADA (18/08/2026)

Pergunta: o sinal "tocou a maxima/minima de ontem + rejeitou" tem edge direcional
de verdade, ou o PnL positivo do backtest vem so da engenharia de saida (BE/
trailing/TP) numa entrada que, sozinha, nao e melhor que aleatorio?

Metodologia (2 testes, sem nenhuma gestao de SL/TP/BE/trailing no meio -- olha
so pro que o PRECO faz depois do sinal, puro):

1) CORRIDA SIMETRICA ATE 12,5pt: a partir de cada sinal, anda candle a candle
   pra frente e ve quem chega primeiro: +12,5pt a favor ou -12,5pt contra (a
   MESMA distancia do SL de producao, sem TP/trailing no meio). Se o sinal
   tem edge real, deve ganhar essa corrida em MAIS de 50% das vezes.
   Compara com um benchmark de sinais ALEATORIOS (mesmo volume, direcao 50/50,
   dentro da mesma janela 9h30-16h) -- se o sinal real nao vencer o aleatorio
   por margem clara, o "edge" e' estatisticamente indistinguivel de ruido.

2) MFE/MAE medio nos primeiros 24 candles de 5min (2h) depois do sinal --
   quanto o preco anda a favor (MFE) vs contra (MAE) em media, sinal real vs
   aleatorio.

Reaproveita a mesma base de dados e motor de nivel/toque de diagnostico_portoes.py.
"""
import sys
import os
import random
import csv
from datetime import timedelta

sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp

TICK = dp.TICK
TOL_TICKS = 20
MAX_DIST = 15.0
ALVO_CORRIDA = 12.5     # mesma distancia do SL de producao
MAX_BARRAS_CORRIDA = 100   # ~8h de barras de 5min -- teto generoso
JANELA_MFE_MAE = 24        # 24 barras de 5min = 2h

ANO_INICIO, ANO_FIM = '2025-06-11', '2026-06-11'
SEED = 42


def coleta_sinais_reais(bars5m):
    """Roda a mesma maquina de estado de diagnostico_portoes.py e devolve so
    os sinais que o bot REALMENTE dispararia (categoria OPEROU)."""
    tol_pts = TOL_TICKS * TICK
    cur_hi = cur_lo = None
    pd_hi = pd_lo = None
    dia = None
    on_key = None
    on_hi = on_lo = None

    sinais = []
    for idx, b in enumerate(bars5m):
        dt = b['dt']; d = dt.strftime('%Y-%m-%d'); m = dp.mins(dt); dow = dt.weekday()
        em_sessao = dp.SESSAO_INICIO <= m < dp.ENTRADA_FIM

        if d != dia:
            if cur_hi is not None:
                pd_hi, pd_lo = cur_hi, cur_lo
            dia = d
            cur_hi = b['h'] if em_sessao else None
            cur_lo = b['l'] if em_sessao else None
        elif em_sessao:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])

        chave_seg = None
        if dow == 6 and m >= dp.DOM_NOITE_INICIO:
            chave_seg = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
        elif dow == 0 and m < dp.SESSAO_INICIO:
            chave_seg = d
        if chave_seg is not None:
            if chave_seg != on_key:
                on_key, on_hi, on_lo = chave_seg, b['h'], b['l']
            else:
                on_hi = max(on_hi, b['h']); on_lo = min(on_lo, b['l'])

        if not (ANO_INICIO <= d <= ANO_FIM):
            continue
        if not (dp.SESSAO_INICIO <= m < dp.ENTRADA_FIM):
            continue
        if pd_hi is None or pd_lo is None:
            continue

        if dow == 0 and on_key == d and on_hi is not None and on_hi > 0:
            n_hi, n_lo = on_hi, on_lo
        else:
            n_hi, n_lo = pd_hi, pd_lo

        ev = dp.avalia_bar(b, n_hi, n_lo, tol_pts, MAX_DIST)
        if ev is not None and ev['cat'] == 'OPEROU':
            sinais.append({'idx': idx, 'lado': ev['lado'], 'entry': b['c'], 'data': d})

    return sinais


def coleta_sinais_aleatorios(bars5m, n, seed=SEED):
    """Mesmo volume de 'sinais', em barras aleatorias dentro da janela 9h30-16h,
    direcao 50/50 -- benchmark de 'nao ter nenhuma logica de entrada'."""
    rnd = random.Random(seed)
    candidatos = [idx for idx, b in enumerate(bars5m)
                  if ANO_INICIO <= b['dt'].strftime('%Y-%m-%d') <= ANO_FIM
                  and dp.SESSAO_INICIO <= dp.mins(b['dt']) < dp.ENTRADA_FIM
                  and idx + JANELA_MFE_MAE < len(bars5m)]
    escolhidos = rnd.sample(candidatos, min(n, len(candidatos)))
    sinais = []
    for idx in escolhidos:
        b = bars5m[idx]
        lado = rnd.choice(['LONG', 'SHORT'])
        sinais.append({'idx': idx, 'lado': lado, 'entry': b['c'],
                        'data': b['dt'].strftime('%Y-%m-%d')})
    return sinais


def corrida_simetrica(bars5m, sinais, alvo_pts=ALVO_CORRIDA, max_barras=MAX_BARRAS_CORRIDA):
    ganhou = perdeu = timeout = 0
    for s in sinais:
        entry = s['entry']; lado = s['lado']; i0 = s['idx']
        resolvido = False
        for k in range(1, max_barras + 1):
            j = i0 + k
            if j >= len(bars5m):
                break
            b = bars5m[j]
            if lado == 'LONG':
                fav = b['h'] - entry; adv = entry - b['l']
            else:
                fav = entry - b['l']; adv = b['h'] - entry
            atingiu_fav = fav >= alvo_pts
            atingiu_adv = adv >= alvo_pts
            if atingiu_adv:      # se os dois batem na mesma barra, trata como perda
                perdeu += 1; resolvido = True; break
            if atingiu_fav:
                ganhou += 1; resolvido = True; break
        if not resolvido:
            timeout += 1
    total = len(sinais)
    return {'total': total, 'ganhou': ganhou, 'perdeu': perdeu, 'timeout': timeout,
            'taxa_ganho': ganhou / total * 100 if total else 0.0}


def mfe_mae(bars5m, sinais, janela=JANELA_MFE_MAE):
    mfes = []; maes = []
    for s in sinais:
        entry = s['entry']; lado = s['lado']; i0 = s['idx']
        mfe = 0.0; mae = 0.0
        for k in range(1, janela + 1):
            j = i0 + k
            if j >= len(bars5m):
                break
            b = bars5m[j]
            if lado == 'LONG':
                fav = b['h'] - entry; adv = entry - b['l']
            else:
                fav = entry - b['l']; adv = b['h'] - entry
            mfe = max(mfe, fav); mae = max(mae, adv)
        mfes.append(mfe); maes.append(mae)
    n = len(mfes)
    mfes_s = sorted(mfes); maes_s = sorted(maes)
    mediana = lambda xs: xs[len(xs)//2] if len(xs) % 2 else (xs[len(xs)//2-1]+xs[len(xs)//2])/2
    return {
        'mfe_medio': sum(mfes) / n if n else 0.0,
        'mae_medio': sum(maes) / n if n else 0.0,
        'mfe_mediana': mediana(mfes_s) if n else 0.0,
        'mae_mediana': mediana(maes_s) if n else 0.0,
        'razao_mfe_mae': (sum(mfes) / sum(maes)) if sum(maes) else float('inf'),
    }


def main():
    print("Carregando dados ...")
    bars1m = dp.carregar_1min(dp.PASTA_DADOS)
    bars5m = dp.resample_5min(bars1m)
    print(f"  {len(bars5m):,} candles de 5min ({ANO_INICIO} a {ANO_FIM})\n")

    print("Coletando sinais reais (toque + rejeicao + dentro do MaxDist) ...")
    sinais_reais = coleta_sinais_reais(bars5m)
    print(f"  {len(sinais_reais)} sinais reais no ano")

    print("Gerando benchmark aleatorio (mesmo volume, direcao 50/50) ...")
    sinais_rand = coleta_sinais_aleatorios(bars5m, len(sinais_reais))
    print(f"  {len(sinais_rand)} sinais aleatorios\n")

    print("=" * 90)
    print(f"TESTE 1 — CORRIDA SIMETRICA: quem chega primeiro, +{ALVO_CORRIDA}pt a favor ou "
          f"-{ALVO_CORRIDA}pt contra? (sem SL/TP/trailing, so o preco puro)")
    print("=" * 90)
    r_real = corrida_simetrica(bars5m, sinais_reais)
    r_rand = corrida_simetrica(bars5m, sinais_rand)

    print(f"\n{'':<20}{'N':<8}{'Ganhou':<10}{'Perdeu':<10}{'Timeout':<10}{'Taxa ganho'}")
    print(f"{'Sinal REAL':<20}{r_real['total']:<8}{r_real['ganhou']:<10}{r_real['perdeu']:<10}"
          f"{r_real['timeout']:<10}{r_real['taxa_ganho']:.1f}%")
    print(f"{'Aleatorio (base)':<20}{r_rand['total']:<8}{r_rand['ganhou']:<10}{r_rand['perdeu']:<10}"
          f"{r_rand['timeout']:<10}{r_rand['taxa_ganho']:.1f}%")
    print(f"\nDiferenca (real - aleatorio): {r_real['taxa_ganho'] - r_rand['taxa_ganho']:+.1f} "
          f"pontos percentuais")
    print("(50% = moeda honesta seria o esperado sem nenhum edge, ja que a corrida e' simetrica)")

    print("\n" + "=" * 90)
    print(f"TESTE 2 — MFE/MAE MEDIO nos primeiros {JANELA_MFE_MAE} candles de 5min (2h) apos o sinal")
    print("=" * 90)
    m_real = mfe_mae(bars5m, sinais_reais)
    m_rand = mfe_mae(bars5m, sinais_rand)
    print(f"\n{'':<20}{'MFE medio':<12}{'MFE mediana':<13}{'MAE medio':<12}{'MAE mediana':<13}{'Razao(medio)'}")
    print(f"{'Sinal REAL':<20}{m_real['mfe_medio']:<12.2f}{m_real['mfe_mediana']:<13.2f}"
          f"{m_real['mae_medio']:<12.2f}{m_real['mae_mediana']:<13.2f}{m_real['razao_mfe_mae']:.2f}")
    print(f"{'Aleatorio (base)':<20}{m_rand['mfe_medio']:<12.2f}{m_rand['mfe_mediana']:<13.2f}"
          f"{m_rand['mae_medio']:<12.2f}{m_rand['mae_mediana']:<13.2f}{m_rand['razao_mfe_mae']:.2f}")

    print("\n" + "=" * 90)
    print("VEREDITO")
    print("=" * 90)
    diff = r_real['taxa_ganho'] - r_rand['taxa_ganho']
    if abs(diff) < 3:
        print(f"⚠️  A entrada (toque+rejeicao) venceu a corrida simetrica em {r_real['taxa_ganho']:.1f}%")
        print(f"    das vezes, contra {r_rand['taxa_ganho']:.1f}% do aleatorio -- diferenca de só "
              f"{diff:+.1f}pp.")
        print("    Isso é ESTATISTICAMENTE INDISTINGUIVEL de moeda honesta. A entrada, pura, NAO")
        print("    tem edge direcional detectavel nesse teste. O PnL positivo do backtest vem da")
        print("    engenharia de saida (SL menor que o alvo, trailing, WR alto por corte cedo de")
        print("    perda) -- nao de um sinal que realmente preve pra onde o preco vai.")
    else:
        print(f"✅ A entrada venceu a corrida em {r_real['taxa_ganho']:.1f}% vs {r_rand['taxa_ganho']:.1f}% "
              f"do aleatorio ({diff:+.1f}pp de diferenca) -- ha sinal de edge direcional real.")

    csv_path = os.path.join(os.path.dirname(__file__), 'edge_estrutural.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['tipo', 'n', 'ganhou', 'perdeu', 'timeout', 'taxa_ganho_pct',
                    'mfe_medio', 'mae_medio', 'razao_mfe_mae'])
        w.writerow(['real', r_real['total'], r_real['ganhou'], r_real['perdeu'], r_real['timeout'],
                    round(r_real['taxa_ganho'], 2), round(m_real['mfe_medio'], 2),
                    round(m_real['mae_medio'], 2), round(m_real['razao_mfe_mae'], 3)])
        w.writerow(['aleatorio', r_rand['total'], r_rand['ganhou'], r_rand['perdeu'], r_rand['timeout'],
                    round(r_rand['taxa_ganho'], 2), round(m_rand['mfe_medio'], 2),
                    round(m_rand['mae_medio'], 2), round(m_rand['razao_mfe_mae'], 3)])
    print(f"\nCSV salvo em: {csv_path}")


if __name__ == '__main__':
    main()
