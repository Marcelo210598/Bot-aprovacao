#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SEGUNDA-FEIRA COM LINHAS DO DOMINGO A NOITE (15/06)
Config de producao: 5 MNQ, tol 20t, TP 60, trail 1.75, maxDist 15pt,
janela 16h, stop diario $750, conta 25K Intraday.

Pergunta: na segunda, em vez de usar a linha (baguncada) de sexta/domingo-1-barra,
usar o RANGE do domingo a noite (abertura do Globex) como nivel de rejeicao.

Compara 3 cenarios:
  BASELINE  - logica atual (linha = RTH do ultimo dia com barras 9h30-16h)
  DOM-NOITE - segunda usa high/low do domingo 18h00 -> 23h59 ET
  OVERNIGHT - segunda usa high/low do domingo 18h00 -> segunda 09h29 ET
Demais dias (ter-sex): identicos nos 3 cenarios.
Tambem isola metricas SO das segundas pra medir o efeito real.
"""
import glob, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
MNQ_PV = 2.0; RT_PER = 1.20
META = 1500.0; DD = 1500.0; MIN_DIAS = 7
TICK = 0.25; N_CONTR = 5
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
    """Precalcula high/low do domingo a noite por data de SEGUNDA seguinte.
    Retorna (dom_noite, overnight): dicts {seg_date_iso: (hi, lo)}."""
    from datetime import timedelta
    dom_noite = {}; overnight = {}
    for b in bars:
        dt = b['dt']; wd = dt.weekday(); m = mins(dt)
        # Domingo 18h00-23h59 -> segunda seguinte
        if wd == 6 and m >= 18*60:
            seg = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
            for D in (dom_noite, overnight):
                if seg not in D: D[seg] = [b['h'], b['l']]
                else: D[seg][0] = max(D[seg][0], b['h']); D[seg][1] = min(D[seg][1], b['l'])
        # Segunda 00h00-09h29 -> entra so no overnight
        elif wd == 0 and m < ENTRADA_INI:
            seg = dt.strftime('%Y-%m-%d')
            if seg not in overnight: overnight[seg] = [b['h'], b['l']]
            else: overnight[seg][0] = max(overnight[seg][0], b['h']); overnight[seg][1] = min(overnight[seg][1], b['l'])
    return ({k: tuple(v) for k, v in dom_noite.items()},
            {k: tuple(v) for k, v in overnight.items()})


def bt(bars, modo='baseline', dom_map=None):
    """modo: 'baseline' | 'dom_noite' | 'overnight'. dom_map = dict seg->(hi,lo)."""
    pv = MNQ_PV * N_CONTR; rt = RT_PER * N_CONTR
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False
    realized = 0.0; trades = []
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None
    aprov = reprov = 0; d2a = []; pnl_d0 = 0.0; block = False; dia_k = None
    seg_hoje = None  # (hi, lo) override da segunda; None = usa pd normal
    # metricas isoladas de segunda
    seg_trades = []; trade_wd = None

    def fecha(p):
        nonlocal pos, realized
        if pos == 0: return
        g = (p - entry) * pos * pv - rt
        realized += g; trades.append(g)
        if trade_wd == 0: seg_trades.append(g)
        pos = 0

    for b in bars:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d'); wd = dt.weekday()
        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = cur_lo = None
            # define override de segunda
            seg_hoje = None
            if modo != 'baseline' and wd == 0 and dom_map and d in dom_map:
                seg_hoje = dom_map[d]
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
        # nivel ativo: override de segunda (se houver) senao pd normal
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
                trade_wd = wd
    if pos != 0: fecha(bars[-1]['c'])

    wins = [t for t in trades if t > 0]; n = len(trades); tot = aprov + reprov
    gw = sum(wins); gl = abs(sum(t for t in trades if t <= 0))
    ds = sorted(d2a); med = ds[len(ds)//2] if ds else 0
    sw = [t for t in seg_trades if t > 0]
    return {
        'n': n, 'wr': 100 * len(wins) / n if n else 0,
        'pf': gw / gl if gl > 0 else 99,
        'net': sum(trades), 'aprov': aprov, 'reprov': reprov, 'tot': tot,
        'taxa': 100 * aprov / tot if tot else 0,
        'dmediana': med, 'trd_dia': n / 220,
        'seg_n': len(seg_trades), 'seg_net': sum(seg_trades),
        'seg_wr': 100 * len(sw) / len(seg_trades) if seg_trades else 0,
    }


def linha(label, r):
    print(f"  {label:>26s} {r['taxa']:>4.0f}% {r['aprov']:>5} {r['reprov']:>6} "
          f"{r['dmediana']:>5.0f}d {r['n']:>6} {r['trd_dia']:>6.1f} "
          f"{r['wr']:>3.0f}% {r['pf']:>5.2f} {r['net']:>10,.0f}  | "
          f"{r['seg_n']:>4} {r['seg_wr']:>3.0f}% {r['seg_net']:>9,.0f}")


if __name__ == '__main__':
    print("Carregando NQ 1-min..."); bars = carregar('NQ_dados')
    dom_noite, overnight = domingo_ranges(bars)
    meio = bars[len(bars)//2]['dt']
    b1 = [b for b in bars if b['dt'] < meio]; b2 = [b for b in bars if b['dt'] >= meio]
    print(f"{len(bars):,} barras | 5 MNQ, tol 20t, TP 60, maxDist 15pt, janela 16h, stop/dia $750")
    print(f"Segundas com range de domingo-noite: {len(dom_noite)} | com overnight: {len(overnight)}\n")

    print("=" * 118)
    print("  SEGUNDA: BASELINE vs LINHAS DO DOMINGO A NOITE")
    print("=" * 118)
    print(f"  {'cenario':>26s} {'taxa':>5s} {'aprv':>5s} {'repr':>6s} {'d.med':>6s} "
          f"{'trds':>6s} {'t/dia':>6s} {'WR':>4s} {'PF':>5s} {'PnL$/ano':>10s}  | "
          f"{'SEG-n':>5s} {'WR':>3s} {'SEG-PnL':>9s}")
    print("-" * 118)
    linha("BASELINE (atual)", bt(bars, 'baseline'))
    linha("DOM-NOITE (18h->24h)", bt(bars, 'dom_noite', dom_noite))
    linha("OVERNIGHT (18h->9h30)", bt(bars, 'overnight', overnight))
    print("-" * 118)
    print("  (colunas apos | = SO trades de segunda-feira: qtd, win rate, PnL$/ano)")

    print("\n" + "=" * 118)
    print("  ROBUSTEZ OUT-OF-SAMPLE (1a / 2a metade)")
    print("=" * 118)
    for label, modo, mp in [("BASELINE", 'baseline', None),
                            ("DOM-NOITE", 'dom_noite', dom_noite),
                            ("OVERNIGHT", 'overnight', overnight)]:
        r1 = bt(b1, modo, mp); r2 = bt(b2, modo, mp)
        print(f"  {label:>12s}  "
              f"{r1['aprov']:>2}/{r1['tot']:<2} ({r1['taxa']:>3.0f}%) PF {r1['pf']:>4.2f} med {r1['dmediana']:>3.0f}d   |   "
              f"{r2['aprov']:>2}/{r2['tot']:<2} ({r2['taxa']:>3.0f}%) PF {r2['pf']:>4.2f} med {r2['dmediana']:>3.0f}d")
    print("-" * 118)
