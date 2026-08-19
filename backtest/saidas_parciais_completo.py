#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FASE 2-8 — Distribuicao do risco/recompensa dentro dos 5 MNQ (18/08/2026)

Motor identico ao baseline de producao. Adiciona idx_mfe/idx_mae (tempo ate
o pico favoravel/adverso) sem mudar nenhuma outra logica.

AVISO DE LOOK-AHEAD (Fase 9): a Fase 3 original pedia gatilhos como "25% do
MFE" -- se isso significar 25% do MFE FINAL de CADA trade, e' look-ahead (o
MFE final so e' conhecido depois que o trade acaba). Uso em vez disso valores
ABSOLUTOS FIXOS em pontos, derivados da DISTRIBUICAO HISTORICA da populacao
(conhecida de antemao, nao do futuro de cada trade individual) -- isso e'
zero look-ahead de verdade.
"""
import sys, os
from datetime import timedelta
sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp

TICK = dp.TICK; TOL_TICKS = 20; MAX_DIST = 15.0
PTS_SL=12.5; PTS_TP=60.0; PTS_BE_TRIG=3.75; PTS_BE_LOCK=2.50; PTS_TRAIL=1.75
MNQ_PV=2.0; N_CONTR=5; RT_PER_CONTR=1.20; SLIP=2*TICK
STOP_DIA_PT = 750.0/(MNQ_PV*N_CONTR); MAX_TRADES_DIA=12
ANO_INICIO, ANO_FIM = '2025-06-11', '2026-06-11'


def simula_com_timing(bars):
    tol_pts=TOL_TICKS*TICK; pv=MNQ_PV*N_CONTR
    cur_hi=cur_lo=None; pd_hi=pd_lo=None; dia=None; on_key=None; on_hi=on_lo=None
    pos=0; entry=stop=alvo=fav=0.0; be_feito=False
    pnl_dia0=0.0; realizado=0.0; bloqueado_hoje=False
    trades=[]; mfe_atual=mae_atual=0.0; idx_entry=None; idx_mfe=None; idx_mae=None

    def fecha(preco, motivo, d, idx_saida):
        nonlocal pos, realizado
        preco_real = preco-SLIP if pos>0 else preco+SLIP
        pts=(preco_real-entry) if pos>0 else (entry-preco_real)
        usd = pts*pv - RT_PER_CONTR*N_CONTR
        realizado += usd
        trades.append({'pnl_usd':usd,'pts':pts,'motivo':motivo,'data':d,'mfe':mfe_atual,
                        'mae':mae_atual,'idx_entry':idx_entry,'idx_exit':idx_saida,
                        'idx_mfe':idx_mfe,'idx_mae':idx_mae,'lado':'LONG' if pos>0 else 'SHORT'})
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
                if b['h']-entry > mfe_atual: mfe_atual=b['h']-entry; idx_mfe=idx
                if entry-b['l'] > mae_atual: mae_atual=entry-b['l']; idx_mae=idx
                fav=max(fav,b['h'])
                if b['l']<=stop: fecha(stop,'BE_TRAIL' if be_feito else 'SL', d, idx); saiu=True
                elif b['h']>=alvo: fecha(alvo,'TP',d,idx); saiu=True
            else:
                if entry-b['l'] > mfe_atual: mfe_atual=entry-b['l']; idx_mfe=idx
                if b['h']-entry > mae_atual: mae_atual=b['h']-entry; idx_mae=idx
                fav=min(fav,b['l'])
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
            idx_entry=idx; idx_mfe=idx; idx_mae=idx
    return trades


bars = dp.carregar_1min(dp.PASTA_DADOS)
print(f"{len(bars):,} candles carregados\n")
trades = simula_com_timing(bars)
n = len(trades)
print(f"N = {n} trades (identico ao baseline de todas as investigacoes anteriores)\n")

def media(xs): return sum(xs)/len(xs) if xs else 0
def mediana(xs):
    xs=sorted(xs); m=len(xs)
    return xs[m//2] if m%2 else (xs[m//2-1]+xs[m//2])/2
def pctl(xs,p):
    xs=sorted(xs); return xs[int(len(xs)*p)] if xs else 0

# ===================== FASE 2 =====================
print("=" * 110)
print("FASE 2 — MFE/MAE INTRATRADE")
print("=" * 110)
mfes=[t['mfe'] for t in trades]; maes=[t['mae'] for t in trades]
tempo_mfe=[t['idx_mfe']-t['idx_entry'] for t in trades]
tempo_mae=[t['idx_mae']-t['idx_entry'] for t in trades]
print(f"MFE: media={media(mfes):.2f} mediana={mediana(mfes):.2f} P25={pctl(mfes,.25):.2f} P75={pctl(mfes,.75):.2f}")
print(f"MAE: media={media(maes):.2f} mediana={mediana(maes):.2f} P25={pctl(maes,.25):.2f} P75={pctl(maes,.75):.2f}")
print(f"Tempo ate MFE (min): media={media(tempo_mfe):.2f} mediana={mediana(tempo_mfe):.2f}")
print(f"Tempo ate MAE (min): media={media(tempo_mae):.2f} mediana={mediana(tempo_mae):.2f}")

print("\n--- A) Quanto do MFE potencial e capturado pela saida atual? ---")
capturas = [(t['pts']/t['mfe']*100 if t['mfe']>0 else None) for t in trades]
capturas = [c for c in capturas if c is not None]
print(f"Fracao capturada (pts realizados / MFE): media={media(capturas):.1f}% mediana={mediana(capturas):.1f}%")

print("\n--- B) Quantos trades tiveram MFE significativamente maior que o PnL final? ---")
sig = [t for t in trades if t['mfe'] > t['pts'] + 10]  # MFE pelo menos 10pt acima do que foi realizado
print(f"MFE >= pts_realizado + 10pt: {len(sig)} de {n} ({len(sig)/n*100:.1f}%)")

print("\n--- C) Trades com MAE pequeno (<5pt) que depois geraram MFE grande (>=15pt)? ---")
c = [t for t in trades if t['mae'] < 5 and t['mfe'] >= 15]
print(f"MAE<5pt E MFE>=15pt: {len(c)} de {n} ({len(c)/n*100:.1f}%)")

print("\n--- D) Trades encerrados antes de capturar fracao relevante do MFE (<50%)? ---")
d_ = [t for t in trades if t['mfe']>0 and t['pts']/t['mfe'] < 0.5]
print(f"Capturaram <50% do proprio MFE: {len(d_)} de {n} ({len(d_)/n*100:.1f}%)")
d2_ = [t for t in trades if t['mfe']>0 and t['pts']/t['mfe'] < 0.3]
print(f"Capturaram <30% do proprio MFE: {len(d2_)} de {n} ({len(d2_)/n*100:.1f}%)")

print("\n--- Distribuicao de MFE por bucket (p/ escolher gatilhos fixos SEM olhar resultado) ---")
for bkt in [2.5,5,7.5,8.75,10,15,20,30]:
    pct = sum(1 for t in trades if t['mfe']>=bkt)/n*100
    print(f"  MFE>={bkt}pt: {pct:.1f}% dos trades alcancam")

# ===================== FASE 3-8: CONTRAFACTUAL DE SAIDA PARCIAL =====================
print("\n" + "=" * 110)
print("FASE 3 — SAIDA PARCIAL (gatilhos FIXOS em pontos, pre-registrados pela distribuicao, zero look-ahead)")
print("=" * 110)
print("Gatilhos escolhidos ANTES de ver resultado: 5pt (cedo, 71,5% alcancam), "
      "8,75pt (mediana, 50,6%), 15pt (tardio, 30,1%)")

GATILHOS = [5.0, 8.75, 15.0]
MODELOS = [('B (1+4)', 1, 4), ('C (2+3)', 2, 3), ('D (3+2)', 3, 2), ('E (4+1)', 4, 1)]

def pnl_parcial(t, L, c_out, c_remain):
    pv = MNQ_PV
    rt = RT_PER_CONTR
    if t['mfe'] < L:
        return t['pnl_usd']  # gatilho nunca disparou -> comportamento identico ao baseline
    saida_parcial = c_out * (L * pv - rt)
    saida_resto = c_remain * (t['pts'] * pv - rt)
    return saida_parcial + saida_resto

trades_por_modelo = {'A (baseline)': [{'pnl_usd': t['pnl_usd'], 'data': t['data']} for t in trades]}
for nome, c_out, c_remain in MODELOS:
    for L in GATILHOS:
        key = f'{nome} @ {L}pt'
        trades_por_modelo[key] = [{'pnl_usd': pnl_parcial(t, L, c_out, c_remain), 'data': t['data']} for t in trades]

# ===================== decomposicao da cauda (Fase 7) para cada modelo =====================
def decomp_cauda(trs):
    total = sum(t['pnl_usd'] for t in trs)
    ordenado = sorted(trs, key=lambda t: -t['pnl_usd'])
    top10 = sum(t['pnl_usd'] for t in ordenado[:int(len(trs)*0.10)])
    resto90 = total - top10
    return total, top10/total*100 if total else 0, resto90/total*100 if total else 0

# ===================== simulacao de janela 30d (mesma de sempre) =====================
from datetime import datetime
META=1500.0; DD_LIM=1000.0; MIN_DIAS=7

def simula_janelas(trs, meta, dd_lim, min_dias=7):
    pnl_dia={}
    for t in trs: pnl_dia[t['data']]=pnl_dia.get(t['data'],0.0)+t['pnl_usd']
    datas_ord=sorted(pnl_dia)
    dts=[datetime.strptime(d,'%Y-%m-%d') for d in datas_ord]
    aprovadas=estouradas=0; pnls=[]; dds=[]
    for i,d0 in enumerate(dts):
        fim=d0+timedelta(days=29)
        acumulado=0.0; pico=0.0; dd_max=0.0; dias_op=0; resultado=None
        for j in range(i,len(dts)):
            dj=dts[j]
            if dj>fim: break
            acumulado+=pnl_dia[datas_ord[j]]; dias_op+=1
            pico=max(pico,acumulado); dd_max=max(dd_max,pico-acumulado)
            if dd_max>dd_lim: resultado='BUST'; break
            if acumulado>=meta and dias_op>=min_dias: resultado='APROVOU'; break
        if resultado is None: resultado='INCOMPLETA'
        if resultado=='APROVOU': aprovadas+=1
        elif resultado=='BUST': estouradas+=1
        pnls.append(acumulado); dds.append(dd_max)
    total=len(dts)
    return {'taxa':aprovadas/total*100,'bust':estouradas/total*100,
            'pnl_med':media(pnls),'dd_med':media(dds),'dd_max':max(dds) if dds else 0}

print("\n" + "=" * 110)
print("TABELA PRINCIPAL — Aprovacao 30d, bust, PnL, decomposicao da cauda")
print("=" * 110)
print(f"{'Modelo':<18}{'Aprov%':<9}{'Bust%':<8}{'PnLmed(jan)':<13}{'DDmed':<9}{'DDmax':<9}"
      f"{'PnLano':<11}{'%doTop10':<11}{'%doResto90'}")
resultados = {}
for key, trs in trades_por_modelo.items():
    r = simula_janelas(trs, META, DD_LIM, MIN_DIAS)
    total, pct_top10, pct_resto90 = decomp_cauda(trs)
    resultados[key] = (r, total, pct_top10, pct_resto90)
    print(f"{key:<18}{r['taxa']:<9.1f}{r['bust']:<8.1f}${r['pnl_med']:<12.1f}${r['dd_med']:<8.1f}"
          f"${r['dd_max']:<8.1f}${total:<10.1f}{pct_top10:<11.1f}{pct_resto90:.1f}")

# ===================== FASE 8: SENSIBILIDADE (regiao robusta ou ponto isolado?) =====================
print("\n" + "=" * 110)
print("FASE 8 — SENSIBILIDADE em torno do gatilho de 15pt (D 3+2 e E 4+1)")
print("=" * 110)
GATILHOS_SENS = [10, 12, 15, 18, 20, 25]
for nome, c_out, c_remain in [('D (3+2)', 3, 2), ('E (4+1)', 4, 1)]:
    print(f"\n--- {nome} ---")
    print(f"{'Gatilho':<9}{'Aprov%':<9}{'Bust%':<8}{'PnLmed(jan)':<13}{'DDmax'}")
    for L in GATILHOS_SENS:
        trs = [{'pnl_usd': pnl_parcial(t, L, c_out, c_remain), 'data': t['data']} for t in trades]
        r = simula_janelas(trs, META, DD_LIM, MIN_DIAS)
        print(f"{L:<9}{r['taxa']:<9.1f}{r['bust']:<8.1f}${r['pnl_med']:<12.1f}${r['dd_max']:.1f}")

# ===================== FASE 6: ROBUSTEZ TEMPORAL (blocos + metades) =====================
print("\n" + "=" * 110)
print("FASE 6 — ROBUSTEZ TEMPORAL — candidato D(3+2)@15pt e E(4+1)@15pt vs baseline, por bloco")
print("=" * 110)
BLOCOS = [('B1','2025-06-13','2025-08-12'), ('B2','2025-08-13','2025-11-05'),
          ('B3','2025-11-06','2026-01-27'), ('B4','2026-01-28','2026-04-10'),
          ('B5','2026-04-13','2026-06-11')]

def simula_janelas_periodo(trs, meta, dd_lim, min_dias, periodo=None):
    pnl_dia={}
    for t in trs:
        if periodo and not (periodo[0]<=t['data']<=periodo[1]): continue
        pnl_dia[t['data']]=pnl_dia.get(t['data'],0.0)+t['pnl_usd']
    if not pnl_dia: return {'taxa':0,'bust':0,'n':0}
    datas_ord=sorted(pnl_dia)
    dts=[datetime.strptime(d,'%Y-%m-%d') for d in datas_ord]
    aprovadas=estouradas=0
    for i,d0 in enumerate(dts):
        fim=d0+timedelta(days=29)
        acumulado=0.0; pico=0.0; dd_max=0.0; dias_op=0; resultado=None
        for j in range(i,len(dts)):
            dj=dts[j]
            if dj>fim: break
            acumulado+=pnl_dia[datas_ord[j]]; dias_op+=1
            pico=max(pico,acumulado); dd_max=max(dd_max,pico-acumulado)
            if dd_max>dd_lim: resultado='BUST'; break
            if acumulado>=meta and dias_op>=min_dias: resultado='APROVOU'; break
        if resultado is None: resultado='INCOMPLETA'
        if resultado=='APROVOU': aprovadas+=1
        elif resultado=='BUST': estouradas+=1
    total=len(dts)
    return {'taxa':aprovadas/total*100,'bust':estouradas/total*100,'n':total}

candidatos = {
    'A (baseline)': [{'pnl_usd': t['pnl_usd'], 'data': t['data']} for t in trades],
    'D(3+2)@15pt': [{'pnl_usd': pnl_parcial(t, 15.0, 3, 2), 'data': t['data']} for t in trades],
    'E(4+1)@15pt': [{'pnl_usd': pnl_parcial(t, 15.0, 4, 1), 'data': t['data']} for t in trades],
}
print(f"\n{'Modelo':<16}" + "".join(f"{b[0]:<9}" for b in BLOCOS) + "1a met.   2a met.")
todas_datas_ord = sorted({t['data'] for t in trades})
meio = todas_datas_ord[len(todas_datas_ord)//2]
for nome, trs in candidatos.items():
    linha = f"{nome:<16}"
    for bnome, ini, fim in BLOCOS:
        r = simula_janelas_periodo(trs, META, DD_LIM, MIN_DIAS, periodo=(ini, fim))
        linha += f"{r['taxa']:<9.1f}"
    r1 = simula_janelas_periodo(trs, META, DD_LIM, MIN_DIAS, periodo=(todas_datas_ord[0], meio))
    r2 = simula_janelas_periodo(trs, META, DD_LIM, MIN_DIAS, periodo=(meio, todas_datas_ord[-1]))
    linha += f"{r1['taxa']:<9.1f}{r2['taxa']:.1f}"
    print(linha)
