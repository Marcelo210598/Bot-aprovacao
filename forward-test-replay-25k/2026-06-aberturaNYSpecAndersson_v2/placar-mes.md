# Placar — AberturaNYSpecAndersson_v2 (4 contratos / stop $150 / BE 60-0-30), JUNHO/2026

> Mesmos 22 dias que o V1 (`../2026-06-aberturaNYSpecAndersson/`), pra comparação pareada dia a
> dia. Config: Contratos=4, StopLoss=$150, TakeProfit=$500, BE ativa=$60/protege=$0/
> incremento=$30. MNQ JUN26→SEP26 (rollover 18/06, igual V1), Tick Replay.

## Registro dia a dia — V2 completo (22 dias)

| Dia | Saída V2 | PnL V2 | Acumulado V2 | Pico V2 | DD do pico V2 |
|---|---|---|---|---|---|
| 01/06 | AbBe | +$70,50 | +$70,50 | $70,50 | $0 |
| 02/06 | AbTrail | +$80,00 | +$150,50 | $150,50 | $0 |
| 03/06 | AbTrail | +$176,00 | +$326,50 | $326,50 | $0 |
| 04/06 | AbTrail | +$71,50 | +$398,00 | $398,00 | $0 |
| 05/06 | AbTrail | +$28,00 | +$426,00 | $426,00 | $0 |
| 08/06 | AbStop | −$7,50 | +$418,50 | $426,00 | $7,50 |
| 09/06 | AbTrail | +$115,00 | +$533,50 | $533,50 | $0 |
| 10/06 | AbStop | −$9,00 | +$524,50 | $533,50 | $9,00 |
| 11/06 | AbBe | −$5,50 | +$519,00 | $533,50 | $14,50 |
| 12/06 | AbStop | −$160,50 | +$358,50 | $533,50 | $175,00 |
| 15/06 | AbTrail | +$185,50 | +$544,00 | $544,00 | $0 |
| 16/06 | AbTrail | +$45,50 | +$589,50 | $589,50 | $0 |
| 17/06 | AbTrail | +$149,00 | +$738,50 | $738,50 | $0 |
| 18/06 | AbTrail | −$10,00 | +$728,50 | $738,50 | $10,00 |
| 19/06 | AbStop | −$162,00 | +$566,50 | $738,50 | $172,00 |
| 22/06 | AbTrail | −$7,50 | +$559,00 | $738,50 | $179,50 |
| 23/06 | **AbStop** | **−$239,00** | +$320,00 | $738,50 | $418,50 |
| 24/06 | AbStop | −$8,50 | +$311,50 | $738,50 | $427,00 |
| 25/06 | AbBe | −$9,00 | +$302,50 | $738,50 | **$436,00** |
| 26/06 | AbTrail | +$23,50 | +$326,00 | $738,50 | $412,50 |
| 29/06 | AbBe | −$7,50 | +$318,50 | $738,50 | $420,00 |
| 30/06 | AbTrail | +$66,00 | **+$384,50** | $738,50 | $354,00 |

## 🆚 Comparativo completo V1 x V2 — junho fechado, mesmos 22 dias

| Métrica | V1 (6c / stop $250) | V2 (4c / stop $150) |
|---|---|---|
| Resultado do mês | **−$73,50** | **+$384,50** |
| Vitórias / Derrotas | 11 / 11 (50%) | 11 / 11 (50%) — **mesmo padrão dia a dia**, nenhum dia mudou de sinal |
| Profit Factor | 0,95 | **1,61** |
| Gross Profit | $1.456,50 | $1.010,50 |
| Gross Loss | $1.530,00 | $626,00 |
| Pico do mês | $714,50 (dia 09) | $738,50 (dia 17) |
| **DD máximo** | **$908,00 (90,8% do limite)** | **$436,00 (43,6% do limite)** |
| Aprovaria a conta? | Não (não bateu meta) | Não (não bateu meta, mas fechou no verde e com DD confortável) |

## 🎯 Análise

**O que os dados mostram:** V2 tem EXATAMENTE o mesmo padrão de vitória/derrota que V1 em todos
os 22 dias — a entrada (sinal) não mudou em nenhum dia. A diferença inteira está em quanto cada
vitória/derrota vale em $. Os ganhos do V2 encolheram proporcionalmente ao tamanho (4/6 = 66,7%
do V1, bate certinho: dia 03 V1 +$262,50 → V2 +$176,00 = 67,1%). **As perdas encolheram MUITO
mais que isso** — dia 10: V1 −$345,00 → V2 apenas −$9,00 (2,6%, não 66,7%); dia 11: V1 −$238,50
→ V2 −$5,50 (2,3%). O stop mais apertado + BE mais baixo está limitando o pior caso bem além do
que só reduzir o tamanho explicaria.

**Hipótese:** o BE ativando em $60 (em vez de $100) consegue armar proteção num movimento menor
a favor, ANTES do preço reverter — convertendo vários trades que no V1 iam até o stop cheio em
saídas quase de graça no V2. Isso é o mecanismo funcionando como desenhado, não coincidência de
calendário (mesmos sinais, mesmos dias).

**⚠️ MAS — dia 23/06 é o contraponto que confirma o risco que eu já tinha avisado:** o V2 tomou
um stop de **−$239,00 num stop nominal de $150** (59% pior — "acima do nosso stop estipulado",
como você mesmo notou). Curiosamente esse valor bate quase exatamente com o V1 ESCALADO pra 4
contratos (V1 −$359 × 4/6 = −$239,3). **Nesse dia específico, o movimento foi tão violento que
o stop menor NÃO protegeu proporcionalmente mais** — a hipótese de que "stop menor = risco
proporcionalmente menor" falhou justo no pior dia do mês. Isso não invalida o resultado geral
(10 dos 11 dias de derrota tiveram proteção muito melhor que a linear), mas mostra que em
spikes muito fortes o problema de execução (slippage do stop sintético) continua existindo —
é a mesma limitação que identifiquei ontem, ainda não resolvida (ordem nativa vs sintética).

**Números finais:** Profit Factor foi de **0,95 (V1, abaixo de 1 = não lucrativo) pra 1,61 (V2,
lucrativo)**. Drawdown máximo caiu de 90,8% do limite pra 43,6% — bem mais que a redução linear
de tamanho (4/6=66,7%) explicaria sozinha.

## ⚠️ Ressalva de robustez (advogado do diabo)

Só 1 mês (22 dias), mesmos sinais de entrada em ambas as configs (não é uma validação
independente — é a MESMA sequência de sinais gerenciada diferente). O resultado É promissor e
tem explicação estrutural clara (BE mais baixo protege mais cedo), não é coincidência de
calendário como os padrões de dia-da-semana que descartamos ontem. Mas **1 mês não é suficiente
pra declarar vitória** — precisa repetir em julho (mesmos dias que já temos do V1) antes de
confiar de verdade. E o achado do dia 23 mostra que o risco de slippage no stop sintético
continua sem solução — meu experimento recomendado (trocar pra ordem STOP nativa do NT8) segue
valendo, inclusive mais ainda agora que vimos outro caso concreto de slippage no V2.

## 🚧 Próximo
Rodar V2 em julho (mesmos dias 01-31/07 que já temos do V1) pra confirmar se o padrão se repete
fora de junho.
