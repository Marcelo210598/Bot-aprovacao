#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NOTURNA 1min — "B passa o A" sem rejeicao (17/06)
=================================================
Pedido do Marcelo: voltar a noturna pro grafico de 1min. Regra:
  - candle A TOCA a linha (zona Fib), pode ate ter passado;  SEM exigir rejeicao;
  - candle B vem no SENTIDO INVERSO e "passa o A" -> entra (na vela B).
Testamos como definir "B passa o A":
  niv 'corpo'  = corpo de A (min/max open,close)   |  niv 'closeA' = close de A
  trig 'pavio' = mecha de B toca o nivel (Low/High de B)  -> entra cedo (intrabar)
  trig 'close' = B FECHA alem do nivel                    -> confirma no fechamento
  j1 = so a vela B   |   j2 = vela B ou C
Conta 25K/5 MNQ, gestao identica (SL12.5/BE3.75-2.5/trail1.75/TP60), canal>=40, pula domingo.
"""
import glob, os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); BR = ZoneInfo('America/Sao_Paulo'); UTC = timezone.utc
MNQ_PV = 2.0; RT_PER = 1.20
META = 1500.0; DD = 1500.0; MIN_DIAS = 7
TICK = 0.25; N_CONTR = 5
PTS_SL = 12.5; PTS_BE_TRIG = 3.75; PTS_BE_LOCK = 2.5; PTS_TRAIL = 1.75
TOL_TICKS = 20; TP = 60.0; MAX_DIST = 15.0
ENTRADA_INI = 9*60+30; ENTRADA_FIM = 16*60; FLATTEN = 16*60+55
STOP_DIA = 750.0
NOITE_INI_BR = 19*60; NOITE_FIM_BR = 21*60
NOITE_WARMUP_BR = 19*60+15; NOITE_FLATTEN_BR = 22*60
FIB_VENDA = 0.764; FIB_COMPRA = 0.236; RANGE_MIN = 40.0


def carregar(pasta):
    vistos = {}
    for f in sorted(glob.glob(os.path.join(pasta, '*.txt'))):
        with open(f, encoding='utf-8', errors='ignore') as fh:
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
                if dt not in vistos:
                    vistos[dt] = (dt.astimezone(ET), dt.astimezone(BR), o, h, l, c, v)
    return [{'dt': vistos[k][0], 'br': vistos[k][1], 'o': vistos[k][2], 'h': vistos[k][3],
             'l': vistos[k][4], 'c': vistos[k][5], 'v': vistos[k][6]} for k in sorted(vistos)]


def mins(dt): return dt.hour*60 + dt.minute


def domingo_ranges(bars):
    dom = {}
    for b in bars:
        dt = b['dt']; wd = dt.weekday(); m = mins(dt)
        if wd == 6 and m >= 18*60:
            seg = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
            if seg not in dom: dom[seg] = [b['h'], b['l']]
            else: dom[seg][0] = max(dom[seg][0], b['h']); dom[seg][1] = min(dom[seg][1], b['l'])
    return {k: tuple(v) for k, v in dom.items()}


def bt(bars, usar_diurna=True, usar_noturna=True, dom_map=None,
       niv='corpo', trig='pavio', gat=1, pular_dom=True):
    pv = MNQ_PV * N_CONTR; rt = RT_PER * N_CONTR
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False; origem = None
    realized = 0.0; trades = []
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None
    aprov = reprov = 0; d2a = []; pnl_d0 = 0.0; block = False; dia_k = None
    seg_hoje = None
    noite_dia = None; noite_hi = noite_lo = None; pend = None
    t_diur = []; t_not = []; trade_org = None
    tol = TOL_TICKS * TICK

    def fecha(p):
        nonlocal pos, realized
        if pos == 0: return
        g = (p - entry) * pos * pv - rt
        realized += g; trades.append(g)
        if trade_org == 'D': t_diur.append(g)
        elif trade_org == 'N': t_not.append(g)
        pos = 0

    for b in bars:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d'); wd = dt.weekday()
        mbr = mins(b['br']); dbr = b['br'].strftime('%Y-%m-%d')
        h, l, c, o = b['h'], b['l'], b['c'], b['o']

        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = cur_lo = None
            seg_hoje = dom_map[d] if (dom_map and wd == 0 and d in dom_map) else None
        if ENTRADA_INI <= m < 16*60:
            cur_hi = h if cur_hi is None else max(cur_hi, h)
            cur_lo = l if cur_lo is None else min(cur_lo, l)
        if d != dia_k:
            dia_k = d; pnl_d0 = realized; block = False
        if ini_aval is None: ini_aval = dt

        if pos != 0:
            saiu = False
            if pos > 0:
                if l <= stop: fecha(stop); saiu = True
                elif h >= target: fecha(target); saiu = True
            else:
                if h >= stop: fecha(stop); saiu = True
                elif l <= target: fecha(target); saiu = True
            if not saiu and pos != 0:
                if pos > 0:
                    fav = max(fav, h)
                    if not be_done and (fav - entry) >= PTS_BE_TRIG: stop = max(stop, entry + PTS_BE_LOCK); be_done = True
                    if be_done: stop = max(stop, fav - PTS_TRAIL)
                else:
                    fav = min(fav, l)
                    if not be_done and (entry - fav) >= PTS_BE_TRIG: stop = min(stop, entry - PTS_BE_LOCK); be_done = True
                    if be_done: stop = min(stop, fav + PTS_TRAIL)

        pr = realized - r_ini; ua = uf = 0.0
        if pos > 0: ua = (l - entry) * pv; uf = (h - entry) * pv
        elif pos < 0: ua = (entry - h) * pv; uf = (entry - l) * pv
        if pr + uf > pico: pico = pr + uf
        if STOP_DIA > 0 and (realized - pnl_d0 + ua) <= -STOP_DIA:
            block = True
            if pos != 0: fecha(c)
        if pr + ua <= pico - DD:
            fecha(c); reprov += 1; r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt
        elif pr >= META and len(dias) >= MIN_DIAS:
            fecha(c); aprov += 1; d2a.append((dt - ini_aval).days); r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt

        if usar_diurna:
            if m >= FLATTEN and pos != 0 and origem == 'D': fecha(c)
            if not block and pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
                nh = seg_hoje[0] if seg_hoje else pd_hi; nl = seg_hoje[1] if seg_hoje else pd_lo
                if nh is not None:
                    lado = 0
                    if h >= nh - tol and c < nh and (nh - c) <= MAX_DIST: lado = -1
                    elif l <= nl + tol and c > nl and (c - nl) <= MAX_DIST: lado = 1
                    if lado != 0:
                        entry = c; pos = lado; fav = c; be_done = False; origem = 'D'; trade_org = 'D'
                        stop = c - lado * PTS_SL; target = c + lado * TP; dias.add(d)

        if usar_noturna:
            na_janela = (NOITE_INI_BR <= mbr < NOITE_FIM_BR and not (pular_dom and b['br'].weekday() == 6))
            if na_janela:
                if dbr != noite_dia: noite_dia = dbr; noite_hi = h; noite_lo = l; pend = None
                else: noite_hi = max(noite_hi, h); noite_lo = min(noite_lo, l)
            if mbr >= NOITE_FLATTEN_BR and pos != 0 and origem == 'N': fecha(c)
            pode = (na_janela and mbr >= NOITE_WARMUP_BR and noite_hi is not None
                    and (noite_hi - noite_lo) >= RANGE_MIN and not block and pos == 0)
            if pode:
                rng = noite_hi - noite_lo
                z_venda = noite_lo + FIB_VENDA * rng; z_compra = noite_lo + FIB_COMPRA * rng
                # aciona setup pendente (vela B/C "passa o A")
                if pend is not None:
                    lado, nivel, rest = pend; disparou = False
                    if lado == -1:
                        cruzou = (l <= nivel) if trig == 'pavio' else (c <= nivel)
                        if cruzou:
                            entry = (min(nivel, o) if trig == 'pavio' else c)
                            pos = -1; stop = entry + PTS_SL; target = entry - TP; disparou = True
                    else:
                        cruzou = (h >= nivel) if trig == 'pavio' else (c >= nivel)
                        if cruzou:
                            entry = (max(nivel, o) if trig == 'pavio' else c)
                            pos = 1; stop = entry - PTS_SL; target = entry + TP; disparou = True
                    if disparou:
                        fav = entry; be_done = False; origem = 'N'; trade_org = 'N'; dias.add(d); pend = None
                    else:
                        rest -= 1; pend = None if rest <= 0 else (lado, nivel, rest)
                # arma novo setup: A tocou a zona (sem rejeicao). nivel = corpo ou close de A
                if pos == 0 and pend is None:
                    if h >= z_venda:
                        nivel = (min(o, c) if niv == 'corpo' else c); pend = (-1, nivel, gat)
                    elif l <= z_compra:
                        nivel = (max(o, c) if niv == 'corpo' else c); pend = (1, nivel, gat)
            elif not na_janela:
                pend = None

    if pos != 0: fecha(bars[-1]['c'])

    def stats(ts):
        w = [t for t in ts if t > 0]; n = len(ts); gw = sum(w); gl = abs(sum(t for t in ts if t <= 0))
        return {'n': n, 'wr': 100*len(w)/n if n else 0, 'pf': gw/gl if gl > 0 else (99 if gw > 0 else 0), 'net': sum(ts)}

    g = stats(trades); tot = aprov + reprov; ds = sorted(d2a); med = ds[len(ds)//2] if ds else 0
    g.update({'aprov': aprov, 'tot': tot, 'taxa': 100*aprov/tot if tot else 0, 'dmediana': med,
              'trd_dia': g['n']/220, 'not': stats(t_not)})
    return g


if __name__ == '__main__':
    print("Carregando NQ 1-min real..."); bars = carregar('NQ_dados')
    dom = domingo_ranges(bars)
    meio = bars[len(bars)//2]['dt']
    b1 = [b for b in bars if b['dt'] < meio]; b2 = [b for b in bars if b['dt'] >= meio]
    print(f"{len(bars):,} barras 1min | noturna: A toca a linha (sem rejeicao), B passa o A\n")

    cfgs = [
        ("B pavio>corpoA  j1",  dict(niv='corpo',  trig='pavio', gat=1)),
        ("B pavio>corpoA  j2",  dict(niv='corpo',  trig='pavio', gat=2)),
        ("B FECHA>corpoA  j1",  dict(niv='corpo',  trig='close', gat=1)),
        ("B FECHA>corpoA  j2",  dict(niv='corpo',  trig='close', gat=2)),
        ("B FECHA>closeA  j1",  dict(niv='closeA', trig='close', gat=1)),
        ("B FECHA>closeA  j2",  dict(niv='closeA', trig='close', gat=2)),
    ]
    print("=" * 98)
    print("  REGRA (noite 1min)            taxa  aprov   d.med  noite-trades  WR  PF   PnL$/ano   OOS(1a|2a)")
    print("=" * 98)
    for lbl, kw in cfgs:
        rc = bt(bars, True, True, dom, **kw)
        r1 = bt(b1, True, True, dom, **kw); r2 = bt(b2, True, True, dom, **kw)
        nn = rc['not']
        print(f"  {lbl:>24s} {rc['taxa']:>4.0f}% {rc['aprov']:>3}/{rc['tot']:<3} {rc['dmediana']:>4.0f}d "
              f"{nn['n']:>6} {nn['wr']:>4.0f}% {nn['pf']:>4.2f} {rc['net']:>10,.0f}   "
              f"{r1['taxa']:>3.0f}%|{r2['taxa']:>3.0f}%")
    print("=" * 98)
    print("  (noite-trades/WR/PF = so a parte NOTURNA; PnL e taxa = conta combinada)")
