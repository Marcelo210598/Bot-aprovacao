# Placar — AberturaNYSpecAndersson_v2 (4 contratos / stop $150 / BE 60-0-30), JULHO/2026

> Mesmos 23 dias que o V1 (`../2026-07-aberturaNYSpecAndersson/`), comparação pareada.
> Avaliação nova e independente de julho (parte de $0, igual o V1).

## Registro dia a dia — V2 completo (23 dias)

| Dia | PnL V2 | Acumulado V2 | Pico V2 | DD do pico V2 |
|---|---|---|---|---|
| 01/07 | −$8,00 | −$8,00 | $0 | $8,00 |
| 02/07 | −$8,50 | −$16,50 | $0 | $16,50 |
| 03/07 | +$116,00 | +$99,50 | $99,50 | $0 |
| 06/07 | **−$14,50** | +$85,00 | $99,50 | $14,50 |
| 07/07 | −$6,50 | +$78,50 | $99,50 | $21,00 |
| 08/07 | +$213,50 | +$292,00 | $292,00 | $0 |
| 09/07 | −$8,00 | +$284,00 | $292,00 | $8,00 |
| 10/07 | **−$247,50** | +$36,50 | $292,00 | $255,50 |
| 13/07 | −$4,00 | +$32,50 | $292,00 | $259,50 |
| 14/07 | **−$189,50** | −$157,00 | $292,00 | $449,00 |
| 15/07 | −$7,50 | −$164,50 | $292,00 | $456,50 |
| 16/07 | −$5,50 | −$170,00 | $292,00 | **$462,00** |
| 17/07 | +$141,00 | −$29,00 | $292,00 | $321,00 |
| 20/07 | −$9,00 | −$38,00 | $292,00 | $330,00 |
| 21/07 | −$8,50 | −$46,50 | $292,00 | $338,50 |
| 22/07 | +$97,00 | +$50,50 | $292,00 | $241,50 |
| 23/07 | −$8,00 | +$42,50 | $292,00 | $249,50 |
| 24/07 | −$6,00 | +$36,50 | $292,00 | $255,50 |
| 27/07 | −$7,50 | +$29,00 | $292,00 | $263,00 |
| 28/07 | −$9,00 | +$20,00 | $292,00 | $272,00 |
| 29/07 | +$27,50 | +$47,50 | $292,00 | $244,50 |
| 30/07 | −$11,50 | +$36,00 | $292,00 | $256,00 |
| 31/07 | −$12,50 | **+$23,50** | $292,00 | $268,50 |

## 🏁 JULHO FECHADO — V2

23 dias, **5W/18L (21,7%)**, resultado **+$23,50** (quase zero, mas positivo). Pico $292,00
(dia 08). DD máximo $462,00 (46,2% do limite). Não estourou.

## 🆚 Comparativo completo V1 x V2 — julho, mesmos 23 dias

| Métrica | V1 (6c / $250) | V2 (4c / $150) |
|---|---|---|
| Resultado do mês | −$267,00 | **+$23,50** |
| Vitórias/Derrotas | 6/17 (26%) | 5/18 (22%) |
| Profit Factor | 0,75 | **1,04** (quase empate) |
| DD máximo | $758,50 (75,9%) | **$462,00 (46,2%)** |

## ⚠️ O PRIMEIRO caso onde V2 tem DESVANTAGEM — dia 06/07

Em todos os outros 44 dias (jun+jul), V1 e V2 bateram no MESMO sinal (mesmo win/loss). **Dia
06/07 é a única exceção:** V1 ganhou **+$248,50** (um dos maiores trades do projeto — deixou o
trade correr até o trailing render bem); V2 perdeu **−$14,50** (saiu em `AbBe`, travou cedo
demais). Isso é o **custo real** do BE mais agressivo: ele protege nos dias ruins (várias vezes
em junho), mas em compensação corta ALGUNS dias muito bons antes deles decolarem. Nenhum
almoço grátis — é o trade-off estrutural do desenho, não um bug.

## 🔴 Mais 2 casos de slippage além do stop nominal $150

- **10/07:** stop nominal $150 → encheu em **−$247,50** (65% pior) — "mais um stop acima",
  como você notou.
- **14/07:** stop nominal $150 → encheu em **−$189,50** (26% pior).

Confirma pela terceira vez (depois de 23/06) que o problema de execução do stop sintético
continua sem solução — independente do tamanho do stop.

## 📊 TOTAL COMBINADO — jun+jul, V1 x V2 (45 dias)

| Métrica | V1 | V2 |
|---|---|---|
| Resultado total | −$340,50 | **+$408,00** |
| Profit Factor | 0,87 | **1,34** |
| Win Rate | 37,8% (17/45) | 35,6% (16/45) — **menor**, e ainda assim mais lucrativo |
| Avg Winner | $131,91 | $100,34 |
| Avg Loser | $92,25 | **$41,29** |
| Payoff Ratio | 1,43 | **2,43** |
| **DD máximo (curva contínua, sem reset mensal)** | **$1.162,50 — ESTOUROU o limite $1.000** | **$524,00 — 52,4% do limite, NÃO estoura** |

## 🎯 Análise final (comitê)

**O que os dados mostram:** V2 vence em praticamente todas as métricas que importam — mais
lucro total, Profit Factor muito melhor (1,34 vs 0,87), perdas médias MENOS DA METADE (41,29
vs 92,25), payoff ratio quase 2x melhor. E o achado mais importante: **rodando a curva de
patrimônio contínua (sem resetar por mês, como uma conta real veria), o V1 estouraria o limite
de $1.000 EOD ($1.162,50 de DD); o V2 não estoura (fica em $524, 52,4% do limite).**

**Hipótese confirmada com evidência forte:** o BE mais baixo ($60 em vez de $100) + stop menor
($150 em vez de $250) reduz o tamanho médio das derrotas MUITO além do que a redução linear de
contratos (4/6=67%) explicaria — a razão é estrutural (arma proteção mais cedo), não
coincidência. Confirmado em 2 meses (jun forte, jul mais fraco mas ainda positivo) e com um
caso concreto e explicável do CUSTO desse design (dia 06/07 — corta um trade que teria sido
grande).

**Risco da conclusão / ressalva de robustez:** 2 meses (jun forte PF 1,61, jul fraco PF 1,04) —
julho quase não teria batido a régua sozinho. O padrão de slippage no stop sintético (3
ocorrências em 45 dias, todas piorando o resultado) é um problema real e não resolvido — meu
experimento recomendado (trocar pra ordem STOP nativa do NT8) continua sendo o próximo passo
mais bem fundamentado, agora com mais evidência sustentando ele.

**Classificação (mesma régua de ontem): V2 sobe de INVESTIGATE pra algo mais perto de KEEP
CONDICIONAL** — não é aprovação de conta ainda (nenhum mês bateu a meta $1.500), mas é a
primeira vez no projeto inteiro que a curva de patrimônio contínua de 45 dias reais NÃO
estourou o drawdown. Antes de subir mais o nível de confiança: (1) testar agosto pra ter um
3º mês independente, (2) implementar a troca pro stop nativo e ver se elimina os 3 casos de
slippage, (3) só depois disso considerar aumentar contratos ou tentar bater a meta de aprovação
de verdade.
