#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Converte o CSV OHLCV-1m do Databento (GLBX.MDP3: MES + MNQ outrights + spreads,
06/2025 -> 06/2026) em 2 arquivos no MESMO formato de NQ_dados/
  (YYYYMMDD HHMMSS;open;high;low;close;volume, timestamp em UTC)
um por root, já com front-month contínuo:
  dados_databento/MES_1min.txt
  dados_databento/MNQ_1min.txt

Front-month = por dia UTC, o outright de maior volume do root (rollover natural).
Spreads (símbolo com '-') descartados. Rodar 1x; depois o backtest usa
run_estrategias_comparativo.carregar('dados_databento') como sempre.
"""
import csv, os, sys

D = os.path.join(os.path.dirname(__file__), '..', 'dados_databento')
# cada CSV -> lista de roots (3 letras) que ele contem
CSVS = {
    'glbx-mdp3-20250601-20260613.ohlcv-1m.csv': ('MES', 'MNQ'),
    'm2k_mym.ohlcv-1m.csv':                     ('M2K', 'MYM'),
}


def proc(csv_name, roots):
    path = os.path.join(D, csv_name)
    if not os.path.exists(path):
        print(f"  (pulando {csv_name} — nao encontrado)"); return
    vol = {}
    with open(path, newline='') as fh:
        rd = csv.reader(fh); next(rd)
        for row in rd:
            sym = row[9]
            if '-' in sym: continue
            root = sym[:3]
            if root not in roots or len(sym) != 5: continue
            dia = row[0][:10].replace('-', '')
            d = vol.setdefault((root, dia), {})
            d[sym] = d.get(sym, 0.0) + float(row[8])
    front = {k: max(cs, key=cs.get) for k, cs in vol.items()}

    outs = {r: open(os.path.join(D, f'{r}_1min.txt'), 'w') for r in roots}
    seen = {r: set() for r in roots}; n = {r: 0 for r in roots}
    with open(path, newline='') as fh:
        rd = csv.reader(fh); next(rd)
        for row in rd:
            sym = row[9]
            if '-' in sym: continue
            root = sym[:3]
            if root not in roots or len(sym) != 5: continue
            ts = row[0]; dia = ts[:10].replace('-', '')
            if front.get((root, dia)) != sym: continue
            hhmmss = ts[11:13] + ts[14:16] + ts[17:19]
            key = dia + hhmmss
            if key in seen[root]: continue
            seen[root].add(key)
            o, h, l, c = float(row[4]), float(row[5]), float(row[6]), float(row[7])
            h = max(h, o, c); l = min(l, o, c)
            outs[root].write(f"{dia} {hhmmss};{o};{h};{l};{c};{float(row[8]):.0f}\n")
            n[root] += 1
    for r in roots:
        outs[r].close()
        seq = sorted((k[1], v) for k, v in front.items() if k[0] == r)
        rolls = [f"{d}:{c}" for i, (d, c) in enumerate(seq) if i == 0 or c != seq[i-1][1]]
        print(f"  {r}: {n[r]:,} barras -> {r}_1min.txt | rollovers: {rolls}")


def main():
    for csv_name, roots in CSVS.items():
        print(f"processando {csv_name} ...")
        proc(csv_name, roots)


if __name__ == '__main__':
    main()
