#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RENKO + MA vs REVERSAO — MESMA METODOLOGIA do resto do projeto:
"comprei uma avaliacao $25K nova, tenho ATE 30 dias corridos pra fazer $1.500
(min 7 dias operados) senao a conta expira; se estourar o DD de $1.000 tambem
acaba. Assim que decide, comeco outra na hora." (motor identico ao
run_janela_30d.py)

Gestao de saida: a MESMA de tudo no projeto (SL 12,5 / BE 3,75->2,5 / trail 1,75
/ alvo 60pt), DD real $1000, MaxTradesDia=12, slippage 2 ticks, 5 MNQ, janela
9h30-16h ET. So muda o SINAL DE ENTRADA.

Fontes:
  REV   = reversao PDH/PDL (producao)
  RENKO = cruzamento de MA nas closes de tijolo de Renko (o "bot MA em Renko" que
          o Marcelo viu na Flash Funded), com gate opcional de N tijolos da mesma
          cor. Tijolo reconstruido das barras de 1min (ver aviso em renko.py).

Roda cada uma sozinha, mesclada (REV+RENKO: a que sinalizar primeiro na barra
abre; MaxTradesDia dividido), e OOS (1a metade x 2a metade do dado).
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from run_estrategias_comparativo import (
    carregar, domingo_ranges, Estado, sinal_reversao,
    MNQ_PV, RT_PER, N_CONTR, TICK, PTS_SL, PTS_BE_TRIG, PTS_BE_LOCK, PTS_TRAIL, TP,
    ENTRADA_INI, ENTRADA_FIM, FLATTEN, SLIP_BASE, META, DD, STOP_DIA, MAX_TRADES,
    MIN_DIAS, mins,
)
from renko import estado_renko

JANELA_DIAS = 30


def make_sinal_renko(rk_state, gate_same=0, exige_dir=True):
    """Gatilho de entrada Renko: no bar em que o regime da MA virou (cross_up/dn).
    gate_same: exige que os ultimos N tijolos sejam da mesma cor (0 = desliga).
    exige_dir: exige que a direcao do ultimo tijolo bata com o lado do sinal."""
    def fn(bars, i, st, dom_map, ind=None):
        s = rk_state[i]
        if s['ma'] is None or s['n_bricks'] < max(gate_same, 2):
            return 0
        lado = 0
        if s['cross_up']: lado = 1
        elif s['cross_dn']: lado = -1
        if lado == 0: return 0
        if exige_dir and s['dir'] != lado: return 0
        return lado
    return fn


def roda_30d(bars, dom_map, fontes, rk_state=None, rk_kw=None,
             renko_exit=False):
    """fontes: lista de 'REV' e/ou 'RENKO'. renko_exit: alem do SL/BE/trail/alvo,
    fecha a posicao se o regime da MA de Renko virar contra (so faz sentido com
    RENKO na lista)."""
    rk_kw = rk_kw or {}
    sinal_rk = make_sinal_renko(rk_state, **rk_kw) if rk_state is not None else None
    FN = {'REV': lambda bars, i, st: sinal_reversao(bars, i, st, dom_map),
          'RENKO': lambda bars, i, st: sinal_rk(bars, i, st, dom_map)}

    pv = MNQ_PV * N_CONTR; rt = RT_PER * N_CONTR; slip = SLIP_BASE * TICK
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False; origem = ''
    realized = 0.0
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None; trades_janela = 0
    pnl_d0 = 0.0; block = False; dia_k = None; trades_hoje = 0
    st = Estado()
    resultados = []; trades_all = []

    def fecha(p):
        nonlocal pos, realized
        if pos == 0: return
        g = ((p - entry) * pos - 2 * slip) * pv - rt
        realized += g; trades_all.append(g); pos = 0

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
        if ENTRADA_INI <= m < 16*60:
            st.cur_hi = b['h'] if st.cur_hi is None else max(st.cur_hi, b['h'])
            st.cur_lo = b['l'] if st.cur_lo is None else min(st.cur_lo, b['l'])
        if d != dia_k:
            dia_k = d; pnl_d0 = realized; block = False; trades_hoje = 0

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
            if not saiu and pos != 0 and renko_exit and rk_state is not None:
                s = rk_state[i]
                if (pos > 0 and s['cross_dn']) or (pos < 0 and s['cross_up']):
                    fecha(b['c']); saiu = True

        pr = realized - r_ini
        ua = uf = 0.0
        if pos > 0: ua = (b['l']-entry)*pv; uf = (b['h']-entry)*pv
        elif pos < 0: ua = (entry-b['h'])*pv; uf = (entry-b['l'])*pv
        if pr + uf > pico: pico = pr + uf
        if STOP_DIA > 0 and (realized - pnl_d0 + ua) <= -STOP_DIA:
            block = True
            if pos != 0: fecha(b['c'])

        decidiu = False
        if pr + ua <= pico - DD:
            fecha(b['c'])
            resultados.append({'status': 'ESTOUROU', 'dias_corridos': (dt - ini_aval).days,
                                'pnl_final': realized - r_ini, 'dias_operados': len(dias),
                                'trades': trades_janela})
            decidiu = True
        elif pr >= META and len(dias) >= MIN_DIAS:
            fecha(b['c'])
            resultados.append({'status': 'APROVOU', 'dias_corridos': (dt - ini_aval).days,
                                'pnl_final': realized - r_ini, 'dias_operados': len(dias),
                                'trades': trades_janela})
            decidiu = True
        elif (dt - ini_aval).days >= JANELA_DIAS:
            fecha(b['c'])
            resultados.append({'status': 'EXPIROU', 'dias_corridos': (dt - ini_aval).days,
                                'pnl_final': realized - r_ini, 'dias_operados': len(dias),
                                'trades': trades_janela})
            decidiu = True
        if decidiu: nova_tentativa(dt)

        if m >= FLATTEN and pos != 0: fecha(b['c'])
        lim_ok = (MAX_TRADES == 0 or trades_hoje < MAX_TRADES)
        if not block and lim_ok and pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
            lado = 0
            for f in fontes:
                lado = FN[f](bars, i, st)
                if lado != 0: break
            if lado != 0:
                entry = b['c']; pos = lado; fav = entry; be_done = False
                stop = entry - lado * PTS_SL; target = entry + lado * TP
                dias.add(d); trades_janela += 1; trades_hoje += 1

    return resultados, trades_all


def resume(res, trades):
    tot = len(res)
    ap = sum(1 for r in res if r['status'] == 'APROVOU')
    es = sum(1 for r in res if r['status'] == 'ESTOUROU')
    ex = sum(1 for r in res if r['status'] == 'EXPIROU')
    dias_ap = sorted(r['dias_corridos'] for r in res if r['status'] == 'APROVOU')
    dmed = dias_ap[len(dias_ap)//2] if dias_ap else 0
    n = len(trades); w = [t for t in trades if t > 0]
    gw = sum(w); gl = abs(sum(t for t in trades if t <= 0))
    wr = 100*len(w)/n if n else 0
    pf = gw/gl if gl > 0 else 99
    avgW = (gw/len(w)) if w else 0
    lo = [t for t in trades if t <= 0]
    avgL = (sum(lo)/len(lo)) if lo else 0
    return dict(tot=tot, ap=ap, es=es, ex=ex, taxa=100*ap/tot if tot else 0,
               dmed=dmed, n=n, wr=wr, pf=pf, avgW=avgW, avgL=avgL)


def linha(label, r):
    print(f"  {label:<34s} {r['taxa']:>4.0f}%  {r['ap']:>2}ap/{r['es']:>2}es/{r['ex']:>2}ex  "
          f"d{r['dmed']:<3} n={r['n']:<5} WR{r['wr']:>3.0f}% PF{r['pf']:>4.2f}  "
          f"gW{r['avgW']:>+5.0f} pL{r['avgL']:>+5.0f}")


if __name__ == '__main__':
    print("Carregando NQ 1min real..."); bars = carregar('NQ_dados')
    dom = domingo_ranges(bars)
    meio = len(bars)//2
    b1, b2 = bars[:meio], bars[meio:]
    dom1, dom2 = domingo_ranges(b1), domingo_ranges(b2)
    print(f"{len(bars):,} barras | {bars[0]['dt'].date()} -> {bars[-1]['dt'].date()}")
    print("motor: janela 30d corridos, retry imediato | SL12,5/BE3,75-2,5/trail1,75/alvo60 | "
          "DD$1000 | Max12/dia | slip 2t | 5 MNQ\n")

    H = f"  {'cenario':<34s} {'taxa':>5s}  {'ap/es/ex':>10s}  {'dmed':>4s} {'trades':>7s} {'WR':>5s} {'PF':>6s}  {'gW/pL':>11s}"

    print("="*104); print("  (0) BASELINE — reversao sozinha (tem que dar ~50%, sanity check)"); print("="*104)
    print(H); print("-"*104)
    linha('REV (producao)', resume(*roda_30d(bars, dom, ['REV'])))

    print("\n" + "="*104)
    print("  (1) RENKO + MA sozinho — varre tamanho de tijolo x periodo de MA x gate")
    print("      gestao PADRAO (SL/BE/trail/alvo iguais aos da reversao)")
    print("="*104); print(H); print("-"*104)
    combos = []
    for bp in (10, 15, 20, 25):
        for ma in (5, 10, 20):
            combos.append((bp, ma, 0))
        combos.append((bp, 10, 3))   # + gate 3 tijolos mesma cor
    cache = {}
    for bp, ma, gate in combos:
        key = (bp, ma)
        if key not in cache:
            cache[key] = estado_renko(bars, bp, ma_period=ma)
        rk = cache[key]
        r = resume(*roda_30d(bars, dom, ['RENKO'], rk_state=rk,
                             rk_kw=dict(gate_same=gate)))
        linha(f'RENKO brick{bp} ma{ma}' + (f' gate{gate}' if gate else ''), r)

    print("\n" + "="*104)
    print("  (2) RENKO + MA com SAIDA NATIVA (fecha no cruzamento contrario da MA)")
    print("="*104); print(H); print("-"*104)
    for bp, ma in [(15, 10), (20, 10), (25, 10), (20, 20)]:
        rk = cache.get((bp, ma)) or estado_renko(bars, bp, ma_period=ma)
        cache[(bp, ma)] = rk
        r = resume(*roda_30d(bars, dom, ['RENKO'], rk_state=rk, renko_exit=True))
        linha(f'RENKO brick{bp} ma{ma} +saida nativa', r)

    print("\n" + "="*104)
    print("  (3) MESCLA — reversao + Renko (a que disparar primeiro na barra)")
    print("="*104); print(H); print("-"*104)
    for bp, ma, gate in [(15, 10, 0), (20, 10, 0), (20, 10, 3), (25, 10, 0), (20, 20, 0)]:
        rk = cache.get((bp, ma)) or estado_renko(bars, bp, ma_period=ma)
        cache[(bp, ma)] = rk
        r = resume(*roda_30d(bars, dom, ['REV', 'RENKO'], rk_state=rk,
                             rk_kw=dict(gate_same=gate)))
        linha(f'REV + RENKO brick{bp} ma{ma}' + (f' gate{gate}' if gate else ''), r)

    print("\n" + "="*104)
    print("  (4) OOS — 1a metade x 2a metade (so os cenarios que interessam)")
    print("="*104)
    def oos(label, fontes, bp=None, ma=None, gate=0, rexit=False):
        rk1 = estado_renko(b1, bp, ma_period=ma) if bp else None
        rk2 = estado_renko(b2, bp, ma_period=ma) if bp else None
        r1 = resume(*roda_30d(b1, dom1, fontes, rk_state=rk1, rk_kw=dict(gate_same=gate), renko_exit=rexit))
        r2 = resume(*roda_30d(b2, dom2, fontes, rk_state=rk2, rk_kw=dict(gate_same=gate), renko_exit=rexit))
        print(f"  {label:<34s}  1a: {r1['ap']:>2}ap/{r1['es']:>2}es ({r1['taxa']:>3.0f}%) PF{r1['pf']:>4.2f}"
              f"   2a: {r2['ap']:>2}ap/{r2['es']:>2}es ({r2['taxa']:>3.0f}%) PF{r2['pf']:>4.2f}")
    oos('REV sozinho', ['REV'])
    oos('RENKO brick20 ma10', ['RENKO'], 20, 10)
    oos('RENKO brick25 ma10', ['RENKO'], 25, 10)
    oos('RENKO brick20 ma10 +saida nativa', ['RENKO'], 20, 10, rexit=True)
    oos('REV + RENKO brick20 ma10', ['REV', 'RENKO'], 20, 10)
    oos('REV + RENKO brick25 ma10', ['REV', 'RENKO'], 25, 10)
    print("="*104)
