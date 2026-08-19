#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FILTRO DE REGIME POR ADX (18/08/2026)

Testa a pista da pesquisa: so operar a estrategia atual (reversao em nivel
unico) em dias de regime LATERAL (ADX diario baixo), pulando dias de tendencia
forte (ADX alto) -- onde reversao tende a "levar atropelada".

ADX(14) diario, calculado com barras RTH (9h30-16h ET) agregadas por dia.
Usa o ADX conhecido ATE O FECHAMENTO DE ONTEM pra decidir se opera HOJE (sem
lookahead -- o valor de hoje so fecha as 16h, dado que so teriamos depois do
pregao). Motor de entrada/saida = o mesmo ja validado (1min, slippage 2 ticks,
SL 12,5/TP 60/BE 3,75-2,5/trail 1,75 -- config de producao).
"""
import sys, os, csv
from datetime import timedelta
sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp
import grid_trailing_alvo as gta

ANO_INICIO, ANO_FIM = '2025-06-11', '2026-06-11'


def bars_diarios_rth(bars1m):
    """Agrega barras de 1min em 1 OHLC por dia, so RTH (9h30-16h ET)."""
    dias = {}
    for b in bars1m:
        dt = b['dt']; d = dt.strftime('%Y-%m-%d'); m = dp.mins(dt)
        if not (dp.SESSAO_INICIO <= m < dp.ENTRADA_FIM):
            continue
        if d not in dias:
            dias[d] = {'o': b['o'], 'h': b['h'], 'l': b['l'], 'c': b['c']}
        else:
            dias[d]['h'] = max(dias[d]['h'], b['h'])
            dias[d]['l'] = min(dias[d]['l'], b['l'])
            dias[d]['c'] = b['c']
    datas = sorted(dias)
    return [{'data': d, **dias[d]} for d in datas]


def calcula_adx(dbars, periodo=14):
    """ADX(14) classico (Wilder), sobre barras diarias RTH. Retorna dict
    data -> adx (o ADX que fecha NAQUELE dia, so conhecido a partir do close)."""
    n = len(dbars)
    tr = [0.0] * n; plus_dm = [0.0] * n; minus_dm = [0.0] * n
    for i in range(1, n):
        h, l, c_prev = dbars[i]['h'], dbars[i]['l'], dbars[i - 1]['c']
        h_prev, l_prev = dbars[i - 1]['h'], dbars[i - 1]['l']
        tr[i] = max(h - l, abs(h - c_prev), abs(l - c_prev))
        up = h - h_prev; down = l_prev - l
        plus_dm[i] = up if (up > down and up > 0) else 0.0
        minus_dm[i] = down if (down > up and down > 0) else 0.0

    adx = [None] * n
    if n <= periodo * 2:
        return {dbars[i]['data']: None for i in range(n)}

    atr = sum(tr[1:periodo + 1])
    pdm = sum(plus_dm[1:periodo + 1])
    mdm = sum(minus_dm[1:periodo + 1])
    dx_list = []
    for i in range(periodo + 1, n):
        atr = atr - (atr / periodo) + tr[i]
        pdm = pdm - (pdm / periodo) + plus_dm[i]
        mdm = mdm - (mdm / periodo) + minus_dm[i]
        plus_di = 100 * pdm / atr if atr else 0.0
        minus_di = 100 * mdm / atr if atr else 0.0
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) else 0.0
        dx_list.append(dx)
        if len(dx_list) == periodo:
            adx[i] = sum(dx_list) / periodo
        elif len(dx_list) > periodo:
            adx[i] = (adx[i - 1] * (periodo - 1) + dx) / periodo
    return {dbars[i]['data']: adx[i] for i in range(n)}


def simula_com_filtro_regime(bars1m, adx_por_dia, modo, limiar):
    """modo: 'lateral' (so opera se ADX(ontem) < limiar) ou 'tendencia' (so
    opera se ADX(ontem) >= limiar) ou None (sem filtro)."""
    tol_pts = 20 * dp.TICK; MAX_DIST = 15.0
    SL = 12.5; TP = 60.0; BE_TRIG = 3.75; BE_LOCK = 2.5; TRAIL = 1.75
    SLIP = 2 * dp.TICK
    STOP_DIA_PT = 750.0 / (2.0 * 5); MAX_TRADES_DIA = 12
    pv = 2.0 * 5; RT = 1.20 * 5

    cur_hi = cur_lo = None; pd_hi = pd_lo = None; dia = None
    on_key = None; on_hi = on_lo = None
    pos = 0; entry = stop = alvo = fav = 0.0; be_feito = False
    pnl_dia0 = 0.0; realizado = 0.0; bloqueado_hoje = False
    trades = []; adx_ontem = None

    def fecha(preco, d):
        nonlocal pos, realizado
        preco_real = preco - SLIP if pos > 0 else preco + SLIP
        pts = (preco_real - entry) if pos > 0 else (entry - preco_real)
        usd = pts * pv - RT
        realizado += usd
        trades.append({'pnl_usd': usd, 'data': d})
        pos = 0

    for b in bars1m:
        dt = b['dt']; d = dt.strftime('%Y-%m-%d'); m = dp.mins(dt); dow = dt.weekday()
        em_sessao = dp.SESSAO_INICIO <= m < dp.ENTRADA_FIM
        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = b['h'] if em_sessao else None; cur_lo = b['l'] if em_sessao else None
            bloqueado_hoje = False; pnl_dia0 = realizado
            # ADX conhecido ANTES de hoje = o ADX que fechou ontem (ultimo dia < d no dict)
            adx_ontem = adx_por_dia.get(d, None)  # ja vem pre-calculado como "ADX conhecido no inicio de d"
        elif em_sessao:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
        chave_seg = None
        if dow == 6 and m >= dp.DOM_NOITE_INICIO: chave_seg = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
        elif dow == 0 and m < dp.SESSAO_INICIO: chave_seg = d
        if chave_seg is not None:
            if chave_seg != on_key: on_key, on_hi, on_lo = chave_seg, b['h'], b['l']
            else: on_hi = max(on_hi, b['h']); on_lo = min(on_lo, b['l'])
        if not (ANO_INICIO <= d <= ANO_FIM): continue

        if pos != 0:
            saiu = False
            if pos > 0:
                if b['l'] <= stop: fecha(stop, d); saiu = True
                elif b['h'] >= alvo: fecha(alvo, d); saiu = True
            else:
                if b['h'] >= stop: fecha(stop, d); saiu = True
                elif b['l'] <= alvo: fecha(alvo, d); saiu = True
            if not saiu:
                if pos > 0:
                    fav = max(fav, b['h'])
                    if not be_feito and (fav - entry) >= BE_TRIG: stop = max(stop, entry + BE_LOCK); be_feito = True
                    if be_feito: stop = max(stop, fav - TRAIL)
                else:
                    fav = min(fav, b['l'])
                    if not be_feito and (entry - fav) >= BE_TRIG: stop = min(stop, entry - BE_LOCK); be_feito = True
                    if be_feito: stop = min(stop, fav + TRAIL)
            else:
                if STOP_DIA_PT > 0 and (realizado - pnl_dia0) <= -STOP_DIA_PT * pv: bloqueado_hoje = True
            continue

        if bloqueado_hoje or not (dp.SESSAO_INICIO <= m < dp.ENTRADA_FIM): continue
        if pd_hi is None or pd_lo is None: continue
        trades_hoje = sum(1 for t in trades if t['data'] == d)
        if MAX_TRADES_DIA > 0 and trades_hoje >= MAX_TRADES_DIA: continue

        # ---- FILTRO DE REGIME ----
        if modo == 'lateral' and (adx_ontem is None or adx_ontem >= limiar): continue
        if modo == 'tendencia' and (adx_ontem is None or adx_ontem < limiar): continue

        if dow == 0 and on_key == d and on_hi is not None and on_hi > 0: n_hi, n_lo = on_hi, on_lo
        else: n_hi, n_lo = pd_hi, pd_lo
        ev = dp.avalia_bar(b, n_hi, n_lo, tol_pts, MAX_DIST)
        if ev is not None and ev['cat'] == 'OPEROU':
            if ev['lado'] == 'SHORT':
                entry = b['c'] - SLIP; pos = -1; stop = entry + SL; alvo = entry - TP
            else:
                entry = b['c'] + SLIP; pos = 1; stop = entry - SL; alvo = entry + TP
            fav = entry; be_feito = False
    return trades


def resume(trades):
    wins = [t for t in trades if t['pnl_usd'] > 0]; losses = [t for t in trades if t['pnl_usd'] < 0]
    gm = sum(t['pnl_usd'] for t in wins) / len(wins) if wins else 0.0
    pm = sum(t['pnl_usd'] for t in losses) / len(losses) if losses else 0.0
    ratio = gm / abs(pm) if pm else float('inf')
    wr = len(wins) / len(trades) * 100 if trades else 0.0
    dias_op = len({t['data'] for t in trades})
    return {'n': len(trades), 'wr': wr, 'gm': gm, 'pm': pm, 'ratio': ratio,
            'pnl': sum(t['pnl_usd'] for t in trades), 'dias_op': dias_op}


def main():
    print("Carregando dados ...")
    bars1m = dp.carregar_1min(dp.PASTA_DADOS)
    print(f"  {len(bars1m):,} candles de 1min\n")

    dbars = bars_diarios_rth(bars1m)
    print(f"{len(dbars)} dias uteis com RTH completo")
    adx_fecha_hoje = calcula_adx(dbars, periodo=14)

    # ADX "conhecido no INICIO do dia D" = ADX que fechou no dia ANTERIOR
    datas_ordenadas = [db['data'] for db in dbars]
    adx_por_dia = {}
    for i, d in enumerate(datas_ordenadas):
        if i == 0:
            adx_por_dia[d] = None
        else:
            adx_por_dia[d] = adx_fecha_hoje.get(datas_ordenadas[i - 1])

    validos = [v for v in adx_por_dia.values() if v is not None]
    validos.sort()
    nn = len(validos)
    print(f"ADX(14) diario calculado -- {nn} dias validos. "
          f"p25={validos[nn//4]:.1f} mediana={validos[nn//2]:.1f} p75={validos[3*nn//4]:.1f}\n")

    print("=" * 100)
    print("BASELINE (sem filtro de regime)")
    print("=" * 100)
    tr_base = simula_com_filtro_regime(bars1m, adx_por_dia, None, 0)
    r_base = resume(tr_base)
    print(f"Trades={r_base['n']} DiasOp={r_base['dias_op']} WR={r_base['wr']:.1f}% "
          f"GanhoMed=${r_base['gm']:.1f} PerdaMed=${r_base['pm']:.1f} Ratio={r_base['ratio']:.2f} "
          f"PnL=${r_base['pnl']:.1f}")

    print("\n" + "=" * 100)
    print("SO OPERA EM DIA LATERAL (ADX de ontem < limiar)")
    print("=" * 100)
    print(f"{'Limiar':<9}{'Trades':<8}{'DiasOp':<8}{'WR%':<7}{'GanhoMed':<11}{'PerdaMed':<11}{'Ratio':<7}{'PnL'}")
    linhas = []
    for lim in [15, 18, 20, 22, 25, 30]:
        tr = simula_com_filtro_regime(bars1m, adx_por_dia, 'lateral', lim)
        r = resume(tr); r['limiar'] = lim; r['modo'] = 'lateral'
        print(f"{lim:<9}{r['n']:<8}{r['dias_op']:<8}{r['wr']:<7.1f}${r['gm']:<10.1f}${r['pm']:<10.1f}"
              f"{r['ratio']:<7.2f}${r['pnl']:.1f}")
        linhas.append(r)

    print("\n" + "=" * 100)
    print("SO OPERA EM DIA DE TENDENCIA (ADX de ontem >= limiar) -- controle/sanity check")
    print("=" * 100)
    print(f"{'Limiar':<9}{'Trades':<8}{'DiasOp':<8}{'WR%':<7}{'GanhoMed':<11}{'PerdaMed':<11}{'Ratio':<7}{'PnL'}")
    for lim in [20, 25, 30]:
        tr = simula_com_filtro_regime(bars1m, adx_por_dia, 'tendencia', lim)
        r = resume(tr); r['limiar'] = lim; r['modo'] = 'tendencia'
        print(f"{lim:<9}{r['n']:<8}{r['dias_op']:<8}{r['wr']:<7.1f}${r['gm']:<10.1f}${r['pm']:<10.1f}"
              f"{r['ratio']:<7.2f}${r['pnl']:.1f}")
        linhas.append(r)

    csv_path = os.path.join(os.path.dirname(__file__), 'filtro_adx.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        campos = ['modo', 'limiar', 'n', 'dias_op', 'wr', 'gm', 'pm', 'ratio', 'pnl']
        w = csv.DictWriter(f, fieldnames=campos); w.writeheader()
        for l in linhas: w.writerow({k: l.get(k) for k in campos})
    print(f"\nBaseline p/ comparar: PnL=${r_base['pnl']:.1f} em {r_base['n']} trades ({r_base['dias_op']} dias)")
    print(f"CSV: {csv_path}")


if __name__ == '__main__':
    main()
