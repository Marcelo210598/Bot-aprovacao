#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Estatisticas detalhadas da CONFIG VENCEDORA (Niveis 25K, 94%) p/ resumo Andersson."""
import glob, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
PV = 20.0; TICK = 0.25; RT_COST = 5.0
META = 1500.0; DD = 1500.0; MIN_DIAS = 7
TP_USD = 500.0; SL_USD = 250.0; BE_TRIG = 75.0; BE_LOCK = 50.0
TRAIL = 35.0; MAX_TRADES = 3; STOP_DIA = 750.0


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


def run(bars):
    pts_tp = TP_USD/PV; pts_sl = SL_USD/PV; pts_trail = TRAIL/PV; pts_lock = BE_LOCK/PV
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False
    realized = 0.0; trades = []
    vpv = vv = vwap = 0.0; pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None
    aprov = reprov = 0; d2a = []; pnl_d0 = 0.0; block = False; dia_k = None; trades_dia = 0

    def fecha(p):
        nonlocal pos, realized
        if pos == 0: return
        realized += (p-entry)*pos*PV - RT_COST; trades.append((p-entry)*pos*PV - RT_COST); pos = 0

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
                    if not be_done and (fav-entry)*PV >= BE_TRIG: stop = max(stop, entry+pts_lock); be_done = True
                    if be_done: stop = max(stop, fav-pts_trail)
                else:
                    fav = min(fav, b['l'])
                    if not be_done and (entry-fav)*PV >= BE_TRIG: stop = min(stop, entry-pts_lock); be_done = True
                    if be_done: stop = min(stop, fav+pts_trail)
        pr = realized - r_ini
        ua = uf = 0.0
        if pos > 0: ua = (b['l']-entry)*PV; uf = (b['h']-entry)*PV
        elif pos < 0: ua = (entry-b['h'])*PV; uf = (entry-b['l'])*PV
        if pr+uf > pico: pico = pr+uf
        if STOP_DIA > 0 and (realized - pnl_d0 + ua) <= -STOP_DIA:
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
        if not block and pos == 0 and trades_dia < MAX_TRADES and 9*60+30 <= m < 15*60 and pd_hi is not None:
            tol = 6*TICK; h, l, c = b['h'], b['l'], b['c']; lado = 0
            if h >= pd_hi-tol and c < pd_hi: lado = -1
            elif l <= pd_lo+tol and c > pd_lo: lado = 1
            if lado != 0:
                entry = c; pos = lado; fav = c; be_done = False
                stop = c - lado*pts_sl; target = c + lado*pts_tp; dias.add(d); trades_dia += 1
    if pos != 0: fecha(bars[-1]['c'])

    wins = [t for t in trades if t > 0]; losses = [t for t in trades if t <= 0]
    streak = mx = 0
    for t in trades:
        if t <= 0: streak += 1; mx = max(mx, streak)
        else: streak = 0
    n = len(trades)
    print(f"  Trades totais ............. {n}")
    print(f"  Trades/dia (media) ........ {n/220:.1f}")
    print(f"  Win rate .................. {100*len(wins)/n:.0f}%  ({len(wins)} ganhos / {len(losses)} perdas)")
    print(f"  Ganho medio por trade ..... ${sum(wins)/len(wins):,.0f}")
    print(f"  Perda media por trade ..... ${sum(losses)/len(losses):,.0f}")
    print(f"  Maior ganho ............... ${max(wins):,.0f}")
    print(f"  Maior perda ............... ${min(losses):,.0f}")
    print(f"  Expectancy por trade ...... ${sum(trades)/n:,.1f}")
    print(f"  Maior sequencia de perdas . {mx} trades seguidos")
    print(f"  Profit Factor ............. {sum(wins)/abs(sum(losses)):.2f}")
    print(f"  PnL liquido (ano) ......... ${sum(trades):,.0f}")
    print(f"  --- AVALIACOES APEX 25K ---")
    print(f"  Aprovadas ................. {aprov}")
    print(f"  Reprovadas ................ {reprov}")
    print(f"  Taxa de aprovacao ......... {100*aprov/(aprov+reprov):.0f}%")
    print(f"  Dias medios p/ aprovar .... {sum(d2a)/len(d2a):.0f} dias")


if __name__ == '__main__':
    print("CONFIG VENCEDORA — Niveis 25K (94%)\n")
    run(carregar('NQ_dados'))
