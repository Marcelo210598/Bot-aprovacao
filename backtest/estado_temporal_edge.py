#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESTADO TEMPORAL DO EDGE — investigacao final (18/08/2026)

Pergunta: existe informacao disponivel ANTES de cada sinal que preveja se o
fluxo de trades esta numa fase favoravel ou desfavoravel? ZERO look-ahead:
todo "estado" no trade T usa SOMENTE trades 0..T-1.

Fonte: sequencia REAL de 1084 trades realizados (baseline producao, 5 MNQ,
SL12,5/TP60/BE3,75-2,5/trail1,75, slippage 2 ticks, ano inteiro), na ordem
cronologica exata em que aconteceram.
"""
import sys, os, random
from datetime import timedelta
sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp

random.seed(42)
TICK = dp.TICK; TOL_TICKS = 20; MAX_DIST = 15.0
PTS_SL = 12.5; PTS_TP = 60.0; PTS_BE_TRIG = 3.75; PTS_BE_LOCK = 2.50; PTS_TRAIL = 1.75
MNQ_PV = 2.0; N_CONTR = 5; RT = 1.20 * N_CONTR; SLIP = 2 * TICK
STOP_DIA_PT = 750.0 / (MNQ_PV * N_CONTR); MAX_TRADES_DIA = 12
ANO_INICIO, ANO_FIM = '2025-06-11', '2026-06-11'


def atr_simples(bars, i0, n=14):
    ini = max(1, i0-n+1); trs=[]
    for j in range(ini, i0+1):
        trs.append(max(bars[j]['h']-bars[j]['l'], abs(bars[j]['h']-bars[j-1]['c']), abs(bars[j]['l']-bars[j-1]['c'])))
    return sum(trs)/len(trs) if trs else 0.0

def range_bars(bars, i0, n):
    ini = max(0, i0-n+1); sub = bars[ini:i0+1]
    return (max(b['h'] for b in sub) - min(b['l'] for b in sub)) if sub else 0.0


def simula_com_contexto(bars):
    tol_pts = TOL_TICKS*TICK; pv = MNQ_PV*N_CONTR
    cur_hi=cur_lo=None; pd_hi=pd_lo=None; dia=None; on_key=None; on_hi=on_lo=None
    pos=0; entry=stop=alvo=fav=0.0; be_feito=False
    pnl_dia0=0.0; realizado=0.0; bloqueado_hoje=False
    trades=[]; mfe_atual=mae_atual=0.0; idx_entry=None

    def fecha(preco, motivo, d, idx_saida):
        nonlocal pos, realizado
        preco_real = preco-SLIP if pos>0 else preco+SLIP
        pts = (preco_real-entry) if pos>0 else (entry-preco_real)
        usd = pts*pv - RT
        realizado += usd
        trades.append({'pnl_usd':usd,'motivo':motivo,'data':d,'mfe':mfe_atual,'mae':mae_atual,
                        'idx_entry':idx_entry,'win':usd>0})
        pos=0

    for idx, b in enumerate(bars):
        dt=b['dt']; d=dt.strftime('%Y-%m-%d'); m=dp.mins(dt); dow=dt.weekday()
        em_sessao = dp.SESSAO_INICIO<=m<dp.ENTRADA_FIM
        if d!=dia:
            if cur_hi is not None: pd_hi,pd_lo=cur_hi,cur_lo
            dia=d; cur_hi=b['h'] if em_sessao else None; cur_lo=b['l'] if em_sessao else None
            bloqueado_hoje=False; pnl_dia0=realizado
        elif em_sessao:
            cur_hi=b['h'] if cur_hi is None else max(cur_hi,b['h'])
            cur_lo=b['l'] if cur_lo is None else min(cur_lo,b['l'])
        chave_seg=None
        if dow==6 and m>=dp.DOM_NOITE_INICIO: chave_seg=(dt+timedelta(days=1)).strftime('%Y-%m-%d')
        elif dow==0 and m<dp.SESSAO_INICIO: chave_seg=d
        if chave_seg is not None:
            if chave_seg!=on_key: on_key,on_hi,on_lo=chave_seg,b['h'],b['l']
            else: on_hi=max(on_hi,b['h']); on_lo=min(on_lo,b['l'])
        if not (ANO_INICIO<=d<=ANO_FIM): continue

        if pos!=0:
            saiu=False
            if pos>0:
                fav=max(fav,b['h']); mfe_atual=max(mfe_atual,fav-entry); mae_atual=max(mae_atual,entry-b['l'])
                if b['l']<=stop: fecha(stop,'BE_TRAIL' if be_feito else 'SL', d, idx); saiu=True
                elif b['h']>=alvo: fecha(alvo,'TP',d,idx); saiu=True
            else:
                fav=min(fav,b['l']); mfe_atual=max(mfe_atual,entry-fav); mae_atual=max(mae_atual,b['h']-entry)
                if b['h']>=stop: fecha(stop,'BE_TRAIL' if be_feito else 'SL', d, idx); saiu=True
                elif b['l']<=alvo: fecha(alvo,'TP',d,idx); saiu=True
            if not saiu:
                if pos>0:
                    if not be_feito and (fav-entry)>=PTS_BE_TRIG: stop=max(stop,entry+PTS_BE_LOCK); be_feito=True
                    if be_feito: stop=max(stop,fav-PTS_TRAIL)
                else:
                    if not be_feito and (entry-fav)>=PTS_BE_TRIG: stop=min(stop,entry-PTS_BE_LOCK); be_feito=True
                    if be_feito: stop=min(stop,fav+PTS_TRAIL)
            else:
                if STOP_DIA_PT>0 and (realizado-pnl_dia0)<=-STOP_DIA_PT*pv: bloqueado_hoje=True
            continue

        if bloqueado_hoje or not em_sessao: continue
        if pd_hi is None or pd_lo is None: continue
        trades_hoje = sum(1 for t in trades if t['data']==d)
        if MAX_TRADES_DIA>0 and trades_hoje>=MAX_TRADES_DIA: continue

        if dow==0 and on_key==d and on_hi: n_hi,n_lo=on_hi,on_lo
        else: n_hi,n_lo=pd_hi,pd_lo
        ev = dp.avalia_bar(b, n_hi, n_lo, tol_pts, MAX_DIST)
        if ev is not None and ev['cat']=='OPEROU':
            if ev['lado']=='SHORT':
                entry=b['c']-SLIP; pos=-1; stop=entry+PTS_SL; alvo=entry-PTS_TP
            else:
                entry=b['c']+SLIP; pos=1; stop=entry-PTS_SL; alvo=entry+PTS_TP
            fav=entry; be_feito=False; mfe_atual=mae_atual=0.0
            idx_entry=idx
    return trades


bars = dp.carregar_1min(dp.PASTA_DADOS)
print(f"{len(bars):,} candles carregados\n")
trades = simula_com_contexto(bars)
n = len(trades)
print(f"N total de trades realizados (sequencia cronologica) = {n}\n")

# ===================== FASE 1: ESTADO RECENTE (SEM LOOK-AHEAD) =====================
CAUDA_LIMIAR = 169.0  # ja estabelecido em analise anterior (top 10% do ano), usado aqui so como referencia fixa, nao reotimizado

for i, t in enumerate(trades):
    hist = trades[:i]  # SOMENTE passado -- trades[i] (o atual) e trades[i+1:] NUNCA entram aqui
    t['hist_n'] = len(hist)
    for N in [3,5,10,20,30]:
        h = hist[-N:] if len(hist)>=N else hist
        t[f'pnl_ult{N}'] = sum(x['pnl_usd'] for x in h) if h else 0.0
    for N in [5,10,20]:
        h = hist[-N:] if len(hist)>=N else hist
        t[f'wr_ult{N}'] = sum(1 for x in h if x['win'])/len(h)*100 if h else None
    h10 = hist[-10:] if len(hist)>=10 else hist
    wins10 = [x['pnl_usd'] for x in h10 if x['win']]; losses10 = [x['pnl_usd'] for x in h10 if not x['win']]
    t['gm_ult10'] = sum(wins10)/len(wins10) if wins10 else 0.0
    t['pm_ult10'] = sum(losses10)/len(losses10) if losses10 else 0.0
    t['ratio_ult10'] = t['gm_ult10']/abs(t['pm_ult10']) if t['pm_ult10'] else None
    t['exp_ult10'] = sum(x['pnl_usd'] for x in h10)/len(h10) if h10 else None
    h20 = hist[-20:] if len(hist)>=20 else hist
    t['exp_ult20'] = sum(x['pnl_usd'] for x in h20)/len(h20) if h20 else None

    # sequencia recente (streak terminando no ultimo trade do historico)
    streak = 0
    for x in reversed(hist):
        if not hist: break
        if (x['win'] and (streak>=0)):
            streak = streak+1 if streak>=0 else 1
        elif (not x['win'] and (streak<=0)):
            streak = streak-1 if streak<=0 else -1
        else:
            break
    t['streak'] = streak  # positivo=vitorias seguidas, negativo=derrotas seguidas
    t['ult1'] = hist[-1]['win'] if len(hist)>=1 else None
    t['ult2_losses'] = sum(1 for x in hist[-2:] if not x['win']) if len(hist)>=2 else None
    t['ult3_losses'] = sum(1 for x in hist[-3:] if not x['win']) if len(hist)>=3 else None
    t['ult4_losses'] = sum(1 for x in hist[-4:] if not x['win']) if len(hist)>=4 else None

    # contexto de mercado ANTES da entrada (idx_entry ja e' anterior ao 1o tick do trade, sem look-ahead)
    t['atr14'] = atr_simples(bars, t['idx_entry']) if t['idx_entry'] else 0.0
    t['range15c'] = range_bars(bars, t['idx_entry'], 15) if t['idx_entry'] else 0.0
    t['hora_min'] = dp.mins(bars[t['idx_entry']]['dt']) if t['idx_entry'] else 0

print("Estado calculado pra todos os trades (sem look-ahead). Amostra util comeca no trade #30 "
      "(precisa de historico minimo pra 'ultimos 30').\n")
print("Exemplo (trade #50):")
ex = trades[50]
print(f"  data={ex['data']} pnl_ult10=${ex['pnl_ult10']:.1f} wr_ult10={ex['wr_ult10']:.1f}% "
      f"streak={ex['streak']} exp_ult10=${ex['exp_ult10']:.1f} atr14={ex['atr14']:.1f}")

# ===================== FASE 3/4/6/7: ESTADO -> RESULTADO FUTURO (SEM LOOK-AHEAD) =====================
def media(xs): return sum(xs)/len(xs) if xs else 0.0

def forward_stats(idx_t, N):
    """Trades ESTRITAMENTE depois de T (idx_t+1 .. idx_t+N). Nunca inclui T."""
    fut = trades[idx_t+1: idx_t+1+N]
    if not fut: return None
    wins = [x for x in fut if x['win']]
    wr = len(wins)/len(fut)*100
    exp = sum(x['pnl_usd'] for x in fut)/len(fut)
    pnl = sum(x['pnl_usd'] for x in fut)
    mfe = media([x['mfe'] for x in fut]); mae = media([x['mae'] for x in fut])
    return {'n': len(fut), 'wr': wr, 'exp': exp, 'pnl': pnl, 'mfe': mfe, 'mae': mae}

MIN_HIST = 30  # so avalia estado com historico minimo

print("=" * 130)
print("FASE 6 — PERSISTENCIA APOS ESTADOS RUINS (o resultado FUTURO comeca IMEDIATAMENTE apos T, nunca inclui T)")
print("=" * 130)

condicoes_ruins = [
    ('Apos 1 perda (ultimo trade = loss)', lambda t: t['ult1'] == False),
    ('Apos 2 perdas seguidas', lambda t: t['streak'] is not None and t['streak'] <= -2),
    ('Apos 3 perdas seguidas', lambda t: t['streak'] is not None and t['streak'] <= -3),
    ('Apos 4 perdas seguidas', lambda t: t['streak'] is not None and t['streak'] <= -4),
    ('WR ultimos 10 < 50%', lambda t: t['wr_ult10'] is not None and t['wr_ult10'] < 50),
    ('Expectancy ult10 < 0', lambda t: t['exp_ult10'] is not None and t['exp_ult10'] < 0),
    ('PnL ultimos 10 < 0', lambda t: t['pnl_ult10'] < 0),
    ('PnL ultimos 20 < 0', lambda t: t['pnl_ult20'] < 0),
]

print(f"\nBASELINE geral (media de todo N-forward, sem condicionar em nada):")
for N in [5, 10, 20, 30]:
    todos = [forward_stats(i, N) for i in range(MIN_HIST, n) if forward_stats(i, N)]
    print(f"  proximos {N}: WR={media([f['wr'] for f in todos]):.1f}% Exp=${media([f['exp'] for f in todos]):.1f}")

resultados_condicoes = {}
for nome, cond in condicoes_ruins:
    print(f"\n--- {nome} ---")
    linha = {}
    for N in [5, 10, 20, 30]:
        idxs_cond = [i for i in range(MIN_HIST, n) if cond(trades[i])]
        fwds = [forward_stats(i, N) for i in idxs_cond]
        fwds = [f for f in fwds if f]
        if not fwds:
            print(f"  proximos {N}: sem dados suficientes"); continue
        wr = media([f['wr'] for f in fwds]); exp = media([f['exp'] for f in fwds])
        print(f"  proximos {N}: N_ocorrencias={len(fwds)} WR={wr:.1f}% Exp=${exp:.1f}")
        linha[N] = {'wr': wr, 'exp': exp, 'n_oc': len(fwds)}
    resultados_condicoes[nome] = linha

print("\n" + "=" * 130)
print("FASE 7 — PERSISTENCIA APOS ESTADOS BONS (inverso)")
print("=" * 130)
condicoes_boas = [
    ('Apos 2 vitorias seguidas', lambda t: t['streak'] is not None and t['streak'] >= 2),
    ('Apos 3 vitorias seguidas', lambda t: t['streak'] is not None and t['streak'] >= 3),
    ('PnL ultimos 10 > 0', lambda t: t['pnl_ult10'] > 0),
    ('Expectancy ult10 > 0', lambda t: t['exp_ult10'] is not None and t['exp_ult10'] > 0),
    ('WR ultimos 10 > 75%', lambda t: t['wr_ult10'] is not None and t['wr_ult10'] > 75),
]
for nome, cond in condicoes_boas:
    print(f"\n--- {nome} ---")
    linha = {}
    for N in [5, 10, 20, 30]:
        idxs_cond = [i for i in range(MIN_HIST, n) if cond(trades[i])]
        fwds = [forward_stats(i, N) for i in idxs_cond]
        fwds = [f for f in fwds if f]
        if not fwds:
            print(f"  proximos {N}: sem dados suficientes"); continue
        wr = media([f['wr'] for f in fwds]); exp = media([f['exp'] for f in fwds])
        print(f"  proximos {N}: N_ocorrencias={len(fwds)} WR={wr:.1f}% Exp=${exp:.1f}")
        linha[N] = {'wr': wr, 'exp': exp, 'n_oc': len(fwds)}
    resultados_condicoes[nome] = linha

# ===================== FASE 10: TESTE DE PERMUTACAO =====================
print("\n" + "=" * 130)
print("FASE 10 — TESTE DE PERMUTACAO (o candidato mais chamativo: apos 3 perdas seguidas, proximos 10)")
print("=" * 130)

def calc_efeito_apos_3perdas(seq_trades):
    """Recalcula streak/expectancy-futura EM CIMA de uma sequencia (pode ser embaralhada)."""
    # recalcula streak local (nao usa os campos precomputados, que sao da ordem original)
    idxs_3perdas = []
    for i in range(MIN_HIST, len(seq_trades)):
        hist = seq_trades[:i]
        s = 0
        for x in reversed(hist):
            if x['win'] and s >= 0: s = s+1 if s > 0 else 1
            elif not x['win'] and s <= 0: s = s-1 if s < 0 else -1
            else: break
        if s <= -3: idxs_3perdas.append(i)
    fwds = []
    for i in idxs_3perdas:
        fut = seq_trades[i+1:i+11]
        if len(fut) < 10: continue
        fwds.append(sum(x['pnl_usd'] for x in fut)/len(fut))
    return media(fwds) if fwds else None, len(fwds)

exp_real, n_real = calc_efeito_apos_3perdas(trades)
exp_baseline_geral = media([sum(x['pnl_usd'] for x in trades[i+1:i+11])/10
                             for i in range(MIN_HIST, n) if len(trades[i+1:i+11]) == 10])
efeito_real = exp_real - exp_baseline_geral
print(f"Expectancy real apos 3 perdas seguidas (prox 10): ${exp_real:.2f} (N={n_real} ocorrencias)")
print(f"Expectancy baseline geral (prox 10, media de todos os pontos): ${exp_baseline_geral:.2f}")
print(f"Efeito observado: ${efeito_real:+.2f}")

print("\nEmbaralhando a ORDEM CRONOLOGICA dos 1084 trades 1000x (mesmo conjunto de resultados, "
      "ordem aleatoria) e recalculando o mesmo efeito em cada uma...")
efeitos_shuffle = []
pnls_e_wins = [(t['pnl_usd'], t['win']) for t in trades]
for it in range(1000):
    random.shuffle(pnls_e_wins)
    seq_shuf = [{'pnl_usd': p, 'win': w} for p, w in pnls_e_wins]
    exp_s, n_s = calc_efeito_apos_3perdas(seq_shuf)
    if exp_s is not None and n_s >= 10:
        exp_base_s = media([sum(x['pnl_usd'] for x in seq_shuf[i+1:i+11])/10
                             for i in range(MIN_HIST, n) if len(seq_shuf[i+1:i+11]) == 10])
        efeitos_shuffle.append(exp_s - exp_base_s)

efeitos_shuffle.sort()
mais_extremos = sum(1 for e in efeitos_shuffle if abs(e) >= abs(efeito_real))
p_valor = mais_extremos / len(efeitos_shuffle) if efeitos_shuffle else None
print(f"\nDe {len(efeitos_shuffle)} embaralhamentos validos, {mais_extremos} produziram um efeito "
      f"tao grande (em modulo) quanto o real (${efeito_real:+.2f}).")
print(f"'p-valor' empirico: {p_valor:.3f}" if p_valor is not None else "sem dados suficientes")
print("(se p-valor for alto, tipo >0.10-0.20, o efeito observado e' compativel com ordem aleatoria "
      "-- nao e' evidencia de persistencia temporal real)")
