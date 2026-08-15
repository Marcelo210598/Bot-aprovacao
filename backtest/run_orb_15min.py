#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ORB 15min (9:30-9:45 ET) pra MNQ, dados 1min reais (NQ_dados, ~1 ano).
Testa: baseline breakout+confirmacao, retest, filtro de tamanho de range,
EMA200(1h) de tendencia, VWAP.

⚠️ MNQ: 1 tick = 0.25pt = $0.50 -> 1 PONTO = $2,00 (nao $0,50 -- $0,50 e o valor do TICK,
nao do ponto. Confusao comum). Mesmo padrao value dos outros scripts do projeto (MNQ_PV=2.0).
"""
import glob, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York'); UTC = timezone.utc
MNQ_PV = 2.0          # $ por ponto por contrato
RT_PER = 1.20         # custo round-trip por contrato (mesmo padrao dos outros scripts do projeto)
N_CONTR = 5
TICK = 0.25


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


def mins(dt): return dt.hour * 60 + dt.minute


def agrega_5min(bars1):
    """1min -> 5min, alinhado ao relogio (xx:00,05,10...), por dia ET."""
    out = []
    cur_key = None; o = h = l = c = v = None; dt0 = None
    for b in bars1:
        m5 = (b['dt'].minute // 5) * 5
        key = (b['dt'].year, b['dt'].month, b['dt'].day, b['dt'].hour, m5)
        if key != cur_key:
            if cur_key is not None:
                out.append({'dt': dt0, 'o': o, 'h': h, 'l': l, 'c': c, 'v': v})
            cur_key = key; dt0 = b['dt'].replace(minute=m5, second=0, microsecond=0)
            o = b['o']; h = b['h']; l = b['l']; c = b['c']; v = b['v']
        else:
            h = max(h, b['h']); l = min(l, b['l']); c = b['c']; v += b['v']
    if cur_key is not None:
        out.append({'dt': dt0, 'o': o, 'h': h, 'l': l, 'c': c, 'v': v})
    return out


def agrega_horaria(bars1):
    out = []
    cur_key = None; o = h = l = c = None; dt0 = None
    for b in bars1:
        key = (b['dt'].year, b['dt'].month, b['dt'].day, b['dt'].hour)
        if key != cur_key:
            if cur_key is not None:
                out.append({'dt': dt0, 'c': c})
            cur_key = key; dt0 = b['dt'].replace(minute=0, second=0, microsecond=0)
            o = b['o']; h = b['h']; l = b['l']; c = b['c']
        else:
            c = b['c']
    if cur_key is not None:
        out.append({'dt': dt0, 'c': c})
    return out


def ema200_por_hora(bars1h, periodo=200):
    """Retorna dict {dt_da_barra_horaria: ema_naquele_fechamento}."""
    k = 2.0 / (periodo + 1)
    valores = {}
    ema_val = None
    closes = [b['c'] for b in bars1h]
    for i, b in enumerate(bars1h):
        if ema_val is None:
            if i < periodo - 1:
                valores[b['dt']] = None; continue
            ema_val = sum(closes[i - periodo + 1:i + 1]) / periodo
        else:
            ema_val = b['c'] * k + ema_val * (1 - k)
        valores[b['dt']] = ema_val
    return valores


ORB_INI = 9 * 60 + 30   # 9:30 ET
ORB_FIM = 9 * 60 + 45   # 9:45 ET (range fecha aqui)
FLATTEN = 10 * 60 + 30  # 10:30 ET
STOP_DIA_PT = 999999.0  # kill switch opcional (testado a parte)


def bt_orb(bars5, ema_lookup=None, range_min=0, range_max=999,
           retest=False, confirm=True, ema_filter=False, vwap_filter=False,
           sl_pts=10.0, tp_mult=2.0, max_trades=2, stop_dia_usd=0):
    pv = MNQ_PV * N_CONTR; rt = RT_PER * N_CONTR
    pos = 0; entry = stop = target = 0.0
    realized = 0.0; trades = []
    dia = None; orb_hi = orb_lo = None; orb_pronto = False
    n_trades_dia = 0; aguardando_confirm = False; lado_pend = 0; nivel_pend = 0.0
    aguardando_retest = False
    vwap_num = vwap_den = 0.0
    pnl_dia0 = 0.0; bloq_dia = False

    def fecha(p):
        nonlocal pos, realized
        if pos == 0: return
        realized += (p - entry) * pos * pv - rt
        trades.append((p - entry) * pos * pv - rt)
        pos = 0

    for b in bars5:
        dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d')
        if d != dia:
            dia = d; orb_hi = orb_lo = None; orb_pronto = False
            n_trades_dia = 0; aguardando_confirm = False; aguardando_retest = False
            vwap_num = vwap_den = 0.0; pnl_dia0 = realized; bloq_dia = False

        # gestao de posicao aberta (stop/alvo intrabar, simplificado por candle)
        if pos != 0:
            if pos > 0:
                if b['l'] <= stop: fecha(stop)
                elif b['h'] >= target: fecha(target)
            else:
                if b['h'] >= stop: fecha(stop)
                elif b['l'] <= target: fecha(target)

        if stop_dia_usd > 0 and (realized - pnl_dia0) <= -stop_dia_usd:
            bloq_dia = True
            if pos != 0: fecha(b['c'])

        # VWAP (sessao RTH, reset a cada dia)
        if m >= ORB_INI:
            tp = (b['h'] + b['l'] + b['c']) / 3.0
            vwap_num += tp * b['v']; vwap_den += b['v']
        vwap = (vwap_num / vwap_den) if vwap_den > 0 else None

        # formacao do range 9:30-9:45
        if ORB_INI <= m < ORB_FIM:
            orb_hi = b['h'] if orb_hi is None else max(orb_hi, b['h'])
            orb_lo = b['l'] if orb_lo is None else min(orb_lo, b['l'])
        elif m >= ORB_FIM and not orb_pronto and orb_hi is not None:
            orb_pronto = True
            rng = orb_hi - orb_lo

        # flatten forcado
        if m >= FLATTEN:
            if pos != 0: fecha(b['c'])
            continue

        if not orb_pronto or bloq_dia or pos != 0 or n_trades_dia >= max_trades:
            continue

        rng = orb_hi - orb_lo
        if rng < range_min or rng > range_max:
            continue

        # trend/vwap filtro, calculado no candle atual
        ema_ok_long = ema_ok_short = True
        if ema_filter and ema_lookup is not None:
            hkey = dt.replace(minute=0, second=0, microsecond=0)
            ev = ema_lookup.get(hkey)
            if ev is None: continue
            ema_ok_long = b['c'] > ev; ema_ok_short = b['c'] < ev
        vwap_ok_long = vwap_ok_short = True
        if vwap_filter and vwap is not None:
            vwap_ok_long = b['c'] > vwap; vwap_ok_short = b['c'] < vwap

        lado = 0
        if not retest:
            # --- BREAKOUT + confirmacao opcional ---
            if aguardando_confirm:
                if lado_pend > 0:
                    if b['c'] > orb_hi: lado = 1
                else:
                    if b['c'] < orb_lo: lado = -1
                aguardando_confirm = False
            else:
                if b['c'] > orb_hi:
                    if confirm:
                        aguardando_confirm = True; lado_pend = 1; continue
                    lado = 1
                elif b['c'] < orb_lo:
                    if confirm:
                        aguardando_confirm = True; lado_pend = -1; continue
                    lado = -1
        else:
            # --- RETEST: precisa antes ter havido breakout confirmado no dia ---
            if not aguardando_retest:
                if b['c'] > orb_hi: aguardando_retest = True; lado_pend = 1; continue
                elif b['c'] < orb_lo: aguardando_retest = True; lado_pend = -1; continue
            else:
                if lado_pend > 0:
                    if b['l'] <= orb_hi and b['c'] > orb_hi: lado = 1
                    elif b['c'] < orb_lo: aguardando_retest = False  # invalidou, virou short
                else:
                    if b['h'] >= orb_lo and b['c'] < orb_lo: lado = -1
                    elif b['c'] > orb_hi: aguardando_retest = False

        if lado == 0: continue
        if lado > 0 and not (ema_ok_long and vwap_ok_long): continue
        if lado < 0 and not (ema_ok_short and vwap_ok_short): continue

        entry = b['c']; pos = lado; n_trades_dia += 1
        stop = entry - lado * sl_pts
        target = entry + lado * sl_pts * tp_mult
        if retest: aguardando_retest = False

    if pos != 0: fecha(bars5[-1]['c'])

    wins = [t for t in trades if t > 0]; n = len(trades)
    gw = sum(wins); gl = abs(sum(t for t in trades if t <= 0))
    return {'n': n, 'wr': 100 * len(wins) / n if n else 0,
            'pf': (gw / gl if gl > 0 else (99 if gw > 0 else 0)),
            'net': sum(trades), 'trd_ano': n / (300174 / 390)}  # aprox pregoes no dataset


if __name__ == '__main__':
    print("Carregando NQ 1-min..."); bars1 = carregar('NQ_dados')
    print(f"{len(bars1):,} barras 1min carregadas")
    bars5 = agrega_5min(bars1)
    bars1h = agrega_horaria(bars1)
    ema_lookup = ema200_por_hora(bars1h, 200)
    print(f"{len(bars5):,} barras 5min | {len(bars1h):,} barras 1h (EMA200 pronta a partir da barra 200)\n")

    meio = bars5[len(bars5) // 2]['dt']
    b5_1 = [b for b in bars5 if b['dt'] < meio]; b5_2 = [b for b in bars5 if b['dt'] >= meio]

    print("=" * 100)
    print("  ORB 15min BASELINE: breakout + confirmacao candle seguinte, SL 10pt, TP 2x SL (20pt)")
    print("=" * 100)
    for label, kw in [
        ("sem filtro range", dict()),
        ("range 15-80pt", dict(range_min=15, range_max=80)),
        ("range 10-60pt", dict(range_min=10, range_max=60)),
        ("range 20-50pt", dict(range_min=20, range_max=50)),
    ]:
        r = bt_orb(bars5, ema_lookup, **kw)
        print(f"  {label:20s} n={r['n']:4d}  WR={r['wr']:5.1f}%  PF={r['pf']:5.2f}  "
              f"net=${r['net']:>10,.0f}  trades/ano~{r['trd_ano']:.0f}")

    print("\n" + "=" * 100)
    print("  COMPARATIVO DE VARIANTES (todas com range 15-80pt, SL10/TP2x)")
    print("=" * 100)
    cfgs = [
        ("breakout SEM confirm", dict(range_min=15, range_max=80, confirm=False)),
        ("breakout COM confirm", dict(range_min=15, range_max=80, confirm=True)),
        ("retest (reteste)     ", dict(range_min=15, range_max=80, retest=True)),
        ("+ filtro EMA200(1h)  ", dict(range_min=15, range_max=80, confirm=True, ema_filter=True)),
        ("+ filtro VWAP        ", dict(range_min=15, range_max=80, confirm=True, vwap_filter=True)),
        ("+ EMA200 + VWAP      ", dict(range_min=15, range_max=80, confirm=True, ema_filter=True, vwap_filter=True)),
    ]
    for label, kw in cfgs:
        r = bt_orb(bars5, ema_lookup, **kw)
        r1 = bt_orb(b5_1, ema_lookup, **kw); r2 = bt_orb(b5_2, ema_lookup, **kw)
        print(f"  {label}  n={r['n']:4d}  WR={r['wr']:5.1f}%  PF={r['pf']:5.2f}  net=${r['net']:>9,.0f}  "
              f"OOS: n{r1['n']:3d}/PF{r1['pf']:4.2f} | n{r2['n']:3d}/PF{r2['pf']:4.2f}")

    print("\n" + "=" * 100)
    print("  SWEEP DE TP (ratio sobre SL=10pt), range 15-80pt, confirm=True")
    print("=" * 100)
    for tp_mult in [1.0, 1.5, 2.0, 2.5, 3.0, 4.0]:
        r = bt_orb(bars5, ema_lookup, range_min=15, range_max=80, tp_mult=tp_mult)
        print(f"  TP {tp_mult:.1f}x SL ({10*tp_mult:.0f}pt)  n={r['n']:4d}  WR={r['wr']:5.1f}%  "
              f"PF={r['pf']:5.2f}  net=${r['net']:>10,.0f}")

    print("\n" + "=" * 100)
    print("  SWEEP DE SL (pontos), TP = 2x SL, range 15-80pt")
    print("=" * 100)
    for sl in [5, 7.5, 10, 12.5, 15, 20]:
        r = bt_orb(bars5, ema_lookup, range_min=15, range_max=80, sl_pts=sl, tp_mult=2.0)
        print(f"  SL {sl:5.1f}pt  n={r['n']:4d}  WR={r['wr']:5.1f}%  PF={r['pf']:5.2f}  net=${r['net']:>10,.0f}")
