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

**Total até agora: −$66,00 — 8 trades, 2 ganhos / 6 perdas (25% WR)**

### Observação por motivo de saída (ainda amostra pequena, mas de olho)
- **STOP** (2×): sempre perda cheia, como esperado (−149, −43).
- **BE** (3×): as 3 vezes deu **perda pequena**, nunca lucro — o stop sintético trava em ~$0
  mas o preencimento costuma escorregar um pouco pro lado errado antes de sair (−41,50, −4,50,
  −26,00). Não é catastrófico, mas até agora BE nunca protegeu de verdade, só reduziu o dano.
- **TRAIL** (3×): é de onde saem os ganhos — 2 de 3 foram positivos e grandes (+91,50, +113,00),
  só 1 pequeno negativo (−6,50). Bom sinal do degrau de proteção funcionando quando o preço
  anda bastante a favor.

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
