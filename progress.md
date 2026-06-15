# Bot Trade NT8 (BotAprovacao) - Progresso

## Última atualização: 2026-06-15

## 📌 Visão Geral
- **Objetivo:** Bot de APROVAÇÃO de conta Apex (produto de entrada) → upsell do bot de operação
- **Público:** Comunidade Nômade Trader (traders BR, Apex)
- **Stack:** NinjaScript (C#) + backtest em Python (validação)
- **Status:** 🟢 Bot implementado e em forward test — **100% de aprovação no backtest**

## 🎯 Config vencedora atual (5 MNQ, conta 25K Intraday)

```
Mercado:     MNQ (Micro Nasdaq) — 5 contratos
Conta:       Apex 25K Intraday (meta $1.500 | DD $1.500 | mín. 7 dias)
Entrada:     reversão na máxima/mínima do dia anterior
             (SEGUNDA: range do domingo à noite / Globex 18h→9h30)
Tolerância:  20 ticks = 5pt
Filtro:      MaxDistPontos = 15pt (close a no max 15pt da linha)
Alvo (TP):   60 pontos
Stop (SL):   12,5 pontos  →  $125/trade (5 MNQ)
Breakeven:   +3,75pt → trava +2,5pt
Trailing:    1,75pt
Stop diário: $750
Janela:      9h30–16h00 ET (flatten 16h55)
Parar:       ao bater meta $1.500 + 7 dias operados
```

## 📊 Resultado do backtest (1 ano real, 300k barras NQ 1min)

| Métrica | Valor |
|---|---|
| **Taxa de aprovação** | **100%** (19 aprovadas / 0 reprovadas) |
| **Mediana por aprovação** | **15 dias** |
| **Profit Factor** | **1.60** |
| **PnL estimado/ano** | **+$36.978** |
| **Robustez OOS** | **100%/100%** (1ª e 2ª metade) |
| Win Rate | 68% |
| Trades/dia | ~6.7 |

## ✅ Concluído

### Estratégia e backtest
- Análise competitiva (NinjaBot IA / NinjaPass) — diferencial: gestão de DD
- Backtest com 1 ano de dados reais NQ 1min (~300k barras)
- Testadas 4 estratégias: ORB+VWAP, MeanReversion, Níveis, Matheus
- **Vencedora: Níveis + trailing stop** (rejeição high/low do dia anterior)
- Validação out-of-sample (2 metades) — robusto, não overfit

### Otimizações (comprovadas por backtest, todas adotadas)
1. **Tolerância de toque: 6 → 20 ticks** (13/06) — +21% PnL, +2 aprovações
2. **Janela de entrada: 15h → 16h** (14/06) — +2 aprovações/ano, zero noturnas
3. **Filtro de proximidade: MaxDistPontos = 15pt** (14/06) — 100% taxa, PF 1.60, OOS perfeito
4. **Segunda usa range do domingo à noite (Globex)** (15/06) — 19→**22 aprov/ano**, mediana 15→**13d**, PF 1.60→1.64, OOS 100%/100%. Antes a segunda usava a linha de sexta (ou linha degenerada de 1 barra de domingo, efeito colateral). Toggle `SegUsaDomingo` (default ON). Backtest: `backtest/run_segunda_domingo.py`. ⚠️ No gráfico exige sessão ETH/Globex (não RTH-only) senão cai no fallback da linha de sexta.

### Implementação
- Strategy de produção **`src/BotAprovacao.cs`** — compilada e funcionando no NT8
- Modelo híbrido de saída: stop servidor (intrabar) + trailing/alvo sintéticos (bar close)
- Integração TraderOS (HTTP 201, dedup por externalId) — funcionando
- Repo GitHub: `Marcelo210598/Bot-aprovacao` (privado)

### Forward test (Market Replay)
- Dias **09/06 a 12/06/2026** concluídos
- Bugs encontrados e corrigidos na sessão 13/06 (4 bugs críticos)
- Comportamentos validados: stop intrabar, filtro chase, TraderOS sync, spam de log

## 🚧 Em progresso
- Forward test — semana **02–06/06/2026** pendente (baixar dados: 30/05 a 06/06)
- Confirmar com Andersson: regra 7 dias mínimos + custo real MNQ

## ⚠️ Problemas mapeados

### Resolvidos
- OCO ID reutilizado → stop/alvo não criados → **resolvido** (sinal único por trade)
- Trailing c/ ordem no servidor desabilitava bot → **resolvido** (trailing sintético)
- Stop inicial inválido → perdas enormes → **resolvido** (ticks na entrada)
- Entradas "chase" (3 stops em 3 min no mesmo nível) → **resolvido** (filtro 15pt)
- Spam de log em dias acima do PDH → **resolvido** (guard tol*2)

### Monitorar (baixa prioridade)
- Overtrading: ~14 trades/dia no backtest — decisão: manter (fiel ao backtest). Soluções mapeadas se der problema ao vivo (cooldown / max 12 trades-dia).
- Dias de mercado lateral (range extremo dia anterior): zero entradas. Comportamento esperado, já no backtest dos 100%.

## 📋 Próximos passos (roadmap)
1. **Forward test semana 02–06/06** — baixar dados e rodar
2. **Forward test completo** — validar slippage real ao vivo no Sim101
3. **Confirmar Andersson** — regra 7 dias + custo MNQ
4. **Bot Funded 25K** — estratégia pós-aprovação (foco consistência, não velocidade)
5. **Bot Funded 50K** — variante com mais folga de DD

## 🎯 Visão de produto (3 produtos)
1. **Bot Aprovação** ← atual (BotAprovacao, 100%/15d, 5 MNQ, 25K) ✅ forward test
2. **Bot Funded 25K** — estratégia pós-aprovação para operar a conta funded
3. **Bot Funded 50K** — idem para conta 50K (mais agressivo)

## 📁 Arquivos importantes
- `src/BotAprovacao.cs` — **estratégia de produção** (compilar e usar no NT8)
- `docs/estrategia-mnq-5contratos.md` — documentação da estratégia escolhida
- `backtest/run_mnq_5contr.py` — backtest baseline
- `backtest/run_tolerancia.py` — otimização tolerância (tol 20t)
- `backtest/run_horario_18h.py` — otimização janela (16h)
- `backtest/run_proximity_filter.py` — otimização MaxDist (15pt)
- `backtest/run_stop_diario.py` — otimização stop diário ($750)
- `NQ_dados/` — dados NQ 1min (jun/2025–jun/2026)
- `historico/` — snapshots diários das sessões

## 🔧 Como usar o bot no NT8
1. Baixar `src/BotAprovacao.cs` do GitHub (repo privado — não colar texto, corrompe)
2. Colocar na pasta Strategies do NT8
3. Compilar (F5 no Editor NinjaScript)
4. Adicionar ao gráfico MNQ 1min (fuso ET)
5. Config padrão já está correta — conferir parâmetros antes de ligar

## ⚖️ Ressalvas
- Backtest em NQ 1min (~10,5 meses úteis) — custos estimados ($1,20 RT/contrato MNQ)
- Backtest ≠ ao vivo — forward test em Sim101 obrigatório antes de conta real
- Apex trailing DD só estimado de dentro do NinjaScript
