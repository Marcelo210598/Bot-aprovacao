# Mesas alternativas à Apex (pesquisa 03/09/2026)

> Fontes: guias de terceiros (proptradingvibes, quantcrawler, damnpropfirms, tradetanto,
> crosstrade, pickmytrade, Tradeify help center). **Confirmar tudo na fonte oficial de cada mesa
> ANTES de comprar** — todas mudam regra o tempo todo, e a maioria "reestruturou" nos últimos 12 meses.

## O que a gente precisa (do projeto)
1. **Automação 100% hands-off permitida na conta FUNDED** (não só na avaliação)
2. **Drawdown estático** (achado 01/09: DD trailing = a trava; estático levou aprovação sim de ~31%→~60%)
3. Tolerância a **grind de ganhos pequenos diários** (regra de consistência não atrapalha um bot que faz dias parelhos)
4. **NinjaTrader 8** (via Rithmic ou Tradovate)
5. Preço e payout razoáveis

## Tier de qualidade (mesas sérias, com histórico e payout real)
**Topstep · Take Profit Trader · MyFundedFutures · Tradeify · TradeDay · Bulenox · Alpha Futures · Apex.**
Fora desse grupo = mesa de risco (regra abusiva, payout que trava, some do mercado). Não considerar.

> ⚠️ Praticamente todas hoje (Apex incluída) são **"sim funded"**: você opera uma conta funded
> *simulada* e o pagamento sai do caixa de marketing da firma, não de P&L real de mercado. É o
> modelo do setor inteiro em 2026.

## Comparação — foco em bot + DD estático

| Mesa | Bot 100% auto na FUNDED? | Drawdown | Consistência (funded) | Payout | Observações |
|---|---|---|---|---|---|
| **Tradeify** | ✅ **Sim, eval e funded** | trailing EOD que **trava estático** após funding | Lightning: progressiva **20%→25%→30%** (1º/2º/3º saque) | — | 🔶 regra: **≥50% dos trades e do lucro em trades segurados >10s** (mata HFT/scalp de tick; grind M5 ok). Strategy tem que ser **só sua**, não pode repetir em outra firma. Paths: Growth/Select (com eval) e Lightning (funded no dia 1, DD mais apertado). |
| **Bulenox** | ✅ **Sim, todos os tipos** (EA, copier, automação) — "política mais limpa do mercado" | Opção 1: trailing real-time / Opção 2: **EOD + scaling + daily loss limit** | **40%** no Master | Master: 100% dos 1os $10k, depois 90/10, **quarta-feira semanal**, mín **10 dias** operados; 1os 3 saques capados; depois vira Funded "real" | HFT proibido. $25K–250K. Rithmic/Tradovate. |
| **MyFundedFutures** | 🔶 **Não documentado claro pra funded** — confirmar | Rapid: intraday trail que trava / **Rapid EOD** / **Pro: EOD MLL** / Builder: buffer fixo | **Rapid e Pro = SEM regra de consistência no funded** ✅✅ / Builder = 50% | Rapid: **saque diário**, mín $500, 90/10 / Pro: 14 dias, mín $1.000, 80/20, teto $100k/usuário | "SEM consistência no funded" é o grande atrativo pra grind. Mas a política de automação na funded é o ponto a bater com o suporte. |
| **TradeDay** | 🔶 permite automação **sem submeter a strategy pra review** — confirmar se vale na funded | 3 tipos de DD nos SKUs | **eval-only 30%** (nenhuma no funded, aparentemente) | assinatura mensal | **NT8 nativo** (+ Tradovate, TradingView, Jigsaw). |
| **Take Profit Trader** | 🔶 "automação via API Tradovate, verifique antes de deployar" | trailing EOD que pode travar | tem regra | — | Menos clara sobre bot hands-off. |
| **Topstep (TopstepX)** | 🔶 API via ProjectX, mas **regras de consistência + risco valem no combine E no funded** | trailing | sim, no funded | — | HFT e latency-arb proibidos. Mais restritiva pra bot. |
| **Apex** (atual) | 🔴 **fontes conflitam** (várias: só na avaliação; PA exige trader presente) | Intraday trailing OU EOD (4.0) | **50%** (era 30%) | automático, máx 6 saques | Ver `docs/apex-regras-4.0-2026-09.md`. |

## Leitura / recomendação

### Trocar de mesa faz sentido? **Sim — SE o objetivo é bot 100% automatizado.**
O projeto já concluiu (01/09) que o **formato do DD** (trailing + relógio de 30 dias) é a trava, não
a estratégia. E a política de automação da Apex na conta funded é ambígua no melhor caso, proibitiva
no pior — não dá pra construir um bot pra conta funded e correr o risco de confisco por "automação
hands-off".

### MAS: trocar de mesa NÃO resolve o problema de fundo
~14 famílias de estratégia mecânica testadas no projeto, **nenhuma passa fora de amostra.** DD
estático faz um edge marginal **sobreviver**, não **cria** edge. Se PF < 1,0 OOS, nenhuma mesa
salva. **Escolher mesa é o passo 2** — o passo 1 é ter uma estratégia com edge real (mesmo pequeno)
no novo enquadramento de "grind".

### Sobre a regra de consistência
Um bot de grind que faz ~$100-200/dia de forma parelha é o **melhor caso possível** pra regra de
consistência — não tem dia grande que quebre os 30-50%. Consistência **não é o gargalo pra gente**.
O gargalo é: (a) política de automação e (b) ter edge de verdade.

### Shortlist pra investigar (ordem)
1. **MyFundedFutures (Rapid ou Pro)** — *sem* regra de consistência no funded + DD EOD/estático +
   saque frequente. **Bater com o suporte: bot 100% hands-off vale na conta funded?**
2. **Tradeify (Growth ou Lightning)** — bot explicitamente OK na funded, DD trava estático,
   estabelecida. Atenção à regra dos **>10s de holding** (não é problema pra M5) e à consistência
   progressiva 20-30%.
3. **Bulenox** — política de bot mais limpa do mercado, opção EOD + scaling. Atenção: 40%
   consistência, saques capados no começo, 10 dias mínimos.
4. **TradeDay** — NT8 nativo, sem review de strategy. Confirmar regra de automação/consistência na funded.

### Perguntas idênticas pra fazer no suporte de cada uma
- Bot 100% automatizado, sem humano presente, vale na conta **funded** (não só eval)?
- Precisa registrar/submeter a estratégia?
- Definição de HFT deles (holding mínimo, trades/min)?
- DD é **estático de verdade** na funded, ou "EOD trailing que trava" (e trava quando)?
- Consistência na funded: % e como calcula?
- Preço da conta ~$25-50K + taxa de ativação + custo mensal?

## Fontes
- https://pickmytrade.io/faq/prop-firm-automation
- https://finseeds.com/firms/futures-prop-firms-that-allow-automation/
- https://damnpropfirms.com/best-prop-firms-for-algo-trading/
- https://help.tradeify.co/en/articles/10495938-lightning-funded-accounts
- https://proptradingvibes.com/blog/tradeify-rules
- https://proptradingvibes.com/blog/myfundedfutures-payout-rules
- https://proptradingvibes.com/prop-firms/bulenox
- https://tradetanto.com/learn/bulenox-rules-what-traders-need-to-know
- https://crosstrade.io/prop-funding
- https://quantcrawler.com/learn/bulenox-review
