#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Otimizacao (grid search) da estrategia ORB+VWAP — a mais promissora do 1o passe.
Varia stop/alvo/horario/filtro + instrumento (NQ vs MNQ) e busca config
lucrativa que aprove conta Apex 50K. Dados: NQ 5min ~60 dias (Yahoo).
"""
import json
from datetime import datetime, timezone, timedelta

ET       = timezone(timedelta(hours=-4))
TICK     = 0.25
RT_COST  = 5.0
META     = 3000.0
DD       = 2500.0
MIN_DIAS = 7
SESS_INI = 9*60+30
ORB_FIM  = 9*60+35
FLATTEN  = 15*60+55


def carregar(path):
    d = json.load(open(path)); r = d['chart']['result'][0]
    ts = r['timestamp']; q = r['indicators']['quote'][0]
    bars = []
    for i, t in enumerate(ts):
        o, h, l, c, v = q['open'][i], q['high'][i], q['low'][i], q['close'][i], q['volume'][i]
        if None in (o, h, l, c):
            continue
        dt = datetime.fromtimestamp(t, ET)
        h = max(h, o, c); l = min(l, o, c)
        bars.append({'dt': dt, 'o': float(o), 'h': float(h), 'l': float(l),
                     'c': float(c), 'v': float(v or 0)})
    bars.sort(key=lambda b: b['dt'])
    return bars


def mins(dt):
    return dt.hour*60 + dt.minute


def run(bars, pv, stop_f, alvo_f, ent_fim, usar_vwap, intrabar):
    """intrabar: 'pess'=stop primeiro | 'real'=direcao pela cor da barra"""
    pos = 0; entry = stop = target = 0.0
    realized = 0.0; trades = []
    vwap_pv = vwap_v = vwap = 0.0
    orb_hi = orb_lo = None; orb_pronto = False; trade_dia = False
    dia = None
    # apex
    real_ini = 0.0; pico = 0.0; dias_op = set(); ativa = True
    aprov = 0; reprov = 0

    def fecha(preco):
        nonlocal pos, realized
        if pos == 0:
            return
        pnl = (preco - entry) * pos * pv - RT_COST
        realized += pnl
        trades.append(pnl)
        pos = 0

    def reset_aval():
        nonlocal real_ini, pico, dias_op, ativa
        real_ini = realized; pico = 0.0; dias_op = set(); ativa = True

    for bar in bars:
        dt = bar['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d')
        if d != dia:
            dia = d; trade_dia = False
        if m == SESS_INI:
            vwap_pv = vwap_v = 0.0; orb_hi = orb_lo = None; orb_pronto = False
        if not (SESS_INI <= m < 16*60):
            continue
        tp = (bar['h']+bar['l']+bar['c'])/3.0
        vwap_pv += tp*bar['v']; vwap_v += bar['v']
        vwap = vwap_pv/vwap_v if vwap_v > 0 else bar['c']
        if SESS_INI <= m < ORB_FIM:
            orb_hi = bar['h'] if orb_hi is None else max(orb_hi, bar['h'])
            orb_lo = bar['l'] if orb_lo is None else min(orb_lo, bar['l'])
        elif m >= ORB_FIM and not orb_pronto and orb_hi is not None:
            orb_pronto = True

        # ---- saida intrabar ----
        if pos != 0:
            h, l = bar['h'], bar['l']
            up = bar['c'] >= bar['o']
            if pos > 0:
                hs = l <= stop; ht = h >= target
                if hs and ht:
                    fecha(target if (intrabar == 'real' and up) else stop)
                elif hs:
                    fecha(stop)
                elif ht:
                    fecha(target)
            else:
                hs = h >= stop; ht = l <= target
                if hs and ht:
                    fecha(target if (intrabar == 'real' and not up) else stop)
                elif hs:
                    fecha(stop)
                elif ht:
                    fecha(target)

        # ---- apex sim ----
        if ativa:
            pnl_real = realized - real_ini
            uf = ua = 0.0
            if pos > 0:
                uf = (bar['h']-entry)*pv; ua = (bar['l']-entry)*pv
            elif pos < 0:
                uf = (entry-bar['l'])*pv; ua = (entry-bar['h'])*pv
            if pnl_real+uf > pico:
                pico = pnl_real+uf
            if pnl_real+ua <= pico - DD:
                fecha(bar['c']); reprov += 1; ativa = False; reset_aval()
            elif pnl_real >= META and len(dias_op) >= MIN_DIAS:
                fecha(bar['c']); aprov += 1; ativa = False; reset_aval()

        if m >= FLATTEN:
            fecha(bar['c']); continue
        if not ativa:
            continue

        # ---- entrada ----
        if pos == 0 and orb_pronto and not trade_dia and m < ent_fim:
            rng = orb_hi - orb_lo
            if rng > 0:
                c = bar['c']
                long_ok = c > orb_hi and (c > vwap or not usar_vwap)
                short_ok = c < orb_lo and (c < vwap or not usar_vwap)
                if long_ok:
                    entry = c; stop = orb_hi - rng*stop_f; target = orb_hi + rng*alvo_f
                    pos = 1; trade_dia = True; dias_op.add(d)
                elif short_ok:
                    entry = c; stop = orb_lo + rng*stop_f; target = orb_lo - rng*alvo_f
                    pos = -1; trade_dia = True; dias_op.add(d)

    if pos != 0:
        fecha(bars[-1]['c'])
    n = len(trades); wins = [t for t in trades if t > 0]
    gw = sum(wins); gl = abs(sum(t for t in trades if t <= 0))
    return {
        'pv': 'NQ' if pv == 20 else 'MNQ', 'stop_f': stop_f, 'alvo_f': alvo_f,
        'ent_fim': ent_fim, 'vwap': usar_vwap, 'intrabar': intrabar,
        'trades': n, 'wr': 100*len(wins)/n if n else 0,
        'pf': (gw/gl if gl > 0 else 99), 'net': sum(trades),
        'aprov': aprov, 'reprov': reprov,
    }


if __name__ == '__main__':
    bars = carregar('backtest/data/nq_5m_60d.json')
    print(f"Otimizando ORB+VWAP | {len(bars)} candles | {bars[0]['dt'].date()} a {bars[-1]['dt'].date()}\n")
    grid = []
    for pv in (20, 2):                       # NQ, MNQ
        for stop_f in (0.3, 0.5, 0.75, 1.0):
            for alvo_f in (1.0, 1.5, 2.0, 2.5, 3.0):
                for ent_fim in (10*60+15, 11*60, 11*60+30):
                    for vwap in (True, False):
                        for intra in ('pess', 'real'):
                            grid.append(run(bars, pv, stop_f, alvo_f, ent_fim, vwap, intra))
    print(f"Combinacoes testadas: {len(grid)}\n")

    def show(titulo, rows):
        print(f"{'='*86}\n  {titulo}\n{'-'*86}")
        print(f"  {'inst':4s} {'stop':4s} {'alvo':4s} {'entFim':6s} {'vwap':5s} {'intra':5s} "
              f"{'trd':>4s} {'WR':>5s} {'PF':>5s} {'PnL$':>9s} {'aprov':>6s} {'reprov':>6s}")
        for r in rows:
            print(f"  {r['pv']:4s} {r['stop_f']:<4} {r['alvo_f']:<4} "
                  f"{r['ent_fim']//60:02d}:{r['ent_fim']%60:02d}  "
                  f"{str(r['vwap']):5s} {r['intrabar']:5s} {r['trades']:>4} "
                  f"{r['wr']:>4.0f}% {r['pf']:>5.2f} {r['net']:>9,.0f} "
                  f"{r['aprov']:>6} {r['reprov']:>6}")
        print()

    show("TOP 10 por PnL liquido", sorted(grid, key=lambda x: x['net'], reverse=True)[:10])
    show("TOP 10 por contas APROVADAS (depois PnL)",
         sorted(grid, key=lambda x: (x['aprov'], x['net']), reverse=True)[:10])
    lucrativas = [r for r in grid if r['net'] > 0]
    aprovam = [r for r in grid if r['aprov'] > 0]
    print(f"Configs lucrativas: {len(lucrativas)}/{len(grid)}  |  Configs que aprovam >=1 conta: {len(aprovam)}")
