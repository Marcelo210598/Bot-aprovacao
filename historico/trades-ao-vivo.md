# 📒 Histórico de Trades AO VIVO (forward test)

> Log vivo de todos os trades reais (Sim101 / conta real) pra analisar o que funciona e o que não
> na estratégia. Fonte da verdade do PnL = TraderOS / corretora. Atualizar a cada trade.
>
> **Colunas:** `fav` = melhor preço a favor atingido | `BE` = breakeven armou? | `Motivo` = como saiu
> (StopTick/TrailingTick = intrabar; StopInicial/Trailing/Alvo = fechamento de barra) | obs relevante.

## Legenda de motivos
- **TrailingTick / StopTick** = saída intrabar (tick a tick, OnMarketData) — preço ≈ stop trilhado
- **StopInicial / Trailing / Alvo** = saída no fechamento da barra (a mercado ≈ close)
- **BE=sim** = trade andou ≥3,75pt a favor e travou lucro mínimo; **BE=nao** = não chegou lá (stop cheio)

---

## 2026-06-18

### ☀️ Diurna (linha Max dia anterior = 30544,75) — ANTES do fix do fantasma
| # | Hora | Lado | Sinal | Entrada | fav | BE | Motivo | PnL | Obs |
|---|------|------|-------|---------|-----|-----|--------|-----|-----|
| 1 | 11:11 | SHORT | NIV_S25 | 30540,75 | — | — | Stop | ~−$ | rejeição na linha |
| 2 | 11:14 | SHORT | NIV_S26 | 30538,00 | — | sim | ~BE | ~+$ | travou no breakeven |
| 3 | 11:36 | SHORT | NIV_S27 | 30533,00 | — | — | Stop | ~−$ | — |
| 4 | 12:40 | SHORT | NIV_S28 | 30540,80 | 30534,00 | sim | TrailingTick | **+$41** | win |
| 5 | 12:41 | SHORT | NIV_S29 | 30539,95 | 30535,75 | sim | TrailingTick | **+$19,5** | win |
| 6 | 12:44 | SHORT | NIV_S30 | 30541,90 | 30537,50 | sim | TrailingTick | **+$34** | win |
| 7 | 12:45 | SHORT | NIV_S31 | 30535,40 | 30528,50 | sim | TrailingTick | **+$49,5** | win (correu mais) |
| 8 | 12:49 | SHORT | NIV_S32 | 30533,45 | 30532,50 | nao | StopTick | **−$111** | 🐛 gerou LONG FANTASMA (duplo-fill) |

**🐛 Bug do dia:** o S32 (stop cheio, BE não armou) disparou stop a mercado + stop do servidor no mesmo
preço → virou long fantasma. Fechado na mão. **Dia diurno fechou −$95,50** (winzinhos +$144 vs stop+bagunça).
Corrigido com `BufferStopServidorPontos=5` (commit `7ff20d4`).

### 🌙 Noturna (canal 19-21h BR) — DEPOIS do fix
| # | Hora | Lado | Sinal | Entrada | fav | BE | Motivo | PnL | Obs |
|---|------|------|-------|---------|-----|-----|--------|-----|-----|
| 9 | 19:25 | LONG | NOT_L31 | 30687,85 | 30692,25 | sim | TrailingTick | **+$30** | ✅ saída LIMPA (sem fantasma) |
| 10 | 19:26 | LONG | NOT_L32 | 30691,25 | 30693,50 | nao | StopTick | **−$130** | ✅ STOP CHEIO limpo = fix validado! |
| 11 | 19:28 | LONG | NOT_L33 | 30688,95 | 30690,75 | nao | StopInicial | **−$18,5** | fill melhor que o stop (pavio+recupera) |
| 12 | 19:34 | LONG | NOT_L34 | 30678,45 | 30680,25 | nao | StopTick | **−$128,5** | stop cheio limpo |

**Noturna parcial: +$30 / −$130 / −$18,5 / −$128,5 = −$247.**

**⚠️ Observação importante (padrão):** noite em **DOWNTREND** — canal de baixa caindo (linha de compra
30771 → 30675 → 30673), todos os LONGs de reversão tomando stop (fav minúsculo, BE nunca arma). Isso bate
com a lição já documentada: *"em downtrend a reversão SEMPRE sangra; a proteção é o STOP DIÁRIO $750, não
filtro"*. Os 4 longs seguidos contra = mercado furando a linha de baixa repetidamente. Acompanhar se o
stop diário trava antes de piorar.
