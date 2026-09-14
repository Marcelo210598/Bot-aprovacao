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
| 01/06 | LONG | 30546,90 | 30528,10 | STOP | −18,80 | **−$150,40** |

**Total até agora: −$150,40 — 1 trade, 0 ganho / 1 perda (0% WR)**

---

## Detalhe por dia

### 01/06/2026 — LONG → STOP (−$150,40)
- Abertura (18:00 ET) → gatilho de 10 ticks disparou LONG.
- Entrada: 2 @ 30546,75 + 2 @ 30547,00 (fill em 2 pedaços, 4 contratos).
- Saída: `AbStop` — 2 @ 30528,25 + 2 @ 30528,00.
- Perda bateu certinho o `StopLossDolares=$150` configurado (mecanismo de stop sintético
  validado, mesmo sem ordem nativa no NT8).

---

## ⚠️ Notas de leitura
- **1 trade ainda não diz nada** — critério de "satisfatório" só faz sentido com o mês
  inteiro rodado (≈20 pregões). Não tirar conclusão cedo.
- P&L aqui é **bruto** (sem comissão/slippage) — igual ao padrão do V1/V2. Ver relatório do
  Strategy Analyzer pro número líquido quando o mês fechar.
- Ir mandando os prints/resultados de cada dia que eu vou somando aqui.
