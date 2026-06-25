#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VARREDURA TRAILING DA NOTURNA (23/06/2026)
Pergunta: L23 saiu em +$23 (+2.5pt) enquanto o mercado continuou +40pt.
Trailing 1.75pt apertado demais pra movimentos direcionais fortes?

Varia PTS_TRAIL da noturna: [1.75, 3, 5, 8, 12]
BE_TRIG e BE_LOCK mantidos (3.75/2.5 - config de producao).
Avalia: SÓ NOTURNA | COMBINADO. Taxa de aprov, dias, WR, PF, PnL, OOS.
"""
import glob, os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); BR = ZoneInfo('America/Sao_Paulo'); UTC = timezone.utc
MNQ_PV = 2.0; RT_PER = 1.20
META = 1500.0; DD = 1500.0; MIN_DIAS = 7
TICK = 0.25; N_CONTR = 5
PTS_SL = 12.5; PTS_BE_TRIG = 3.75; PTS_BE_LOCK = 2.5
PTS_TRAIL_DIURNA = 1.75  # diurna fixo (ja provado otimo)

TOL_TICKS = 20; TP = 60.0; MAX_DIST = 15.0
ENTRADA_INI = 9*60+30; ENTRADA_FIM = 16*60; FLATTEN = 16*60+55; STOP_DIA = 750.0

NOITE_INI_BR = 19*60; NOITE_FIM_BR = 21*60
NOITE_WARMUP_BR = 19*60+15; NOITE_FLATTEN_BR = 22*60
FIB_VENDA = 0.764; FIB_COMPRA = 0.236; RANGE_MIN = 15.0
REJ_PAVIO = 0.5; REJ_DOJI = 0.3; GATILHO_BARRAS = 4; TP_NOITE = 60.0


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
                    vistos[dt] = (dt.astimezone(ET), dt.astimezone(BR), o, h, l, c, v)
    return [{'dt': vistos[k][0], 'br': vistos[k][1], 'o': vistos[k][2], 'h': vistos[k][3],
             'l': vistos[k][4], 'c': vistos[k][5], 'v': vistos[k][6]} for k in sorted(vistos)]


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


def eh_rejeicao_alta(b):
    rng = b['h'] - b['l']
    if rng <= 0: return False
    corpo = abs(b['c'] - b['o']); pav_sup = b['h'] - max(b['o'], b['c'])
    return pav_sup >= REJ_PAVIO * rng or corpo <= REJ_DOJI * rng


def eh_rejeicao_baixa(b):
    rng = b['h'] - b['l']
    if rng <= 0: return False
    corpo = abs(b['c'] - b['o']); pav_inf = min(b['o'], b['c']) - b['l']
    return pav_inf >= REJ_PAVIO * rng or corpo <= REJ_DOJI * rng


def bt(bars, usar_diurna, usar_noturna, dom_map, trail_noturna):
    """Engine combinada. trail_noturna: trailing em pontos para trades noturnos.
    Diurna usa sempre PTS_TRAIL_DIURNA=1.75 (já validado como ótimo)."""
    pv = MNQ_PV * N_CONTR; rt = RT_PER * N_CONTR
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False; origem = None
    realized = 0.0; trades = []
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None
    aprov = reprov = 0; d2a = []; pnl_d0 = 0.0; block = False; dia_k = None
    seg_hoje = None
    noite_dia = None; noite_hi = noite_lo = None; pend = None; not_trades_dia = 0
    t_diur = []; t_not = []; trade_org = None

    def fecha(p):
        nonlocal pos, realized
        if pos == 0: return
        g = (p - entry) * pos * pv - rt
        realized += g; trades.append(g)
        if trade_org == 'D': t_diur.append(g)
        elif trade_org == 'N': t_not.append(g)
        pos = 0

    for b in bars:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d'); wd = dt.weekday()
        mbr = mins(b['br']); dbr = b['br'].strftime('%Y-%m-%d')

        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = cur_lo = None
            seg_hoje = dom_map[d] if (dom_map and wd == 0 and d in dom_map) else None
        if ENTRADA_INI <= m < 16*60:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
        if d != dia_k:
            dia_k = d; pnl_d0 = realized; block = False
        if ini_aval is None: ini_aval = dt

        if pos != 0:
            saiu = False
            # trailing ativo: usa trail da origem correta
            trail_ativo = trail_noturna if trade_org == 'N' else PTS_TRAIL_DIURNA
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
                    if be_done: stop = max(stop, fav - trail_ativo)
                else:
                    fav = min(fav, b['l'])
                    if not be_done and (entry - fav) >= PTS_BE_TRIG:
                        stop = min(stop, entry - PTS_BE_LOCK); be_done = True
                    if be_done: stop = min(stop, fav + trail_ativo)

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

        if usar_diurna:
            if m >= FLATTEN and pos != 0 and origem == 'D':
                fecha(b['c'])
            if not block and pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
                niv_hi = seg_hoje[0] if seg_hoje else pd_hi
                niv_lo = seg_hoje[1] if seg_hoje else pd_lo
                if niv_hi is not None:
                    tol = TOL_TICKS * TICK; h, l, c = b['h'], b['l'], b['c']; lado = 0
                    if h >= niv_hi - tol and c < niv_hi:
                        if MAX_DIST == 0 or (niv_hi - c) <= MAX_DIST: lado = -1
                    elif l <= niv_lo + tol and c > niv_lo:
                        if MAX_DIST == 0 or (c - niv_lo) <= MAX_DIST: lado = 1
                    if lado != 0:
                        entry = c; pos = lado; fav = c; be_done = False; origem = 'D'; trade_org = 'D'
                        stop = c - lado * PTS_SL; target = c + lado * TP; dias.add(d)

        if usar_noturna:
            na_janela = NOITE_INI_BR <= mbr < NOITE_FIM_BR
            if na_janela:
                if dbr != noite_dia:
                    noite_dia = dbr; noite_hi = b['h']; noite_lo = b['l']; pend = None; not_trades_dia = 0
                else:
                    noite_hi = max(noite_hi, b['h']); noite_lo = min(noite_lo, b['l'])
            if mbr >= NOITE_FLATTEN_BR and pos != 0 and origem == 'N':
                fecha(b['c'])
            pode = (na_janela and mbr >= NOITE_WARMUP_BR and noite_hi is not None
                    and (noite_hi - noite_lo) >= RANGE_MIN)
            if pode and not block:
                rng = noite_hi - noite_lo
                z_venda = noite_lo + FIB_VENDA * rng
                z_compra = noite_lo + FIB_COMPRA * rng
                if pos == 0 and pend is not None:
                    lado, nivel, rest = pend
                    if lado == -1 and b['l'] <= nivel:
                        entry = min(nivel, b['o']); pos = -1; fav = entry; be_done = False
                        origem = 'N'; trade_org = 'N'; not_trades_dia += 1
                        stop = entry + PTS_SL; target = entry - TP_NOITE; dias.add(d); pend = None
                    elif lado == 1 and b['h'] >= nivel:
                        entry = max(nivel, b['o']); pos = 1; fav = entry; be_done = False
                        origem = 'N'; trade_org = 'N'; not_trades_dia += 1
                        stop = entry - PTS_SL; target = entry + TP_NOITE; dias.add(d); pend = None
                    else:
                        rest -= 1; pend = None if rest <= 0 else (lado, nivel, rest)
                if pos == 0 and pend is None:
                    if b['h'] >= z_venda and eh_rejeicao_alta(b):
                        pend = (-1, b['l'], GATILHO_BARRAS)
                    elif b['l'] <= z_compra and eh_rejeicao_baixa(b):
                        pend = (1, b['h'], GATILHO_BARRAS)
            elif not na_janela:
                pend = None

    if pos != 0: fecha(bars[-1]['c'])

    def stats(ts):
        w = [t for t in ts if t > 0]; n = len(ts)
        gw = sum(w); gl = abs(sum(t for t in ts if t <= 0))
        avg_w = gw/len(w) if w else 0
        avg_l = sum(t for t in ts if t <= 0)/len([t for t in ts if t <= 0]) if [t for t in ts if t <= 0] else 0
        return {'n': n, 'wr': 100*len(w)/n if n else 0,
                'pf': gw/gl if gl > 0 else (99 if gw > 0 else 0),
                'net': sum(ts), 'avg_w': avg_w, 'avg_l': avg_l}

    g = stats(trades); tot = aprov + reprov
    ds = sorted(d2a); med = ds[len(ds)//2] if ds else 0
    g.update({'aprov': aprov, 'reprov': reprov, 'tot': tot,
              'taxa': 100*aprov/tot if tot else 0,
              'dmediana': med,
              'diur': stats(t_diur), 'not': stats(t_not)})
    return g


if __name__ == '__main__':
    print("Carregando NQ 1-min..."); bars = carregar('NQ_dados')
    dom = domingo_ranges(bars)
    meio = bars[len(bars)//2]['dt']
    b1 = [b for b in bars if b['dt'] < meio]
    b2 = [b for b in bars if b['dt'] >= meio]
    print(f"{len(bars):,} barras | 5 MNQ | meta ${META:.0f} DD ${DD:.0f}")
    print(f"Diurna: trail FIXO 1.75pt (ótimo provado) | Noturna: trail VARIADO\n")

    TRAIL_GRID = [1.75, 3.0, 5.0, 8.0, 12.0]
    BASE_TRAIL = 1.75

    print("=" * 102)
    print("  SWEEP TRAILING NOTURNA  (* = producao atual)")
    print("  Diurna trail = 1.75pt fixo | BE 3.75/2.5 inalterado")
    print("=" * 102)
    print(f"  {'trail':>7s}  {'-- SÓ NOTURNA --------':^30s}  {'-- COMBINADO -----------------------':^45s}")
    print(f"  {'':>7s}  {'taxa':>4s} {'aprv':>5s} {'d.med':>5s} {'WR':>4s} {'PF':>5s} {'avgW':>6s} {'PnL$':>9s}  "
          f"{'taxa':>4s} {'aprv':>5s} {'d.med':>5s} {'WR':>4s} {'PF':>5s} {'PnL$':>9s}")
    print("-" * 102)

    resultados = []
    for tr in TRAIL_GRID:
        tag = " *" if tr == BASE_TRAIL else "  "
        rn = bt(bars, False, True, dom, tr)
        rc = bt(bars, True, True, dom, tr)
        nd = rn['not']
        print(f"  trail{tr:>4.2f}pt{tag}  "
              f"{rn['taxa']:>3.0f}% {rn['aprov']:>2}/{rn['tot']:<2} {rn['dmediana']:>4.0f}d "
              f"{nd['wr']:>3.0f}% {nd['pf']:>5.2f} {nd['avg_w']:>6.0f} {nd['net']:>9,.0f}  "
              f"{rc['taxa']:>3.0f}% {rc['aprov']:>2}/{rc['tot']:<2} {rc['dmediana']:>4.0f}d "
              f"{rc['not']['wr']:>3.0f}% {rc['not']['pf']:>5.2f} {rc['net']:>9,.0f}")
        resultados.append((tr, rn, rc))

    print("=" * 102)
    print("\n  ROBUSTEZ OOS (1a metade | 2a metade) — COMBINADO")
    print("-" * 70)
    for tr, _, _ in resultados:
        tag = " (baseline)" if tr == BASE_TRAIL else ""
        r1 = bt(b1, True, True, dom, tr)
        r2 = bt(b2, True, True, dom, tr)
        print(f"  trail {tr:.2f}pt{tag:>11s}  "
              f"1a: {r1['aprov']:>2}/{r1['tot']:<2} ({r1['taxa']:>3.0f}%) PF {r1['pf']:>4.2f} med {r1['dmediana']:>3.0f}d  |  "
              f"2a: {r2['aprov']:>2}/{r2['tot']:<2} ({r2['taxa']:>3.0f}%) PF {r2['pf']:>4.2f} med {r2['dmediana']:>3.0f}d")
    print("=" * 70)

    print("\n  IMPACTO NOS TRADES NOTURNOS (SÓ NOTURNA — avgWin / avgLoss / WR):")
    print("-" * 55)
    for tr, rn, _ in resultados:
        nd = rn['not']
        tag = " *" if tr == BASE_TRAIL else "  "
        print(f"  trail {tr:.2f}pt{tag}  WR {nd['wr']:>3.0f}% | avgW ${nd['avg_w']:>5.0f} "
              f"| avgL ${nd['avg_l']:>6.0f} | PF {nd['pf']:>4.2f}")
    print("=" * 55)
    print("\n  VEREDICTO:")
    base_rn = next(rn for tr, rn, _ in resultados if tr == BASE_TRAIL)
    base_rc = next(rc for tr, _, rc in resultados if tr == BASE_TRAIL)
    melhor_rc = max(resultados, key=lambda x: (x[2]['taxa'], x[2]['not']['pf']))
    bt_tr, bt_rn, bt_rc = melhor_rc
    print(f"  Baseline (1.75pt): COMBINADO {base_rc['taxa']:.0f}% ({base_rc['aprov']}/{base_rc['tot']}) "
          f"PF {base_rc['pf']:.2f} PnL ${base_rc['net']:,.0f}")
    print(f"  Melhor noturna:    trail {bt_tr:.2f}pt -> COMBINADO {bt_rc['taxa']:.0f}% "
          f"({bt_rc['aprov']}/{bt_rc['tot']}) PF {bt_rc['pf']:.2f} PnL ${bt_rc['net']:,.0f}")
    if bt_tr == BASE_TRAIL:
        print("  >> Baseline JA E OTIMO. Aumentar trailing NA NOTURNA nao melhora.")
    else:
        diff_pnl = bt_rc['net'] - base_rc['net']
        print(f"  >> trail {bt_tr:.2f}pt domina baseline. Ganho PnL: ${diff_pnl:+,.0f}. "
              f"Validar OOS antes de mudar producao.")
