#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANALISE EXPLORATORIA DA QUALIDADE DO SINAL DE ENTRADA (18/08/2026)

Objetivo: descobrir o que diferencia sinais que viram reversao forte (MFE alto)
dos que viram reversao fraca (MFE baixo) -- usando so caracteristicas
observaveis NO MOMENTO DA ENTRADA (sem lookahead).

Fonte: os 71 trades reais do forward-test-replay-25k/2026-06-1min/ (nao so os
58 que ativaram BE -- os fracos que nunca ativam BE sao justamente o Grupo 1,
MFE<5, que precisamos incluir).

JANELA DE MFE -- decidida ANTES de rodar qualquer resultado:
60 minutos a partir da entrada. Justificativa: a gestao da estrategia
(trailing 1,75pt) normalmente resolve o trade bem antes disso -- 60min da
folga suficiente pra reversao "provar" a tese sem contaminar com movimento
de outras horas do dia (o erro que ja cometi antes, testando ate 400min).
Nao e o "melhor" numero pro resultado -- e o teto operacional razoavel antes
de olhar qualquer numero.
"""
import sys, os, csv
from datetime import timedelta
sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp
import parse_trades_replay as ptr

JANELA_MFE_MIN = 60   # DECIDIDO ANTES de olhar resultado


def carrega_1min_indexado():
    bars = dp.carregar_1min(dp.PASTA_DADOS)
    por_dia = {}
    for i, b in enumerate(bars):
        d = b['dt'].strftime('%Y-%m-%d')
        por_dia.setdefault(d, []).append(i)
    return bars, por_dia


def nivel_do_dia(bars, data_alvo):
    """Reconstroi pdHigh/pdLow (ou range de domingo p/ segunda) ate a data
    alvo, replicando a maquina de estado do .cs (mesma logica de sempre)."""
    cur_hi = cur_lo = None; pd_hi = pd_lo = None; dia = None
    on_key = None; on_hi = on_lo = None
    for b in bars:
        dt = b['dt']; d = dt.strftime('%Y-%m-%d'); m = dp.mins(dt); dow = dt.weekday()
        if d > data_alvo:
            break
        em_sessao = dp.SESSAO_INICIO <= m < dp.ENTRADA_FIM
        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = b['h'] if em_sessao else None; cur_lo = b['l'] if em_sessao else None
        elif em_sessao:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
        chave_seg = None
        if dow == 6 and m >= dp.DOM_NOITE_INICIO: chave_seg = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
        elif dow == 0 and m < dp.SESSAO_INICIO: chave_seg = d
        if chave_seg is not None:
            if chave_seg != on_key: on_key, on_hi, on_lo = chave_seg, b['h'], b['l']
            else: on_hi = max(on_hi, b['h']); on_lo = min(on_lo, b['l'])
    dow_alvo = dp.bars_diarios_rth if False else None
    return pd_hi, pd_lo, on_key, on_hi, on_lo


def localiza_toque(bars, idxs_dia, t, tol=1.5):
    if t['hora'] is None or not idxs_dia: return None
    hh, mm = map(int, t['hora'].split(':'))
    alvo_min = (hh - 1) * 60 + mm
    if alvo_min < 0: alvo_min += 24 * 60
    cand = [i for i in idxs_dia if dp.mins(bars[i]['dt']) == alvo_min]
    if not cand: return None
    touch_idx = cand[0]
    entry_idx = touch_idx + 1
    if entry_idx >= len(bars) or bars[entry_idx]['dt'].strftime('%Y-%m-%d') != t['data']:
        return None
    if abs(bars[entry_idx]['o'] - t['entry']) > tol:
        for k in range(2, 4):
            if entry_idx + k < len(bars) and abs(bars[entry_idx + k]['o'] - t['entry']) <= tol:
                touch_idx += (k - 1); entry_idx += (k - 1); break
        else:
            return None
    return touch_idx, entry_idx


def range_bars(bars, i0, n):
    """range (high-low) das n barras terminando em i0 (inclusive), olhando p/ TRAS."""
    ini = max(0, i0 - n + 1)
    sub = bars[ini:i0 + 1]
    if not sub: return 0.0
    return max(b['h'] for b in sub) - min(b['l'] for b in sub)


def atr_simples(bars, i0, n=14):
    ini = max(1, i0 - n + 1)
    trs = []
    for j in range(ini, i0 + 1):
        tr = max(bars[j]['h'] - bars[j]['l'], abs(bars[j]['h'] - bars[j-1]['c']), abs(bars[j]['l'] - bars[j-1]['c']))
        trs.append(tr)
    return sum(trs) / len(trs) if trs else 0.0


def conta_toques_antes(bars, idxs_dia, touch_idx, nivel, lado, tol_pts):
    """Quantas vezes o preco chegou perto do nivel HOJE, antes desse toque."""
    n = 0
    for i in idxs_dia:
        if i >= touch_idx: break
        m = dp.mins(bars[i]['dt'])
        if not (dp.SESSAO_INICIO <= m < dp.ENTRADA_FIM): continue
        if lado == 'SHORT' and bars[i]['h'] >= nivel - tol_pts: n += 1
        if lado == 'LONG' and bars[i]['l'] <= nivel + tol_pts: n += 1
    return n


def mfe_janela(bars, entry_idx, entry_price, lado, janela_min):
    lado_sinal = 1 if lado == 'LONG' else -1
    mfe = 0.0; mae = 0.0
    limite = min(entry_idx + janela_min, len(bars))
    d0 = bars[entry_idx]['dt'].strftime('%Y-%m-%d')
    for j in range(entry_idx, limite):
        if bars[j]['dt'].strftime('%Y-%m-%d') != d0: break
        if dp.mins(bars[j]['dt']) >= 1655: break
        fav = (bars[j]['h'] - entry_price) if lado_sinal > 0 else (entry_price - bars[j]['l'])
        adv = (entry_price - bars[j]['l']) if lado_sinal > 0 else (bars[j]['h'] - entry_price)
        mfe = max(mfe, fav); mae = max(mae, adv)
    return mfe, mae


def main():
    trades = ptr.carrega_todos()
    bars, por_dia = carrega_1min_indexado()
    print(f"{len(trades)} trades reais carregados\n")

    linhas = []
    nao_loc = 0
    for t in trades:
        loc = localiza_toque(bars, por_dia.get(t['data'], []), t)
        if loc is None:
            nao_loc += 1
            continue
        touch_idx, entry_idx = loc
        lado = t['lado']; entry = t['entry']

        pd_hi, pd_lo, on_key, on_hi, on_lo = nivel_do_dia(bars, t['data'])
        dt_touch = bars[touch_idx]['dt']
        dow = dt_touch.weekday()
        if dow == 0 and on_key == t['data'] and on_hi:
            nivel = on_hi if lado == 'SHORT' else on_lo
        else:
            nivel = pd_hi if lado == 'SHORT' else pd_lo
        if nivel is None: continue

        # --- contexto pre-entrada ---
        idxs_dia = por_dia.get(t['data'], [])
        idxs_sessao_ate_agora = [i for i in idxs_dia if dp.SESSAO_INICIO <= dp.mins(bars[i]['dt']) <= dp.mins(dt_touch)]
        range_dia_ate_agora = (max(bars[i]['h'] for i in idxs_sessao_ate_agora) -
                                min(bars[i]['l'] for i in idxs_sessao_ate_agora)) if idxs_sessao_ate_agora else 0
        abre_sessao = next((bars[i]['o'] for i in idxs_dia if dp.mins(bars[i]['dt']) == dp.SESSAO_INICIO), None)

        candle_toque = bars[touch_idx]
        candle_ant = bars[touch_idx - 1] if touch_idx > 0 else candle_toque
        corpo_ant = abs(candle_ant['c'] - candle_ant['o'])
        pavio_sup_ant = candle_ant['h'] - max(candle_ant['o'], candle_ant['c'])
        pavio_inf_ant = min(candle_ant['o'], candle_ant['c']) - candle_ant['l']
        dir_ant = 1 if candle_ant['c'] >= candle_ant['o'] else -1

        seq = 0
        k = touch_idx - 1
        while k >= 0 and bars[k]['dt'].strftime('%Y-%m-%d') == t['data']:
            d_k = 1 if bars[k]['c'] >= bars[k]['o'] else -1
            if d_k != dir_ant: break
            seq += 1; k -= 1

        vel1 = candle_toque['h'] - candle_toque['l'] if touch_idx - 1 < 0 else abs(bars[touch_idx]['c'] - bars[max(0,touch_idx-1)]['c'])
        vel3 = abs(bars[touch_idx]['c'] - bars[max(0,touch_idx-3)]['c'])
        vel5 = abs(bars[touch_idx]['c'] - bars[max(0,touch_idx-5)]['c'])

        n_toques_antes = conta_toques_antes(bars, idxs_dia, touch_idx, nivel, lado, 5.0)

        dist_nivel = abs(t['entry'] - nivel)
        excesso_toque = (candle_toque['h'] - nivel) if lado == 'SHORT' else (nivel - candle_toque['l'])

        mfe60, mae60 = mfe_janela(bars, entry_idx, entry, lado, JANELA_MFE_MIN)
        mfe_flatten, mae_flatten = mfe_janela(bars, entry_idx, entry, lado, 500)

        linhas.append({
            'sinal': t['sinal'], 'data': t['data'], 'hora': t['hora'], 'lado': lado,
            'entry': entry, 'nivel': round(nivel, 2), 'dist_nivel': round(dist_nivel, 2),
            'range_dia_ate_toque': round(range_dia_ate_agora, 2),
            'range_5c': round(range_bars(bars, touch_idx, 5), 2),
            'range_15c': round(range_bars(bars, touch_idx, 15), 2),
            'atr14': round(atr_simples(bars, touch_idx), 2),
            'corpo_candle_ant': round(corpo_ant, 2), 'pavio_sup_ant': round(pavio_sup_ant, 2),
            'pavio_inf_ant': round(pavio_inf_ant, 2), 'dir_candle_ant': dir_ant,
            'seq_mesma_direcao': seq,
            'vel_1min': round(vel1, 2), 'vel_3min': round(vel3, 2), 'vel_5min': round(vel5, 2),
            'n_toques_antes_hoje': n_toques_antes,
            'ordinal_toque': n_toques_antes + 1,
            'dist_abertura_sessao': round(abs(entry - abre_sessao), 2) if abre_sessao else None,
            'excesso_sobre_nivel': round(excesso_toque, 2),
            'hora_min_et': dp.mins(bars[touch_idx]['dt']),
            'mfe60': round(mfe60, 2), 'mae60': round(mae60, 2),
            'mfe_flatten': round(mfe_flatten, 2),
            'pnl_real': t['pnl'], 'motivo_real': t['motivo'],
        })

    print(f"Localizados: {len(linhas)} de {len(trades)} ({len(linhas)/len(trades)*100:.1f}%). "
          f"Nao localizados: {nao_loc}\n")

    csvp = os.path.join(os.path.dirname(__file__), 'analise_qualidade_entrada.csv')
    with open(csvp, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys())); w.writeheader(); w.writerows(linhas)
    print(f"CSV: {csvp}")

    return linhas

if __name__ == '__main__':
    main()
