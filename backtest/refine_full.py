#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
REFINAMENTO COMPLETO (conta 25K, R:R 2:1):
  PASSO 1 - varredura fina da Niveis (breakeven/trailing/VWAP)
  PASSO 2 - aplica breakeven+trailing na ORB e na Matheus
  PASSO 3 - validacao de robustez (1a metade vs 2a metade do periodo)
Dados: NQ 1-min reais (~10,5 meses).
"""
import glob, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
PV = 20.0; TICK = 0.25; RT_COST = 5.0
META = 1500.0; DD = 1500.0; MIN_DIAS = 7
TP_USD = 500.0; SL_USD = 250.0


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


def bt(bars, modo, be_trig=0, trail=0, time_bars=0, fvwap=False, be_lock=50.0):
    pts_tp = TP_USD/PV; pts_sl = SL_USD/PV
    pts_trail = trail/PV; pts_lock = be_lock/PV
    pos = 0; entry = stop = target = 0.0; fav = 0.0; nbar = 0; be_done = False
    realized = 0.0; trades = []
    vpv = vv = vwap = 0.0
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    man_hi = man_lo = None; man_ok = False
    orb_hi = orb_lo = None; orb_ok = False; trade_dia = False
    r_ini = 0.0; pico = 0.0; dias = set(); ativa = True
    aprov = reprov = 0; pnl_d0 = 0.0; block = False; dia_k = None

    def fecha(p):
        nonlocal pos, realized
        if pos == 0: return
        realized += (p-entry)*pos*PV - RT_COST
        trades.append((p-entry)*pos*PV - RT_COST); pos = 0

    for b in bars:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d')
        sess = 9*60+30 <= m < 16*60
        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = cur_lo = None; trade_dia = False
            man_hi = man_lo = None; man_ok = False
        if m < 12*60:
            man_hi = b['h'] if man_hi is None else max(man_hi, b['h'])
            man_lo = b['l'] if man_lo is None else min(man_lo, b['l'])
        elif not man_ok and man_hi is not None: man_ok = True
        if sess:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
        if m == 9*60+30:
            vpv = vv = 0.0; orb_hi = orb_lo = None; orb_ok = False
        if sess:
            tp = (b['h']+b['l']+b['c'])/3.0; vpv += tp*b['v']; vv += b['v']
            vwap = vpv/vv if vv > 0 else b['c']
            if 9*60+30 <= m < 9*60+35:
                orb_hi = b['h'] if orb_hi is None else max(orb_hi, b['h'])
                orb_lo = b['l'] if orb_lo is None else min(orb_lo, b['l'])
            elif m >= 9*60+35 and not orb_ok and orb_hi is not None: orb_ok = True
        if d != dia_k: dia_k = d; pnl_d0 = realized; block = False

        # ----- saida + protecao de lucro -----
        if pos != 0:
            saiu = False
            if pos > 0:
                if b['l'] <= stop: fecha(stop); saiu = True
                elif b['h'] >= target: fecha(target); saiu = True
            else:
                if b['h'] >= stop: fecha(stop); saiu = True
                elif b['l'] <= target: fecha(target); saiu = True
            if not saiu and pos != 0:
                nbar += 1
                if pos > 0:
                    fav = max(fav, b['h']); lf = (fav-entry)*PV
                    if be_trig > 0 and not be_done and lf >= be_trig:
                        stop = max(stop, entry + pts_lock); be_done = True
                    if trail > 0 and be_done: stop = max(stop, fav - pts_trail)
                else:
                    fav = min(fav, b['l']); lf = (entry-fav)*PV
                    if be_trig > 0 and not be_done and lf >= be_trig:
                        stop = min(stop, entry - pts_lock); be_done = True
                    if trail > 0 and be_done: stop = min(stop, fav + pts_trail)
                if time_bars > 0 and nbar >= time_bars and (b['c']-entry)*pos*PV > 0:
                    fecha(b['c'])

        # ----- apex sim -----
        if ativa:
            pr = realized - r_ini
            ua = uf = 0.0
            if pos > 0: ua = (b['l']-entry)*PV; uf = (b['h']-entry)*PV
            elif pos < 0: ua = (entry-b['h'])*PV; uf = (entry-b['l'])*PV
            if pr+uf > pico: pico = pr+uf
            if (realized-pnl_d0+ua) <= -(DD*0.5):
                block = True
                if pos != 0: fecha(b['c'])
            if pr+ua <= pico - DD:
                fecha(b['c']); reprov += 1; r_ini = realized; pico = 0.0; dias = set()
            elif pr >= META and len(dias) >= MIN_DIAS:
                fecha(b['c']); aprov += 1; r_ini = realized; pico = 0.0; dias = set()

        if m >= 15*60+55:
            if pos != 0: fecha(b['c'])
            continue
        if not ativa or block: continue

        # ----- entradas -----
        if pos == 0:
            lado = 0; c = b['c']
            if modo == 'NIVEIS' and 9*60+30 <= m < 15*60 and pd_hi is not None:
                tol = 6*TICK
                if b['h'] >= pd_hi-tol and c < pd_hi and (c < vwap or not fvwap): lado = -1
                elif b['l'] <= pd_lo+tol and c > pd_lo and (c > vwap or not fvwap): lado = 1
            elif modo == 'ORB' and orb_ok and not trade_dia and 9*60+35 <= m < 10*60+15:
                if orb_hi-orb_lo > 0:
                    if c > orb_hi and c > vwap: lado = 1
                    elif c < orb_lo and c < vwap: lado = -1
            elif modo == 'MATHEUS' and man_ok and not trade_dia and 12*60 <= m < 15*60:
                if man_hi-man_lo > 0:
                    if c > man_hi: lado = 1
                    elif c < man_lo: lado = -1
            if lado != 0:
                entry = c; pos = lado; fav = c; nbar = 0; be_done = False
                stop = c - lado*pts_sl; target = c + lado*pts_tp
                dias.add(d); trade_dia = True

    if pos != 0: fecha(bars[-1]['c'])
    n = len(trades); wins = [t for t in trades if t > 0]
    gw = sum(wins); gl = abs(sum(t for t in trades if t <= 0))
    tot = aprov + reprov
    return {'n': n, 'wr': 100*len(wins)/n if n else 0, 'pf': (gw/gl if gl > 0 else 99),
            'net': sum(trades), 'aprov': aprov, 'reprov': reprov, 'tot': tot,
            'taxa': 100*aprov/tot if tot else 0, 'be': be_trig, 'tr': trail, 'fv': fvwap}


if __name__ == '__main__':
    print("Carregando NQ 1-min real..."); bars = carregar('NQ_dados')
    meio = bars[len(bars)//2]['dt']
    b1 = [b for b in bars if b['dt'] < meio]
    b2 = [b for b in bars if b['dt'] >= meio]
    print(f"Barras: {len(bars):,} | conta 25K | TP $500/SL $250 (R:R 2:1)")
    print(f"Split robustez: 1a metade {b1[0]['dt'].date()}->{b1[-1]['dt'].date()} | "
          f"2a metade {b2[0]['dt'].date()}->{b2[-1]['dt'].date()}")

    # ====== PASSO 1: varredura fina da Niveis ======
    print("\n" + "="*94)
    print("  PASSO 1 — VARREDURA FINA DA NIVEIS (breakeven x trailing x VWAP)")
    print("-"*94)
    grid = []
    for fv in (False, True):
        for be in (75, 100, 125, 150):
            for tr in (50, 75, 100, 125, 150):
                grid.append(bt(bars, 'NIVEIS', be_trig=be, trail=tr, fvwap=fv))
    print(f"  {'vwap':5s} {'BE$':>4s} {'trail$':>6s} {'trd':>5s} {'WR':>5s} {'PF':>5s} "
          f"{'PnL$':>10s} {'aprov':>6s} {'reprov':>7s} {'taxa':>6s}")
    for r in sorted(grid, key=lambda x: (x['aprov'], x['net']), reverse=True)[:12]:
        print(f"  {str(r['fv']):5s} {r['be']:>4} {r['tr']:>6} {r['n']:>5} {r['wr']:>4.0f}% "
              f"{r['pf']:>5.2f} {r['net']:>10,.0f} {r['aprov']:>6} {r['reprov']:>7} {r['taxa']:>5.0f}%")
    best = sorted(grid, key=lambda x: (x['aprov'], x['net']), reverse=True)[0]
    print(f"\n  >> MELHOR NIVEIS: VWAP={best['fv']} BE=${best['be']} trail=${best['tr']} "
          f"-> {best['aprov']} aprov / {best['reprov']} reprov ({best['taxa']:.0f}%), PnL ${best['net']:,.0f}")

    # ====== PASSO 2: ORB e Matheus com breakeven+trailing ======
    print("\n" + "="*94)
    print("  PASSO 2 — ORB e MATHEUS com breakeven+trailing (mesmo framework)")
    print("-"*94)
    print(f"  {'estrat':8s} {'BE$':>4s} {'trail$':>6s} {'trd':>5s} {'WR':>5s} {'PF':>5s} "
          f"{'PnL$':>10s} {'aprov':>6s} {'reprov':>7s} {'taxa':>6s}")
    for mo in ('ORB', 'MATHEUS'):
        # baseline (sem protecao) + variacoes de trailing
        for be, tr in ((0, 0), (100, 100), (150, 150), (200, 200), (250, 250)):
            r = bt(bars, mo, be_trig=be, trail=tr)
            tag = 'puro' if be == 0 else f'BE{be}/tr{tr}'
            print(f"  {mo:8s} {r['be']:>4} {r['tr']:>6} {r['n']:>5} {r['wr']:>4.0f}% "
                  f"{r['pf']:>5.2f} {r['net']:>10,.0f} {r['aprov']:>6} {r['reprov']:>7} {r['taxa']:>5.0f}%")
        print()

    # ====== PASSO 3: robustez (out-of-sample temporal) ======
    print("="*94)
    print("  PASSO 3 — ROBUSTEZ: melhor Niveis testada em cada metade do periodo")
    print("-"*94)
    cfg = dict(be_trig=best['be'], trail=best['tr'], fvwap=best['fv'])
    print(f"  Config: VWAP={best['fv']} BE=${best['be']} trail=${best['tr']}\n")
    print(f"  {'periodo':16s} {'trd':>5s} {'WR':>5s} {'PF':>5s} {'PnL$':>10s} "
          f"{'aprov':>6s} {'reprov':>7s} {'taxa':>6s}")
    for nome, sub in (('1a metade', b1), ('2a metade', b2), ('ano inteiro', bars)):
        r = bt(sub, 'NIVEIS', **cfg)
        print(f"  {nome:16s} {r['n']:>5} {r['wr']:>4.0f}% {r['pf']:>5.2f} {r['net']:>10,.0f} "
              f"{r['aprov']:>6} {r['reprov']:>7} {r['taxa']:>5.0f}%")
    print("\n  Robusto = lucrativo e aprovando nas DUAS metades (nao so no agregado).")
    print("="*94)
