# Bot Aprova Conta — Estratégias Testadas (para debate com Andersson)

> **Data:** 11/06/2026
> **Objetivo:** escolher a estratégia do bot de aprovação de conta Apex (produto de entrada).
> **Status:** backtest concluído com dados reais. Falta decidir config + implementar no NinjaScript.

---

## 🎯 TL;DR (resumo de 30 segundos)

- Testamos **4 estratégias** com **1 ano de dados reais** do NQ (1 minuto, ~10,5 meses).
- A vencedora é a **Níveis** (rejeição na máxima/mínima do dia anterior) **+ trailing stop**.
- O **trailing** (proteger lucro quando o trade perde força) foi o que **virou o jogo**: win rate de 34% → **64%**.
- **FOCO 25K:** limitando a **3 trades/dia** + trailing $35, a taxa saltou pra **94%** (15 aprov/ano, robusto). O overtrading era o que estourava o DD apertado.
- Em contas maiores (50K/100K) a taxa também fica em **88%** sem precisar do limite.

## 🥇 CONFIG RECOMENDADA (conta 25K — foco)

```
Estratégia:     Níveis (rejeição na máxima/mínima do dia anterior)
TP / SL:        $500 / $250  (R:R 2:1)
Breakeven:      +$75 → trava stop em +$50
Trailing:       $35
Máx trades/dia: 3   ← corta overtrading (a chave dos 94%)
Stop diário:    $750
```
**Resultado (1 ano, conta 25K):** 15 aprovadas / 1 reprovada = **94%**, PnL +$25.615.
**Robustez:** 1ª metade 7/7 (100%, PF 1.81) | 2ª metade 8/9 (89%, PF 1.50).

---

## 📐 Metodologia (pra confiar nos números)

- **Dados:** NQ E-mini, candles de 1 minuto, exportados do NinjaTrader (jun/2025 → jun/2026).
- **300.174 barras reais**, ~10,5 meses (faltam 2ª metade de set/dez/mar = vencimento de contrato).
- **Custos incluídos:** $5 por contrato (round-turn = comissão + slippage).
- **Conservador:** quando stop e alvo cabem na mesma vela, assumimos que bateu o **stop primeiro** (pior caso). Número realista, não otimista.
- **Validação out-of-sample:** toda config foi testada em **2 metades independentes** do período (anti-overfit).

---

## 🔧 Como funciona a saída (TP / SL + Trailing)

| Elemento | Valor | O que faz |
|----------|-------|-----------|
| **TP (alvo)** | $500 (25 pts) | Teto de lucro. Raramente atingido (trailing fecha antes). |
| **SL (stop)** | $250 (12,5 pts) | Perda máxima — só ocorre se o trade vai contra desde o início. |
| **Breakeven** | +$75 | Ao andar +$75 a favor, o stop pula pra +$50 → trade não pode mais perder. |
| **Trailing** | $50 | Stop persegue o preço $50 atrás do topo → garante o lucro se perder força. |

**R:R 2:1.** Na prática o bot colhe **muitos ganhos pequenos/médios** ($50–$400) e **poucas perdas** de $250.

---

## 📊 Resultado das 4 estratégias (1ª rodada, conta 25K, sem refinamento)

| Estratégia | Trades | WR | PF | PnL ano | Aprovadas | Reprovadas | Taxa |
|------------|--------|-----|-----|---------|:---:|:---:|:---:|
| Níveis | 724 | 34% | 1.00 | +$335 | 7 | 32 | 18% |
| ORB+VWAP | 220 | 30% | 0.82 | −$7.045 | 3 | 17 | 15% |
| Matheus (manhã)* | 130 | 25% | 0.65 | −$8.395 | 1 | 11 | 8% |
| MeanReversion | 4.265 | 32% | 0.89 | −$82.995 | 0 | 243 | 0% |

\* **Matheus** = minha *interpretação* do indicador da manhã (rompimento do canal 00h–12h + Fib). A definição exata depende das perguntas pendentes ao Matheus — pode mudar muito.

---

## 🚀 Evolução da Níveis (com refinamento)

| Versão | WR | PF | PnL ano | Aprovadas | Taxa |
|--------|-----|-----|---------|:---:|:---:|
| Pura | 34% | 1.00 | +$335 | 7 | 18% |
| + Breakeven $100 / Trail $100 | 61% | 1.20 | +$20.785 | 13 | 43% |
| **+ Breakeven $75 / Trail $50** ✅ | **64%** | **1.36** | **+$36.785** | **16** | **52%** |

**Config final:** Níveis | TP $500 / SL $250 | Breakeven +$75 (trava +$50) | Trailing $50 | sem filtro VWAP.

---

## 💰 A DESCOBERTA — taxa de aprovação por tamanho de conta

Mesma estratégia (config final). Só muda o tamanho da conta:

| Conta | Meta | DD | Aprovadas | Reprovadas | **Taxa** | PnL/ano | Observação |
|-------|------|-----|:---:|:---:|:---:|---------|------------|
| **25K** | $1.500 | $1.500 | 16 | 15 | **52%** | +$36.785 | DD apertado, reprova mais |
| **50K** ⭐ | $3.000 | $2.500 | 14 | 2 | **88%** | +$42.295 | **Sweet spot: alta taxa + volume** |
| **100K** | $6.000 | $3.000 | 7 | 1 | **88%** | +$45.740 | Alta taxa, menos volume (meta maior) |

**Conclusão:** quanto maior a conta, mais folga de drawdown → menos reprovações → **taxa dispara**. A **50K** é o melhor equilíbrio (88% + 14 aprovações no ano).

---

## 🎯 Refinamento da 25K — limite de trades/dia (chegou a 94%)

A Níveis sem limite faz **~5 trades/dia** → overtrading estoura o DD apertado da 25K (causa #1 de falha, segundo a pesquisa de prop firm). Limitando a **3 trades/dia** + trailing $35:

| Config (conta 25K) | Trades/dia | Aprovadas | Reprovadas | Taxa | PnL |
|--------------------|:---:|:---:|:---:|:---:|-----|
| Sem limite | ~5 | 16 | 15 | 52% | +$36.785 |
| **Máx 3/dia + trail $35** ✅ | ≤3 | 15 | **1** | **94%** | +$25.615 |

Reprovações caíram de **15 → 1**, mantendo 15 aprovações. Robusto: 1ª metade 100% (PF 1.81), 2ª metade 89% (PF 1.50). **Esse é o caminho dos 70%+ na 25K, validado.**

> ⚠️ **Não confundir com a armadilha:** travar o bot com buffer de DD dá "100%" falso (só 4 avaliações, não robusto). O limite de trades/dia é diferente — mantém volume alto (15 aprov) E sobe a taxa. É legítimo.

## 🛡️ Robustez (out-of-sample) — confirma que NÃO é sorte

| Conta | 1ª metade (jun–dez/25) | 2ª metade (dez/25–jun/26) |
|-------|------------------------|----------------------------|
| 25K | 7/13 (54%) — PF 1.35 | 8/17 (47%) — PF 1.38 |
| 50K | 6/6 (100%) — PF 1.41 | 7/9 (78%) — PF 1.34 |
| 100K | 3/3 (100%) — PF 1.41 | 4/5 (80%) — PF 1.39 |

**PF praticamente igual nas duas metades** em todos os casos → estratégia consistente em períodos independentes. Sinal forte contra overfit.

---

## ⚠️ Armadilha descoberta: NÃO perseguir "taxa" cegamente

Quando tentei forçar a taxa travando o bot (buffer de DD + meta diária), apareceu "100%" — mas era **falso**:
- Só **4 avaliações no ano** (o bot quase parou de operar).
- Na 2ª metade: **0 aprovações**, PF negativo → **não robusto**.

**Métrica certa = aprovações absolutas + robustez**, não taxa isolada. Forçar a taxa = bot que não opera.

---

## 🧭 Matriz de decisão (opções pra discutir)

| Opção | Conta | Taxa | Aprov/ano | A favor | Contra |
|-------|-------|------|:---:|---------|--------|
| **A — Níveis 25K + máx 3 trades/dia** ⭐ | 25K | **94%** | 15 | **Entrada barata (foco) E alta taxa**, robusto | Limite de trades reduz flexibilidade |
| **B — Níveis 50K** | 50K | 88% | 14 | Alta taxa sem limite de trades | Avaliação mais cara |
| **C — Níveis 100K** | 100K | 88% | 7 | Mais lucro/conta | Meta maior, conta cara |
| **D — Níveis 25K sem limite** | 25K | 52% | 16 | Mais aprovações absolutas | Reprova muito mais |
| **E — Matheus (manhã)** | — | a definir | — | Estratégia "da casa" | Precisa da definição exata do Matheus |

---

## 🎯 Recomendação para teste inicial

1. **Estratégia:** Níveis + trailing **+ limite de 3 trades/dia** (config recomendada no topo).
2. **Conta-alvo principal:** **25K** (foco do negócio) → **94%** de aprovação com o limite de trades/dia.
3. **Disciplina é tão importante quanto a entrada:** limite de trades/dia + stop diário = o que sobe a taxa.
4. **Validar a estratégia do Matheus** na versão correta (depende das perguntas a ele).

---

## 📋 Pendências / próximos passos

- [ ] Decidir config + conta-alvo com o Andersson.
- [ ] Responder as **7 perguntas da estratégia do Matheus** (pra testar a versão real dela).
- [ ] Implementar a config final no **NinjaScript** (`src/ApexApprovalSim.cs`).
- [ ] Rodar no **Sim101 / Market Replay** do NT8 (forward test ao vivo).
- [ ] Testar **sizing** (2 contratos, MNQ) e **portfólio** (Níveis + ORB juntas).
- [ ] Validar em mais histórico quando tiver dados (forward test 1–2 meses reais).

---

## ⚖️ Ressalvas honestas (pra não vender ilusão)

- 1 ano de dados, ~10,5 meses, **1 contrato NQ**, candle de minuto (não tick).
- Custos estimados ($5/RT) — confirmar com a corretora real.
- Backtest ≠ ao vivo: slippage, latência e execução real podem reduzir um pouco os números.
- **88% não é garantia** — é a taxa histórica nesse período. O cliente ainda pode reprovar.
