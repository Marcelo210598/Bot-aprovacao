# Snapshot - 2026-06-16 (Estratégia Noturna)

> Segunda sessão do dia. A primeira (trailing tick a tick) está em `2026-06-16.md`.
> Branch: `feat/estrategia-noturna` (repo `Marcelo210598/Bot-aprovacao`) — NÃO mergeada na main.

## 🎯 O que foi feito hoje
Implementação da **estratégia NOTURNA "Nomads Trade da Noite"** (ping-pong nas bordas do canal Fibonacci 19h-21h BR), integrada ao `BotAprovacao.cs` para rodar **junto da diurna na mesma conta**.

1. **Backtest combinado** (`backtest/run_diurna_noturna.py`) — diurna (níveis) + noturna na mesma conta 25K/5 MNQ. Varreduras: SL×TP, anti-overtrading (maxN × canal mín), filtro domingo, warm-up de domingo.
2. **Implementação no `.cs`** (4 commits): noturna integrada + desenho do canal/Fib + fix de fuso ET→BR + filtro pular domingo. Diurna ficou 100% inalterada (provado por `git diff`).
3. **Forward test no Market Replay** (08-15/06): validou lógica, fuso, gestão. Achados importantes abaixo.

## 📊 Resultados do backtest (1 ano real)
| Cenário | Taxa | Aprov | d.med | PnL/ano | OOS |
|---|---|---|---|---|---|
| Só Diurna | 100% | 21/21 | 14d | $38.932 | 100/100 |
| Combinado COM domingo | 100% | 29/29 | 8d | $51.799 | 100/100 |
| **Combinado SEM domingo** (honesto) | **96%** | 24/25 | 11d | **$47.438** | 100/93 |

A noturna sozinha é fraca (~89%) — serve como **acelerador** da diurna, não standalone.

## 📝 Decisões técnicas importantes
- **Gestão da noturna = a mesma da diurna** (SL 12,5 + BE 3,75/2,5 + trailing tick a tick). Só a lógica de ENTRADA é nova. Reusa `OnMarketData` e `GerenciaPosicao`.
- **Gatilho noturno (3 partes, em teste):** (1) vela TOCA a zona Fib; (2) é REJEIÇÃO (pavio ≥50% ou doji ≤30%); (3) próxima vela (≤4 barras) rompe o extremo no sentido da reversão → entra a mercado no fechamento.
- **Entrada a mercado no fechamento** (decisão do Marcelo) — mais simples que ordem stop, igual filosofia da diurna.
- **Fuso ET→BR via flag de DST do Eastern** (gráfico em ET): +1h verão US, +2h inverno. NÃO usar `Bars.TradingHours.TimeZoneInfo` (retornava fuso errado).
- **Filtro canal ≥40pt** = config vencedora (cravava 100% no backtest com domingo).
- **PENDÊNCIA FUTURA** (decisão do Marcelo): variante de gatilho sem exigir vela de rejeição (só toca+rompe). Não agora, e com backtest antes. (em `[[project-bot-noturna]]` da memória)

## ⚠️ Problemas encontrados e soluções
- **Bug de fuso:** operava ~1h antes (17:24 ET=18:24 BR entrava como 19:24). → offset pelo DST do Eastern. Commit `607bccd`.
- **Domingo à noite = armadilha do backtest:** 14/06 (domingo) o replay mostrou canal de 247pt de SPIKES (abertura do Globex, baixa liquidez). O backtest 1min "gosta" desses trades (+5 aprov/ano) mas ao vivo a execução é lixo. PROVADO: warm-up de domingo 19:15→19:30 já zera TODOS os trades de domingo (vivem só na abertura caótica). → filtro `PularDomingoNoite` (default ON). Commit `34cec43`.
- **Slippage do replay furando o breakeven:** trades com BE=sim saindo NEGATIVOS (impossível ao vivo — o stop no servidor garantiria +$125). É artefato do replay (dados saltam). Ao vivo com tick real some.

## 🔧 Configurações adicionadas (grupo "7. Noturna" no NT8)
- `OperarNoite` (ON), `NoiteInicioBR` 1900, `NoiteFimBR` 2100, `NoiteWarmupBR` 1915, `NoiteFlattenBR` 2200, `CanalMinPontos` 40, `GatilhoBarras` 4, `PularDomingoNoite` (ON).

## 📊 Estado atual do projeto
- Branch `feat/estrategia-noturna` no GitHub (4 commits), compilando e rodando no Market Replay. Diurna intacta.
- Análise da 1ª semana de replay (08-15/06): log incompleto/repetido, só 16 trades fechados — **não dá pra avaliar performance** (replay distorce, furando até o breakeven). Lógica OK, fuso OK.
- Achado acionável REAL: **overtrading no mesmo nível** (diurna 12/06: 6 trades/8min no nível 29605 = -$251). Avaliar cooldown pós-stop no mesmo nível (com backtest).

## 🚧 Próxima sessão (To-do)
- **Conseguir feed real-time grátis** (Ironbeam/AMP/Tradovate demo) + Sim101 → forward test AO VIVO com tick real (replay distorce demais).
- Avaliar **cooldown pós-stop no mesmo nível** (diurna) por backtest — único achado real da 1ª semana.
- **Decisão de produto:** noturna seg-qui custa ~4pp de taxa (96% vs 100% diurna pura). Validar ao vivo antes de decidir se entra no produto.
- Pendência antiga: variante de gatilho noturno sem exigir rejeição (só com backtest).
- Possível: mergear `feat/estrategia-noturna` na main após forward test ao vivo OK.

## 💡 Observações importantes
- **TraderOS NÃO foi alterado** (Marcelo cogitou limpar o histórico dele, mas decidiu deixar — 102 trades dele + 34 do Andersson intactos).
- Lição geral: **backtest de barra 1min superestima qualquer estratégia em janela de baixa liquidez** (abertura de fim de semana). Sempre desconfiar de trades em domingo/abertura.
- Noites operáveis reais: dom→qui (sexta à noite o mercado já fechou). Pulando domingo = seg→qui.
