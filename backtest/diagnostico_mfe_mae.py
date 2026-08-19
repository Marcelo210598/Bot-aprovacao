#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIAGNOSTICO MFE/MAE + CLASSIFICACAO DE TRADES (18/08/2026)

NAO e' otimizacao. E' instrumentacao: registra, por trade, tudo que aconteceu
DEPOIS da entrada, pra descobrir ONDE o edge esta sendo perdido.

Modela FIELMENTE o BotAprovacao.cs (auditado hoje):
  - Sinal avaliado no FECHAMENTO da barra (Calculate.OnBarClose)
  - Entrada = ordem a mercado -> FILL NO OPEN DA BARRA SEGUINTE (nao no close do sinal!)
  - GerenciaPosicao(): checa ALVO -> checa STOP -> SO DEPOIS atualiza fav/BE/trailing
    (ou seja: trailing so vale a partir da barra seguinte -- lag de 1 barra)

Roda 3 motores de saida pra separar o que e' estrategia do que e' motor:
  BAR_LAG   = o que o BACKTEST faz (trailing com lag de 1 barra)
  TICK_OTIM = tick a tick, assumindo ordem intrabar FAVORAVEL (limite superior)
  TICK_PESS = tick a tick, assumindo ordem intrabar ADVERSA  (limite inferior)
O ao vivo (OnMarketData, tick a tick real) fica ENTRE otimista e pessimista.
"""
import sys, os, csv
from datetime import timedelta
sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp

TICK = dp.TICK
TOL_TICKS = 20; MAX_DIST = 15.0
SL = 12.5; TP = 60.0; BE_TRIG = 3.75; BE_LOCK = 2.5; TRAIL = 1.75
MNQ_PV = 2.0; N_CONTR = 5; RT = 1.20 * N_CONTR
PV = MNQ_PV * N_CONTR
STOP_DIA_USD = 750.0; MAX_TRADES_DIA = 12
ANO_INICIO, ANO_FIM = '2025-06-11', '2026-06-11'

MFE_BUCKETS = [2.5, 5, 7.5, 10, 15, 20, 30, 40, 50, 60]
MAE_BUCKETS = [2.5, 5, 7.5, 10, 12.5]


def coleta_sinais(bars):
    """Replica EntradaNiveis() do .cs. Sinal no fechamento da barra i ->
    entrada no OPEN da barra i+1 (comportamento real do NT8 OnBarClose)."""
    tol_pts = TOL_TICKS * TICK
    cur_hi = cur_lo = None; pd_hi = pd_lo = None; dia = None
    on_key = None; on_hi = on_lo = None
    sinais = []
    for idx, b in enumerate(bars):
        dt = b['dt']; d = dt.strftime('%Y-%m-%d'); m = dp.mins(dt); dow = dt.weekday()
        em_sessao = dp.SESSAO_INICIO <= m < dp.ENTRADA_FIM
        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d
            cur_hi = b['h'] if em_sessao else None
            cur_lo = b['l'] if em_sessao else None
        elif em_sessao:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
        chave_seg = None
        if dow == 6 and m >= dp.DOM_NOITE_INICIO: chave_seg = (dt+timedelta(days=1)).strftime('%Y-%m-%d')
        elif dow == 0 and m < dp.SESSAO_INICIO: chave_seg = d
        if chave_seg is not None:
            if chave_seg != on_key: on_key, on_hi, on_lo = chave_seg, b['h'], b['l']
            else: on_hi = max(on_hi, b['h']); on_lo = min(on_lo, b['l'])
        if not (ANO_INICIO <= d <= ANO_FIM): continue
        if not (dp.SESSAO_INICIO <= m < dp.ENTRADA_FIM): continue
        if pd_hi is None or pd_lo is None: continue
        if dow == 0 and on_key == d and on_hi is not None and on_hi > 0: n_hi, n_lo = on_hi, on_lo
        else: n_hi, n_lo = pd_hi, pd_lo
        ev = dp.avalia_bar(b, n_hi, n_lo, tol_pts, MAX_DIST)
        if ev is not None and ev['cat'] == 'OPEROU':
            sinais.append({'idx_sinal': idx, 'lado': ev['lado'], 'data': d,
                            'hora': dt.strftime('%H:%M'), 'dow': dow,
                            'n_hi': n_hi, 'n_lo': n_lo, 'nivel': ev['nivel'],
                            'close_sinal': b['c'], 'dist_nivel': ev['dist']})
    return sinais


def roda(bars, sinais, motor):
    """motor: 'BAR_LAG' | 'TICK_OTIM' | 'TICK_PESS'."""
    por_idx = {}
    for s in sinais: por_idx.setdefault(s['idx_sinal'], s)
    trades = []
    i = 0; n = len(bars)
    trades_dia = {}; pnl_dia = {}
    while i < n:
        b = bars[i]
        d = b['dt'].strftime('%Y-%m-%d')
        s = por_idx.get(i)
        if s is None or i + 1 >= n:
            i += 1; continue
        if trades_dia.get(d, 0) >= MAX_TRADES_DIA: i += 1; continue
        if pnl_dia.get(d, 0.0) <= -STOP_DIA_USD: i += 1; continue

        # ---- ENTRADA: open da barra SEGUINTE (fiel ao NT8 OnBarClose + ordem a mercado) ----
        bi = bars[i + 1]
        if bi['dt'].strftime('%Y-%m-%d') != d: i += 1; continue
        entry = bi['o']
        lado = 1 if s['lado'] == 'LONG' else -1
        stop = entry - SL*lado
        alvo = entry + TP*lado
        fav = entry
        be = False
        mfe = 0.0; mae = 0.0
        saida = None; motivo = None; idx_saida = None

        j = i + 1
        while j < n:
            bb = bars[j]
            if bb['dt'].strftime('%Y-%m-%d') != d:
                saida = bars[j-1]['c']; motivo = 'FIM_DIA'; idx_saida = j-1; break
            mj = dp.mins(bb['dt'])
            fav_exc = (bb['h']-entry)*lado if lado > 0 else (entry-bb['l'])
            adv_exc = (entry-bb['l'])*1 if lado > 0 else (bb['h']-entry)
            if lado > 0: fav_exc = bb['h']-entry; adv_exc = entry-bb['l']
            else:        fav_exc = entry-bb['l']; adv_exc = bb['h']-entry
            mfe = max(mfe, fav_exc); mae = max(mae, adv_exc)

            if mj >= 16*60+55:   # FlattenHora 1655
                saida = bb['c']; motivo = 'FLATTEN'; idx_saida = j; break

            if motor == 'BAR_LAG':
                # ordem EXATA do GerenciaPosicao(): alvo -> stop -> depois atualiza trailing
                if (lado > 0 and bb['h'] >= alvo) or (lado < 0 and bb['l'] <= alvo):
                    saida = alvo; motivo = 'TP'; idx_saida = j; break
                if (lado > 0 and bb['l'] <= stop) or (lado < 0 and bb['h'] >= stop):
                    saida = stop; motivo = ('TRAIL' if be else 'SL'); idx_saida = j; break
                if lado > 0:
                    fav = max(fav, bb['h'])
                    if not be and (fav-entry) >= BE_TRIG: be = True
                    if be: stop = max(stop, max(entry+BE_LOCK, fav-TRAIL))
                else:
                    fav = min(fav, bb['l'])
                    if not be and (entry-fav) >= BE_TRIG: be = True
                    if be: stop = min(stop, min(entry-BE_LOCK, fav+TRAIL))
            else:
                # TICK: trailing atualiza DENTRO da barra. Sem saber a sequencia intrabar,
                # limitamos os dois extremos possiveis.
                if motor == 'TICK_OTIM':
                    # favoravel primeiro: sobe ate o high, trailing acompanha, so depois cai
                    if lado > 0:
                        if bb['h'] >= alvo: saida = alvo; motivo='TP'; idx_saida=j; break
                        fav = max(fav, bb['h'])
                        if not be and (fav-entry) >= BE_TRIG: be = True
                        if be: stop = max(stop, max(entry+BE_LOCK, fav-TRAIL))
                        if bb['l'] <= stop: saida=stop; motivo=('TRAIL' if be else 'SL'); idx_saida=j; break
                    else:
                        if bb['l'] <= alvo: saida = alvo; motivo='TP'; idx_saida=j; break
                        fav = min(fav, bb['l'])
                        if not be and (entry-fav) >= BE_TRIG: be = True
                        if be: stop = min(stop, min(entry-BE_LOCK, fav+TRAIL))
                        if bb['h'] >= stop: saida=stop; motivo=('TRAIL' if be else 'SL'); idx_saida=j; break
                else:  # TICK_PESS: adverso primeiro
                    if lado > 0:
                        if bb['l'] <= stop: saida=stop; motivo=('TRAIL' if be else 'SL'); idx_saida=j; break
                        if bb['h'] >= alvo: saida=alvo; motivo='TP'; idx_saida=j; break
                        fav = max(fav, bb['h'])
                        if not be and (fav-entry) >= BE_TRIG: be = True
                        if be: stop = max(stop, max(entry+BE_LOCK, fav-TRAIL))
                    else:
                        if bb['h'] >= stop: saida=stop; motivo=('TRAIL' if be else 'SL'); idx_saida=j; break
                        if bb['l'] <= alvo: saida=alvo; motivo='TP'; idx_saida=j; break
                        fav = min(fav, bb['l'])
                        if not be and (entry-fav) >= BE_TRIG: be = True
                        if be: stop = min(stop, min(entry-BE_LOCK, fav+TRAIL))
            j += 1
        if saida is None:
            saida = bars[min(j, n-1)]['c']; motivo='EOD'; idx_saida = min(j, n-1)

        pts = (saida-entry)*lado
        usd = pts*PV - RT
        dur = idx_saida - (i+1)
        trades.append({**s, 'entry': entry, 'saida': saida, 'pts': pts, 'usd': usd,
                        'motivo': motivo, 'mfe': mfe, 'mae': mae, 'dur_bars': dur,
                        'be_ativado': be, 'gap_entrada': (bi['o']-s['close_sinal'])*lado})
        trades_dia[d] = trades_dia.get(d, 0) + 1
        pnl_dia[d] = pnl_dia.get(d, 0.0) + usd
        i = idx_saida + 1
    return trades


def stats(trades, nome):
    w = [t for t in trades if t['usd'] > 0]; l = [t for t in trades if t['usd'] < 0]
    gm = sum(t['usd'] for t in w)/len(w) if w else 0
    pm = sum(t['usd'] for t in l)/len(l) if l else 0
    ratio = gm/abs(pm) if pm else 0
    wr = len(w)/len(trades)*100 if trades else 0
    pnl = sum(t['usd'] for t in trades)
    gross_w = sum(t['usd'] for t in w); gross_l = abs(sum(t['usd'] for t in l))
    pf = gross_w/gross_l if gross_l else 0
    exp = pnl/len(trades) if trades else 0
    print(f"{nome:<12}{len(trades):<7}{wr:<7.1f}${gm:<9.1f}${pm:<10.1f}{ratio:<8.2f}{pf:<7.2f}${exp:<9.1f}${pnl:.1f}")
    return {'n':len(trades),'wr':wr,'gm':gm,'pm':pm,'ratio':ratio,'pf':pf,'exp':exp,'pnl':pnl}


def main():
    bars = dp.carregar_1min(dp.PASTA_DADOS)
    print(f"{len(bars):,} candles de 1min\n")
    sinais = coleta_sinais(bars)
    print(f"{len(sinais)} sinais brutos\n")

    print("="*100)
    print("COMPARACAO DOS 3 MOTORES DE SAIDA (mesma entrada, mesma config)")
    print("="*100)
    print(f"{'Motor':<12}{'N':<7}{'WR%':<7}{'GanhoMed':<10}{'PerdaMed':<11}{'Ratio':<8}{'PF':<7}{'Expect':<10}{'PnL'}")
    res = {}
    tr = {}
    for motor in ['BAR_LAG', 'TICK_OTIM', 'TICK_PESS']:
        tr[motor] = roda(bars, sinais, motor)
        res[motor] = stats(tr[motor], motor)
    print("\nREAL medido no forward test junho/2026: WR 67,1% | ratio 0,54")
    print("(o ao vivo usa OnMarketData tick a tick -> deve cair ENTRE TICK_OTIM e TICK_PESS)")

    T = tr['BAR_LAG']
    # ---------- MFE/MAE ----------
    print("\n" + "="*100); print("MFE / MAE (motor BAR_LAG)"); print("="*100)
    def med(xs):
        xs = sorted(xs); n=len(xs)
        return xs[n//2] if n%2 else (xs[n//2-1]+xs[n//2])/2
    w = [t for t in T if t['usd']>0]; l = [t for t in T if t['usd']<0]
    for nome, grp in [('TODOS', T), ('VENCEDORES', w), ('PERDEDORES', l)]:
        if not grp: continue
        print(f"{nome:<14} MFE med={sum(t['mfe'] for t in grp)/len(grp):6.2f} mediana={med([t['mfe'] for t in grp]):6.2f} | "
              f"MAE med={sum(t['mae'] for t in grp)/len(grp):6.2f} mediana={med([t['mae'] for t in grp]):6.2f}")

    print(f"\n{'Bucket MFE':<14}{'Todos':<12}{'Vencedores':<14}{'Perdedores'}")
    for bkt in MFE_BUCKETS:
        a=sum(1 for t in T if t['mfe']>=bkt); b=sum(1 for t in w if t['mfe']>=bkt); c=sum(1 for t in l if t['mfe']>=bkt)
        print(f"+{bkt:<13}{a} ({a/len(T)*100:4.1f}%){'':<3}{b} ({b/len(w)*100:4.1f}%){'':<5}{c} ({c/len(l)*100:4.1f}%)")
    print(f"\n{'Bucket MAE':<14}{'Todos':<12}{'Vencedores':<14}{'Perdedores'}")
    for bkt in MAE_BUCKETS:
        a=sum(1 for t in T if t['mae']>=bkt); b=sum(1 for t in w if t['mae']>=bkt); c=sum(1 for t in l if t['mae']>=bkt)
        print(f"-{bkt:<13}{a} ({a/len(T)*100:4.1f}%){'':<3}{b} ({b/len(w)*100:4.1f}%){'':<5}{c} ({c/len(l)*100:4.1f}%)")

    # ---------- motivos de saida ----------
    print("\n" + "="*100); print("MOTIVOS DE SAIDA"); print("="*100)
    mot = {}
    for t in T: mot[t['motivo']] = mot.get(t['motivo'],0)+1
    for k,v in sorted(mot.items(), key=lambda x:-x[1]):
        pnl_k = sum(t['usd'] for t in T if t['motivo']==k)
        print(f"  {k:<12}{v:>5} ({v/len(T)*100:5.1f}%)  PnL=${pnl_k:>10.1f}")

    # ---------- "e se saisse em +X" ----------
    print("\n" + "="*100); print("SE TIVESSE SAIDO EM +X (usando MFE real; perdedores que nunca chegaram = stop cheio)")
    print("="*100)
    print(f"{'Alvo fixo':<12}{'Atingiu':<16}{'PnL total':<14}{'vs atual'}")
    pnl_atual = sum(t['usd'] for t in T)
    for alvo in [5,10,15,20,30,40,50,60]:
        tot = 0.0; hits = 0
        for t in T:
            if t['mfe'] >= alvo: tot += alvo*PV - RT; hits += 1
            else: tot += -SL*PV - RT   # nao chegou -> assume stop cheio (conservador)
        print(f"+{alvo:<11}{hits} ({hits/len(T)*100:4.1f}%){'':<5}${tot:<13.1f}{tot-pnl_atual:+.1f}")

    # ---------- classificacao ----------
    print("\n" + "="*100); print("CLASSIFICACAO DOS TRADES"); print("="*100)
    def classifica(t):
        if t['motivo']=='TP': return 'A) Reversao limpa (TP)'
        if t['mfe'] < 2.5: return 'D) Stop imediato / sem excursao'
        if t['usd'] < 0 and t['mfe'] >= 10: return 'E) Chegou a +10 e devolveu p/ loss'
        if t['usd'] < 0 and t['mfe'] >= 5: return 'C) Falso toque (+5 e devolveu)'
        if t['usd'] < 0: return 'I) Perdedor sem excursao relevante'
        if t['motivo']=='TRAIL' and t['mfe'] >= 20: return 'F) Trailing cortou trade grande (MFE>=20)'
        if t['motivo']=='TRAIL': return 'B) Reversao curta (trailing)'
        return 'H) Outro'
    cls = {}
    for t in T:
        k = classifica(t); cls.setdefault(k, []).append(t)
    for k in sorted(cls, key=lambda x: -len(cls[x])):
        g = cls[k]; pnl_g = sum(t['usd'] for t in g)
        mfe_g = sum(t['mfe'] for t in g)/len(g)
        print(f"  {k:<42}{len(g):>5} ({len(g)/len(T)*100:5.1f}%)  PnL=${pnl_g:>10.1f}  MFEmed={mfe_g:6.2f}")

    # ---------- gap de entrada ----------
    print("\n" + "="*100); print("GAP DE ENTRADA (open da barra seguinte vs close do sinal)"); print("="*100)
    gaps = [t['gap_entrada'] for t in T]
    contra = sum(1 for g in gaps if g < 0)
    print(f"  Gap medio: {sum(gaps)/len(gaps):+.3f}pt | mediana: {med(gaps):+.3f}pt")
    print(f"  Trades que abriram CONTRA (pior preco): {contra} ({contra/len(gaps)*100:.1f}%)")
    print(f"  Custo total do gap: ${sum(gaps)*PV:+.1f}")

    csvp = os.path.join(os.path.dirname(__file__), 'diagnostico_mfe_mae_trades.csv')
    with open(csvp,'w',newline='',encoding='utf-8') as f:
        campos = ['data','hora','dow','lado','entry','saida','pts','usd','motivo','mfe','mae',
                  'dur_bars','be_ativado','n_hi','n_lo','nivel','dist_nivel','gap_entrada','close_sinal']
        wcsv = csv.DictWriter(f, fieldnames=campos, extrasaction='ignore')
        wcsv.writeheader(); wcsv.writerows(T)
    print(f"\nCSV com todos os trades: {csvp}")

if __name__ == '__main__':
    main()
