#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TESTE DE TOLERANCIA DE TOQUE (pedido do forward test 13/06).
Pergunta: e se o bot aceitasse toques "no fio" / quase-toques na max/min do dia
anterior? Hoje a tolerancia e 6 ticks (1,5pt). Aqui varremos varias tolerancias
mantendo TODO o resto da config vencedora (5 MNQ, TP 60, trail 1,75, stop diario
$750, sem limite de trades) e comparamos taxa de aprovacao, dias e robustez.

OBS: a tolerancia mede o quao LONGE da linha o candle pode estar e ainda contar
como "toque". A regra de rejeicao (fechar do lado certo da linha) NAO muda.
"""
import glob, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
MNQ_PV = 2.0; RT_PER = 1.20
META = 1500.0; DD = 1500.0; MIN_DIAS = 7
TICK = 0.25
N_CONTR = 5
PTS_SL = 12.5; PTS_BE_TRIG = 3.75; PTS_BE_LOCK = 2.5; PTS_TRAIL = 1.75

# Config vencedora fixa (so a tolerancia varia)
TP = 60.0; TRAIL = 1.75; STOP_DIA_PT = 75.0; MAX_TRD = 99


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
                if dt not in vistos: vistos[dt] = (dt.astimezone(ET), o, h, l, c, v)
    return [{'dt': vistos[k][0], 'o': vistos[k][1], 'h': vistos[k][2],
             'l': vistos[k][3], 'c': vistos[k][4], 'v': vistos[k][5]} for k in sorted(vistos)]


def mins(dt): return dt.hour*60 + dt.minute


def bt(bars, tol_ticks=6, pts_tp=TP, pts_trail=TRAIL, pts_stop_dia=STOP_DIA_PT, max_trades=MAX_TRD):
    pv = MNQ_PV * N_CONTR; rt = RT_PER * N_CONTR; stop_dia = pts_stop_dia * pv
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False
    realized = 0.0; trades = []
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None
    aprov = reprov = 0; d2a = []; pnl_d0 = 0.0; block = False; dia_k = None; trades_dia = 0

    def fecha(p):
        nonlocal pos, realized
        if pos == 0: return
        realized += (p-entry)*pos*pv - rt; trades.append((p-entry)*pos*pv - rt); pos = 0

    for b in bars:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d')
        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = cur_lo = None
        if 9*60+30 <= m < 16*60:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
        if d != dia_k: dia_k = d; pnl_d0 = realized; block = False; trades_dia = 0
        if ini_aval is None: ini_aval = dt
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
                    if not be_done and (fav-entry) >= PTS_BE_TRIG: stop = max(stop, entry+PTS_BE_LOCK); be_done = True
                    if be_done: stop = max(stop, fav-pts_trail)
                else:
                    fav = min(fav, b['l'])
                    if not be_done and (entry-fav) >= PTS_BE_TRIG: stop = min(stop, entry-PTS_BE_LOCK); be_done = True
                    if be_done: stop = min(stop, fav+pts_trail)
        pr = realized - r_ini
        ua = uf = 0.0
        if pos > 0: ua = (b['l']-entry)*pv; uf = (b['h']-entry)*pv
        elif pos < 0: ua = (entry-b['h'])*pv; uf = (entry-b['l'])*pv
        if pr+uf > pico: pico = pr+uf
        if stop_dia > 0 and (realized - pnl_d0 + ua) <= -stop_dia:
            block = True
            if pos != 0: fecha(b['c'])
        if pr+ua <= pico - DD:
            fecha(b['c']); reprov += 1; r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt
        elif pr >= META and len(dias) >= MIN_DIAS:
            fecha(b['c']); aprov += 1; d2a.append((dt-ini_aval).days)
            r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt
        if m >= 15*60+55:
            if pos != 0: fecha(b['c'])
            continue
        if not block and pos == 0 and trades_dia < max_trades and 9*60+30 <= m < 15*60 and pd_hi is not None:
            tol = tol_ticks*TICK; h, l, c = b['h'], b['l'], b['c']; lado = 0
            if h >= pd_hi-tol and c < pd_hi: lado = -1
            elif l <= pd_lo+tol and c > pd_lo: lado = 1
            if lado != 0:
                entry = c; pos = lado; fav = c; be_done = False
                stop = c - lado*PTS_SL; target = c + lado*pts_tp; dias.add(d); trades_dia += 1
    if pos != 0: fecha(bars[-1]['c'])

    wins = [t for t in trades if t > 0]; n = len(trades); tot = aprov+reprov
    gw = sum(wins); gl = abs(sum(t for t in trades if t <= 0))
    ds = sorted(d2a); med = ds[len(ds)//2] if ds else 0
    return {'n': n, 'wr': 100*len(wins)/n if n else 0, 'pf': (gw/gl if gl > 0 else 99),
            'net': sum(trades), 'aprov': aprov, 'reprov': reprov, 'tot': tot,
            'taxa': 100*aprov/tot if tot else 0,
            'dmed': sum(d2a)/len(d2a) if d2a else 0, 'dmediana': med,
            'dmin': min(d2a) if d2a else 0, 'dmax': max(d2a) if d2a else 0,
            'trd_dia': n/220}


if __name__ == '__main__':
    print("Carregando NQ 1-min real..."); bars = carregar('NQ_dados')
    meio = bars[len(bars)//2]['dt']
    b1 = [b for b in bars if b['dt'] < meio]; b2 = [b for b in bars if b['dt'] >= meio]
    print(f"{len(bars):,} barras | 5 MNQ, TP {TP:.0f}, trail {TRAIL}, stop diario ${STOP_DIA_PT*MNQ_PV*N_CONTR:.0f}, sem limite\n")

    print("="*104)
    print("  VARREDURA DE TOLERANCIA DE TOQUE (resto da config vencedora fixo)")
    print("="*104)
    print(f"  {'tol(ticks)':>10s} {'tol(pts)':>8s} {'taxa':>5s} {'aprov':>6s} {'reprov':>7s} "
          f"{'d.mediana':>9s} {'d.media':>7s} {'trades':>7s} {'trd/dia':>7s} {'WR':>4s} {'PF':>5s} {'PnL$/ano':>10s}")
    print("-"*104)
    for tk in (6, 8, 10, 12, 16, 20, 24, 30, 40, 60):
        r = bt(bars, tol_ticks=tk)
        marca = "  <- ATUAL (validada)" if tk == 6 else ""
        print(f"  {tk:>10} {tk*TICK:>7.2f}p {r['taxa']:>4.0f}% {r['aprov']:>6} {r['reprov']:>7} "
              f"{r['dmediana']:>8.0f}d {r['dmed']:>6.0f}d {r['n']:>7} {r['trd_dia']:>6.1f} "
              f"{r['wr']:>3.0f}% {r['pf']:>5.2f} {r['net']:>10,.0f}{marca}")
    print("-"*104)

    print("\n" + "="*104)
    print("  ROBUSTEZ OUT-OF-SAMPLE (1a metade x 2a metade) por tolerancia")
    print("="*104)
    print(f"  {'tol(ticks)':>10s} {'1a metade':>22s} {'2a metade':>22s}")
    print("-"*104)
    for tk in (6, 10, 16, 20, 30):
        r1 = bt(b1, tol_ticks=tk); r2 = bt(b2, tol_ticks=tk)
        print(f"  {tk:>10} "
              f"{r1['aprov']:>3}/{r1['tot']:<3} ({r1['taxa']:>3.0f}%) PF {r1['pf']:>4.2f}      "
              f"{r2['aprov']:>3}/{r2['tot']:<3} ({r2['taxa']:>3.0f}%) PF {r2['pf']:>4.2f}")
    print("-"*104)
