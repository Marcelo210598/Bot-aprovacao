#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera o arquivo de importacao NT8 da serie CONTINUA front-month do MNQ, a partir
do CSV Databento (o mesmo que o harness Python le).

VARIANTE MNQ do backtest/gera_import_nt8_mym.py. Mesma logica:
  - Databento ts_event = UTC, INICIO da barra -> EASTERN (ET), +1 min (FIM da barra)
  - front-month continuo: por dia UTC, o outright MNQ de MAIOR volume (roll natural)
  - spreads (simbolo com '-') descartados
  - SEM ajuste de preco (nao e' back-adjusted) — precos reais do outright ativo

⚠️ CONVERSAO PARA EASTERN (nao Chicago): o fuso global do NT8 desta maquina esta
em Eastern e o campo "Fuso horario de dados importados" volta pro padrao Eastern
toda vez. Convertendo o arquivo p/ ET, o import com o padrao (Eastern) fica certo.
O contrato §8 e' todo em ET -> zero conversao mental.

Saida: dados_databento/MNQ_NT8_import_2022_2026_CONT.txt  (+ .zip)

O nome do arquivo DENTRO do zip decide em qual contrato o NT8 importa. Usamos
um contrato JA EXPIRADO ('MNQ 12-21') de proposito: o NT8 nao busca dados de
feed (Rithmic) para contrato vencido, entao o Analyzer usa 100% o dado importado,
sem merge/override do feed. (O problema visto no dump: 'MNQ 12-25' e' um contrato
REAL ativo, e o NT8 estava servindo o MNQZ5 fininho de verdade em vez da serie
continua importada.)

Depois de importar em 'MNQ 12-21' (fuso Eastern), rodar OnFadeHarness no Strategy
Analyzer apontando 'Ativo = MNQ 12-21', periodo 2024-09-13 -> 2024-11-01.
"""
import csv, os, zipfile
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ET  = ZoneInfo("America/New_York")
UTC = timezone.utc
D = os.path.join(os.path.dirname(__file__), "..", "dados_databento")
CSV_IN  = os.path.join(D, "glbx-mdp3-20220601-20260831.ohlcv-1m.csv")
TXT_OUT = os.path.join(D, "MNQ_NT8_import_2022_2026_CONT.txt")
ZIP_OUT = os.path.join(D, "MNQ_NT8_import_2022_2026_CONT.zip")
NOME_NO_ZIP = "MNQ 12-21.txt"   # contrato EXPIRADO -> NT8 nao mistura feed


def main():
    # passo 1: volume por (dia_utc, symbol) -> front month do dia
    vol = {}
    with open(CSV_IN, newline="") as fh:
        rd = csv.reader(fh); next(rd)
        for row in rd:
            ts, sym = row[0], row[9]
            if "-" in sym:
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
    with open(CSV_IN, newline="") as fh:
        rd = csv.reader(fh); next(rd)
        for row in rd:
            ts, sym = row[0], row[9]
            if "-" in sym:
                continue
            dia = ts[:10]
            if front.get(dia, (None,))[0] != sym:
                continue
            dt_utc = datetime(int(ts[0:4]), int(ts[5:7]), int(ts[8:10]),
                              int(ts[11:13]), int(ts[14:16]), tzinfo=UTC)
            dt_et = (dt_utc + timedelta(minutes=1)).astimezone(ET)
            o, h, l, c, v = (float(row[4]), float(row[5]), float(row[6]),
                             float(row[7]), int(float(row[8])))
            h = max(h, o, c); l = min(l, o, c)
            linhas.append((dt_et, f"{dt_et:%Y%m%d %H%M%S};{o:.2f};{h:.2f};{l:.2f};{c:.2f};{v}"))

    linhas.sort(key=lambda x: x[0])
    with open(TXT_OUT, "w") as fh:
        fh.write("\n".join(s for _, s in linhas) + "\n")
    mb = os.path.getsize(TXT_OUT) / 1e6
    print(f"  {len(linhas):,} barras -> {os.path.basename(TXT_OUT)} ({mb:.0f} MB)")
    print(f"  primeira: {linhas[0][1]}")
    print(f"  ultima:   {linhas[-1][1]}")

    with zipfile.ZipFile(ZIP_OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(TXT_OUT, NOME_NO_ZIP)
    zmb = os.path.getsize(ZIP_OUT) / 1e6
    print(f"  {os.path.basename(ZIP_OUT)} ({zmb:.0f} MB) — contem '{NOME_NO_ZIP}'")

    # sanity: preco no dia da reconciliacao (deve ser ~19.400, nao ~20.600)
    for _, s in linhas:
        if s.startswith("20240913 093"):   # ~09:3x ET = abertura RTH
            print(f"  [sanity 2024-09-13 ~abertura RTH] {s}")
            break


if __name__ == "__main__":
    main()
