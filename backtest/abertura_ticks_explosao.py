#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ABERTURA NY - "quantos ticks de explosao da 1a vela?"

Pergunta: a partir do open de 9:30 ET, quando o preco desloca N ticks,
seguir esse movimento tem edge? Qual N e qual janela de leitura?

Dados: dados_databento/MNQ_1min_2022_2026.txt  (OHLCV 1-min, timestamp UTC)
Saida: tabelas no stdout + CSVs em backtest/out_abertura/

Limitacao: barras de 1 min, nao tick real. Proxy = caminho dos primeiros minutos.
Ordenacao intrabar (quando high e low disparam na mesma barra) e resolvida
PESSIMISTA para checagem de stop (adverso primeiro) e por heuristica de corpo
para direcao do gatilho.
"""
import os
import numpy as np
import pandas as pd

TICK = 0.25
DOLLAR_PER_TICK = 0.50   # MNQ
RT_COMM = 1.50           # comissao round-trip US$ (ajustavel)

HERE = os.path.dirname(__file__)
SRC = os.path.join(HERE, '..', 'dados_databento', 'MNQ_1min_2022_2026.txt')
OUT = os.path.join(HERE, 'out_abertura')
os.makedirs(OUT, exist_ok=True)

NS = [4, 6, 8, 10, 12, 16, 20, 24, 30, 40]      # ticks de "explosao"
WINDOWS = [1, 2, 3, 5]                            # min de leitura
HORIZONS = {'11h': (11, 0), '16h': (16, 0)}      # zera a posicao nesse horario ET
TARGET_MULTS = [2.0, 3.0]                         # alvo = mult * N ; stop = N


def carregar():
    print(f"lendo {SRC} ...")
    df = pd.read_csv(SRC, sep=';', header=None,
                     names=['ts', 'o', 'h', 'l', 'c', 'v'],
                     dtype={'ts': str})
    dt_utc = pd.to_datetime(df['ts'], format='%Y%m%d %H%M%S', utc=True)
    et = dt_utc.dt.tz_convert('America/New_York')
    df['et'] = et
    df['date'] = et.dt.date
    df['minutes'] = et.dt.hour * 60 + et.dt.minute
    df = df.sort_values('et').reset_index(drop=True)
    print(f"  {len(df):,} barras, {df['date'].nunique():,} dias  "
          f"({df['date'].min()} -> {df['date'].max()})")
    return df


OPEN_MIN = 9 * 60 + 30  # 09:30 ET


def por_dia(df):
    """gera (date, day_df) para dias com barra de abertura 9:30."""
    for d, g in df.groupby('date', sort=True):
        g = g.set_index('minutes')
        if OPEN_MIN not in g.index:
            continue
        yield d, g


def simula():
    df = carregar()
    dias = list(por_dia(df))
    print(f"  {len(dias):,} dias com abertura 9:30 valida\n")

    rows = []          # modo A (deslocamento)
    rows_b = []        # modo B (corpo da 1a vela)

    for d, g in dias:
        year = d.year
        o_open = g.loc[OPEN_MIN, 'o']
        # ---- MODO B: corpo da vela de 9:30 ----
        c_open = g.loc[OPEN_MIN, 'c']
        body_ticks = (c_open - o_open) / TICK
        # ---- caminho pos-abertura, por minuto ----
        # bar de entrada B = fechamento de 9:30 => avaliamos a partir de 9:31
        for W in WINDOWS:
            win_mins = [OPEN_MIN + k for k in range(W)]
            win = g.reindex(win_mins).dropna(subset=['o'])
            if win.empty:
                continue
            for N in NS:
                up_lvl = o_open + N * TICK
                dn_lvl = o_open - N * TICK
                trig_min = None
                direction = 0
                for m, bar in win.iterrows():
                    hit_up = bar['h'] >= up_lvl
                    hit_dn = bar['l'] <= dn_lvl
                    if hit_up and hit_dn:
                        # ambos na mesma barra: heuristica pelo corpo da barra
                        direction = 1 if bar['c'] >= bar['o'] else -1
                        trig_min = m
                        break
                    if hit_up:
                        direction = 1
                        trig_min = m
                        break
                    if hit_dn:
                        direction = -1
                        trig_min = m
                        break
                if trig_min is None:
                    continue  # nao explodiu nessa janela -> sem trade
                entry = o_open + direction * N * TICK
                _aval(rows, g, d, year, 'A', W, N, direction, trig_min, entry)

        # ---- MODO B: so precisa do corpo ----
        for N in NS:
            if abs(body_ticks) < N:
                continue
            direction = 1 if body_ticks > 0 else -1
            entry = c_open
            _aval(rows_b, g, d, year, 'B', 1, N, direction, OPEN_MIN, entry)

    ra = pd.DataFrame(rows)
    rb = pd.DataFrame(rows_b)
    ra.to_csv(os.path.join(OUT, 'trades_modoA.csv'), index=False)
    rb.to_csv(os.path.join(OUT, 'trades_modoB.csv'), index=False)
    return ra, rb, len(dias)


def _aval(sink, g, d, year, modo, W, N, direction, trig_min, entry):
    """avalia um sinal: MFE/MAE, first-passage, pnl por horizonte."""
    fut = g[g.index >= trig_min]
    rec = dict(date=str(d), year=year, modo=modo, W=W, N=N, dir=direction,
               entry=entry)

    # MFE/MAE + first-passage (stop=N, varios alvos) ate 16h
    mfe = 0.0
    mae = 0.0
    fp = {f'hit_{m}N': None for m in TARGET_MULTS}   # True=alvo, False=stop
    stopped = False
    hit = {m: False for m in TARGET_MULTS}
    for m, bar in fut.iterrows():
        fav = (bar['h'] - entry) / TICK if direction == 1 else (entry - bar['l']) / TICK
        adv = (entry - bar['l']) / TICK if direction == 1 else (bar['h'] - entry) / TICK
        mfe = max(mfe, fav)
        mae = max(mae, adv)
        # pessimista: adverso primeiro dentro da barra
        if not stopped and adv >= N:
            stopped = True
        for mult in TARGET_MULTS:
            if fp[f'hit_{mult}N'] is None:
                if stopped and not hit[mult]:
                    fp[f'hit_{mult}N'] = False
                elif fav >= mult * N:
                    hit[mult] = True
                    fp[f'hit_{mult}N'] = True
        if m >= 16 * 60:
            break
    rec['mfe_t'] = round(mfe, 1)
    rec['mae_t'] = round(mae, 1)
    for k, v in fp.items():
        rec[k] = v

    # pnl "close do horizonte" (sem stop/alvo, so segurar e zerar)
    for name, (hh, mm) in HORIZONS.items():
        cut = hh * 60 + mm
        sub = fut[fut.index <= cut]
        if sub.empty:
            rec[f'pnl_{name}_t'] = np.nan
            continue
        last_c = sub.iloc[-1]['c']
        pnl_t = (last_c - entry) / TICK * direction
        rec[f'pnl_{name}_t'] = round(pnl_t, 1)
    sink.append(rec)


def _exp_stop_alvo(sub, N, mult):
    """expectancia de trade stop=N alvo=mult*N a partir da col first-passage."""
    col = f'hit_{mult}N'
    res = sub[col].dropna()
    if len(res) == 0:
        return None
    wins = (res == True).sum()
    losses = (res == False).sum()
    undecided = len(sub) - len(res)  # nem alvo nem stop ate 16h -> zera no fim
    wr = wins / len(res)
    # pnl bruto ticks: win = +mult*N, loss = -N ; undecided ~ pnl_16h
    gross_t = wins * mult * N - losses * N
    und = sub[sub[col].isna()]
    gross_t += und['pnl_16h_t'].fillna(0).sum()
    n = len(sub)
    gross_usd = gross_t * DOLLAR_PER_TICK
    net_usd = gross_usd - n * RT_COMM
    return dict(n=n, wr=round(wr, 3), wins=int(wins), losses=int(losses),
                undecided=int(undecided),
                exp_gross_usd=round(gross_usd / n, 2),
                exp_net_usd=round(net_usd / n, 2),
                total_net_usd=round(net_usd, 0))


def resumo(ra, rb, ndias):
    for modo, df in (('A', ra), ('B', rb)):
        if df.empty:
            continue
        print("\n" + "=" * 100)
        print(f"MODO {modo}  ({'deslocamento N ticks do open' if modo=='A' else 'corpo da 1a vela >= N ticks'})")
        print("=" * 100)
        for W in sorted(df['W'].unique()):
            sw = df[df['W'] == W]
            print(f"\n--- janela leitura = {W} min ---")
            hdr = (f"{'N':>3} {'dias':>5} {'%dia':>5} "
                   f"{'MFE':>6} {'MAE':>6} {'MFE/MAE':>7} "
                   f"{'P(2N<-1N)':>9} "
                   f"{'a2N wr':>7} {'a2N $g':>7} {'a2N $n':>7} {'a2N tot':>9} "
                   f"{'a3N wr':>7} {'a3N $n':>7} {'a3N tot':>9}")
            print(hdr)
            for N in NS:
                s = sw[sw['N'] == N]
                if s.empty:
                    continue
                pct = len(s) / ndias * 100
                mfe = s['mfe_t'].median()
                mae = s['mae_t'].median()
                ratio = mfe / mae if mae else float('nan')
                p2 = s['hit_2.0N'].dropna()
                p2rate = (p2 == True).mean() if len(p2) else float('nan')
                e2 = _exp_stop_alvo(s, N, 2.0)
                e3 = _exp_stop_alvo(s, N, 3.0)
                if not e2 or not e3:
                    continue
                print(f"{N:>3} {len(s):>5} {pct:>4.0f}% "
                      f"{mfe:>6.1f} {mae:>6.1f} {ratio:>7.2f} "
                      f"{p2rate:>8.2f} "
                      f"{e2['wr']:>7.2f} {e2['exp_gross_usd']:>7.2f} {e2['exp_net_usd']:>7.2f} {e2['total_net_usd']:>9.0f} "
                      f"{e3['wr']:>7.2f} {e3['exp_net_usd']:>7.2f} {e3['total_net_usd']:>9.0f}")

    # quebra por ano p/ configs de destaque
    print("\n" + "=" * 100)
    print("QUEBRA POR ANO  (exp liquida US$/trade, alvo=2N, stop=N, comm 1.50 RT)")
    print("=" * 100)
    for modo, df in (('A', ra), ('B', rb)):
        if df.empty:
            continue
        for W in sorted(df['W'].unique()):
            for N in NS:
                s = df[(df['W'] == W) & (df['N'] == N)]
                if len(s) < 100:
                    continue
                per = []
                for y in sorted(s['year'].unique()):
                    sy = s[s['year'] == y]
                    e = _exp_stop_alvo(sy, N, 2.0)
                    per.append(f"{y}:{e['exp_net_usd']:>6.2f}(n{e['n']})" if e else f"{y}:--")
                alle = _exp_stop_alvo(s, N, 2.0)
                print(f"modo {modo} W{W} N{N:>2} | tudo {alle['exp_net_usd']:>6.2f} $/t "
                      f"(n{alle['n']}, wr {alle['wr']:.2f}) | " + "  ".join(per))


if __name__ == '__main__':
    ra, rb, ndias = simula()
    resumo(ra, rb, ndias)
    print(f"\nCSVs em {OUT}/")
