#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Re-roda as 2 grades (gatilho de BE, trailing x alvo) em granularidade de
1min (sem resample p/ 5min), ja que 18/08 mostrou que 5min estava mascarando
resultado (ratio 1.48 em 5min vs 0.69 em 1min vs 0.54 real)."""
import sys, os, csv
sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp
import sensibilidade_breakeven as sb
import grid_trailing_alvo as gta

print("Carregando 1min (sem resample) ...")
bars1m = dp.carregar_1min(dp.PASTA_DADOS)
print(f"  {len(bars1m):,} candles de 1min\n")

SLIP = 2 * dp.TICK

# ===================== GRADE 1: GATILHO DE BREAKEVEN =====================
print("=" * 100)
print("GRADE 1 — GATILHO DE BREAKEVEN, 1min, ano inteiro, slippage 2 ticks "
      "(trail 1,75 / alvo 60 / SL 12,5 fixos)")
print("=" * 100)
print(f"{'Gatilho':<9}{'Trades':<8}{'GanhoMed':<11}{'PerdaMed':<11}{'Ratio':<8}"
      f"{'WR%':<7}{'PnLTotal':<12}{'TP':<5}{'BE/Trail':<10}{'SL'}")
linhas_be = []
for g in sb.GATILHOS:
    tr = sb.simula(bars1m, g, sb.ANO_INICIO, sb.ANO_FIM, slip_pts=SLIP)
    r = sb.resume(tr); r['gatilho'] = g
    marca = ' (atual)' if g == 3.75 else ''
    print(f"{g:<9}{r['trades']:<8}${r['ganho_medio']:<10.1f}${r['perda_media']:<10.1f}"
          f"{r['ratio']:<8.2f}{r['wr']:<7.1f}${r['pnl_total']:<11.1f}"
          f"{r['tp_hits']:<5}{r['be_trail_hits']:<10}{r['sl_hits']}{marca}")
    linhas_be.append(r)

csv_path1 = os.path.join(os.path.dirname(__file__), 'grade_breakeven_1min.csv')
with open(csv_path1, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(linhas_be[0].keys())); w.writeheader(); w.writerows(linhas_be)
print(f"\nCSV: {csv_path1}")

# ===================== GRADE 2: TRAILING x ALVO =====================
print("\n" + "=" * 100)
print("GRADE 2 — TRAILING x ALVO, 1min, ano inteiro, slippage 2 ticks "
      "(BE gatilho 3,75 / trava 2,5 / SL 12,5 fixos)")
print("=" * 100)
print(f"{'Trail':<7}{'Alvo':<7}{'N':<6}{'WR%':<7}{'GanhoMed':<11}{'PerdaMed':<11}{'Ratio':<7}{'PnLTotal'}")
linhas_grid = []
trails = [1.75, 3.0, 5.0, 8.0]
alvos = [20.0, 30.0, 40.0, 60.0]
for tr in trails:
    for tp in alvos:
        trs = gta.simula(bars1m, tr, tp)
        r = gta.resume(trs)
        marca = ' (atual)' if tr == 1.75 and tp == 60.0 else ''
        print(f"{tr:<7}{tp:<7}{r['n']:<6}{r['wr']:<7.1f}${r['gm']:<10.1f}${r['pm']:<10.1f}"
              f"{r['ratio']:<7.2f}${r['pnl']:.1f}{marca}")
        linhas_grid.append({'trail': tr, 'alvo': tp, **r})

csv_path2 = os.path.join(os.path.dirname(__file__), 'grid_trailing_alvo_1min.csv')
with open(csv_path2, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(linhas_grid[0].keys())); w.writeheader(); w.writerows(linhas_grid)
print(f"\nCSV: {csv_path2}")

# ===================== VEREDITO =====================
print("\n" + "=" * 100)
print("VEREDITO")
print("=" * 100)
melhor_be = max(linhas_be, key=lambda l: l['pnl_total'])
base_be = linhas_be[0]
print(f"Gatilho — baseline (3,75pt): ratio={base_be['ratio']:.2f} PnL=${base_be['pnl_total']:.1f}")
print(f"Gatilho — melhor PnL: {melhor_be['gatilho']}pt -> ratio={melhor_be['ratio']:.2f} "
      f"PnL=${melhor_be['pnl_total']:.1f}")

melhor_grid = max(linhas_grid, key=lambda l: l['pnl'])
base_grid = linhas_grid[0]
print(f"\nTrail/Alvo — baseline (1,75/60): ratio={base_grid['ratio']:.2f} PnL=${base_grid['pnl']:.1f}")
print(f"Trail/Alvo — melhor PnL: trail={melhor_grid['trail']} alvo={melhor_grid['alvo']} -> "
      f"ratio={melhor_grid['ratio']:.2f} PnL=${melhor_grid['pnl']:.1f}")
