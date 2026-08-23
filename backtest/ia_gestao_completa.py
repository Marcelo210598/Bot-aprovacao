#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IA na gestão completa (23/08) — junta as 4 possibilidades discutidas:

  1. Seletor diário de estratégia, agora com CONTEXTO RICO (desempenho
     recente de cada estratégia nos últimos 15 pregões, não só dia da
     semana/range).
  2+3+4. Gestão por trade decidida NA ENTRADA (não no meio do trade, pra não
     esbarrar no "teto estrutural" de MFE/MAE já documentado em 18/08):
     - contratos (3 a 7) -> ataca "perda maior que ganho" (sizing por risco)
     - trail_mult (0,5x a 3x do trailing padrão de 1,75pt) -> ataca "deixar
       rolar mais" (trailing mais largo = mais folga pro trade respirar)
     - be_lock_frac (0,3 a 1,0) -> quanto do MFE trava no breakeven

IMPORTANTE — por que "no meio do trade" virou "na entrada": chamar a IA a
cada barra de um trade aberto seria caro, lento, e (pela auditoria de 18/08)
provavelmente inútil, já que MFE/MAE de vencedores e perdedores se sobrepõem
demais pra decidir no meio do caminho. Decidir a "personalidade" do trade
(quanto arriscar, quanta folga dar) ANTES de entrar, com o contexto que já
sabemos ter algum sinal real (dist_nivel, dia da semana, regime recente),
é testável e não tem esse problema.

Roda 4 cenários com o motor de aprovação real (30 dias, retry imediato):
  A) BASELINE (REV, sem IA)
  B) SÓ seletor diário rico
  C) SÓ gestão por trade
  D) OS DOIS combinados

Uso:
    source .env   (ou export ANTHROPIC_API_KEY=...)
    python3 backtest/ia_gestao_completa.py --limit-dias 30   # teste barato
    python3 backtest/ia_gestao_completa.py                   # roda tudo
    python3 backtest/ia_gestao_completa.py --refresh

Modelo: Haiku 4.5 (barato). ~236 chamadas (seletor diário) + ~1.441
(gestão por trade) = ~1.677 chamadas — ainda assim < US$1 no total.

IMPORTANTE (regra de ouro do projeto): isto é só um teste de backtest. Nada
aqui toca o BotAprovacao*.cs nem o Market Replay.
"""
import argparse
import json
import os
import sys
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_estrategias_comparativo import (
    carregar, domingo_ranges, calcula_indicadores, FONTES_DISPONIVEIS,
    Estado, sinal_reversao, ENTRADA_INI, ENTRADA_FIM, ORB_FIM, FLATTEN, mins,
    MNQ_PV, RT_PER, N_CONTR, TICK, PTS_SL, TP, PTS_BE_TRIG, PTS_BE_LOCK, PTS_TRAIL,
    SLIP_BASE, META, DD, MIN_DIAS,
)
from run_janela_30d import JANELA_DIAS

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIA = os.path.join(HERE, "ia_gestao_cache_dia.json")
CACHE_TRADE = os.path.join(HERE, "ia_gestao_cache_trade.json")
OUT_CSV_DIA = os.path.join(HERE, "ia_gestao_decisoes_dia.csv")
OUT_CSV_TRADE = os.path.join(HERE, "ia_gestao_decisoes_trade.csv")

MODEL = "claude-haiku-4-5"
DOW_NOMES = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]
ESTRATEGIAS_VALIDAS = {"REV", "ORB", "EMAV", "ICT"}
JANELA_PERF = 15  # pregões pra trás pra medir "desempenho recente"

# ===========================================================================
# UTILITÁRIOS DE CACHE (genéricos)
# ===========================================================================
def carrega_cache(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def salva_cache(path, cache):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def chama_ia_em_lote(itens, decide_fn, cache_path, refresh, workers, label):
    """itens: lista de (chave, payload). decide_fn(client, payload) -> dict."""
    import anthropic

    client = anthropic.Anthropic()
    cache = {} if refresh else carrega_cache(cache_path)
    pendentes = [(k, p) for k, p in itens if refresh or k not in cache]

    if pendentes:
        print(f"[{label}] Chamando Claude ({MODEL}) para {len(pendentes)} itens novos "
              f"(de {len(itens)} total, {len(itens) - len(pendentes)} já em cache)...")
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(decide_fn, client, p): k for k, p in pendentes}
            done = 0
            for fut in as_completed(futs):
                k = futs[fut]
                try:
                    cache[k] = fut.result()
                except Exception as e:
                    cache[k] = {"_erro": str(e)}
                done += 1
                if done % 100 == 0 or done == len(pendentes):
                    print(f"  [{label}] {done}/{len(pendentes)}...")
                    salva_cache(cache_path, cache)
        salva_cache(cache_path, cache)
    else:
        print(f"[{label}] Todas as decisões já estavam em cache.")
    return cache


# ===========================================================================
# PARTE 0: coleta de trades por estratégia, com data (pra medir desempenho
# recente) — motor simples e contínuo, SEM o ciclo de aprovação de 30 dias
# (isso é só pra alimentar contexto, não é o teste em si).
# ===========================================================================
def coleta_trades_estrategia(bars, dom, fonte_key, ind):
    pv = MNQ_PV * N_CONTR
    rt = RT_PER * N_CONTR
    slip = SLIP_BASE * TICK
    pos = 0
    entry = stop = target = 0.0
    fav = 0.0
    be_done = False
    trades = []
    st = Estado()
    fn = FONTES_DISPONIVEIS[fonte_key]

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
            st.orb_hi = st.orb_lo = None
            st.orb_pronto = False
            st.fvg_bull = []
            st.fvg_bear = []
        if ENTRADA_INI <= m < 16 * 60:
            st.cur_hi = b["h"] if st.cur_hi is None else max(st.cur_hi, b["h"])
            st.cur_lo = b["l"] if st.cur_lo is None else min(st.cur_lo, b["l"])
        if ENTRADA_INI <= m < ORB_FIM:
            st.orb_hi = b["h"] if st.orb_hi is None else max(st.orb_hi, b["h"])
            st.orb_lo = b["l"] if st.orb_lo is None else min(st.orb_lo, b["l"])
        elif m >= ORB_FIM:
            st.orb_pronto = True

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
                        stop = max(stop, entry + PTS_BE_LOCK); be_done = True
                    if be_done:
                        stop = max(stop, fav - PTS_TRAIL)
                else:
                    fav = min(fav, b["l"])
                    if not be_done and (entry - fav) >= PTS_BE_TRIG:
                        stop = min(stop, entry - PTS_BE_LOCK); be_done = True
                    if be_done:
                        stop = min(stop, fav + PTS_TRAIL)

        if m >= FLATTEN and pos != 0:
            trades.append({"day": d, "pnl": ((b["c"] - entry) * pos - 2 * slip) * pv - rt})
            pos = 0

        if pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
            lado = fn(bars, i, st, dom, ind) if fonte_key == "EMAV" else fn(bars, i, st, dom)
            if lado != 0:
                entry = b["c"]; pos = lado; fav = entry; be_done = False
                stop = entry - lado * PTS_SL; target = entry + lado * TP
    return trades


def agrupa_por_dia(trades):
    por_dia = {}
    for t in trades:
        por_dia.setdefault(t["day"], []).append(t["pnl"])
    return por_dia


# ===========================================================================
# PARTE 1: seletor diário RICO (contexto pré-pregão + desempenho recente)
# ===========================================================================
TOOL_SELETOR = {
    "name": "escolher_estrategias",
    "description": "Escolhe quais estratégias usar hoje, em ordem de prioridade.",
    "input_schema": {
        "type": "object",
        "properties": {
            "estrategias": {
                "type": "array",
                "items": {"type": "string", "enum": ["REV", "ORB", "EMAV", "ICT"]},
                "minItems": 1,
            },
            "confianca": {"type": "number", "minimum": 0, "maximum": 1},
            "motivo": {"type": "string"},
        },
        "required": ["estrategias", "confianca", "motivo"],
    },
}

SYSTEM_SELETOR = """Você escolhe, um dia por vez, qual(is) estratégia(s) de trading em NQ/MNQ
(futuros, 1 minuto) priorizar naquele pregão: REV (reversão no nível do dia
anterior/domingo — a estratégia em produção), ORB (opening range breakout),
EMAV (EMA+VWAP+RSI), ICT (FVG "ICT-lite").

FATO JÁ CONHECIDO: REV sozinha tem a melhor taxa de aprovação agregada;
misturar historicamente PIORA porque todas compartilham o mesmo limite de
trades por avaliação. Na dúvida, prefira só REV. Mas você agora recebe o
DESEMPENHO REAL de cada estratégia nos últimos 15 pregões — se alguma
estiver claramente performando melhor que REV nesse recorte recente, é um
motivo concreto (não é achismo) pra considerar incluí-la como reserva hoje.

Você NÃO vê o resultado de hoje (seria trapaça). Responda usando a tool
`escolher_estrategias`."""


def formata_desempenho(por_dia_estrategia, dias_recentes):
    linhas = []
    for k in ["REV", "ORB", "EMAV", "ICT"]:
        pnls = [p for d in dias_recentes for p in por_dia_estrategia[k].get(d, [])]
        if not pnls:
            linhas.append(f"{k}: sem trades no período")
            continue
        n = len(pnls); wr = 100 * len([p for p in pnls if p > 0]) / n
        linhas.append(f"{k}: {n} trades, WR {wr:.0f}%, PnL líquido ${sum(pnls):.0f}")
    return "\n".join(linhas)


def coleta_contexto_diario(bars, dom):
    st = Estado()
    contexto = {}
    vistos = set()
    for b in bars:
        dt = b["dt"]; d = dt.strftime("%Y-%m-%d"); wd = dt.weekday(); m = mins(dt)
        if d != st.dia:
            if st.cur_hi is not None:
                st.pd_hi, st.pd_lo = st.cur_hi, st.cur_lo
            st.dia = d; st.cur_hi = st.cur_lo = None
            st.seg_hoje = dom[d] if (dom and wd == 0 and d in dom) else None
        if ENTRADA_INI <= m < 16 * 60:
            st.cur_hi = b["h"] if st.cur_hi is None else max(st.cur_hi, b["h"])
            st.cur_lo = b["l"] if st.cur_lo is None else min(st.cur_lo, b["l"])
        if d not in vistos and ENTRADA_INI <= m < ENTRADA_FIM:
            vistos.add(d)
            niv_hi = st.seg_hoje[0] if st.seg_hoje else st.pd_hi
            niv_lo = st.seg_hoje[1] if st.seg_hoje else st.pd_lo
            contexto[d] = {
                "dow": wd, "usou_domingo": st.seg_hoje is not None,
                "range_ant": (niv_hi - niv_lo) if (niv_hi and niv_lo) else None,
            }
    return contexto


def decide_dia(client, payload):
    resp = client.messages.create(
        model=MODEL, max_tokens=400, system=SYSTEM_SELETOR,
        tools=[TOOL_SELETOR], tool_choice={"type": "tool", "name": "escolher_estrategias"},
        messages=[{"role": "user", "content": payload}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            estrategias = [e for e in block.input.get("estrategias", []) if e in ESTRATEGIAS_VALIDAS]
            return {"estrategias": estrategias or ["REV"], "confianca": block.input.get("confianca", 0),
                    "motivo": block.input.get("motivo", "")}
    return {"estrategias": ["REV"], "confianca": 0.0, "motivo": "(falha, usa REV)"}


# ===========================================================================
# PARTE 2: gestão por trade (contratos + trailing + BE-lock), decidida na
# entrada, com base no contexto pré-trade (mesmo usado no teste de filtro).
# ===========================================================================
TOOL_GESTAO = {
    "name": "definir_gestao",
    "description": "Define o perfil de risco/gestão de UM trade específico, no momento da entrada.",
    "input_schema": {
        "type": "object",
        "properties": {
            "contratos": {"type": "integer", "minimum": 3, "maximum": 7,
                          "description": "Quantos contratos MNQ usar (padrão sempre usado: 5)."},
            "trail_mult": {"type": "number", "minimum": 0.5, "maximum": 3.0,
                           "description": "Multiplicador do trailing padrão (1,75pt). >1 = mais folga (deixa rolar mais). <1 = mais apertado (protege ganho antes)."},
            "be_lock_frac": {"type": "number", "minimum": 0.3, "maximum": 1.0,
                              "description": "Fração do MFE travada quando o breakeven ativa (padrão 0,75). Mais perto de 1,0 = trava quase tudo; mais baixo = mais folga pra continuar."},
            "confianca": {"type": "number", "minimum": 0, "maximum": 1},
            "motivo": {"type": "string"},
        },
        "required": ["contratos", "trail_mult", "be_lock_frac", "confianca", "motivo"],
    },
}

SYSTEM_GESTAO = """Você define o perfil de risco de UM trade específico de reversão em NQ/MNQ,
NO MOMENTO DA ENTRADA (antes de saber o resultado — decidir no meio do
trade não funciona, MFE e MAE de vencedores e perdedores se sobrepõem
demais, já testado e comprovado).

Você decide 3 coisas, baseado só no contexto do sinal (distância até a
linha, horário, dia da semana, se o nível é domingo/Globex):

- contratos (3 a 7, padrão 5): mais contratos = mais risco E mais retorno
  nesse trade específico. Use menos em sinais de menor qualidade (dist_nivel
  grande, nível de domingo mais espúrio), mais em sinais de alta qualidade
  (toque bem próximo da linha, nível RTH normal).
- trail_mult (0,5 a 3,0, padrão 1,0 = trailing de 1,75pt): valores MAIORES
  dão mais folga pro trade "respirar" e potencialmente capturar mais lucro
  se for um vencedor real, mas também dão mais chance de devolver lucro se
  reverter. Valores MENORES travam ganho mais cedo, mais seguro mas corta
  vencedores grandes.
- be_lock_frac (0,3 a 1,0, padrão 0,75): quanto do favor máximo (MFE) fica
  garantido quando o breakeven ativa. Mais alto = mais proteção, mais baixo
  = mais espaço pro trade continuar antes de travar.

Você NÃO vê o resultado do trade (seria trapaça). Use julgamento honesto —
é perfeitamente válido responder com os valores padrão (5 / 1,0 / 0,75) se
não achar motivo concreto pra mudar. Responda usando `definir_gestao`."""


def contexto_trade(s):
    dt = s["dt"]
    dow_nome = DOW_NOMES[dt.weekday()]
    lado_nome = "SHORT (venda no topo)" if s["lado"] == -1 else "LONG (compra no fundo)"
    origem = "range de domingo à noite (Globex)" if s["usou_domingo"] else "máx/mín do dia anterior (RTH)"
    return (
        f"Data: {dt.strftime('%Y-%m-%d')} ({dow_nome})\n"
        f"Hora do sinal: {dt.strftime('%H:%M')} ET\n"
        f"Lado: {lado_nome}\n"
        f"Origem do nível: {origem}\n"
        f"Distância do toque até a linha (dist_nivel): {s['dist_nivel']:.2f}pt"
    )


def coleta_sinais_rev(bars, dom):
    capturados = []

    def instrumentado(bars_, i, st, dom_map):
        lado = sinal_reversao(bars_, i, st, dom_map)
        if lado != 0:
            b = bars_[i]
            niv_hi = st.seg_hoje[0] if st.seg_hoje else st.pd_hi
            niv_lo = st.seg_hoje[1] if st.seg_hoje else st.pd_lo
            dist = (niv_hi - b["c"]) if lado == -1 else (b["c"] - niv_lo)
            capturados.append({"dt": b["dt"], "lado": lado, "dist_nivel": dist,
                                "usou_domingo": st.seg_hoje is not None})
        return lado

    original = FONTES_DISPONIVEIS["REV"]
    FONTES_DISPONIVEIS["REV"] = instrumentado
    try:
        from run_janela_30d import roda_janela_30d
        roda_janela_30d(bars, dom, ["REV"], ind=None, be_lock_frac=0.75)
    finally:
        FONTES_DISPONIVEIS["REV"] = original
    return capturados


def decide_trade(client, payload):
    resp = client.messages.create(
        model=MODEL, max_tokens=400, system=SYSTEM_GESTAO,
        tools=[TOOL_GESTAO], tool_choice={"type": "tool", "name": "definir_gestao"},
        messages=[{"role": "user", "content": payload}],
    )
    for block in resp.content:
        if block.type == "tool_use":
            i = block.input
            return {"contratos": int(i.get("contratos", 5)), "trail_mult": float(i.get("trail_mult", 1.0)),
                    "be_lock_frac": float(i.get("be_lock_frac", 0.75)), "confianca": i.get("confianca", 0),
                    "motivo": i.get("motivo", "")}
    return {"contratos": 5, "trail_mult": 1.0, "be_lock_frac": 0.75, "confianca": 0.0, "motivo": "(falha, usa padrão)"}


def chave_sinal(s):
    return f"{s['dt'].isoformat()}_{s['lado']}"


# ===========================================================================
# PARTE 3: motor de aprovação (fork de roda_janela_30d) com overrides por
# estratégia-do-dia E gestão-por-trade, opcionais e independentes.
# ===========================================================================
def roda_motor(bars, dom_map, ind, fontes_por_dia=None, gestao_por_trade=None):
    """fontes_por_dia: dict dia -> lista ordenada de chaves de FONTES_DISPONIVEIS
    (default: sempre ['REV']). gestao_por_trade: dict chave_sinal -> overrides
    de contratos/trail_mult/be_lock_frac (default: valores padrão do bot)."""
    fontes_por_dia = fontes_por_dia or {}
    gestao_por_trade = gestao_por_trade or {}

    pv_un = MNQ_PV; rt_un = RT_PER; slip = SLIP_BASE * TICK
    qtd_atual = N_CONTR
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False
    trail_ativo = PTS_TRAIL; belock_ativo = 0.75
    realized = 0.0
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None
    st = Estado()
    resultados = []

    def fecha(p):
        nonlocal pos, realized, qtd_atual
        if pos == 0 or qtd_atual == 0:
            return
        pv_ = pv_un * qtd_atual; rt_ = rt_un * qtd_atual
        realized += ((p - entry) * pos - 2 * slip) * pv_ - rt_
        pos = 0; qtd_atual = 0

    def nova_tentativa(dt):
        nonlocal r_ini, pico, ini_aval, dias
        r_ini = realized; pico = 0.0; ini_aval = dt; dias = set()

    for i, b in enumerate(bars):
        dt = b["dt"]; m = mins(dt); d = dt.strftime("%Y-%m-%d"); wd = dt.weekday()
        if ini_aval is None:
            nova_tentativa(dt)
        if d != st.dia:
            if st.cur_hi is not None:
                st.pd_hi, st.pd_lo = st.cur_hi, st.cur_lo
            st.dia = d; st.cur_hi = st.cur_lo = None
            st.seg_hoje = dom_map[d] if (dom_map and wd == 0 and d in dom_map) else None
            st.orb_hi = st.orb_lo = None; st.orb_pronto = False
            st.fvg_bull = []; st.fvg_bear = []
        if ENTRADA_INI <= m < 16 * 60:
            st.cur_hi = b["h"] if st.cur_hi is None else max(st.cur_hi, b["h"])
            st.cur_lo = b["l"] if st.cur_lo is None else min(st.cur_lo, b["l"])
        if ENTRADA_INI <= m < ORB_FIM:
            st.orb_hi = b["h"] if st.orb_hi is None else max(st.orb_hi, b["h"])
            st.orb_lo = b["l"] if st.orb_lo is None else min(st.orb_lo, b["l"])
        elif m >= ORB_FIM:
            st.orb_pronto = True

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
                    if not be_done and (fav - entry) >= PTS_BE_TRIG:
                        be_done = True
                        lock = (fav - entry) * belock_ativo
                        stop = max(stop, entry + lock)
                    if be_done:
                        lock = (fav - entry) * belock_ativo
                        stop = max(stop, max(entry + lock, fav - trail_ativo))
                else:
                    fav = min(fav, b["l"])
                    if not be_done and (entry - fav) >= PTS_BE_TRIG:
                        be_done = True
                        lock = (entry - fav) * belock_ativo
                        stop = min(stop, entry - lock)
                    if be_done:
                        lock = (entry - fav) * belock_ativo
                        stop = min(stop, min(entry - lock, fav + trail_ativo))

        pr = realized - r_ini
        ua = uf = 0.0
        if pos > 0: ua = (b["l"] - entry) * pv_un * qtd_atual; uf = (b["h"] - entry) * pv_un * qtd_atual
        elif pos < 0: ua = (entry - b["h"]) * pv_un * qtd_atual; uf = (entry - b["l"]) * pv_un * qtd_atual
        if pr + uf > pico:
            pico = pr + uf

        decidiu = False
        if pr + ua <= pico - DD:
            fecha(b["c"])
            resultados.append({"status": "ESTOUROU", "dias_corridos": (dt - ini_aval).days, "dias_operados": len(dias)})
            decidiu = True
        elif pr >= META and len(dias) >= MIN_DIAS:
            fecha(b["c"])
            resultados.append({"status": "APROVOU", "dias_corridos": (dt - ini_aval).days, "dias_operados": len(dias)})
            decidiu = True
        elif (dt - ini_aval).days >= JANELA_DIAS:
            fecha(b["c"])
            resultados.append({"status": "EXPIROU", "dias_corridos": (dt - ini_aval).days, "dias_operados": len(dias)})
            decidiu = True
        if decidiu:
            nova_tentativa(dt)

        if m >= FLATTEN and pos != 0:
            fecha(b["c"])

        if pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
            ordem = fontes_por_dia.get(d, ["REV"])
            lado = 0
            for f in ordem:
                fn = FONTES_DISPONIVEIS[f]
                lado = fn(bars, i, st, dom_map, ind) if f == "EMAV" else fn(bars, i, st, dom_map)
                if lado != 0:
                    break
            if lado != 0:
                entry = b["c"]; pos = lado; fav = entry; be_done = False
                k = f"{dt.isoformat()}_{lado}"
                g = gestao_por_trade.get(k, {})
                qtd_atual = g.get("contratos", N_CONTR)
                trail_ativo = PTS_TRAIL * g.get("trail_mult", 1.0)
                belock_ativo = g.get("be_lock_frac", 0.75)
                stop = entry - lado * PTS_SL; target = entry + lado * TP
                dias.add(d)

    return resultados


def resume(label, resultados):
    tot = len(resultados)
    n_ap = sum(1 for r in resultados if r["status"] == "APROVOU")
    n_es = sum(1 for r in resultados if r["status"] == "ESTOUROU")
    n_ex = sum(1 for r in resultados if r["status"] == "EXPIROU")
    dias_ap = sorted(r["dias_corridos"] for r in resultados if r["status"] == "APROVOU")
    dmed = dias_ap[len(dias_ap) // 2] if dias_ap else 0
    taxa = 100 * n_ap / tot if tot else 0
    print(f"  {label:>28s} {tot:>10} {n_ap:>8} {n_es:>9} {n_ex:>8} {taxa:>5.1f}% {dmed:>11}d")
    return taxa


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit-dias", type=int, default=None, help="testa só nos N dias mais recentes (mais barato)")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--workers", type=int, default=10)
    args = ap.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERRO: ANTHROPIC_API_KEY não definida. Rode: set -a && source .env && set +a")
        sys.exit(1)

    print("Carregando NQ 1-min real...")
    bars = carregar("NQ_dados")
    dom = domingo_ranges(bars)
    ind = calcula_indicadores(bars)

    print("Coletando trades por estratégia (pra medir desempenho recente)...")
    trades_por_estr = {k: agrupa_por_dia(coleta_trades_estrategia(bars, dom, k, ind))
                        for k in ["REV", "ORB", "EMAV", "ICT"]}

    print("Coletando contexto diário...")
    contexto_dias = coleta_contexto_diario(bars, dom)
    dias_ordenados = sorted(contexto_dias.keys())
    if args.limit_dias:
        dias_ordenados = dias_ordenados[-args.limit_dias:]
    print(f"{len(dias_ordenados)} dias de pregão ({dias_ordenados[0]} -> {dias_ordenados[-1]})\n")

    # ---- Parte 1: decisões do seletor diário rico ----
    itens_dia = []
    for idx, d in enumerate(dias_ordenados):
        info = contexto_dias[d]
        anteriores = dias_ordenados[max(0, idx - JANELA_PERF):idx]
        desemp = formata_desempenho(trades_por_estr, anteriores) if anteriores else "(sem histórico ainda)"
        dow_nome = DOW_NOMES[info["dow"]]
        origem = "range de domingo à noite (Globex)" if info["usou_domingo"] else "máx/mín do dia anterior (RTH)"
        range_txt = f"{info['range_ant']:.2f}pt" if info["range_ant"] else "(indisponível)"
        payload = (
            f"Data: {d} ({dow_nome})\nOrigem do nível hoje: {origem}\n"
            f"Range do dia anterior: {range_txt}\n\n"
            f"Desempenho de cada estratégia nos últimos {len(anteriores)} pregões:\n{desemp}"
        )
        itens_dia.append((d, payload))

    cache_dia = chama_ia_em_lote(itens_dia, decide_dia, CACHE_DIA, args.refresh, args.workers, "seletor-dia")
    fontes_por_dia = {d: cache_dia.get(d, {}).get("estrategias", ["REV"]) for d in dias_ordenados}

    # ---- Parte 2: decisões de gestão por trade (sinais da REV) ----
    print("\nColetando sinais da REV pra gestão por trade...")
    sinais = coleta_sinais_rev(bars, dom)
    if args.limit_dias:
        primeiro_dia = dias_ordenados[0]
        sinais = [s for s in sinais if s["dt"].strftime("%Y-%m-%d") >= primeiro_dia]
    print(f"{len(sinais)} sinais\n")

    itens_trade = [(chave_sinal(s), contexto_trade(s)) for s in sinais]
    cache_trade = chama_ia_em_lote(itens_trade, decide_trade, CACHE_TRADE, args.refresh, args.workers, "gestao-trade")
    gestao_por_trade = {k: v for k, v in cache_trade.items() if "_erro" not in v}

    # ---- Parte 3: roda os 4 cenários ----
    print("\nRerodando o motor de aprovação real (30 dias, retry imediato) — 4 cenários...\n")
    print(f"  {'cenário':>28s} {'tentativas':>10s} {'aprovou':>8s} {'estourou':>9s} {'expirou':>8s} "
          f"{'taxa':>6s} {'d.med aprov':>12s}")
    print("-" * 100)
    taxa_a = resume("A) BASELINE (REV, sem IA)", roda_motor(bars, dom, ind))
    taxa_b = resume("B) SÓ seletor diário rico", roda_motor(bars, dom, ind, fontes_por_dia=fontes_por_dia))
    taxa_c = resume("C) SÓ gestão por trade", roda_motor(bars, dom, ind, gestao_por_trade=gestao_por_trade))
    taxa_d = resume("D) OS DOIS combinados",
                     roda_motor(bars, dom, ind, fontes_por_dia=fontes_por_dia, gestao_por_trade=gestao_por_trade))
    print("-" * 100)
    for label, taxa in [("B (seletor)", taxa_b), ("C (gestão)", taxa_c), ("D (combinado)", taxa_d)]:
        delta = taxa - taxa_a
        sinal_txt = "+" if delta >= 0 else ""
        print(f"Δ {label} vs. baseline: {sinal_txt}{delta:.1f} pontos percentuais")

    import csv
    with open(OUT_CSV_DIA, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["data", "estrategias_ia", "confianca", "motivo"])
        for d in dias_ordenados:
            dec = cache_dia.get(d, {})
            w.writerow([d, "+".join(dec.get("estrategias", ["REV"])), dec.get("confianca"), dec.get("motivo")])
    with open(OUT_CSV_TRADE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["data", "hora", "lado", "dist_nivel", "contratos", "trail_mult", "be_lock_frac", "confianca", "motivo"])
        for s in sinais:
            k = chave_sinal(s); dec = cache_trade.get(k, {})
            w.writerow([s["dt"].strftime("%Y-%m-%d"), s["dt"].strftime("%H:%M"),
                        "SHORT" if s["lado"] == -1 else "LONG", f"{s['dist_nivel']:.2f}",
                        dec.get("contratos"), dec.get("trail_mult"), dec.get("be_lock_frac"),
                        dec.get("confianca"), dec.get("motivo")])
    print(f"\nDecisões salvas em {OUT_CSV_DIA} e {OUT_CSV_TRADE}")


if __name__ == "__main__":
    main()
