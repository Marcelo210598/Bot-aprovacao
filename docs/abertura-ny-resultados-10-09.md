# Abertura de NY — resultados 10/09/2026

Estratégia `src/AberturaExplosao.cs` (breakout direcional da explosão da 1ª vela das 09:30 ET).
Testes: NT8 Market Replay, MNQ JUN26, 1-min + Tick Replay, fuso ET, 6 contratos,
config base 6/6/6, `AlvoDolar` 500. Comissão/slippage = Analyzer (não codados).

## Jornada de bugs (todos corrigidos)

1. `FlushFiles` "Index out of range" → reescrito com acumulador, sem parse de string.
2. **Fuso**: VM em horário de Brasília. `EmET()` + `ResolveFusoGrafico()` (reflection) portados
   do `BotAprovacao`. NT8 detectou "Eastern Standard Time" → conversão vira no-op, ok.
3. **Timing (o grande)**: NT8 carimba barra intraday no FECHO; numa barra em formação (`OnEachTick`)
   `Time[0]` já retorna o horário de fecho → o código lia "09:30" durante o candle das 09:29 e
   **entrava antes da 1ª vela**. Fix: `etStart = EmET(Time[0]).AddMinutes(-1)`, captura na barra
   que COMEÇA >= 09:30.

## Run A — segue o rompimento (`InverterDirecao` = false), 01→17/06

Flushes (soma cash BRUTO, s/ comissão, 6 MNQ) — ⚠️ dados sujos: Marcelo reiniciou a cada dia,
janelas se sobrepõem, ~4 trades por flush:

    -453, -219, -189, -190, -23, -30, +136, +2, +193, +283, +57, -329, -862, -528

→ oscila de −$862 a +$283, **net claramente negativo**, sem padrão.

## Run B — fada a abertura (`InverterDirecao` = true), 01→17/06

    +210, +183, +19, -2, -152, -16, -197, -298, -70, +301, +787, +501

→ oscila de −$298 a +$787, **net perto de zero / levemente positivo**, mas variância enorme e
os dias grandes carregam tudo (típico de ausência de edge + sorte de regime).

## Leitura

- **Nenhuma das duas direções mostra edge** em tick replay honesto. Bate com o harness Python
  (`backtest/abertura_trigger_causal.py`): com trigger causal (sem look-ahead), seguir o
  rompimento dá −$11/trade; o "+$4-5/trade" de 09/09 era look-ahead intra-segundo.
- **Observação do Marcelo (10/09):** entra no 1º tick que mexe 0,75 pt (ruído) e sai em segundos
  com stop/trail de 6t — o trade nunca participa do movimento.

## Próximo teste (v4 — `EsperaSegundos`)

`src/AberturaExplosao.cs` build v4 (commit b01e694): param `EsperaSegundos` — aguarda N s após
09:30, usa o preço APÓS a espera como referência, só então arma o gatilho.

Rodar **UMA vez contínua** (sem parar por dia), `TradeWindowStart`=2026-06-01,
`TradeWindowEnd`=2026-06-17:
- `EsperaSegundos`=90, `GatilhoTicks`=3, `StopTicks`=12, `BeTicks`=24, `TrailTicks`=10, `AlvoDolar`=500
- 1 flush limpo. Depois `InverterDirecao`✓ e repete.

**Critério:** ambos negativos/zero com ~10-14 trades → **no-go cravado** na abertura de NY.

---

## Iteração v5-v7 (10/09 tarde) — entrada "le o caminho" + trailing em $

- **v5-v6:** trocada a lógica do `EsperaSegundos` — depois da espera, compara preço vs open;
  se afastou >= GatilhoTicks, entra NESSA direção na hora (segue o caminho). Bug de fundo achado:
  `Time[0]` no NT8 só anda de minuto em minuto -> EsperaSegundos < 60 caía sempre na 2a vela.
  Corrigido movendo a lógica de tempo pro `OnMarketData` (timestamp real do tick). v6 entra
  aos 09:30:32 com Espera=30.
- **v7 (commit ec883a6):** trailing em $ (ideia do Marcelo): `StopDolar` (stop fixo em $),
  `RespiroSegundos` (só o stop fixo vale nesse tempo), `TrailDolar` (depois de ficar verde,
  stop = pico - TrailDolar, ratchet).

### v6 — Espera 30 / Stop 12t / BE 24t / Trail 10t (6 MNQ, $ = soma_pts x 12)
| dia | 01 | 02 | 03 | 04 | 05 | 08 | 09 | 10 | 11 |
|---|---|---|---|---|---|---|---|---|---|
| $ | -68 | -8 | **+99** | +6 | -15 | -4 | -1 | -5 | -22 |
Net ≈ -18 / 9 trades. Losers pequenos, +99 do dia 3 carrega. "Trade nem respira e stopa."

### v7 — Espera 10 / StopDolar 250 / TrailDolar 100 / Respiro 20 (6 MNQ)
| dia | soma_pts | $ real (x12) | dir |
|---|---|---|---|
| 01 | -19.75 | **-237** | LONG |
| 02 | +9.75 | +117 | SHORT |
| 03 | -21.5 | **-258** | LONG |
| 04 | +5.75 | +69 | SHORT |
| 05 | -22 | **-264** | LONG |
| 08 | -22 | **-257** | SHORT |
Net ≈ **-830 / 6 dias**. WR 2/6. **TODA perda bate o StopDolar cheio (-250)** — o trade vai
direto contra e come o stop inteiro. Espera 10s + stop largo = PIOR que a v6.
LONG 0/3, SHORT 2/2 (amostra ínfima).

### ⚠️ BUG conhecido no CSV
`pnlCash` no CSV/flush subestima quando a saída preenche em partes (só a 1a execução é logada
com `quantity` parcial). O `soma_pts` está certo — multiplicar por (pointVal x Contratos) pro $ real.

### Leitura
7 versões, ~todas as configs (seguir/fadar, stop apertado/largo, trail em tick/$, espera
0/10/30s): **tudo entre breakeven e negativo.** Ler o caminho da abertura aos 5-30s **não
prevê** o próximo movimento — 4 de 6 dias o trade vai direto contra. Trailing não conserta
entrada de moeda ao ar. O harness já dizia isso no 1o dia (o "+edge" era look-ahead).

**Recomendação (Claude): no-go na abertura de NY.** Antes de cravar, 1 run limpo full-period
(01→17/06, `TradeWindow` setado, sem parar por dia) com a config menos ruim (v6 tight, Espera 30).

## ➡️ AMANHÃ (11/09) — Marcelo vai mexer no STOP e no TRAILING

Marcelo parou o dia 10/09 aqui. Não aceitou o no-go ainda — quer testar mais configs de stop/trail.
Estado: `src/AberturaExplosao.cs` build v7 (commit ec883a6), compilado na VM.

O que testar (grid, grupo "1. Abertura"):
- `EsperaSegundos`: quer testar **5** (além de 10/30). ⚠️ mais curto = mais ruído.
- `StopDolar`: **250 é largo demais** (~5 pt) — toda perda da v7 bateu o stop cheio.
  Testar 100-150. Ou voltar pro modo ticks (`StopDolar`=0) que deu perdas pequenas na v6.
- `TrailDolar`: pra "travar mais lucro" (pedido do Marcelo no dia 04) → **baixar pra 50 ou 30**
  (stop = pico - TrailDolar, mais colado).
- `RespiroSegundos`: 20 (ou testar 10-30).

⚠️ **Antes de mais tuning:** rodar **UM run limpo** — 01→17/06 contínuo, `TradeWindowStart`=
`2026-06-01` / `TradeWindowEnd`=`2026-06-17`, SEM parar por dia — pra ter ~13 trades por config
e não 6 olhados no olho. A cada dia solto o `barras processadas` pula (janelas sobrepostas) e o
`soma_pts` vira ruído.

**Se depois desse tuning ainda for breakeven/negativo → cravar no-go** e ir pro próximo caminho:
firma de DD estático (memória `project_bot_trade_nt8` #22) OU estratégia nova do zero
(decisão em aberto desde 23/08).

## Pendências técnicas do `.cs` (não bloqueiam)
- **CSV pnlCash subestimado** em saídas com preenchimento parcial (só a 1a execução logada).
  `soma_pts` OK. Corrigir: acumular todas as execuções de saída antes de fechar o trade.
- **"Index out of range"** ainda aparece no log = instâncias velhas do NT8 (builds pré-c52f936).
  Fechar+reabrir o NinjaTrader limpa. O código v7 não tem indexação em lugar nenhum.
- **Stop sintético (ExitLong/Short a mercado)** enche mal em spike violento (fill 5-6 pt além do
  nível). Realista pra ordem a mercado, mas considerar `SetStopLoss` server-side se for pra live.
- `[MeuTrade] HTTP 401` = AddOn TraderOSSync tentando sync a conta Playback101. Ignorar ou
  desabilitar o AddOn no backtest.
