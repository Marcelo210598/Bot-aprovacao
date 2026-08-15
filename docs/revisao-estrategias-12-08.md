# 🔍 Revisão geral de estratégia — 12/08/2026

> Motivo: mês 06/2026 fechou incompleto (+$170,5 de $1.500, 12 de 22 pregões zerados).
> Marcelo pediu revisão da estratégia + pesquisa de estratégias novas pra testar num funil.
>
> **Conclusão em uma linha: o problema não era a estratégia. Era o TIMEFRAME do gráfico.**

---

## 🔴 ACHADO PRINCIPAL — o forward test rodou numa config que nunca foi validada

O backtest que aprovou essa estratégia (100% taxa, PF 1.60, $36.978/ano) foi rodado em barras de
**1 minuto**. O forward test de junho rodou num gráfico de **5 minutos** (confirmado nos prints do
NT8: "MNQ SEP26 | 5 minutos").

São estratégias diferentes na prática. Mesma regra, mesma config de risco, só o timeframe mudando:

| Gráfico | trades/dia | WR | PF | ganho médio | PnL/ano | **Aprovação em 30d** | Estouros |
|---|---|---|---|---|---|---|---|
| **1 min** (validado) | 7,3 | 67,4% | 1,64 | 11,0pt | $31.586 | **82%** | **0** |
| 2 min | 4,3 | 64,2% | 1,80 | 13,7pt | $35.134 | — | — |
| 3 min | 3,1 | 57,9% | 1,62 | 16,0pt | $23.548 | — | — |
| **5 min** (junho) | 3,7 | 49,5% | 1,59 | 21,8pt | $19.600 | **54%** | **5** |
| 15 min | 1,0 | 35,2% | 1,33 | 32,6pt | $5.825 | — | — |

**Por que o 5min mata a estratégia:**
1. **Metade dos sinais.** Menos barras = menos oportunidades de "tocou a linha e fechou de volta".
2. **O filtro anti-chase rejeita mais.** Uma barra de 5min percorre muito mais distância antes de
   fechar. O `MaxDistPontos=15pt` foi calibrado pra barra de 1min — em 5min ele barra rejeições
   que seriam válidas. **Isso explica boa parte dos 12 dias zerados de junho.**
3. WR desaba de 67% pra 49%.

**Comparação direta, mesmo período, mesmo mercado** (01/06 → 11/06/2026):
- Backtest em **1min**: **+$1.240** em 6 dias operados
- Forward test ao vivo em **5min**: **+$206**

Seis vezes menos, nos mesmos 11 dias. Não foi azar de mercado — foi o timeframe.

### Robustez OOS do achado

| Config | Total | 1ª metade | 2ª metade |
|---|---|---|---|
| 1min | 82% aprov, **0 bust** | 82%, 0 bust | 74%, **0 bust** |
| 5min | 54% aprov, 5 bust | 70%, 0 bust | **38%, 5 bust** |

O 1min segura nas duas metades e **nunca estoura conta**. O 5min degrada feio no semestre recente.

---

## ⚠️ Expectativa REALISTA (com slippage) — não vender ilusão

Os 82% acima são com slippage ZERO. Com atrito real de MNQ (2 ticks, o padrão que já usamos
desde 23/06):

| Slippage | 1 minuto | 5 minutos |
|---|---|---|
| 0 tick | 82% aprov, 0 bust, $31.586 | 54% aprov, 5 bust, $19.600 |
| 1 tick | 54% aprov, 3 bust, $24.250 | 36% aprov, 9 bust, $14.934 |
| **2 ticks (realista)** | **44% aprov, 4 bust, $18.132** | 26% aprov, 21 bust, $12.514 |
| 3 ticks | 29% aprov, 25 bust, $12.918 | 24% aprov, 22 bust, $10.401 |

**Número honesto pra levar pro ar: ~44% de aprovação por janela de 30 dias no 1min.**
Ou seja: aproximadamente **1 mês a cada 2 aprova**. Não é 100%. Mas é quase o dobro do 5min (26%)
e com 4 estouros/ano em vez de 21.

### PnL mês a mês (1min, sem slippage — teto otimista)

| Mês | PnL | Dias operados | Bateria $1.500? |
|---|---|---|---|
| 2025-06 | $900 | 9 | não |
| 2025-07 | $2.847 | 18 | SIM |
| 2025-08 | $1.788 | 16 | SIM |
| 2025-09 | $1.545 | 6 | não (faltou dia operado) |
| 2025-10 | $1.884 | 12 | SIM |
| 2025-11 | $4.084 | 11 | SIM |
| 2025-12 | $2.442 | 9 | SIM |
| 2026-01 | $3.500 | 16 | SIM |
| 2026-02 | $4.680 | 17 | SIM |
| 2026-03 | $2.206 | 9 | SIM |
| 2026-04 | $3.356 | 14 | SIM |
| 2026-05 | $1.113 | 15 | não |
| 2026-06 | $1.240 | 6 | não (mês parcial no dado) |

**9 de 13 meses** bateriam a meta. E repare nos **dias operados: 9 a 18 por mês** — contra os
**10 dias com apenas 25 trades** de junho no 5min. O problema de "metade do mês sem operar"
some no 1min.

---

## 🧪 FUNIL DE ESTRATÉGIAS NOVAS — todas testadas, todas piores

Pesquisa web (12/08) + backtest próprio no mesmo motor, mesmo custo, mesma métrica de aprovação
Apex. Fontes da pesquisa listadas no fim.

| # | Estratégia | trd/dia | WR | PF | PnL/ano | **Aprovação** | Estouros |
|---|---|---|---|---|---|---|---|
| **A** | **NÍVEIS_FADE 1min (a ATUAL)** | 7,3 | 67,4% | 1,64 | $31.586 | **82%** | **0** |
| A4 | NÍVEIS_FADE 5min (junho) | 3,7 | 49,5% | 1,59 | $19.600 | 54% | 5 |
| F | VWAP reversão (2 desvios) | 4,3 | 33,5% | 0,93 | **-$5.026** | 28% | 102 |
| A3 | NÍVEIS_FADE trail 8pt | 6,6 | 52,5% | 1,14 | $9.062 | 23% | 74 |
| A2 | NÍVEIS_FADE sem trailing | 4,5 | 17,9% | 0,95 | -$3.626 | 20% | 113 |
| B | NÍVEIS_BREAK (o inverso da atual) | 8,9 | 18,7% | 1,01 | $2.856 | 9% | 181 |
| C | ORB 15min | 1,6 | 32,9% | 1,32 | $2.067 | 6% | 6 |
| D | ORB 30min | 1,6 | 28,6% | 1,13 | $415 | 0% | 0 |
| E | Initial Balance breakout (1ª hora) | 1,7 | 20,8% | 0,75 | -$2.380 | 0% | 8 |
| G | Gap fill | — | — | — | — | **não testado** (bug no harness, ver nota) |

### Claims da internet que NÃO se sustentaram

- **"ORB 30min: WR 74,5%, PF 2,51"** (tradealgo.com) → medido: **WR 28,6%, PF 1,13, 0% de
  aprovação**. Não chega nem perto.
- **"ORB 15min: WR 65-78%, 433%/ano"** (pesquisa anterior, 12/08) → medido: **WR 32,9%, PF 1,32**.
- **"Mean reversion NQ: +730%, PF 1,40"** → nossa versão VWAP deu **PF 0,93 (perde dinheiro)** e
  102 estouros de conta.
- **"Gap fill NQ: 68-75% de acerto"** → **não consegui testar** — meu gerador de sinal de gap tinha
  um bug (`ultimo_close` nunca era preenchido) e produziu zero trades. Fica como não-testado, não
  como rejeitado. Se quiser, testo depois.

### O que aprendi testando as variantes da própria estratégia

- **Tirar o trailing de 1,75pt é péssimo** (A2): WR desaba 67%→18%, PF vira 0,95. Minha primeira
  hipótese era que o trailing estava "estrangulando os ganhos" — **estava errado, e o teste provou**.
  O trailing curto é o que sustenta o WR alto. Não mexer.
- **Afrouxar o trailing pra 8pt também piora** (A3): 23% de aprovação, 74 estouros.
- **Inverter a estratégia (romper em vez de reverter) é desastre** (B): 181 estouros.

---

## ✅ RECOMENDAÇÃO

**1. Trocar o gráfico do forward test de 5min para 1min.** É a mudança de maior impacto do projeto
inteiro e não exige tocar em uma linha de código — só mudar o timeframe do gráfico no NT8.
Isso já estava documentado na memória do projeto desde 17/06 ("Gráfico DEVE ser 1min"), mas a
observação era sobre a noturna e se perdeu no caminho pra diurna.

**2. Refazer o mês de junho no 1min antes de decidir qualquer outra coisa.** Se o replay de junho
no 1min render perto dos $1.240 que o backtest indica pros primeiros 11 dias, o diagnóstico está
confirmado na prática e não precisamos de estratégia nova nenhuma.

**3. NÃO adicionar as estratégias novas.** Nenhuma delas aprova conta. O ORB (que eu implementei
mais cedo hoje) fica no repositório como módulo dormente — 6% de aprovação não justifica ligar.

**4. Deixar o `MaxDistPontos=15pt` quieto por enquanto.** Ele foi calibrado pra 1min. Boa parte
dos dias zerados de junho foi ele agindo "certo demais" em barras de 5min. Voltar pro 1min pode
resolver sozinho — só reavaliar depois, com dado novo.

**5. Verificar a regra de bracket da Apex** (achado da pesquisa, precisa confirmar): há relatos de
que desde 2026 a Apex exige ordem bracket (entrada + stop + **alvo**) em toda posição, e que
Tradovate/Rithmic rejeitam ordem sem isso. Nosso bot usa **alvo sintético** (sem `SetProfitTarget`,
proposital pra evitar conflito de OCO). Se a regra for real e valer pra Rithmic/NT8, isso é risco
de compliance. **Não mexi no código por isso — precisa confirmar direto com a Apex antes.**

---

## Fontes da pesquisa (12/08/2026)

- [Does Apex Trader Funding Allow Automated Trading Bots? — QuantVPS](https://www.quantvps.com/blog/apex-trader-funding-automated-trading-bots)
- [How to Pass Apex Trader Funding (2026): Rules, Trailing Drawdown & MNQ Strategy — Falcon AI](https://thefalconai.com/blog/how-to-pass-apex-trader-funding-2026)
- [Apex Trader Funding FAQs (2026) — PickMyTrade](https://pickmytrade.trade/prop-firm-faq/apex-trader-funding-faq/)
- [Futures Trading Strategies: 6 Proven Methods (2026 Data) — TradeAlgo](https://www.tradealgo.com/trading-guides/futures/futures-trading-strategies)
- [MNQ Scalping: The Complete Guide — theforexscalpers](https://theforexscalpers.com/mnq-scalping-complete-guide/)
- [Initial Balance Breakout Strategy for ES & NQ — Trader-Dale](https://www.trader-dale.com/initial-balance-breakout-strategy-for-es-nq-15th-jul-26/)
- [Prop firm trading: data-backed strategies — edgeful](https://www.edgeful.com/blog/posts/prop-firm-trading-data-backed-strategies)

Scripts: `backtest/run_funil_estrategias.py` (funil completo, reproduzível).
