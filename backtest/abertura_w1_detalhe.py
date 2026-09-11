#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ABERTURA W=1 em detalhe: o sinal do 1o minuto tem edge DIRECIONAL real,
ou e so o mercado derivando pra cima?

Separa LONG-signal vs SHORT-signal. Compara com baseline "sempre comprado".
Mostra media E mediana. Sim de stop/alvo checado no CLOSE de 1min (limite
otimista, subestima stop intrabar) so pra ter ordem de grandeza.
"""
import os
import numpy as np
import pandas as pd

TICK = 0.25
DPT = 0.50
HERE = os.path.dirname(__file__)
SRC = os.path.join(HERE, '..', 'dados_databento', 'MNQ_1min_2022_2026.txt')

OPEN_MIN = 9 * 60 + 30
SIG_MIN = OPEN_MIN + 1          # fim do 1o minuto
NS = [2, 4, 6, 8, 10, 14]
FWD_MIN = [5, 15, 30, 60, 90]


def carregar():
    df = pd.read_csv(SRC, sep=';', header=None,
                     names=['ts', 'o', 'h', 'l', 'c', 'v'], dtype={'ts': str})
    et = pd.to_datetime(df['ts'], format='%Y%m%d %H%M%S', utc=True).dt.tz_convert('America/New_York')
    df['date'] = et.dt.date
    df['min'] = et.dt.hour * 60 + et.dt.minute
    df['year'] = et.dt.year
    return df.sort_values(['date', 'min']).reset_index(drop=True)


def main():
    df = carregar()
    piv = df.pivot_table(index='date', columns='min', values='c', aggfunc='last')
    hi = df.pivot_table(index='date', columns='min', values='h', aggfunc='max')
    lo = df.pivot_table(index='date', columns='min', values='l', aggfunc='min')
    opens = df[df['min'] == OPEN_MIN].set_index('date')['o']
    idx = opens.index.intersection(piv.index)
    piv, hi, lo, opens = piv.loc[idx], hi.loc[idx], lo.loc[idx], opens.loc[idx]
    yr = df.groupby('date')['year'].first().loc[idx]

    sig_px = piv[SIG_MIN]
    sig_t = (sig_px - opens) / TICK

    # baseline: retorno "sempre comprado" a partir do fim do 1o min
    print("=== BASELINE: retorno medio/mediano SEMPRE COMPRADO a partir de 9:31 (ticks) ===")
    for f in FWD_MIN:
        fm = SIG_MIN + f
        if fm not in piv.columns:
            continue
        r = ((piv[fm] - sig_px)).dropna() / TICK
        print(f"  +{f:>2}min: media {r.mean():+6.2f}  mediana {r.median():+6.2f}  p>0 {(r>0).mean():.3f}  (n{len(r)})")

    for N in NS:
        m_long = sig_t >= N
        m_short = sig_t <= -N
        print(f"\n{'='*90}\nN = {N} ticks   |   LONG-sig n={int(m_long.sum())}   SHORT-sig n={int(m_short.sum())}")
        print(f"{'':10} {'+5m':>16} {'+15m':>16} {'+30m':>16} {'+60m':>16} {'+90m':>16}")
        for nome, mask, d in (('LONG ', m_long, 1), ('SHORT', m_short, -1)):
            cells = []
            for f in FWD_MIN:
                fm = SIG_MIN + f
                if fm not in piv.columns:
                    cells.append(f"{'--':>16}"); continue
                r = ((piv.loc[mask, fm] - sig_px[mask]) / TICK * d).dropna()
                cells.append(f"{r.mean():+6.1f}/{r.median():+5.1f} {(r>0).mean():.2f}".rjust(16))
            print(f"  {nome}   " + " ".join(cells))
        # LONG e SHORT juntos (o que o bot faria): retorno no sentido do sinal
        m_any = m_long | m_short
        d_any = np.sign(sig_t[m_any])
        print("  -- combinado (media/mediana p>0), e por ano no +30m --")
        for f in FWD_MIN:
            fm = SIG_MIN + f
            if fm not in piv.columns:
                continue
            r = ((piv.loc[m_any, fm] - sig_px[m_any]) / TICK * d_any).dropna()
            print(f"     +{f:>2}m: {r.mean():+6.2f} / {r.median():+6.2f}  p>0 {(r>0).mean():.3f}")
        fm30 = SIG_MIN + 30
        by = []
        for y in sorted(yr.unique()):
            ym = m_any & (yr == y)
            r = ((piv.loc[ym, fm30] - sig_px[ym]) / TICK * np.sign(sig_t[ym])).dropna()
            if len(r) < 20:
                continue
            by.append(f"{y}: {r.mean():+6.1f}/{r.median():+5.1f} (n{len(r)}, p>0 {(r>0).mean():.2f})")
        print("     +30m por ano: " + " | ".join(by))

        # sim close-based stop/alvo (LIMITE OTIMISTA - so checa no fechamento de 1min)
        print("  -- sim stop/alvo checado no CLOSE de 1min (otimista, subestima stop) --")
        for stop_t, tgt_t in [(N, 2 * N), (N, 3 * N), (2 * N, 3 * N), (2 * N, 4 * N)]:
            pnls = []
            span = [SIG_MIN + k for k in range(1, 121) if SIG_MIN + k in piv.columns]
            for dte in piv.index[m_any]:
                d = 1 if sig_t[dte] > 0 else -1
                entry = sig_px[dte]
                out = None
                for mm in span:
                    px = piv.at[dte, mm]
                    if np.isnan(px):
                        continue
                    move = (px - entry) / TICK * d
                    if move <= -stop_t:
                        out = -stop_t; break
                    if move >= tgt_t:
                        out = tgt_t; break
                if out is None:
                    last = piv.at[dte, span[-1]] if not np.isnan(piv.at[dte, span[-1]]) else entry
                    out = (last - entry) / TICK * d
                pnls.append(out)
            pnls = np.array(pnls)
            gross = pnls * DPT
            net = gross - 1.5
            print(f"     stop {stop_t:>3} alvo {tgt_t:>3}: wr {(pnls>0).mean():.2f}  "
                  f"exp_bruto ${gross.mean():+5.2f}  exp_liq ${net.mean():+5.2f}  "
                  f"total_liq ${net.sum():+8.0f}  (n{len(pnls)})")


if __name__ == '__main__':
    main()
