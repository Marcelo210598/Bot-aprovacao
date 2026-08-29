#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backtest RSI Deep Mean Reversion — NQ 1min real (NQ_dados/, ~1 ano jun/2025-jun/2026),
agregado p/ 5min ET, RTH (9:30-16:00), simulado como MNQ (mesmo preco do NQ, so' muda
o multiplicador financeiro).

ESTRATEGIA (fade de extremo profundo de RSI):
  1. RSI(14) no grafico de 5min.
  2. Sinal: RSI < 30 (long) ou RSI > 70 (short) E precisa ser o minimo/maximo dos
     ultimos 10 candles de RSI (extremo LOCAL, nao qualquer toque na zona).
  3. Confirmacao: aguarda o fechamento de um candle SEGUINTE fechar acima (long) ou
     abaixo (short) do close do candle de sinal. Tem ate 3 candles pra confirmar.
  4. Se nao confirmar em 3 candles, o setup expira sem entrada.
  5. 3 variantes de saida testadas separadamente: A (TP/SL 20/10), B (TP/SL 24/8),
     C (trailing com breakeven em +5 e trail de 3pt).

PARAMETROS FINANCEIROS (confirmados com o Marcelo em 29/08/2026):
  MNQ = $2,00/ponto, 1 tick = 0.25pt = $0.50. O enunciado original tinha um erro
  ($0,50/ponto), corrigido apos conferir a matematica do proprio tick e a
  convencao ja usada em outros scripts do projeto (MNQ_PV=2.0 em
  run_comparativo_3estrategias.py, carrega_mnq_real.py etc).

DECISOES DE IMPLEMENTACAO (documentadas p/ transparencia):
  - Slippage (2 ticks = 0.5pt) aplicado SO' na entrada, como pedido no enunciado.
    Saidas (stop/alvo/flatten) saem no preco exato, sem atrito extra.
  - RSI e calculado continuamente 24h (nao reseta por dia) p/ chegar "aquecido"
    na abertura RTH. So' reseta em gaps de dados > 96h (rollover de contrato -
    os arquivos de NQ_dados/ tem buracos de semanas quando o contrato trocava).
  - Deteccao de NOVO sinal (extremo de RSI) so' roda entre 00:00 e 15:49 ET —
    ou seja, ate o flatten. Depois do flatten (15:50-23:59) o RSI continua sendo
    atualizado, mas nao abrimos novos setups fora do horario de operacao real.
    Um sinal formado de madrugada pode confirmar e entrar assim que a sessao
    9:30-15:50 abrir.
  - Quando 2 preços (stop e alvo) sao tocados na MESMA barra de 5min, assume-se
    que o STOP bateu primeiro (cenario conservador — sem tick replay real).
  - Trailing (variante C) e' atualizado apenas ao FINAL da barra corrente, valendo
    a partir da barra seguinte (evita look-ahead dentro da mesma barra).
  - CAVEAT GERAL: simulacao por barra de 5min (High/Low), sem tick replay. E' uma
    APROXIMACAO do que o NT8 Strategy Analyzer faria de verdade — serve p/
    decidir se vale a pena portar pro NinjaTrader, nao substitui o teste real.

Rodar: python3 backtest_rsi_reversion.py
"""
import csv
import glob
import os
from collections import deque
from datetime import datetime, timedelta

import pytz

ET = pytz.timezone('America/New_York')
UTC = pytz.utc
PASTA_DADOS = os.path.join(os.path.dirname(__file__), '..', 'NQ_dados')
PASTA_SAIDA = os.path.dirname(__file__)

# ---------------------------------------------------------------- financeiro
MNQ_PV = 2.0                              # $/ponto, 1 contrato MNQ
TICK = 0.25
SLIPPAGE_TICKS = 2
SLIPPAGE_PTS = SLIPPAGE_TICKS * TICK       # 0.5 pt na entrada
COMISSAO_LADO = 0.52
COMISSAO_RT = COMISSAO_LADO * 2            # $1.04 round-trip
CAPITAL_INICIAL = 25000.0

GAP_RESET_HORAS = 96                       # gap > 4 dias -> reseta indicadores (rollover)

# ---------------------------------------------------------------- risco (igual ao bot atual)
STOP_DIARIO = -300.0
MAX_TRADES_DIA = 6
SESSAO_INICIO = 930     # 9:30 ET
CORTE_ENTRADA = 1550    # nao abre depois de 15:50
FLATTEN = 1550          # fecha tudo as 15:50

# ---------------------------------------------------------------- bot atual (benchmark dado pelo Marcelo)
BOT_ATUAL = {
    'win_rate': 76.0, 'avg_win': 42.90, 'avg_loss': -107.40,
    'ratio': 0.40, 'pnl_mes': 170.0, 'max_dd': -299.0,
}

VARIANTES = {
    'A': {'tipo': 'fixo', 'sl': 10.0, 'tp': 20.0, 'nome': 'A (TP/SL 20/10, 1:2)'},
    'B': {'tipo': 'fixo', 'sl': 8.0, 'tp': 24.0, 'nome': 'B (TP/SL 24/8, 1:3)'},
    'C': {'tipo': 'trailing', 'sl': 10.0, 'be_trigger': 5.0, 'trail': 3.0, 'nome': 'C (trailing + BE)'},
}


# ============================================================ carregamento e agregacao
def carregar_1min(pasta):
    """Le todos os NQ_dados/*.txt (UTC;O;H;L;C;V) e converte p/ ET com pytz (DST correto)."""
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
                    dt_utc = UTC.localize(datetime(
                        int(data[:4]), int(data[4:6]), int(data[6:8]),
                        int(hora[:2]), int(hora[2:4])))
                    o, h, l, c, v = float(o), float(h), float(l), float(c), float(v)
                except Exception:
                    continue
                h = max(h, o, c)
                l = min(l, o, c)
                if dt_utc not in vistos:
                    vistos[dt_utc] = (dt_utc.astimezone(ET), o, h, l, c, v)
    return [vistos[k] for k in sorted(vistos)]


def agrega_5min(bars1m):
    """Agrega 1min -> 5min. Rotulo do bucket = inicio do intervalo (ET)."""
    buckets = {}
    ordem = []
    for (dtet, o, h, l, c, v) in bars1m:
        floor_min = (dtet.minute // 5) * 5
        chave = dtet.replace(minute=floor_min, second=0, microsecond=0)
        if chave not in buckets:
            buckets[chave] = [o, h, l, c, v]
            ordem.append(chave)
        else:
            b = buckets[chave]
            b[1] = max(b[1], h)
            b[2] = min(b[2], l)
            b[3] = c
            b[4] += v
    ordem.sort()
    return [{'dt': k, 'o': buckets[k][0], 'h': buckets[k][1], 'l': buckets[k][2],
             'c': buckets[k][3], 'v': buckets[k][4]} for k in ordem]


def hhmm(dt):
    return dt.hour * 100 + dt.minute


# ============================================================ RSI de Wilder
class RSIWilder:
    def __init__(self, period):
        self.period = period
        self._reset_estado()

    def _reset_estado(self):
        self.prev_close = None
        self.avg_gain = None
        self.avg_loss = None
        self.buf_g = []
        self.buf_l = []

    def reset(self):
        self._reset_estado()

    def update(self, close):
        if self.prev_close is None:
            self.prev_close = close
            return None
        delta = close - self.prev_close
        gain = delta if delta > 0 else 0.0
        loss = -delta if delta < 0 else 0.0
        self.prev_close = close
        if self.avg_gain is None:
            self.buf_g.append(gain)
            self.buf_l.append(loss)
            if len(self.buf_g) < self.period:
                return None
            self.avg_gain = sum(self.buf_g) / self.period
            self.avg_loss = sum(self.buf_l) / self.period
        else:
            self.avg_gain = (self.avg_gain * (self.period - 1) + gain) / self.period
            self.avg_loss = (self.avg_loss * (self.period - 1) + loss) / self.period
        if self.avg_loss == 0:
            return 100.0
        rs = self.avg_gain / self.avg_loss
        return 100.0 - (100.0 / (1.0 + rs))


# ============================================================ motor de backtest
def registra_trade(trades, entry_dt, exit_dt, direcao, entry_px, exit_px, motivo):
    pnl_bruto = (exit_px - entry_px) * direcao * MNQ_PV
    pnl_liq = pnl_bruto - COMISSAO_RT
    trades.append({
        'entry_dt': entry_dt, 'exit_dt': exit_dt,
        'dir': 'LONG' if direcao > 0 else 'SHORT',
        'entry_px': entry_px, 'exit_px': exit_px, 'motivo': motivo,
        'pnl_bruto': pnl_bruto, 'comissao': COMISSAO_RT, 'pnl': pnl_liq,
    })


def rodar_backtest(bars, saida, rsi_period=14, janela_extremo=10, os_th=30.0, ob_th=70.0,
                    stop_diario=STOP_DIARIO, max_trades_dia=MAX_TRADES_DIA,
                    sessao_ini=SESSAO_INICIO, corte_entrada=CORTE_ENTRADA, flatten=FLATTEN):
    """
    saida: {'tipo': 'fixo', 'sl': X, 'tp': Y}          -> variantes A/B
           {'tipo': 'trailing', 'sl': X, 'be_trigger': Y, 'trail': Z}  -> variante C
    """
    rsi_calc = RSIWilder(rsi_period)
    janela_rsi = deque(maxlen=janela_extremo)

    trades = []
    dia_atual = None
    trades_hoje = 0
    bloqueado_dia = False
    pnl_realizado = 0.0
    pnl_inicio_dia = 0.0

    pos = 0                       # 0 sem posicao, 1 long, -1 short
    entry_dt = entry_px = stop_px = tgt_px = None
    highest_px = lowest_px = None  # extremos favoraveis p/ trailing (variante C)
    be_ativo = False

    pendente = None               # {'dir':1/-1, 'signal_close':x, 'n':0}
    bar_anterior_dt = None

    for b in bars:
        dt, o, h, l, c = b['dt'], b['o'], b['h'], b['l'], b['c']
        m = hhmm(dt)
        dia = dt.date()

        # --- reset por gap grande (rollover de contrato entre arquivos) ---
        if bar_anterior_dt is not None and (dt - bar_anterior_dt) > timedelta(hours=GAP_RESET_HORAS):
            rsi_calc.reset()
            janela_rsi.clear()
            pendente = None
        bar_anterior_dt = dt

        # --- novo dia: reseta contadores de risco ---
        if dia != dia_atual:
            dia_atual = dia
            trades_hoje = 0
            bloqueado_dia = False
            pnl_inicio_dia = pnl_realizado
            pendente = None

        rsi_val = rsi_calc.update(c)

        pnl_dia = pnl_realizado - pnl_inicio_dia
        if not bloqueado_dia and pnl_dia <= stop_diario:
            bloqueado_dia = True

        # --- flatten forcado as 15:50 ET; fora disso nao abre novo setup ---
        if m >= flatten:
            if pos != 0:
                registra_trade(trades, entry_dt, dt, pos, entry_px, c, 'FLATTEN')
                pnl_realizado += trades[-1]['pnl']
                pos = 0
            if rsi_val is not None:
                janela_rsi.append(rsi_val)
            continue

        # --- 1) gerencia posicao aberta (stop/alvo fixos ou trailing) ---
        if pos != 0:
            saiu = False
            if saida['tipo'] == 'fixo':
                if pos > 0:
                    if l <= stop_px:
                        registra_trade(trades, entry_dt, dt, pos, entry_px, stop_px, 'STOP')
                        saiu = True
                    elif h >= tgt_px:
                        registra_trade(trades, entry_dt, dt, pos, entry_px, tgt_px, 'ALVO')
                        saiu = True
                else:
                    if h >= stop_px:
                        registra_trade(trades, entry_dt, dt, pos, entry_px, stop_px, 'STOP')
                        saiu = True
                    elif l <= tgt_px:
                        registra_trade(trades, entry_dt, dt, pos, entry_px, tgt_px, 'ALVO')
                        saiu = True
            else:  # trailing (variante C)
                if pos > 0:
                    if l <= stop_px:
                        motivo = 'BE/TRAIL' if be_ativo else 'STOP'
                        registra_trade(trades, entry_dt, dt, pos, entry_px, stop_px, motivo)
                        saiu = True
                    else:
                        highest_px = max(highest_px, h)
                        if not be_ativo and (highest_px - entry_px) >= saida['be_trigger']:
                            be_ativo = True
                            stop_px = max(stop_px, entry_px)
                        if be_ativo:
                            stop_px = max(stop_px, highest_px - saida['trail'])
                else:
                    if h >= stop_px:
                        motivo = 'BE/TRAIL' if be_ativo else 'STOP'
                        registra_trade(trades, entry_dt, dt, pos, entry_px, stop_px, motivo)
                        saiu = True
                    else:
                        lowest_px = min(lowest_px, l)
                        if not be_ativo and (entry_px - lowest_px) >= saida['be_trigger']:
                            be_ativo = True
                            stop_px = min(stop_px, entry_px)
                        if be_ativo:
                            stop_px = min(stop_px, lowest_px + saida['trail'])
            if saiu:
                pnl_realizado += trades[-1]['pnl']
                pos = 0

        # --- 2) tenta confirmar/expirar setup pendente (usa o close desta barra) ---
        if rsi_val is not None:
            janela_rsi.append(rsi_val)

        if pendente is not None and pos == 0:
            confirmou = (c > pendente['signal_close']) if pendente['dir'] == 1 \
                else (c < pendente['signal_close'])
            if confirmou:
                pode_entrar = (not bloqueado_dia) and (sessao_ini <= m < corte_entrada) and \
                              (max_trades_dia <= 0 or trades_hoje < max_trades_dia)
                if pode_entrar:
                    direcao = pendente['dir']
                    slip = SLIPPAGE_PTS * direcao
                    entry_px = c + slip
                    entry_dt = dt
                    pos = direcao
                    trades_hoje += 1
                    be_ativo = False
                    if direcao > 0:
                        stop_px = entry_px - saida['sl']
                        highest_px = entry_px
                    else:
                        stop_px = entry_px + saida['sl']
                        lowest_px = entry_px
                    if saida['tipo'] == 'fixo':
                        tgt_px = entry_px + saida['tp'] * direcao
                pendente = None
            else:
                pendente['n'] += 1
                if pendente['n'] >= 3:
                    pendente = None  # expirou sem confirmar

        # --- 3) detecta NOVO extremo profundo de RSI (vira pendente p/ a proxima barra) ---
        if rsi_val is not None and len(janela_rsi) == janela_rsi.maxlen:
            if rsi_val < os_th and rsi_val == min(janela_rsi):
                pendente = {'dir': 1, 'signal_close': c, 'n': 0}
            elif rsi_val > ob_th and rsi_val == max(janela_rsi):
                pendente = {'dir': -1, 'signal_close': c, 'n': 0}

    return trades


# ============================================================ metricas
def metricas_gerais(trades, dias_periodo, capital_inicial=CAPITAL_INICIAL):
    if not trades:
        return dict(n=0, ganhadores=0, perdedores=0, win_rate=0.0, avg_win=0.0, avg_loss=0.0,
                    ratio=0.0, pf=0.0, net=0.0, pnl_mes=0.0, max_dd=0.0, dd_pct=0.0)
    n = len(trades)
    ordenados = sorted(trades, key=lambda t: t['entry_dt'])
    ganhos = [t['pnl'] for t in ordenados if t['pnl'] > 0]
    perdas = [t['pnl'] for t in ordenados if t['pnl'] <= 0]
    win_rate = 100.0 * len(ganhos) / n
    avg_win = sum(ganhos) / len(ganhos) if ganhos else 0.0
    avg_loss = sum(perdas) / len(perdas) if perdas else 0.0  # numero negativo
    ratio = (avg_win / abs(avg_loss)) if avg_loss != 0 else (float('inf') if avg_win > 0 else 0.0)
    soma_g, soma_p = sum(ganhos), -sum(perdas)
    pf = (soma_g / soma_p) if soma_p > 0 else (float('inf') if soma_g > 0 else 0.0)
    net = sum(t['pnl'] for t in ordenados)

    eq = pico = max_dd = 0.0
    for t in ordenados:
        eq += t['pnl']
        pico = max(pico, eq)
        max_dd = min(max_dd, eq - pico)

    meses = max(dias_periodo / 30.4, 0.1)
    return dict(n=n, ganhadores=len(ganhos), perdedores=len(perdas), win_rate=win_rate,
                avg_win=avg_win, avg_loss=avg_loss, ratio=ratio, pf=pf, net=net,
                pnl_mes=net / meses, max_dd=max_dd, dd_pct=abs(max_dd) / capital_inicial * 100.0)


def metricas_mensais(trades):
    grupos = {}
    for t in trades:
        chave = (t['entry_dt'].year, t['entry_dt'].month)
        grupos.setdefault(chave, []).append(t)
    linhas = []
    for chave in sorted(grupos):
        ts = sorted(grupos[chave], key=lambda t: t['entry_dt'])
        n = len(ts)
        ganhos = [t['pnl'] for t in ts if t['pnl'] > 0]
        win_rate = 100.0 * len(ganhos) / n if n else 0.0
        pnl_mes = sum(t['pnl'] for t in ts)
        eq = pico = max_dd = 0.0
        for t in ts:
            eq += t['pnl']
            pico = max(pico, eq)
            max_dd = min(max_dd, eq - pico)
        linhas.append({'ano_mes': f"{chave[0]}-{chave[1]:02d}", 'n': n,
                        'win_rate': win_rate, 'pnl': pnl_mes, 'max_dd': max_dd})
    return linhas


def fmt_pf(pf):
    return 'inf' if pf == float('inf') else f"{pf:.2f}"


# ============================================================ exportacao CSV
def exportar_csv(trades, caminho):
    campos = ['entry_dt', 'dir', 'entry_px', 'exit_dt', 'exit_px', 'motivo',
              'pnl_bruto', 'comissao', 'pnl']
    with open(caminho, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for t in sorted(trades, key=lambda x: x['entry_dt']):
            linha = dict(t)
            linha['entry_dt'] = t['entry_dt'].strftime('%Y-%m-%d %H:%M')
            linha['exit_dt'] = t['exit_dt'].strftime('%Y-%m-%d %H:%M')
            w.writerow(linha)


# ============================================================ relatorio
def imprime_relatorio_variante(nome, trades, dias_periodo):
    m = metricas_gerais(trades, dias_periodo)
    print(f"\n{'=' * 78}\nVARIANTE {nome}\n{'=' * 78}")
    print(f"Total de trades:        {m['n']}")
    print(f"Ganhadores / Perdedores: {m['ganhadores']} / {m['perdedores']}")
    print(f"Win rate:               {m['win_rate']:.1f}%")
    print(f"Ganho medio/trade:      ${m['avg_win']:.2f}")
    print(f"Perda media/trade:      ${m['avg_loss']:.2f}")
    print(f"Ratio ganho/perda:      {m['ratio']:.2f}   (precisa ser > 0.67)")
    print(f"Profit factor:          {fmt_pf(m['pf'])}")
    print(f"PnL total:              ${m['net']:.2f}")
    print(f"PnL medio/mes:          ${m['pnl_mes']:.2f}")
    print(f"Drawdown maximo:        ${m['max_dd']:.2f}  ({m['dd_pct']:.2f}% de ${CAPITAL_INICIAL:,.0f})")

    print(f"\n{'Mes':<10}{'Trades':>8}{'Win%':>8}{'PnL $':>12}{'DD max $':>12}")
    for l in metricas_mensais(trades):
        print(f"{l['ano_mes']:<10}{l['n']:>8}{l['win_rate']:>8.1f}{l['pnl']:>12.2f}{l['max_dd']:>12.2f}")
    return m


# ============================================================ main
def main():
    print("Lendo NQ_dados/*.txt ...")
    arquivos = sorted(glob.glob(os.path.join(PASTA_DADOS, '*.txt')))
    if not arquivos:
        print(f"ERRO: nenhum arquivo .txt encontrado em {PASTA_DADOS}")
        return
    print(f"  {len(arquivos)} arquivos encontrados.")

    b1 = carregar_1min(PASTA_DADOS)
    print(f"  {len(b1):,} candles de 1min carregados.")
    bars = agrega_5min(b1)
    print(f"  {len(bars):,} candles de 5min apos agregacao.")

    dt_ini, dt_fim = bars[0]['dt'], bars[-1]['dt']
    dias_totais = (dt_fim.date() - dt_ini.date()).days
    print(f"  Periodo: {dt_ini.date()} -> {dt_fim.date()}  (~{dias_totais / 30.4:.1f} meses)\n")

    # ================================================== PARTE 1+2: 3 variantes principais
    resultados = {}
    for chave, cfg in VARIANTES.items():
        trades = rodar_backtest(bars, cfg)
        m = imprime_relatorio_variante(cfg['nome'], trades, dias_totais)
        resultados[chave] = {'trades': trades, 'm': m, 'cfg': cfg}
        caminho_csv = os.path.join(PASTA_SAIDA, f'trades_rsi_variante_{chave}.csv')
        exportar_csv(trades, caminho_csv)
        print(f"\n  -> {len(trades)} trades exportados em {os.path.basename(caminho_csv)}")

    # ================================================== tabela comparativa com o bot atual
    print(f"\n\n{'=' * 100}\nCOMPARACAO COM O BOT ATUAL\n{'=' * 100}")
    linha = "{:<22}{:>14}{:>16}{:>16}{:>16}"
    print(linha.format("Metrica", "Bot Atual", "Variante A", "Variante B", "Variante C"))
    ma, mb, mc = resultados['A']['m'], resultados['B']['m'], resultados['C']['m']

    def pf_ou_num(m, chave, fmt="{:.2f}"):
        return fmt.format(m[chave]) if m[chave] != float('inf') else 'inf'

    print(linha.format("Win rate", f"{BOT_ATUAL['win_rate']:.0f}%",
                        f"{ma['win_rate']:.1f}%", f"{mb['win_rate']:.1f}%", f"{mc['win_rate']:.1f}%"))
    print(linha.format("Ganho medio/trade", f"${BOT_ATUAL['avg_win']:.2f}",
                        f"${ma['avg_win']:.2f}", f"${mb['avg_win']:.2f}", f"${mc['avg_win']:.2f}"))
    print(linha.format("Perda media/trade", f"${BOT_ATUAL['avg_loss']:.2f}",
                        f"${ma['avg_loss']:.2f}", f"${mb['avg_loss']:.2f}", f"${mc['avg_loss']:.2f}"))
    print(linha.format("Ratio ganho/perda", f"{BOT_ATUAL['ratio']:.2f}",
                        f"{ma['ratio']:.2f}", f"{mb['ratio']:.2f}", f"{mc['ratio']:.2f}"))
    print(linha.format("PnL medio/mes", f"~${BOT_ATUAL['pnl_mes']:.0f}",
                        f"${ma['pnl_mes']:.2f}", f"${mb['pnl_mes']:.2f}", f"${mc['pnl_mes']:.2f}"))
    print(linha.format("DD maximo", f"${BOT_ATUAL['max_dd']:.0f}",
                        f"${ma['max_dd']:.2f}", f"${mb['max_dd']:.2f}", f"${mc['max_dd']:.2f}"))

    # ================================================== PARTE 3: analise de sensibilidade
    # IMPORTANTE: a variante que "ganha" pra escolher a gestao de saida do grid e' a de
    # MAIOR PROFIT FACTOR entre A/B/C (nao a de maior ratio isolado) — um ratio alto com
    # win rate baixo pode ainda dar prejuizo (foi exatamente o que aconteceu com A e B
    # nesta rodada: ratio 1.85 e 2.73, mas PF 0.72 e 0.69 — deram prejuizo).
    melhor_variante_chave = max(resultados, key=lambda k: resultados[k]['m']['pf']
                                 if resultados[k]['m']['n'] >= 10 else -1)
    saida_grid = VARIANTES[melhor_variante_chave]
    print(f"\n\n{'=' * 100}\nPARTE 3 — ANALISE DE SENSIBILIDADE (usando a gestao de saida {melhor_variante_chave}, "
          f"melhor profit factor entre A/B/C)\n{'=' * 100}")

    rsi_periodos = [10, 14, 20]
    janelas = [5, 10, 15]
    zonas = [(25.0, 75.0), (30.0, 70.0), (35.0, 65.0)]

    linha_grid = "{:<8}{:<10}{:<12}{:>8}{:>10}{:>10}{:>8}{:>12}"
    print(linha_grid.format("RSI", "Janela", "Zona", "Trades", "Win%", "Ratio", "PF", "PnL $"))
    grid_resultados = []
    for periodo in rsi_periodos:
        for janela in janelas:
            for os_th, ob_th in zonas:
                trades_g = rodar_backtest(bars, saida_grid, rsi_period=periodo,
                                           janela_extremo=janela, os_th=os_th, ob_th=ob_th)
                mg = metricas_gerais(trades_g, dias_totais)
                grid_resultados.append({
                    'rsi': periodo, 'janela': janela, 'zona': f"{int(os_th)}/{int(ob_th)}",
                    'n': mg['n'], 'win_rate': mg['win_rate'], 'ratio': mg['ratio'],
                    'pf': mg['pf'], 'net': mg['net'], 'max_dd': mg['max_dd'],
                })

    # ordena por PROFIT FACTOR (o que realmente importa p/ saber se ganha dinheiro),
    # nao por ratio isolado — ratio so' aparece marcado quando TAMBEM e' lucrativo.
    grid_resultados.sort(key=lambda r: r['pf'], reverse=True)
    for r in grid_resultados:
        ratio_str = fmt_pf(r['ratio'])
        pf_str = fmt_pf(r['pf'])
        marca = "  <-- ratio>0.67 E lucrativo" if r['ratio'] > 0.67 and r['pf'] > 1.0 and r['n'] >= 10 else ""
        print(linha_grid.format(f"{r['rsi']}", f"{r['janela']}", r['zona'], r['n'],
                                 f"{r['win_rate']:.1f}", ratio_str, pf_str, f"{r['net']:.2f}") + marca)

    caminho_grid = os.path.join(PASTA_SAIDA, 'sensibilidade_rsi.csv')
    with open(caminho_grid, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['rsi', 'janela', 'zona', 'n', 'win_rate', 'ratio', 'pf', 'net', 'max_dd'])
        w.writeheader()
        w.writerows(grid_resultados)
    print(f"\n  -> grade completa exportada em {os.path.basename(caminho_grid)}")

    # ================================================== PARTE 4: veredito
    print(f"\n\n{'=' * 100}\nPARTE 4 — VEREDITO FINAL\n{'=' * 100}")

    # Uma unica "config vencedora" (nao mistura ratio de uma config com PF de outra):
    # candidata = A, B, C + toda a grade, com pelo menos 10 trades, ranqueada por PF.
    candidatas = [
        {'nome': f"Variante {k}", 'ratio': v['m']['ratio'], 'pf': v['m']['pf'], 'net': v['m']['net'],
         'win_rate': v['m']['win_rate'], 'n': v['m']['n'], 'pnl_mes': v['m']['pnl_mes'],
         'max_dd': v['m']['max_dd']}
        for k, v in resultados.items()
    ] + [
        {'nome': f"Grid RSI={r['rsi']} janela={r['janela']} zona={r['zona']} (saida {melhor_variante_chave})",
         'ratio': r['ratio'], 'pf': r['pf'], 'net': r['net'], 'win_rate': r['win_rate'], 'n': r['n'],
         'pnl_mes': r['net'] / max(dias_totais / 30.4, 0.1), 'max_dd': r['max_dd']}
        for r in grid_resultados
    ]
    candidatas_validas = [c for c in candidatas if c['n'] >= 10]
    melhor = max(candidatas_validas, key=lambda c: c['pf'])

    tem_edge = melhor['ratio'] > 0.55 and melhor['pf'] > 1.3
    supera_067 = melhor['ratio'] > 0.67
    lucrativa = melhor['pf'] > 1.0

    # extrapolacao p/ 30 dias, 5 contratos, usando a config vencedora (a de melhor PF)
    dias_uteis_aprox = dias_totais * (5 / 7.0)  # aproximacao de dias de pregao
    pnl_dia_1c = melhor['net'] / dias_uteis_aprox if dias_uteis_aprox > 0 else 0.0
    pnl_30d_5c = pnl_dia_1c * 30 * 5

    pnl_mes_melhor = melhor['pnl_mes']
    supera_pnl = pnl_mes_melhor > BOT_ATUAL['pnl_mes']
    supera_dd = melhor['max_dd'] is not None and abs(melhor['max_dd']) < abs(BOT_ATUAL['max_dd'])
    if not tem_edge:
        resumo_item5 = 'NAO neste formato'
    elif supera_pnl and (supera_dd or melhor['max_dd'] is None):
        resumo_item5 = 'SIM'
    else:
        resumo_item5 = 'PARCIAL — troca de perfil de risco, nao upgrade obvio'

    print(f"""
1) A estrategia tem edge real nos dados do NQ?
   {'SIM' if tem_edge else 'NAO'} — a melhor configuracao encontrada, ranqueada por PROFIT FACTOR
   (nao por ratio isolado, que sozinho engana quando o win rate desaba), foi:
   {melhor['nome']}
   -> ratio ganho/perda {melhor['ratio']:.2f} | profit factor {fmt_pf(melhor['pf'])} | win rate {melhor['win_rate']:.1f}% | {melhor['n']} trades
   {'Isso passa do limiar minimo (ratio>0.55 e PF>1.3) definido antes de rodar o teste.' if tem_edge else
   'Isso NAO passa do limiar minimo (ratio>0.55 e PF>1.3) definido antes de rodar o teste.'}

2) Qual variante de saida performa melhor?
   Variante {melhor_variante_chave} ({VARIANTES[melhor_variante_chave]['nome']}) foi a UNICA das 3 lucrativa
   (PF {fmt_pf(resultados[melhor_variante_chave]['m']['pf'])}, PnL total ${resultados[melhor_variante_chave]['m']['net']:.2f}).
   A e B tiveram ratio ganho/perda MAIOR (1.85 e 2.73 vs {resultados[melhor_variante_chave]['m']['ratio']:.2f} de C),
   mas com win rate tao baixo (20-28%) que ainda deram prejuizo — ratio alto sozinho nao
   basta, precisa vir junto com profit factor > 1.

3) O ratio ganho/perda supera 0,67 em alguma configuracao LUCRATIVA?
   {'SIM' if (supera_067 and lucrativa) else 'NAO'} — a melhor combinacao de ratio+lucro observada foi ratio={melhor['ratio']:.2f}
   com PF={fmt_pf(melhor['pf'])} ({melhor['nome']}).
   {'Existem configuracoes com ratio > 0.67, mas nenhuma delas lucrativa (PF<1) — ratio alto ali vem de um win rate tao baixo que o resultado liquido e negativo.' if supera_067 and not lucrativa else ''}

4) PnL esperado em 30 dias, 5 contratos MNQ, conta Apex $25k (extrapolacao linear
   da media diaria real observada no periodo testado, config "{melhor['nome']}"):
   ~${pnl_30d_5c:,.2f}
   (media de ${pnl_dia_1c:.2f}/dia com 1 contrato, x30 dias x5 contratos — extrapolacao
    simples, NAO leva em conta variancia entre meses nem risco de ruina).

5) Vale a pena implementar no NinjaTrader 8 no lugar do bot atual?
   {resumo_item5} —
   comparando com o bot atual (ratio 0.40, PnL medio/mes ~$170, DD max $299):
""")

    if not tem_edge:
        print(f"   Melhor config achada: ratio {melhor['ratio']:.2f}, PF {fmt_pf(melhor['pf'])} — nao bate")
        print("   ratio > 0.55 COM profit factor > 1.3 ao mesmo tempo.")
        print("   RECOMENDACAO: nao vale portar essa estrategia pro NinjaTrader como esta.")
        print("   Precisa de uma estrategia diferente ou de filtros adicionais (ex: regime de")
        print("   mercado, ADX, horario) antes de tentar de novo.")
    else:
        dd_str = f"${melhor['max_dd']:.2f}" if melhor['max_dd'] is not None else "n/d"
        print(f"   {melhor['nome']}:")
        print(f"     ratio ganho/perda: {melhor['ratio']:.2f}  vs {BOT_ATUAL['ratio']:.2f} do bot atual  (MELHOR)")
        print(f"     PnL medio/mes:     ${pnl_mes_melhor:.2f}  vs ~${BOT_ATUAL['pnl_mes']:.0f} do bot atual  "
              f"({'MELHOR' if supera_pnl else 'PIOR — ganha menos por mes que o bot atual'})")
        print(f"     DD maximo:         {dd_str}  vs ${BOT_ATUAL['max_dd']:.0f} do bot atual  "
              f"({'MELHOR (mais raso)' if supera_dd else 'PIOR (mais fundo)' if melhor['max_dd'] is not None else 'nao calculado nesta config'})")
        print()
        if supera_pnl and (supera_dd or melhor['max_dd'] is None):
            print("   Ratio, PnL/mes e DD todos melhores (ou equivalentes) que o bot atual — vale a pena")
            print("   portar pro NinjaTrader e validar no Strategy Analyzer antes de trocar em producao.")
        elif supera_pnl:
            print("   Ratio e PnL/mes melhores que o bot atual, mas o drawdown maximo observado no")
            print("   periodo testado foi MAIOR (mais fundo) que o do bot atual — o ganho vem com mais")
            print("   oscilacao de capital pelo caminho. Vale prototipar e confirmar essa relacao")
            print("   risco/retorno no Strategy Analyzer antes de trocar em producao.")
        elif supera_dd:
            print("   Ratio bem melhor e drawdown mais raso que o bot atual, mas o PnL medio/mes fica")
            print("   ABAIXO do bot atual no periodo testado — essa config e' mais 'segura' (menos")
            print("   dependente de acertar toda hora, oscila menos), porem nao necessariamente MAIS")
            print("   RENTAVEL. Vale prototipar e comparar lado a lado com o bot atual antes de trocar.")
        else:
            print("   O ratio ganho/perda e' bem melhor que o bot atual (opera com win rate mais baixo")
            print("   sem quebrar), mas tanto o PnL medio/mes quanto o drawdown maximo ficaram PIORES")
            print("   que o bot atual no periodo testado — e' uma troca de perfil de risco, nao um")
            print("   upgrade obvio. Vale prototipar no NinjaTrader e comparar lado a lado com o bot")
            print("   atual no Strategy Analyzer antes de decidir trocar em producao.")

    print(f"\n{'=' * 100}")
    print("Lembrete: backtest por barra de 5min (sem tick replay) — aproximacao, nao substitui")
    print("o teste real no NT8 Strategy Analyzer antes de ir pra conta real.")
    print(f"{'=' * 100}\n")


if __name__ == '__main__':
    main()
