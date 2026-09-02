# Bot Trade NT8 (BotAprovacao) - Progresso

## Última atualização: 2026-09-02 — Candidata B (event 8h30) TESTADA e SEM EDGE. Candidata C (gap-and-go) apareceu com PF ~1,3 IS≈OOS — primeira coisa robusta do projeto. Próximo: refinar C + grill-me + NT8 Analyzer.

## 🔵 02/09 — Itens 1-3 do plano: B testada (morta), C promissora

**Protótipo Python — decisão final é sempre no NT8 Analyzer.** Dado: MNQ 1-min 2022-2026
(Databento). IS = 2022-2025, holdout = 2026.

### Item 1 — lista de releases 8h30 ET (`backtest/run_event_830.py`)
Detectada DO PRÓPRIO DADO: um release das 8h30 ET produz spike de volume 10-30× no minuto
exato (ex.: CPI 12/02/2025 8h30 ET = 16.064 contr vs ~500 antes). **241 dias de release**
2022-2026 (vol barra 8h30 ≥ 3× mediana móvel 20d). Classificados por posição no calendário
(Qui=claims, Sex cedo=NFP, meio=CPI/PPI/retail, fim=GDP/PCE). Contagem bate com o esperado
(~150-190/ano com claims semanal).

### Item 2 — teste tosco: candidata B NÃO tem edge
Breakout do range 8h25-30 na barra 8h30, bracket fixo, slippage 3-5t, flat 9h00 ET:

| Variante | PF IS 2022-2025 | Leitura |
|---|---|---|
| Breakout puro (todas as configs SL/RR) | **0,92 – 0,98** | coin flip; avgW ≈ avgL |
| FADE (contra o rompimento) | 0,48 – 0,84 | pior ainda |
| DELAY (entra na 8h32 no range 8h30+31) | 1,4 mas **n=33 (8/ano)**, holdout misto | overfit / amostra ínfima |
| Só eventos grandes (vol ≥10×) | 2,16 mas **n=25, holdout PF 0,00** | overfit de regime |
| Ride the trend (segura até 10h-13h) | 0,80 – 0,88, DD até −$35k | **pior quanto mais segura** — mean-reverte |
| NFP-only ride | 0,42 | morto |

**O movimento das 8h30 é ruído depois do slippage.** O spike não prevê o follow-through de
30 min; segurar mais tempo reverte contra. Confirma o próprio risco do doc ("head fake dos
releases"). **Corte = PF > 1,3 IS. Nada legítimo passa. → NÃO escreve o .cs da B. B morta.**
(B entra no cemitério: reversão, ORB, EMA/VWAP, ICT, Renko, breakout, squeeze, RSI, IB, event.)

### Item 3 — B reprovou o gate → probe da candidata C (`backtest/run_gap_open.py`)
Gap RTH open (9h30 ET) vs prior RTH close (16h00 ET):
- **gap-FILL (fade) = catástrofe**: PF 0,22–0,36, −$40k a −$69k. O MNQ **tende**, não volta pro close.
- **gap-and-GO** (gap médio que segura os 1os 15 min → vai a favor, bracket 2:1, flat 13h ET):

| Banda de gap | PF IS 22-25 | PF holdout 26 | n IS | maxDD IS |
|---|---|---|---|---|
| 20-150 pt, 2:1 | **1,29** | **1,30** | 380 | −$6,5k |
| 30-200 pt, 2:1 | 1,23 | 1,27 | 402 | −$6,5k |
| 30-200 pt, 3:1 flat13h | 1,15 | 1,37 | 402 | −$11k |

gap 30-200 / 2:1 **ano a ano: 2022 PF 1,48 · 2023 1,25 · 2024 1,26 · 2025 1,08 · 2026 1,27** —
**positivo TODO ano.** Primeira coisa da exploração toda com IS ≈ OOS. ~100 trades/ano, avg
~$55/trade, ~$5,5-6,8k/ano líquido em 5 MNQ (5c) após custo+slippage.

**Ressalvas (não empolgar ainda):**
1. Motor Python é ~40% otimista no PF → PF 1,29 aqui pode ser ~1,0-1,1 no NT8 Analyzer.
2. Lógica ainda tosca (entrada no minuto 15, risco = distância ao extremo dos 15 min).
3. **maxDD −$6,5k contra o DD trailing de $1.000 da Apex = estoura.** Precisa firma de DD
   estático (opção C da análise da reversão) OU risco bem mais apertado / menos contratos.
4. WR 40-42% (o alvo 2:1 faz o trabalho — exige disciplina).

### Próxima sessão
1. **Refinar a gap-and-go em Python** (entrada melhor, risco melhor, filtro de dia) — objetivo:
   PF folgado > 1,3 IS com regra limpa, DD menor.
2. **grill-me** na regra final.
3. **Escrever `.cs` mínimo da gap-and-go** e rodar o **NT8 Strategy Analyzer** 2022-2025 (o teste
   de verdade). Só continua se PF > 1,3 lá também.
4. Se passar: firma de DD estático (Tradeify/MFFU/TPT) — o DD de $6,5k não cabe no trailing Apex.
5. Produção (`BotAprovacao.cs`) segue INTACTA. Nada escrito ainda.

---


## 🔴 01/09 (noite, fim) — OOS: a reversão morreu. Pivot pra estratégia nova.

Short-only importado 2022-2025 no NT8 (`MNQ 12-25`, dado do Databento):
**PF 0,91 · −$894 · 201 trades · avg −$4,45/trade · Max DD −$2.372.** Perdedor nos 4 anos.
O PF 1,44 de 2026 era sorte de regime (2026 teve ~3× mais setups e funcionaram). O motor
Python do projeto estava errado no OOS também (dizia lucro todo ano).

**A reversão PDH/PDL no MNQ não tem edge fora da amostra — nem both-sides, nem short.**
Firma de DD estático não conserta PF < 1. Já morreram no projeto: ORB, EMA/VWAP, ICT, Renko,
rompimento, squeeze, RSI-reversion, e agora a reversão fora de 2026.

**Marcelo escolheu opção 2: estratégia nova do zero (não variação da reversão).**
- **B (escolhida) — event-driven: spike das 8h30 ET** (CPI/PPI/NFP/claims/retail/GDP/PCE).
  Segue o 1º fechamento de 1-min pós-release, bracket fixo apertado, flat em 15-30min. Melhor
  encaixe no DD trailing (exposição de minutos, perda travada). Mecanismo distinto de tudo já
  testado.
- A — seguir tendência intradiária (momentum continuation). Conceitualmente a mais correta
  (o MNQ tende), mas risco de perdas em cluster no DD.
- C — gap de abertura (Globex→RTH). Nunca testado direito. Rápido de testar.

Detalhe completo das 3 + regras do jogo (NT8 é o motor, OOS 2022-2025 / holdout 2026, slippage
agressivo, bracket fixo sem trailing tick, corte PF > 1,3): **`docs/estrategia-nova-2026-09.md`**.

**Começar 02/09:** montar lista de releases 8h30 ET 2022-2026, teste tosco no Analisador.
Produção intacta.


## 🎯 01/09 (noite) — TESTES NO STRATEGY ANALYZER + descoberta do SHORT-ONLY

O motor Python do projeto estava **~40% otimista no PF e pegava ~6x mais trades** que o
Analisador de Estratégia do NT8 (que roda o `.cs` compilado de verdade). **O Analisador
passou a ser a fonte da verdade.** Rodadas no `BotAprovacao_BETrigger25` / MNQ SEP26 / 1min,
~7 meses (jan-ago 2026, único período com dado nesse contrato):

| Config | Comissão | PF | Líquido | Max DD |
|---|---|---|---|---|
| Baseline (alvo 60, trail 1,75, BE 2,5) | não | 1,23 | +$1.965 | −$1.192 |
| Baseline | **sim** | **0,96** | **−$690** | −$3.167 |
| Teste A (alvo 12, BE off, trail 0) | não | 0,90 | — | — |
| Teste B (alvo 40, BE 4, trail 8) + parcial ON | não | 1,24 | +$2.020 | −$1.187 |
| Teste B | **sim** | **0,96** | **−$746** | −$3.287 |
| Teste C (BE gat. 6, trail 1,75, alvo 60) | não | 0,97 | — | — |

**Com comissão real, NENHUMA variação de saída passa de PF ~0,96.** A comissão (~$6,50/RT ×
251 trades = $1.631) come o ganho bruto. A saída parcial **não dá pra testar no Analisador**
(está no `OnMarketData`, que não roda em backtest) — só no Market Replay.

**ACHADO GRANDE: o LONG está morto, o SHORT carrega tudo.** Em TODOS os testes:
Long PF 0,85 (net −$1.136) · Short PF 1,04 (net +$389). Rodando **`So operar SHORT` isolado**
(novo parâmetro no `.cs`, commit 4a6ad83): **PF 1,44 · +$1.516 · Max DD −$716 · Sortino 6,88**
em ~7 meses, com comissão. Curva robusta de verdade — mas **lenta**: ~$216/mês com 5 contratos,
não bate $1.500/30 dias na Apex. Serve pra **firma de DD estático sem prazo**.

## 🔬 01/09 (noite) — OPÇÃO D: OOS longo (Databento 2022-2026)

Baixado MNQ OHLCV-1m 2022-06 → 2026-08 do Databento ($9,02 / crédito grátis; total gasto $16,62).
`backtest/oos_short_only_4anos.py` — reversão SHORT-ONLY por ano (motor Python, otimista):

| Ano | PF | Líquido |
|---|---|---|
| 2022 (jun+) | 1,26 | +$5.386 |
| 2023 | **1,12** | +$4.426 |
| 2024 | 1,42 | +$15.169 |
| 2025 | 1,42 | +$15.684 |
| 2026 | 1,54 | +$15.404 |

**Não é fluke de 2026** — PF > 1,1 todo ano, melhorando com o tempo. **2023 é o ano fraco**
(PF 1,12 otimista → provável ~breakeven real). Python 2026 short-only (1,54) ≈ NT8 2026 (1,44)
→ o motor track bem PRA SHORT-ONLY (não pro both-sides).

**PENDENTE (Marcelo no NT8):** importar `dados_databento/MNQ_NT8_import_2022_2026.zip`
(→ `MNQ 12-25`, front-month contínuo, timestamp já em horário de Chicago) via Ferramentas →
Dados históricos → Importar. Rodar o Analisador short-only em 2022-01 → 2025-12.
- PF > 1,2 e 2023 > 1,0 → edge real, ir pra firma de DD estático (opção C).
- 2023 < 1,0 → sem robustez, encerrar a reversão.

Produção intacta. `.cs` alterado só o BETrigger25 (item #18 + `SoOperarShort`), não produção.


## 🔬 01/09 — AUDITORIA COMPLETA do forward test de julho (`docs/auditoria-julho-2026.md`)

Forward test do BETrigger25 rodado 01-20/07 (Market Replay ao vivo): **acumulado −$771, PF 0,44,
WR 45%, E −$17,5/trade** em 44 trades. Pausado em 22/07 pelo bug do item #18 (níveis zerados no
restart — 21 e 22/07 mortos). Auditoria nos 4 papéis (quant / trader / price action / eng. NT8).

**ACHADO CENTRAL:** o backtest de 13 meses dá **PF 1,50, WR 73%, ZERO meses vermelhos em 13**. O
forward test está em PF 0,44. A causa é estrutural: `Calculate = OnBarClose` → o **backtest** gere
a saída 1× por barra (segura o trade através de repiques intrabar); **ao vivo**, `OnMarketData`
gere tick a tick e sai no 1º repique. Resultado: **avgW $80 → $31, WR 73% → 45%** — ~28 trades a
cada 100 que o backtest conta como ganho pequeno saem no breakeven ao vivo. **O edge de "100% de
aprovação" pode ser artefato de `OnBarClose`** (Tick Replay não estava ligado no gráfico).

**Problemas (classificados A-G):** #1 gestão intrabar estrangula os ganhos [F+C] — o principal,
~−$1.100/mês; #2 facada [E] — 7 dos 9 grandes losses de julho (−$975), sem filtro possível; #3 gap
de entrada [F+B] — 2 casos, fill +10-11pt após vela de spike, −$300; #4 pdHigh/pdLow zeram no
restart [A] — BLOQUEANTE, matou 21-22/07; #5 custos = 63% do prejuízo [D]; #6 overfit do backtest
original [G].

**FASE 0 EXECUTADA (01/09):** (1) ✅ **item #18 CORRIGIDO** — método `SincronizaNiveisComHistorico()`
em `BotAprovacao_BETrigger25.cs` + `BotAprovacaoDow_MYM.cs` (reconstrói os níveis varrendo o
histórico; assinatura não mudou, só recompilar). `backtest/run_trailing_bridge.py` (ponte
browniana ≈ Tick Replay) CONFIRMA: gestão tick-a-tick capa o avgW em **~$35** (vs $80 OnBarClose;
forward real $31), e **afrouxar o trailing não recupera** — quem capa é o BE-lock 0,75. **O edge
de PF 1,50 é artefato de `OnBarClose`.** Próximo (Marcelo no NT8): (2) **LIGAR TICK
REPLAY** no gráfico e re-rodar o backtest de 13 meses do BETrigger25 — se der PF 0,4-0,8, o edge
histórico era artefato de `OnBarClose` e a estratégia precisa ser repensada, não ajustada; se der
PF > 1,3, ir pra Fase 1 (revisar entrada `OnMarketData`, sweep de trailing com Tick Replay,
reduzir pra 2-3 MNQ). Nada mexido em produção nem nos `.cs`.



## 🆕 01/09 (fim do dia) — Bot novo: `src/BotAprovacaoDow_MYM.cs` (MYM + DD estático)

Marcelo decidiu perseguir as 2 alavancas da direção B **juntas**, em cima do "3º bot" da linhagem
(`BotAprovacao_BETrigger25.cs`):
1. **MYM** (Micro Dow, $0,50/pt, tick 1pt) em vez de MNQ
2. **Firma de DD estático** (Tradeify/MFFU/TPT) em vez do DD trailing intradiário da Apex

**`src/BotAprovacaoDow_MYM.cs`** = cópia do BETrigger25 com **só** o instrumento + params trocados
(mesma lógica de entrada/gestão/recovery/stop servidor/fuso, byte-idêntica). Mudanças: nome da
classe, defaults escalados pro Dow (SL 29 / TP 117 / BE +9→+6 / trail 2 / tol 12 ticks / maxdist
35 / 5 contratos), `UsarBELockProporcional=false`, $/pt nos logs (2,0→0,5), nome do arquivo de
PnL. `MetaLucroDolar` / `StopDiarioDolar` / `MinDiasOperados` ficam como campos ⚠️ a ajustar
conforme a firma. Ficha completa + firmas a levantar + passo a passo do forward test:
**`docs/bot-mym-dd-estatico.md`**.

⚠️ **NÃO validado ao vivo.** Produção (`BotAprovacao.cs`) e os outros `.cs` **não foram tocados.**

### 🔴 REVISÃO (mesmo dia) — as 2 alavancas são separáveis, só uma vale (`run_mnq_mym_junto.py`)

Marcelo perguntou se dá pra agregar o MYM ao BETrigger25 e testar junto. Testado (MNQ + MYM na
mesma conta, P&L/DD/meta compartilhados):

| DD estático, 5c cada | Taxa | OOS |
|---|---|---|
| **MNQ sozinho (params BETrigger25)** | **75%** | 62%/69% |
| MYM sozinho | 23% | 0%/33% |
| MNQ + MYM juntos | 73% | 56%/91% (mais estouros) |

- **Juntar MYM não ajuda** — MNQ e MYM são ~0,9 correlacionados (Nasdaq × Dow), é dobrar a mesma
  aposta.
- **Lever 1 (DD estático) NÃO é código** — aplica ao BETrigger25 direto, só trocar de firma. E
  ajuda MUITO: params do BETrigger25 no dado do Databento vão de 43% → **62% (Apex) / 75%
  (estático)**. Confirmação forte do edge do BETrigger25 num dado independente do NT8.
- **Caminho recomendado:** `BotAprovacao_BETrigger25.cs` (MNQ) numa firma de DD estático. Sem
  código novo. `BotAprovacaoDow_MYM.cs` fica como experimento opcional.

**Próximo:**
1. Marcelo levanta termos de 1 firma de DD estático (automação + DD estático de verdade + preço +
   consistência) → seta `Meta`/`StopDiario`/`MinDias` no BETrigger25.
2. **🔀 Forward test do BETrigger25 muda de JUNHO pra JULHO/2026** (junho é o pior mês pro achado
   do BE trig 2,5; 9 de 13 meses melhoram). Retomar do dia 01/07. Pasta criada:
   `forward-test-replay-25k/2026-07-betrigger25/` (placar-mes.md com o scaffold pronto).

## 🧪 01/09 — Direção B: Renko + modelos de DD + MES/M2K/MYM (dado real Databento)

Sessão inteira na **decisão estratégica em aberto desde 23/08** (aceitar ~50% e escalar vs.
repensar do zero). Marcelo pediu pra testar Renko + MA no motor de aprovação de 30 dias e varrer
as outras possibilidades da direção B. **Nada tocado em produção nem nos `.cs`.** Detalhe completo:
`docs/melhorias-sugeridas.md` #22 + `historico/2026-09-01.md`.

- **Renko + MA:** sem edge. Gestão de tendência = **0% de aprovação em toda config, PF 0,77–0,97**
  (perde no bruto). Mesclado com a REV, nos dias que a REV fica muda o Renko opera 400–640×/ano e
  perde $5k–$23k. Scripts: `backtest/renko.py`, `run_renko_30d.py`, `run_renko_fair.py`. **Fechado.**
- **Modelo de drawdown = a maior alavanca estrutural achada** (`run_direcaoB_scan.py`, NQ NT8):
  DD trailing intradiário (Apex) 55% → **DD estático 60% com ZERO estouros**. O trailing é o que
  fabrica o risco de explodir. Firmas com DD estático + bot: Tradeify, MyFundedFutures (Expert),
  TPT. **Confirmar termos (automação + DD estático + preço conta ~25K + regra de consistência).**
- **Conta Apex maior NÃO resolve:** 50K/14MNQ ≈ 59% (OOS frágil), 100K+ ≈ 0% (alvo grande demais
  pro prazo de 30d). O relógio de 30 dias corridos é a trava.
- **2º sinal — fade do range overnight (Globex) durante o RTH:** sozinho 52% (empata a REV, mesma
  família). Mesclado REV+ON sob DD estático: **75%, OOS 82%/69%** — 1ª coisa do projeto acima de
  ~55% com OOS não-miragem (mas o ganho vem do DD estático, não do sinal). Nunca forward-testado.
- **Databento configurado** (conta do Marcelo, US$ 7,60 de US$ 125 de crédito grátis): dado real
  OHLCV-1m de MES/MNQ/M2K/MYM, mesmo período do `NQ_dados/`. `backtest/carrega_databento.py`
  monta front-month contínuo → `dados_databento/{...}_1min.txt`. CSV bruto no `.gitignore`.
- **A reversão em outros instrumentos** (`run_instrumento_scan.py`, ~108 configs de gestão por
  instrumento, tick REAL por instrumento — crítico pro slippage):

  | Instrumento | PF máx | Taxa | Leitura |
  |---|---|---|---|
  | MES (Micro S&P) | 0,80 | 8% | ❌ sem edge — o S&P atravessa os níveis do dia anterior |
  | M2K (Micro Russell) | 0,85 | 5% | ❌ sem edge — small caps rompem o nível (momentum) |
  | **MYM (Micro Dow)** | **1,44** (fill 1 tick) / 1,18 (2 ticks) | 62% / 43% | 🟡 único com edge, frágil a slippage |

  MYM: mesmo edge do NQ com fill bom (PF 1,44 ≈ NQ 1,41), WR 76% (> NQ 68%), quase não estoura
  (o Dow não dá spike contra) — mas depende de fill de ~1 pt Dow. Só forward test ao vivo resolve.
  ⚠️ Bug meu: 1º run com tick 0,25 pra todos deu MYM 72% (falso); MYM tick real = 1,0 pt Dow.

- **Rompimento (breakout) nos 4 instrumentos + como complemento da reversão** (`run_break_instr.py`,
  pergunta do Marcelo): edge FRACO só no Nasdaq (PF ~1,1 = 1/3 da força da reversão), morto no
  resto (MES/M2K PF <0,9; MYM PF 1,00 — o Dow reverte, não rompe). **Juntar fade + break PIORA**
  (NQ 52%/PF1,13 vs FADE sozinho 59%/PF1,43 — dilui o edge forte). **ORB morto em TODOS os 5
  instrumentos.** M2K mata a hipótese "se não faz fade, faz break" — no Russell nem um nem outro.
- **Veredito da direção B:** trocar de instrumento OU de tipo de estratégia é quase um beco. A
  alavanca real é o **FORMATO** — firma de DD estático — que se aplica ao NQ atual e ao MYM.
  Renko, rompimento, ORB: fechados.

## 🎯 29/08 — Forward test BETrigger25+MaxDist20 (5 dias) + análise ganho/perda — Marcelo não ficou satisfeito

## 🎯 29/08 — Forward test BETrigger25+MaxDist20 (5 dias) + análise ganho/perda — Marcelo não ficou satisfeito

**Forward test (Market Replay):** dias 05, 08, 09, 10, 11/06 registrados em
`forward-test-replay-25k/2026-06-betrigger25-maxdist20/` (bot: `src/BotAprovacao_BETrigger25.cs`,
BE trig 2,5pt + MaxDistPontos 20). 05/06 e 10/06 sem entradas. 08/06: -$9,5 (stop cheio -$118,5
apagou 2 ganhos). 09/06: +$80,0 (3G/0L). 11/06: -$76,0 (stop cheio -$105 no último trade comeu o
saldo do dia). **Acumulado 9 dias (01-11/06): +$38,0, 40 trades (~$0,95/trade).**

**Análise de qualidade do trade** (`backtest/analise_qualidade_trades_rev.py`, motor oficial de 13
meses): testado SL menor (10/8/6pt) pra atacar o tamanho dos stops cheios (-$105/-$118, que são
~o teto teórico do SL 12,5pt×5 contratos). Resultado: **diminuir o SL melhora o ratio ganho/perda
(0,67→1,31) mas destrói o win rate (68%→44%) e o PnL total (Net/mês $1.796→$128)**. Nenhuma
redução de SL testada supera o SL 12,5 atual — o loss grande não é bug, é o desenho do risco por
trade. `bt()` em `run_estrategias_comparativo.py` ganhou 1 chave nova (`'trades'`, lista crua de
PnL) pra viabilizar essa análise, mudança aditiva.

**🔴 Marcelo decidiu parar o forward test por hoje, insatisfeito:** "já sabemos que não terá
aprovação de conta" e "não estou feliz com o que temos". O backtest de 13 meses (1166+ trades)
segue mostrando edge real (WR 68%, ~$1.800/mês) que não bate com a sensação dos últimos dias de
forward test (amostra de 9 dias/40 trades é pequena) — **essa reconciliação, e a decisão
estratégica em aberto desde 23/08 (aceitar ~50% e escalar vs. repensar do zero), ficam pendentes
pra próxima sessão.** Nenhuma mudança em `.cs` ou produção hoje.

**Trabalho paralelo (projeto separado, mesmos dados NQ):** implementado e rodado
`backtest/backtest_rsi_reversion.py` (estratégia RSI Deep Mean Reversion, não relacionada ao
BotAprovacao) — melhor config achada é lucrativa mas com PnL/mês e DD piores que o bot atual, não
é upgrade óbvio. Ver `historico/2026-08-29.md` pro detalhe completo.

## 🎯 23/08 — Forward test de julho registrado (02 a 20/07) + 4 tentativas de IA testadas e REJEITADAS

**Forward test (Market Replay):** dias 01-20/07 registrados em
`forward-test-replay-25k/2026-07-saidaparcial/`. Acumulado até 20/07: **-$522,5** (mês começou
mal: -$698,5 até 13/07, depois 3 dias positivos seguidos 15-16-20/07 recuperaram parte). Achado
aberto e **NÃO investigado ainda**: dia 13/07 teve 2 trades (`NIV_L5`, `NIV_L7`) com stop cheio
tendo favor máximo <1pt — registrado como item #17 em `docs/melhorias-sugeridas.md`.

**⚠️ BUG ENCONTRADO, NÃO CORRIGIDO (item #18):** `pdHigh`/`pdLow` (nível do dia anterior, usado
todo dia que não é segunda) zeram toda vez que a estratégia reinicia no gráfico (comum ao mexer
no Market Replay) — sem persistência nem recálculo do histórico. Enquanto fica zerado, **o bot
não consegue dar entrada nenhuma no dia inteiro, silenciosamente**. Detalhe completo no item #18.
Isso significa que dias já registrados como "sem entradas" podem, na verdade, ter sido afetados
por esse bug — não dá pra saber sem ter visto a tela na hora.

**Testamos integrar IA (Claude) no bot — 4 formas, todas rejeitadas por backtest** (item #19 em
`docs/melhorias-sugeridas.md`, scripts em `backtest/ia_*.py`): filtro de entrada (-19,2pp),
seletor diário de estratégia com contexto simples (neutro) e rico (-45,7pp — caiu na armadilha de
"achado de curto prazo não é regra"), e gestão de risco por trade (-4,5pp). **Nenhum bateu os 50%
do baseline.** Nada disso tocou o NinjaScript nem produção — tudo em backtest Python.

**Investigação do teto de 50% (item #20):** tentativa de bootstrap estatístico esbarrou em parede
técnica (não dá pra embaralhar barras de preço reais preservando fidelidade de drawdown — script
`backtest/investiga_teto_50.py` marcado como abandonado, resultado não confiável). Conclusão
tirada por CONVERGÊNCIA: ~15 ângulos já testados com o motor oficial (SL, saída parcial, BE-lock,
filtros de entrada, estratégias alternativas, os 4 testes de IA) convergem pro mesmo teto de
~50% — evidência de que é estrutural (instrumento/timeframe/formato de avaliação), não falta de
parâmetro certo.

**🧭 DECISÃO ESTRATÉGICA EM ABERTO, pendente pra próxima sessão:** (1) aceitar ~50% e escalar
operação (rodar várias avaliações em paralelo), ou (2) repensar estratégia/instrumento do zero
(projeto novo, semanas de trabalho). Ver item #20 em `docs/melhorias-sugeridas.md`. Nenhuma ação
de código pendente até essa decisão.

## Última atualização: 2026-08-20 (tarde/noite — sessão de pesquisa: taxa de aprovação REAL medida em 50%, nenhuma estratégia nova bate a reversão, recomendação final dada)

## 🎯 20/08 (noite) — TAXA DE APROVAÇÃO REAL: 50%. Nenhuma alternativa testada supera. Recomendação: BOT 2 com saída parcial DESLIGADA.

**Resumo executivo** (detalhe completo em `docs/taxa-aprovacao-30dias-20-08.md`,
`docs/comparativo-estrategias-20-08.md`, `docs/melhorias-sugeridas.md` itens 14-16):

1. **Testamos 3 jeitos de medir "taxa de aprovação"** — ciclo infinito sem limite de
   tempo (70%, otimista demais), mês calendário puro (15%, pessimista demais
   porque desperdiça dias após estouro cedo), e **janela de 30 dias rolante com
   retry imediato (a correta): 50%**. Esse é o número real pro negócio: de cada 2
   avaliações $25K compradas, 1 aprova.
2. **Testamos 4 famílias de estratégia** (reversão atual, ORB, EMA+VWAP+RSI,
   "ICT-lite" com FVG) sozinhas e mescladas, no mesmo teste rigoroso de 30 dias.
   **Nenhuma bate a reversão sozinha** (ORB 1%, EMAV 19%, ICT 10%, melhor mescla
   REV+EMAV 29% — todas abaixo dos 50% da reversão pura). Mesclar com a reversão
   sempre piora ela (`MaxTradesDia` compartilhado "engole" o espaço da reversão).
3. **BOT 1 vs BOT 2, no teste de 30 dias:** BE-lock 0,75 sozinho deu **exatamente
   a mesma taxa (50%, 24 tentativas, 12 aprovações — número idêntico ao bot 1)**
   nesse backtest de barra de 1 ano — não contradiz o Δ +$122,5 real confirmado em
   Replay (é real, só pequeno demais pra virar tentativas inteiras de 30 dias
   nesse dataset). **A saída parcial piorou de novo** (50%→40%) — mais uma
   confirmação de que ela não presta (item #15).
4. **Testamos também, no mesmo dia:** abaixar o alvo da saída parcial (piorou
   quanto mais baixo, item #15), corte de perda antecipado (piorou, corta
   futuros vencedores, item #16), filtro de entrada por `dist_nivel`/sexta-feira
   como corte (estoura prazo de 30 dias) e como sizing seletivo (dist piora
   muito, sexta neutro-modesto).

### 🎯 RECOMENDAÇÃO FINAL: seguir o Market Replay com BOT 2 (`BotAprovacao_SaidaParcial.cs`
ou as cópias `_REPLAY`), mas com **`UsarSaidaParcial=false`** (só o BE-lock 0,75
ligado). É a única config que bate ou empata o baseline em TODOS os testes de hoje,
sem o componente (saída parcial) que consistentemente piora. Não precisa recompilar
— é só mudar o parâmetro no gráfico do NT8.

**Estado real:** taxa de aprovação de 50% parece ser o teto estrutural da
estratégia de reversão em nível único, testado exaustivamente hoje (gestão de
saída, sizing, filtro de entrada, e 3 famílias de estratégia alternativa — nada
melhora). Próxima conversa: decidir se 50% é um número com que dá pra tocar o
negócio (quantas avaliações rodar em paralelo, custo de cada estouro) ou se vale
buscar uma estratégia completamente nova do zero (não mais variação da atual).

---

## 🔴 20/08 (tarde) — Junho fechado (quase): melhoria confirmada, mas insuficiente pra aprovar. Marcelo NÃO vai fazer julho — próxima sessão é debate estratégico.

**Baseline certo pro bloco 19-30/06 era o `2026-06-1min/placar-mes.md`** (mesmo timeframe/numeração
dos dias 01-18) — não precisou rodar nada de novo no NT8, só comparar arquivos que já existiam.
Achado ao comparar: dias 19, 22, 23, 24, 25, 26, 30/06 batem **100% idênticos** entre baseline e
versão nova (BE-lock 0,75 não mexeu em nada, mecanismo de parcial nunca disparou). **29/06 ficou
incompleto** — faltam 2 trades da versão nova (baseline tem 7 trades naquele dia, só temos prints
de 5) — pendente pro Marcelo mandar o resto.

**Resultado confirmado até 28/06:** baseline +$58,5 → nova versão +$181,0 → **Δ +$122,5**, e essa
melhoria inteira veio do bloco 01-18/06 (19-28/06 teve Δ zero cravado). Falta só 29-30/06 pra
fechar o mês.

**Decisão do Marcelo: não vai testar julho.** Quer debater a estratégia de base em vez de seguir
empilhando meses — mesmo com a melhoria real (+83% relativo no período confirmado), o mês inteiro
projetado fica em torno de +$290 de $1.500 (≈19-20% da meta), longe de aprovar. Bate com o
diagnóstico estrutural de 18/08 ("problema é o formato do payoff, não parâmetro").
**Próxima sessão: debate aberto sobre pra onde levar a estratégia** (filtro de entrada, saída, ou
repensar a tese do zero) — ver a resposta completa dada ao Marcelo em 20/08 pra retomar o fio.

## 🔴 18/08 — Sessão longa: auditoria de código, teste real de trailing em Replay, diagnóstico do "gargalo" de aprovação, e implementação da saída parcial pra Market Replay

Resumo curto (detalhe completo em `historico/2026-08-18.md`):
- Achado a causa do teto de ganho ao vivo (~+2,50 a +7,45pt): motor de saída tick-a-tick (Replay/real) é bem mais apertado que o motor de barra do backtest.
- Testado trailing 5,0 em Replay real → **piorou**. BE lock testado controlado → quase não importa.
- Filtro de regime por ATR (Q4): melhora qualidade por trade mas **derruba aprovação de 47%→19,2%** → rejeitado.
- Investigação do gargalo: top 10% dos trades = 161% do PnL; os outros 90% perdem dinheiro no agregado. O que separa janela aprovada de não-aprovada não é "sorte de pegar trade grande" (isso é estável) — é quanto os 90% comuns sangram naquela janela específica.
- Estado temporal do edge: nenhuma persistência real encontrada (permutação p=0,213) — sequência de trades é ruído, não sinal.
- Auditoria do modelo de aprovação Apex: `.cs` não faz tracking de DD (só o Python), modelo já sempre foi EOD. Sizing oficial confirmado (até 4 NQ/40 MNQ): **5 MNQ segue sendo o ótimo**, tudo acima piora aprovação E dispara risco de estouro junto.
- **Veredito do dia: problema estrutural do formato de payoff (cauda longa), não parâmetro.**
- **Última descoberta do dia:** distribuindo os 5 MNQ (não aumentando contratos) — saída parcial de 4 contratos em +20pt, 1 contrato continua com a gestão normal — melhorou aprovação e eliminou estouro em backtest, robusto em sensibilidade (10-25pt) e nos 5 blocos cronológicos. **Ainda não validado em Replay real** (mesma ressalva de sempre: backtest de barra tende a superestimar mecanismo sensível a timing de saída — já provado hoje mesmo com o trailing=5,0).
- **Preparação pro teste real:** backup do baseline (`src/BotAprovacao_BASELINE_BACKUP.cs`, idêntico byte a byte) + versão nova isolada (`src/BotAprovacao_SaidaParcial.cs`, classe separada, só adiciona a lógica de saída parcial, resto 100% igual — verificado por diff). `BotAprovacao.cs` de produção **nunca foi tocado**. Tudo commitado no git (`feat/estrategia-noturna`, commit `8ad859c`).
- Config de produção segue **inalterada**: SL 12,5 / TP 60 / BE 3,75→2,5 / trailing 1,75 / 5 MNQ.

---

## Última atualização anterior: 2026-08-14 (SL 15pt testado ao vivo em 01-12/06 — PIOR que SL 12,5, teste interrompido)

## 🔴 14/08 — SL 15pt testado manualmente (01-12/06) — RESULTADO PIOR, teste interrompido pelo Marcelo

Marcelo rodou o replay de junho de novo, agora com SL 15pt (a melhoria que o backtest de 13/08
tinha "validado 2x"), registrando os trades manualmente dia a dia. **Parou no dia 12/06** (mesmo
ponto de corte usado pra comparar com o teste 1min de 13/08) porque o resultado já estava pior e
não queria perder mais tempo.

**Comparação direta, mesmos 10 pregões (01/06→12/06), mesma engine/config exceto o SL:**

| Dia | Acumulado SL 12,5 (13/08) | Acumulado SL 15 (manual, 14/08) |
|---|---|---|
| 01/06 | +$101,5 | +$270,5 |
| 02/06 | +$266,0 | +$373,0 |
| 03/06 | +$509,0 | +$616,0 |
| 04/06 | +$377,5 | +$407,0 |
| 05/06 | +$377,5 | +$407,0 |
| 08/06 | +$367,5 | +$374,0 |
| 09/06 | +$458,5 | +$465,0 |
| 10/06 | +$458,5 | +$465,0 |
| 11/06 | +$377,0 | +$287,5 |
| 12/06 | **+$243,5** | **+$96,0** |

- Até o dia 10/06 o SL 15 estava até um pouco **à frente** (+$465 vs +$458,5) — consistente com a
  ideia do backtest de que o stop mais largo evita saídas prematuras.
- **Nos dias 11/06 e 12/06 o SL 15 devolveu tudo**: -$177,5 e -$191,5 (dois dias seguidos de stop
  largo batendo cheio), contra -$81,5 e -$133,5 do SL 12,5 nos mesmos dias. Só nesses 2 dias a
  diferença foi de -$154 — mais que o suficiente pra virar a comparação do mês inteiro.
- **Contradiz a expectativa do backtest** (+32% sob slippage 2 ticks, ou seja ~$243,5 → ~$320+).
  Na prática, na mesma janela, deu **60% pior** (+$96,0 vs +$243,5).

**Conclusão do Marcelo: "isso também não deu certo" — registrado, sem aplicar SL 15pt em
produção.** Terceiro veredito seguido (depois do timeframe 1min/5min e das travas de gestão do
dia) que o backtest sugeriu como melhoria e o teste real não confirmou — ou pelo menos não nessa
amostra pequena (10 dias, stop batendo forte 2x seguidas pode ser variância, não é
necessariamente prova de que o SL 15 é pior no longo prazo — mas também não é a confirmação que
o Marcelo esperava, e ele decidiu não insistir).

**Decisão: não aplicar SL 15pt em produção. Config de produção segue SL 12,5, inalterada.**
Precisamos repensar a estratégia de base — ver `docs/melhorias-sugeridas.md` (#13 atualizado) e
retomar a discussão de fundo sobre se "reversão em nível único" tem edge suficiente depois do
atrito real (mesma pergunta já levantada em 12/08 e 13/08).

## 🔴 13/08 — Junho refeito no 1min: +$168,0. O timeframe não era o problema.
- **Mês 06/2026 no 1min FECHADO**: +$168,0 de $1.500 (11,2%), 73 trades (49G/24L, WR 67,1%),
  DD máx $546,5/$1.000 (54,6%), 16 dias operados. Detalhe: `forward-test-replay-25k/2026-06-1min/`.
- **Empatou com o 5min** (+$170,5) apesar de 3x mais trades e menos dias zerados (5 vs 12) —
  o diagnóstico de 12/08 ("era só o timeframe") **não se confirmou**.
- **Assimetria é o problema estrutural**: ganho médio $40 vs perda média $75. Precisa 65,1% de WR
  só pra empatar; tem 67,1%. 13 stops cheios (18% dos trades) consumiram 84% do lucro bruto.
- **Testadas e REJEITADAS** (`backtest/run_gestao_dia.py`, 13 meses): max trades/dia (−28% a −64%),
  cooldown entre entradas (−23% a −57%), parar após stop cheio (−59%). Eram achados do mês real
  que não sobreviveram ao dado longo (overfitting: 73 trades vs 1.440).
- **✅ SL 15pt VALIDADO 2x** (18/06 e 13/08) e **nunca aplicado** — junho inteiro rodou com SL 12,5.
  +14% sem slippage, **+32% com 2 ticks**, WR 69→74%. Ver `docs/gestao-dia-veredito.md`.
- Nada alterado em `src/BotAprovacao.cs`.

## 🔴 12/08 — Mês 06 fechou INCOMPLETO + achado crítico: timeframe errado no forward test
- **Mês 06/2026 (Market Replay) FECHADO**: +$170,5 de $1.500 (11,4% da meta), DD máx $298,5/$1.000
  (29,9%, nunca perto de estourar), 10 de 22 pregões com trade (12 zerados), 25 trades, WR 76%.
  Detalhe completo em `forward-test-replay-25k/2026-06/placar-mes.md`.
- Marcelo achou o resultado insatisfatório, pediu revisão da estratégia + estratégia nova (ORB).
  Implementado `src/NomadeBot_ORB_Manha.cs` (ORB 15min) já validado por backtest próprio
  (`backtest/run_orb_15min.py`) — PF 1,90 mas edge modesta (+$2.766/ano), NÃO resolve o problema
  principal sozinha.
- **🔴🔴 ACHADO CRÍTICO ao revisar tudo:** o forward test de junho rodou num gráfico de **5
  MINUTOS** — mas o backtest original que validou 100%/PF1.60/$36.978 foi feito em **1 MINUTO**
  (isso já estava documentado abaixo, seção "Como usar o bot", passo 4: "MNQ 1min" — mas ninguém
  conferiu contra o gráfico real do forward test até hoje).
- Mesma regra, só mudando o TF: **1min = 82% de aprovação em janelas de 30 dias, 0 estouros.
  5min = 54% de aprovação, 5 estouros.** OOS: 1min robusto (82%/74%, zero bust); 5min degrada
  (70%→38%, 5 bust) no semestre recente. Causa: barra de 5min percorre mais antes de fechar →
  `MaxDistPontos=15pt` (calibrado pra 1min) rejeita reversões válidas — explica boa parte dos
  12 dias zerados de junho. Comparação direta mesmos 11 dias: 1min=$1.240 | 5min ao vivo=$206.
  Com slippage 2 ticks: 1min=44% aprov/4 busts; 5min=26%/21 busts.
- Funil de 10 estratégias novas testado (`backtest/run_funil_estrategias.py`, pesquisa web +
  backtest próprio) pela métrica de aprovação Apex — **todas piores que a atual em 1min**: VWAP
  reversão (28%, PF 0,93, 102 busts), inverter a estratégia (9%, 181 busts), ORB15 (6%), ORB30
  (0%), Initial Balance (0%). Claims de blog/YouTube sobre ORB/mean-reversion não se sustentaram.
- Doc completo: `docs/revisao-estrategias-12-08.md`.
- **Próximo passo (combinado): Marcelo roda o mês 06 inteiro de novo no gráfico de 1min** pra
  confirmar o achado na prática. Se confirmar → 1min vira padrão definitivo, ORB fica em standby.
  Se o resultado negativo persistir mesmo no 1min → revisar tudo de novo, considerando que o
  problema pode ser a própria lógica de "reversão em nível único", não só o timeframe.

## Última atualização anterior: 2026-08-11 (forward test 25K em andamento — 9 dias úteis rodados, WR 86,7%)

## 🆕 11/08 — Forward test de aprovação (contas 25K) em andamento no Market Replay
- Dado do Market Replay (NT8) **completo: 01/06 a 10/08/2026** (fechava a janela que faltava desde
  o `historico/2026-08-10.md`, limite de 90 dias corridos do Market Replay gratuito).
- Objetivo: rodar o `BotAprovacao` de produção nesse dado e contar quantas contas **25K**
  seriam **aprovadas vs. estouradas (bust)** — forward test real no NT8, não backtest Python.
  Config: TP60/SL12,5/BE3,75-2,5/trail1,75/tol20t/maxDist15pt/maxTrades12/stopDiário$750,
  `OperarNoite=false`, DD real $1.000 EOD.
- Registro estruturado em `forward-test-replay-25k/2026-06/` (`placar-mes.md` = acumulado +
  histórico completo de trades; `dia-XX-DD-MM.md` = detalhe por dia).
- **Progresso até 09/06/2026 (5 dias úteis operados de 7 mínimos):** 15 trades, **13 gain / 2 loss
  (WR 86,7%)**, PnL **+$206 de $1.500 (13,7% da meta)**, pico $327, **drawdown atual $121** (12,1%
  do limite $1.000). As 2 perdas foram stop cheio (nunca ativaram breakeven), -$113 e -$124,5.
- Detalhe completo da sessão em `historico/2026-08-11.md`.

## Última atualização anterior: 2026-08-10 (3 estratégias novas p/ comparar no Strategy Analyzer — só 1 tem edge real)

## 🆕 10/08 — 3 estratégias diurnas novas (IB, VWAP, Momentum ATR) + backtest Python no dado real
- Pedido: 3 `.cs` separados pra comparar no Strategy Analyzer (MNQ 5min, RTH ET — **não são pra noturna
  19h-21h BRT**, isso ficou explícito com o usuário antes de codar).
  `src/NomadeBot_InitialBalance.cs`, `src/NomadeBot_VWAPReversao.cs`, `src/NomadeBot_MomentumBreakout.cs`.
  Não compilados no NT8 ainda (sem Windows aqui) — só revisão manual de sintaxe.
- **Antes de mandar pro NT8, rodei as 3 em Python no NQ real** (`backtest/run_comparativo_3estrategias.py`,
  1 ano jun/2025-jun/2026, 1min→5min agregado) — lição do 23/06 aplicada: testado **com E sem slippage**
  (2 ticks + comissão $1,20 RT) desde o início, não só depois.
- **Resultado — só a Estratégia 1 (Initial Balance) tem edge real:**
  - **IB:** 173 trades/ano, WR 57%, PF 1,18 (realista), net +$2.398/ano (1 MNQ). OOS fraco na 1ª metade
    (PF 1,04 ~empate) mas segura na 2ª (PF 1,31). Meses negativos existem (set, nov, jan, mar) — edge
    real mas não é "toda semana ganha".
  - **VWAP Reversão:** PF 0,26 — **quebrada**. Long E short perdem igual (~20% WR nos dois lados) — não é
    viés direcional de ano em alta, é sinal fraco mesmo (toque de banda + confirmação de 1 candle é ruído
    demais em 5min). Não recomendo compilar no NT8 sem redesenhar o gatilho.
  - **Momentum/ATR:** limiar padrão do `.cs` (12pt) quase não dispara (4 trades/ano) — ATR real do MNQ
    5min no período: mediana 17,6pt, p25 11,6pt (limiar tá alto demais pro regime do ano). Recalibrado
    pro real (~17,6pt): só 21-25 trades/ano, PF ~1,3 — **amostra pequena demais pra confiar**.
- Próximo passo: só compilar/validar a **IB** no NT8 Strategy Analyzer de verdade. VWAP e Momentum como
  estão não valem o tempo de compilar — precisam de redesenho antes.
- **Comparei a IB (menos pior) contra a estratégia ATUAL de produção**, mesmo dado/custo
  (`backtest/run_comparativo_atual_vs_ib.py`, espelha `EntradaNiveis()`+`GerenciaPosicao()` do `.cs`
  linha a linha). **ATUAL ganha em tudo:** WR 68,7% vs 57,2%, PF 1,46 vs 1,18, Net $4.415 vs $2.398,
  MaxDD -$330 vs -$1.926 (1 MNQ). OOS: ATUAL lucrativa nas 2 metades do ano; IB empatou na 1ª (PF 1,04).
  **Conclusão: nenhuma das 3 novas bate a atual — não trocar nada em produção.**
- **Baixando dado real pro Market Replay** (NT8, manual): limite é 90 dias corridos, 1 dia por vez.
  `MNQ JUN26` até 11/06/2026, `MNQ SEP26` de 12/06/2026 em diante (contrato expira ~19/06). Baixado até
  agora: 12/05→18/06/2026. Falta 19/06→09/08/2026. Detalhe completo em `historico/2026-08-10.md`.

## Última atualização anterior: 2026-06-23 (noturna DESLIGADA + max12 + DD real $1000 confirmado)

## 🔴 23/06 — SLIPPAGE REALISTA muda o jogo + foco só na DIURNA
- **Backtests rodavam com slippage ZERO.** Sob 2 ticks (real MNQ): DIURNA robusta, **NOTURNA desaba**
  (40% a 2t, prejuízo a 3t — wins curtos não absorvem atrito). → **`OperarNoite=false`** (noturna desligada,
  código dormente). `backtest/run_slippage_test.py`.
- **DD REAL confirmado = $1.000** (conta 25K EOD, dashboard Apex), NÃO $1.500. Todos backtests atualizados.
- **`MaxTradesDia=12`** aplicado: sobe aprovação 57%→70% no DD real (corta overtrading). Validado OOS.
- **Número real que vai pro ar** ($25K DD1000, slippage 2t, max12, só diurna): **~70% aprovação,
  14 aprov/6 busts/ano, PnL $21.562, PF 1.41, OOS 62%|75%.**
- **News filter (FOMC) testado e REJEITADO**: bot lucra nos dias de FOMC, filtro só reduz PnL.
- **Conta $50K (futuro)**: mesmas 5 MNQ → 100% sem busts (gordura DD $2.000). Avaliar na próxima.
- ⚠️ **Consistência 50% Apex 4.0**: ~40% das aprovações concentram >50% do lucro em 1 dia (risco de saque).
- Pesquisa pesada + plano: `docs/pesquisa-bots-nt8-apex.md`, `docs/melhorias-sugeridas.md`.
- ⚠️ **PRECISA RECOMPILAR o `.cs` na VM** — noturna off + max12 ainda NÃO estão rodando ao vivo.
- 🚨 Apex proíbe automação OFICIALMENTE (eval tolera, PA confisca). Alternativas: TopstepX, Tradeify, MFF, TPT.
- Commits `deb1dab`→`c3735eb` (branch `feat/estrategia-noturna`).

## Última atualização anterior: 2026-06-21 (revisão pré-22/06: deploy = Sim101 dia todo via Andersson, NÃO conta real; log SL15 do 18/06 registrado)

## 🐛 FIX CRÍTICO 18/06 — duplo-fill / posição fantasma (forward test Sim101)
- **Sintoma:** short S32 tomou stop, mas o bot "virou LONG" sozinho. Era posição FANTASMA.
- **Causa-raiz:** stop em DOIS lugares no MESMO preço → saída a mercado (`OnMarketData`) + stop do
  servidor (`SetStopLoss`) encheram no mesmo tick → comprou 10 estando vendido 5 → flip pra long 5.
  A neutralização `SetStopLoss(5000)` PERDE a corrida (servidor já disparou). O long preso não fechava
  porque `sinalAtivo` ainda era "NIV_S32" (short) → `ExitLong` não casava.
- **Correção:** novo param **`BufferStopServidorPontos` (default 5pt)** — stop do servidor fica sempre
  5pt MAIS LARGO que o gerenciado (entradas diurna+noturna E move de breakeven). A saída a mercado
  dispara ANTES do servidor → impossível duplo-fill. Trade-off: backstop de desconexão ~5pt mais largo.
- **Backtest INTACTO:** `OnMarketData` não roda no histórico → 94%/OOS 100% inalterados.
- **Bônus:** fix do log `~saida` (mostrava close da vela, fazia win parecer loss; agora usa stop/alvoPrice).
- ⚠️ Recompilar no NT (F5) + REMOVER e RE-ADICIONAR a estratégia (assinatura mudou: param novo).
- Dia Sim101 fechou −$95,50 (a bagunça do fantasma comeu os 5 winzinhos +$144 vs stop −$111).

## 📊 VARREDURA TRAILING x BREAKEVEN (18/06, `backtest/run_trailing_sweep.py`)
- Pergunta: afrouxar o trailing pra trades maiores? **RESPOSTA: NÃO.** Baseline (BE3,75/tr1,75) venceu tudo:
  100% aprov, 14d, WR 69%, PF 1,66, **$38,9k** (melhor PnL). OOS 100%/100% nas duas metades.
- Afrouxar sobe o ganho médio ($99→$203) mas DESTRÓI o WR (69%→45%) e a taxa de aprovação → menos PnL.
  Trailing apertado = feature (catar winzinhos consistentes), não bug. MANTÉM como está.


## 🌙 NOTURNA — estado FINAL (branch `feat/estrategia-noturna`)
- **Gatilho na LINHA (extremo do canal alta/baixa), NÃO nas Fib centrais:** vela A toca/passa a LINHA
  (`zVenda = noiteHigh - LinhaToleranciaPontos`; `zCompra = noiteLow + LinhaToleranciaPontos`) → arma no
  CORPO de A → vela B passa o corpo → entra TICK A TICK. Param `LinhaToleranciaPontos` default **5pt**.
  Backtest `run_noturna_linha.py`: **+5pt → 100% (26/26), OOS 100/100, ~$48k/ano** (10pt $52k, 15pt $55k).
- **Entrada TICK A TICK** (OnMarketData `TentaEntradaNoturnaTick`): entra no instante que o preço cruza o
  corpo de A, sem esperar a vela fechar. Rede backtest histórico (State!=Realtime) no fechamento.
- **FUSO-PROOF:** detecta o fuso do gráfico (reflection) → diurna→ET, noturna→BR em qualquer fuso. Fallback ET.
- **Gráfico DEVE ser 1min** (diurna degrada em 5min). Desenho: LINHA alta/baixa + banda de tolerância dourada.
- **`ToqueFresco`** = toggle default OFF (foi um fix de interpretação errada; a linha-extremo já restringe).
- 🔑 LIÇÃO: toda restrição de seletividade na reversão REDUZ PnL ou não conserta o downtrend. Rejeitados:
  corpo+pavio, filtro anti-tendência, zona apertada, toque fresco, níveis à noite, fecha-close, 5min.
  Em downtrend a reversão SEMPRE sangra (a linha rompe) — proteção = STOP DIÁRIO $750, não filtro.
- Replay 15/06 (downtrend) com gatilho na linha: net −$190 (L30+18,5 L31−124,5 L32−137 L33+53). Capado.
- Commits: `2ca5fe7`(corpo+fuso) `486d4e4`(1min+tick) `8e4f0f3`(toque fresco) `6ea8471`(LINHA/extremo).

## 🚀 DEPLOY (atualizado 21/06)
- Andersson testou **quinta 18/06 e sexta 19/06** (Marcelo enviou ZIP do bot).
- **Segunda 22/06: 1º dia rodando o dia TODO (diurna + noturna) — AINDA Sim101, NÃO conta real.**
- Fluxo: Marcelo no serviço de dia → **Andersson manda as operações**, Marcelo organiza à noite no
  `historico/trades-ao-vivo.md` (seção 2026-06-22 já montada).
- Conta real fica pra depois de validar uns dias de Sim101 com o log vivo.
- ⚠️ Antes do real (quando for): StartBehavior → **AdoptAccountPosition** (já no código).



## 🌙 ESTRATÉGIA NOTURNA (16/06 — branch `feat/estrategia-noturna`, NÃO mergeada)
Reversão "ping-pong" nas bordas do canal Fibonacci **19h-21h BR**, integrada ao `BotAprovacao.cs`
pra rodar **junto da diurna na mesma conta**. Vende zona 76,4-100% (topo), compra 0-23,6% (fundo);
gatilho = rompimento do pavio da vela de rejeição; filtro canal ≥40pt; gestão idêntica à diurna.
- **Backtest combinado (sem domingo, honesto):** 96% / 11 dias / +$47k/ano / OOS 100%/93%.
  (Com domingo dava 100%/8d/$52k, mas é ILUSÓRIO — trades de domingo vivem na abertura caótica do Globex.)
- **Toggle `OperarNoite` + grupo "7. Noturna"** no NT8. Default `PularDomingoNoite` = ON.
- **Status:** compilando e em forward test no Market Replay. A noturna é ACELERADOR (sozinha ~89%).
- **Pendência:** forward test AO VIVO (replay distorce/fura breakeven); decidir se entra no produto
  (custa ~4pp de taxa vs diurna pura 100%); variante de gatilho sem exigir rejeição (com backtest).
- Detalhes em `historico/2026-06-16-estrategia-noturna.md`. Backtest: `backtest/run_diurna_noturna.py`.

---


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
- **Gestão de saída ao vivo TICK A TICK** (16/06): `OnMarketData` faz fav→breakeven→trailing→alvo/stop a cada tick, desde o 1º tick pós-fill. SL sobe junto com o lucro DENTRO da vela (não espera a vela fechar). `GerenciaPosicao` (OnBarClose) mantido p/ backtest + rede no fechamento.
- ⚠️ `OnMarketData` só roda ao vivo/replay (`State==Realtime`) → **backtest 100% inalterado**; live diverge do backtest bar-based no tick-level (validação empírica via replay).
- Integração TraderOS (HTTP 201, dedup por externalId) — funcionando
- Repo GitHub: `Marcelo210598/Bot-aprovacao` (privado)

### Forward test (Market Replay)
- Dias **09/06 a 12/06/2026** concluídos
- Bugs encontrados e corrigidos na sessão 13/06 (4 bugs críticos)
- **Sessão 16/06** — replay do **15/06** (segunda, nível domingo à noite): achados/corrigidos Bug 5 (stop servidor rejeitado em rally → `OnMarketData` intrabar) e Bug 6 (trailing 1 barra atrasado + saídas mudas). Implementado trailing tick a tick a pedido do Marcelo. Trades 15/06: NIV_S11 +$29, NIV_S12 -$124 (faltou 1 tick p/ breakeven), NIV_S13 -$10,5 (proteção cortou de -$125). Dia de rally forte + gap de entrada pesaram.
- Comportamentos validados: stop intrabar, trailing tick a tick, filtro chase, TraderOS sync, spam de log

## 🚧 Em progresso
- Forward test — rodar **mais dias de replay** (dias calmos, sem reversão em V) p/ ver o trailing tick a tick travando lucro de verdade
- Avaliar (SÓ se necessário, por backtest) antecipar gatilho de breakeven **3,75 → 3,0/2,5** p/ proteger trades que ficam a ~3,5pt a favor (ex.: NIV_S12 -$124 do 15/06)
- Observar o **gap de entrada** (fill no abre da vela seguinte) — maior dano em dia de rally; pensar mitigação só com backtest
- Forward test — semana **02–06/06/2026** pendente (baixar dados: 30/05 a 06/06)
- Confirmar com Andersson: regra 7 dias mínimos + custo real MNQ

## ⚠️ Problemas mapeados

### Resolvidos
- OCO ID reutilizado → stop/alvo não criados → **resolvido** (sinal único por trade)
- Trailing c/ ordem no servidor desabilitava bot → **resolvido** (trailing sintético)
- Stop inicial inválido → perdas enormes → **resolvido** (ticks na entrada)
- Entradas "chase" (3 stops em 3 min no mesmo nível) → **resolvido** (filtro 15pt)
- Spam de log em dias acima do PDH → **resolvido** (guard tol*2)
- **[17/06] Trailing sumia no restart** → resolvido (`AdoptAccountPosition` + recovery em `State.Realtime`)
- **[17/06] Bot se auto-desabilitava** → resolvido (null-safety em `TradesHoje` e `RealizadoAcumulado`)
- **[17/06] SHORT fantasma pós-exit** → resolvido (neutraliza server stop 5000 ticks antes de fechar)

### Monitorar (baixa prioridade)
- Overtrading: ~14 trades/dia no backtest — decisão: manter (fiel ao backtest). Soluções mapeadas se der problema ao vivo (cooldown / max 12 trades-dia).
- Dias de mercado lateral (range extremo dia anterior): zero entradas. Comportamento esperado, já no backtest dos 100%.
- **[13/08] PnL real não bate com a matemática simples de pontos** — vários trades no forward test
  1min (dias 08, 09, 11 e 12/06) fecham com PnL real (via `[MeuTrade]`) diferente do que a diferença
  entrada→saída do texto do log sugeriria — às vezes até com sinal trocado (pontos sugerem ganho,
  PnL fecha negativo). Não é erro de transcrição isolado, é recorrente o suficiente pra investigar:
  pode ser slippage no fill real não capturado no texto resumido do trailing, comissão, ou algo a
  conferir no `BotAprovacao.cs`. Ainda não afeta a confiança nos números agregados (o PnL usado nos
  placares é sempre o real, via `[MeuTrade]`), mas vale entender a causa. Ver
  `forward-test-replay-25k/2026-06-1min/dia-12-12-06.md` pro exemplo mais recente.

## 📋 Próximos passos (roadmap)
1. **Forward test junho inteiro no 1min — CONCLUÍDO (13/08).** Todos os 21 pregões de junho
   registrados em `forward-test-replay-25k/2026-06-1min/`. **Resultado final: +$168,0 (11,2% da
   meta de $1.500), 73 trades (49G/24L, WR 67,1%), drawdown máximo $546,5/$1.000 (54,6%, não
   estourou), 16 dias operados.**
   🔴 **Veredito: o diagnóstico "era só o timeframe" NÃO se confirmou.** O 1min real fechou o mês
   quase EMPATADO com o 5min real original (+$168,0 vs +$170,5) — apesar de gerar quase 3x mais
   trades (73 vs 25) e menos dias zerados (5 vs 12), os stops cheios de -12,50pt consumiram o
   ganho extra, e o drawdown máximo quase dobrou (54,6% vs 29,9%). O backtest projetava +$1.240
   pros primeiros 11 dias — o real bateu 30% disso no dia 11 e não recuperou a diferença até o
   fim. Ver veredito completo e a tabela comparativa em
   `forward-test-replay-25k/2026-06-1min/placar-mes.md` (seção "🏁 VEREDITO FINAL DO MÊS").
   **Próximo passo é decisão do Marcelo** — não mudar nada em produção sem essa decisão.
2. ~~🎯 APLICAR SL 15pt~~ — ❌ **TESTADO AO VIVO E REJEITADO (14/08).** Marcelo rodou 01-12/06
   manualmente com SL 15pt: +$96,0 contra +$243,5 do SL 12,5 na mesma janela (60% pior),
   contrariando os +32% projetados pelo backtest sob slippage. Teste interrompido no dia 12/06.
   **Config de produção segue SL 12,5.** Ver entrada 14/08 acima e `docs/melhorias-sugeridas.md` (#13).
3. ~~Trava de lucro por horário~~ — ❌ **TESTADO E REJEITADO 13/08.** Todas as variantes (max
   trades/dia, cooldown entre entradas, parar após stop cheio) pioram de −23% a −64% no backtest de
   13 meses. O padrão visto em junho era overfitting (73 trades vs 1.440).
3. **Forward test semana 02–06/06** — baixar dados e rodar
2. **Forward test completo** — validar slippage real ao vivo no Sim101
3. **Confirmar Andersson** — regra 7 dias + custo MNQ
4. **Bot Funded 25K** — 🟡 backtest iniciado e refinado (15/06, pasta `Estrategia 25/`). Falta `.cs` + forward test.
5. **Bot Funded 50K** — variante com mais folga de DD

## 🎯 Visão de produto (3 produtos)
1. **Bot Aprovação** ← atual (BotAprovacao, 100%/15d, 5 MNQ, 25K) ✅ forward test
2. **Bot Funded 25K** — 🟡 estratégia pós-aprovação em backtest. Config v3 refinada (15/06): Intraday,
   **2→3 MNQ** (escalona após travar a gordura $26.600), alvo **$400/dia**, **breakeven 1.5/1.0**.
   Resultado: **19 saques/ano (~$19k ≈ R$104k)**, **WR 75,9% / 78,8% dias verdes / PF 1.91 / 0 violação**,
   OOS 0/0. Proteção 4 camadas (SL 12.5pt/trade + BE + stop diário $300 + DD $1.500). Pasta `Estrategia 25/`.
   Descartados: filtro horário, escalonamento 2 degraus, filtro SMA (ver README). Falta `.cs` + forward test.
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
