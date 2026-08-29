#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
COMPARATIVO DE ESTRATEGIAS (20/08) — pedido do Marcelo: testar as familias de
estrategia levantadas na pesquisa de 23/06 (docs/pesquisa-bots-nt8-apex.md),
SOZINHAS e MESCLADAS com o que ja temos (reversao PDH/PDL + ORB), tudo no
MESMO motor de gestao/aprovacao pra ser comparacao justa.

IMPORTANTE (leia antes de comparar com outros docs do projeto):
Pra isolar "o sinal de entrada e' melhor ou pior", todas as 4 estrategias abaixo
usam a MESMA gestao de saida do BotAprovacao (SL 12,5 / BE 3,75->2,5 fixo /
trailing 1,75 / alvo 60pt) e o MESMO motor de aprovacao (DD real $1000,
MaxTradesDia=12 dividido entre as fontes ativas, stop diario $750, slippage 2
ticks, 5 MNQ). Isso e' DIFERENTE do numero "+$2.766/ano" do ORB em
`run_orb_15min.py` (que usa SL/TP proprios, validados a parte) -- aqui o ORB
roda com a gestao da reversao, de proposito, pra comparar maca com maca.

Estrategias implementadas:
  REV  = reversao PDH/PDL (a que ja roda em producao)
  ORB  = opening range breakout 9h30-9h45 ET, entra no rompimento com
         confirmacao de fechamento fora do range
  EMAV = EMA9>20>50 alinhadas + Close vs VWAP diario + cruzamento do RSI14
         pela linha 50 (definicao citada na pesquisa de 23/06)
  ICT  = "ICT-lite": Fair Value Gap (gap de 3 candles) + retorno da linha ao
         gap com fechamento de rejeicao (continuacao) -- versao SIMPLIFICADA
         e MECANICA do conceito, nao e' o ICT ortodoxo completo. Documentado
         assim de proposito, pra nao inventar regra vaga.

Cada teste roda: 1 estrategia sozinha, e combinacoes (a fonte que sinalizar
primeiro na barra abre o trade; MaxTradesDia e' compartilhado entre as fontes
ativas, igual seria em producao rodando os bots juntos).
"""
import glob, os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import pandas as pd

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
MNQ_PV = 2.0; RT_PER = 1.20; N_CONTR = 5
MIN_DIAS = 7
TICK = 0.25
PTS_SL = 12.5; PTS_BE_TRIG = 3.75; PTS_BE_LOCK = 2.5; PTS_TRAIL = 1.75; TP = 60.0
MAX_DIST = 15.0; TOL_TICKS = 20
ENTRADA_INI = 9*60+30; ENTRADA_FIM = 16*60; FLATTEN = 16*60+55
ORB_FIM = 9*60+45   # range de abertura fecha aqui
SLIP_BASE = 2.0
META = 1500.0; DD = 1000.0; STOP_DIA = 750.0; MAX_TRADES = 12


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


# ============================== INDICADORES (EMA/VWAP/RSI) ==============================

def calcula_indicadores(bars):
    """EMA9/20/50, RSI14, VWAP diario (reset por dia ET). Retorna arrays paralelos a `bars`."""
    df = pd.DataFrame({'c': [b['c'] for b in bars],
                        'h': [b['h'] for b in bars],
                        'l': [b['l'] for b in bars],
                        'v': [b['v'] for b in bars],
                        'dia': [b['dt'].strftime('%Y-%m-%d') for b in bars]})
    df['ema9']  = df['c'].ewm(span=9,  adjust=False).mean()
    df['ema20'] = df['c'].ewm(span=20, adjust=False).mean()
    df['ema50'] = df['c'].ewm(span=50, adjust=False).mean()

    delta = df['c'].diff()
    ganho = delta.clip(lower=0); perda = -delta.clip(upper=0)
    avg_g = ganho.ewm(alpha=1/14, adjust=False).mean()
    avg_p = perda.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_g / avg_p.replace(0, 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))

    tp = (df['h'] + df['l'] + df['c']) / 3.0
    tpv = tp * df['v']
    grp = df.groupby('dia')
    df['vwap'] = tpv.groupby(df['dia']).cumsum() / df['v'].groupby(df['dia']).cumsum().replace(0, 1e-9)

    return {'ema9': df['ema9'].tolist(), 'ema20': df['ema20'].tolist(), 'ema50': df['ema50'].tolist(),
            'rsi': df['rsi'].tolist(), 'vwap': df['vwap'].tolist()}


# ============================== MOTOR GENERICO ==============================

class Estado:
    """Estado mutavel compartilhado entre as funcoes de sinal, por barra."""
    def __init__(self):
        self.dia = None; self.pd_hi = self.pd_lo = None; self.cur_hi = self.cur_lo = None
        self.seg_hoje = None
        self.orb_hi = self.orb_lo = None; self.orb_pronto = False
        self.fvg_bull = []  # lista de (topo, fundo, idx_criado) ainda nao mitigados
        self.fvg_bear = []
        self.rsi_prev = None


def sinal_reversao(bars, i, st, dom_map):
    b = bars[i]; d = b['dt'].strftime('%Y-%m-%d'); m = mins(b['dt']); wd = b['dt'].weekday()
    niv_hi = st.seg_hoje[0] if st.seg_hoje else st.pd_hi
    niv_lo = st.seg_hoje[1] if st.seg_hoje else st.pd_lo
    if niv_hi is None or not (ENTRADA_INI <= m < ENTRADA_FIM): return 0
    tol = TOL_TICKS * TICK; h, l, c = b['h'], b['l'], b['c']
    if h >= niv_hi - tol and c < niv_hi:
        if (niv_hi - c) <= MAX_DIST: return -1
    elif l <= niv_lo + tol and c > niv_lo:
        if (c - niv_lo) <= MAX_DIST: return 1
    return 0


def sinal_orb(bars, i, st, dom_map):
    b = bars[i]; m = mins(b['dt'])
    if not (ORB_FIM <= m < ENTRADA_FIM) or not st.orb_pronto or st.orb_hi is None: return 0
    if b['c'] > st.orb_hi: return 1
    if b['c'] < st.orb_lo: return -1
    return 0


def sinal_emavwap(bars, i, st, dom_map, ind):
    m = mins(bars[i]['dt'])
    if not (ENTRADA_INI <= m < ENTRADA_FIM) or i < 51: return 0
    c = bars[i]['c']; e9, e20, e50 = ind['ema9'][i], ind['ema20'][i], ind['ema50'][i]
    vwap = ind['vwap'][i]; rsi = ind['rsi'][i]; rsi_prev = ind['rsi'][i-1]
    if c > vwap and e9 > e20 > e50 and rsi_prev <= 50 < rsi: return 1
    if c < vwap and e9 < e20 < e50 and rsi_prev >= 50 > rsi: return -1
    return 0


def sinal_ict(bars, i, st, dom_map):
    """ICT-lite: usa FVGs (gap de 3 candles) formados HOJE, ainda nao mitigados.
    Entrada = preco toca a zona do gap e fecha de volta na direcao original (continuacao)."""
    m = mins(bars[i]['dt'])
    if not (ENTRADA_INI <= m < ENTRADA_FIM) or i < 2: return 0
    b = bars[i]
    # atualiza a lista de FVGs ativos: remove os que ja foram totalmente atravessados (mitigados)
    st.fvg_bull = [z for z in st.fvg_bull if b['l'] > z[1]]   # se o low ja passou do fundo, mitigado
    st.fvg_bear = [z for z in st.fvg_bear if b['h'] < z[0]]
    sinal = 0
    for topo, fundo, _ in st.fvg_bull:
        if b['l'] <= topo and b['c'] > topo:   # tocou a zona e fechou de volta acima
            sinal = 1; break
    if sinal == 0:
        for topo, fundo, _ in st.fvg_bear:
            if b['h'] >= fundo and b['c'] < fundo:
                sinal = -1; break
    # cria novo FVG (3 candles: i-2, i-1, i)
    b0 = bars[i-2]
    if b0['h'] < b['l']:
        st.fvg_bull.append((b['l'], b0['h'], i))   # zona (topo=b.low, fundo=b0.high)
    if b0['l'] > b['h']:
        st.fvg_bear.append((b0['l'], b['h'], i))   # zona (topo=b0.low, fundo=b.high)
    return sinal


FONTES_DISPONIVEIS = {'REV': sinal_reversao, 'ORB': sinal_orb, 'EMAV': sinal_emavwap, 'ICT': sinal_ict}


def bt(bars, dom_map, fontes, ind=None, meta=META, dd=DD, stop_dia=STOP_DIA,
       max_trades=MAX_TRADES, slip_ticks=SLIP_BASE, n_contr=N_CONTR):
    """fontes: lista de chaves de FONTES_DISPONIVEIS, checadas nessa ordem (a 1a que
    sinalizar na barra abre o trade). Retorna metricas + contagem de trades por fonte."""
    pv = MNQ_PV * n_contr; rt = RT_PER * n_contr; slip = slip_ticks * TICK
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be_done = False; origem = ''
    realized = 0.0; trades = []; trades_por_fonte = {f: [] for f in fontes}
    r_ini = 0.0; pico = 0.0; dias = set(); ini_aval = None
    aprov = reprov = 0; d2a = []; pnl_d0 = 0.0; block = False; dia_k = None
    trades_hoje = 0
    st = Estado()

    def fecha(p):
        nonlocal pos, realized
        if pos == 0: return
        g = ((p - entry) * pos - 2 * slip) * pv - rt
        realized += g; trades.append(g)
        if origem in trades_por_fonte: trades_por_fonte[origem].append(g)
        pos = 0

    for i, b in enumerate(bars):
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d'); wd = dt.weekday()

        if d != st.dia:
            if st.cur_hi is not None: st.pd_hi, st.pd_lo = st.cur_hi, st.cur_lo
            st.dia = d; st.cur_hi = st.cur_lo = None
            st.seg_hoje = dom_map[d] if (dom_map and wd == 0 and d in dom_map) else None
            st.orb_hi = st.orb_lo = None; st.orb_pronto = False
            st.fvg_bull = []; st.fvg_bear = []
        if ENTRADA_INI <= m < 16*60:
            st.cur_hi = b['h'] if st.cur_hi is None else max(st.cur_hi, b['h'])
            st.cur_lo = b['l'] if st.cur_lo is None else min(st.cur_lo, b['l'])
        if ENTRADA_INI <= m < ORB_FIM:
            st.orb_hi = b['h'] if st.orb_hi is None else max(st.orb_hi, b['h'])
            st.orb_lo = b['l'] if st.orb_lo is None else min(st.orb_lo, b['l'])
        elif m >= ORB_FIM:
            st.orb_pronto = True
        if d != dia_k:
            dia_k = d; pnl_d0 = realized; block = False; trades_hoje = 0
        if ini_aval is None: ini_aval = dt

        if pos != 0:
            saiu = False
            if pos > 0:
                if b['l'] <= stop: fecha(stop); saiu = True
                elif b['h'] >= target: fecha(target); saiu = True
            else:
                if b['h'] >= stop: fecha(stop); saiu = True
                elif b['l'] <= target: fecha(target); saiu = True
            if not saiu and pos != 0:
                if pos > 0:
                    fav = max(fav, b['h'])
                    if not be_done and (fav - entry) >= PTS_BE_TRIG:
                        stop = max(stop, entry + PTS_BE_LOCK); be_done = True
                    if be_done: stop = max(stop, fav - PTS_TRAIL)
                else:
                    fav = min(fav, b['l'])
                    if not be_done and (entry - fav) >= PTS_BE_TRIG:
                        stop = min(stop, entry - PTS_BE_LOCK); be_done = True
                    if be_done: stop = min(stop, fav + PTS_TRAIL)

        pr = realized - r_ini
        ua = uf = 0.0
        if pos > 0: ua = (b['l']-entry)*pv; uf = (b['h']-entry)*pv
        elif pos < 0: ua = (entry-b['h'])*pv; uf = (entry-b['l'])*pv
        if pr + uf > pico: pico = pr + uf
        if stop_dia > 0 and (realized - pnl_d0 + ua) <= -stop_dia:
            block = True
            if pos != 0: fecha(b['c'])
        if pr + ua <= pico - dd:
            fecha(b['c']); reprov += 1; r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt
        elif pr >= meta and len(dias) >= MIN_DIAS:
            fecha(b['c']); aprov += 1; d2a.append((dt - ini_aval).days)
            r_ini = realized; pico = 0.0; dias = set(); ini_aval = dt

        if m >= FLATTEN and pos != 0:
            fecha(b['c'])
        lim_ok = (max_trades == 0 or trades_hoje < max_trades)
        if not block and lim_ok and pos == 0 and ENTRADA_INI <= m < ENTRADA_FIM:
            lado = 0; fonte_disp = ''
            for f in fontes:
                fn = FONTES_DISPONIVEIS[f]
                lado = fn(bars, i, st, dom_map, ind) if f == 'EMAV' else fn(bars, i, st, dom_map)
                if lado != 0: fonte_disp = f; break
            if lado != 0:
                entry = b['c']; pos = lado; fav = entry; be_done = False; origem = fonte_disp
                stop = entry - lado * PTS_SL; target = entry + lado * TP
                dias.add(d); trades_hoje += 1

    if pos != 0: fecha(bars[-1]['c'])

    w = [t for t in trades if t > 0]; n = len(trades)
    gw = sum(w); gl = abs(sum(t for t in trades if t <= 0))
    tot = aprov + reprov; ds = sorted(d2a); med = ds[len(ds)//2] if ds else 0
    por_fonte = {}
    for f, ts in trades_por_fonte.items():
        if ts: por_fonte[f] = {'n': len(ts), 'net': sum(ts), 'wr': 100*len([t for t in ts if t>0])/len(ts)}
    return {'n': n, 'wr': 100*len(w)/n if n else 0, 'pf': gw/gl if gl > 0 else 99,
            'net': sum(trades), 'aprov': aprov, 'reprov': reprov, 'tot': tot,
            'taxa': 100*aprov/tot if tot else 0, 'dmediana': med, 'por_fonte': por_fonte,
            'trades': trades}  # [29/08] lista crua de PnL por trade, p/ analise de qualidade
            # (ganho medio/perda media/ratio) sem quebrar nenhum consumidor existente (chave nova)


def linha(label, r):
    fontes_str = ' + '.join(f"{k}:{v['n']}" for k, v in sorted(r['por_fonte'].items()))
    print(f"  {label:>20s} {r['taxa']:>4.0f}% {r['aprov']:>3}/{r['tot']:<3} {r['dmediana']:>4.0f}d "
          f"{r['n']:>5} {r['wr']:>3.0f}% {r['pf']:>5.2f} {r['net']:>9,.0f}   [{fontes_str}]")


if __name__ == '__main__':
    print("Carregando NQ 1-min real..."); bars = carregar('NQ_dados')
    dom = domingo_ranges(bars)
    print("Calculando indicadores (EMA/RSI/VWAP)..."); ind = calcula_indicadores(bars)
    meio = bars[len(bars)//2]['dt']
    idx_meio = next(i for i, b in enumerate(bars) if b['dt'] >= meio)
    b1, ind1 = bars[:idx_meio], {k: v[:idx_meio] for k, v in ind.items()}
    b2, ind2 = bars[idx_meio:], {k: v[idx_meio:] for k, v in ind.items()}
    dom1 = domingo_ranges(b1); dom2 = domingo_ranges(b2)
    print(f"{len(bars):,} barras | gestao PADRAO (SL12,5/BE3,75-2,5/trail1,75/alvo60) | "
          f"DD real $1000 | MaxTradesDia=12 | 5 MNQ\n")
    H = f"  {'cenario':>20s} {'taxa':>5s} {'aprov':>7s} {'d.med':>5s} {'trds':>5s} {'WR':>4s} {'PF':>5s} {'PnL$':>9s}"

    print("=" * 100); print("  (1) ESTRATEGIAS SOZINHAS"); print("=" * 100); print(H); print("-"*100)
    for f in ['REV', 'ORB', 'EMAV', 'ICT']:
        linha(f, bt(bars, dom, [f], ind=ind))
    print("=" * 100 + "\n")

    print("=" * 100); print("  (2) MESCLAS COM A REVERSAO (o que ja roda em producao)"); print("=" * 100); print(H); print("-"*100)
    for combo in [['REV'], ['REV','ORB'], ['REV','EMAV'], ['REV','ICT'], ['REV','ORB','EMAV'], ['REV','ORB','EMAV','ICT']]:
        linha('+'.join(combo), bt(bars, dom, combo, ind=ind))
    print("=" * 100 + "\n")

    print("=" * 100); print("  (3) MESCLAS SEM REVERSAO (so as novas)"); print("=" * 100); print(H); print("-"*100)
    for combo in [['ORB','EMAV'], ['ORB','ICT'], ['EMAV','ICT'], ['ORB','EMAV','ICT']]:
        linha('+'.join(combo), bt(bars, dom, combo, ind=ind))
    print("=" * 100 + "\n")

    print("=" * 100); print("  OOS (1a metade x 2a metade) -- sozinhas + melhores mesclas"); print("=" * 100)
    def oos(label, combo):
        r1 = bt(b1, dom1, combo, ind=ind1); r2 = bt(b2, dom2, combo, ind=ind2)
        print(f"  {label:>20s}  1a: {r1['aprov']:>2}/{r1['tot']:<3}({r1['taxa']:>3.0f}%) PF{r1['pf']:>5.2f} n={r1['n']:<4} "
              f"  2a: {r2['aprov']:>2}/{r2['tot']:<3}({r2['taxa']:>3.0f}%) PF{r2['pf']:>5.2f} n={r2['n']:<4}")
    for combo in [['REV'], ['ORB'], ['EMAV'], ['ICT'], ['REV','ORB'], ['REV','EMAV'], ['REV','ICT'], ['REV','ORB','EMAV','ICT']]:
        oos('+'.join(combo), combo)
    print("=" * 100)
