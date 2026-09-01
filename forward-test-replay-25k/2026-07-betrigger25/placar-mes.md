# Placar — BETrigger25 (BE trig 2,5 + MaxDist 20 + BE-lock 0,75), JULHO/2026

> **Troca de mês (01/09):** o forward test do BETrigger25 estava em junho e parou em 11/06
> (Marcelo insatisfeito, 29/08). Junho é o **pior mês** pro achado do BE trig 2,5 — no backtest de
> 13 meses os DOIS junhos (2025 e 2026) estão entre os que pioram, e 9 de 13 meses melhoram.
> Marcelo decidiu refazer em **julho/2026, do dia 01**, com a mira numa **firma de DD estático**
> (Tradeify/MFFU/TPT). Bot: `src/BotAprovacao_BETrigger25.cs` (inalterado), MNQ, gráfico 1min.

## Registro dia a dia

| Dia | Trades | G/L | PnL dia | Acumulado | Obs |
|---|---|---|---|---|---|
| 01/07 | 0 | — | $0,00 | $0,00 | sem entradas |
| 02/07 | 2 | 1/1 | **−$118,0** | −$118,0 | NIV_L9 +$51; NIV_L10 −$169 (facada, favor +0,75pt) |
| 03/07 | 0 | — | $0,00 | −$118,0 | sem entradas |
| 06/07 | 5* | 1/4 | **−$245,5** | **−$363,5** | 2 facadas (S4 −$148, S5 −$122) + 2 scratches de trailing (S1, S3) |

\* prints de 06/07 até ~11:33 — pode não ser o dia completo.

**Acumulado (01→06/07, 4 pregões, 2 operados de 7 mínimos): −$363,5**
Pico: +$51 (após NIV_L9 em 02/07). Drawdown atual: **$414,5** (Apex trailing) / **$363,5** do
saldo inicial (DD estático).

## 🔴 Padrão que apareceu já nos 2 primeiros dias operados: "facada" (item #17)

3 de 7 trades (02/07 NIV_L10, 06/07 NIV_S4 e NIV_S5) foram **stop cheio com favor máximo < 1pt** —
a vela de entrada já reverte, sem dar tempo do breakeven agir. Juntos: **−$439** dos −$363,5 do
mês. Sem esses 3, o mês estaria **+$75**.

**Análise no backtest de 13 meses (01/09, `backtest/diagnostico_mfe_mae_trades.csv`):**
- 70 trades assim / 13 meses (~5-6/mês, **−$131/trade**, **−$9,2k total**).
- **Nenhum sinal pré-entrada os distingue:** dist_nivel idêntico (5,2 vs 5,0pt), gap idêntico
  (0,00), mesma hora, mesmo dia da semana, espalhados por todas as faixas de distância. Duração
  mediana = **0 barras** (morre na própria vela de entrada).
- Cortar cedo (loss-cut) já foi testado e **rejeitado** (item #16): 10,7% dos VENCEDORES também
  tocam −12,5pt de MAE antes de virar — o corte mata esses junto.
- **Conclusão: não tem filtro.** O SL de 12,5pt existe pra capar exatamente isso. O que impede a
  facada de estourar a conta é o **DD estático** (você absorve 2-3 facadas num dia ruim como o
  06/07 desde que não vá −$1.000 do saldo inicial). É mais um motivo pra firma de DD estático.

## 🟡 Segundo problema (06/07 NIV_S1, NIV_S3): trailing sai pior que o gerenciado no replay

"A vela desceu e mesmo assim deu loss" — o preço foi a favor, o BE ativou, mas o trailing 1,75pt
+ o fill tick a tick (replay 500x) saíram ~2-3pt piores que o nível gerenciado no log → +$20/+$25
esperado virou −$6/−$5,5. É a diferença conhecida motor bar-based × execução real (`progress.md`).
**Watch:** medir ao vivo (velocidade real) se o fill do `TrailingTick` sai consistentemente pior
que o gerenciado — se sim, o trailing pode estar apertado demais pro atrito real.

## Métrica que decide

- Aprovação dentro de 30 dias corridos (01/07 → 30/07) + PnL.
- Backtest: BETrigger25 params no dado do Databento = ~62% (Apex) / **75% (DD estático)**. Julho
  é um dos meses "bons" pro BE trig 2,5.
