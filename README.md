# 🤖 Bot Aprovação Apex — Estratégia "94 em 15 dias"

Bot de **aprovação de conta Apex** para NinjaTrader 8 (NinjaScript C#), focado em NQ/MNQ.
Estratégia de **reversão na máxima/mínima do dia anterior** ("Níveis 94"), validada com 1 ano de dados reais.

## 📊 Resultado do backtest (1 ano real, 5 MNQ)

| Métrica | Valor |
|---------|:---:|
| Taxa de aprovação | **94%** (17/1) |
| Mediana p/ aprovar | **15 dias** |
| Profit Factor | 1.53 |
| Win rate | 64% |
| Risco por trade | $125 (buffer 12x no DD) |

Robustez out-of-sample: 1ª metade 100% (7/7) · 2ª metade 90% (9/10).

## 🏆 Config vencedora (5 MNQ — conta 25K)

```
Mercado:      MNQ (Micro Nasdaq) — 5 contratos
Conta:        Apex 25K (meta $1.500 | DD $1.500 | mín. 7 dias)
Entrada:      reversão na máx/mín do dia anterior (tol. 6 ticks)
Alvo (TP):    60 pontos
Stop (SL):    12,5 pontos
Breakeven:    +3,75pt → trava +2,5pt
Trailing:     1,75pt
Stop diário:  $750
Horário:      RTH EUA, entradas 9h30–15h00 ET, flatten 15h55
```

## 📁 Estrutura

```
src/
  ApexBot94.cs        ← Strategy de PRODUÇÃO (opera ao vivo) ⭐
  ApexApprovalSim.cs  ← Backtest comparativo (3 estratégias + simulador Apex)
backtest/             ← Scripts Python de validação (run_mnq_5contr.py = vencedor)
docs/                 ← Documentação das estratégias
NQ_dados/             ← 1 ano de dados reais do NQ (1min)
historico/            ← Snapshots de sessão
progress.md           ← Progresso do projeto
```

## 🚀 Como usar no NT8

1. Copie `src/ApexBot94.cs` para `Documents\NinjaTrader 8\bin\Custom\Strategies\`
2. Editor NinjaScript → **F5** (compilar)
3. Gráfico **MNQ de 1 minuto**, horário em **US Eastern (ET)**
4. **Forward test primeiro** no Sim101 / Market Replay antes de qualquer conta real

## ⚠️ Ressalvas

- 94% é a taxa **histórica** do período, não garantia.
- Backtest em candle de 1min (não tick); ao vivo o slippage no trailing pode variar.
- `Calculate = OnBarClose`: ao vivo entra na abertura da barra seguinte (~1min de defasagem vs. backtest).
- **Validar com forward test é obrigatório.**
