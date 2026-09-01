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
| 11-12/07 | — | — | — | −$696,0 | fim de semana — mercado fechado |
| 13/07 | 5 | 3/2 | **−$0,5** | −$696,5 | +$225 nos 3 verdes (L5/L7 correram +$100 cada); L6 −$153 (gap +11pt), L8 −$121 (facada) |
| 14/07 | 6 | 1/5 | **−$140,0** | **−$836,5** | 5 de 6 trades = trailing quebrado (deviam ganhar pequeno, saíram no BE); S16 −$119,5 (facada) |

> **Calendário julho/2026:** 03/07 = feriado (Independence Day observado). 04-05, 11-12, 18-19,
> 25-26 = fins de semana. Segundas usam o range do Globex de domingo à noite.

**Acumulado (01→14/07, 10 pregões, 6 operados): −$836,5.** Faltam ~18 pregões e +$2.336,5.
Drawdown: **$887,5** (Apex trailing, **89% do limite $1.000 — a 1 trade ruim de estourar**) /
**$836,5** (DD estático, 84%).

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
| 13/07 NIV_L6 | −$153,0 | **gap de entrada** — sinal @ 29558, fill 29569,45 (+11,45pt); vela de sinal foi spike de 53pt |
| 13/07 NIV_L8 | −$121,0 | **facada** — fav +0,75pt |

**8 losses grandes = −$1.166.** Os 21 trades restantes somaram **+$470**. 5 facadas, 2 gaps de
entrada, 1 borderline. **O resultado do mês (−$696,5) É esses 8 trades.**

### 🔴 Gap de entrada — agora é padrão CONFIRMADO (2x: 08/07 NIV_L14, 13/07 NIV_L6)

Nos 2 casos: vela de sinal foi um **spike violento** (17pt e 53pt abaixo da linha) seguido de
fechamento longe do fundo. O bot manda a ordem no close da vela e o `OnMarketData` preenche
**~11pt pior**, porque o preço já correu nos segundos seguintes. O favor "some" no fill → stop
cheio. **Recomendação: investigar a lógica de entrada do `OnMarketData` no `.cs`** — parece estar
perseguindo o preço em vez de entrar a mercado no 1º tick. Numa reversão violenta, esperar = pagar
10pt. Isso o backtest NÃO modela (preenche no close da vela). Ver item #17.

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

## 🔴 Trailing quebrado no replay 500x — CONFIRMADO em escala (14/07)

Começou como "sai 2-3pt pior" (06/07 S1/S3, 08/07 L13). No **14/07 foi o dia inteiro**: 5 de 6
trades ativaram o BE, favor de +2,5 a +15pt, trailing gerenciado travando +2 a +13pt de lucro —
e o **PnL real de cada um foi ~$0** (−$11, −$7, −$2,5, −$4, +$4).

**Hipótese: a 500x o `OnMarketData` não acompanha os ticks.** O trailing é gerido tick a tick;
com os ticks chegando em lote, o gerente exita no preço atual (breakeven) em vez do nível
trilhado. O `<<< SAIDA ~saida X` do log mostra um nível que **nunca executou**.

**AÇÃO (Marcelo, próximo dia): rodar o replay a 1x ou 5x.** Se os trailing exits passarem a sair
nos +$18-30 esperados, boa parte da perda de julho (~$200-400 nos ~10-15 trailing scratches) é
**artefato de velocidade de replay**, não da estratégia. Se continuar saindo no BE mesmo a 1x, aí
o trailing de 1,75pt é apertado demais pra valer.

## Métrica que decide

- Aprovação dentro de 30 dias corridos (01/07 → 30/07) + PnL.
- Backtest: BETrigger25 params no dado do Databento = ~62% (Apex) / **75% (DD estático)**. Julho
  é um dos meses "bons" pro BE trig 2,5.
