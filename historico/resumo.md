# 📌 Resumo geral — Bot Trade NT8 (BotAprovacao)

> Visão rápida pra retomar o projeto depois de dias/semanas sem mexer. Detalhe completo sempre
> em `progress.md` (topo) e nos snapshots diários desta pasta.

## O que é o projeto

Bot de automação (NinjaScript/NT8) pra passar avaliações Apex Trader Funding — conta $25K,
meta $1.500 em até 30 dias corridos, drawdown real $1.000. Estratégia: reversão na máxima/mínima
do dia anterior ("Níveis 94"), 5 MNQ, timeframe 1min.

## ⚠️ AÇÃO PENDENTE PRO MARCELO (ver `2026-08-20.md` pro passo a passo completo)

**Precisa alterar o `BotAprovacao_SaidaParcial.cs` (o SEGUNDO bot, o experimental — não o de
produção)** no NT8: recompilar e confirmar manualmente que `[EXP] Usar saida parcial = false` na
instância que já está no gráfico do Market Replay (o recompile sozinho não atualiza uma
instância já adicionada). `BotAprovacao.cs` (produção) e o backup **não mudam**.

## Estado atual (20/08/2026)

- **Produção (`BotAprovacao.cs`):** rodando ao vivo, config original (SL 12,5/BE fixo
  3,75→2,5/trailing 1,75/alvo 60/5 MNQ/MaxTradesDia 12). Nunca alterado.
- **Experimental (`BotAprovacao_SaidaParcial.cs`):** BE-lock proporcional 0,75 ligado (melhoria
  real, confirmada em Replay, Δ+$122,5 no período testado) + saída parcial 4+1@20pt **desligada**
  (testada exaustivamente 20/08, piora em todo teste — nunca disparou de verdade em Replay).
- **Taxa de aprovação real medida (janela de 30 dias, retry imediato — a metodologia correta):
  50%.** De cada 2 avaliações $25K, 1 aprova, no ritmo atual.
- **Nenhuma estratégia alternativa testada (ORB, EMA+VWAP+RSI, "ICT-lite") supera a reversão** —
  sozinha ou mesclada. Ver `docs/comparativo-estrategias-20-08.md`.
- Junho (Market Replay, dia a dia): registrado até 28/06 completo; faltam 2 trades de 29/06 pra
  fechar o mês por inteiro.

## Arquivos-chave

- `progress.md` — estado detalhado, atualizado toda sessão (topo = mais recente).
- `docs/melhorias-sugeridas.md` — lista de TODAS as melhorias testadas, aceitas e rejeitadas
  (16 itens até agora).
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
