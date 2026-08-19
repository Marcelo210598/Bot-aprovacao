#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SENSIBILIDADE DO GATILHO DE BREAKEVEN (18/08/2026)

Pergunta do Marcelo: atrasar o gatilho de breakeven (hoje +3,75pt -> trava +2,5pt)
aumenta o ganho medio por trade sem destruir o WR? Tudo o resto fica igual a
producao: SL 12,5pt, trailing 1,75pt (distancia), MaxDistPontos 15pt, tolerancia
de toque 20 ticks (5pt), TP 60pt, stop diario $750.

⚠️ AVISO DE DADOS: NQ_dados/ so cobre 2025-06-11 a 2026-06-11 -- "junho completo"
de 2026 nao existe localmente (so 01-11/06, ~8 dias uteis). Rodamos em duas vistas:
  (A) ANO INTEIRO disponivel -- amostra robusta, mesma base dos backtests
      ja validados do projeto (backtest/run_proximity_filter.py etc).
  (B) SO o pedaco de junho/2026 que existe -- so como conferencia, amostra pequena,
      NAO usar sozinho pra decidir nada (regra do projeto: achado de 1 mes curto
      nao vira regra sem confirmar no dado longo).

Usa src/BotAprovacao.cs como referencia de logica (entrada = mesmo motor de
backtest/diagnostico_portoes.py, ja corrigido/validado em 18/08).
"""
import sys
import os
import csv
from datetime import timedelta

sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp  # reaproveita carregar_1min, resample_5min, avalia_bar

# ===================== CONFIG FIXA (producao, exceto o gatilho de BE) =====================
TICK = dp.TICK
TOL_TICKS = 20          # 5pt
MAX_DIST = 15.0
PTS_SL = 12.5
PTS_TP = 60.0
PTS_BE_LOCK = 2.5        # fixo, so o GATILHO varia
PTS_TRAIL = 1.75         # fixo (distancia do trailing), so o GATILHO varia
STOP_DIA_PT = 750.0 / (2.0 * 5)   # $750 / (MNQ_PV=2 * 5 contratos) = 75pt
MAX_TRADES_DIA = 12
MNQ_PV = 2.0
N_CONTR = 5
RT_PER_TRADE = 1.20 * N_CONTR   # custo round-trip ($)

GATILHOS = [3.75, 5.0, 6.0, 7.0, 8.0, 10.0, 12.0]   # 3.75 = baseline (producao)

ANO_INICIO, ANO_FIM = '2025-06-11', '2026-06-11'   # tudo que existe localmente
JUN_INICIO, JUN_FIM = '2026-06-01', '2026-06-11'   # pedaco de junho/2026 disponivel


def simula(bars5m, pts_be_trig, data_ini, data_fim, slip_pts=0.0):
    """Backtest bar a bar (5min), motor identico ao ja usado no projeto, so que
    aqui registra o MOTIVO da saida (TP / BE_TRAIL / SL) pra cada trade.
    slip_pts: slippage APLICADO CONTRA o trader em toda entrada e saida (padrao
    do projeto: 2 ticks = 0.5pt -> ver docs/melhorias-sugeridas.md)."""
    tol_pts = TOL_TICKS * TICK
    pv = MNQ_PV * N_CONTR

    cur_hi = cur_lo = None
    pd_hi = pd_lo = None
    dia = None
    on_key = None
    on_hi = on_lo = None

    pos = 0; entry = stop = alvo = fav = 0.0; be_feito = False
    dia_k = None; pnl_dia0 = 0.0; realizado = 0.0; bloqueado_hoje = False
    trades = []   # lista de dicts: {'pnl_pts':, 'pnl_usd':, 'motivo':, 'data':}

    def fecha(preco, motivo, dt_str):
        nonlocal pos, realizado
        preco_real = preco - slip_pts if pos > 0 else preco + slip_pts  # pior pro trader
        pts = (preco_real - entry) if pos > 0 else (entry - preco_real)
        usd = pts * pv - RT_PER_TRADE
        realizado += usd
        trades.append({'pnl_pts': pts, 'pnl_usd': usd, 'motivo': motivo, 'data': dt_str})
        pos = 0

    for b in bars5m:
        dt = b['dt']; d = dt.strftime('%Y-%m-%d'); m = dp.mins(dt); dow = dt.weekday()
        em_sessao = dp.SESSAO_INICIO <= m < dp.ENTRADA_FIM

        if d != dia:
            if cur_hi is not None:
                pd_hi, pd_lo = cur_hi, cur_lo
            dia = d
            cur_hi = b['h'] if em_sessao else None
            cur_lo = b['l'] if em_sessao else None
            bloqueado_hoje = False
            pnl_dia0 = realizado
        elif em_sessao:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])

        chave_seg = None
        if dow == 6 and m >= dp.DOM_NOITE_INICIO:
            chave_seg = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
        elif dow == 0 and m < dp.SESSAO_INICIO:
            chave_seg = d
        if chave_seg is not None:
            if chave_seg != on_key:
                on_key, on_hi, on_lo = chave_seg, b['h'], b['l']
            else:
                on_hi = max(on_hi, b['h']); on_lo = min(on_lo, b['l'])

        if not (data_ini <= d <= data_fim):
            continue

        # ---- gestao de posicao aberta ----
        if pos != 0:
            saiu = False
            if pos > 0:
                if b['l'] <= stop:
                    fecha(stop, 'BE_TRAIL' if be_feito else 'SL', d); saiu = True
                elif b['h'] >= alvo:
                    fecha(alvo, 'TP', d); saiu = True
            else:
                if b['h'] >= stop:
                    fecha(stop, 'BE_TRAIL' if be_feito else 'SL', d); saiu = True
                elif b['l'] <= alvo:
                    fecha(alvo, 'TP', d); saiu = True
            if not saiu:
                if pos > 0:
                    fav = max(fav, b['h'])
                    if not be_feito and (fav - entry) >= pts_be_trig:
                        stop = max(stop, entry + PTS_BE_LOCK); be_feito = True
                    if be_feito:
                        stop = max(stop, fav - PTS_TRAIL)
                else:
                    fav = min(fav, b['l'])
                    if not be_feito and (entry - fav) >= pts_be_trig:
                        stop = min(stop, entry - PTS_BE_LOCK); be_feito = True
                    if be_feito:
                        stop = min(stop, fav + PTS_TRAIL)
            else:
                if STOP_DIA_PT > 0 and (realizado - pnl_dia0) <= -STOP_DIA_PT * pv:
                    bloqueado_hoje = True
            continue

        if d != dia_k:
            dia_k = d
        if bloqueado_hoje or not (dp.SESSAO_INICIO <= m < dp.ENTRADA_FIM):
            continue
        if pd_hi is None or pd_lo is None:
            continue
        trades_hoje = sum(1 for t in trades if t['data'] == d)
        if MAX_TRADES_DIA > 0 and trades_hoje >= MAX_TRADES_DIA:
            continue

        if dow == 0 and on_key == d and on_hi is not None and on_hi > 0:
            n_hi, n_lo = on_hi, on_lo
        else:
            n_hi, n_lo = pd_hi, pd_lo

        ev = dp.avalia_bar(b, n_hi, n_lo, tol_pts, MAX_DIST)
        if ev is not None and ev['cat'] == 'OPEROU':
            if ev['lado'] == 'SHORT':
                entry = b['c'] - slip_pts   # vende mais barato do que o preco teorico
                pos = -1; stop = entry + PTS_SL; alvo = entry - PTS_TP
            else:
                entry = b['c'] + slip_pts   # compra mais caro do que o preco teorico
                pos = 1; stop = entry - PTS_SL; alvo = entry + PTS_TP
            fav = entry; be_feito = False

    return trades


def resume(trades):
    wins = [t for t in trades if t['pnl_usd'] > 0]
    losses = [t for t in trades if t['pnl_usd'] < 0]
    tp = [t for t in trades if t['motivo'] == 'TP']
    be_trail = [t for t in trades if t['motivo'] == 'BE_TRAIL']
    sl = [t for t in trades if t['motivo'] == 'SL']

    gm = sum(t['pnl_usd'] for t in wins) / len(wins) if wins else 0.0
    pm = sum(t['pnl_usd'] for t in losses) / len(losses) if losses else 0.0
    ratio = (gm / abs(pm)) if pm != 0 else float('inf')
    wr = len(wins) / len(trades) * 100 if trades else 0.0
    pnl_total = sum(t['pnl_usd'] for t in trades)

    return {
        'trades': len(trades), 'wins': len(wins), 'losses': len(losses),
        'ganho_medio': gm, 'perda_media': pm, 'ratio': ratio, 'wr': wr,
        'pnl_total': pnl_total, 'tp_hits': len(tp), 'be_trail_hits': len(be_trail),
        'sl_hits': len(sl),
    }


def imprime_tabela(titulo, linhas):
    print(f"\n{titulo}")
    print(f"{'Gatilho':<9}{'Trades':<8}{'GanhoMed':<11}{'PerdaMed':<11}{'Ratio':<8}"
          f"{'WR%':<7}{'PnLTotal':<11}{'TP':<5}{'BE/Trail':<10}{'SL':<5}")
    for l in linhas:
        marca = ' (atual)' if l['gatilho'] == 3.75 else ''
        print(f"{l['gatilho']:<9}{l['trades']:<8}${l['ganho_medio']:<10.1f}"
              f"${l['perda_media']:<10.1f}{l['ratio']:<8.2f}{l['wr']:<7.1f}"
              f"${l['pnl_total']:<10.1f}{l['tp_hits']:<5}{l['be_trail_hits']:<10}{l['sl_hits']:<5}{marca}")


def main():
    print("Carregando NQ_dados/*.txt (1min) ...")
    bars1m = dp.carregar_1min(dp.PASTA_DADOS)
    print(f"  {len(bars1m):,} candles de 1min ({bars1m[0]['dt'].date()} a {bars1m[-1]['dt'].date()})")
    bars5m = dp.resample_5min(bars1m)
    print(f"  {len(bars5m):,} candles de 5min\n")

    print("=" * 110)
    print("SENSIBILIDADE DO GATILHO DE BREAKEVEN — SL 12,5pt | Trailing 1,75pt | "
          "MaxDist 15pt | Tol 5pt | TP 60pt (fixos)")
    print("=" * 110)

    SLIP_TICKS = 2
    SLIP_PTS = SLIP_TICKS * TICK   # 0.5pt, padrao ja validado no projeto (docs/melhorias-sugeridas.md)

    linhas_ano = []
    linhas_ano_slip = []
    linhas_jun = []
    csv_rows = []

    for g in GATILHOS:
        tr_ano = simula(bars5m, g, ANO_INICIO, ANO_FIM, slip_pts=0.0)
        r_ano = resume(tr_ano); r_ano['gatilho'] = g
        linhas_ano.append(r_ano)

        tr_ano_slip = simula(bars5m, g, ANO_INICIO, ANO_FIM, slip_pts=SLIP_PTS)
        r_ano_slip = resume(tr_ano_slip); r_ano_slip['gatilho'] = g
        linhas_ano_slip.append(r_ano_slip)

        tr_jun = simula(bars5m, g, JUN_INICIO, JUN_FIM, slip_pts=SLIP_PTS)
        r_jun = resume(tr_jun); r_jun['gatilho'] = g
        linhas_jun.append(r_jun)

        csv_rows.append({'Gatilho': g,
                          **{f'ano_semslip_{k}': v for k, v in r_ano.items() if k != 'gatilho'},
                          **{f'ano_2ticks_{k}': v for k, v in r_ano_slip.items() if k != 'gatilho'},
                          **{f'jun_2ticks_{k}': v for k, v in r_jun.items() if k != 'gatilho'}})

    imprime_tabela(f"(A) ANO INTEIRO, SEM SLIPPAGE ({ANO_INICIO} a {ANO_FIM}) — otimista, so referencia", linhas_ano)
    imprime_tabela(f"(A2) ANO INTEIRO, COM SLIPPAGE 2 TICKS (0,5pt) — a visao que importa de verdade", linhas_ano_slip)
    imprime_tabela(f"(B) SO junho/2026 disponivel ({JUN_INICIO} a {JUN_FIM}, ~8 dias uteis, com slippage) — "
                    f"SO CONFERENCIA, amostra pequena demais pra decidir sozinha", linhas_jun)

    print("\n" + "=" * 110)
    print("VEREDITO (baseado na visao A2 — ano inteiro COM slippage 2 ticks, a mais realista)")
    print("=" * 110)
    base_sem = linhas_ano[0]; base_com = linhas_ano_slip[0]
    print(f"Baseline SEM slippage:  ratio={base_sem['ratio']:.2f}  (pra referencia -- e' otimista demais)")
    print(f"Baseline COM slippage:  ratio={base_com['ratio']:.2f}, WR={base_com['wr']:.1f}%, "
          f"PnL total=${base_com['pnl_total']:.1f}")
    print(f"  (compare com o ratio REAL medido no forward test ao vivo: 0.54 -- se ainda")
    print(f"   estiver bem acima disso, o backtest continua otimista demais mesmo com slippage)")

    melhor = max(linhas_ano_slip, key=lambda l: l['ratio'])
    print(f"\nMelhor ratio com slippage: gatilho {melhor['gatilho']}pt -> ratio={melhor['ratio']:.2f}, "
          f"WR={melhor['wr']:.1f}%, PnL total=${melhor['pnl_total']:.1f}")

    acima_055 = [l for l in linhas_ano_slip if l['ratio'] > 0.55]
    if not acima_055:
        print("\n⚠️  NENHUMA variante passou de ratio 0.55 no ano inteiro, mesmo com slippage.")
        print("    -> Problema estrutural da entrada, nao da saida.")
    else:
        print(f"\n{len(acima_055)} variante(s) passaram de ratio 0.55 com slippage: "
              f"{[l['gatilho'] for l in acima_055]}")

    melhor_pnl = max(linhas_ano_slip, key=lambda l: l['pnl_total'])
    print(f"\nMelhor PnL total com slippage: gatilho {melhor_pnl['gatilho']}pt -> "
          f"${melhor_pnl['pnl_total']:.1f} (vs baseline ${base_com['pnl_total']:.1f})")

    csv_path = os.path.join(os.path.dirname(__file__), 'sensibilidade_breakeven.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        campos = list(csv_rows[0].keys())
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(csv_rows)
    print(f"\nCSV salvo em: {csv_path}")


if __name__ == '__main__':
    main()
