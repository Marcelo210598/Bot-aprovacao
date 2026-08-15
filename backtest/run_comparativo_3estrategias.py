#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backtest comparativo das 3 estrategias novas (Initial Balance, VWAP Reversao,
Momentum Breakout ATR) — espelha a logica dos arquivos .cs em src/, rodado
no NQ 1min REAL (NQ_dados/, ~1 ano: jun/2025-jun/2026), agregado p/ 5min ET.

MNQ: $2/ponto (1 contrato), tick 0.25.

LICAO DO 23/06 (historico/2026-06-23.md): um backtest anterior rodou com
slippage ZERO e escondeu o ponto fraco real de uma estrategia (a noturna
so desabou sob atrito de 2 ticks). Por isso aqui SEMPRE roda 2 cenarios:
  - "sem atrito" (informativo, otimista demais p/ confiar)
  - "realista" (2 ticks de slippage por perna + comissao $1.20 RT/contrato,
    mesmo padrao usado em backtest/run_slippage_test.py)

CAVEAT: agregacao 1min->5min e simulacao por bar (High/Low, sem tick replay)
e uma APROXIMACAO do que o NT8 Strategy Analyzer faria de verdade. Serve p/
comparar as 3 entre si e descartar a pior antes de gastar tempo compilando
no NT8 — nao substitui o teste real no Strategy Analyzer.
"""
import glob
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')
UTC = timezone.utc
PASTA = os.path.join(os.path.dirname(__file__), '..', 'NQ_dados')

MNQ_PV = 2.0    # $/ponto por contrato MNQ
TICK = 0.25
COMISSAO_RT = 1.20   # $ por contrato/round-turn (mesmo valor usado em run_mnq.py)


# ============================================================ carregamento
def carregar_1min(pasta):
    vistos = {}
    for f in sorted(glob.glob(os.path.join(pasta, '*.txt'))):
        with open(f, encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    dtp, rest = line.split(';', 1)
                    data, hora = dtp.split()
                    o, h, l, c, v = rest.split(';')
                    dt = datetime(int(data[:4]), int(data[4:6]), int(data[6:8]),
                                  int(hora[:2]), int(hora[2:4]), tzinfo=UTC)
                    o, h, l, c, v = float(o), float(h), float(l), float(c), float(v)
                except Exception:
                    continue
                h = max(h, o, c)
                l = min(l, o, c)
                if dt not in vistos:
                    vistos[dt] = (dt.astimezone(ET), o, h, l, c, v)
    return [vistos[k] for k in sorted(vistos)]


def agrega_5min(bars1m):
    """Agrega 1min -> 5min. Rotulo do bucket = inicio do intervalo (ET)."""
    buckets = {}
    ordem = []
    for (dtet, o, h, l, c, v) in bars1m:
        floor_min = (dtet.minute // 5) * 5
        chave = dtet.replace(minute=floor_min, second=0, microsecond=0)
        if chave not in buckets:
            buckets[chave] = [o, h, l, c, v]
            ordem.append(chave)
        else:
            b = buckets[chave]
            b[1] = max(b[1], h)
            b[2] = min(b[2], l)
            b[3] = c
            b[4] += v
    ordem.sort()
    return [{'dt': k, 'o': buckets[k][0], 'h': buckets[k][1], 'l': buckets[k][2],
             'c': buckets[k][3], 'v': buckets[k][4]} for k in ordem]


def hhmm(dt):
    return dt.hour * 100 + dt.minute


# ============================================================ indicadores (Wilder)
class ATRCalc:
    def __init__(self, period):
        self.period = period
        self.prev_c = None
        self.buf = []
        self.atr = None

    def update(self, h, l, c):
        tr = (h - l) if self.prev_c is None else max(h - l, abs(h - self.prev_c), abs(l - self.prev_c))
        self.prev_c = c
        if self.atr is None:
            self.buf.append(tr)
            if len(self.buf) < self.period:
                return None
            self.atr = sum(self.buf) / self.period
        else:
            self.atr = (self.atr * (self.period - 1) + tr) / self.period
        return self.atr


class ADXCalc:
    def __init__(self, period):
        self.period = period
        self.prev_h = self.prev_l = self.prev_c = None
        self.trs, self.pdms, self.mdms, self.dxs = [], [], [], []
        self.tr_s = self.pdm_s = self.mdm_s = None
        self.adx = None

    def update(self, h, l, c):
        if self.prev_h is None:
            self.prev_h, self.prev_l, self.prev_c = h, l, c
            return None
        up, down = h - self.prev_h, self.prev_l - l
        pdm = up if (up > down and up > 0) else 0.0
        mdm = down if (down > up and down > 0) else 0.0
        tr = max(h - l, abs(h - self.prev_c), abs(l - self.prev_c))
        self.prev_h, self.prev_l, self.prev_c = h, l, c

        if self.tr_s is None:
            self.trs.append(tr); self.pdms.append(pdm); self.mdms.append(mdm)
            if len(self.trs) < self.period:
                return None
            self.tr_s, self.pdm_s, self.mdm_s = sum(self.trs), sum(self.pdms), sum(self.mdms)
        else:
            self.tr_s = self.tr_s - self.tr_s / self.period + tr
            self.pdm_s = self.pdm_s - self.pdm_s / self.period + pdm
            self.mdm_s = self.mdm_s - self.mdm_s / self.period + mdm

        if self.tr_s == 0:
            return self.adx
        pdi = 100 * self.pdm_s / self.tr_s
        mdi = 100 * self.mdm_s / self.tr_s
        denom = pdi + mdi
        dx = 0.0 if denom == 0 else 100 * abs(pdi - mdi) / denom

        if self.adx is None:
            self.dxs.append(dx)
            if len(self.dxs) < self.period:
                return None
            self.adx = sum(self.dxs) / self.period
        else:
            self.adx = (self.adx * (self.period - 1) + dx) / self.period
        return self.adx


# ============================================================ util comum de trade
def registra_saida(trades, entry_dt, exit_dt, direcao, entry_px, exit_px, slip_pts, comissao):
    """direcao: +1 long, -1 short. Aplica slippage adverso em entrada e saida."""
    entry_fill = entry_px + slip_pts * direcao
    exit_fill = exit_px - slip_pts * direcao
    pnl = (exit_fill - entry_fill) * direcao * MNQ_PV - comissao
    trades.append({'entry_dt': entry_dt, 'exit_dt': exit_dt, 'dir': direcao,
                    'entry': entry_fill, 'exit': exit_fill, 'pnl': pnl})


def metricas(trades, meses):
    if not trades:
        return dict(n=0, win_rate=0, pf=0, net=0, max_dd=0, trades_mes=0)
    n = len(trades)
    ganhos = [t['pnl'] for t in trades if t['pnl'] > 0]
    perdas = [t['pnl'] for t in trades if t['pnl'] <= 0]
    win_rate = 100 * len(ganhos) / n
    soma_g = sum(ganhos)
    soma_p = -sum(perdas)
    pf = (soma_g / soma_p) if soma_p > 0 else (float('inf') if soma_g > 0 else 0)
    net = sum(t['pnl'] for t in trades)
    eq = 0.0
    pico = 0.0
    max_dd = 0.0
    for t in trades:
        eq += t['pnl']
        pico = max(pico, eq)
        max_dd = min(max_dd, eq - pico)
    return dict(n=n, win_rate=win_rate, pf=pf, net=net, max_dd=max_dd, trades_mes=n / meses if meses else 0)


# ============================================================ ESTRATEGIA 1 — Initial Balance
def bt_ib(bars, slip_ticks=0, comissao=0.0,
          h_inicio=930, ib_fim=1030, entrada_fim=1500, flatten=1550,
          tol_reteste=3.0, alvo_ext_ib=1.0, stop_buffer=1.0,
          stop_diario=-300.0, max_trades_dia=3):
    slip = slip_ticks * TICK
    trades = []
    dia = None
    ib_high = ib_low = 0.0
    ib_fechado = False
    fase = 0          # 0 formando IB | 1 pronto aguardando rompimento | 2 rompeu alta | 3 rompeu baixa
    retestou = False
    pos = 0
    entry_dt = entry_px = stop_px = tgt_px = 0.0
    pnl_inicio_dia = 0.0
    bloqueado = False
    trades_hoje = 0
    realizado = 0.0

    for b in bars:
        dt, o, h, l, c = b['dt'], b['o'], b['h'], b['l'], b['c']
        m = hhmm(dt)
        d = dt.strftime('%Y-%m-%d')

        if d != dia:
            dia = d
            ib_high = ib_low = 0.0
            ib_fechado = False
            fase = 0
            retestou = False
            pnl_inicio_dia = realizado
            bloqueado = False
            trades_hoje = 0

        # flatten forcado
        if m >= flatten:
            if pos != 0:
                registra_saida(trades, entry_dt, dt, pos, entry_px, c, slip, comissao)
                realizado += trades[-1]['pnl']
                pos = 0
            continue

        pnl_dia = realizado - pnl_inicio_dia
        if not bloqueado and stop_diario < 0 and pnl_dia <= stop_diario:
            bloqueado = True

        if h_inicio <= m < ib_fim:
            ib_high = h if ib_high == 0 else max(ib_high, h)
            ib_low = l if ib_low == 0 else min(ib_low, l)
            continue

        if m >= ib_fim and not ib_fechado and ib_high > 0:
            ib_fechado = True
            fase = 1

        if not ib_fechado:
            continue

        # gestao de posicao aberta
        if pos != 0:
            if pos > 0:
                if l <= stop_px:
                    registra_saida(trades, entry_dt, dt, pos, entry_px, stop_px, slip, comissao)
                    realizado += trades[-1]['pnl']; pos = 0
                elif h >= tgt_px:
                    registra_saida(trades, entry_dt, dt, pos, entry_px, tgt_px, slip, comissao)
                    realizado += trades[-1]['pnl']; pos = 0
            else:
                if h >= stop_px:
                    registra_saida(trades, entry_dt, dt, pos, entry_px, stop_px, slip, comissao)
                    realizado += trades[-1]['pnl']; pos = 0
                elif l <= tgt_px:
                    registra_saida(trades, entry_dt, dt, pos, entry_px, tgt_px, slip, comissao)
                    realizado += trades[-1]['pnl']; pos = 0
            continue

        pode_entrar = (not bloqueado) and (ib_fim <= m < entrada_fim) and \
                      (max_trades_dia <= 0 or trades_hoje < max_trades_dia)

        if fase == 1:
            if c > ib_high:
                fase = 2; retestou = False
            elif c < ib_low:
                fase = 3; retestou = False
            continue

        if fase == 2:
            if c < ib_low:
                fase = 1; retestou = False
                continue
            if not retestou and l <= ib_high + tol_reteste:
                retestou = True
            if retestou and pode_entrar and c > o and c > ib_high:
                ib_range = ib_high - ib_low
                stop_px = ib_low - stop_buffer
                tgt_px = ib_high + alvo_ext_ib * ib_range
                entry_dt, entry_px, pos = dt, c, 1
                trades_hoje += 1
                fase = 1; retestou = False
            continue

        if fase == 3:
            if c > ib_high:
                fase = 1; retestou = False
                continue
            if not retestou and h >= ib_low - tol_reteste:
                retestou = True
            if retestou and pode_entrar and c < o and c < ib_low:
                ib_range = ib_high - ib_low
                stop_px = ib_high + stop_buffer
                tgt_px = ib_low - alvo_ext_ib * ib_range
                entry_dt, entry_px, pos = dt, c, -1
                trades_hoje += 1
                fase = 1; retestou = False
            continue

    return trades


# ============================================================ ESTRATEGIA 2 — VWAP Reversao
def bt_vwap(bars, slip_ticks=0, comissao=0.0,
            desv_entrada=2.0, desv_stop=2.5, adx_periodo=14, adx_desativa=30.0,
            h_inicio=930, entrada_fim=1500, flatten=1550,
            stop_diario=-300.0, max_trades_dia=3):
    slip = slip_ticks * TICK
    trades = []
    dia = None
    soma_pv = soma_pv2 = soma_v = 0.0
    aguarda_short = aguarda_long = False
    vwap_sinal = stop_sinal = 0.0
    pos = 0
    entry_dt = entry_px = stop_px = tgt_px = 0.0
    pnl_inicio_dia = 0.0
    bloqueado = False
    trades_hoje = 0
    realizado = 0.0
    adx = ADXCalc(adx_periodo)
    prev_c = None

    for b in bars:
        dt, o, h, l, c = b['dt'], b['o'], b['h'], b['l'], b['c']
        m = hhmm(dt)
        d = dt.strftime('%Y-%m-%d')
        adx_val = adx.update(h, l, c)

        if d != dia:
            dia = d
            soma_pv = soma_pv2 = soma_v = 0.0
            aguarda_short = aguarda_long = False
            pnl_inicio_dia = realizado
            bloqueado = False
            trades_hoje = 0

        if m >= flatten:
            if pos != 0:
                registra_saida(trades, entry_dt, dt, pos, entry_px, c, slip, comissao)
                realizado += trades[-1]['pnl']; pos = 0
            prev_c = c
            continue

        pnl_dia = realizado - pnl_inicio_dia
        if not bloqueado and stop_diario < 0 and pnl_dia <= stop_diario:
            bloqueado = True

        if m < h_inicio:
            prev_c = c
            continue

        vol = b['v'] if b['v'] > 0 else 1.0
        tp = (h + l + c) / 3.0
        soma_pv += tp * vol
        soma_pv2 += tp * tp * vol
        soma_v += vol
        if soma_v <= 0:
            prev_c = c
            continue
        vwap = soma_pv / soma_v
        var = (soma_pv2 / soma_v) - vwap * vwap
        stdev = var ** 0.5 if var > 0 else 0.0
        banda_sup2 = vwap + desv_entrada * stdev
        banda_inf2 = vwap - desv_entrada * stdev
        stop_sup = vwap + desv_stop * stdev
        stop_inf = vwap - desv_stop * stdev

        if pos != 0:
            if pos > 0:
                if l <= stop_px:
                    registra_saida(trades, entry_dt, dt, pos, entry_px, stop_px, slip, comissao)
                    realizado += trades[-1]['pnl']; pos = 0
                elif h >= tgt_px:
                    registra_saida(trades, entry_dt, dt, pos, entry_px, tgt_px, slip, comissao)
                    realizado += trades[-1]['pnl']; pos = 0
            else:
                if h >= stop_px:
                    registra_saida(trades, entry_dt, dt, pos, entry_px, stop_px, slip, comissao)
                    realizado += trades[-1]['pnl']; pos = 0
                elif l <= tgt_px:
                    registra_saida(trades, entry_dt, dt, pos, entry_px, tgt_px, slip, comissao)
                    realizado += trades[-1]['pnl']; pos = 0
            aguarda_short = aguarda_long = False
            prev_c = c
            continue

        filtro_adx = adx_val is None or adx_desativa <= 0 or adx_val <= adx_desativa
        pode_entrar = (not bloqueado) and filtro_adx and (h_inicio <= m < entrada_fim) and \
                      (max_trades_dia <= 0 or trades_hoje < max_trades_dia)

        if aguarda_short:
            aguarda_short = False
            if pode_entrar and prev_c is not None and c < o and c < prev_c:
                stop_px, tgt_px = stop_sinal, vwap_sinal
                entry_dt, entry_px, pos = dt, c, -1
                trades_hoje += 1
                prev_c = c
                continue
        if aguarda_long:
            aguarda_long = False
            if pode_entrar and prev_c is not None and c > o and c > prev_c:
                stop_px, tgt_px = stop_sinal, vwap_sinal
                entry_dt, entry_px, pos = dt, c, 1
                trades_hoje += 1
                prev_c = c
                continue

        if pode_entrar:
            rejeitou_topo = h >= banda_sup2 and c < banda_sup2
            rejeitou_fundo = l <= banda_inf2 and c > banda_inf2
            if rejeitou_topo:
                aguarda_short = True
                vwap_sinal, stop_sinal = vwap, stop_sup
            elif rejeitou_fundo:
                aguarda_long = True
                vwap_sinal, stop_sinal = vwap, stop_inf

        prev_c = c

    return trades


# ============================================================ ESTRATEGIA 3 — Momentum Breakout ATR
def bt_momentum(bars, slip_ticks=0, comissao=0.0,
                 atr_periodo=14, atr_limiar=12.0, barras_consol=3,
                 alvo_atr=2.0, stop_atr=0.5,
                 h_inicio=930, minutos_sem_operar=5, entrada_fim=1500, flatten=1550,
                 stop_diario=-300.0, max_trades_dia=3):
    slip = slip_ticks * TICK
    trades = []
    dia = None
    consol_barras = 0
    consol_high = consol_low = 0.0
    pos = 0
    entry_dt = entry_px = stop_px = tgt_px = 0.0
    pnl_inicio_dia = 0.0
    bloqueado = False
    trades_hoje = 0
    realizado = 0.0
    atr_calc = ATRCalc(atr_periodo)
    inicio_liberado = ((h_inicio // 100) * 60 + (h_inicio % 100) + minutos_sem_operar)
    inicio_liberado = (inicio_liberado // 60) * 100 + (inicio_liberado % 60)
    atr_amostras = []

    for b in bars:
        dt, o, h, l, c = b['dt'], b['o'], b['h'], b['l'], b['c']
        m = hhmm(dt)
        d = dt.strftime('%Y-%m-%d')
        atr_val = atr_calc.update(h, l, c)
        if atr_val is not None:
            atr_amostras.append(atr_val)

        if d != dia:
            dia = d
            consol_barras = 0
            consol_high = consol_low = 0.0
            pnl_inicio_dia = realizado
            bloqueado = False
            trades_hoje = 0

        if m >= flatten:
            if pos != 0:
                registra_saida(trades, entry_dt, dt, pos, entry_px, c, slip, comissao)
                realizado += trades[-1]['pnl']; pos = 0
            continue

        pnl_dia = realizado - pnl_inicio_dia
        if not bloqueado and stop_diario < 0 and pnl_dia <= stop_diario:
            bloqueado = True

        if atr_val is None:
            continue

        if pos != 0:
            if pos > 0:
                if l <= stop_px:
                    registra_saida(trades, entry_dt, dt, pos, entry_px, stop_px, slip, comissao)
                    realizado += trades[-1]['pnl']; pos = 0
                elif h >= tgt_px:
                    registra_saida(trades, entry_dt, dt, pos, entry_px, tgt_px, slip, comissao)
                    realizado += trades[-1]['pnl']; pos = 0
            else:
                if h >= stop_px:
                    registra_saida(trades, entry_dt, dt, pos, entry_px, stop_px, slip, comissao)
                    realizado += trades[-1]['pnl']; pos = 0
                elif l <= tgt_px:
                    registra_saida(trades, entry_dt, dt, pos, entry_px, tgt_px, slip, comissao)
                    realizado += trades[-1]['pnl']; pos = 0
            continue

        janela_aberta = h_inicio <= m < entrada_fim
        pode_entrar = (not bloqueado) and janela_aberta and (m >= inicio_liberado) and \
                      (max_trades_dia <= 0 or trades_hoje < max_trades_dia)

        entrou = False
        if pode_entrar and consol_barras >= barras_consol and atr_val >= atr_limiar:
            if c > consol_high:
                stop_px = c - stop_atr * atr_val
                tgt_px = c + alvo_atr * atr_val
                entry_dt, entry_px, pos = dt, c, 1
                trades_hoje += 1
                consol_barras = 0; consol_high = consol_low = 0.0
                entrou = True
            elif c < consol_low:
                stop_px = c + stop_atr * atr_val
                tgt_px = c - alvo_atr * atr_val
                entry_dt, entry_px, pos = dt, c, -1
                trades_hoje += 1
                consol_barras = 0; consol_high = consol_low = 0.0
                entrou = True

        if not entrou:
            if atr_val < atr_limiar:
                if consol_barras == 0:
                    consol_high, consol_low = h, l
                else:
                    consol_high, consol_low = max(consol_high, h), min(consol_low, l)
                consol_barras += 1
            else:
                consol_barras = 0
                consol_high = consol_low = 0.0

    return trades, atr_amostras


# ============================================================ main
def main():
    print("Carregando NQ_dados/ (1min)...")
    b1 = carregar_1min(PASTA)
    print(f"  {len(b1):,} barras de 1min carregadas.")
    bars = agrega_5min(b1)
    print(f"  {len(bars):,} barras de 5min apos agregacao.")
    dt_ini, dt_fim = bars[0]['dt'], bars[-1]['dt']
    dias_totais = (dt_fim.date() - dt_ini.date()).days
    meses = max(dias_totais / 30.4, 0.1)
    print(f"  Periodo: {dt_ini.date()} -> {dt_fim.date()}  (~{meses:.1f} meses)\n")

    cenarios = [("SEM atrito (informativo)", 0, 0.0),
                ("REALISTA (2 ticks + comissao $1.20)", 2, COMISSAO_RT)]

    resultados = {}

    for nome_cen, slip_ticks, comissao in cenarios:
        print(f"\n{'='*78}\nCENARIO: {nome_cen}\n{'='*78}")

        t1 = bt_ib(bars, slip_ticks, comissao)
        m1 = metricas(t1, meses)

        t2 = bt_vwap(bars, slip_ticks, comissao)
        m2 = metricas(t2, meses)

        t3, atr_amostras = bt_momentum(bars, slip_ticks, comissao)
        m3 = metricas(t3, meses)

        linha = "{:<28}{:>8}{:>10}{:>10}{:>14}{:>14}{:>12}"
        print(linha.format("Estrategia", "Trades", "Win%", "PF", "Net $", "MaxDD $", "Trades/mes"))
        for nome, m in [("1. Initial Balance", m1), ("2. VWAP Reversao", m2), ("3. Momentum ATR", m3)]:
            pf_str = "inf" if m['pf'] == float('inf') else f"{m['pf']:.2f}"
            print(linha.format(nome, m['n'], f"{m['win_rate']:.1f}", pf_str,
                                f"{m['net']:.2f}", f"{m['max_dd']:.2f}", f"{m['trades_mes']:.1f}"))

        resultados[nome_cen] = {'ib': m1, 'vwap': m2, 'momentum': m3}

    if atr_amostras:
        atr_amostras.sort()
        n = len(atr_amostras)
        p50 = atr_amostras[n // 2]
        p25 = atr_amostras[n // 4]
        p75 = atr_amostras[3 * n // 4]
        print(f"\n\nATR(14) real no MNQ 5min (p/ calibrar 'Limiar consolidacao' da Estrategia 3):")
        print(f"  p25={p25:.2f}pt  mediana={p50:.2f}pt  p75={p75:.2f}pt  "
              f"(limiar padrao no .cs = 12.0pt)")

    return resultados


if __name__ == '__main__':
    main()
