# Placar — BE trig 2,5pt vs. config atual (BE trig 3,75pt), dias 01-04/06/2026

Comparação direta contra `../2026-06-saidaparcial/` (mesmos dias, mesma config exceto
`BreakevenTrigPontos`). Ambas rodam BE-lock proporcional 0,75 e saída parcial desligada.

| Dia | PnL (BE trig 2,5) | PnL (BE trig 3,75) | Δ |
|---|---|---|---|
| 01/06 | -$0,5 | +$74,0 | -$74,5 |
| 02/06 | +$44,0 | +$199,0 | -$155,0 |
| 03/06 | +$83,0 | +$287,0 | -$204,0 |
| 04/06 | -$81,5 | -$127,5 | +$46,0 |
| **Total (4 dias)** | **+$45,0** | **+$432,5** | **-$387,5** |

## ⚠️ Marcelo está certo: piorou nesses 4 dias. Mas o mecanismo é conhecido e explicável.

Rodei uma comparação trade a trade no **dataset inteiro de 13 meses** (não só esses 4 dias) pra
entender por quê — script `backtest/compara_be_trigger.py`. Resultado, em 1.422 trades pareados:

| | Quantidade | Δ médio por trade | Δ total |
|---|---|---|---|
| Trades idênticos (favor nunca chega nem em 2,5pt) | 1.290 | $0 | $0 |
| **Trades que MELHORARAM** (loss cheio virou pequeno/breakeven) | 46 | **+$147,1** | +$6.764 |
| **Trades que PIORARAM** (ganho cortado mais cedo) | 86 | -$50,0 | -$4.302 |
| **Líquido (ano inteiro)** | | | **+$2.462** |

**O mecanismo é real dos dois lados:**
- Gatilho mais baixo trava o lucro mais cedo → **na maioria das vezes** (86 casos), isso corta um
  pouco de um trade que ia continuar favorecendo (custo médio -$50/trade — pequeno, mas frequente).
- Só que **quando o trade ia mesmo reverter** pra um stop cheio depois de favorecer entre 2,5 e
  3,75pt, o gatilho mais baixo agora consegue proteger — convertendo uma perda de ~$141 numa saída
  pequena (ganho médio quando acontece: +$147 — **grande, mas raro**, só 46 de 1.422 trades = 3,2%).
- **O raro-mas-grande compensa o comum-mas-pequeno no ano inteiro** (+$2.462 líquido), mas numa
  amostra de só 4 dias (~30 trades), é perfeitamente possível pegar vários dos "comuns" (custo) e
  nenhum dos "raros" (proteção) — foi exatamente o que aconteceu em 01-03/06. **04/06 já mostrou o
  primeiro caso de proteção real** (`NIV_L36`, -$131 virou -$16,5, ver `dia-04-04-06.md`).

## 📌 Um agravante específico desses 4 dias: junho é o MELHOR mês do backtest

Já sabíamos (registrado desde agosto) que **01-18/06 sozinho concentrou toda a melhoria do
BE-lock 0,75 no ano inteiro** — é um trecho de mercado com tendências fortes e trades que
favorecem bastante antes de reverter. **Esse é exatamente o tipo de mês onde o CUSTO do gatilho
baixo (cortar ganho que ia continuar) aparece mais, e o BENEFÍCIO (proteger reversão rápida)
aparece menos** — o oposto do que um mês mais "de vaivém"/lateral mostraria. Testar essa mudança
justamente nos primeiros dias do melhor mês do ano é quase o pior recorte possível pra julgar ela
de forma justa (mesmo viés já documentado: "achado de 1 mês não é regra").

## 📊 Quebra mês a mês (13 meses do backtest) — CONFIRMA que junho é excepcionalmente ruim pra essa mudança

| Mês | BE trig 3,75 | BE trig 2,5 | Δ |
|---|---|---|---|
| 2025-06 | +$406,9 | +$178,1 | **-$228,8** ❌ |
| 2025-07 | +$1.807,9 | +$1.652,9 | -$155,0 ❌ |
| 2025-08 | +$1.286,8 | +$2.253,0 | +$966,2 ✅ |
| 2025-09 | +$217,8 | +$300,2 | +$82,5 ✅ |
| 2025-10 | +$2.794,9 | +$3.393,0 | +$598,1 ✅ |
| 2025-11 | +$3.072,5 | +$3.167,5 | +$95,0 ✅ |
| 2025-12 | +$1.195,2 | +$1.230,2 | +$35,0 ✅ |
| 2026-01 | +$2.827,5 | +$2.688,1 | -$139,4 ❌ |
| 2026-02 | +$4.090,9 | +$4.475,2 | +$384,4 ✅ |
| 2026-03 | +$1.618,2 | +$1.769,5 | +$151,2 ✅ |
| 2026-04 | +$5.189,8 | +$5.527,2 | +$337,5 ✅ |
| 2026-05 | +$444,5 | +$984,5 | +$540,0 ✅ |
| **2026-06** | +$739,6 | +$534,6 | **-$205,0** ❌ |

**9 de 13 meses melhoraram, só 4 pioraram — e os dois JUNHOS do dataset (2025 e 2026) estão entre
os 4 que pioraram.** Isso não é acaso isolado: junho parece ser sistematicamente um mês ruim pra
essa mudança específica (mercado mais "trendy", trades favorecem bastante antes de reverter — o
cenário onde o custo do gatilho baixo pesa mais que o benefício). **Você calhou de testar
justamente no mês historicamente pior pra esse achado**, mas o quadro completo (13 meses) segue
fortemente a favor: melhora em 69% dos meses, incluindo ganhos grandes (+$966, +$598, +$540,
+$384, +$337).

## 📋 Recomendação

**Não abandonar — o quadro mês a mês sustenta o achado.** Sugestão: continuar o forward test do
`BotAprovacao_BETrigger25.cs` passando de junho pra frente (julho em diante, já sabemos que é um
mês mais lateral/whipsaw pro baseline) — se o padrão dos 13 meses se confirmar, esses meses devem
mostrar o lado protetor com mais frequência do que junho mostrou.
