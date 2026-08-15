#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GESTAO DO DIA (13/08) — filtros de contexto que NUNCA foram testados.

Origem: analise dos 73 trades do forward test 1min de junho/2026
(forward-test-replay-25k/2026-06-1min/). Achados no dado real do mes:
  - 1o ao 4o trade do dia: +$650 | do 5o em diante: -$519
  - Entradas em rajada (<=5min da anterior): -$306 | espacadas: +$474
  - 13 stops cheios (18% dos trades) consumiram 84% do lucro bruto

Testa 3 filtros novos + o SL 15 (validado em 18/06 mas nunca aplicado):
  1. MAX_TRADES_DIA  - cap baixo (2-6). Ja testado 8-12 em 23/06; 4 e novo.
  2. COOLDOWN_MIN    - minutos de espera apos fechar um trade. NUNCA testado.
  3. STOP_APOS_FULL  - para o dia apos 1 stop cheio. NUNCA testado.
  4. SL 15pt         - validado 18/06 (run_stop_sweep), nunca foi pra producao.

Engine identica a run_stop_sweep.py / run_segunda_domingo.py (producao DOM-NOITE).
Nao altera nada em src/ — so mede.
"""
import glob, os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
MNQ_PV = 2.0; RT_PER = 1.20
META = 1500.0; DD = 1500.0; MIN_DIAS = 7
TICK = 0.25; N_CONTR = 5
PTS_BE_TRIG = 3.75; PTS_BE_LOCK = 2.5; PTS_TRAIL = 1.75
TOL_TICKS = 20; TP = 60.0; MAX_DIST = 15.0
ENTRADA_FIM = 16*60; FLATTEN = 16*60+55; ENTRADA_INI = 9*60+30
STOP_DIA = 750.0
BASE_SL = 12.5


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


def bt(bars, dom_map, sl=BASE_SL, max_trades=0, cooldown=0, stop_apos_full=False, slip_ticks=0.0):
    """max_trades=0 -> sem cap | cooldown=0 -> sem espera | stop_apos_full=False -> segue o dia
    slip_ticks: slippage por LADO (entrada e saida), mesmo modelo do run_slippage_test.py"""
    pv = MNQ_PV * N_CONTR; rt = RT_PER * N_CONTR
    slip = slip_ticks * TICK
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False
    realized = 0.0; trades = []
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None
    aprov = reprov = 0; d2a = []; pnl_d0 = 0.0; block = False; dia_k = None
    seg_hoje = None
    # --- novos contadores por dia ---
    n_dia = 0            # trades abertos hoje
    ultima_saida = None  # minuto (ET) do fechamento do ultimo trade
    travou_full = False  # ja tomou stop cheio hoje?
    m_atual = 0          # minuto da barra corrente (pro cooldown)
    limiar_full = -(sl * pv * 0.8)  # perda que conta como "stop cheio"

    def fecha(p):
        nonlocal pos, realized, ultima_saida, travou_full
        if pos == 0: return
        g = ((p - entry) * pos - 2 * slip) * pv - rt
        realized += g; trades.append(g); pos = 0
        ultima_saida = m_atual
        if g <= limiar_full: travou_full = True

    for b in bars:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d'); wd = dt.weekday()
        m_atual = m
        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = cur_lo = None
            seg_hoje = dom_map[d] if (wd == 0 and d in dom_map) else None
        if ENTRADA_INI <= m < 16*60:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
        if d != dia_k:
            dia_k = d; pnl_d0 = realized; block = False
            n_dia = 0; ultima_saida = None; travou_full = False
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
                    if be_done: stop = max(stop, entry + PTS_BE_LOCK, fav - PTS_TRAIL)
                else:
                    fav = min(fav, b['l'])
                    if not be_done and (entry - fav) >= PTS_BE_TRIG:
                        stop = min(stop, entry - PTS_BE_LOCK); be_done = True
                    if be_done: stop = min(stop, entry - PTS_BE_LOCK, fav + PTS_TRAIL)
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
        niv_hi = seg_hoje[0] if seg_hoje else pd_hi
        niv_lo = seg_hoje[1] if seg_hoje else pd_lo
        # --- gates novos (so bloqueiam ABERTURA, nunca a gestao de quem ja esta dentro) ---
        gate = True
        if max_trades and n_dia >= max_trades: gate = False
        if stop_apos_full and travou_full: gate = False
        if cooldown and ultima_saida is not None and (m - ultima_saida) < cooldown: gate = False
        if gate and not block and pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM and niv_hi is not None:
            tol = TOL_TICKS * TICK; h, l, c = b['h'], b['l'], b['c']; lado = 0
            if h >= niv_hi - tol and c < niv_hi:
                if MAX_DIST == 0 or (niv_hi - c) <= MAX_DIST: lado = -1
            elif l <= niv_lo + tol and c > niv_lo:
                if MAX_DIST == 0 or (c - niv_lo) <= MAX_DIST: lado = 1
            if lado != 0:
                entry = c; pos = lado; fav = c; be_done = False
                stop = c - lado * sl; target = c + lado * TP; dias.add(d); n_dia += 1
    if pos != 0: fecha(bars[-1]['c'])

    wins = [t for t in trades if t > 0]; losses = [t for t in trades if t <= 0]
    n = len(trades); tot = aprov + reprov
    gw = sum(wins); gl = abs(sum(losses))
    ds = sorted(d2a); med = ds[len(ds)//2] if ds else 0
    return {
        'n': n, 'wr': 100 * len(wins) / n if n else 0,
        'pf': gw / gl if gl > 0 else 99, 'net': sum(trades),
        'aprov': aprov, 'reprov': reprov, 'tot': tot,
        'taxa': 100 * aprov / tot if tot else 0, 'dmediana': med,
        'avg_win': gw / len(wins) if wins else 0,
        'avg_loss': sum(losses) / len(losses) if losses else 0,
    }


def linha(label, r, base=None):
    delta = ''
    if base is not None and base['net']:
        d = 100 * (r['net'] - base['net']) / abs(base['net'])
        delta = f"{d:+6.0f}%"
    print(f"  {label:<26s} {r['taxa']:>4.0f}% {r['aprov']:>3}/{r['tot']:<3} {r['dmediana']:>4.0f}d "
          f"{r['n']:>5} {r['wr']:>4.0f}% {r['pf']:>5.2f} {r['avg_win']:>6.0f} {r['avg_loss']:>7.0f} "
          f"{r['net']:>10,.0f} {delta:>7s}")


def cab():
    print("=" * 108)
    print(f"  {'config':<26s} {'taxa':>5s} {'aprov':>7s} {'dmed':>5s} {'trades':>5s} {'WR':>5s} "
          f"{'PF':>5s} {'avgW':>6s} {'avgL':>7s} {'PnL$':>10s} {'vs base':>7s}")
    print("-" * 108)


if __name__ == '__main__':
    print("Carregando NQ 1-min..."); bars = carregar('NQ_dados')
    dom = domingo_ranges(bars)
    meio = bars[len(bars)//2]['dt']
    b1 = [b for b in bars if b['dt'] < meio]; b2 = [b for b in bars if b['dt'] >= meio]
    print(f"{len(bars):,} barras | engine de producao (DOM-NOITE). Base = config atual do forward test.\n")

    base = bt(bars, dom)

    print("### 1) BASELINE + SL 15 (validado 18/06, nunca aplicado)")
    cab(); linha("BASE (SL 12,5) *atual*", base, base)
    linha("SL 15pt", bt(bars, dom, sl=15.0), base)
    print()

    print("### 2) MAX TRADES/DIA (dado do mes real sugeria 4)")
    cab(); linha("BASE (sem cap) *atual*", base, base)
    for mt in [2, 3, 4, 5, 6, 8]:
        linha(f"max {mt} trades/dia", bt(bars, dom, max_trades=mt), base)
    print()

    print("### 3) COOLDOWN ENTRE ENTRADAS (nunca testado)")
    cab(); linha("BASE (sem cooldown) *atual*", base, base)
    for cd in [3, 5, 10, 15, 30]:
        linha(f"cooldown {cd} min", bt(bars, dom, cooldown=cd), base)
    print()

    print("### 4) PARAR O DIA APOS 1 STOP CHEIO (nunca testado)")
    cab(); linha("BASE (segue o dia) *atual*", base, base)
    linha("para apos 1 stop cheio", bt(bars, dom, stop_apos_full=True), base)
    print()

    print("### 5) COMBINACOES (so as que fizerem sentido apos ver 1-4)")
    cab(); linha("BASE *atual*", base, base)
    combos = [
        ("SL15 + max4",            dict(sl=15.0, max_trades=4)),
        ("SL15 + cooldown10",      dict(sl=15.0, cooldown=10)),
        ("SL15 + max4 + cd10",     dict(sl=15.0, max_trades=4, cooldown=10)),
        ("SL15 + stop-apos-full",  dict(sl=15.0, stop_apos_full=True)),
        ("max4 + cd10",            dict(max_trades=4, cooldown=10)),
    ]
    res_combo = []
    for lbl, kw in combos:
        r = bt(bars, dom, **kw); linha(lbl, r, base); res_combo.append((lbl, kw, r))
    print()

    print("### 5b) O TESTE DECISIVO: SL 12,5 vs SL 15 COM SLIPPAGE REALISTA")
    print("     (o forward test real ficou MUITO abaixo do backtest sem slippage -")
    print("      a pergunta e se o SL15 aguenta o atrito de execucao ou se e ilusao)")
    cab()
    for slp in [0.0, 1.0, 2.0, 3.0]:
        b12 = bt(bars, dom, sl=12.5, slip_ticks=slp)
        b15 = bt(bars, dom, sl=15.0, slip_ticks=slp)
        tag = "  <-- cenario realista" if slp == 2.0 else ""
        print(f"  --- slippage {slp:.0f} tick(s) = ${slp*TICK*MNQ_PV*N_CONTR*2:.0f}/trade{tag}")
        linha(f"   SL 12,5 (atual)", b12, b12)
        linha(f"   SL 15", b15, b12)
    print()

    print("### 6) ROBUSTEZ OOS (1a metade | 2a metade) — base + top 3 por PnL")
    print("-" * 108)
    ranked = sorted(res_combo, key=lambda x: -x[2]['net'])[:3]
    alvos = [("BASE (atual)", {})] + [(l, k) for l, k, _ in ranked]
    for lbl, kw in alvos:
        r1 = bt(b1, dom, **kw); r2 = bt(b2, dom, **kw)
        print(f"    {lbl:<26s} {r1['taxa']:>3.0f}% PF {r1['pf']:.2f} ${r1['net']:>9,.0f}  |  "
              f"{r2['taxa']:>3.0f}% PF {r2['pf']:.2f} ${r2['net']:>9,.0f}")
    print("-" * 108)
    print("\n  Criterio: so vale se melhorar PnL E taxa de aprovacao E segurar nas DUAS metades OOS.")
