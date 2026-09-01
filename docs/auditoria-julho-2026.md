# Auditoria completa — BotAprovacao_BETrigger25 (forward test julho/2026)

> Pedido do Marcelo (01/09): auditoria quantitativa completa. Não "é lucrativo ou não" — **POR QUE
> o resultado está ruim** e quais mudanças têm maior potencial de robustez, sem overfitting.
> Fonte: 44 trades reais do Market Replay ao vivo (`forward-test-replay-25k/2026-07-betrigger25/`,
> `[MeuTrade] PnL` de cada trade `[REAL]`). Scripts: `backtest/auditoria_julho.py`,
> `backtest/analise_facada.py`.

---

## PARTE 0 — DIAGNÓSTICO DOS DADOS (antes de qualquer sugestão)

### 0.1 — Números de julho vs. o backtest de 13 meses

| Métrica | Forward julho (44 trades) | Backtest 13 meses (1.512 trades) |
|---|---|---|
| **Win rate** | **45,5%** | **73%** |
| **Profit Factor** | **0,44** | **1,50** |
| Expectancy | **−$17,5 / trade** | +$19,1 / trade |
| Avg Win | **+$31** | +$80 |
| Avg Loss | −$58 (média) / −$143 (só os stops cheios) | −$141 |
| Payoff \|AW/AL\| | 0,53 | 0,57 |
| Max Drawdown | $892 (curva de 44 trades) | — |
| Recovery Factor | 0,86 | — |
| Sharpe / trade | −0,25 | +0,14 |
| Meses vermelhos | 1 de 1 (julho) | **0 de 13** |

**O backtest NUNCA teve um mês vermelho** (13/13 verdes, PF 1,03 a 1,94). O forward test de julho
está em PF 0,44. Isso não é "azar de um mês" — é uma **divergência estrutural entre o backtest e a
execução real.**

### 0.2 — Onde exatamente o resultado quebrou

Duas coisas colapsaram, e são a MESMA causa:

**(a) Win rate 73% → 45%.** No backtest, 73% dos trades terminam positivos. Em julho, 45%.
A diferença são **~28 trades por 100 que o backtest conta como "ganho pequeno" (+$20-40) e que,
ao vivo, saem no breakeven ou levemente negativos (−$5 a −$13).**

**(b) Avg Win $80 → $31.** Os ganhos ao vivo são ~1/3 do backtest.

Reconstrução do mecanismo (por 100 trades):
- Backtest: 73 ganham +$80 (+$5.840), 27 perdem −$141 (−$3.807) → **net +$2.033, PF 1,53**
- Julho: 45 ganham +$31 (+$1.395); 55 perdem, sendo ~16 stops cheios −$140 (−$2.240) + ~39
  "scratches de trailing" −$7 (−$273) → **net −$1.118, PF 0,44**

**O trailing tick-a-tick ao vivo (`OnMarketData`) não está segurando o lucro dos trades que o
backtest (`OnBarClose`) segura.** Esse é o problema #1.

### 0.3 — Distribuição dos 44 trades

```
  [ -999,-100)  9   #########   <- 7 facadas + 2 gaps de entrada = -$1.286
  [ -100, -50)  0
  [  -50, -10)  3   ###          <- 15/07 L20, 20/07 L1, 08/07 L14... trailing loss
  [  -10,   0) 12   ############  <- trailing "nickado" (deveria ser +$20)
  [    0,  10)  4   ####
  [   10,  30) 10   ##########    <- trailing que funcionou pequeno
  [   30,  80)  4   ####
  [   80, 999)  2   ##            <- os 2 runners: 13/07 L5 +$123, L7 +$102
```

**Barbell quebrada:** as 9 perdas grandes (−$1.286) não são compensadas porque os ganhos estão
capados em +$30 em vez de +$85, e 12 trades que deveriam ser ganho pequeno viraram perda pequena.

### 0.4 — Os 8-9 grandes losses SÃO o mês inteiro

| Trade | fav máx | PnL | tipo |
|---|---|---|---|
| 02/07 11:27 L | +0,75pt | −$169 | facada |
| 08/07 12:00 L | +2,10pt | −$158 | gap de entrada |
| 10/07 13:16 S | +1,00pt | −$156 | facada |
| 13/07 11:18 L | +0,55pt | −$153 | gap de entrada |
| 06/07 11:22 S | +0,80pt | −$148 | facada |
| 08/07 12:01 L | +1,85pt | −$139 | facada |
| 06/07 11:29 S | +0,85pt | −$122 | facada |
| 13/07 13:27 L | +0,75pt | −$121 | facada |
| 14/07 10:51 S | +1,05pt | −$120 | facada |
| **soma** | | **−$1.286** | |
| os outros 35 trades | | **+$515** | |

---

## PARTE 1 — ANALISTA QUANTITATIVO

- **Profit Factor 0,44** (backtest 1,50). PF < 1 = estratégia perdedora na amostra.
- **Expectancy −$17,5/trade.** Precisa virar positiva.
- **Win Rate 45,5%** — abaixo do que a reversão precisa (o payoff é 0,53, então o breakeven de WR
  é ~65%). Está 20pp abaixo.
- **AW/AL: +$31 / −$58.** Os stops cheios são −$143 (idênticos ao backtest — o SL de 12,5pt×5
  contratos×$2 = $125 + slippage). Os ganhos é que sumiram.
- **Max Drawdown $892** na curva de 44 trades. Numa Apex real, 89% do limite — estouraria.
- **Recovery Factor 0,86** (<1 = não recuperou o drawdown).
- **Sequências:** pior sequência de perdas = 6 trades seguidos (2x: 06/07 e 08/07-10/07). Melhor
  de ganhos = 5 (10/07 e 15/07).
- **Por horário:** 13h E[−$87] (n=3, ruído), 12h E[−$26] (n=7), 11h E[−$20] (n=16), 10h E[−$1]
  (n=18). **No backtest de 13 meses TODAS as horas são +$16 a +$29/trade** (11h é a melhor, WR
  75%). O perfil ruim de julho por hora é **amostra pequena, não efeito real** — filtro de hora
  aqui é overfitting.
- **Por dia da semana:** seg −$236 (n=16), ter −$140 (n=6), qua −$218 (n=11). Todos vermelhos,
  todos amostra pequena.
- **Long × Short:** −$390 vs −$382, WR 45% nos dois. **Zero viés direcional.** Backtest também
  equilibrado.
- **Custos:** comissão $6 RT / 5 contratos + slippage 2 ticks ($5) = ~$11/trade. Em 44 trades =
  −$484. **Isso sozinho vira −$771 em −$287.** Não é a causa, mas num E[−$17,5] os custos são 63%
  do prejuízo. Reduzir contratos (2-3 MNQ) corta o custo pela metade sem mudar o edge (meta e DD
  são em $, não escalam — já testado).

---

## PARTE 2 — TRADER (as entradas/saídas fazem sentido?)

- **A entrada faz sentido no conceito:** fade da máx/mín do dia anterior é um nível real que o
  mercado respeita. WR 73% no backtest confirma que o nível "segura" na maioria das vezes.
- **O problema é o CONTEXTO:** julho o MNQ ficou **rangey/choppy em volta dos níveis PDH/PDL**.
  Nesse regime:
  - As reversões que "seguram" só quicam +2-4pt e param (→ trailing win minúsculo).
  - As reversões FALSAS (o preço só atravessa o nível) viram facada (→ stop cheio).
  - O ratio ganho pequeno / perda cheia fica insustentável.
- **Backtest confirma a dependência de regime:** meses de tendência (nov/25 avgW +$130, mar/26
  +$143, fev/26 +$120) carregam a média; meses choppy (jun/25 avgW +$51, jul/25 +$50, mai/26
  +$91 mas PF 1,17) mal ficam positivos. **Julho e junho foram os 2 meses do forward test — e o
  BE trig 2,5 tem os DOIS junhos do dataset entre os piores.** Amostra ruim de propósito.
- **Stop atingido por ruído?** Parcialmente. Nos stops cheios "normais" (não-facada), o preço foi
  a favor 3-14pt antes de reverter — o SL de 12,5pt é atingido por um movimento REAL de reversão,
  não por ruído de 1-2pt. Nas facadas, a "reversão em V" é o mercado, não ruído.
- **TP distante demais?** O alvo de 60pt **nunca foi atingido em julho** (nem em junho). Na
  prática a estratégia não tem alvo — vive do trailing. O "60pt" é decorativo.
- **Entradas atrasadas: SIM, confirmado 2x** (gap de entrada, ver Parte 4).
- **Saídas prematuras: SIM** — 12 trades com BE ativo + favor ≥3pt saíram ≤$0 (Parte 4).

---

## PARTE 3 — PRICE ACTION (o que winners e losers têm em comum?)

### Vencedores (20 trades, avg +$31):
- **Os 2 grandes** (13/07 L5 +$123, L7 +$102): reversão num nível + **o mercado seguiu na direção
  por 10-12pt**. Follow-through real. O trailing capturou tudo.
- **Os pequenos** (+$10-30): reversão quicou +2,5-4pt, BE ativou, trailing travou +1,5-2,5pt.
- Padrão comum dos vencedores: **BE ativou (fav ≥ 2,5pt) e o preço não voltou forte pro nível.**

### Perdedores (24 trades):
- **7-9 facadas** (−$1.000): favor máx < 2pt, a **vela de entrada já reverte** em V. Duração
  mediana no backtest desse subgrupo = **0 barras**.
- **12 "trailing nick"** (−$5 a −$13): favor 3-6pt, BE ativou, mas saiu no breakeven.
- **2 gaps de entrada** (−$300): fill 10-11pt pior que o sinal após vela de spike violento.

### Condições em que o bot NÃO deveria operar (evidência):
- **Vela de sinal violenta** (spike > 15-20pt além do nível + fechamento longe do extremo).
  Nos 2 gaps de entrada a vela de sinal teve L a 17pt e 53pt do nível. Uma vela dessas = o
  mercado está em movimento forte, não em rejeição limpa → alta chance de facada OU gap de
  entrada. **Candidato a filtro de contexto** (ver Parte 5, com ressalva de overfitting).
- **Range apertado do dia anterior** — quando PDH−PDL é pequeno, o preço fica pingando os 2
  níveis o dia todo (20/07: canal de 33pt, 6 trades pra +$10). Sem evidência forte ainda.

### Long × Short: **comportamento idêntico.** Não separar.

### O SL está sendo atingido por ruído? **Não** — é atingido por reversão real (facada) ou por
movimento de 3-14pt (stop cheio normal). Apertar o SL já foi testado 3x e piora tudo.

### O TP está longe demais? **Irrelevante** — nunca é atingido. A saída real é o trailing.

---

## PARTE 4 — ESPECIALISTA NT8 (execução / backtest)

### 4.1 — `OnBarClose` × gestão intrabar (`OnMarketData`) — A CAUSA RAIZ

- `Calculate = OnBarClose`. O **backtest** roda `GerenciaPosicao` 1× por barra: checa o stop
  contra o `Low`/`High` da barra usando o stop do **início** da barra, DEPOIS atualiza o
  favor e trilha. Efeito: **repiques intrabar não tiram o trade** — o motor "segura" até o
  fechamento da barra e só então re-avalia.
- **Ao vivo/replay**, `OnMarketData` gere **a cada tick**: o favor sobe, o trailing sobe, e o
  stop é checado imediatamente. Efeito: **qualquer pullback intrabar de 2pt tira o trade** no
  nível trilhado (ou pior, no fill).
- **Consequência medida:** o backtest conta como ganho (+$20-40) trades que ao vivo saem no
  breakeven. WR 73% → 45%, avgW $80 → $31.
- **Isso invalida parcialmente TODOS os backtests do projeto** — a taxa de aprovação de "82-100%"
  assumiu a gestão `OnBarClose`. A realidade `OnMarketData` é PF ~0,44.

### 4.2 — Gap de entrada (2 casos confirmados: 08/07 NIV_L14, 13/07 NIV_L6)

- Sinal @ close da vela; `OnMarketData` preenche 10-11pt pior. O backtest preenche no close
  (perfeito). Nas 2 velas o sinal foi um spike violento.
- Provável: a lógica de entrada do `OnMarketData` espera confirmação / persegue o melhor tick em
  vez de entrar **a mercado no 1º tick após o sinal**.

### 4.3 — Velocidade do replay (500-1000x)

- 14/07 (todo trailing saiu no BE) rodou a 500x; 15/07 (trailing funcionou) a 1000x. **Inconsistente**
  → a velocidade não é a causa única, mas pode agravar. Rodar a **1x** pra descartar.

### 4.4 — `~saida` do log NÃO é o fill real

- O `<<< SAIDA ~saida X` mostra um nível de trailing inicial. O fill real (marker do gráfico +
  `[MeuTrade] PnL`) diverge muito (13/07 L5: log "~saida 29563" mas fill 29573, +$123). **Só
  confiar no `[MeuTrade] PnL`.**

### 4.5 — 🔴 Reset de nível ao reiniciar (item #18) — BLOQUEANTE

- 21/07: estratégia não aparece, gráfico não anda. 22/07: "Níveis dia anterior: (aguardando 1º
  dia)". **`pdHigh`/`pdLow` zeram quando a estratégia reinicia** (comum ao mexer no Replay). Sem
  eles, o bot fica MUDO o dia inteiro. **Precisa ser corrigido pra continuar o forward test.**

### 4.6 — Reprocessamento `[HIST]` no restart

- Ao reiniciar, o motor bar-based reprocessa o dia e gera trades `[HIST]` com nomes/PnL
  diferentes (ex.: 13/07 14:09 "StopDiario NIV_L13" que não existiu). **Ignorar tudo que é
  `[HIST]`** — só `[REAL]` conta.

### 4.7 — Order Fill Resolution / Tick Replay

- `OrderFillResolution = Standard` e **Tick Replay não está ligado** no gráfico (não há menção no
  log). Sem Tick Replay, o `OnMarketData` no backtest histórico não roda — por isso o backtest
  usa só `OnBarClose`. **Ligar Tick Replay no gráfico faria o backtest histórico rodar a mesma
  gestão intrabar do ao vivo** → os números do backtest passariam a bater com a realidade (e
  provavelmente despencariam pra perto de PF 0,44). É o teste definitivo de 4.1.

---

## PARTE 5 — PROBLEMAS CLASSIFICADOS

### 🔴 PROBLEMA #1 — Gestão de saída intrabar estrangula os ganhos `[F + C]`

- **Evidência:** avgW $80→$31, WR 73%→45%; 12 trades com BE+favor≥3pt saíram ≤$0; backtest 13/13
  meses verdes vs forward PF 0,44.
- **Impacto:** ~−$1.100/mês (a diferença entre PF 1,5 e PF 0,44). **É o problema.**
- **Causa provável:** `OnBarClose` no backtest segura o trade através de repiques intrabar; o
  `OnMarketData` tick-a-tick sai no 1º repique. O trailing de 1,75pt + BE-lock 0,75 é curto
  demais pro ruído tick-level.
- **Alteração sugerida (em ordem de preferência):**
  1. **Ligar Tick Replay no gráfico e re-rodar o backtest de 13 meses** — mede o edge REAL sob a
     gestão intrabar. Se o backtest com Tick Replay der PF > 1,3, o problema é outro; se der PF
     ~0,4-0,7, confirmado que o edge histórico era artefato de `OnBarClose`.
  2. Se confirmado: **testar trailing largo (4-8pt) e BE-lock maior (0,5-0,6 fixo) NO backtest
     COM Tick Replay.** O "trailing largo piora" do projeto foi medido só no motor `OnBarClose` —
     onde largar só devolve lucro. No motor de tick, largar pode EVITAR o nick. São motores
     diferentes, o veredito antigo não se aplica.
  3. Alternativa: **gerir a saída SÓ no `OnBarClose` mesmo ao vivo** (desligar o trailing do
     `OnMarketData`, manter só o stop inicial no servidor). Faz o ao vivo bater com o backtest.
     Risco: perde a proteção contra "stop abaixo do mercado" em rally (bug 5 de 16/06) — mas só
     pro trailing, não pro stop inicial.
- **Risco de overfitting:** BAIXO se testado com Tick Replay em 13 meses + OOS. É correção de
  execução, não filtro.
- **Como testar:** Tick Replay ON → backtest 13 meses → OOS 1ª/2ª metade → sweep de trailing
  (1,75 / 3 / 5 / 8) → escolher pela robustez (PF estável nas 2 metades), não pelo PnL máximo.

### 🔴 PROBLEMA #2 — Facada (reversão em V instantânea) `[E]`

- **Evidência:** 7 de 9 grandes losses de julho (−$975). Backtest: 70/13 meses (~5/mês, −$131
  cada, −$9,2k). Duração 0 barras. **Nenhum sinal pré-entrada as distingue** (dist_nivel, gap,
  hora, dow idênticos ao resto; espalhadas por todas as faixas).
- **Impacto:** −$130/trade × ~5-7/mês = −$650 a −$900/mês.
- **Causa:** o mercado atravessa o nível e a "vela de rejeição" era falsa. Característica de
  mean-reversion em nível fixo. O SL de 12,5pt existe pra capar isso.
- **Alteração sugerida:** NÃO tem filtro de entrada (loss-cut já rejeitado no item #16 — mata
  10,7% dos vencedores). Duas opções REAIS:
  1. **DD estático** (trocar de firma) — não evita a facada, mas evita que 2-3 num dia estourem a
     conta.
  2. **Confirmação de entrada mínima:** exigir que a vela APÓS o sinal não feche de volta além do
     nível antes de entrar (entra na 2ª vela, não na 1ª). Reduz frequência → risco no prazo de 30
     dias. **Testar no backtest COM Tick Replay** se corta mais facada do que ganho.
- **Risco de overfitting:** MÉDIO pra opção 2 (é um filtro). BAIXO pra opção 1.
- **Como testar:** opção 2 — backtest 13 meses, medir Δ facada vs Δ trades bons perdidos, OOS.

### 🟡 PROBLEMA #3 — Gap de entrada após vela de sinal violenta `[F + B]`

- **Evidência:** 08/07 L14 (fill +10pt), 13/07 L6 (fill +11pt). 2 em 9 dias = −$300. Backtest não
  modela (fill no close).
- **Impacto:** −$150/trade × ~2/mês = −$300/mês.
- **Causa provável:** `OnMarketData` persegue o preço. Ou: entrar em vela de spike violento é
  ruim de qualquer jeito (essas velas são as que mais viram facada).
- **Alteração sugerida:**
  1. **Entrar a mercado no 1º tick após o sinal** (revisar a lógica de entrada do `OnMarketData`).
  2. OU **não operar quando a vela de sinal for um spike** (ex.: range da vela de sinal > 3× o
     ATR, ou L/H a mais de 25pt do nível). Isso mataria os 2 gaps E parte das facadas.
- **Risco de overfitting:** BAIXO pra (1). MÉDIO pra (2).
- **Como testar:** (1) — comparar log de fill vs preço do sinal ao vivo, sem backtest. (2) —
  backtest com filtro de range da vela de sinal, OOS.

### 🔴 PROBLEMA #4 — `pdHigh`/`pdLow` zeram no restart `[A]` — BLOQUEANTE

- **Evidência:** 21/07 e 22/07 mortos ("aguardando 1º dia").
- **Impacto:** dias inteiros sem operar, silenciosamente. Já aconteceu 21/07 (junho tb).
- **Causa:** `pdHigh`/`pdLow` são variáveis de instância sem persistência nem recálculo do
  histórico (item #18).
- **Alteração sugerida:** na inicialização, **recalcular `pdHigh`/`pdLow` varrendo pra trás o
  `Bars`/`BarsArray` já carregado** em vez de depender do acúmulo ao vivo. Mudança só nos `.cs`
  experimentais.
- **Risco de overfitting:** ZERO (é bug).
- **Como testar:** reiniciar a estratégia no meio do Replay e ver se os níveis aparecem na hora.

### 🟡 PROBLEMA #5 — Custos são 63% do prejuízo `[D]`

- **Evidência:** ~$11/trade de custo × 44 = −$484 de −$771.
- **Impacto:** com E[−$17,5], os $11 de custo são a maior parte.
- **Alteração:** 2-3 MNQ em vez de 5 (meta/DD são em $, não escalam — já sabido). Corta custo
  pela metade. **Só depois de resolver o #1** (não adianta reduzir custo de uma estratégia
  perdedora).
- **Risco de overfitting:** ZERO.

### ⚠️ PROBLEMA #6 — Possível overfitting do backtest original `[G]`

- **Evidência:** backtest 13/13 meses verdes, PF 1,03-1,94, "100% de aprovação". Forward test:
  PF 0,44. **Um backtest que nunca perde um mês e a realidade que perde 2 seguidos = o backtest
  não estava medindo a coisa certa** (era `OnBarClose`, ver #1).
- **Impacto:** todas as decisões do projeto foram tomadas contra um backtest otimista.
- **Alteração:** re-validar TUDO com Tick Replay ligado. Se o edge sumir, a estratégia
  precisa ser repensada (não ajustada).

---

## PARTE 6 — PLANO DE MELHORIA (ordem de prioridade)

### Fase 0 — DESTRAVAR e MEDIR A VERDADE (sem mexer na lógica)

1. **Corrigir o `pdHigh`/`pdLow` no restart** (Problema #4). Sem isso o forward test não anda.
   Mudança pequena e sem risco. **Fazer primeiro.**
2. **Ligar Tick Replay no gráfico** e re-rodar o backtest de 13 meses do BETrigger25.
   - Se PF > 1,3 com Tick Replay → o edge é real, o problema é execução pontual (gap de entrada,
     velocidade) → ir pra Fase 1.
   - Se PF 0,4-0,8 com Tick Replay → **o edge histórico era artefato de `OnBarClose`.** A
     estratégia como está não tem edge sob gestão intrabar. Ir pra Fase 2.
3. **Rodar 1-2 dias do forward test a 1x** (velocidade real) e comparar os trailing exits com os
   do 500x. Descarta a velocidade como causa.

### Fase 1 — SE o edge sobreviver ao Tick Replay: corrigir execução

4. **Revisar a lógica de entrada do `OnMarketData`** — entrar a mercado no 1º tick após o sinal
   (Problema #3.1). Sem risco de overfitting.
5. **Sweep de trailing (1,75 / 3 / 5 / 8pt) e BE-lock, NO backtest COM Tick Replay**, escolhendo
   pela estabilidade OOS (Problema #1.2).
6. **Reduzir pra 2-3 MNQ** (Problema #5).
7. Só então retomar o forward test.

### Fase 2 — SE o edge NÃO sobreviver ao Tick Replay

8. A reversão PDH/PDL em MNQ 1min sob gestão intrabar **não tem edge**. As opções viram:
   - **Gestão de saída totalmente diferente** (alvo fixo pequeno + sem trailing; ou parcial +
     runner com trailing largo) — testar com Tick Replay.
   - **Outro timeframe** (2-3min reduz o ruído tick que estrangula o trailing — o backtest antigo
     mostrou 2min PF 1,80 no motor `OnBarClose`; testar com Tick Replay).
   - **Direção B** (já explorada — MES/M2K sem edge, MYM frágil; DD estático é a alavanca de
     formato).
   - **Aceitar que a estratégia é regime-dependente** e só operá-la com sizing pequeno em
     paralelo a várias contas.

### O que NÃO fazer

- ❌ Filtro de horário / dia da semana — perfil ruim de julho é amostra pequena, backtest não
  mostra efeito. Overfitting garantido.
- ❌ Apertar o SL — testado 3x, piora.
- ❌ Loss-cut pra facada — testado (item #16), mata vencedores.
- ❌ Adicionar dezenas de filtros de entrada — a família toda já foi rejeitada.
- ❌ Ajustar qualquer parâmetro olhando só o PnL histórico. Só mudar o que melhora a
  **estabilidade OOS** com Tick Replay ligado.
