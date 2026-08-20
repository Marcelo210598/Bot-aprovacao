#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RESULTADO MES A MES (20/08) — pedido do Marcelo: em vez do "ciclo infinito que
reseta quando aprova ou estoura" (usado nos outros sweeps), simular EXATAMENTE
o que aconteceria comprando uma avaliacao $25K nova no dia 1 de CADA mes do
calendario: acompanha o mes inteiro e registra se BATEU $1.500 (aprovou),
ESTOUROU o DD $1.000, ou terminou o mes SEM DECIDIR (incompleto).

Diferenca importante de modelagem: o "conhecimento" do bot (nivel do dia
anterior, EMAs, FVGs abertos) continua acumulando dia a dia, SEM resetar no
inicio do mes -- so o DINHEIRO da conta (realizado/pico/dias operados) reseta,
como se fosse trocar de avaliacao mantendo o bot rodando. Assim que um mes
decide (aprova ou estoura), o bot PARA de abrir trade novo ate o mes seguinte
comecar (1 tentativa por mes, igual ao produto real: comprou, decidiu, acabou).

Reaproveita os sinais e o motor de gestao de backtest/run_estrategias_comparativo.py
(SL 12,5/BE 3,75-2,5/trailing 1,75/alvo 60, DD real $1000, MaxTradesDia=12,
slippage 2 ticks, 5 MNQ).
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from run_estrategias_comparativo import (
    carregar, domingo_ranges, calcula_indicadores, FONTES_DISPONIVEIS, Estado,
    MNQ_PV, RT_PER, N_CONTR, TICK, PTS_SL, PTS_BE_TRIG, PTS_BE_LOCK, PTS_TRAIL, TP,
    ENTRADA_INI, ENTRADA_FIM, FLATTEN, ORB_FIM, SLIP_BASE, META, DD, STOP_DIA, MAX_TRADES,
    MIN_DIAS, mins,
)


def roda_mes_a_mes(bars, dom_map, fontes, ind=None):
    """1 passada pelo ano inteiro, resultado por mes-calendario. Retorna lista de
    dicts: {'mes': 'YYYY-MM', 'status': 'APROVOU'|'ESTOUROU'|'INCOMPLETO',
    'dia_evento': 'YYYY-MM-DD' ou None, 'pnl_final': float, 'dias_operados': int,
    'trades': int, 'pico': float}."""
    pv = MNQ_PV * N_CONTR; rt = RT_PER * N_CONTR; slip = SLIP_BASE * TICK
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False; origem = ''
    realized = 0.0
    r_ini = 0.0; pico = 0.0; dias = set(); trades_mes = 0
    st = Estado()
    mes_atual = None; mes_concluido = False
    resultados = []

    def fecha(p):
        nonlocal pos, realized
        if pos == 0: return
        realized += ((p - entry) * pos - 2 * slip) * pv - rt
        pos = 0

    for i, b in enumerate(bars):
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d'); wd = dt.weekday()
        mes_key = dt.strftime('%Y-%m')

        if mes_key != mes_atual:
            if mes_atual is not None:
                if pos != 0: fecha(b['c'])
                pr_final = realized - r_ini
                if not resultados or resultados[-1]['mes'] != mes_atual:
                    resultados.append({'mes': mes_atual, 'status': 'INCOMPLETO', 'dia_evento': None,
                                        'pnl_final': pr_final, 'dias_operados': len(dias),
                                        'trades': trades_mes, 'pico': pico})
            mes_atual = mes_key; mes_concluido = False
            r_ini = realized; pico = 0.0; dias = set(); trades_mes = 0

        if d != st.dia:
            if st.cur_hi is not None: st.pd_hi, st.pd_lo = st.cur_hi, st.cur_lo
            st.dia = d; st.cur_hi = st.cur_lo = None
            st.seg_hoje = dom_map[d] if (dom_map and wd == 0 and d in dom_map) else None
            st.orb_hi = st.orb_lo = None; st.orb_pronto = False
            st.fvg_bull = []; st.fvg_bear = []
        if ENTRADA_INI <= m < 16*60:
            st.cur_hi = b['h'] if st.cur_hi is None else max(st.cur_hi, b['h'])
            st.cur_lo = b['l'] if st.cur_lo is None else min(st.cur_lo, b['l'])
        if ENTRADA_INI <= m < ORB_FIM:
            st.orb_hi = b['h'] if st.orb_hi is None else max(st.orb_hi, b['h'])
            st.orb_lo = b['l'] if st.orb_lo is None else min(st.orb_lo, b['l'])
        elif m >= ORB_FIM:
            st.orb_pronto = True

        if pos != 0:
            saiu = False
            if pos > 0:
                if b['l'] <= stop: fecha(stop); saiu = True
                elif b['h'] >= target: fecha(target); saiu = True
            else:
                if b['h'] >= stop: fecha(stop); saiu = True
                elif b['l'] <= target: fecha(target); saiu = True
            if not saiu and pos != 0:
                if pos > 0:
                    fav = max(fav, b['h'])
                    if not be_done and (fav - entry) >= PTS_BE_TRIG:
                        stop = max(stop, entry + PTS_BE_LOCK); be_done = True
                    if be_done: stop = max(stop, fav - PTS_TRAIL)
                else:
                    fav = min(fav, b['l'])
                    if not be_done and (entry - fav) >= PTS_BE_TRIG:
                        stop = min(stop, entry - PTS_BE_LOCK); be_done = True
                    if be_done: stop = min(stop, fav + PTS_TRAIL)

        pr = realized - r_ini
        ua = uf = 0.0
        if pos > 0: ua = (b['l']-entry)*pv; uf = (b['h']-entry)*pv
        elif pos < 0: ua = (entry-b['h'])*pv; uf = (entry-b['l'])*pv
        if pr + uf > pico: pico = pr + uf

        if not mes_concluido:
            if pr + ua <= pico - DD:
                fecha(b['c']); mes_concluido = True
                resultados.append({'mes': mes_atual, 'status': 'ESTOUROU', 'dia_evento': d,
                                    'pnl_final': realized - r_ini, 'dias_operados': len(dias),
                                    'trades': trades_mes, 'pico': pico})
            elif pr >= META and len(dias) >= MIN_DIAS:
                fecha(b['c']); mes_concluido = True
                resultados.append({'mes': mes_atual, 'status': 'APROVOU', 'dia_evento': d,
                                    'pnl_final': realized - r_ini, 'dias_operados': len(dias),
                                    'trades': trades_mes, 'pico': pico})

        if m >= FLATTEN and pos != 0:
            fecha(b['c'])
        if not mes_concluido and pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
            lado = 0; fonte_disp = ''
            for f in fontes:
                fn = FONTES_DISPONIVEIS[f]
                lado = fn(bars, i, st, dom_map, ind) if f == 'EMAV' else fn(bars, i, st, dom_map)
                if lado != 0: fonte_disp = f; break
            if lado != 0:
                entry = b['c']; pos = lado; fav = entry; be_done = False; origem = fonte_disp
                stop = entry - lado * PTS_SL; target = entry + lado * TP
                dias.add(d); trades_mes += 1

    if mes_atual is not None and (not resultados or resultados[-1]['mes'] != mes_atual):
        pr_final = realized - r_ini
        resultados.append({'mes': mes_atual, 'status': 'INCOMPLETO', 'dia_evento': None,
                            'pnl_final': pr_final, 'dias_operados': len(dias),
                            'trades': trades_mes, 'pico': pico})
    return resultados


def fmt_resultado(r):
    if r is None: return '—'
    simbolo = {'APROVOU': '✅', 'ESTOUROU': '💥', 'INCOMPLETO': '⬜'}[r['status']]
    if r['status'] == 'APROVOU':
        return f"{simbolo} +${r['pnl_final']:,.0f} (dia {r['dia_evento'][-2:]}, {r['trades']}t)"
    elif r['status'] == 'ESTOUROU':
        return f"{simbolo} ${r['pnl_final']:,.0f} (dia {r['dia_evento'][-2:]}, {r['trades']}t)"
    else:
        return f"{simbolo} ${r['pnl_final']:+,.0f} ({r['trades']}t, {r['dias_operados']}d)"


if __name__ == '__main__':
    print("Carregando NQ 1-min real..."); bars = carregar('NQ_dados')
    dom = domingo_ranges(bars)
    print("Calculando indicadores..."); ind = calcula_indicadores(bars)
    print(f"{len(bars):,} barras | {bars[0]['dt'].date()} -> {bars[-1]['dt'].date()}\n")

    combos = [
        ('REV',              ['REV']),
        ('ORB',              ['ORB']),
        ('EMAV',             ['EMAV']),
        ('ICT',              ['ICT']),
        ('REV+ORB',          ['REV', 'ORB']),
        ('REV+EMAV',         ['REV', 'EMAV']),
        ('REV+ICT',          ['REV', 'ICT']),
        ('REV+ORB+EMAV+ICT', ['REV', 'ORB', 'EMAV', 'ICT']),
    ]

    todos = {}
    for label, fontes in combos:
        print(f"Rodando {label}..."); todos[label] = roda_mes_a_mes(bars, dom, fontes, ind=ind)

    meses = sorted(set(r['mes'] for res in todos.values() for r in res))

    for label, _ in combos:
        print("\n" + "=" * 78)
        print(f"  {label}")
        print("=" * 78)
        por_mes = {r['mes']: r for r in todos[label]}
        n_aprov = n_est = n_inc = 0
        for mes in meses:
            r = por_mes.get(mes)
            print(f"  {mes}  {fmt_resultado(r)}")
            if r:
                if r['status'] == 'APROVOU': n_aprov += 1
                elif r['status'] == 'ESTOUROU': n_est += 1
                else: n_inc += 1
        print(f"  --- {n_aprov} aprovou / {n_est} estourou / {n_inc} incompleto "
              f"(de {n_aprov+n_est+n_inc} meses) ---")
