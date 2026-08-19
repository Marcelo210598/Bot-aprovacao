#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIAGNOSTICO DOS 3 PORTOES — BotAprovacao.cs (18/08/2026)

Pergunta: por que o bot ficou ZERADO em varios dias do forward test 5min de
junho/2026? Este script reproduz, fora do NT8, exatamente a logica de
EntradaNiveis() do src/BotAprovacao.cs (Portao 1: toque | Portao 2: rejeicao |
Portao 3: anti-chase) e classifica o motivo de cada dia zerado.

Dados: reaproveita NQ_dados/*.txt (1min, export NinjaTrader, timestamps UTC).
NAO precisa baixar nada novo — o grafico de 5min e' obtido agregando (resample)
os candles de 1min aqui dentro, do mesmo jeito que o NT8 monta um grafico de
5min a partir do feed.

Uso:
    python3 diagnostico_portoes.py

Gera:
    - relatorio no terminal (Parte 2: diagnostico + Parte 3: sensibilidade)
    - backtest/diagnostico_portoes_junho.csv (Parte 2, uma linha por dia)
    - backtest/sensibilidade_portoes_junho.csv (Parte 3)
"""
import glob
import os
import csv
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')
UTC = timezone.utc

# ===================== CONFIG DE PRODUCAO (espelha BotAprovacao.cs) =====================
TICK = 0.25
TOL_TICKS_PROD = 20          # TolToqueTicks -> 20*0.25 = 5pt
MAX_DIST_PROD = 15.0         # MaxDistPontos
SESSAO_INICIO = 9 * 60 + 30  # 930 ET
ENTRADA_FIM = 16 * 60        # 1600 ET
DOM_NOITE_INICIO = 18 * 60   # 1800 ET (domingo)

# Perna de risco (so usada na Parte 3, pra estimar trades/dia com simulacao real)
PTS_SL = 12.5
PTS_TP = 60.0
PTS_BE_TRIG = 3.75
PTS_BE_LOCK = 2.5
PTS_TRAIL = 1.75
STOP_DIA_PT = 750.0 / (2.0 * 5)   # StopDiarioDolar=$750 / (MNQ_PV=2 * 5 contratos) = 75pt

PASTA_DADOS = os.path.join(os.path.dirname(__file__), '..', 'NQ_dados')
SAIDA_DIR = os.path.dirname(__file__)

# Janela do forward test que queremos diagnosticar
ANALISE_INICIO = '2026-06-01'
ANALISE_FIM = '2026-06-30'

# Dias explicitamente pedidos pra diagnostico (o script tambem acha os outros sozinho)
DIAS_PEDIDOS = ['2026-06-05', '2026-06-10', '2026-06-15',
                 '2026-06-19', '2026-06-22', '2026-06-23']


# ===================== CARGA E RESAMPLE =====================
def carregar_1min(pasta):
    """Le todos os *.txt (1min, UTC), dedupe por timestamp, retorna lista ordenada em ET."""
    vistos = {}
    for f in sorted(glob.glob(os.path.join(pasta, '*.txt'))):
        with open(f, encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    dtp, resto = line.split(';', 1)
                    data, hora = dtp.split()
                    o, h, l, c, v = resto.split(';')
                    dt = datetime(int(data[:4]), int(data[4:6]), int(data[6:8]),
                                  int(hora[:2]), int(hora[2:4]), tzinfo=UTC)
                    o, h, l, c, v = float(o), float(h), float(l), float(c), float(v)
                except Exception:
                    continue
                if dt not in vistos:
                    vistos[dt] = (dt.astimezone(ET), o, h, l, c, v)
    return [{'dt': vistos[k][0], 'o': vistos[k][1], 'h': vistos[k][2],
             'l': vistos[k][3], 'c': vistos[k][4], 'v': vistos[k][5]}
            for k in sorted(vistos)]


def resample_5min(bars1m):
    """Agrega candles de 1min em candles de 5min alinhados no relogio (:00,:05,:10...).
    9h30 cai exatamente numa borda de 5min, entao a janela RTH nao desalinha."""
    out = []
    cur_key = None
    o = h = l = c = v = None
    for b in bars1m:
        dt = b['dt']
        bucket = dt.replace(minute=(dt.minute // 5) * 5, second=0, microsecond=0)
        if bucket != cur_key:
            if cur_key is not None:
                out.append({'dt': cur_key, 'o': o, 'h': h, 'l': l, 'c': c, 'v': v})
            cur_key, o, h, l, c, v = bucket, b['o'], b['h'], b['l'], b['c'], b['v']
        else:
            h = max(h, b['h']); l = min(l, b['l']); c = b['c']; v += b['v']
    if cur_key is not None:
        out.append({'dt': cur_key, 'o': o, 'h': h, 'l': l, 'c': c, 'v': v})
    return out


def mins(dt):
    return dt.hour * 60 + dt.minute


# ===================== PORTOES (replica EntradaNiveis do .cs) =====================
def avalia_bar(b, n_hi, n_lo, tol_pts, max_dist):
    """Reproduz a ordem exata do .cs: checa a zona da MAXIMA primeiro (SHORT) e, se
    tocou, RETORNA sem olhar a MINIMA nessa barra (igual ao 'return;' do EntradaNiveis).
    So cai pro lado LONG se a barra nao tocou a zona da MAXIMA."""
    h, l, c = b['h'], b['l'], b['c']

    if h >= n_hi - tol_pts:
        if c < n_hi:
            dist = n_hi - c
            if max_dist > 0 and dist > max_dist:
                return {'lado': 'SHORT', 'cat': 'P3_CHASE', 'dist': dist, 'nivel': n_hi}
            return {'lado': 'SHORT', 'cat': 'OPEROU', 'dist': dist, 'nivel': n_hi}
        return {'lado': 'SHORT', 'cat': 'P2_ROMPEU', 'dist': c - n_hi, 'nivel': n_hi}

    if l <= n_lo + tol_pts:
        if c > n_lo:
            dist = c - n_lo
            if max_dist > 0 and dist > max_dist:
                return {'lado': 'LONG', 'cat': 'P3_CHASE', 'dist': dist, 'nivel': n_lo}
            return {'lado': 'LONG', 'cat': 'OPEROU', 'dist': dist, 'nivel': n_lo}
        return {'lado': 'LONG', 'cat': 'P2_ROMPEU', 'dist': n_lo - c, 'nivel': n_lo}

    return None


# ===================== PARTE 2: DIAGNOSTICO DIA A DIA =====================
def diagnostica(bars5m, tol_ticks=TOL_TICKS_PROD, max_dist=MAX_DIST_PROD):
    """Passa uma vez por todas as barras (mesma maquina de estados do .cs: pdHigh/pdLow
    e onHigh/onLow) e, para cada dia dentro da janela de analise, registra os toques
    ocorridos na janela RTH e classifica o motivo se o dia ficar zerado."""
    tol_pts = tol_ticks * TICK

    cur_hi = cur_lo = None
    pd_hi = pd_lo = None
    dia = None
    on_key = None
    on_hi = on_lo = None

    dias = {}   # data -> dict com toques, nivel, fonte, day_hi, day_lo

    for b in bars5m:
        dt = b['dt']
        d = dt.strftime('%Y-%m-%d')
        m = mins(dt)
        dow = dt.weekday()  # Python: Monday=0 ... Sunday=6

        em_sessao = SESSAO_INICIO <= m < ENTRADA_FIM  # janela RTH p/ range do nivel (9h30-16h)

        if d != dia:
            if cur_hi is not None:
                pd_hi, pd_lo = cur_hi, cur_lo
            dia = d
            cur_hi = b['h'] if em_sessao else None
            cur_lo = b['l'] if em_sessao else None
        elif em_sessao:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])

        # range do domingo a noite (Globex) -> alimenta a SEGUNDA seguinte
        chave_seg = None
        if dow == 6 and m >= DOM_NOITE_INICIO:
            chave_seg = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
        elif dow == 0 and m < SESSAO_INICIO:
            chave_seg = d
        if chave_seg is not None:
            if chave_seg != on_key:
                on_key, on_hi, on_lo = chave_seg, b['h'], b['l']
            else:
                on_hi = max(on_hi, b['h']); on_lo = min(on_lo, b['l'])

        if not (ANALISE_INICIO <= d <= ANALISE_FIM):
            continue
        if not (SESSAO_INICIO <= m < ENTRADA_FIM):
            continue

        # nivel ativo do dia (igual a NivelAtivo() do .cs)
        if dow == 0 and on_key == d and on_hi is not None and on_hi > 0:
            n_hi, n_lo, fonte = on_hi, on_lo, 'domingo (Globex)'
        else:
            n_hi, n_lo, fonte = pd_hi, pd_lo, 'RTH anterior'

        reg = dias.setdefault(d, {'nivel': (n_hi, n_lo, fonte), 'toques': [],
                                   'day_hi': None, 'day_lo': None})
        reg['day_hi'] = b['h'] if reg['day_hi'] is None else max(reg['day_hi'], b['h'])
        reg['day_lo'] = b['l'] if reg['day_lo'] is None else min(reg['day_lo'], b['l'])

        if n_hi is None or n_lo is None:
            continue  # sem nivel de referencia (inicio do dataset) -> nao da p/ avaliar

        ev = avalia_bar(b, n_hi, n_lo, tol_pts, max_dist)
        if ev is not None:
            ev['hora'] = dt.strftime('%H:%M')
            reg['toques'].append(ev)

    return dias


def classifica_dia(reg):
    """Decide o motivo do dia zerado (ou 'OPEROU') a partir da lista de toques."""
    toques = reg['toques']
    if any(t['cat'] == 'OPEROU' for t in toques):
        return 'OPEROU', None
    if not toques:
        return 'P1_NUNCA_TOCOU', None
    # dia zerado com toques -> motivo principal = categoria do PRIMEIRO toque (foi o que
    # de fato bloqueou a primeira chance real do dia)
    primeiro = toques[0]
    return primeiro['cat'], primeiro


def gera_relatorio_parte2(dias):
    linhas = []
    contagem = {'P1_NUNCA_TOCOU': 0, 'P2_ROMPEU': 0, 'P3_CHASE': 0}
    dias_operados = 0

    for d in sorted(dias):
        reg = dias[d]
        n_hi, n_lo, fonte = reg['nivel']
        cat, primeiro = classifica_dia(reg)
        data_br = datetime.strptime(d, '%Y-%m-%d').strftime('%d/%m/%Y')

        if cat == 'OPEROU':
            dias_operados += 1
            continue  # so reportamos os ZERADOS na Parte 2, como pedido

        contagem[cat] += 1
        n_toques = len(reg['toques'])
        n_p2 = sum(1 for t in reg['toques'] if t['cat'] == 'P2_ROMPEU')
        n_p3 = sum(1 for t in reg['toques'] if t['cat'] == 'P3_CHASE')

        if cat == 'P1_NUNCA_TOCOU':
            motivo = (f"Preco ficou entre {reg['day_lo']:.2f} e {reg['day_hi']:.2f} "
                      f"(nHi={n_hi:.2f}, faltou {n_hi - reg['day_hi']:.2f}pt | "
                      f"nLo={n_lo:.2f}, faltou {reg['day_lo'] - n_lo:.2f}pt)")
        elif cat == 'P2_ROMPEU':
            motivo = (f"Tocou {primeiro['lado']} as {primeiro['hora']} em {primeiro['nivel']:.2f} "
                      f"mas fechou {primeiro['dist']:.2f}pt do OUTRO lado da linha (rompimento, "
                      f"sem rejeicao). {n_toques} toque(s) no dia ({n_p2}xP2, {n_p3}xP3)")
        else:  # P3_CHASE
            motivo = (f"Rejeitou {primeiro['lado']} as {primeiro['hora']} na linha "
                      f"{primeiro['nivel']:.2f}, mas fechou a {primeiro['dist']:.2f}pt dela "
                      f"(> {MAX_DIST_PROD}pt permitido). {n_toques} toque(s) no dia "
                      f"({n_p2}xP2, {n_p3}xP3)")

        linhas.append({
            'Data': data_br, 'Portao': cat.split('_')[0], 'Motivo': motivo,
            'nHi': round(n_hi, 2), 'nLo': round(n_lo, 2),
            'MaxChegou': round(reg['day_hi'], 2), 'MinChegou': round(reg['day_lo'], 2),
            'Fonte': fonte, 'Pedido': 'SIM' if d in DIAS_PEDIDOS else '',
        })

    return linhas, contagem, dias_operados


# ===================== PARTE 3: SIMULACAO COMPLETA (p/ sensibilidade) =====================
def simula(bars5m, tol_ticks, max_dist):
    """Backtest completo (entrada + gestao de saida SL/BE/trailing/TP), bar a bar,
    igual ao motor ja usado no projeto (backtest/run_proximity_filter.py), so que
    aqui em barras de 5min. Retorna dias_operados, dias_zerados, total de trades."""
    tol_pts = tol_ticks * TICK

    cur_hi = cur_lo = None
    pd_hi = pd_lo = None
    dia = None
    on_key = None
    on_hi = on_lo = None

    pos = 0; entry = stop = alvo = fav = 0.0; be_feito = False
    dia_trade = None; pnl_dia0 = 0.0; realizado = 0.0; bloqueado_hoje = False
    trades_por_dia = {}

    def fecha(preco):
        nonlocal pos, realizado
        pv = 1.0  # so contamos pontos aqui, PnL$ nao e' o foco da Parte 3
        realizado += (preco - entry) * pos if pos > 0 else (entry - preco) * abs(pos)
        pos = 0

    for b in bars5m:
        dt = b['dt']; d = dt.strftime('%Y-%m-%d'); m = mins(dt); dow = dt.weekday()
        if not (ANALISE_INICIO <= d <= ANALISE_FIM):
            # ainda precisa alimentar os niveis mesmo fora da janela de analise
            pass

        em_sessao = SESSAO_INICIO <= m < ENTRADA_FIM  # BUG CORRIGIDO 18/08: era "< 1600" comparado
                                                       # contra minutos-desde-meia-noite (m), onde
                                                       # 1600 nunca excluia nada (m max = 1439) -> a
                                                       # janela RTH vazava pro pregao noturno inteiro
                                                       # e inflava nHi/nLo com o range de Globex.
        if d != dia:
            if cur_hi is not None:
                pd_hi, pd_lo = cur_hi, cur_lo
            dia = d
            cur_hi = b['h'] if em_sessao else None
            cur_lo = b['l'] if em_sessao else None
            bloqueado_hoje = False
            pnl_dia0 = realizado
        elif em_sessao:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])

        chave_seg = None
        if dow == 6 and m >= DOM_NOITE_INICIO:
            chave_seg = (dt + timedelta(days=1)).strftime('%Y-%m-%d')
        elif dow == 0 and m < SESSAO_INICIO:
            chave_seg = d
        if chave_seg is not None:
            if chave_seg != on_key:
                on_key, on_hi, on_lo = chave_seg, b['h'], b['l']
            else:
                on_hi = max(on_hi, b['h']); on_lo = min(on_lo, b['l'])

        if not (ANALISE_INICIO <= d <= ANALISE_FIM):
            continue

        # ---- gestao de posicao aberta (checagem por range da barra, igual ao motor atual) ----
        if pos != 0:
            saiu = False
            if pos > 0:
                if b['l'] <= stop: fecha(stop); saiu = True
                elif b['h'] >= alvo: fecha(alvo); saiu = True
            else:
                if b['h'] >= stop: fecha(stop); saiu = True
                elif b['l'] <= alvo: fecha(alvo); saiu = True
            if not saiu and pos != 0:
                if pos > 0:
                    fav = max(fav, b['h'])
                    if not be_feito and (fav - entry) >= PTS_BE_TRIG:
                        stop = max(stop, entry + PTS_BE_LOCK); be_feito = True
                    if be_feito: stop = max(stop, fav - PTS_TRAIL)
                else:
                    fav = min(fav, b['l'])
                    if not be_feito and (entry - fav) >= PTS_BE_TRIG:
                        stop = min(stop, entry - PTS_BE_LOCK); be_feito = True
                    if be_feito: stop = min(stop, fav + PTS_TRAIL)
            if saiu:
                trades_por_dia[d] = trades_por_dia.get(d, 0) + 1
                if STOP_DIA_PT > 0 and (realizado - pnl_dia0) <= -STOP_DIA_PT:
                    bloqueado_hoje = True
            continue  # uma barra so gerencia OU procura entrada, nunca as duas

        if bloqueado_hoje or not (SESSAO_INICIO <= m < ENTRADA_FIM):
            continue
        if pd_hi is None or pd_lo is None:
            continue

        if dow == 0 and on_key == d and on_hi is not None and on_hi > 0:
            n_hi, n_lo = on_hi, on_lo
        else:
            n_hi, n_lo = pd_hi, pd_lo

        ev = avalia_bar(b, n_hi, n_lo, tol_pts, max_dist)
        if ev is not None and ev['cat'] == 'OPEROU':
            entry = b['c']; fav = entry; be_feito = False
            if ev['lado'] == 'SHORT':
                pos = -1; stop = entry + PTS_SL; alvo = entry - PTS_TP
            else:
                pos = 1; stop = entry - PTS_SL; alvo = entry + PTS_TP

    dias_uteis = sorted({b['dt'].strftime('%Y-%m-%d') for b in bars5m
                          if ANALISE_INICIO <= b['dt'].strftime('%Y-%m-%d') <= ANALISE_FIM
                          and b['dt'].weekday() < 5})
    dias_operados = sum(1 for d in dias_uteis if trades_por_dia.get(d, 0) > 0)
    dias_zerados = len(dias_uteis) - dias_operados
    total_trades = sum(trades_por_dia.values())
    return dias_operados, dias_zerados, total_trades


# ===================== MAIN =====================
def main():
    print("Carregando NQ_dados/*.txt (1min) ...")
    bars1m = carregar_1min(PASTA_DADOS)
    print(f"  {len(bars1m):,} candles de 1min carregados "
          f"({bars1m[0]['dt'].date()} a {bars1m[-1]['dt'].date()})")

    print("Agregando para 5min ...")
    bars5m = resample_5min(bars1m)
    print(f"  {len(bars5m):,} candles de 5min\n")

    # ---------------- PARTE 2 ----------------
    print("=" * 100)
    print("PARTE 2 — DIAGNOSTICO DOS DIAS ZERADOS (junho/2026, config de producao: "
          f"tol={TOL_TICKS_PROD}t/{TOL_TICKS_PROD*TICK}pt, maxDist={MAX_DIST_PROD}pt)")
    print("=" * 100)

    dias = diagnostica(bars5m, TOL_TICKS_PROD, MAX_DIST_PROD)
    linhas, contagem, dias_operados = gera_relatorio_parte2(dias)

    print(f"\n{'Data':<12}{'Portao':<8}{'Fonte':<18}{'Motivo'}")
    print("-" * 100)
    for l in linhas:
        marca = " *PEDIDO*" if l['Pedido'] else ""
        print(f"{l['Data']:<12}{l['Portao']:<8}{l['Fonte']:<18}{l['Motivo']}{marca}")

    total_zerados = sum(contagem.values())
    print("\n--- RESUMO ---")
    print(f"Dias operados:              {dias_operados}")
    print(f"Dias zerados (total):       {total_zerados}")
    print(f"  P1 (nunca tocou):         {contagem['P1_NUNCA_TOCOU']} dias")
    print(f"  P2 (rompeu, sem rejeicao):{contagem['P2_ROMPEU']:>4} dias")
    print(f"  P3 (rejeitou mas chase):  {contagem['P3_CHASE']} dias")

    # checa se os dias pedidos explicitamente foram todos encontrados
    achados = {l['Data'] for l in linhas}
    faltando = [d for d in DIAS_PEDIDOS
                if datetime.strptime(d, '%Y-%m-%d').strftime('%d/%m/%Y') not in achados
                and d not in {dd for dd, r in dias.items() if classifica_dia(r)[0] == 'OPEROU'}]
    if faltando:
        print(f"\n⚠️  Dias pedidos nao encontrados no dataset ou fora da janela: {faltando}")

    csv_path2 = os.path.join(SAIDA_DIR, 'diagnostico_portoes_junho.csv')
    with open(csv_path2, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['Data', 'Portao', 'Motivo', 'nHi', 'nLo',
                                           'MaxChegou', 'MinChegou', 'Fonte', 'Pedido'])
        w.writeheader()
        w.writerows(linhas)
    print(f"\nCSV salvo em: {csv_path2}")

    # ---------------- PARTE 3 ----------------
    print("\n" + "=" * 100)
    print("PARTE 3 — ANALISE DE SENSIBILIDADE (junho/2026)")
    print("=" * 100)

    tol_vals = [10, 15, 20, 25, 30]
    dist_vals = [10, 12, 15, 18, 20, 25]

    print(f"\n--- Variando TolToqueTicks (MaxDistPontos fixo em {MAX_DIST_PROD}pt) ---")
    print(f"{'TolTicks':<10}{'TolPts':<8}{'DiasOperados':<14}{'DiasZerados':<13}{'Trades':<8}")
    linhas_sens = []
    for t in tol_vals:
        do_, dz_, tr_ = simula(bars5m, t, MAX_DIST_PROD)
        print(f"{t:<10}{t*TICK:<8}{do_:<14}{dz_:<13}{tr_:<8}")
        linhas_sens.append({'Parametro': 'TolToqueTicks', 'Valor': t, 'ValorPts': t*TICK,
                             'MaxDistPontos': MAX_DIST_PROD, 'DiasOperados': do_,
                             'DiasZerados': dz_, 'Trades': tr_})

    print(f"\n--- Variando MaxDistPontos (TolToqueTicks fixo em {TOL_TICKS_PROD}) ---")
    print(f"{'MaxDist':<10}{'DiasOperados':<14}{'DiasZerados':<13}{'Trades':<8}")
    for md in dist_vals:
        do_, dz_, tr_ = simula(bars5m, TOL_TICKS_PROD, md)
        print(f"{md:<10}{do_:<14}{dz_:<13}{tr_:<8}")
        linhas_sens.append({'Parametro': 'MaxDistPontos', 'Valor': md, 'ValorPts': md,
                             'TolToqueTicks': TOL_TICKS_PROD, 'DiasOperados': do_,
                             'DiasZerados': dz_, 'Trades': tr_})

    csv_path3 = os.path.join(SAIDA_DIR, 'sensibilidade_portoes_junho.csv')
    campos = ['Parametro', 'Valor', 'ValorPts', 'MaxDistPontos', 'TolToqueTicks',
              'DiasOperados', 'DiasZerados', 'Trades']
    with open(csv_path3, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for l in linhas_sens:
            w.writerow({k: l.get(k, '') for k in campos})
    print(f"\nCSV salvo em: {csv_path3}")


if __name__ == '__main__':
    main()
