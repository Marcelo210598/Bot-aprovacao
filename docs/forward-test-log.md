# 📒 Log do Forward Test — BotAprovacao (Market Replay)

Registro dos trades e observações do bot rodando no NinjaTrader 8 (Market Replay, MNQ 09-26, conta Playback101). Config: 5 MNQ, TP 60, SL 12,5, BE +3,75→+2,5, trailing 1,75, **tolerância 20 ticks (5pt)**, stop diário $750, sem limite de trades.

---

## Sessão 13/06/2026 — dia de replay: 09/06/2026

### ✅ Trade 1 — SHORT (10:06) → +$79
- Sinal: `SHORT @ 30033,50 | tocou Max 30038,75 (H=30035,00) e FECHOU ABAIXO (C=30033,50)`
- **Só existiu por causa da tolerância 20.** Com a tolerância antiga (6 ticks), a zona começava em 30037,25 e o topo (H=30035) não alcançaria → não entraria. Com tol 20, a zona vai até 30033,75 → entrou.
- Desfecho: o **trailing funcionou** — preço caiu ~15pt a favor, breakeven+trailing desceram o stop de 30047 para ~30027; o preço reverteu pra cima e bateu o stop trailing. Saiu em 3 lotes (~30026,87). **Lucro +$79** (trailing transformou uma reversão em ganho protegido).
- TraderOS: `MNQ SHORT x5 PnL=$79 — HTTP 201 OK` (enviado).

### ⏭️ Não-entrada (~10:29) — rejeição linda IGNORADA (correto)
- Candle vermelho forte de rejeição, mas o **topo ficou abaixo de 30033,75** (zona de short). Nem gerou log = não tocou a zona.
- Lição: a estratégia só opera rejeição **na máx/mín do dia anterior** (dentro da tolerância). Rejeição fora da linha, por mais bonita, não é o setup. Não vale afrouxar mais a tolerância (backtest: acima de 24 ticks a taxa cai p/ 91% + overfit).

### ✅ Trade 2 — SHORT (10:31) → +$398,50 (fechado por erro de ordem, ver bug)
- Sinal: `SHORT @ 30022,00 | tocou Max 30038,75 (H=30035,00) e FECHOU ABAIXO (C=30022,00)`
- Por que pegou (e o de 10:29 não): o topo **H=30035 alcançou a zona** (≥ 30033,75); o de 10:29 ficou abaixo. ~2pt no topo decidiram.
- Fill real ~30010 (preço caiu na abertura da barra seguinte → entrou ~12pt melhor que o sinal; a defasagem do OnBarClose jogou a favor desta vez).
- Preço despencou ~46pt a favor (chegou a +$455). **Mas fechou em ~29970 com +$398,50 por causa de um BUG** (ver abaixo), não pelo trailing/alvo planejado.

### 💰 Placar do dia (replay 09/06): **+$477,50** (Trade 1 +$79,00 · Trade 2 +$398,50) — 2 trades, 2 ganhos

---

## 🐞 BUG ENCONTRADO (13/06) — trailing desabilitava a estratégia
- No Trade 2, o preço caiu muito rápido; ao tentar **mover o trailing**, o NT8 retornou `'Não é possível alterar ordem'` e, por `RealtimeErrorHandling=StopCancelClose`, **desabilitou a estratégia inteira** e fechou a posição (StopCancelClose ~29970).
- **Causa:** trailing apertado (1,75pt) + fills parciais (2 ordens stop: 1 e 4) + OnBarClose em movimento veloz → o stop calculado ficou do lado errado do mercado no instante do envio → ordem inválida.
- **Gravidade:** o trade até lucrou ($398,5), mas ao vivo o bot **pararia de operar sozinho** sem o usuário perceber. Crítico.
- **Correção aplicada (13/06):**
  1. `RealtimeErrorHandling = IgnoreAllErrors` — um erro de alteração de ordem não desabilita mais a estratégia.
  2. **Validação do trailing:** só reposiciona o stop se ele for válido vs. mercado (short: stop > Close; long: stop < Close). Evita gerar a ordem inválida.
- Pendente: re-rodar o replay com a correção e confirmar que o trailing move sem derrubar a estratégia.

---

## 🔎 Observações técnicas confirmadas no forward test
1. **Trailing em degraus (OnBarClose):** o stop só atualiza no FECHAMENTO de cada barra de 1 min. A 1ª barra em posição apenas seta o stop inicial; o trailing só move a partir da 2ª barra. Entre fechamentos o stop fica parado — fiel ao backtest, mas ao vivo numa reversão intrabar rápida pode devolver um pouco mais que um trailing tick-a-tick.
2. **Tolerância 20 capturando trades reais** que a de 6 deixaria passar (Trade 1) — otimização validada na prática.
3. **Indicador `OrderLineDecorator`** (adicionado manualmente no meio) deu `NullReferenceException` no OnStateChange. **NÃO interferiu** na estratégia (trades rodaram normais) — erro é só do indicador. Recomendado remover.
4. **Integração TraderOS** enviando os trades (HTTP 201). Verificar se aparecem no painel — possível filtro de conta simulação (Playback101).
