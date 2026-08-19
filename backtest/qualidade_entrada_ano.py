#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QUALIDADE DA ENTRADA — ANO INTEIRO (18/08/2026)

Mesmas features da analise de 43 trades reais de junho, agora em cima de TODOS
os sinais (OPEROU) do ano inteiro no NQ_dados (ja validado que bate com o
preco real). Objetivo: separar H1 (excesso sobre o nivel prediz MFE, sinal de
qualidade real) de H2 (e so autocorrelacao com regime de volatilidade/ATR).
"""
import sys, os, csv
from datetime import timedelta
sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp
import analise_qualidade_entrada as aqe

ANO_INICIO, ANO_FIM = '2025-06-11', '2026-06-11'
JANELA_MFE_MIN = 60


def coleta_sinais_com_contexto(bars):
    tol_pts = dp.TICK * 20; MAX_DIST = 15.0
    cur_hi = cur_lo = None; pd_hi = pd_lo = None; dia = None
    on_key = None; on_hi = on_lo = None
    linhas = []
    idxs_dia_atual = []

    for idx, b in enumerate(bars):
        dt = b['dt']; d = dt.strftime('%Y-%m-%d'); m = dp.mins(dt); dow = dt.weekday()
        em_sessao = dp.SESSAO_INICIO <= m < dp.ENTRADA_FIM
        if d != dia:
            if cur_hi is not None: pd_hi, pd_lo = cur_hi, cur_lo
            dia = d; cur_hi = b['h'] if em_sessao else None; cur_lo = b['l'] if em_sessao else None
            idxs_dia_atual = []
        elif em_sessao:
            cur_hi = b['h'] if cur_hi is None else max(cur_hi, b['h'])
            cur_lo = b['l'] if cur_lo is None else min(cur_lo, b['l'])
        if em_sessao:
            idxs_dia_atual.append(idx)
        chave_seg = None
        if dow == 6 and m >= dp.DOM_NOITE_INICIO: chave_seg = (dt+timedelta(days=1)).strftime('%Y-%m-%d')
        elif dow == 0 and m < dp.SESSAO_INICIO: chave_seg = d
        if chave_seg is not None:
            if chave_seg != on_key: on_key, on_hi, on_lo = chave_seg, b['h'], b['l']
            else: on_hi = max(on_hi, b['h']); on_lo = min(on_lo, b['l'])
        if not (ANO_INICIO <= d <= ANO_FIM): continue
        if not em_sessao: continue
        if pd_hi is None or pd_lo is None: continue

        if dow == 0 and on_key == d and on_hi is not None and on_hi > 0: n_hi, n_lo = on_hi, on_lo
        else: n_hi, n_lo = pd_hi, pd_lo

        ev = dp.avalia_bar(b, n_hi, n_lo, tol_pts, MAX_DIST)
        if ev is None or ev['cat'] != 'OPEROU': continue

        lado = ev['lado']; nivel = ev['nivel']
        entry_idx = idx + 1
        if entry_idx >= len(bars) or bars[entry_idx]['dt'].strftime('%Y-%m-%d') != d: continue
        entry = bars[entry_idx]['o']

        candle_ant = bars[idx - 1] if idx > 0 else b
        corpo_ant = abs(candle_ant['c'] - candle_ant['o'])
        dir_ant = 1 if candle_ant['c'] >= candle_ant['o'] else -1
        seq = 0; k = idx - 1
        while k >= 0 and bars[k]['dt'].strftime('%Y-%m-%d') == d:
            dk = 1 if bars[k]['c'] >= bars[k]['o'] else -1
            if dk != dir_ant: break
            seq += 1; k -= 1
        vel3 = abs(bars[idx]['c'] - bars[max(0, idx - 3)]['c'])
        dist_nivel = abs(entry - nivel)
        excesso = ev['dist']

        mfe60, mae60 = aqe.mfe_janela(bars, entry_idx, entry, lado, JANELA_MFE_MIN)

        linhas.append({
            'idx': idx, 'data': d, 'lado': lado, 'entry': entry, 'nivel': round(nivel, 2),
            'dist_nivel': round(dist_nivel, 2),
            'range_5c': round(aqe.range_bars(bars, idx, 5), 2),
            'range_15c': round(aqe.range_bars(bars, idx, 15), 2),
            'atr14': round(aqe.atr_simples(bars, idx), 2),
            'corpo_candle_ant': round(corpo_ant, 2), 'seq_mesma_direcao': seq,
            'vel_3min': round(vel3, 2), 'excesso_sobre_nivel': round(excesso, 2),
            'hora_min_et': m, 'mfe60': round(mfe60, 2), 'mae60': round(mae60, 2),
        })
    return linhas


def pearson(xs, ys):
    n = len(xs); mx = sum(xs)/n; my = sum(ys)/n
    cov = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
    vx = sum((x-mx)**2 for x in xs); vy = sum((y-my)**2 for y in ys)
    return cov/((vx*vy)**0.5) if vx > 0 and vy > 0 else 0


def correlacao_parcial(x, y, z):
    """Correlacao entre x e y CONTROLANDO por z (formula padrao de corr parcial)."""
    rxy = pearson(x, y); rxz = pearson(x, z); ryz = pearson(y, z)
    denom = ((1 - rxz**2) * (1 - ryz**2)) ** 0.5
    return (rxy - rxz*ryz) / denom if denom else 0


def main():
    bars = dp.carregar_1min(dp.PASTA_DADOS)
    print(f"{len(bars):,} candles carregados\n")
    linhas = coleta_sinais_com_contexto(bars)
    n = len(linhas)
    print(f"{n} sinais no ano inteiro (com contexto pre-entrada + MFE60)\n")

    csvp = os.path.join(os.path.dirname(__file__), 'qualidade_entrada_ano.csv')
    with open(csvp, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0].keys())); w.writeheader(); w.writerows(linhas)

    mfe = sorted(r['mfe60'] for r in linhas)
    print("=== DISTRIBUICAO MFE60 (ano inteiro) ===")
    print(f"min={mfe[0]:.2f} p25={mfe[n//4]:.2f} mediana={mfe[n//2]:.2f} p75={mfe[3*n//4]:.2f} "
          f"max={mfe[-1]:.2f} media={sum(mfe)/n:.2f}\n")

    def grupo(m):
        if m < 5: return 'G1'
        if m < 10: return 'G2'
        if m < 15: return 'G3'
        return 'G4'
    from collections import Counter
    c = Counter(grupo(r['mfe60']) for r in linhas)
    print("=== GRUPOS (agora com N grande) ===")
    for g in ['G1', 'G2', 'G3', 'G4']:
        print(f"  {g}: {c.get(g, 0)} ({c.get(g,0)/n*100:.1f}%)")

    feats = ['dist_nivel', 'range_5c', 'range_15c', 'atr14', 'corpo_candle_ant',
              'seq_mesma_direcao', 'vel_3min', 'excesso_sobre_nivel', 'hora_min_et']
    mfe_vals = [r['mfe60'] for r in linhas]
    print("\n=== CORRELACAO SIMPLES com MFE60 (N={}) ===".format(n))
    for feat in feats:
        xs = [r[feat] for r in linhas]
        print(f"  {feat:<22} r={pearson(xs, mfe_vals):+.3f}")

    print("\n=== TESTE H1 vs H2: excesso_sobre_nivel controlando por ATR14 ===")
    xs_exc = [r['excesso_sobre_nivel'] for r in linhas]
    xs_atr = [r['atr14'] for r in linhas]
    r_simples = pearson(xs_exc, mfe_vals)
    r_parcial = correlacao_parcial(xs_exc, mfe_vals, xs_atr)
    print(f"  Correlacao SIMPLES excesso->MFE:              {r_simples:+.3f}")
    print(f"  Correlacao PARCIAL excesso->MFE (controlando ATR): {r_parcial:+.3f}")
    print(f"  Correlacao ATR->MFE:                          {pearson(xs_atr, mfe_vals):+.3f}")
    print(f"  Correlacao excesso->ATR (confound?):          {pearson(xs_exc, xs_atr):+.3f}")

    print("\n=== TESTE POR QUARTIS DE ATR (excesso ainda prediz MFE DENTRO de cada regime?) ===")
    atr_sorted = sorted(linhas, key=lambda r: r['atr14'])
    quart = n // 4
    for qi, nome in enumerate(['Q1 (ATR baixo)', 'Q2', 'Q3', 'Q4 (ATR alto)']):
        sub = atr_sorted[qi*quart: (qi+1)*quart] if qi < 3 else atr_sorted[qi*quart:]
        xs = [r['excesso_sobre_nivel'] for r in sub]
        ys = [r['mfe60'] for r in sub]
        atrmed = sorted(r['atr14'] for r in sub)[len(sub)//2]
        print(f"  {nome:<16} N={len(sub):<5} ATRmed={atrmed:<7.2f} corr(excesso,MFE)={pearson(xs,ys):+.3f} "
              f"MFEmed={sorted(ys)[len(ys)//2]:.1f}")

    print("\n=== WR real (motor completo) por bucket de excesso_sobre_nivel ===")
    exc_sorted = sorted(linhas, key=lambda r: r['excesso_sobre_nivel'])
    for qi, nome in enumerate(['Q1 (excesso baixo)', 'Q2', 'Q3', 'Q4 (excesso alto)']):
        sub = exc_sorted[qi*quart: (qi+1)*quart] if qi < 3 else exc_sorted[qi*quart:]
        mfes = sorted(r['mfe60'] for r in sub)
        print(f"  {nome:<20} N={len(sub):<5} MFEmediana={mfes[len(mfes)//2]:.1f} MFEmedia={sum(mfes)/len(mfes):.1f}")

if __name__ == '__main__':
    main()
