#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera o arquivo de importacao de dado historico do NinjaTrader 8 a partir do CSV
do Databento (GLBX.MDP3, OHLCV-1m, MNQ outrights + spreads, 2022-06 -> 2026-08).

Saida: dados_databento/MNQ_NT8_import_2022_2026.txt

Formato NT8 (Ferramentas -> Dados historicos -> Importar):
  AAAAMMDD HHMMSS;abertura;maxima;minima;fechamento;volume
  - 1 linha por barra de 1 minuto, SEM cabecalho
  - horario no FUSO DA BOLSA (CME = America/Chicago), no FIM da barra

Conversoes feitas aqui:
  - Databento ts_event = UTC, inicio da barra  ->  Chicago, +1 min (fim da barra)
  - front-month continuo: por dia UTC, o outright MNQ de maior volume (roll natural)
  - spreads (simbolo com '-') descartados

Depois de importar em "MNQ ##-##", rodar o Analisador de Estrategia no
BotAprovacao_BETrigger25 com "So operar SHORT" ligado, periodo 2022-01 -> 2026-08.
"""
import csv, os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

CHI = ZoneInfo('America/Chicago')
UTC = timezone.utc
D = os.path.join(os.path.dirname(__file__), '..', 'dados_databento')
CSV_IN  = os.path.join(D, 'glbx-mdp3-20220601-20260831.ohlcv-1m.csv')
TXT_OUT = os.path.join(D, 'MNQ_NT8_import_2022_2026.txt')


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


if __name__ == '__main__':
    main()
