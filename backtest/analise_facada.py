#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANÁLISE "FACADA" (item #17) — 01/09/2026.

Gatilho: o forward test de julho/2026 (BETrigger25) mostrou de novo o padrão
'stop cheio com favor máximo < 1pt' — a vela de entrada já reverte, sem o
breakeven ter tempo de agir. 3 casos em 2 dias (02/07 NIV_L10, 06/07 NIV_S4/S5).

Pergunta: dá pra corrigir? Tem algum sinal ANTES de entrar que distinga esses
trades dos que funcionam?

Lê `backtest/diagnostico_mfe_mae_trades.csv` (1.091 trades do backtest de 13
meses, com MFE/MAE/dist_nivel/hora por trade).

RESULTADO: 70 facadas/13 meses (~5-6/mês, −$131/trade, −$9,2k total). NENHUM
sinal pré-entrada as distingue (dist_nivel, gap, hora, dow idênticos ao resto;
espalhadas por todas as faixas de distância; duração mediana 0 barras). Loss-cut
já rejeitado (item #16). Não tem filtro — o SL de 12,5pt existe pra capar isso.
O que impede de estourar a conta é DD estático.
"""
import csv, os, statistics as st
from collections import Counter

CSV = os.path.join(os.path.dirname(__file__), 'diagnostico_mfe_mae_trades.csv')


def main():
    rows = list(csv.DictReader(open(CSV)))
    for r in rows:
        for k in ('pts', 'usd', 'mfe', 'mae', 'dist_nivel', 'dur_bars', 'gap_entrada'):
            r[k] = float(r[k])
    n = len(rows); tot = sum(r['usd'] for r in rows)
    sl = [r for r in rows if r['motivo'] == 'SL' and r['be_ativado'] == 'False']

    print(f"{n} trades | PnL total ${tot:,.0f} | stops cheios (SL, BE=não): {len(sl)}\n")
    print("favor máx antes do stop cheio  |  n   | % total | PnL       | média")
    for lim in (0.5, 1.0, 1.5, 2.0, 3.0):
        g = [r for r in sl if r['mfe'] < lim]
        print(f"  mfe < {lim:>3}pt                     | {len(g):>3}  | {100*len(g)/n:>5.1f}%  | "
              f"${sum(r['usd'] for r in g):>8,.0f} | ${st.mean(r['usd'] for r in g):>5.0f}")

    faca = [r for r in sl if r['mfe'] < 1.0]
    resto = [r for r in rows if not (r['motivo'] == 'SL' and r['be_ativado'] == 'False' and r['mfe'] < 1.0)]
    print(f"\n>>> FACADA (SL, BE=não, favor < 1pt): {len(faca)} trades = ${sum(r['usd'] for r in faca):,.0f} "
          f"(~{len(faca)/13:.0f}/mês)")
    print(f"    se sumissem: PnL 13m ${tot:,.0f} -> ${tot - sum(r['usd'] for r in faca):,.0f}\n")

    print("--- tem sinal PRÉ-ENTRADA? facada vs resto ---")
    for lbl, g in [('facada', faca), ('resto', resto)]:
        print(f"  {lbl:8s} n={len(g):<4} dist_nivel med {st.median(r['dist_nivel'] for r in g):>5.1f}pt  "
              f"gap med {st.median(r['gap_entrada'] for r in g):>+5.2f}pt  "
              f"dur med {st.median(r['dur_bars'] for r in g):>3.0f}b")
    print(f"  hora facada: {Counter(r['hora'][:2] for r in faca).most_common(6)}")

    print("\n--- WR por faixa de dist_nivel (o único filtro pré-entrada plausível) ---")
    for a, b in [(0, 3), (3, 6), (6, 10), (10, 15), (15, 25)]:
        g = [r for r in rows if a <= r['dist_nivel'] < b]
        if not g: continue
        wr = 100*sum(1 for r in g if r['usd'] > 0)/len(g)
        nf = sum(1 for r in faca if a <= r['dist_nivel'] < b)
        print(f"  {a:>2}-{b:<2}pt: n={len(g):<4} WR {wr:>3.0f}%  PnL/trade ${st.mean(r['usd'] for r in g):>+5.0f}  "
              f"facadas: {nf}")
    print("\n=> facada espalhada por todas as faixas, proporcional ao volume. Sem filtro possível.")
    print("   (loss-cut já rejeitado no item #16: mata 10,7% dos vencedores que também tocam -12,5pt MAE)")


if __name__ == '__main__':
    main()
