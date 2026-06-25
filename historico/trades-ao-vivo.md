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
| 13 | 19:42 | LONG | NOT_L35 | 30659,70 | 30664,25 | sim | TrailingTick | **+$26,5** | win pequeno (fav só +4,5pt) |
| 14 | 19:44 | LONG | NOT_L36 | 30661,45 | 30666,75 | sim | TrailingTick | **+$18,5** | win pequeno (fav só +5,3pt) |
| 15 | 19:48 | LONG | NOT_L37 | 30659,60 | 30664,75 | sim | TrailingTick | **+$28** | win pequeno (fav só +5,1pt) |

**Noturna parcial: +30 / −130 / −18,5 / −128,5 / +26,5 / +18,5 / +28 = −$174.**
**🔴 Assimetria viva: 4 wins (+$103) vs 3 stops (−$277). 1 stop apaga ~5 wins. Win rate baixo hoje (downtrend) = sangra.**
**📌 Decisão 18/06: testar SL 15pt (backtest: WR 69%→74%, PnL +14%, OOS 100%/92%). Aplicado via param no gráfico.**

**⚠️ Observação importante (padrão):** noite em **DOWNTREND** — canal de baixa caindo (linha de compra
30771 → 30675 → 30673), todos os LONGs de reversão tomando stop (fav minúsculo, BE nunca arma). Isso bate
com a lição já documentada: *"em downtrend a reversão SEMPRE sangra; a proteção é o STOP DIÁRIO $750, não
filtro"*. Os 4 longs seguidos contra = mercado furando a linha de baixa repetidamente. Acompanhar se o
stop diário trava antes de piorar.

---

### 🔁 Rodada SL15 — replay 18/06 (FRAGMENTO de log, parcial — não fechou o dia)
> Logs colados pelo Marcelo em 21/06. É **outra rodada** do mesmo dia 18/06 (provável teste do SL15),
> com sinais/preços diferentes da tabela acima. Só os trades com `<<< SAIDA` no trecho estão fechados;
> entradas sem saída ficaram fora do recorte. **Não tirar conclusão de PnL do dia daqui — é fragmento.**

**☀️ Diurna (linha Max dia anterior = 30544,75):**
| # | Hora | Lado | Sinal | Entrada | Saída | fav | BE | Motivo | PnL |
|---|------|------|-------|---------|-------|-----|-----|--------|-----|
| 1 | 11:16 | SHORT | NIV_S24 | 30537,75 | 30503,25 | 30501,50 (+36pt) | sim | Trailing | **+$345** |
| 2 | 12:46 | SHORT | NIV_S27 | 30544,25 | 30531,50 | 30529,75 (+14,5pt) | sim | Trailing | **+$127,5** |

Filtro CHASE rejeitou corretamente 10:35 (−59,5pt), 10:54 (−21,75pt), 11:29 (−20pt), 12:39 (−40,5pt).
11:35 tocou SEM rejeição (C≥linha) → não entrou. **Confirmados: +$472,5 nos 2 trailing.** Entradas
11:11/11:14/11:36/12:40/12:44/12:49 sem saída no recorte.

**🌙 Noturna (canal 19-21h BR, downtrend de novo):**
| # | Hora | Lado | Sinal | Entrada | Saída | fav | BE | Motivo | PnL |
|---|------|------|-------|---------|-------|-----|-----|--------|-----|
| 3 | 19:28 | LONG | NOT_L29 | 30691,00 | 30678,50 | +2,5pt | nao | StopInicial | **−$125** |
| 4 | 19:33 | LONG | NOT_L30 | 30686,75 | 30674,25 | +2pt | nao | StopInicial | **−$125** |
| 5 | 19:36 | LONG | NOT_L31 | 30676,75 | 30664,25 | 0pt | nao | StopInicial | **−$125** |
| 6 | 19:51 | LONG | NOT_L34 | 30665,50 | 30677,50 | +13,75pt | sim | Trailing | **+$120** |

Canal expandindo pra baixo (30675,50 → 30650,00) = mesma faca caindo de sempre. **3 stops seguidos
(−$375) antes do L34 ganhar (+$120).** Entradas L32 (19:38) e L33 (19:45) sem saída no recorte.
Confirma de novo: **proteção em downtrend = stop diário $750, não filtro de entrada.**

---

## 2026-06-22 (Sim101) — 1º dia com Andersson rodando o dia todo
> ⚠️ **Sim101, NÃO conta real ainda.** Marcelo no serviço de dia → Andersson manda as operações,
> Marcelo organiza aqui à noite. Diurna (9h30-16h ET) + Noturna (19h15-21h BR). Esperar comportamento:
> diurna filtra bem; noturna brilha em range, sangra em downtrend (capada pelo stop diário $750).

### ☀️ Diurna (linha Max dia anterior = ____)
| # | Hora | Lado | Sinal | Entrada | Saída | fav | BE | Motivo | PnL |
|---|------|------|-------|---------|-------|-----|-----|--------|-----|
| _ | _ | _ | _ | _ | _ | _ | _ | _ | _ |

### 🌙 Noturna (canal 19-21h BR)
| # | Hora | Lado | Sinal | Entrada | Saída | fav | BE | Motivo | PnL |
|---|------|------|-------|---------|-------|-----|-----|--------|-----|
| _ | _ | _ | _ | _ | _ | _ | _ | _ | _ |

**Resumo do dia:** diurna ___ | noturna ___ | total ___ | bateu stop diário? ___

---

## 2026-06-23 (Sim101) — 1º dia rodando no Windows 11 após abandono da VPS Azure
> ⚠️ **Sim101, NÃO conta real.** Bot voltou pro Windows 11 (UTM no Mac) após 2 dias tentando resolver VPS Azure.
> VPS abandonada: Rithmic detecta IP Azure e não completa feed de preços (amarelo infinito).
> Monitorar via AnyDesk do trabalho. Diurna perdida (problemas de conexão). Noturna iniciada às 19h28.

### ☀️ Diurna — perdida (problemas de conexão o dia todo)

### 🌙 Noturna (canal 19-21h BR)
| # | Hora | Lado | Sinal | Entrada | fav | BE | Motivo | PnL | Obs |
|---|------|------|-------|---------|-----|-----|--------|-----|-----|
| 1 | 19:28 | LONG | NOT_L22 | 29715,45 | 29719,50 | sim | TrailingTick | **+$25** | canal 104pt [29700,75-29804,75] |
| 2 | 19:30 | LONG | NOT_L23 | 29715,25 | 29719,50 | sim | TrailingTick | **+$23** | saiu em +2,5pt — preço continuou forte +40pt após saída ⚠️ |
| 3 | 19:37 | LONG | NOT_L24 | 29679,20 | 29681,75 | nao | StopTick | **−$126,5** | stop 29666,50 | vela vermelha anterior (bearish forte) não era rejeição → bot pulou; L24 entrou na vela seguinte c/ pavio correto |

**Resumo do dia:** diurna — | noturna: +25 +23 −126,5 = **−$78,5** até 19:37

> ⚠️ **Observação L23 (backtest respondeu 23/06):** BE armou (fav +4,25pt), trailing travou em +2,5pt, saiu. Preço subiu +40pt depois. Backtest (sweep trailing 1.75→12pt): **1.75pt JÁ É ÓTIMO para a noturna**. Aumentar trail reduz WR e PF sistematicamente — o L23 foi outlier, não erro de parâmetro.
> 
> **Por que não entrou na vela vermelha que tocou a linha?** Vela bearish forte (corpo grande, pavio inferior pequeno) → `eh_rejeicao_baixa()` = False → sem setup armado. Verde que "passou o corpo" não tinha pend ativo. NOT_L24 entrou pela vela seguinte que tinha pavio inferior dominante correto.

---

## 2026-06-24 (Sim101) — diurna: 1 trade limpo (LONG reversão na mínima do dia anterior)
> ⚠️ **Sim101, NÃO conta real.** Andersson rodando. **Apenas 1 entrada no dia inteiro** (diurna). Saída
> via TrailingTick **sem posição fantasma** — comportamento modelo. Bot desabilitado após o trade.

### ☀️ Diurna (linha Mín dia anterior = 29577,25)
| # | Hora | Lado | Sinal | Entrada | Saída | fav | BE | Motivo | PnL | Obs |
|---|------|------|-------|---------|-------|-----|-----|--------|-----|-----|
| 1 | 10:49 | LONG | NIV_L21 | 29587,55 | ~29596,50 | 29598,25 (+10,7pt) | sim | TrailingTick | **~+$89,5** ⚠️ | tocou mín 29577,25 (L=29564, dist 10pt) e FECHOU ACIMA (C=29587,25) → rejeição válida; trava tick a tick, devolveu 1,75pt do topo |

**Resumo do dia:** diurna +1 trade (win) | noturna **DESLIGADA** (decisão 23/06) | **total ~+$89,5** | bateu stop diário? não.

> ⚠️ **PnL a confirmar (fonte da verdade = TraderOS/corretora):** cálculo pelo log = (29596,50 − 29587,55) × 5 MNQ × $2 ≈ **+$89,5** (fill 29595,00 no log → ~+$74,5). **Painel do print mostrava `$ 60,50`** — divergência possível por taxas/comissão ou fill real pior. O `A: 29665 / B: 29664,25` do print é só o book no momento (não o trade).
>
> ✅ **Saída LIMPA, sem fantasma** — mais um dia validando o fix `BufferStopServidorPontos=5`. Trade-livro: reversão na mínima do dia anterior, vela fechou acima da linha (rejeição válida), BE armou (fav +10,7pt), trailing tick saiu no lucro. 1 só entrada = dentro do esperado pós-`MaxTradesDia=12`.
>
> 🧪 **Feedback Andersson+Marcelo (trailing apertado) → TESTADO e REJEITADO (25/06):** a sensação de "saiu cedo, pegou a merreca e depois correu" foi investigada com 3 backtests (300k candles): trailing uniforme largo, escalonado e saída parcial — **todos pioram**. O 1,75pt é o ótimo. Detalhe completo em `docs/trailing-veredito.md`. Scripts: `run_trailing_fino.py`, `run_trailing_escalonado.py`, `run_saida_parcial.py`.
