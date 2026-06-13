#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backtest DIRECIONAL das 3 estrategias p/ aprovar conta Apex (NQ, 5min).
Dados: Yahoo Finance NQ=F 5min / ultimos ~60 dias (gratis).
Objetivo: comparar ORB+VWAP vs MeanReversion vs Niveis e ver qual segue.

ATENCAO: periodo curto (~45 pregoes). Serve p/ DIRECAO, nao p/ numero final.
"""
import json
from datetime import datetime, timezone, timedelta

# ---------------- Parametros de mercado (NQ E-mini) ----------------
ET           = timezone(timedelta(hours=-4))   # abr-jun/2026 = EDT (UTC-4)
POINT_VALUE  = 20.0     # USD por ponto (NQ)
TICK         = 0.25
TICK_VALUE   = 5.0      # USD por tick
RT_COST      = 5.0      # custo round-turn por contrato (comissao ~3.5 + slippage)
CONTRATOS    = 1

# ---------------- Regras Apex (conta 50K) ----------------
META_LUCRO   = 3000.0
LIMITE_DD    = 2500.0
MIN_DIAS     = 7

# ---------------- Horarios (ET) ----------------
SESS_INI = 9*60+30     # 09:30
ORB_FIM  = 9*60+35     # 09:35 (1 candle de 5m)
ENT_FIM  = 10*60+15    # 10:15 corte de entrada ORB
MR_FIM   = 15*60+0     # 15:00 corte mean reversion / niveis
FLATTEN  = 15*60+55    # 15:55 zera tudo


def carregar(path):
    d = json.load(open(path))
    r = d['chart']['result'][0]
    ts = r['timestamp']; q = r['indicators']['quote'][0]
    bars = []
    for i, t in enumerate(ts):
        o, h, l, c, v = q['open'][i], q['high'][i], q['low'][i], q['close'][i], q['volume'][i]
        if None in (o, h, l, c):
            continue
        dt = datetime.fromtimestamp(t, ET)
        # garante coerencia OHLC
        h = max(h, o, c); l = min(l, o, c)
        bars.append({'dt': dt, 'o': float(o), 'h': float(h), 'l': float(l),
                     'c': float(c), 'v': float(v or 0)})
    bars.sort(key=lambda b: b['dt'])
    return bars


def minutos(dt):
    return dt.hour * 60 + dt.minute


def em_sessao(dt):
    return SESS_INI <= minutos(dt) < 16*60


class Backtest:
    def __init__(self, bars, modo):
        self.bars = bars
        self.modo = modo
        # posicao
        self.pos = 0            # +1 long, -1 short, 0 flat (em contratos)
        self.entry = 0.0
        self.stop = 0.0
        self.target = 0.0
        # contabilidade de trades
        self.trades = []        # lista de PnL $ por trade (liquido)
        self.realized = 0.0     # PnL realizado acumulado (global, $)
        # estado por sessao
        self.vwap_pv = 0.0
        self.vwap_v = 0.0
        self.vwap = 0.0
        self.orb_hi = None
        self.orb_lo = None
        self.orb_pronto = False
        self.trade_no_dia = False
        self.dia = None
        self.cur_hi = None
        self.cur_lo = None
        self.pd_hi = None       # prior-day high (sessao regular)
        self.pd_lo = None
        # simulador Apex
        self.real_ini_aval = 0.0
        self.pico = 0.0
        self.dias_op = set()
        self.aval_ativa = True
        self.aprovadas = 0
        self.reprovadas = 0
        self.dias_p_aprovar = []
        self.aval_inicio = None
        # curva de equity p/ max drawdown
        self.equity_curve = []

    # ---------- gestao de posicao ----------
    def _fecha(self, preco, dt):
        if self.pos == 0:
            return
        pnl_pts = (preco - self.entry) * self.pos
        pnl = pnl_pts * POINT_VALUE * CONTRATOS - RT_COST * CONTRATOS
        self.realized += pnl
        self.trades.append(pnl)
        self.pos = 0

    def _abre(self, lado, preco, stop, target, dt):
        self.pos = lado
        self.entry = preco
        self.stop = stop
        self.target = target
        self.dias_op.add(dt.strftime('%Y-%m-%d'))

    def _checa_saida_intrabar(self, bar, dt):
        """Se em posicao, ve se stop/target bateram na barra. Pior caso = stop primeiro."""
        if self.pos == 0:
            return
        h, l = bar['h'], bar['l']
        if self.pos > 0:  # long
            hit_stop = l <= self.stop
            hit_tgt  = h >= self.target
            if hit_stop:                      # conservador: stop antes do alvo
                self._fecha(self.stop, dt)
            elif hit_tgt:
                self._fecha(self.target, dt)
        else:             # short
            hit_stop = h >= self.stop
            hit_tgt  = l <= self.target
            if hit_stop:
                self._fecha(self.stop, dt)
            elif hit_tgt:
                self._fecha(self.target, dt)

    # ---------- simulador de avaliacao Apex ----------
    def _reset_aval(self, dt):
        self.real_ini_aval = self.realized
        self.pico = 0.0
        self.dias_op = set()
        self.aval_ativa = True
        self.aval_inicio = dt

    def _atualiza_apex(self, bar, dt):
        if not self.aval_ativa:
            return
        pnl_real = self.realized - self.real_ini_aval
        # unrealized pior/melhor caso via high/low
        unreal_fav = unreal_adv = 0.0
        if self.pos > 0:
            unreal_fav = (bar['h'] - self.entry) * POINT_VALUE * CONTRATOS
            unreal_adv = (bar['l'] - self.entry) * POINT_VALUE * CONTRATOS
        elif self.pos < 0:
            unreal_fav = (self.entry - bar['l']) * POINT_VALUE * CONTRATOS
            unreal_adv = (self.entry - bar['h']) * POINT_VALUE * CONTRATOS
        eq_fav = pnl_real + unreal_fav
        eq_adv = pnl_real + unreal_adv
        if eq_fav > self.pico:
            self.pico = eq_fav
        nivel_dd = self.pico - LIMITE_DD

        self.equity_curve.append(pnl_real)

        # REPROVACAO (trailing DD intraday, pior caso)
        if eq_adv <= nivel_dd:
            self._fecha(bar['c'], dt)
            self.reprovadas += 1
            self.aval_ativa = False
            self._reset_aval(dt)
            return
        # APROVACAO (meta + 7 dias, so realizado)
        if pnl_real >= META_LUCRO and len(self.dias_op) >= MIN_DIAS:
            self._fecha(bar['c'], dt)
            self.aprovadas += 1
            self.dias_p_aprovar.append((dt - self.aval_inicio).days)
            self.aval_ativa = False
            self._reset_aval(dt)

    # ---------- loop principal ----------
    def run(self):
        for bar in self.bars:
            dt = bar['dt']
            d = dt.strftime('%Y-%m-%d')
            m = minutos(dt)

            # virada de dia
            if d != self.dia:
                if self.cur_hi is not None:
                    self.pd_hi, self.pd_lo = self.cur_hi, self.cur_lo
                self.dia = d
                self.cur_hi, self.cur_lo = bar['h'], bar['l']
                self.trade_no_dia = False
            else:
                if em_sessao(dt):
                    self.cur_hi = bar['h'] if self.cur_hi is None else max(self.cur_hi, bar['h'])
                    self.cur_lo = bar['l'] if self.cur_lo is None else min(self.cur_lo, bar['l'])

            # reset VWAP/ORB no inicio da sessao regular
            if m == SESS_INI:
                self.vwap_pv = self.vwap_v = 0.0
                self.orb_hi = self.orb_lo = None
                self.orb_pronto = False

            # so opera/contabiliza na sessao regular
            if not em_sessao(dt):
                continue

            # VWAP
            tp = (bar['h'] + bar['l'] + bar['c']) / 3.0
            self.vwap_pv += tp * bar['v']
            self.vwap_v += bar['v']
            self.vwap = self.vwap_pv / self.vwap_v if self.vwap_v > 0 else bar['c']

            # ORB (candle das 9:30)
            if SESS_INI <= m < ORB_FIM:
                self.orb_hi = bar['h'] if self.orb_hi is None else max(self.orb_hi, bar['h'])
                self.orb_lo = bar['l'] if self.orb_lo is None else min(self.orb_lo, bar['l'])
            elif m >= ORB_FIM and not self.orb_pronto and self.orb_hi is not None:
                self.orb_pronto = True

            # 1) primeiro resolve saidas de posicao aberta
            self._checa_saida_intrabar(bar, dt)
            # 2) atualiza simulador apex (DD/meta)
            self._atualiza_apex(bar, dt)

            # flatten EOD
            if m >= FLATTEN:
                self._fecha(bar['c'], dt)
                continue
            if not self.aval_ativa:
                continue

            # 3) entradas (so se flat)
            if self.pos == 0:
                if self.modo == 'ORB_VWAP':
                    self._sig_orb(bar, m)
                elif self.modo == 'MEANREV':
                    self._sig_meanrev(bar, m)
                elif self.modo == 'NIVEIS':
                    self._sig_niveis(bar, m)

        # fecha posicao residual
        if self.pos != 0:
            self._fecha(self.bars[-1]['c'], self.bars[-1]['dt'])
        return self._metricas()

    # ---------- sinais ----------
    def _sig_orb(self, bar, m):
        if not self.orb_pronto or self.trade_no_dia:
            return
        if m < ORB_FIM or m >= ENT_FIM:
            return
        rng = self.orb_hi - self.orb_lo
        if rng <= 0:
            return
        c = bar['c']
        if c > self.orb_hi and c > self.vwap:
            stop = self.orb_hi - rng * 0.5
            tgt = self.orb_hi + rng * 1.0
            self._abre(+1, c, stop, tgt, bar['dt'])
            self.trade_no_dia = True
        elif c < self.orb_lo and c < self.vwap:
            stop = self.orb_lo + rng * 0.5
            tgt = self.orb_lo - rng * 1.0
            self._abre(-1, c, stop, tgt, bar['dt'])
            self.trade_no_dia = True

    def _sig_meanrev(self, bar, m):
        if m < SESS_INI or m >= MR_FIM:
            return
        dist = 40 * TICK
        c = bar['c']
        if c < self.vwap - dist:
            self._abre(+1, c, c - 30*TICK, c + 25*TICK, bar['dt'])
        elif c > self.vwap + dist:
            self._abre(-1, c, c + 30*TICK, c - 25*TICK, bar['dt'])

    def _sig_niveis(self, bar, m):
        if m < SESS_INI or m >= MR_FIM:
            return
        if self.pd_hi is None or self.pd_lo is None:
            return
        tol = 6 * TICK
        h, l, c = bar['h'], bar['l'], bar['c']
        if h >= self.pd_hi - tol and c < self.pd_hi:
            self._abre(-1, c, c + 24*TICK, c - 30*TICK, bar['dt'])
        elif l <= self.pd_lo + tol and c > self.pd_lo:
            self._abre(+1, c, c - 24*TICK, c + 30*TICK, bar['dt'])

    # ---------- metricas ----------
    def _metricas(self):
        n = len(self.trades)
        wins = [t for t in self.trades if t > 0]
        losses = [t for t in self.trades if t <= 0]
        gross_w = sum(wins)
        gross_l = abs(sum(losses))
        win_rate = 100.0 * len(wins) / n if n else 0
        pf = (gross_w / gross_l) if gross_l > 0 else float('inf')
        net = sum(self.trades)
        expc = net / n if n else 0
        # max drawdown da curva de equity realizada
        peak = 0; maxdd = 0; eq = 0
        for t in self.trades:
            eq += t
            peak = max(peak, eq)
            maxdd = min(maxdd, eq - peak)
        aval_tot = self.aprovadas + self.reprovadas
        taxa = 100.0 * self.aprovadas / aval_tot if aval_tot else 0
        mdias = sum(self.dias_p_aprovar)/len(self.dias_p_aprovar) if self.dias_p_aprovar else 0
        return {
            'modo': self.modo, 'trades': n, 'win_rate': win_rate, 'pf': pf,
            'net': net, 'expect': expc, 'avg_win': (gross_w/len(wins) if wins else 0),
            'avg_loss': (-gross_l/len(losses) if losses else 0), 'maxdd': maxdd,
            'aprovadas': self.aprovadas, 'reprovadas': self.reprovadas,
            'aval_tot': aval_tot, 'taxa': taxa, 'mdias': mdias,
        }


def fmt(r):
    pf = '∞' if r['pf'] == float('inf') else f"{r['pf']:.2f}"
    print(f"\n{'='*58}")
    print(f"  {r['modo']}")
    print(f"{'-'*58}")
    print(f"  Trades ................ {r['trades']}")
    print(f"  Win rate .............. {r['win_rate']:.1f}%")
    print(f"  Profit factor ......... {pf}")
    print(f"  PnL liquido (1 NQ) .... ${r['net']:,.0f}")
    print(f"  Expectancy/trade ...... ${r['expect']:,.1f}")
    print(f"  Ganho medio ........... ${r['avg_win']:,.0f}")
    print(f"  Perda media ........... ${r['avg_loss']:,.0f}")
    print(f"  Max drawdown .......... ${r['maxdd']:,.0f}")
    print(f"  -- Simulacao Apex 50K (meta $3k / DD $2.5k) --")
    print(f"  Avaliacoes ............ {r['aval_tot']}")
    print(f"  APROVADAS ............. {r['aprovadas']}")
    print(f"  REPROVADAS ............ {r['reprovadas']}")
    print(f"  Taxa de aprovacao ..... {r['taxa']:.0f}%")


if __name__ == '__main__':
    bars = carregar('backtest/data/nq_5m_60d.json')
    print(f"Candles carregados: {len(bars)}")
    print(f"Periodo: {bars[0]['dt'].strftime('%Y-%m-%d')} a {bars[-1]['dt'].strftime('%Y-%m-%d')}")
    print(f"Contratos: {CONTRATOS} NQ | custo round-turn: ${RT_COST}/contrato")
    resultados = []
    for modo in ['ORB_VWAP', 'MEANREV', 'NIVEIS']:
        bt = Backtest(bars, modo)
        resultados.append(bt.run())
    for r in resultados:
        fmt(r)
    # ranking
    print(f"\n{'='*58}")
    print("  RANKING (por PnL liquido)")
    print(f"{'-'*58}")
    for i, r in enumerate(sorted(resultados, key=lambda x: x['net'], reverse=True), 1):
        print(f"  {i}. {r['modo']:12s} ${r['net']:>8,.0f}  | WR {r['win_rate']:.0f}% | aprov {r['aprovadas']}/{r['aval_tot']}")
    print(f"{'='*58}")
