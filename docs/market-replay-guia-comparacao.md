# 🔬 Guia — Market Replay A/B (BASELINE vs SaidaParcial) + auditoria DEBUG

> Criado 20/08/2026. Cobre os 3 arquivos novos em `src/`:
> `BotAprovacao_BASELINE_REPLAY.cs`, `BotAprovacao_SaidaParcial_REPLAY.cs`,
> `BotAprovacao_SaidaParcial_REPLAY_DEBUG.cs`. Nenhum deles é o bot de produção.

## 1. O que cada arquivo é

| Arquivo | Classe/Nome no NT8 | Lógica | Uso |
|---|---|---|---|
| `BotAprovacao.cs` | `BotAprovacao` | produção | **NÃO TOCAR, NÃO RODAR EM REPLAY JUNTO COM OS OUTROS** (mesmo arquivo de PnL diário que nenhum dos 3 novos usa mais — ver §2) |
| `BotAprovacao_BASELINE_BACKUP.cs` | (mesma classe `BotAprovacao`) | idêntico à produção | só referência/backup em texto — **não compila junto com produção** (nome de classe colide) |
| `BotAprovacao_BASELINE_REPLAY.cs` | `BotAprovacao_BASELINE_REPLAY` | idêntico à produção | (A) baseline, pra rodar no Replay |
| `BotAprovacao_SaidaParcial.cs` | `BotAprovacao_SaidaParcial` | parcial 4+1@20pt + BE-lock 0,75 | versão original do experimento (rodada nos últimos dias) — **continua existindo, intocada** |
| `BotAprovacao_SaidaParcial_REPLAY.cs` | `BotAprovacao_SaidaParcial_REPLAY` | idêntica à de cima | (B) experimental, pra rodar lado a lado com (A) |
| `BotAprovacao_SaidaParcial_REPLAY_DEBUG.cs` | `BotAprovacao_SaidaParcial_REPLAY_DEBUG` | idêntica a (B) + logs | (C) mesma coisa que (B), só com muito mais log — usar quando quiser auditar um trade específico |

**Nenhuma condição de entrada foi tocada em nenhum dos 3.** Só foram alterados: nome da classe, `Name`/`Description` (cosmético, aparece no NT8), e o caminho do arquivo de PnL diário (ver §2). No (C) foram adicionados só `Print()` — nenhuma linha de decisão nova.

## 2. ⚠️ Ponto crítico pra você não pisar: arquivo de PnL diário

O baseline original grava o "quanto já perdi hoje" (usado pro `StopDiarioDolar=$750`) em
`%AppData%/NinjaTrader 8/BotAprovacao_pnl_diario.txt`. Se duas estratégias usassem o mesmo
arquivo rodando juntas no Replay, uma leria/escreveria por cima da outra e o stop diário de
ambas ficaria errado — invalidando a comparação. Corrigi isso: cada um dos 3 arquivos novos
grava num arquivo próprio:

- `BotAprovacao_BASELINE_REPLAY_pnl_diario.txt`
- `BotAprovacao_SaidaParcial_REPLAY_pnl_diario.txt`
- `BotAprovacao_SaidaParcial_REPLAY_DEBUG_pnl_diario.txt`

Isso é infraestrutura, não estratégia — não muda nenhuma regra de entrada/saída, só evita que os
3 pisem um no outro (ou na produção) quando rodarem ao mesmo tempo na mesma máquina.

## 3. Como rodar no NinjaTrader 8

1. **Compilar**: NinjaScript Editor → confirme que os 3 arquivos aparecem em Strategies. `F5`
   pra compilar. **Se der erro de compilação, me manda o texto exato do erro** — não testei a
   compilação real (não tenho NT8 aqui), só revisei o código manualmente e conferi chaves/
   parênteses balanceados.
2. **Abrir o Market Replay** no instrumento/timeframe de sempre (MNQ, 1 minuto — é o mesmo
   timeframe usado nos testes de junho, não misturar com o gráfico de 5min).
3. **Adicionar as DUAS estratégias no mesmo gráfico**: `BotAprovacao_BASELINE_REPLAY` e
   `BotAprovacao_SaidaParcial_REPLAY` — ambas ligadas ao mesmo tempo, no mesmo instrumento, no
   mesmo Replay. Isso é o que garante que as duas veem exatamente os mesmos ticks, na mesma
   ordem — comparação de verdade, não duas rodadas separadas em dias diferentes.
4. **Params**: os dois já vêm com os defaults corretos (5 MNQ, SL 12,5, meta $1.500, DD real
   via `StopDiarioDolar=750`, `MaxTradesDia=12`). Não precisa mexer em nada pra rodar o teste
   padrão. Se quiser rodar `BotAprovacao_SaidaParcial_REPLAY_DEBUG` em vez da (B) pra ter os
   logs extras, ela tem os mesmos defaults + o toggle `[DEBUG] Log tick a tick` (Order=100,
   grupo "11. Debug/Auditoria") — deixa `false` pro dia inteiro, só liga `true` quando for
   focar em auditar 1 dia específico (o log fica gigante).
5. **Rodar o Replay** a partir de 01/06 (mesma data de sempre), velocidade que preferir.

## 4. O que observar nos logs (aba "NinjaScript Output" ou "Strategies" → Log)

Com a (C) DEBUG rodando, cada trade gera esta sequência (todas com `id=<sinal>`, ex. `NIV_S7` —
esse é o ID pra filtrar/auditar um trade específico, ver §5):

```
[DEBUG] ===== TRADE OPEN =====           ← entrada, direção, qtd, SL inicial
[PLANO SAIDA — EXPERIMENTO]              ← já existia: mostra o alvo dos 20pt e o alvo final 60pt
[DEBUG] --- durante o trade ---          ← 1 linha por barra nova (MFE/MAE/distância até 20pt/estado)
[DEBUG] ===== BE ATIVADO =====           ← só quando ativar: MFE no momento, cálculo do lock, novo stop
<<< SAIDA PARCIAL [...]                  ← só se tocar +20pt: qtd antes/enviada/restante, preço do gatilho
[DEBUG] ===== EXECUCAO REAL (PARCIAL) ===== ← preço de FILL real (do broker/simulador) vs preço do gatilho = slippage
[STOP INTRABAR] ou [ALVO INTRABAR]       ← já existia: qual nível fechou o trade
<<< SAIDA [...]                          ← já existia + agora com MAE
[DEBUG] ===== EXECUCAO REAL (SAIDA FINAL) ===== ← preço de FILL real da saída final vs gatilho = slippage
```

**O que isso responde, direto das suas 10 perguntas da seção "OBJETIVO DO MARKET REPLAY":**
1-3 → linha `<<< SAIDA PARCIAL`. 4-5 → linha `EXECUCAO REAL (PARCIAL)` (qtd preenchida + preço
real). 6 → linhas `--- durante o trade ---` depois da parcial (mostra o 1 contrato seguindo
normal). 7-9 → linha `BE ATIVADO`. 10 → comparar isso tudo com o CSV de trades do backtest
Python (ver §6).

## 5. Como identificar um trade pra auditoria

O **ID do trade é o `sinalAtivo`** (ex. `NIV_S7`, `NIV_L3`) — é único por trade dentro do dia e
aparece em TODAS as linhas relacionadas àquele trade (`id=NIV_S7`). No NinjaScript Output,
Ctrl+F por `id=NIV_S7` (ou pelo timestamp aproximado) reconstrói a história completa daquele
trade específico, do OPEN até a SAIDA.

## 6. Como exportar pra comparar depois

- **Log bruto**: NinjaScript Output → botão direito → "Save As..." → salva o `.txt` inteiro da
  sessão de Replay. Guardar em `forward-test-replay-25k/` com nome do período (mesmo padrão já
  usado nos `dia-XX.md`).
- **Trade a trade estruturado**: `SystemPerformance.AllTrades` de cada estratégia pode ser
  exportado pelo próprio NT8 (aba Strategies → botão direito na estratégia → "Grid" → exportar
  CSV) — dá entrada/saída/PnL por trade, útil pra bater direto com o CSV que os scripts Python
  de `backtest/` geram (mesmas colunas: entrada, saída, PnL, horário).
- Já existe `backtest/parse_trades_replay.py` no repo — dá uma olhada nele antes de escrever
  um parser novo, pode já servir (ou quase) pra ler o log do Replay e gerar o CSV comparável.

## 7. ⚠️ Limite que este guia NÃO resolve (repetindo a Fase 1 da auditoria)

A saída parcial (4+1@20pt) **só existe no caminho tick a tick** (`OnMarketData`, que só roda em
`State.Realtime` — ou seja, live ou Market Replay). Ela **não existe** no caminho por barra
(`GerenciaPosicao`), que é o que qualquer backtest de barra de 1min (Python ou Strategy
Analyzer) replicaria. **Isso significa que não dá pra comparar "backtest disse que a parcial
disparou X vezes" contra o Replay de forma direta** — o backtest de barra, se reimplementado
ingenuamente, teria que ADIVINHAR se o preço tocou os 20pt antes ou depois de outros eventos
dentro da mesma barra de 1min, e isso é exatamente o tipo de suposição que a Fase 11 do seu
pedido original proíbe. Qualquer trade em que isso for ambíguo no backtest tem que ser marcado
como tal no relatório comparativo — não assumir a ordem favorável.

## 8. Nenhuma alteração definitiva

Nada disso mexeu em `BotAprovacao.cs` (produção) nem em `BotAprovacao_BASELINE_BACKUP.cs`. Os
3 arquivos novos são cópias isoladas. Nenhum parâmetro de estratégia foi otimizado ou escolhido
"pelo melhor resultado" — só foi preparada a infraestrutura pra rodar o A/B e auditar.
