# 📌 Resumo geral — Bot Trade NT8 (BotAprovacao)

> Visão rápida pra retomar o projeto depois de dias/semanas sem mexer. Detalhe completo sempre
> em `progress.md` (topo) e nos snapshots diários desta pasta.

## O que é o projeto

Bot de automação (NinjaScript/NT8) pra passar avaliações Apex Trader Funding — conta $25K,
meta $1.500 em até 30 dias corridos, drawdown real $1.000. Estratégia: reversão na máxima/mínima
do dia anterior ("Níveis 94"), 5 MNQ, timeframe 1min.

## 🔴 29/08 — Marcelo insatisfeito, forward test pausado

Forward test do `BETrigger25+MaxDist20` (dias 05-11/06) fechou em +$38,0/40 trades (~$0,95/trade,
loss grandes de -$105/-$118). Testado SL menor no backtest de 13 meses pra atacar isso: piora WR e
PnL total (Net/mês $1.796→$128 com SL 6pt) — o loss grande é o desenho do risco, não um bug.
Marcelo: "já sabemos que não terá aprovação de conta", "não estou feliz com o que temos" — parou
por hoje. **Isso reforça a decisão estratégica em aberto abaixo, que segue sem resposta.** Começar
a próxima sessão por aí, sem forçar otimismo.

## 🧭 DECISÃO ESTRATÉGICA EM ABERTO (23/08) — a mais importante, decidir antes do resto

Depois de ~15 ângulos testados (gestão de saída, filtros de entrada, estratégias alternativas, 4
testes de IA — ver item #20 em `docs/melhorias-sugeridas.md`) convergirem pro mesmo teto de ~50%
de aprovação, falta decidir:
1. **Aceitar ~50% e escalar operação** (várias avaliações em paralelo, funil de negócio), ou
2. **Repensar estratégia/instrumento do zero** (projeto novo, semanas de trabalho).

Nenhuma ação de código pendente até essa decisão.

## ⚠️ OUTRAS PENDÊNCIAS ABERTAS (23/08)

- **Bug não corrigido (item #18):** `pdHigh`/`pdLow` zeram quando a estratégia reinicia no
  gráfico, deixando o bot mudo o dia inteiro sem aviso. Aconteceu em 21/07. Precisa decisão do
  Marcelo antes de mexer no `.cs` experimental pra corrigir.
- **Item #17 (watch):** 2 casos de stop cheio com favor <1pt em 13/07 — ver se se repete.
- **Segurança:** API key da Anthropic foi exposta no chat em 23/08. Marcelo optou por manter e
  seguir (ciente do risco). Vale sugerir revogar/trocar numa próxima sessão, sem insistir.

## Estado atual (23/08/2026)

- **Produção (`BotAprovacao.cs`):** rodando ao vivo, config original (SL 12,5/BE fixo
  3,75→2,5/trailing 1,75/alvo 60/5 MNQ/MaxTradesDia 12). Nunca alterado.
- **Experimental (`BotAprovacao_SaidaParcial.cs`):** BE-lock proporcional 0,75 ligado (melhoria
  real, confirmada em Replay, Δ+$122,5 em junho) + saída parcial 4+1@20pt **desligada**. Rodando
  forward test de julho no Market Replay: acumulado **-$522,5 até 20/07**.
- **Taxa de aprovação real medida (janela de 30 dias, retry imediato — a metodologia correta):
  50%.** De cada 2 avaliações $25K, 1 aprova, no ritmo atual.
- **Nenhuma estratégia alternativa (ORB, EMA+VWAP+RSI, "ICT-lite") supera a reversão** — sozinha
  ou mesclada. Ver `docs/comparativo-estrategias-20-08.md`.
- **IA (Claude) testada de 4 jeitos diferentes em cima da REV (23/08) — nenhum bateu os 50%.**
  Filtro de entrada, seletor de estratégia (2 versões) e gestão de risco por trade, todos
  rejeitados por backtest. Ver item #19 em `docs/melhorias-sugeridas.md`. **Decisão: parar essa
  linha de investigação.** Nada foi implementado em produção nem no NinjaScript.
- Junho (Market Replay): fechado 100% (todos os 30 dias, Δ +$122,5 confirmado).
- Julho (Market Replay): registrado 01-20/07, acumulado -$522,5. Continua sendo lançado dia a dia.

## Arquivos-chave

- `progress.md` — estado detalhado, atualizado toda sessão (topo = mais recente).
- `docs/melhorias-sugeridas.md` — lista de TODAS as melhorias testadas, aceitas e rejeitadas
  (19 itens até agora, incluindo os 4 testes de IA de 23/08).
- `docs/taxa-aprovacao-30dias-20-08.md` — as 3 metodologias de medir aprovação + o número real.
- `docs/market-replay-guia-comparacao.md` — como rodar o A/B no Market Replay.
- `src/BotAprovacao.cs` — produção, NUNCA alterar sem autorização explícita.
- `src/BotAprovacao_BASELINE_BACKUP.cs` — cópia de referência, mantida byte-idêntica à produção.
- `src/BotAprovacao_SaidaParcial.cs` — experimental ativo (o que roda no Replay hoje).
- `backtest/` — dezenas de scripts Python de validação; todos rodam a partir da raiz do projeto
  (`python3 backtest/nome_do_script.py`), porque `NQ_dados/` fica na raiz.

## Regra de ouro do projeto (não pular)

Nenhuma mudança de comportamento em produção sem: (1) backtest com o motor de aprovação real
(DD $1.000, MaxTradesDia=12, slippage 2 ticks), (2) confirmação OOS (não confiar em achado de
1 mês/1 metade do dado), e (3) autorização explícita do Marcelo. Toda investigação em cópia
isolada, produção e backup nunca tocados.
