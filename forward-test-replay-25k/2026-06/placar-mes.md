# Placar acumulado — Junho/2026 (conta 25K)

> ⚠️ **Este teste rodou sem querer no gráfico de 5 minutos** (o backtest original usa 1min).
> Diagnóstico da revisão de 12/08: o timeframe errado é a causa mais provável do resultado fraco,
> não a estratégia em si. Mês sendo refeito no timeframe certo em **`../2026-06-1min/`** — use
> aquela pasta pra julgar a estratégia, esta fica só como registro histórico.

Meta de aprovação: **+$1.500** realizado em **≥7 dias operados**, sem violar **DD $1.000 (EOD, trailing)**,
**dentro da janela de 30 dias corridos (01/06 → 30/06/2026)**.

| Dia | Data | Trades (G/L) | PnL do dia | PnL acumulado | Pico (p/ DD EOD) | Drawdown atual | Dias operados |
|---|---|---|---|---|---|---|---|
| 1 | 01/06 (seg) | 2 (2G/0L) | +$108 | +$108 | $108 | $0 | 1/7 |
| 2 | 02/06 (ter) | 5 (5G/0L) | +$186 | +$294 | $327 *(pico atingido no dia 3)* | $0 | 2/7 |
| 3 | 03/06 (qua) | 3 (2G/1L) | -$80 | +$214 | $327 | $113 | 3/7 |
| 4 | 04/06 (qui) | 0 | $0 | +$214 | $327 | $113 | 3/7 |
| 5 | 05/06 (sex) | 0 | $0 | +$214 | $327 | $113 | 3/7 |
| 8 | 08/06 (seg) | 3 (2G/1L) | -$99 | +$115 | $327 | $212 | 4/7 |
| 9 | 09/06 (ter) | 2 (2G/0L) | +$91 | **+$206** | $327 | **$121** | 5/7 |
| 10 | 10/06 (qua) | 0 | $0 | +$206 | $327 | $121 | 5/7 |
| 11 | 11/06 (qui) | 0 | $0 | +$206 | $327 | $121 | 5/7 |
| 12 | 12/06 (sex) | 0 | $0 | +$206 | $327 | $121 | 5/7 |
| 15 | 15/06 (seg) | 0 | $0 | +$206 | $327 | $121 | 5/7 |
| 16 | 16/06 (ter) | 1 (1G/0L) | +$56 | +$262 | $327 | $65 | 6/7 |
| 17 | 17/06 (qua) | 2 (0G/2L) | -$170 | +$92 | $327 | $235 | 7/7 ✅ |
| 18 | 18/06 (qui) | 2 (2G/0L) | +$62,5 | +$154,5 | $327 | $172,5 | 8 |
| 19 | 19/06 (sex) | 0 | $0 | +$154,5 | $327 | $172,5 | 8 |
| 22 | 22/06 (seg) | 0 | $0 | +$154,5 | $327 | $172,5 | 8 |
| 23 | 23/06 (ter) | 0 | $0 | +$154,5 | $327 | $172,5 | 8 |
| 24 | 24/06 (qua) | 1 (0G/1L) | -$126 | +$28,5 | $327 | $298,5 | 9 |
| 25 | 25/06 (qui) | 0 | $0 | +$28,5 | $327 | $298,5 | 9 |
| 26 | 26/06 (sex) | 0 | $0 | +$28,5 | $327 | $298,5 | 9 |
| 29 | 29/06 (seg) | 4 (3G/1L) | +$142 | +$170,5 | $327 | $156,5 | 10 |
| 30 | 30/06 (ter) | 0 | $0 | **+$170,5** | $327 | **$156,5** | 10 |

*(06-07/06, 13-14/06, 20-21/06 e 27-28/06 = fins de semana, sem pregão RTH; range de domingo à noite alimentou os níveis de 08/06, 22/06 e 29/06)*
*(A partir do dia 18/06: contrato trocado pra **MNQ SEP26**, JUN26 vencia 19/06 — ver `dia-18-18-06.md`)*

## 🏁 VEREDITO FINAL DO MÊS — Junho/2026 (janela 01/06 → 30/06, FECHADA)

- **Resultado: MÊS INCOMPLETO** — nem aprovou, nem estourou.
- **PnL final:** +$170,5 de $1.500 (**11,4%** da meta)
- **Drawdown máximo atingido:** $298,5 de $1.000 (29,9%, no dia 24) — **nunca chegou perto de
  estourar**, sobrou $701,5 de margem até no pior momento
- **Dias operados:** 10 de 7 mínimos — gate de dias nunca foi o problema
- **Trades:** 25 no total, **19 gain / 6 loss (WR 76%)**
- **22 pregões cobertos no mês** (todos os dias úteis de junho) — **10 com trade, 12 zerados**
  (mercado não tocou a linha ou foi bloqueado pelo filtro anti-chase na maioria)
- Segue pro mês 07/2026 com a mesma config (decisão de manter `MaxDistPontos=15pt`, ver #10 em
  `docs/melhorias-sugeridas.md`).

## 📜 Histórico completo de trades (todos os dias)

| # | Data | Hora ET | Sinal | Lado | Entrada | Saída | Pontos | PnL |
|---|---|---|---|---|---|---|---|---|
| 1 | 01/06 | 11:05 | NIV_L4 | LONG | 30306,80 | 30314,25 | +7,45 | +$73 |
| 2 | 01/06 | 16:45 | NIV_S5 | SHORT | 30586,75 | 30582,00 | +4,75 | +$35 |
| 3 | 02/06 | 12:55 | NIV_S6 | SHORT | 30687,00 | 30684,50 | +2,50 | +$20,5 |
| 4 | 02/06 | 13:00 | NIV_S7 | SHORT | 30691,40 | 30686,75 | +4,65 | +$56,5 |
| 5 | 02/06 | 13:55 | NIV_S8 | SHORT | 30677,00 | 30674,50 | +2,50 | +$14 |
| 6 | 02/06 | 14:00 | NIV_S9 | SHORT | 30691,00 | 30685,50 | +5,50 | +$68,5 |
| 7 | 02/06 | 14:10 | NIV_S10 | SHORT | 30691,75 | 30688,75 | +3,00 | +$26,5 |
| 8 | 03/06 | 11:35 | NIV_S11 | SHORT | 30707,55 | 30704,25 | +3,30 | +$20 |
| 9 | 03/06 | 11:40 | NIV_S12 | SHORT | 30712,30 | 30709,75 | +2,55 | +$13 |
| 10 | 03/06 | 11:45 | NIV_S13 | SHORT | 30700,55 | 30713,05 | **-12,50** | **-$113** |
| 11 | 08/06 | 14:30 | NIV_S1 | SHORT | 29602,30 | 29599,25 | +3,05 | +$20,5 |
| 12 | 08/06 | 15:10 | NIV_S2 | SHORT | 29598,00 | 29595,25 | +2,75 | +$5 |
| 13 | 08/06 | 15:35 | NIV_S3 | SHORT | 29592,30 | 29604,80 | **-12,50** | **-$124,5** |
| 14 | 09/06 | 10:30 | NIV_S4 | SHORT | 29732,75 | 29727,25 | +5,50 | +$54 |
| 15 | 09/06 | 10:55 | NIV_S5 | SHORT | 29731,20 | 29726,25 | +4,95 | +$37 |
| 16 | 16/06 | 12:15 | NIV_L1 | LONG | 30312,45 | 30318,50 | +6,05 | +$56 |
| 17 | 17/06 | 11:00 | NIV_L2 | LONG | 30025,45 | 30031,25 | — *(ver nota)* | -$19 |
| 18 | 17/06 | 16:15 | NIV_L3 | LONG | 30049,65 | 30037,15 | -12,50 | -$151 |

*PnL de ambos os trades do dia 17 confirmado via `[MeuTrade]` (sync real com TraderOS), não só
pelos preços do print (ver ressalva em `dia-17-17-06.md`).*

| 19 | 18/06 | 12:40 | NIV_S4 | SHORT | 30542,90 | 30540,40 | +2,50 | +$30,5 |
| 20 | 18/06 | 12:45 | NIV_S5 | SHORT | 30533,95 | 30530,25 | +3,70 | +$32 |
| 21 | 24/06 | 11:20 | NIV_L1 | LONG | 29581,90 | 29569,40 | **-12,50** | **-$126** |
| 22 | 29/06 | 10:35 | NIV_S1 | SHORT | 29757,80 | 29755,25 | +2,55 | +$34,5 |
| 23 | 29/06 | 10:50 | NIV_S2 | SHORT | 29762,45 | 29757,75 | — *(ver nota)* | +$168 |
| 24 | 29/06 | 10:55 | NIV_S3 | SHORT | 29760,30 | 29772,80 | **-12,50** | **-$111** |
| 25 | 29/06 | 12:35 | NIV_S4 | SHORT | 29764,00 | 29758,25 | +5,75 | +$50,5 |

*Trade 23: PnL confirmado via `[MeuTrade]` (sync real com TraderOS) — trecho de H/dist do print
pouco legível pra esse trade específico, ver ressalva em `dia-29-29-06.md`.*

**Total até agora: +$170,5 — 25 trades, 19 gain, 6 loss (WR 76%). Pico $327, drawdown atual $156,5.**

## Como isso vira "aprovado ou não" no fim do mês

- **Aprovada** se: PnL acumulado ≥ $1.500 **E** dias operados ≥ 7 **E** nunca violou o DD $1.000 (EOD)
- **Estourada (bust)** se: em algum dia o drawdown (pico − saldo do dia) ultrapassar $1.000
- Se chegar ao fim do mês sem bater os $1.500 nem estourar: mês "incompleto" (nem aprovou nem
  perdeu a conta) — registrar e seguir pro próximo mês de dado, já que a aprovação real do backtest
  leva ~13-15 dias em média.

*(Atualizar esta tabela a cada dia novo — adicionar linha, recalcular acumulado/pico/drawdown.)*
