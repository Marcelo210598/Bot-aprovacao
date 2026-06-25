#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SAIDA PARCIAL / SCALE-OUT (25/06) — pedido do Marcelo + Andersson.
Problema: trailing 1,75 fixo trava a "merreca" e perde os trades que pullbackam raso
e DEPOIS correm forte. Sweep uniforme e escalonado ja foram rejeitados (pioram a media).
Esta e a unica alternativa nao testada: DIVIDIR a posicao.

  - PERNA SCALP (q_scalp contratos): sai no trailing apertado 1,75 (igual hoje) -> garante
    o win e segura o WR alto.
  - PERNA RUNNER (q_run contratos): apos o breakeven, NAO trilha apertado. Fica com stop no
    BE-lock (+2,5) [modo 'be'] ou trilha largo W [modo 'trailW'], e corre ate o alvo 60pt.

Engine = IDENTICA aos outros sweeps (producao, DOM-NOITE): tol 20t, chase 15pt, stop 12,5,
alvo 60, stop/dia $750, conta 25K Intraday (META/DD 1500), 5 MNQ no total.
Valida reproduzindo o baseline (q_run=0 -> deve bater $38.932 / 21 aprov / 14d).
"""
import glob, os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
MNQ_PV = 2.0; RT_PER = 1.20          # por contrato
META = 1500.0; DD = 1500.0; MIN_DIAS = 7
TICK = 0.25; N_TOTAL = 5
PTS_SL = 12.5; PTS_BE_TRIG = 3.75; PTS_BE_LOCK = 2.5; PTS_TRAIL = 1.75
TOL_TICKS = 20; TP = 60.0; MAX_DIST = 15.0
ENTRADA_FIM = 16*60; FLATTEN = 16*60+55; ENTRADA_INI = 9*60+30
STOP_DIA = 750.0


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


def bt(bars, dom_map, q_run=0, run_mode='be', run_w=8.0):
    """q_run = contratos na perna runner (0 = baseline puro, todos no trailing 1,75).
    run_mode: 'be' = runner para no BE-lock e mira o alvo; 'trailW' = runner trilha largo run_w."""
    q_scalp = N_TOTAL - q_run
    pos = 0; entry = 0.0; fav = 0.0; be_done = False
    qs = qr = 0                       # contratos abertos em cada perna
    stop_s = stop_r = target = 0.0    # stops por perna; target comum (alvo)
    realized = 0.0; trades = []       # cada saida (de cada perna) e um "trade" de PnL
    n_alvo_run = 0; pnl_alvo_run = 0.0
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None
    aprov = reprov = 0; d2a = []; pnl_d0 = 0.0; block = False; dia_k = None
    seg_hoje = None

    def fecha_perna(qty, p, is_run):
        nonlocal realized, n_alvo_run, pnl_alvo_run
        if qty <= 0: return 0.0
        g = (p - entry) * pos * MNQ_PV * qty - RT_PER * qty
        realized += g; trades.append(g)
        return g

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
            # ---- 1) checa saidas com os stops/target VIGENTES (da barra anterior) ----
            #         prioriza stop sobre alvo (elif), igual ao baseline. SEM look-ahead.
            if pos > 0:
                if qs > 0:
                    if b['l'] <= stop_s: fecha_perna(qs, stop_s, False); qs = 0
                    elif b['h'] >= target: fecha_perna(qs, target, False); qs = 0
                if qr > 0:
                    if b['l'] <= stop_r: fecha_perna(qr, stop_r, True); qr = 0
                    elif b['h'] >= target:
                        g = fecha_perna(qr, target, True); qr = 0
                        n_alvo_run += 1; pnl_alvo_run += g
            else:
                if qs > 0:
                    if b['h'] >= stop_s: fecha_perna(qs, stop_s, False); qs = 0
                    elif b['l'] <= target: fecha_perna(qs, target, False); qs = 0
                if qr > 0:
                    if b['h'] >= stop_r: fecha_perna(qr, stop_r, True); qr = 0
                    elif b['l'] <= target:
                        g = fecha_perna(qr, target, True); qr = 0
                        n_alvo_run += 1; pnl_alvo_run += g
            if qs == 0 and qr == 0: pos = 0
            # ---- 2) se ainda aberto, atualiza fav + stops com a barra atual (vale p/ proxima) ----
            if pos != 0:
                if pos > 0:
                    fav = max(fav, b['h'])
                    if not be_done and (fav - entry) >= PTS_BE_TRIG:
                        be_done = True
                        stop_s = max(stop_s, entry + PTS_BE_LOCK)
                        stop_r = max(stop_r, entry + PTS_BE_LOCK)
                    if be_done:
                        stop_s = max(stop_s, fav - PTS_TRAIL)
                        if run_mode == 'trailW': stop_r = max(stop_r, fav - run_w)
                else:
                    fav = min(fav, b['l'])
                    if not be_done and (entry - fav) >= PTS_BE_TRIG:
                        be_done = True
                        stop_s = min(stop_s, entry - PTS_BE_LOCK)
                        stop_r = min(stop_r, entry - PTS_BE_LOCK)
                    if be_done:
                        stop_s = min(stop_s, fav + PTS_TRAIL)
                        if run_mode == 'trailW': stop_r = min(stop_r, fav + run_w)

        # ---- controle de aprovacao / DD / stop diario (posicao combinada aberta) ----
        qty_open = qs + qr
        pr = realized - r_ini
        ua = uf = 0.0
        if pos > 0: ua = (b['l'] - entry) * MNQ_PV * qty_open; uf = (b['h'] - entry) * MNQ_PV * qty_open
        elif pos < 0: ua = (entry - b['h']) * MNQ_PV * qty_open; uf = (entry - b['l']) * MNQ_PV * qty_open
        if pr + uf > pico: pico = pr + uf
        if STOP_DIA > 0 and (realized - pnl_d0 + ua) <= -STOP_DIA:
            block = True
            if pos != 0:
                if qs > 0: fecha_perna(qs, b['c'], False)
                if qr > 0: fecha_perna(qr, b['c'], True)
                qs = qr = 0; pos = 0
        if pr + ua <= pico - DD:
            if pos != 0:
                if qs > 0: fecha_perna(qs, b['c'], False)
                if qr > 0: fecha_perna(qr, b['c'], True)
                qs = qr = 0; pos = 0
            reprov += 1; r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt
        elif pr >= META and len(dias) >= MIN_DIAS:
            if pos != 0:
                if qs > 0: fecha_perna(qs, b['c'], False)
                if qr > 0: fecha_perna(qr, b['c'], True)
                qs = qr = 0; pos = 0
            aprov += 1; d2a.append((dt - ini_aval).days)
            r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt
        if m >= FLATTEN:
            if pos != 0:
                if qs > 0: fecha_perna(qs, b['c'], False)
                if qr > 0: fecha_perna(qr, b['c'], True)
                qs = qr = 0; pos = 0
            continue

        # ---- entrada ----
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
                qs = q_scalp; qr = q_run
                stop_s = stop_r = c - lado * PTS_SL
                target = c + lado * TP; dias.add(d)
    if pos != 0:
        if qs > 0: fecha_perna(qs, bars[-1]['c'], False)
        if qr > 0: fecha_perna(qr, bars[-1]['c'], True)

    wins = [t for t in trades if t > 0]; n = len(trades); tot = aprov + reprov
    gw = sum(wins); gl = abs(sum(t for t in trades if t <= 0))
    ds = sorted(d2a); med = ds[len(ds)//2] if ds else 0
    return {
        'n': n, 'wr': 100 * len(wins) / n if n else 0,
        'pf': gw / gl if gl > 0 else 99, 'net': sum(trades),
        'aprov': aprov, 'reprov': reprov, 'tot': tot,
        'taxa': 100 * aprov / tot if tot else 0, 'dmediana': med,
        'n_alvo_run': n_alvo_run, 'pnl_alvo_run': pnl_alvo_run,
    }


def linha(label, r):
    print(f"  {label:>26s} {r['taxa']:>4.0f}% {r['aprov']:>4}/{r['tot']:<3} "
          f"{r['dmediana']:>4.0f}d {r['wr']:>4.0f}% {r['pf']:>5.2f} "
          f"{r['n_alvo_run']:>6} {r['pnl_alvo_run']:>10,.0f} {r['net']:>11,.0f}")


if __name__ == '__main__':
    print("Carregando NQ 1-min..."); bars = carregar('NQ_dados')
    dom = domingo_ranges(bars)
    meio = bars[len(bars)//2]['dt']
    b1 = [b for b in bars if b['dt'] < meio]; b2 = [b for b in bars if b['dt'] >= meio]
    print(f"{len(bars):,} barras | 5 MNQ total, tol 20t, chase 15pt, stop 12,5, alvo 60, DOM-NOITE\n")

    print("=" * 100)
    print("  SAIDA PARCIAL: q_scalp (trail 1,75) + q_runner (corre ate alvo 60)  vs  BASELINE")
    print("=" * 100)
    print(f"  {'config':>26s} {'taxa':>5s} {'aprov':>8s} {'dmed':>5s} "
          f"{'WR':>5s} {'PF':>5s} {'#alvoR':>6s} {'$alvoR':>10s} {'PnL$':>11s}")
    print("-" * 100)

    base = bt(bars, dom, q_run=0)
    linha("BASELINE 5x trail1,75 *", base)
    print()

    cfgs = []
    # runner mira o alvo, parado no BE-lock
    for qr in [1, 2, 3]:
        r = bt(bars, dom, q_run=qr, run_mode='be')
        linha(f"{5-qr}scalp + {qr}run(BE->alvo)", r); cfgs.append((f"{5-qr}+{qr} BE", qr, 'be', None, r))
    print()
    # runner trilha largo (8pt) em vez de mirar so o alvo
    for qr in [1, 2, 3]:
        for w in [6, 10]:
            r = bt(bars, dom, q_run=qr, run_mode='trailW', run_w=w)
            linha(f"{5-qr}scalp + {qr}run(trailW{w:g})", r)
            cfgs.append((f"{5-qr}+{qr} W{w:g}", qr, 'trailW', w, r))

    print("\n" + "=" * 100)
    print("  LEITURA: alguem bate o baseline em PnL mantendo 100% aprovacao?")
    print("=" * 100)
    print(f"  baseline -> taxa {base['taxa']:.0f}% | {base['aprov']}/{base['tot']} | {base['dmediana']:.0f}d | PnL ${base['net']:,.0f}")
    cands = sorted(cfgs, key=lambda x: (-x[4]['taxa'], -x[4]['net']))
    best = cands[0]
    print(f"  melhor parcial ({best[0]}) -> taxa {best[4]['taxa']:.0f}% | {best[4]['aprov']}/{best[4]['tot']} | {best[4]['dmediana']:.0f}d | PnL ${best[4]['net']:,.0f}")
    delta = best[4]['net'] - base['net']
    print(f"  delta PnL: ${delta:+,.0f}  ({'MELHOR' if delta > 0 else 'PIOR'} que baseline)")

    print("\n" + "=" * 100)
    print("  ROBUSTEZ OOS do melhor parcial vs baseline (1a metade | 2a metade)")
    print("=" * 100)
    for label, qr, mode, w, _ in [("BASELINE", 0, 'be', None, None), (best[0], best[1], best[2], best[3], None)]:
        kw = {'q_run': qr, 'run_mode': mode}
        if w is not None: kw['run_w'] = w
        r1 = bt(b1, dom, **kw); r2 = bt(b2, dom, **kw)
        print(f"  {label:>16s}  {r1['aprov']:>2}/{r1['tot']:<2} ({r1['taxa']:>3.0f}%) PF {r1['pf']:>4.2f} med {r1['dmediana']:>3.0f}d ${r1['net']:>9,.0f}  |  "
              f"{r2['aprov']:>2}/{r2['tot']:<2} ({r2['taxa']:>3.0f}%) PF {r2['pf']:>4.2f} med {r2['dmediana']:>3.0f}d ${r2['net']:>9,.0f}")
    print("-" * 100)
