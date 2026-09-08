#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera o arquivo de importacao de dado historico do NinjaTrader 8 a partir do CSV
do Databento (GLBX.MDP3, OHLCV-1m, MYM outrights + spreads, 2022-01 -> 2026-09).

VARIANTE MYM do backtest/gera_import_nt8.py (que e' pro MNQ). Mesma logica:
  - Databento ts_event = UTC, inicio da barra  ->  Chicago, +1 min (fim da barra)
  - front-month continuo: por dia UTC, o outright MYM de maior volume (roll natural)
  - spreads (simbolo com '-') descartados

Saida: dados_databento/MYM_NT8_import_2022_2026.txt  (+ .zip com 'MYM 12-25.txt' dentro)

Formato NT8 (Ferramentas -> Dados historicos -> Importar):
  AAAAMMDD HHMMSS;abertura;maxima;minima;fechamento;volume
  - 1 linha por barra de 1 minuto, SEM cabecalho
  - horario no FUSO DA BOLSA (CME = America/Chicago), no FIM da barra

MYM: tick = 1,0 ponto Dow, $0,50/ponto.

Depois de importar em "MYM 12-25", rodar o Analisador de Estrategia no
BotAprovacaoDow_MYM, periodo IS 2022-01 -> 2025-12 e holdout 2026-01 -> 2026-09.
"""
import csv, os, zipfile
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

CHI = ZoneInfo('America/Chicago')
UTC = timezone.utc
D = os.path.join(os.path.dirname(__file__), '..', 'dados_databento')
CSV_IN  = os.path.join(D, 'glbx-mdp3-20220101-20260907.ohlcv-1m.csv')
TXT_OUT = os.path.join(D, 'MYM_NT8_import_2022_2026.txt')
ZIP_OUT = os.path.join(D, 'MYM_NT8_import_2022_2026.zip')
NOME_NO_ZIP = 'MYM 12-25.txt'   # NT8 auto-detecta o instrumento pelo nome do arquivo


def main():
    # passo 1: volume por (dia_utc, symbol) -> front month do dia
    vol = {}
    with open(CSV_IN, newline='') as fh:
        rd = csv.reader(fh); next(rd)
        for row in rd:
            ts, sym = row[0], row[9]
            if '-' in sym:
                continue
            dia = ts[:10]
            vol[(dia, sym)] = vol.get((dia, sym), 0.0) + float(row[8])
    front = {}
    for (dia, sym), v in vol.items():
        if dia not in front or v > front[dia][1]:
            front[dia] = (sym, v)
    print(f"  {len(front)} dias | {min(front)} ({front[min(front)][0]}) -> "
          f"{max(front)} ({front[max(front)][0]})")

    # passo 2: reescreve so as barras do front-month, convertendo o timestamp
    linhas = []
    with open(CSV_IN, newline='') as fh:
        rd = csv.reader(fh); next(rd)
        for row in rd:
            ts, sym = row[0], row[9]
            if '-' in sym:
                continue
            dia = ts[:10]
            if front.get(dia, (None,))[0] != sym:
                continue
            # ts_event UTC (inicio da barra) -> Chicago, +1 min (fim da barra)
            dt_utc = datetime(int(ts[0:4]), int(ts[5:7]), int(ts[8:10]),
                              int(ts[11:13]), int(ts[14:16]), tzinfo=UTC)
            dt_chi = (dt_utc + timedelta(minutes=1)).astimezone(CHI)
            o, h, l, c, v = float(row[4]), float(row[5]), float(row[6]), float(row[7]), int(float(row[8]))
            h = max(h, o, c); l = min(l, o, c)
            linhas.append((dt_chi, f"{dt_chi:%Y%m%d %H%M%S};{o:.2f};{h:.2f};{l:.2f};{c:.2f};{v}"))

    linhas.sort(key=lambda x: x[0])
    with open(TXT_OUT, 'w') as fh:
        fh.write('\n'.join(s for _, s in linhas) + '\n')
    mb = os.path.getsize(TXT_OUT) / 1e6
    print(f"  {len(linhas):,} barras -> {os.path.basename(TXT_OUT)} ({mb:.0f} MB)")
    print(f"  primeira: {linhas[0][1]}")
    print(f"  ultima:   {linhas[-1][1]}")

    with zipfile.ZipFile(ZIP_OUT, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(TXT_OUT, NOME_NO_ZIP)
    zmb = os.path.getsize(ZIP_OUT) / 1e6
    print(f"  {os.path.basename(ZIP_OUT)} ({zmb:.0f} MB) — contem '{NOME_NO_ZIP}'")


if __name__ == '__main__':
    main()
