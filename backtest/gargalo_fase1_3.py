#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FASE 1-3: decomposicao do PnL, classificacao das janelas de 30d, curva de
equity. Motor identico ao baseline sempre usado (SL12,5/TP60/BE3,75-2,5/
trail1,75, slippage 2 ticks, 1min, ano inteiro, 5 MNQ)."""
import sys, os
from datetime import timedelta, datetime
sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp
import experimento_final_atr as efa

bars = dp.carregar_1min(dp.PASTA_DADOS)
print(f"{len(bars):,} candles carregados\n")


def simula_com_duracao_hora(bars):
    """Como experimento_final_atr.simula, mas guarda tambem duracao (em
    barras=minutos) e hora de entrada."""
    tol_pts = efa.TOL_TICKS * efa.TICK; pv = efa.MNQ_PV * efa.N_CONTR
    cur_hi = cur_lo = None; pd_hi = pd_lo = None; dia = None
    on_key = None; on_hi = on_lo = None
    pos = 0; entry = stop = alvo = fav = 0.0; be_feito = False
    pnl_dia0 = 0.0; realizado = 0.0; bloqueado_hoje = False
    trades = []; mfe_atual = mae_atual = 0.0; idx_entry = None; hora_entry = None

    def fecha(preco, motivo, d, idx_saida):
        nonlocal pos, realizado
        preco_real = preco - efa.SLIP if pos > 0 else preco + efa.SLIP
        pts = (preco_real - entry) if pos > 0 else (entry - preco_real)
        usd = pts * pv - efa.RT
        realizado += usd
        trades.append({'pnl_usd': usd, 'motivo': motivo, 'data': d, 'mfe': mfe_atual,
                        'mae': mae_atual, 'dur_min': idx_saida - idx_entry, 'hora_entry': hora_entry})
        pos = 0

    for idx, b in enumerate(bars):
        dt = b['dt']; d = dt.strftime('%Y-%m-%d'); m = dp.mins(dt); dow = dt.weekday()
        em_sessao = dp.SESSAO_INICIO <= m < dp.ENTRADA_FIM
        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = b['h'] if em_sessao else None; cur_lo = b['l'] if em_sessao else None
            bloqueado_hoje = False; pnl_dia0 = realizado
        elif em_sessao:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
        chave_seg = None
        if dow == 6 and m >= dp.DOM_NOITE_INICIO: chave_seg = (dt+timedelta(days=1)).strftime('%Y-%m-%d')
        elif dow == 0 and m < dp.SESSAO_INICIO: chave_seg = d
        if chave_seg is not None:
            if chave_seg != on_key: on_key, on_hi, on_lo = chave_seg, b['h'], b['l']
            else: on_hi = max(on_hi, b['h']); on_lo = min(on_lo, b['l'])
        if not (efa.ANO_INICIO <= d <= efa.ANO_FIM): continue

        if pos != 0:
            saiu = False
            if pos > 0:
                fav = max(fav, b['h']); mfe_atual = max(mfe_atual, fav - entry)
                mae_atual = max(mae_atual, entry - b['l'])
                if b['l'] <= stop: fecha(stop, 'BE_TRAIL' if be_feito else 'SL', d, idx); saiu = True
                elif b['h'] >= alvo: fecha(alvo, 'TP', d, idx); saiu = True
            else:
                fav = min(fav, b['l']); mfe_atual = max(mfe_atual, entry - fav)
                mae_atual = max(mae_atual, b['h'] - entry)
                if b['h'] >= stop: fecha(stop, 'BE_TRAIL' if be_feito else 'SL', d, idx); saiu = True
                elif b['l'] <= alvo: fecha(alvo, 'TP', d, idx); saiu = True
            if not saiu:
                if pos > 0:
                    if not be_feito and (fav-entry) >= efa.PTS_BE_TRIG: stop = max(stop, entry+efa.PTS_BE_LOCK); be_feito = True
                    if be_feito: stop = max(stop, fav - efa.PTS_TRAIL)
                else:
                    if not be_feito and (entry-fav) >= efa.PTS_BE_TRIG: stop = min(stop, entry-efa.PTS_BE_LOCK); be_feito = True
                    if be_feito: stop = min(stop, fav + efa.PTS_TRAIL)
            else:
                if efa.STOP_DIA_PT > 0 and (realizado-pnl_dia0) <= -efa.STOP_DIA_PT*pv: bloqueado_hoje = True
            continue

        if bloqueado_hoje or not em_sessao: continue
        if pd_hi is None or pd_lo is None: continue
        trades_hoje = sum(1 for t in trades if t['data'] == d)
        if efa.MAX_TRADES_DIA > 0 and trades_hoje >= efa.MAX_TRADES_DIA: continue

        if dow == 0 and on_key == d and on_hi: n_hi, n_lo = on_hi, on_lo
        else: n_hi, n_lo = pd_hi, pd_lo
        ev = dp.avalia_bar(b, n_hi, n_lo, tol_pts, efa.MAX_DIST)
        if ev is not None and ev['cat'] == 'OPEROU':
            if ev['lado'] == 'SHORT':
                entry = b['c'] - efa.SLIP; pos = -1; stop = entry+efa.PTS_SL; alvo = entry-efa.PTS_TP
            else:
                entry = b['c'] + efa.SLIP; pos = 1; stop = entry-efa.PTS_SL; alvo = entry+efa.PTS_TP
            fav = entry; be_feito = False; mfe_atual = mae_atual = 0.0
            idx_entry = idx; hora_entry = m
    return trades


trades = simula_com_duracao_hora(bars)
n = len(trades)
print(f"N total de trades = {n}\n")

# ===================== FASE 1 =====================
print("=" * 100)
print("FASE 1 — DECOMPOSICAO DO PnL")
print("=" * 100)

def med(xs):
    xs = sorted(xs); m = len(xs)
    return xs[m//2] if m % 2 else (xs[m//2-1]+xs[m//2])/2

def pctl(xs, p):
    xs = sorted(xs); return xs[int(len(xs)*p)]

wins = [t['pnl_usd'] for t in trades if t['pnl_usd'] > 0]
losses = [t['pnl_usd'] for t in trades if t['pnl_usd'] < 0]
wr = len(wins)/n*100
gm = sum(wins)/len(wins); pm = sum(losses)/len(losses)
pf = sum(wins)/abs(sum(losses))
exp = sum(t['pnl_usd'] for t in trades)/n
pnl_total = sum(t['pnl_usd'] for t in trades)

print(f"N={n} | WR={wr:.1f}% | GanhoMed=${gm:.1f} | PerdaMed=${pm:.1f} | PF={pf:.2f} | Expectancy=${exp:.1f}")
print(f"Mediana ganho=${med(wins):.1f} | Mediana perda=${med(losses):.1f}")
print(f"P25/P75 ganhos: ${pctl(wins,.25):.1f} / ${pctl(wins,.75):.1f}")
print(f"P25/P75 perdas: ${pctl(losses,.25):.1f} / ${pctl(losses,.75):.1f}")
print(f"PnL total = ${pnl_total:.1f}")

seq = maxseq_l = 0; seqg = maxseq_g = 0
for t in trades:
    if t['pnl_usd'] < 0: seq += 1; maxseq_l = max(maxseq_l, seq); seqg = 0
    else: seqg += 1; maxseq_g = max(maxseq_g, seqg); seq = 0
print(f"Maior sequencia de perdas: {maxseq_l} | Maior sequencia de ganhos: {maxseq_g}")

mfes = [t['mfe'] for t in trades]; maes = [t['mae'] for t in trades]
print(f"MFE medio={sum(mfes)/n:.2f} mediana={med(mfes):.2f} | MAE medio={sum(maes)/n:.2f} mediana={med(maes):.2f}")

durs = [t['dur_min'] for t in trades]
print(f"Duracao media={sum(durs)/n:.1f}min mediana={med(durs):.1f}min")

pnl_dia = {}
for t in trades: pnl_dia[t['data']] = pnl_dia.get(t['data'], 0.0) + t['pnl_usd']
print(f"PnL medio por trade=${exp:.1f} | PnL medio por dia operado=${sum(pnl_dia.values())/len(pnl_dia):.1f}")

pnl_hora = {}
for t in trades:
    h = t['hora_entry']//60
    pnl_hora[h] = pnl_hora.get(h, 0.0) + t['pnl_usd']
print("PnL por hora de entrada (ET):")
for h in sorted(pnl_hora):
    print(f"  {h:02d}h: ${pnl_hora[h]:.1f}")

print("\n--- Concentracao do PnL (edge depende de poucos trades excepcionais?) ---")
trades_ord = sorted(trades, key=lambda t: -t['pnl_usd'])
for pct, label in [(0.01,'top 1%'), (0.05,'top 5%'), (0.10,'top 10%')]:
    k = max(1, int(n*pct))
    soma = sum(t['pnl_usd'] for t in trades_ord[:k])
    print(f"  {label} ({k} trades): ${soma:.1f} ({soma/pnl_total*100:.1f}% do PnL total)")
resto90 = trades_ord[int(n*0.10):]
print(f"  Resto (90%, {len(resto90)} trades): ${sum(t['pnl_usd'] for t in resto90):.1f} "
      f"({sum(t['pnl_usd'] for t in resto90)/pnl_total*100:.1f}%)")
extremas = [t for t in trades if t['pnl_usd'] <= pctl(losses,.05)]
print(f"  Perdas extremas (piores 5% das perdas, {len(extremas)} trades): ${sum(t['pnl_usd'] for t in extremas):.1f}")
