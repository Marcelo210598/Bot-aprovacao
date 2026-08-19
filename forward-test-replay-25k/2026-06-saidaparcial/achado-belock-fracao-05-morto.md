# Achado — BE-lock proporcional com fração 0,5 é matematicamente inerte

**19/08/2026** — Replay dos dias 01, 02, 03 e 04/06 rodado de novo com
`UsarBELockProporcional=true` / `BELockFracaoMFE=0,5`.

## Resultado

**Trade a trade, PnL real idêntico ao registrado antes** (baseline `BotAprovacao` original E
à primeira rodada da `SaidaParcial` sem o BE-lock proporcional):

| Dia | PnL (todas as 3 versões) | Trades |
|---|---|---|
| 01/06 | +$101,5 | 6 (5G/1L) |
| 02/06 | +$164,5 | 8 (7G/1L) |
| 03/06 | +$243,0 | 7 (7G/0L) |
| 04/06 | -$131,5 | 5 (3G/2L) |
| **Acumulado** | **+$377,5** | **26 (22G/4L)** |

(Os nomes dos sinais mudaram — ex. `NIV_L9`→segue igual, mas `NIV_S15`→`NIV_S16` em diante —
porque o contador interno incrementa a cada recálculo `[HIST]` do NT8 entre sessões. Isso é só
numeração de log, não afeta os trades reais nem o PnL.)

## Causa raiz (não foi coincidência nos 26 trades — é garantido matematicamente)

A trava proporcional só vence o trailing quando:

```
fracao * MFE  >  MFE - TrailingPontos
```

Isolando a fração: só vence quando `MFE < TrailingPontos / (1 - fracao)`.

Com `fracao = 0,5` e `TrailingPontos = 1,75`: só venceria com **MFE < 3,5pt**.

Mas o breakeven (e portanto a trava) só liga quando **MFE ≥ BreakevenTrigPontos = 3,75pt**.

**3,75 > 3,5 → a trava proporcional nasce sempre mais frouxa que o trailing, em TODO trade,
sempre.** Não existe cenário (nenhum dado de mercado, nenhum número de dias de replay) em que
ela vencesse com esses parâmetros. O trailing sempre dominava desde o primeiro tick pós-BE.

**Condição geral para a trava ter qualquer chance de valer algo:**

```
fracao > 1 - (TrailingPontos / BreakevenTrigPontos)
```

Com a config padrão (Trailing 1,75 / BE gatilho 3,75): `fracao > 0,5333...`

## Fix aplicado (19/08)

`BELockFracaoMFE` alterado de **0,5 → 0,75** no `BotAprovacao_SaidaParcial.cs` (commit
seguinte a este arquivo). Com 0,75, a trava domina o trailing para qualquer trade com MFE
entre 3,75pt e 7,0pt — faixa onde caiu a maioria dos MFEs reais observados nos 4 dias já
testados (4,1 a 9,1pt). Agora sim o experimento pode gerar resultado diferente do baseline.

## Próximo passo

Rodar os mesmos dias 01-04/06 de novo com a fração corrigida (0,75) e comparar. Se ainda
assim não houver diferença (pouco provável dado o cálculo acima, mas possível se o MFE real
ficar concentrado abaixo de 3,75pt — ou seja, quase nenhum trade chegando a acionar o BE),
subir a fração mais ainda ou reconsiderar a abordagem.
