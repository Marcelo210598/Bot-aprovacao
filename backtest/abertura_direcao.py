#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ABERTURA NY - o deslocamento inicial PREVE a direcao das proximas barras?

Estudo puramente direcional (barra de 1 min responde isso; stop/alvo NAO).
Para cada dia:
  - open_price = open da barra 9:30 ET
  - sinal(W) = preco no fim do minuto W  -  open_price   (em ticks)
      W = 1,2,3,5 min
  - condiciona em |sinal| >= N  e no sinal da direcao
  - retorno futuro (ticks, ja no sentido do sinal) ao fim de:
      +1, +5, +15, +30, +60 min apos o sinal, e ate 11:00 e 16:00 ET
  - metricas: media do retorno, P(retorno>0), e "edge liquido"
    (media - 3 ticks de custo (1 tick spread + 1.5 US$ RT ~ 3 ticks))

Tambem: MFE/MAE por BARRA (close-to-close) no sentido do sinal ate +60min,
so pra ter ideia de amplitude (nao e excursao intrabar real).
"""
import os
import numpy as np
import pandas as pd

TICK = 0.25
DPT = 0.50               # US$/tick MNQ
COST_TICKS = 3.0         # custo ida+volta aproximado em ticks (spread+comissao)

HERE = os.path.dirname(__file__)
SRC = os.path.join(HERE, '..', 'dados_databento', 'MNQ_1min_2022_2026.txt')
OUT = os.path.join(HERE, 'out_abertura')
os.makedirs(OUT, exist_ok=True)

OPEN_MIN = 9 * 60 + 30
NS = [2, 4, 6, 8, 10, 12, 16, 20, 25, 30, 40]
WINDOWS = [1, 2, 3, 5]
FWD = [1, 5, 15, 30, 60]                 # min apos o sinal
CUT_ABS = {'11h': 11 * 60, '16h': 16 * 60}


def carregar():
    print(f"lendo {SRC} ...")
    df = pd.read_csv(SRC, sep=';', header=None,
                     names=['ts', 'o', 'h', 'l', 'c', 'v'], dtype={'ts': str})
    et = pd.to_datetime(df['ts'], format='%Y%m%d %H%M%S', utc=True).dt.tz_convert('America/New_York')
    df['date'] = et.dt.date
    df['min'] = et.dt.hour * 60 + et.dt.minute
    df['year'] = et.dt.year
    df = df.sort_values(['date', 'min']).reset_index(drop=True)
    print(f"  {len(df):,} barras, {df['date'].nunique():,} dias")
    return df


def matriz_precos(df):
    """pivota: linha = dia, coluna = minuto ET, valor = close. + open da 9:30."""
    piv = df.pivot_table(index='date', columns='min', values='c', aggfunc='last')
    opens = df[df['min'] == OPEN_MIN].set_index('date')['o']
    piv = piv.loc[opens.index.intersection(piv.index)]
    opens = opens.loc[piv.index]
    yr = df.groupby('date')['year'].first().loc[piv.index]
    return piv, opens, yr


def estudo(piv, opens, yr):
    minutes = piv.columns
    linhas = []
    for W in WINDOWS:
        sig_min = OPEN_MIN + W
        if sig_min not in minutes:
            continue
        sig_px = piv[sig_min]
        sig_t = (sig_px - opens) / TICK          # deslocamento em ticks (com sinal)
        valid_sig = sig_px.notna() & opens.notna()
        for N in NS:
            mask = valid_sig & (sig_t.abs() >= N)
            d = np.sign(sig_t[mask])              # +1 / -1
            base = sig_px[mask]                   # preco de referencia (fim do minuto W)
            n = int(mask.sum())
            if n < 50:
                continue
            row = dict(W=W, N=N, n=n, pct=round(n / len(piv) * 100, 1),
                       long_share=round((d > 0).mean(), 2))
            for f in FWD:
                fm = sig_min + f
                if fm not in minutes:
                    row[f'r{f}_mean'] = np.nan
                    continue
                fut = piv.loc[mask, fm]
                ret = (fut - base) / TICK * d     # retorno no sentido do sinal, ticks
                ret = ret.dropna()
                if len(ret) < 30:
                    row[f'r{f}_mean'] = np.nan
                    continue
                row[f'r{f}_mean'] = round(ret.mean(), 2)
                row[f'r{f}_p>0'] = round((ret > 0).mean(), 3)
                row[f'r{f}_net'] = round(ret.mean() - COST_TICKS, 2)
            for name, cm in CUT_ABS.items():
                if cm not in minutes:
                    continue
                fut = piv.loc[mask, cm]
                ret = ((fut - base) / TICK * d).dropna()
                row[f'{name}_mean'] = round(ret.mean(), 2) if len(ret) else np.nan
                row[f'{name}_p>0'] = round((ret > 0).mean(), 3) if len(ret) else np.nan
            # MFE/MAE por close ate +60min (amplitude grosseira)
            span = [sig_min + k for k in range(1, 61) if sig_min + k in minutes]
            sub = piv.loc[mask, span]
            exc = sub.sub(base, axis=0).div(TICK).mul(d, axis=0)
            row['mfe_close_med'] = round(exc.max(axis=1).median(), 1)
            row['mae_close_med'] = round(exc.min(axis=1).median(), 1)
            # quebra por ano do retorno +30
            fm30 = sig_min + 30
            if fm30 in minutes:
                per = []
                for y in sorted(yr.unique()):
                    ym = mask & (yr == y)
                    if ym.sum() < 20:
                        continue
                    r = ((piv.loc[ym, fm30] - sig_px[ym]) / TICK * np.sign(sig_t[ym])).dropna()
                    per.append(f"{y}:{r.mean():+.1f}(n{len(r)})")
                row['r30_por_ano'] = " ".join(per)
            linhas.append(row)
    return pd.DataFrame(linhas)


def mostra(res):
    pd.set_option('display.width', 220)
    pd.set_option('display.max_columns', 40)
    pd.set_option('display.max_rows', 200)
    print("\n===== RETORNO FUTURO MEDIO no sentido do sinal (ticks) — 1 tick MNQ = US$0.50 =====")
    print("net = media - 3 ticks de custo.  p>0 = fracao de vezes que continuou.\n")
    cols = ['W', 'N', 'n', 'pct', 'long_share',
            'r5_mean', 'r5_p>0', 'r15_mean', 'r15_p>0',
            'r30_mean', 'r30_p>0', 'r30_net', 'r60_mean', 'r60_p>0',
            '11h_mean', '11h_p>0', 'mfe_close_med', 'mae_close_med']
    cols = [c for c in cols if c in res.columns]
    print(res[cols].to_string(index=False))
    print("\n===== RETORNO +30min POR ANO (ticks) =====")
    for _, r in res.iterrows():
        if isinstance(r.get('r30_por_ano'), str):
            print(f"W{int(r['W'])} N{int(r['N']):>2} (n{int(r['n'])}, cont {r.get('r30_p>0','?')}): {r['r30_por_ano']}")
    res.to_csv(os.path.join(OUT, 'direcao.csv'), index=False)
    print(f"\nCSV: {OUT}/direcao.csv")


if __name__ == '__main__':
    df = carregar()
    piv, opens, yr = matriz_precos(df)
    print(f"  matriz: {piv.shape[0]} dias x {piv.shape[1]} minutos")
    res = estudo(piv, opens, yr)
    mostra(res)
