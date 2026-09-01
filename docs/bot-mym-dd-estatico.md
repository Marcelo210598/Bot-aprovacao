# Bot MYM + DD estático — plano e ficha de config (01/09/2026)

> ## 🔴 ATUALIZAÇÃO (01/09, mesmo dia): as 2 alavancas são SEPARÁVEIS e só uma vale
>
> Testado `backtest/run_mnq_mym_junto.py` (MNQ + MYM na mesma conta):
> - **Lever 1 (DD estático) NÃO é código** — aplica ao `BotAprovacao_BETrigger25.cs` (MNQ) como
>   está, só trocar de conta/firma. E **ajuda muito**: os params do BETrigger25 no dado do
>   Databento vão de 43% → **62% (Apex trailing) / 75% (DD estático)**.
> - **Lever 2 (MYM) não soma nada** em cima do MNQ. MNQ sozinho = 75% (OOS 62/69); MNQ+MYM = 73%
>   (OOS 56/91, mais estouros). MNQ e MYM são ~0,9 correlacionados (Nasdaq × Dow) → é dobrar a
>   mesma aposta.
>
> **Caminho recomendado:** `BotAprovacao_BETrigger25.cs` (MNQ, que o Marcelo já tem e já
> forward-testou) numa firma de **DD estático**. Nenhum código novo.
>
> **`src/BotAprovacaoDow_MYM.cs` fica como experimento standalone OPCIONAL** — só se o Marcelo
> quiser testar o Dow isolado. Não é a prioridade. O resto deste doc (ficha de params, firmas,
> passo a passo do forward test) continua válido pra esse caso.

---

## Por que essas duas alavancas

Da varredura de 01/09 (`docs/melhorias-sugeridas.md` #22, dado real Databento, motor de aprovação
de 30 dias):

| Alavanca | Achado |
|---|---|
| **MYM (Dow)** | Único instrumento além do NQ com edge na reversão PDH/PDL. WR **76%** (> 68% do NQ), quase **não estoura** (o Dow não dá spike contra você). PF **1,44 com fill de 1 tick / 1,18 com 2 ticks** — frágil a slippage, só forward test resolve. MES e M2K: sem edge. |
| **DD estático** | O DD trailing intradiário da Apex é o que fabrica o risco de estourar. Com limite **fixo** desde o saldo inicial (nunca sobe), a estratégia **nunca estoura** — ou aprova ou só expira o prazo. Backtest NQ: 55% → **60%, zero estouros**. |
| **Os dois juntos** | MYM sob DD estático: melhor risco-retorno do que qualquer coisa testada no NQ sob Apex. |

**Importante sobre "DD estático" vs "EOD trailing":**
- **Apex** = DD trailing INTRADIÁRIO (conta lucro não-realizado no pico) → o pior caso.
- **EOD trailing puro** (trava no fim do dia mas continua subindo) → no backtest ajudou pouco
  (55%, quase igual à Apex).
- **EOD trailing que TRAVA** (para de subir quando você passa do buffer) OU **static de verdade**
  (fixo desde o dia 1) → é o que dá o salto pra ~60%.
- **O que procurar:** conta com **static drawdown** de verdade, ou EOD-que-trava. Não adianta uma
  firma com EOD trailing normal.

---

## Ficha de config do `BotAprovacaoDow_MYM.cs` (defaults já no código)

Do grid de 01/09 (`backtest/run_instrumento_scan.py`), range RTH mediano do MYM ≈ 417pt.
**MYM: $0,50/ponto, tick = 1,00 ponto Dow.**

| Param (grupo no NT8) | Default | Racional |
|---|---|---|
| Contratos | **5** | Conservador. Backtest tem pico em 8–10c. 5c × $0,50 = $2,50/pt; SL 29pt = **$72,50/trade** |
| Alvo (pontos) | 117 | ~4× o stop |
| Stop (pontos) | 29 | ~7% do range RTH mediano do MYM |
| Breakeven gatilho | 9 | ~SL × 0,3 |
| Breakeven trava | 6 | ~SL × 0,2 |
| Trailing (pontos) | 2 | ~SL × 0,07 |
| Tolerância toque (ticks) | 12 | MYM tick = 1pt → 12 ticks = **12pt** de tolerância no toque da linha |
| Max dist. entrada (pontos) | 35 | anti-chase |
| Buffer stop servidor | 10 | o Dow anda mais em pontos que o Nasdaq |
| Stop diário ($) | **750** ⚠️ | ajustar conforme a firma |
| Max trades/dia | 12 | mesmo do NQ |
| BE-lock proporcional | **OFF** | era otimização marginal do NQ, nunca validada no Dow. Ligar só se for testar (fração 0,85). |
| Meta lucro ($) | **1500** ⚠️ | ajustar conforme a firma |
| Mín. dias operados | **7** ⚠️ | ajustar conforme a firma (muitas de DD estático = 2–5) |

Tudo é campo no gráfico — dá pra ajustar sem recompilar.

---

## Firmas a levantar (Marcelo confirma os números — mudam toda hora)

Procurar: **automação liberada** + **DD estático (ou EOD-que-trava)** + preço de conta pequena +
regra de consistência.

| Firma | O que checar |
|---|---|
| **Tradeify** | "Straight to Funded" / planos com **static drawdown**. Automação: permitida (confirmar). Regra de consistência no payout. |
| **MyFundedFutures (MFFU)** | Plano "Milestone" (static-ish) vs "Starter"/"Expert" (EOD trailing). Automação: permitida. Menor conta costuma ser 50K. |
| **Take Profit Trader (TPT)** | Conta 25K: meta ~$1.500, DD ~$1.500 EOD (trava ao atingir a meta). Automação: permitida. Sem mín. de dias na eval. |
| **Topstep (TopstepX)** | DD trailing por saldo EOD (não trava até funded). Consistência 50% no payout. Automação: permitida na TopstepX. |
| **Alpha Futures / Legends** | Têm opções de static drawdown. Menos conhecidas, checar automação. |

⚠️ **Apex proíbe automação oficialmente** (item de risco jurídico do projeto). Uma das razões da
troca de firma é justamente sair disso.

Assim que o Marcelo trouxer os números de UMA firma, é só setar `Meta` / `Stop diário` /
`Mín. dias` no gráfico e rodar.

---

## Como forward-testar (mesmo processo da diurna)

1. **Baixar o `.cs` do GitHub** (não colar texto — corrompe linhas longas). Conferir hash MD5.
   Compilar F5 no NT8.
2. **Gráfico:** MYM, **1 minuto**, sessão **ETH/Globex** (não RTH-only — a segunda-feira usa o
   range do domingo à noite), fuso **ET**, "Days to load" ≥ 3.
3. **Market Replay:** rodar dia a dia, do começo de um mês, registrando **o preço de fill de cada
   trade** (o log já mostra `entryPrice`) — é isso que vai dizer se o fill real do MYM aguenta
   (o backtest com fill de 1 tick dá 62%, com 2 ticks dá 43%).
4. **Métrica:** aprovação em 30 dias + PnL, comparando contra o forward test do NQ nos mesmos
   dias.
5. Só depois: conta real (na firma de DD estático).

**Pasta de registro sugerida:** `forward-test-replay-25k/2026-XX-mym-ddestatico/`.

---

## O que este bot NÃO tem (de propósito)

- **Guarda de DD trailing interna** — nunca teve (o BotAprovacao sempre confiou no
  `StopDiarioDolar`). Numa firma de DD estático isso é até melhor: menos coisa pra dar errado.
- **Estratégia noturna** — código dormente (`OperarNoite=false`), igual ao BETrigger25.
- **Saída parcial** — desligada (`UsarSaidaParcial=false`), rejeitada no NQ (item #15).

## Pendências / próximos passos

1. Marcelo levanta os termos de 1 firma de DD estático → setar Meta/StopDiario/MinDias.
2. Forward test no Market Replay do MYM, medindo o fill real.
3. Se o fill aguentar (PF > 1,2 no replay): considerar subir pra 8c e/ou ligar o merge com o
   fade do range overnight (precisa de código no `.cs` — o 2º sinal ainda não está implementado).
4. Se o fill NÃO aguentar: a direção B por instrumento está encerrada; sobra aceitar ~50% no NQ
   e escalar, OU só a troca de firma (DD estático) no NQ atual.
