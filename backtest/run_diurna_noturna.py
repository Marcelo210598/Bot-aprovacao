#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIURNA + NOTURNA NA MESMA CONTA (16/06)
=======================================
Combina, na MESMA conta Apex 25K / 5 MNQ:

  DIURNA  (estrategia de producao "Niveis" dos 100%)
    - reversao na maxima/minima do dia anterior, 9h30->16h ET
    - tol 20t, TP 60, trail 1.75, maxDist 15pt, stop/dia $750
    - segunda usa range do domingo a noite (modo dom_noite)

  NOTURNA ("Nomads Trade da Noite", 19h-21h BR)
    - canal dinamico formado entre 19h-21h BR + retracoes de Fibonacci
    - VENDA na zona 76.4%-100% (topo) apos vela de rejeicao de alta
    - COMPRA na zona 0%-23.6% (fundo) apos vela de rejeicao de baixa
    - gatilho = rompimento do pavio da vela de rejeicao nas ~4 barras seguintes
    - gestao IGUAL a diurna (stop 12.5pt + BE 3.75/2.5 + trailing 1.75) -> deixa correr

A conta e UNICA: DD, meta, dias operados e aprovacao somam trades das duas.
Rodamos 3 cenarios para comparar: SO DIURNA | SO NOTURNA | COMBINADO.

PREMISSAS objetivadas da noturna (a estrategia veio sem stop/alvo numerico):
  - barras de 1min; canal = max/min acumulado desde 19h00 BR ate a barra atual
  - warm-up: so opera a partir de 19h15 BR e exige canal >= 15pt (evita canal raso)
  - vela de rejeicao = pavio dominante (>=50% do range) OU doji (corpo <=30%) tocando a zona
  - alvo = teto de 60pt + trailing (mesma mecanica que destravou a diurna: deixa correr)
  - nao abre apos 21h BR; flatten de seguranca 22h BR (nao carrega overnight)
"""
import glob, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); BR = ZoneInfo('America/Sao_Paulo'); UTC = timezone.utc
MNQ_PV = 2.0; RT_PER = 1.20
META = 1500.0; DD = 1500.0; MIN_DIAS = 7
TICK = 0.25; N_CONTR = 5
PTS_SL = 12.5; PTS_BE_TRIG = 3.75; PTS_BE_LOCK = 2.5; PTS_TRAIL = 1.75

# --- DIURNA (config de producao) ---
TOL_TICKS = 20; TP = 60.0; MAX_DIST = 15.0
ENTRADA_INI = 9*60+30; ENTRADA_FIM = 16*60; FLATTEN = 16*60+55
STOP_DIA = 750.0

# --- NOTURNA (Nomads Noite) ---
NOITE_INI_BR = 19*60; NOITE_FIM_BR = 21*60
NOITE_WARMUP_BR = 19*60+15; NOITE_FLATTEN_BR = 22*60
FIB_VENDA = 0.764; FIB_COMPRA = 0.236
RANGE_MIN = 15.0          # canal minimo (pts) pra operar
REJ_PAVIO = 0.5           # pavio >= 50% do range = rejeicao
REJ_DOJI = 0.3            # corpo <= 30% do range = doji
GATILHO_BARRAS = 4        # janela (min) p/ romper o pavio da vela anterior
TP_NOITE = 60.0           # teto; trailing cuida da saida real


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
    """high/low do domingo a noite (18h->24h ET) por data da SEGUNDA seguinte."""
    from datetime import timedelta
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


def bt(bars, usar_diurna=True, usar_noturna=True, dom_map=None, sl_not=PTS_SL, tp_not=TP_NOITE,
       max_not=99, rng_min=RANGE_MIN):
    pv = MNQ_PV * N_CONTR; rt = RT_PER * N_CONTR
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False; origem = None
    realized = 0.0; trades = []
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None
    aprov = reprov = 0; d2a = []; pnl_d0 = 0.0; block = False; dia_k = None
    seg_hoje = None
    # estado noturno
    noite_dia = None; noite_hi = noite_lo = None; pend = None  # pend=(lado,nivel,restantes)
    not_trades_dia = 0
    # contabilidade por origem
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

        # ---- gestao da posicao aberta (qualquer origem) ----
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
                    if be_done: stop = max(stop, fav - PTS_TRAIL)
                else:
                    fav = min(fav, b['l'])
                    if not be_done and (entry - fav) >= PTS_BE_TRIG:
                        stop = min(stop, entry - PTS_BE_LOCK); be_done = True
                    if be_done: stop = min(stop, fav + PTS_TRAIL)

        # ---- avaliacao da CONTA (DD / meta / aprovacao) ----
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

        # ============ DIURNA ============
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

        # ============ NOTURNA ============
        if usar_noturna:
            na_janela = NOITE_INI_BR <= mbr < NOITE_FIM_BR
            # reset/atualiza canal da sessao noturna
            if na_janela:
                if dbr != noite_dia:
                    noite_dia = dbr; noite_hi = b['h']; noite_lo = b['l']; pend = None; not_trades_dia = 0
                else:
                    noite_hi = max(noite_hi, b['h']); noite_lo = min(noite_lo, b['l'])
            # flatten de seguranca pos-sessao
            if mbr >= NOITE_FLATTEN_BR and pos != 0 and origem == 'N':
                fecha(b['c'])
            # so opera dentro da janela, com warmup e canal valido
            pode = (na_janela and mbr >= NOITE_WARMUP_BR and noite_hi is not None
                    and (noite_hi - noite_lo) >= rng_min)
            if pode and not block and not_trades_dia < max_not:
                rng = noite_hi - noite_lo
                z_venda = noite_lo + FIB_VENDA * rng   # 76.4%
                z_compra = noite_lo + FIB_COMPRA * rng  # 23.6%
                # 1) tenta acionar setup pendente (rompimento do pavio nas ~4 barras)
                if pos == 0 and pend is not None:
                    lado, nivel, rest = pend
                    if lado == -1 and b['l'] <= nivel:       # venda: rompeu pra baixo
                        entry = min(nivel, b['o']); pos = -1; fav = entry; be_done = False
                        origem = 'N'; trade_org = 'N'; not_trades_dia += 1
                        stop = entry + sl_not; target = entry - tp_not; dias.add(d); pend = None
                    elif lado == 1 and b['h'] >= nivel:      # compra: rompeu pra cima
                        entry = max(nivel, b['o']); pos = 1; fav = entry; be_done = False
                        origem = 'N'; trade_org = 'N'; not_trades_dia += 1
                        stop = entry - sl_not; target = entry + tp_not; dias.add(d); pend = None
                    else:
                        rest -= 1; pend = None if rest <= 0 else (lado, nivel, rest)
                # 2) detecta nova vela de rejeicao p/ armar setup (se sem pos e sem pend)
                if pos == 0 and pend is None:
                    if b['h'] >= z_venda and eh_rejeicao_alta(b):
                        pend = (-1, b['l'], GATILHO_BARRAS)     # gatilho = pavio inferior
                    elif b['l'] <= z_compra and eh_rejeicao_baixa(b):
                        pend = (1, b['h'], GATILHO_BARRAS)      # gatilho = pavio superior
            elif not na_janela:
                pend = None

    if pos != 0: fecha(bars[-1]['c'])

    def stats(ts):
        w = [t for t in ts if t > 0]; n = len(ts)
        gw = sum(w); gl = abs(sum(t for t in ts if t <= 0))
        return {'n': n, 'wr': 100*len(w)/n if n else 0,
                'pf': gw/gl if gl > 0 else (99 if gw > 0 else 0), 'net': sum(ts)}

    g = stats(trades); tot = aprov + reprov
    ds = sorted(d2a); med = ds[len(ds)//2] if ds else 0
    g.update({'aprov': aprov, 'reprov': reprov, 'tot': tot,
              'taxa': 100*aprov/tot if tot else 0,
              'dmediana': med, 'dmed': sum(d2a)/len(d2a) if d2a else 0,
              'dmin': min(d2a) if d2a else 0, 'dmax': max(d2a) if d2a else 0,
              'trd_dia': g['n']/220,
              'diur': stats(t_diur), 'not': stats(t_not)})
    return g


def linha(label, r):
    print(f"  {label:>16s} {r['taxa']:>4.0f}% {r['aprov']:>4}/{r['tot']:<3} {r['dmediana']:>4.0f}d "
          f"{r['n']:>5} {r['trd_dia']:>5.1f} {r['wr']:>3.0f}% {r['pf']:>5.2f} {r['net']:>10,.0f}")


if __name__ == '__main__':
    print("Carregando NQ 1-min real..."); bars = carregar('NQ_dados')
    dom = domingo_ranges(bars)
    meio = bars[len(bars)//2]['dt']
    b1 = [b for b in bars if b['dt'] < meio]; b2 = [b for b in bars if b['dt'] >= meio]
    # quantas barras caem na janela noturna?
    n_noite = sum(1 for b in bars if NOITE_INI_BR <= mins(b['br']) < NOITE_FIM_BR)
    print(f"{len(bars):,} barras | {n_noite:,} na janela 19h-21h BR")
    print(f"Conta 25K / 5 MNQ | risco ${PTS_SL*MNQ_PV*N_CONTR:.0f}/trade | meta ${META:.0f} DD ${DD:.0f}\n")

    rd = bt(bars, True, False, dom)    # so diurna
    rn = bt(bars, False, True, dom)    # so noturna
    rc = bt(bars, True, True, dom)     # combinado

    print("=" * 80)
    print("  CENARIO            taxa  aprov   d.med trades t/dia  WR    PF   PnL$/ano")
    print("=" * 80)
    linha("SO DIURNA", rd)
    linha("SO NOTURNA", rn)
    linha("COMBINADO", rc)
    print("=" * 80)

    print("\n  COMBINADO — quebra por estrategia (trades / WR / PnL$):")
    print(f"    Diurnos : {rc['diur']['n']:>5} | WR {rc['diur']['wr']:>3.0f}% | PF {rc['diur']['pf']:>4.2f} | ${rc['diur']['net']:>9,.0f}")
    print(f"    Noturnos: {rc['not']['n']:>5} | WR {rc['not']['wr']:>3.0f}% | PF {rc['not']['pf']:>4.2f} | ${rc['not']['net']:>9,.0f}")

    print("\n" + "=" * 80)
    print("  ROBUSTEZ OUT-OF-SAMPLE (1a metade  |  2a metade)")
    print("=" * 80)
    for label, ud, un in [("SO DIURNA", True, False), ("SO NOTURNA", False, True),
                          ("COMBINADO", True, True)]:
        r1 = bt(b1, ud, un, dom); r2 = bt(b2, ud, un, dom)
        print(f"  {label:>12s}  {r1['aprov']:>2}/{r1['tot']:<2} ({r1['taxa']:>3.0f}%) PF {r1['pf']:>4.2f} med {r1['dmediana']:>3.0f}d  "
              f"|  {r2['aprov']:>2}/{r2['tot']:<2} ({r2['taxa']:>3.0f}%) PF {r2['pf']:>4.2f} med {r2['dmediana']:>3.0f}d")
    print("=" * 80)

    # ---- VARREDURA SL x TP da NOTURNA (gestao identica a manha; varia so SL/TP) ----
    SL_GRID = [10.0, 12.5, 15.0]; TP_GRID = [40.0, 60.0, 80.0, 120.0]
    print("\n" + "=" * 92)
    print("  VARREDURA NOTURNA — SL x TP (BE 3.75/2.5 + trail 1.75, igual a manha)")
    print("=" * 92)
    print("  -------------- SO NOTURNA --------------    ----------- COMBINADO -----------")
    print(f"  {'SL':>4s} {'TP':>4s} | {'taxa':>4s} {'aprv':>5s} {'d.med':>5s} {'t/dia':>5s} "
          f"{'WR':>3s} {'PF':>5s} {'PnL$':>8s} | {'taxa':>4s} {'aprv':>5s} {'d.med':>5s} {'PF':>5s} {'PnL$':>8s}")
    print("-" * 92)
    melhor = None
    for sl in SL_GRID:
        for tp in TP_GRID:
            rn = bt(bars, False, True, dom, sl, tp)
            rc = bt(bars, True, True, dom, sl, tp)
            mark = " *igual-manha" if (sl == 12.5 and tp == 60.0) else ""
            print(f"  {sl:>4.1f} {tp:>4.0f} | {rn['taxa']:>3.0f}% {rn['aprov']:>2}/{rn['tot']:<2} "
                  f"{rn['dmediana']:>4.0f}d {rn['trd_dia']:>5.1f} {rn['wr']:>3.0f}% {rn['pf']:>5.2f} {rn['net']:>8,.0f} | "
                  f"{rc['taxa']:>3.0f}% {rc['aprov']:>2}/{rc['tot']:<2} {rc['dmediana']:>4.0f}d "
                  f"{rc['pf']:>5.2f} {rc['net']:>8,.0f}{mark}")
            cand = (rc['taxa'], rc['net'], sl, tp, rc)
            if melhor is None or (cand[0], cand[1]) > (melhor[0], melhor[1]): melhor = cand
        print("-" * 92)
    _, _, bsl, btp, brc = melhor
    print(f"  >> Melhor COMBINADO por (taxa, PnL): SL {bsl:.1f} / TP {btp:.0f} -> "
          f"{brc['taxa']:.0f}% ({brc['aprov']}/{brc['tot']}) med {brc['dmediana']:.0f}d "
          f"PF {brc['pf']:.2f} PnL ${brc['net']:,.0f}")
    print("=" * 92)

    # ---- ANTI-OVERTRADING: limite de trades/noite x range minimo do canal ----
    MAXN_GRID = [1, 2, 3, 99]; RNG_GRID = [15.0, 25.0, 40.0]
    print("\n" + "=" * 96)
    print("  ANTI-OVERTRADING NOTURNO (SL 12.5 / TP 60 da manha) — max trades/noite x canal minimo")
    print("=" * 96)
    print("  ------------ SO NOTURNA ------------    -------------- COMBINADO --------------")
    print(f"  {'maxN':>4s} {'rng':>4s} | {'taxa':>4s} {'aprv':>5s} {'t/dia':>5s} {'WR':>3s} {'PF':>5s} {'PnL$':>8s} "
          f"| {'taxa':>4s} {'aprv':>5s} {'d.med':>5s} {'t/dia':>5s} {'PF':>5s} {'PnL$':>8s}")
    print("-" * 96)
    melhorc = None
    for mn in MAXN_GRID:
        for rg in RNG_GRID:
            rn = bt(bars, False, True, dom, max_not=mn, rng_min=rg)
            rc = bt(bars, True, True, dom, max_not=mn, rng_min=rg)
            print(f"  {mn:>4} {rg:>4.0f} | {rn['taxa']:>3.0f}% {rn['aprov']:>2}/{rn['tot']:<2} {rn['trd_dia']:>5.1f} "
                  f"{rn['wr']:>3.0f}% {rn['pf']:>5.2f} {rn['net']:>8,.0f} | {rc['taxa']:>3.0f}% {rc['aprov']:>2}/{rc['tot']:<2} "
                  f"{rc['dmediana']:>4.0f}d {rc['trd_dia']:>5.1f} {rc['pf']:>5.2f} {rc['net']:>8,.0f}")
            cand = (rc['taxa'], rc['net'], mn, rg, rc)
            if melhorc is None or (cand[0], cand[1]) > (melhorc[0], melhorc[1]): melhorc = cand
        print("-" * 96)
    _, _, bmn, brg, bc = melhorc
    print(f"  >> Melhor COMBINADO: maxN {bmn} / canal>={brg:.0f}pt -> {bc['taxa']:.0f}% "
          f"({bc['aprov']}/{bc['tot']}) med {bc['dmediana']:.0f}d t/dia {bc['trd_dia']:.1f} "
          f"PF {bc['pf']:.2f} PnL ${bc['net']:,.0f}")
    # robustez OOS da melhor
    r1 = bt(b1, True, True, dom, max_not=bmn, rng_min=brg)
    r2 = bt(b2, True, True, dom, max_not=bmn, rng_min=brg)
    print(f"     OOS -> 1a: {r1['aprov']}/{r1['tot']} ({r1['taxa']:.0f}%) PF {r1['pf']:.2f} | "
          f"2a: {r2['aprov']}/{r2['tot']} ({r2['taxa']:.0f}%) PF {r2['pf']:.2f}")
    print("=" * 96)
