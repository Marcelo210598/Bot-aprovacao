#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Testa #3 (mitigação do gap de entrada) e #4 (gatilho de breakeven mais baixo)
propostos pelo Marcelo pro BotAprovacao.cs — TUDO em backtest Python, SEM
tocar em nenhum .cs. Decisão de fazer cópia experimental vem DEPOIS de ver
os números aqui.

#4 usa o motor OFICIAL já validado (`run_janela_30d.py`, o mesmo que bate os
50% documentados) — só varia PTS_BE_TRIG (o valor de gatilho do breakeven).
Comparável direto com o baseline conhecido.

#3 (gap de entrada) PRECISA de um motor diferente: o motor oficial preenche
a entrada no CLOSE da própria barra do sinal — ou seja, ele não tem gap
nenhum representado, e por isso não serve pra testar mitigação de gap. Fill
realista = na ABERTURA DA BARRA SEGUINTE (o que o BotAprovacao.cs realmente
faz: Calculate=OnBarClose, ordem a mercado enviada no fechamento, enche no
próximo tick == abertura da barra seguinte). Escrevi um motor específico pra
isso (`roda_motor_gap`), com o MESMO acompanhamento de drawdown intrabar do
motor oficial (não cometo de novo o erro de agregar por dia). Os números da
Parte 3 (#3) NÃO são comparáveis com os 50% oficiais — comparam só ENTRE os
cenários desta seção (baseline-com-gap vs. as 2 mitigações).

Uso:
    python3 backtest/testa_gap_e_be_trigger.py

Zero custo de API — só backtest local.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_janela_30d as rj30
from run_janela_30d import roda_janela_30d, JANELA_DIAS
from run_estrategias_comparativo import (
    carregar, domingo_ranges, Estado, sinal_reversao,
    ENTRADA_INI, ENTRADA_FIM, FLATTEN, mins,
    MNQ_PV, RT_PER, N_CONTR, TICK, PTS_SL, TP, PTS_TRAIL, SLIP_BASE,
    META, DD, MIN_DIAS,
)

BE_LOCK_FRAC = 0.75  # config atual em produção-candidata (BotAprovacao_SaidaParcial.cs)


def resume(label, resultados):
    tot = len(resultados)
    n_ap = sum(1 for r in resultados if r["status"] == "APROVOU")
    n_es = sum(1 for r in resultados if r["status"] == "ESTOUROU")
    n_ex = sum(1 for r in resultados if r["status"] == "EXPIROU")
    taxa = 100 * n_ap / tot if tot else 0
    print(f"  {label:>34s} {tot:>10} {n_ap:>8} {n_es:>9} {n_ex:>8} {taxa:>5.1f}%")
    return taxa


# ===========================================================================
# #4 — gatilho de breakeven mais baixo (motor OFICIAL, sem mudança nenhuma
# de metodologia — só monkeypatcha PTS_BE_TRIG antes de chamar)
# ===========================================================================
def testa_be_trigger(bars, dom):
    print("=== #4 — Gatilho de breakeven (motor OFICIAL, comparável aos 50% conhecidos) ===\n")
    print(f"  {'gatilho BE':>34s} {'tentativas':>10s} {'aprovou':>8s} {'estourou':>9s} {'expirou':>8s} {'taxa':>6s}")
    print("-" * 90)
    original = rj30.PTS_BE_TRIG
    try:
        for trig in [3.75, 3.0, 2.5]:
            rj30.PTS_BE_TRIG = trig
            res = roda_janela_30d(bars, dom, ["REV"], ind=None, be_lock_frac=BE_LOCK_FRAC)
            label = f"BE trig {trig}pt" + (" (atual)" if trig == 3.75 else "")
            resume(label, res)
    finally:
        rj30.PTS_BE_TRIG = original
    print()


# ===========================================================================
# #3 — mitigação do gap de entrada (motor PRÓPRIO, fill na abertura da
# barra seguinte — com acompanhamento de drawdown intrabar de verdade)
# ===========================================================================
def roda_motor_gap(bars, dom_map, modo="baseline", gap_max=None):
    """modo: 'baseline' (fill sempre no open da barra seguinte, sem filtro
    nenhum — é o que o bot faz hoje) | 'rejeita_gap' (pula o trade se o gap
    contra o sinal for maior que gap_max pontos) | 'limit' (só entra se a
    barra seguinte voltar até o preço de fechamento do sinal; senão, trade
    perdido - oportunidade não capturada, sem custo de gap ruim)."""
    pv = MNQ_PV * N_CONTR
    rt = RT_PER * N_CONTR
    slip = SLIP_BASE * TICK
    pos = 0
    entry = stop = target = 0.0
    fav = 0.0
    be_done = False
    realized = 0.0
    r_ini = 0.0
    pico = 0.0
    dias = set()
    ini_aval = None
    st = Estado()
    resultados = []
    pendente = None
    n_rejeitados_gap = 0
    n_perdidos_limit = 0

    def nova_tentativa(dt):
        nonlocal r_ini, pico, ini_aval, dias
        r_ini = realized; pico = 0.0; ini_aval = dt; dias = set()

    def fecha(p):
        nonlocal pos, realized
        if pos == 0:
            return
        realized += ((p - entry) * pos - 2 * slip) * pv - rt
        pos = 0

    for i, b in enumerate(bars):
        dt = b["dt"]; m = mins(dt); d = dt.strftime("%Y-%m-%d"); wd = dt.weekday()
        if ini_aval is None:
            nova_tentativa(dt)
        if d != st.dia:
            if st.cur_hi is not None:
                st.pd_hi, st.pd_lo = st.cur_hi, st.cur_lo
            st.dia = d; st.cur_hi = st.cur_lo = None
            st.seg_hoje = dom_map[d] if (dom_map and wd == 0 and d in dom_map) else None
        if ENTRADA_INI <= m < 16 * 60:
            st.cur_hi = b["h"] if st.cur_hi is None else max(st.cur_hi, b["h"])
            st.cur_lo = b["l"] if st.cur_lo is None else min(st.cur_lo, b["l"])

        # 1) resolve sinal pendente da barra anterior NESTA barra (= "abertura da barra seguinte")
        if pendente is not None and pos == 0:
            lado = pendente["lado"]; c_sinal = pendente["c_sinal"]
            gap_contra = (c_sinal - b["o"]) if lado > 0 else (b["o"] - c_sinal)  # >0 = gap ruim
            entra = True
            preco_fill = b["o"]
            if modo == "rejeita_gap" and gap_contra > gap_max:
                entra = False; n_rejeitados_gap += 1
            elif modo == "limit":
                if lado > 0:
                    if b["l"] <= c_sinal: preco_fill = c_sinal
                    else: entra = False; n_perdidos_limit += 1
                else:
                    if b["h"] >= c_sinal: preco_fill = c_sinal
                    else: entra = False; n_perdidos_limit += 1
            if entra:
                entry = preco_fill; pos = lado; fav = entry; be_done = False
                stop = entry - lado * PTS_SL; target = entry + lado * TP
                dias.add(d)
            pendente = None

        # 2) gestão normal de posição aberta (SL/TP/BE-lock 0,75/trailing)
        if pos != 0:
            saiu = False
            if pos > 0:
                if b["l"] <= stop: fecha(stop); saiu = True
                elif b["h"] >= target: fecha(target); saiu = True
            else:
                if b["h"] >= stop: fecha(stop); saiu = True
                elif b["l"] <= target: fecha(target); saiu = True
            if not saiu and pos != 0:
                if pos > 0:
                    fav = max(fav, b["h"])
                    if not be_done and (fav - entry) >= 3.75:
                        be_done = True; stop = max(stop, entry + (fav - entry) * BE_LOCK_FRAC)
                    if be_done:
                        lock = (fav - entry) * BE_LOCK_FRAC
                        stop = max(stop, max(entry + lock, fav - PTS_TRAIL))
                else:
                    fav = min(fav, b["l"])
                    if not be_done and (entry - fav) >= 3.75:
                        be_done = True; stop = min(stop, entry - (entry - fav) * BE_LOCK_FRAC)
                    if be_done:
                        lock = (entry - fav) * BE_LOCK_FRAC
                        stop = min(stop, min(entry - lock, fav + PTS_TRAIL))

        # 3) avaliação de 30 dias (idêntica ao motor oficial)
        pr = realized - r_ini
        ua = uf = 0.0
        if pos > 0: ua = (b["l"] - entry) * pv; uf = (b["h"] - entry) * pv
        elif pos < 0: ua = (entry - b["h"]) * pv; uf = (entry - b["l"]) * pv
        if pr + uf > pico:
            pico = pr + uf
        decidiu = False
        if pr + ua <= pico - DD:
            fecha(b["c"]); resultados.append({"status": "ESTOUROU", "dias_corridos": (dt - ini_aval).days}); decidiu = True
        elif pr >= META and len(dias) >= MIN_DIAS:
            fecha(b["c"]); resultados.append({"status": "APROVOU", "dias_corridos": (dt - ini_aval).days}); decidiu = True
        elif (dt - ini_aval).days >= JANELA_DIAS:
            fecha(b["c"]); resultados.append({"status": "EXPIROU", "dias_corridos": (dt - ini_aval).days}); decidiu = True
        if decidiu:
            nova_tentativa(dt)

        if m >= FLATTEN and pos != 0:
            fecha(b["c"])

        # 4) checa sinal NOVO nesta barra -> vira pendente pra resolver na próxima
        if pos == 0 and pendente is None and ENTRADA_INI <= m < ENTRADA_FIM:
            lado = sinal_reversao(bars, i, st, dom_map)
            if lado != 0:
                pendente = {"lado": lado, "c_sinal": b["c"]}

    return resultados, n_rejeitados_gap, n_perdidos_limit


def testa_gap(bars, dom):
    print("=== #3 — Mitigação do gap de entrada (motor PRÓPRIO, fill realista) ===")
    print("(números NÃO comparáveis aos 50% oficiais — comparar só entre as linhas abaixo)\n")
    print(f"  {'cenário':>34s} {'tentativas':>10s} {'aprovou':>8s} {'estourou':>9s} {'expirou':>8s} {'taxa':>6s}")
    print("-" * 90)

    res, _, _ = roda_motor_gap(bars, dom, modo="baseline")
    taxa_base = resume("baseline (fill sempre, gap ignorado)", res)

    for w in [10.0, 8.0, 5.0, 3.0]:
        res, n_rej, _ = roda_motor_gap(bars, dom, modo="rejeita_gap", gap_max=w)
        resume(f"rejeita gap > {w}pt ({n_rej} pulados)", res)

    res, _, n_perd = roda_motor_gap(bars, dom, modo="limit")
    resume(f"ordem Limit no nível ({n_perd} não enchidos)", res)
    print()
    return taxa_base


def main():
    print("Carregando NQ 1-min real...")
    bars = carregar("NQ_dados")
    dom = domingo_ranges(bars)
    print(f"{len(bars):,} barras\n")

    testa_be_trigger(bars, dom)
    testa_gap(bars, dom)


if __name__ == "__main__":
    main()
