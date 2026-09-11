#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ABERTURA DE NY — 6 ideias NOVAS (11/09/2026), diferentes do "espera+segue" do v7.
Mesma metodologia honesta do abertura_grid_dolar.py (fill com GAP no stop, sem
look-ahead) sobre os 352 pregoes de dado 1s (2024/2025/2026ago).

  A) Opening Range Breakout classico — range dos 1os R minutos, rompe DEPOIS.
  B) Filtro por range do pre-mercado (09:00-09:30 ET, proxy de overnight —
     o dado 1s NAO tem sessao eletronica anterior, so 09:00 em diante).
  C) Filtro por volume do 1o minuto (baseline movel causal, so dias passados).
  D) Fada SO em movimento extremo (gatilho bem maior, nao ruido de 3t).
  E) Entrada por LIMITE na retracao (nao persegue a mercado).
  F) Rompe a maxima/minima do "dia anterior" na MESMA janela 09:00-12:00
     (proxy de Initial Balance — nao e a sessao completa de ontem).

Uso: python3 backtest/abertura_ideas.py
"""
import importlib.util
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location('h', os.path.join(HERE, 'abertura_harness.py'))
H = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(H)

TICK = H.TICK
PV = H.POINT_VALUE
QTY = 6
COMM = 1.24
OPEN_SOD = H.OPEN_SOD          # 09:30:00
PREMKT_SOD = 9 * 3600          # 09:00:00 (inicio real do dado)

DAT = os.path.join(HERE, '..', 'dados_databento')
BLOCOS = H.BLOCOS


# ---------------- loader full-day (mantem 09:00 em diante + volume) ----------------
def load_days_full(fn):
    df = pd.read_csv(os.path.join(DAT, fn), sep=';', header=None,
                      names=['ts', 'o', 'h', 'l', 'c', 'v'], dtype={'ts': str})
    t = pd.to_datetime(df['ts'], format='%Y%m%d %H%M%S')
    df['date'] = t.dt.normalize()
    df['sod'] = (t.dt.hour * 3600 + t.dt.minute * 60 + t.dt.second).astype(np.int32)
    days = []
    for d, g in df.groupby('date', sort=True):
        sod = g['sod'].values
        i930 = np.searchsorted(sod, OPEN_SOD)
        if i930 >= len(sod) or sod[i930] != OPEN_SOD:
            continue
        days.append(dict(
            date=pd.Timestamp(d),
            o=g['o'].values.astype(np.float64), h=g['h'].values.astype(np.float64),
            l=g['l'].values.astype(np.float64), c=g['c'].values.astype(np.float64),
            v=g['v'].values.astype(np.float64), sod=sod.astype(np.int32),
            i930=int(i930),
        ))
    return days


def load_all_blocks_full():
    days = []
    for label, fn in BLOCOS:
        ds = load_days_full(fn)
        for d in ds:
            d['bloco'] = label
        days += ds
    days.sort(key=lambda d: d['date'])
    return days


# ---------------- gestao $ compartilhada (com fix de gap no stop) ----------------
SLIP = TICK * PV * QTY


def gerencia_dolar(o, h, l, c, sod, entry_i, entry, direction, alvo, stopd, traild, respiro):
    """Roda a partir de entry_i+1. Retorna (pnl_liquido, motivo)."""
    n = len(o)
    entry_sod = sod[entry_i]
    hwm = 0.0
    stop_lock = -stopd
    for i in range(entry_i + 1, n):
        if direction == 1:
            op_px, lo_px, hi_px = o[i], l[i], h[i]
        else:
            op_px, lo_px, hi_px = o[i], h[i], l[i]
        op_dollar = (op_px - entry) * direction * PV * QTY
        pnl_lo = (lo_px - entry) * direction * PV * QTY
        pnl_hi = (hi_px - entry) * direction * PV * QTY

        if pnl_lo <= stop_lock:
            fill = op_dollar if op_dollar < stop_lock else stop_lock - SLIP
            saida = max(fill, pnl_lo)
            motivo = 'STOP' if stop_lock < -1e-6 else ('BE' if stop_lock < traild else 'TRAIL')
            return saida - COMM * QTY, motivo
        if alvo > 0 and pnl_hi >= alvo:
            return alvo - COMM * QTY, 'ALVO'
        if pnl_hi > hwm:
            hwm = pnl_hi
        if (sod[i] - entry_sod) >= respiro and hwm > 0:
            cand = hwm - traild
            if cand > stop_lock:
                stop_lock = cand
    saida = (c[-1] - entry) * direction * PV * QTY
    return saida - COMM * QTY, 'FLATTEN'


def stats(net, motivos=None):
    if len(net) == 0:
        return None
    a = np.array(net)
    eq = np.cumsum(a)
    maxdd = -(eq - np.maximum.accumulate(eq)).min()
    streak = worst = 0.0
    for x in a:
        streak = streak + x if x < 0 else 0.0
        worst = min(worst, streak)
    return dict(n=len(a), wr=(a > 0).mean(), media=a.mean(), total=a.sum(),
                maxdd=maxdd, streak=worst)


def linha(tag, r):
    if r is None:
        return f"{tag:<55} sem trades"
    return (f"{tag:<55} n={r['n']:>4} wr={r['wr']:>4.0%} $/trade={r['media']:>+7.2f} "
            f"total={r['total']:>+8.0f} maxDD={r['maxdd']:>6.0f} streak={r['streak']:>+6.0f}")


# ================================================================== A) ORB
def ideia_A(days, range_min, gatilho_extra_ticks, janela_breakout_min, alvo, stopd, traild, respiro):
    net = []
    for d in days:
        o, h, l, c, sod = d['o'], d['h'], d['l'], d['c'], d['sod']
        i930 = d['i930']
        i_fim_range = np.searchsorted(sod, OPEN_SOD + range_min * 60)
        if i_fim_range <= i930 or i_fim_range >= len(sod):
            continue
        rng_hi = h[i930:i_fim_range].max()
        rng_lo = l[i930:i_fim_range].min()
        extra = gatilho_extra_ticks * TICK
        i_fim_janela = np.searchsorted(sod, OPEN_SOD + (range_min + janela_breakout_min) * 60)
        trig_i = -1
        direction = 0
        for i in range(i_fim_range, min(i_fim_janela, len(sod))):
            if c[i] >= rng_hi + extra:
                direction = 1
                trig_i = i
                break
            if c[i] <= rng_lo - extra:
                direction = -1
                trig_i = i
                break
        if trig_i < 0:
            continue
        entry = c[trig_i]
        pnl, _ = gerencia_dolar(o, h, l, c, sod, trig_i, entry, direction, alvo, stopd, traild, respiro)
        net.append(pnl)
    return stats(net)


# ================================================================== D) fada extremo
def ideia_D(days, gatilho_ticks, espera, alvo, stopd, traild, respiro):
    JANELA = 180
    net = []
    for d in days:
        o, h, l, c, sod = d['o'], d['h'], d['l'], d['c'], d['sod']
        i930 = d['i930']
        n = len(o)
        t0 = sod[i930]
        open_px = o[i930]
        trig_i = -1
        direction = 0
        for i in range(i930, n):
            decorrido = sod[i] - t0
            if decorrido < espera:
                continue
            if decorrido > espera + JANELA:
                break
            disp = c[i] - open_px
            if disp >= gatilho_ticks * TICK:
                direction = -1  # FADA
                trig_i = i
                break
            elif disp <= -gatilho_ticks * TICK:
                direction = 1
                trig_i = i
                break
        if trig_i < 0:
            continue
        entry = c[trig_i]
        pnl, _ = gerencia_dolar(o, h, l, c, sod, trig_i, entry, direction, alvo, stopd, traild, respiro)
        net.append(pnl)
    return stats(net)


# ================================================================== E) limite na retracao
def ideia_E(days, gatilho_ticks, retracao_ticks, timeout_s, alvo, stopd, traild, respiro):
    JANELA = 180
    net = []
    n_timeout = 0
    for d in days:
        o, h, l, c, sod = d['o'], d['h'], d['l'], d['c'], d['sod']
        i930 = d['i930']
        n = len(o)
        t0 = sod[i930]
        open_px = o[i930]
        trig_i = -1
        direction = 0
        for i in range(i930, n):
            if sod[i] - t0 > JANELA:
                break
            disp = c[i] - open_px
            if disp >= gatilho_ticks * TICK:
                direction = 1
                trig_i = i
                break
            elif disp <= -gatilho_ticks * TICK:
                direction = -1
                trig_i = i
                break
        if trig_i < 0:
            continue
        nivel_gatilho = c[trig_i]
        nivel_limite = nivel_gatilho - direction * retracao_ticks * TICK
        t_gatilho = sod[trig_i]
        entry_i = -1
        for i in range(trig_i + 1, n):
            if sod[i] - t_gatilho > timeout_s:
                break
            if direction == 1 and l[i] <= nivel_limite:
                entry_i = i
                break
            if direction == -1 and h[i] >= nivel_limite:
                entry_i = i
                break
        if entry_i < 0:
            n_timeout += 1
            continue
        entry = nivel_limite
        pnl, _ = gerencia_dolar(o, h, l, c, sod, entry_i, entry, direction, alvo, stopd, traild, respiro)
        net.append(pnl)
    r = stats(net)
    if r:
        r['timeouts'] = n_timeout
    return r


# ================================================================== F) rompe faixa do "dia anterior"
def ideia_F(days, gatilho_extra_ticks, janela_min, alvo, stopd, traild, respiro):
    net = []
    prev = None
    for d in days:
        o, h, l, c, sod = d['o'], d['h'], d['l'], d['c'], d['sod']
        i930 = d['i930']
        if prev is not None and (d['date'] - prev['date']).days <= 4:
            ph, pl = prev['h'][prev['i930']:], prev['l'][prev['i930']:]
            ref_hi, ref_lo = ph.max(), pl.min()
            extra = gatilho_extra_ticks * TICK
            i_fim = np.searchsorted(sod, OPEN_SOD + janela_min * 60)
            trig_i = -1
            direction = 0
            for i in range(i930, min(i_fim, len(sod))):
                if c[i] >= ref_hi + extra:
                    direction = 1
                    trig_i = i
                    break
                if c[i] <= ref_lo - extra:
                    direction = -1
                    trig_i = i
                    break
            if trig_i >= 0:
                entry = c[trig_i]
                pnl, _ = gerencia_dolar(o, h, l, c, sod, trig_i, entry, direction, alvo, stopd, traild, respiro)
                net.append(pnl)
        prev = d
    return stats(net)


# ================================================================== B/C) filtros
def premkt_range(d):
    o, h, l, sod = d['o'], d['h'], d['l'], d['sod']
    i0 = np.searchsorted(sod, PREMKT_SOD)
    i1 = d['i930']
    if i1 <= i0:
        return 0.0
    return (h[i0:i1].max() - l[i0:i1].min())


def vol_1o_min(d):
    v, sod = d['v'], d['sod']
    i0 = d['i930']
    i1 = np.searchsorted(sod, OPEN_SOD + 60)
    return v[i0:i1].sum()


def entrada_base(d, gatilho_ticks, espera):
    """mesma entrada 'espera+segue' do v7, devolve (trig_i, direction) ou (-1,0)."""
    JANELA = 180
    o, c, sod = d['o'], d['c'], d['sod']
    i930 = d['i930']
    n = len(o)
    t0 = sod[i930]
    open_px = o[i930]
    for i in range(i930, n):
        decorrido = sod[i] - t0
        if decorrido < espera:
            continue
        if decorrido > espera + JANELA:
            break
        disp = c[i] - open_px
        if disp >= gatilho_ticks * TICK:
            return i, 1
        if disp <= -gatilho_ticks * TICK:
            return i, -1
    return -1, 0


def ideia_BC(days, gatilho_ticks, espera, alvo, stopd, traild, respiro,
             usa_premkt_filtro, premkt_pct, usa_vol_filtro, vol_janela, vol_mult):
    """B: so opera se range pre-mercado >= percentil X (fixo, olhando os 352 dias
    inteiros — nao e 100% causal dia-a-dia, e um corte de regime pra ESTUDO, nao
    pra ir de producao direto). C: baseline movel causal (so dias passados)."""
    pm = np.array([premkt_range(d) for d in days])
    thr_pm = np.percentile(pm, premkt_pct) if usa_premkt_filtro else -1

    vols = [vol_1o_min(d) for d in days]

    net = []
    for idx, d in enumerate(days):
        if usa_premkt_filtro and pm[idx] < thr_pm:
            continue
        if usa_vol_filtro:
            hist = vols[max(0, idx - vol_janela):idx]
            if len(hist) < 5:
                continue
            baseline = np.median(hist)
            if baseline <= 0 or vols[idx] < baseline * vol_mult:
                continue
        trig_i, direction = entrada_base(d, gatilho_ticks, espera)
        if trig_i < 0:
            continue
        o, h, l, c, sod = d['o'], d['h'], d['l'], d['c'], d['sod']
        entry = c[trig_i]
        pnl, _ = gerencia_dolar(o, h, l, c, sod, trig_i, entry, direction, alvo, stopd, traild, respiro)
        net.append(pnl)
    return stats(net)


def main():
    print("carregando dados 1s full-day (2024/2025/2026ago)...")
    days = load_all_blocks_full()
    print(f"  {len(days)} pregoes\n")

    ALVO, STOPD, TRAILD, RESPIRO = 500, 250, 60, 20  # config-base pra isolar o efeito da ideia

    print("=" * 30, "A) OPENING RANGE BREAKOUT", "=" * 30)
    for range_min in (5, 15, 30):
        for extra in (0, 2, 4):
            r = ideia_A(days, range_min, extra, 60, ALVO, STOPD, TRAILD, RESPIRO)
            print(linha(f"range={range_min}min extra={extra}t janela=60min", r))
    print()

    print("=" * 30, "B) FILTRO RANGE PRE-MERCADO (proxy overnight)", "=" * 30)
    print(linha("SEM filtro (base: espera=10 gat=3)",
                 ideia_BC(days, 3, 10, ALVO, STOPD, TRAILD, RESPIRO, False, 0, False, 0, 0)))
    for pct in (50, 70, 85):
        r = ideia_BC(days, 3, 10, ALVO, STOPD, TRAILD, RESPIRO, True, pct, False, 0, 0)
        print(linha(f"so dias c/ range pre-mkt >= p{pct}", r))
    print()

    print("=" * 30, "C) FILTRO VOLUME 1o MINUTO (baseline movel causal)", "=" * 30)
    for mult in (1.0, 1.3, 1.6, 2.0):
        r = ideia_BC(days, 3, 10, ALVO, STOPD, TRAILD, RESPIRO, False, 0, True, 20, mult)
        print(linha(f"vol 1omin >= {mult}x mediana(20d passados)", r))
    print()

    print("=" * 30, "D) FADA SO EM MOVIMENTO EXTREMO", "=" * 30)
    for gat in (3, 6, 10, 15, 20, 25):
        r = ideia_D(days, gat, 0, ALVO, STOPD, TRAILD, RESPIRO)
        print(linha(f"gatilho fada={gat}t (espera=0)", r))
    print()

    print("=" * 30, "E) ENTRADA POR LIMITE NA RETRACAO", "=" * 30)
    for gat in (3, 5):
        for retr in (1, 2, 3, 4):
            r = ideia_E(days, gat, retr, 60, ALVO, STOPD, TRAILD, RESPIRO)
            if r:
                print(linha(f"gatilho={gat}t retracao={retr}t timeout=60s "
                             f"(timeouts={r.get('timeouts','?')})", r))
    print()

    print("=" * 30, "F) ROMPE FAIXA DO 'DIA ANTERIOR' (proxy Initial Balance)", "=" * 30)
    for extra in (0, 2, 4, 8):
        r = ideia_F(days, extra, 60, ALVO, STOPD, TRAILD, RESPIRO)
        print(linha(f"extra={extra}t janela=60min", r))


if __name__ == '__main__':
    main()
