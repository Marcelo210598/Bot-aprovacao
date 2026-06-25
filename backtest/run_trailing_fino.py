#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VARREDURA FINA: TrailingPontos na faixa 1.75 -> 3.0 (passo 0.25), BE_trig fixo 3.75 (25/06)
Pergunta do Andersson: o trail de 1.75pt fecha o trade com pouca variacao do candle.
O sweep antigo (run_trailing_sweep.py) pulou de 1.75 direto pra 3 -> nao mediu o "proximo
nivel acima de 1.75". Aqui mede 1.75 / 2.0 / 2.25 / 2.5 / 2.75 / 3.0 sem achismo.

Engine = IDENTICA a run_trailing_sweep.py (config de producao, modo DOM-NOITE).
So muda o grid de trailing pra ser fino. Avalia aprovacao, dias-mediana, WR, PF, PnL e OOS.
"""
import glob, os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
MNQ_PV = 2.0; RT_PER = 1.20
META = 1500.0; DD = 1500.0; MIN_DIAS = 7
TICK = 0.25; N_CONTR = 5
PTS_SL = 12.5; TOL_TICKS = 20; TP = 60.0; MAX_DIST = 15.0
ENTRADA_FIM = 16*60; FLATTEN = 16*60+55; ENTRADA_INI = 9*60+30
STOP_DIA = 750.0

BASE_BE_TRIG = 3.75; BASE_TRAIL = 1.75


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


def domingo_ranges(bars):
    dom_noite = {}
    for b in bars:
        dt = b['dt']; wd = dt.weekday(); m = mins(dt)
        if wd == 6 and m >= 18*60:
            seg = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
            if seg not in dom_noite: dom_noite[seg] = [b['h'], b['l']]
            else: dom_noite[seg][0] = max(dom_noite[seg][0], b['h']); dom_noite[seg][1] = min(dom_noite[seg][1], b['l'])
    return {k: tuple(v) for k, v in dom_noite.items()}


def bt(bars, be_trig, trail, dom_map):
    """Modo DOM-NOITE fixo (producao). be_lock = min(2.5, be_trig) p/ nunca passar do gatilho."""
    be_lock = min(2.5, be_trig)
    pv = MNQ_PV * N_CONTR; rt = RT_PER * N_CONTR
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False
    realized = 0.0; trades = []
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None
    aprov = reprov = 0; d2a = []; pnl_d0 = 0.0; block = False; dia_k = None
    seg_hoje = None

    def fecha(p):
        nonlocal pos, realized
        if pos == 0: return
        g = (p - entry) * pos * pv - rt
        realized += g; trades.append(g); pos = 0

    for b in bars:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d'); wd = dt.weekday()
        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = cur_lo = None
            seg_hoje = dom_map[d] if (wd == 0 and d in dom_map) else None
        if ENTRADA_INI <= m < 16*60:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
        if d != dia_k:
            dia_k = d; pnl_d0 = realized; block = False
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
                    if not be_done and (fav - entry) >= be_trig:
                        stop = max(stop, entry + be_lock); be_done = True
                    if be_done: stop = max(stop, fav - trail)
                else:
                    fav = min(fav, b['l'])
                    if not be_done and (entry - fav) >= be_trig:
                        stop = min(stop, entry - be_lock); be_done = True
                    if be_done: stop = min(stop, fav + trail)
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
        if m >= FLATTEN:
            if pos != 0: fecha(b['c'])
            continue
        niv_hi = seg_hoje[0] if seg_hoje else pd_hi
        niv_lo = seg_hoje[1] if seg_hoje else pd_lo
        if not block and pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM and niv_hi is not None:
            tol = TOL_TICKS * TICK; h, l, c = b['h'], b['l'], b['c']; lado = 0
            if h >= niv_hi - tol and c < niv_hi:
                if MAX_DIST == 0 or (niv_hi - c) <= MAX_DIST: lado = -1
            elif l <= niv_lo + tol and c > niv_lo:
                if MAX_DIST == 0 or (c - niv_lo) <= MAX_DIST: lado = 1
            if lado != 0:
                entry = c; pos = lado; fav = c; be_done = False
                stop = c - lado * PTS_SL; target = c + lado * TP; dias.add(d)
    if pos != 0: fecha(bars[-1]['c'])

    wins = [t for t in trades if t > 0]; n = len(trades); tot = aprov + reprov
    gw = sum(wins); gl = abs(sum(t for t in trades if t <= 0))
    ds = sorted(d2a); med = ds[len(ds)//2] if ds else 0
    avg_win = gw / len(wins) if wins else 0
    losses = [t for t in trades if t <= 0]
    avg_loss = sum(losses) / len(losses) if losses else 0
    return {
        'n': n, 'wr': 100 * len(wins) / n if n else 0,
        'pf': gw / gl if gl > 0 else 99,
        'net': sum(trades), 'aprov': aprov, 'reprov': reprov, 'tot': tot,
        'taxa': 100 * aprov / tot if tot else 0,
        'dmediana': med, 'avg_win': avg_win, 'avg_loss': avg_loss,
    }


def linha(label, r):
    print(f"  {label:>22s} {r['taxa']:>4.0f}% {r['aprov']:>4}/{r['tot']:<3} "
          f"{r['dmediana']:>4.0f}d {r['n']:>5} {r['wr']:>4.0f}% {r['pf']:>5.2f} "
          f"{r['avg_win']:>7.0f} {r['avg_loss']:>7.0f} {r['net']:>11,.0f}")


if __name__ == '__main__':
    print("Carregando NQ 1-min..."); bars = carregar('NQ_dados')
    dom = domingo_ranges(bars)
    meio = bars[len(bars)//2]['dt']
    b1 = [b for b in bars if b['dt'] < meio]; b2 = [b for b in bars if b['dt'] >= meio]
    print(f"{len(bars):,} barras | 5 MNQ, tol 20t, chase 15pt, stop 12.5pt, alvo 60pt, modo DOM-NOITE")
    print(f"Baseline producao: BE_TRIG {BASE_BE_TRIG}pt / TRAIL {BASE_TRAIL}pt\n")

    TRAIL_GRID = [1.75, 2.0, 2.25, 2.5, 2.75, 3.0]

    print("=" * 96)
    print("  VARREDURA FINA DO TRAILING (BE_trig fixo 3.75)  (* = baseline de producao)")
    print("=" * 96)
    print(f"  {'BE_trig / trail':>22s} {'taxa':>5s} {'aprov':>8s} "
          f"{'dmed':>5s} {'trds':>5s} {'WR':>5s} {'PF':>5s} "
          f"{'avgWin':>7s} {'avgLos':>7s} {'PnL$':>11s}")
    print("-" * 96)

    resultados = []
    for tr in TRAIL_GRID:
        r = bt(bars, BASE_BE_TRIG, tr, dom)
        tag = " *" if tr == BASE_TRAIL else ""
        linha(f"BE{BASE_BE_TRIG:g} / tr{tr:g}{tag}", r)
        resultados.append((BASE_BE_TRIG, tr, r))

    ranked = sorted(resultados, key=lambda x: (-x[2]['taxa'], x[2]['dmediana'], -x[2]['net']))
    print("\n" + "=" * 96)
    print("  RANKING (por taxa de aprovacao -> menos dias -> mais PnL)")
    print("=" * 96)
    for be, tr, r in ranked:
        linha(f"BE{be:g} / tr{tr:g}", r)

    print("\n" + "=" * 96)
    print("  ROBUSTEZ OUT-OF-SAMPLE (1a metade | 2a metade) — todos os niveis do grid")
    print("=" * 96)
    for tr in TRAIL_GRID:
        r1 = bt(b1, BASE_BE_TRIG, tr, dom); r2 = bt(b2, BASE_BE_TRIG, tr, dom)
        base = " *" if tr == BASE_TRAIL else ""
        print(f"  BE3.75/tr{tr:g}{base:>3s}  "
              f"{r1['aprov']:>2}/{r1['tot']:<2} ({r1['taxa']:>3.0f}%) PF {r1['pf']:>4.2f} med {r1['dmediana']:>3.0f}d WR {r1['wr']:>3.0f}%   |   "
              f"{r2['aprov']:>2}/{r2['tot']:<2} ({r2['taxa']:>3.0f}%) PF {r2['pf']:>4.2f} med {r2['dmediana']:>3.0f}d WR {r2['wr']:>3.0f}%")
    print("-" * 96)
