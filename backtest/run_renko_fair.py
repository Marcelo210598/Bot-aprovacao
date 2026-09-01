#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RENKO com GESTAO JUSTA (de tendencia) + medida direta de COMPLEMENTARIDADE.

Motivacao: no run_renko_30d.py o Renko rodou com a gestao da REVERSAO (SL 12,5 /
trail 1,75 / alvo 60) -- injusto pra uma estrategia de tendencia, que quer stop
largo e deixar correr. Aqui o Renko roda com:
  - stop = N tijolos (recoloca atras do tijolo), configuravel
  - sem alvo fixo (ou alvo largo) -- sai no cruzamento contrario da MA
E mede: nos dias em que a REVERSAO fica MUDA (0 trade), o Renko opera? da lucro?

Mesmo motor de aprovacao: janela 30d corridos, DD $1000, Max12/dia, slip 2t, 5 MNQ.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from run_estrategias_comparativo import (
    carregar, domingo_ranges, Estado, sinal_reversao,
    MNQ_PV, RT_PER, N_CONTR, TICK, ENTRADA_INI, ENTRADA_FIM, FLATTEN,
    SLIP_BASE, META, DD, STOP_DIA, MAX_TRADES, MIN_DIAS, mins,
    PTS_SL, TP, PTS_BE_TRIG, PTS_BE_LOCK, PTS_TRAIL,
)
from renko import estado_renko

JANELA = 30


def roda(bars, dom, modo, rk=None, brick=20, stop_bricks=2, tp_pts=0.0,
         trail_bricks=0, collect_days=False):
    """modo: 'REV' | 'RENKO' | 'MERGE'. Renko: stop atras de stop_bricks tijolos,
    tp_pts=0 -> sem alvo, sai no cross contrario; trail_bricks>0 -> trail por tijolo."""
    pv = MNQ_PV*N_CONTR; rt = RT_PER*N_CONTR; slip = SLIP_BASE*TICK
    pos = 0; entry = stop = target = 0.0; origem = ''; fav = 0.0; be_done = False
    realized = 0.0; r_ini = 0.0; pico = 0.0; dias = set(); ini = None
    pnl_d0 = 0.0; block = False; dia_k = None; th = 0
    st = Estado(); res = []; trades = []
    dias_rev = set(); dias_rk = set(); pnl_rk_solo = 0.0; n_rk_solo = 0
    rev_mudo_hoje = True

    def fecha(p, tag=''):
        nonlocal pos, realized, pnl_rk_solo, n_rk_solo
        if pos == 0: return
        g = ((p-entry)*pos - 2*slip)*pv - rt
        realized += g; trades.append(g)
        if origem == 'RENKO' and rev_mudo_hoje:
            pnl_rk_solo += g; n_rk_solo += 1
        pos = 0

    def nova(dt):
        nonlocal r_ini, pico, dias, ini; r_ini = realized; pico = 0.0; dias = set(); ini = dt

    for i, b in enumerate(bars):
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d'); wd = dt.weekday()
        if ini is None: nova(dt)
        if d != st.dia:
            if st.cur_hi is not None: st.pd_hi, st.pd_lo = st.cur_hi, st.cur_lo
            st.dia = d; st.cur_hi = st.cur_lo = None
            st.seg_hoje = dom[d] if (dom and wd == 0 and d in dom) else None
            rev_mudo_hoje = True
        if ENTRADA_INI <= m < 16*60:
            st.cur_hi = b['h'] if st.cur_hi is None else max(st.cur_hi, b['h'])
            st.cur_lo = b['l'] if st.cur_lo is None else min(st.cur_lo, b['l'])
        if d != dia_k:
            dia_k = d; pnl_d0 = realized; block = False; th = 0

        if pos != 0:
            saiu = False
            if pos > 0:
                if b['l'] <= stop: fecha(stop); saiu = True
                elif target and b['h'] >= target: fecha(target); saiu = True
            else:
                if b['h'] >= stop: fecha(stop); saiu = True
                elif target and b['l'] <= target: fecha(target); saiu = True
            if not saiu and pos != 0 and origem == 'REV':
                if pos > 0:
                    fav = max(fav, b['h'])
                    if not be_done and (fav-entry) >= PTS_BE_TRIG:
                        stop = max(stop, entry+PTS_BE_LOCK); be_done = True
                    if be_done: stop = max(stop, fav-PTS_TRAIL)
                else:
                    fav = min(fav, b['l'])
                    if not be_done and (entry-fav) >= PTS_BE_TRIG:
                        stop = min(stop, entry-PTS_BE_LOCK); be_done = True
                    if be_done: stop = min(stop, fav+PTS_TRAIL)
            if not saiu and pos != 0 and origem == 'RENKO' and rk is not None:
                s = rk[i]
                if trail_bricks and s['brick_close'] is not None:
                    if pos > 0:
                        stop = max(stop, s['brick_close'] - trail_bricks*brick)
                    else:
                        stop = min(stop, s['brick_close'] + trail_bricks*brick)
                if (pos > 0 and s['cross_dn']) or (pos < 0 and s['cross_up']):
                    fecha(b['c']); saiu = True

        pr = realized - r_ini
        ua = uf = 0.0
        if pos > 0: ua = (b['l']-entry)*pv; uf = (b['h']-entry)*pv
        elif pos < 0: ua = (entry-b['h'])*pv; uf = (entry-b['l'])*pv
        if pr+uf > pico: pico = pr+uf
        if STOP_DIA > 0 and (realized-pnl_d0+ua) <= -STOP_DIA:
            block = True
            if pos != 0: fecha(b['c'])
        decidiu = False
        if pr+ua <= pico-DD:
            fecha(b['c']); res.append(('ESTOUROU', (dt-ini).days)); decidiu = True
        elif pr >= META and len(dias) >= MIN_DIAS:
            fecha(b['c']); res.append(('APROVOU', (dt-ini).days)); decidiu = True
        elif (dt-ini).days >= JANELA:
            fecha(b['c']); res.append(('EXPIROU', (dt-ini).days)); decidiu = True
        if decidiu: nova(dt)

        if m >= FLATTEN and pos != 0: fecha(b['c'])
        if not block and th < MAX_TRADES and pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
            lado = 0; src = ''
            lr = sinal_reversao(bars, i, st, dom) if modo in ('REV', 'MERGE') else 0
            if lr != 0:
                lado, src = lr, 'REV'
            elif modo in ('RENKO', 'MERGE') and rk is not None:
                s = rk[i]
                if s['ma'] is not None and s['n_bricks'] >= 2:
                    if s['cross_up'] and s['dir'] == 1: lado, src = 1, 'RENKO'
                    elif s['cross_dn'] and s['dir'] == -1: lado, src = -1, 'RENKO'
            if lado != 0:
                entry = b['c']; pos = lado; origem = src; fav = entry; be_done = False
                if src == 'REV':
                    stop = entry - lado*PTS_SL; target = entry + lado*TP
                    dias_rev.add(d); rev_mudo_hoje = False
                else:
                    stop = entry - lado*stop_bricks*brick
                    target = (entry + lado*tp_pts) if tp_pts else 0.0
                    dias_rk.add(d)
                dias.add(d); th += 1

    # metricas
    tot = len(res); ap = sum(1 for s, _ in res if s == 'APROVOU')
    es = sum(1 for s, _ in res if s == 'ESTOUROU'); ex = tot-ap-es
    dda = sorted(dd for s, dd in res if s == 'APROVOU')
    dmed = dda[len(dda)//2] if dda else 0
    n = len(trades); w = [t for t in trades if t > 0]
    gw = sum(w); gl = abs(sum(t for t in trades if t <= 0))
    out = dict(taxa=100*ap/tot if tot else 0, ap=ap, es=es, ex=ex, dmed=dmed,
               n=n, wr=100*len(w)/n if n else 0, pf=gw/gl if gl else 99,
               net=sum(trades),
               dias_rev=len(dias_rev), dias_rk=len(dias_rk),
               rk_solo_n=n_rk_solo, rk_solo_pnl=pnl_rk_solo)
    return out


def pl(label, r, extra=''):
    print(f"  {label:<40s} {r['taxa']:>4.0f}%  {r['ap']:>2}/{r['es']:>2}/{r['ex']:>2}  "
          f"d{r['dmed']:<3} n={r['n']:<5} WR{r['wr']:>3.0f}% PF{r['pf']:>4.2f} "
          f"net{r['net']:>+8,.0f}  {extra}")


if __name__ == '__main__':
    bars = carregar('NQ_dados'); dom = domingo_ranges(bars)
    meio = len(bars)//2; b1, b2 = bars[:meio], bars[meio:]
    dom1, dom2 = domingo_ranges(b1), domingo_ranges(b2)
    print(f"{len(bars):,} barras | {bars[0]['dt'].date()} -> {bars[-1]['dt'].date()}")
    print("janela 30d | DD$1000 | Max12/dia | slip 2t | 5 MNQ\n")

    print("="*104)
    print("  REV baseline")
    print("="*104)
    pl('REV', roda(bars, dom, 'REV'))

    print("\n" + "="*104)
    print("  RENKO gestao de TENDENCIA (stop N tijolos, saida no cross contrario da MA)")
    print("="*104)
    cache = {}
    for brick, ma in [(15, 10), (20, 10), (20, 20), (25, 10), (25, 20), (30, 10)]:
        cache[(brick, ma)] = estado_renko(bars, brick, ma_period=ma)
        for sb in (1, 2, 3):
            r = roda(bars, dom, 'RENKO', rk=cache[(brick, ma)], brick=brick, stop_bricks=sb)
            pl(f'RENKO b{brick} ma{ma} stop{sb}tj', r)
        # com trailing por tijolo
        r = roda(bars, dom, 'RENKO', rk=cache[(brick, ma)], brick=brick, stop_bricks=2, trail_bricks=2)
        pl(f'RENKO b{brick} ma{ma} stop2tj +trail2tj', r)
        print()

    print("="*104)
    print("  RENKO com ALVO fixo grande (deixa correr mas realiza)")
    print("="*104)
    for brick, ma, tp in [(20, 10, 40), (20, 10, 80), (20, 10, 120), (25, 10, 80)]:
        rk = cache.get((brick, ma)) or estado_renko(bars, brick, ma_period=ma)
        r = roda(bars, dom, 'RENKO', rk=rk, brick=brick, stop_bricks=2, tp_pts=tp)
        pl(f'RENKO b{brick} ma{ma} stop2tj alvo{tp}', r)

    print("\n" + "="*104)
    print("  MESCLA REV + RENKO  +  quanto o Renko rende NOS DIAS EM QUE A REV FICA MUDA")
    print("="*104)
    for brick, ma, sb in [(20, 10, 2), (20, 20, 2), (25, 10, 2), (20, 10, 3)]:
        rk = cache.get((brick, ma)) or estado_renko(bars, brick, ma_period=ma)
        cache[(brick, ma)] = rk
        r = roda(bars, dom, 'MERGE', rk=rk, brick=brick, stop_bricks=sb)
        extra = f"[dias REV={r['dias_rev']} dias RENKO={r['dias_rk']} | Renko em dia REV-mudo: {r['rk_solo_n']} trades, net {r['rk_solo_pnl']:+,.0f}]"
        pl(f'MERGE b{brick} ma{ma} stop{sb}tj', r, extra)

    print("\n" + "="*104)
    print("  OOS 1a x 2a metade")
    print("="*104)
    def oos(label, modo, brick=None, ma=None, sb=2):
        rk1 = estado_renko(b1, brick, ma_period=ma) if brick else None
        rk2 = estado_renko(b2, brick, ma_period=ma) if brick else None
        r1 = roda(b1, dom1, modo, rk=rk1, brick=brick or 20, stop_bricks=sb)
        r2 = roda(b2, dom2, modo, rk=rk2, brick=brick or 20, stop_bricks=sb)
        print(f"  {label:<40s} 1a:{r1['ap']:>2}ap/{r1['es']:>2}es({r1['taxa']:>3.0f}%)PF{r1['pf']:.2f}"
              f"  2a:{r2['ap']:>2}ap/{r2['es']:>2}es({r2['taxa']:>3.0f}%)PF{r2['pf']:.2f}")
    oos('REV', 'REV')
    oos('RENKO b20 ma10 stop2tj', 'RENKO', 20, 10)
    oos('RENKO b25 ma10 stop2tj', 'RENKO', 25, 10)
    oos('MERGE b20 ma10 stop2tj', 'MERGE', 20, 10)
    oos('MERGE b20 ma20 stop2tj', 'MERGE', 20, 20)
    print("="*104)
