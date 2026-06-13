#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PERSEGUIR 70% de aprovacao — Niveis 25K (R:R 2:1, BE$75/trail$50 base).
Adiciona gestao de JORNADA/AVALIACAO p/ reduzir reprovacoes por estouro de DD:
  - stop diario   (para o dia ao perder $X)
  - meta diaria   (para o dia ao ganhar $X — nao devolve)
  - buffer de DD  (nao opera se chegar perto do limite de drawdown)
Respeita regras Apex 25K: meta $1500, DD trailing $1500, minimo 7 dias.
"""
import glob, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
PV = 20.0; TICK = 0.25; RT_COST = 5.0
META = 1500.0; DD = 1500.0; MIN_DIAS = 7
TP_USD = 500.0; SL_USD = 250.0
BE_TRIG = 75.0; TRAIL = 50.0; BE_LOCK = 50.0   # melhor config do passo anterior


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
                    vistos[dt] = (dt.astimezone(ET), o, h, l, c, v)
    return [{'dt': vistos[k][0], 'o': vistos[k][1], 'h': vistos[k][2],
             'l': vistos[k][3], 'c': vistos[k][4], 'v': vistos[k][5]} for k in sorted(vistos)]


def mins(dt): return dt.hour*60 + dt.minute


def bt(bars, stop_dia=750.0, meta_dia=0.0, buffer_dd=0.0, max_perdas=0):
    pts_tp = TP_USD/PV; pts_sl = SL_USD/PV; pts_trail = TRAIL/PV; pts_lock = BE_LOCK/PV
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False
    realized = 0.0; trades = []
    vpv = vv = vwap = 0.0
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    r_ini = 0.0; pico = 0.0; dias = set(); ativa = True
    aprov = reprov = 0
    pnl_d0 = 0.0; block = False; dia_k = None; perdas_dia = 0

    def fecha(p):
        nonlocal pos, realized, perdas_dia
        if pos == 0: return
        pnl = (p-entry)*pos*PV - RT_COST
        realized += pnl; trades.append(pnl)
        if pnl < 0: perdas_dia += 1
        pos = 0

    for b in bars:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d')
        sess = 9*60+30 <= m < 16*60
        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = cur_lo = None
        if sess:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
        if m == 9*60+30: vpv = vv = 0.0
        if sess:
            tp = (b['h']+b['l']+b['c'])/3.0; vpv += tp*b['v']; vv += b['v']
            vwap = vpv/vv if vv > 0 else b['c']
        if d != dia_k: dia_k = d; pnl_d0 = realized; block = False; perdas_dia = 0

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
                    if not be_done and (fav-entry)*PV >= BE_TRIG:
                        stop = max(stop, entry+pts_lock); be_done = True
                    if be_done: stop = max(stop, fav-pts_trail)
                else:
                    fav = min(fav, b['l'])
                    if not be_done and (entry-fav)*PV >= BE_TRIG:
                        stop = min(stop, entry-pts_lock); be_done = True
                    if be_done: stop = min(stop, fav+pts_trail)

        # apex sim
        if ativa:
            pr = realized - r_ini
            ua = uf = 0.0
            if pos > 0: ua = (b['l']-entry)*PV; uf = (b['h']-entry)*PV
            elif pos < 0: ua = (entry-b['h'])*PV; uf = (entry-b['l'])*PV
            if pr+uf > pico: pico = pr+uf
            pnl_dia = realized - pnl_d0 + ua
            # gestao de jornada
            if pnl_dia <= -stop_dia:
                block = True
                if pos != 0: fecha(b['c'])
            if meta_dia > 0 and (realized - pnl_d0 + (uf if pos!=0 else 0)) >= meta_dia:
                block = True
                if pos != 0: fecha(b['c'])
            if max_perdas > 0 and perdas_dia >= max_perdas:
                block = True
            # reprovacao / aprovacao
            if pr+ua <= pico - DD:
                fecha(b['c']); reprov += 1; r_ini = realized; pico = 0.0; dias = set()
            elif pr >= META and len(dias) >= MIN_DIAS:
                fecha(b['c']); aprov += 1; r_ini = realized; pico = 0.0; dias = set()

        if m >= 15*60+55:
            if pos != 0: fecha(b['c'])
            continue
        if not ativa or block: continue

        # entrada Niveis + buffer de DD
        if pos == 0 and 9*60+30 <= m < 15*60 and pd_hi is not None:
            pr = realized - r_ini
            nivel_dd = pico - DD
            if buffer_dd > 0 and pr <= nivel_dd + buffer_dd:
                continue   # perto do limite -> nao arrisca
            tol = 6*TICK; h, l, c = b['h'], b['l'], b['c']
            lado = 0
            if h >= pd_hi-tol and c < pd_hi: lado = -1
            elif l <= pd_lo+tol and c > pd_lo: lado = 1
            if lado != 0:
                entry = c; pos = lado; fav = c; be_done = False
                stop = c - lado*pts_sl; target = c + lado*pts_tp
                dias.add(d)

    if pos != 0: fecha(bars[-1]['c'])
    n = len(trades); wins = [t for t in trades if t > 0]
    gw = sum(wins); gl = abs(sum(t for t in trades if t <= 0))
    tot = aprov + reprov
    return {'n': n, 'wr': 100*len(wins)/n if n else 0, 'pf': (gw/gl if gl > 0 else 99),
            'net': sum(trades), 'aprov': aprov, 'reprov': reprov, 'tot': tot,
            'taxa': 100*aprov/tot if tot else 0,
            'sd': stop_dia, 'md': meta_dia, 'bf': buffer_dd, 'mp': max_perdas}


if __name__ == '__main__':
    print("Carregando NQ 1-min real..."); bars = carregar('NQ_dados')
    meio = bars[len(bars)//2]['dt']
    b1 = [b for b in bars if b['dt'] < meio]; b2 = [b for b in bars if b['dt'] >= meio]
    print(f"Barras: {len(bars):,} | Niveis 25K | TP500/SL250 BE75/trail50\n")

    ref = bt(bars, stop_dia=750, meta_dia=0, buffer_dd=0)
    print(f"REFERENCIA (so trailing): aprov {ref['aprov']}/{ref['tot']} ({ref['taxa']:.0f}%), PnL ${ref['net']:,.0f}\n")

    print("="*96)
    print("  VARREDURA — gestao de jornada (stop diario / meta diaria / buffer DD / max perdas)")
    print("-"*96)
    grid = []
    for sd in (375, 500, 750):
        for md in (0, 400, 600):
            for bf in (0, 300, 500):
                for mp in (0, 2, 3):
                    grid.append(bt(bars, stop_dia=sd, meta_dia=md, buffer_dd=bf, max_perdas=mp))
    print(f"  {'stopDia':>7s} {'metaDia':>7s} {'bufDD':>5s} {'maxP':>4s} "
          f"{'trd':>5s} {'WR':>5s} {'PF':>5s} {'PnL$':>9s} {'aprov':>6s} {'reprov':>7s} {'taxa':>6s}")
    top = sorted(grid, key=lambda x: (x['taxa'], x['net']), reverse=True)[:14]
    for r in top:
        print(f"  {r['sd']:>7.0f} {r['md']:>7.0f} {r['bf']:>5.0f} {r['mp']:>4} "
              f"{r['n']:>5} {r['wr']:>4.0f}% {r['pf']:>5.2f} {r['net']:>9,.0f} "
              f"{r['aprov']:>6} {r['reprov']:>7} {r['taxa']:>5.0f}%")
    best = top[0]
    print(f"\n  >> MELHOR: stopDia ${best['sd']:.0f} | metaDia ${best['md']:.0f} | "
          f"bufDD ${best['bf']:.0f} | maxPerdas {best['mp']} -> {best['taxa']:.0f}% "
          f"({best['aprov']}/{best['tot']}), PnL ${best['net']:,.0f}")

    print("\n" + "="*96)
    print("  ROBUSTEZ da melhor config (1a vs 2a metade)")
    print("-"*96)
    cfg = dict(stop_dia=best['sd'], meta_dia=best['md'], buffer_dd=best['bf'], max_perdas=best['mp'])
    for nome, sub in (('1a metade', b1), ('2a metade', b2), ('ano', bars)):
        r = bt(sub, **cfg)
        print(f"  {nome:12s} aprov {r['aprov']:>2}/{r['tot']:<2} ({r['taxa']:>3.0f}%) | "
              f"WR {r['wr']:.0f}% | PF {r['pf']:.2f} | PnL ${r['net']:,.0f}")
    print("="*96)
