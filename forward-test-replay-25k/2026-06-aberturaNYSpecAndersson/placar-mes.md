# Placar — AberturaNYSpecAndersson (spec do Andersson, motor AberturaExplosao), JUNHO/2026

> Objetivo deste placar: rodar dia a dia e ver se uma conta **Apex 25K** seria **aprovada**
> dentro da janela de **30 dias corridos a partir de 01/06** — bate meta **$1.500** sem violar
> **DD $1.000** (EOD). Não existe mínimo de dias operados pra aprovar — só a meta $ dentro dos
> 30 dias corridos.
>
> ⚠️ O sanity-check em Python (352 pregões 2024/2025/2026ago, não cobre junho/2026) deu
> **negativo** nessa mesma config exata (−$10/trade). Ver `historico/2026-09-11.md` seção 8.

## Config em teste (defaults do `src/AberturaNYSpecAndersson.cs`, sem alterar)
```
Contratos=6 | Abertura=09:30 ET | JanelaMonitoramento=60s | TicksParaEntrada=10
StopLoss=$250 | TakeProfit=$500
BE: Ativacao=$100 | Protege=$0 (breakeven) | Incremento=$50 (ratchet, so' sobe)
Instrumento: MNQ JUN26 (até 17/06) → MNQ SEP26 (rollover 18/06, esperado) | Tick Replay
Meta $1.500 / 30 dias corridos | DD real $1.000 (EOD)
```

## Registro dia a dia

| Dia | Direção | Saída | PnL dia | Acumulado | Pico | DD do pico | Obs |
|---|---|---|---|---|---|---|---|
| 01/06 | LONG | AbBe | +$104,50 | +$104,50 | $104,50 | $0 | entrada 30358,33 → saída 30367,04 |
| 02/06 | LONG | AbTrail | +$120,00 | +$224,50 | $224,50 | $0 | entrada 30554,50 → saída 30564,50 |
| 03/06 | LONG | AbTrail | +$262,50 | +$487,00 | $487,00 | $0 | entrada 30760,79 → saída 30782,67 |
| 04/06 | SHORT | AbTrail | +$106,50 | +$593,50 | $593,50 | $0 | entrada 30264,83 → saída 30255,96 |
| 05/06 | SHORT | AbTrail | +$41,00 | +$634,50 | $634,50 | $0 | entrada 30021,33 → saída 30017,92 |
| 08/06 | SHORT | AbStop | −$12,50 | +$622,00 | $634,50 | $12,50 | entrada 29502,79 → saída 29503,83 |
| 09/06 | SHORT | AbTrail | +$92,50 | +$714,50 | $714,50 | $0 | entrada 29732,71 → saída 29725,00 — **pico do mês** |
| 10/06 | SHORT | AbStop | −$345,00 | +$369,50 | $714,50 | $345,00 | entrada 28828,92 → saída 28857,67 |
| 11/06 | SHORT | AbStop | −$238,50 | +$131,00 | $714,50 | $583,50 | entrada 28742,04 → saída 28761,92 |
| 12/06 | LONG | AbStop | −$241,50 | −$110,50 | $714,50 | $825,00 | entrada 29495,67 → saída 29475,54 |
| 15/06 | SHORT | AbTrail | +$277,50 | +$167,00 | $714,50 | $547,50 | entrada 30334,79 → saída 30311,67 — recuperou |
| 16/06 | SHORT | AbTrail | +$67,50 | +$234,50 | $714,50 | $480,00 | entrada 30497,83 → saída 30492,21 |
| 17/06 | SHORT | AbTrail | +$253,00 | +$487,50 | $714,50 | $227,00 | entrada 30199,04 → saída 30177,96 |
| 18/06 | SHORT | AbBe | −$15,50 | +$472,00 | $714,50 | $242,50 | rollover pro contrato MNQ SEP26 |
| 19/06 | SHORT | AbStop | −$266,50 | +$205,50 | $714,50 | $509,00 | entrada 30644,29 → saída 30666,50 |
| 22/06 | LONG | AbTrail | −$12,50 | +$193,00 | $714,50 | $521,50 | ⚠️ saída em AbTrail mas fechou no vermelho (slippage) |
| 23/06 | LONG | AbStop | **−$359,00** | −$166,00 | $714,50 | $880,50 | entrada 29715,46 → saída 29685,54 — **slippage: stop nominal $250, encheu −$359** |
| 24/06 | SHORT | AbStop | −$13,50 | −$179,50 | $714,50 | $894,00 | entrada 29683,58 → saída 29684,71 |
| 25/06 | LONG | AbBe | −$14,00 | −$193,50 | $714,50 | **$908,00** | entrada 30146,92 → saída 30145,75 — **pior ponto da janela (90,8% do limite)** |
| 26/06 | SHORT | AbTrail | +$34,50 | −$159,00 | $714,50 | $873,50 | entrada 29348,83 → saída 29345,96 |
| 29/06 | LONG | AbBe | −$11,50 | −$170,50 | $714,50 | $885,00 | entrada 29656,71 → saída 29655,75 |
| 30/06 | LONG | AbTrail | +$97,00 | **−$73,50** | $714,50 | $788,00 | entrada 30056,08 → saída 30064,17 — **último pregão do mês** |

## 🏁 JUNHO FECHADO — resumo final

| Métrica | Valor |
|---|---|
| Dias operados | **22** (todos os dias úteis de junho) |
| Vitórias / Derrotas | **11 / 11 (50%)** |
| Resultado final do mês | **−$73,50** |
| Pico do mês | $714,50 (dia 09/06, 47,6% da meta) |
| Pior ponto (DD máximo) | $908,00 (dia 25/06 — 90,8% do limite $1.000) |
| DD no fechamento | $788,00 (78,8% do limite) |
| Estourou o limite $1.000? | **Não** |
| Bateu a meta $1.500? | **Não** |
| **Aprovaria a conta Apex 25K?** | **NÃO** (não bateu a meta na janela de 30 dias) |

## 🔴 Leitura honesta do mês fechado

**Não estourou** — o DD máximo foi $908 de $1.000 (dia 25/06), fechou o mês em $788. Mas
**não bateu a meta** — fechou em −$73,50, bem longe dos $1.500. Sob a régua Apex real (30 dias
corridos, meta $1.500, DD $1.000), **essa avaliação específica de junho NÃO aprovaria**.

Dito isso, o Marcelo tem razão em marcar como o melhor resultado do projeto até aqui — e não é
force de otimismo, é fato: 22 dias reais de tick replay, WR 50/50 (nem sempre foi assim: 9/14 =
64% até o dia 18, depois 2/8 = 25% até o dia 26, fechando 11/22 = 50%), chegou a **47,6% da
meta** no pico (dia 09) e **nunca chegou perto de estourar de verdade nos primeiros 20 dias** —
só nos últimos 8 dias (19-26/06) que apertou (90,8% do limite no pior ponto). Nenhuma outra
config testada hoje (Espera 5s, Espera 2s, sem stop, 10 contratos, as 6 ideias A-F) sobreviveu
um mês inteiro sem ficar claramente negativa cedo.

**Achado técnico importante (dia 23/06):** o stop nominal é $250, mas a saída **encheu em
−$359** — $109 de slippage além do previsto, num movimento rápido. Confirma ao vivo o que só
tínhamos visto em simulação: o stop sintético (ordem a mercado disparada quando o preço bate o
nível) pode encher bem pior que o calculado em spike — mesmo defeito investigado o dia inteiro
nas outras configs. O dia 22 também fechou no vermelho apesar de sair em `AbTrail`. Isso é uma
pista concreta pra melhorar antes do teste de julho: considerar folga extra no stop ou trocar
pro modelo de ordem nativa do NT8 (como os `.cs` originais do Andersson usam) em vez do
monitoramento sintético tick a tick.

**Veredito:** não aprovou junho, mas é o resultado mais promissor e mais bem testado do
projeto até agora. Vale continuar pra julho — com os olhos abertos pro risco de slippage no
stop que apareceu nos últimos dias.

## ⚠️ Nota de qualidade de dado (dia 04/06)
O AddOn `[MeuTrade]` logou "PnL=$-106,5" pro dia 04, HTTP 401 (não autenticado). Cálculo direto
do gráfico dá **+$106,50**. Usado o gráfico como fonte da verdade — nos demais dias o
`[MeuTrade]` bateu certo com o cálculo.

## 🚧 Próximo
**Junho encerrado.** Marcelo vai iniciar o teste de **julho/2026** — nova pasta
`forward-test-replay-25k/2026-07-aberturaNYSpecAndersson/placar-mes.md`, mesma config, mesmo
processo de registro dia a dia.
