# Placar — Julho/2026 (Market Replay)

Config rodando: `BotAprovacao_SaidaParcial.cs` — `[EXP] Usar saida parcial = false` +
`[EXP2] Usar BE-lock proporcional = true` (fração 0,75). Config final decidida em 20/08 após
o mês de junho fechar com Δ +$122,5 sobre o baseline (ver `../2026-06-saidaparcial/`). Não é mais
um teste A/B contra baseline — é o acompanhamento direto dessa config em produção-candidata.

| Dia | Trades | PnL do dia | PnL acumulado |
|---|---|---|---|
| 01/07 (qua) | 0 | $0 | $0 |
| 02/07 (qui) | 1 (0G/1L) | -$169,0 | -$169,0 |
| 03/07 (sex) | 0 | $0 | -$169,0 |
| 06/07 (seg) | 5 (2G/3L) | -$206,0 | -$375,0 |
| 07/07 (ter) | 0 | $0 | -$375,0 |
| 08/07 (qua) | 5 (2G/3L) | -$245,0 | -$620,0 |
| 09/07 (qui) | 0 | $0 | -$620,0 |
| 10/07 (sex) | 3 (2G/1L) | -$78,0 | -$698,0 |
| 13/07 (seg) | 5 (3G/2L) | -$0,5 | -$698,5 |
| 14/07 (ter) | 7 (3G/4L) | -$80,0 | -$778,5 |
| 15/07 (qua) | 6 (4G/2L) | +$126,0 | -$652,5 |
| 16/07 (qui) | 5 (3G/2L) | +$110,0 | -$542,5 |
| 17/07 (sex) | 0 | $0 | -$542,5 |
| 20/07 (seg) | 6 (5G/1L) | +$20,0 | **-$522,5** |

## 💡 Observações

- Trade de 02/07 (`NIV_L8`, LONG, stop cheio -12,50pt): PnL real -$169 ficou acima do que a
  matemática simples de pontos sugeriria (12,5pt × $10/pt × 5 contratos = -$125) — mesmo padrão
  de divergência já mapeado em `progress.md` (seção "Monitorar", item 13/08), provavelmente
  slippage real de fill não capturado no texto resumido do log. PnL usado no placar é sempre o
  real via `[MeuTrade]`.
- **06/07 — dia horrível (-$206,0, 5 trades, 2G/3L):** linha Max 30010,00 ficou grudada no preço
  a manhã inteira, gerando 5 entradas na mesma região e 2 stops cheios seguidos (trades 4 e 5,
  -$148 e -$122). Trade 3 é mais um caso da divergência PnL-real-vs-pontos (BE ativado, saída
  levemente a favor nos pontos, PnL real ainda assim negativo). Detalhe completo em
  `dia-06-06-07.md`.
- **08/07 (-$245,0, 5 trades, 2G/3L):** 2 stops cheios logo cedo (-$158 e -$139) pesaram mais que
  os 2 ganhos que vieram depois no mesmo dia. Linha Min 29209,75 testada 5 vezes.
- **Semana 06-10/07 fechou muito negativa:** -$529,0 nos 3 dias com entrada (06, 08 e 10) — pior
  trecho do forward test desde que começou o acompanhamento.
- **13/07 fechou quase zero a zero (-$0,5)**, mas com um achado importante: 2 dos 5 trades
  (`NIV_L5` -$153 e `NIV_L7` -$121) tomaram stop cheio com favor máximo de menos de 1pt — entrada
  na direção certa, reversão quase imediata, sem tempo do BE/trailing agir. Registrado como
  **item #17 pra investigar** em `docs/melhorias-sugeridas.md` (ainda não é achado confirmado,
  só 2 casos — watch se repete). Detalhe em `dia-13-13-07.md`.
- **Virada a partir de 15/07:** depois de 4 dias negativos seguidos (02, 06, 08, 14/07), 15/07
  (+$126,0), 16/07 (+$110,0) e agora 20/07 (+$20,0) formam 3 dias positivos em 4 — só 1 stop cheio
  no meio desse trecho (20/07, -$126). Acumulado do mês ainda bem negativo (-$522,5), mas a
  sangria dos stops cheios deu uma pausa clara desde 15/07.
