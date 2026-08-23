#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compara trade a trade (mesma entrada) o efeito de baixar o gatilho de
breakeven de 3,75 pra 2,5pt — pra entender POR QUE o forward test dos
primeiros dias (01-04/06) mostrou ganhos menores, mesmo o backtest de 13
meses mostrando melhora agregada (+9,1pp). Resposta: são dois efeitos
opostos que acontecem em proporções bem diferentes — este script mede os
dois no dataset inteiro.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_estrategias_comparativo import (
    carregar, domingo_ranges, Estado, sinal_reversao,
    ENTRADA_INI, ENTRADA_FIM, FLATTEN, mins,
    MNQ_PV, RT_PER, N_CONTR, TICK, PTS_SL, TP, PTS_TRAIL, SLIP_BASE,
)

BE_LOCK_FRAC = 0.75


def coleta_trades(bars, dom, be_trig):
    pv = MNQ_PV * N_CONTR
    rt = RT_PER * N_CONTR
    slip = SLIP_BASE * TICK
    pos = 0
    entry = stop = target = 0.0
    fav = 0.0
    be_done = False
    trades = []
    st = Estado()

    for i, b in enumerate(bars):
        dt = b["dt"]
        m = mins(dt)
        d = dt.strftime("%Y-%m-%d")
        wd = dt.weekday()
        if d != st.dia:
            if st.cur_hi is not None:
                st.pd_hi, st.pd_lo = st.cur_hi, st.cur_lo
            st.dia = d
            st.cur_hi = st.cur_lo = None
            st.seg_hoje = dom[d] if (dom and wd == 0 and d in dom) else None
        if ENTRADA_INI <= m < 16 * 60:
            st.cur_hi = b["h"] if st.cur_hi is None else max(st.cur_hi, b["h"])
            st.cur_lo = b["l"] if st.cur_lo is None else min(st.cur_lo, b["l"])

        if pos != 0:
            saiu = False
            if pos > 0:
                if b["l"] <= stop:
                    trades.append({"dt": entry_dt, "entry": entry, "pnl": ((stop - entry) * pos - 2 * slip) * pv - rt, "mfe": fav - entry}); pos = 0; saiu = True
                elif b["h"] >= target:
                    trades.append({"dt": entry_dt, "entry": entry, "pnl": ((target - entry) * pos - 2 * slip) * pv - rt, "mfe": fav - entry}); pos = 0; saiu = True
            else:
                if b["h"] >= stop:
                    trades.append({"dt": entry_dt, "entry": entry, "pnl": ((stop - entry) * pos - 2 * slip) * pv - rt, "mfe": entry - fav}); pos = 0; saiu = True
                elif b["l"] <= target:
                    trades.append({"dt": entry_dt, "entry": entry, "pnl": ((target - entry) * pos - 2 * slip) * pv - rt, "mfe": entry - fav}); pos = 0; saiu = True
            if not saiu and pos != 0:
                if pos > 0:
                    fav = max(fav, b["h"])
                    if not be_done and (fav - entry) >= be_trig:
                        be_done = True; stop = max(stop, entry + (fav - entry) * BE_LOCK_FRAC)
                    if be_done:
                        lock = (fav - entry) * BE_LOCK_FRAC
                        stop = max(stop, max(entry + lock, fav - PTS_TRAIL))
                else:
                    fav = min(fav, b["l"])
                    if not be_done and (entry - fav) >= be_trig:
                        be_done = True; stop = min(stop, entry - (entry - fav) * BE_LOCK_FRAC)
                    if be_done:
                        lock = (entry - fav) * BE_LOCK_FRAC
                        stop = min(stop, min(entry - lock, fav + PTS_TRAIL))

        if m >= FLATTEN and pos != 0:
            mfe = (fav - entry) if pos > 0 else (entry - fav)
            trades.append({"dt": entry_dt, "entry": entry, "pnl": ((b["c"] - entry) * pos - 2 * slip) * pv - rt, "mfe": mfe})
            pos = 0

        if pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
            lado = sinal_reversao(bars, i, st, dom)
            if lado != 0:
                entry = b["c"]; pos = lado; fav = entry; be_done = False; entry_dt = dt
                stop = entry - lado * PTS_SL; target = entry + lado * TP

    return trades


def main():
    print("Carregando NQ 1-min real...")
    bars = carregar("NQ_dados")
    dom = domingo_ranges(bars)

    print("Coletando trades com BE trig 3,75 (config atual)...")
    t375 = coleta_trades(bars, dom, be_trig=3.75)
    print("Coletando trades com BE trig 2,5 (novo)...")
    t250 = coleta_trades(bars, dom, be_trig=2.5)

    # casa por (data+hora de entrada, preco de entrada) -- mesmos sinais, mesma sequencia
    # ate a primeira divergencia; a partir dai os dois trilhos podem descolar (mesmo
    # fenomeno ja visto no forward test manual: mudar a saida de um trade libera o bot
    # pra reentrar num horario diferente).
    m375 = {(t["dt"], round(t["entry"], 2)): t for t in t375}
    m250 = {(t["dt"], round(t["entry"], 2)): t for t in t250}
    chaves_comuns = sorted(set(m375) & set(m250))

    print(f"\n{len(t375)} trades (BE 3,75) | {len(t250)} trades (BE 2,5) | "
          f"{len(chaves_comuns)} pareados exatamente (mesma entrada)\n")

    ajudou = []   # loss grande no 3,75 virou ganho/perda pequena no 2,5
    atrapalhou = []  # ganho grande no 3,75 virou ganho menor no 2,5
    neutro = 0

    for k in chaves_comuns:
        a = m375[k]["pnl"]; b = m250[k]["pnl"]
        delta = b - a
        if abs(delta) < 1:
            neutro += 1
        elif b > a:
            ajudou.append((a, b, delta))
        else:
            atrapalhou.append((a, b, delta))

    print(f"  Trades idênticos (Δ<$1):        {neutro}")
    print(f"  Trades que MELHORARAM com 2,5:  {len(ajudou):>4}  |  Δ médio +${sum(d for _,_,d in ajudou)/len(ajudou):.1f}  |  soma +${sum(d for _,_,d in ajudou):.0f}" if ajudou else "  Trades que MELHORARAM com 2,5:     0")
    print(f"  Trades que PIORARAM com 2,5:    {len(atrapalhou):>4}  |  Δ médio ${sum(d for _,_,d in atrapalhou)/len(atrapalhou):.1f}  |  soma ${sum(d for _,_,d in atrapalhou):.0f}" if atrapalhou else "  Trades que PIORARAM com 2,5:       0")
    print(f"\n  Δ líquido total (trades pareados): ${sum(d for _,_,d in ajudou)+sum(d for _,_,d in atrapalhou):.0f}")

    print("\n  --- Top 5 casos que MAIS ajudaram (loss grande virou pequeno/ganho) ---")
    for a, b, d in sorted(ajudou, key=lambda x: -x[2])[:5]:
        print(f"    BE 3,75: ${a:>7.1f}  ->  BE 2,5: ${b:>7.1f}   (Δ +${d:.1f})")

    print("\n  --- Top 5 casos que MAIS atrapalharam (ganho cortado cedo) ---")
    for a, b, d in sorted(atrapalhou, key=lambda x: x[2])[:5]:
        print(f"    BE 3,75: ${a:>7.1f}  ->  BE 2,5: ${b:>7.1f}   (Δ ${d:.1f})")


if __name__ == "__main__":
    main()
