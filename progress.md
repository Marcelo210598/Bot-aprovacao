# Bot Trade NT8 ("Ping Pong" / Aprova Conta) - Progresso

## Última atualização: 2026-06-13

## 📌 Visão Geral
- **Objetivo:** Bot de trading automatizado para NQ/MNQ no NinjaTrader 8 (NinjaScript C#)
- **Foco atual:** **Bot de APROVAÇÃO de conta Apex** (produto de entrada) → depois upsell do bot de operação
- **Público:** Comunidade Nômade Trader (traders BR, Apex)
- **Stack:** NinjaScript (C#) + backtest em Python (validação)
- **Status:** 🟢 Estratégia ESCOLHIDA e aprovada — partindo p/ implementação no NinjaScript

## 🎯 ESTRATÉGIA ESCOLHIDA (12/06) — 1ª a ser trabalhada
> **Decisão tomada:** rodar o bot de aprovação no **MNQ com 5 micro contratos**, config "94 em 15 dias".
> Escolhida por unir **alta taxa (94%)**, **prazo curto (mediana 15 dias)** e **risco baixo** ($125/trade, buffer DD 12x).

```
Mercado:      MNQ (Micro Nasdaq) — 5 contratos     | risco $125/trade (buffer DD 12x)
Conta:        Apex 25K (meta $1.500 | DD $1.500 | mín. 7 dias)
Entrada:      reversão na máxima/mínima do dia anterior (estratégia "Níveis 94")
Alvo (TP):    60 pontos   ← deixar o ganho correr é o que dá os 15 dias
Stop (SL):    12,5 pontos
Breakeven:    +3,75pt → trava +2,5pt
Trailing:     1,75pt
Stop diário:  $750   (variante $1.000 → 100% aprovação, mais agressiva)
Trades/dia:   sem limite rígido (~5/dia)
```
**Resultado (1 ano real):** 94% aprovação (17/1) · mediana 15 dias · PF 1.53 · PnL +$30.900.
**Robustez:** 1ª metade 100% (7/7) · 2ª metade 90% (9/10).
**Doc completo:** `docs/estrategia-mnq-5contratos.md` · **Script:** `backtest/run_mnq_5contr.py`

### Por que não foi mais rápido (5 dias)?
- **Apex exige mín. 7 dias** de operação → aprovar em 5 dias é impossível pela regra (piso real ~8 dias).
- 5 MNQ é pequeno demais p/ fazer $1.500 em 5 pregões (mediana trava em ~14d mesmo ignorando a regra).
- Forçar 5 dias exigiria 8-10 MNQ → taxa despenca p/ 69-77% e dobra o risco. Péssima troca.
- ⚠️ **Confirmar com Andersson** se a regra dos 7 dias mínimos ainda vale no plano usado.

## ✅ Concluído (11/06)
- Análise competitiva do concorrente (NinjaBot IA / NinjaPass) — sem mágica, vende "IA" vaporware
- Decisão: bot de aprovação como produto principal; diferencial = gestão de DD
- **Backtest com 1 ano de dados reais do NQ** (1min, ~10,5 meses, 300k barras, exportado do NT8)
- Testadas 4 estratégias: ORB+VWAP, MeanReversion, Níveis, Matheus(manhã)
- **VENCEDORA: Níveis + trailing stop** (rejeição high/low do dia anterior)
- Refinamento: breakeven $75 + trailing $50 → win rate 34% → 64%
- Validação out-of-sample (2 metades) → robusto, não overfit
- **Documento pro Andersson:** `docs/estrategias-para-andersson.md`

## 🏆 Config vencedora (Níveis 25K — FOCO)
```
Entrada:        rejeição na máxima/mínima do dia anterior
TP / SL:        $500 / $250 (R:R 2:1)
Breakeven:      +$75 → trava stop em +$50
Trailing:       $35 (garante lucro ao perder força)
Máx trades/dia: 3   ← a chave dos 94% (corta overtrading)
Stop diário:    $750
Filtro VWAP:    OFF
```

## 📊 Resultados (1 ano real)
| Conta | Config | Taxa | Aprov/ano | PnL/ano |
|-------|--------|:---:|:---:|---------|
| **25K** ⭐ | máx 3 trades/dia + trail $35 | **94%** | 15 | +$25.615 |
| 25K | sem limite (trail $50) | 52% | 16 | +$36.785 |
| 50K | sem limite (trail $50) | 88% | 14 | +$42.295 |
| 100K | sem limite (trail $50) | 88% | 7 | +$45.740 |

→ **25K com limite de 3 trades/dia = 94%, robusto** (1ª metade 100%/PF 1.81, 2ª metade 89%/PF 1.50).
→ Descoberta-chave: **limitar trades/dia corta o overtrading que estourava o DD apertado da 25K**.

## ⚠️ Aprendizados-chave
1. **Trailing stop é o segredo** — converte perdas em ganhos protegidos (WR 34%→64%)
2. **Gestão de saída tem que casar com a entrada** — reversão (Níveis) quer alvo curto; rompimento (ORB) quer alvo amplo
3. **Conta maior = mais folga de DD = taxa maior** (caminho legítimo pros 70%+, virou 88%)
4. **NÃO perseguir "taxa" cegamente** — travar o bot dá 100% falso (4 avaliações, não robusto). Métrica certa = aprovações absolutas + robustez
5. **Sizing é o gargalo na 25K** — DD $1.500 com 1 NQ é apertado

## 🚧 Em progresso / Próximos passos
- [x] ~~Debater config + conta-alvo com Andersson~~ → **escolhida: 5 MNQ, 94% em 15 dias**
- [x] ~~Implementar a config 5 MNQ no NinjaScript~~ → **`src/ApexBot94.cs` criado** (Strategy de produção, fiel ao `run_mnq_5contr.py`)
- [ ] **PRÓXIMO (segunda 15/06):** Levar `ApexBot94.cs` pro NT8, compilar (F5) e configurar no gráfico MNQ 1min → iniciar forward test no Sim101
- [ ] Rodar no Sim101 / Market Replay (forward test ao vivo) p/ medir slippage real no trailing
- [ ] Confirmar com Andersson: regra dos 7 dias mínimos + custo real do MNQ na corretora
- [ ] (Futuro) Variante stop diário $1.000 (100% no backtest) + portfólio Níveis+ORB

## 🤖 Strategy de produção (`src/ApexBot94.cs`) — criado 13/06
- Classe `ApexBot94` (Strategy NT8), **separada** do `ApexApprovalSim.cs` (que é só backtest comparativo).
- Lógica idêntica ao backtest validado `backtest/run_mnq_5contr.py`:
  reversão na máx/mín do dia anterior · tol 6 ticks · TP 60 · SL 12,5 · BE +3,75→trava +2,5 · trail 1,75.
- Risco: stop diário $750 (kill switch), sem limite de trades/dia.
- Extra de segurança: "Parar ao aprovar" (meta $1.500 + 7 dias → flatten e para de operar).
- Tudo parametrizável na tela do NT8. Horários em **ET** (RTH 9h30–15h00, flatten 15h55).
- ⚠️ Calculate=OnBarClose: entra na abertura da barra seguinte (backtest entra no close) → diferença ~1min.

## 📁 Arquivos importantes
- `docs/estrategia-mnq-5contratos.md` — **estratégia ESCOLHIDA (5 MNQ, 94%/15d)**
- `docs/estrategias-para-andersson.md` — documento de decisão (debate, NQ)
- `src/ApexApprovalSim.cs` — Strategy NinjaScript (base, recebe a config 5 MNQ)
- `backtest/run_mnq_5contr.py` — **varredura 5 MNQ → config vencedora (15d)**
- `backtest/run_mnq_5dias.py` — busca por 5 dias (mostra por que não rola)
- `backtest/run_mnq.py` / `run_mnq_speed.py` — sweeps de sizing MNQ
- `backtest/stats_94.py` / `refine_25k_final.py` — estratégia 94 original (NQ)
- `NQ_dados/` — 13 arquivos de NQ 1min (jun/2025–jun/2026)

## 🔧 Como rodar o backtest
```bash
cd "Desktop/Projetos AI/Bot-trade-nt8"
python3 backtest/test_contas.py        # resultado por conta (principal)
python3 backtest/refine_full.py        # refinamento + robustez
```

## ⚖️ Ressalvas
- ~10,5 meses (buracos em set/dez/mar = vencimento), 1 contrato NQ, candle de minuto (não tick)
- Custos estimados ($5/RT) — confirmar com corretora real
- Backtest ≠ ao vivo — validar com forward test antes de vender
