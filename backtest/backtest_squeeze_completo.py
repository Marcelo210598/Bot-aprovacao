#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BACKTEST COMPLETO — Conceito C (Squeeze 1h -> rompimento), 18/08/2026

Motor de saida completo (SL/TP/BE/trailing, 1 posicao por vez, stop diario,
max trades/dia) pro sinal que venceu a triagem barata (+8.7pp sobre aleatorio,
maior de todos os conceitos testados hoje, incluindo a estrategia em producao).

Granularidade: 1min (licao do dia -- 5min mascarava resultado). Slippage 2
ticks embutido desde o inicio. Mesmo contexto de conta: 5 MNQ, $2/pt, $1.20 RT.
"""
import sys, os, csv
sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp
import screening_novas_entradas as sc

TICK = dp.TICK
MNQ_PV = 2.0; N_CONTR = 5; RT = 1.20 * N_CONTR
SLIP = 2 * TICK
ANO_INICIO, ANO_FIM = sc.ANO_INICIO, sc.ANO_FIM
STOP_DIA_PT = 750.0 / (MNQ_PV * N_CONTR)
MAX_TRADES_DIA = 12


def simula_saida(bars, sinais, sl_pts, tp_pts, be_trig, be_lock, trail_pts):
    pv = MNQ_PV * N_CONTR
    idx_sinal = {}
    for s in sinais:
        idx_sinal.setdefault(s['idx'], s)   # 1 sinal por indice de barra

    pos = 0; entry = stop = alvo = fav = 0.0; be_feito = False
    dia = None; pnl_dia0 = 0.0; realizado = 0.0; bloqueado_hoje = False
    trades = []
    pico = 0.0; dd_max = 0.0

    def fecha(preco, motivo, d):
        nonlocal pos, realizado, pico, dd_max
        preco_real = preco - SLIP if pos > 0 else preco + SLIP
        pts = (preco_real - entry) if pos > 0 else (entry - preco_real)
        usd = pts * pv - RT
        realizado += usd
        pico = max(pico, realizado)
        dd_max = max(dd_max, pico - realizado)
        trades.append({'pnl_usd': usd, 'motivo': motivo, 'data': d})
        pos = 0

    for idx, b in enumerate(bars):
        dt = b['dt']; d = dt.strftime('%Y-%m-%d'); m = dp.mins(dt)
        if d != dia:
            dia = d; bloqueado_hoje = False; pnl_dia0 = realizado
        if not (ANO_INICIO <= d <= ANO_FIM):
            continue

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
                    if not be_feito and (fav - entry) >= be_trig:
                        stop = max(stop, entry + be_lock); be_feito = True
                    if be_feito:
                        stop = max(stop, fav - trail_pts)
                else:
                    fav = min(fav, b['l'])
                    if not be_feito and (entry - fav) >= be_trig:
                        stop = min(stop, entry - be_lock); be_feito = True
                    if be_feito:
                        stop = min(stop, fav + trail_pts)
            else:
                if STOP_DIA_PT > 0 and (realizado - pnl_dia0) <= -STOP_DIA_PT * pv:
                    bloqueado_hoje = True
            continue

        if bloqueado_hoje:
            continue
        trades_hoje = sum(1 for t in trades if t['data'] == d)
        if MAX_TRADES_DIA > 0 and trades_hoje >= MAX_TRADES_DIA:
            continue

        s = idx_sinal.get(idx)
        if s is not None:
            if s['lado'] == 'SHORT':
                entry = b['c'] - SLIP; pos = -1; stop = entry + sl_pts; alvo = entry - tp_pts
            else:
                entry = b['c'] + SLIP; pos = 1; stop = entry - sl_pts; alvo = entry + tp_pts
            fav = entry; be_feito = False

    return trades, dd_max


def resume(trades):
    wins = [t for t in trades if t['pnl_usd'] > 0]
    losses = [t for t in trades if t['pnl_usd'] < 0]
    tp = [t for t in trades if t['motivo'] == 'TP']
    be = [t for t in trades if t['motivo'] == 'BE_TRAIL']
    sl = [t for t in trades if t['motivo'] == 'SL']
    gm = sum(t['pnl_usd'] for t in wins) / len(wins) if wins else 0.0
    pm = sum(t['pnl_usd'] for t in losses) / len(losses) if losses else 0.0
    ratio = gm / abs(pm) if pm else float('inf')
    wr = len(wins) / len(trades) * 100 if trades else 0.0
    return {'n': len(trades), 'wr': wr, 'gm': gm, 'pm': pm, 'ratio': ratio,
            'pnl': sum(t['pnl_usd'] for t in trades), 'tp': len(tp), 'be': len(be), 'sl': len(sl)}


def main():
    print("Carregando 1min ...")
    bars1m = dp.carregar_1min(dp.PASTA_DADOS)
    print(f"  {len(bars1m):,} candles de 1min\n")

    print("Gerando sinais Squeeze em 1min (janela canal 60min = 1h, range<40pt) ...")
    sinais = sc.coleta_squeeze(bars1m, janela_canal=60, limiar_range_pts=40.0)
    print(f"  {len(sinais)} sinais no ano\n")

    print("=" * 100)
    print("GRADE DE SAIDA — SL x TP (BE gatilho=SL, trava=SL/2, trailing=SL/2 -- escala com o SL)")
    print("=" * 100)
    print(f"{'SL':<6}{'TP':<6}{'N':<6}{'WR%':<7}{'GanhoMed':<11}{'PerdaMed':<11}{'Ratio':<7}"
          f"{'PnLTotal':<12}{'DDmax':<10}{'TP':<5}{'BE':<5}{'SL'}")
    linhas = []
    for sl in [8.0, 10.0, 12.5, 15.0, 20.0]:
        for tp in [10.0, 15.0, 20.0, 25.0, 30.0, 40.0]:
            be_trig = sl * 0.5; be_lock = sl * 0.15; trail = sl * 0.3
            trades, dd = simula_saida(bars1m, sinais, sl, tp, be_trig, be_lock, trail)
            r = resume(trades)
            print(f"{sl:<6}{tp:<6}{r['n']:<6}{r['wr']:<7.1f}${r['gm']:<10.1f}${r['pm']:<10.1f}"
                  f"{r['ratio']:<7.2f}${r['pnl']:<11.1f}${dd:<9.1f}{r['tp']:<5}{r['be']:<5}{r['sl']}")
            linhas.append({'sl_pts': sl, 'tp_pts': tp, 'be_trig': be_trig, 'be_lock': be_lock,
                            'trail': trail, 'dd_max': dd, **r})

    csv_path = os.path.join(os.path.dirname(__file__), 'backtest_squeeze_grade.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys())); w.writeheader(); w.writerows(linhas)

    melhor = max(linhas, key=lambda l: l['pnl'])
    print(f"\nMelhor por PnL: SL={melhor['sl_pts']} TP={melhor['tp_pts']} -> ratio={melhor['ratio']:.2f} "
          f"WR={melhor['wr']:.1f}% PnL=${melhor['pnl']:.1f} DDmax=${melhor['dd_max']:.1f}")
    print(f"CSV: {csv_path}")


if __name__ == '__main__':
    main()
