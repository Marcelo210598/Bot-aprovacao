# Estratégia 25 — Bot Funded 25K (conta já aprovada)

Bot **pós-aprovação** pra operar a conta funded Apex **25K Intraday** com foco em
**SAQUE CONSISTENTE** (≠ bot de aprovação, que corre atrás da meta rápido).

> "O objetivo não é apenas operar. O objetivo é transformar conhecimento em **saques consistentes**." — material Apex / Nômade

## 🎯 Filosofia
- **Não** correr atrás de lucro grande. Fazer um **alvo modesto por dia e parar**.
- Distribuir o lucro entre os dias → mantém a **regra de consistência (30%)** e acumula **dias qualificados**.
- Proteger o drawdown a todo custo (violou = conta queimada = custo de nova conta).
- Objetivo de cada conta: **6 saques de $1.000 = $6.000**, depois encerra e reinicia.

## 📋 Regras Apex 25K (fonte: PDF oficial Nômade, contas 2026)

| Regra | Valor |
|---|---|
| Drawdown (Intraday, tempo real) | **$1.500** |
| Lucro mínimo/dia (dia qualificado) | **$100** |
| Gordura p/ saque (safety net) | **$1.600** → precisa bater **$26.600** |
| Trailing trava em | initial + gordura = $26.600 (piso final $25.100) |
| Dias com lucro p/ sacar | **≥ 5** (cada um ≥ $100) |
| Consistência | maior dia ≤ **30%** do lucro total |
| Saques por conta | **6 × $1.000** = $6.000 |

## 🧮 Modelo do backtest (`run_funded_25k.py`)
- **Motor de entrada:** mesmo validado (reversão na máx/mín do dia anterior + range do
  domingo à noite na segunda, tol 20t, maxDist 15pt, TP 60 / SL 12.5 / BE / trail).
- **Novo — gestão diária:** `alvo diário` (para de abrir trade ao atingir) + `stop diário`.
- **Novo — máquina da conta funded:** drawdown intraday trailing $1.500 (segue equity
  pico, trava em $26.600), conta dias qualificados, consistência 30%, saca $1.000 quando
  elegível, encerra/reinicia em violação ou após 6 saques.
- **Saída:** quantos saques/ano, contas violadas vs completas, dias por saque, renda $/ano.

## ✅ Config ADOTADA v3 (após refinamento 15/06 + DNA do aprovação)
```
Conta:       Apex 25K INTRADAY (DD $1.500 trailing)
Contratos:   2 MNQ  →  3 MNQ depois que trava a gordura ($26.600)  [escalonamento]
Alvo/dia:    $400 (escala p/ $600 na fase 2) — para de abrir ao atingir
Stop/dia:    $300 (escala p/ $450 na fase 2)
Entrada:     reversão na máx/mín do dia anterior + range do domingo à noite (segunda)
TP/SL:       60pt / 12.5pt | tol 20t | maxDist 15pt
Breakeven:   gatilho +1.5pt → trava +1.0pt  (chave do refino)
Trailing:    1.75pt
Saque:       6× $1.000, gordura $26.600, ≥8 dias com lucro, consistência 30%
```
**Resultado (1 ano, backtest inteiro):** **19 saques/ano (~$19k ≈ R$104k)**, **WR 75,9%**
(1187 verdes / 376 vermelhos), **78,8% dias verdes**, **PF 1.91**, **0 violação**.
OOS robusto: **0 violação nas duas metades** (PF 1.89 / 1.94).

## 🛡️ Proteção — 4 camadas (a estratégia TEM stop loss)
1. **SL por trade: 12.5pt** (~$50 a 2 MNQ) — ordem no servidor, protege intrabar. 1ª linha.
2. **Breakeven: +1.5pt → trava +1.0pt** — trade andou 1.5pt, stop vira lucro garantido.
3. **Stop diário: $300** (escala na fase 2) — perdeu isso no dia, para de operar.
4. **DD da conta: $1.500** (regra Apex) — proteção final. Nenhum trade fica solto.

## ⚙️ Como o bot decide escalonar (gatilho objetivo p/ o .cs)
Rastreia o **pico de equity da conta** (high-water mark, inclui lucro aberto):
- `eq_peak < $26.600` → fase 1 (DD ainda persegue) → **2 MNQ**
- `eq_peak ≥ $26.600` → gordura travada (piso fixo $25.100, há buffer) → **3 MNQ**
Trava na fase 2 até a conta encerrar (6 saques) ou ser queimada → conta nova volta a 2 MNQ.

### Evolução do refino
| Versão | Config | Saques | WR | PF | Viol |
|---|---|---|---|---|---|
| v0 | 2 MNQ, alvo $250, BE padrão | 12 | 68.4% | 1.65 | 0 |
| v1 | + breakeven antecipado 2.0/1.0 | 13 | 73.7% | 1.81 | 0 |
| v2 | + alvo $400 + escalonar 2→3 MNQ | 18 | 74.4% | 1.86 | 0 |
| **v3** | **+ breakeven 1.5/1.0** | **19** | **75.9%** | **1.91** | **0** |

### Testes que NÃO foram adotados (e por quê)
- **Horário (pular abertura 9h30-10h):** sobe WR p/ 76-78% mas corta 4 saques. Trade-off ruim.
- **Escalonamento em 2 degraus (3→4 MNQ):** não funciona — a conta saca em $26.600 e nunca acumula até o 2º limiar ($28k+). O 3º degrau nunca ativa.
- **Filtro de tendência (SMA):** corta ~50% dos saques pra subir WR marginal. Conflita com mean-reversion. Descartado.

## 🔬 O que o refinamento ensinou (5 baterias)
1. **Filtros de setup:** apertar maxDist sobe WR por trade mas baixa WR por dia (consistência) e renda. maxDist 15 fica.
2. **TP/trailing:** TP raramente é tocado; alargar trailing PIORA (devolve lucro, viola). Trail 1.75 fica.
3. **Dias mínimos:** 5/8/10 = idêntico. Regra Apex de 8 dias **não morde** (acumula dias de sobra). Usado 8 p/ conformidade.
4. **EOD vs Intraday:** EOD (DD $1.000) violou 4×/ano; Intraday (DD $1.500) = 0. **Intraday é mais seguro aqui.**
5. **Ganho/perda (chave):** reduzir o stop melhora g/p MAS derruba WR, PF e saques (otimiza métrica errada). O caminho certo é o **breakeven antecipado** (BE 2.0/1.0): sobe o acerto pra 73,7% e o PF pra 1.81. Variante agressiva validada: BE 1.5/0.75 (WR 75,5%, PF 1.86) — testar no forward.
6. **DNA do aprovação (agressividade):** stop diário não morde (300=750); afrouxar o **alvo p/ $400** ganha saques (deixa dias verdes renderem); **escalonar contratos 2→3 MNQ só após travar a gordura** captura o upside do aprovação SEM o risco da fase inicial — +5 saques, OOS 0/0. Acima de 3 (4-6 MNQ) viola no OOS (DD é fixo $1.500, não escala).

> **g/p (ganho médio/perda média) < 1 NÃO é defeito** — é a assinatura de sistema de alto acerto. A métrica que mede "ganho mais do que perco" é o **Profit Factor** (1.81 = ganho $1,81 p/ cada $1 perdido).

## ⚠️ Premissas a confirmar (Andersson/Apex)
- Nº mínimo de dias de trade pro 1º saque (usei 5 dias com lucro ≥$100; Apex às vezes
  exige 8 dias totais — ajustável no script).
- Base exata da consistência 30% (usei lucro líquido acumulado da conta).
- Trava do trailing intraday (usei initial + gordura $1.600).
- **Backtest ≠ ao vivo.** Forward test no Sim101 obrigatório antes de conta real.
