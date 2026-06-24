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

### #4 — MaxTradesDia = 10-12 (hoje = 0/ilimitado) — PENDENTE
Comunidade usa 3-5 trades/dia. Nosso bot tem o parâmetro mas desligado. Limitar
reduz dias de overtrading. Já temos `run_diurna_noturna.py` com varredura maxN —
revisar e escolher o limite.

---

## 🟡 Média prioridade

### #5 — Regra de consistência Apex 4.0 (50%) — VERIFICAR
Nenhum dia pode ser >50% do lucro total acumulado. Se o bot faz $800 num dia e
precisa de $1.500 total, esse dia "gastou" 53% → viola mesmo sem estourar DD.
- Analisar se o padrão de trades respeita isso.

### #6 — Conta $50K em vez de $25K — AVALIAR
Comunidade unânime: $25K tem DLL muito apertado ($500). $50K tem melhor
custo-benefício (DD $2.000, meta $3.000, DLL $1.000).

### #7 — Corrigir DD do backtest ($1.000, não $1.500) — VERIFICAR
A conta $25K Intraday real tem DD=$1.000. Nosso backtest usa $1.500 (otimista).
Rodar de novo com DD=$1.000 pra ver a taxa real de aprovação.

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
| 3 | VPS QuantVPS/FinTechVPS | Baixo | Altíssimo | ⬜ Pendente |
| 4 | MaxTradesDia = 10-12 | Baixo | Médio | ⬜ Pendente |
| 5 | Regra consistência 50% | Médio | Alto | ⬜ Verificar |
| 6 | Conta $50K | Financeiro | Alto | ⬜ Avaliar |
| 7 | DD backtest $1.000 | Baixo | Alto | ⬜ Verificar |
| 8 | ORB complementar | Alto | Incerto | ⬜ Backlog |
| 9 | MCL alternativa | Médio | Incerto | ⬜ Backlog |

---

## ⚖️ Risco jurídico (não é melhoria de código, mas decisão de negócio)

A Apex proíbe automação OFICIALMENTE em toda fase (ver pesquisa). Eval tolera na
prática; PA confisca. Considerar:
- Operar a eval com bot, mas a PA de forma assistida/manual; OU
- Migrar o bot pra prop firm que permite (TopstepX, Tradeify, MyFundedFutures, TPT).
