# 🛠️ Melhorias Sugeridas — BotAprovacao

> Derivado da pesquisa de 23/06/2026 (ver `docs/pesquisa-bots-nt8-apex.md`).
> Lista priorizada do que mudar, com status de cada item.

---

## 🔴 DESCOBERTA #1 — Slippage realista (FEITO 23/06)

**O backtest rodava com slippage ZERO.** A comunidade usa 2-4 ticks no MNQ.
Rodamos `backtest/run_slippage_test.py` (varredura 0→4 ticks na config de produção).

### Resultado (config produção: canal≥40, pula domingo, SL12.5/TP60/trail1.75):

| Slippage | SÓ DIURNA | SÓ NOTURNA | COMBINADO | PnL$/ano combinado |
|----------|-----------|------------|-----------|--------------------|
| 0 tick   | 100% PF1.66 | 100% PF1.35 | 96% PF1.57 | $47.438 |
| 1 tick   | 100% PF1.52 | 67% PF1.20  | 100% PF1.43 | $36.876 |
| **2 tick** ⭐ | **100% PF1.38** | **40% PF1.06** | **89% PF1.28** | **$25.044** |
| 3 tick   | 71% PF1.24  | 0% PF0.94 ❌ | 56% PF1.15 | $13.365 |
| 4 tick   | 50% PF1.13  | 0% PF0.82 ❌ | 43% PF1.03 | $2.903 |

### 🎯 Conclusões CRÍTICAS:
1. **DIURNA é ROBUSTA**: segura 100% de aprovação até 2 ticks de slippage. Só
   degrada em 3+ ticks. É a verdadeira workhorse do bot. ✅
2. **NOTURNA é FRÁGIL**: desaba feio. 1 tick → 67%, 2 ticks → 40%, **3 ticks já dá
   PREJUÍZO** (PF 0.94, -$1.680/ano). Os wins minúsculos da noturna (vimos +$18-30
   no forward test) NÃO absorvem slippage. ❌
3. **Isso BATE com o forward test ao vivo**: os wins da noturna eram curtíssimos e
   os stops cheios. Sob atrito real, a vantagem de "+33% PnL" da noturna some — e
   pode virar negativa.
4. **O backtest estava otimista — especificamente sobre a noturna.** A diurna sozinha
   aguenta a realidade; a noturna depende de execução quase perfeita.

### OOS a 2 ticks (robustez):
- Diurna: 100% | 100% (sólida nas duas metades) ✅
- Noturna: 0% | 50% (instável) ⚠️
- Combinado: 83% | 92%

### 📌 DECISÃO A TOMAR:
- **Opção A (conservadora):** desligar a noturna ao vivo (`OperarNoite=false`) e
  rodar só a diurna, que é robusta a slippage. Perde PnL nominal mas ganha
  consistência real.
- **Opção B:** manter noturna mas só com canal MUITO grande (já testar rng_min mais
  alto) ou alvo maior pra dar gordura contra slippage — exige novo backtest.
- **Opção C:** manter como está e monitorar o forward test, sabendo que a noturna
  é o elo fraco. Se sangrar ao vivo, desligar.
- ⚠️ Não decidir no achismo — se mexer, backtestar antes (regra do Marcelo).

---

## 🔴 Alta prioridade (próximos passos)

### #2 — News filter (FOMC) — ❌ TESTADO E REJEITADO (23/06)
Hipótese: parar de operar em torno do FOMC (14h ET) reduziria perdas. **O backtest
DERRUBOU a hipótese.** Rodado `backtest/run_news_filter.py` (diurna only, slippage
2 ticks, 8 dias de FOMC reais no período 06/25-06/26):

| Cenário | Taxa | PF | PnL$/ano | PnL dias FOMC |
|---------|------|-----|----------|---------------|
| SEM filtro (baseline) | 100% | 1.38 | $23.517 | **+$1.476** |
| blackout ±15min | 100% | 1.37 | $23.176 | +$1.135 |
| blackout ±30min | 100% | 1.36 | $22.716 | +$780 |
| blackout ±60min | 100% | 1.36 | $22.347 | +$410 |

**Por que não ajuda:** a diurna LUCRA nos dias de FOMC (+$1.476 em 8 dias). Pior dia
foi só -$264 (bem dentro do stop diário $750). A reversão em nível do dia anterior
aguenta a volatilidade do FOMC, e o stop diário já capa o tail risk. Qualquer
blackout só REMOVE trades lucrativos → menos PnL.

PnL por dia de FOMC (sem filtro): -264 / +574 / 0 / -134 / +767 / -240 / 0 / +774.
Nenhum desastre. CPI/NFP (8h30 ET) são PRÉ-abertura → a diurna (9h30+) nem opera neles.

**DECISÃO: não implementar.** Achismo da comunidade que não vale pro nosso bot
(que já tem stop $125/trade + stop diário $750 + reversão em nível). Menos
complexidade, menos ponto de falha. ✅

### #3 — VPS profissional (QuantVPS ~$60 ou FinTechVPS ~$50/mês) — PENDENTE
Win 11 doméstico depende da internet de casa (causou os problemas dessa semana).
AWS/Azure não servem (Rithmic bloqueia — já confirmamos na prática).
- Maior ROI do projeto agora: elimina ~100% dos problemas de conexão.
- Opcional: Ninja Watchdog ($49/mês) pra relançar NT8 sozinho.

### #4 — MaxTradesDia = 8-12 — ✅ VIÁVEL E VALIDADO OOS (23/06)
Testado em `backtest/run_melhorias_sweep.py` (DD real 1000, slippage 2 ticks).
**Limitar trades/dia SOBE a aprovação cortando overtrading:**

| Limite | Taxa | Aprov | Trades | OOS (1a\|2a) |
|--------|------|-------|--------|--------------|
| sem limite (atual) | 57% | 13/23 | 1419 | 56% \| 54% |
| max 8/dia | **68%** | 13/19 | 934 | 71% \| 67% |
| max 12/dia | **70%** | 14/20 | 1166 | 62% \| 75% |

**max 8** = melhor eficiência (mesmas 13 aprovações com 34% menos trades = menos
slippage/comissão). **max 12** = maior taxa (70%, 14 aprovações). Ambos seguram OOS.
✅ **Implementação ZERO risco: o parâmetro `MaxTradesDia` JÁ EXISTE no .cs** (só está
em 0). Basta setar 8 ou 12 no gráfico — sem recompilar código.

---

## 🟡 Média prioridade

### #5 — Regra de consistência Apex 4.0 (50%) — ⚠️ RISCO REAL CONFIRMADO (23/06)
Medido no sweep: **~40% das nossas "aprovações" violariam a regra dos 50%** (um único
dia fez >50% do lucro total). Pior caso: 1 dia = 82% do lucro. Média do melhor dia =
45-51% do total (bem no limite).

| Config | Aprov | Válidas (≤50%/dia) | Pior dia |
|--------|-------|--------------------|---------| 
| DD1500 | 14 | 8 (57%) | 82% |
| DD1000 | 13 | 10 (77%) | 81% |

**O bot concentra lucro em poucos dias.** Mesmo batendo a meta, pode não qualificar
pro saque/aprovação na Apex 4.0. Mitigação possível (testar): cap de lucro diário, ou
o MaxTradesDia (espalha o lucro). ⬜ Avaliar cap diário em backtest.

### #6 — Conta $50K em vez de $25K — ✅ VIÁVEL E FORTE (23/06)
Testado: **$50K com as MESMAS 5 MNQ elimina os busts.** A gordura maior (DD $2.000 vs
$1.000) transforma um bot de 57% num bot de **100%**:

| Conta | Taxa | Aprov | d.med | OOS (1a\|2a) |
|-------|------|-------|-------|--------------|
| $25K (5 MNQ) | 57% | 13/23 | 15d | 56% \| 54% |
| **$50K (5 MNQ)** | **100%** | **7/7** | 41d | 100% \| 100% |
| $50K (10 MNQ) | 57% | 13/23 | 15d | (escala risco junto) |

$50K/5MNQ = ZERO busts nas duas metades OOS. Trade-off: meta 2x ($3.000) → aprova
menos vezes/ano (7) e demora mais (41d), MAS nunca quebra (sem reset fees) e cada
aprovação vale 2x. **Melhor escolha risco-ajustada.** Combinado com max12: 100% + PF melhor.

### #7 — DD real $1.000 — ✅ CONFIRMADO no dashboard Apex (23/06)
**Confirmado: a conta $25K tem DD = $1.000** (variante EOD, NÃO $1.500). O backtest
antigo (DD $1.500) era otimista. Todos os scripts atualizados pra DD $1.000.

**Número REAL que vai pro ar ($25K, DD $1.000, slippage 2 ticks, max 12 trades):**
- **70% de aprovação** | 14 aprov / 6 busts no ano | PnL $21.562 | PF 1.41
- OOS: 62% | 75% (segura nas duas metades)
- Sem o max12 seria 57% (13 aprov / 10 busts) → **o max12 tira 4 busts**

Tradução: na conta $25K real, o bot aprova ~14x/ano mas busta ~6x (cada bust = comprar
nova eval). É lucrativo no agregado, mas tem reset fees. Próxima conta → $50K elimina
os busts (100%). Por ora o Marcelo testa na $25K já comprada.

---

## 🟢 Baixa prioridade (testar com backtest antes)

### #8 — ORB como estratégia complementar
Opening Range Breakout = melhor backtest documentado pela comunidade ($60.924, 2 anos).
Já temos `backtest/optimize_orb.py` e `run_backtest.py` — poderia virar 3ª estratégia
exclusiva 9:30-10:00 ET.

### #9 — MCL (Micro Crude Oil) como alternativa
Apareceu nos backtests ICT com DD de só -$788 (vs -$3.703 do MNQ). Menos volátil.
Vale backtest comparativo.

### #10 — Filtro anti-chase (`MaxDistPontos=15pt`) pode estar cortando reversões boas
Observado no forward test replay 25K, dia 11/06/2026 (ver `forward-test-replay-25k/2026-06/dia-11-11-06.md`):
4 toques na linha do dia, todos bloqueados por `CHASE ignorado` (candle fechou mais de 15pt
além da linha) — dia inteiro sem operação. Duas velas (15:05 e 15:25 ET) tocaram a linha e
reverteram de forma limpa, mas fecharam 137pt e 58pt de distância, respectivamente — acima do
limite fixo de 15pt.

Hipótese a testar: distância fixa em pontos pode ser rígida demais em dias de candle grande
(alta volatilidade), rejeitando reversões válidas. Alternativas a comparar em backtest:
- `MaxDistPontos` maior (ex.: 20-25pt) e medir se sobe trades sem estourar DD;
- regra relativa ao tamanho do candle/ATR do dia em vez de distância fixa em pontos;
- separar o limite por regime de volatilidade (ligado ao trabalho já feito em
  [[project_vida_de_trader_regime_dia]] sobre agitação do pregão, se aplicável).

⬜ **Não implementar sem backtest** — é a mesma trava de 0 trades que já vimos em mercado
lateral/esticado ([[project_bot_aprovacao_mercado_lateral]]); mudar sem medir pode abrir
espaço pra entradas ruins (perseguir movimento já esgotado).

**Sweep rodado 12/08** (`backtest/run_proximity_filter.py`, dados atuais):

| Filtro | Taxa aprovação | Aprov/Reprov | Mediana dias | PF | PnL$/ano | OOS (1ª\|2ª) |
|---|---|---|---|---|---|---|
| **15pt (atual)** | **100%** | 19/0 | 15d | 1.60 | $36.978 | **100% \| 100%** |
| 20pt | 91% | 20/2 | 14d | 1.57 | $38.414 | 90% \| 92% |
| 25pt | 91% | 20/2 | 13d | 1.54 | $37.794 | 90% \| 92% |
| 30pt | 91% | 21/2 | 14d | 1.55 | $39.380 | 91% \| 92% |

Afrouxar pra 20pt+ ganha PnL bruto (+$1,4k a +$2,4k/ano) e mais trades/dia, mas introduz **2
estouros de conta por ano** que não existem em 15pt — padrão consistente nas duas metades OOS,
não é ruído. 15pt segue sendo o único ponto do sweep com **0 busts** em 1 ano de dado real.

**🔴 DECISÃO (12/08): manter 15pt como está.** Marcelo vai terminar o forward test dos meses
06 e 07 com a config atual pra ver se aprova alguma conta. **Só revisitar afrouxar o filtro
(20-30pt) se o resultado desses dois meses não for satisfatório** (ex.: muitos dias zerados
matando o mínimo de 7 dias operados, ou não bater a meta $1.500 mesmo com dias bons). Até lá,
não mexer.

**🔴 GATILHO ACIONADO (12/08): mês de junho fechou incompleto** — +$170,5 de $1.500 (11,4%),
12 de 22 pregões zerados (quase metade do mês). Isso é o cenário que a decisão acima previu como
"resultado não satisfatório". Diagnóstico de causa dos 12 dias zerados (revendo os `dia-XX.md`):
- **~5 dias** tiveram toque na linha bloqueado pelo filtro anti-chase (11, 22, 25, 26/06 + outros)
- **~7 dias** o preço nunca chegou perto da linha (estrutural — reversão em nível único é
  seletiva por natureza, afrouxar o `MaxDistPontos` NÃO resolve esses dias)
- Ou seja: afrouxar o filtro recuperaria no máximo **~5 dos 12 dias zerados**, não todos.
- **Pendente decisão do Marcelo:** testar 20pt ao vivo em julho (troca ~5 dias zerados por ~2
  busts/ano de risco, ver sweep acima) OU manter 15pt e confiar no módulo ORB (abaixo) pra
  aumentar a frequência de trade sem mexer no risco da diurna.

## 🟠 #11 — Módulo ORB 15min (9h30-9h45 ET) — implementado e validado por backtest (12/08)

Segundo módulo independente (`src/NomadeBot_ORB_Manha.cs`), pedido do Marcelo pra aumentar a
frequência de trade sem mexer no risco da diurna. **Testado em `backtest/run_orb_15min.py`
sobre ~1 ano de dados 1min reais do NQ antes de escrever qualquer linha de `.cs`** (regra do
Marcelo: nada de achismo).

**Achado principal:** os números de "433%/ano, WR 65-78%" que circulam na internet pra ORB **NÃO
se sustentaram nos dados reais**. ORB "cru" (sem filtro de range): PF 0.58, WR 24% — perde
dinheiro. Config validada, depois de sweep de filtros:

| Config | n/ano | WR | PF | net/ano (5 MNQ) | OOS (1ª\|2ª) |
|---|---|---|---|---|---|
| Sem filtro de range | 291 | 24,4% | 0,58 | -$9.634 | — |
| + range 15-80pt | 77 | 37,7% | 1,08 | +$388 | 1,17 \| 0,84 (instável) |
| + EMA200(1h) | 49 | 42,9% | 1,34 | +$956 | 1,49 \| 1,10 |
| **+ SL12,5/TP37,5 (3x)** | **46** | **43,5%** | **1,90** | **+$2.766** | **1,72 \| 2,19** ✅ |

- **Filtro de range (15-80pt): ESSENCIAL**, não é opcional — sem ele o resultado é negativo
  mesmo com EMA200.
- **EMA200(1h): o filtro que mais ajudou isolado** (PF 1,08→1,34).
- **Reteste (entrada conservadora): REJEITADO** — piora (PF 0,96 vs 1,90 do breakout direto).
- **VWAP: REJEITADO** — redundante, não bloqueou 1 único trade no ano inteiro no backtest.
- **Notícias (CPI/NFP 8h30 ET): sem calendário pra backtestar de verdade** — mitigação indireta
  via o filtro de range máximo (80pt), que já descarta a maioria dos dias distorcidos.

**Veredito:** edge real mas modesta — ~46 trades/ano (~3-4/mês), +$2.766/ano com 5 MNQ. **NÃO é
"a solução" pros dias zerados da diurna** — é um complemento que adiciona uns 3-4 dias de trade/mês
que a diurna sozinha não teria. Rodar em forward test (Market Replay) antes de ligar ao vivo,
mesmo processo da diurna.

Status: ✅ Implementado (`src/NomadeBot_ORB_Manha.cs`), config validada por backtest. Kill switch
diário próprio + kill switch GLOBAL opcional (soma PnL dos outros bots via arquivo compartilhado
em `%AppData%/NinjaTrader 8/*_pnl_diario.txt`). Pendente: **BotAprovacao já grava seu PnL diário
nesse formato — NomadeTraderNoite ainda não** (checar antes de ligar `UsaKillSwitchGlobal=true`).

---

## 📋 Tabela de prioridade

| # | Melhoria | Esforço | Impacto | Status |
|---|----------|---------|---------|--------|
| 1 | Slippage realista no backtest | Baixo | Alto | ✅ FEITO 23/06 |
| 2 | News filter (FOMC) | Médio | — | ❌ TESTADO/REJEITADO 23/06 |
| — | Desligar noturna | Baixo | Alto | ✅ FEITO 23/06 (OperarNoite=false) |
| 3 | VPS QuantVPS/FinTechVPS | Baixo | Altíssimo | ⬜ Pendente (infra) |
| 4 | MaxTradesDia = 8-12 | Baixo | Alto | ✅ VIÁVEL — setar no gráfico (param já existe) |
| 5 | Regra consistência 50% | Médio | Alto | ⚠️ RISCO confirmado — avaliar cap diário |
| 6 | Conta $50K | Financeiro | Alto | ✅ VIÁVEL — 100% s/ busts (vs 57% no $25K) |
| 7 | DD real $1.000 | Baixo | Alto | ✅ TESTADO — confirmar DD real no dashboard |
| 8 | ORB complementar | Alto | Incerto | ⬜ Backlog |
| 9 | MCL alternativa | Médio | Incerto | ⬜ Backlog (sem dados) |
| 10 | Filtro anti-chase 15pt pode cortar reversões | Médio | Incerto | 🔴 Mês 06 no 1min FECHADO 13/08: +$168,0 (11,2% da meta), quase empatado com o 5min (+$170,5) — diagnóstico "era só o timeframe" NÃO confirmado. Ver veredito final em `forward-test-replay-25k/2026-06-1min/placar-mes.md` |
| 11 | Módulo ORB 15min (complemento, não substitui a diurna) | Alto | Modesto (+$2.766/ano) | ✅ Implementado e validado — `src/NomadeBot_ORB_Manha.cs` |
| 12 | Trava de lucro por horário (bot "sabe" o PnL do dia + a hora) | Médio | Incerto — precisa backtest | ❌ **TESTADO/REJEITADO 13/08** — variantes (max trades/dia, cooldown, parar após stop cheio) todas piores −23% a −64%. Ver `docs/gestao-dia-veredito.md` |
| 13 | **SL 12,5 → 15pt** | Baixo (param no gráfico) | — | ❌ **TESTADO AO VIVO E REJEITADO (14/08)** — validado 2x em backtest (18/06 e 13/08: +14%/+32% s/ slippage, WR 69→74%), mas o teste real manual (01-12/06, mesma janela) deu +$96,0 contra +$243,5 do SL 12,5 (60% pior). Não aplicado em produção. Ver `progress.md` 14/08. |
| 14 | BE-lock proporcional (0,75) | Baixo (já implementado) | Modesto, real | ✅ **VALIDADO EM MARKET REPLAY (18-20/08)** — Δ +$122,5 confirmado no bloco 01-18/06 (baseline +$147,0 → nova +$269,5). Zero efeito adicional em 19-28/06 (mecanismo só age quando MFE cai entre 3,75-7,0pt). Único mecanismo de saída que sobreviveu a todos os testes. |
| 15 | Saída parcial 4+1 em alvo MENOR (5/8/10/12,5/15pt) | Baixo | — | ❌ **TESTADO E REJEITADO (20/08)** — backtest completo (motor de aprovação, DD real $1000): quanto menor o alvo, PIOR o resultado (taxa 71%→5% no extremo). Até o alvo original de 20pt fica abaixo do "só BE-lock" (63% vs 71%) quando testado no motor de barra. Ver seção detalhada abaixo. |
| 16 | Corte de perda antecipado (loss-cut 2 de 5 contratos) | Baixo | — | ❌ **TESTADO E REJEITADO (20/08)** — corta futuros vencedores junto (10,7% dos vencedores tocam até -12,5pt de MAE antes de reverter); WR desaba de 68%→47-61%, taxa de aprovação cai em todos os thresholds testados (4/6/8/10pt). Ver seção detalhada abaixo. |

---

## 🎯 VEREDICTO DA VARREDURA (23/06) — o que vale e o que não

**Vale implementar (comprovado por backtest + OOS):**
1. **MaxTradesDia = 12** (ou 8 p/ eficiência) — sobe 57%→70%, zero risco (param já existe).
2. **Migrar pra conta $50K** com as mesmas 5 MNQ — 100% sem busts vs 57% no $25K.
   Combinado: **$50K + max12 = 100% aprovação, PF melhor, sem reset fees.**

**Atenção (não é melhoria, é risco a gerenciar):**
3. **Consistência 50%** — ~40% das aprovações concentram lucro em 1 dia. Pode travar
   saque na Apex 4.0. Avaliar cap de lucro diário no próximo backtest.
4. **DD real** — confirmar no dashboard se é $1.000 (EOD) ou $1.500 (Intraday). Muda
   a expectativa de 57% pra 100%.

**Não vale:**
5. **News filter** (já rejeitado). **MCL/ORB** = backlog (estratégia/dados novos).

---

## 💡 Item #12 — Trava de lucro por horário (registrado 13/08)

**Origem:** forward test 1min, dia 04/06/2026 (`forward-test-replay-25k/2026-06-1min/dia-04-04-06.md`).
O bot abriu o dia com uma loss de -$124, emendou 3 gains e chegou a -$0,5 (praticamente zerou o
prejuízo) — e aí o **último trade do dia** foi outro stop cheio (-$131), devolvendo toda a
recuperação. Resultado: dia que "deveria" ter fechado neutro/positivo fechou em -$131,5.

**Confirmado de novo no dia 08/06** (`dia-08-08-06.md`): bot chegou a +$120,5 no meio do dia, e o
**último trade** (13:11) foi um stop cheio de -$130,5, fechando o dia em -$10.

**Terceira confirmação no dia 11/06** (`dia-11-11-06.md`): pico intraday de +$23,5 (após trade 4),
e o **último trade do dia** (15:56) foi outro stop cheio de -$105, fechando em -$81,5.

**Quarta confirmação no dia 18/06** (`dia-18-18-06.md`) — o caso mais limpo até agora: 4 trades
seguidos de ganho (+$34, +$33,5, +$36,5, +$30,5, pico +$134,5) e o **último trade do dia** foi um
stop cheio de -$134,5, fechando o dia em **exatamente $0,00**. Um dia que valeria quase 9% da meta
sozinho fechou zerado.

**4 de 4 dias com recuperação/lucro no meio do pregão acabaram devolvendo tudo no último trade** —
já não é mais coincidência isolada, é um padrão recorrente. Reforça bastante a prioridade de validar
essa trava por backtest assim que o mês inteiro estiver registrado.

**Ideia (Marcelo, 13/08):** dar ao bot noção de **quanto ele já fez no dia + que horas são**. Perto
do fim da janela de operação, se ele já tiver recuperado um dia ruim (voltou perto de $0) ou já
estiver no lucro, **parar de abrir novas entradas** — trava o resultado em vez de arriscar o último
trade devolver tudo.

**O que precisa pra implementar (esboço, NÃO implementado ainda):**
- O bot já rastreia PnL acumulado do dia (usa isso pro `StopDiário $750`) — a infra de "saber
  quanto já fez" já existe, é só reaproveitar.
- Precisa de: (1) um horário de corte configurável (ex.: últimos 30-60min antes do `Flatten`), (2)
  uma condição de "dia já está bom" (ex.: `PnLDoDia >= 0` ou `PnLDoDia >= algumX`), (3) um toggle
  pra ligar/desligar (`TravarLucroPertoDoFechamento`, default OFF até validar).
- Trades já abertos continuam sendo geridos normalmente (BE/trailing/stop) — a trava é só pra
  **novas entradas**, não fecha posição aberta.

**Perguntas em aberto antes de codar:**
- Qual o horário de corte ideal? Testar algumas janelas (ex.: últimos 30min, 45min, 60min) no
  backtest e comparar aprovação/PF.
- "Já recuperado" = voltar a $0, ou nunca ter ficado negativo, ou já estar acima de algum valor
  mínimo (ex.: metade do StopDiário)? Precisa definir o gatilho exato.
- Quantas vezes esse padrão (recupera e devolve no fim) realmente aconteceu no histórico completo
  de backtest? Se for raro, o ganho esperado pode não justificar a complexidade.

**Regra do projeto (não pular):** só vai pra produção depois de rodar em `backtest/` e comparar
aprovação/PF com e sem a trava — mesma regra de todas as outras melhorias desta lista. Nenhuma
mudança de comportamento em produção sem backtest + confirmação explícita do Marcelo.

---

## 💡 Itens #14-16 — BE-lock validado + duas tentativas de atacar ganho/perda direto na gestão (registrado 20/08)

**Contexto:** depois do Δ +$122,5 confirmado do BE-lock 0,75 em Replay (item #14), o Marcelo pediu
pra achar formas de subir o ganho médio por trade E diminuir o tamanho das perdas — sem ficar só
em filtro de entrada (item extra abaixo, dist_nivel/sexta, também testados e rejeitados no mesmo
dia). Rodado em `backtest/run_gestao_saida_sweep.py` (motor de aprovação completo: DD real $1000,
MaxTradesDia=12, slippage 2 ticks, nível de domingo — 300k barras de 1min, ano inteiro + OOS
1ª/2ª metade).

### #15 — Saída parcial 4+1 em alvos menores que 20pt

Hipótese: já que o alvo de 20pt nunca disparou em ~20 dias de Replay real (MFE mediano dos
vencedores no backtest é só 12,5pt), um alvo menor deveria disparar de verdade e capturar mais
ganho. **Testado o oposto do esperado:**

| Alvo da parcial | Taxa aprovação | PF | avgW | OOS 1ª\|2ª |
|---|---|---|---|---|
| (sem parcial, só BE-lock 0,75) | 71% | 1,43 | $95 | 67%\|75% |
| 5pt | 5% | 0,73 | $26 | 0%\|20% |
| 8pt | 17% | 0,94 | $39 | 0%\|20% |
| 10pt | 27% | 1,04 | $47 | 17%\|33% |
| 12,5pt | 39% | 1,12 | $55 | 38%\|40% |
| 15pt | 47% | 1,19 | $63 | — |
| 20pt (o valor já em teste) | 63% | 1,29 | $74 | — |

Quanto menor o alvo, pior — monotônico, confirmado nas duas metades do ano. **Causa raiz:** o
mecanismo fecha 4 contratos no lucro parcial mas o 1 que sobra continua exposto ao stop
**completo** de 12,5pt. Em alvos baixos, dispara em trades que só tiveram favor passageiro e
reverteram pra loss de qualquer forma — trava um lucro pequeno em 4 contratos, mas ainda leva o
stop cheio no 1 restante (o `avgL` fica travado em ~$140 em todo cenário, só o `avgW` desaba).
**Achado extra relevante:** mesmo o alvo de 20pt (o que já está no experimento) fica abaixo do
"só BE-lock" (63% vs 71%) nesse motor de barra — reforça que ele não tem ajudado nem atrapalhado
no Replay real só porque nunca disparou, não porque seria neutro se disparasse.

**Status: REJEITADO.** Não mudar o alvo da parcial. Considerar até desligar `UsarSaidaParcial` no
experimento, já que o motor de barra sugere que ela piora se algum dia disparar.

### #16 — Corte de perda antecipado (loss-cut)

Hipótese nova: cortar 2 dos 5 contratos se o preço for contra em X pontos **sem nunca ter
favorecido o suficiente pra ativar o BE** — reduziria o tamanho em $ dos "loss cheios imediatos"
sem mexer nos trades que já mostraram algum sinal de vida.

| Corte em | Taxa aprovação | PF | WR | avgL | OOS 1ª\|2ª |
|---|---|---|---|---|---|
| (sem corte) | 70% | 1,41 | 68% | $140 | 62%\|75% |
| 4pt | 28% | 1,05 | 47% | $65 | — |
| 6pt | 40% | 1,12 | 51% | $78 | 43%\|42% |
| 8pt | 47% | 1,20 | 56% | $92 | 50%\|50% |
| 10pt | 60% | 1,30 | 61% | $110 | — |

O `avgL` cai como esperado, mas o **WR desaba junto** (68%→47-61%) — confirma nos dados reais a
preocupação já levantada no diagnóstico: **10,7% dos vencedores tocam até -12,5pt de MAE antes de
reverter pra cima.** Cortar cedo baseado só em "foi contra X pontos sem favor" pega esses futuros
vencedores também, travando perda garantida em 2 contratos de trades que iriam virar lucro nos 5.
Confirmado nas duas metades do ano (não é ruído).

**Status: REJEITADO.** Não implementar.

### Leitura geral dos dois

Mesmo problema estrutural nos dois lados: **MFE e MAE de vencedores e perdedores se sobrepõem
demais** pra dar pra distinguir "vai reverter" de "vai continuar" olhando só o movimento parcial
do trade. Qualquer decisão antecipada (trava ganho ou corta perda) erra pros dois lados. Reforça
o veredito da auditoria de 18/08: o teto está no formato do payoff da estratégia base, não em
parâmetro de gestão de saída — já foram tentados SL maior/menor, trailing maior, parcial em vários
tamanhos, corte de perda, BE-lock em várias frações. Só o BE-lock 0,75 sobrou como melhoria real,
e é pequena.

### Extra do mesmo dia — filtros de entrada por qualidade (dist_nivel / sexta-feira)

Diagnóstico (`backtest/diagnostico_mfe_mae_trades.csv`, 1.091 trades, robusto nas duas metades do
ano): trades com `dist_nivel < 5pt` têm WR 73% vs 62% em `10-15pt`; sexta-feira tem WR ~74% vs
~67% no resto da semana (independente do dist_nivel). **Como FILTRO DE CORTE** (só operar
dist<10pt, ou só sexta): rejeitado em `backtest/run_qualidade_entrada_sweep.py` — reduz demais a
frequência de trade, mediana de dias até bater a meta sobe pra 31-85 dias, estourando o prazo real
de 30 dias do produto Apex. **Como SIZING SELETIVO** (manter todos os trades, só aumentar
contratos nos de qualidade): testado em `backtest/run_sizing_seletivo_sweep.py` — boost por
`dist_nivel` piora muito (critério comum demais, ~metade dos trades, só aumenta variância: taxa
70%→44% no boost de 8 MNQ); boost por sexta fica neutro-a-levemente-positivo mas modesto e OOS
misto (não é achado forte o suficiente pra implementar). Nenhum dos dois implementado.

---

## ⚖️ Risco jurídico (não é melhoria de código, mas decisão de negócio)

A Apex proíbe automação OFICIALMENTE em toda fase (ver pesquisa). Eval tolera na
prática; PA confisca. Considerar:
- Operar a eval com bot, mas a PA de forma assistida/manual; OU
- Migrar o bot pra prop firm que permite (TopstepX, Tradeify, MyFundedFutures, TPT).
