#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MOTOR DE RENKO a partir das barras de 1min reais (NQ_dados/).

⚠️ LIMITACAO CONHECIDA E DECLARADA: nao temos dados de TICK do NQ pro periodo de
13 meses do backtest. O tijolo de Renko "de verdade" se forma tick a tick; aqui
ele e' reconstruido varrendo cada barra de 1min com um caminho intrabar ASSUMIDO
(open -> extremo contra -> extremo a favor -> close). Esse modelo:
  - e' PESSIMISTA pra estrategia de tendencia (assume que o preco vai contra
    primeiro dentro da vela -> gera mais tijolo de "ruido"/whipsaw);
  - fica cada vez mais fiel quanto MAIOR o tijolo (brick >= 15pt: a barra de 1min
    quase nunca tem mais de 1-2 tijolos, o caminho assumido quase nao importa);
  - fica cada vez MENOS confiavel quanto menor o tijolo (brick 1-4pt: a barra de
    1min percorre 5-30pt, o caminho assumido domina o resultado -> NAO CONFIAR).

Uso: gerar, pra cada indice de barra, o estado Renko corrente (MA das closes de
tijolo, direcao do ultimo tijolo, se houve cruzamento da MA nessa barra).
"""


def _renko_feeder(brick_pts, reversal_bricks=2):
    """Retorna (feed, estado). feed(price) -> lista de dirs de tijolos que
    fecharam (+1/-1). Renko classico com reversao de `reversal_bricks` tijolos."""
    st = {'last_close': None, 'dir': 0}

    def feed(price):
        emitted = []
        if st['last_close'] is None:
            st['last_close'] = price
            return emitted
        while True:
            lc = st['last_close']; d = st['dir']
            up_th = brick_pts if d >= 0 else reversal_bricks * brick_pts
            dn_th = brick_pts if d <= 0 else reversal_bricks * brick_pts
            if price >= lc + up_th:
                step = up_th if d < 0 else brick_pts
                st['last_close'] = lc + step; st['dir'] = 1
                emitted.append(1); continue
            if price <= lc - dn_th:
                step = dn_th if d > 0 else brick_pts
                st['last_close'] = lc - step; st['dir'] = -1
                emitted.append(-1); continue
            break
        return emitted

    return feed, st


def _intrabar_path(o, h, l, c, model='against_first'):
    """Sequencia de precos-alvo pra varrer dentro da barra."""
    if model == 'against_first':
        return [o, l, h, c] if c >= o else [o, h, l, c]
    elif model == 'favor_first':
        return [o, h, l, c] if c >= o else [o, l, h, c]
    else:  # 'ohlc' cru
        return [o, h, l, c]


def estado_renko(bars, brick_pts, ma_period, reversal_bricks=2,
                 path_model='against_first'):
    """Para cada barra i, devolve dict com o estado Renko AO FIM da barra i:
      ma          : media movel simples das ultimas `ma_period` closes de tijolo
                    (None ate ter tijolos suficientes)
      dir         : direcao do ultimo tijolo (+1/-1/0)
      brick_close : nivel de fechamento do ultimo tijolo
      n_bricks    : total de tijolos formados ate aqui
      cross_up    : True se NESSA barra o regime virou p/ cima (brick_close cruzou
                    a MA de baixo p/ cima) -- gatilho fresco de LONG
      cross_dn    : idem p/ baixo -- gatilho fresco de SHORT
    """
    feed, _ = _renko_feeder(brick_pts, reversal_bricks)
    closes = []          # closes de tijolo em ordem
    regime_prev = 0      # +1 se ultima brick_close > ma, -1 se <, 0 indefinido
    out = []
    for b in bars:
        seq = _intrabar_path(b['o'], b['h'], b['l'], b['c'], path_model)
        prev = seq[0]
        cross_up = cross_dn = False
        for tgt in seq[1:]:
            # varre monotonicamente de prev ate tgt, alimentando o feeder nos
            # pontos em que ele pode fechar tijolo (o feeder ja lida com multiplos)
            for dir_emit in feed(tgt):
                # recompute brick close level from feeder state via closes list
                step = brick_pts
                if closes:
                    closes.append(closes[-1] + dir_emit * step)
                else:
                    closes.append(b['o'] + dir_emit * step)
                if len(closes) >= ma_period:
                    ma = sum(closes[-ma_period:]) / ma_period
                    reg = 1 if closes[-1] > ma else -1
                    if reg != regime_prev and regime_prev != 0:
                        if reg > 0: cross_up = True
                        else: cross_dn = True
                    regime_prev = reg
            prev = tgt
        ma = (sum(closes[-ma_period:]) / ma_period) if len(closes) >= ma_period else None
        d = 0
        if len(closes) >= 2:
            d = 1 if closes[-1] > closes[-2] else -1
        elif len(closes) == 1:
            d = 1 if closes[-1] > bars[0]['o'] else -1
        out.append({'ma': ma, 'dir': d,
                    'brick_close': closes[-1] if closes else None,
                    'n_bricks': len(closes),
                    'cross_up': cross_up, 'cross_dn': cross_dn})
    return out


if __name__ == '__main__':
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from run_estrategias_comparativo import carregar
    bars = carregar('NQ_dados')
    print(f"{len(bars):,} barras 1min | {bars[0]['dt'].date()} -> {bars[-1]['dt'].date()}\n")
    for bp in (4, 10, 15, 20, 25):
        stt = estado_renko(bars, bp, ma_period=10)
        nb = stt[-1]['n_bricks']
        ncu = sum(1 for s in stt if s['cross_up'])
        ncd = sum(1 for s in stt if s['cross_dn'])
        print(f"  brick {bp:>2}pt: {nb:>7,} tijolos no total | "
              f"{ncu+ncd:>5} cruzamentos de MA ({ncu} up / {ncd} dn) | "
              f"~{nb/252:.0f} tijolos/dia")
