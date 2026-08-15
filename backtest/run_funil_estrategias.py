#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FUNIL DE ESTRATEGIAS (12/08/2026) — todas as candidatas no MESMO motor, MESMO custo,
medidas pela METRICA QUE IMPORTA: probabilidade de APROVAR a conta Apex 25K em 30 dias
corridos (meta $1.500, DD $1.000 EOD, min 7 dias operados).

Nao usa profit factor como criterio de escolha — PF alto com 1 trade/semana nao aprova
conta nenhuma. O que aprova e: PnL suficiente DENTRO da janela de 30 dias sem estourar DD.

Candidatas (origem: forward test proprio + pesquisa web 12/08, tudo validado aqui):
  A) NIVEIS_FADE   — a atual: reversao na max/min do dia anterior
  B) NIVEIS_BREAK  — o INVERSO da atual: rompimento da max/min do dia anterior
  C) ORB15         — Opening Range Breakout 9h30-9h45 ET
  D) ORB30         — ORB 9h30-10h00 ET (web claim: WR 74,5% PF 2,51 — verificar)
  E) IB_BREAK      — Initial Balance breakout (primeira hora, 9h30-10h30)
  F) VWAP_REV      — reversao a media: entra a 2 desvios do VWAP, alvo no VWAP
  G) GAP_FILL      — gap de abertura tende a fechar (web claim: 68-75% — verificar)

Uso: python3 backtest/run_funil_estrategias.py
"""
import glob, os, statistics
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
MNQ_PV = 2.0          # $ por PONTO por contrato (tick=0,25pt=$0,50)
RT_PER = 1.20         # custo round-trip por contrato
N_CONTR = 5
TICK = 0.25

# Regras da conta Apex 25K (confirmadas no dashboard, ver docs)
META = 1500.0
DD_LIMITE = 1000.0
MIN_DIAS = 7
JANELA_DIAS = 30

RTH_INI = 9*60+30; RTH_FIM = 16*60; FLATTEN = 16*60+55


def carregar(pasta):
    v = {}
    for f in sorted(glob.glob(os.path.join(pasta, '*.txt'))):
        for line in open(f, encoding='utf-8', errors='ignore'):
            line = line.strip()
            if not line: continue
            try:
                dtp, rest = line.split(';', 1); da, ho = dtp.split()
                o, h, l, c, vol = rest.split(';')
                dt = datetime(int(da[:4]), int(da[4:6]), int(da[6:8]),
                              int(ho[:2]), int(ho[2:4]), tzinfo=UTC)
                o, h, l, c, vol = float(o), float(h), float(l), float(c), float(vol)
            except Exception: continue
            h = max(h, o, c); l = min(l, o, c)
            if dt not in v: v[dt] = (dt.astimezone(ET), o, h, l, c, vol)
    return [{'dt': v[k][0], 'o': v[k][1], 'h': v[k][2], 'l': v[k][3],
             'c': v[k][4], 'v': v[k][5]} for k in sorted(v)]


def agrega(b1, mm):
    out = []; key = None; o = h = l = c = vv = None; dt0 = None
    for b in b1:
        m = (b['dt'].minute // mm) * mm
        k = (b['dt'].year, b['dt'].month, b['dt'].day, b['dt'].hour, m)
        if k != key:
            if key is not None: out.append({'dt': dt0, 'o': o, 'h': h, 'l': l, 'c': c, 'v': vv})
            key = k; dt0 = b['dt'].replace(minute=m, second=0, microsecond=0)
            o, h, l, c, vv = b['o'], b['h'], b['l'], b['c'], b['v']
        else:
            h = max(h, b['h']); l = min(l, b['l']); c = b['c']; vv += b['v']
    if key is not None: out.append({'dt': dt0, 'o': o, 'h': h, 'l': l, 'c': c, 'v': vv})
    return out


def mins(d): return d.hour * 60 + d.minute


# =============================================================================
#  MOTOR UNICO: recebe um gerador de sinais, devolve lista de trades fechados.
#  sinal_fn(estado, barra) -> 0 (nada) | +1 (long) | -1 (short)
#  Mesma gestao pra todas: SL fixo, TP fixo, trailing opcional apos breakeven.
# =============================================================================
def executa(bars, sinal_fn, sl_pts, tp_pts, trail_pts=0.0, be_trig=0.0, be_lock=0.0,
            max_trades_dia=12, stop_dia=750.0, hora_fim=RTH_FIM, prep_dia_fn=None):
    pv = MNQ_PV * N_CONTR; rt = RT_PER * N_CONTR
    pos = 0; entry = stop = target = 0.0; fav = 0.0; be = False
    trades = []   # (dt_saida, pnl_$, pontos)
    est = {}      # estado livre da estrategia
    dia = None; n_dia = 0; pnl_dia = 0.0; blq = False

    def fecha(p, dt):
        nonlocal pos, pnl_dia
        if pos == 0: return
        pnl = (p - entry) * pos * pv - rt
        trades.append((dt, pnl, (p - entry) * pos)); pnl_dia += pnl; pos = 0

    for b in bars:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d')
        if d != dia:
            if prep_dia_fn: prep_dia_fn(est, d)
            dia = d; n_dia = 0; pnl_dia = 0.0; blq = False
            est['_dia'] = d

        if pos != 0:
            saiu = False
            if pos > 0:
                if b['l'] <= stop: fecha(stop, dt); saiu = True
                elif b['h'] >= target: fecha(target, dt); saiu = True
            else:
                if b['h'] >= stop: fecha(stop, dt); saiu = True
                elif b['l'] <= target: fecha(target, dt); saiu = True
            if not saiu and pos != 0 and trail_pts > 0:
                if pos > 0:
                    fav = max(fav, b['h'])
                    if not be and (fav - entry) >= be_trig: stop = max(stop, entry + be_lock); be = True
                    if be: stop = max(stop, fav - trail_pts)
                else:
                    fav = min(fav, b['l'])
                    if not be and (entry - fav) >= be_trig: stop = min(stop, entry - be_lock); be = True
                    if be: stop = min(stop, fav + trail_pts)

        if stop_dia > 0 and pnl_dia <= -stop_dia:
            blq = True
            if pos != 0: fecha(b['c'], dt)

        if m >= FLATTEN:
            if pos != 0: fecha(b['c'], dt)
            continue

        # a estrategia sempre "ve" a barra (pra acumular range/vwap etc.)
        lado = sinal_fn(est, b, m, pos != 0 or blq or (max_trades_dia > 0 and n_dia >= max_trades_dia))

        if pos == 0 and not blq and lado != 0 and m < hora_fim:
            if max_trades_dia > 0 and n_dia >= max_trades_dia: continue
            entry = b['c']; pos = lado; fav = b['c']; be = False; n_dia += 1
            stop = entry - lado * sl_pts; target = entry + lado * tp_pts

    if pos != 0: fecha(bars[-1]['c'], bars[-1]['dt'])
    return trades


# =============================================================================
#  ESTRATEGIAS
# =============================================================================
def mk_niveis(fade=True, tol_ticks=20, maxdist=15.0):
    """A) fade=True: reversao na max/min do dia anterior (a ATUAL).
       B) fade=False: rompimento (o inverso)."""
    def f(est, b, m, travado):
        # acumula RTH do dia
        if RTH_INI <= m < RTH_FIM:
            est['ch'] = b['h'] if est.get('ch') is None else max(est['ch'], b['h'])
            est['cl'] = b['l'] if est.get('cl') is None else min(est['cl'], b['l'])
        if travado: return 0
        pdh, pdl = est.get('pdh'), est.get('pdl')
        if pdh is None or not (RTH_INI <= m < RTH_FIM): return 0
        tol = tol_ticks * TICK; h, l, c = b['h'], b['l'], b['c']
        if fade:
            if h >= pdh - tol and c < pdh:
                return -1 if (pdh - c) <= maxdist else 0
            if l <= pdl + tol and c > pdl:
                return 1 if (c - pdl) <= maxdist else 0
        else:
            if c > pdh: return 1
            if c < pdl: return -1
        return 0
    def prep(est, d):
        if est.get('ch') is not None:
            est['pdh'] = est['ch']; est['pdl'] = est['cl']
        est['ch'] = None; est['cl'] = None
    return f, prep


def mk_orb(fim_min, rng_min=15.0, rng_max=80.0, hora_fim=None, confirm=True):
    """C/D/E) Opening Range Breakout: range 9h30->fim_min, entra no rompimento."""
    def f(est, b, m, travado):
        if RTH_INI <= m < fim_min:
            est['hi'] = b['h'] if est.get('hi') is None else max(est['hi'], b['h'])
            est['lo'] = b['l'] if est.get('lo') is None else min(est['lo'], b['l'])
            return 0
        if travado or est.get('hi') is None: return 0
        rng = est['hi'] - est['lo']
        if rng < rng_min or rng > rng_max: return 0
        if est.get('pend'):
            lado = est['pend']; est['pend'] = 0
            if lado > 0 and b['c'] > est['hi']: return 1
            if lado < 0 and b['c'] < est['lo']: return -1
            return 0
        if b['c'] > est['hi']:
            if confirm: est['pend'] = 1; return 0
            return 1
        if b['c'] < est['lo']:
            if confirm: est['pend'] = -1; return 0
            return -1
        return 0
    def prep(est, d):
        est['hi'] = None; est['lo'] = None; est['pend'] = 0
    return f, prep


def mk_vwap_rev(n_desv=2.0):
    """F) Reversao a media: preco a N desvios do VWAP -> entra contra, alvo no VWAP."""
    def f(est, b, m, travado):
        if not (RTH_INI <= m < RTH_FIM): return 0
        tp = (b['h'] + b['l'] + b['c']) / 3.0
        est['num'] = est.get('num', 0.0) + tp * b['v']
        est['den'] = est.get('den', 0.0) + b['v']
        est.setdefault('hist', []).append(tp)
        if est['den'] <= 0 or len(est['hist']) < 20: return 0
        vwap = est['num'] / est['den']
        desv = statistics.pstdev(est['hist'][-60:]) if len(est['hist']) >= 20 else 0
        if desv <= 0 or travado: return 0
        if b['c'] >= vwap + n_desv * desv: return -1
        if b['c'] <= vwap - n_desv * desv: return 1
        return 0
    def prep(est, d):
        est['num'] = 0.0; est['den'] = 0.0; est['hist'] = []
    return f, prep


def mk_gap_fill(gap_min=20.0):
    """G) Gap de abertura tende a fechar: entra contra o gap na abertura."""
    def f(est, b, m, travado):
        if RTH_INI <= m < RTH_FIM and est.get('open_rth') is None:
            est['open_rth'] = b['o']
        if travado or est.get('close_ant') is None or est.get('open_rth') is None: return 0
        if not (RTH_INI <= m < RTH_INI + 90): return 0   # so na primeira 1h30
        if est.get('usou'): return 0
        gap = est['open_rth'] - est['close_ant']
        if abs(gap) < gap_min: return 0
        est['usou'] = True
        return -1 if gap > 0 else 1     # gap up -> short (fecha pra baixo)
    def prep(est, d):
        if est.get('ultimo_close') is not None:
            est['close_ant'] = est['ultimo_close']
        est['open_rth'] = None; est['usou'] = False
    return f, prep


# =============================================================================
#  HARNESS DE APROVACAO APEX — a metrica que decide
#  Simula avaliacoes rolantes: comeca em cada dia util, 30 dias corridos de janela.
# =============================================================================
def avalia_apex(trades, verbose=False):
    if not trades: return {'n_aval': 0, 'taxa': 0, 'aprov': 0, 'bust': 0, 'inc': 0, 'dmed': 0, 'pnl_med_mes': 0}
    por_dia = {}
    for dt, pnl, pts in trades:
        d = dt.date(); por_dia[d] = por_dia.get(d, 0.0) + pnl
    dias = sorted(por_dia)
    aprov = bust = inc = 0; dias_ate = []; pnl_janelas = []

    for i, d0 in enumerate(dias):
        saldo = 0.0; pico = 0.0; ndias = 0; fim = d0 + timedelta(days=JANELA_DIAS)
        resultado = None
        for d in dias[i:]:
            if d >= fim: break
            saldo += por_dia[d]; ndias += 1
            pico = max(pico, saldo)
            if pico - saldo >= DD_LIMITE:
                resultado = 'bust'; break
            if saldo >= META and ndias >= MIN_DIAS:
                resultado = 'aprov'; dias_ate.append((d - d0).days); break
        if resultado == 'aprov': aprov += 1
        elif resultado == 'bust': bust += 1
        else:
            inc += 1
            pnl_janelas.append(saldo)
    tot = aprov + bust + inc
    return {'n_aval': tot, 'taxa': 100 * aprov / tot if tot else 0,
            'aprov': aprov, 'bust': bust, 'inc': inc,
            'dmed': statistics.median(dias_ate) if dias_ate else 0,
            'pnl_med_mes': statistics.mean(pnl_janelas) if pnl_janelas else 0}


def resumo(trades):
    if not trades: return dict(n=0, wr=0, pf=0, net=0, g=0, p=0, dia=0)
    pts = [t[2] for t in trades]; pnl = [t[1] for t in trades]
    w = [p for p in pts if p > 0]; ls = [p for p in pts if p <= 0]
    gw = sum(x for x in pnl if x > 0); gl = abs(sum(x for x in pnl if x <= 0))
    ndias = len(set(t[0].date() for t in trades))
    return dict(n=len(trades), wr=100*len(w)/len(pts), pf=gw/gl if gl > 0 else 99,
                net=sum(pnl), g=statistics.mean(w) if w else 0,
                p=abs(statistics.mean(ls)) if ls else 0,
                dia=len(trades)/max(ndias, 1))


if __name__ == '__main__':
    print("Carregando dados..."); b1 = carregar('NQ_dados')
    b5 = agrega(b1, 5)
    d0 = b1[0]['dt'].date(); d1 = b1[-1]['dt'].date()
    print(f"{len(b1):,} barras 1min | {d0} -> {d1}\n")

    # (nome, barras, sinal, prep, sl, tp, trail, be_trig, be_lock, max_trd, hora_fim)
    CAND = [
        ("A) NIVEIS_FADE 1min (ATUAL, trail 1,75)", b1, mk_niveis(True),  12.5, 60.0, 1.75, 3.75, 2.5, 12, RTH_FIM),
        ("A2) NIVEIS_FADE 1min SEM trailing",       b1, mk_niveis(True),  12.5, 60.0, 0.0,  0,    0,   12, RTH_FIM),
        ("A3) NIVEIS_FADE 1min trail 8pt",          b1, mk_niveis(True),  12.5, 60.0, 8.0,  10.0, 5.0, 12, RTH_FIM),
        ("A4) NIVEIS_FADE 5min (o que rodou jun)",  b5, mk_niveis(True),  12.5, 60.0, 1.75, 3.75, 2.5, 12, RTH_FIM),
        ("B) NIVEIS_BREAK 1min (INVERSO)",          b1, mk_niveis(False), 12.5, 60.0, 0.0,  0,    0,   12, RTH_FIM),
        ("C) ORB15 5min",                           b5, mk_orb(9*60+45), 12.5, 37.5, 0.0,  0,    0,   2,  10*60+30),
        ("D) ORB30 5min",                           b5, mk_orb(10*60),   12.5, 37.5, 0.0,  0,    0,   2,  11*60),
        ("E) IB_BREAK 5min (1a hora)",              b5, mk_orb(10*60+30, rng_min=20, rng_max=120), 15.0, 45.0, 0.0, 0, 0, 2, 13*60),
        ("F) VWAP_REV 5min (2 desvios)",            b5, mk_vwap_rev(2.0), 12.5, 25.0, 0.0,  0,    0,   6,  RTH_FIM),
        ("G) GAP_FILL 5min",                        b5, mk_gap_fill(20.0), 20.0, 40.0, 0.0, 0,    0,   1,  RTH_FIM),
    ]

    print("="*126)
    print("  FUNIL — ordenado pelo que importa: TAXA DE APROVACAO em janelas de 30 dias corridos (Apex 25K)")
    print("="*126)
    print(f"  {'estrategia':<42s} {'trd/dia':>7s} {'WR':>6s} {'PF':>5s} {'g.med':>7s} {'p.med':>7s} "
          f"{'PnL/ano':>10s} {'APROV':>6s} {'bust':>5s} {'d.med':>6s} {'PnL/mes':>9s}")
    print("-"*126)
    linhas = []
    for nome, bars, (sig, prep), sl, tp, tr, bt_, bl, mt, hf in CAND:
        trades = executa(bars, sig, sl, tp, tr, bt_, bl, max_trades_dia=mt,
                         hora_fim=hf, prep_dia_fn=prep)
        r = resumo(trades); a = avalia_apex(trades)
        linhas.append((a['taxa'], nome, r, a))
    for taxa, nome, r, a in sorted(linhas, key=lambda x: -x[0]):
        print(f"  {nome:<42s} {r['dia']:>7.1f} {r['wr']:>5.1f}% {r['pf']:>5.2f} {r['g']:>6.1f}pt {r['p']:>6.1f}pt "
              f"${r['net']:>9,.0f} {a['taxa']:>5.0f}% {a['bust']:>5} {a['dmed']:>5.0f}d ${a['pnl_med_mes']:>8,.0f}")
    print("-"*126)
    print("  APROV = % das janelas de 30 dias que bateram $1.500 sem estourar DD $1.000 (>=7 dias operados)")
    print("  PnL/mes = PnL medio das janelas que NAO aprovaram (mostra o quao longe da meta ficou)")
