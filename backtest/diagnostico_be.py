#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DIAGNOSTICO DO BREAKEVEN — dados REAIS do Market Replay (18/08/2026)

Parte 1: para cada trade REAL que ativou o BE (config producao: trail 1,75,
BE 3,75/2,5), localiza entrada/pico/saida no historico real de 1min (NQ_dados)
e traca PRA FRENTE a partir da saida real -- sem usar MFE de motor de backtest,
usando preco historico real que realmente aconteceu depois.

Parte 2: teste controlado, MESMOS sinais reais (toque+rejeicao), variando so
BE trigger/lock, trailing fixo em 1,75 -- simulacao bar a bar, com aviso
explicito de vies conhecido (ver rodape).
"""
import sys, os, csv
from datetime import timedelta
sys.path.insert(0, os.path.dirname(__file__))
import diagnostico_portoes as dp
import parse_trades_replay as ptr

TICK = dp.TICK
TOL = 1.0       # tolerancia de preco p/ localizar entrada/pico/saida (pt)
JANELA_FRENTE = 300   # barras de 1min a examinar depois da saida (~5h, ate flatten)


def carrega_1min_indexado():
    bars = dp.carregar_1min(dp.PASTA_DADOS)
    por_dia = {}
    for i, b in enumerate(bars):
        d = b['dt'].strftime('%Y-%m-%d')
        por_dia.setdefault(d, []).append(i)
    return bars, por_dia


def localiza_trade(bars, idxs_dia, t):
    """Retorna (entry_idx, peak_idx, exit_idx) ou None se nao localizar com confianca.
    BUG CORRIGIDO 18/08: a hora do log do NT8 (Print/Time[0]) e' BRT (fuso de
    exibicao do grafico), NAO ET -- confirmado cruzando 2 trades independentes
    contra dado baixado direto do feed (MNQ JUN26/SEP26, conta Apex). BRT = ET+1h
    (BRT UTC-3, ET/EDT UTC-4). Os bars aqui estao em ET (carregar_1min converte
    pra ET) -- entao a hora do log precisa +1h pra virar ET antes de buscar."""
    if t['hora'] is None or not idxs_dia:
        return None
    hh, mm = map(int, t['hora'].split(':'))
    # BRT (UTC-3) -> ET (UTC-4): ET = BRT - 1h (ET fica 1h ATRAS do BRT).
    # Conferido com 2 trades reais contra dado baixado direto do feed:
    # log "14:33" BRT bateu com a barra de 13:33 ET (17:33 UTC), nao 15:33.
    alvo_min = (hh - 1) * 60 + mm
    if alvo_min < 0: alvo_min += 24 * 60
    # acha a barra de TOQUE (hora do sinal) -> entrada e' a barra seguinte
    cand = [i for i in idxs_dia if dp.mins(bars[i]['dt']) == alvo_min]
    if not cand:
        return None
    sig_idx = cand[0]
    entry_idx = sig_idx + 1
    if entry_idx >= len(bars) or bars[entry_idx]['dt'].strftime('%Y-%m-%d') != t['data']:
        return None
    if abs(bars[entry_idx]['o'] - t['entry']) > TOL:
        # tenta mais 2 barras adiante (spam de toques sem entrada pode ter deslocado)
        achou = False
        for k in range(2, 5):
            if entry_idx + k < len(bars) and abs(bars[entry_idx + k]['o'] - t['entry']) <= TOL:
                entry_idx = entry_idx + k; achou = True; break
        if not achou:
            return None

    lado = 1 if t['lado'] == 'LONG' else -1
    entry = t['entry']

    # acha o PICO (fav) andando pra frente
    peak_idx = entry_idx
    melhor_fav = entry
    j = entry_idx
    limite = min(entry_idx + JANELA_FRENTE, len(bars))
    while j < limite and bars[j]['dt'].strftime('%Y-%m-%d') == t['data']:
        preco_fav = bars[j]['h'] if lado > 0 else bars[j]['l']
        exc = (preco_fav - entry) * lado
        if exc > (melhor_fav - entry) * lado:
            melhor_fav = preco_fav
        if abs(melhor_fav - t['fav']) <= TOL:
            peak_idx = j
            break
        j += 1
    else:
        return None  # nao achou o pico esperado na janela -> baixa confianca, descarta

    # acha a SAIDA andando pra frente a partir do pico
    exit_idx = None
    j = peak_idx
    while j < limite and bars[j]['dt'].strftime('%Y-%m-%d') == t['data']:
        lo, hi = bars[j]['l'], bars[j]['h']
        if lo - TOL <= t['saida'] <= hi + TOL:
            exit_idx = j
            break
        j += 1
    if exit_idx is None:
        return None

    return entry_idx, peak_idx, exit_idx


def traca_frente(bars, t, exit_idx):
    """A partir da barra de saida (exclusive), traca o que o preco fez depois."""
    lado = 1 if t['lado'] == 'LONG' else -1
    entry = t['entry']; saida = t['saida']
    tp_nivel = entry + 60 * lado
    sl_orig_nivel = entry - 12.5 * lado

    extra_mfe = 0.0
    idx_extra_mfe = None
    hit_tp = False
    hit_sl_orig = False
    voltou_ate_entry = False

    j = exit_idx + 1
    limite = min(exit_idx + JANELA_FRENTE, len(bars))
    while j < limite and bars[j]['dt'].strftime('%Y-%m-%d') == t['data'] and dp.mins(bars[j]['dt']) < 1655:
        hi, lo = bars[j]['h'], bars[j]['l']
        fav_extra = (hi - saida) * lado if lado > 0 else (saida - lo)
        if lado < 0:
            fav_extra = saida - lo
        else:
            fav_extra = hi - saida
        if fav_extra > extra_mfe:
            extra_mfe = fav_extra
            idx_extra_mfe = j
        if lado > 0 and hi >= tp_nivel: hit_tp = True
        if lado < 0 and lo <= tp_nivel: hit_tp = True
        if lado > 0 and lo <= sl_orig_nivel: hit_sl_orig = True
        if lado < 0 and hi >= sl_orig_nivel: hit_sl_orig = True
        if lado > 0 and lo <= entry: voltou_ate_entry = True
        if lado < 0 and hi >= entry: voltou_ate_entry = True
        j += 1

    tempo_min = (idx_extra_mfe - exit_idx) if idx_extra_mfe else 0
    return {'extra_mfe': extra_mfe, 'tempo_extra_mfe_min': tempo_min,
            'hit_tp_depois': hit_tp, 'hit_sl_orig_depois': hit_sl_orig,
            'voltou_ate_entry_depois': voltou_ate_entry}


def classifica(extra_mfe, voltou_ate_entry):
    if extra_mfe >= 10:
        return 'D) BE PROBLEMATICO'
    if extra_mfe >= 3:
        return 'B) BE PREMATURO'
    if voltou_ate_entry:
        return 'A) BE CORRETO'
    return 'C) BE NEUTRO'


def main():
    trades = ptr.carrega_todos()
    bars, por_dia = carrega_1min_indexado()
    be_trades = [t for t in trades if t['be_ativado']]
    print(f"{len(trades)} trades reais parseados | {len(be_trades)} ativaram BE ({len(be_trades)/len(trades)*100:.1f}%)\n")

    print("=" * 130)
    print("PARTE 1 — DIAGNOSTICO TRADE A TRADE (so os que ativaram BE)")
    print("=" * 130)
    hdr = f"{'Data':<12}{'Sinal':<10}{'Lado':<7}{'MFE':<7}{'Saida+2,5?':<12}{'ExtraMFE':<10}{'t(min)':<8}{'TP dps?':<9}{'SLorig dps?':<12}{'Class'}"
    print(hdr)

    linhas = []
    nao_localizados = 0
    for t in be_trades:
        loc = localiza_trade(bars, por_dia.get(t['data'], []), t)
        mfe = abs(t['fav'] - t['entry'])
        saida_25 = abs(abs(t['saida'] - t['entry']) - 2.5) < 0.05
        if loc is None:
            nao_localizados += 1
            print(f"{t['data']:<12}{t['sinal']:<10}{t['lado']:<7}{mfe:<7.2f}{'sim' if saida_25 else 'nao':<12}"
                  f"{'?':<10}{'?':<8}{'?':<9}{'?':<12}NAO LOCALIZADO")
            continue
        entry_idx, peak_idx, exit_idx = loc
        fr = traca_frente(bars, t, exit_idx)
        cls = classifica(fr['extra_mfe'], fr['voltou_ate_entry_depois'])
        print(f"{t['data']:<12}{t['sinal']:<10}{t['lado']:<7}{mfe:<7.2f}{'sim' if saida_25 else 'nao':<12}"
              f"{fr['extra_mfe']:<10.2f}{fr['tempo_extra_mfe_min']:<8}"
              f"{'SIM' if fr['hit_tp_depois'] else 'nao':<9}{'SIM' if fr['hit_sl_orig_depois'] else 'nao':<12}{cls}")
        linhas.append({**t, 'mfe': mfe, 'saida_25': saida_25, **fr, 'classe': cls})

    print(f"\n{nao_localizados} de {len(be_trades)} trades nao puderam ser localizados com confianca "
          f"no historico (tolerancia {TOL}pt) e foram excluidos da classificacao abaixo.")

    print("\n" + "=" * 130)
    print("CLASSIFICACAO (so o subgrupo que SAIU EXATAMENTE EM +2,50)")
    print("=" * 130)
    grupo25 = [l for l in linhas if l['saida_25']]
    cont = {}
    for l in grupo25:
        cont[l['classe']] = cont.get(l['classe'], 0) + 1
    for k in sorted(cont):
        pct = cont[k] / len(grupo25) * 100 if grupo25 else 0
        print(f"  {k:<25}{cont[k]:>4}  ({pct:.1f}%)")
    print(f"\nTotal no grupo +2,50: {len(grupo25)}")

    grupo_trail = [l for l in linhas if not l['saida_25']]
    print(f"\nBE ativou e saiu via TRAILING acima do lock (nao classificado A-D): {len(grupo_trail)}")
    if grupo_trail:
        mfe_med = sum(l['mfe'] for l in grupo_trail) / len(grupo_trail)
        print(f"  MFE medio desse grupo: {mfe_med:.2f}pt (media ja capturada bem alem do lock)")

    csvp = os.path.join(os.path.dirname(__file__), 'diagnostico_be_trades.csv')
    with open(csvp, 'w', newline='', encoding='utf-8') as f:
        campos = ['data', 'sinal', 'lado', 'entry', 'fav', 'saida', 'pnl', 'mfe', 'saida_25',
                   'extra_mfe', 'tempo_extra_mfe_min', 'hit_tp_depois', 'hit_sl_orig_depois',
                   'voltou_ate_entry_depois', 'classe']
        w = csv.DictWriter(f, fieldnames=campos, extrasaction='ignore')
        w.writeheader(); w.writerows(linhas)
    print(f"\nCSV: {csvp}")

if __name__ == '__main__':
    main()
