#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compara a estrategia ATUAL de producao (BotAprovacao.cs — reversao na max/min
do dia anterior, config live: TP60/SL12,5/BE3,75-2,5/trail1,75/tol20t/maxDist15pt)
contra a estrategia MENOS PIOR do backtest comparativo (Initial Balance), no
MESMO dado real (NQ_dados/, ~1 ano) e MESMA convencao de custo (2 ticks slippage
+ $1,20 comissao RT/contrato — licao do 23/06, ver historico/2026-06-23.md).

Fidelidade: a atual roda em barras de 1min (timeframe REAL de producao, gestao
espelhada de GerenciaPosicao() no .cs — alvo checado ANTES do stop, igual ao
codigo real). A IB roda em 5min (seu timeframe de design). Cada uma no seu
timeframe real — nao forcei as duas pro mesmo grid.

Normalizado em 1 MNQ p/ comparar com a IB (que tambem default 1 contrato).
A atual em producao roda em 5 MNQ: multiplique Net$/MaxDD por 5 p/ ver a
escala real (WR/PF/trades nao mudam com o tamanho da posicao).
"""
import sys
import os
from datetime import timedelta

sys.path.insert(0, os.path.dirname(__file__))
from run_comparativo_3estrategias import (carregar_1min, agrega_5min, bt_ib, metricas,
                                           registra_saida, hhmm, PASTA, MNQ_PV, TICK, COMISSAO_RT)


def bt_atual(bars1m, slip_ticks=0, comissao=0.0,
             stop_pts=12.5, alvo_pts=60.0, be_trig=3.75, be_lock=2.5, trail=1.75,
             tol_ticks=20, max_dist=15.0,
             sessao_inicio=930, entrada_fim=1600, flatten_hora=1655,
             stop_diario=150.0, max_trades_dia=12, seg_usa_domingo=True, dom_noite_inicio=1800):
    """Espelha EntradaNiveis() + GerenciaPosicao() do src/BotAprovacao.cs, 1 contrato."""
    slip = slip_ticks * TICK
    tol = tol_ticks * TICK
    trades = []

    dia = None
    pd_high = pd_low = None
    cur_high = cur_low = None
    on_high = on_low = None
    on_key = None

    pos = 0
    gerenciando = False
    entry_dt = entry_price = stop_price = alvo_price = fav = 0.0
    be_feito = False

    pnl_inicio_dia = 0.0
    bloqueado = False
    trades_hoje = 0
    realizado = 0.0

    for b in bars1m:
        dt, o, h, l, c = b['dt'], b['o'], b['h'], b['l'], b['c']
        m = hhmm(dt)
        d = dt.strftime('%Y-%m-%d')
        dow = dt.weekday()   # Monday=0 ... Sunday=6

        if d != dia:
            if cur_high is not None:
                pd_high, pd_low = cur_high, cur_low
            dia = d
            cur_high = cur_low = None
            pnl_inicio_dia = realizado
            bloqueado = False
            trades_hoje = 0

        sess = 930 <= m < 1600
        if sess:
            cur_high = h if cur_high is None else max(cur_high, h)
            cur_low = l if cur_low is None else min(cur_low, l)

        if seg_usa_domingo:
            chave_seg = None
            if dow == 6 and m >= dom_noite_inicio:
                chave_seg = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
            elif dow == 0 and m < sessao_inicio:
                chave_seg = d
            if chave_seg is not None:
                if chave_seg != on_key:
                    on_key, on_high, on_low = chave_seg, h, l
                else:
                    on_high, on_low = max(on_high, h), min(on_low, l)

        # ---------------- gestao da posicao aberta (espelha GerenciaPosicao) ----------------
        if pos != 0:
            is_long = pos > 0
            if not gerenciando:
                entry_price = entry_px_tmp
                fav = entry_price
                be_feito = False
                stop_price = entry_price - stop_pts if is_long else entry_price + stop_pts
                alvo_price = entry_price + alvo_pts if is_long else entry_price - alvo_pts
                gerenciando = True

            saiu = False
            if is_long:
                if h >= alvo_price:
                    registra_saida(trades, entry_dt, dt, pos, entry_price, alvo_price, slip, comissao)
                    saiu = True
                elif l <= stop_price:
                    registra_saida(trades, entry_dt, dt, pos, entry_price, stop_price, slip, comissao)
                    saiu = True
            else:
                if l <= alvo_price:
                    registra_saida(trades, entry_dt, dt, pos, entry_price, alvo_price, slip, comissao)
                    saiu = True
                elif h >= stop_price:
                    registra_saida(trades, entry_dt, dt, pos, entry_price, stop_price, slip, comissao)
                    saiu = True

            if saiu:
                realizado += trades[-1]['pnl']
                pos = 0
                gerenciando = False
                continue

            if is_long:
                fav = max(fav, h)
                if not be_feito and (fav - entry_price) >= be_trig:
                    be_feito = True
                if be_feito:
                    stop_price = max(stop_price, max(entry_price + be_lock, fav - trail))
            else:
                fav = min(fav, l)
                if not be_feito and (entry_price - fav) >= be_trig:
                    be_feito = True
                if be_feito:
                    stop_price = min(stop_price, min(entry_price - be_lock, fav + trail))
            continue

        # ---------------- kill switch diario (roda mesmo sem posicao) ----------------
        pnl_dia = realizado - pnl_inicio_dia
        if not bloqueado and stop_diario > 0 and pnl_dia <= -stop_diario:
            bloqueado = True

        # ---------------- flatten forcado ----------------
        if m >= flatten_hora:
            continue

        # ---------------- entrada ----------------
        if bloqueado or not (sessao_inicio <= m < entrada_fim) or \
           (max_trades_dia > 0 and trades_hoje >= max_trades_dia):
            continue

        usa_dom = seg_usa_domingo and dow == 0 and on_key == d and on_high is not None and on_high > 0
        n_hi = on_high if usa_dom else pd_high
        n_lo = on_low if usa_dom else pd_low
        if not n_hi or not n_lo or n_hi <= 0 or n_lo <= 0:
            continue

        if h >= n_hi - tol:
            if c < n_hi:
                dist = n_hi - c
                if max_dist <= 0 or dist <= max_dist:
                    entry_px_tmp, pos, entry_dt = c, -1, dt
                    trades_hoje += 1
                    gerenciando = False
        elif l <= n_lo + tol:
            if c > n_lo:
                dist = c - n_lo
                if max_dist <= 0 or dist <= max_dist:
                    entry_px_tmp, pos, entry_dt = c, 1, dt
                    trades_hoje += 1
                    gerenciando = False

    return trades


def main():
    print("Carregando NQ_dados/ (1min)...")
    bars1m_raw = carregar_1min(PASTA)
    bars1m = [{'dt': dtet, 'o': o, 'h': h, 'l': l, 'c': c, 'v': v} for (dtet, o, h, l, c, v) in bars1m_raw]
    bars5m = agrega_5min(bars1m_raw)
    dt_ini, dt_fim = bars1m[0]['dt'], bars1m[-1]['dt']
    dias_totais = (dt_fim.date() - dt_ini.date()).days
    meses = max(dias_totais / 30.4, 0.1)
    print(f"  Periodo: {dt_ini.date()} -> {dt_fim.date()}  (~{meses:.1f} meses)\n")

    cenarios = [("SEM atrito (informativo)", 0, 0.0),
                ("REALISTA (2 ticks + comissao $1,20)", 2, COMISSAO_RT)]

    linha = "{:<32}{:>8}{:>10}{:>10}{:>14}{:>14}{:>12}"
    for nome_cen, slip_ticks, comissao in cenarios:
        print(f"\n{'='*90}\nCENARIO: {nome_cen}  (1 MNQ)\n{'='*90}")
        t_atual = bt_atual(bars1m, slip_ticks, comissao)
        m_atual = metricas(t_atual, meses)
        t_ib = bt_ib(bars5m, slip_ticks, comissao)
        m_ib = metricas(t_ib, meses)

        print(linha.format("Estrategia", "Trades", "Win%", "PF", "Net $", "MaxDD $", "Trades/mes"))
        for nome, m in [("ATUAL (BotAprovacao, 1min)", m_atual), ("Initial Balance (5min)", m_ib)]:
            pf_str = "inf" if m['pf'] == float('inf') else f"{m['pf']:.2f}"
            print(linha.format(nome, m['n'], f"{m['win_rate']:.1f}", pf_str,
                                f"{m['net']:.2f}", f"{m['max_dd']:.2f}", f"{m['trades_mes']:.1f}"))

        if nome_cen.startswith("REALISTA"):
            print(f"\n  Em producao (5 MNQ): ATUAL Net ~${m_atual['net']*5:,.0f} | "
                  f"MaxDD ~${m_atual['max_dd']*5:,.0f}  (WR/PF/trades nao mudam com o sizing)")

    # ---- robustez OOS (1a vs 2a metade) no cenario realista ----
    print(f"\n\n{'='*90}\nROBUSTEZ OOS — 1a metade vs 2a metade (cenario realista)\n{'='*90}")
    meio_1m = bars1m[len(bars1m)//2]['dt']
    meio_5m_idx = len(bars5m)//2
    meio_5m = bars5m[meio_5m_idx]['dt']

    b1m_1, b1m_2 = [b for b in bars1m if b['dt'] < meio_1m], [b for b in bars1m if b['dt'] >= meio_1m]
    b5m_1, b5m_2 = [b for b in bars5m if b['dt'] < meio_5m], [b for b in bars5m if b['dt'] >= meio_5m]

    for nome, fn, dados_1, dados_2 in [("ATUAL", bt_atual, b1m_1, b1m_2), ("Initial Balance", bt_ib, b5m_1, b5m_2)]:
        t1 = fn(dados_1, 2, COMISSAO_RT)
        t2 = fn(dados_2, 2, COMISSAO_RT)
        m1, m2 = metricas(t1, meses/2), metricas(t2, meses/2)
        pf1 = "inf" if m1['pf'] == float('inf') else f"{m1['pf']:.2f}"
        pf2 = "inf" if m2['pf'] == float('inf') else f"{m2['pf']:.2f}"
        print(f"  {nome:<20} 1a metade: n={m1['n']:>4} WR={m1['win_rate']:>5.1f}% PF={pf1:>5} net=${m1['net']:>9,.2f}  |  "
              f"2a metade: n={m2['n']:>4} WR={m2['win_rate']:>5.1f}% PF={pf2:>5} net=${m2['net']:>9,.2f}")


if __name__ == '__main__':
    main()
