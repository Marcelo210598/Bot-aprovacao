# 🔍 Pesquisa: Bots NinjaTrader 8 + Apex Trader Funding

> Pesquisa pesada feita em 23/06/2026 (fóruns, Reddit, YouTube, sites especializados,
> docs oficiais Apex). Objetivo: comparar o que a comunidade faz com o nosso bot
> (BotAprovacao) e identificar acertos, erros e melhorias.

---

## 🚨 PONTO MAIS CRÍTICO — Política da Apex sobre automação

**A Apex PROÍBE automação em TODAS as fases** (eval E performance account). Texto
oficial da página "Prohibited Activities" (verificado jun/2026):

> *"AI, Autobots, Algorithms, Fully Automated Trading Systems or Software, HFTs, or
> any other automated trading is strictly prohibited on all account types. Any type
> of hands-off, set-and-forget, or set-and-walk-away trading... is strictly prohibited.
> Using these types of automation will result in the immediate closure of your PA or
> Live account and the forfeiture of all funds and balances."*

Fontes oficiais:
- https://apextraderfunding.com/help-center/getting-started/prohibited-activities/
- https://support.apextraderfunding.com/hc/en-us/articles/40463668243099-Prohibited-Activities

### O que PODE usar (suporte Apex confirmou por escrito):
- Auto-breakeven via NT8 ✅
- Trailing stop automático via NT8 ✅
- ATM Strategies (bracket orders SL+TP) ✅
- Scalping rápido (sem duração mínima de trade) ✅
- Copy trading entre SUAS PRÓPRIAS contas (até 20) ✅
- ❌ Bot autônomo de entrada (set-and-forget) = PROIBIDO

### Realidade prática (comunidade):
- **Eval/Combine**: fiscalização fraca, comunidade usa bots amplamente sem punição
- **Performance Account (PA)**: fiscalização ATIVA, confisco documentado
- Caso real (Reddit, abr/2026, 161 upvotes): trader 100% MANUAL teve $2.603 confiscados
  por "automated activity" após 46 dias. Abriu reclamação no CFTC.
  - Um bot tick-a-tick idêntico sessão após sessão tem fingerprint MUITO mais óbvio
    nos logs do Rithmic.

### Métodos de detecção de bot pela Apex:
1. Análise de padrão de ordens (intervalos regulares entre entradas)
2. Timing de milissegundos (execuções sub-segundo consistentes)
3. Logs de API Rithmic (distingue manual de automático no protocolo)
4. Comparação entre sessões (entradas idênticas em horários idênticos)

### Prop firms que PERMITEM bot explicitamente (alternativas):
- **TopstepX** — full automação permitida
- **Tradeify** — permitido se você desenvolveu o bot
- **My Funded Futures** — automação via Tradovate API
- **Take Profit Trader** — bots permitidos

---

## 1. ESTRATÉGIAS MAIS USADAS PELA COMUNIDADE

### 🥇 Opening Range Breakout (ORB) — a mais popular no NT8
- Range dos primeiros 5-15-30 min após 9:30 ET
- Entrada no rompimento com confirmação de volume
- **Ratio 4:1 = melhor resultado** (backtest MES 1-min, 2 anos): $60.924, DD -$3.443
- Ratio 2:1 = mais usado na prática (equilíbrio frequência/retorno)
- Stop: wick do candle de breakout, Fib do range (38.2/61.8%), ou ATR

### 🥈 Reversão PDH/PDL (máx/mín dia anterior) — O QUE NOSSO BOT FAZ ✅
- Estratégia clássica e validada para prop firms
- Win rate típico 65-69% bem calibrado

### 🥉 EMA + VWAP Scalping
- EMA 9/20/50 + VWAP diário + RSI 14
- Long: preço > VWAP + EMA 9>20>50 + RSI cruza 50
- Win rate 55-65% no NQ/ES; ~1.8%/mês no MNQ, DD < 15%
- Timeframe 3-5 min

### ICT Concepts (FVG + Order Block + MSS)
- 6 setups automatizando conceitos do Inner Circle Trader
- Backtest MNQ 1-min: $11.387 (DD -$3.703); MCL: $4.771 (DD só -$788)
- Filtro Higher Timeframe (confirma 4H antes de entrar no 1-min)

### Instrumentos mais usados:
| Instrumento | Tick | Uso ideal |
|---|---|---|
| **MNQ** | $0.50 | PADRÃO para eval $25K-$100K (o nosso) ✅ |
| MES | $1.25 | 2ª opção, menos volátil |
| MCL (crude) | $1.00 | Drawdown menor (ICT mostrou -$788) |
| MGC (gold) | $1.00 | Bom com volume bars |
| NQ full | $5.00 | Contas $150K+ |

### Timeframes: 1-min domina (ORB, ICT, reversão). 3-5 min p/ scalping EMA/VWAP.

### Horários:
- **9:30-11:30 ET** = favorito (maior volume/range)
- **14:00-16:00 ET** = 2ª janela
- Flatten HARDCODED antes 16:59 ET (bug de timezone no "Exit on Session Close")

### Gestão de risco (templates da comunidade):
- Stop MNQ scalping: 10-20 ticks ($20-40)
- Auto-liquidação em 70-80% do limite real da firma
- Máx 3 trades/dia = regra defensiva comum entre aprovados
- Apex 4.0 (desde 01/03/2026): TODA ordem exige SL+TP anexados

---

## 2. INFRAESTRUTURA / VPS

### VPS recomendadas (ranking comunidade):
| Provedor | Preço/mês | Destaque |
|---|---|---|
| **QuantVPS** | $59.99 | Mais citado, 0.52ms ao CME, suporte NT8 24/7 |
| **FinTechVPS** | $50 | Rithmic pré-instalado, Chicago |
| **TradoxVPS** | $39 | Ryzen 9950X, DDR5, Chicago |
| ❌ AWS/Azure/GCP | — | **Rithmic BLOQUEIA** (nosso problema confirmado) |

### OS: Windows Server 2022 (consenso absoluto)
- Melhor que Win 10/11 (sem Cortana/Superfetch/telemetria)
- Hierarquia: Server 2022 > Server 2019 > Win 10 Pro >> Win 11 (evitar)

### Configurações obrigatórias:
```powershell
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /change monitor-timeout-ac 0
powercfg /setactive SCHEME_MIN
```
- Desabilitar Windows Defender (ou NT8 como exceção) — causa spike de CPU
- Sincronizar relógio (Rithmic cai se relógio desviado)
- Windows Update: "Download but do not auto-install", agendar fim de semana
- NT8: `Restore prior state on startup` ATIVADO; limite 5-10k barras

### Problema de desconexão do NT8 ("Panic" mode):
NT8 para de tentar reconectar e loga `(Panic) Unable to re-establish connection`.
Soluções:
- **Ninja Watchdog** ($49/mês, 30d grátis): relança NT8, reconecta, reativa estratégia
- **CrossTrade XT**: detecta "feed congelado silencioso" (Connected mas dados pararam)
- **PowerShell DIY** (grátis): script que monitora processo e relança via Task Scheduler

### Rithmic vs alternativas:
| Feed | Estabilidade |
|---|---|
| **Rithmic** | Excelente (padrão prop firms) |
| Continuum (CQG) | Boa |
| Tradovate | Ruim (disconnects, token expira) |

Endpoint Apex: `Rithmic01Chicago`, porta 64100 TCP.

### Hardware: single-core importa mais que nº de cores. AMD Ryzen > Intel Xeon E5
(múltiplos relatos de NT8 lento com Xeon). Custo profissional 24/7: $100-120/mês.

---

## 3. APEX — Detalhes

### Apex 4.0 (desde 01/03/2026):
| Regra | Antes | Apex 4.0 |
|---|---|---|
| Consistência | 30% lucro máx/dia | **50%** do lucro total máx em 1 dia |
| Mín entre pagamentos | 8 dias | 5 dias |
| Mín dias na eval | 7 dias | **Removido** (pode passar em 1 sessão) |
| Ordens sem SL+TP | Aceitas | **Rejeitadas** |
| DCA (médio) | Zona cinza | **Banido** |

### Trailing Drawdown (o que mais mata bots):
- **EOD Trailing** (amigável): atualiza 1x/dia às 16:59 ET pelo saldo final.
  Ignora flutuação intraday. Trava em: inicial + DD + $100.
- **Intraday Trailing** (perigoso): rastreia maior equity NÃO realizado tick a tick.
  Ex: bot vai a +$800 unrealized → threshold sobe $800 → fecha em +$200 → você
  ganhou $200 mas perdeu $800 de cushion PERMANENTE.

### Tamanho de conta ideal:
| Conta | DD | DLL | Meta | Custo |
|---|---|---|---|---|
| $25K | **$1.000** | $500 | $1.500 | ~$15/mês |
| **$50K** | $2.000 | $1.000 | $3.000 | ~$37/mês |
| $100K | $3.000 | $1.500 | $6.000 | ~$57/mês |

- **$25K = comunidade considera RUIM** (DLL $500 muito apertado)
- **$50K = melhor custo-benefício** (recomendação da maioria)
- Escalar: múltiplos $50K em paralelo (até 20 PAs) > 1x $150K concentrado

> ⚠️ **ATENÇÃO — discrepância no nosso setup:** a conta $25K Intraday tem **DD=$1.000,
> não $1.500**. O $1.500 é a META de lucro. Nosso backtest usa DD=$1.500 (mais
> permissivo que a conta real). Confirmar parâmetros reais no dashboard Apex.

### Taxa de aprovação real:
- Pass rate Apex auto-declarado: 15-20%
- Pass rate setor prop (independente): 5-10%
- Pass rate com bot verificado independente: **não existe**
- Reddit: 70% dos posts de 2025 reportam aprovação com bot em $50K-$150K

---

## 4. ERROS MAIS COMUNS (que matam bots)

1. **OnEachTick sem testar consistência** — backtest 1x/barra, live 100x/barra → re-entradas
   - Regra de ouro: usar **OnBarClose** (o nosso usa ✅)
2. **Slippage=0 no backtest** — irrealista; usar 2-4 ticks MNQ (ver doc de melhorias)
3. **Sem auto-flatten hardcoded** — bug de timezone fecha às 23h em vez de 16:59
4. **Ordens fantasma** — variáveis não inicializadas + latência (corrigimos c/ buffer ✅)
5. **Re-entrada em loop** — leva stop, condição ainda true, entra de novo
6. **Overfitting** — 80% WR no backtest → 30-40% ao vivo. Solução: OOS + walk-forward (fazemos ✅)
7. **Bug de reconexão com posição aberta** — variáveis resetam, "Wait Until Flat" não
   gerencia a posição (corrigimos c/ RECOVERY + anti-reset ✅)

---

## 5. COMUNIDADES E RECURSOS

### Reddit:
- r/algotrading (1.87M) — NQ/MNQ muito discutido
- r/ApexTraderFunding (4K) — regras + bots em tempo real
- r/FuturesTrading (190K), r/ninjatrader (7.4K)

### Discord:
- TradeSaber NT8 (~9.5K) — mais ativo p/ NinjaScript open-source
- Apex oficial (~24K), Topstep oficial (~181K)

### Fórum oficial: forum.ninjatrader.com/strategy-development (mais ativo)

### GitHub (código real):
- MattWinkley/NinjaScripts — `PropFirmRiskControl`, `VWAPPullbackStrategy`, `ATRStopStrategy`
- MicroTrendsLtd/NinjaTrader8 — framework semi/full-auto

### Comunidade BR 🇧🇷:
- **NeoTraderBot** (neotraderbot.com) — única BR estruturada, parceiro oficial NT,
  docs NinjaScript em PT, pack específico p/ Apex, cursos no Hotmart.

---

## 📊 RESUMO: NÓS vs COMUNIDADE

### ✅ Acertando:
- Reversão PDH/PDL = estratégia validada
- MNQ 1-min = combinação padrão
- Ratio 4.8:1 (60/12.5) = melhor que 4:1 recomendado
- OOS testing rigoroso = poucos fazem
- Stop servidor + trailing sintético = prática avançada
- Sunday/Monday range = diferencial não documentado em outros bots
- OnBarClose, fixes de fantasma/reconexão/anti-reset = problemas que a maioria sofre e não resolve

### ⚠️ Gaps (ver docs/melhorias-sugeridas.md):
- Slippage 0 no backtest → noturna desaba sob slippage realista (descoberta 23/06)
- Sem news filter (FOMC/CPI/NFP)
- VPS doméstica (Win 11) vs QuantVPS/FinTechVPS
- MaxTradesDia ilimitado
- Conta $25K (comunidade prefere $50K)
- Risco jurídico real na PA da Apex (automação proibida oficialmente)
