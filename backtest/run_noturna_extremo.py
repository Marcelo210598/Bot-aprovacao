#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NOTURNA EM 5 MINUTOS vs 1 MINUTO (17/06)
========================================
Pedido do Marcelo: rodar a estrategia da NOITE (canal Fib, gatilho 'corpo' j2) no
grafico de 5 MINUTOS. Comparamos:
  A) NOTURNA sozinha:   1min  vs  5min
  B) COMBINADO inteiro: 1min  vs  5min (diurna+noturna no mesmo TF)
  C) MISTO realista:    diurna 1min  +  NOTURNA 5min  (cada uma no seu TF)

Gestao identica (SL 12.5 / BE 3.75-2.5 / trail 1.75 / TP 60). Conta 25K / 5 MNQ.
Canal >=40pt, pular domingo. Gatilho corpo j2 (a proxima rompe o corpo, ate 2 barras).
OBS: o backtest gerencia a saida no FECHAMENTO da barra. Ao vivo o bot gerencia
TICK A TICK (OnMarketData), entao em 5min o trailing real e mais fino que aqui.
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
FIB_VENDA = 0.764; FIB_COMPRA = 0.236
RANGE_MIN = 40.0


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


def _bucket(dt):
    return dt.replace(minute=(dt.minute // 5) * 5, second=0, microsecond=0)


def resample5(bars1):
    """Agrega barras de 1min em 5min (alinhado :00/:05/:10...)."""
    out = []; cur = None; key = None
    for b in bars1:
        k = _bucket(b['dt'])
        if k != key:
            if cur is not None: out.append(cur)
            key = k
            cur = {'dt': b['dt'], 'br': b['br'], 'o': b['o'], 'h': b['h'],
                   'l': b['l'], 'c': b['c'], 'v': b['v']}
        else:
            cur['h'] = max(cur['h'], b['h']); cur['l'] = min(cur['l'], b['l'])
            cur['c'] = b['c']; cur['v'] += b['v']
    if cur is not None: out.append(cur)
    return out


def attach5(bars1):
    """Anexa em cada barra de 1min o campo 'bar5' = a barra de 5min COMPLETA, quando
    essa 1min fecha o bucket (senao None). Usado no modo MISTO (noturna decide em 5min)."""
    acc = None; key = None
    for i, b in enumerate(bars1):
        k = _bucket(b['dt'])
        if k != key:
            key = k
            acc = {'dt': b['dt'], 'br': b['br'], 'o': b['o'], 'h': b['h'],
                   'l': b['l'], 'c': b['c']}
        else:
            acc['h'] = max(acc['h'], b['h']); acc['l'] = min(acc['l'], b['l']); acc['c'] = b['c']
        # esta 1min fecha o bucket se a proxima 1min cair em outro bucket (ou for a ultima)
        fecha_bucket = (i + 1 >= len(bars1)) or (_bucket(bars1[i + 1]['dt']) != key)
        b['bar5'] = dict(acc) if fecha_bucket else None
    return bars1


def bt(bars, usar_diurna=True, usar_noturna=True, dom_map=None, gat_barras=2,
       pular_dom=True, mixed5=False, gatilho='corpo'):
    pv = MNQ_PV * N_CONTR; rt = RT_PER * N_CONTR
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False; origem = None
    realized = 0.0; trades = []
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None
    aprov = reprov = 0; d2a = []; pnl_d0 = 0.0; block = False; dia_k = None
    seg_hoje = None
    noite_dia = None; noite_hi = noite_lo = None; pend = None
    t_diur = []; t_not = []; trade_org = None

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

        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = cur_lo = None
            seg_hoje = dom_map[d] if (dom_map and wd == 0 and d in dom_map) else None
        if ENTRADA_INI <= m < 16*60:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
        if d != dia_k:
            dia_k = d; pnl_d0 = realized; block = False
        if ini_aval is None: ini_aval = dt

        # ---- gestao posicao (sempre no TF da barra base) ----
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

        # ---- conta ----
        pr = realized - r_ini
        ua = uf = 0.0
        if pos > 0: ua = (b['l'] - entry) * pv; uf = (b['h'] - entry) * pv
        elif pos < 0: ua = (entry - b['h']) * pv; uf = (entry - b['l']) * pv
        if pr + uf > pico: pico = pr + uf
        if STOP_DIA > 0 and (realized - pnl_d0 + ua) <= -STOP_DIA:
            block = True
            if pos != 0: fecha(b['c'])
        if pr + ua <= pico - DD:
            fecha(b['c']); reprov += 1; r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt
        elif pr >= META and len(dias) >= MIN_DIAS:
            fecha(b['c']); aprov += 1; d2a.append((dt - ini_aval).days)
            r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt

        # ============ DIURNA (sempre no TF da barra base) ============
        if usar_diurna:
            if m >= FLATTEN and pos != 0 and origem == 'D':
                fecha(b['c'])
            if not block and pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
                niv_hi = seg_hoje[0] if seg_hoje else pd_hi
                niv_lo = seg_hoje[1] if seg_hoje else pd_lo
                if niv_hi is not None:
                    tol = TOL_TICKS * TICK; h, l, c = b['h'], b['l'], b['c']; lado = 0
                    if h >= niv_hi - tol and c < niv_hi and (niv_hi - c) <= MAX_DIST: lado = -1
                    elif l <= niv_lo + tol and c > niv_lo and (c - niv_lo) <= MAX_DIST: lado = 1
                    if lado != 0:
                        entry = c; pos = lado; fav = c; be_done = False; origem = 'D'; trade_org = 'D'
                        stop = c - lado * PTS_SL; target = c + lado * TP; dias.add(d)

        # ============ NOTURNA ============
        if usar_noturna:
            # no modo MISTO a noturna so "ve" barra ao FECHAR um bucket de 5min (b['bar5'])
            nb = (b.get('bar5') if mixed5 else b)
            na_janela = (NOITE_INI_BR <= mbr < NOITE_FIM_BR
                         and not (pular_dom and b['br'].weekday() == 6))
            if na_janela and nb is not None:
                if dbr != noite_dia:
                    noite_dia = dbr; noite_hi = nb['h']; noite_lo = nb['l']; pend = None
                else:
                    noite_hi = max(noite_hi, nb['h']); noite_lo = min(noite_lo, nb['l'])
            if mbr >= NOITE_FLATTEN_BR and pos != 0 and origem == 'N':
                fecha(b['c'])
            pode = (na_janela and nb is not None and mbr >= NOITE_WARMUP_BR
                    and noite_hi is not None and (noite_hi - noite_lo) >= RANGE_MIN
                    and not block and pos == 0)
            if pode:
                rng = noite_hi - noite_lo
                z_venda = noite_lo + FIB_VENDA * rng
                z_compra = noite_lo + FIB_COMPRA * rng
                h, l, c, o = nb['h'], nb['l'], nb['c'], nb['o']
                if pend is not None:
                    lado, nivel, rest = pend
                    if lado == -1 and l <= nivel:
                        entry = min(nivel, o); pos = -1; fav = entry; be_done = False
                        origem = 'N'; trade_org = 'N'; stop = entry + PTS_SL; target = entry - TP
                        dias.add(d); pend = None
                    elif lado == 1 and h >= nivel:
                        entry = max(nivel, o); pos = 1; fav = entry; be_done = False
                        origem = 'N'; trade_org = 'N'; stop = entry - PTS_SL; target = entry + TP
                        dias.add(d); pend = None
                    else:
                        rest -= 1; pend = None if rest <= 0 else (lado, nivel, rest)
                if pos == 0 and pend is None:
                    if gatilho == 'corpo':
                        if h >= z_venda: pend = (-1, min(o, c), gat_barras)
                        elif l <= z_compra: pend = (1, max(o, c), gat_barras)
                    else:  # 'extremo': corpo + pavio = minima/maxima CHEIA da vela A
                        if h >= z_venda: pend = (-1, l, gat_barras)
                        elif l <= z_compra: pend = (1, h, gat_barras)
            elif not na_janela:
                pend = None

    if pos != 0: fecha(bars[-1]['c'])

    def stats(ts):
        w = [t for t in ts if t > 0]; n = len(ts)
        gw = sum(w); gl = abs(sum(t for t in ts if t <= 0))
        return {'n': n, 'wr': 100*len(w)/n if n else 0,
                'pf': gw/gl if gl > 0 else (99 if gw > 0 else 0), 'net': sum(ts)}

    g = stats(trades); tot = aprov + reprov
    ds = sorted(d2a); med = ds[len(ds)//2] if ds else 0
    g.update({'aprov': aprov, 'reprov': reprov, 'tot': tot,
              'taxa': 100*aprov/tot if tot else 0, 'dmediana': med,
              'trd_dia': g['n']/220, 'diur': stats(t_diur), 'not': stats(t_not)})
    return g


def linha(label, r):
    print(f"  {label:>26s} {r['taxa']:>4.0f}% {r['aprov']:>3}/{r['tot']:<3} {r['dmediana']:>4.0f}d "
          f"{r['n']:>5} {r['trd_dia']:>5.1f} {r['wr']:>3.0f}% {r['pf']:>5.2f} {r['net']:>10,.0f}")


if __name__ == '__main__':
    print("Carregando NQ 1-min real..."); bars1 = carregar('NQ_dados')
    dom = domingo_ranges(bars1)
    bars5 = resample5(bars1)
    bars1m = attach5([dict(b) for b in bars1])
    meio = bars1[len(bars1)//2]['dt']
    def split(bs): return [b for b in bs if b['dt'] < meio], [b for b in bs if b['dt'] >= meio]
    print(f"{len(bars1):,}->{len(bars5):,} (5min) | corpo (min/max o,c) vs EXTREMO (low/high cheio = corpo+pavio)\n")

    def linha(lbl, r):
        print(f"  {lbl:>30s} {r['taxa']:>4.0f}% {r['aprov']:>3}/{r['tot']:<3} {r['dmediana']:>4.0f}d "
              f"{r['n']:>5} {r['trd_dia']:>5.1f} {r['wr']:>3.0f}% {r['pf']:>5.2f} {r['net']:>10,.0f}")

    print("="*98)
    print("  CENARIO                          taxa  aprov   d.med trades t/dia  WR    PF   PnL$/ano")
    print("="*98)
    print("  --- NOTURNA SOZINHA em 5min ---")
    for g in ('corpo','extremo'):
        linha(f"noturna5m [{g}]", bt(bars5, False, True, dom, gatilho=g))
    print("  --- MISTO: diurna 1min + noturna 5min ---")
    res = {}
    for g in ('corpo','extremo'):
        r = bt(bars1m, True, True, dom, mixed5=True, gatilho=g); res[g]=r
        linha(f"misto d1m+n5m [{g}]", r)
    print("="*98)
    print("\n  Quebra dos trades NOTURNOS no misto:")
    for g in ('corpo','extremo'):
        nn = res[g]['not']
        print(f"    [{g:>7s}]: {nn['n']:>4} trades | WR {nn['wr']:>3.0f}% | PF {nn['pf']:>4.2f} | ${nn['net']:>8,.0f}")
    print("\n  OOS do MISTO (1a | 2a metade):")
    a,b = split(bars1m)
    for g in ('corpo','extremo'):
        r1 = bt(a, True, True, dom, mixed5=True, gatilho=g); r2 = bt(b, True, True, dom, mixed5=True, gatilho=g)
        print(f"    [{g:>7s}]: {r1['aprov']:>2}/{r1['tot']:<2} ({r1['taxa']:>3.0f}%) PF {r1['pf']:.2f} | "
              f"{r2['aprov']:>2}/{r2['tot']:<2} ({r2['taxa']:>3.0f}%) PF {r2['pf']:.2f}")
