# 🎯 Gestão do dia + SL — veredito (13/08/2026)

> **Contexto:** o forward test de junho/2026 no 1min fechou em **+$168** (11,2% da meta), quase
> empatado com o 5min que já tinha sido descartado. Analisamos os 73 trades reais do mês e
> levantamos hipóteses de melhoria. Este doc registra o que foi testado no backtest de 13 meses
> (300.174 barras, engine de produção DOM-NOITE) e o veredito de cada uma.
>
> Script: `backtest/run_gestao_dia.py`

---

## ⚠️ Antes de tudo: 3 hipóteses já estavam mortas

A análise do mês real sugeriu atacar a assimetria (arrisca 12,5pt pra ganhar ~4pt). As três
saídas óbvias **já tinham sido testadas e rejeitadas** — só descobrimos ao ler os docs:

| Hipótese | Já testado em | Veredito |
|---|---|---|
| Reduzir o stop (12,5 → 6-8pt) | 18/06, `run_stop_sweep.py` | ❌ **Apertar PIORA** — WR despenca. O caminho é o oposto: alargar |
| Saída parcial / scale-out | 25/06, `run_saida_parcial.py` | ❌ Pega runner (+$11k) mas perde mais no meio (−$2.876) |
| Trailing mais largo | 25/06, `run_trailing_fino.py` | ❌ Degradação monotônica — 1,75pt é o ótimo |

📌 **Lição:** ler `docs/trailing-veredito.md` e o histórico antes de propor mudança de gestão.

---

## 🔴 Os filtros de gestão do dia — TODOS REJEITADOS

Vieram da análise dos 73 trades de junho, onde pareciam ótimos:
- 1º ao 4º trade do dia: **+$650** | do 5º em diante: **−$519**
- Rajadas (≤5min): **−$306** | espaçados: **+$474**
- Combinando os dois no mês real: +$474 vs +$168 reais (quase 3x)

**No backtest de 13 meses, todos destroem o resultado:**

| Filtro | Taxa aprov. | Trades | PnL | vs base |
|---|---|---|---|---|
| **BASE (sem filtro)** ⭐ | 100% (21/21) | 1.440 | **$38.932** | — |
| max 2 trades/dia | 100% (8/8) | 307 | $13.953 | **−64%** |
| max 3 trades/dia | 100% (10/10) | 441 | $16.634 | **−57%** |
| max 4 trades/dia | 100% (11/11) | 564 | $18.391 | **−53%** |
| max 6 trades/dia | 94% (15/16) | 766 | $24.256 | **−38%** |
| max 8 trades/dia | 100% (17/17) | 934 | $28.108 | **−28%** |
| cooldown 3 min | 100% (17/17) | 992 | $29.963 | **−23%** |
| cooldown 10 min | 100% (15/15) | 707 | $24.228 | **−38%** |
| cooldown 30 min | 100% (10/10) | 467 | $16.643 | **−57%** |
| parar após 1 stop cheio | 100% (10/10) | 433 | $16.102 | **−59%** |

**Por que falham:** todos melhoram o **PF** (1,66 → 1,90-2,11) e o WR — mas cortam volume de
trades, e a estratégia vive de **muitos** lucros pequenos. Menos trades = menos aprovações por
ano e mediana de dias-até-aprovar muito pior (14d → 29-45d). Pra conta Apex o que importa é
aprovação/ano, não PF.

⚠️ **O achado de junho era overfitting puro.** 73 trades de 1 mês contra 1.440 de 13 meses.
O padrão "5º trade em diante é ruim" não existe no dado longo.

---

## ✅ A ÚNICA melhoria que passa: SL 15pt

Já validada em **18/06** (`run_stop_sweep.py`), com decisão registrada de "testar ao vivo" —
**e nunca foi aplicada**. O forward test de junho inteiro rodou com **SL 12,5**.

| | SL 12,5 (atual) | SL 15 | ganho |
|---|---|---|---|
| Taxa de aprovação | 100% (21/21) | 100% (22/22) | +1 aprovação |
| WR | 69% | **74%** | +5pp |
| PF | 1,66 | **1,81** | +9% |
| Mediana dias p/ aprovar | 14d | **13d** | −1d |
| PnL/ano | $38.932 | **$44.242** | **+14%** |

### E o mais importante: melhora MAIS com slippage realista

| Slippage | SL 12,5 | SL 15 | vantagem do SL15 |
|---|---|---|---|
| 0 tick | $38.932 (100%) | $44.242 (100%) | **+14%** |
| 1 tick | $31.682 (100%) | $37.448 (95%) | **+18%** |
| **2 ticks (realista)** | $23.517 (100%) | **$30.997 (94%)** | **+32%** |
| 3 ticks | $15.304 (71%) | $24.386 (81%) | **+59%** |

**A vantagem cresce conforme o atrito de execução aumenta** — exatamente o cenário do mundo real
que derrubou o forward test. Não é artefato de backtest idealizado; é o oposto. Com 3 ticks de
slippage, o SL 12,5 desaba pra 71% de aprovação enquanto o SL 15 segura 81%.

**Razão de fundo:** stop mais largo deixa o trade sobreviver ao ruído e voltar. Com stop apertado,
mais trades morrem em movimentos que teriam se recuperado — e cada trade morto ainda paga slippage.

---

## 📋 Conclusão e próximo passo

1. **Aplicar SL 15pt** — é a única mudança com evidência em 13 meses, OOS (100%/92% no teste de
   18/06) e que melhora sob slippage. Já era decisão de 18/06 que nunca saiu do papel.
2. **Não aplicar nenhum filtro de gestão do dia** (max trades, cooldown, parar após stop) —
   todos comprovadamente piores no dado longo.
3. **Não re-testar** stop menor, saída parcial e trailing largo (ver tabela do topo).
4. O parâmetro de stop já existe no `.cs` — mudança é de configuração no gráfico, não de código.

> ⚠️ **Nada foi alterado em `src/BotAprovacao.cs`.** Este doc é só medição. A decisão de aplicar
> o SL 15 é do Marcelo.
