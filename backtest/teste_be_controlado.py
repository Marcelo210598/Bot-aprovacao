#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TESTE CONTROLADO DO BREAKEVEN (18/08/2026)

MESMOS sinais reais (toque+rejeicao, motor ja validado), trailing FIXO em 1,75,
SL 12,5, TP 60 -- SO varia BE trigger/lock. Simulacao em 1min, ano inteiro,
slippage 2 ticks, mesma metodologia ja usada em todos os testes anteriores
dessa conversa (grid_trailing_alvo.py / sensibilidade_breakeven.py).

AVISO DE VIES CONHECIDO (achado hoje, auditoria + teste em Replay): simulacao
bar-a-bar de 1min SUPERESTIMA o ganho medio absoluto em ~2,5x frente ao real
(confirmado comparando os 3 motores de simulacao contra 84 trades reais de
producao). Os NUMEROS ABSOLUTOS abaixo devem ser lidos como ranking relativo
entre configs, NAO como previsao do resultado real em dólares.
"""
import sys, os, csv
from datetime import timedelta
sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp

TICK = dp.TICK; TOL_TICKS = 20; MAX_DIST = 15.0
PTS_SL = 12.5; PTS_TP = 60.0; PTS_TRAIL = 1.75   # FIXOS em todos os testes
MNQ_PV = 2.0; N_CONTR = 5; RT = 1.20 * N_CONTR
SLIP = 2 * TICK
STOP_DIA_PT = 750.0 / (MNQ_PV * N_CONTR); MAX_TRADES_DIA = 12
ANO_INICIO, ANO_FIM = '2025-06-11', '2026-06-11'

CONFIGS = [
    ('1) Baseline (3,75 / 2,50)', 3.75, 2.50),
    ('2) BE conservador (3,75 / 1,25)', 3.75, 1.25),
    ('3) BE neutro (3,75 / 0,00)', 3.75, 0.00),
    ('4) BE tardio (5,00 / 2,50)', 5.00, 2.50),
]


def simula(bars, be_trig, be_lock):
    tol_pts = TOL_TICKS * TICK; pv = MNQ_PV * N_CONTR
    cur_hi = cur_lo = None; pd_hi = pd_lo = None; dia = None
    on_key = None; on_hi = on_lo = None
    pos = 0; entry = stop = alvo = fav = 0.0; be_feito = False
    pnl_dia0 = 0.0; realizado = 0.0; bloqueado_hoje = False
    trades = []

    def fecha(preco, motivo, d, idx_exit):
        nonlocal pos, realizado
        preco_real = preco - SLIP if pos > 0 else preco + SLIP
        pts = (preco_real - entry) if pos > 0 else (entry - preco_real)
        usd = pts * pv - RT
        realizado += usd
        trades.append({'pnl_usd': usd, 'pts': pts, 'motivo': motivo, 'data': d,
                        'lado': 1 if pos > 0 else -1, 'entry': entry, 'idx_exit': idx_exit})
        pos = 0

    for idx, b in enumerate(bars):
        dt = b['dt']; d = dt.strftime('%Y-%m-%d'); m = dp.mins(dt); dow = dt.weekday()
        em_sessao = dp.SESSAO_INICIO <= m < dp.ENTRADA_FIM
        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = b['h'] if em_sessao else None; cur_lo = b['l'] if em_sessao else None
            bloqueado_hoje = False; pnl_dia0 = realizado
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

        if pos != 0:
            saiu = False
            if pos > 0:
                if b['l'] <= stop: fecha(stop, 'BE_TRAIL' if be_feito else 'SL', d, idx); saiu = True
                elif b['h'] >= alvo: fecha(alvo, 'TP', d, idx); saiu = True
            else:
                if b['h'] >= stop: fecha(stop, 'BE_TRAIL' if be_feito else 'SL', d, idx); saiu = True
                elif b['l'] <= alvo: fecha(alvo, 'TP', d, idx); saiu = True
            if not saiu:
                if pos > 0:
                    fav = max(fav, b['h'])
                    if not be_feito and (fav - entry) >= be_trig: stop = max(stop, entry + be_lock); be_feito = True
                    if be_feito: stop = max(stop, fav - PTS_TRAIL)
                else:
                    fav = min(fav, b['l'])
                    if not be_feito and (entry - fav) >= be_trig: stop = min(stop, entry - be_lock); be_feito = True
                    if be_feito: stop = min(stop, fav + PTS_TRAIL)
            else:
                if STOP_DIA_PT > 0 and (realizado - pnl_dia0) <= -STOP_DIA_PT * pv: bloqueado_hoje = True
            continue

        if bloqueado_hoje or not (dp.SESSAO_INICIO <= m < dp.ENTRADA_FIM): continue
        if pd_hi is None or pd_lo is None: continue
        trades_hoje = sum(1 for t in trades if t['data'] == d)
        if MAX_TRADES_DIA > 0 and trades_hoje >= MAX_TRADES_DIA: continue

        if dow == 0 and on_key == d and on_hi is not None and on_hi > 0: n_hi, n_lo = on_hi, on_lo
        else: n_hi, n_lo = pd_hi, pd_lo
        ev = dp.avalia_bar(b, n_hi, n_lo, tol_pts, MAX_DIST)
        if ev is not None and ev['cat'] == 'OPEROU':
            if ev['lado'] == 'SHORT':
                entry = b['c'] - SLIP; pos = -1; stop = entry + PTS_SL; alvo = entry - PTS_TP
            else:
                entry = b['c'] + SLIP; pos = 1; stop = entry - PTS_SL; alvo = entry + PTS_TP
            fav = entry; be_feito = False
    return trades


def forward_check(bars, t, alvo_extra):
    """A partir do bar de saida, checa se o preco eventualmente teria batido
    entry +/- alvo_extra (contrafactual, MESMA serie -- consistente)."""
    lado = t['lado']; entry = t['entry']; nivel = entry + alvo_extra * lado
    j = t['idx_exit'] + 1
    d0 = bars[t['idx_exit']]['dt'].strftime('%Y-%m-%d')
    limite = min(j + 400, len(bars))
    while j < limite and bars[j]['dt'].strftime('%Y-%m-%d') == d0:
        if lado > 0 and bars[j]['h'] >= nivel: return True
        if lado < 0 and bars[j]['l'] <= nivel: return True
        j += 1
    return False


def maior_sequencia_perdas(trades):
    seq = maxseq = 0
    for t in trades:
        if t['pnl_usd'] < 0: seq += 1; maxseq = max(maxseq, seq)
        else: seq = 0
    return maxseq


def drawdown(trades):
    pico = acum = dd = 0.0
    for t in trades:
        acum += t['pnl_usd']; pico = max(pico, acum); dd = max(dd, pico - acum)
    return dd


def resume(bars, trades, nome):
    wins = [t for t in trades if t['pnl_usd'] > 0]; losses = [t for t in trades if t['pnl_usd'] < 0]
    gm = sum(t['pnl_usd'] for t in wins)/len(wins) if wins else 0
    pm = sum(t['pnl_usd'] for t in losses)/len(losses) if losses else 0
    ratio = gm/abs(pm) if pm else 0
    wr = len(wins)/len(trades)*100 if trades else 0
    pnl = sum(t['pnl_usd'] for t in trades)
    gross_w = sum(t['pnl_usd'] for t in wins); gross_l = abs(sum(t['pnl_usd'] for t in losses))
    pf = gross_w/gross_l if gross_l else 0
    exp = pnl/len(trades) if trades else 0
    n_be = sum(1 for t in trades if t['motivo']=='BE_TRAIL')
    pct_be = n_be/len(trades)*100 if trades else 0
    dd = drawdown(trades)
    seq = maior_sequencia_perdas(trades)

    # contrafactual: dos que NAO saíram no alvo, quantos teriam batido +10/+15/+20 depois
    nao_tp = [t for t in trades if t['motivo'] != 'TP']
    hit10 = sum(1 for t in nao_tp if forward_check(bars, t, 10))
    hit15 = sum(1 for t in nao_tp if forward_check(bars, t, 15))
    hit20 = sum(1 for t in nao_tp if forward_check(bars, t, 20))

    print(f"\n{nome}")
    print(f"  Trades={len(trades)}  WR={wr:.1f}%  Ratio={ratio:.2f}  PF={pf:.2f}  Expectancy=${exp:.1f}")
    print(f"  GanhoMed=${gm:.1f}  PerdaMed=${pm:.1f}  PnLTotal=${pnl:.1f}")
    print(f"  Saidas via BE/Trailing: {n_be} ({pct_be:.1f}%)  MaiorSeqPerdas={seq}  DDmax=${dd:.1f}")
    print(f"  Dos que nao bateram TP, quantos teriam alcancado +10 dps: {hit10} ({hit10/len(nao_tp)*100:.1f}%)")
    print(f"  ...+15 dps: {hit15} ({hit15/len(nao_tp)*100:.1f}%)   ...+20 dps: {hit20} ({hit20/len(nao_tp)*100:.1f}%)")
    return {'nome': nome, 'n': len(trades), 'wr': wr, 'ratio': ratio, 'pf': pf, 'exp': exp,
            'gm': gm, 'pm': pm, 'pnl': pnl, 'pct_be': pct_be, 'seq': seq, 'dd': dd,
            'hit10': hit10/len(nao_tp)*100, 'hit15': hit15/len(nao_tp)*100, 'hit20': hit20/len(nao_tp)*100}


def main():
    bars = dp.carregar_1min(dp.PASTA_DADOS)
    print(f"{len(bars):,} candles 1min carregados\n")
    print("=" * 100)
    print("TESTE CONTROLADO — SO o BE varia (trailing 1,75 / SL 12,5 / TP 60 fixos em TODOS)")
    print("=" * 100)
    resultados = []
    for nome, trig, lock in CONFIGS:
        trades = simula(bars, trig, lock)
        r = resume(bars, trades, nome)
        resultados.append(r)

    print("\n" + "=" * 100)
    print("TABELA COMPARATIVA")
    print("=" * 100)
    print(f"{'Config':<32}{'N':<6}{'WR%':<7}{'Ratio':<7}{'PF':<6}{'Exp$':<8}{'PnL':<10}{'%BE':<7}{'MaxSeq':<8}{'DD$':<9}{'+10dps':<8}{'+15dps':<8}{'+20dps'}")
    for r in resultados:
        print(f"{r['nome']:<32}{r['n']:<6}{r['wr']:<7.1f}{r['ratio']:<7.2f}{r['pf']:<6.2f}${r['exp']:<7.1f}"
              f"${r['pnl']:<9.1f}{r['pct_be']:<7.1f}{r['seq']:<8}${r['dd']:<8.1f}{r['hit10']:<8.1f}{r['hit15']:<8.1f}{r['hit20']:.1f}")

    csvp = os.path.join(os.path.dirname(__file__), 'teste_be_controlado.csv')
    with open(csvp, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(resultados[0].keys())); w.writeheader(); w.writerows(resultados)
    print(f"\nCSV: {csvp}")

if __name__ == '__main__':
    main()
