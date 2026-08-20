#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SIZING SELETIVO (20/08) — em vez de CORTAR trades fora do padrao bom (dist perto
da linha / sexta-feira, achados de diagnostico_mfe_mae.py), AUMENTA o tamanho so
nesses trades especificos, mantendo TODOS os outros trades no tamanho normal (5
MNQ). Objetivo: concentrar mais risco onde o dado mostra mais qualidade, SEM
reduzir a frequencia total de trade (que foi o que matou os filtros de corte
testados em run_qualidade_entrada_sweep.py -- mediana de dias pra aprovar
estourava os 30 dias do produto Apex).

Motor identico a run_qualidade_entrada_sweep.py (DD real $1000, MaxTradesDia=12,
slippage 2 ticks, nivel de domingo, config atual de producao como base), com
UMA mudanca: contratos por trade agora e' VARIAVEL -- 5 (base) ou um valor maior
("boost") quando o trade de abertura bate o criterio de qualidade.
"""
import glob, os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
MNQ_PV = 2.0; RT_PER = 1.20
MIN_DIAS = 7
TICK = 0.25
PTS_SL = 12.5; PTS_BE_TRIG = 3.75; PTS_BE_LOCK = 2.5; PTS_TRAIL = 1.75
TOL_TICKS = 20; TP = 60.0; MAX_DIST = 15.0
ENTRADA_INI = 9*60+30; ENTRADA_FIM = 16*60; FLATTEN = 16*60+55
SLIP_BASE = 2.0
CONSIST = 0.50


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
    dom = {}
    for b in bars:
        dt = b['dt']; wd = dt.weekday(); m = mins(dt)
        if wd == 6 and m >= 18*60:
            seg = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
            if seg not in dom: dom[seg] = [b['h'], b['l']]
            else: dom[seg][0] = max(dom[seg][0], b['h']); dom[seg][1] = min(dom[seg][1], b['l'])
    return {k: tuple(v) for k, v in dom.items()}


def bt(bars, dom_map=None, meta=1500.0, dd=1000.0, stop_dia=750.0,
       max_trades=12, slip_ticks=SLIP_BASE, base_contr=5,
       boost_contr=None, boost_dist=None, boost_dow=None):
    """DIURNA only. boost_contr: qtd de contratos quando o trade de abertura bate
    o criterio de qualidade (boost_dist e/ou boost_dow); senao usa base_contr.
    boost_dist: dist_nivel <= X pt (None = nao usa esse criterio).
    boost_dow: set de weekdays que tambem contam como qualidade (None = nao usa)."""
    slip = slip_ticks * TICK
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False; contr_atual = base_contr
    realized = 0.0; trades = []
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None
    aprov = reprov = 0; d2a = []; pnl_d0 = 0.0; block = False; dia_k = None
    seg_hoje = None; trades_hoje = 0
    cycle_days = {}
    n_boost = 0   # quantos trades usaram o tamanho boost (contagem, p/ conferencia)

    def fecha(p, d):
        nonlocal pos, realized
        if pos == 0: return
        pv = MNQ_PV * contr_atual; rt = RT_PER * contr_atual
        g = ((p - entry) * pos - 2 * slip) * pv - rt
        realized += g; trades.append(g)
        cycle_days[d] = cycle_days.get(d, 0.0) + g
        pos = 0

    for b in bars:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d'); wd = dt.weekday()

        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = cur_lo = None
            seg_hoje = dom_map[d] if (dom_map and wd == 0 and d in dom_map) else None
        if ENTRADA_INI <= m < 16*60:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
        if d != dia_k:
            dia_k = d; pnl_d0 = realized; block = False; trades_hoje = 0
        if ini_aval is None: ini_aval = dt

        pv_atual = MNQ_PV * contr_atual
        if pos != 0:
            saiu = False
            if pos > 0:
                if b['l'] <= stop: fecha(stop, d); saiu = True
                elif b['h'] >= target: fecha(target, d); saiu = True
            else:
                if b['h'] >= stop: fecha(stop, d); saiu = True
                elif b['l'] <= target: fecha(target, d); saiu = True
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

        pr = realized - r_ini
        ua = uf = 0.0
        if pos > 0: ua = (b['l'] - entry) * pv_atual; uf = (b['h'] - entry) * pv_atual
        elif pos < 0: ua = (entry - b['h']) * pv_atual; uf = (entry - b['l']) * pv_atual
        if pr + uf > pico: pico = pr + uf
        if stop_dia > 0 and (realized - pnl_d0 + ua) <= -stop_dia:
            block = True
            if pos != 0: fecha(b['c'], d)
        if pr + ua <= pico - dd:
            fecha(b['c'], d); reprov += 1
            r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt; cycle_days = {}
        elif pr >= meta and len(dias) >= MIN_DIAS:
            fecha(b['c'], d); aprov += 1
            d2a.append((dt - ini_aval).days)
            r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt; cycle_days = {}

        if m >= FLATTEN and pos != 0:
            fecha(b['c'], d)
        lim_ok = (max_trades == 0 or trades_hoje < max_trades)
        if not block and lim_ok and pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
            niv_hi = seg_hoje[0] if seg_hoje else pd_hi
            niv_lo = seg_hoje[1] if seg_hoje else pd_lo
            if niv_hi is not None:
                tol = TOL_TICKS * TICK; h, l, c = b['h'], b['l'], b['c']; lado = 0; dist_atual = 0.0
                if h >= niv_hi - tol and c < niv_hi:
                    dist_atual = niv_hi - c
                    if MAX_DIST == 0 or dist_atual <= MAX_DIST: lado = -1
                elif l <= niv_lo + tol and c > niv_lo:
                    dist_atual = c - niv_lo
                    if MAX_DIST == 0 or dist_atual <= MAX_DIST: lado = 1
                if lado != 0:
                    qualidade = ((boost_dist is not None and dist_atual <= boost_dist) or
                                 (boost_dow is not None and wd in boost_dow))
                    contr_atual = boost_contr if (qualidade and boost_contr) else base_contr
                    if qualidade and boost_contr: n_boost += 1
                    entry = c; pos = lado; fav = c; be_done = False
                    stop = c - lado * PTS_SL; target = c + lado * TP
                    dias.add(d); trades_hoje += 1

    if pos != 0: fecha(bars[-1]['c'], dia)

    w = [t for t in trades if t > 0]; n = len(trades)
    gw = sum(w); gl = abs(sum(t for t in trades if t <= 0))
    tot = aprov + reprov; ds = sorted(d2a); med = ds[len(ds)//2] if ds else 0
    return {'n': n, 'wr': 100*len(w)/n if n else 0, 'pf': gw/gl if gl > 0 else 99,
            'net': sum(trades), 'aprov': aprov, 'reprov': reprov, 'tot': tot,
            'taxa': 100*aprov/tot if tot else 0, 'dmediana': med,
            'trd_dia': n/220, 'n_boost': n_boost}


def linha(label, r):
    print(f"  {label:>30s} {r['taxa']:>4.0f}% {r['aprov']:>3}/{r['tot']:<3} {r['dmediana']:>4.0f}d "
          f"{r['n']:>5} {r['n_boost']:>6} {r['wr']:>3.0f}% {r['pf']:>5.2f} {r['net']:>9,.0f}")


if __name__ == '__main__':
    print("Carregando NQ 1-min real..."); bars = carregar('NQ_dados')
    dom = domingo_ranges(bars)
    meio = bars[len(bars)//2]['dt']
    b1 = [b for b in bars if b['dt'] < meio]; b2 = [b for b in bars if b['dt'] >= meio]
    dom1 = domingo_ranges(b1); dom2 = domingo_ranges(b2)
    print(f"{len(bars):,} barras | DIURNA only | slippage 2t | DD real $1000 | MaxTradesDia=12 | base=5 MNQ\n")
    H = f"  {'cenario':>30s} {'taxa':>5s} {'aprov':>7s} {'d.med':>5s} {'trds':>5s} {'boost':>6s} {'WR':>4s} {'PF':>5s} {'PnL$':>9s}"

    print("=" * 100)
    print("  SIZING SELETIVO por dist_nivel<=5pt (base 5 MNQ, boost quando bate o criterio)")
    print("=" * 100); print(H); print("-" * 100)
    cfgs_dist = [
        ("baseline (5 MNQ sempre)", None, None, None),
        ("boost 6 MNQ @ dist<=5pt", 6, 5.0, None),
        ("boost 7 MNQ @ dist<=5pt", 7, 5.0, None),
        ("boost 8 MNQ @ dist<=5pt", 8, 5.0, None),
    ]
    for lbl, bc, bd, bw in cfgs_dist:
        linha(lbl, bt(bars, dom, boost_contr=bc, boost_dist=bd, boost_dow=bw))
    print("-" * 100)
    print("  OOS (1a metade x 2a metade):")
    for lbl, bc, bd, bw in cfgs_dist:
        r1 = bt(b1, dom1, boost_contr=bc, boost_dist=bd, boost_dow=bw)
        r2 = bt(b2, dom2, boost_contr=bc, boost_dist=bd, boost_dow=bw)
        print(f"  {lbl:>30s}  1a: {r1['aprov']:>2}/{r1['tot']:<3}({r1['taxa']:>3.0f}%) PF{r1['pf']:>5.2f} "
              f"med{r1['dmediana']:>3.0f}d   2a: {r2['aprov']:>2}/{r2['tot']:<3}({r2['taxa']:>3.0f}%) PF{r2['pf']:>5.2f} med{r2['dmediana']:>3.0f}d")
    print("=" * 100 + "\n")

    print("=" * 100)
    print("  SIZING SELETIVO por sexta-feira (base 5 MNQ, boost quando dow=4)")
    print("=" * 100); print(H); print("-" * 100)
    cfgs_dow = [
        ("baseline (5 MNQ sempre)", None, None, None),
        ("boost 6 MNQ @ sexta", 6, None, {4}),
        ("boost 7 MNQ @ sexta", 7, None, {4}),
        ("boost 8 MNQ @ sexta", 8, None, {4}),
    ]
    for lbl, bc, bd, bw in cfgs_dow:
        linha(lbl, bt(bars, dom, boost_contr=bc, boost_dist=bd, boost_dow=bw))
    print("-" * 100)
    print("  OOS (1a metade x 2a metade):")
    for lbl, bc, bd, bw in cfgs_dow:
        r1 = bt(b1, dom1, boost_contr=bc, boost_dist=bd, boost_dow=bw)
        r2 = bt(b2, dom2, boost_contr=bc, boost_dist=bd, boost_dow=bw)
        print(f"  {lbl:>30s}  1a: {r1['aprov']:>2}/{r1['tot']:<3}({r1['taxa']:>3.0f}%) PF{r1['pf']:>5.2f} "
              f"med{r1['dmediana']:>3.0f}d   2a: {r2['aprov']:>2}/{r2['tot']:<3}({r2['taxa']:>3.0f}%) PF{r2['pf']:>5.2f} med{r2['dmediana']:>3.0f}d")
    print("=" * 100 + "\n")

    print("=" * 100)
    print("  COMBINADO (dist<=5pt OU sexta), boost 7 MNQ")
    print("=" * 100); print(H); print("-" * 100)
    linha("baseline (5 MNQ sempre)", bt(bars, dom))
    linha("boost 7 MNQ @ dist<=5 OU sexta", bt(bars, dom, boost_contr=7, boost_dist=5.0, boost_dow={4}))
    print("=" * 100)
