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

### #7 — DD real $1.000 (não $1.500) — ✅ TESTADO: muda tudo (23/06)
**Descoberta importante:** com o DD real de $1.000 (conta EOD), a diurna cai de
**100% → 57%** de aprovação (13 aprov / 10 busts em 23 ciclos). O backtest com DD
$1.500 era otimista. Stop diário não muda muito (750 vs 1000 = mesma taxa).
- Se a conta do Marcelo tem DD $1.500 (Intraday) → 100% segue valendo.
- Se tem DD $1.000 (EOD) → bot é 57% sozinho; subir pra $50K resolve (100%).
- ⚠️ **CONFIRMAR no dashboard Apex qual é o DD real da conta.**

---

## 🟢 Baixa prioridade (testar com backtest antes)

### #8 — ORB como estratégia complementar
Opening Range Breakout = melhor backtest documentado pela comunidade ($60.924, 2 anos).
Já temos `backtest/optimize_orb.py` e `run_backtest.py` — poderia virar 3ª estratégia
exclusiva 9:30-10:00 ET.

### #9 — MCL (Micro Crude Oil) como alternativa
Apareceu nos backtests ICT com DD de só -$788 (vs -$3.703 do MNQ). Menos volátil.
Vale backtest comparativo.

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

## ⚖️ Risco jurídico (não é melhoria de código, mas decisão de negócio)

A Apex proíbe automação OFICIALMENTE em toda fase (ver pesquisa). Eval tolera na
prática; PA confisca. Considerar:
- Operar a eval com bot, mas a PA de forma assistida/manual; OU
- Migrar o bot pra prop firm que permite (TopstepX, Tradeify, MyFundedFutures, TPT).
