#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Carrega os 2 arquivos exportados direto do feed real (MNQ JUN26 + SEP26),
mesmo formato do NQ_dados (UTC;O;H;L;C;V), cobrindo o mes de junho inteiro."""
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')
UTC = timezone.utc
ARQUIVOS = [
    os.path.expanduser('~/Desktop/MNQ 06-26.Last.txt'),
    os.path.expanduser('~/Desktop/MNQ 09-26.Last2.txt'),
]


def carregar():
    vistos = {}
    for f in ARQUIVOS:
        with open(f, encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                line = line.strip()
                if not line: continue
                try:
                    dtp, resto = line.split(';', 1)
                    data, hora = dtp.split()
                    o, h, l, c, v = resto.split(';')
                    dt = datetime(int(data[:4]), int(data[4:6]), int(data[6:8]),
                                  int(hora[:2]), int(hora[2:4]), tzinfo=UTC)
                    o, h, l, c, v = float(o), float(h), float(l), float(c), float(v)
                except Exception:
                    continue
                if dt not in vistos:
                    vistos[dt] = (dt.astimezone(ET), o, h, l, c, v)
    return [{'dt': vistos[k][0], 'o': vistos[k][1], 'h': vistos[k][2],
             'l': vistos[k][3], 'c': vistos[k][4], 'v': vistos[k][5]}
            for k in sorted(vistos)]


if __name__ == '__main__':
    bars = carregar()
    print(f"{len(bars):,} candles carregados, {bars[0]['dt']} a {bars[-1]['dt']}")
