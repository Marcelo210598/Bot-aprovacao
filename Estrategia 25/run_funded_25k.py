#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BOT FUNDED 25K (Apex Intraday ja aprovada) — foco em SAQUE CONSISTENTE + WR altissimo.
Simula a jornada da conta funded e mede ACERTOS x PERDAS (% e $) no backtest inteiro.

REFINAMENTO (15/06) — 4 baterias de experimentos partindo do baseline 2 MNQ / $250:
  1. Filtros de setup (subir WR): max trades/dia, distancia max da linha
  2. Relacao ganho/perda: varre TP e trailing
  3. Regra Apex de dias minimos pro saque: 5 vs 8 vs 10
  4. Conta EOD vs Intraday lado a lado

Motor de entrada = validado: reversao na max/min do dia anterior + range do domingo
a noite (Globex) na SEGUNDA. tol 20t. Gestao por trade: SL 12.5, BE, trail.
"""
import glob, os
from collections import deque
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
MNQ_PV = 2.0; RT_PER = 1.20
TICK = 0.25
PTS_SL = 12.5
TOL_TICKS = 20
ENTRADA_INI = 9*60+30; ENTRADA_FIM = 16*60; FLATTEN = 16*60+55
DOM_NOITE_INI = 18*60
SALDO_INI = 25000.0
GORDURA = 1600.0; TRAVA = SALDO_INI + GORDURA   # precisa bater 26600 p/ sacar
LUCRO_MIN_DIA = 100.0
CONSIST = 0.30
SAQUE_VAL = 1000.0; SAQUES_MAX = 6


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
    overnight = {}
    for b in bars:
        dt = b['dt']; wd = dt.weekday(); m = mins(dt); seg = None
        if wd == 6 and m >= DOM_NOITE_INI: seg = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
        elif wd == 0 and m < ENTRADA_INI:  seg = dt.strftime('%Y-%m-%d')
        if seg:
            if seg not in overnight: overnight[seg] = [b['h'], b['l']]
            else:
                overnight[seg][0] = max(overnight[seg][0], b['h'])
                overnight[seg][1] = min(overnight[seg][1], b['l'])
    return {k: tuple(v) for k, v in overnight.items()}


def simula(bars, dom_map, n_contr=2, alvo_dia=250.0, stop_dia=300.0,
           max_trades_dia=0, max_dist=15.0, tp=60.0, trail=1.75,
           be_trig=3.75, be_lock=2.5, dias_min=5, modo='intraday', sl=PTS_SL,
           contr_fase2=None, contr_fase3=None, limiar3=28000.0,
           ent_ini=ENTRADA_INI, ent_fim=ENTRADA_FIM, sma_len=0):
    """modo: 'intraday' (DD 1500, checa intrabar) | 'eod' (DD 1000, checa no fechamento).
    Escalonamento de contratos por pico de equity da conta (high-water mark):
      eq_peak < TRAVA($26.600)  -> n_contr      (fase 1: DD ainda persegue)
      eq_peak >= TRAVA          -> contr_fase2   (fase 2: gordura travada)
      eq_peak >= limiar3        -> contr_fase3   (fase 3: buffer extra)
    ent_ini/ent_fim: janela de ENTRADA (HHmm em minutos). sma_len: filtro de tendencia (0=off)."""
    DD = 1500.0 if modo == 'intraday' else 1000.0
    pos_pv = MNQ_PV * n_contr; pos_rt = RT_PER * n_contr   # valores da posicao aberta

    def contratos(eqp):
        if contr_fase3 and eqp >= limiar3: return contr_fase3
        if contr_fase2 and eqp >= TRAVA:   return contr_fase2
        return n_contr

    def nova_conta():
        return dict(balance=SALDO_INI, eq_peak=SALDO_INI, qual_dias=0,
                    max_dia=0.0, sacado=0.0, dia_ini=None)
    acc = nova_conta()
    saques_tot = 0; contas_violadas = 0; contas_completas = 0; dias_por_saque = []

    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None; seg_hoje = None
    day_start_bal = SALDO_INI; dia_pnl_real = 0.0; bloq_dia = False
    dia_teve_trade = False; trades_dia = 0
    trades = []; dias_res = []
    closes = deque(maxlen=sma_len) if sma_len else None; sma_atual = None

    def fecha(p):
        nonlocal pos, dia_pnl_real
        if pos == 0: return
        g = (p - entry) * pos * pos_pv - pos_rt
        acc['balance'] += g; dia_pnl_real += g
        trades.append(g); pos = 0

    def tenta_saque(dt):
        nonlocal saques_tot, acc, day_start_bal, dia_pnl_real, bloq_dia
        nonlocal contas_completas, pos
        lucro_total = (acc['balance'] - SALDO_INI) + acc['sacado']
        while True:
            cons_ok = (acc['max_dia'] <= CONSIST * lucro_total) if lucro_total > 0 else False
            if not (acc['balance'] >= TRAVA and acc['qual_dias'] >= dias_min
                    and cons_ok and acc['sacado'] < SAQUES_MAX * SAQUE_VAL):
                break
            acc['balance'] -= SAQUE_VAL; acc['sacado'] += SAQUE_VAL; saques_tot += 1
            if acc['dia_ini'] is not None: dias_por_saque.append((dt - acc['dia_ini']).days)
            if acc['sacado'] >= SAQUES_MAX * SAQUE_VAL:
                contas_completas += 1; pos = 0
                acc = nova_conta(); acc['dia_ini'] = dt
                day_start_bal = SALDO_INI; dia_pnl_real = 0.0; bloq_dia = False
                return
            lucro_total = (acc['balance'] - SALDO_INI) + acc['sacado']

    def queima(dt):
        nonlocal acc, day_start_bal, dia_pnl_real, bloq_dia, contas_violadas, pos
        contas_violadas += 1; pos = 0
        acc = nova_conta(); acc['dia_ini'] = dt
        day_start_bal = SALDO_INI; dia_pnl_real = 0.0; bloq_dia = False

    for b in bars:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d'); wd = dt.weekday()
        if closes is not None:   # SMA de tendencia (barras anteriores)
            sma_atual = (sum(closes) / sma_len) if len(closes) == sma_len else None
            closes.append(b['c'])

        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            if dia is not None:
                if dia_teve_trade: dias_res.append(dia_pnl_real)
                if dia_pnl_real >= LUCRO_MIN_DIA: acc['qual_dias'] += 1
                acc['max_dia'] = max(acc['max_dia'], dia_pnl_real)
                if modo == 'eod':   # drawdown trava no fechamento do dia
                    acc['eq_peak'] = max(acc['eq_peak'], acc['balance'])
                    if acc['balance'] <= (min(acc['eq_peak'], TRAVA) - DD):
                        queima(dt)
                    else:
                        tenta_saque(dt)
                else:
                    tenta_saque(dt)
            if acc['dia_ini'] is None: acc['dia_ini'] = dt
            dia = d; cur_hi = cur_lo = None
            day_start_bal = acc['balance']; dia_pnl_real = 0.0; bloq_dia = False
            dia_teve_trade = False; trades_dia = 0
            seg_hoje = dom_map.get(d) if wd == 0 else None

        if ENTRADA_INI <= m < ENTRADA_FIM:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])

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
                    if not be_done and (fav - entry) >= be_trig:
                        stop = max(stop, entry + be_lock); be_done = True
                    if be_done: stop = max(stop, fav - trail)
                else:
                    fav = min(fav, b['l'])
                    if not be_done and (entry - fav) >= be_trig:
                        stop = min(stop, entry - be_lock); be_done = True
                    if be_done: stop = min(stop, fav + trail)

        if pos > 0:   uw = (b['l'] - entry) * pos_pv; ub = (b['h'] - entry) * pos_pv
        elif pos < 0: uw = (entry - b['h']) * pos_pv; ub = (entry - b['l']) * pos_pv
        else:         uw = ub = 0.0

        if modo == 'intraday':   # drawdown segue equity intrabar
            acc['eq_peak'] = max(acc['eq_peak'], acc['balance'] + ub)
            if (acc['balance'] + uw) <= (min(acc['eq_peak'], TRAVA) - DD):
                if pos != 0: fecha(b['c'])
                queima(dt); continue

        fator = contratos(acc['eq_peak']) / n_contr
        if stop_dia > 0 and (dia_pnl_real + uw) <= -stop_dia * fator:
            bloq_dia = True
            if pos != 0: fecha(b['c'])
        if dia_pnl_real >= alvo_dia * fator: bloq_dia = True

        if m >= FLATTEN:
            if pos != 0: fecha(b['c'])
            continue

        if bloq_dia or pos != 0: continue
        if max_trades_dia > 0 and trades_dia >= max_trades_dia: continue
        if not (ent_ini <= m < ent_fim): continue
        niv_hi = seg_hoje[0] if seg_hoje else pd_hi
        niv_lo = seg_hoje[1] if seg_hoje else pd_lo
        if niv_hi is None: continue
        tol = TOL_TICKS * TICK; h, l, c = b['h'], b['l'], b['c']; lado = 0
        if h >= niv_hi - tol and c < niv_hi:
            if max_dist == 0 or (niv_hi - c) <= max_dist: lado = -1
        elif l <= niv_lo + tol and c > niv_lo:
            if max_dist == 0 or (c - niv_lo) <= max_dist: lado = 1
        # filtro de tendencia (SMA): so entra na direcao confirmada pelo momentum
        if lado != 0 and sma_atual is not None:
            if lado == -1 and c >= sma_atual: lado = 0   # short so se ja abaixo da media
            elif lado == 1 and c <= sma_atual: lado = 0   # long so se ja acima da media
        if lado != 0:
            nc_t = contratos(acc['eq_peak'])
            pos_pv = MNQ_PV * nc_t; pos_rt = RT_PER * nc_t
            entry = c; pos = lado; fav = c; be_done = False
            stop = c - lado * sl; target = c + lado * tp
            dia_teve_trade = True; trades_dia += 1

    wins = [t for t in trades if t > 0]; losses = [t for t in trades if t <= 0]
    n = len(trades); gw = sum(wins); gl = abs(sum(losses))
    wr = 100 * len(wins) / n if n else 0
    aw = gw / len(wins) if wins else 0; al = gl / len(losses) if losses else 0
    dverde = [x for x in dias_res if x > 0]; nd = len(dias_res)
    ds = sorted(dias_por_saque); med = ds[len(ds)//2] if ds else 0
    return dict(saques=saques_tot, violadas=contas_violadas, completas=contas_completas,
                renda=saques_tot * SAQUE_VAL, dias_med_saque=med,
                n_trades=n, wins=len(wins), losses=len(losses), wr=wr, lr=100 - wr,
                diff_pp=wr - (100 - wr), gw=gw, gl=gl, lucro_liq=gw - gl,
                pf=(gw / gl if gl > 0 else 99), avg_win=aw, avg_loss=al,
                gp_ratio=(aw / al if al > 0 else 0),
                n_dias=nd, dias_verdes=len(dverde), wr_dias=(100 * len(dverde) / nd if nd else 0))


# ---- CONFIG ADOTADA v3 (15/06 apos refinamento + DNA do aprovacao) ----
# BE 1.5/1.0 + alvo diario $400 + escalonamento 2->3 MNQ apos travar a gordura.
# Resultado: 19 saques/ano ($19k) / WR 75.9% / 78.8% dias verdes / PF 1.91 / 0 violacao / OOS 0-0.
# Protecao em 4 camadas: SL 12.5pt/trade -> BE 1.5->1.0 -> stop diario $300 -> DD conta $1.500.
BASE = dict(n_contr=2, alvo_dia=400.0, stop_dia=300.0, max_trades_dia=0,
            max_dist=15.0, tp=60.0, trail=1.75, dias_min=8, modo='intraday',
            be_trig=1.5, be_lock=1.0, contr_fase2=3)

def hdr(titulo):
    print("\n" + "=" * 118); print("  " + titulo); print("=" * 118)
    print(f"  {'variacao':>26s} {'viol':>5s} {'saques':>7s} {'renda$':>9s} "
          f"{'trades':>7s} {'WR%':>6s} {'difp.p':>7s} {'PF':>5s} {'g.med$':>7s} {'p.med$':>7s} "
          f"{'g/p':>5s} {'lucroliq$':>10s}")
    print("-" * 118)

def lin(rotulo, r, mark=""):
    print(f"  {rotulo:>26s} {r['violadas']:>5d} {r['saques']:>7d} {r['renda']:>8,.0f}$ "
          f"{r['n_trades']:>7d} {r['wr']:>5.1f}% {r['diff_pp']:>+6.1f} {r['pf']:>5.2f} "
          f"{r['avg_win']:>6.0f}$ {r['avg_loss']:>6.0f}$ {r['gp_ratio']:>5.2f} {r['lucro_liq']:>9,.0f}${mark}")


if __name__ == '__main__':
    print("Carregando NQ 1-min...")
    bars = carregar(os.path.join('..', 'NQ_dados'))
    if not bars: bars = carregar('NQ_dados')
    dom = domingo_ranges(bars)
    print(f"{len(bars):,} barras | baseline: 2 MNQ, alvo $250/dia, stop $300, Intraday, regra 5 dias")
    base_r = simula(bars, dom, **BASE)

    # ---------- BATERIA 1: filtros de setup (subir WR) ----------
    hdr("BATERIA 1 — FILTROS DE SETUP (objetivo: subir WR / reduzir trades ruins)")
    lin("BASELINE", base_r, "  <-")
    for mt in (1, 2, 3):
        lin(f"max {mt} trade(s)/dia", simula(bars, dom, **{**BASE, 'max_trades_dia': mt}))
    for md in (10.0, 8.0, 6.0, 4.0):
        lin(f"maxDist {md:.0f}pt", simula(bars, dom, **{**BASE, 'max_dist': md}))
    lin("max1/dia + maxDist 8", simula(bars, dom, **{**BASE, 'max_trades_dia': 1, 'max_dist': 8.0}))

    # ---------- BATERIA 2: relacao ganho/perda (TP e trailing) ----------
    hdr("BATERIA 2 — RELACAO GANHO/PERDA (objetivo: ganho medio > perda media)")
    lin("BASELINE (TP60 tr1.75)", base_r, "  <-")
    for t in (40.0, 50.0, 80.0, 100.0, 120.0):
        lin(f"TP {t:.0f}pt", simula(bars, dom, **{**BASE, 'tp': t}))
    for tr in (3.0, 5.0, 8.0, 12.0):
        lin(f"trail {tr:.1f}pt", simula(bars, dom, **{**BASE, 'trail': tr}))
    lin("TP80 + trail 5", simula(bars, dom, **{**BASE, 'tp': 80.0, 'trail': 5.0}))
    lin("TP100 + trail 8", simula(bars, dom, **{**BASE, 'tp': 100.0, 'trail': 8.0}))

    # ---------- BATERIA 3: dias minimos pro saque (regra Apex) ----------
    hdr("BATERIA 3 — DIAS MINIMOS PRO SAQUE (regra Apex: 5 vs 8 vs 10)")
    lin("5 dias (baseline)", base_r, "  <-")
    for dm in (8, 10):
        lin(f"{dm} dias minimos", simula(bars, dom, **{**BASE, 'dias_min': dm}))

    # ---------- BATERIA 4: conta EOD vs Intraday ----------
    hdr("BATERIA 4 — CONTA EOD (DD$1000) vs INTRADAY (DD$1500)")
    lin("INTRADAY (baseline)", base_r, "  <-")
    lin("EOD (DD $1000)", simula(bars, dom, **{**BASE, 'modo': 'eod'}))
    lin("EOD + 3 MNQ", simula(bars, dom, **{**BASE, 'modo': 'eod', 'n_contr': 3}))
    lin("EOD + 3 MNQ alvo$200", simula(bars, dom, **{**BASE, 'modo': 'eod', 'n_contr': 3, 'alvo_dia': 200.0}))

    # ---------- BATERIA 5: melhorar ganho/perda (STOP + BREAKEVEN) ----------
    def hdr2(t):
        print("\n" + "=" * 122); print("  " + t); print("=" * 122)
        print(f"  {'variacao':>26s} {'viol':>4s} {'saqs':>5s} {'trades':>6s} "
              f"{'VERDES (qtd/%)':>16s} {'VERMELHOS (qtd/%)':>18s} {'g.med':>7s} {'p.med':>7s} {'g/p':>5s} {'PF':>5s}")
        print("-" * 122)
    def lin2(rot, r, mark=""):
        v = f"{r['wins']} ({r['wr']:.1f}%)"; vm = f"{r['losses']} ({r['lr']:.1f}%)"
        print(f"  {rot:>26s} {r['violadas']:>4d} {r['saques']:>5d} {r['n_trades']:>6d} "
              f"{v:>16s} {vm:>18s} {r['avg_win']:>6.0f}$ {r['avg_loss']:>6.0f}$ "
              f"{r['gp_ratio']:>5.2f} {r['pf']:>5.2f}{mark}")

    hdr2("BATERIA 5 — MELHORAR GANHO/PERDA: reduzir STOP (SL) e antecipar BREAKEVEN")
    lin2("BASELINE (SL 12.5)", base_r, "  <-")
    for s in (10.0, 8.0, 7.0, 6.0, 5.0, 4.0):
        lin2(f"SL {s:.0f}pt", simula(bars, dom, **{**BASE, 'sl': s}))
    print("  " + "-" * 60)
    for bt, bl in ((3.0, 2.0), (2.5, 1.5), (2.0, 1.0), (1.5, 0.75)):
        lin2(f"BE trig{bt}/lock{bl}", simula(bars, dom, **{**BASE, 'be_trig': bt, 'be_lock': bl}))
    print("  " + "-" * 60)
    lin2("SL8 + BE2.0/1.0", simula(bars, dom, **{**BASE, 'sl': 8.0, 'be_trig': 2.0, 'be_lock': 1.0}))
    lin2("SL6 + BE2.0/1.0", simula(bars, dom, **{**BASE, 'sl': 6.0, 'be_trig': 2.0, 'be_lock': 1.0}))
    lin2("SL7 + BE2.5/1.5 + tr1.25", simula(bars, dom, **{**BASE, 'sl': 7.0, 'be_trig': 2.5, 'be_lock': 1.5, 'trail': 1.25}))
    lin2("SL8 + BE2.5/1.5 + TP80", simula(bars, dom, **{**BASE, 'sl': 8.0, 'be_trig': 2.5, 'be_lock': 1.5, 'tp': 80.0}))

    print("\n" + "=" * 122)
    print("  ALVO: g/p >= 1 (ganho medio >= perda media) MANTENDO viol=0, WR alto e saques.")
    print("  VERDES/VERMELHOS = qtd de trades e % no backtest inteiro.")
    print("=" * 122)
