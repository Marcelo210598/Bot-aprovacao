# 🪜 Trailing 1,75pt — veredito definitivo (NÃO re-testar)

> **Data: 25/06/2026.** Andersson + Marcelo sentiram que o trailing de 1,75pt sai cedo
> ("a vela dá uma variada mínima, pega a merreca e depois sobe/desce forte"). Investigamos
> a fundo com 3 backtests independentes (300 mil candles, conta 25K, modo DOM-NOITE).
> **Conclusão: o 1,75pt é o ÓTIMO. Afrouxar piora, comprovado de 3 jeitos.**
>
> ⚠️ Se a dúvida voltar daqui a uns meses, **lê este doc antes de re-testar** — já foi medido.

---

## A intuição (natural, mas errada pelos números)
"O trailing aperta no primeiro recuo e perde os trades que iam correr forte." Verdade que dói
de ver — mas é **minoria**. A estratégia é reversão (scalp): a **maioria** dos trades anda pouco.
O trailing apertado captura esse lucro pequeno-médio de forma confiável → é o que sustenta o WR ~69%.

## Os 3 testes (todos rejeitados)

### 1. Trailing uniforme mais largo — `run_trailing_fino.py` / `run_trailing_sweep.py`
Varredura de 1,75 → 12pt. Degradação **monotônica**: cada ponto a mais custa PnL e aprovação.

| trail | aprovação | PnL | vs baseline |
|---|---|---|---|
| **1,75** ⭐ | 100% (21/21) | $38.932 | — |
| 2,0 | 100% (20/20) | $37.080 | −5% |
| 3,0 | 100% (18/18) | $32.680 | −16% |
| 5,0 | 100% (15/15) | $26.433 | −32% |

→ Se um dia *tiver* que afrouxar (preferência operacional), **2,0pt** é o único defensável (−5%). Mas não melhora.

### 2. Trailing escalonado ("cavalgar a alta") — `run_trailing_escalonado.py`
Aperta no começo, alarga depois de X pt de lucro. Melhor config (P30/W6): **maxWin idêntico ao
baseline ($594) e MESMO nº de big wins (108)**. Ou seja, **não cavalgou nada a mais** — e o PnL caiu.
Motivo: os runners de verdade já batem o **alvo de 60pt**; o trailing nunca foi o limitador deles.

### 3. Saída parcial / scale-out — `run_saida_parcial.py`
Parte da posição sai no trailing 1,75, parte vira runner até o alvo. **Esse capturou runners de
verdade** (93 alvos batidos = +$11.048 dos runners!). Mesmo assim o PnL total **caiu −$2.876** no
melhor caso (4 scalp + 1 runner) e perdeu aprovações.

| config | aprovação | $ dos runners | PnL total |
|---|---|---|---|
| **baseline 5× trail1,75** ⭐ | 100% (21/21) | — | $38.932 |
| 4 scalp + 1 runner→alvo | 100% (18/18) | +$11.048 | $34.144 |
| 4 scalp + 1 runner(trailW6) | 100% (19/19) | +$1.663 | $36.056 |

**Por quê:** o runner ganha nos poucos casos que explodem, mas nas muitas vezes que **não** vai ao
alvo, volta e sai no breakeven (+2,5pt) — desistindo do lucro intermediário (5-30pt) que o trailing
apertado teria travado. A conta líquida é negativa.

## Conclusão
| Abordagem | Veredito |
|---|---|
| Trailing uniforme largo | ❌ pior (monotônico) |
| Trailing escalonado | ❌ não pega runner a mais |
| Saída parcial | ❌ pega runner (+$11k) mas perde mais no meio |

**Razão de fundo:** estratégia de WR alto vive do lucro pequeno-médio garantido. Trocar o grosso
confiável pelos poucos runners não fecha — de 3 jeitos. O **alvo de 60pt já é o "deixa correr"**.
**Mantido: trailing 1,75pt.**
