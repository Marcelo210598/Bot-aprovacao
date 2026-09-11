#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Carrega OHLCV-1s do Databento (DBN ou CSV), monta front-month continuo,
converte pra ET e recorta a janela da abertura -> arquivo enxuto.

Uso:
  python3 carrega_1s.py <arquivo.dbn.zst|arquivo.csv.zst|arquivo.csv> <tag_saida>

Saida: dados_databento/MNQ_1s_<tag>.txt
  formato: YYYYMMDD HHMMSS;open;high;low;close;volume   (hora em ET, sem tz)
  so barras com ET time em [WIN_START, WIN_END)
"""
import os
import sys
import pandas as pd

HERE = os.path.dirname(__file__)
OUTDIR = os.path.join(HERE, '..', 'dados_databento')

WIN_START = 9 * 60 + 0      # 09:00 ET
WIN_END = 12 * 60 + 0       # 12:00 ET (cobre abertura + 2h30)


def ler(path):
    if path.endswith('.dbn') or path.endswith('.dbn.zst'):
        import databento as db
        df = db.DBNStore.from_file(path).to_df()
        df = df.reset_index()  # ts_event vira coluna
    else:
        # CSV (possivelmente .zst) do Databento
        comp = 'zstd' if path.endswith('.zst') else None
        df = pd.read_csv(path, compression=comp)
    # normaliza nomes
    if 'ts_event' not in df.columns:
        raise SystemExit(f"colunas inesperadas: {df.columns.tolist()}")
    df = df[['ts_event', 'symbol', 'open', 'high', 'low', 'close', 'volume']].copy()
    df['ts_event'] = pd.to_datetime(df['ts_event'], utc=True)
    return df


def processar(df):
    df = df[~df['symbol'].str.contains('-', na=False)]      # sem spreads
    et = df['ts_event'].dt.tz_convert('America/New_York')
    df = df.assign(date=et.dt.date,
                   minutes=et.dt.hour * 60 + et.dt.minute,
                   hhmmss=et.dt.strftime('%H%M%S'),
                   ymd=et.dt.strftime('%Y%m%d'))
    # front-month por dia = maior volume total
    vol = df.groupby(['date', 'symbol'])['volume'].sum()
    front = vol.groupby('date').idxmax().map(lambda t: t[1])   # date -> symbol
    df = df[df.apply(lambda r: front.get(r['date']) == r['symbol'], axis=1)]
    # janela da abertura
    df = df[(df['minutes'] >= WIN_START) & (df['minutes'] < WIN_END)]
    df = df.sort_values('ts_event')
    return df, front


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(1)
    src, tag = sys.argv[1], sys.argv[2]
    print(f"lendo {src} ...")
    df = ler(src)
    print(f"  {len(df):,} linhas brutas  ({df['ts_event'].min()} -> {df['ts_event'].max()})")
    df, front = processar(df)
    print(f"  {len(df):,} linhas na janela {WIN_START//60}:00-{WIN_END//60}:00 ET, "
          f"{df['date'].nunique()} dias")
    print("  front-month usado:", front.value_counts().to_dict())
    out = os.path.join(OUTDIR, f'MNQ_1s_{tag}.txt')
    with open(out, 'w') as fh:
        for r in df.itertuples(index=False):
            fh.write(f"{r.ymd} {r.hhmmss};{r.open};{r.high};{r.low};{r.close};{int(r.volume)}\n")
    sz = os.path.getsize(out) / 1e6
    print(f"  -> {out}  ({sz:.1f} MB, {len(df):,} barras)")


if __name__ == '__main__':
    main()
