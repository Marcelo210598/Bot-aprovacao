#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GESTAO DE SAIDA — GANHO + PERDA (20/08) — pedido do Marcelo: parar de focar so
em filtro de entrada (sexta/dist_nivel ja descartados) e atacar os dois lados
do payoff direto na gestao da posicao:

  (A) SUBIR O GANHO: saida parcial (4+1) com alvo MENOR que os 20pt do
      experimento anterior (que NUNCA disparou em ~20 dias de Replay real --
      o MFE mediano dos vencedores no backtest e' 12,5pt, entao um alvo de
      20pt e' raro demais). Testa 5/8/10/12,5/15/20pt, SEMPRE com o BE-lock
      proporcional 0,75 ja validado (Delta +$122,5 confirmado em Replay).

  (B) DIMINUIR A PERDA: ideia NOVA, ainda nao testada -- corta parte da
      posicao (2 de 5) se o preco for contra em X pontos SEM NUNCA ter
      favorecido o suficiente pra ativar o breakeven. Reduz o tamanho em $
      dos "loss cheios imediatos" sem mexer no stop dos trades que ja
      mostraram algum sinal de vida (que hoje ficam protegidos pelo BE-lock).

Motor: mesmo bar-lag de producao (DD real $1000, MaxTradesDia=12, slippage 2
ticks, nivel de domingo), igual aos sweeps anteriores. Cada mecanismo testado
ISOLADO primeiro (nao combinar sem entender o efeito de cada um separado).
"""
import glob, os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
MNQ_PV = 2.0; RT_PER = 1.20
MIN_DIAS = 7
TICK = 0.25
PTS_SL = 12.5; PTS_BE_TRIG = 3.75; PTS_BE_LOCK = 2.5; PTS_TRAIL = 1.75
TOL_TICKS = 20; TP = 60.0; MAX_DIST = 15.0
ENTRADA_INI = 9*60+30; ENTRADA_FIM = 16*60; FLATTEN = 16*60+55
SLIP_BASE = 2.0
CONTR_BASE = 5


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


def bt(bars, dom_map=None, meta=1500.0, dd=1000.0, stop_dia=750.0, max_trades=12,
       slip_ticks=SLIP_BASE, be_lock_frac=None,
       parcial_pts=None, parcial_qtd=4,
       loss_cut_pts=None, loss_cut_qtd=2):
    """
    be_lock_frac: None = lock fixo (BreakevenLockPontos=2,5, comportamento original).
                  0.75 = lock proporcional ja validado (auditoria 18-19/08).
    parcial_pts: None = sem saida parcial. X = fecha parcial_qtd contratos ao
                 atingir +X pt a favor (resto segue pro alvo/trailing normal).
    loss_cut_pts: None = sem corte de perda. X = fecha loss_cut_qtd contratos
                  se o preco for contra em X pt ANTES do BE ter ativado (preco
                  nunca favoreceu o suficiente). Resto segue pro stop normal.
    """
    slip = slip_ticks * TICK
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False
    qtd_atual = 0; parcial_feita = False; loss_cut_feita = False
    realized = 0.0; trades = []
    pd_hi = pd_lo = None; cur_hi = cur_lo = None; dia = None
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None
    aprov = reprov = 0; d2a = []; pnl_d0 = 0.0; block = False; dia_k = None
    seg_hoje = None; trades_hoje = 0
    n_parciais = 0; n_loss_cuts = 0

    for b in bars:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d'); wd = dt.weekday()

        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = cur_lo = None
            seg_hoje = dom_map[d] if (dom_map and wd == 0 and d in dom_map) else None
        if ENTRADA_INI <= m < 16*60:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
        if d != dia_k:
            dia_k = d; pnl_d0 = realized; block = False; trades_hoje = 0
        if ini_aval is None: ini_aval = dt

        pos_sign = 1 if pos > 0 else (-1 if pos < 0 else 0)

        def fecha_full(p):
            nonlocal pos, realized, qtd_atual
            if pos == 0 or qtd_atual == 0: return
            pv = MNQ_PV * qtd_atual; rt = RT_PER * qtd_atual
            g = ((p - entry) * pos_sign - 2 * slip) * pv - rt
            realized += g; trades.append(g)
            cycle_days[d] = cycle_days.get(d, 0.0) + g
            pos = 0; qtd_atual = 0

        def fecha_parcial(qtd, p):
            nonlocal realized, qtd_atual
            if qtd <= 0 or qtd_atual < qtd: return
            pv = MNQ_PV * qtd; rt = RT_PER * qtd
            g = ((p - entry) * pos_sign - 2 * slip) * pv - rt
            realized += g; trades.append(g)
            cycle_days[d] = cycle_days.get(d, 0.0) + g
            qtd_atual -= qtd

        if pos != 0:
            saiu = False
            # 1) alvo/stop cheio no que restou da posicao
            if pos > 0:
                if b['l'] <= stop: fecha_full(stop); saiu = True
                elif b['h'] >= target: fecha_full(target); saiu = True
            else:
                if b['h'] >= stop: fecha_full(stop); saiu = True
                elif b['l'] <= target: fecha_full(target); saiu = True

            # 2) saida parcial (lado do GANHO) -- so 1x por trade, so se ainda nao fechou tudo
            if not saiu and pos != 0 and parcial_pts and not parcial_feita and qtd_atual > parcial_qtd:
                alvo_parcial = entry + pos_sign * parcial_pts
                tocou = (pos > 0 and b['h'] >= alvo_parcial) or (pos < 0 and b['l'] <= alvo_parcial)
                if tocou:
                    parcial_feita = True; n_parciais += 1
                    fecha_parcial(parcial_qtd, alvo_parcial)

            # 3) corte de PERDA (lado ruim) -- so 1x por trade, so ANTES do BE ativar,
            #    so se ainda nao fechou tudo por stop/alvo nesta barra
            if not saiu and pos != 0 and loss_cut_pts and not loss_cut_feita and not be_done and qtd_atual > loss_cut_qtd:
                preco_corte = entry - pos_sign * loss_cut_pts
                tocou = (pos > 0 and b['l'] <= preco_corte) or (pos < 0 and b['h'] >= preco_corte)
                if tocou:
                    loss_cut_feita = True; n_loss_cuts += 1
                    fecha_parcial(loss_cut_qtd, preco_corte)

            # 4) atualiza fav/BE/trailing (vale a partir da proxima barra), so se ainda tem posicao
            if pos != 0:
                if pos > 0:
                    fav = max(fav, b['h'])
                    if not be_done and (fav - entry) >= PTS_BE_TRIG:
                        be_done = True
                        lock = (fav - entry) * be_lock_frac if be_lock_frac else PTS_BE_LOCK
                        stop = max(stop, entry + lock)
                    if be_done:
                        lock = (fav - entry) * be_lock_frac if be_lock_frac else PTS_BE_LOCK
                        stop = max(stop, max(entry + lock, fav - PTS_TRAIL))
                else:
                    fav = min(fav, b['l'])
                    if not be_done and (entry - fav) >= PTS_BE_TRIG:
                        be_done = True
                        lock = (entry - fav) * be_lock_frac if be_lock_frac else PTS_BE_LOCK
                        stop = min(stop, entry - lock)
                    if be_done:
                        lock = (entry - fav) * be_lock_frac if be_lock_frac else PTS_BE_LOCK
                        stop = min(stop, min(entry - lock, fav + PTS_TRAIL))

        pr = realized - r_ini
        ua = uf = 0.0
        if pos > 0: ua = (b['l']-entry)*MNQ_PV*qtd_atual; uf = (b['h']-entry)*MNQ_PV*qtd_atual
        elif pos < 0: ua = (entry-b['h'])*MNQ_PV*qtd_atual; uf = (entry-b['l'])*MNQ_PV*qtd_atual
        if pr + uf > pico: pico = pr + uf
        if stop_dia > 0 and (realized - pnl_d0 + ua) <= -stop_dia:
            block = True
            if pos != 0: fecha_full(b['c'])
        if pr + ua <= pico - dd:
            fecha_full(b['c']); reprov += 1
            r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt; cycle_days.clear()
        elif pr >= meta and len(dias) >= MIN_DIAS:
            fecha_full(b['c']); aprov += 1
            d2a.append((dt - ini_aval).days)
            r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt; cycle_days.clear()

        if m >= FLATTEN and pos != 0:
            fecha_full(b['c'])
        lim_ok = (max_trades == 0 or trades_hoje < max_trades)
        if not block and lim_ok and pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
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
                    qtd_atual = CONTR_BASE; parcial_feita = False; loss_cut_feita = False
                    stop = c - lado * PTS_SL; target = c + lado * TP
                    dias.add(d); trades_hoje += 1

    if pos != 0:
        pos_sign = 1 if pos > 0 else -1
        pv = MNQ_PV * qtd_atual; rt = RT_PER * qtd_atual
        g = ((bars[-1]['c'] - entry) * pos_sign - 2 * slip) * pv - rt
        realized += g; trades.append(g)

    w = [t for t in trades if t > 0]; n = len(trades)
    gw = sum(w); gl = abs(sum(t for t in trades if t <= 0))
    tot = aprov + reprov; ds = sorted(d2a); med = ds[len(ds)//2] if ds else 0
    avgw = gw/len(w) if w else 0; l_ = [t for t in trades if t <= 0]
    avgl = gl/len(l_) if l_ else 0
    return {'n': n, 'wr': 100*len(w)/n if n else 0, 'pf': gw/gl if gl > 0 else 99,
            'net': sum(trades), 'aprov': aprov, 'reprov': reprov, 'tot': tot,
            'taxa': 100*aprov/tot if tot else 0, 'dmediana': med,
            'avgw': avgw, 'avgl': avgl, 'n_parciais': n_parciais, 'n_loss_cuts': n_loss_cuts}


# cycle_days precisa existir no escopo do modulo p/ as closures acima; recriamos por chamada
cycle_days = {}
_bt_orig = bt
def bt(*args, **kwargs):
    global cycle_days
    cycle_days = {}
    return _bt_orig(*args, **kwargs)


def linha(label, r):
    print(f"  {label:>28s} {r['taxa']:>4.0f}% {r['aprov']:>3}/{r['tot']:<3} {r['dmediana']:>4.0f}d "
          f"{r['n']:>5} {r['wr']:>3.0f}% {r['pf']:>5.2f} avgW{r['avgw']:>7,.0f} avgL{r['avgl']:>7,.0f} {r['net']:>9,.0f}")


if __name__ == '__main__':
    print("Carregando NQ 1-min real..."); bars = carregar('NQ_dados')
    dom = domingo_ranges(bars)
    meio = bars[len(bars)//2]['dt']
    b1 = [b for b in bars if b['dt'] < meio]; b2 = [b for b in bars if b['dt'] >= meio]
    dom1 = domingo_ranges(b1); dom2 = domingo_ranges(b2)
    print(f"{len(bars):,} barras | DD real $1000 | MaxTradesDia=12 | 5 MNQ\n")
    H = f"  {'cenario':>28s} {'taxa':>5s} {'aprov':>7s} {'d.med':>5s} {'trds':>5s} {'WR':>4s} {'PF':>5s} {'avgW':>8s} {'avgL':>8s} {'PnL$':>9s}"

    print("=" * 105)
    print("  (A) SUBIR O GANHO -- alvo da parcial 4+1, SEMPRE com BE-lock 0,75")
    print("=" * 105); print(H); print("-" * 105)
    linha("baseline puro (sem nada)", bt(bars, dom))
    linha("so BE-lock 0,75 (ja validado)", bt(bars, dom, be_lock_frac=0.75))
    for pp in [5.0, 8.0, 10.0, 12.5, 15.0, 20.0]:
        linha(f"BE0,75 + parcial@{pp:g}pt", bt(bars, dom, be_lock_frac=0.75, parcial_pts=pp))
    print("=" * 105 + "\n")

    print("=" * 105)
    print("  (B) DIMINUIR A PERDA -- corte de 2 contratos se for contra sem nunca ter favorecido")
    print("=" * 105); print(H); print("-" * 105)
    linha("baseline puro (sem nada)", bt(bars, dom))
    for lp in [4.0, 6.0, 8.0, 10.0]:
        linha(f"loss-cut@{lp:g}pt (2 de 5)", bt(bars, dom, loss_cut_pts=lp, loss_cut_qtd=2))
    print("=" * 105 + "\n")

    print("=" * 105)
    print("  OOS (1a metade x 2a metade) -- baseline + as configs mais promissoras de cada lado")
    print("=" * 105)
    def oos(label, **kw):
        r1 = bt(b1, dom1, **kw); r2 = bt(b2, dom2, **kw)
        print(f"  {label:>28s}  1a: {r1['aprov']:>2}/{r1['tot']:<3}({r1['taxa']:>3.0f}%) PF{r1['pf']:>5.2f} "
              f"med{r1['dmediana']:>3.0f}d   2a: {r2['aprov']:>2}/{r2['tot']:<3}({r2['taxa']:>3.0f}%) PF{r2['pf']:>5.2f} med{r2['dmediana']:>3.0f}d")
    oos("baseline puro")
    oos("so BE-lock 0,75", be_lock_frac=0.75)
    oos("BE0,75 + parcial@8pt", be_lock_frac=0.75, parcial_pts=8.0)
    oos("BE0,75 + parcial@10pt", be_lock_frac=0.75, parcial_pts=10.0)
    oos("BE0,75 + parcial@12,5pt", be_lock_frac=0.75, parcial_pts=12.5)
    oos("loss-cut@6pt", loss_cut_pts=6.0, loss_cut_qtd=2)
    oos("loss-cut@8pt", loss_cut_pts=8.0, loss_cut_qtd=2)
    print("=" * 105)
