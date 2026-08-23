#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IA como seletor DIÁRIO de estratégia (23/08) — protótipo em Python.

Ideia: em vez de rodar sempre REV (reversão), 1x por dia (antes do pregão
abrir) pergunta pra IA qual(is) estratégia(s) já testadas (REV/ORB/EMAV/ICT)
faz mais sentido priorizar NAQUELE dia, com base em contexto disponível ANTES
do pregão (dia da semana, tamanho do range do dia anterior, se usa o range
de domingo/Globex). A 1ª da lista que gerar sinal no dia vence — mesma regra
de sempre (`FONTES_DISPONIVEIS`, `run_estrategias_comparativo.py`).

Por que 1x/dia (não por sinal): já sabemos de 20/08 que misturar estratégia
sempre esbarra no `MaxTradesDia` compartilhado — o objetivo aqui não é
"aceitar/recusar trade" (já testado e piorou, 23/08), é ver se dá pra ativar
a estratégia certa pro REGIME do dia sem cortar frequência. Isso também é
MUITO mais barato: ~270 chamadas (1 por dia de pregão em 13 meses) em vez de
1.441 (1 por sinal).

Modelo: Haiku 4.5 (mais barato, sem custo de "thinking" — task é simples o
suficiente pra não precisar de raciocínio profundo). Custo estimado pro
dataset inteiro: bem abaixo de US$1.

Uso:
    export ANTHROPIC_API_KEY=...   (ou: source .env)
    python3 backtest/ia_seletor_estrategia_diario.py --limit 30   # teste barato primeiro
    python3 backtest/ia_seletor_estrategia_diario.py              # roda tudo (~270 dias)
    python3 backtest/ia_seletor_estrategia_diario.py --refresh    # ignora cache

IMPORTANTE (regra de ouro do projeto): isto é só um teste de backtest. Nada
aqui toca o BotAprovacao*.cs nem o Market Replay.
"""
import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_estrategias_comparativo import (
    carregar, domingo_ranges, calcula_indicadores, FONTES_DISPONIVEIS,
    Estado, ENTRADA_INI, ENTRADA_FIM, mins,
)
from run_janela_30d import roda_janela_30d

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(HERE, "ia_seletor_cache.json")
OUT_CSV = os.path.join(HERE, "ia_seletor_decisoes.csv")

MODEL = "claude-haiku-4-5"
DOW_NOMES = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
ESTRATEGIAS_VALIDAS = {"REV", "ORB", "EMAV", "ICT"}

TOOL_SELETOR = {
    "name": "escolher_estrategias",
    "description": "Escolhe quais estratégias usar hoje, em ordem de prioridade (a primeira que gerar sinal no dia vence, as outras ficam de reserva).",
    "input_schema": {
        "type": "object",
        "properties": {
            "estrategias": {
                "type": "array",
                "items": {"type": "string", "enum": ["REV", "ORB", "EMAV", "ICT"]},
                "minItems": 1,
                "description": "Ordem de prioridade. Pode repetir só REV se achar melhor não mudar nada hoje.",
            },
            "confianca": {"type": "number", "minimum": 0, "maximum": 1},
            "motivo": {"type": "string", "description": "Uma frase curta explicando a escolha."},
        },
        "required": ["estrategias", "confianca", "motivo"],
    },
}

SYSTEM_PROMPT = """Você escolhe, um dia por vez, qual(is) estratégia(s) de trading em NQ/MNQ
(futuros, 1 minuto) priorizar naquele pregão. Existem 4 estratégias já
implementadas e testadas:

- REV: reversão — entra contra o toque na máxima/mínima do dia anterior (ou
  range de domingo à noite/Globex na segunda) quando a vela fecha rejeitando
  a linha. É a estratégia em produção, a única validada de forma consistente.
- ORB: opening range breakout — entra na direção do rompimento da faixa dos
  primeiros minutos do pregão.
- EMAV: cruzamento de médias (EMA) + VWAP + RSI.
- ICT: "ICT-lite" — entra em preenchimento de FVG (fair value gap).

FATO JÁ CONHECIDO (de meses de backtest): REV sozinha tem a melhor taxa de
aprovação agregada; ORB/EMAV/ICT sozinhas são bem piores; e misturar
qualquer uma delas com REV historicamente PIORA o resultado, porque todas
compartilham o mesmo limite de 12 trades/dia — cada trade de outra
estratégia "rouba" espaço de um trade da REV. Na dúvida ou sem informação
que sugira o contrário, prefira usar só REV.

Sua tarefa: olhando o contexto do dia (dia da semana, tamanho do range do
dia anterior, se o nível vem do domingo à noite), decidir se há algum motivo
concreto pra também habilitar outra estratégia como reserva NAQUELE dia
específico, ou se é melhor manter só REV. Você NÃO vê o resultado do dia
(seria trapaça) — decida só com o que está disponível antes do pregão abrir.

Responda SEMPRE usando a tool `escolher_estrategias`."""


def contexto_dia(d, info):
    dow_nome = DOW_NOMES[info["dow"]]
    origem = "range de domingo à noite (Globex)" if info["usou_domingo"] else "máx/mín do dia anterior (RTH)"
    range_txt = f"{info['range_ant']:.2f}pt" if info["range_ant"] else "(indisponível, 1º dia)"
    return (
        f"Data: {d} ({dow_nome})\n"
        f"Origem do nível de referência hoje: {origem}\n"
        f"Tamanho do range anterior (proxy de volatilidade): {range_txt}"
    )


def chave_dia(d):
    return d


# ---------------------------------------------------------------------------
# Passo 1: coleta o contexto de CADA dia de pregão (antes da abertura), sem
# rodar nenhuma estratégia — só a lógica de range do dia anterior / domingo.
# ---------------------------------------------------------------------------
def coleta_contexto_diario(bars, dom):
    st = Estado()
    contexto = {}
    vistos = set()
    for b in bars:
        dt = b["dt"]
        d = dt.strftime("%Y-%m-%d")
        wd = dt.weekday()
        m = mins(dt)
        if d != st.dia:
            if st.cur_hi is not None:
                st.pd_hi, st.pd_lo = st.cur_hi, st.cur_lo
            st.dia = d
            st.cur_hi = st.cur_lo = None
            st.seg_hoje = dom[d] if (dom and wd == 0 and d in dom) else None
        if ENTRADA_INI <= m < 16 * 60:
            st.cur_hi = b["h"] if st.cur_hi is None else max(st.cur_hi, b["h"])
            st.cur_lo = b["l"] if st.cur_lo is None else min(st.cur_lo, b["l"])
        if d not in vistos and ENTRADA_INI <= m < ENTRADA_FIM:
            vistos.add(d)
            niv_hi = st.seg_hoje[0] if st.seg_hoje else st.pd_hi
            niv_lo = st.seg_hoje[1] if st.seg_hoje else st.pd_lo
            contexto[d] = {
                "dow": wd,
                "usou_domingo": st.seg_hoje is not None,
                "range_ant": (niv_hi - niv_lo) if (niv_hi and niv_lo) else None,
            }
    return contexto


# ---------------------------------------------------------------------------
# Passo 2: decisões da IA (com cache em disco)
# ---------------------------------------------------------------------------
def carrega_cache():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def salva_cache(cache):
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def decide_um(client, d, info):
    resp = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=SYSTEM_PROMPT,
        tools=[TOOL_SELETOR],
        tool_choice={"type": "tool", "name": "escolher_estrategias"},
        messages=[{"role": "user", "content": contexto_dia(d, info)}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            estrategias = [e for e in block.input.get("estrategias", []) if e in ESTRATEGIAS_VALIDAS]
            if not estrategias:
                estrategias = ["REV"]
            return {"estrategias": estrategias, "confianca": block.input.get("confianca", 0),
                    "motivo": block.input.get("motivo", "")}
    return {"estrategias": ["REV"], "confianca": 0.0, "motivo": "(falha ao extrair decisão, usa só REV por padrão)"}


def obtem_decisoes(contexto, refresh, workers):
    import anthropic

    client = anthropic.Anthropic()
    cache = {} if refresh else carrega_cache()
    pendentes = [d for d in contexto if refresh or d not in cache]

    if pendentes:
        print(f"Chamando Claude ({MODEL}) para {len(pendentes)} dias novos "
              f"(de {len(contexto)} total, {len(contexto) - len(pendentes)} já em cache)...")
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(decide_um, client, d, contexto[d]): d for d in pendentes}
            done = 0
            for fut in as_completed(futs):
                d = futs[fut]
                try:
                    cache[d] = fut.result()
                except Exception as e:
                    cache[d] = {"estrategias": ["REV"], "confianca": 0.0, "motivo": f"(erro: {e}, usa só REV)"}
                done += 1
                if done % 50 == 0 or done == len(pendentes):
                    print(f"  {done}/{len(pendentes)}...")
                    salva_cache(cache)
        salva_cache(cache)
    else:
        print("Todas as decisões já estavam em cache — nenhuma chamada nova à API.")
    return cache


# ---------------------------------------------------------------------------
# Passo 3: reroda o motor REAL com a IA escolhendo a estratégia por dia
# ---------------------------------------------------------------------------
def roda_com_seletor(bars, dom, cache, ind):
    def dinamico(bars_, i, st, dom_map):
        d = bars_[i]["dt"].strftime("%Y-%m-%d")
        ordem = cache.get(d, {}).get("estrategias", ["REV"])
        for f in ordem:
            fn = FONTES_DISPONIVEIS[f]
            lado = fn(bars_, i, st, dom_map, ind) if f == "EMAV" else fn(bars_, i, st, dom_map)
            if lado != 0:
                return lado
        return 0

    FONTES_DISPONIVEIS["IA_DIA"] = dinamico
    try:
        return roda_janela_30d(bars, dom, ["IA_DIA"], ind=ind, be_lock_frac=0.75)
    finally:
        del FONTES_DISPONIVEIS["IA_DIA"]


def resume(label, resultados):
    tot = len(resultados)
    n_ap = sum(1 for r in resultados if r["status"] == "APROVOU")
    n_es = sum(1 for r in resultados if r["status"] == "ESTOUROU")
    n_ex = sum(1 for r in resultados if r["status"] == "EXPIROU")
    dias_ap = sorted(r["dias_corridos"] for r in resultados if r["status"] == "APROVOU")
    dmed = dias_ap[len(dias_ap) // 2] if dias_ap else 0
    taxa = 100 * n_ap / tot if tot else 0
    print(f"  {label:>32s} {tot:>10} {n_ap:>8} {n_es:>9} {n_ex:>8} {taxa:>5.1f}% {dmed:>11}d")
    return taxa


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="testa só nos N dias mais recentes (mais barato/rápido)")
    ap.add_argument("--refresh", action="store_true", help="ignora cache e rechama a IA em todos os dias")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERRO: variável ANTHROPIC_API_KEY não definida. Rode:\n"
              "  export ANTHROPIC_API_KEY=sk-ant-...\n"
              "(ou: set -a && source .env && set +a) antes de chamar este script.")
        sys.exit(1)

    print("Carregando NQ 1-min real...")
    bars = carregar("NQ_dados")
    dom = domingo_ranges(bars)
    ind = calcula_indicadores(bars)

    print("Coletando contexto diário (antes da abertura, sem rodar estratégia)...")
    contexto = coleta_contexto_diario(bars, dom)
    dias = sorted(contexto.keys())
    if args.limit:
        dias = dias[-args.limit:]
        contexto = {d: contexto[d] for d in dias}
    print(f"{len(contexto)} dias de pregão ({dias[0]} -> {dias[-1]})\n")

    cache = obtem_decisoes(contexto, refresh=args.refresh, workers=args.workers)

    so_rev = sum(1 for d in dias if cache.get(d, {}).get("estrategias", ["REV"]) == ["REV"])
    print(f"IA manteve só REV em {so_rev}/{len(dias)} dias "
          f"({100 * so_rev / len(dias):.1f}%), adicionou reserva em {len(dias) - so_rev}\n")

    print("Rerodando o motor de aprovação real (30 dias, retry imediato)...\n")
    print(f"  {'cenário':>32s} {'tentativas':>10s} {'aprovou':>8s} {'estourou':>9s} {'expirou':>8s} "
          f"{'taxa':>6s} {'d.med aprov':>12s}")
    print("-" * 102)
    res_base = roda_janela_30d(bars, dom, ["REV"], ind=None, be_lock_frac=0.75)
    taxa_base = resume("BASELINE (REV, sem IA)", res_base)
    res_ia = roda_com_seletor(bars, dom, cache, ind)
    taxa_ia = resume("COM SELETOR DIÁRIO DA IA (Haiku)", res_ia)
    print("-" * 102)
    delta = taxa_ia - taxa_base
    sinal_txt = "+" if delta >= 0 else ""
    print(f"\nΔ taxa de aprovação: {sinal_txt}{delta:.1f} pontos percentuais ({taxa_base:.1f}% -> {taxa_ia:.1f}%)")

    import csv
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["data", "dow", "usou_domingo", "range_ant", "estrategias_ia", "confianca", "motivo"])
        for d in dias:
            info = contexto[d]
            dec = cache.get(d, {})
            w.writerow([d, DOW_NOMES[info["dow"]], info["usou_domingo"],
                        f"{info['range_ant']:.2f}" if info["range_ant"] else "",
                        "+".join(dec.get("estrategias", ["REV"])), dec.get("confianca"), dec.get("motivo")])
    print(f"\nDecisões detalhadas (pra auditoria manual) salvas em {OUT_CSV}")


if __name__ == "__main__":
    main()
