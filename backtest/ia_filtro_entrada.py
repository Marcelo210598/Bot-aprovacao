#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IA como filtro de entrada (23/08) — protótipo em Python, ANTES de qualquer
integração no NinjaScript. Testa se pedir pra Claude aceitar/recusar cada
sinal histórico (usando SÓ o contexto disponível NO MOMENTO do sinal, sem
vazar o resultado) melhora a taxa de aprovação real (motor de 30 dias, retry
imediato) sobre os 50% já medidos pro BOT 2 (BE-lock 0,75, idêntico ao
baseline nesse teste) — ver `run_janela_30d.py` e
`docs/taxa-aprovacao-30dias-20-08.md`.

CORREÇÃO IMPORTANTE (23/08): a primeira versão deste script usava
`diagnostico_mfe_mae_trades.csv` filtrado post-hoc, com um motor de
aprovação simplificado (só PnL realizado, sem DD intrabar). Um sanity check
mostrou 80% de aprovação e ZERO estouros no baseline — muito diferente dos
~50-71% reais, porque (1) esse CSV vem de um motor de backtest DIFERENTE
(`diagnostico_portoes.py`, fill no open da barra seguinte) do motor de
aprovação real (`run_estrategias_comparativo.py`/`run_janela_30d.py`, fill
no close da barra do sinal, com DD acompanhando o PnL intrabar de verdade),
e (2) filtrar trades de uma lista pronta não reproduz o comportamento real
de "só reavalia quando está flat".

Por isso esta versão NÃO usa o CSV — ela pluga a decisão da IA DIRETO na
função de sinal (`sinal_reversao`) do motor de aprovação real, rodando o
MESMO `roda_janela_30d()` que já valida todas as taxas de aprovação citadas
no projeto. Isso garante que baseline e "com IA" são comparados na mesma
régua, com DD/META/STOP_DIA/MaxTradesDia intrabar de verdade.

Uso:
    export ANTHROPIC_API_KEY=...
    python3 backtest/ia_filtro_entrada.py --limit 50      # teste rápido/barato primeiro
    python3 backtest/ia_filtro_entrada.py                 # roda tudo (~1500-2000 sinais/13 meses)
    python3 backtest/ia_filtro_entrada.py --refresh       # ignora cache, rechama a IA

Custo estimado (Sonnet 5, ~1.441 sinais no dataset inteiro de 13 meses,
~300 tokens de entrada + ~150 de saída por chamada): uns $3-5 no total pra
rodar tudo uma vez. As decisões ficam em cache (`ia_decisoes_cache.json`) —
reruns não pagam de novo, só sinais novos ou --refresh. Rodar com --limit
antes (ex.: --limit 50, menos de $0,20) pra conferir que está tudo certo
antes de pagar pelo dataset inteiro.

IMPORTANTE (regra de ouro do projeto): isto é só um teste de backtest. Nada
aqui toca o BotAprovacao*.cs nem o Market Replay. Só decide se vale a pena
seguir pra integração real.
"""
import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_estrategias_comparativo import (
    carregar, domingo_ranges, FONTES_DISPONIVEIS, sinal_reversao,
)
from run_janela_30d import roda_janela_30d

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_PATH = os.path.join(HERE, "ia_decisoes_cache.json")
OUT_CSV = os.path.join(HERE, "ia_decisoes_entrada.csv")

MODEL = "claude-sonnet-5"
DOW_NOMES = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]

TOOL_DECISAO = {
    "name": "decidir_trade",
    "description": "Decide se aceita ou recusa um sinal de entrada de reversão na máxima/mínima do dia anterior.",
    "input_schema": {
        "type": "object",
        "properties": {
            "decisao": {"type": "string", "enum": ["ACEITA", "RECUSA"]},
            "confianca": {"type": "number", "minimum": 0, "maximum": 1},
            "motivo": {"type": "string", "description": "Uma frase curta explicando a decisão."},
        },
        "required": ["decisao", "confianca", "motivo"],
    },
}

SYSTEM_PROMPT = """Você filtra sinais de entrada de um bot de reversão em NQ/MNQ (futuros).

A estratégia base: quando o preço toca a máxima (short) ou mínima (long) do
dia anterior (ou o range de domingo à noite/Globex na segunda) e a vela
fecha rejeitando a linha, o bot entra na reversão. A gestão de saída (stop
12,5pt / trailing tick a tick / breakeven proporcional 0,75 do MFE) é FIXA
e não depende da sua decisão — você só decide se ESTE sinal específico vale
a pena OPERAR ou PULAR, com base no contexto disponível no momento do toque.

Você NÃO vê o resultado do trade (isso seria trapaça, o backtest fica
inválido). Decida só com o que um trader teria disponível na hora:
distância entre o toque e a linha, horário, dia da semana, e se o nível é o
range de domingo à noite (Globex, mais espúrio) ou o dia anterior normal.

Responda SEMPRE usando a tool `decidir_trade`."""


def contexto_sinal(s):
    dt = s["dt"]
    dow_nome = DOW_NOMES[dt.weekday()]
    lado_nome = "SHORT (venda no topo)" if s["lado"] == -1 else "LONG (compra no fundo)"
    origem = "range de domingo à noite (Globex)" if s["usou_domingo"] else "máx/mín do dia anterior (RTH)"
    return (
        f"Data: {dt.strftime('%Y-%m-%d')} ({dow_nome})\n"
        f"Hora do sinal: {dt.strftime('%H:%M')} ET\n"
        f"Lado: {lado_nome}\n"
        f"Origem do nível: {origem}\n"
        f"Nível tocado: {s['nivel']:.2f}\n"
        f"Distância do toque até a linha (dist_nivel): {s['dist_nivel']:.2f}pt\n"
        f"Fechamento da vela de sinal: {s['close_sinal']:.2f}"
    )


def chave_sinal(s):
    return f"{s['dt'].isoformat()}_{s['lado']}"


# ---------------------------------------------------------------------------
# Passo 1: coleta os sinais reais do motor (só dispara quando a estrategia
# esta FLAT, exatamente como em producao) instrumentando sinal_reversao.
# ---------------------------------------------------------------------------
def coleta_sinais(bars, dom):
    capturados = []

    def instrumentado(bars_, i, st, dom_map):
        lado = sinal_reversao(bars_, i, st, dom_map)
        if lado != 0:
            b = bars_[i]
            niv_hi = st.seg_hoje[0] if st.seg_hoje else st.pd_hi
            niv_lo = st.seg_hoje[1] if st.seg_hoje else st.pd_lo
            nivel = niv_hi if lado == -1 else niv_lo
            dist = (niv_hi - b["c"]) if lado == -1 else (b["c"] - niv_lo)
            capturados.append({
                "dt": b["dt"], "lado": lado, "nivel": nivel, "dist_nivel": dist,
                "close_sinal": b["c"], "usou_domingo": st.seg_hoje is not None,
            })
        return lado

    original = FONTES_DISPONIVEIS["REV"]
    FONTES_DISPONIVEIS["REV"] = instrumentado
    try:
        roda_janela_30d(bars, dom, ["REV"], ind=None, be_lock_frac=0.75)
    finally:
        FONTES_DISPONIVEIS["REV"] = original
    return capturados


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


def decide_um(client, sinal):
    resp = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        tools=[TOOL_DECISAO],
        tool_choice={"type": "tool", "name": "decidir_trade"},
        messages=[{"role": "user", "content": contexto_sinal(sinal)}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            return block.input
    return {"decisao": "ACEITA", "confianca": 0.0, "motivo": "(falha ao extrair decisão da IA, aceito por padrão)"}


def obtem_decisoes(sinais, refresh, workers):
    import anthropic

    client = anthropic.Anthropic()
    cache = {} if refresh else carrega_cache()
    pendentes = [s for s in sinais if refresh or chave_sinal(s) not in cache]

    if pendentes:
        print(f"Chamando Claude ({MODEL}) para {len(pendentes)} sinais novos "
              f"(de {len(sinais)} total, {len(sinais) - len(pendentes)} já em cache)...")
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(decide_um, client, s): chave_sinal(s) for s in pendentes}
            done = 0
            for fut in as_completed(futs):
                k = futs[fut]
                try:
                    cache[k] = fut.result()
                except Exception as e:
                    cache[k] = {"decisao": "ACEITA", "confianca": 0.0, "motivo": f"(erro: {e}, aceito por padrão)"}
                done += 1
                if done % 50 == 0 or done == len(pendentes):
                    print(f"  {done}/{len(pendentes)}...")
                    salva_cache(cache)
        salva_cache(cache)
    else:
        print("Todas as decisões já estavam em cache — nenhuma chamada nova à API.")
    return cache


# ---------------------------------------------------------------------------
# Passo 3: reroda o motor REAL com a IA filtrando as entradas
# ---------------------------------------------------------------------------
def roda_com_filtro(bars, dom, cache, min_confianca):
    def filtrado(bars_, i, st, dom_map):
        lado = sinal_reversao(bars_, i, st, dom_map)
        if lado == 0:
            return 0
        b = bars_[i]
        k = f"{b['dt'].isoformat()}_{lado}"
        d = cache.get(k, {})
        aceita = d.get("decisao") == "ACEITA" and d.get("confianca", 0) >= min_confianca
        return lado if aceita else 0

    original = FONTES_DISPONIVEIS["REV"]
    FONTES_DISPONIVEIS["REV"] = filtrado
    try:
        return roda_janela_30d(bars, dom, ["REV"], ind=None, be_lock_frac=0.75)
    finally:
        FONTES_DISPONIVEIS["REV"] = original


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
    ap.add_argument("--limit", type=int, default=None, help="testa só nos N sinais mais recentes (mais barato/rápido)")
    ap.add_argument("--refresh", action="store_true", help="ignora cache e rechama a IA em todos os sinais")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--min-confianca", type=float, default=0.0,
                     help="só aceita sinais com confiança >= X (0 = desliga esse filtro extra)")
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERRO: variável ANTHROPIC_API_KEY não definida. Rode:\n"
              "  export ANTHROPIC_API_KEY=sk-ant-...\n"
              "antes de chamar este script.")
        sys.exit(1)

    print("Carregando NQ 1-min real...")
    bars = carregar("NQ_dados")
    dom = domingo_ranges(bars)

    print("Coletando sinais reais do motor (BOT 2, BE-lock 0,75)...")
    sinais = coleta_sinais(bars, dom)
    if args.limit:
        sinais = sinais[-args.limit:]
    print(f"{len(sinais)} sinais coletados "
          f"({sinais[0]['dt'].date()} -> {sinais[-1]['dt'].date()})\n")

    cache = obtem_decisoes(sinais, refresh=args.refresh, workers=args.workers)

    n_aceitos = sum(1 for s in sinais
                     if cache.get(chave_sinal(s), {}).get("decisao") == "ACEITA"
                     and cache.get(chave_sinal(s), {}).get("confianca", 0) >= args.min_confianca)
    print(f"IA aceitou {n_aceitos}/{len(sinais)} sinais ({100 * n_aceitos / len(sinais):.1f}%), "
          f"recusou {len(sinais) - n_aceitos}\n")

    print("Rerodando o motor de aprovação real (30 dias, retry imediato)...\n")
    print(f"  {'cenário':>32s} {'tentativas':>10s} {'aprovou':>8s} {'estourou':>9s} {'expirou':>8s} "
          f"{'taxa':>6s} {'d.med aprov':>12s}")
    print("-" * 102)
    res_base = roda_janela_30d(bars, dom, ["REV"], ind=None, be_lock_frac=0.75)
    taxa_base = resume("BASELINE (BOT 2, sem IA)", res_base)
    res_ia = roda_com_filtro(bars, dom, cache, args.min_confianca)
    taxa_ia = resume("COM FILTRO DA IA (Sonnet 5)", res_ia)
    print("-" * 102)
    delta = taxa_ia - taxa_base
    sinal_txt = "+" if delta >= 0 else ""
    print(f"\nΔ taxa de aprovação: {sinal_txt}{delta:.1f} pontos percentuais ({taxa_base:.1f}% -> {taxa_ia:.1f}%)")

    import csv
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["data", "hora", "lado", "nivel", "dist_nivel", "usou_domingo",
                    "decisao_ia", "confianca", "motivo"])
        for s in sinais:
            d = cache.get(chave_sinal(s), {})
            w.writerow([s["dt"].strftime("%Y-%m-%d"), s["dt"].strftime("%H:%M"),
                        "SHORT" if s["lado"] == -1 else "LONG", f"{s['nivel']:.2f}",
                        f"{s['dist_nivel']:.2f}", s["usou_domingo"],
                        d.get("decisao"), d.get("confianca"), d.get("motivo")])
    print(f"\nDecisões detalhadas (pra auditoria manual) salvas em {OUT_CSV}")


if __name__ == "__main__":
    main()
