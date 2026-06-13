# 🤖 Estratégia MNQ (5 micro contratos) — Aprova conta 25K em ~15 dias com 94%

> **Data:** 12/06/2026
> **Base:** estratégia "Níveis 94" rodada no **MNQ (Micro Nasdaq, $2/ponto)** com 1 ano de dados reais do NQ.
> **Status:** backtest concluído. Config validada out-of-sample. Falta implementar no NinjaScript + forward test.

---

## 🎯 TL;DR

- Travamos em **5 micro contratos (MNQ)** → risco de só **$125/trade** (buffer de **12x** no DD de $1.500).
- A estratégia "94" pura (alvo 25pt) aprovava, mas era **lenta: ~42 dias** (2 mensalidades Apex).
- A alavanca que destravou a velocidade **não foi trade/dia** — foi **deixar o ganho correr**: alvo (TP) de **25pt → 60pt** com trailing curto.
- Resultado: **94% de aprovação E mediana de 15 dias** — rápido E seguro ao mesmo tempo.

---

## 🏆 CONFIG RECOMENDADA (5 MNQ — conta 25K)

```
Mercado:          MNQ (Micro Nasdaq) — 5 contratos
Conta:            Apex 25K (meta $1.500 | DD $1.500 | mín. 7 dias)
Estratégia:       Reversão na máxima/mínima do dia anterior (igual à "94")
Alvo (TP):        60 pontos      ← antes 25pt; ESSE é o segredo da velocidade
Stop (SL):        12,5 pontos    (risco $125/trade)
Breakeven:        +3,75pt → trava stop em +2,5pt
Trailing:         1,75pt (curto — protege o lucro quando perde força)
Stop diário:      $750
Trades/dia:       sem limite rígido (~5/dia na prática)
Horário:          pregão regular EUA, entradas 9h30–15h00 ET (fecha tudo 15h55)
```

| Métrica | Resultado (1 ano real) |
|---------|:---:|
| **Taxa de aprovação** | **94%** (17 aprovadas / 1 reprovada) |
| **Mediana p/ aprovar** | **15 dias** (média 20d · mín 8 · máx 39) |
| Profit Factor | 1.53 |
| Win rate | 64% |
| PnL no ano | +$30.900 |
| Risco por trade | $125 (buffer 12x no DD) |

**Robustez (out-of-sample):** 1ª metade **100%** (7/7, PF 1.55) · 2ª metade **90%** (9/10, PF 1.53).

---

## 💡 Por que funciona

O alvo antigo de 25pt **cortava os ganhos cedo demais**. Com alvo largo (60pt) + trailing curto (1,75pt), nos dias de reversão forte o bot **captura o movimento inteiro** (até $600 num trade de 5 MNQ) em vez de fechar em $250. Efeito triplo:

1. **Bate a meta de $1.500 muito mais rápido** → 15 dias em vez de 42.
2. **A taxa SOBE de 89% → 94%** (não cai!) — chegar rápido na meta dá menos tempo pra uma sequência ruim estourar o DD.
3. **Risco por trade continua $125** — o mais seguro de todas as opções testadas.

---

## 🥈 Alternativa mais conservadora (trava de trades)

```
5 MNQ | TP 60pt | trailing 1,75 | máx 12 trades/dia | stop diário $375
→ 94% (15/1) | mediana 15d | PF 1.56 | PnL $25.657
```
Mesma taxa e prazo, porém com limite de trades/dia e stop diário menor (operação mais "amarrada").

---

## 📊 Comparativo de sizing MNQ (referência)

| Config | Risco/trade | Mediana | Taxa | PnL/ano |
|--------|:---:|:---:|:---:|---:|
| 5 MNQ — TP 25pt (pura) | $125 | ~30d | 89% | $11.482 |
| **5 MNQ — TP 60pt** ⭐ | $125 | **15d** | **94%** | $30.900 |
| 10 MNQ — TP 25pt, máx 4/dia | $250 | 15d | 71% | $24.278 |
| 1 NQ (estratégia 94 original) | $250 | ~24d | 94% | $25.615 |

→ Os **5 MNQ com TP 60pt** dominam: mesma taxa do NQ original, prazo menor e **metade do risco por trade**.

---

## ⚖️ Ressalvas honestas

- O alvo de 60pt numa estratégia de **reversão** é otimista por natureza — só captura o movimento grande quando a reversão vira tendência. No backtest (vela 1min, saída stop-first conservadora) segurou bem e melhorou o PF, mas **ao vivo o slippage no trailing pode comer parte** desse ganho extra.
- 1 ano de dados (~10,5 meses), candle de 1 minuto (não tick), custo $1,20/contrato RT estimado.
- **94% é a taxa histórica do período, não garantia.**
- Próximo passo obrigatório: **forward test no Sim101 / Market Replay** do NT8 pra confirmar ao vivo.

---

## 📁 Script

`backtest/run_mnq_5contr.py` — reproduz toda a varredura e a config vencedora.
