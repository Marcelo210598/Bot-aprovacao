#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NEWS FILTER (FOMC) — vale a pena? (23/06)
=========================================
Item #2 das melhorias. A comunidade para de operar em torno de eventos de alto
impacto (FOMC, CPI, NFP) porque o spike vira whipsaw e detona reversao. Mede com
numero: blackout em torno do FOMC (14h ET) melhora a DIURNA?

Engine = DIURNA-ONLY (noturna desligada), config producao + SLIPPAGE 2 TICKS
(nosso baseline realista). FOMC = unico evento testado aqui porque:
  - 14h ET cai DENTRO da janela diurna (9h30-16h);
  - horario exato e previsivel; datas sao publicas (8/ano).

FOMC = anuncio no 2o dia da reuniao, 14h00 ET. Datas no range 11/06/25-11/06/26
(calendario oficial do Fed). Press conf (Powell) 14h30 = +30min de turbulencia.

Compara: SEM filtro vs blackout de +/- X min em torno das 14h, em 3 larguras de
janela. Mostra tambem o PnL especifico DOS dias de FOMC (com e sem filtro).
"""
import glob, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
MNQ_PV = 2.0; RT_PER = 1.20
META = 1500.0; DD = 1500.0; MIN_DIAS = 7
TICK = 0.25; N_CONTR = 5
PTS_SL = 12.5; PTS_BE_TRIG = 3.75; PTS_BE_LOCK = 2.5; PTS_TRAIL = 1.75
TOL_TICKS = 20; TP = 60.0; MAX_DIST = 15.0
ENTRADA_INI = 9*60+30; ENTRADA_FIM = 16*60; FLATTEN = 16*60+55
STOP_DIA = 750.0
SLIP_BASE = 2.0   # baseline realista (ticks por lado)

# FOMC: anuncio 14h00 ET. Datas no range dos dados (11/06/2025 -> 11/06/2026).
FOMC_DATAS = {
    '2025-06-18', '2025-07-30', '2025-09-17', '2025-10-29',
    '2025-12-10', '2026-01-28', '2026-03-18', '2026-04-29',
}
FOMC_HORA_ET = 14*60   # 14h00 ET


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
    from datetime import timedelta
    dom = {}
    for b in bars:
        dt = b['dt']; wd = dt.weekday(); m = mins(dt)
        if wd == 6 and m >= 18*60:
            seg = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
            if seg not in dom: dom[seg] = [b['h'], b['l']]
            else: dom[seg][0] = max(dom[seg][0], b['h']); dom[seg][1] = min(dom[seg][1], b['l'])
    return {k: tuple(v) for k, v in dom.items()}


def bt(bars, dom_map=None, slip_ticks=SLIP_BASE, news_buffer=0, flat_news=True):
    """
    DIURNA only. news_buffer=0 -> sem filtro. >0 -> blackout +/- buffer min em torno
    das 14h ET nos dias de FOMC: bloqueia entradas e (se flat_news) fecha posicao
    aberta ao ENTRAR na janela (protege do spike).
    Retorna stats gerais + PnL isolado dos dias de FOMC.
    """
    pv = MNQ_PV * N_CONTR; rt = RT_PER * N_CONTR
    slip = slip_ticks * TICK
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False
    realized = 0.0; trades = []
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None
    aprov = reprov = 0; d2a = []; pnl_d0 = 0.0; block = False; dia_k = None
    seg_hoje = None
    pnl_fomc = 0.0; n_fomc = 0   # contabilidade isolada dos dias de FOMC

    def fecha(p, dia_atual):
        nonlocal pos, realized, pnl_fomc, n_fomc
        if pos == 0: return
        g = ((p - entry) * pos - 2 * slip) * pv - rt
        realized += g; trades.append(g)
        if dia_atual in FOMC_DATAS: pnl_fomc += g; n_fomc += 1
        pos = 0

    nb_lo = FOMC_HORA_ET - news_buffer; nb_hi = FOMC_HORA_ET + news_buffer

    for b in bars:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d'); wd = dt.weekday()
        eh_fomc = d in FOMC_DATAS
        em_blackout = (news_buffer > 0 and eh_fomc and nb_lo <= m < nb_hi)

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

        # gestao posicao aberta
        if pos != 0:
            saiu = False
            if pos > 0:
                if b['l'] <= stop: fecha(stop, d); saiu = True
                elif b['h'] >= target: fecha(target, d); saiu = True
            else:
                if b['h'] >= stop: fecha(stop, d); saiu = True
                elif b['l'] <= target: fecha(target, d); saiu = True
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

        # NEWS FILTER: ao entrar na janela de blackout, fecha posicao aberta (protege do spike)
        if em_blackout and flat_news and pos != 0:
            fecha(b['c'], d)

        # avaliacao da conta
        pr = realized - r_ini
        ua = uf = 0.0
        if pos > 0: ua = (b['l'] - entry) * pv; uf = (b['h'] - entry) * pv
        elif pos < 0: ua = (entry - b['h']) * pv; uf = (entry - b['l']) * pv
        if pr + uf > pico: pico = pr + uf
        if STOP_DIA > 0 and (realized - pnl_d0 + ua) <= -STOP_DIA:
            block = True
            if pos != 0: fecha(b['c'], d)
        if pr + ua <= pico - DD:
            fecha(b['c'], d); reprov += 1; r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt
        elif pr >= META and len(dias) >= MIN_DIAS:
            fecha(b['c'], d); aprov += 1; d2a.append((dt - ini_aval).days)
            r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt

        # flatten EOD
        if m >= FLATTEN and pos != 0:
            fecha(b['c'], d)
        # entrada diurna (bloqueada em blackout de noticia)
        if not block and not em_blackout and pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
            niv_hi = seg_hoje[0] if seg_hoje else pd_hi
            niv_lo = seg_hoje[1] if seg_hoje else pd_lo
            if niv_hi is not None:
                tol = TOL_TICKS * TICK; h, l, c = b['h'], b['l'], b['c']; lado = 0
                if h >= niv_hi - tol and c < niv_hi:
                    if MAX_DIST == 0 or (niv_hi - c) <= MAX_DIST: lado = -1
                elif l <= niv_lo + tol and c > niv_lo:
                    if MAX_DIST == 0 or (c - niv_lo) <= MAX_DIST: lado = 1
                if lado != 0:
                    entry = c; pos = lado; fav = c; be_done = False
                    stop = c - lado * PTS_SL; target = c + lado * TP; dias.add(d)

    if pos != 0: fecha(bars[-1]['c'], dia)

    w = [t for t in trades if t > 0]; n = len(trades)
    gw = sum(w); gl = abs(sum(t for t in trades if t <= 0))
    tot = aprov + reprov; ds = sorted(d2a); med = ds[len(ds)//2] if ds else 0
    return {'n': n, 'wr': 100*len(w)/n if n else 0, 'pf': gw/gl if gl > 0 else 99,
            'net': sum(trades), 'aprov': aprov, 'reprov': reprov, 'tot': tot,
            'taxa': 100*aprov/tot if tot else 0, 'dmediana': med,
            'pnl_fomc': pnl_fomc, 'n_fomc': n_fomc}


def linha(label, r):
    print(f"  {label:>26s} {r['taxa']:>4.0f}% {r['aprov']:>3}/{r['tot']:<3} {r['dmediana']:>4.0f}d "
          f"{r['n']:>5} {r['wr']:>3.0f}% {r['pf']:>5.2f} {r['net']:>10,.0f}  "
          f"| FOMC: {r['n_fomc']:>2} trd ${r['pnl_fomc']:>8,.0f}")


if __name__ == '__main__':
    print("Carregando NQ 1-min real..."); bars = carregar('NQ_dados')
    dom = domingo_ranges(bars)
    print(f"{len(bars):,} barras | DIURNA only | slippage {SLIP_BASE:.0f} ticks (baseline realista)")
    print(f"FOMC no periodo: {len(FOMC_DATAS)} dias (anuncio 14h ET)\n")

    print("=" * 104)
    print("  NEWS FILTER (FOMC) — blackout +/- X min em torno das 14h ET nos dias de FOMC")
    print("=" * 104)
    print(f"  {'cenario':>26s} {'taxa':>5s} {'aprov':>7s} {'d.med':>5s} {'trds':>5s} "
          f"{'WR':>4s} {'PF':>5s} {'PnL$/ano':>10s}  | PnL isolado dos dias FOMC")
    print("-" * 104)

    r0 = bt(bars, dom, news_buffer=0)
    linha("SEM filtro (baseline)", r0)
    print("-" * 104)
    for buf in [10, 15, 30, 60]:
        r = bt(bars, dom, news_buffer=buf, flat_news=True)
        linha(f"blackout +/-{buf}min +flatten", r)
    print("=" * 104)

    print("\n  Comparacao direta (baseline vs melhor janela):")
    print(f"    SEM filtro : {r0['taxa']:.0f}% aprov, PF {r0['pf']:.2f}, ${r0['net']:,.0f}/ano | "
          f"dias FOMC: ${r0['pnl_fomc']:,.0f} em {r0['n_fomc']} trades")
    print("\n  Leitura: se o PnL dos dias de FOMC e NEGATIVO sem filtro e o filtro reduz a perda")
    print("  sem derrubar a taxa de aprovacao geral, vale ligar. Se o FOMC ja da lucro, nao mexer.")
