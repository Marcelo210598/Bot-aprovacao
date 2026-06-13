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

## 🐞 BUG 2 (13/06) — trailing com ordem no servidor é incompatível com 1,75pt
Após o 1º fix, apareceram mais erros ao mover o stop em reentradas/movimento rápido:
- `'Não é possível alterar ordem'`
- `'OCO ID não pode ser reutilizado'`
- `'Ordens de comprar stop não podem ser aplicadas abaixo do mercado'` (BuyToCover StopMarket)

**Causa raiz (a mesma dos 3):** manter uma **ordem de stop real no servidor** colada ao preço com trailing de **1,75pt** é incompatível — a ordem fica sempre dentro do range da barra (→ "stop abaixo do mercado"), e reentradas colidem OCO IDs. No backtest não dá problema porque lá o stop é só comparação, não ordem real.

**Correção definitiva (13/06) — reescrita da gestão de saída (`src/BotAprovacao.cs`, arquivo renomeado de ApexBot94.cs):**
- **Stop inicial (12,5) + Alvo (60)** = ordens FIXAS no servidor (válidas, protegem intrabar). Nunca movidas.
- **Breakeven + trailing** = SINTÉTICOS no código (igual ao backtest): a cada barra, se atingiu o nível do trailing (após o breakeven), fecha **a mercado**. Não move ordens.
- **Nome de sinal único por trade** (`NIV_S{n}`/`NIV_L{n}`) → mata a colisão de OCO.
- `RealtimeErrorHandling = IgnoreAllErrors` como rede.
- **Trade-off honesto:** o trailing sintético fecha **a mercado** (próximo tick), não no preço exato como no backtest → pode haver leve slippage na saída do trailing. É o custo de robustez (sem os erros de ordem).
- Pendente: re-rodar o replay e confirmar que opera limpo (sem erros) e o trailing fecha os trades.

### ✅ Trade 3 — SHORT (10:55) → +$554,00 (FECHADO NA MÃO)
- Sinal: `SHORT @ 30025,00 | tocou Max 30038,75 (H=30074,25) e FECHOU ABAIXO (C=30025,00)`
- ⚠️ Entrou **sem TP nem SL** (bug do OCO da versão antiga impediu a criação das ordens de proteção → posição desprotegida). O Marcelo **fechou manualmente** (botão Flat) num bom momento, garantindo +$554.
- Foi o achado mais grave: posição sem stop ao vivo = risco de estourar a conta. **Corrigido na versão nova** (nomes únicos → stop+alvo sempre criados).

### 💰 PLACAR FINAL DIA 09 (replay, versão ANTIGA com bugs): **+$1.031,50**
- Trade 1 +$79,00 · Trade 2 +$398,50 · Trade 3 +$554,00 — 3 trades, 3 ganhos.
- ⚠️ Resultado obtido na versão ANTIGA (com os bugs de ordem). O dia 09 serviu para **descobrir e corrigir** os bugs (tolerância, trailing/erro de ordem, OCO/posição desprotegida). O placar não valida a estratégia ao vivo — valida que os achados foram reais.

---

## 🐞 BUG 3 (13/06) — stop inicial nascia inválido (LONG perdeu -$1.918)
Ao testar a versão "corrigida", um LONG (entrou na mín 29627, furou e despencou) **perdeu -$1.918** porque o stop de 12,5pt **nunca foi criado**:
```
Ordens de vender stop não podem ser aplicadas ACIMA do mercado. Ordem afetada: Sell 2 StopMarket @ 29623
```
**Causa:** o `SetStopLoss(Price)` era chamado no **fechamento da barra** (OnBarClose). Quando o candle de entrada despencava rápido, no fechamento o mercado já estava abaixo do stop → ordem inválida → não criada → posição sem proteção. Só fechou quando o stop diário ($750) acionou — mas em queda livre, saiu em -$1.918.
> Esclarecimento: o stop é 12,5pt ($125) pra a posição inteira (não há "stop dividido"; só os fills vêm em lotes). A perda gigante foi o bug, não o design.

**Correção (13/06):** `SetStopLoss`/`SetProfitTarget` agora são chamados em **`CalculationMode.Ticks` ANTES do Enter** → o NT8 cria as ordens **atreladas ao fill**, no preço correto, protegendo intrabar desde o 1º tick. Nunca mais nasce inválido. Trailing sintético mantido.

## ✅ Versão corrigida compilada (13/06 ~18h)
`BotAprovacao.cs` (trailing sintético + nomes únicos + IgnoreAllErrors + stop/alvo na entrada por ticks) baixada do GitHub e compilada no NT8 (Compile succeeded).

### 🔢 Trade 4 — LONG (11:44) → -$1.918 (bug) | ajustado p/ -$125 (stop correto)
- `LONG @ 29631,00 | tocou Min 29627,00 (L=29626,75) e FECHOU ACIMA (C=29631,00)`. Furou a mínima e despencou. Stop não foi criado (bug 3) → perda real -$1.918. Com o stop funcionando (12,5pt) teria sido **-$125**.

## 💰 PLACAR CONSOLIDADO DIA 09 (ajustado, considerando stop correto no T4): **+$906,50**
| # | Trade | Real | Ajustado (stop ok) |
|---|---|---:|---:|
| 1 | SHORT (trailing) | +$79,00 | +$79,00 |
| 2 | SHORT | +$398,50 | +$398,50 |
| 3 | SHORT (mão) | +$554,00 | +$554,00 |
| 4 | LONG (bug) | -$1.918,00 | **-$125,00** |
| | **TOTAL** | -$886,50 | **+$906,50** |

⚠️ Todos os 4 trades rodaram em versões com bug (dia de debugging). O número ajustado (+$906,50) é uma estimativa do que seria com o stop funcionando — NÃO um resultado validado. A validação real virá ao rodar um **dia limpo** com a versão final.

## 📌 Status no fim da sessão 13/06
- 4 bugs achados e corrigidos no forward test: (1) tolerância 6→20 [melhoria], (2) trailing desabilitava estratégia, (3) OCO → posição sem proteção, (4) stop inicial inválido → perda gigante.
- Versão final `BotAprovacao.cs` compilada, no GitHub e na pasta do NT8.
- **Próximo (dia 10/06):** rodar o replay limpo com a versão final e confirmar: SL/TP sempre na tela, stop cortando em ~$125, trailing fechando, zero erros. Esse é o teste que valida o bot.

---

## 🔎 Observações técnicas confirmadas no forward test
1. **Trailing em degraus (OnBarClose):** o stop só atualiza no FECHAMENTO de cada barra de 1 min. A 1ª barra em posição apenas seta o stop inicial; o trailing só move a partir da 2ª barra. Entre fechamentos o stop fica parado — fiel ao backtest, mas ao vivo numa reversão intrabar rápida pode devolver um pouco mais que um trailing tick-a-tick.
2. **Tolerância 20 capturando trades reais** que a de 6 deixaria passar (Trade 1) — otimização validada na prática.
3. **Indicador `OrderLineDecorator`** (adicionado manualmente no meio) deu `NullReferenceException` no OnStateChange. **NÃO interferiu** na estratégia (trades rodaram normais) — erro é só do indicador. Recomendado remover.
4. **Integração TraderOS** enviando os trades (HTTP 201). Verificar se aparecem no painel — possível filtro de conta simulação (Playback101).
