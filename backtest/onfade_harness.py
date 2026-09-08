#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FASE A — Harness determinístico do ONFADE (lado Python).

Implementa o CONTRATO MATEMÁTICO CONGELADO (§8 do protocolo). NÃO é medida de
rentabilidade real — é a referência lógica que o OnFadeHarness.cs (NinjaScript,
Fase A) tem que reproduzir BIT A BIT.

Regras (congeladas, sem otimização):
  instrumento     MNQ  (TICK=0.25, POINT_VALUE=$2.0/pt)
  janela ON       intervalos que COMEÇAM em [18:00:00, 09:30:00) ET
  congelamento    na 1a barra RTH (1o intervalo que começa >= 09:30 ET)
  toque           ESTRITO: high >= ON_high  /  low <= ON_low   (sem tolerância)
  sem anti-chase, sem BE, sem trailing, sem filtros
  stop            12.5 pt   |  alvo   60.0 pt   (a partir de E_exec)
  entrada         open da barra SEGUINTE ao sinal  (B+1)
  janela sinal    intervalos que começam em [09:30:00, 15:00:00] ET
  flatten         1o intervalo que começa >= 15:55 ET  (meio-dia: fim_sessao-5min)
  max trades/dia  2   |   1 posição por vez
  após STOP       o lado stopado não reentra no mesmo dia
  slippage        SLIP_TICKS aplicado ao preço teórico -> preço efetivo (adverso)
  comissao        C_RT round-turn/contrato   [PROVISÓRIO 1.44 — CONFIRMAR NO ANALYZER]

Convenção de timestamp (lado Python / Databento):
  ts_event = UTC, INÍCIO do intervalo de agregação. Aqui trabalhamos com
  interval_start em ET. A barra "das 09:30" = intervalo [09:30, 09:31).
  O OnFadeHarness.cs usa timestamp de FIM de barra (rótulo +1min) — a
  reconciliação de convenção (timestamps_dump.csv) confirma que os dois
  lados representam os MESMOS intervalos.

Saídas:
  <out>/trades_python_slip{N}.csv   — 21 colunas, 1 linha por trade
  <out>/timestamps_dump.csv         — 10 dias amostra, barras-chave, ET e UTC

Uso:
  python3 backtest/onfade_harness.py --ini 2024-09-17 --fim 2024-10-31 --out /tmp/onfade
"""
import argparse, csv, os, sys
from datetime import datetime, timedelta, timezone, time, date
from zoneinfo import ZoneInfo

UTC = timezone.utc
ET  = ZoneInfo("America/New_York")

# ---------------- contrato congelado ----------------
TICK          = 0.25
POINT_VALUE   = 2.0
ON_START      = time(18, 0)
ON_END        = time(9, 30)          # exclusivo: 1o intervalo RTH começa aqui
SIGNAL_FIRST  = time(9, 30)
SIGNAL_LAST   = time(15, 0)          # último intervalo de sinal COMEÇA às 15:00
FLATTEN_T     = time(15, 55)
STOP_PTS      = 12.5
TARGET_PTS    = 60.0
MAX_TRADES    = 2
N_CONTR       = 1
C_RT_PROVISORIO = 1.44               # <<< CONFIRMAR no Strategy Analyzer (#2)
MIN_ON_BARS   = 300
MAX_ON_GAP_MIN = 15
SESSION_RESET_GAP_MIN = 90           # gap > isso na janela ON => nova sessão

# meios-dias NYSE (fecho 13:00 ET) — lista fixa, conhecida a priori.
NYSE_HALF_DAYS = {
    date(2022,11,25), date(2022,7,3),  date(2023,7,3),  date(2023,11,24),
    date(2024,7,3),   date(2024,11,29), date(2024,12,24),
    date(2025,7,3),   date(2025,11,28), date(2025,12,24),
    date(2026,11,27),
}
# transições de DST dos EUA (2o domingo de março, 1o domingo de novembro)
DST_DAYS = {
    date(2022,3,13), date(2022,11,6), date(2023,3,12), date(2023,11,5),
    date(2024,3,10), date(2024,11,3), date(2025,3,9),  date(2025,11,2),
    date(2026,3,8),  date(2026,11,1),
}


def minute_of_day(t: time) -> int:
    return t.hour * 60 + t.minute


ON_START_M   = minute_of_day(ON_START)     # 1080
ON_END_M     = minute_of_day(ON_END)       # 570
SIG_FIRST_M  = minute_of_day(SIGNAL_FIRST) # 570
SIG_LAST_M   = minute_of_day(SIGNAL_LAST)  # 900
FLATTEN_M    = minute_of_day(FLATTEN_T)    # 955


def carrega_front_month(csv_path, ini_utc_date, fim_utc_date):
    """Databento GLBX OHLCV-1m (MNQ outrights + spreads). Constrói front-month
    contínuo: por dia UTC, o outright de MAIOR volume. Descarta spreads ('-').
    Retorna lista de dicts ordenada por interval_start ET.
    Idêntico ao critério de gera_import_nt8.py (o que gerou 'MNQ 12-25' no NT8).
    """
    vol = {}
    with open(csv_path, newline="") as fh:
        rd = csv.reader(fh); next(rd)
        for row in rd:
            ts, sym = row[0], row[9]
            if "-" in sym:
                continue
            dia = ts[:10]
            if dia < ini_utc_date or dia > fim_utc_date:
                continue
            vol[(dia, sym)] = vol.get((dia, sym), 0.0) + float(row[8])
    front = {}
    for (dia, sym), v in vol.items():
        if dia not in front or v > front[dia][1]:
            front[dia] = (sym, v)

    bars = []
    with open(csv_path, newline="") as fh:
        rd = csv.reader(fh); next(rd)
        for row in rd:
            ts, sym = row[0], row[9]
            if "-" in sym:
                continue
            dia = ts[:10]
            if dia < ini_utc_date or dia > fim_utc_date:
                continue
            if front.get(dia, (None,))[0] != sym:
                continue
            dt_utc = datetime(int(ts[0:4]), int(ts[5:7]), int(ts[8:10]),
                              int(ts[11:13]), int(ts[14:16]), tzinfo=UTC)
            dt_et = dt_utc.astimezone(ET)
            o, h, l, c, v = (float(row[4]), float(row[5]), float(row[6]),
                             float(row[7]), int(float(row[8])))
            h = max(h, o, c); l = min(l, o, c)
            bars.append({"ts_utc": dt_utc, "ts_et": dt_et, "sym": sym,
                         "o": o, "h": h, "l": l, "c": c, "v": v})
    bars.sort(key=lambda b: b["ts_et"])
    # dedup por ts_et (segurança)
    out, seen = [], set()
    for b in bars:
        if b["ts_et"] in seen:
            continue
        seen.add(b["ts_et"]); out.append(b)
    return out, front


def in_on_window(m):
    return m >= ON_START_M or m < ON_END_M


def flatten_minute_for_day(d: date):
    """Normal: 15:55. Meio-dia NYSE: fim da sessão - 5 min (fecho 13:00 -> 12:55)."""
    if d in NYSE_HALF_DAYS:
        return minute_of_day(time(12, 55))
    return FLATTEN_M


def run(bars, slip_ticks, c_rt):
    trades = []
    # estado ON
    acc = None            # dict hi/lo/count/gap_max/last/start  ou None
    ON_high = ON_low = None
    day_valid = False
    cur_day = None
    trades_today = 0
    stopped_sides = set()
    flatten_m_today = FLATTEN_M
    # estado posição
    pos = None            # "LONG" / "SHORT" / None
    E_exec = stop_theo = target_theo = None
    entry_ts = None
    pending_side = None
    pending_from_ts = None
    tid = 0
    last_ts = None

    for idx, b in enumerate(bars):
        t = b["ts_et"]
        m = minute_of_day(t.time())
        d = t.date()

        # ---------- 1. manutenção do range ON ----------
        if in_on_window(m):
            gap = ((t - last_ts).total_seconds() / 60.0) if last_ts else 1e9
            if acc is None or gap > SESSION_RESET_GAP_MIN:
                acc = {"hi": b["h"], "lo": b["l"], "count": 1,
                       "gap_max": 0.0, "last": t, "start": t}
            else:
                acc["hi"] = max(acc["hi"], b["h"])
                acc["lo"] = min(acc["lo"], b["l"])
                acc["count"] += 1
                acc["gap_max"] = max(acc["gap_max"],
                                     (t - acc["last"]).total_seconds() / 60.0)
                acc["last"] = t
        else:
            # 1a barra não-ON depois de uma sessão overnight => congela
            if acc is not None:
                ON_high, ON_low = acc["hi"], acc["lo"]
                # day_valid = SÓ validade do range ON (sem look-ahead na RTH)
                day_valid = (acc["count"] >= MIN_ON_BARS
                             and acc["gap_max"] <= MAX_ON_GAP_MIN)
                acc = None
                cur_day = d
                trades_today = 0
                stopped_sides = set()
                flatten_m_today = flatten_minute_for_day(d)

        # ---------- 2. fill de entrada pendente (sinal foi na barra anterior) ----------
        if pending_side is not None:
            side = 1 if pending_side == "LONG" else -1
            E_theo = b["o"]
            E_exec = E_theo + slip_ticks * TICK * side
            stop_theo = E_exec - STOP_PTS * side
            target_theo = E_exec + TARGET_PTS * side
            pos = pending_side
            entry_ts = t
            trades_today += 1
            cur_trade = {
                "trade_id": tid, "contract": b["sym"], "data_pregao": str(d),
                "bar_sinal_ts_et": pending_from_ts["ts"].strftime("%Y-%m-%dT%H:%M:%S"),
                "sinal_preco_close": pending_from_ts["close"],
                "sinal_nivel": pending_from_ts["nivel"],
                "direcao": pending_side,
                "bar_entrada_ts_et": t.strftime("%Y-%m-%dT%H:%M:%S"),
                "entrada_preco_teorico": round(E_theo, 4),
                "entrada_slippage_ticks": slip_ticks,
                "entrada_preco_efetivo": round(E_exec, 4),
                "stop_teorico": round(stop_theo, 4),
                "alvo_teorico": round(target_theo, 4),
            }
            pending_side = None
            pending_from_ts = None
        # ---------- 3. checagem de saída (inclui a própria barra de entrada) ----------
        if pos is not None:
            side = 1 if pos == "LONG" else -1
            reason = None; X_theo = None
            if side == 1:
                if b["l"] <= stop_theo:
                    reason, X_theo = "STOP", stop_theo
                elif b["h"] >= target_theo:
                    reason, X_theo = "ALVO", target_theo
            else:
                if b["h"] >= stop_theo:
                    reason, X_theo = "STOP", stop_theo
                elif b["l"] <= target_theo:
                    reason, X_theo = "ALVO", target_theo
            if reason is None and m >= flatten_m_today:
                reason, X_theo = "FLATTEN", b["c"]
            if reason is not None:
                X_exec = X_theo - slip_ticks * TICK * side
                pnl_bruto = (X_exec - E_exec) * side * POINT_VALUE * N_CONTR
                pnl_liq = pnl_bruto - c_rt * N_CONTR
                cur_trade.update({
                    "bar_saida_ts_et": t.strftime("%Y-%m-%dT%H:%M:%S"),
                    "saida_motivo": reason,
                    "saida_preco_teorico": round(X_theo, 4),
                    "saida_slippage_ticks": slip_ticks,
                    "saida_preco_efetivo": round(X_exec, 4),
                    "comissao_rt": c_rt,
                    "pnl_bruto": round(pnl_bruto, 4),
                    "pnl_liquido": round(pnl_liq, 4),
                })
                trades.append(cur_trade)
                tid += 1
                if reason == "STOP":
                    stopped_sides.add(pos)
                pos = None

        # ---------- 4. detecção de sinal (posição FLAT) ----------
        if (pos is None and pending_side is None and day_valid
                and d == cur_day                       # barra pertence ao dia congelado
                and SIG_FIRST_M <= m <= SIG_LAST_M
                and trades_today < MAX_TRADES
                and ON_high is not None):
            toca_topo = (b["h"] >= ON_high and b["c"] < ON_high
                         and "SHORT" not in stopped_sides)
            toca_fundo = (b["l"] <= ON_low and b["c"] > ON_low
                          and "LONG" not in stopped_sides)
            if toca_topo and toca_fundo:
                pass  # barra ambígua -> não opera
            elif toca_topo:
                pending_side = "SHORT"
                pending_from_ts = {"ts": t, "close": b["c"], "nivel": round(ON_high, 4)}
            elif toca_fundo:
                pending_side = "LONG"
                pending_from_ts = {"ts": t, "close": b["c"], "nivel": round(ON_low, 4)}

        last_ts = t

    return trades


def dump_timestamps(bars, out_path, n_days=10):
    by_day = {}
    for b in bars:
        by_day.setdefault(b["ts_et"].date(), []).append(b)
    dias = sorted(by_day)
    # dias úteis "cheios" espalhados
    uteis = [d for d in dias if d.weekday() < 5 and len(by_day[d]) > 500]
    if len(uteis) > n_days:
        step = len(uteis) / n_days
        amostra = [uteis[int(i * step)] for i in range(n_days)]
    else:
        amostra = uteis

    def find(day_bars, hh, mm):
        for b in day_bars:
            if b["ts_et"].hour == hh and b["ts_et"].minute == mm:
                return b
        return None

    rows = []
    for d in amostra:
        db = by_day[d]
        marca = [
            ("primeira_barra_do_dia_ET", db[0]),
            ("ultima_barra_do_dia_ET",   db[-1]),
            ("bar_ET_09:29", find(db, 9, 29)),
            ("bar_ET_09:30", find(db, 9, 30)),
            ("bar_ET_09:31", find(db, 9, 31)),
            ("bar_ET_15:59", find(db, 15, 59)),
            ("bar_ET_16:00", find(db, 16, 0)),
            ("bar_ET_17:59", find(db, 17, 59)),
            ("bar_ET_18:00", find(db, 18, 0)),
        ]
        for nome, b in marca:
            if b is None:
                rows.append({"data": str(d), "tipo": nome, "ts_et": "(sem barra)",
                             "ts_utc": "", "symbol": "", "open": "", "high": "",
                             "low": "", "close": "", "volume": ""})
            else:
                rows.append({
                    "data": str(d), "tipo": nome,
                    "ts_et": b["ts_et"].strftime("%Y-%m-%d %H:%M:%S %Z"),
                    "ts_utc": b["ts_utc"].strftime("%Y-%m-%d %H:%M:%S"),
                    "symbol": b["sym"], "open": b["o"], "high": b["h"],
                    "low": b["l"], "close": b["c"], "volume": b["v"],
                })
    with open(out_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    return amostra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=os.path.join(os.path.dirname(__file__), "..",
                    "dados_databento", "glbx-mdp3-20220601-20260831.ohlcv-1m.csv"),
                    help="CSV Databento que originou o 'MNQ 12-25' no NT8")
    ap.add_argument("--ini", required=True, help="AAAA-MM-DD (data de pregão ET inicial)")
    ap.add_argument("--fim", required=True, help="AAAA-MM-DD (data de pregão ET final)")
    ap.add_argument("--out", required=True, help="diretório de saída")
    ap.add_argument("--crt", type=float, default=C_RT_PROVISORIO,
                    help="comissão round-turn/contrato (PROVISÓRIO 1.44)")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    # buffer de 3 dias corridos antes para formar o 1o range ON
    ini_buf = (datetime.strptime(args.ini, "%Y-%m-%d") - timedelta(days=4)).strftime("%Y-%m-%d")
    fim_buf = (datetime.strptime(args.fim, "%Y-%m-%d") + timedelta(days=2)).strftime("%Y-%m-%d")

    print(f"[carrega] {args.csv}")
    print(f"[janela]  pregão {args.ini} -> {args.fim}  (buffer UTC {ini_buf} -> {fim_buf})")
    bars, front = carrega_front_month(args.csv, ini_buf, fim_buf)
    if not bars:
        print("ERRO: nenhuma barra carregada."); sys.exit(1)
    print(f"[barras]  {len(bars):,}  {bars[0]['ts_et']}  ->  {bars[-1]['ts_et']}")
    print(f"[contratos front-month no período]")
    for dia in sorted(front):
        if args.ini <= dia <= args.fim or True:
            pass
    syms = sorted({s for (s, _) in front.values()})
    print(f"          {syms}")

    dst_no_periodo = [d for d in DST_DAYS if args.ini <= str(d) <= args.fim]
    half_no_periodo = [d for d in NYSE_HALF_DAYS if args.ini <= str(d) <= args.fim]
    if dst_no_periodo:
        print(f"[AVISO]   transição de DST no período: {dst_no_periodo} — trades nesses dias marcados p/ revisão manual")
    if half_no_periodo:
        print(f"[AVISO]   meio-dia NYSE no período: {half_no_periodo}")

    # dump de timestamps (10 dias) — para confirmar convenção com o NT8
    amostra = dump_timestamps(bars, os.path.join(args.out, "timestamps_dump.csv"))
    print(f"[dump]    timestamps_dump.csv  ({len(amostra)} dias: {[str(d) for d in amostra]})")

    # roda o contrato: slip 0 (pré-slippage, p/ comparar mecânica) e slip 1 (base)
    for slip in (0, 1):
        trades = run(bars, slip_ticks=slip, c_rt=args.crt)
        # filtra p/ janela de pregão pedida
        trades = [t for t in trades if args.ini <= t["data_pregao"] <= args.fim]
        path = os.path.join(args.out, f"trades_python_slip{slip}.csv")
        cols = ["trade_id", "contract", "data_pregao", "bar_sinal_ts_et",
                "sinal_preco_close", "sinal_nivel", "direcao", "bar_entrada_ts_et",
                "entrada_preco_teorico", "entrada_slippage_ticks", "entrada_preco_efetivo",
                "stop_teorico", "alvo_teorico", "bar_saida_ts_et", "saida_motivo",
                "saida_preco_teorico", "saida_slippage_ticks", "saida_preco_efetivo",
                "comissao_rt", "pnl_bruto", "pnl_liquido"]
        with open(path, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for t in trades:
                w.writerow({c: t.get(c, "") for c in cols})
        n = len(trades)
        if n:
            gl = sum(t["pnl_liquido"] for t in trades)
            wins = [t for t in trades if t["pnl_liquido"] > 0]
            gw = sum(t["pnl_bruto"] for t in trades if t["pnl_bruto"] > 0)
            gloss = abs(sum(t["pnl_bruto"] for t in trades if t["pnl_bruto"] <= 0))
            pf = gw / gloss if gloss else float("inf")
            longs = sum(1 for t in trades if t["direcao"] == "LONG")
            mot = {}
            for t in trades:
                mot[t["saida_motivo"]] = mot.get(t["saida_motivo"], 0) + 1
            print(f"[slip {slip}] {n} trades ({longs}L/{n-longs}S) | "
                  f"WR {100*len(wins)/n:.0f}% | PF(bruto) {pf:.2f} | "
                  f"PnL líq ${gl:,.2f} | saídas {mot}")
        else:
            print(f"[slip {slip}] 0 trades no período")
        print(f"          -> {path}")

    print("\n[NOTA] C_RT =", args.crt, "é PROVISÓRIO. Confirmar comissão real no "
          "Strategy Analyzer antes de qualquer conclusão econômica (Fase B / B1).")
    print("[NOTA] Este é o lado Python da FASE A. O veredito de equivalência exige "
          "o OnFadeHarness.cs produzindo log idêntico. Nada aqui é rentabilidade real.")


if __name__ == "__main__":
    main()
