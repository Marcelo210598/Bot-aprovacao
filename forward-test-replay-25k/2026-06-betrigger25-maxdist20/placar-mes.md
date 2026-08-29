# Placar — BE trig 2,5pt + MaxDistPontos 20pt, dias 01-11/06/2026

Comparação contra `../2026-06-betrigger25/` (mesmos dias, só BE trig 2,5, MaxDist ainda 15) e
contra `../2026-06-saidaparcial/` (config atual de produção-candidata, BE trig 3,75) — essas duas
colunas só têm dado até 04/06 (nao rodadas mais pra frente ainda).

| Dia | Trades | Novo (BE2,5+Dist20) | Só BE 2,5 (Dist15) | Config atual (BE3,75) |
|---|---|---|---|---|
| 01/06 | 6 | -$2,0 | -$0,5 | +$74,0 |
| 02/06 | 8 | +$44,0 | +$44,0 | +$199,0 |
| 03/06 | 7 | +$83,0 | +$83,0 | +$287,0 |
| 04/06 | 5 | -$81,5 | -$81,5 | -$127,5 |
| 05/06 | 0 | $0,0 | — | — |
| 08/06 | 5 | -$9,5 | — | — |
| 09/06 | 3 | +$80,0 | — | — |
| 10/06 | 0 | $0,0 | — | — |
| 11/06 | 6 | -$76,0 | — | — |
| **Total (9 dias)** | **40** | **+$38,0** | — | — |

*(sub-total 01-04/06, único trecho com as 3 colunas comparáveis: **+$43,5**)*

## ✅ Confirmado: Marcelo está certo, quase nenhum trade a mais nesses 4 dias

Comparei entrada por entrada com o teste anterior (só BE trig 2,5). **Só 1 trade extra em 4 dias**
(28 toques totais nos dois testes juntos): `NIV_L11` no dia 01/06, distância 17,00pt — um toque
que caiu exatamente na faixa 15-20pt que só o MaxDist novo libera. Todo o resto (25 trades) é
**idêntico, ponto a ponto**, entre as duas configs.

**Isso não é um problema no parâmetro — é o que o backtest já sugeria, só a escala é que engana.**
O backtest mostrou tentativas subindo de 22 para 25 no ano inteiro (13 meses) — ou seja, a
mudança adiciona uns **3 sinais extras no ano inteiro inteiro**, não 3 por semana. É uma alavanca
rara, cujo valor está nos poucos casos em que dispara (como esse `NIV_L11` de hoje, +$21,5), não
em gerar volume constante de trades novos. Não é sinal de que o parâmetro "não está funcionando"
— é o comportamento esperado de um filtro que só afeta a cauda da distribuição (toques entre 15 e
20pt da linha, que são raros por definição).

## 📋 Resultado líquido dos 4 dias

O `MaxDistPontos=20` não mudou o resultado de forma perceptível nesses 4 dias específicos (+$43,5
vs +$45,0, diferença de $1,5, só por causa do 1 trade extra). O padrão de junho ser um mês
historicamente ruim pro **BE trig 2,5** (ver `../2026-06-betrigger25/placar-mes.md`) continua
sendo o fator dominante — segue valendo continuar o forward test passando de junho pra frente.

## 📆 Dias 05-11/06 (sem comparação de 3 colunas — só essa config foi rodada)

05/06 e 10/06 sem entradas. 08/06 fechou -$9,5 (5 trades, stop cheio no NIV_S7 apagou os 2
primeiros ganhos). 09/06 foi o melhor dia da leva: +$80,0, 3 trades, 100% ganhador. 11/06 voltou a
ficar negativo (-$76,0, 6 trades) — um stop cheio feio no último trade do dia (NIV_S31, -$105)
comeu o saldo positivo dos 4 trades anteriores.

Saldo 05-11/06: -$5,5 (5 dias, 14 trades). Somado ao sub-total de 01-04/06 (+$43,5), o acumulado
dos 9 dias registrados até agora fecha em **+$38,0**. Ainda cedo pra tirar conclusão — a amostra
segue pequena e junho já é conhecidamente ruim pra essa config (ver acima).
