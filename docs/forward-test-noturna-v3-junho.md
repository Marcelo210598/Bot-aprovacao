# 📒 Forward Test — AberturaNYSpecAndersson_v3 (janela NOITE, junho/2026)

Registro dos trades reportados pelo Marcelo no Market Replay (NT8, MNQ JUN26, Tick Replay,
conta Playback101). Objetivo: testar **só a janela da noite** (18:00 ET = 19h Brasília) em
junho/2026 inteiro; se satisfatório, ligar manhã (09:30 ET) + noite juntas em jun+jul.

**Config fixa do teste:** `AtivarAberturaManha=false` / `AtivarAberturaNoite=true`,
abertura noite=18:00 ET, flatten noite=20:00 ET, Contratos=4, StopLossDolares=$150,
TakeProfitDolares=$500, BE ativa=$60/protege=$0/incremento=$30, Gatilho=10 ticks,
JanelaMonitoramento=60s. `src/AberturaNYSpecAndersson_v3.cs`.

---

## Placar acumulado

| Dia | Direção | Entrada (média) | Saída (média) | Motivo | Pts | $ (bruto, s/comissão) |
|---|---|---|---|---|---|---|
| 01/06 | LONG | 30546,88 | 30528,13 | STOP | −18,75 | **−$149,00** |
| 02/06 | SHORT | 30741,81 | 30730,38 | TRAIL | +11,44 | **+$91,50** |
| 03/06 | SHORT | 30444,56 | 30449,75 | BE | −5,19 | **−$41,50** (confirmado na aba Execuções) |
| 04/06 | LONG | 30406,50 | 30405,69 | TRAIL | −0,81 | **−$6,50** |
| — | — | — | Sexta (05/06) | — | — | sem pregão noturno — Globex fecha 17h ET sexta, reabre 18h ET domingo |
| 08/06 | SHORT | 29438,06 | 29438,63 | BE | −0,56 | **−$4,50** |
| 09/06 | SHORT | 29042,25 | 29047,63 | STOP | −5,38 | **−$43,00** |
| 10/06 | SHORT | 28464,25 | 28467,50 | BE | −3,25 | **−$26,00** |
| 11/06 | LONG | 29456,44 | 29470,56 | TRAIL | +14,13 | **+$113,00** |

| 15/06 | LONG | 30545,13 | 30552,31 | TRAIL | +7,19 | **+$57,50** |
| 16/06 | LONG | 30022,19 | 30011,25 | STOP | −10,94 | **−$87,50** |
| 17/06 | SHORT | 29835,13 | 29856,13 | STOP | −21,00 | **−$168,00** |
| 18/06 | LONG | 30763,88 | 30759,13 | STOP | −4,75 | **−$38,00** (rolou pro contrato SEP26 aqui) |
| 22/06 | LONG | — | — | TRAIL | — | **+$21,50** |
| 23/06 | LONG | — | — | TRAIL | — | **−$14,00** |
| 24/06 | SHORT | — | — | STOP | — | **−$142,50** |
| 25/06 | SHORT | — | — | STOP | — | **−$137,00** |
| 29/06 | LONG | — | — | STOP | — | **−$144,50** |
| 30/06 | LONG | — | — | TRAIL | — | **+$68,50** |

**MÊS FECHADO (junho, só noite): −$650,00 — 18 trades, 5 ganhos / 13 perdas (28% WR)**

### Quebra por motivo de saída (mês inteiro)
| Motivo | Trades | Ganhos | Resultado |
|---|---|---|---|
| STOP | 8 | 0 | **−$909,50** |
| BE | 3 | 0 | **−$72,00** |
| TRAIL | 7 | 5 | **+$331,50** |

**Leitura:** o TRAIL é a única fonte de lucro (71% WR, +$331,50) — o BE nunca protegeu de
verdade (3/3 negativas, pequenas) e o STOP cheio (8×, sempre perda máxima) consome tudo:
quase −$910 sozinho. Sozinha, a janela da noite **fechou o mês no negativo**. Pelo critério
combinado com o Marcelo ("se satisfatório, testa manhã + noite juntas"), esse resultado
**não bate o critério** como está — decisão em aberto: testar manhã sozinha primeiro, ou ir
direto pro combo mesmo com a noite fraca.

### ⏳ Pendente
- **Manhã sozinha** (`AtivarAberturaManha=true`, `AtivarAberturaNoite=false`) — ainda não rodado.
- **Manhã + noite juntas** — ainda não rodado.

---

## 🐞 Bug encontrado e corrigido (14/09, entre o dia 01/06 e 02/06)
O `.cs` só contava o **último pedaço** quando a entrada/saída enchia em mais de 1 fill
parcial (comum no Replay) — jogava fora o PnL do(s) fill(s) anterior(es). Foi por isso que
o `[FLUSH]` do dia 01/06 mostrou −$75 (só a saída de 2 contratos @ 30528,00), quando o real
(somando os 2 pedaços da saída, 2+2) é **−$149,00**. Corrigido: agora acumula média
ponderada de entrada E saída até a posição ficar flat. Números da tabela acima já são os
corretos (recalculados na mão pra 01/06; 02/06 já saiu certo). Dias a partir de agora, se
você resalvar o `.cs` atualizado na VM, o `[FLUSH]` já vem certo sozinho.

---

## Detalhe por dia

### 01/06/2026 — LONG → STOP (−$149,00)
- Abertura (18:00 ET) → gatilho de 10 ticks disparou LONG.
- Entrada: 2 @ 30546,75 + 2 @ 30547,00 (média 30546,88, 4 contratos).
- Saída: `AbStop` — 2 @ 30528,25 + 2 @ 30528,00 (média 30528,13).
- Perda bateu certinho o `StopLossDolares=$150` configurado (mecanismo de stop sintético
  validado, mesmo sem ordem nativa no NT8).

### 02/06/2026 — SHORT → TRAIL (+$91,50)
- Entrada: 1 @ 30742,00 + 3 @ 30741,75 (média 30741,81, 4 contratos).
- Saída: `AbTrail` — 2 @ 30730,25 + 2 @ 30730,50 (média 30730,38).
- O BE progressivo travou lucro no trailing antes de reverter — não foi alvo nem stop, foi
  o degrau de proteção segurando o ganho. Primeiro sinal de que a gestão em degraus funciona
  como pensado.

---

## ⚠️ Notas de leitura
- **1 trade ainda não diz nada** — critério de "satisfatório" só faz sentido com o mês
  inteiro rodado (≈20 pregões). Não tirar conclusão cedo.
- P&L aqui é **bruto** (sem comissão/slippage) — igual ao padrão do V1/V2. Ver relatório do
  Strategy Analyzer pro número líquido quando o mês fechar.
- Ir mandando os prints/resultados de cada dia que eu vou somando aqui.
