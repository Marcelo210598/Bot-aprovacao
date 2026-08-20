# 📊 Comparativo de estratégias — sozinhas e mescladas (20/08/2026)

> Script: `backtest/run_estrategias_comparativo.py`. Motor: mesma gestão de saída da
> reversão (SL 12,5 / BE 3,75→2,5 fixo / trailing 1,75 / alvo 60pt), DD real $1.000,
> MaxTradesDia=12 (compartilhado entre fontes ativas), stop diário $750, slippage 2
> ticks, 5 MNQ. 300.174 barras de 1min, ano inteiro (jun/2025-jun/2026) + OOS 1ª/2ª metade.

## ⚠️ Leia antes dos números

Pra comparar maçã com maçã, todas as 4 estratégias usam a **mesma gestão de risco da
reversão** (SL/TP/trailing calibrados pra ela). Isso **não é** o teste "ideal" pra
ORB/EMAV/ICT — cada uma tradicionalmente usa outro perfil (o ORB já validado em
`run_orb_15min.py` usa SL 10pt/TP 2:1 próprio, +$2.766/ano). Aqui o objetivo era
isolar "o sinal de entrada sozinho é melhor que a reversão?", não validar a versão
ótima de cada estratégia.

**Definições usadas** (mecânicas, documentadas no código):
- **REV**: reversão PDH/PDL — o que já roda em produção.
- **ORB**: rompimento do range 9h30-9h45 ET com fechamento fora do range.
- **EMAV**: Close vs VWAP diário + EMA9>20>50 alinhadas + RSI14 cruzando a linha 50.
- **ICT**: "ICT-lite" — Fair Value Gap (gap de 3 candles) + retorno ao gap com
  fechamento de rejeição (continuação). Versão simplificada, não é o ICT ortodoxo.

## 1. Sozinhas

| Estratégia | Taxa aprovação | Aprov | PF | Trades | PnL$/ano | OOS 1ª\|2ª |
|---|---|---|---|---|---|---|
| **REV (atual)** | **70%** | 14/20 | 1,41 | 1.166 | 21.562 | 62%\|75% (estável) |
| ORB | 41% | 18/44 | 1,19 | 2.561 | 26.314 | 60%\|28% (instável) |
| EMAV | 23% | 7/30 | 1,03 | 1.682 | 2.118 | 0%\|41% (péssima) |
| ICT | 42% | 16/38 | 1,28 | 2.554 | 36.658 | 62%\|27% (instável) |

## 2. Mescladas com a reversão

| Combo | Taxa | PF | PnL$ | Distribuição de trades |
|---|---|---|---|---|
| REV sozinha | 70% | 1,41 | 21.562 | REV:1166 |
| REV+ORB | 43% | 1,22 | 31.292 | ORB:2272 + REV:294 |
| REV+EMAV | 33% | 1,18 | 18.812 | EMAV:1296 + REV:892 |
| REV+ICT | 42% | 1,30 | 40.399 | ICT:2126 + REV:415 |
| REV+ORB+EMAV | 33% | 1,19 | 27.192 | mistura |
| REV+ORB+EMAV+ICT | 32% | 1,18 | 27.230 | mistura |

## 3. Mescladas sem a reversão

| Combo | Taxa | PF | PnL$ |
|---|---|---|---|
| ORB+EMAV | 34% | 1,18 | 26.744 |
| ORB+ICT | 32% | 1,19 | 27.300 |
| EMAV+ICT | 43% | 1,30 | 39.582 |
| ORB+EMAV+ICT | 33% | 1,18 | 26.996 |

## Leitura

**Nenhuma estratégia nova, sozinha ou mesclada, supera a reversão sozinha na métrica
que importa (taxa de aprovação).** Todas geram MAIS PnL bruto (mais trades = mais
volume), mas isso é enganoso — mais trades com o mesmo DD fixo de $1.000 significa
mais variância, e a taxa de aprovação despenca em todas (23-43% vs 70% da reversão).

**Pior ainda: mesclar com a reversão PIORA a reversão.** Como `MaxTradesDia=12` é
compartilhado, e ORB/EMAV/ICT disparam sinal com muito mais frequência que a
reversão, elas "engolem" o espaço de trades do dia antes da reversão ter chance de
entrar (REV cai de 1166 trades sozinha pra só 294-892 nas mesclas). O resultado
combinado nunca chega perto dos 70% da reversão pura.

**Instabilidade OOS é o segundo problema:** ORB e ICT parecem bons olhando o ano
inteiro (41-42%), mas a taxa desaba na 2ª metade (28% e 27%) — não é um edge estável,
pode ser sorte de período. EMAV é ruim nas duas metades (não tem edge real nesse
teste). Só a reversão se mantém estável nas duas metades (62%\|75%).

## Conclusão

Com a MESMA gestão de risco, a reversão PDH/PDL continua sendo a melhor opção, de
longe — nada testado hoje (sozinho ou mesclado) chega perto. Isso não invalida
ORB/ICT como conceitos (o ORB com risco PRÓPRIO já validado é +$2.766/ano, positivo),
mas confirma que forçar o molde de risco da reversão em cima de sinais diferentes
não funciona — cada estratégia precisaria da sua própria calibração de SL/TP/trailing
pra ter uma chance justa, o que é um projetoà parte, não uma tarde de teste.

**Próximo passo, se quiser continuar essa linha:** escolher UMA candidata (ICT teve o
maior PnL bruto sozinha, mas instável OOS — vale investigar se um filtro de tendência
HTF, já cogitado na pesquisa original, estabiliza isso) e dar a ela uma gestão de
risco própria, testada do zero, em vez de emprestar a da reversão.
