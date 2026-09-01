# Estratégia nova (do zero) — decisão de 01/09/2026

## Por que estamos aqui

A reversão PDH/PDL no MNQ **não passou o teste de robustez fora da amostra**. Verificado
no NT8 Strategy Analyzer (o motor confiável — o backtest Python do projeto era ~40% otimista
no PF e pegava 6-16× mais trades):

| Config | Período | Fator de lucro | Líquido |
|---|---|---|---|
| Both-sides + comissão | 2026 (~7 meses) | **0,96** | −$746 |
| Short-only + comissão | 2026 (~7 meses) | 1,44 | +$1.516 |
| **Short-only + comissão** | **2022-2025 (4 anos)** | **0,91** | **−$894** |

O PF 1,44 de 2026 era **sorte de regime** — 2026 teve ~3× mais setups (toques na linha com
rejeição) e eles funcionaram; 2022-2025 não. 201 trades em 4 anos, avg −$4,45/trade, DD −$2.372.

Firma de DD estático **não conserta** um PF 0,91 — DD estático faz perder mais devagar, mas
ainda precisa bater uma meta de lucro com uma estratégia negativa.

**Já morreram no backtest ao longo do projeto:** reversão PDH/PDL (agora), ORB (15/30min),
EMA/VWAP, ICT-lite (FVG), Renko+MA, rompimento de PDH/PDL, squeeze, RSI-reversion, Initial
Balance, VWAP-reversão. Todos no MNQ 1-min, formato de aprovação Apex.

**Decisão do Marcelo (01/09):** estratégia nova de verdade, do zero — não variação da reversão.
Começar por **B (event-driven)**. Iniciar amanhã (02/09).

---

## As 3 candidatas levantadas

### Restrições do formato (valem pras 3)

- Apex 25K: meta **$1.500 em 30 dias corridos**, DD **trailing $1.000**, mín. dias já não pesa.
- 5 MNQ = **$10/ponto**. Precisa ~**$50-75/dia** de média, ~15-20 pregões pra bater a meta.
- **Nunca** abaixar $1.000 do pico (DD trailing intradiário — devolver lucro conta).
- Custo real ~**$6,50/round-turn** (5 MNQ, modelo NinjaTrader Brokerage) → o trade precisa de
  expectativa **gorda**, não volume de trades pequenos.
- Motor de teste = **NT8 Strategy Analyzer**, nunca mais o Python reimplementado.
- Dado disponível: **MNQ 1-min contínuo 2022-06 → 2026-08** já importado no NT8 como `MNQ 12-25`
  (fuso Central/Chicago). Testar em **2022-2025** desde o dia 1, **2026 = holdout**.

---

### ✅ B — Event-driven: o spike das 8h30 ET (ESCOLHIDA)

**Tese:** releases econômicos das 8h30 ET (CPI, PPI, NFP, retail sales, jobless claims, GDP,
PCE) produzem volatilidade **agendada e enorme**. Não se negocia estrutura de preço — se
negocia uma injeção de liquidez com hora marcada.

**Mecânica (rascunho — definir exato amanhã):**
- Só nos dias/horários de release relevante (calendário — ~8-12 eventos/mês).
- No 1º fechamento de barra de 1-min **após** o release (8h31 ET), entra **a favor** do movimento
  se a barra fechou fora de um range de referência (ex.: range das 8h25-8h30) com corpo > X.
- Bracket **apertado e fixo** (sem trailing tick-a-tick que estrangula — lição da auditoria):
  stop = tamanho da barra de disparo ou X pts; alvo = 2-3× o stop OU parcial + runner.
- Flat em ~15-30 min (o edge do release decai rápido). Sem overnight.

**Por que pode funcionar onde a reversão não funcionou:**
- Exposição de **minutos** por dia → o DD trailing quase não é ameaçado (não fica "devolvendo
  lucro" a tarde inteira).
- Perda **travada** no bracket, sem give-back de gestão.
- Mecanismo independente de o MNQ tender ou reverter — é reação a informação nova.
- FOMC já mostrou (no projeto, com a reversão): o bot **lucra** em dia de evento. Aqui seria
  dedicado.

**Riscos / o que testar:**
- O follow-through do 1º minuto é real ou é ruído/whipsaw? (o "head fake" dos releases).
- Slippage no fill às 8h31 pode ser brutal (spread alarga no release). **Testar com slippage
  agressivo** (3-5 ticks) desde já — foi slippage que matou a noturna.
- Poucos eventos/mês → variância alta, custa mais tempo pra ter significância.
- Calendário de eventos precisa ser carregado no bot (lista de datas/horas ou fonte).

**1º passo amanhã:** montar a lista de releases 8h30 ET de 2022-2026 (CPI/PPI/NFP/claims/retail/
GDP/PCE), rodar um teste tosco no Analisador (entra 8h31 ET a favor do rompimento do range
8h25-30, bracket 2:1) só nesses dias, ver se tem sinal antes de refinar.

---

### A — Seguir tendência intradiária (momentum continuation)

**Tese:** o MNQ **tende** (foi o que matou a reversão). Então opere a favor: dia com 1ª hora
direcional forte → entra nos **pullbacks na direção da tendência**, stop largo, deixa correr
2-3R.

**Mecânica (rascunho):**
- Filtro de dia: só opera se a 1ª hora (9h30-10h30 ET) tem range direcional > X e Close perto
  do extremo (dia que "abriu andando"). ~40-50% dos dias.
- Entrada: pullback a uma MME/VWAP na direção da 1ª hora, com barra de retomada.
- Stop largo (abaixo do pullback), alvo runner (trailing FROUXO ou parcial + deixa correr).

**Por que pode funcionar:** inverte a premissa da reversão. O "inverso" certo não é romper a
PDH (testado, fraco) — é **cavalgar a tendência já estabelecida**.

**Riscos:** dias de chop = **perdas em cluster** → perigoso pro DD trailing. Win rate baixo
(35-45%) exige disciplina de deixar o runner correr; se cortar cedo, morre. Precisa de filtro
de tendência bom (a parte difícil).

---

### C — Gap de abertura (Globex close → RTH open)

**Tese:** o gap entre o fechamento do Globex e a abertura RTH (8h30 ET) tem comportamento
estatístico documentado em índice: gaps pequenos tendem a **fechar** (fade pro close anterior);
gaps grandes que **seguram** os 1os 15 min tendem a continuar (gap-and-go).

**Mecânica (rascunho):**
- Mede o gap na abertura RTH vs. fechamento RTH anterior (ou settlement).
- Gap-fill: gap pequeno-médio → entra contra o gap mirando o close anterior, stop além do
  extremo da abertura.
- Gap-and-go: gap grande + segura 15 min → entra a favor.
- 1 setup/dia, decisão rápida, flat antes do meio-dia.

**Por que pode funcionar:** edge clássico e simples, 1 trade/dia, exposição curta. O projeto
**nunca testou direito** (bug no harness Python antigo).

**Riscos:** a distinção "vai fechar" vs "vai continuar" pode ser tão difícil de separar quanto
foi "vai reverter" vs "vai romper" na reversão (a parede que já batemos). Edge de gap pode ter
decaído (muito arbitrado hoje).

---

## Regras do jogo pra evitar repetir os erros

1. **NT8 Strategy Analyzer é o motor.** Python só pra prototipar hipótese, nunca pra decidir.
2. **OOS desde o dia 1:** desenvolve/calibra em **2022-2025**, **2026 é holdout** (só olha no fim).
3. **Slippage agressivo** no teste (3-5 ticks nos eventos) — foi slippage que matou a noturna e
   inflou o MYM.
4. **Bracket fixo, sem trailing tick-a-tick** — a auditoria de julho provou que o
   `OnBarClose`×`OnMarketData` + BE-lock 0,75 estrangula o avgW em ~$35. Alvo fixo ou parcial+runner.
5. **Critério de corte:** PF > 1,3 em 2022-2025 com comissão E slippage, senão não escreve `.cs`.
6. **Não tocar produção** (`BotAprovacao.cs`).
7. Considerar rodar o skill **grill-me** na regra final da B antes de codar.
