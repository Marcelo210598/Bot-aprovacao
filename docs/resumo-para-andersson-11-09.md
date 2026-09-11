# AberturaNYSpecAndersson — resumo pra enviar ao Andersson (11/09/2026)

## 1. Configuração do bot (exatamente como pediu)

| Parâmetro | Valor | O que faz |
|---|---|---|
| **Contratos** | 6 | Tamanho da posição (MNQ) |
| **Horário de abertura** | 09:30 ET (~10:30 Brasília, horário de verão americano) | Referência: preço do 1º print a partir desse horário |
| **Janela de monitoramento** | 60 segundos | Só monitora o gatilho no 1º minuto após a abertura — depois disso, se não disparou, não entra mais naquele dia |
| **Gatilho de entrada** | 10 ticks | Quando o preço anda 10 ticks pra cima ou pra baixo a partir do preço de abertura, entra na hora (a mercado), na direção do movimento — não espera a vela fechar, é em tempo real |
| **Stop Loss** | $250 (na posição) | Perda máxima antes de qualquer proteção entrar |
| **Take Profit** | $500 (na posição) | Alvo fixo — se bater, sai com lucro travado |
| **Break-Even — Ativação** | $100 de lucro | Quando o lucro flutuante bate $100, o stop se move pra $0 (perde o risco inicial) |
| **Break-Even — Proteção inicial** | $0 (breakeven exato) | Nível que o stop trava na 1ª ativação |
| **Break-Even — Incremento** | $50 | A CADA $50 a mais de lucro (além dos $100 iniciais), o stop sobe mais $50 — sempre só pra cima, nunca desce (ratchet). Ex: lucro chega a $150 → stop vai pra $50 travado; lucro chega a $200 → stop vai pra $100 travado; e assim por diante |
| **1 entrada por dia** | — | Depois de entrar (ganhando ou perdendo), não entra de novo na mesma abertura |
| **Fechamento de segurança** | 15:55 ET | Fecha qualquer posição aberta no fim da sessão |

**Resumo em uma frase:** o bot espera o preço andar 10 ticks no 1º minuto da abertura de NY, entra na direção desse movimento, arrisca até $250, mira $500, e vai travando lucro em degraus de $50 conforme o trade for bem (a partir de $100 de lucro).

## 2. Resumo dos testes (Market Replay, tick-a-tick, MNQ, dado real)

**Junho/2026 — 22 dias operados**
- 11 vitórias / 11 derrotas (50%)
- Resultado do mês: **−$73,50**
- Pico durante o mês: +$714,50 (dia 09/06)
- Pior drawdown do mês: $908,00 (dia 25/06, 90,8% do limite de $1.000)
- Não bateu a meta de $1.500, mas também não estourou o limite de risco (isolado)

**Julho/2026 — 23 dias operados**
- 6 vitórias / 17 derrotas (26%)
- Resultado do mês: **−$267,00**
- Pico durante o mês: +$384,00 (dia 06/07)
- Pior drawdown do mês: $758,50 (dia 16/07)
- Não bateu a meta, não estourou (isolado)

**Total: 45 dias reais, 17W/28L (37,8%), resultado −$340,50.**

**⚠️ Achado mais importante:** olhando os dois meses como uma conta contínua (sem resetar a
cada mês, como seria numa conta de verdade), o drawdown real do pico (dia 09/06) até o fundo
(dia 16/07) foi de **$1.162,50 — isso estouraria o limite de $1.000 de uma conta EOD real.**
Fechado por meses separados isso ficou escondido.

**O que funciona bem:** o BE progressivo. Nos trades que não batem o stop cheio (53% deles),
a média é **+$84,81/trade** — o mecanismo de proteção de lucro cumpre o que promete.

**O que não funciona:** os 27% de trades que batem o stop cheio custam em média **−$198/trade**,
e alguns tiveram slippage bem pior que o nominal $250 (chegou a −$372,50, 49% a mais) — porque o
stop é monitorado tick a tick e dispara uma ordem a mercado, que em spikes rápidos (justamente
onde essa estratégia entra) pode encher longe do nível calculado.

## 3. Minhas sugestões

1. **Não mexer em stop/alvo/BE ainda** — não temos evidência de que apertar ou alargar esses
   números resolve algo; os dados mostram que o problema está mais em COMO o stop enche do que
   em ONDE ele está.

2. **Testar trocar o stop sintético por ordem nativa do NT8** (`ExitLongStopMarket`, do jeito
   que os 2 arquivos originais do Andersson já fazem) em vez do monitoramento tick a tick que
   esse `.cs` usa hoje — é a mudança com justificativa técnica mais clara pra reduzir o slippage
   nos stops cheios, sem mexer em nenhum parâmetro que dependa de olhar o resultado passado.

3. **Não filtrar por dia da semana nem por direção (compra/venda)** — os dados dão alguma
   diferença aparente, mas a amostra (9 trades por dia da semana, ~22 por direção) é pequena
   demais pra confiar; risco real de estar ajustando ao passado (overfitting) em vez de achar
   um padrão de mercado de verdade.

4. **Veredito honesto até aqui:** não é uma estratégia pronta pra conta real — não bateu a meta
   em nenhum dos 2 meses e o drawdown contínuo estouraria o limite. Mas também não é pra
   descartar — o mecanismo de proteção de lucro (BE progressivo) mostrou um sinal real e
   consistente. Vale testar o ajuste do item 2 antes de decidir se segue ou não.
