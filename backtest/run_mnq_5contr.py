#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TRAVADO em 5 MNQ. Objetivo: aprovar conta 25K em ~15 dias com a MENOR taxa de perda.
Como sizing esta fixo, varremos as outras alavancas:
  - trades/dia (3..12)
  - TP do alvo (deixar o ganho correr mais p/ acumular meta mais rapido)
  - stop diario
Reporta taxa de aprovacao + dias (mediana/media) + robustez out-of-sample.
"""
import glob, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
MNQ_PV = 2.0; RT_PER = 1.20
META = 1500.0; DD = 1500.0; MIN_DIAS = 7
TICK = 0.25
N_CONTR = 5                       # TRAVADO
PTS_SL = 12.5; PTS_BE_TRIG = 3.75; PTS_BE_LOCK = 2.5; PTS_TRAIL = 1.75


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


def bt(bars, max_trades=3, pts_tp=25.0, pts_trail=PTS_TRAIL, pts_stop_dia=37.5):
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
        sess = 9*60+30 <= m < 16*60
        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = cur_lo = None
        if sess:
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
            tol = 6*TICK; h, l, c = b['h'], b['l'], b['c']; lado = 0
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
    print(f"{len(bars):,} barras | TRAVADO em {N_CONTR} MNQ (risco ${PTS_SL*MNQ_PV*N_CONTR:.0f}/trade, "
          f"buffer DD {DD/(PTS_SL*MNQ_PV*N_CONTR):.0f}x)\n")

    print("="*96)
    print("  ALAVANCA A — TRADES/DIA (5 MNQ, alvo TP padrao 25pt)")
    print("="*96)
    print(f"  {'maxTrd':>6s} {'trd/dia':>7s} {'taxa':>5s} {'aprov':>6s} {'reprov':>7s} "
          f"{'d.mediana':>9s} {'d.media':>7s} {'d.min':>5s} {'d.max':>5s} {'WR':>4s} {'PF':>5s} {'PnL$/ano':>9s}")
    print("-"*96)
    for mt in (3, 4, 5, 6, 8, 10, 12, 99):
        r = bt(bars, max_trades=mt)
        print(f"  {mt:>6} {r['trd_dia']:>6.1f} {r['taxa']:>4.0f}% {r['aprov']:>6} {r['reprov']:>7} "
              f"{r['dmediana']:>8.0f}d {r['dmed']:>6.0f}d {r['dmin']:>4.0f}d {r['dmax']:>4.0f}d "
              f"{r['wr']:>3.0f}% {r['pf']:>5.2f} {r['net']:>9,.0f}")
    print("-"*96)

    print("\n" + "="*96)
    print("  ALAVANCA B — DEIXAR O GANHO CORRER (5 MNQ, sem limite de trades, varia TP + trailing)")
    print("  (acumula meta mais rapido com ganhos maiores em vez de mais trades)")
    print("="*96)
    print(f"  {'TP pt':>5s} {'trail':>5s} {'taxa':>5s} {'aprov':>6s} {'reprov':>7s} "
          f"{'d.mediana':>9s} {'d.media':>7s} {'WR':>4s} {'PF':>5s} {'PnL$/ano':>9s}")
    print("-"*96)
    for tp in (25, 40, 60, 80):
        for tr in (1.75, 3.0, 5.0):
            r = bt(bars, max_trades=99, pts_tp=float(tp), pts_trail=tr)
            print(f"  {tp:>5} {tr:>5.1f} {r['taxa']:>4.0f}% {r['aprov']:>6} {r['reprov']:>7} "
                  f"{r['dmediana']:>8.0f}d {r['dmed']:>6.0f}d {r['wr']:>3.0f}% {r['pf']:>5.2f} {r['net']:>9,.0f}")
    print("-"*96)

    # melhor config com mediana <= 15 dias e maior taxa
    print("\n" + "="*96)
    print("  >> BUSCA: mediana <= 15 dias com MAIOR taxa (varredura combinada)")
    print("="*96)
    cands = []
    for mt in (3, 4, 5, 6, 8, 10, 12, 99):
        for tp in (25, 40, 60, 80):
            for tr in (1.75, 3.0, 5.0):
                for sd in (37.5, 50, 75):
                    r = bt(bars, max_trades=mt, pts_tp=float(tp), pts_trail=tr, pts_stop_dia=sd)
                    if r['dmediana'] <= 15 and r['aprov'] >= 8:
                        cands.append((mt, tp, tr, sd, r))
    cands.sort(key=lambda x: (-x[4]['taxa'], x[4]['dmediana']))
    print(f"  {len(cands)} configs com mediana<=15d e >=8 aprovacoes. TOP 12 por taxa:")
    print(f"  {'maxTrd':>6s} {'TP':>3s} {'trail':>5s} {'stopDia':>7s} {'taxa':>5s} "
          f"{'aprov':>5s} {'reprov':>6s} {'d.med':>5s} {'PF':>5s} {'PnL$':>8s}")
    for mt, tp, tr, sd, r in cands[:12]:
        print(f"  {mt:>6} {tp:>3} {tr:>5.1f} {sd:>7.0f} {r['taxa']:>4.0f}% "
              f"{r['aprov']:>5} {r['reprov']:>6} {r['dmediana']:>4.0f}d {r['pf']:>5.2f} {r['net']:>8,.0f}")

    if cands:
        mt, tp, tr, sd, r = cands[0]
        print(f"\n  >>> MELHOR (5 MNQ, mediana<=15d, maior taxa): "
              f"maxTrd={mt} TP={tp}pt trail={tr} stopDia=${sd:.0f}")
        print(f"      Taxa {r['taxa']:.0f}% ({r['aprov']}/{r['tot']}) | mediana {r['dmediana']:.0f}d "
              f"(media {r['dmed']:.0f}, min {r['dmin']:.0f}/max {r['dmax']:.0f}) | PF {r['pf']:.2f} | PnL ${r['net']:,.0f}")
        cfg = dict(max_trades=mt, pts_tp=float(tp), pts_trail=tr, pts_stop_dia=sd)
        r1 = bt(b1, **cfg); r2 = bt(b2, **cfg)
        print(f"      ROBUSTEZ -> 1a metade: {r1['aprov']}/{r1['tot']} ({r1['taxa']:.0f}%) PF {r1['pf']:.2f} | "
              f"2a metade: {r2['aprov']}/{r2['tot']} ({r2['taxa']:.0f}%) PF {r2['pf']:.2f}")
    print("="*96)
