# Apex Trader Funding — regras (pesquisa 03/09/2026)

> Fontes: guias de terceiros (traderssecondbrain, quantvps, tradetanto, satotrades, damnpropfirms,
> propfirmsfinder). **`apextraderfunding.com` bloqueou o fetch (403)** — os números abaixo precisam
> ser **confirmados por você no help center logado** ou com o suporte. Onde as fontes divergem, está marcado 🔶.

## 🔄 Mudança grande: Apex 4.0 (vigente desde 01/03/2026)
| Item | Antes (3.0 / legacy) | Agora (4.0) |
|---|---|---|
| Regra de consistência | 30% | **50%** |
| Dias qualificados p/ saque | 8 (ou 7) | **5** |
| Modelo de drawdown | só Intraday trailing | **Intraday trailing OU EOD** (escolhe na compra) |
| Processamento de saque | manual | automático (botão libera sozinho quando cumpre tudo) |
| Nº de saques por PA | — | **6, depois a PA fecha** |

## Conta 25K — números (🔶 confirmar)
### Avaliação
- Meta de lucro: **$1.500**
- Trailing drawdown: **$1.000**
- Contratos: **4 full / 2 half** (micros ×10 → 40 / 20). **5 MNQ cabe no half-size.**
- Prazo: **30 dias corridos**, compra única
- Automação: **permitida na avaliação** (consenso das fontes)

### PA (funded)
- **Safety net (nível onde o trailing trava): $26.100** (= 25.000 + 1.000 + 100)
- Só lucro **acima de $26.100** é sacável
- **Dia qualificado = fechar o dia com ≥ $100 de lucro** (25K, tanto EOD quanto Intraday)
- Precisa de **5 dias qualificados** (não consecutivos) antes de pedir saque → cadência semanal possível
- **Saque mínimo: $500**
- Contratos na PA começam reduzidos e destravam por faixa de lucro acumulado

## Regra de consistência 50% (4.0)
Nenhum **dia lucrativo** pode representar **≥ 50%** do lucro líquido total desde o último saque aprovado.
- Ex.: melhor dia = $1.500 → lucro líquido tem que ser ≥ $3.000 pra poder sacar.
- Só conta dias positivos; dias de loss não entram no cálculo.
- Reseta a cada saque aprovado.
- **Isso é mais folgado que a regra de 30% que o projeto assumia até 02/09.**

## Intraday trailing vs EOD (escolha na compra da conta)
- **Intraday:** o piso do drawdown sobe seguindo o **pico do equity não-realizado** durante o pregão. Spike de lucro não-realizado move o piso mesmo que você feche no zero. Mais punitivo.
- **EOD:** o piso só re-ancora no **fechamento do dia**. Perdoa swing intradiário grande. Tem **Daily Loss Limit** por faixa.
- Ambos travam no safety net.
- 🔶 Para um bot de grind, **EOD provавelmente é melhor** (não pune a oscilação intradiária) — validar.

## Regras de trading que afetam o bot
- **Direcional apenas:** não pode ter long e short ao mesmo tempo no mesmo instrumento ou em correlatos, **nem entre contas diferentes**.
- **Notícia:** pode operar, mas **não pode "cercar" os dois lados** apostando no resultado. 🔶 uma fonte diz "não operar durante eventos econômicos grandes salvo se o bot evita esses períodos".
- **DCA:** permitido, se respeitar o drawdown e aplicar de forma consistente.
- **Copy trading:** só entre **suas próprias** contas. De/para conta de terceiro = proibido.
- **HFT e certas arbitragens: proibidos.**
- **Stop-loss obrigatório.**

## 🔴 A GRANDE DÚVIDA — automação na conta PA (funded)
As fontes **conflitam**:
- **Versão restritiva** (quantvps "PA account rules", pickmytrade, sentinel): _"Fully automated, hands-off trading or continuous 24-hour systems are not allowed. Traders must remain actively involved."_ / _"Automation is allowed during the Apex EVALUATION only. It is BANNED on funded Performance Accounts."_ / _"fully automated trading is prohibited on PA and Live accounts."_
- **Versão permissiva** (quantvps "automated trading bots", lunefi): _"Apex allows automated trading bots"_ incluindo EAs, ATM strategies, DCA bots, algo em NinjaTrader — com stop/TP, monitoramento em tempo real, kill switch, log.
- **Ponto comum:** o que claramente vale é **semi-automático com o trader presente e monitorando ativamente**. Bot 100% hands-off que entra e sai sozinho sem humano = zona proibida/cinza na PA.

**Isso é decisivo pro projeto.** A nova direção ("bot pra operar a conta funded") só faz sentido se automação for permitida na PA. Se for só "semi-auto com humano presente", o desenho muda (bot dá sinal / gerencia, Marcelo supervisiona e pode ter que clicar).

### Ação obrigatória antes de seguir
**Marcelo confirmar na fonte oficial** (help center logado ou ticket no suporte Apex):
1. Bot 100% automatizado é permitido numa conta **PA/funded**? Ou só semi-auto com trader presente?
2. Precisa de presença humana durante o pregão?
3. HFT — qual a definição/limite deles (trades/min, holding time)?
4. Intraday vs EOD — qual escolher pra um bot de ganhos pequenos diários.

> Lembrete: o projeto já errou antes afirmando regra da Apex sem confirmar (memória `feedback_apex_sem_avaliacoes_paralelas`). Não repetir — confirmar no oficial.

## Firmas alternativas de DD estático (já mapeadas no projeto)
Tradeify, MyFundedFutures, TPT. Se a Apex travar automação na PA, **checar a política de bot de cada uma dessas** — o projeto já concluiu (01/09) que o DD estático é a alavanca real, não a estratégia.

## Fontes
- https://traderssecondbrain.com/guides/apex-payout-rules-explained
- https://www.quantvps.com/blog/apex-pa-account-rules
- https://www.quantvps.com/blog/apex-trader-funding-automated-trading-bots
- https://tradetanto.com/learn/apex-trader-funding-rules-what-you-need-to-know
- https://satotrades.com/guides/apex-payout-rules
- https://damnpropfirms.com/trading-guides/apex-trader-funding-50-percent-consistency-rule-how-to-beat/
- https://propfirmsfinder.com/prop-firm/apex-trader-funding/payouts/
- https://blog.traderspost.io/article/apex-trader-funding-payout-rules-what-prop-traders-must-know
- Oficial (não acessível via fetch, 403): apextraderfunding.com/help-center/
