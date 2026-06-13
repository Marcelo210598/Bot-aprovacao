#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
REFINAMENTO da estrategia Niveis (conta 25K, R:R 2:1 mantido).
Adiciona gestao de saida que protege lucro + filtro de entrada, e varre combinacoes:
  - filtro VWAP (so opera alinhado)
  - breakeven (anda a favor -> stop vai p/ entrada)
  - trailing stop (segue o preco; perdeu forca -> garante lucro acumulado)
  - time stop (travou em X min sem bater alvo -> fecha garantindo o que tem)
Dados: NQ 1-min reais, ~10,5 meses.
"""
import glob, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
PV = 20.0; TICK = 0.25; RT_COST = 5.0
META = 1500.0; DD = 1500.0; MIN_DIAS = 7
TP_USD = 500.0; SL_USD = 250.0     # R:R 2:1 fixo


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


def run(bars, filtro_vwap, be_trig, trail, time_bars, be_lock=50.0):
    pts_tp = TP_USD/PV; pts_sl = SL_USD/PV
    pts_be_trig = be_trig/PV; pts_trail = trail/PV; pts_be_lock = be_lock/PV
    pos = 0; entry = stop = target = 0.0; fav = 0.0; nbar = 0; be_done = False
    realized = 0.0; trades = []
    vpv = vv = vwap = 0.0
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
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
            dia = d; cur_hi = cur_lo = None
        if sess:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
        if m == 9*60+30: vpv = vv = 0.0
        if sess:
            tp = (b['h']+b['l']+b['c'])/3.0; vpv += tp*b['v']; vv += b['v']
            vwap = vpv/vv if vv > 0 else b['c']
        if d != dia_k: dia_k = d; pnl_d0 = realized; block = False

        # ----- saida da posicao -----
        if pos != 0:
            # 1) checa stop/target atuais (conservador: stop antes do alvo)
            saiu = False
            if pos > 0:
                if b['l'] <= stop: fecha(stop); saiu = True
                elif b['h'] >= target: fecha(target); saiu = True
            else:
                if b['h'] >= stop: fecha(stop); saiu = True
                elif b['l'] <= target: fecha(target); saiu = True
            # 2) se continua, ajusta protecao p/ proximas barras
            if not saiu and pos != 0:
                nbar += 1
                if pos > 0:
                    fav = max(fav, b['h'])
                    lucro_fav = (fav-entry)*PV
                    if be_trig > 0 and not be_done and lucro_fav >= be_trig:
                        stop = max(stop, entry + pts_be_lock); be_done = True
                    if trail > 0 and be_done:
                        stop = max(stop, fav - pts_trail)
                else:
                    fav = min(fav, b['l'])
                    lucro_fav = (entry-fav)*PV
                    if be_trig > 0 and not be_done and lucro_fav >= be_trig:
                        stop = min(stop, entry - pts_be_lock); be_done = True
                    if trail > 0 and be_done:
                        stop = min(stop, fav + pts_trail)
                # time stop: travou X min e esta no lucro -> garante
                if time_bars > 0 and nbar >= time_bars:
                    cur_pnl = (b['c']-entry)*pos*PV
                    if cur_pnl > 0: fecha(b['c'])

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
                fecha(b['c']); reprov += 1; ativa = False
                r_ini = realized; pico = 0.0; dias = set(); ativa = True; ini = dt
            elif pr >= META and len(dias) >= MIN_DIAS:
                fecha(b['c']); aprov += 1
                r_ini = realized; pico = 0.0; dias = set(); ativa = True

        if m >= 15*60+55:
            if pos != 0: fecha(b['c'])
            continue
        if not ativa or block: continue

        # ----- entrada Niveis (rejeicao high/low dia anterior + filtro vwap) -----
        if pos == 0 and 9*60+30 <= m < 15*60 and pd_hi is not None:
            tol = 6*TICK; h, l, c = b['h'], b['l'], b['c']
            short_ok = h >= pd_hi - tol and c < pd_hi and (c < vwap or not filtro_vwap)
            long_ok  = l <= pd_lo + tol and c > pd_lo and (c > vwap or not filtro_vwap)
            if short_ok:
                pos = -1; entry = c; stop = c + pts_sl; target = c - pts_tp
                fav = c; nbar = 0; be_done = False; dias.add(d)
            elif long_ok:
                pos = 1; entry = c; stop = c - pts_sl; target = c + pts_tp
                fav = c; nbar = 0; be_done = False; dias.add(d)

    if pos != 0: fecha(bars[-1]['c'])
    n = len(trades); wins = [t for t in trades if t > 0]
    gw = sum(wins); gl = abs(sum(t for t in trades if t <= 0))
    tot = aprov + reprov
    return {'n': n, 'wr': 100*len(wins)/n if n else 0, 'pf': (gw/gl if gl > 0 else 99),
            'net': sum(trades), 'aprov': aprov, 'reprov': reprov, 'tot': tot,
            'taxa': 100*aprov/tot if tot else 0,
            'fv': filtro_vwap, 'be': be_trig, 'tr': trail, 'ts': time_bars}


if __name__ == '__main__':
    print("Carregando NQ 1-min real..."); bars = carregar('NQ_dados')
    print(f"Barras: {len(bars):,} | conta 25K | TP $500 / SL $250 (R:R 2:1)\n")

    base = run(bars, False, 0, 0, 0)
    print("BASELINE (Niveis pura, sem refinamento):")
    print(f"  trades {base['n']} | WR {base['wr']:.0f}% | PF {base['pf']:.2f} | "
          f"PnL ${base['net']:,.0f} | aprov {base['aprov']} | reprov {base['reprov']} | taxa {base['taxa']:.0f}%\n")

    grid = []
    for fv in (False, True):
        for be in (0, 100, 150, 200):
            for tr in (0, 100, 150):
                for ts in (0, 45, 90):
                    grid.append(run(bars, fv, be, tr, ts))
    print(f"Combinacoes testadas: {len(grid)}\n")

    def tab(titulo, rows):
        print("="*92); print(f"  {titulo}"); print("-"*92)
        print(f"  {'vwap':5s} {'BE$':>4s} {'trail$':>6s} {'timeStop':>8s} "
              f"{'trd':>5s} {'WR':>5s} {'PF':>5s} {'PnL$':>10s} {'aprov':>6s} {'reprov':>7s} {'taxa':>6s}")
        for r in rows:
            print(f"  {str(r['fv']):5s} {r['be']:>4} {r['tr']:>6} "
                  f"{(str(r['ts'])+'min') if r['ts'] else 'off':>8s} "
                  f"{r['n']:>5} {r['wr']:>4.0f}% {r['pf']:>5.2f} {r['net']:>10,.0f} "
                  f"{r['aprov']:>6} {r['reprov']:>7} {r['taxa']:>5.0f}%")
        print()

    tab("TOP 10 por contas APROVADAS (depois PnL)",
        sorted(grid, key=lambda x: (x['aprov'], x['net']), reverse=True)[:10])
    tab("TOP 10 por PnL liquido",
        sorted(grid, key=lambda x: x['net'], reverse=True)[:10])
    luc = [r for r in grid if r['net'] > 0]
    print(f"Configs lucrativas: {len(luc)}/{len(grid)} | "
          f"que aprovam >=8 contas: {len([r for r in grid if r['aprov']>=8])}")
