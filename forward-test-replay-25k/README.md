# Forward Test — Market Replay NT8 (conta 25K)

Objetivo: rodar o `BotAprovacao` de produção no Market Replay (dado real 01/06→10/08/2026) e
contar, mês a mês, se uma conta **Apex 25K** seria **aprovada** (bate meta $1.500 em ≥7 dias
operados) ou **estourada** (viola DD $1.000 EOD) — validação real, não backtest Python.

## Config em teste (produção, sem alterar)
```
TP 60 | SL 12,5 | BE +3,75→+2,5 | Trail 1,75 | Tol 20 ticks | MaxDist 15pt
StopDiário $750 | MaxTrades 12 | Janela 9h30-16h ET | Flatten 16h55 ET
SegUsaDomingo=ON | OperarNoite=OFF | Meta $1.500 | MinDias 7 | DD real $1.000 (EOD)
```

## ⚠️ Duas pastas de junho — leia isto primeiro
- **`2026-06/`** — teste original, rodado sem querer no **gráfico de 5 minutos**. Mês fechado como
  "incompleto" (nem aprovou nem estourou), mas o diagnóstico da revisão de 12/08
  (`docs/revisao-estrategias-12-08.md`) é **timeframe errado**, não estratégia ruim. Mantido como
  registro histórico — não usar pra julgar a estratégia.
- **`2026-06-1min/`** — re-teste no **gráfico de 1 minuto** (o que o backtest sempre usou), em
  andamento desde 13/08. Esta é a versão que conta pra decisão final.

## Estrutura (dentro de cada pasta de mês)
- `placar-mes.md` — placar acumulado do mês (dia a dia): PnL, pico, drawdown, progresso da meta
- `dia-XX-DD-MM.md` — detalhe de cada dia (trades, entrada/saída, motivo)
- `prints/` — screenshots das entradas/saídas (gain e loss), se salvos manualmente

## ⚠️ Nota sobre os prints
Os prints usados na sessão de 11/08 (via chat) não ficaram salvos em disco — a pasta temporária
do macOS (`NSIRD_screencaptureui_*`) já limpou os arquivos antes de eu conseguir copiar. O registro
do dia 01/06 ficou só em texto (preço/horário/pontos, extraído direto do log do NinjaScript). Se
quiser prints de verdade daqui pra frente, salve o print (Cmd+Shift+4 → escolher pasta) direto em
`2026-06/prints/` com nome tipo `01-06_trade1_long.png` — aí eu referencio no arquivo do dia.
