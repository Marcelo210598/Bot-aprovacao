#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ESTRATEGIA NOVA — candidata B (event-driven, spike das 8h30 ET)
==============================================================
Teste TOSCO (protótipo Python — decisão final é sempre no NT8 Strategy Analyzer).

Tese (docs/estrategia-nova-2026-09.md): releases economicos das 8h30 ET (CPI, PPI,
NFP, jobless claims, retail sales, GDP, PCE) injetam volatilidade AGENDADA. Nao se
negocia estrutura — se negocia a injecao de liquidez com hora marcada.

ITEM 1 — lista de releases: detectada DO PROPRIO DADO. Um release das 8h30 ET
produz um spike de volume 10-30x no minuto exato (verificado: CPI 12/02/2025,
8h30 ET = 16.064 contratos vs ~500 nos minutos anteriores). Dia de release =
volume da barra 8h30 ET > 3x a mediana movel de 20 dias dessa mesma barra.
Classificacao aproximada por posicao no calendario (Qui=claims, Sex cedo=NFP,
meio do mes=CPI/PPI/retail, fim do mes=GDP/PCE).

ITEM 2 — teste tosco:
  - range de referencia = high/low das barras 8h25..8h29 ET (5 min antes do release)
  - gatilho = barra 8h30 ET (abre no release, fecha 8h31 ET). Se fechou ACIMA do
    range -> LONG; ABAIXO -> SHORT; dentro -> nao opera
  - entrada = close da barra 8h30 (8h31 ET)
  - bracket FIXO 2:1 (sem trailing tick-a-tick — licao da auditoria). SL testado
    em: tamanho da barra de gatilho, e X pts fixo
  - slippage AGRESSIVO 3 e 5 ticks/lado (spread alarga no release)
  - flat as 9h00 ET (o edge decai rapido)
  - 5 MNQ, $2/pt, custo ~$6,50 round-turn (5c)

OOS: calibra 2022-2025, 2026 = HOLDOUT (so olha no fim).
Corte pra escrever .cs: PF > 1,3 em 2022-2025 COM custo E slippage.

Dado: dados_databento/MNQ_1min_2022_2026.txt (UTC, inicio da barra, front-month).
"""
import os
import statistics as st
from collections import defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
D = os.path.join(os.path.dirname(__file__), "..", "dados_databento")
TXT = os.path.join(D, "MNQ_1min_2022_2026.txt")

TICK = 0.25
MNQ_PV = 2.0
N_CONTR = 5
PV = MNQ_PV * N_CONTR                # $/ponto na posicao inteira
RT = 1.30 * N_CONTR                  # custo round-turn (~$6,50 p/ 5 MNQ)

REL_MIN = 8 * 60 + 30               # 8h30 ET (release)
RANGE_INI = 8 * 60 + 25            # range de referencia 8h25..8h29
FLAT_MIN = 9 * 60                   # flat 9h00 ET
SPIKE_MULT = 3.0                    # vol da barra 8h30 > SPIKE_MULT x mediana20 -> release
SPIKE_ABS_MIN = 2500               # ...e volume absoluto minimo (evita dia morto)


# --------------------------------------------------------------------------- io
def carrega():
    bars = []
    with open(TXT, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                dtp, o, h, l, c, v = line.replace(" ", ";", 1).split(";")
                data, hora = dtp.split(";") if ";" in dtp else (dtp[:8], dtp[9:])
            except ValueError:
                # formato "YYYYMMDD HHMMSS;o;h;l;c;v"
                dtp, rest = line.split(";", 1)
                data, hora = dtp.split()
                o, h, l, c, v = rest.split(";")
            dt = datetime(int(data[:4]), int(data[4:6]), int(data[6:8]),
                          int(hora[:2]), int(hora[2:4]), tzinfo=UTC).astimezone(ET)
            o, h, l, c, v = float(o), float(h), float(l), float(c), float(v)
            h = max(h, o, c)
            l = min(l, o, c)
            bars.append((dt, o, h, l, c, v))
    bars.sort(key=lambda b: b[0])
    return bars


def mins(dt):
    return dt.hour * 60 + dt.minute


# ------------------------------------------------------- item 1: detecta eventos
def detecta_eventos(bars):
    """Agrupa por dia ET. Retorna dict {dia: info} para dias com spike as 8h30 ET."""
    por_dia = defaultdict(dict)          # dia -> {minuto_et: (o,h,l,c,v)}
    for dt, o, h, l, c, v in bars:
        por_dia[dt.strftime("%Y-%m-%d")][mins(dt)] = (o, h, l, c, v)

    dias = sorted(por_dia)
    vol_830_hist = []
    eventos = {}
    for dia in dias:
        m = por_dia[dia]
        b830 = m.get(REL_MIN)
        if not b830:
            continue
        v830 = b830[4]
        med = st.median(vol_830_hist[-20:]) if len(vol_830_hist) >= 5 else None
        vol_830_hist.append(v830)
        if med and v830 >= SPIKE_MULT * med and v830 >= SPIKE_ABS_MIN:
            d = datetime.strptime(dia, "%Y-%m-%d")
            wd = d.weekday()   # 0=seg .. 4=sex
            dom = d.day
            # classificacao aproximada
            if wd == 3:
                tipo = "claims (Qui)"
            elif wd == 4 and dom <= 8:
                tipo = "NFP (Sex cedo)"
            elif 9 <= dom <= 19:
                tipo = "CPI/PPI/retail (meio)"
            elif dom >= 23 or dom <= 2:
                tipo = "GDP/PCE (fim)"
            else:
                tipo = "outro 8h30"
            eventos[dia] = {"tipo": tipo, "wd": wd, "vol830": v830,
                            "mult": v830 / med if med else 0}
    return eventos, por_dia


# --------------------------------------------------------- item 2: backtest tosco
def bt(eventos, por_dia, slip_ticks, sl_mode, sl_pts, rr, flat_min=FLAT_MIN):
    """
    sl_mode: 'barra' (SL = tamanho da barra de gatilho) ou 'fixo' (SL = sl_pts)
    rr: multiplo do alvo sobre o SL (bracket rr:1)
    """
    slip = slip_ticks * TICK
    trades = []
    for dia in sorted(eventos):
        m = por_dia[dia]
        # range de referencia 8h25..8h29
        ref = [m[k] for k in range(RANGE_INI, REL_MIN) if k in m]
        gat = m.get(REL_MIN)
        if len(ref) < 3 or not gat:
            continue
        rhi = max(b[1] for b in ref)
        rlo = min(b[2] for b in ref)
        go, gh, gl, gc, gv = gat
        # direcao pelo fechamento da barra de gatilho
        if gc > rhi:
            lado = 1
        elif gc < rlo:
            lado = -1
        else:
            continue
        entry = gc + lado * slip                 # slippage contra na entrada
        if sl_mode == "barra":
            risco = max(gh - gl, 2 * TICK)
        else:
            risco = sl_pts
        stop = entry - lado * risco
        target = entry + lado * rr * risco

        # simula minuto a minuto ate flat
        saida = None
        for k in range(REL_MIN + 1, flat_min + 1):
            b = m.get(k)
            if not b:
                continue
            _, bh, bl, bc, _ = b
            if lado == 1:
                if bl <= stop:
                    saida = stop - slip
                    break
                if bh >= target:
                    saida = target - slip
                    break
            else:
                if bh >= stop:
                    saida = stop + slip
                    break
                if bl <= target:
                    saida = target + slip
                    break
        if saida is None:
            bflat = m.get(flat_min) or m.get(flat_min - 1)
            saida = (bflat[3] if bflat else entry)
        pnl = ((saida - entry) * lado) * PV - RT
        trades.append((dia, lado, pnl, risco))
    return trades


def stats(trades):
    if not trades:
        return None
    pn = [t[2] for t in trades]
    w = [x for x in pn if x > 0]
    gw = sum(w)
    gl = abs(sum(x for x in pn if x <= 0))
    # max drawdown na curva de equity
    eq = 0.0
    pico = 0.0
    mdd = 0.0
    for x in pn:
        eq += x
        pico = max(pico, eq)
        mdd = min(mdd, eq - pico)
    return {
        "n": len(pn), "wr": 100 * len(w) / len(pn), "pf": gw / gl if gl else 99.9,
        "net": sum(pn), "avg": sum(pn) / len(pn),
        "avgW": (gw / len(w)) if w else 0,
        "avgL": (-gl / (len(pn) - len(w))) if (len(pn) - len(w)) else 0,
        "mdd": mdd,
    }


def por_ano(trades):
    d = defaultdict(list)
    for t in trades:
        d[t[0][:4]].append(t)
    return {a: stats(v) for a, v in sorted(d.items())}


# ----------------------------------------------------------------------- main
if __name__ == "__main__":
    print("carregando MNQ 1-min 2022-2026 (UTC->ET)...")
    bars = carrega()
    print(f"  {len(bars):,} barras | {bars[0][0].date()} -> {bars[-1][0].date()}\n")

    eventos, por_dia = detecta_eventos(bars)
    print(f"ITEM 1 — {len(eventos)} dias de release detectados (spike vol 8h30 ET >= {SPIKE_MULT}x med20)\n")

    # resumo por tipo e por ano
    cont = defaultdict(lambda: defaultdict(int))
    for dia, info in eventos.items():
        cont[dia[:4]][info["tipo"]] += 1
    print(f"  {'ano':<6}", end="")
    tipos = ["claims (Qui)", "NFP (Sex cedo)", "CPI/PPI/retail (meio)", "GDP/PCE (fim)", "outro 8h30"]
    for tp in tipos:
        print(f"{tp:>24}", end="")
    print()
    for ano in sorted(cont):
        print(f"  {ano:<6}", end="")
        for tp in tipos:
            print(f"{cont[ano][tp]:>24}", end="")
        print()

    print("\n  amostra (primeiros 12):")
    for dia in sorted(eventos)[:12]:
        i = eventos[dia]
        print(f"    {dia}  {i['tipo']:<24} vol830={i['vol830']:>7.0f} ({i['mult']:.1f}x)")

    print("\n" + "=" * 92)
    print("ITEM 2 — backtest tosco (breakout do range 8h25-30 na barra 8h30, bracket fixo)")
    print("=" * 92)

    grid = []
    for slip in (3, 5):
        for sl_mode, sl_pts in (("barra", 0), ("fixo", 15), ("fixo", 25)):
            for rr in (1.5, 2.0, 3.0):
                grid.append((slip, sl_mode, sl_pts, rr))

    print(f"\n  {'slip':>4} {'SL':>10} {'RR':>4} | {'N':>4} {'WR%':>5} {'PF':>5} {'net$':>10} "
          f"{'avg$':>7} {'avgW':>7} {'avgL':>7} {'maxDD$':>9}   [IS 22-25 / holdout 26]")
    print("  " + "-" * 118)
    for slip, sl_mode, sl_pts, rr in grid:
        tr = bt(eventos, por_dia, slip, sl_mode, sl_pts, rr)
        is_tr = [t for t in tr if t[0] < "2026"]
        oo_tr = [t for t in tr if t[0] >= "2026"]
        s = stats(is_tr)
        o = stats(oo_tr)
        if not s:
            continue
        sllab = "barra" if sl_mode == "barra" else f"fixo{sl_pts}"
        print(f"  {slip:>4} {sllab:>10} {rr:>4.1f} | {s['n']:>4} {s['wr']:>5.1f} {s['pf']:>5.2f} "
              f"{s['net']:>10,.0f} {s['avg']:>7.0f} {s['avgW']:>7.0f} {s['avgL']:>7.0f} {s['mdd']:>9,.0f}"
              f"   | 26: PF {o['pf']:.2f} net {o['net']:,.0f} (n{o['n']})" if o else
              f"  {slip:>4} {sllab:>10} {rr:>4.1f} | {s['n']:>4} {s['wr']:>5.1f} {s['pf']:>5.2f} "
              f"{s['net']:>10,.0f} {s['avg']:>7.0f} {s['avgW']:>7.0f} {s['avgL']:>7.0f} {s['mdd']:>9,.0f}")

    # detalhe ano a ano da config mediana (slip 5, SL barra, RR 2)
    print("\n  --- ano a ano | slip 5t, SL=barra de gatilho, bracket 2:1 ---")
    tr = bt(eventos, por_dia, 5, "barra", 0, 2.0)
    for ano, s in por_ano(tr).items():
        if s:
            print(f"    {ano}: n{s['n']:>3} WR {s['wr']:>4.0f}%  PF {s['pf']:>4.2f}  "
                  f"net ${s['net']:>8,.0f}  avg ${s['avg']:>6.0f}  maxDD ${s['mdd']:>8,.0f}")

    # split por tipo de evento (config slip 5 / barra / 2:1)
    print("\n  --- por tipo de evento | slip 5t, SL=barra, 2:1 (IS+holdout junto) ---")
    bytipo = defaultdict(list)
    for t in tr:
        bytipo[eventos[t[0]]["tipo"]].append(t)
    for tp, v in sorted(bytipo.items()):
        s = stats(v)
        print(f"    {tp:<24} n{s['n']:>3} WR {s['wr']:>4.0f}%  PF {s['pf']:>4.2f}  net ${s['net']:>8,.0f}  avg ${s['avg']:>6.0f}")
