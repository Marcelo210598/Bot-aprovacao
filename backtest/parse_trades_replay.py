#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parser dos dias de forward-test-replay-25k/2026-06-1min/*.md -> lista
estruturada de trades REAIS (config producao: trail 1,75, BE 3,75/2,5)."""
import re, glob, os

PASTA = os.path.join(os.path.dirname(__file__), '..', 'forward-test-replay-25k', '2026-06-1min')


def pnum(s):
    s = s.strip().replace('.', '').replace(',', '.')
    s = re.sub(r'[^\d\.\-\+]', '', s)
    try: return float(s)
    except: return None


def parse_arquivo(path, data_str):
    txt = open(path, encoding='utf-8').read()
    blocos = re.split(r'\n## ', txt)
    trades = []
    for b in blocos[1:]:
        if not b.startswith(('🟢 Trade', '🔴 Trade')):
            continue
        header = b.splitlines()[0]
        lado = 'LONG' if 'LONG' in header else ('SHORT' if 'SHORT' in header else None)
        if lado is None: continue

        m_sinal = re.search(r'\|\s*Sinal\s*\|\s*`([^`]+)`', b)
        m_hora  = re.search(r'\|\s*(\d{1,2}:\d{2})\s*ET\s*\|', b)
        m_entry = re.search(r'Entrada \(fill real\)\s*\|\s*\*\*([\d\.,]+)\*\*', b)
        m_fav   = re.search(r'Favoreceu até\s*\|\s*([\d\.,]+)\s*\(([^)]*)\)', b)
        m_saida = re.search(r'Sa[ií]da\s*\|\s*([^|]*?)@\s*\*\*([\d\.,]+)\*\*', b)
        m_pnl   = re.search(r'PnL \(5 MNQ\)\*\*\s*\|\s*\*\*([+\-]?\$[\d\.,]+)\*\*', b)

        if not (m_sinal and m_entry and m_fav and m_saida and m_pnl):
            continue

        entry = pnum(m_entry.group(1))
        fav   = pnum(m_fav.group(1))
        fav_obs = m_fav.group(2)
        saida = pnum(m_saida.group(2))
        motivo_txt = m_saida.group(1)
        pnl_str = m_pnl.group(1).replace('$', '')
        pnl = pnum(pnl_str) * (-1 if pnl_str.strip().startswith('-') else 1)
        if pnl_str.strip().startswith('-'):
            pnl = -abs(pnum(pnl_str))
        else:
            pnl = abs(pnum(pnl_str))

        fav_obs_l = fav_obs.lower()
        be_ativado = 'ativado' in fav_obs_l and 'não' not in fav_obs_l and 'nao' not in fav_obs_l

        motivo = 'Trailing' if 'railing' in motivo_txt else ('Stop' if 'top' in motivo_txt else motivo_txt.strip())

        trades.append({
            'data': data_str, 'sinal': m_sinal.group(1), 'lado': lado,
            'hora': m_hora.group(1) if m_hora else None,
            'entry': entry, 'fav': fav, 'saida': saida, 'pnl': pnl,
            'be_ativado': be_ativado, 'motivo': motivo,
        })
    return trades


def carrega_todos():
    todos = []
    for f in sorted(glob.glob(os.path.join(PASTA, 'dia-*.md'))):
        base = os.path.basename(f)
        m = re.match(r'dia-\d+-(\d{2})-(\d{2})\.md', base)
        if not m: continue
        dia, mes = m.group(1), m.group(2)
        data_str = f'2026-{mes}-{dia}'
        todos.extend(parse_arquivo(f, data_str))
    return todos


if __name__ == '__main__':
    trades = carrega_todos()
    print(f"{len(trades)} trades parseados de {len(glob.glob(os.path.join(PASTA,'dia-*.md')))} arquivos\n")
    be_on = [t for t in trades if t['be_ativado']]
    print(f"BE ativado: {len(be_on)} de {len(trades)} ({len(be_on)/len(trades)*100:.1f}%)")
    n_25 = sum(1 for t in be_on if abs(abs(t['saida']-t['entry']) - 2.5) < 0.05)
    print(f"Saídas em exatamente +2,50 (dos que ativaram BE): {n_25} ({n_25/len(be_on)*100:.1f}%)")
    for t in trades[:5]:
        print(t)
