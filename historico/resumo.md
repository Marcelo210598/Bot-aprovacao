# 📌 Resumo geral — Bot Trade NT8 (BotAprovacao)

> Visão rápida pra retomar o projeto depois de dias/semanas sem mexer. Detalhe completo sempre
> em `progress.md` (topo) e nos snapshots diários desta pasta.

## O que é o projeto

Bot de automação (NinjaScript/NT8) pra passar avaliações Apex Trader Funding — conta $25K,
meta $1.500 em até 30 dias corridos, drawdown real $1.000. 5 MNQ, timeframe 1min.

**🔴 01/09/2026 — a estratégia de reversão PDH/PDL foi ABANDONADA.** Testada fora da amostra
no NT8 Strategy Analyzer (2022-2025): PF 0,91, perdedora nos 4 anos. O bom resultado de 2026
era sorte de regime. **Projeto pivotou pra estratégia NOVA do zero**, começando 02/09 pela
candidata B (event-driven, spike das 8h30 ET). Ver `docs/estrategia-nova-2026-09.md` e
`progress.md` (topo). O bot de produção `BotAprovacao.cs` continua intacto mas sem edge
comprovado fora de amostra.

## 🧪 01/09 — Direção B destrinchada (Renko + DD + outros instrumentos via Databento)

Sessão inteira na decisão estratégica de 23/08. Detalhe: `historico/2026-09-01.md` +
`docs/melhorias-sugeridas.md` #22. Resumo:
- **Renko + MA (motor de 30d):** sem edge. Gestão de tendência = 0% aprovação, PF 0,77–0,97.
  Fechado.
- **Modelo de drawdown = a maior alavanca:** DD trailing (Apex) 55% → **DD estático 60%, zero
  estouros**. Firmas c/ DD estático + bot: Tradeify, MyFundedFutures, TPT. Confirmar termos.
- **Conta Apex maior não resolve** (relógio de 30d trava; 50K/14MNQ ≈ 59% frágil, 100K ≈ 0%).
- **2º sinal — fade do range overnight (Globex) no RTH:** empata a REV sozinho; mesclado
  (REV+ON) sob DD estático dá **75%, OOS 82%/69%** (mas o ganho vem do DD, não do sinal).
- **Databento (US$ 7,60 de US$ 125):** dado real MES/MNQ/M2K/MYM, jun/25→jun/26.
  `backtest/carrega_databento.py` → front-month contínuo.
- **A reversão em outros instrumentos:** MES (S&P) PF máx 0,80, M2K (Russell) 0,85 — **sem edge**
  (a reversão em nível é fenômeno de Nasdaq/Dow). **MYM (Dow) PF 1,44 com fill de 1 tick / 1,18
  com 2 ticks** — único glimmer, edge parecido com o NQ + menos risco de estouro, mas frágil a
  slippage. Só forward test resolve.
- **Rompimento (breakout) nos 4 instrumentos + como complemento** (`run_break_instr.py`): edge
  fraco só no Nasdaq (PF ~1,1), morto no resto. **Juntar fade + break PIORA** (dilui o edge forte
  da reversão). ORB morto em todos os 5 instrumentos. Rompimento não é o complemento que faltava.
- **Veredito:** trocar de instrumento OU de tipo de estratégia é quase um beco. A alavanca real
  da direção B é o FORMATO (firma de DD estático).
- **Bot novo `src/BotAprovacaoDow_MYM.cs`** criado (cópia do BETrigger25, só troca instrumento +
  params) — mas ver revisão abaixo, virou experimento opcional.
- **REVISÃO (mesmo dia, `run_mnq_mym_junto.py`):** Marcelo perguntou se dá pra agregar o MYM ao
  BETrigger25. Testado MNQ+MYM na mesma conta: **não ajuda** (MNQ sozinho 75% sob DD estático /
  OOS 62-69; juntos 73% / OOS 56-91, mais estouros — MNQ e MYM ~0,9 correlacionados). **As 2
  alavancas são separáveis e só uma vale:** lever 1 (DD estático) NÃO é código, aplica ao
  BETrigger25 direto e leva ele de 43%→75% no dado do Databento; lever 2 (MYM) não soma nada.
  **Caminho recomendado: BETrigger25 (MNQ) numa firma de DD estático, sem código novo.** Produção
  e os `.cs` de produção intactos (só criei `BotAprovacaoDow_MYM.cs`, experimento opcional).
- **🔀 Forward test do BETrigger25 muda de JUNHO pra JULHO/2026** (junho é o pior mês pro achado
  do BE trig 2,5; 9 de 13 meses melhoram). Pasta nova: `forward-test-replay-25k/2026-07-betrigger25/`.

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
