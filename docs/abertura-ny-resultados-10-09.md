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
