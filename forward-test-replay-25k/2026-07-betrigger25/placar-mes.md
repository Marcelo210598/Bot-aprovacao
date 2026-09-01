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
| 02/07 | 2 | 1/1 | **−$118,0** | −$118,0 | NIV_L9 +$51; NIV_L10 −$169 (facada, fav +0,75pt) |
| 03/07 | 0 | — | $0,00 | −$118,0 | sem entradas |
| 06/07 | 5 | 1/4 | **−$245,5** | −$363,5 | 2 facadas (S4 −$148, S5 −$122) + 2 scratches de trailing |
| 07/07 | 0 | — | $0,00 | −$363,5 | sem entradas |
| 08/07 | 5 | 2/3 | **−$270,0** | −$633,5 | NIV_L14 −$158 (gap de entrada +10pt); L15 −$139 |
| 09/07 | 0 | — | $0,00 | −$633,5 | sem entradas |
| 10/07 | 4 | 3/1 | **−$62,5** | **−$696,0** | +$94 nos 3 primeiros, aí NIV_S20 −$156,5 (facada) devolveu tudo |

**Acumulado (01→10/07, 8 pregões, 4 operados): −$696,0.**
A trava real: **$1.500 em 30 dias corridos**. Faltam ~20 pregões, precisa de +$2.196 do ponto
atual.
Pico acumulado: +$51 (02/07). Drawdown atual: **$747,0** (Apex trailing, **75% do limite $1.000**)
/ **$696,0** do saldo inicial (DD estático, 70%).

## 🔴 Os 5 losses grandes de julho (−$736) — 2 causas

| Trade | PnL | Causa |
|---|---|---|
| 02/07 NIV_L10 | −$169 | **facada** — fav +0,75pt, vela reverte na hora |
| 06/07 NIV_S4 | −$148 | **facada** — fav +0,8pt |
| 06/07 NIV_S5 | −$122 | **facada** — fav +0,85pt |
| 08/07 NIV_L14 | −$158 | **gap de entrada** — sinal @ 29211,75, fill real 29221,90 (+10pt); o favor "sumiu" no fill |
| 08/07 NIV_L15 | −$139 | fav +1,85pt (facada-borderline) |
| 10/07 NIV_S20 | −$156,5 | **facada** — entrada em cima da linha, fav +1pt, reversão em V |

Os 16 trades restantes somaram **+$196**. **O resultado do mês inteiro (−$696) são esses 6
trades** (−$892). 4 são facada, 1 é gap de entrada, 1 borderline.

### Facada (item #17) — sem filtro, já investigado

02/07 NIV_L10, 06/07 NIV_S4 e S5: **stop cheio com favor < 1pt**, a vela de entrada já reverte.
Backtest de 13 meses (`backtest/analise_facada.py`): 70 casos (~5-6/mês, −$131/trade). **Nenhum
sinal pré-entrada os distingue.** Loss-cut já rejeitado (item #16). O SL de 12,5pt existe pra
capar isso — e o DD estático é o que impede de estourar a conta num dia como o 06/07.

### 🆕 Gap de entrada — NIV_L14 (08/07)

O sinal disparou LONG @ 29211,75 (vela de rejeição limpa, L=29194,50, C=29211,75). Mas o fill
real foi **29221,90 — 10,15pt pior**. Nos segundos entre o close da vela e o `OnMarketData`
mandar a ordem, o preço já correu 10pt. Aí o favor a partir do fill real foi só +2,1pt (não bateu
BE), reverteu, stop cheio. **No preço do sinal esse trade teria dado +12pt de favor.**
Conecta com a 2ª hipótese do item #17 ("fill de entrada vem tarde"). Aqui veio 10pt tarde depois
de uma vela de sinal violenta (spike + fechamento longe do fundo). **Watch:** ver se se repete e,
se sim, checar a lógica de entrada do `OnMarketData` (pode estar perseguindo o preço em vez de
entrar a mercado no 1º tick).

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
