#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROMPIMENTO (breakout) em vez de / junto com a reversao, nos 4 instrumentos.

Motivacao (pergunta do Marcelo 01/09): so testamos a REVERSAO nos outros
instrumentos. E se o mercado NAO reverte no nivel e ROMPE? Vale um breakout pra
completar? O M2K (Russell) da uma pista: a reversao la perde (WR 24%) porque o
preco ATRAVESSA o nivel — ou seja o INVERSO pode ter edge.

Testado (motor de aprovacao 30d, mesmo do resto do projeto, tick real por
instrumento, slippage 2 ticks):
  BREAK  = fecha ALEM da max/min do dia anterior -> entra na direcao do rompimento
  ORB    = rompimento do range de abertura (9h30-9h45 ET)
  FADE   = a reversao atual (referencia)
  FADE+BREAK = os dois juntos (fade quando rejeita, break quando rompe)

Gestao de TENDENCIA pro breakout (stop largo, deixa correr, trailing solto) —
diferente da gestao da reversao (stop curto, trava rapido). Params proporcionais
ao range RTH mediano de cada instrumento.

NQ_dados/ = NT8 (NQ). dados_databento/ = MES/MNQ/M2K/MYM (Databento front-month).
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from run_estrategias_comparativo import carregar, domingo_ranges, Estado, mins
from run_instrumento_scan import carrega_arq, range_rth_mediano, TICKS

ENTRADA_INI, ENTRADA_FIM, FLATTEN = 9*60+30, 16*60, 16*60+55
ORB_FIM = 9*60+45
RT_PER = 1.20
META, DD, STOP_DIA, MAXTR, MINDIAS, JANELA = 1500.0, 1000.0, 750.0, 12, 7, 30


def roda(bars, dom, pv, nc, tick, R, fonte='BREAK', dd_mode='intraday',
         slip_ticks=2.0, fSL=0.08, mTP=0.0, fTR=0.10, fBE=0.5):
    """fonte: BREAK | ORB | FADE | FADE+BREAK.
    Gestao proporcional ao range R: SL=R*fSL, trail=SL*fTR, BE trig/lock=SL*fBE,
    TP=SL*mTP (mTP=0 -> sem alvo, so trailing). FADE usa params fixos da producao."""
    SLIP = slip_ticks * tick
    if fonte == 'FADE':
        SL, TP, TOL, MAXD, BETRIG, BELOCK, TRAIL = (
            R*0.043, R*0.21, R*0.017, R*0.052, R*0.013, R*0.0087, R*0.0061)
    else:
        SL = R * fSL
        TP = SL * mTP if mTP else 0.0
        TRAIL = SL * fTR
        BELOCK = SL * fBE * 0.6
        BETRIG = SL * fBE
        TOL = R * 0.017
        MAXD = R * 0.20        # break: nao entra se ja rompeu muito longe
    pvc = pv * nc; rt = RT_PER * nc
    pos = 0; entry = stop = target = fav = 0.0; be = False; realized = 0.0
    r0 = pico = pico_e = 0.0; dias = set(); ini = None
    pd0 = 0.0; blk = False; dk = None; th = 0
    st = Estado()
    orb_hi = orb_lo = None; orb_ok = False
    res = []; tr = []

    def fecha(p):
        nonlocal pos, realized
        if pos == 0: return
        realized += ((p - entry) * pos - 2*SLIP) * pvc - rt; tr.append(realized); pos = 0

    def nova(dt):
        nonlocal r0, pico, pico_e, dias, ini
        r0 = realized; pico = pico_e = 0.0; dias = set(); ini = dt

    for b in bars:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d'); wd = dt.weekday()
        if ini is None: nova(dt)
        if d != st.dia:
            if st.cur_hi is not None: st.pd_hi, st.pd_lo = st.cur_hi, st.cur_lo
            st.dia = d; st.cur_hi = st.cur_lo = None
            st.seg_hoje = dom[d] if (dom and wd == 0 and d in dom) else None
            orb_hi = orb_lo = None; orb_ok = False
        if ENTRADA_INI <= m < 16*60:
            st.cur_hi = b['h'] if st.cur_hi is None else max(st.cur_hi, b['h'])
            st.cur_lo = b['l'] if st.cur_lo is None else min(st.cur_lo, b['l'])
        if ENTRADA_INI <= m < ORB_FIM:
            orb_hi = b['h'] if orb_hi is None else max(orb_hi, b['h'])
            orb_lo = b['l'] if orb_lo is None else min(orb_lo, b['l'])
        elif m >= ORB_FIM:
            orb_ok = True
        if d != dk:
            if dk is not None and dd_mode == 'eod': pico_e = max(pico_e, realized - r0)
            dk = d; pd0 = realized; blk = False; th = 0

        if pos != 0:
            s = False
            if pos > 0:
                if b['l'] <= stop: fecha(stop); s = True
                elif target and b['h'] >= target: fecha(target); s = True
            else:
                if b['h'] >= stop: fecha(stop); s = True
                elif target and b['l'] <= target: fecha(target); s = True
            if not s and pos != 0:
                if pos > 0:
                    fav = max(fav, b['h'])
                    if not be and (fav-entry) >= BETRIG: stop = max(stop, entry+BELOCK); be = True
                    if be: stop = max(stop, fav-TRAIL)
                else:
                    fav = min(fav, b['l'])
                    if not be and (entry-fav) >= BETRIG: stop = min(stop, entry-BELOCK); be = True
                    if be: stop = min(stop, fav+TRAIL)

        pr = realized - r0; ua = uf = 0.0
        if pos > 0: ua = (b['l']-entry)*pvc; uf = (b['h']-entry)*pvc
        elif pos < 0: ua = (entry-b['h'])*pvc; uf = (entry-b['l'])*pvc
        if dd_mode == 'intraday':
            if pr+uf > pico: pico = pr+uf
            ref = pico
        elif dd_mode == 'eod': ref = max(pico_e, 0.0)
        else: ref = 0.0
        if STOP_DIA > 0 and (realized-pd0+ua) <= -STOP_DIA:
            blk = True
            if pos != 0: fecha(b['c'])
        dec = False
        if pr+ua <= ref-DD: fecha(b['c']); res.append(('E', (dt-ini).days)); dec = True
        elif pr >= META and len(dias) >= MINDIAS: fecha(b['c']); res.append(('A', (dt-ini).days)); dec = True
        elif (dt-ini).days >= JANELA: fecha(b['c']); res.append(('X', (dt-ini).days)); dec = True
        if dec: nova(dt)
        if m >= FLATTEN and pos != 0: fecha(b['c'])

        if not blk and th < MAXTR and pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
            nh = st.seg_hoje[0] if st.seg_hoje else st.pd_hi
            nl = st.seg_hoje[1] if st.seg_hoje else st.pd_lo
            lado = 0
            if fonte in ('BREAK', 'FADE+BREAK') and nh is not None:
                if b['c'] > nh and (b['c']-nh) <= MAXD: lado = 1
                elif b['c'] < nl and (nl-b['c']) <= MAXD: lado = -1
            if lado == 0 and fonte in ('FADE', 'FADE+BREAK') and nh is not None:
                tol = R*0.017; maxd = R*0.052
                if b['h'] >= nh-tol and b['c'] < nh and (nh-b['c']) <= maxd: lado = -1
                elif b['l'] <= nl+tol and b['c'] > nl and (b['c']-nl) <= maxd: lado = 1
            if lado == 0 and fonte == 'ORB' and orb_ok and orb_hi is not None:
                rng = orb_hi - orb_lo
                if R*0.15 <= rng <= R*0.9:      # filtro de range (essencial no ORB)
                    if b['c'] > orb_hi: lado = 1
                    elif b['c'] < orb_lo: lado = -1
            if lado != 0:
                entry = b['c']; pos = lado; fav = entry; be = False
                stop = entry - lado*SL; target = (entry + lado*TP) if TP else 0.0
                dias.add(d); th += 1

    tot = len(res); a = sum(1 for x, _ in res if x == 'A')
    e = sum(1 for x, _ in res if x == 'E'); xx = tot-a-e
    dda = sorted(y for x, y in res if x == 'A'); dm = dda[len(dda)//2] if dda else 0
    n = len(tr); difs = [tr[j]-(tr[j-1] if j else 0) for j in range(n)]
    w = [x for x in difs if x > 0]; gw = sum(w); gl = abs(sum(x for x in difs if x <= 0))
    return dict(taxa=100*a/tot if tot else 0, a=a, e=e, x=xx, dm=dm, n=n,
               wr=100*len(w)/n if n else 0, pf=gw/gl if gl else 99, net=sum(difs))


def pl(lbl, r):
    print(f"  {lbl:<30s} {r['taxa']:>4.0f}%  {r['a']:>2}a/{r['e']:>3}e/{r['x']:>2}x  "
          f"d{r['dm']:<3} n={r['n']:<5} WR{r['wr']:>3.0f}% PF{r['pf']:>4.2f} net{r['net']:>+9,.0f}")


if __name__ == '__main__':
    NQ = carregar('NQ_dados')
    INSTR = {
        'NQ':  (NQ, 2.0, TICKS['NQ']),
        'MES': (carrega_arq('dados_databento/MES_1min.txt'), 5.0, TICKS['MES']),
        'MNQ': (carrega_arq('dados_databento/MNQ_1min.txt'), 2.0, TICKS['MNQ']),
        'M2K': (carrega_arq('dados_databento/M2K_1min.txt'), 5.0, TICKS['M2K']),
        'MYM': (carrega_arq('dados_databento/MYM_1min.txt'), 0.5, TICKS['MYM']),
    }
    print("motor 30d | DD$1000 | Max12/dia | slippage 2 ticks reais\n")

    for nm, (bars, pv, tk) in INSTR.items():
        dom = domingo_ranges(bars); R = range_rth_mediano(bars)
        h = len(bars)//2; d1 = domingo_ranges(bars[:h]); d2 = domingo_ranges(bars[h:])
        print("="*96)
        print(f"  {nm}  (${pv}/pt, tick {tk}) — range RTH mediano {R:.0f}pt")
        print("="*96)
        # FADE de referencia
        pl('FADE (reversao, ref)', roda(bars, dom, pv, 8, tk, R, fonte='FADE'))
        # BREAK: sweep de stop x trailing x alvo x contratos
        best = None
        for fSL in (0.05, 0.08, 0.12):
            for fTR in (0.10, 0.25, 0.5):
                for mTP in (0, 3, 6):
                    for nc in (5, 8):
                        r = roda(bars, dom, pv, nc, tk, R, fonte='BREAK',
                                 fSL=fSL, fTR=fTR, mTP=mTP)
                        if best is None or r['pf'] > best[0]:
                            best = (r['pf'], nc, fSL, fTR, mTP, r)
        pf, nc, fSL, fTR, mTP, r = best
        pl(f'BREAK best (nc{nc} SL{R*fSL:.0f} tr{R*fSL*fTR:.1f} tp{"x"+str(mTP) if mTP else "trail"})', r)
        # OOS + DD estatico + FADE+BREAK do best
        r1 = roda(bars[:h], d1, pv, nc, tk, R, fonte='BREAK', fSL=fSL, fTR=fTR, mTP=mTP)
        r2 = roda(bars[h:], d2, pv, nc, tk, R, fonte='BREAK', fSL=fSL, fTR=fTR, mTP=mTP)
        print(f"     BREAK OOS: 1a {r1['taxa']:.0f}%/PF{r1['pf']:.2f}  2a {r2['taxa']:.0f}%/PF{r2['pf']:.2f}")
        pl('BREAK best / static DD', roda(bars, dom, pv, nc, tk, R, fonte='BREAK',
                                          fSL=fSL, fTR=fTR, mTP=mTP, dd_mode='static'))
        pl('FADE+BREAK juntos', roda(bars, dom, pv, nc, tk, R, fonte='FADE+BREAK',
                                     fSL=fSL, fTR=fTR, mTP=mTP))
        pl('FADE+BREAK / static DD', roda(bars, dom, pv, nc, tk, R, fonte='FADE+BREAK',
                                          fSL=fSL, fTR=fTR, mTP=mTP, dd_mode='static'))
        # ORB
        pl('ORB (opening range break)', roda(bars, dom, pv, nc, tk, R, fonte='ORB',
                                             fSL=fSL, fTR=fTR, mTP=mTP or 3))
        print()
