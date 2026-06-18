# Bot Trade NT8 (BotAprovacao) - Progresso

## Última atualização: 2026-06-18 noite (fix fantasma VALIDADO ao vivo + SL15 em teste + Andersson em MNQ + TraderOS limpo)

## 🐛 FIX CRÍTICO 18/06 — duplo-fill / posição fantasma (forward test Sim101)
- **Sintoma:** short S32 tomou stop, mas o bot "virou LONG" sozinho. Era posição FANTASMA.
- **Causa-raiz:** stop em DOIS lugares no MESMO preço → saída a mercado (`OnMarketData`) + stop do
  servidor (`SetStopLoss`) encheram no mesmo tick → comprou 10 estando vendido 5 → flip pra long 5.
  A neutralização `SetStopLoss(5000)` PERDE a corrida (servidor já disparou). O long preso não fechava
  porque `sinalAtivo` ainda era "NIV_S32" (short) → `ExitLong` não casava.
- **Correção:** novo param **`BufferStopServidorPontos` (default 5pt)** — stop do servidor fica sempre
  5pt MAIS LARGO que o gerenciado (entradas diurna+noturna E move de breakeven). A saída a mercado
  dispara ANTES do servidor → impossível duplo-fill. Trade-off: backstop de desconexão ~5pt mais largo.
- **Backtest INTACTO:** `OnMarketData` não roda no histórico → 94%/OOS 100% inalterados.
- **Bônus:** fix do log `~saida` (mostrava close da vela, fazia win parecer loss; agora usa stop/alvoPrice).
- ⚠️ Recompilar no NT (F5) + REMOVER e RE-ADICIONAR a estratégia (assinatura mudou: param novo).
- Dia Sim101 fechou −$95,50 (a bagunça do fantasma comeu os 5 winzinhos +$144 vs stop −$111).

## 📊 VARREDURA TRAILING x BREAKEVEN (18/06, `backtest/run_trailing_sweep.py`)
- Pergunta: afrouxar o trailing pra trades maiores? **RESPOSTA: NÃO.** Baseline (BE3,75/tr1,75) venceu tudo:
  100% aprov, 14d, WR 69%, PF 1,66, **$38,9k** (melhor PnL). OOS 100%/100% nas duas metades.
- Afrouxar sobe o ganho médio ($99→$203) mas DESTRÓI o WR (69%→45%) e a taxa de aprovação → menos PnL.
  Trailing apertado = feature (catar winzinhos consistentes), não bug. MANTÉM como está.


## 🌙 NOTURNA — estado FINAL (branch `feat/estrategia-noturna`)
- **Gatilho na LINHA (extremo do canal alta/baixa), NÃO nas Fib centrais:** vela A toca/passa a LINHA
  (`zVenda = noiteHigh - LinhaToleranciaPontos`; `zCompra = noiteLow + LinhaToleranciaPontos`) → arma no
  CORPO de A → vela B passa o corpo → entra TICK A TICK. Param `LinhaToleranciaPontos` default **5pt**.
  Backtest `run_noturna_linha.py`: **+5pt → 100% (26/26), OOS 100/100, ~$48k/ano** (10pt $52k, 15pt $55k).
- **Entrada TICK A TICK** (OnMarketData `TentaEntradaNoturnaTick`): entra no instante que o preço cruza o
  corpo de A, sem esperar a vela fechar. Rede backtest histórico (State!=Realtime) no fechamento.
- **FUSO-PROOF:** detecta o fuso do gráfico (reflection) → diurna→ET, noturna→BR em qualquer fuso. Fallback ET.
- **Gráfico DEVE ser 1min** (diurna degrada em 5min). Desenho: LINHA alta/baixa + banda de tolerância dourada.
- **`ToqueFresco`** = toggle default OFF (foi um fix de interpretação errada; a linha-extremo já restringe).
- 🔑 LIÇÃO: toda restrição de seletividade na reversão REDUZ PnL ou não conserta o downtrend. Rejeitados:
  corpo+pavio, filtro anti-tendência, zona apertada, toque fresco, níveis à noite, fecha-close, 5min.
  Em downtrend a reversão SEMPRE sangra (a linha rompe) — proteção = STOP DIÁRIO $750, não filtro.
- Replay 15/06 (downtrend) com gatilho na linha: net −$190 (L30+18,5 L31−124,5 L32−137 L33+53). Capado.
- Commits: `2ca5fe7`(corpo+fuso) `486d4e4`(1min+tick) `8e4f0f3`(toque fresco) `6ea8471`(LINHA/extremo).

## 🚀 DEPLOY (definido 18/06)
- Andersson testa **quinta 18/06 e sexta 19/06** (Marcelo envia ZIP do bot).
- **Segunda 22/06: início teste na CONTA REAL** (Apex, tentando aprovar).
- ⚠️ Antes do real: StartBehavior → **AdoptAccountPosition**.



## 🌙 ESTRATÉGIA NOTURNA (16/06 — branch `feat/estrategia-noturna`, NÃO mergeada)
Reversão "ping-pong" nas bordas do canal Fibonacci **19h-21h BR**, integrada ao `BotAprovacao.cs`
pra rodar **junto da diurna na mesma conta**. Vende zona 76,4-100% (topo), compra 0-23,6% (fundo);
gatilho = rompimento do pavio da vela de rejeição; filtro canal ≥40pt; gestão idêntica à diurna.
- **Backtest combinado (sem domingo, honesto):** 96% / 11 dias / +$47k/ano / OOS 100%/93%.
  (Com domingo dava 100%/8d/$52k, mas é ILUSÓRIO — trades de domingo vivem na abertura caótica do Globex.)
- **Toggle `OperarNoite` + grupo "7. Noturna"** no NT8. Default `PularDomingoNoite` = ON.
- **Status:** compilando e em forward test no Market Replay. A noturna é ACELERADOR (sozinha ~89%).
- **Pendência:** forward test AO VIVO (replay distorce/fura breakeven); decidir se entra no produto
  (custa ~4pp de taxa vs diurna pura 100%); variante de gatilho sem exigir rejeição (com backtest).
- Detalhes em `historico/2026-06-16-estrategia-noturna.md`. Backtest: `backtest/run_diurna_noturna.py`.

---


## 📌 Visão Geral
- **Objetivo:** Bot de APROVAÇÃO de conta Apex (produto de entrada) → upsell do bot de operação
- **Público:** Comunidade Nômade Trader (traders BR, Apex)
- **Stack:** NinjaScript (C#) + backtest em Python (validação)
- **Status:** 🟢 Bot implementado e em forward test — **100% de aprovação no backtest**

## 🎯 Config vencedora atual (5 MNQ, conta 25K Intraday)

```
Mercado:     MNQ (Micro Nasdaq) — 5 contratos
Conta:       Apex 25K Intraday (meta $1.500 | DD $1.500 | mín. 7 dias)
Entrada:     reversão na máxima/mínima do dia anterior
             (SEGUNDA: range do domingo à noite / Globex 18h→9h30)
Tolerância:  20 ticks = 5pt
Filtro:      MaxDistPontos = 15pt (close a no max 15pt da linha)
Alvo (TP):   60 pontos
Stop (SL):   12,5 pontos  →  $125/trade (5 MNQ)
Breakeven:   +3,75pt → trava +2,5pt
Trailing:    1,75pt
Stop diário: $750
Janela:      9h30–16h00 ET (flatten 16h55)
Parar:       ao bater meta $1.500 + 7 dias operados
```

## 📊 Resultado do backtest (1 ano real, 300k barras NQ 1min)

| Métrica | Valor |
|---|---|
| **Taxa de aprovação** | **100%** (19 aprovadas / 0 reprovadas) |
| **Mediana por aprovação** | **15 dias** |
| **Profit Factor** | **1.60** |
| **PnL estimado/ano** | **+$36.978** |
| **Robustez OOS** | **100%/100%** (1ª e 2ª metade) |
| Win Rate | 68% |
| Trades/dia | ~6.7 |

## ✅ Concluído

### Estratégia e backtest
- Análise competitiva (NinjaBot IA / NinjaPass) — diferencial: gestão de DD
- Backtest com 1 ano de dados reais NQ 1min (~300k barras)
- Testadas 4 estratégias: ORB+VWAP, MeanReversion, Níveis, Matheus
- **Vencedora: Níveis + trailing stop** (rejeição high/low do dia anterior)
- Validação out-of-sample (2 metades) — robusto, não overfit

### Otimizações (comprovadas por backtest, todas adotadas)
1. **Tolerância de toque: 6 → 20 ticks** (13/06) — +21% PnL, +2 aprovações
2. **Janela de entrada: 15h → 16h** (14/06) — +2 aprovações/ano, zero noturnas
3. **Filtro de proximidade: MaxDistPontos = 15pt** (14/06) — 100% taxa, PF 1.60, OOS perfeito
4. **Segunda usa range do domingo à noite (Globex)** (15/06) — 19→**22 aprov/ano**, mediana 15→**13d**, PF 1.60→1.64, OOS 100%/100%. Antes a segunda usava a linha de sexta (ou linha degenerada de 1 barra de domingo, efeito colateral). Toggle `SegUsaDomingo` (default ON). Backtest: `backtest/run_segunda_domingo.py`. ⚠️ No gráfico exige sessão ETH/Globex (não RTH-only) senão cai no fallback da linha de sexta.

### Implementação
- Strategy de produção **`src/BotAprovacao.cs`** — compilada e funcionando no NT8
- **Gestão de saída ao vivo TICK A TICK** (16/06): `OnMarketData` faz fav→breakeven→trailing→alvo/stop a cada tick, desde o 1º tick pós-fill. SL sobe junto com o lucro DENTRO da vela (não espera a vela fechar). `GerenciaPosicao` (OnBarClose) mantido p/ backtest + rede no fechamento.
- ⚠️ `OnMarketData` só roda ao vivo/replay (`State==Realtime`) → **backtest 100% inalterado**; live diverge do backtest bar-based no tick-level (validação empírica via replay).
- Integração TraderOS (HTTP 201, dedup por externalId) — funcionando
- Repo GitHub: `Marcelo210598/Bot-aprovacao` (privado)

### Forward test (Market Replay)
- Dias **09/06 a 12/06/2026** concluídos
- Bugs encontrados e corrigidos na sessão 13/06 (4 bugs críticos)
- **Sessão 16/06** — replay do **15/06** (segunda, nível domingo à noite): achados/corrigidos Bug 5 (stop servidor rejeitado em rally → `OnMarketData` intrabar) e Bug 6 (trailing 1 barra atrasado + saídas mudas). Implementado trailing tick a tick a pedido do Marcelo. Trades 15/06: NIV_S11 +$29, NIV_S12 -$124 (faltou 1 tick p/ breakeven), NIV_S13 -$10,5 (proteção cortou de -$125). Dia de rally forte + gap de entrada pesaram.
- Comportamentos validados: stop intrabar, trailing tick a tick, filtro chase, TraderOS sync, spam de log

## 🚧 Em progresso
- Forward test — rodar **mais dias de replay** (dias calmos, sem reversão em V) p/ ver o trailing tick a tick travando lucro de verdade
- Avaliar (SÓ se necessário, por backtest) antecipar gatilho de breakeven **3,75 → 3,0/2,5** p/ proteger trades que ficam a ~3,5pt a favor (ex.: NIV_S12 -$124 do 15/06)
- Observar o **gap de entrada** (fill no abre da vela seguinte) — maior dano em dia de rally; pensar mitigação só com backtest
- Forward test — semana **02–06/06/2026** pendente (baixar dados: 30/05 a 06/06)
- Confirmar com Andersson: regra 7 dias mínimos + custo real MNQ

## ⚠️ Problemas mapeados

### Resolvidos
- OCO ID reutilizado → stop/alvo não criados → **resolvido** (sinal único por trade)
- Trailing c/ ordem no servidor desabilitava bot → **resolvido** (trailing sintético)
- Stop inicial inválido → perdas enormes → **resolvido** (ticks na entrada)
- Entradas "chase" (3 stops em 3 min no mesmo nível) → **resolvido** (filtro 15pt)
- Spam de log em dias acima do PDH → **resolvido** (guard tol*2)
- **[17/06] Trailing sumia no restart** → resolvido (`AdoptAccountPosition` + recovery em `State.Realtime`)
- **[17/06] Bot se auto-desabilitava** → resolvido (null-safety em `TradesHoje` e `RealizadoAcumulado`)
- **[17/06] SHORT fantasma pós-exit** → resolvido (neutraliza server stop 5000 ticks antes de fechar)

### Monitorar (baixa prioridade)
- Overtrading: ~14 trades/dia no backtest — decisão: manter (fiel ao backtest). Soluções mapeadas se der problema ao vivo (cooldown / max 12 trades-dia).
- Dias de mercado lateral (range extremo dia anterior): zero entradas. Comportamento esperado, já no backtest dos 100%.

## 📋 Próximos passos (roadmap)
1. **Forward test semana 02–06/06** — baixar dados e rodar
2. **Forward test completo** — validar slippage real ao vivo no Sim101
3. **Confirmar Andersson** — regra 7 dias + custo MNQ
4. **Bot Funded 25K** — 🟡 backtest iniciado e refinado (15/06, pasta `Estrategia 25/`). Falta `.cs` + forward test.
5. **Bot Funded 50K** — variante com mais folga de DD

## 🎯 Visão de produto (3 produtos)
1. **Bot Aprovação** ← atual (BotAprovacao, 100%/15d, 5 MNQ, 25K) ✅ forward test
2. **Bot Funded 25K** — 🟡 estratégia pós-aprovação em backtest. Config v3 refinada (15/06): Intraday,
   **2→3 MNQ** (escalona após travar a gordura $26.600), alvo **$400/dia**, **breakeven 1.5/1.0**.
   Resultado: **19 saques/ano (~$19k ≈ R$104k)**, **WR 75,9% / 78,8% dias verdes / PF 1.91 / 0 violação**,
   OOS 0/0. Proteção 4 camadas (SL 12.5pt/trade + BE + stop diário $300 + DD $1.500). Pasta `Estrategia 25/`.
   Descartados: filtro horário, escalonamento 2 degraus, filtro SMA (ver README). Falta `.cs` + forward test.
3. **Bot Funded 50K** — idem para conta 50K (mais agressivo)

## 📁 Arquivos importantes
- `src/BotAprovacao.cs` — **estratégia de produção** (compilar e usar no NT8)
- `docs/estrategia-mnq-5contratos.md` — documentação da estratégia escolhida
- `backtest/run_mnq_5contr.py` — backtest baseline
- `backtest/run_tolerancia.py` — otimização tolerância (tol 20t)
- `backtest/run_horario_18h.py` — otimização janela (16h)
- `backtest/run_proximity_filter.py` — otimização MaxDist (15pt)
- `backtest/run_stop_diario.py` — otimização stop diário ($750)
- `NQ_dados/` — dados NQ 1min (jun/2025–jun/2026)
- `historico/` — snapshots diários das sessões

## 🔧 Como usar o bot no NT8
1. Baixar `src/BotAprovacao.cs` do GitHub (repo privado — não colar texto, corrompe)
2. Colocar na pasta Strategies do NT8
3. Compilar (F5 no Editor NinjaScript)
4. Adicionar ao gráfico MNQ 1min (fuso ET)
5. Config padrão já está correta — conferir parâmetros antes de ligar

## ⚖️ Ressalvas
- Backtest em NQ 1min (~10,5 meses úteis) — custos estimados ($1,20 RT/contrato MNQ)
- Backtest ≠ ao vivo — forward test em Sim101 obrigatório antes de conta real
- Apex trailing DD só estimado de dentro do NinjaScript
