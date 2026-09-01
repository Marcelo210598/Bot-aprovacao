#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PREVIEW do que o Tick Replay vai mostrar (auditoria 01/09, Fase 0 item 2).

Nao temos tick real do periodo. Aqui: simula o CAMINHO INTRABAR de cada barra de
1min com uma PONTE BROWNIANA restrita (comeca no open, termina no close, e OBRIGA
a tocar o high e o low da barra) + ruido. Sobre esse caminho, gere a saida TICK A
TICK (como o OnMarketData faz ao vivo). Monte Carlo: N caminhos por barra.

Compara:
  [BAR]  = gestao OnBarClose (1 checagem por barra) = o backtest oficial do projeto
  [TICK] = gestao tick a tick sobre a ponte browniana = aproximacao do ao vivo

Se no [TICK] o avgW despencar (~$95 -> ~$31, como no forward test de julho), a
hipotese central da auditoria esta certa. E o sweep de trailing mostra qual
largura sobrevive ao ruido tick-level.
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(__file__))
from run_estrategias_comparativo import (
    carregar, domingo_ranges, Estado, sinal_reversao,
    MNQ_PV, RT_PER, TICK, PTS_SL, TP, ENTRADA_INI, ENTRADA_FIM, FLATTEN, SLIP_BASE, mins,
)
import statistics as st

random.seed(42)
NPATH = 6          # caminhos Monte Carlo por barra em posicao
NSTEPS = 40        # 'ticks' por barra de 1min


def bridge(o, h, l, c, n=NSTEPS):
    """ponte browniana o->c que toca h e l, ~n passos. Ruido proporcional ao range."""
    rng = max(h - l, TICK)
    # random walk
    w = [0.0]
    for _ in range(n):
        w.append(w[-1] + random.gauss(0, 1))
    # ponte: remove a tendencia p/ terminar em 0
    w = [w[i] - w[-1]*i/n for i in range(n+1)]
    sd = st.pstdev(w) or 1.0
    amp = rng * 0.42
    path = [o + (c - o)*i/n + w[i]/sd*amp for i in range(n+1)]
    path[0] = o; path[-1] = c
    # força tocar h e l: injeta nos indices do min/max atual
    imax = max(range(n+1), key=lambda i: path[i])
    imin = min(range(n+1), key=lambda i: path[i])
    path[imax] = h; path[imin] = l
    return path


def bt(bars, dom, motor, TRAIL, BETRIG=2.5, BELOCK_FRAC=0.75, MAXD=20.0, n_contr=5):
    pv = MNQ_PV*n_contr; rt = RT_PER*n_contr; slip = SLIP_BASE*TICK
    pos = 0; entry = stop = tgt = fav = 0.0; be = False
    st_ = Estado(); trades = []; wmfe = []

    def close_trade(p):
        nonlocal pos
        g = ((p-entry)*pos - 2*slip)*pv - rt
        trades.append(g)
        if g > 0: wmfe.append((fav-entry)*pos)
        pos = 0

    for i, b in enumerate(bars):
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d'); wd = dt.weekday()
        if d != st_.dia:
            if st_.cur_hi is not None: st_.pd_hi, st_.pd_lo = st_.cur_hi, st_.cur_lo
            st_.dia = d; st_.cur_hi = st_.cur_lo = None
            st_.seg_hoje = dom[d] if (dom and wd == 0 and d in dom) else None
        if ENTRADA_INI <= m < 16*60:
            st_.cur_hi = b['h'] if st_.cur_hi is None else max(st_.cur_hi, b['h'])
            st_.cur_lo = b['l'] if st_.cur_lo is None else min(st_.cur_lo, b['l'])

        if pos != 0:
            def manage(px):
                nonlocal be, stop
                if pos > 0:
                    if px > fav: return px
                else:
                    if px < fav: return px
                return fav
            if motor == 'bar':
                # checa contra low/high da barra (stop antigo), depois trilha
                hit = None
                if pos > 0:
                    if b['l'] <= stop: hit = stop
                    elif b['h'] >= tgt: hit = tgt
                else:
                    if b['h'] >= stop: hit = stop
                    elif b['l'] <= tgt: hit = tgt
                if hit is not None:
                    close_trade(hit)
                else:
                    if pos > 0:
                        fav = max(fav, b['h'])
                        if not be and (fav-entry) >= BETRIG: be = True
                        if be: stop = max(stop, entry+(fav-entry)*BELOCK_FRAC, fav-TRAIL)
                    else:
                        fav = min(fav, b['l'])
                        if not be and (entry-fav) >= BETRIG: be = True
                        if be: stop = min(stop, entry-(entry-fav)*BELOCK_FRAC, fav+TRAIL)
            else:
                # tick: media de NPATH caminhos brownianos
                outs = []
                for _ in range(NPATH):
                    p = bridge(b['o'], b['h'], b['l'], b['c'])
                    lf, lb, lst = fav, be, stop; sim_pos = pos; res = None
                    for px in p:
                        if sim_pos > 0:
                            if px <= lst: res = lst; break
                            if px >= tgt: res = tgt; break
                            if px > lf:
                                lf = px
                                if not lb and (lf-entry) >= BETRIG: lb = True
                                if lb: lst = max(lst, entry+(lf-entry)*BELOCK_FRAC, lf-TRAIL)
                        else:
                            if px >= lst: res = lst; break
                            if px <= tgt: res = tgt; break
                            if px < lf:
                                lf = px
                                if not lb and (entry-lf) >= BETRIG: lb = True
                                if lb: lst = min(lst, entry-(entry-lf)*BELOCK_FRAC, lf+TRAIL)
                    if res is None: res = b['c']
                    outs.append((res, lf, lb))
                # resultado medio dos caminhos
                exit_px = st.mean(o[0] for o in outs)
                fav = st.mean(o[1] for o in outs)
                be = sum(1 for o in outs if o[2]) > NPATH//2
                # 'saiu' se a maioria dos caminhos saiu antes do close
                saiu_maioria = sum(1 for o in outs if abs(o[0]-b['c']) > TICK) > NPATH//2
                if saiu_maioria or m >= FLATTEN:
                    close_trade(exit_px)

        if pos != 0 and m >= FLATTEN:
            close_trade(b['c'])
        if pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
            lado = sinal_reversao(bars, i, st_, dom)
            if lado != 0:
                entry = b['c']; pos = lado; fav = entry; be = False
                stop = entry - lado*PTS_SL; tgt = entry + lado*TP

    n = len(trades); w = [x for x in trades if x > 0]
    gw = sum(w); gl = abs(sum(x for x in trades if x <= 0))
    return dict(n=n, wr=100*len(w)/n if n else 0, pf=gw/gl if gl else 99,
               net=sum(trades), aw=st.mean(w) if w else 0,
               al=st.mean([x for x in trades if x <= 0]) if n-len(w) else 0,
               wmfe=st.mean(wmfe) if wmfe else 0)


if __name__ == '__main__':
    bars = carregar('NQ_dados'); dom = domingo_ranges(bars)
    print(f"{len(bars):,} barras NQ 1min | reversao PDH/PDL, BE 2,5, BE-lock 0,75, SL 12,5")
    print(f"ponte browniana: {NPATH} caminhos x {NSTEPS} passos por barra\n")
    print(f"  {'cenario':<32s} {'n':>5s} {'WR':>4s} {'PF':>5s} {'net$':>9s} {'avgW':>7s} {'avgL':>8s} {'MFE_W':>6s}")
    print("-"*90)
    print("  [BAR] OnBarClose (= backtest oficial):")
    for tr in (1.75, 3.0, 5.0):
        r = bt(bars, dom, 'bar', tr)
        print(f"    trail {tr:>4.2f}pt                    {r['n']:>5} {r['wr']:>3.0f}% {r['pf']:>5.2f} "
              f"{r['net']:>+9,.0f} {r['aw']:>+7.0f} {r['al']:>+8.0f} {r['wmfe']:>5.1f}pt")
    print("\n  [TICK] ponte browniana (= aproximacao do ao vivo / Tick Replay):")
    for tr in (1.75, 3.0, 5.0, 8.0, 12.0):
        r = bt(bars, dom, 'tick', tr)
        print(f"    trail {tr:>4.2f}pt                    {r['n']:>5} {r['wr']:>3.0f}% {r['pf']:>5.2f} "
              f"{r['net']:>+9,.0f} {r['aw']:>+7.0f} {r['al']:>+8.0f} {r['wmfe']:>5.1f}pt")
    print("\n  REFERENCIA forward julho: WR 45%, PF 0.44, avgW +$31, avgL -$58 (só stop cheio -$143)")
    print("  LEITURA: se [TICK] com trail 1,75 der avgW ~$30-40 (vs [BAR] ~$80), a hipotese da")
    print("  auditoria bate. Se afrouxar (5-8pt) recuperar o avgW/PF no [TICK], essa e' a direcao.")
