# Análise de Comitê — AberturaNYSpecAndersson — 45 dias reais (jun+jul/2026)

Diagnóstico completo (FASE 1) do forward test em Market Replay tick-a-tick, `src/AberturaNYSpecAndersson.cs`,
config default (Gatilho 10t/60s, Stop $250, Alvo $500, BE ativa $100/protege $0/incremento $50, 6 MNQ).
Dataset: 22 dias de junho + 23 dias de julho/2026 = **45 trades, 1 por dia**. Nenhuma alteração de código
foi feita — isto é só diagnóstico, conforme solicitado.

## 1. QUANTITATIVE — números do sistema (45 trades)

| Métrica | Valor |
|---|---|
| Net Profit | **−$340,50** |
| Gross Profit | $2.242,50 |
| Gross Loss | $2.583,00 |
| Profit Factor | **0,87** |
| Win Rate | **37,8%** (17W / 28L) |
| Average Trade (Expectancy) | **−$7,57** |
| Average Winner | +$131,91 |
| Average Loser | −$92,25 |
| Payoff Ratio | 1,43 |
| Max Drawdown (mês-a-mês, resetando) | $908,00 (jun) / $758,50 (jul) |
| **Max Drawdown (curva contínua, sem reset)** | **$1.162,50** (pico $714,50 em 09/06 → fundo −$448,00 em 16/07) |
| Recovery Factor | −0,29 (não aplicável, net negativo) |
| Sharpe-like (por trade, não anualizado) | ≈ −0,048 (desvio-padrão $158,75) — ⚠️ N pequeno, ver ressalva |
| Maior sequência de vitórias | 5 (01-05/06) |
| Maior sequência de derrotas | **6** (18-25/06) **e 6** (09-16/07) — duas vezes |
| R-Multiple médio (R = $250 nominal) | −0,03R |

**MFE / MAE / ETD / duração exata dos trades: DADOS INSUFICIENTES PARA CONCLUIR** — não temos o
tick-a-tick intrabar de cada trade, só entrada/saída/motivo. O CSV nativo do `.cs`
(`trades_abertura_andersson.csv`) teria isso se exportado e lido linha a linha; não foi feito aqui.

## 2. Segmentação por TIPO DE SAÍDA (achado mais forte do dataset)

| Saída | n | % dos trades | Soma | Média/trade |
|---|---|---|---|---|
| AbTrail | 24 | 53% | **+$2.035,50** | **+$84,81** |
| AbStop | 12 | 27% | **−$2.377,00** | **−$198,08** |
| AbBe | 9 | 20% | +$1,00 | +$0,11 (essencialmente zero, como desenhado) |

**O que isso mostra:** o sistema de saída se comporta EXATAMENTE como projetado — `AbBe` é
neutro (trava perto do zero, cumpre a função), `AbTrail` é fortemente positivo (+$84,81/trade,
n=24, mais da metade dos trades). O problema inteiro do sistema está concentrado nos 12 trades
(27%) que batem `AbStop`: média de −$198/trade, e dentro desse grupo a variância é enorme — de
−$8 (quase nada) a −$372,50 (48% pior que o nominal $250).

**Hipótese:** a entrada tem alguma capacidade real de identificar quando o movimento vai
continuar (73% dos trades nunca precisam do stop cheio) — isso não é óbvio a priori numa moeda
ao ar (que daria mais TAKE/STOP e menos BE/TRAIL). O problema não parece estar SÓ na entrada;
está em quanto os 27% de trades ruins custam quando dão errado.

**Risco desta conclusão:** N=12 no grupo AbStop é pequeno — um ou dois outliers de slippage
($359, $372,50, $345, $285,50 — 4 dos 12 já são >$250, ou seja MAIORES que o nominal) dominam a
média do grupo. Sem eles, a média de AbStop cairia bastante. Ver seção 5 (microestrutura).

## 3. Segmentação LONG x SHORT

| Direção | n | Soma | Média/trade |
|---|---|---|---|
| LONG | 22 | −$310,00 | −$14,09 |
| SHORT | 23 | −$30,50 | −$1,33 |

SHORT ficou bem mais perto do零 que LONG. **Risco da conclusão:** N=22/23 é pequeno, e MNQ nesse
período (jun-jul/2026) teve viés de alta na maior parte do tempo (visível nos gráficos —
sequências de candles verdes maiores que vermelhos). Pode ser (a) a estratégia realmente lida
melhor com reversões/quedas nesse instrumento, ou (b) put simplesmente pegou menos dos poucos
trades SHORT grandes perdedores por acaso da amostra. **Não é suficiente pra filtrar direção.**

## 4. Segmentação por DIA DA SEMANA (n=9 cada, EXTREMAMENTE frágil)

| Dia | Soma | Média/trade |
|---|---|---|
| Segunda | +$560,50 | +$62,28 |
| Terça | −$510,00 | −$56,67 |
| Quarta | +$474,00 | +$52,67 |
| Quinta | −$225,50 | −$25,06 |
| Sexta | −$639,50 | −$71,06 |

**ADVOGADO DO DIABO (persona 7):** este padrão parece bonito (alterna +/−/+/−/−) mas com n=9
por dia é ruído clássico — 1-2 trades grandes bastam pra virar a média inteira. Sexta, por
exemplo, é dominada por só 3 trades grandes: −$372,50 (10/07), −$266,50 (19/06) e −$241,50
(12/06) somam −$880,50 sozinhos, mais que o total do grupo. **NÃO existe justificativa
estrutural de mercado óbvia pra "sexta é pior"** (não é vencimento, não é NFP toda sexta) — é
muito provável que seja só a amostra pequena concentrando outliers num dia. **Não filtrar por
dia da semana com esse tamanho de amostra.**

## 5. MARKET MICROSTRUCTURE / NINJASCRIPT — o achado técnico mais sério

Quatro trades tiveram o stop sintético (`StopLossDolares=$250`, ordem a mercado disparada
tick-a-tick via `OnMarketData`) encher **pior que o nível nominal**:

| Dia | Nominal | Real | Slippage |
|---|---|---|---|
| 23/06 | −$250 | −$359,00 | **+44%** |
| 10/07 | −$250 | −$372,50 | **+49%** |
| 14/07 | −$250 | −$285,50 | +14% |
| 07/07 | −$250 | −$214,50 | (dentro do esperado, ok) |

**Por quê isso acontece (persona 4+5):** o `.cs` usa monitoramento sintético — a cada tick
calcula `pnl <= stopDolLock` e manda `ExitLong/ExitShort` (ordem A MERCADO) quando verdadeiro.
Num movimento rápido (spike na abertura, que é justamente onde essa estratégia entra), entre o
tick que dispara a condição e o fill da ordem a mercado, o preço já andou mais — em Tick Replay
isso é fiel ao que aconteceria numa conta real nesse instante de velocidade. **Isso não é bug do
código nem do teste — é o comportamento real de "stop sintético" em mercado rápido.** Os
`.cs` originais do Andersson (`AberturaNYBreakout_andersson.cs`) usam `ExitLongStopMarket`
(ordem STOP nativa do NT8, registrada na corretora) em vez de monitoramento tick a tick — isso
NÃO elimina o risco de slippage (ordem stop também vira ordem a mercado quando tocada), mas
tende a reagir mais rápido que um loop de comparação em `OnMarketData`, porque fica registrada
no book em vez de esperar o próximo tick pra ser avaliada em código gerenciado.

**Diferença Tick Replay vs Strategy Analyzer padrão:** os logs confirmam `Calculate: OnEachTick`
e `Tick Replay ligado` — correto pro que estamos testando. Se estivesse rodando em
`OnBarClose`/sem tick replay, o problema de slippage FICARIA ESCONDIDO (o backtest ignoraria
movimento intrabar), e o Marcelo só descobriria isso ao vivo — **o teste está sendo feito do
jeito certo**, e é exatamente por isso que apareceu.

## 6. BACKTEST & VALIDATION — podemos confiar nisso?

- **Tick Replay real, 45 dias, 2 meses não-contíguos de dados out-of-sample um do outro** (julho
  não foi otimizado olhando junho) — isso é validação **out-of-sample honesta**, não walk-forward
  formal, mas também não é in-sample/overfit no sentido comum.
- **O achado crítico da curva contínua** (seção 1): tratar junho e julho como duas avaliações
  separadas ($0 a cada mês) mascarou um drawdown de $1.162,50 que uma conta real, operando sem
  parar, teria sentido cheio — **isso estouraria o limite de $1.000 EOD de verdade**. O placar
  mês-a-mês não estava errado como registro de "essa avaliação específica passaria?", mas estava
  incompleto como resposta a "essa estratégia é segura pra rodar ao vivo?".
- **N=45 trades (1/dia) é pequeno** pra qualquer estatística de segunda ordem (Sharpe, streaks,
  segmentações). O sinal mais confiável do dataset é a segmentação por tipo de saída (seção 2),
  porque não depende de agrupar por data/calendário — é uma propriedade estrutural do próprio
  mecanismo de gestão, com N maior por grupo (24/12/9) e uma lógica causal clara.

## 7. STRATEGY ARCHITECT — a hipótese de mercado é explicável?

- **O que a entrada tenta explorar:** momentum de curtíssimo prazo no exato instante da abertura
  de NY — aposta que um movimento de 10 ticks no 1º minuto tende a continuar. Mecanismo
  plausível: ordens institucionais / ordens a mercado acumuladas overnight sendo liberadas de
  uma vez na abertura podem gerar continuidade por alguns minutos (efeito conhecido, mas
  historicamente contestado — ver o achado de hoje mais cedo com o harness causal: seguir o
  rompimento simples deu −$11/trade sem BE progressivo).
- **Por que o stop está em $250:** não tem justificativa técnica documentada (é um valor redondo
  escolhido pelo Andersson) — não é baseado em ATR, não é baseado em volatilidade do instrumento
  no horário. Isso é uma bandeira amarela: um stop fixo em $ (não em volatilidade) tende a ser
  ora largo demais, ora apertado demais, dependendo do dia.
- **Por que o BE progressivo existe:** faz sentido — proteger lucro conforme o trade avança é
  gestão de risco padrão. **Os dados confirmam que funciona** (seção 2: AbTrail é o motor
  positivo do sistema).
- **Onde deveria funcionar:** dias com tendência real logo na abertura (gap + continuação).
- **Onde deveria falhar:** dias de abertura falsa/whipsaw (rompe, reverte, rompe de novo) — que é
  exatamente o padrão descrito nos dias de `AbStop` com slippage grande.
- **Sinal de alerta:** não temos como, com os dados atuais, DISTINGUIR de antemão (antes da
  entrada) um dia "vai tender" de um dia "vai ser whipsaw" — a estratégia entra igual nos dois
  casos. Isso é a lacuna central: falta um filtro de CONTEXTO, não um ajuste de gestão.

## 8. ANTI-OVERFITTING — o que NÃO fazer agora

- Não reduzir o stop baseado nos 4 slippages grandes — isso são movimentos de mercado, um stop
  menor teria batido ANTES e ainda sofrido slippage proporcional, ou pior, cortado trades que
  iriam virar `AbTrail` positivo.
- Não filtrar por dia da semana (seção 4) — amostra pequena demais, sem causa estrutural.
- Não trocar de direção (fadar em vez de seguir) baseado em LONG x SHORT (seção 3) — diferença
  pequena, mesmo problema de amostra.
- **Qualquer alteração precisa de uma hipótese de mercado ANTES do teste, não depois de olhar
  o resultado.** A única hipótese com evidência estrutural (não coincidência de calendário) é a
  da seção 2: o problema está concentrado na cauda do grupo `AbStop`.

## 9. FASE 2 — HIPÓTESES (ranqueadas por evidência)

**H1 (forte, evidência estrutural):** A vantagem do sistema está no mecanismo de BE progressivo
protegendo trades que vão bem (`AbTrail`, +$84,81/trade, n=24) — mas o `StopLossDolares=$250`
fixo, monitorado sinteticamente tick-a-tick, sofre slippage desproporcional em spikes rápidos,
tornando a cauda de perdas (`AbStop`, n=12) maior que o necessário. **O problema está na
EXECUÇÃO da saída de proteção máxima, não na entrada nem no BE.**

**H2 (moderada, sem teste ainda):** Não existe filtro de contexto de mercado (volatilidade
overnight, tamanho do gap, dia de evento macro) — a estratégia entra igual em todo dia. Dias que
viram `AbStop` grande podem ter uma assinatura de contexto ANTES da abertura (ex: gap grande +
reversão) que diferenciaria de dias `AbTrail`. **DADOS INSUFICIENTES pra confirmar** — não
capturamos o contexto overnight desses 45 dias especificamente.

**H3 (fraca, provável ruído):** dia da semana e direção (LONG/SHORT) têm alguma influência.
Evidência insuficiente, N pequeno demais — tratar como ruído até n ficar bem maior.

## 10. FASE 3 — UM experimento recomendado (não cinco)

**Teste único:** trocar o mecanismo de saída do stop de "monitoramento sintético + ExitLong/
ExitShort a mercado" para **ordem STOP nativa do NT8** (`ExitLongStopMarket`/`ExitShortStopMarket`),
mantendo TODOS os outros parâmetros idênticos (mesmo $250, mesmo BE progressivo, mesmo gatilho).

**Por que esse e não outro:** é o único ajuste com justificativa de mercado clara (seção 5 —
ordem nativa registrada no book reage antes que um loop de comparação em `OnMarketData`) e não
mexe em NENHUM parâmetro que dependa de olhar o resultado passado (não é curve-fitting).

**Métrica pra validar:** comparar a MÉDIA e o PIOR CASO do grupo `AbStop` (seção 2) entre a
versão atual e a versão com ordem nativa, nos MESMOS 45 dias (mesma sequência de sinais de
entrada — só a execução do stop muda). Se a média do grupo `AbStop` melhorar de −$198 pra mais
perto de −$250 (ou seja, menos slippage) SEM piorar o grupo `AbTrail`, é evidência real de que o
problema era de execução, não de sinal.

## 11. FASE 6 — CLASSIFICAÇÃO

**Sistema atual (`AberturaNYSpecAndersson.cs`, config default): INVESTIGATE.**

Não é REJECT — o mecanismo de BE progressivo tem uma perna claramente positiva e estatisticamente
não-trivial (n=24, +$84,81/trade). Não é KEEP — net profit negativo em 45 dias reais, e o
drawdown contínuo real ($1.162,50) estouraria uma conta de verdade. A decisão certa é isolar e
testar a hipótese H1 (execução do stop) antes de descartar ou promover a estratégia.
