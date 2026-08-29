#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Marcelo reclamou (29/08) que o forward test do BETrigger25+MaxDist20 ta com media de
~$1/trade e perdas grandes demais (stops cheios de -$105/-$118 comendo o ganho de
varios trades bons). Esse script usa o motor OFICIAL (`run_estrategias_comparativo.bt`,
o mesmo que ja bate os 50% documentados) pra medir, no backtest de 13 meses:

  1) Ganho medio, perda media e ratio ganho/perda da estrategia REV no baseline atual
     (SL 12,5pt) -> serve de referencia pro que o forward test de poucos dias mostrou.
  2) SL MENOR (10, 8, 6pt) -> objetivo: reduzir o tamanho de cada perda, ainda que
     aumente a frequencia de stop.
  3) BE trigger mais agressivo combinado com SL menor.

So' leitura/analise, ZERO mudanca em .cs ou em producao. `bt()` ganhou 1 chave nova
('trades', lista crua de PnL por trade) — mudanca aditiva, nao quebra nenhum script
que ja consome esse dict.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_estrategias_comparativo as rc
from run_estrategias_comparativo import bt, carregar, domingo_ranges


def metricas_qualidade(r):
    trades = r['trades']
    n = len(trades)
    if n == 0:
        return dict(n=0, avg_win=0.0, avg_loss=0.0, ratio=0.0)
    ganhos = [t for t in trades if t > 0]
    perdas = [t for t in trades if t <= 0]
    avg_win = sum(ganhos) / len(ganhos) if ganhos else 0.0
    avg_loss = sum(perdas) / len(perdas) if perdas else 0.0
    ratio = (avg_win / abs(avg_loss)) if avg_loss != 0 else float('inf')
    return dict(n=n, avg_win=avg_win, avg_loss=avg_loss, ratio=ratio)


def main():
    print("Carregando NQ 1-min real (13 meses)...")
    bars = carregar("NQ_dados")
    dom = domingo_ranges(bars)
    dt_ini, dt_fim = bars[0]['dt'], bars[-1]['dt']
    dias_totais = (dt_fim.date() - dt_ini.date()).days
    meses = max(dias_totais / 30.4, 0.1)
    print(f"{len(bars):,} barras | {dt_ini.date()} -> {dt_fim.date()} (~{meses:.1f} meses)\n")

    print("=" * 108)
    print("QUALIDADE DO TRADE — estrategia REV (a mesma do BotAprovacao/BETrigger25), 13 meses continuos")
    print("=" * 108)
    linha = "{:<30}{:>6}{:>7}{:>12}{:>12}{:>8}{:>8}{:>12}{:>12}"
    print(linha.format("Config", "N", "WR%", "Ganho med", "Perda med", "Ratio", "PF", "Net $", "Net/mes"))

    original_sl = rc.PTS_SL
    original_be_trig = rc.PTS_BE_TRIG
    original_trail = rc.PTS_TRAIL

    cenarios = [
        ("SL 12,5 (atual)", 12.5, original_be_trig, original_trail),
        ("SL 10,0", 10.0, original_be_trig, original_trail),
        ("SL 8,0", 8.0, original_be_trig, original_trail),
        ("SL 6,0", 6.0, original_be_trig, original_trail),
        ("SL 12,5 + BE trig 2,5", 12.5, 2.5, original_trail),
        ("SL 10,0 + BE trig 2,5", 10.0, 2.5, original_trail),
        ("SL 8,0 + BE trig 2,5", 8.0, 2.5, original_trail),
        ("SL 8,0 + BE2,5 + Trail1,0", 8.0, 2.5, 1.0),
        ("SL 6,0 + BE trig 2,0", 6.0, 2.0, original_trail),
    ]

    try:
        for nome, sl, be_trig, trail in cenarios:
            rc.PTS_SL = sl
            rc.PTS_BE_TRIG = be_trig
            rc.PTS_TRAIL = trail
            r = bt(bars, dom, fontes=['REV'])
            m = metricas_qualidade(r)
            ratio_str = f"{m['ratio']:.2f}" if m['ratio'] != float('inf') else 'inf'
            pf_str = f"{r['pf']:.2f}" if r['pf'] != float('inf') else 'inf'
            print(linha.format(nome, m['n'], f"{r['wr']:.1f}", f"${m['avg_win']:.2f}",
                                f"${m['avg_loss']:.2f}", ratio_str, pf_str,
                                f"${r['net']:.2f}", f"${r['net']/meses:.2f}"))
    finally:
        rc.PTS_SL = original_sl
        rc.PTS_BE_TRIG = original_be_trig
        rc.PTS_TRAIL = original_trail

    print("\nLembrete: backtest continuo de 13 meses, SEM a trava de aprovacao/estouro de conta")
    print("(so' PnL bruto da estrategia) — serve pra comparar QUALIDADE do trade entre configs,")
    print("nao a taxa de aprovacao (isso e' testa_gap_e_be_trigger.py / run_janela_30d.py).")


if __name__ == '__main__':
    main()
