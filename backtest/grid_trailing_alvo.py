#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GRADE trailing x alvo (18/08/2026) -- acha candidatos pra levar pro replay do NT8.
Mantem fixo: SL 12,5pt, BE gatilho 3,75pt, BE trava 2,5pt, MaxDist 15pt, tol 5pt.
Varia: Trailing (pontos) e Alvo (pontos). Slippage 2 ticks embutido desde o inicio.
"""
import sys, os, csv
from datetime import timedelta
sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp

TICK = dp.TICK; TOL_TICKS = 20; MAX_DIST = 15.0
PTS_SL = 12.5; PTS_BE_TRIG = 3.75; PTS_BE_LOCK = 2.5
STOP_DIA_PT = 750.0/(2.0*5); MAX_TRADES_DIA = 12
MNQ_PV = 2.0; N_CONTR = 5; RT = 1.20*N_CONTR
ANO_INICIO, ANO_FIM = '2025-06-11', '2026-06-11'
SLIP = 2*TICK

def simula(bars5m, pts_trail, pts_tp):
    tol_pts = TOL_TICKS*TICK; pv = MNQ_PV*N_CONTR
    cur_hi=cur_lo=None; pd_hi=pd_lo=None; dia=None; on_key=None; on_hi=on_lo=None
    pos=0; entry=stop=alvo=fav=0.0; be_feito=False
    pnl_dia0=0.0; realizado=0.0; bloqueado_hoje=False
    trades=[]
    def fecha(preco, motivo, d):
        nonlocal pos, realizado
        preco_real = preco - SLIP if pos>0 else preco + SLIP
        pts = (preco_real-entry) if pos>0 else (entry-preco_real)
        usd = pts*pv - RT
        realizado += usd
        trades.append({'pnl_usd':usd,'motivo':motivo,'data':d})
        pos=0
    for b in bars5m:
        dt=b['dt']; d=dt.strftime('%Y-%m-%d'); m=dp.mins(dt); dow=dt.weekday()
        em_sessao = dp.SESSAO_INICIO <= m < dp.ENTRADA_FIM
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
                if b['l']<=stop: fecha(stop,'BE_TRAIL' if be_feito else 'SL',d); saiu=True
                elif b['h']>=alvo: fecha(alvo,'TP',d); saiu=True
            else:
                if b['h']>=stop: fecha(stop,'BE_TRAIL' if be_feito else 'SL',d); saiu=True
                elif b['l']<=alvo: fecha(alvo,'TP',d); saiu=True
            if not saiu:
                if pos>0:
                    fav=max(fav,b['h'])
                    if not be_feito and (fav-entry)>=PTS_BE_TRIG: stop=max(stop,entry+PTS_BE_LOCK); be_feito=True
                    if be_feito: stop=max(stop,fav-pts_trail)
                else:
                    fav=min(fav,b['l'])
                    if not be_feito and (entry-fav)>=PTS_BE_TRIG: stop=min(stop,entry-PTS_BE_LOCK); be_feito=True
                    if be_feito: stop=min(stop,fav+pts_trail)
            else:
                if STOP_DIA_PT>0 and (realizado-pnl_dia0)<=-STOP_DIA_PT*pv: bloqueado_hoje=True
            continue
        if bloqueado_hoje or not (dp.SESSAO_INICIO<=m<dp.ENTRADA_FIM): continue
        if pd_hi is None or pd_lo is None: continue
        trades_hoje = sum(1 for t in trades if t['data']==d)
        if MAX_TRADES_DIA>0 and trades_hoje>=MAX_TRADES_DIA: continue
        if dow==0 and on_key==d and on_hi is not None and on_hi>0: n_hi,n_lo=on_hi,on_lo
        else: n_hi,n_lo=pd_hi,pd_lo
        ev = dp.avalia_bar(b, n_hi, n_lo, tol_pts, MAX_DIST)
        if ev is not None and ev['cat']=='OPEROU':
            if ev['lado']=='SHORT':
                entry=b['c']-SLIP; pos=-1; stop=entry+PTS_SL; alvo=entry-pts_tp
            else:
                entry=b['c']+SLIP; pos=1; stop=entry-PTS_SL; alvo=entry+pts_tp
            fav=entry; be_feito=False
    return trades

def resume(trades):
    wins=[t for t in trades if t['pnl_usd']>0]; losses=[t for t in trades if t['pnl_usd']<0]
    gm = sum(t['pnl_usd'] for t in wins)/len(wins) if wins else 0.0
    pm = sum(t['pnl_usd'] for t in losses)/len(losses) if losses else 0.0
    ratio = gm/abs(pm) if pm else float('inf')
    wr = len(wins)/len(trades)*100 if trades else 0.0
    return {'n':len(trades),'wr':wr,'gm':gm,'pm':pm,'ratio':ratio,'pnl':sum(t['pnl_usd'] for t in trades)}

def main():
    bars1m = dp.carregar_1min(dp.PASTA_DADOS)
    bars5m = dp.resample_5min(bars1m)
    print(f"{len(bars5m):,} candles 5min carregados\n")
    trails = [1.75, 3.0, 5.0, 8.0]
    alvos  = [20.0, 30.0, 40.0, 60.0]
    linhas=[]
    print(f"{'Trail':<7}{'Alvo':<7}{'N':<6}{'WR%':<7}{'GanhoMed':<11}{'PerdaMed':<11}{'Ratio':<7}{'PnLTotal'}")
    for tr in trails:
        for tp in alvos:
            trs = simula(bars5m, tr, tp)
            r = resume(trs)
            marca = ' (atual)' if tr==1.75 and tp==60.0 else ''
            print(f"{tr:<7}{tp:<7}{r['n']:<6}{r['wr']:<7.1f}${r['gm']:<10.1f}${r['pm']:<10.1f}{r['ratio']:<7.2f}${r['pnl']:.1f}{marca}")
            linhas.append({'trail':tr,'alvo':tp,**r})
    csv_path = os.path.join(os.path.dirname(__file__), 'grid_trailing_alvo.csv')
    with open(csv_path,'w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=list(linhas[0].keys())); w.writeheader(); w.writerows(linhas)
    top = sorted(linhas, key=lambda l: l['pnl'], reverse=True)[:5]
    print("\nTOP 5 por PnL total:")
    for l in top:
        print(f"  trail={l['trail']} alvo={l['alvo']} -> ratio={l['ratio']:.2f} WR={l['wr']:.1f}% PnL=${l['pnl']:.1f}")
    print(f"\nCSV: {csv_path}")

if __name__=='__main__':
    main()
