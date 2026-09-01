#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AUDITORIA — forward test do BotAprovacao_BETrigger25 em JULHO/2026 (MNQ, Market
Replay ao vivo). Os 44 trades REAIS registrados em forward-test-replay-25k/
2026-07-betrigger25/ (fonte: [MeuTrade] PnL de cada trade [REAL] no log do
NinjaScript).

Config: 5 MNQ ($2/pt), SL 12,5pt, TP 60pt, BE trig 2,5pt, BE-lock prop 0,75,
trail 1,75pt, TolToque 20 ticks, MaxDist 20pt, StopDiario $750, Max 12/dia.
"""
import statistics as st
from collections import Counter

# (dia, hora, dir, motivo, be, fav_pts, pnl, tag)
#   motivo: TRAIL | STOP (stop cheio)
#   be: True se o breakeven ativou
#   fav_pts: favor maximo (MFE) em pontos a partir do fill real
#   tag: '' | 'facada' | 'gap' (gap de entrada) | 'runner' (trailing deixou correr >8pt)
T = [
 ('02/07','10:39','L','TRAIL',True, 7.35,  51.0,'runner'),
 ('02/07','11:27','L','STOP', False,0.75,-169.0,'facada'),

 ('06/07','10:52','S','TRAIL',True, 3.00,  -6.0,''),
 ('06/07','11:12','S','STOP', True, 3.00,  36.0,''),
 ('06/07','11:20','S','TRAIL',True, 3.90,  -5.5,''),
 ('06/07','11:22','S','STOP', False,0.80,-148.0,'facada'),
 ('06/07','11:29','S','STOP', False,0.85,-122.0,'facada'),

 ('08/07','11:46','L','TRAIL',True, 2.65,  -7.0,''),
 ('08/07','12:00','L','STOP', False,2.10,-158.0,'gap'),
 ('08/07','12:01','L','STOP', False,1.85,-139.0,'facada'),
 ('08/07','12:06','L','TRAIL',True, 2.65,  18.0,''),
 ('08/07','13:15','L','TRAIL',True, 2.50,  16.0,''),

 ('10/07','12:31','S','TRAIL',True, 2.95,  15.5,''),
 ('10/07','12:33','S','TRAIL',True, 4.15,  26.5,''),
 ('10/07','12:34','S','TRAIL',True, 4.50,  52.0,'runner'),
 ('10/07','13:16','S','STOP', False,1.00,-156.5,'facada'),

 ('13/07','10:56','L','TRAIL',True, 3.35,  48.0,''),
 ('13/07','11:17','L','TRAIL',True,12.00, 123.5,'runner'),
 ('13/07','11:18','L','STOP', False,0.55,-153.0,'gap'),
 ('13/07','11:19','L','TRAIL',True,10.00, 102.0,'runner'),
 ('13/07','13:27','L','STOP', False,0.75,-121.0,'facada'),

 ('14/07','10:32','S','TRAIL',True,15.40, -11.0,''),
 ('14/07','10:33','S','TRAIL',True, 3.80,  -7.0,''),
 ('14/07','10:51','S','STOP', False,1.05,-119.5,'facada'),
 ('14/07','10:53','S','TRAIL',True, 3.25,  -2.5,''),
 ('14/07','10:56','S','TRAIL',True, 5.75,  -4.0,''),
 ('14/07','11:02','S','TRAIL',True, 2.55,   4.0,''),

 ('15/07','10:38','S','TRAIL',True, 3.40,  16.5,''),
 ('15/07','10:40','S','TRAIL',True, 3.90,  21.0,''),
 ('15/07','11:09','S','TRAIL',True, 2.75,   1.0,''),
 ('15/07','11:44','L','TRAIL',True, 2.85,  21.0,''),
 ('15/07','11:46','L','TRAIL',True, 4.20, -13.5,''),
 ('15/07','12:16','L','TRAIL',True, 3.00,   5.5,''),

 ('16/07','10:39','L','TRAIL',True, 6.15,  -4.0,''),
 ('16/07','10:41','L','TRAIL',True, 4.00,  -5.5,''),
 ('16/07','11:04','L','TRAIL',True, 2.85,  10.5,''),
 ('16/07','11:05','L','TRAIL',True, 3.35,   8.5,'gap'),   # entry gap +6,4pt mas nao virou loss
 ('16/07','11:51','L','TRAIL',True, 3.20,  -5.5,''),

 ('20/07','10:30','L','TRAIL',True, 5.05, -11.5,''),
 ('20/07','10:31','S','TRAIL',True, 2.95,  -6.0,''),
 ('20/07','10:53','S','TRAIL',True, 3.50,  13.0,''),
 ('20/07','10:54','S','TRAIL',True, 2.50,  -7.0,''),
 ('20/07','10:56','S','TRAIL',True, 3.00,  28.0,''),
 ('20/07','10:57','L','TRAIL',True, 4.85,  -6.5,''),
]

DOW = {'02/07':'qui','06/07':'seg','08/07':'qua','10/07':'sex','13/07':'seg',
       '14/07':'ter','15/07':'qua','16/07':'qui','20/07':'seg'}


def stats(rows, lbl):
    if not rows:
        print(f"  {lbl:26s} (vazio)"); return
    pnl = [r[6] for r in rows]
    w = [x for x in pnl if x > 0]; l = [x for x in pnl if x <= 0]
    gw = sum(w); gl = abs(sum(l))
    pf = gw/gl if gl else 99
    exp = st.mean(pnl)
    aw = st.mean(w) if w else 0; al = st.mean(l) if l else 0
    print(f"  {lbl:26s} n={len(rows):<3} PnL ${sum(pnl):>+8,.0f}  WR {100*len(w)/len(rows):>3.0f}%  "
          f"PF {pf:>4.2f}  E[${exp:>+6.1f}]  gW ${aw:>+6.1f}  pL ${al:>+7.1f}")


def main():
    pnl = [r[6] for r in T]
    n = len(T); w = [x for x in pnl if x > 0]; l = [x for x in pnl if x <= 0]
    gw = sum(w); gl = abs(sum(l))

    print("="*100)
    print(f"  AUDITORIA — {n} trades REAIS, forward test julho/2026 (BETrigger25, MNQ 5c, Market Replay)")
    print("="*100)
    print(f"  PnL total: ${sum(pnl):+,.1f}   |   Win rate: {100*len(w)/n:.1f}%   "
          f"({len(w)}G / {len(l)}L)")
    print(f"  Profit Factor: {gw/gl:.2f}   (ganhos ${gw:,.0f} / perdas ${gl:,.0f})")
    print(f"  Expectancy: ${st.mean(pnl):+.1f}/trade   |   mediana ${st.median(pnl):+.1f}")
    print(f"  Avg Win: ${st.mean(w):+.1f}   Avg Loss: ${st.mean(l):+.1f}   "
          f"Payoff (|AW/AL|): {abs(st.mean(w)/st.mean(l)):.2f}")
    print(f"  Desvio-padrao do PnL/trade: ${st.pstdev(pnl):.1f}")
    print(f"  Maior ganho: ${max(pnl):+,.0f}   Maior perda: ${min(pnl):+,.0f}")
    # drawdown na curva de equity
    eq = 0; peak = 0; mdd = 0
    for x in pnl:
        eq += x; peak = max(peak, eq); mdd = max(mdd, peak-eq)
    print(f"  Curva de equity: pico ${peak:+,.0f}  |  fim ${eq:+,.0f}  |  Max Drawdown ${mdd:,.0f}")
    print(f"  Recovery Factor (|PnL|/MDD): {abs(eq)/mdd:.2f}   (< 0 = nao recuperou nada)")
    # 'sharpe' simples por trade
    sh = st.mean(pnl)/st.pstdev(pnl)
    dn = [x for x in pnl if x < 0]
    so = st.mean(pnl)/st.pstdev(dn) if len(dn) > 1 else 0
    print(f"  Sharpe/trade: {sh:.3f}   Sortino/trade: {so:.3f}   (anualizar nao faz sentido c/ n={n})")

    print("\n  --- SEQUENCIA (streaks) ---")
    streak = []; cur = 0
    for x in pnl:
        s = 1 if x > 0 else -1
        if cur == 0 or (cur > 0) == (s > 0): cur += s
        else: streak.append(cur); cur = s
    streak.append(cur)
    print(f"  {streak}")
    print(f"  pior sequencia de perdas: {min(streak)} trades   melhor de ganhos: {max(streak)}")

    print("\n  --- DISTRIBUICAO ---")
    faixas = [(-999,-100),(-100,-50),(-50,-10),(-10,0),(0,10),(10,30),(30,80),(80,999)]
    for a,b in faixas:
        c = sum(1 for x in pnl if a <= x < b)
        bar = '#'*c
        print(f"    [{a:>5},{b:>4}) {c:>2}  {bar}")

    print("\n" + "="*100); print("  POR MOTIVO DE SAIDA"); print("="*100)
    stats([r for r in T if r[3]=='TRAIL'], 'TRAIL (trailing/BE)')
    stats([r for r in T if r[3]=='STOP'], 'STOP cheio (BE nao ativou)')
    stats([r for r in T if r[3]=='STOP' and r[7]=='facada'], '  -> facada (fav<2pt)')
    stats([r for r in T if r[7]=='gap'], 'GAP de entrada')
    stats([r for r in T if r[7]=='runner'], 'RUNNER (trail deixou correr)')
    stats([r for r in T if r[3]=='TRAIL' and r[7]==''], 'TRAIL "normal" (nem runner)')

    print("\n" + "="*100); print("  POR DIRECAO"); print("="*100)
    stats([r for r in T if r[2]=='L'], 'LONG')
    stats([r for r in T if r[2]=='S'], 'SHORT')

    print("\n" + "="*100); print("  POR HORARIO (hora ET do fill)"); print("="*100)
    for h in sorted(set(r[1][:2] for r in T)):
        stats([r for r in T if r[1][:2]==h], f'{h}:00-{h}:59')

    print("\n" + "="*100); print("  POR DIA DA SEMANA"); print("="*100)
    for d in ('seg','ter','qua','qui','sex'):
        stats([r for r in T if DOW[r[0]]==d], d)

    print("\n" + "="*100); print("  POR DIA"); print("="*100)
    for d in sorted(set(r[0] for r in T), key=lambda x:(x[3:],x[:2])):
        stats([r for r in T if r[0]==d], d + f" ({DOW[d]})")

    print("\n" + "="*100); print("  FAVOR MAXIMO (MFE) vs RESULTADO — os trailing sao 'estrangulados'?"); print("="*100)
    for a,b in [(0,2),(2,3),(3,4),(4,6),(6,10),(10,99)]:
        g = [r for r in T if a <= r[5] < b]
        if not g: continue
        pn = [r[6] for r in g]
        print(f"  MFE {a}-{b}pt: n={len(g):<3} PnL/trade ${st.mean(pn):>+7.1f}  "
              f"(o trade chegou a +{a}-{b}pt de favor e terminou nisso)")
    # dos trailing que ativaram BE, quantos sairam <= $0 apesar de MFE >= 3pt?
    estrang = [r for r in T if r[3]=='TRAIL' and r[4] and r[5] >= 3.0 and r[6] <= 0]
    print(f"\n  TRAILING ESTRANGULADO (BE ativou, MFE>=3pt, saiu <= $0): {len(estrang)} trades, "
          f"${sum(r[6] for r in estrang):,.0f}")
    print(f"    esses 'deveriam' ter dado ~+$20-40 cada. Perda de oportunidade ~"
          f"${len(estrang)*25:,.0f} a ${len(estrang)*35:,.0f}.")

    print("\n" + "="*100); print("  OS 8 GRANDES LOSSES (o mes inteiro esta aqui)"); print("="*100)
    big = sorted([r for r in T if r[6] <= -100], key=lambda r: r[6])
    for r in big:
        print(f"  {r[0]} {r[1]} {r[2]} {r[3]:5s} fav +{r[5]:.2f}pt  ${r[6]:+,.0f}  [{r[7]}]")
    print(f"  soma dos 8: ${sum(r[6] for r in big):,.0f}")
    resto = [r for r in T if r[6] > -100]
    print(f"  os outros {len(resto)} trades: ${sum(r[6] for r in resto):+,.0f}")


if __name__ == '__main__':
    main()
