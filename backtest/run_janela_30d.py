#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JANELA ROLANTE DE 30 DIAS (20/08) — o meio-termo mais realista entre os dois
testes anteriores:
  - `run_estrategias_comparativo.py` (ciclo infinito): reinicia na hora apos
    aprovar/estourar, mas SEM limite de tempo -> superestima (deixa ciclo
    demorar 40+ dias e ainda contar como aprovado).
  - `run_mes_a_mes.py` (mes calendario): tem limite de 30 dias, mas so
    reinicia no dia 1 do mes seguinte -> desperdica dias depois de um estouro
    cedo no mes, subestima.

Aqui: cada tentativa comeca com conta nova (like comprar uma avaliacao $25K),
tem ATE 30 DIAS CORRIDOS pra decidir. Se aprovar ou estourar, a proxima
tentativa comeca IMEDIATAMENTE (proximo bar), sem esperar nada. Se passar 30
dias sem decidir, conta como EXPIROU (nao aprovou) e tambem reinicia na hora.
Isso e' o numero mais correto pra "quantas avaliacoes eu preciso comprar por
ano, e quantas aprovam de verdade".
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from run_estrategias_comparativo import (
    carregar, domingo_ranges, calcula_indicadores, FONTES_DISPONIVEIS, Estado,
    MNQ_PV, RT_PER, N_CONTR, TICK, PTS_SL, PTS_BE_TRIG, PTS_BE_LOCK, PTS_TRAIL, TP,
    ENTRADA_INI, ENTRADA_FIM, FLATTEN, ORB_FIM, SLIP_BASE, META, DD, MIN_DIAS, mins,
)

JANELA_DIAS = 30


def roda_janela_30d(bars, dom_map, fontes, ind=None, be_lock_frac=None,
                     parcial_pts=None, parcial_qtd=4):
    """be_lock_frac: None = BE-lock fixo (bot 1/baseline). 0.75 = proporcional
    (bot 2, ja validado em Replay). parcial_pts: None = sem saida parcial;
    X = saida parcial 4+1 no bot 2 completo (gatilho testado a parte, ja que
    nunca disparou de verdade em ~20 dias de Replay real)."""
    pv = MNQ_PV * N_CONTR; rt = RT_PER * N_CONTR; slip = SLIP_BASE * TICK
    qtd_atual = N_CONTR; parcial_feita = False
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False
    realized = 0.0
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None; trades_janela = 0
    st = Estado()
    resultados = []

    def fecha(p):
        nonlocal pos, realized, qtd_atual
        if pos == 0 or qtd_atual == 0: return
        pv_ = MNQ_PV * qtd_atual; rt_ = RT_PER * qtd_atual
        realized += ((p - entry) * pos - 2 * slip) * pv_ - rt_
        pos = 0; qtd_atual = 0

    def fecha_parcial(qtd, p):
        nonlocal realized, qtd_atual
        if qtd <= 0 or qtd_atual < qtd: return
        pv_ = MNQ_PV * qtd; rt_ = RT_PER * qtd
        realized += ((p - entry) * pos - 2 * slip) * pv_ - rt_
        qtd_atual -= qtd

    def nova_tentativa(dt):
        nonlocal r_ini, pico, dias, ini_aval, trades_janela
        r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt; trades_janela = 0

    for i, b in enumerate(bars):
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d'); wd = dt.weekday()
        if ini_aval is None: nova_tentativa(dt)

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

            if not saiu and pos != 0 and parcial_pts and not parcial_feita and qtd_atual > parcial_qtd:
                alvo_parcial = entry + pos * parcial_pts
                tocou = (pos > 0 and b['h'] >= alvo_parcial) or (pos < 0 and b['l'] <= alvo_parcial)
                if tocou:
                    parcial_feita = True
                    fecha_parcial(parcial_qtd, alvo_parcial)

            if not saiu and pos != 0:
                if pos > 0:
                    fav = max(fav, b['h'])
                    if not be_done and (fav - entry) >= PTS_BE_TRIG:
                        be_done = True
                        lock = (fav - entry) * be_lock_frac if be_lock_frac else PTS_BE_LOCK
                        stop = max(stop, entry + lock)
                    if be_done:
                        lock = (fav - entry) * be_lock_frac if be_lock_frac else PTS_BE_LOCK
                        stop = max(stop, max(entry + lock, fav - PTS_TRAIL))
                else:
                    fav = min(fav, b['l'])
                    if not be_done and (entry - fav) >= PTS_BE_TRIG:
                        be_done = True
                        lock = (entry - fav) * be_lock_frac if be_lock_frac else PTS_BE_LOCK
                        stop = min(stop, entry - lock)
                    if be_done:
                        lock = (entry - fav) * be_lock_frac if be_lock_frac else PTS_BE_LOCK
                        stop = min(stop, min(entry - lock, fav + PTS_TRAIL))

        pr = realized - r_ini
        ua = uf = 0.0
        if pos > 0: ua = (b['l']-entry)*MNQ_PV*qtd_atual; uf = (b['h']-entry)*MNQ_PV*qtd_atual
        elif pos < 0: ua = (entry-b['h'])*MNQ_PV*qtd_atual; uf = (entry-b['l'])*MNQ_PV*qtd_atual
        if pr + uf > pico: pico = pr + uf

        decidiu = False
        if pr + ua <= pico - DD:
            fecha(b['c'])
            resultados.append({'status': 'ESTOUROU', 'inicio': ini_aval, 'fim': dt,
                                'dias_corridos': (dt - ini_aval).days, 'pnl_final': realized - r_ini,
                                'dias_operados': len(dias), 'trades': trades_janela})
            decidiu = True
        elif pr >= META and len(dias) >= MIN_DIAS:
            fecha(b['c'])
            resultados.append({'status': 'APROVOU', 'inicio': ini_aval, 'fim': dt,
                                'dias_corridos': (dt - ini_aval).days, 'pnl_final': realized - r_ini,
                                'dias_operados': len(dias), 'trades': trades_janela})
            decidiu = True
        elif (dt - ini_aval).days >= JANELA_DIAS:
            fecha(b['c'])
            resultados.append({'status': 'EXPIROU', 'inicio': ini_aval, 'fim': dt,
                                'dias_corridos': (dt - ini_aval).days, 'pnl_final': realized - r_ini,
                                'dias_operados': len(dias), 'trades': trades_janela})
            decidiu = True

        if decidiu:
            nova_tentativa(dt)

        if m >= FLATTEN and pos != 0:
            fecha(b['c'])
        if pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
            lado = 0
            for f in fontes:
                fn = FONTES_DISPONIVEIS[f]
                lado = fn(bars, i, st, dom_map, ind) if f == 'EMAV' else fn(bars, i, st, dom_map)
                if lado != 0: break
            if lado != 0:
                entry = b['c']; pos = lado; fav = entry; be_done = False
                qtd_atual = N_CONTR; parcial_feita = False
                stop = entry - lado * PTS_SL; target = entry + lado * TP
                dias.add(d); trades_janela += 1

    # tentativa em andamento no fim do dado: nao conta (dado incompleto, nao decidiu)
    return resultados


if __name__ == '__main__':
    print("Carregando NQ 1-min real..."); bars = carregar('NQ_dados')
    dom = domingo_ranges(bars)
    print("Calculando indicadores..."); ind = calcula_indicadores(bars)
    print(f"{len(bars):,} barras | {bars[0]['dt'].date()} -> {bars[-1]['dt'].date()} | "
          f"janela de {JANELA_DIAS} dias corridos, retry imediato\n")

    print(f"  {'estrategia':>28s} {'tentativas':>10s} {'aprovou':>8s} {'estourou':>9s} {'expirou':>8s} "
          f"{'taxa':>6s} {'d.med aprov':>12s}")
    print("-" * 100)

    def roda(label, fontes, **kw):
        res = roda_janela_30d(bars, dom, fontes, ind=ind, **kw)
        tot = len(res)
        n_ap = sum(1 for r in res if r['status'] == 'APROVOU')
        n_es = sum(1 for r in res if r['status'] == 'ESTOUROU')
        n_ex = sum(1 for r in res if r['status'] == 'EXPIROU')
        dias_ap = sorted(r['dias_corridos'] for r in res if r['status'] == 'APROVOU')
        dmed = dias_ap[len(dias_ap)//2] if dias_ap else 0
        taxa = 100*n_ap/tot if tot else 0
        print(f"  {label:>28s} {tot:>10} {n_ap:>8} {n_es:>9} {n_ex:>8} {taxa:>5.0f}% {dmed:>11}d")

    print("  -- BOT 1 vs BOT 2 (mesma entrada, so muda a gestao de saida) --")
    roda('BOT 1 (baseline, sem nada)', ['REV'])
    roda('BOT 2 so BE-lock 0,75',      ['REV'], be_lock_frac=0.75)
    roda('BOT 2 completo (+parcial20)', ['REV'], be_lock_frac=0.75, parcial_pts=20.0)
    print("-" * 100)
    print("  -- outras estrategias, sozinhas e mescladas com a REVERSAO (bot 1) --")
    for label, fontes in [
        ('ORB', ['ORB']), ('EMAV', ['EMAV']), ('ICT', ['ICT']),
        ('REV+ORB', ['REV', 'ORB']), ('REV+EMAV', ['REV', 'EMAV']),
        ('REV+ICT', ['REV', 'ICT']), ('REV+ORB+EMAV+ICT', ['REV', 'ORB', 'EMAV', 'ICT']),
    ]:
        roda(label, fontes)
    print("-" * 100)
