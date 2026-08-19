#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EXPERIMENTO FINAL DE REGIME — ATR (18/08/2026)

Pergunta unica: um regime de volatilidade alto (ATR no momento do sinal)
melhora a ECONOMIA COMPLETA da estrategia (nao so MFE)? Motor de saida
IDENTICO a producao (SL 12,5 / TP 60 / BE 3,75-2,5 / trail 1,75), slippage
2 ticks, 1min, ano inteiro. Cortes de ATR = quartis JA calculados na analise
anterior (qualidade_entrada_ano.csv) -- nao reotimizados aqui.
"""
import sys, os, csv
from datetime import timedelta
sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp
import aprovacao_conta_paralelo as acp

TICK = dp.TICK; TOL_TICKS = 20; MAX_DIST = 15.0
PTS_SL = 12.5; PTS_TP = 60.0; PTS_BE_TRIG = 3.75; PTS_BE_LOCK = 2.50; PTS_TRAIL = 1.75
MNQ_PV = 2.0; N_CONTR = 5; RT = 1.20 * N_CONTR; SLIP = 2 * TICK
STOP_DIA_PT = 750.0 / (MNQ_PV * N_CONTR); MAX_TRADES_DIA = 12
ANO_INICIO, ANO_FIM = '2025-06-11', '2026-06-11'


def range_bars(bars, i0, n):
    ini = max(0, i0 - n + 1); sub = bars[ini:i0 + 1]
    return (max(b['h'] for b in sub) - min(b['l'] for b in sub)) if sub else 0.0


def atr_simples(bars, i0, n=14):
    ini = max(1, i0 - n + 1); trs = []
    for j in range(ini, i0 + 1):
        trs.append(max(bars[j]['h']-bars[j]['l'], abs(bars[j]['h']-bars[j-1]['c']), abs(bars[j]['l']-bars[j-1]['c'])))
    return sum(trs)/len(trs) if trs else 0.0


def calcula_quartis_atr(bars):
    """Recalcula os MESMOS quartis de ATR14 ja usados na analise anterior
    (2466 sinais), so pra ter os cortes -- nao reotimiza nada."""
    tol_pts = TOL_TICKS * TICK
    cur_hi = cur_lo = None; pd_hi = pd_lo = None; dia = None
    on_key = None; on_hi = on_lo = None
    atrs = []
    for idx, b in enumerate(bars):
        dt = b['dt']; d = dt.strftime('%Y-%m-%d'); m = dp.mins(dt); dow = dt.weekday()
        em_sessao = dp.SESSAO_INICIO <= m < dp.ENTRADA_FIM
        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = b['h'] if em_sessao else None; cur_lo = b['l'] if em_sessao else None
        elif em_sessao:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
        chave_seg = None
        if dow == 6 and m >= dp.DOM_NOITE_INICIO: chave_seg = (dt+timedelta(days=1)).strftime('%Y-%m-%d')
        elif dow == 0 and m < dp.SESSAO_INICIO: chave_seg = d
        if chave_seg is not None:
            if chave_seg != on_key: on_key, on_hi, on_lo = chave_seg, b['h'], b['l']
            else: on_hi = max(on_hi, b['h']); on_lo = min(on_lo, b['l'])
        if not (ANO_INICIO <= d <= ANO_FIM): continue
        if not em_sessao: continue
        if pd_hi is None or pd_lo is None: continue
        if dow == 0 and on_key == d and on_hi: n_hi, n_lo = on_hi, on_lo
        else: n_hi, n_lo = pd_hi, pd_lo
        ev = dp.avalia_bar(b, n_hi, n_lo, tol_pts, MAX_DIST)
        if ev is not None and ev['cat'] == 'OPEROU':
            atrs.append(atr_simples(bars, idx))
    atrs.sort(); n = len(atrs)
    q1 = atrs[n//4]; q2 = atrs[n//2]; q3 = atrs[3*n//4]
    return q1, q2, q3


def simula(bars, filtro=None):
    """filtro = None (baseline) ou (lo, hi) em ATR14 no momento do TOQUE."""
    tol_pts = TOL_TICKS * TICK; pv = MNQ_PV * N_CONTR
    cur_hi = cur_lo = None; pd_hi = pd_lo = None; dia = None
    on_key = None; on_hi = on_lo = None
    pos = 0; entry = stop = alvo = fav = 0.0; be_feito = False
    pnl_dia0 = 0.0; realizado = 0.0; bloqueado_hoje = False
    trades = []; mfe_atual = mae_atual = 0.0

    def fecha(preco, motivo, d):
        nonlocal pos, realizado, mfe_atual, mae_atual
        preco_real = preco - SLIP if pos > 0 else preco + SLIP
        pts = (preco_real - entry) if pos > 0 else (entry - preco_real)
        usd = pts * pv - RT
        realizado += usd
        trades.append({'pnl_usd': usd, 'motivo': motivo, 'data': d,
                        'mfe': mfe_atual, 'mae': mae_atual})
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
        if not (ANO_INICIO <= d <= ANO_FIM): continue

        if pos != 0:
            saiu = False
            if pos > 0:
                fav = max(fav, b['h']); mfe_atual = max(mfe_atual, fav - entry)
                mae_atual = max(mae_atual, entry - min(fav, b['l']) if b['l'] < entry else mae_atual)
                mae_atual = max(mae_atual, entry - b['l'])
                if b['l'] <= stop: fecha(stop, 'BE_TRAIL' if be_feito else 'SL', d); saiu = True
                elif b['h'] >= alvo: fecha(alvo, 'TP', d); saiu = True
            else:
                fav = min(fav, b['l']); mfe_atual = max(mfe_atual, entry - fav)
                mae_atual = max(mae_atual, b['h'] - entry)
                if b['h'] >= stop: fecha(stop, 'BE_TRAIL' if be_feito else 'SL', d); saiu = True
                elif b['l'] <= alvo: fecha(alvo, 'TP', d); saiu = True
            if not saiu:
                if pos > 0:
                    if not be_feito and (fav - entry) >= PTS_BE_TRIG: stop = max(stop, entry + PTS_BE_LOCK); be_feito = True
                    if be_feito: stop = max(stop, fav - PTS_TRAIL)
                else:
                    if not be_feito and (entry - fav) >= PTS_BE_TRIG: stop = min(stop, entry - PTS_BE_LOCK); be_feito = True
                    if be_feito: stop = min(stop, fav + PTS_TRAIL)
            else:
                if STOP_DIA_PT > 0 and (realizado - pnl_dia0) <= -STOP_DIA_PT * pv: bloqueado_hoje = True
            continue

        if bloqueado_hoje or not (dp.SESSAO_INICIO <= m < dp.ENTRADA_FIM): continue
        if pd_hi is None or pd_lo is None: continue
        trades_hoje = sum(1 for t in trades if t['data'] == d)
        if MAX_TRADES_DIA > 0 and trades_hoje >= MAX_TRADES_DIA: continue

        if dow == 0 and on_key == d and on_hi: n_hi, n_lo = on_hi, on_lo
        else: n_hi, n_lo = pd_hi, pd_lo
        ev = dp.avalia_bar(b, n_hi, n_lo, tol_pts, MAX_DIST)
        if ev is not None and ev['cat'] == 'OPEROU':
            if filtro is not None:
                atr_agora = atr_simples(bars, idx)
                lo, hi = filtro
                if not (lo <= atr_agora < hi):
                    continue
            if ev['lado'] == 'SHORT':
                entry = b['c'] - SLIP; pos = -1; stop = entry + PTS_SL; alvo = entry - PTS_TP
            else:
                entry = b['c'] + SLIP; pos = 1; stop = entry - PTS_SL; alvo = entry + PTS_TP
            fav = entry; be_feito = False; mfe_atual = 0.0; mae_atual = 0.0
    return trades


def mediana(xs):
    xs = sorted(xs); n = len(xs)
    return xs[n//2] if n % 2 else (xs[n//2-1]+xs[n//2])/2


def resume_completo(trades):
    wins = [t for t in trades if t['pnl_usd'] > 0]; losses = [t for t in trades if t['pnl_usd'] < 0]
    n = len(trades)
    gm = sum(t['pnl_usd'] for t in wins)/len(wins) if wins else 0
    pm = sum(t['pnl_usd'] for t in losses)/len(losses) if losses else 0
    ratio = gm/abs(pm) if pm else 0
    wr = len(wins)/n*100 if n else 0
    pnl = sum(t['pnl_usd'] for t in trades)
    gross_w = sum(t['pnl_usd'] for t in wins); gross_l = abs(sum(t['pnl_usd'] for t in losses))
    pf = gross_w/gross_l if gross_l else 0
    exp = pnl/n if n else 0

    pico = acum = dd = 0.0; seq = maxseq = 0
    for t in trades:
        acum += t['pnl_usd']; pico = max(pico, acum); dd = max(dd, pico-acum)
        if t['pnl_usd'] < 0: seq += 1; maxseq = max(maxseq, seq)
        else: seq = 0

    pnl_dia = {}
    for t in trades: pnl_dia[t['data']] = pnl_dia.get(t['data'], 0.0) + t['pnl_usd']
    dias = list(pnl_dia.values())
    dias_pos = sum(1 for v in dias if v > 0); dias_neg = sum(1 for v in dias if v < 0)
    maior_ganho_dia = max(dias) if dias else 0; maior_perda_dia = min(dias) if dias else 0
    pnl_med_dia = sum(dias)/len(dias) if dias else 0

    mfes = [t['mfe'] for t in trades]; maes = [t['mae'] for t in trades]

    return {'n': n, 'wr': wr, 'gm': gm, 'pm': pm, 'ratio': ratio, 'pf': pf, 'exp': exp,
            'pnl': pnl, 'dd': dd, 'maxseq': maxseq, 'mfe_med': sum(mfes)/n if n else 0,
            'mfe_mediana': mediana(mfes) if mfes else 0, 'mae_med': sum(maes)/n if n else 0,
            'mae_mediana': mediana(maes) if maes else 0, 'n_dias': len(dias),
            'dias_pos': dias_pos, 'dias_neg': dias_neg, 'maior_ganho_dia': maior_ganho_dia,
            'maior_perda_dia': maior_perda_dia, 'pnl_med_dia': pnl_med_dia}


def simula_janelas_30d(trades, meta=1500.0, dd_limite=1000.0, min_dias=7):
    pnl_dia = {}
    for t in trades: pnl_dia[t['data']] = pnl_dia.get(t['data'], 0.0) + t['pnl_usd']
    datas_ord = sorted(pnl_dia)
    if not datas_ord: return {'n_janelas':0,'aprovadas':0,'taxa':0,'pnl_med':0,'dd_med':0,'dd_abs':0,'trades_med':0}
    from datetime import datetime
    dts = [datetime.strptime(d, '%Y-%m-%d') for d in datas_ord]
    n_trades_dia = {}
    for t in trades: n_trades_dia[t['data']] = n_trades_dia.get(t['data'], 0) + 1

    aprovadas = 0; pnls_janela = []; dds_janela = []; trades_janela = []
    for i, d0 in enumerate(dts):
        fim = d0 + timedelta(days=29)
        acumulado = 0.0; pico = 0.0; dd_max_janela = 0.0; dias_op = 0; ntrades = 0
        aprovou = False
        for j in range(i, len(dts)):
            dj = dts[j]
            if dj > fim: break
            acumulado += pnl_dia[datas_ord[j]]; dias_op += 1
            ntrades += n_trades_dia[datas_ord[j]]
            pico = max(pico, acumulado); dd_max_janela = max(dd_max_janela, pico - acumulado)
            if dd_max_janela > dd_limite: break
            if acumulado >= meta and dias_op >= min_dias:
                aprovou = True; break
        if aprovou: aprovadas += 1
        pnls_janela.append(acumulado); dds_janela.append(dd_max_janela); trades_janela.append(ntrades)

    total = len(dts)
    return {'n_janelas': total, 'aprovadas': aprovadas, 'taxa': aprovadas/total*100 if total else 0,
            'pnl_med': sum(pnls_janela)/total if total else 0,
            'dd_med': sum(dds_janela)/total if total else 0,
            'dd_abs': max(dds_janela) if dds_janela else 0,
            'trades_med': sum(trades_janela)/total if total else 0}


def main():
    bars = dp.carregar_1min(dp.PASTA_DADOS)
    print(f"{len(bars):,} candles carregados\n")

    print("Recalculando os quartis de ATR JA estabelecidos (nao reotimizado) ...")
    q1, q2, q3 = calcula_quartis_atr(bars)
    print(f"  Cortes: Q1={q1:.2f} | Q2={q2:.2f} | Q3={q3:.2f}\n")

    configs = [
        ('BASELINE (todos os sinais)', None),
        (f'Q1 (ATR < {q1:.1f}, 0-25%)', (0.0, q1)),
        (f'Q2 ({q1:.1f} <= ATR < {q2:.1f}, 25-50%)', (q1, q2)),
        (f'Q3 ({q2:.1f} <= ATR < {q3:.1f}, 50-75%)', (q2, q3)),
        (f'Q4 (ATR >= {q3:.1f}, 75-100%)', (q3, 999999.0)),
    ]

    resultados = {}
    for nome, filtro in configs:
        print(f"Simulando: {nome} ...")
        trades = simula(bars, filtro)
        r = resume_completo(trades)
        j = simula_janelas_30d(trades)
        resultados[nome] = (r, j, trades)

    print("\n" + "=" * 130)
    print("TABELA 1 — METRICAS POR TRADE")
    print("=" * 130)
    print(f"{'Config':<38}{'N':<6}{'WR%':<7}{'Ratio':<7}{'PF':<6}{'Exp$':<8}{'GanhoM':<9}{'PerdaM':<9}{'PnL':<10}{'DD$':<9}{'MaxSeq'}")
    for nome, filtro in configs:
        r = resultados[nome][0]
        print(f"{nome:<38}{r['n']:<6}{r['wr']:<7.1f}{r['ratio']:<7.2f}{r['pf']:<6.2f}${r['exp']:<7.1f}"
              f"${r['gm']:<8.1f}${r['pm']:<8.1f}${r['pnl']:<9.1f}${r['dd']:<8.1f}{r['maxseq']}")

    print("\n" + "=" * 130)
    print("TABELA 2 — MFE/MAE POR TRADE (medido dentro do proprio trade, ate a saida)")
    print("=" * 130)
    print(f"{'Config':<38}{'MFEmed':<10}{'MFEmediana':<12}{'MAEmed':<10}{'MAEmediana'}")
    for nome, filtro in configs:
        r = resultados[nome][0]
        print(f"{nome:<38}{r['mfe_med']:<10.2f}{r['mfe_mediana']:<12.2f}{r['mae_med']:<10.2f}{r['mae_mediana']:.2f}")

    print("\n" + "=" * 130)
    print("TABELA 3 — PnL POR DIA DE CALENDARIO")
    print("=" * 130)
    print(f"{'Config':<38}{'NDias':<8}{'DiasPos':<9}{'DiasNeg':<9}{'PnLMedDia':<12}{'MaiorGanhoDia':<15}{'MaiorPerdaDia'}")
    for nome, filtro in configs:
        r = resultados[nome][0]
        print(f"{nome:<38}{r['n_dias']:<8}{r['dias_pos']:<9}{r['dias_neg']:<9}${r['pnl_med_dia']:<11.1f}"
              f"${r['maior_ganho_dia']:<14.1f}${r['maior_perda_dia']:.1f}")

    print("\n" + "=" * 130)
    print("TABELA 4 — APROVACAO APEX EM JANELAS DE 30 DIAS CORRIDOS (a mais importante)")
    print("=" * 130)
    print(f"{'Config':<38}{'NJanelas':<10}{'Aprovadas':<11}{'Taxa%':<8}{'PnLMedJan':<11}{'DDmedJan':<10}{'DDabsJan':<10}{'TradesMedJan'}")
    for nome, filtro in configs:
        j = resultados[nome][1]
        print(f"{nome:<38}{j['n_janelas']:<10}{j['aprovadas']:<11}{j['taxa']:<8.1f}${j['pnl_med']:<10.1f}"
              f"${j['dd_med']:<9.1f}${j['dd_abs']:<9.1f}{j['trades_med']:.1f}")

    csvp = os.path.join(os.path.dirname(__file__), 'experimento_final_atr.csv')
    with open(csvp, 'w', newline='', encoding='utf-8') as f:
        campos = ['config','n','wr','ratio','pf','exp','gm','pm','pnl','dd','maxseq',
                   'mfe_med','mfe_mediana','mae_med','mae_mediana','n_dias','dias_pos','dias_neg',
                   'pnl_med_dia','maior_ganho_dia','maior_perda_dia',
                   'n_janelas','aprovadas','taxa','pnl_med_jan','dd_med_jan','dd_abs_jan','trades_med_jan']
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for nome, filtro in configs:
            r, j, _ = resultados[nome]
            w.writerow({'config': nome, **{k: r[k] for k in r if k in campos},
                        'n_janelas': j['n_janelas'], 'aprovadas': j['aprovadas'], 'taxa': j['taxa'],
                        'pnl_med_jan': j['pnl_med'], 'dd_med_jan': j['dd_med'], 'dd_abs_jan': j['dd_abs'],
                        'trades_med_jan': j['trades_med']})
    print(f"\nCSV: {csvp}")

if __name__ == '__main__':
    main()
