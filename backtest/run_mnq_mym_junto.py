#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MNQ + MYM na MESMA CONTA — pergunta do Marcelo (01/09): dá pra agregar o MYM ao
BETrigger25 (MNQ) e testar junto?

Aqui: DOIS bots de reversao (um em MNQ, um em MYM), MESMA conta — P&L, drawdown,
stop diario, dias operados e meta COMPARTILHADOS. É o padrao "kill switch global"
que o projeto ja usa (NomadeBot_ORB_Manha.cs le um arquivo de PnL compartilhado).

Compara: MNQ sozinho | MYM sozinho | MNQ+MYM juntos — no motor de aprovacao de
30 dias, 3 modelos de DD, slippage 2 ticks reais por instrumento.

⚠️ MNQ e MYM sao ~0,85-0,9 correlacionados (Nasdaq x Dow). Sinais costumam
disparar juntos, na mesma direcao -> pode ser DOBRAR a mesma aposta em vez de
diversificar. O teste diz se ajuda (mais trades -> bate meta/7 dias mais rapido)
ou atrapalha (dia de tendencia = 2 stops).
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from run_estrategias_comparativo import carregar, domingo_ranges, Estado, mins
from run_instrumento_scan import carrega_arq

ENTRADA_INI, ENTRADA_FIM, FLATTEN = 9*60+30, 16*60, 16*60+55
RT_PER = 1.20
META, DD, STOP_DIA, MAXTR, MINDIAS, JANELA = 1500.0, 1000.0, 750.0, 12, 7, 30

# (bars, dom, $/pt, tick, SL, TP, TOL_pts, MAXD, BEtrig, BElock, TRAIL)
def cfg_mnq(bars):
    return dict(bars=bars, dom=domingo_ranges(bars), pv=2.0, tick=0.25,
               SL=12.5, TP=60.0, TOL=5.0, MAXD=20.0, BT=2.5, BL=2.5, TR=1.75)
def cfg_mym(bars):
    return dict(bars=bars, dom=domingo_ranges(bars), pv=0.5, tick=1.0,
               SL=29.0, TP=117.0, TOL=12.0, MAXD=35.0, BT=9.0, BL=6.0, TR=2.0)


def sinal(b, st, TOL, MAXD):
    nh = st.seg_hoje[0] if st.seg_hoje else st.pd_hi
    nl = st.seg_hoje[1] if st.seg_hoje else st.pd_lo
    if nh is None: return 0
    if b['h'] >= nh-TOL and b['c'] < nh and (nh-b['c']) <= MAXD: return -1
    if b['l'] <= nl+TOL and b['c'] > nl and (b['c']-nl) <= MAXD: return 1
    return 0


def roda(cfgs, nc_list, dd_mode='intraday'):
    """cfgs: lista de dicts (1 = so um instrumento; 2 = os dois juntos).
    nc_list: contratos por instrumento (mesma ordem)."""
    # merge dos bar streams por timestamp
    stream = []
    for idx, c in enumerate(cfgs):
        for b in c['bars']:
            stream.append((b['dt'], idx, b))
    stream.sort(key=lambda x: x[0])

    K = len(cfgs)
    S = [Estado() for _ in cfgs]
    pos = [0]*K; entry = [0.0]*K; stop = [0.0]*K; tgt = [0.0]*K
    fav = [0.0]*K; be = [False]*K
    realized = 0.0
    r0 = pico = pico_e = 0.0; dias = set(); ini = None
    pd0 = 0.0; blk = False; dk = None; th = [0]*K
    res = []; tr = []

    def fecha(k, p):
        nonlocal realized
        if pos[k] == 0: return
        c = cfgs[k]; pvc = c['pv']*nc_list[k]; rt = RT_PER*nc_list[k]
        slip = 2.0*c['tick']
        realized += ((p-entry[k])*pos[k] - 2*slip)*pvc - rt
        tr.append(realized); pos[k] = 0

    def nova(dt):
        nonlocal r0, pico, pico_e, dias, ini
        r0 = realized; pico = pico_e = 0.0; dias = set(); ini = dt

    for dt, k, b in stream:
        m = mins(dt); d = dt.strftime('%Y-%m-%d'); wd = dt.weekday()
        c = cfgs[k]; st = S[k]
        if ini is None: nova(dt)
        if d != st.dia:
            if st.cur_hi is not None: st.pd_hi, st.pd_lo = st.cur_hi, st.cur_lo
            st.dia = d; st.cur_hi = st.cur_lo = None
            st.seg_hoje = c['dom'][d] if (c['dom'] and wd == 0 and d in c['dom']) else None
        if ENTRADA_INI <= m < 16*60:
            st.cur_hi = b['h'] if st.cur_hi is None else max(st.cur_hi, b['h'])
            st.cur_lo = b['l'] if st.cur_lo is None else min(st.cur_lo, b['l'])
        if d != dk:
            if dk is not None and dd_mode == 'eod': pico_e = max(pico_e, realized-r0)
            dk = d; pd0 = realized; blk = False; th = [0]*K

        pvc = c['pv']*nc_list[k]
        if pos[k] != 0:
            s = False
            if pos[k] > 0:
                if b['l'] <= stop[k]: fecha(k, stop[k]); s = True
                elif b['h'] >= tgt[k]: fecha(k, tgt[k]); s = True
            else:
                if b['h'] >= stop[k]: fecha(k, stop[k]); s = True
                elif b['l'] <= tgt[k]: fecha(k, tgt[k]); s = True
            if not s and pos[k] != 0:
                if pos[k] > 0:
                    fav[k] = max(fav[k], b['h'])
                    if not be[k] and (fav[k]-entry[k]) >= c['BT']: stop[k] = max(stop[k], entry[k]+c['BL']); be[k] = True
                    if be[k]: stop[k] = max(stop[k], fav[k]-c['TR'])
                else:
                    fav[k] = min(fav[k], b['l'])
                    if not be[k] and (entry[k]-fav[k]) >= c['BT']: stop[k] = min(stop[k], entry[k]-c['BL']); be[k] = True
                    if be[k]: stop[k] = min(stop[k], fav[k]+c['TR'])

        # PnL / DD agregado (todas as posicoes abertas)
        pr = realized - r0
        ua = uf = 0.0
        for j in range(K):
            if pos[j] == 0: continue
            pj = cfgs[j]['pv']*nc_list[j]
            bj = b if j == k else None
            # so temos a barra corrente do instrumento k; p/ os outros usa ult. entry como proxy neutro
            if bj is not None:
                if pos[j] > 0: ua += (bj['l']-entry[j])*pj; uf += (bj['h']-entry[j])*pj
                else: ua += (entry[j]-bj['h'])*pj; uf += (entry[j]-bj['l'])*pj
        if dd_mode == 'intraday':
            if pr+uf > pico: pico = pr+uf
            ref = pico
        elif dd_mode == 'eod': ref = max(pico_e, 0.0)
        else: ref = 0.0
        if STOP_DIA > 0 and (realized-pd0+ua) <= -STOP_DIA:
            blk = True
            for j in range(K): fecha(j, b['c'] if j == k else entry[j])
        dec = False
        if pr+ua <= ref-DD:
            for j in range(K): fecha(j, b['c'] if j == k else entry[j])
            res.append(('E', (dt-ini).days)); dec = True
        elif pr >= META and len(dias) >= MINDIAS:
            for j in range(K): fecha(j, b['c'] if j == k else entry[j])
            res.append(('A', (dt-ini).days)); dec = True
        elif (dt-ini).days >= JANELA:
            for j in range(K): fecha(j, b['c'] if j == k else entry[j])
            res.append(('X', (dt-ini).days)); dec = True
        if dec: nova(dt); continue

        if m >= FLATTEN and pos[k] != 0: fecha(k, b['c'])
        tot_th = sum(th)
        if not blk and tot_th < MAXTR and pos[k] == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
            lado = sinal(b, st, c['TOL'], c['MAXD'])
            if lado != 0:
                entry[k] = b['c']; pos[k] = lado; fav[k] = b['c']; be[k] = False
                stop[k] = entry[k] - lado*c['SL']; tgt[k] = entry[k] + lado*c['TP']
                dias.add(d); th[k] += 1

    tot = len(res); a = sum(1 for x, _ in res if x == 'A')
    e = sum(1 for x, _ in res if x == 'E'); xx = tot-a-e
    dda = sorted(y for x, y in res if x == 'A'); dm = dda[len(dda)//2] if dda else 0
    n = len(tr); difs = [tr[j]-(tr[j-1] if j else 0) for j in range(n)]
    w = [x for x in difs if x > 0]; gw = sum(w); gl = abs(sum(x for x in difs if x <= 0))
    return dict(taxa=100*a/tot if tot else 0, a=a, e=e, x=xx, dm=dm, n=n,
               wr=100*len(w)/n if n else 0, pf=gw/gl if gl else 99, net=sum(difs))


def pl(lbl, r):
    print(f"  {lbl:<34s} {r['taxa']:>4.0f}%  {r['a']:>2}a/{r['e']:>3}e/{r['x']:>2}x  "
          f"d{r['dm']:<3} n={r['n']:<5} WR{r['wr']:>3.0f}% PF{r['pf']:>4.2f} net{r['net']:>+9,.0f}")


if __name__ == '__main__':
    MNQ = carrega_arq('dados_databento/MNQ_1min.txt')
    MYM = carrega_arq('dados_databento/MYM_1min.txt')
    print(f"MNQ {len(MNQ):,} | MYM {len(MYM):,} barras (Databento front-month)")
    print("motor 30d | DD$1000 | Max12/dia COMPARTILHADO | slippage 2 ticks reais\n")

    cM, cY = cfg_mnq(MNQ), cfg_mym(MYM)
    for mode in ('intraday', 'eod', 'static'):
        print(f"===== DD {mode} =====")
        pl('MNQ sozinho 5c', roda([cM], [5], mode))
        pl('MYM sozinho 5c', roda([cY], [5], mode))
        pl('MNQ+MYM juntos 5c+5c', roda([cM, cY], [5, 5], mode))
        pl('MNQ+MYM juntos 3c+3c', roda([cM, cY], [3, 3], mode))
        pl('MNQ 3c + MYM 5c', roda([cM, cY], [3, 5], mode))
        print()

    print("===== OOS (1a x 2a metade) — DD estatico =====")
    def oos(lbl, cfgs, ncl):
        out = []
        for half in (0, 1):
            cc = []
            for c in cfgs:
                h = len(c['bars'])//2
                bb = c['bars'][:h] if half == 0 else c['bars'][h:]
                cc.append(dict(c, bars=bb, dom=domingo_ranges(bb)))
            out.append(roda(cc, ncl, 'static'))
        print(f"  {lbl:<28s} 1a {out[0]['taxa']:.0f}%/PF{out[0]['pf']:.2f}  2a {out[1]['taxa']:.0f}%/PF{out[1]['pf']:.2f}")
    oos('MNQ sozinho', [cM], [5])
    oos('MYM sozinho', [cY], [5])
    oos('MNQ+MYM 5c+5c', [cM, cY], [5, 5])
    oos('MNQ+MYM 3c+3c', [cM, cY], [3, 3])
