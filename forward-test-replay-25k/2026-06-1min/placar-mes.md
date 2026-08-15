# Placar acumulado — Junho/2026 (conta 25K) — MNQ **1 MINUTO** (re-teste)

Correção do teste original: o replay de junho foi rodado por engano no gráfico de **5 minutos**
(veredito antigo, incompleto, em `../2026-06/placar-mes.md`). Diagnóstico da revisão de 12/08
(`docs/revisao-estrategias-12-08.md`): 1min aprova ~44%/ano vs 5min ~26%/ano em backtest com
slippage — o mês precisa ser refeito no timeframe certo antes de julgar a estratégia.

Meta de aprovação: **+$1.500** realizado em **≥7 dias operados**, sem violar **DD $1.000 (EOD, trailing)**,
**dentro da janela de 30 dias corridos (01/06 → 30/06/2026)**.

## Config em teste (produção, sem alterar)
```
TP 60 | SL 12,5 | BE +3,75→+2,5 | Trail 1,75 | Tol 20 ticks | MaxDist 15pt
StopDiário $750 | MaxTrades 12 | Janela 9h30-16h ET | Flatten 16h55 ET
SegUsaDomingo=ON | OperarNoite=OFF | Meta $1.500 | MinDias 7 | DD real $1.000 (EOD)
```

## Estrutura
- `placar-mes.md` (este arquivo) — placar acumulado do mês, dia a dia
- `dia-XX-DD-MM.md` — detalhe de cada dia (trades, entrada/saída, motivo)

| Dia | Data | Trades (G/L) | PnL do dia | PnL acumulado | Pico (p/ DD EOD) | Drawdown atual | Dias operados |
|---|---|---|---|---|---|---|---|
| 1 | 01/06 (seg) | 6 (5G/1L) | +$101,5 | +$101,5 | $101,5 | $0 | 1/7 |
| 2 | 02/06 (ter) | 8 (7G/1L) | +$164,5 | +$266,0 | $266,0 | $0 | 2/7 |
| 3 | 03/06 (qua) | 7 (7G/0L) | +$243,0 | +$509,0 | $509,0 | $0 | 3/7 |
| 4 | 04/06 (qui) | 5 (3G/2L) | -$131,5 | +$377,5 | $509,0 | $131,5 | 4/7 |
| 5 | 05/06 (sex) | 0 | $0 | +$377,5 | $509,0 | $131,5 | 4/7 |
| 8 | 08/06 (seg) | 6 (3G/3L) | -$10,0 | +$367,5 | $509,0 | $141,5 | 5/7 |
| 9 | 09/06 (ter) | 2 (2G/0L) | +$91,0 | +$458,5 | $509,0 | $50,5 | 6/7 |
| 10 | 10/06 (qua) | 0 | $0 | +$458,5 | $509,0 | $50,5 | 6/7 |
| 11 | 11/06 (qui) | 5 (2G/3L) | -$81,5 | +$377,0 | $509,0 | $132,0 | 7/7 ✅ |
| 12 | 12/06 (sex) | 5 (1G/4L) | -$133,5 | +$243,5 | $509,0 | $265,5 | 8 |
| 15 | 15/06 (seg) | 0 | $0 | +$243,5 | $509,0 | $265,5 | 8 |
| 16 | 16/06 (ter) | 5 (2G/3L) | -$112,5 | +$131,0 | $509,0 | $378,0 | 9 |
| 17 | 17/06 (qua) | 5 (4G/1L) | +$16,0 | +$147,0 | $509,0 | $362,0 | 10 |
| 18 | 18/06 (qui) | 5 (4G/1L) | $0,00 | +$147,0 | $509,0 | $362,0 | 11 |
| 19 | 19/06 (sex) | 0 | $0 | +$147,0 | $509,0 | $362,0 | 11 |
| 22 | 22/06 (seg) | 2 (2G/0L) | +$67,5 | +$214,5 | $509,0 | $294,5 | 12 |
| 23 | 23/06 (ter) | 0 | $0 | +$214,5 | $509,0 | $294,5 | 12 |
| 24 | 24/06 (qua) | 3 (1G/2L) | **-$252,0** | **-$37,5** | $509,0 | **$546,5** | 13 |
| 25 | 25/06 (qui) | 1 (1G/0L) | +$111,5 | +$74,0 | $509,0 | $435,0 | 14 |
| 26 | 26/06 (sex) | 1 (0G/1L) | -$15,5 | +$58,5 | $509,0 | $450,5 | 15 |
| 29 | 29/06 (seg) | 7 (5G/2L) | +$109,5 | +$168,0 | $509,0 | $341,0 | 16 |
| 30 | 30/06 (ter) | 0 | $0 | +$168,0 | $509,0 | $341,0 | 16 |

## 📜 Histórico completo de trades

| # | Data | Hora ET | Sinal | Lado | Entrada | Saída | Pontos | PnL |
|---|---|---|---|---|---|---|---|---|
| 1 | 01/06 | 11:04 | NIV_L9 | LONG | 30300,70 | 30303,25 | +2,55 | +$59 |
| 2 | 01/06 | 14:33 | NIV_S10 | SHORT | 30581,10 | 30573,75 | +7,35 | +$72,5 |
| 3 | 01/06 | 16:36 | NIV_S11 | SHORT | 30590,50 | 30586,00 | +4,50 | +$39 |
| 4 | 01/06 | 16:37 | NIV_S12 | SHORT | 30587,75 | 30585,25 | +2,50 | +$27,5 |
| 5 | 01/06 | 16:38 | NIV_S13 | SHORT | 30586,50 | 30599,00 | **-12,50** | **-$122,5** |
| 6 | 01/06 | 16:41 | NIV_S14 | SHORT | 30594,60 | 30592,10 | +2,50 | +$26 |
| 7 | 02/06 | 12:54 | NIV_S15 | SHORT | 30686,20 | 30681,25 | +4,95 | +$52 |
| 8 | 02/06 | 12:55 | NIV_S16 | SHORT | 30687,00 | 30684,50 | +2,50 | +$20,5 |
| 9 | 02/06 | 12:56 | NIV_S17 | SHORT | 30689,00 | 30681,75 | +7,25 | +$57,5 |
| 10 | 02/06 | 12:58 | NIV_S18 | SHORT | 30688,75 | 30686,25 | +2,50 | +$30 |
| 11 | 02/06 | 13:02 | NIV_S19 | SHORT | 30683,25 | 30676,50 | +6,75 | +$51 |
| 12 | 02/06 | 13:06 | NIV_S20 | SHORT | 30687,60 | 30700,10 | **-12,50** | **-$129** |
| 13 | 02/06 | 13:16 | NIV_S21 | SHORT | 30691,25 | 30688,75 | +2,50 | +$45 |
| 14 | 02/06 | 13:53 | NIV_S22 | SHORT | 30678,75 | 30675,00 | +3,75 | +$37,5 |
| 15 | 03/06 | 10:35 | NIV_S19 | SHORT | 30709,25 | 30706,50 | +2,75 | +$46,5 |
| 16 | 03/06 | 10:42 | NIV_S20 | SHORT | 30718,00 | 30713,75 | +4,25 | +$50 |
| 17 | 03/06 | 11:31 | NIV_S21 | SHORT | 30715,15 | 30711,00 | +4,15 | +$38 |
| 18 | 03/06 | 11:32 | NIV_S22 | SHORT | 30717,35 | 30711,25 | +6,10 | +$66 |
| 19 | 03/06 | 11:33 | NIV_S23 | SHORT | 30716,45 | 30713,95 | +2,50 | +$4 |
| 20 | 03/06 | 11:34 | NIV_S24 | SHORT | 30718,85 | 30716,35 | +2,50 | +$18,5 |
| 21 | 03/06 | 11:35 | NIV_S25 | SHORT | 30707,55 | 30704,25 | +3,30 | +$20 |
| 22 | 04/06 | 14:12 | NIV_L30 | LONG | 30500,40 | 30487,90 | **-12,50** | **-$124** |
| 23 | 04/06 | 14:26 | NIV_L31 | LONG | 30504,75 | 30507,75 | +3,00 | +$40 |
| 24 | 04/06 | 16:56 | NIV_L32 | LONG | 30497,10 | 30500,75 | +3,65 | +$39 |
| 25 | 04/06 | 16:58 | NIV_L33 | LONG | 30494,05 | 30498,25 | +4,20 | +$44,5 |
| 26 | 04/06 | 16:59 | NIV_L34 | LONG | 30499,00 | 30486,50 | **-12,50** | **-$131** |
| 27 | 08/06 | 11:37 | NIV_S1 | SHORT | 29593,25 | 29588,50 | +4,75 | +$44,5 |
| 28 | 08/06 | 11:41 | NIV_S2 | SHORT | 29590,65 | 29586,00 | +4,65 | +$30 |
| 29 | 08/06 | 12:32 | NIV_S3 | SHORT | 29594,95 | 29591,25 | — *(ver nota)* | **-$3** |
| 30 | 08/06 | 12:59 | NIV_S4 | SHORT | 29598,45 | 29595,95 | — *(ver nota)* | **-$5,5** |
| 31 | 08/06 | 13:01 | NIV_S5 | SHORT | 29595,95 | 29590,50 | +5,45 | +$54,5 |
| 32 | 08/06 | 13:11 | NIV_S6 | SHORT | 29598,20 | 29610,70 | **-12,50** | **-$130,5** |

*Trades 29 e 30: PnL confirmado via `[MeuTrade]` (sync real com TraderOS) — a matemática simples de
pontos sugeriria pequeno ganho, mas o PnL real fechou levemente negativo nos dois, ver ressalva em
`dia-08-08-06.md`.*

| 33 | 09/06 | 10:30 | NIV_S13 | SHORT | 29737,25 | 29696,00 | — *(ver nota)* | +$54 |
| 34 | 09/06 | 10:55 | NIV_S14 | SHORT | 29731,20 | 29726,25 | +4,95 | +$37 |
| 35 | 11/06 | 14:34 | NIV_S15 | SHORT | 29248,05 | 29244,00 | — *(ver nota)* | **-$11,5** |
| 36 | 11/06 | 15:18 | NIV_S16 | SHORT | 29237,20 | 29234,70 | +2,50 | +$18,5 |
| 37 | 11/06 | 15:19 | NIV_S17 | SHORT | 29237,30 | 29234,80 | — *(ver nota)* | **-$7,5** |
| 38 | 11/06 | 15:47 | NIV_S18 | SHORT | 29247,10 | 29243,50 | +3,60 | +$24 |
| 39 | 11/06 | 15:56 | NIV_S19 | SHORT | 29234,25 | 29246,75 | **-12,50** | **-$105** |

*Trade 33: diferença de preço no texto (41,25pt) incompatível com o PnL de $54 — provável erro de
leitura do print, ver `dia-09-09-06.md`. Trades 35 e 37: mesma ressalva dos trades 29/30 (PnL real
via `[MeuTrade]` não bate com a matemática simples de pontos).*

**Subtotal até o dia 11: +$377,0 — 39 trades, 29 gain, 10 loss (WR 74,4%). Pico $509,0, drawdown atual $132,0.**

| 40 | 12/06 | 11:13 | NIV_S20 | SHORT | 29547,65 | 29542,00 | — *(ver nota)* | **-$8** |
| 41 | 12/06 | 11:14 | NIV_S21 | SHORT | 29527,45 | 29539,95 | **-12,50** | **-$115** |
| 42 | 12/06 | 11:22 | NIV_S22 | SHORT | 29546,15 | 29539,00 | — *(ver nota)* | **-$24** |
| 43 | 12/06 | 11:26 | NIV_S23 | SHORT | 29543,85 | 29538,50 | — *(ver nota)* | **-$8** |
| 44 | 12/06 | 11:27 | NIV_S24 | SHORT | 29528,15 | 29525,65 | +2,50 | +$21,5 |

*Trades 40, 42, 43: mesma ressalva recorrente — PnL real via `[MeuTrade]` não bate com a
matemática simples de pontos do texto. Terceiro dia seguido (08, 11, 12/06) com esse padrão —
virou item de investigação em `progress.md`.*

| 45 | 16/06 | 11:32 | NIV_L11 | LONG | 30315,15 | 30302,65 | **-12,50** | **-$141** |
| 46 | 16/06 | 11:33 | NIV_L12 | LONG | 30312,20 | 30315,50 | — *(ver nota)* | **-$6,5** |
| 47 | 16/06 | 11:34 | NIV_L13 | LONG | 30316,65 | 30322,00 | +5,35 | +$19 |
| 48 | 16/06 | 11:36 | NIV_L14 | LONG | 30317,95 | 30322,25 | — *(ver nota)* | **-$13,5** |
| 49 | 16/06 | 11:58 | NIV_L15 | LONG | 30312,95 | 30319,00 | +6,05 | +$29,5 |

| 50 | 17/06 | 11:48 | NIV_L7 | LONG | 30038,70 | 30041,20 | +2,50 | +$13,5 |
| 51 | 17/06 | 15:02 | NIV_L8 | LONG | 30020,10 | 30024,75 | +4,65 | +$30 |
| 52 | 17/06 | 15:16 | NIV_L9 | LONG | 30020,15 | 30026,75 | — *(ver nota)* | **-$51** |
| 53 | 17/06 | 15:19 | NIV_L10 | LONG | 30012,65 | 30016,25 | +3,60 | +$16,5 |
| 54 | 17/06 | 15:20 | NIV_L11 | LONG | 30018,60 | 30021,10 | +2,50 | +$7 |

*(A partir do dia 18/06: contrato trocado pra **MNQ SEP26**, JUN26 vencia 19/06.)*

| 55 | 18/06 | 11:11 | NIV_S10 | SHORT | 30540,35 | 30537,50 | +2,85 | +$34 |
| 56 | 18/06 | 11:14 | NIV_S11 | SHORT | 30535,45 | 30532,25 | +3,20 | +$33,5 |
| 57 | 18/06 | 11:36 | NIV_S12 | SHORT | 30530,25 | 30527,50 | +2,75 | +$36,5 |
| 58 | 18/06 | 12:40 | NIV_S13 | SHORT | 30542,90 | 30540,40 | +2,50 | +$30,5 |
| 59 | 18/06 | 12:41 | NIV_S14 | SHORT | 30536,85 | 30549,35 | **-12,50** | **-$134,5** |

**Subtotal até o dia 18: +$147,0 — 59 trades, 40 gain, 19 loss (WR 67,8%). Pico $509,0, drawdown atual $362,0.**

*(19/06: sem operação. 20-21/06: fim de semana.)*

| 60 | 22/06 | 10:37 | NIV_S7 | SHORT | 30861,00 | 30858,50 | +2,50 | +$18,5 |
| 61 | 22/06 | 10:48 | NIV_S8 | SHORT | 30872,50 | 30868,50 | +4,00 | +$49 |

*(23/06: sem operação.)*

| 62 | 24/06 | 10:49 | NIV_L3 | LONG | 29589,90 | 29596,50 | +6,60 | +$33 |
| 63 | 24/06 | 11:20 | NIV_L4 | LONG | 29581,90 | 29569,40 | **-12,50** | **-$126** |
| 64 | 24/06 | 14:11 | NIV_L5 | LONG | 29585,50 | 29573,00 | **-12,50** | **-$159** |

**Subtotal até o dia 24: -$37,5 — 64 trades, 43 gain, 21 loss (WR 67,2%). Pico $509,0, drawdown atual $546,5.**

| 65 | 25/06 | 10:42 | NIV_S6 | SHORT | 29904,90 | 29898,75 | +6,15 | +$111,5 |
| 66 | 26/06 | 10:47 | NIV_L7 | LONG | 29313,60 | 29316,25 | — *(ver nota)* | **-$15,5** |
| 67 | 29/06 | 10:35 | NIV_S3 | SHORT | 29757,80 | 29755,25 | +2,55 | +$34,5 |
| 68 | 29/06 | 10:43 | NIV_S4 | SHORT | 29755,95 | 29753,00 | +2,95 | +$62 |
| 69 | 29/06 | 10:50 | NIV_S5 | SHORT | 29762,45 | 29757,75 | +4,70 | +$168 |
| 70 | 29/06 | 10:55 | NIV_S6 | SHORT | 29760,30 | 29772,80 | **-12,50** | **-$111** |
| 71 | 29/06 | 12:33 | NIV_S7 | SHORT | 29769,40 | 29766,50 | +2,90 | +$31 |
| 72 | 29/06 | 12:35 | NIV_S8 | SHORT | 29764,00 | 29758,25 | +5,75 | +$50,5 |
| 73 | 29/06 | 12:37 | NIV_S9 | SHORT | 29771,35 | 29783,85 | **-12,50** | **-$125,5** |

**TOTAL FINAL DO MÊS: +$168,0 — 73 trades, 49 gain, 24 loss (WR 67,1%). Pico $509,0, drawdown máximo atingido $546,5.**

---

## 🏁 VEREDITO FINAL DO MÊS — Junho/2026, MNQ 1min (janela 01/06 → 30/06, FECHADA)

- **Resultado: MÊS INCOMPLETO** — nem aprovou, nem estourou. Mesmo veredito textual do teste 5min
  original, mas com números bem diferentes por trás.
- **PnL final:** +$168,0 de $1.500 (**11,2%** da meta)
- **Drawdown máximo atingido:** $546,5 de $1.000 (**54,6%**, no dia 24) — não chegou a estourar,
  mas passou de metade do limite, bem mais perto do risco do que o teste 5min original chegou a
  ficar (que tinha atingido no máximo 29,9%)
- **Dias operados:** 16 de 7 mínimos — gate de dias nunca foi o problema
- **Trades:** 73 no total, **49 gain / 24 loss (WR 67,1%)**
- **21 pregões cobertos no mês** (todos os dias úteis) — **16 com trade, 5 zerados** (05, 10, 15,
  19, 23/06 — bem menos dias zerados que os 12 do teste 5min original, confirma que o filtro
  anti-chase realmente barrava demais em 5min)

## 📐 Comparação final: 1min real vs. 5min real vs. backtest

| | PnL do mês | Trades | WR | Drawdown máx. |
|---|---|---|---|---|
| Backtest 1min (projeção, dado parcial ~6-11 dias) | +$1.240 (11 dias) | — | 67,4% (validado) | — |
| Forward test **5min** real (original, mês inteiro) | +$170,5 | 25 | 76% | 29,9% ($298,5) |
| **Forward test 1min real (este teste, mês inteiro)** | **+$168,0** | **73** | **67,1%** | **54,6% ($546,5)** |

**Essa é a virada mais importante do re-teste inteiro: no fechamento do mês, o 1min real (+$168,0)
terminou practicamente EMPATADO com o 5min real (+$170,5)** — não superou como o esperado nos
primeiros dias (chegou a bater 377 vs 206 no dia 11). O 1min gerou quase 3x mais trades (73 vs 25) e
menos dias zerados, confirmando que o filtro anti-chase realmente causava menos operação no 5min —
mas o volume extra de trades não se traduziu em mais lucro, e o **drawdown máximo quase dobrou**
(54,6% vs 29,9%) por causa de mais stops cheios de -12,50pt.

**Conclusão honesta:** o diagnóstico "era só o timeframe" **não se confirmou** na prática. O 1min
opera mais e captura mais sinais que o backtest previa, mas os stops cheios (`-12,50pt`, ~15 deles
ao longo do mês) pesaram tanto quanto os ganhos. Isso bate com o cenário que o Marcelo definiu em
12/08: **"se o resultado negativo persistir mesmo no 1min, vamos ter que repensar tudo."** O
resultado não ficou tecnicamente negativo no fim (fechou +$168), mas ficou empatado com o 5min que
já tinha sido descartado — não há mais base pra dizer que o 1min resolve o problema sozinho.

**Não implementar nada em produção com esse resultado.** Próximo passo é decisão do Marcelo: (a)
investigar o padrão de stops cheios / trava de lucro por horário (`docs/melhorias-sugeridas.md`
#12) por backtest antes de qualquer mudança, (b) retomar o funil de estratégias novas (adiado em
12/08), ou (c) outra direção. Ver `docs/melhorias-sugeridas.md` e `progress.md` pro estado
consolidado.

---

## 🔴 COMPARAÇÃO COM O BACKTEST — piorou, agora é NEGATIVO (atualizado 13/08, dia 24)

*(Nota: esta seção foi escrita no meio do teste, no dia 24 — o mês fechou depois disso. Ver o
**🏁 VEREDITO FINAL DO MÊS**, mais abaixo, pro resultado consolidado e a comparação final.)*

A revisão de 12/08 (`docs/revisao-estrategias-12-08.md`) projetou, pro **mesmo período 01/06 →
11/06/2026**: backtest 1min = **+$1.240** em 6 dias operados. Era esse número que devia "confirmar
o diagnóstico" de que o 5min era o problema.

| Checkpoint | PnL acumulado | % do projetado ($1.240) |
|---|---|---|
| Backtest 1min (projeção, 01-11/06) | **+$1.240** | 100% |
| Forward test 5min real (original, mesmo período) | +$206 | 16,6% |
| 1min real — dia 11 | +$377,0 | 30,4% |
| 1min real — dia 16 | +$131,0 | 10,6% |
| 1min real — dia 18 | +$147,0 | 11,9% |
| **1min real — dia 24 (hoje)** | **-$37,5** | **negativo** |

**Isso já não é mais "sinal de alerta", é confirmação de descolamento real.** O acumulado virou
**negativo** depois do dia 24 (-$252,0 nesse único dia, o pior do teste inteiro — 1 gain, 2 losses
cheias de -12,50pt cada). Drawdown EOD saltou pra **$546,5 de $1.000 (54,6%)** — mais da metade do
limite, ainda sem estourar mas numa trajetória que preocupa de verdade.

O 1min real segue melhor que o 5min real no mesmo trecho inicial (377 vs 206 até o dia 11), mas o
mês como um todo está muito longe dos $1.240 projetados — e piorando, não estabilizando. 13 dias
operados de ~20-22 esperados no mês inteiro; ainda falta terminar, mas esse é exatamente o cenário
que o Marcelo avisou em 12/08 que dispararia o "repensar tudo". Vale decidir se compensa fechar o
mês inteiro antes de discutir isso ou já parar pra analisar agora.

## Como isso vira "aprovado ou não" no fim do mês

- **Aprovada** se: PnL acumulado ≥ $1.500 **E** dias operados ≥ 7 **E** nunca violou o DD $1.000 (EOD)
- **Estourada (bust)** se: em algum dia o drawdown (pico − saldo do dia) ultrapassar $1.000
- Comparar com o esperado da revisão de 12/08: ~$1.240 pros primeiros 11 dias de junho, no backtest 1min com slippage.

*(Atualizar esta tabela a cada dia novo — adicionar linha, recalcular acumulado/pico/drawdown.)*
