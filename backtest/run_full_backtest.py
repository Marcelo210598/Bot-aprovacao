#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BACKTEST DEFINITIVO — 4 estrategias p/ aprovar conta Apex.
Dados: NQ 1-min reais (NinjaTrader), jun/2025 a jun/2026 (~10,5 meses).
Estrategias: ORB+VWAP | MeanReversion | Niveis | Manha-Matheus (canal 00-12h + Fib).
Saida: PnL, metricas e contas Apex APROVADAS vs REPROVADAS no periodo.
"""
import glob, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET  = ZoneInfo('America/New_York')   # converte UTC->ET com DST automatico
UTC = timezone.utc

# ---------- Mercado NQ ----------
PV_NQ   = 20.0     # $/ponto NQ
PV_MNQ  = 2.0      # $/ponto MNQ
TICK    = 0.25
RT_COST = 5.0      # custo round-turn/contrato (comissao+slippage)

# ---------- Regras Apex ----------
CONTAS = {
    '50K':  {'meta': 3000.0, 'dd': 2500.0},
    '100K': {'meta': 6000.0, 'dd': 3000.0},
}
MIN_DIAS = 7


def carregar_todos(pasta):
    arquivos = sorted(glob.glob(os.path.join(pasta, '*.txt')))
    vistos = {}
    for f in arquivos:
        with open(f, encoding='utf-8', errors='ignore') as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    dtp, rest = line.split(';', 1)
                    data, hora = dtp.split()
                    o, h, l, c, v = rest.split(';')
                    y, mo, d = int(data[:4]), int(data[4:6]), int(data[6:8])
                    hh, mi = int(hora[:2]), int(hora[2:4])
                    dt_utc = datetime(y, mo, d, hh, mi, tzinfo=UTC)
                    o, h, l, c, v = float(o), float(h), float(l), float(c), float(v)
                except Exception:
                    continue
                h = max(h, o, c); l = min(l, o, c)
                # dedup por timestamp UTC (rollover entre contratos)
                if dt_utc not in vistos:
                    vistos[dt_utc] = (dt_utc.astimezone(ET), o, h, l, c, v)
    bars = [vistos[k] for k in sorted(vistos)]
    return [{'dt': b[0], 'o': b[1], 'h': b[2], 'l': b[3], 'c': b[4], 'v': b[5]} for b in bars]


def mins(dt):
    return dt.hour * 60 + dt.minute


class BT:
    def __init__(self, bars, modo, conta, pv=PV_NQ, contratos=1, kill_frac=0.5):
        self.bars = bars; self.modo = modo
        self.meta = CONTAS[conta]['meta']; self.dd = CONTAS[conta]['dd']
        self.pv = pv; self.q = contratos; self.kill = kill_frac
        self.pos = 0; self.entry = self.stop = self.target = 0.0
        self.realized = 0.0; self.trades = []
        self.vpv = self.vv = self.vwap = 0.0
        self.orb_hi = self.orb_lo = None; self.orb_ok = False; self.trade_dia = False
        self.dia = None; self.cur_hi = self.cur_lo = None
        self.pd_hi = self.pd_lo = None
        self.man_hi = self.man_lo = None; self.man_ok = False  # canal manha Matheus
        # apex
        self.r_ini = 0.0; self.pico = 0.0; self.dias = set(); self.ativa = True
        self.aprov = 0; self.reprov = 0; self.d2a = []; self.ini_aval = None
        self.pnl_dia0 = 0.0; self.block_dia = False; self.dia_kill = None

    def fecha(self, p):
        if self.pos == 0: return
        pnl = (p - self.entry) * self.pos * self.pv * self.q - RT_COST * self.q
        self.realized += pnl; self.trades.append(pnl); self.pos = 0

    def abre(self, lado, p, stop, tgt, d):
        self.pos = lado; self.entry = p; self.stop = stop; self.target = tgt
        self.dias.add(d); self.trade_dia = True

    def reset_aval(self, dt):
        self.r_ini = self.realized; self.pico = 0.0; self.dias = set()
        self.ativa = True; self.ini_aval = dt

    def run(self):
        for b in self.bars:
            dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d')
            sess = 9*60+30 <= m < 16*60

            if d != self.dia:
                if self.cur_hi is not None:
                    self.pd_hi, self.pd_lo = self.cur_hi, self.cur_lo
                self.dia = d; self.cur_hi = self.cur_lo = None; self.trade_dia = False
                self.man_hi = self.man_lo = None; self.man_ok = False

            # canal da manha (00:00-12:00 ET) p/ Matheus
            if m < 12*60:
                self.man_hi = b['h'] if self.man_hi is None else max(self.man_hi, b['h'])
                self.man_lo = b['l'] if self.man_lo is None else min(self.man_lo, b['l'])
            elif not self.man_ok and self.man_hi is not None:
                self.man_ok = True

            if sess:
                self.cur_hi = b['h'] if self.cur_hi is None else max(self.cur_hi, b['h'])
                self.cur_lo = b['l'] if self.cur_lo is None else min(self.cur_lo, b['l'])

            if m == 9*60+30:
                self.vpv = self.vv = 0.0; self.orb_hi = self.orb_lo = None; self.orb_ok = False

            # VWAP + ORB so contam na sessao regular
            if sess:
                tp = (b['h']+b['l']+b['c'])/3.0
                self.vpv += tp*b['v']; self.vv += b['v']
                self.vwap = self.vpv/self.vv if self.vv > 0 else b['c']
                if 9*60+30 <= m < 9*60+35:
                    self.orb_hi = b['h'] if self.orb_hi is None else max(self.orb_hi, b['h'])
                    self.orb_lo = b['l'] if self.orb_lo is None else min(self.orb_lo, b['l'])
                elif m >= 9*60+35 and not self.orb_ok and self.orb_hi is not None:
                    self.orb_ok = True

            # kill switch diario
            if d != self.dia_kill:
                self.dia_kill = d; self.pnl_dia0 = self.realized; self.block_dia = False

            # saida intrabar (conservador: stop antes do alvo)
            if self.pos != 0:
                if self.pos > 0:
                    if b['l'] <= self.stop: self.fecha(self.stop)
                    elif b['h'] >= self.target: self.fecha(self.target)
                else:
                    if b['h'] >= self.stop: self.fecha(self.stop)
                    elif b['l'] <= self.target: self.fecha(self.target)

            # ---- simulador apex ----
            if self.ativa:
                pr = self.realized - self.r_ini
                uf = ua = 0.0
                if self.pos > 0:
                    uf = (b['h']-self.entry)*self.pv*self.q; ua = (b['l']-self.entry)*self.pv*self.q
                elif self.pos < 0:
                    uf = (self.entry-b['l'])*self.pv*self.q; ua = (self.entry-b['h'])*self.pv*self.q
                if pr+uf > self.pico: self.pico = pr+uf
                # kill switch
                if (self.realized - self.pnl_dia0 + ua) <= -(self.dd*self.kill):
                    self.block_dia = True
                    if self.pos != 0: self.fecha(b['c'])
                # reprovacao
                if pr+ua <= self.pico - self.dd:
                    self.fecha(b['c']); self.reprov += 1; self.ativa = False; self.reset_aval(dt)
                # aprovacao
                elif pr >= self.meta and len(self.dias) >= MIN_DIAS:
                    self.fecha(b['c']); self.aprov += 1
                    self.d2a.append((dt - self.ini_aval).days)
                    self.ativa = False; self.reset_aval(dt)

            if m >= 15*60+55:
                if self.pos != 0: self.fecha(b['c'])
                continue
            if not self.ativa or self.block_dia: continue

            if self.pos == 0:
                getattr(self, 'sig_'+self.modo)(b, m, d)

        if self.pos != 0: self.fecha(self.bars[-1]['c'])
        return self.metricas()

    # ---------- sinais ----------
    def sig_ORB(self, b, m, d):
        if not self.orb_ok or self.trade_dia or m < 9*60+35 or m >= 10*60+15: return
        rng = self.orb_hi - self.orb_lo
        if rng <= 0: return
        c = b['c']
        if c > self.orb_hi and c > self.vwap:
            self.abre(1, c, self.orb_hi - rng*0.3, self.orb_hi + rng*1.5, d)
        elif c < self.orb_lo and c < self.vwap:
            self.abre(-1, c, self.orb_lo + rng*0.3, self.orb_lo - rng*1.5, d)

    def sig_MEANREV(self, b, m, d):
        if m < 9*60+30 or m >= 15*60: return
        dist = 40*TICK; c = b['c']
        if c < self.vwap - dist:
            self.abre(1, c, c-30*TICK, c+25*TICK, d)
        elif c > self.vwap + dist:
            self.abre(-1, c, c+30*TICK, c-25*TICK, d)

    def sig_NIVEIS(self, b, m, d):
        if m < 9*60+30 or m >= 15*60 or self.pd_hi is None: return
        tol = 6*TICK; h, l, c = b['h'], b['l'], b['c']
        if h >= self.pd_hi - tol and c < self.pd_hi:
            self.abre(-1, c, c+24*TICK, c-30*TICK, d)
        elif l <= self.pd_lo + tol and c > self.pd_lo:
            self.abre(1, c, c-24*TICK, c+30*TICK, d)

    def sig_MATHEUS(self, b, m, d):
        # canal 00-12h ET; apos 12h opera breakout; stop em Fib, alvo por extensao
        if not self.man_ok or self.trade_dia or m < 12*60 or m >= 15*60: return
        rng = self.man_hi - self.man_lo
        if rng <= 0: return
        fib382 = self.man_lo + 0.382*rng
        fib618 = self.man_lo + 0.618*rng
        c = b['c']
        if c > self.man_hi:                       # rompe topo do canal -> long
            self.abre(1, c, fib618, self.man_hi + 0.5*rng, d)
        elif c < self.man_lo:                      # rompe fundo -> short
            self.abre(-1, c, fib382, self.man_lo - 0.5*rng, d)

    def metricas(self):
        n = len(self.trades); wins = [t for t in self.trades if t > 0]
        gw = sum(wins); gl = abs(sum(t for t in self.trades if t <= 0))
        peak = eq = mdd = 0
        for t in self.trades:
            eq += t; peak = max(peak, eq); mdd = min(mdd, eq-peak)
        tot = self.aprov + self.reprov
        return {
            'modo': self.modo, 'trades': n, 'wr': 100*len(wins)/n if n else 0,
            'pf': (gw/gl if gl > 0 else 99), 'net': sum(self.trades),
            'mdd': mdd, 'aprov': self.aprov, 'reprov': self.reprov, 'tot': tot,
            'taxa': 100*self.aprov/tot if tot else 0,
            'd2a': sum(self.d2a)/len(self.d2a) if self.d2a else 0,
        }


def linha(r):
    pf = '∞' if r['pf'] >= 99 else f"{r['pf']:.2f}"
    return (f"  {r['modo']:9s} {r['trades']:>5} {r['wr']:>5.0f}% {pf:>6} "
            f"{r['net']:>11,.0f} {r['mdd']:>10,.0f} {r['aprov']:>6} {r['reprov']:>7} {r['taxa']:>6.0f}%")


if __name__ == '__main__':
    print("Carregando dados reais do NQ (NinjaTrader)...")
    bars = carregar_todos('NQ_dados')
    print(f"Barras 1min (dedup): {len(bars):,}")
    print(f"Periodo: {bars[0]['dt'].strftime('%Y-%m-%d %H:%M %Z')} a {bars[-1]['dt'].strftime('%Y-%m-%d %H:%M %Z')}")

    # valida timezone: barra de maior volume deve cair ~09:30-10:00 ET
    from collections import defaultdict
    volh = defaultdict(float)
    for b in bars: volh[mins(b['dt'])//60] += b['v']
    pico_h = max(volh, key=volh.get)
    print(f"Hora ET de maior volume: {pico_h:02d}:00  (esperado ~09-10h = abertura cash) {'OK' if 9<=pico_h<=10 else 'CONFERIR'}")

    modos = ['ORB', 'MEANREV', 'NIVEIS', 'MATHEUS']
    for conta in ['50K', '100K']:
        print(f"\n{'='*82}")
        print(f"  CONTA APEX {conta}  (meta ${CONTAS[conta]['meta']:,.0f} / DD ${CONTAS[conta]['dd']:,.0f}) | 1 contrato NQ | custo ${RT_COST}/RT")
        print(f"{'-'*82}")
        print(f"  {'estrat':9s} {'trades':>5} {'WR':>6} {'PF':>6} {'PnL$':>11} {'maxDD$':>10} {'aprov':>6} {'reprov':>7} {'taxa':>7}")
        print(f"  {'-'*78}")
        res = []
        for mo in modos:
            res.append(BT(bars, mo, conta, pv=PV_NQ, contratos=1).run())
        for r in res:
            print(linha(r))

    print(f"\n{'='*82}")
    print("  Obs: ~10,5 meses reais (buracos em set/dez/mar = vencimento de contrato).")
    print("  Saida intrabar conservadora (stop antes do alvo) = numero realista, nao otimista.")
    print(f"{'='*82}")
