#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backtest conta APEX 25K com TP/SL FIXO ($500/$250) nas 4 estrategias.
Mesma gestao de saida p/ todas; muda so a logica de ENTRADA de cada uma.
Dados: NQ 1-min reais (NinjaTrader), ~10,5 meses.
"""
import glob, os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from collections import defaultdict

ET  = ZoneInfo('America/New_York'); UTC = timezone.utc
PV  = 20.0; TICK = 0.25; RT_COST = 5.0
META = 1500.0; DD = 1500.0; MIN_DIAS = 7      # Apex 25K
TP_USD = 500.0; SL_USD = 250.0                # alvo/stop fixos pedidos


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
                if dt not in vistos:
                    vistos[dt] = (dt.astimezone(ET), o, h, l, c, v)
    return [{'dt': vistos[k][0], 'o': vistos[k][1], 'h': vistos[k][2],
             'l': vistos[k][3], 'c': vistos[k][4], 'v': vistos[k][5]} for k in sorted(vistos)]


def mins(dt): return dt.hour*60 + dt.minute


class BT:
    def __init__(self, bars, modo, q=1, kill_frac=0.5):
        self.bars = bars; self.modo = modo; self.q = q; self.kill = kill_frac
        self.pts_tp = TP_USD/(PV*q); self.pts_sl = SL_USD/(PV*q)
        self.pos = 0; self.entry = self.stop = self.target = 0.0
        self.realized = 0.0; self.trades = []
        self.vpv = self.vv = self.vwap = 0.0
        self.orb_hi = self.orb_lo = None; self.orb_ok = False; self.trade_dia = False
        self.dia = None; self.cur_hi = self.cur_lo = None
        self.pd_hi = self.pd_lo = None
        self.man_hi = self.man_lo = None; self.man_ok = False
        self.r_ini = 0.0; self.pico = 0.0; self.dias = set(); self.ativa = True
        self.aprov = 0; self.reprov = 0; self.d2a = []; self.ini_aval = None
        self.pnl_dia0 = 0.0; self.block_dia = False; self.dia_kill = None

    def fecha(self, p):
        if self.pos == 0: return
        pnl = (p-self.entry)*self.pos*PV*self.q - RT_COST*self.q
        self.realized += pnl; self.trades.append(pnl); self.pos = 0

    def abre(self, lado, p, d):
        # TP/SL fixos em $ p/ TODAS as estrategias
        if lado == 1:
            self.stop = p - self.pts_sl; self.target = p + self.pts_tp
        else:
            self.stop = p + self.pts_sl; self.target = p - self.pts_tp
        self.pos = lado; self.entry = p; self.dias.add(d); self.trade_dia = True

    def reset_aval(self, dt):
        self.r_ini = self.realized; self.pico = 0.0; self.dias = set()
        self.ativa = True; self.ini_aval = dt

    def run(self):
        for b in self.bars:
            dt = b['dt']; m = mins(dt); d = dt.strftime('%Y-%m-%d')
            sess = 9*60+30 <= m < 16*60
            if d != self.dia:
                if self.cur_hi is not None: self.pd_hi, self.pd_lo = self.cur_hi, self.cur_lo
                self.dia = d; self.cur_hi = self.cur_lo = None; self.trade_dia = False
                self.man_hi = self.man_lo = None; self.man_ok = False
            if m < 12*60:
                self.man_hi = b['h'] if self.man_hi is None else max(self.man_hi, b['h'])
                self.man_lo = b['l'] if self.man_lo is None else min(self.man_lo, b['l'])
            elif not self.man_ok and self.man_hi is not None: self.man_ok = True
            if sess:
                self.cur_hi = b['h'] if self.cur_hi is None else max(self.cur_hi, b['h'])
                self.cur_lo = b['l'] if self.cur_lo is None else min(self.cur_lo, b['l'])
            if m == 9*60+30:
                self.vpv = self.vv = 0.0; self.orb_hi = self.orb_lo = None; self.orb_ok = False
            if sess:
                tp = (b['h']+b['l']+b['c'])/3.0
                self.vpv += tp*b['v']; self.vv += b['v']
                self.vwap = self.vpv/self.vv if self.vv > 0 else b['c']
                if 9*60+30 <= m < 9*60+35:
                    self.orb_hi = b['h'] if self.orb_hi is None else max(self.orb_hi, b['h'])
                    self.orb_lo = b['l'] if self.orb_lo is None else min(self.orb_lo, b['l'])
                elif m >= 9*60+35 and not self.orb_ok and self.orb_hi is not None: self.orb_ok = True
            if d != self.dia_kill:
                self.dia_kill = d; self.pnl_dia0 = self.realized; self.block_dia = False

            if self.pos != 0:
                if self.pos > 0:
                    if b['l'] <= self.stop: self.fecha(self.stop)
                    elif b['h'] >= self.target: self.fecha(self.target)
                else:
                    if b['h'] >= self.stop: self.fecha(self.stop)
                    elif b['l'] <= self.target: self.fecha(self.target)

            if self.ativa:
                pr = self.realized - self.r_ini
                ua = 0.0
                if self.pos > 0: ua = (b['l']-self.entry)*PV*self.q
                elif self.pos < 0: ua = (self.entry-b['h'])*PV*self.q
                uf = 0.0
                if self.pos > 0: uf = (b['h']-self.entry)*PV*self.q
                elif self.pos < 0: uf = (self.entry-b['l'])*PV*self.q
                if pr+uf > self.pico: self.pico = pr+uf
                if (self.realized - self.pnl_dia0 + ua) <= -(DD*self.kill):
                    self.block_dia = True
                    if self.pos != 0: self.fecha(b['c'])
                if pr+ua <= self.pico - DD:
                    self.fecha(b['c']); self.reprov += 1; self.ativa = False; self.reset_aval(dt)
                elif pr >= META and len(self.dias) >= MIN_DIAS:
                    self.fecha(b['c']); self.aprov += 1
                    self.d2a.append((dt-self.ini_aval).days); self.ativa = False; self.reset_aval(dt)

            if m >= 15*60+55:
                if self.pos != 0: self.fecha(b['c'])
                continue
            if not self.ativa or self.block_dia: continue
            if self.pos == 0:
                getattr(self, 'sig_'+self.modo)(b, m, d)
        if self.pos != 0: self.fecha(self.bars[-1]['c'])
        return self.metricas()

    # ---- ENTRADAS (so direcao; saida = TP/SL fixo) ----
    def sig_ORB(self, b, m, d):
        if not self.orb_ok or self.trade_dia or m < 9*60+35 or m >= 10*60+15: return
        if self.orb_hi - self.orb_lo <= 0: return
        c = b['c']
        if c > self.orb_hi and c > self.vwap: self.abre(1, c, d)
        elif c < self.orb_lo and c < self.vwap: self.abre(-1, c, d)

    def sig_MEANREV(self, b, m, d):
        if m < 9*60+30 or m >= 15*60: return
        dist = 40*TICK; c = b['c']
        if c < self.vwap - dist: self.abre(1, c, d)
        elif c > self.vwap + dist: self.abre(-1, c, d)

    def sig_NIVEIS(self, b, m, d):
        if m < 9*60+30 or m >= 15*60 or self.pd_hi is None: return
        tol = 6*TICK; h, l, c = b['h'], b['l'], b['c']
        if h >= self.pd_hi - tol and c < self.pd_hi: self.abre(-1, c, d)
        elif l <= self.pd_lo + tol and c > self.pd_lo: self.abre(1, c, d)

    def sig_MATHEUS(self, b, m, d):
        if not self.man_ok or self.trade_dia or m < 12*60 or m >= 15*60: return
        if self.man_hi - self.man_lo <= 0: return
        c = b['c']
        if c > self.man_hi: self.abre(1, c, d)
        elif c < self.man_lo: self.abre(-1, c, d)

    def metricas(self):
        n = len(self.trades); wins = [t for t in self.trades if t > 0]
        gw = sum(wins); gl = abs(sum(t for t in self.trades if t <= 0))
        peak = eq = mdd = 0
        for t in self.trades:
            eq += t; peak = max(peak, eq); mdd = min(mdd, eq-peak)
        tot = self.aprov + self.reprov
        return {'modo': self.modo, 'n': n, 'wr': 100*len(wins)/n if n else 0,
                'pf': (gw/gl if gl > 0 else 99), 'net': sum(self.trades), 'mdd': mdd,
                'aprov': self.aprov, 'reprov': self.reprov, 'tot': tot,
                'taxa': 100*self.aprov/tot if tot else 0,
                'd2a': sum(self.d2a)/len(self.d2a) if self.d2a else 0}


if __name__ == '__main__':
    print("Carregando NQ 1-min real...")
    bars = carregar('NQ_dados')
    print(f"Barras: {len(bars):,} | {bars[0]['dt'].strftime('%Y-%m-%d')} a {bars[-1]['dt'].strftime('%Y-%m-%d')}")
    print(f"\nCONTA APEX 25K | meta ${META:,.0f} / DD ${DD:,.0f} | 1 NQ | TP ${TP_USD:.0f} (25pt) / SL ${SL_USD:.0f} (12,5pt) | R:R 2:1")
    print("="*84)
    print(f"  {'estrat':9s} {'trades':>6} {'WR':>6} {'PF':>6} {'PnL$':>11} {'maxDD$':>10} {'aprov':>6} {'reprov':>7} {'taxa':>7} {'dias':>5}")
    print("  " + "-"*80)
    for mo in ['ORB', 'MEANREV', 'NIVEIS', 'MATHEUS']:
        r = BT(bars, mo, q=1).run()
        pf = '∞' if r['pf'] >= 99 else f"{r['pf']:.2f}"
        print(f"  {r['modo']:9s} {r['n']:>6} {r['wr']:>5.0f}% {pf:>6} {r['net']:>11,.0f} "
              f"{r['mdd']:>10,.0f} {r['aprov']:>6} {r['reprov']:>7} {r['taxa']:>6.0f}% {r['d2a']:>5.0f}")
    print("="*84)
    print("  ~10,5 meses reais | saida intrabar conservadora (stop antes do alvo) = numero realista")
