# 🤖 Robô Aprova Conta — Estratégia "Níveis" (94% de aprovação)

> **Resumo para decisão.** Conta Apex de 25K. Baseado em backtest com 1 ano de dados reais do NQ (Nasdaq futuros).

---

## 🎯 Em uma frase

O robô opera o **NQ** na conta de **25K**, apostando na **volta do preço** quando ele bate nos pontos de máxima/mínima do dia anterior — com **proteção de lucro automática** e **disciplina rígida** pra não operar demais. Resultado: **aprovou 15 de 16 contas (94%)** no último ano.

---

## 📥 COMO ENTRA (o gatilho)

O robô marca a **máxima** e a **mínima do dia anterior** (os pontos mais alto e mais baixo de ontem). São zonas onde o mercado costuma "bater e voltar".

- Preço de hoje **sobe e bate na máxima de ontem** → e dá sinal de recuo → **VENDE** (aposta na queda)
- Preço de hoje **cai e bate na mínima de ontem** → e dá sinal de recuo → **COMPRA** (aposta na alta)

É uma estratégia de **reversão**: aposta que o preço vai voltar depois de bater no nível.

---

## 📤 COMO SAI (a parte inteligente)

Cada operação nasce com 2 ordens automáticas:

| Ordem | Valor | O que é |
|-------|-------|---------|
| **Alvo de lucro (TP)** | **+$500** | Onde fecha ganhando (teto) |
| **Limite de perda (SL)** | **−$250** | Onde fecha perdendo (piso) |

**Mas o robô protege o lucro automaticamente:**

1. **Trava de segurança (breakeven):** assim que a operação anda **+$75 a favor**, o limite de perda sobe pro positivo (+$50). A partir daí, **a operação não pode mais virar prejuízo**.
2. **Acompanhamento de lucro (trailing $35):** conforme o lucro cresce, o robô "persegue" o preço. Se o mercado **perde força e recua $35**, ele **fecha garantindo o lucro acumulado** — em vez de esperar e ver virar perda.

👉 É o "**garante o lucro quando vê que está perdendo força**".

---

## 🚦 DISCIPLINA (o que levou aos 94%)

Sem disciplina, o robô operava ~5 vezes por dia e estourava o limite da conta. Com 3 regras simples, a reprovação caiu de 15 pra 1:

1. **Máximo 3 operações por dia** — evita o "operar demais" (causa #1 de reprovação em mesa)
2. **Stop diário de $750** — se perder isso num dia, para e volta amanhã
3. **Respeita os 7 dias mínimos** que a Apex exige

---

## 💵 OS NÚMEROS POR OPERAÇÃO

| | Valor |
|--|--|
| **Quanto buscamos** | até **$500** (média real: **$258**, porque o trailing fecha antes) |
| **Quanto arriscamos** | **$250** (perda média real: **$255**) |
| **Taxa de acerto** | **62%** (acerta 6 em cada 10) |
| **Lucro médio por operação** | **+$61** |
| **Operações por dia** | ~2 |

> 💡 Por que dá lucro mesmo ganhando quase o mesmo que perde? Porque **acerta 62% das vezes**. Ganhar ~$258 em 62% e perder ~$255 em 38% = lucro consistente.

---

## 📊 RESULTADO (1 ano real, conta 25K)

| Métrica | Resultado |
|---------|-----------|
| **Contas APROVADAS** | **15** ✅ |
| **Contas REPROVADAS** | **1** ❌ |
| **Taxa de aprovação** | **94%** |
| **Retorno no ano** | **+$25.615** |
| Tempo médio pra aprovar 1 conta | ~23 dias |
| Profit Factor | 1.62 (ganha $1,62 pra cada $1 perdido) |

### É confiável? (teste anti-sorte)
Dividimos o ano em 2 metades independentes e testamos em cada uma:
- **1ª metade:** 7 de 7 aprovadas (**100%**)
- **2ª metade:** 8 de 9 aprovadas (**89%**)

→ Funciona nos dois períodos. **Não é sorte de um momento específico do mercado.**

---

## ✅ POR QUE FUNCIONA (resumo)

1. **Acerta muito** (62%) — entra em zonas de reversão de alta probabilidade
2. **Protege o lucro** — o trailing transforma quase-perdas em pequenos ganhos
3. **Não exagera** — limite de 3 operações/dia evita estourar o limite apertado da 25K

---

## ⚖️ O QUE PRECISA SER DITO (honestidade)

- É um **backtest** (simulação com dados reais), **não** operação ao vivo ainda. O próximo passo é rodar no simulador do NinjaTrader pra confirmar.
- Baseado em **~10,5 meses** de dados (1 contrato NQ, candle de 1 minuto).
- Custos de corretora estimados (~$5 por operação) — confirmar com a corretora real.
- **94% é a taxa histórica desse período, não uma garantia.** O cliente ainda pode reprovar 1 vez antes de passar.
- A maior sequência de perdas foi **7 operações seguidas** — a disciplina diária (stop $750 + máx 3/dia) foi o que impediu isso de virar reprovação.

---

## 🎛️ FICHA TÉCNICA (parâmetros exatos)

```
Mercado:         NQ (Nasdaq futuros) — 1 contrato
Conta:           Apex 25K (meta $1.500 | limite de perda $1.500 | mín. 7 dias)
Estratégia:      Reversão na máxima/mínima do dia anterior
Alvo (TP):       $500   (25 pontos)
Stop (SL):       $250   (12,5 pontos)
Breakeven:       +$75   → trava o stop em +$50
Trailing:        $35    (acompanha o lucro)
Máx operações/dia: 3
Stop diário:     $750
Horário:         pregão regular EUA — entradas das 9h30 às 15h00 ET
                 (~10h30 às 16h00 BRT no horário de verão americano);
                 fecha tudo antes do fim do pregão (15h55 ET)
```
