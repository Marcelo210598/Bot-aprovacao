#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚠️ ABANDONADO (23/08) — resultado NÃO CONFIÁVEL, ver "PROBLEMA ENCONTRADO" abaixo.
Mantido só de registro pra não repetir a mesma tentativa. NÃO usar os números
que esse script produz pra decisão nenhuma.

INVESTIGAÇÃO DO TETO DE 50% (23/08) — sem IA, só estatística sobre o que já
temos. Responde duas perguntas:

  (1) BOOTSTRAP DE ORDEM: se a MESMA sequência de resultados de trade (REV +
      BE-lock 0,75, 13 meses) tivesse acontecido em outra ORDEM cronológica,
      a taxa de aprovação mudaria muito? Se sim -> o problema é a forma como
      perdas/ganhos se agrupam no tempo (risco de sequência/clustering), não
      a qualidade média dos trades. Se não (a taxa fica ~igual não importa a
      ordem) -> o teto é do PAYOFF em si (win rate / relação ganho-perda),
      estrutural, e nenhuma tática de timing (incluindo IA) vai resolver.

  (2) SENSIBILIDADE DE PAYOFF: se a gente pudesse magicamente aumentar o
      ganho médio, diminuir a perda média, ou subir a taxa de acerto (sem se
      importar COMO conseguir isso), quanto cada um moveria a taxa de
      aprovação? Mostra onde vale mais a pena focar esforço.

APROXIMAÇÃO ASSUMIDA (documentada, não escondida): o simulador usado aqui
opera em cima do PnL líquido por DIA (não por barra), e usa contagem de
"pregões" como proxy de "dias corridos" (ignora fins de semana). Isso é
diferente do motor oficial bar-a-bar (`run_janela_30d.py`) — não dá pra
comparar o número absoluto com os 50% documentados. O que importa aqui é a
COMPARAÇÃO RELATIVA (ordem real vs. embaralhada; payoff real vs. escalado),
onde a mesma aproximação se aplica dos dois lados por igual.

Uso:
    python3 backtest/investiga_teto_50.py
    python3 backtest/investiga_teto_50.py --trials 5000   # mais preciso, mais lento

Não usa API de IA nenhuma — zero custo, só backtest local.

PROBLEMA ENCONTRADO (rodado 23/08): deu 100% de aprovação na ordem real, o
que é absurdo (deveria bater perto dos 50% do motor oficial). Causa: agregar
o PnL por DIA antes de checar o drawdown esconde o drawdown INTRADIÁRIO — um
dia com perda grande de manhã e ganho parecido à tarde fecha "neutro" no
simulador, mas a conta pode ter estourado no meio do caminho de verdade.
Mesma categoria de erro já visto (e corrigido) em `ia_filtro_entrada.py` na
primeira tentativa, só que na versão "por dia" em vez de "por trade".

Problema de fundo, não só bug: pra fazer um bootstrap de ORDEM de verdade
seria preciso o motor fiel barra a barra (`run_janela_30d.py`) — mas não dá
pra embaralhar barras de preço reais e continuar fazendo sentido (o preço de
amanhã depende do de hoje). Esse tipo de teste esbarra numa parede técnica,
não é só falta de ajuste fino. Conclusão sobre o teto de 50% tirada de outra
forma — ver item #20 em `docs/melhorias-sugeridas.md` (convergência de ~15
ângulos já testados com o motor oficial, todos neutros ou piores).
"""
import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_estrategias_comparativo import (
    carregar, domingo_ranges, Estado, sinal_reversao,
    ENTRADA_INI, ENTRADA_FIM, ORB_FIM, FLATTEN, mins,
    MNQ_PV, RT_PER, N_CONTR, TICK, PTS_SL, TP, PTS_BE_TRIG, PTS_TRAIL,
    SLIP_BASE, META, DD, MIN_DIAS,
)

JANELA_DIAS = 30


# ---------------------------------------------------------------------------
# Coleta os trades REAIS (REV + BE-lock 0,75), bar-a-bar, agrupados por dia.
# ---------------------------------------------------------------------------
def coleta_trades_reais(bars, dom, be_lock_frac=0.75):
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
                    trades.append({"day": d, "pnl": ((stop - entry) * pos - 2 * slip) * pv - rt}); pos = 0; saiu = True
                elif b["h"] >= target:
                    trades.append({"day": d, "pnl": ((target - entry) * pos - 2 * slip) * pv - rt}); pos = 0; saiu = True
            else:
                if b["h"] >= stop:
                    trades.append({"day": d, "pnl": ((stop - entry) * pos - 2 * slip) * pv - rt}); pos = 0; saiu = True
                elif b["l"] <= target:
                    trades.append({"day": d, "pnl": ((target - entry) * pos - 2 * slip) * pv - rt}); pos = 0; saiu = True
            if not saiu and pos != 0:
                if pos > 0:
                    fav = max(fav, b["h"])
                    if not be_done and (fav - entry) >= PTS_BE_TRIG:
                        be_done = True
                        stop = max(stop, entry + (fav - entry) * be_lock_frac)
                    if be_done:
                        lock = (fav - entry) * be_lock_frac
                        stop = max(stop, max(entry + lock, fav - PTS_TRAIL))
                else:
                    fav = min(fav, b["l"])
                    if not be_done and (entry - fav) >= PTS_BE_TRIG:
                        be_done = True
                        stop = min(stop, entry - (entry - fav) * be_lock_frac)
                    if be_done:
                        lock = (entry - fav) * be_lock_frac
                        stop = min(stop, min(entry - lock, fav + PTS_TRAIL))

        if m >= FLATTEN and pos != 0:
            trades.append({"day": d, "pnl": ((b["c"] - entry) * pos - 2 * slip) * pv - rt})
            pos = 0

        if pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
            lado = sinal_reversao(bars, i, st, dom)
            if lado != 0:
                entry = b["c"]; pos = lado; fav = entry; be_done = False
                stop = entry - lado * PTS_SL; target = entry + lado * TP
    return trades


def agrupa_dias_ordenados(trades):
    por_dia = {}
    for t in trades:
        por_dia.setdefault(t["day"], 0.0)
        por_dia[t["day"]] += t["pnl"]
    dias_ordenados = sorted(por_dia.keys())
    return [por_dia[d] for d in dias_ordenados]


# ---------------------------------------------------------------------------
# Simulador em nível de DIA (aproximação — ver aviso no topo do arquivo)
# ---------------------------------------------------------------------------
def simula_dias(pnl_por_dia):
    resultados = []
    realized = 0.0
    r_ini = 0.0
    pico = 0.0
    ini_idx = 0
    dias_operados = 0

    for idx, pnl_dia in enumerate(pnl_por_dia):
        realized += pnl_dia
        if pnl_dia != 0:
            dias_operados += 1
        pr = realized - r_ini
        pico = max(pico, pr)
        dias_corridos = idx - ini_idx + 1

        status = None
        if pr <= pico - DD:
            status = "ESTOUROU"
        elif pr >= META and dias_operados >= MIN_DIAS:
            status = "APROVOU"
        elif dias_corridos >= JANELA_DIAS:
            status = "EXPIROU"

        if status:
            resultados.append({"status": status, "dias_corridos": dias_corridos})
            r_ini = realized; pico = 0.0; ini_idx = idx + 1; dias_operados = 0

    return resultados


def taxa(resultados):
    tot = len(resultados)
    if not tot:
        return 0.0, 0, 0
    ap = sum(1 for r in resultados if r["status"] == "APROVOU")
    return 100 * ap / tot, ap, tot


# ---------------------------------------------------------------------------
# Parte 1: bootstrap de ordem
# ---------------------------------------------------------------------------
def bootstrap_ordem(pnl_por_dia, trials, seed=42):
    rnd = random.Random(seed)
    taxas = []
    for _ in range(trials):
        embaralhado = pnl_por_dia[:]
        rnd.shuffle(embaralhado)
        t, _, _ = taxa(simula_dias(embaralhado))
        taxas.append(t)
    return taxas


# ---------------------------------------------------------------------------
# Parte 2: sensibilidade de payoff (escala ganhos/perdas/WR sintéticamente)
# ---------------------------------------------------------------------------
def escala_trades(trades, mult_ganho=1.0, mult_perda=1.0):
    novos = []
    for t in trades:
        pnl = t["pnl"] * mult_ganho if t["pnl"] > 0 else t["pnl"] * mult_perda
        novos.append({"day": t["day"], "pnl": pnl})
    return novos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=2000)
    args = ap.parse_args()

    print("Carregando NQ 1-min real...")
    bars = carregar("NQ_dados")
    dom = domingo_ranges(bars)

    print("Coletando trades reais (REV + BE-lock 0,75, 13 meses)...")
    trades = coleta_trades_reais(bars, dom, be_lock_frac=0.75)
    w = [t["pnl"] for t in trades if t["pnl"] > 0]
    l = [t["pnl"] for t in trades if t["pnl"] <= 0]
    print(f"{len(trades)} trades | WR {100*len(w)/len(trades):.1f}% | "
          f"avgWin ${sum(w)/len(w):.1f} | avgLoss ${sum(l)/len(l):.1f} | "
          f"PF {sum(w)/abs(sum(l)):.2f}\n")

    pnl_dias_real = agrupa_dias_ordenados(trades)
    taxa_real, ap_real, tot_real = taxa(simula_dias(pnl_dias_real))
    print(f"[Aproximação diária] Taxa com a ORDEM REAL (cronológica): {taxa_real:.1f}% "
          f"({ap_real}/{tot_real} tentativas)")
    print("(não compare esse número com os 50% do motor oficial bar-a-bar — "
          "aproximações diferentes, ver aviso no topo do arquivo)\n")

    # ---- Parte 1: bootstrap ----
    print(f"=== PARTE 1: bootstrap de ordem ({args.trials} embaralhamentos) ===\n")
    taxas_shuffle = bootstrap_ordem(pnl_dias_real, args.trials)
    taxas_shuffle_sorted = sorted(taxas_shuffle)
    media = sum(taxas_shuffle) / len(taxas_shuffle)
    p10 = taxas_shuffle_sorted[int(0.10 * len(taxas_shuffle_sorted))]
    p90 = taxas_shuffle_sorted[int(0.90 * len(taxas_shuffle_sorted))]
    percentil_real = 100 * sum(1 for t in taxas_shuffle if t <= taxa_real) / len(taxas_shuffle)

    print(f"  Taxa com a ordem REAL:         {taxa_real:>5.1f}%")
    print(f"  Média das ordens embaralhadas: {media:>5.1f}%")
    print(f"  Faixa (p10-p90) embaralhadas:  {p10:>5.1f}% - {p90:.1f}%")
    print(f"  A ordem real está no percentil {percentil_real:.0f} da distribuição embaralhada")
    print()
    if abs(taxa_real - media) < 5 and (p90 - p10) < 15:
        print("  -> INTERPRETAÇÃO: a taxa muda pouco não importa a ordem. O teto é do PAYOFF em")
        print("     si (win rate / relação ganho-perda), não de quando os trades aconteceram.")
        print("     Nenhuma tática de timing/sequenciamento (com ou sem IA) deve resolver isso.")
    elif (p90 - p10) >= 15:
        print("  -> INTERPRETAÇÃO: a taxa varia BASTANTE dependendo da ordem — o resultado é")
        print("     sensível a como perdas se agrupam no tempo (risco de sequência). Vale investigar")
        print("     se dá pra reduzir esse risco (ex.: reduzir exposição depois de sequência de losses).")
    else:
        print("  -> INTERPRETAÇÃO: resultado misto, ver os números acima com cuidado.")

    # ---- Parte 2: sensibilidade de payoff ----
    print(f"\n=== PARTE 2: sensibilidade de payoff (na ordem real, hipotético) ===\n")
    print(f"  {'cenário':>38s} {'taxa':>7s}")
    print("-" * 50)
    base, _, _ = taxa(simula_dias(pnl_dias_real))
    print(f"  {'real (baseline)':>38s} {base:>6.1f}%")
    for mult in [1.1, 1.25, 1.5, 2.0]:
        t, _, _ = taxa(simula_dias(agrupa_dias_ordenados(escala_trades(trades, mult_ganho=mult))))
        print(f"  {'ganho médio x' + str(mult):>38s} {t:>6.1f}%")
    for mult in [0.9, 0.75, 0.5]:
        t, _, _ = taxa(simula_dias(agrupa_dias_ordenados(escala_trades(trades, mult_perda=mult))))
        print(f"  {'perda média x' + str(mult):>38s} {t:>6.1f}%")
    # combinado: ganho +25% e perda -25% ao mesmo tempo (cenário "ideal")
    t, _, _ = taxa(simula_dias(agrupa_dias_ordenados(escala_trades(trades, mult_ganho=1.25, mult_perda=0.75))))
    print(f"  {'ganho x1,25 E perda x0,75 juntos':>38s} {t:>6.1f}%")
    print()
    print("  (Escalar 'ganho' ou 'perda' aqui é hipotético/matemático — não representa nenhuma")
    print("   técnica real de trading. Serve só pra mostrar QUANTA melhoria de payoff seria")
    print("   necessária pra mover a taxa de forma visível, como referência de esforço.)")


if __name__ == "__main__":
    main()
