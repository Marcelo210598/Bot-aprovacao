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

## 🔍 Item #17 — Stops cheios com favor quase zero, apontado pelo Marcelo (13/07, registrado 23/08)

**Contexto:** forward test de julho (`forward-test-replay-25k/2026-07-saidaparcial/`), dia
13/07/2026. 2 dos 5 trades do dia (`NIV_L5` e `NIV_L7`, ambos LONG) tomaram **stop cheio -12,5pt**
com favor máximo de apenas **+0,55pt** e **+0,75pt** respectivamente — a entrada foi na direção
certa (sinal de reversão pra cima, vela do gatilho fechou verde), mas o preço reverteu quase
imediatamente após o fill, sem dar tempo de qualquer gestão de saída (BE/trailing) agir.

**Ainda NÃO investigado** (só documentado por enquanto, ver `2026-07-saidaparcial/dia-13-13-07.md`
pros dois casos completos). Diferença do padrão "stop cheio normal" já visto em outros dias (ex.
08/07 `NIV_L14`, fav chegou a 14pt antes de reverter) — aqui o favor nunca saiu do zero.

**Hipóteses a checar antes de qualquer mudança** (regra do projeto: backtest com motor de
aprovação real antes de mexer em produção):
- Se é um padrão recorrente no backtest histórico (não só acaso de 2 trades) — rodar um sweep
  tipo "favor máximo < 1pt antes do stop cheio" nos ~1.400 trades do backtest de 13 meses e ver
  se a frequência/PnL desse subgrupo já está capturada, ou se há algo sistemático no timing do
  gatilho de entrada.
- Conferir se o fill de entrada (preço real reportado) está vindo tarde em relação ao toque na
  linha — se a entrada só sai depois que o preço já começou a reverter, dist_nivel pequeno na
  vela de sinal pode ser um fator (ambos os casos tinham H bem perto da linha: dist 11,50pt e
  8,50pt, não é caso extremo).
- Ainda não há sinal de bug de código — pode ser característica normal do mercado (reversão em V
  que o próprio SL de 12,5pt existe pra limitar). Precisa de mais amostra pra distinguir "só
  aconteceu 2x" de "padrão real".

### ✅ INVESTIGADO (01/09) — é padrão real, mas SEM FILTRO possível

**Gatilho:** o forward test de JULHO/2026 (agora com o BETrigger25, pasta
`forward-test-replay-25k/2026-07-betrigger25/`) mostrou o padrão de novo, 3 vezes em 2 dias:
02/07 `NIV_L10` (fav +0,75pt, −$169), 06/07 `NIV_S4` (fav +0,8pt, −$148) e `NIV_S5` (fav +0,85pt,
−$122). Juntos = −$439 dos −$363,5 do mês até 06/07. **Sem esses 3, o mês estaria +$75.**

**Análise no backtest de 13 meses** (`backtest/diagnostico_mfe_mae_trades.csv`, 1.091 trades):
- **70 trades "facada"** (SL, BE nunca ativou, MFE < 1pt) em 13 meses = **~5-6/mês**, **−$131 de
  média**, **−$9.170 no total**. Sumir com todos → PnL de 13 meses $33k → $42k.
- **Não há NENHUM sinal pré-entrada que os distinga dos trades bons:**
  - `dist_nivel` mediano: 5,2pt (facada) vs 5,0pt (resto) — idêntico
  - `gap_entrada`: 0,00 vs 0,00 — idêntico
  - hora, dia da semana: mesma distribuição
  - espalhados por TODAS as faixas de `dist_nivel` (0-3 / 3-6 / 6-10 / 10-15pt), proporcional ao
    volume — nenhuma faixa é "segura"
  - **duração mediana = 0 barras** → o trade morre na própria vela de entrada (reversão em V
    instantânea, o bot não tem como ver vindo)
- **Loss-cut já foi testado e rejeitado (item #16):** 10,7% dos VENCEDORES também tocam −12,5pt
  de MAE antes de virar pra lucro — cortar cedo mata esses junto (WR 68%→47-61%).

**Veredito:** a facada é característica do mercado (reversão em V), não bug nem parâmetro errado.
O SL de 12,5pt EXISTE pra capar exatamente isso — o edge da estratégia (PF 1,3-1,4, WR 68%) já
conta com ~6% dos trades sendo facada. **Não tem filtro.** O que impede a facada de ESTOURAR a
conta não é gestão de entrada/saída — é o **DD estático** (absorve 2-3 facadas num dia ruim como
o 06/07 desde que não vá −$1.000 do saldo inicial). Mais um motivo pra firma de DD estático.

**Ficam no watch 2 variações de EXECUÇÃO (não da estratégia), vistas no forward test de julho:**

1. **Fill do `TrailingTick` sai 2-3pt pior que o gerenciado** (06/07 NIV_S1/S3, 08/07 NIV_L13 —
   "a vela foi a favor e mesmo assim deu loss pequeno", −$5 a −$7 em vez de +$20). O log `<<< SAIDA`
   mostra o nível gerenciado, o `[MeuTrade] PnL` e o marker do gráfico mostram o fill real, 2-3pt
   pior. Em replay 500x é pior que ao vivo. Se persistir na velocidade real, o trailing de 1,75pt
   (calibrado no NQ do NT8) pode estar apertado demais pro atrito.

2. **🆕 Gap de entrada** (08/07 NIV_L14): sinal disparou LONG @ 29211,75, fill real **29221,90 —
   10,15pt pior**. Nos segundos entre o close da vela de sinal e o `OnMarketData` mandar a ordem,
   o preço correu 10pt. O favor "sumiu" no fill (só +2,1pt a partir do preço real → não bateu BE
   → stop cheio −$158). No preço do sinal o trade teria dado +12pt. Aconteceu depois de uma vela
   de sinal violenta (spike de 17pt abaixo da linha + fechamento longe do fundo). É a 2ª hipótese
   deste item ("o fill vem tarde"). **Antes era considerado raríssimo** (item #21 #3: "gap adverso
   >3pt barra-a-barra em 1min = 0-1 trade/ano" no backtest) — mas o backtest preenche no close da
   vela e não modela o gap do `OnMarketData`. **Watch:** se repetir, checar a lógica de entrada do
   `OnMarketData` (pode estar perseguindo o preço em vez de entrar a mercado no 1º tick após o
   sinal).

---

## 🐛 Item #18 — pdHigh/pdLow (nível dia anterior) zera ao reiniciar a estratégia (23/08, NÃO CORRIGIDO)

**Apontado pelo Marcelo:** no dia 21/07/2026 (Market Replay), o painel de níveis mostrou
"Níveis dia anterior: Max (short) (aguardando 1º dia) / Min (long) (aguardando 1º dia)" — mesmo
já tendo vários pregões de forward test rodados antes (14 a 20/07). Achei a causa no código.

**Causa:** `pdHigh`/`pdLow`/`curHigh`/`curLow`/`diaNiveis` (linhas 89-91) são variáveis de
instância sem NENHUMA persistência ou recálculo a partir do histórico de barras. `pdHigh` só é
preenchido na transição de dia (linha 300-306), herdando de `curHigh` — que por sua vez só
acumula enquanto a MESMA instância da estratégia está viva. Toda vez que a estratégia é
desabilitada/reabilitada no gráfico (acontece com frequência ao mexer no Replay — os logs mostram
"Desabilitando estratégia... Permitindo estratégia..." repetidas vezes), essas variáveis voltam a
zero. Se o histórico atualmente carregado no gráfico não reprocessar um pregão anterior completo
antes da nova instância chegar no dia seguinte, `curHigh` nunca acumula esse dia e `pdHigh` nunca
herda nada — fica 0.

**Por que é grave:** `NivelAtivo()` (linha 557-558) retorna `false` quando `pdHigh`/`pdLow` são 0,
e `EntradaNiveis()` (linha 563-566) simplesmente **retorna sem fazer nada** nesse caso — ou seja,
**o bot fica incapaz de dar qualquer entrada no dia inteiro**, silenciosamente, sem nenhum aviso
de erro. Isso só afeta dias que NÃO são segunda-feira (segunda usa `onHigh`/`onLow`, o range do
domingo à noite, que é calculado de forma independente dentro da própria sessão — não depende do
dia anterior).

**Risco pro forward test:** qualquer dia já registrado como "sem entradas" nos arquivos de
`forward-test-replay-25k/2026-07-saidaparcial/` PODE, na verdade, ter sido um dia afetado por
esse bug (nível zerado = zero entradas possíveis) em vez de genuinamente não ter tocado a linha.
Não dá pra distinguir os dois casos sem ter visto a tela na hora.

**Ainda NÃO corrigido** — aguardando o Marcelo confirmar como o dia 21/07 evoluiu (se o
"aguardando" ficou a sessão toda ou só um instante) antes de propor um fix. Ideia de correção (a
validar): recalcular `pdHigh`/`pdLow` varrendo pra trás no histórico de barras já carregado
(`Bars`/`BarsArray`) na inicialização da estratégia, em vez de depender só do acúmulo ao vivo
desde que a instância atual nasceu. Mudança só nos arquivos experimentais
(`BotAprovacao_SaidaParcial*.cs`) — produção (`BotAprovacao.cs`) nunca é tocada sem autorização
explícita, e mesmo essa mudança nos experimentais precisa ser validada e autorizada antes.

---

## 🤖 Item #19 — IA (Claude) como filtro/seletor/gestor, 4 testes (23/08) — TODOS REJEITADOS

**Contexto:** Marcelo pediu pra integrar Claude no bot pra tentar sair dos 50% de aprovação pros
70%. Testados 4 jeitos diferentes de aplicar IA em cima da REV, todos via backtest com o motor de
aprovação real (`run_janela_30d.py`, 30 dias, retry imediato) antes de cogitar qualquer mudança
no NinjaScript. Scripts em `backtest/ia_filtro_entrada.py`, `backtest/ia_seletor_estrategia_diario.py`
e `backtest/ia_gestao_completa.py`.

| # | O que testou | Modelo | Δ vs. baseline (50%) |
|---|---|---|---|
| 1 | Filtro de entrada (IA aceita/recusa cada sinal) | Sonnet 5 | **-19,2pp** (30,8%) |
| 2 | Seletor diário de estratégia, contexto simples (dow + range) | Haiku 4.5 | 0,0pp (neutro) |
| 3 | Seletor diário, contexto RICO (+ desempenho recente 15 pregões) | Haiku 4.5 | **-45,7pp** (4,3%) |
| 4 | Gestão por trade (contratos/trailing/BE-lock decididos na entrada) | Haiku 4.5 | -4,5pp (45,5%) |

**#1 (filtro de entrada):** IA recusou 58% dos sinais com raciocínio coerente (preferia toque
perto da linha, desconfiava do nível de domingo/Globex) — mas qualquer redução de frequência
esbarra no prazo de 30 dias (dias.med subiu de 13d pra 23d). Mesmo padrão já visto no item #12 e
no filtro `dist_nivel`/sexta (seção anterior): **não importa quão bom seja o critério de recusa,
recusar sempre piora nesse formato de avaliação.**

**#2 e #3 (seletor diário):** com contexto pobre (dia da semana + range), a IA manteve REV sozinha
em 100% dos 236 dias — resultado neutro, ela só confirmou o que já sabíamos. Dando contexto mais
rico (desempenho de cada estratégia nos últimos 5-15 pregões), a IA passou a misturar em 156/236
dias — e a conta desmoronou (4,3%). Causa raiz identificada: ORB/ICT disparam MUITO mais vezes
por dia que a REV, então em qualquer janela curta acumulam PnL absoluto maior só por volume, não
por qualidade — a IA (racionalmente, dada a métrica que eu dei) leu isso como "estratégia
superando REV" e adicionou como reserva. **É o mesmo erro de "achado de 1 mês não é regra"** já
documentado no projeto — só que dessa vez a métrica passada pra IA que induziu ao erro, não uma
decisão dela por conta própria.

**#4 (gestão por trade):** IA ajustou contratos/trailing/BE-lock em 24% dos 1.441 trades (reduzia
risco em sinais de nível Globex/dist_nivel grande, mantinha padrão em sinais de qualidade) —
comportamento sensato, mas **não achou edge real**, só trocou o resultado de lugar (-4,5pp).

**Veredito consolidado:** os 4 testes convergem pro mesmo lugar — nenhum bate os 50% do baseline,
a maioria piora. Ou a IA fica neutra (confirma o que já fazíamos) ou piora (cai em armadilha de
ruído de curto prazo, ou reduz frequência de trade demais pro prazo de 30 dias). Reforça a
conclusão da auditoria de 18/08: **o teto de ~50% parece estrutural** (do instrumento, do
timeframe, ou do formato de avaliação de 30 dias), não uma falta de inteligência na decisão de
entrada/saída — uma IA vendo os mesmos números não tem informação que os meses de backtest
quantitativo já não tenham testado.

**Decisão (23/08, Marcelo concordou):** parar de tentar integrar IA por cima da REV. Não
implementado nada em produção nem no NinjaScript — tudo ficou em backtest Python. Se algum dia
retomar essa linha, NÃO repetir os testes #1-3 (já mostrados ruins); #4 é o único com espaço pra
uma tentativa diferente (ex.: contexto de qualidade de sinal mais rico que só dist_nivel/dia).

---

## 🔎 Item #20 — Investigação do "teto de 50%" (23/08) — sem resposta estatística nova, mas conclusão por convergência

**Tentativa:** depois dos 4 testes de IA (item #19) não moverem o número, tentei um bootstrap de
ORDEM — embaralhar cronologicamente a sequência real de trades (REV + BE-lock 0,75, 13 meses) e
ver se a taxa de aprovação mudava muito, pra separar "problema é o payoff em si" de "problema é
como perdas se agrupam no tempo". Script: `backtest/investiga_teto_50.py`.

**Esbarrou numa parede técnica, não só bug:** pra manter fidelidade de drawdown intradiário é
preciso o motor bar-a-bar oficial — mas não dá pra embaralhar barras de preço reais e continuar
fazendo sentido (o preço de amanhã depende do de hoje). A aproximação por PnL-por-dia que tentei
esconde o drawdown intradiário (mesmo tipo de erro do item #19 corrigido, agora na versão "por
dia") e deu um resultado absurdo (100% de aprovação). **Script marcado como abandonado, não usar
os números dele.**

**Conclusão tirada de outra forma — por CONVERGÊNCIA, não por um teste novo:** contando os testes
já feitos com o motor oficial bar-a-bar ao longo do projeto — SL 15pt (pior), 6 tamanhos de saída
parcial (piores), corte de perda antecipado (pior), BE-lock em várias frações (só 0,75 ajuda, e
pouco), filtro/sizing por `dist_nivel`/sexta (neutro a fraco), ORB/EMAV/ICT sozinhas ou mescladas
(nenhuma supera), e os 4 testes de IA de hoje (item #19, todos neutros ou piores) — são **~15
ângulos de ataque independentes, todos convergindo pro mesmo teto de ~50%.** Essa convergência é
a evidência disponível: não é "ainda não achamos o parâmetro certo", é o formato dessa estratégia
nesse instrumento (MNQ) nesse timeframe (1min) sob essas regras de avaliação (Apex 30d/$1500/
$1000 DD).

## 🧭 DECISÃO ESTRATÉGICA EM ABERTO (23/08) — Marcelo decide numa próxima sessão

Duas direções, sem escolha feita ainda:

1. **Aceitar ~50% e escalar operação** — tratar como taxa de conversão de um funil de negócio,
   rodar várias avaliações em paralelo. Não precisa de mais código/pesquisa, precisa de
   capital/estrutura operacional.
2. **Repensar do zero** — outro instrumento (ex.: ES/MES em vez de NQ/MNQ), outro timeframe, ou
   uma hipótese de estratégia genuinamente diferente (não uma variação da reversão atual). Isso é
   um projeto novo: nova coleta de dados, nova hipótese, toda a validação de novo — semanas, não
   uma sessão.

Nenhuma ação de código pendente até essa decisão ser tomada.

---

## ✅ Item #21 — Gatilho de breakeven mais baixo (2,5pt) — VALIDADO, indo pro Replay (23/08)

**Contexto:** Marcelo pediu uma análise externa das melhorias possíveis pro `BotAprovacao.cs`
(cooldown, filtro de gap de abertura, mitigação de gap de entrada, BE trigger configurável, log de
PnL, kill switch). #1/#2/#6 (cooldown, filtro de gap, kill switch) são a mesma família já rejeitada
no item #12 — não retestados, ficam fora até surgir evidência nova. #3 (gap de entrada) e #4 (BE
trigger) foram testados em backtest Python (`backtest/testa_gap_e_be_trigger.py`).

**#3 — Mitigação do gap de entrada: REJEITADO.** Precisou de um motor próprio (fill na abertura da
barra seguinte, já que o motor oficial preenche no close da própria barra do sinal e não representa
gap nenhum). Achados: (a) gap adverso >3pt de barra-a-barra em 1min é raríssimo (0-1 trade/ano) —
o filtro de rejeição não tem o que filtrar nesse timeframe; (b) ordem Limit no nível piora (47,8%
vs. 54,5% baseline) — 31 trades/ano não enchem, perda de frequência de novo esbarra no prazo de 30
dias. Números dessa seção não comparáveis aos 50% oficiais (baseline diferente, ver aviso no topo
do script).

**#4 — Gatilho de breakeven mais baixo: VALIDADO.** Testado no motor OFICIAL
(`run_janela_30d.py`, comparável direto aos 50% documentados), com BE-lock proporcional 0,75
mantido (só muda QUANDO o breakeven aciona, não a fração travada):

| Gatilho BE | Ano inteiro | 1ª metade (jun-dez/25) | 2ª metade (dez/25-jun/26) |
|---|---|---|---|
| 3,75pt (atual) | 50,0% | 60,0% | 42,9% |
| 3,0pt | 57,1% | 66,7% | 50,0% |
| **2,5pt** | **59,1%** | **70,0%** | 50,0% |

Melhora nas duas metades do ano — **não é achado de período único**, confirmado OOS. É o maior
ganho isolado encontrado no projeto até agora (mais que qualquer variação de saída parcial,
sizing, filtro de entrada, ou os 4 testes de IA de hoje, item #19).

**Ação tomada:** criada cópia experimental `src/BotAprovacao_BETrigger25.cs` (derivada de
`BotAprovacao_SaidaParcial.cs`, só muda `BreakevenTrigPontos` de 3,75 pra 2,5 — resto idêntico:
BE-lock proporcional 0,75 ligado, saída parcial desligada). Arquivo de PnL diário próprio
(`BotAprovacao_BETrigger25_pnl_diario.txt`), não colide com os outros experimentais. Produção
(`BotAprovacao.cs`) e o `BotAprovacao_SaidaParcial.cs` que já roda o forward test de julho **não
foram tocados**. Próximo passo: Marcelo testa no Market Replay antes de cogitar produção.

**#5 (log de PnL do trade) — ainda não implementado**, sem risco, fica pra quando for conveniente.

### Atualização 23/08 (mesmo dia) — forward test dos 4 primeiros dias mostrou piora, mecanismo investigado

Marcelo rodou `BotAprovacao_BETrigger25.cs` nos dias 01-04/06/2026 e viu piora clara (+$45,0
contra +$432,5 da config atual, -$387,5). Investigação trade a trade (dataset inteiro, 1.422
trades pareados, `backtest/compara_be_trigger.py`): 1.290 trades idênticos, **46 trades
melhoraram** (loss cheio virou pequeno, Δ médio +$147,1 — raro mas grande), **86 trades
pioraram** (ganho cortado cedo, Δ médio -$50,0 — comum mas pequeno). Líquido ano inteiro: +$2.462
(bate com os +9,1pp do backtest formal). **Achado extra: quebra mês a mês mostra 9 de 13 meses
melhorando, só 4 piorando — e os DOIS junhos do dataset (2025 e 2026) estão entre os que
pioram.** Ou seja, Marcelo testou justamente no mês historicamente pior pra esse achado (junho é
mais "trendy", favorece o custo do gatilho baixo mais que o benefício). Recomendação: continuar o
forward test passando de junho, sem abandonar — ver `forward-test-replay-25k/2026-06-betrigger25/
placar-mes.md` pra detalhe completo.

### Atualização 23/08 (mesmo dia) — Marcelo pediu "mais trades", 2 alavancas testadas

Motivo: aprovar mais rápido reduz tempo de exposição a risco. Testadas duas formas de aumentar
frequência sem trocar de estratégia nem aumentar tamanho de posição (tamanho maior já foi testado
e piora — ver abaixo):

- **TolToqueTicks mais solto** (25/30/40 ticks em vez de 20): **PIOROU** (54,2-54,5% vs 59,1% com
  BE trig 2,5). Apertar (10 ticks) na verdade MELHOROU (63,2%) — direção oposta à esperada. Não
  mexido, fica 20 ticks.
- **MaxDistPontos mais largo** (20pt em vez de 15pt), combinado com BE trig 2,5: **59,1% -> 64,0%
  no ano inteiro, melhora nas DUAS metades OOS** (70%->80%, 50%->53,3%) — achado robusto. Aplicado
  direto no `BotAprovacao_BETrigger25.cs` (mesmo arquivo do item anterior, não criou arquivo novo).

**Tamanho de posição (contratos) testado e REJEITADO como forma de acelerar aprovação:** sweep de
3 a 10 contratos mostra que aumentar SEMPRE piora a taxa (10 contratos: 9,0%, pior resultado do
projeto inteiro). Motivo matemático: meta ($1.500) e DD ($1.000) são fixos em dólar (não escalam
com o tamanho), então aumentar contratos aproxima o resultado de "moeda ao ar" em vez de deixar o
edge real se manifestar. 4 contratos parecia melhor no ano inteiro mas não passou no teste OOS
(ruído de amostra pequena).

**Config atual do `BotAprovacao_BETrigger25.cs`:** `BreakevenTrigPontos=2,5` + `MaxDistPontos=20`
+ BE-lock proporcional 0,75 + saída parcial off. Resto idêntico à produção. Aguardando forward
test no Replay pra confirmar fora do backtest.

---

## 🧪 Item #22 — Direção B destrinchada: Renko, modelos de DD, outros instrumentos (01/09/2026)

**Contexto:** decisão estratégica em aberto desde 23/08 (aceitar ~50% e escalar vs. repensar do
zero). Marcelo pediu (1) testar Renko + MA "do mesmo jeito que testamos hoje" (avaliação de 30
dias), (2) varrer as outras possibilidades da direção B. Scripts: `backtest/renko.py`,
`backtest/run_renko_30d.py`, `backtest/run_renko_fair.py`, `backtest/run_direcaoB_scan.py`,
`backtest/carrega_databento.py`, `backtest/run_instrumento_scan.py`. Dado novo: Databento
GLBX.MDP3 OHLCV-1m de MES/MNQ/M2K/MYM, front-month contínuo, mesmo período do `NQ_dados/`
(jun/25→jun/26). Custo Databento: **US$ 7,60** dos US$ 125 de crédito grátis. Motor de aprovação
idêntico ao resto do projeto (janela 30d corridos, DD $1000, Max12/dia, slippage 2 ticks).

### 22a — RENKO + Média Móvel — ❌ SEM EDGE

Tijolo de Renko reconstruído das barras de 1min (não temos tick de 13 meses — modelo de caminho
intrabar pessimista, conservador pra estratégia de tendência). Varrido: brick 10–30pt, MA 5–20,
gate de 3 tijolos, saída no cruzamento contrário da MA, gestão de tendência (stop 1–3 tijolos,
trailing por tijolo, alvo fixo).

| Renko + MA | Melhor resultado |
|---|---|
| Gestão da reversão (SL 12,5/trail 1,75) | 48% (brick20/ma10), pior que REV 55%, 16 estouros vs 6 |
| Gestão de tendência (stop N tijolos, saída nativa) | **0% em TODA config** — PF 0,77–0,97 (perde no bruto) |
| Mesclado com a REV, nos dias em que a REV fica muda | Renko opera 400–640×/ano e **perde $5k–$23k** nesses dias |
| OOS mescla (gestão reversão) | 67% / 42% — miragem de 1 metade |

MA-cross em tijolo de Renko no NQ é isca de chop. Os dias que a REV não pega não têm tendência
sobrando — têm ausência de estrutura, exatamente onde um sistema de MA em Renko sangra mais.
**Não implementar. Não retestar sem dado de tick E uma hipótese diferente de MA-cross.**

### 22b — MODELOS DE DRAWDOWN — 🟡 a maior alavanca estrutural achada

Mesma reversão, mesma conta, só mudando COMO o DD funciona (`run_direcaoB_scan.py`, NQ NT8):

| Modelo de DD | Taxa | Estouros |
|---|---|---|
| Apex trailing intradiário (conta lucro aberto) | 55% | 6/20 |
| EOD trailing (pico só no fim do dia) | 55% | 5/20 |
| **Static (limite fixo desde o início, nunca sobe)** | **60%** | **0/15** |

O DD trailing intradiário é o que fabrica o risco de estouro. Com DD estático de $1.000 a
estratégia **nunca estoura** — ou aprova (60%) ou só expira o prazo. Você para de pagar reset fee.
Firmas com opção de DD estático **e que permitem bot**: Tradeify, MyFundedFutures (Expert), Take
Profit Trader. **Ação: confirmar termos (automação + DD estático + preço de conta ~25K).**
Conta Apex MAIOR (50K/100K) NÃO resolve — o relógio de 30 dias trava (50K/14MNQ ≈ 59%, OOS
frágil; 100K+ ≈ 0%, alvo inalcançável no prazo).

### 22c — 2º SINAL: fade do range overnight (Globex) durante o RTH — 🟡 empata sozinho, ajuda no merge

Mesma mecânica da reversão, mas usando o extremo do range do Globex em vez da máx/mín RTH de
ontem. Sozinho: 52% (WR 67%, PF 1,37) — empata a REV. Mesclado (REV+ON): opera ~40% mais dias,
menos expirações. **REV+ON sob DD estático (NQ NT8): 75%, OOS 82%/69%** — 1ª coisa no projeto que
passa dos ~55% com OOS que não é miragem de uma metade (mas o ganho vem quase todo do DD
estático, não do sinal). Nunca foi forward-testado.

### 22d — OUTROS INSTRUMENTOS (dado real Databento) — MES/M2K ❌, MYM 🟡 frágil

`run_instrumento_scan.py`, sweep de ~108 configs de gestão proporcional ao range de cada
instrumento, tick REAL por instrumento (crítico pro slippage: MYM tick = 1pt Dow, não 0,25).
Validação: MNQ-databento reproduz o edge da REV (WR 67%, PF 1,28 ≈ NT8).

| Instrumento | PF máx no grid | Melhor taxa | Leitura |
|---|---|---|---|
| **MES** (Micro S&P) | **0,80** | 8% | ❌ sem edge — o S&P atravessa os níveis do dia anterior, não rejeita. WR 63% mas ganhos minúsculos |
| **M2K** (Micro Russell) | **0,85** | 5% | ❌ sem edge — small caps rompem o nível (momentum), não fazem fade. WR 69% mas PF <1 |
| **MYM** (Micro Dow) | **1,19** (slip 2t) | 33–43% | 🟡 único com edge, mas frágil a slippage |

MYM detalhado (sensibilidade a slippage, o teste que matou noturna/SL15):

| Slippage/fill | Taxa (8c static) | PF | OOS |
|---|---|---|---|
| 1 tick (1pt Dow, spread típico) | 62% | **1,44** | 38%/56% |
| 2 ticks (2pt, conservador) | 43% | 1,18 | 12%/36% |
| 3 ticks (3pt) | 18% | 0,94 | 0%/10% |

MYM tem o MESMO edge do NQ com fill bom (PF 1,44 ≈ NQ 1,41), fica marginal com fill conservador,
morre com fill ruim. WR 76% (> NQ 68%) e **quase não estoura** (o Dow não dá spike contra você
como o Nasdaq) — a propriedade que a direção B procurava. Mas só um forward test ao vivo resolve
se o fill real do MYM aguenta. `REV+ON` no MYM sob DD estático: ~41% (slip 2t) / melhor com fill
bom.

### 22e — ROMPIMENTO (breakout) — nos 4 instrumentos + como complemento da reversão (01/09, 2ª rodada)

Pergunta do Marcelo: só testei a reversão nos outros instrumentos. E rompimento? E se o preço
NÃO reverte e ROMPE — vale um breakout pra completar? `backtest/run_break_instr.py`: rompimento
da máx/mín do dia anterior (o inverso da atual) + ORB + os dois juntos (fade quando rejeita,
break quando rompe), com gestão de TENDÊNCIA (stop largo, deixa correr), motor de 30d, tick real.

| | NQ | MNQ | MES | M2K | MYM |
|---|---|---|---|---|---|
| BREAK (PF, gestão tendência) | **1,12** | **1,06** | 0,81 ❌ | 0,88 ❌ | 1,00 ❌ |
| BREAK taxa (5c, DD estático) | 40% | 42% | 7% | 0% | 34% |
| **FADE sozinho (ref, 5c estático)** | **59%/PF1,43** | **68%/PF1,36** | 0% | 0% | ~40% (fill 2t) |
| FADE+BREAK juntos (5c estático) | 52%/PF1,13 | 47%/PF1,07 | 7% | 5% | 29% |
| ORB (opening range breakout) | 14% | 9% | 2% | 3% | 4% |

**Achados:**
- **Rompimento tem edge FRACO só no Nasdaq** (PF ~1,1 — cerca de 1/3 da força da reversão, PF
  ~1,4). Nos outros instrumentos: morto (MES/M2K PF <0,9; MYM PF exatamente 1,00 — o Dow reverte,
  não rompe).
- **M2K/Russell mata a hipótese "se não faz fade, faz break":** nem fade (PF 0,60) nem break (PF
  0,88) funcionam no Russell no nível do dia anterior — o preço só pica em volta e as duas
  direções perdem.
- **Juntar fade + break NÃO ajuda — PIORA.** FADE+BREAK (NQ 52%/PF1,13) fica ABAIXO do FADE
  sozinho (NQ 59%/PF1,43). Os trades de rompimento diluem o edge forte da reversão com o edge
  fraco deles. É a MESMA parede do item #19/#20: não dá pra saber no setup se vai reverter ou
  romper — adicionar o sinal de break só adiciona ruído. (Bater contratos piora tudo, igual à
  reversão.)
- **ORB: morto em TODOS os 5 instrumentos** (PF 0,75–1,29, quase todos <1) — confirma o achado do
  NQ (revisão de 12/08) e estende pros outros índices.
- Detalhe: rompimento sob DD trailing (Apex) estoura MUITO (60–90 busts/ano) — só o DD estático
  o torna operável, e mesmo assim fica em ~40%.

**Veredito 22e:** rompimento não é o complemento que faltava. Sozinho é fraco (Nasdaq) ou morto
(resto). Combinado com a reversão, atrapalha. ORB confirmado morto em todo lugar.

### 22g — MNQ + MYM na MESMA CONTA (agregar o MYM ao BETrigger25) — ❌ não ajuda (01/09, 3ª rodada)

Pergunta do Marcelo: dá pra agregar o MYM ao BETrigger25 (MNQ) e testar junto?
`backtest/run_mnq_mym_junto.py` — dois bots de reversão (um MNQ, um MYM), MESMA conta (P&L / DD /
stop diário / dias / meta compartilhados), motor de aprovação de 30d.

| Config (5c cada, DD estático) | Taxa | ap/es/ex | OOS 1ª/2ª | net |
|---|---|---|---|---|
| **MNQ sozinho** (params BETrigger25: BE 2,5 + MaxDist 20) | **75%** | 15a/1e/4x | **62%/69%** | +$28k |
| MYM sozinho | 23% | 3a/2e/8x | 0%/33% | +$3k |
| MNQ + MYM juntos | 73% | 16a/3e/3x | 56%/91% | +$25k |

- **Juntar MYM NÃO ajuda.** Empata a taxa (73% vs 75%), mais estouros (3 vs 1), menos PnL, e OOS
  mais instável (56/91 vs 62/69). O MYM dilui em vez de somar.
- **Causa:** MNQ e MYM são ~0,85–0,9 correlacionados (Nasdaq × Dow). Quando o Nasdaq reverte
  limpo no nível, o Dow geralmente também (trade redundante); quando o Nasdaq rompe e estoura o
  stop, o Dow geralmente também (perda em dobro). É **dobrar a mesma aposta**, não diversificar.
  Mesma parede do item #22e (fade + break) e #19/#20.
- **Achado colateral RELEVANTE:** os params do BETrigger25 (BE trig 2,5 + MaxDist 20) no dado
  INDEPENDENTE do Databento levam o MNQ de 43% → **62% (intradiário) / 75% (estático)** — 
  confirmação forte do edge do BETrigger25 num dado que não é o do NT8, apesar do forward test
  curto ter deixado o Marcelo insatisfeito.

**Veredito 22g:** as 2 alavancas da direção B **são separáveis**, e só uma vale:
- **Lever 1 (firma de DD estático):** NÃO é código — aplica ao BETrigger25 (MNQ) como está, só
  trocar de conta. E AJUDA muito (62% → 75%).
- **Lever 2 (MYM):** não soma nada em cima do MNQ. O bot `BotAprovacaoDow_MYM.cs` fica como
  experimento standalone opcional, não como prioridade.
- **Caminho recomendado:** `BotAprovacao_BETrigger25.cs` (que o Marcelo já tem e já forward-testou
  parcialmente) numa firma de DD estático. Simples, e é o número mais alto.

### 22f — VEREDITO DA DIREÇÃO B

- **Trocar de instrumento é quase um beco:** MES e M2K não têm edge (nem fade nem breakout — a
  reversão em nível é fenômeno de Nasdaq/Dow, não de S&P/Russell). MYM é o único com pulso e não é
  claramente melhor que o NQ — "edge parecido, menos risco de explodir, mas depende de fill bom".
- **Rompimento não completa a reversão** (22e): fraco sozinho (só Nasdaq, PF ~1,1), morto no
  resto, e combinado com a reversão PIORA (dilui o edge forte). ORB morto em todo instrumento.
- **A alavanca real da direção B é o FORMATO, não a estratégia nem o instrumento:** firma com DD
  estático (para de estourar) + o merge com o fade overnight. Aplica ao NQ atual E ao MYM.
- Renko: fechado. Rompimento/ORB: fechados.
- **Próximos passos concretos:** (1) Marcelo levanta termos de Tradeify/MFFU (automação + DD
  estático + preço); (2) se quiser perseguir o MYM, forward test no Market Replay (mesmo processo
  da diurna) medindo o fill real; (3) o merge REV+fade-overnight precisa de `.cs` + forward test
  antes de qualquer coisa. Nada foi mexido em produção nem nos `.cs`.

---

## ⚖️ Risco jurídico (não é melhoria de código, mas decisão de negócio)

A Apex proíbe automação OFICIALMENTE em toda fase (ver pesquisa). Eval tolera na
prática; PA confisca. Considerar:
- Operar a eval com bot, mas a PA de forma assistida/manual; OU
- Migrar o bot pra prop firm que permite (TopstepX, Tradeify, MyFundedFutures, TPT).
