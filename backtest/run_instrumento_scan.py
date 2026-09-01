#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIRECAO B — a reversao PDH/PDL em OUTRO INSTRUMENTO (dado real Databento).

Dados: Databento GLBX.MDP3 OHLCV-1m, front-month continuo (carrega_databento.py):
  dados_databento/MES_1min.txt  (Micro E-mini S&P 500,   $5/pt)
  dados_databento/MNQ_1min.txt  (Micro E-mini Nasdaq-100, $2/pt)
Periodo: 2025-06-01 -> 2026-06-12 (mesmo do NQ_dados/).

Hipotese: a falha da reversao no NQ e' a cauda de perda vs. o DD $1.000. O ES
anda ~1/5 do NQ em pontos -> a mesma % de movimento e' menos $ contra o mesmo DD.
Talvez o edge sobreviva melhor no MES.

Metodo: motor de aprovacao 30d corridos (identico ao resto do projeto), gestao
com params EXPLICITOS em pontos (nao escalados as cegas — sub-tick nao funciona).
Varre SL/TP/BE/trail no MES. Valida com MNQ-databento (tem que bater ~55% do NT8).

RESULTADO (01/09): MES NAO tem o edge. PF < 1,0 em TODA config testada (SL 4-10pt,
TP 12-40pt, trail 0,6-2,0pt) -> a reversao no nivel do dia anterior e' um fenomeno
do Nasdaq, nao do S&P. Ver docs/melhorias-sugeridas.md #22.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from run_estrategias_comparativo import carregar, domingo_ranges, Estado, mins

ENTRADA_INI, ENTRADA_FIM, FLATTEN = 9*60+30, 16*60, 16*60+55
RT_PER = 1.20
META, DD, STOP_DIA, MAXTR, MINDIAS, JANELA = 1500.0, 1000.0, 750.0, 12, 7, 30

# tick size (pontos de indice) por instrumento — CRITICO pro slippage:
#   ES/NQ/MES/MNQ = 0,25 | RTY/M2K = 0,10 | YM/MYM = 1,00
TICKS = {'NQ': 0.25, 'MES': 0.25, 'MNQ': 0.25, 'M2K': 0.10, 'MYM': 1.00}


def carrega_arq(path):
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    ET = ZoneInfo('America/New_York'); UTC = timezone.utc
    vistos = {}
    with open(path, encoding='utf-8', errors='ignore') as fh:
        for line in fh:
            line = line.strip()
            if not line: continue
            try:
                dtp, rest = line.split(';', 1); data, hora = dtp.split()
                o, h, l, c, v = rest.split(';')
                dt = datetime(int(data[:4]), int(data[4:6]), int(data[6:8]),
                              int(hora[:2]), int(hora[2:4]), tzinfo=UTC)
                o, h, l, c, v = float(o), float(h), float(l), float(c), float(v)
            except Exception: continue
            h = max(h, o, c); l = min(l, o, c)
            if dt not in vistos: vistos[dt] = (dt.astimezone(ET), o, h, l, c, v)
    return [{'dt': vistos[k][0], 'o': vistos[k][1], 'h': vistos[k][2],
             'l': vistos[k][3], 'c': vistos[k][4], 'v': vistos[k][5]} for k in sorted(vistos)]


def roda(bars, dom, pv, nc, SL, TP, TOL, MAXD, BETRIG, BELOCK, TRAIL,
         fonte='REV', dd_mode='intraday', slip_ticks=2.0, tick=0.25):
    SLIP = slip_ticks * tick
    pvc = pv*nc; rt = RT_PER*nc
    pos = 0; entry = stop = target = fav = 0.0; be = False; realized = 0.0
    r0 = 0.0; pico = 0.0; pico_e = 0.0; dias = set(); ini = None
    pd0 = 0.0; blk = False; dk = None; th = 0
    st = Estado(); st.on_hi = st.on_lo = None
    on_hi_acc = on_lo_acc = None
    res = []; tr = []

    def fecha(p):
        nonlocal pos, realized
        if pos == 0: return
        realized += ((p-entry)*pos - 2*SLIP)*pvc - rt; tr.append(realized); pos = 0

    def nova(dt):
        nonlocal r0, pico, pico_e, dias, ini
        r0 = realized; pico = 0.0; pico_e = 0.0; dias = set(); ini = dt

    for b in bars:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d'); wd = dt.weekday()
        if ini is None: nova(dt)
        if d != st.dia:
            if st.cur_hi is not None: st.pd_hi, st.pd_lo = st.cur_hi, st.cur_lo
            st.dia = d; st.cur_hi = st.cur_lo = None
            st.seg_hoje = dom[d] if (dom and wd == 0 and d in dom) else None
            st.on_hi = on_hi_acc; st.on_lo = on_lo_acc
            on_hi_acc = on_lo_acc = None
        if m >= 18*60 or m < ENTRADA_INI:
            on_hi_acc = b['h'] if on_hi_acc is None else max(on_hi_acc, b['h'])
            on_lo_acc = b['l'] if on_lo_acc is None else min(on_lo_acc, b['l'])
        if ENTRADA_INI <= m < 16*60:
            st.cur_hi = b['h'] if st.cur_hi is None else max(st.cur_hi, b['h'])
            st.cur_lo = b['l'] if st.cur_lo is None else min(st.cur_lo, b['l'])
        if d != dk:
            if dk is not None and dd_mode == 'eod': pico_e = max(pico_e, realized-r0)
            dk = d; pd0 = realized; blk = False; th = 0

        if pos != 0:
            s = False
            if pos > 0:
                if b['l'] <= stop: fecha(stop); s = True
                elif b['h'] >= target: fecha(target); s = True
            else:
                if b['h'] >= stop: fecha(stop); s = True
                elif b['l'] <= target: fecha(target); s = True
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
            if nh is not None:
                if b['h'] >= nh-TOL and b['c'] < nh and (nh-b['c']) <= MAXD: lado = -1
                elif b['l'] <= nl+TOL and b['c'] > nl and (b['c']-nl) <= MAXD: lado = 1
            if lado == 0 and fonte == 'REV+ON' and st.on_hi is not None:
                if b['h'] >= st.on_hi-TOL and b['c'] < st.on_hi and (st.on_hi-b['c']) <= MAXD: lado = -1
                elif b['l'] <= st.on_lo+TOL and b['c'] > st.on_lo and (b['c']-st.on_lo) <= MAXD: lado = 1
            if lado != 0:
                entry = b['c']; pos = lado; fav = entry; be = False
                stop = entry - lado*SL; target = entry + lado*TP; dias.add(d); th += 1

    tot = len(res); a = sum(1 for x, _ in res if x == 'A')
    e = sum(1 for x, _ in res if x == 'E'); xx = tot-a-e
    dda = sorted(y for x, y in res if x == 'A'); dm = dda[len(dda)//2] if dda else 0
    n = len(tr); difs = [tr[j]-(tr[j-1] if j else 0) for j in range(n)]
    w = [x for x in difs if x > 0]; gw = sum(w); gl = abs(sum(x for x in difs if x <= 0))
    return dict(taxa=100*a/tot if tot else 0, a=a, e=e, x=xx, dm=dm, n=n,
               wr=100*len(w)/n if n else 0, pf=gw/gl if gl else 99, net=sum(difs))


def pl(lbl, r):
    print(f"  {lbl:<38s} {r['taxa']:>4.0f}%  {r['a']:>2}a/{r['e']:>2}e/{r['x']:>2}x  "
          f"d{r['dm']:<3} n={r['n']:<5} WR{r['wr']:>3.0f}% PF{r['pf']:>4.2f} net{r['net']:>+9,.0f}")


def range_rth_mediano(bars):
    byd = {}
    for x in bars:
        m = mins(x['dt'])
        if 9*60+30 <= m < 16*60:
            byd.setdefault(x['dt'].strftime('%Y-%m-%d'), []).append(x)
    r = sorted(max(v['h'] for v in bs) - min(v['l'] for v in bs)
               for bs in byd.values() if len(bs) > 60)
    return r[len(r)//2] if r else 0


def sweep_instr(nome, bars, dom, pv, tick):
    """sweep de gestao proporcional ao range RTH mediano. slippage = 2 ticks
    REAIS do instrumento (MYM tick=1pt Dow, nao 0,25!)."""
    R = range_rth_mediano(bars)
    print(f"\n{'='*100}\n  {nome}  (${pv}/pt, tick {tick}pt) — range RTH mediano {R:.1f} pt "
          f"| slippage 2 ticks = {2*tick:.2f}pt")
    print("="*100)
    grid = []
    for fSL in (0.035, 0.05, 0.07, 0.09):
        SL = round(R*fSL, 2)
        TOL = round(SL*0.4, 2); MAXD = round(SL*1.2, 2)
        for mTP in (2, 4, 6):
            TP = round(SL*mTP, 2)
            for fTR in (0.06, 0.12, 0.20):
                TR = round(SL*fTR, 2); BL = round(SL*0.2, 2); BT = round(SL*0.3, 2)
                for nc in (3, 5, 8):
                    r = roda(bars, dom, pv, nc, SL, TP, TOL, MAXD, BT, BL, TR, tick=tick)
                    grid.append((r['taxa'], nc, SL, TP, TR, r))
    grid.sort(key=lambda z: -z[0])
    pfmax = max(r['pf'] for *_, r in grid)
    print(f"  {len(grid)} configs | PF max no grid = {pfmax:.2f}")
    for taxa, nc, SL, TP, TR, r in grid[:6]:
        pl(f'{nc}c SL{SL} TP{TP} tr{TR}', r)
    _, nc, SL, TP, TR, _ = grid[0]
    TOL = round(SL*0.4, 2); MAXD = round(SL*1.2, 2); BL = round(SL*0.2, 2); BT = round(SL*0.3, 2)
    print("  -- melhor config: modelos de DD + merge overnight + OOS + sensibilidade slippage --")
    for mode in ('intraday', 'static'):
        pl(f'best REV {mode}', roda(bars, dom, pv, nc, SL, TP, TOL, MAXD, BT, BL, TR, dd_mode=mode, tick=tick))
    pl('best REV+ON static', roda(bars, dom, pv, nc, SL, TP, TOL, MAXD, BT, BL, TR, fonte='REV+ON', dd_mode='static', tick=tick))
    h = len(bars)//2
    r1 = roda(bars[:h], domingo_ranges(bars[:h]), pv, nc, SL, TP, TOL, MAXD, BT, BL, TR, tick=tick)
    r2 = roda(bars[h:], domingo_ranges(bars[h:]), pv, nc, SL, TP, TOL, MAXD, BT, BL, TR, tick=tick)
    print(f"  OOS best REV: 1a {r1['taxa']:.0f}% PF{r1['pf']:.2f} | 2a {r2['taxa']:.0f}% PF{r2['pf']:.2f}")
    for st in (1.0, 2.0, 3.0):
        rr = roda(bars, dom, pv, nc, SL, TP, TOL, MAXD, BT, BL, TR, dd_mode='static', slip_ticks=st, tick=tick)
        print(f"     slip {st:.0f}t ({st*tick:.2f}pt): {rr['taxa']:.0f}% PF{rr['pf']:.2f}")
    return pfmax, grid[0]


if __name__ == '__main__':
    NQ = carregar('NQ_dados')
    MES = carrega_arq('dados_databento/MES_1min.txt')
    MNQ = carrega_arq('dados_databento/MNQ_1min.txt')
    M2K = carrega_arq('dados_databento/M2K_1min.txt')
    MYM = carrega_arq('dados_databento/MYM_1min.txt')
    dNQ, dMES, dMNQ, dM2K, dMYM = (domingo_ranges(x) for x in (NQ, MES, MNQ, M2K, MYM))
    print(f"NQ-NT8 {len(NQ):,} | MES {len(MES):,} | MNQ-db {len(MNQ):,} | "
          f"M2K {len(M2K):,} | MYM {len(MYM):,} barras\n")

    print("="*100)
    print("  VALIDACAO — reversao params-NQ no NT8 e no MNQ-databento (tem que dar edge)")
    print("="*100)
    pl('NQ  NT8  5c $2', roda(NQ, dNQ, 2.0, 5, 12.5, 60, 5, 15, 3.75, 2.5, 1.75))
    pl('MNQ databento 5c $2', roda(MNQ, dMNQ, 2.0, 5, 12.5, 60, 5, 15, 3.75, 2.5, 1.75))
    pl('MNQ databento 5c static', roda(MNQ, dMNQ, 2.0, 5, 12.5, 60, 5, 15, 3.75, 2.5, 1.75, dd_mode='static'))

    resumo = {}
    resumo['MES'] = sweep_instr('MES (Micro S&P 500)', MES, dMES, 5.0, TICKS['MES'])
    resumo['M2K'] = sweep_instr('M2K (Micro Russell 2000)', M2K, dM2K, 5.0, TICKS['M2K'])
    resumo['MYM'] = sweep_instr('MYM (Micro Dow Jones)', MYM, dMYM, 0.50, TICKS['MYM'])

    print("\n" + "="*100)
    print("  RESUMO — PF maximo do grid por instrumento (>1,2 = tem edge; <1,0 = perde no bruto)")
    print("="*100)
    print(f"  {'NQ/MNQ (ref)':<26s} PF ~1.3-1.4  (edge conhecido)")
    for k, (pfmax, best) in resumo.items():
        print(f"  {k:<26s} PF max no grid = {pfmax:.2f}   melhor taxa = {best[0]:.0f}%")
    print("="*100)
