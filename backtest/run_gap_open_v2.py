#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Candidata C — gap-and-GO, REFINO (02/09, passo 1 da proxima sessao).

Probe v1 (run_gap_open.py): gap que segura 15 min -> a favor, 2:1, flat 13h ET =
PF ~1,29 IS 2022-25 / ~1,30 holdout 2026, mas: entrada tosca (no minuto 15),
risco = distancia ao extremo dos 15 min (pode ser enorme), maxDD -$6,5k.

Refinos testados aqui:
  ENTRADA: rompimento do opening range (OR = high/low dos 1os 15 min RTH), depois
           de confirmar que o gap SEGUROU (preco no minuto 15 do lado certo do
           prior close E do meio do OR).
  RISCO:   stop = outro lado do OR, mas CAPADO em X pts (ou X x ATR diario).
  NORM:    filtra o gap por gap/ATR(14d) em vez de pontos crus (robusto a nivel
           de preco: MNQ foi de 12k -> 29k no periodo).
  FILTROS: (a) gap a favor da tendencia do dia anterior (close-to-close);
           (b) dia da semana (2a feira = gap de fim de semana, testar separado);
           (c) dia tambem e' release 8h30? (usa detecta_eventos do run_event_830).
  GESTAO:  1 trade/dia, flat 13h ET. (DD control.)

IS 2022-2025, holdout 2026. Corte pra .cs: PF > 1,3 IS com custo+slippage, DD menor,
regra limpa. Juiz final = NT8 Strategy Analyzer.
"""
import os
import statistics as st
from collections import defaultdict

import run_event_830 as base

TICK = 0.25
PV = 2.0 * 5
RT = 1.30 * 5
OPEN = 9 * 60 + 30
OREND = OPEN + 15          # opening range = 9h30..9h44 (15 barras)
CLOSE = 16 * 60


def prep(bars):
    """por_dia + ATR14 diario (RTH) + retorno close-to-close do dia anterior."""
    pd = defaultdict(dict)
    for dt, o, h, l, c, v in bars:
        pd[dt.strftime("%Y-%m-%d")][dt.hour * 60 + dt.minute] = (o, h, l, c, v)

    dias = sorted(pd)
    rth_hi, rth_lo, rth_cl = {}, {}, {}
    for d in dias:
        m = pd[d]
        w = [m[k] for k in range(OPEN, CLOSE) if k in m]
        if not w:
            continue
        rth_hi[d] = max(x[1] for x in w)
        rth_lo[d] = min(x[2] for x in w)
        rth_cl[d] = w[-1][3]

    atr, ret_prev = {}, {}
    tr_hist = []
    for i, d in enumerate(dias):
        if d not in rth_hi:
            continue
        if i > 0 and dias[i - 1] in rth_cl:
            pc = rth_cl[dias[i - 1]]
            tr = max(rth_hi[d] - rth_lo[d], abs(rth_hi[d] - pc), abs(rth_lo[d] - pc))
        else:
            tr = rth_hi[d] - rth_lo[d]
        tr_hist.append((d, tr))
        if len(tr_hist) >= 14:
            atr[d] = st.mean(x[1] for x in tr_hist[-14:])
        if i >= 2 and dias[i - 1] in rth_cl and dias[i - 2] in rth_cl:
            ret_prev[d] = rth_cl[dias[i - 1]] - rth_cl[dias[i - 2]]
    return pd, dias, rth_cl, atr, ret_prev


def bt(pd, dias, rth_cl, atr, ret_prev, eventos,
       gapn_lo, gapn_hi, rr, cap_atr, slip_ticks=5,
       so_com_tendencia=False, dow=None, excl_evento=False, flat_min=13 * 60):
    slip = slip_ticks * TICK
    trades = []
    for i in range(1, len(dias)):
        d, dp = dias[i], dias[i - 1]
        if d not in atr or dp not in rth_cl:
            continue
        m = pd[d]
        bo = m.get(OPEN)
        if not bo:
            continue
        pc = rth_cl[dp]
        op = bo[0]
        gap = op - pc
        gapn = abs(gap) / atr[d]
        if not (gapn_lo <= gapn <= gapn_hi):
            continue
        if dow is not None:
            import datetime as _dt
            if _dt.date.fromisoformat(d).weekday() != dow:
                continue
        if excl_evento and d in eventos:
            continue
        if so_com_tendencia and d in ret_prev:
            if (gap > 0) != (ret_prev[d] > 0):
                continue

        orw = [m[k] for k in range(OPEN, OREND) if k in m]
        b15 = m.get(OREND)
        if len(orw) < 12 or not b15:
            continue
        orh = max(x[1] for x in orw)
        orl = min(x[2] for x in orw)
        ormid = (orh + orl) / 2

        # confirmacao: gap segurou (preco no min 15 do lado certo do pc E do mid)
        px15 = b15[3]
        if gap > 0:
            if not (px15 > pc and px15 > ormid):
                continue
            lado = 1
            trig = orh
        else:
            if not (px15 < pc and px15 < ormid):
                continue
            lado = -1
            trig = orl

        # entra no rompimento do OR (a partir do minuto 15)
        entry = None
        for k in range(OREND, flat_min + 1):
            b = m.get(k)
            if not b:
                continue
            if lado == 1 and b[1] >= trig:
                entry = max(trig, b[0]) + slip
                ke = k
                break
            if lado == -1 and b[2] <= trig:
                entry = min(trig, b[0]) - slip
                ke = k
                break
        if entry is None:
            continue

        risco = min(abs(entry - (orl if lado == 1 else orh)), cap_atr * atr[d])
        risco = max(risco, 5.0)
        stop = entry - lado * risco
        target = entry + lado * rr * risco

        saida = None
        for k in range(ke + 1, flat_min + 1):
            b = m.get(k)
            if not b:
                continue
            _, bh, bl, bc, _ = b
            if lado == 1:
                if bl <= stop:
                    saida = stop - slip
                    break
                if bh >= target:
                    saida = target - slip
                    break
            else:
                if bh >= stop:
                    saida = stop + slip
                    break
                if bl <= target:
                    saida = target + slip
                    break
        if saida is None:
            bf = m.get(flat_min) or m.get(flat_min - 1)
            saida = bf[3] if bf else entry
        trades.append((d, lado, ((saida - entry) * lado) * PV - RT, risco))
    return trades


def rep(lbl, tr):
    isr = base.stats([t for t in tr if t[0] < "2026"])
    oo = base.stats([t for t in tr if t[0] >= "2026"])
    if not isr or isr["n"] < 20:
        print(f"  {lbl:<46} n={isr['n'] if isr else 0} (amostra pequena)")
        return
    mk = "  <<<" if (isr["pf"] >= 1.3 and (not oo or oo["pf"] >= 1.1)) else ""
    o = f" | 26: PF {oo['pf']:.2f} ${oo['net']:,.0f} n{oo['n']}" if oo else ""
    print(f"  {lbl:<46} n{isr['n']:>4} WR{isr['wr']:>4.0f}% PF {isr['pf']:>4.2f} "
          f"net ${isr['net']:>8,.0f} avg ${isr['avg']:>5.0f} DD ${isr['mdd']:>7,.0f}{o}{mk}")


def porano(lbl, tr):
    d = defaultdict(list)
    for t in tr:
        d[t[0][:4]].append(t)
    print(f"  {lbl}")
    for a, v in sorted(d.items()):
        s = base.stats(v)
        print(f"    {a}: n{s['n']:>3} WR {s['wr']:>4.0f}% PF {s['pf']:>4.2f} "
              f"net ${s['net']:>8,.0f} avg ${s['avg']:>5.0f} maxDD ${s['mdd']:>8,.0f}")


if __name__ == "__main__":
    bars = base.carrega()
    eventos, _ = base.detecta_eventos(bars)
    pd, dias, rth_cl, atr, ret_prev = prep(bars)
    print(f"{len(dias)} dias | ATR14 em {len(atr)} | IS 2022-2025 / holdout 2026\n")

    A = dict(pd=pd, dias=dias, rth_cl=rth_cl, atr=atr, ret_prev=ret_prev, eventos=eventos)

    print("=== base: OR-breakout apos gap-hold, stop=OR capado, 1 trade/dia ===")
    for lo, hi in ((0.15, 0.6), (0.2, 0.8), (0.25, 1.0), (0.3, 1.2)):
        for rr in (1.5, 2.0, 3.0):
            for cap in (1.0, 1.5):
                rep(f"gapN {lo}-{hi} rr{rr} cap{cap}xATR",
                    bt(**A, gapn_lo=lo, gapn_hi=hi, rr=rr, cap_atr=cap))
    print()

    print("=== filtro: so gap A FAVOR da tendencia do dia anterior ===")
    for lo, hi in ((0.2, 0.8), (0.25, 1.0)):
        for rr in (2.0, 3.0):
            rep(f"gapN {lo}-{hi} rr{rr} cap1.5 +tend",
                bt(**A, gapn_lo=lo, gapn_hi=hi, rr=rr, cap_atr=1.5, so_com_tendencia=True))
    print()

    print("=== filtro: EXCLUI dias que sao release 8h30 ===")
    for lo, hi in ((0.2, 0.8), (0.25, 1.0)):
        for rr in (2.0, 3.0):
            rep(f"gapN {lo}-{hi} rr{rr} cap1.5 sem-evento",
                bt(**A, gapn_lo=lo, gapn_hi=hi, rr=rr, cap_atr=1.5, excl_evento=True))
    print()

    print("=== por dia da semana (gapN 0.2-0.8, rr2, cap1.5) ===")
    for wd, nm in enumerate(("2a", "3a", "4a", "5a", "6a")):
        rep(f"{nm}-feira", bt(**A, gapn_lo=0.2, gapn_hi=0.8, rr=2.0, cap_atr=1.5, dow=wd))
    print()

    # detalhe ano a ano das 2 configs mais promissoras
    porano("ANO A ANO — gapN 0.2-0.8 rr2 cap1.5 (base)",
           bt(**A, gapn_lo=0.2, gapn_hi=0.8, rr=2.0, cap_atr=1.5))
    print()
    porano("ANO A ANO — gapN 0.25-1.0 rr3 cap1.5 (base)",
           bt(**A, gapn_lo=0.25, gapn_hi=1.0, rr=3.0, cap_atr=1.5))
