#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OPCAO D da auditoria (01/09): o short-only rendeu PF 1,44 no NT8 Strategy Analyzer,
mas so temos ~7 meses (2026). Aqui: MNQ continuo 2022-06 -> 2026-08 (Databento,
GLBX.MDP3, OHLCV-1m) e roda a reversao PDH/PDL SHORT-ONLY quebrada POR ANO.

Config = a mesma do teste NT8 short-only:
  Alvo 40 / SL 12,5 / BE gatilho 4 / BE trava 2,5 (fixo) / trailing 8 /
  BE-lock proporcional 0,75 / MaxDist 20 / 5 MNQ / MaxTradesDia 12 / stop diario $750
Comissao ~$1,30/contrato round-turn (bate os $526/81 trades do NT8). Slippage 0
(o NT8 rodou Fastest, Deslizamento 0).

ATENCAO: este motor Python foi ~55% otimista vs NT8 no PF absoluto. O que importa
AQUI e' a CONSISTENCIA ANO A ANO -- se o PF segurar parecido em 2022..2026 o edge
e' estrutural; se so aparecer em 2026 e' vies de regime (nao serve).
"""
import csv, os, statistics as st
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
D = os.path.join(os.path.dirname(__file__), '..', 'dados_databento')
CSV_LONGO = os.path.join(D, 'glbx-mdp3-20220601-20260831.ohlcv-1m.csv')
TXT_OUT   = os.path.join(D, 'MNQ_1min_2022_2026.txt')

MNQ_PV = 2.0; N_CONTR = 5; RT_PER_CONTR = 1.30
TICK = 0.25; SLIP_TICKS = 0.0
SL = 12.5; ALVO = 40.0; BE_TRIG = 4.0; BE_LOCK_FIX = 2.5; TRAIL = 8.0; BELOCK_FRAC = 0.75
MAX_DIST = 20.0; TOL_TICKS = 20
ENTRADA_INI = 9*60+30; ENTRADA_FIM = 16*60; FLATTEN = 16*60+55
STOP_DIA = 750.0 * 1  # em $ (conta toda)
MAX_TRADES = 12


# ---------------------------------------------------------------- build continuo
def build_continuo():
    if os.path.exists(TXT_OUT):
        print(f"  (usa {os.path.basename(TXT_OUT)} ja existente)"); return
    print("  montando front-month continuo do CSV Databento...")
    vol_dia = {}   # (dia, symbol) -> volume acumulado
    with open(CSV_LONGO, newline='') as fh:
        rd = csv.reader(fh); next(rd)
        for row in rd:
            ts, sym = row[0], row[9]
            if '-' in sym: continue                  # spread
            dia = ts[:10]
            vol_dia[(dia, sym)] = vol_dia.get((dia, sym), 0) + float(row[8])
    front = {}   # dia -> symbol de maior volume
    for (dia, sym), v in vol_dia.items():
        if dia not in front or v > front[dia][1]:
            front[dia] = (sym, v)
    print(f"  {len(front)} dias, ex.: {sorted(front.items())[0]} ... {sorted(front.items())[-1]}")
    linhas = []
    with open(CSV_LONGO, newline='') as fh:
        rd = csv.reader(fh); next(rd)
        for row in rd:
            ts, sym = row[0], row[9]
            if '-' in sym: continue
            dia = ts[:10]
            if front.get(dia, (None,))[0] != sym: continue
            o, h, l, c, v = row[4], row[5], row[6], row[7], row[8]
            hhmmss = ts[11:13] + ts[14:16] + '00'
            linhas.append(f"{ts[:4]}{ts[5:7]}{ts[8:10]} {hhmmss};{float(o):.2f};{float(h):.2f};{float(l):.2f};{float(c):.2f};{int(float(v))}")
    with open(TXT_OUT, 'w') as fh:
        fh.write('\n'.join(linhas) + '\n')
    print(f"  gravado {len(linhas):,} barras -> {os.path.basename(TXT_OUT)}")


def carrega():
    out = {}
    with open(TXT_OUT) as fh:
        for line in fh:
            line = line.strip()
            if not line: continue
            dtp, rest = line.split(';', 1); data, hora = dtp.split()
            o, h, l, c, v = [float(x) for x in rest.split(';')]
            dt = datetime(int(data[:4]), int(data[4:6]), int(data[6:8]),
                          int(hora[:2]), int(hora[2:4]), tzinfo=UTC)
            h = max(h, o, c); l = min(l, o, c)
            if dt not in out:
                out[dt] = {'dt': dt.astimezone(ET), 'o': o, 'h': h, 'l': l, 'c': c, 'v': v}
    return [out[k] for k in sorted(out)]


def mins(dt): return dt.hour*60 + dt.minute


def domingo_ranges(bars):
    dom = {}
    for b in bars:
        dt = b['dt']; wd = dt.weekday(); m = mins(dt)
        if wd == 6 and m >= 18*60:
            seg = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
            if seg not in dom: dom[seg] = [b['h'], b['l']]
            else:
                dom[seg][0] = max(dom[seg][0], b['h']); dom[seg][1] = min(dom[seg][1], b['l'])
    return {k: tuple(v) for k, v in dom.items()}


# ---------------------------------------------------------------- backtest
def roda(bars, dom, short_only=True):
    pv = MNQ_PV * N_CONTR; rt = RT_PER_CONTR * N_CONTR; slip = SLIP_TICKS * TICK
    dia = None; pd_hi = pd_lo = cur_hi = cur_lo = None; seg_hoje = None
    pos = 0; entry = stop = tgt = fav = 0.0; be = False
    dia_pnl = 0.0; dia_trades = 0
    trades = []   # (ano, pnl, origem_lado)

    def fecha(px, dtb):
        nonlocal pos, dia_pnl
        g = ((px - entry) * pos - 2*slip) * pv - rt
        trades.append((dtb.year, g, pos))
        dia_pnl += g; pos = 0

    for i, b in enumerate(bars):
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d'); wd = dt.weekday()
        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = cur_lo = None; dia_pnl = 0.0; dia_trades = 0
            seg_hoje = dom[d] if (dom and wd == 0 and d in dom) else None
        if ENTRADA_INI <= m < 16*60:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])

        # ---- gestao OnBarClose (1 checagem/barra) ----
        if pos != 0:
            hit = None
            if pos > 0:
                if b['l'] <= stop: hit = stop
                elif b['h'] >= tgt: hit = tgt
            else:
                if b['h'] >= stop: hit = stop
                elif b['l'] <= tgt: hit = tgt
            if hit is not None:
                fecha(hit, b['dt'])
            else:
                if pos < 0:
                    fav = min(fav, b['l'])
                    if not be and (entry - fav) >= BE_TRIG: be = True
                    if be:
                        stop = min(stop, entry - BE_LOCK_FIX,
                                   entry - (entry - fav) * BELOCK_FRAC, fav + TRAIL)
                else:
                    fav = max(fav, b['h'])
                    if not be and (fav - entry) >= BE_TRIG: be = True
                    if be:
                        stop = max(stop, entry + BE_LOCK_FIX,
                                   entry + (fav - entry) * BELOCK_FRAC, fav - TRAIL)
        if pos != 0 and m >= FLATTEN:
            fecha(b['c'], b['dt'])

        # ---- entrada ----
        if pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
            niv_hi = seg_hoje[0] if seg_hoje else pd_hi
            niv_lo = seg_hoje[1] if seg_hoje else pd_lo
            if niv_hi is None: continue
            if dia_trades >= MAX_TRADES or dia_pnl <= -STOP_DIA: continue
            tol = TOL_TICKS * TICK; h, l, c = b['h'], b['l'], b['c']
            lado = 0
            if h >= niv_hi - tol and c < niv_hi and (niv_hi - c) <= MAX_DIST:
                lado = -1
            elif (not short_only) and l <= niv_lo + tol and c > niv_lo and (c - niv_lo) <= MAX_DIST:
                lado = 1
            if lado != 0:
                entry = b['c']; pos = lado; fav = entry; be = False
                stop = entry - lado*SL; tgt = entry + lado*ALVO
                dia_trades += 1

    return trades


def metrics(trs):
    if not trs: return None
    pnls = [t[1] for t in trs]
    w = [x for x in pnls if x > 0]; ll = [x for x in pnls if x <= 0]
    gw, gl = sum(w), abs(sum(ll))
    return dict(n=len(pnls), wr=100*len(w)/len(pnls), pf=(gw/gl if gl else 99),
               net=sum(pnls), aw=(st.mean(w) if w else 0), al=(st.mean(ll) if ll else 0),
               maxdd=max_dd(pnls))


def max_dd(pnls):
    eq = 0.0; pk = 0.0; dd = 0.0
    for p in pnls:
        eq += p; pk = max(pk, eq); dd = min(dd, eq - pk)
    return dd


if __name__ == '__main__':
    build_continuo()
    bars = carrega()
    dom = domingo_ranges(bars)
    y0, y1 = bars[0]['dt'].year, bars[-1]['dt'].year
    print(f"\n{len(bars):,} barras MNQ 1min continuo | {bars[0]['dt'].date()} -> {bars[-1]['dt'].date()}")
    print("reversao PDH/PDL SHORT-ONLY | Alvo 40 / SL 12,5 / BE 4->2,5 / trail 8 / BE-lock 0,75 / MaxDist 20\n")

    for label, so in (("SHORT-ONLY", True), ("OS 2 LADOS (ref)", False)):
        trs = roda(bars, dom, short_only=so)
        print(f"=== {label} ===")
        print(f"  {'ano':>6} {'n':>5} {'WR':>5} {'PF':>6} {'net$':>10} {'avgW':>7} {'avgL':>7} {'maxDD$':>9}")
        for y in range(y0, y1+1):
            m = metrics([t for t in trs if t[0] == y])
            if not m: continue
            print(f"  {y:>6} {m['n']:>5} {m['wr']:>4.0f}% {m['pf']:>6.2f} {m['net']:>+10,.0f} "
                  f"{m['aw']:>+7.0f} {m['al']:>+7.0f} {m['maxdd']:>+9,.0f}")
        mt = metrics(trs)
        print(f"  {'TOTAL':>6} {mt['n']:>5} {mt['wr']:>4.0f}% {mt['pf']:>6.2f} {mt['net']:>+10,.0f} "
              f"{mt['aw']:>+7.0f} {mt['al']:>+7.0f} {mt['maxdd']:>+9,.0f}\n")
