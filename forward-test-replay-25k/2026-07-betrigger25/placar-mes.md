# Placar — BETrigger25 (BE trig 2,5 + MaxDist 20 + BE-lock 0,75), JULHO/2026

> **Troca de mês (01/09):** o forward test do BETrigger25 estava em junho e parou em 11/06
> (Marcelo insatisfeito, 29/08). Junho é o **pior mês** pro achado do BE trig 2,5 — no backtest de
> 13 meses os DOIS junhos (2025 e 2026) estão entre os que pioram, e 9 de 13 meses melhoram.
> Marcelo decidiu (01/09) **refazer em julho/2026, do dia 01**, com a mira numa **firma de DD
> estático** (Tradeify/MFFU/TPT) — o DD estático remove o risco de estourar a conta, que foi o
> que mais incomodou nos forward tests anteriores.
>
> Bot: `src/BotAprovacao_BETrigger25.cs` (inalterado). Para uma firma de DD estático, só ajustar
> no gráfico: `MetaLucroDolar`, `StopDiarioDolar`, `MinDiasOperados` conforme a firma escolhida
> (ver `docs/bot-mym-dd-estatico.md` pra a lista de firmas a levantar).
>
> Config atual do bot no teste anterior de junho (`../2026-06-betrigger25-maxdist20/`): fechou
> 9 dias (01-11/06) em +$38,0 / 40 trades.

## Registro dia a dia

| Dia | Trades | G/L | PnL dia | Saldo acum. | Pico | DD atual | Obs |
|---|---|---|---|---|---|---|---|
| 01/07 | | | | | | | |

*(preencher a cada print do Market Replay — mesmo processo dos meses anteriores: ler o log do
NinjaScript, não a imagem)*

## Métrica que decide

- **Aprovação dentro de 30 dias corridos** (01/07 → 30/07) + PnL.
- Numa firma de DD estático: o bot **não estoura** — ou aprova ou expira o prazo. O que importa é
  **bater a meta a tempo**.
- Comparar contra o backtest: BETrigger25 params no dado do Databento dão ~62% (Apex) / **75%
  (DD estático)** de aprovação. Julho é um dos meses "bons" pro BE trig 2,5.
