# 🔬 Auditoria profunda — BotAprovacao.cs (18/08/2026)

> Objetivo: descobrir **onde o edge está sendo perdido**, não otimizar parâmetros.
> Scripts: `backtest/diagnostico_mfe_mae.py` (instrumentação MFE/MAE + 3 motores de saída).
> Dados: `NQ_dados/` 1min, 300.174 barras (2025-06-11 → 2026-06-11), slippage/custo embutidos.

---

## 1. RESUMO EXECUTIVO

**O edge não está sendo perdido na entrada, nem no backtest, nem na estrutura de mercado.
Está sendo perdido no MOTOR DE SAÍDA AO VIVO — especificamente no trailing de 1,75pt
executado tick a tick pelo `OnMarketData`.**

Prova em uma linha: nos 84 trades reais registrados no forward test de junho,
**o maior ganho de TODOS foi +7,45pt** — e **nenhum trade jamais ganhou 12,5pt ou mais**,
apesar de o MFE mediano dos vencedores no modelo ser exatamente **12,5pt**.
Não é variância. É um **teto mecânico**.

| | Modelo (barra) | Real (ao vivo) |
|---|---|---|
| Ganho médio | 10,4pt / $104 | **3,96pt / ~$40** |
| Perda média | -13,1pt / -$131 | **-12,50pt / -$107 a -$136** |
| Maior ganho observado | 72pt (TP) | **+7,45pt** |
| Ganhos ≥ 12,5pt | frequentes | **ZERO em 84 trades** |

**As perdas batem perfeitamente entre modelo e realidade. Só os GANHOS estão 2,5x menores.**
Isso isola o problema: não é a entrada (as perdas provariam), é a captura do movimento favorável.

### Mecanismo exato
1. Preço anda +3,75pt → dispara breakeven → stop trava em **+2,5pt**
2. A partir daí o stop é `max(+2,5 ; pico − 1,75pt)`
3. Sob execução **tick a tick**, qualquer recuo de 1,75pt encerra o trade
4. Um recuo de 1,75pt no MNQ acontece em segundos, várias vezes por minuto

Resultado: **24,2% de todos os ganhos reais saem em exatamente +2,50pt** (o nível do
breakeven-lock) e **77,3% saem com ≤ 5pt**. Pra ganhar 12,5pt seria preciso o preço andar
14,25pt sem NUNCA recuar 1,75pt — o que praticamente não existe em dado de tick.

### Por que ninguém tinha visto
O parâmetro `TrailingPontos = 1,75` foi otimizado em **backtest baseado em barras**, onde
`GerenciaPosicao()` só verifica o stop no fechamento da barra e o trailing **só passa a
valer na barra seguinte** (lag de 1 barra — está comentado no próprio código, linha 783).
Nesse motor, 1,75pt se comporta como um trailing MUITO mais folgado do que é na realidade.
Ao vivo, o `OnMarketData` aplica os mesmos 1,75pt a cada tick — um stop brutalmente mais
apertado. **São dois motores de saída diferentes rodando o mesmo número.**

---

## 2. PROBLEMAS ENCONTRADOS NO CÓDIGO

| # | Local | Problema | Gravidade |
|---|---|---|---|
| 1 | `OnMarketData` (351) vs `GerenciaPosicao` (757) | **Dois motores de saída distintos**: tick a tick ao vivo, barra com lag de 1 no backtest. O backtest não consegue prever o comportamento real. | 🔴 Crítica |
| 2 | `GerenciaPosicao` 776-781 | Checa **ALVO antes do STOP** na mesma barra. Se a barra tocou os dois, assume o alvo → viés otimista no backtest. Raro com TP60/SL12,5 (exigiria barra de 72,5pt), mas existe. | 🟡 Média |
| 3 | `TradesHoje()` 946 | Usa `Time[0].ToString(...)` **sem converter para ET**, enquanto todo o resto usa `EmET(Time[0])`. Se o fuso do gráfico ≠ ET, `MaxTradesDia` conta o dia errado. | 🟡 Média |
| 4 | `OnBarUpdate` 285 | `diasOperados.Add(hoje)` só executa se houver posição aberta **no fechamento de uma barra**. Um trade aberto e fechado intrabar (via `OnMarketData`) pode não contar o dia → afeta o gate `MinDiasOperados = 7`. | 🟡 Média |
| 5 | `SetDefaults` 126 | `RealtimeErrorHandling.IgnoreAllErrors` — rejeição de ordem é silenciosamente engolida. Protege contra a estratégia se desabilitar, mas mascara falha de execução. | 🟠 Risco operacional |
| 6 | `SetDefaults` 122 | `Slippage = 0` no backtest interno do NT8. | 🟢 Conhecido |
| 7 | `OnBarUpdate` 249 | `emSessao` usa `1600` hardcoded em vez de `EntradaFim` — mudar `EntradaFim` não muda a janela de cálculo do nível. Aparentemente proposital (nível = RTH), mas é uma armadilha silenciosa. | 🟢 Baixa |

### Lookahead / uso de informação futura
**Não encontrei lookahead real.** Verificado:
- `pdHigh`/`pdLow` vêm do dia anterior fechado ✅
- `EntradaNiveis` usa `High[0]/Low[0]/Close[0]` da barra **já fechada** ✅
- Entrada é ordem a mercado → fill no open da barra seguinte ✅ (modelado corretamente)
- `NivelAtivo` na segunda usa range do domingo já formado ✅

**Hipótese do "gap de entrada" — DESCARTADA com dado.** Medi o gap entre o close do sinal e
o open da barra de fill em 1.091 trades: **média +0,005pt, mediana 0,000pt, custo total +$57,5
no ano inteiro**. 41,4% abrem levemente contra, compensados pelos 58,6% a favor. Não é problema.

---

## 3. RISCOS DE BACKTEST (Tarefa 2 — motor intrabar)

Configuração atual (confirmada no código e nos prints do NT8):
- `Calculate = OnBarClose`
- `OrderFillResolution = Standard` ("Padrão (Fastest)")
- `Slippage = 0`
- Série de entrada: 1 minuto
- **Tick Replay: não habilitado**

### A ambiguidade que NÃO pode ser resolvida com OHLC de 1 minuto
Dentro de uma barra de 1min que tem `High` e `Low` ambos além dos meus níveis, **é
impossível saber pelos dados OHLC qual foi tocado primeiro**. Os casos:

1. Entrada → sobe → cai → stop
2. Entrada → cai → stop (sem nunca subir)
3. Entrada → sobe → trailing acompanha → cai → saída no trailing

Com OHLC de 1min eu só sei que a barra teve aquele high e aquele low — **não a sequência**.
Qualquer backtest que afirme saber isso está inventando.

### Como quantifiquei em vez de inventar
Rodei **3 motores** sobre exatamente os mesmos sinais:

| Motor | Premissa intrabar | N | WR% | Ganho méd | Ratio | PF |
|---|---|---|---|---|---|---|
| `BAR_LAG` | o que o backtest faz (trailing com lag de 1 barra) | 1091 | 68,6% | $104,1 | 0,79 | 1,73 |
| `TICK_OTIM` | tick a tick, ordem intrabar **favorável** (limite superior) | 1166 | 79,4% | $97,1 | 0,74 | 2,86 |
| `TICK_PESS` | tick a tick, ordem intrabar **adversa** (limite inferior) | 1091 | 68,5% | $101,6 | 0,78 | 1,68 |
| **REAL** | execução de verdade | 84 | **67,1%** | **~$40** | **0,54** | — |

**Achado decisivo:** o WR real (67,1%) cai dentro da faixa dos modelos (68,5-68,6%), mas o
**ganho médio real ($40) está MUITO ABAIXO de todos os três limites ($97-104)** — inclusive
do cenário pessimista. Ou seja: **nem o pior cenário que consigo simular com barras de 1min
chega perto do que acontece de verdade.** Isso prova que a perda não está na ambiguidade
intrabar modelável — está na granularidade que barras de 1min simplesmente não capturam:
os micro-recuos de 1,75pt que o trailing tick a tick enxerga e a barra não.

### Consequência prática (importante)
**As grades de trailing/alvo e de gatilho de breakeven que rodamos nos dias 12-18/08 são
INVÁLIDAS para prever comportamento ao vivo.** Elas mediram o motor `BAR_LAG`, não o motor
real. A conclusão "trailing mais largo sempre piora" vale para o backtest e **não pode ser
transportada para a execução real** — no motor tick a tick, um trailing mais largo tem o
efeito oposto: sobrevive ao ruído intrabar em vez de ser estopado por ele.

### Diferenças entre ambientes
| Ambiente | `OnMarketData` roda? | Motor de saída efetivo |
|---|---|---|
| Backtest histórico | ❌ não | `GerenciaPosicao` (barra, lag 1) |
| Market Replay / Playback | ✅ sim | tick a tick (igual ao real) |
| Sim101 / conta real | ✅ sim | tick a tick |

**Por isso o forward test em Replay bateu com a realidade e o backtest não.** O Replay é o
único ambiente de teste que exercita o motor de saída verdadeiro.

---

## 4. ANÁLISE DA ENTRADA

**A entrada está saudável. Não é o problema.**

- Corrida simétrica ±12,5pt: sinal real **47,2%** vs aleatório **41,3%** → **+5,9pp de edge direcional**
- MFE/MAE médio: sinal real **1,40** vs aleatório **1,00**
- MFE mediano dos vencedores: **12,5pt** — há movimento favorável real disponível
- 42,2% dos vencedores alcançam **+15pt**; 27,8% alcançam **+20pt**; 12,0% alcançam **+30pt**
- Perda média real (-12,50pt) **bate exatamente** com o modelo → o lado ruim está sendo
  simulado com fidelidade; só o lado bom não está sendo capturado

**Conclusão: existe matéria-prima. O sinal entrega ~12,5pt medianos de excursão favorável
aos vencedores, e a execução atual captura 3,96pt disso (32%).**

---

## 5. ANÁLISE DO GERENCIAMENTO

### Ordem de avaliação em `GerenciaPosicao()` (backtest)
1. Inicializa stop/alvo sintéticos se `!gerenciando`
2. Checa **ALVO** (`High[0] >= alvoPrice`)
3. Checa **STOP** (`Low[0] <= stopPrice`)
4. **Só então** atualiza `favPrice` → breakeven → trailing

O passo 4 depois do 3 é o que cria o **lag de 1 barra** (documentado na linha 783:
*"vale a partir da proxima barra"*).

### Ordem em `OnMarketData()` (ao vivo)
1. Inicializa no 1º tick pós-fill
2. Atualiza `favPrice` e **aperta o stop imediatamente** (breakeven → trailing)
3. Checa alvo
4. Checa stop **já trilhado neste mesmo tick**

O passo 2 antes do 4 significa: **o stop trilhado pode ser atingido no mesmo tick em que
foi criado.** É o comportamento que gera o cluster de saídas em +2,50pt.

### Conflitos identificados
- **Stop no servidor vs stop sintético**: o servidor fica em `entry ± (12,5 + 5)pt` e, após
  o breakeven, vai para o nível de lock **menos** o buffer de 5pt. O sintético (tick a tick)
  sempre dispara antes. Funciona por design (anti-fantasma), mas significa que o servidor
  é só rede de segurança — **quem manda é o sintético tick a tick**.
- **`TP 60pt` é praticamente decorativo**: apenas **13 de 1.091 trades (1,2%)** atingiram o
  alvo no modelo, e **ZERO** nos 84 trades reais. O alvo não participa do resultado.

### Distribuição de saídas (modelo BAR_LAG)
| Motivo | N | % | PnL |
|---|---|---|---|
| TRAIL | 735 | 67,4% | +$70.172 |
| SL | 343 | 31,4% | -$44.933 |
| TP | 13 | 1,2% | +$7.722 |

**O trailing é 2/3 de todos os trades e é onde todo o resultado se decide.**

---

## 6. MFE / MAE

### Estatísticas (modelo BAR_LAG, 1.091 trades)
| Grupo | MFE médio | MFE mediano | MAE médio | MAE mediano |
|---|---|---|---|---|
| Todos | 13,05 | 9,25 | 11,03 | 8,75 |
| **Vencedores** | 16,64 | **12,50** | 6,68 | 5,25 |
| Perdedores | 5,20 | 2,75 | 20,52 | 17,25 |

### Buckets de MFE
| Bucket | Todos | Vencedores | Perdedores |
|---|---|---|---|
| +5 | 73,1% | 92,8% | 30,0% |
| +10 | 46,9% | 61,6% | 14,9% |
| **+15** | 31,6% | **42,2%** | 8,5% |
| **+20** | 21,0% | **27,8%** | 6,1% |
| +30 | 8,9% | 12,0% | 2,0% |
| +60 | 1,2% | 1,7% | 0,0% |

### Buckets de MAE
| Bucket | Vencedores | Perdedores |
|---|---|---|
| -2,5 | 75,5% | 100% |
| -5 | 53,9% | 100% |
| -10 | 22,2% | 100% |
| -12,5 | **10,7%** | 100% |

**Leitura importante:** 10,7% dos VENCEDORES chegaram a -12,5pt de excursão adversa antes de
virar. Ou seja, o stop de 12,5pt está bem no limite — apertá-lo mataria ~1 em cada 10 vencedores.
**Não mexer no stop.**

### Distribuição REAL dos ganhos (84 trades do forward test)
```
+2,50pt  ████████████████  16x  ← nível exato do breakeven-lock (24,2% dos ganhos)
+2,55pt  ████               4x
+2,75pt  ███                3x
+4,65pt  ███                3x
+4,95pt  ███                3x
...
+7,45pt  █                  1x  ← MAIOR GANHO DE TODOS
```
- Ganhos ≤ 5pt: **77,3%**
- Ganhos ≥ 12,5pt: **ZERO**
- Teto observado: **7,45pt**

---

## 7. HIPÓTESES

### H1 — "O problema está na entrada"
- **A favor:** nenhuma evidência
- **Contra:** edge de +5,9pp sobre aleatório; MFE/MAE 1,40 vs 1,00; perda média real bate
  exatamente com o modelo; 42% dos vencedores alcançam +15pt
- **Confiança: 5% — REJEITADA**

### H2 — "O problema está no gerenciamento da saída"
- **A favor:** ganho médio real (3,96pt) é 32% do MFE mediano disponível (12,5pt); 24,2% dos
  ganhos saem exatamente no nível do breakeven-lock; teto duro de 7,45pt em 84 trades;
  perdas batem com o modelo mas ganhos não
- **Contra:** nada relevante
- **Confiança: 90% — CONFIRMADA**

### H3 — "O problema está na implementação/backtest"
- **A favor:** backtest e live usam motores de saída **diferentes** (`GerenciaPosicao` vs
  `OnMarketData`); todas as otimizações de saída de 12-18/08 mediram o motor errado
- **Contra:** não é um *bug* — é uma divergência arquitetural documentada no código
- **Confiança: 75% — CONFIRMADA como causa da cegueira** (o backtest não erra o WR, erra
  o tamanho do ganho, e por isso vinha apontando otimizações inválidas)

### H4 — "O edge existe mas é estruturalmente pequeno"
- **A favor:** literatura confirma que reversão intraday em índice tem edge fino e sensível
  a custo; edge medido de +5,9pp é modesto
- **Contra:** **o MFE mediano de 12,5pt nos vencedores é material** — há 3x mais movimento
  disponível do que a execução atual captura. O problema imediato não é falta de edge, é
  falta de captura.
- **Confiança: 30% — PREMATURO CONCLUIR.** Só será testável depois de corrigir a captura.

---

## 8. O QUE **NÃO** DEVE SER ALTERADO

| Item | Por quê |
|---|---|
| **Lógica de entrada** (toque + rejeição + `MaxDist 15pt`) | Edge comprovado (+5,9pp). Não é o problema. |
| **`StopPontos = 12,5`** | 10,7% dos vencedores tocam -12,5pt antes de virar. Apertar mata 1 em 10 vencedores. Alargar já foi testado ao vivo em 14/08 e deu 60% pior. |
| **`TolToqueTicks = 20`** | Não é gargalo; sensibilidade já medida. |
| **`Calculate = OnBarClose`** | Correto — evita o erro nº1 da comunidade (re-entradas em `OnEachTick`). |
| **Toda a camada de robustez** | Recovery, anti-reset de PnL, guard de conexão, buffer anti-fantasma, `AdoptAccountPosition` — são acertos raros. Não tocar. |
| **`SegUsaDomingo`** | Validado, fora do escopo do problema. |

---

## 9. O QUE VALE TESTAR (com hipótese causal, não busca de parâmetro)

### 🥇 Prioridade 1 — Alargar o trailing, testado NO MOTOR CERTO
**Hipótese causal:** o trailing de 1,75pt aplicado tick a tick encerra o trade no primeiro
micro-recuo, capturando 3,96pt de um MFE mediano de 12,5pt. Um trailing proporcional ao
ruído real do MNQ (ex.: 4-8pt, ou baseado em ATR) sobreviveria à oscilação intrabar e
capturaria uma fração maior da excursão que já está comprovadamente disponível.

**Como testar:** **exclusivamente em Market Replay** (único ambiente que roda `OnMarketData`).
Backtest não serve — mede o motor errado.

**Métrica de sucesso:** ganho médio em PONTOS acima de 3,96pt, com WR não caindo abaixo de
~55% (há folga: com ratio 1,0 o breakeven de WR é 50%).

### 🥈 Prioridade 2 — Repensar o breakeven-lock em +2,5pt
**Hipótese causal:** 24,2% dos ganhos reais saem exatamente em +2,50pt. Esse nível está
travando lucro cedo demais e criando um piso artificial que domina a distribuição.
Testar lock proporcional (ex.: 50% do MFE já alcançado) ou remover o lock fixo mantendo só
o trailing.

### 🥉 Prioridade 3 — Corrigir os bugs de fuso e contagem
Itens 3 e 4 da seção 2 (`TradesHoje()` sem ET, `diasOperados` perdendo trades intrabar).
Baixo impacto no PnL, mas afetam gates de risco e o critério de aprovação.

### ❌ Não fazer
- Nova busca de grade em backtest bar-based (mede o motor errado)
- Mexer em entrada, stop ou tolerância
- Adicionar filtros que reduzam a amostra (ADX já testado e rejeitado)

---

## 10. RISCOS APEX (Tarefa 9)

| Risco | Estado | Observação |
|---|---|---|
| Limite de perda diária | ✅ `StopDiarioDolar = 750` + persistência anti-reset | Robusto |
| Drawdown | ⚠️ | Backtest usa DD $1.500; **conta real $25K tem DD $1.000** — divergência já sinalizada em 23/06. **Precisa ser confirmado no dashboard.** |
| Máx. contratos | ✅ `Contratos = 5`, `EntriesPerDirection = 1` | |
| Risco por trade | ✅ ~$125-136 (12,5pt × 5 MNQ) ≈ 13% do DD | |
| Múltiplas posições | ✅ `EntryHandling.AllEntries` + check de `Flat` | |
| Ordens duplicadas | 🟡 | Entre envio e fill, `MarketPosition` ainda é `Flat`. Mitigado por `EntriesPerDirection=1`, mas não impossível em mercado rápido. |
| Reconexão | ✅ RECOVERY + `AdoptAccountPosition` + anti-reset de PnL | Bem resolvido |
| Reentrada em loop | ✅ `MaxTradesDia = 12` + filtro anti-chase | |
| Operar após limite | ✅ `bloqueadoHoje` + `aprovado` | |
| Abertura/fechamento | ✅ Flatten 16h55 + `IsExitOnSessionCloseStrategy` | |
| Gaps | ✅ Medido: impacto desprezível (+$57,5/ano) | |
| Erro de execução | 🔴 | `IgnoreAllErrors` engole rejeições silenciosamente. Se uma saída for rejeitada, o bot pode achar que está flat sem estar. |
| **Automação na Apex** | 🔴 **PRECISA SER CONFIRMADO** | Pesquisa de 23/06 indica que a Apex proíbe automação em todas as fases. Não assumir nada sem confirmação direta. |

---

## RECOMENDAÇÃO FINAL

> **Minha recomendação para o próximo experimento é: rodar Market Replay nos MESMOS dias de
> junho já testados (01-12/06), mudando APENAS `TrailingPontos` de 1,75 para 5,0 — e comparar
> o GANHO MÉDIO EM PONTOS contra o baseline real de 3,96pt.**

**Por que este e não outro:**
1. É a única hipótese que explica o dado central (teto duro de 7,45pt, cluster em +2,50pt)
2. É um **único parâmetro**, com hipótese causal explícita — não é busca de grade
3. Tem baseline real de comparação já coletado (84 trades, 3,96pt de ganho médio)
4. Só pode ser testado em Replay — e é barato: 10 dias de replay já dão sinal claro
5. Se o ganho médio não subir de 3,96pt, **H4 (edge estruturalmente pequeno) passa a ser a
   explicação principal** e aí sim a discussão muda de patamar

**Critério de decisão definido ANTES do teste (pra não virar overfitting):**
- ✅ Sucesso: ganho médio ≥ 6pt **e** WR ≥ 55%
- ❌ Falha: ganho médio < 5pt **ou** WR < 50%
- 🤔 Inconclusivo: entre os dois → ampliar amostra antes de decidir

---

*Auditoria feita sem alterar uma linha de `src/BotAprovacao.cs`.*
