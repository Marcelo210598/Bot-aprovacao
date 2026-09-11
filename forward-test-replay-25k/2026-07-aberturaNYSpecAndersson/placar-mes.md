# Placar — AberturaNYSpecAndersson (spec do Andersson, motor AberturaExplosao), JULHO/2026

> Continuação do teste de `2026-06-aberturaNYSpecAndersson/` (junho fechou em −$73,50, 22 dias,
> 11W/11L, nunca estourou o DD $1.000 mas também não bateu a meta $1.500). Mesma config, mesmo
> processo. Avaliação nova e independente (peso parte de $0).

## Config em teste (defaults do `src/AberturaNYSpecAndersson.cs`, sem alterar)
```
Contratos=6 | Abertura=09:30 ET | JanelaMonitoramento=60s | TicksParaEntrada=10
StopLoss=$250 | TakeProfit=$500
BE: Ativacao=$100 | Protege=$0 (breakeven) | Incremento=$50 (ratchet, so' sobe)
Instrumento: MNQ SEP26 | Tick Replay | Meta $1.500 / 30 dias corridos | DD real $1.000 (EOD)
```

## Registro dia a dia

| Dia | Direção | Saída | PnL dia | Acumulado | Pico | DD do pico | Obs |
|---|---|---|---|---|---|---|---|
| 01/07 | LONG | AbTrail | −$13,00 | −$13,00 | $0 | $13,00 | entrada 30225,46 → saída 30224,38 |
| 02/07 | SHORT | AbTrail | −$10,00 | −$23,00 | $0 | $23,00 | entrada 30084,38 → saída 30085,21 |
| 03/07 | LONG | AbTrail | **+$158,50** | +$135,50 | $135,50 | $0 | entrada 29926,63 → saída 29939,83 — **trade mais longo até agora** |
| 06/07 | SHORT | AbTrail | **+$248,50** | **+$384,00** | **$384,00** | $0 | entrada 29815,33 → saída 29794,63 — **pico do mês** |
| 07/07 | SHORT | AbStop | −$214,50 | +$169,50 | $384,00 | $214,50 | entrada 29574,08 → saída 29591,96 |
| 08/07 | LONG | AbTrail | +$157,00 | +$326,50 | $384,00 | $57,50 | entrada 29220,46 → saída 29233,54 |
| 09/07 | LONG | AbTrail | −$13,00 | +$313,50 | $384,00 | $70,50 | entrada 29737,92 → saída 29736,83 |
| 10/07 | LONG | AbStop | **−$372,50** | −$59,00 | $384,00 | $443,00 | entrada 29848,67 → saída 29817,63 — **slippage: stop $250 encheu −$372,50** |
| 13/07 | SHORT | AbTrail | −$8,00 | −$67,00 | $384,00 | $451,00 | entrada 29713,92 → saída 29714,58 |
| 14/07 | LONG | AbStop | −$285,50 | −$352,50 | $384,00 | $736,50 | entrada 29810,63 → saída 29786,83 |
| 15/07 | SHORT | AbTrail | −$12,50 | −$365,00 | $384,00 | $749,00 | entrada 29967,58 → saída 29968,63 |
| 16/07 | LONG | AbStop | −$9,50 | −$374,50 | $384,00 | **$758,50** | entrada 29485,13 → saída 29484,33 — pior ponto até agora |
| 17/07 | LONG | AbTrail | +$36,50 | −$338,00 | $384,00 | $722,00 | entrada 28613,21 → saída 28616,25 |
| 20/07 | LONG | AbTrail | −$14,00 | −$352,00 | $384,00 | $736,00 | entrada 29039,96 → saída 29038,79 |
| 21/07 | LONG | AbBe | −$14,00 | −$366,00 | $384,00 | $750,00 | entrada 29220,46 → saída 29219,29 |
| 22/07 | LONG | AbTrail | +$145,00 | −$221,00 | $384,00 | $605,00 | entrada 29100,96 → saída 29113,04 |
| 23/07 | SHORT | AbBe | −$13,00 | −$234,00 | $384,00 | $618,00 | entrada 28712,63 → saída 28713,71 |
| 24/07 | SHORT | AbBe | −$10,00 | −$244,00 | $384,00 | $628,00 | entrada 28539,00 → saída 28539,83 |
| 27/07 | LONG | AbBe | −$11,50 | −$255,50 | $384,00 | $639,50 | entrada 28584,25 → saída 28583,29 |
| 28/07 | SHORT | AbBe | −$14,00 | −$269,50 | $384,00 | $653,50 | entrada 27942,04 → saída 27943,21 |
| 29/07 | SHORT | AbTrail | +$40,50 | −$229,00 | $384,00 | $613,00 | entrada 27902,83 → saída 27899,46 |
| 30/07 | SHORT | AbStop | −$18,50 | −$247,50 | $384,00 | $631,50 | entrada 27861,29 → saída 27862,83 |
| 31/07 | LONG | AbTrail | −$19,50 | **−$267,00** | $384,00 | $651,00 | entrada 28557,96 → saída 28556,33 — **último pregão do mês** |

## 🏁 JULHO FECHADO — resumo final

| Métrica | Valor |
|---|---|
| Dias operados | **23** (todos os dias úteis de julho) |
| Vitórias / Derrotas | **6 / 17 (26% WR)** |
| Resultado final do mês | **−$267,00** |
| Pico do mês | $384,00 (dia 06/07, 25,6% da meta) |
| Pior ponto (DD máximo) | $758,50 (dia 16/07 — 75,9% do limite $1.000) |
| DD no fechamento | $651,00 (65,1% do limite) |
| Estourou o limite $1.000? | **Não** (nessa contagem por mês) |
| Bateu a meta $1.500? | **Não** |
| **Aprovaria a conta Apex 25K?** | **NÃO** |

⚠️ Ver análise completa (comitê multi-especialista) na conversa — inclui um achado crítico: a
**curva de patrimônio CONTÍNUA** (sem resetar a cada mês, como uma conta ao vivo real veria) tem
drawdown de **$1.162,50** do pico (dia 09/06) até o fundo (dia 16/07) — isso ESTOURARIA o
limite de $1.000 EOD numa conta real. O placar mês-a-mês (que reseta em $0) mascarou isso.

## 🚧 Próximo
Aguardando decisão sobre próximos passos após a análise do comitê.
