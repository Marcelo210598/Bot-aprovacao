# 📐 Taxa de aprovação real — 3 metodologias testadas (20/08/2026)

> Contexto: depois de esgotar variações de gestão de saída e testar 3 famílias de
> estratégia nova (ver `comparativo-estrategias-20-08.md` e `melhorias-sugeridas.md`
> itens 14-16), o Marcelo pediu o número real de "quantas vezes por mês/ano isso
> realmente aprovaria" — não só WR/PF. Testamos 3 jeitos de medir, do mais otimista
> pro mais realista.

## As 3 metodologias (mesmo trade-a-trade, dado idêntico — só muda a janela de risco)

| Metodologia | Como funciona | Viés |
|---|---|---|
| **Ciclo infinito** (`run_estrategias_comparativo.py`) | Reseta a conta só quando aprova/estoura, sem limite de dias | Otimista — ciclo pode "demorar" 40+ dias e ainda contar como aprovado |
| **Mês calendário** (`run_mes_a_mes.py`) | 1 tentativa por mês do calendário, começa sempre no dia 1 | Pessimista — desperdiça dias depois de um estouro cedo no mês, só recomeça no mês seguinte |
| **Janela 30d rolante** (`run_janela_30d.py`) | Reinicia IMEDIATAMENTE após aprovar/estourar, mas cada tentativa tem só 30 dias corridos pra decidir (expira se passar) | **A mais correta** — reflete o produto real (comprar eval, ter 30 dias, decidir) |

## Resultado da reversão (BOT 1 — gestão original, SL 12,5/BE fixo 2,5/trailing 1,75/alvo 60) nas 3 metodologias

| Metodologia | Taxa de aprovação |
|---|---|
| Ciclo infinito | 70% |
| Mês calendário | 15% (2 de 13 meses) |
| **Janela 30d rolante (correta)** | **50% (12 de 24 tentativas/ano)** |

**A taxa de aprovação real da reversão, medida do jeito mais correto: 50%.** De cada 2
avaliações $25K compradas, 1 aprova, rodando o bot continuamente.

## BOT 1 vs BOT 2, no teste de janela 30d (o mais rigoroso)

| Config | Tentativas/ano | Aprovou | Taxa | Mediana p/ aprovar |
|---|---|---|---|---|
| **BOT 1** (baseline, sem nada) | 24 | 12 | 50% | 13d |
| **BOT 2 só BE-lock 0,75** (sem parcial) | 24 | 12 | **50% — idêntico** | 13d |
| **BOT 2 completo** (BE-lock 0,75 + parcial 20pt) | 20 | 8 | **40% — pior** | 17d |

**Achado importante:** o BE-lock 0,75 sozinho, nesse backtest de barra de 1 ano
inteiro, **não mudou UMA ÚNICA tentativa** de estourada pra aprovada (24/12/50%
idêntico ao bot 1, número por número). Isso não contradiz o Δ +$122,5 confirmado
em Market Replay real (18-20/08) — aquele Δ é real, mas pequeno demais e concentrado
em poucos trades de fronteira pra virar o resultado de uma janela de 30 dias inteira
nesse dataset. **A saída parcial, de novo, piora** (50%→40%) — mais uma confirmação
do item #15 (`melhorias-sugeridas.md`), agora no teste mais rigoroso de todos.

## Outras estratégias, mesmo teste (pra contexto)

| Estratégia | Tentativas | Taxa |
|---|---|---|
| ORB sozinho | 216 | 1% |
| EMAV sozinho | 32 | 19% |
| ICT sozinho | 79 | 10% |
| REV+EMAV (melhor mescla) | 45 | 29% |
| REV+ORB / REV+ICT / tudo junto | 87-256 | 0-9% |

Nenhuma chega perto dos 50% da reversão sozinha.

## 🎯 Conclusão e recomendação

1. **A taxa de aprovação real da estratégia atual é 50%**, não os 70% do teste mais
   otimista usado antes — esse é o número pra planejar o negócio.
2. **Nenhuma estratégia nova ou mescla testada supera isso** — a reversão PDH/PDL
   continua sendo, de longe, a melhor opção disponível.
3. **BOT 1 e "BOT 2 só com BE-lock 0,75 (sem a saída parcial)" têm exatamente a
   mesma taxa de aprovação nesse backtest (50%)** — e o BOT 2 tem a vantagem extra,
   já confirmada em Replay real, de capturar um pouco mais de PnL nos trades de
   fronteira (Δ +$122,5 no período testado), sem nenhuma desvantagem observada.
4. **A saída parcial (item #15) deve ser DESLIGADA** (`UsarSaidaParcial=false`) —
   ela piora consistentemente em todos os testes de hoje, inclusive este, o mais
   rigoroso.

**Recomendação: seguir os testes de Market Replay com o BOT 2, mas com
`UsarSaidaParcial=false`** (só o BE-lock 0,75 ligado) — é a única configuração que
bate ou empata o baseline em todos os testes, sem o componente que sabidamente
piora. Isso pode ser feito no próprio `BotAprovacao_SaidaParcial.cs` (ou nas
cópias `_REPLAY`) mudando esse parâmetro no gráfico, sem precisar recompilar nada.
