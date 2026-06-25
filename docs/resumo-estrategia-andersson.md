# 🤖 BotAprovacao — Resumo da estratégia (pro Andersson)

> Atualizado em 25/06/2026. Resumo prático de como o bot opera: entrada, saída,
> acompanhamento tick a tick, e por que os parâmetros estão como estão.
> Tem 2 versões: a **completa** (abaixo) e a **WhatsApp** (no final, pronta pra colar).

---

## Em uma frase
O bot opera **reversão na máxima/mínima do dia anterior** — quando o preço bate numa
dessas linhas e *rejeita*, ele entra na contramão. São **5 contratos MNQ** ($10/ponto).

## 📥 ENTRADA (diurna, 9h30–16h ET)

1. O bot marca a **máxima** e a **mínima do dia anterior** (na 2ª-feira usa o range do domingo à noite / Globex).
2. Espera o preço **tocar** uma dessas linhas — com **folga de 5 pontos** (20 ticks). Não precisa cravar.
3. Só entra se a vela **rejeitar** a linha:
   - Tocou a **máxima** e **fechou abaixo** → **VENDE** (short)
   - Tocou a **mínima** e **fechou acima** → **COMPRA** (long)
4. **Filtro anti-corrida (chase):** se a vela fechar a mais de **15pt** da linha, ignora (não corre atrás do preço).
5. Entra **a mercado no fechamento** da vela de rejeição.

## 📤 SAÍDA e ACOMPANHAMENTO (tick a tick, ao vivo)

O bot acompanha **cada tick** (não espera a vela fechar):

| Etapa | Valor | Em $ (5 MNQ) |
|---|---|---|
| 🛑 **Stop inicial** (no servidor) | 12,5 pt | −$125 |
| 🎯 **Alvo** | 60 pt | +$600 |
| 🔒 **Breakeven** — quando anda a favor… | +3,75 pt | …trava **+2,5 pt** (+$25) |
| 🪜 **Trailing** — depois do breakeven | persegue o topo a **1,75 pt** | — |

**Como funciona:** assim que o trade anda **+3,75pt** a favor, o stop sobe pro lucro travado de
**+2,5pt** (não tem mais como virar prejuízo). A partir daí, o stop **persegue o melhor preço a
1,75pt de distância**, tick a tick — **só aperta, nunca afrouxa**. Se o preço recuar 1,75pt do
topo, fecha no lucro. Se disparar, vai até os 60pt do alvo.

## 🤔 Por que o trailing de 1,75pt é tão "apertado"?

Testamos **de 3 jeitos** com backtest de 300 mil candles:

| Tentativa de "deixar correr mais" | Resultado |
|---|---|
| Trailing mais largo (2 a 12pt) | ❌ piorou tudo |
| Trailing escalonado (aperta e depois solta) | ❌ não pegou nenhum runner a mais |
| Saída parcial (parte sai, parte corre) | ❌ pegou +$11k nos runners, mas perdeu mais no meio |

**O motivo:** é uma estratégia de **acerto alto (≈68%)** que vive do **lucro pequeno-médio
confiável**. Na reversão, a maioria dos trades anda pouco — o trailing apertado garante esse
lucro. Os trades que *correm de verdade* já são pegos pelo **alvo de 60pt**. Afrouxar o trailing
só faz **devolver lucro** na maioria das vezes.

> 💡 Aquela sensação de "saiu cedo e depois subiu forte" é real e chata de ver, mas é o
> **preço de ter acerto alto**. Nos números, segurar pra cavalgar **custa mais do que rende** —
> comprovado 3 vezes.

## ✅ Taxa de aprovação atual (números realistas)

Com as condições **reais da conta** (25K EOD, drawdown $1.000, slippage de 2 ticks, máx 12 trades/dia):

- **~70% de aprovação** das janelas testadas
- Aprova em **~16 dias** (mediana)
- **Acerto 68%** · Fator de lucro **1,41**

## 🛡️ Proteções

- **Stop diário: $750** — bateu, para o dia.
- **Máx 12 trades/dia** — corta overtrading (subiu a aprovação de 57% → 70%).
- **Noturna: DESLIGADA** (decisão de 23/06).

---

## 📱 VERSÃO WHATSAPP (copiar e colar)

```
🤖 *BOT DE APROVAÇÃO — COMO FUNCIONA*

Resumindo: o bot opera *reversão na máxima/mínima do dia anterior*. Quando o preço bate numa dessas linhas e rejeita, ele entra na contramão. São *5 contratos MNQ* ($10 por ponto).

━━━━━━━━━━━━━━━
📥 *ENTRADA* (9h30–16h, horário de NY)

1️⃣ O bot marca a *máxima* e a *mínima do dia anterior* (na segunda usa o range do domingo à noite).

2️⃣ Espera o preço *tocar* uma dessas linhas — com *folga de 5 pontos*. Não precisa cravar exato.

3️⃣ Só entra se a vela *rejeitar*:
• Tocou a *máxima* e fechou abaixo → *VENDE*
• Tocou a *mínima* e fechou acima → *COMPRA*

4️⃣ Filtro anti-corrida: se a vela fechar a mais de *15pt* da linha, ignora (não corre atrás).

5️⃣ Entra *a mercado no fechamento* da vela de rejeição.

━━━━━━━━━━━━━━━
📤 *SAÍDA E ACOMPANHAMENTO* (tick a tick, ao vivo)

O bot acompanha *cada tick*, não espera a vela fechar:

🛑 Stop inicial: *12,5 pt* (−$125)
🎯 Alvo: *60 pt* (+$600)
🔒 Breakeven: andou *+3,75pt* a favor → trava *+2,5pt* de lucro
🪜 Trailing: depois do breakeven, o stop persegue o topo a *1,75pt*

Na prática: quando o trade anda +3,75pt, o stop sobe pro lucro travado de +2,5pt (não vira mais prejuízo). Daí ele *persegue o melhor preço a 1,75pt*, tick a tick — só aperta, nunca afrouxa. Recuou 1,75pt do topo, fecha no lucro. Disparou, vai até os 60pt.

━━━━━━━━━━━━━━━
🤔 *POR QUE O TRAILING DE 1,75 É TÃO APERTADO?*

Boa pergunta — testamos com backtest de 300 mil candles, de 3 jeitos:

❌ Trailing mais largo (2 a 12pt) → piorou tudo
❌ Trailing escalonado (aperta e depois solta) → não pegou nenhum trade grande a mais
❌ Saída parcial (parte sai, parte corre) → pegou lucro extra nos grandes, mas perdeu mais no meio

O motivo: é uma estratégia de *acerto alto (~68%)* que vive do *lucro pequeno-médio confiável*. Na reversão, a maioria dos trades anda pouco — o trailing apertado garante esse lucro. Os trades que correm de verdade já são pegos pelo *alvo de 60pt*.

💡 Aquela sensação de "saiu cedo e depois subiu forte" é real e chata de ver, mas é o *preço de ter acerto alto*. Nos números, segurar pra cavalgar custa mais do que rende — comprovado 3 vezes.

━━━━━━━━━━━━━━━
✅ *TAXA DE APROVAÇÃO* (números reais)

Com as condições reais da conta (25K, drawdown $1.000, slippage, máx 12 trades/dia):

• *~70% de aprovação*
• Aprova em *~16 dias* (mediana)
• Acerto *68%* · Fator de lucro *1,41*

━━━━━━━━━━━━━━━
🛡️ *PROTEÇÕES*

• Stop diário: *$750* (bateu, para o dia)
• Máx *12 trades/dia* (corta overtrading)
• Noturna: *DESLIGADA*
```
