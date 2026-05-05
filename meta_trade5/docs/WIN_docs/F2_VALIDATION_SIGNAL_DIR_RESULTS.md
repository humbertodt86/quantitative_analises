# F2 Validation: PA_SIGNAL_DIR Variants — Resultados

**Data:** 2026-05-03
**Metodologia:** Tick-level backtest (41M ticks OOS)
**Período OOS:** Mar 30 — Abr 29, 2026

---

## Resultados OOS

| Rank | Variante | IS PnL | IS WR | OOS PnL | OOS N | OOS WR | Stress (C=60) | Overfit |
|------|----------|--------|-------|---------|-------|--------|---------------|---------|
| 1 | **S0_Z30_R05** | +2,823 | 87.7% | **+261** | 34 | 47.1% | -759 | 10.8x |
| 2 | **S0_Z25_R05** | +2,828 | 87.5% | **+261** | 34 | 47.1% | -759 | 10.8x |
| 3 | **S10_Z30_R05** | +2,833 | 87.3% | **+261** | 34 | 47.1% | -759 | 10.9x |
| 4 | **S0_Z999_R05** | +2,818 | 87.8% | **+261** | 34 | 47.1% | -759 | 10.8x |
| 5 | **S5_Z30_R05** | +2,823 | 87.7% | **+261** | 34 | 47.1% | -759 | 10.8x |
| 6 | **S10_Z25_R05** | +2,838 | 87.1% | **+261** | 34 | 47.1% | -759 | 10.9x |
| 7 | **S0_Z30_R03** | +1,059 | 87.7% | **+236** | 35 | 48.6% | -814 | 4.5x |
| 8 | **S0_Z25_R03** | +1,064 | 87.5% | **+236** | 35 | 48.6% | -814 | 4.5x |
| 9 | **S10_Z30_R03** | +1,069 | 87.3% | **+236** | 35 | 48.6% | -814 | 4.5x |
| 10 | **S5_Z30_R03** | +1,059 | 87.7% | **+236** | 35 | 48.6% | -814 | 4.5x |

**TODAS as 10 variantes com OOS POSITIVO.** ✅

---

## Análise

### ✅ O que melhorou?

1. **De negativo para positivo:** Versão anterior (DEPRECATED) tinha OOS = -5,765. Nova versão = **+261**.
2. **Delta de +6,026 pts** na melhor config.
3. **WR OOS:** 47-48% (baixo, mas lucrativo com R:R favorável).

### ⚠️ Problemas identificados

1. **Overfit alto:** 4.5x a 10.9x. IS é muito melhor que OOS.
2. **Stress negativo:** Com C=60, TODOS viram negativo (-759 a -814).
3. **Trade count baixo:** 34-35 trades OOS — limite de significância estatística.
4. **IS WR muito alto:** 87% em IS sugere que algo está errado no cálculo ou o F1 estava muito otimizado.

### 🔍 Por que IS WR = 87%?

Isso é **suspeito**. Um WR de 87% em IS com TP=4x e SL=4x não é realista. Possíveis causas:
- O F1 usou simulação OHLC que superestima winners (high/low touch)
- Os filtros de ATR 400-600 selecionaram apenas os melhores períodos
- O regime=trend em IS pode ter sido mais favorável que OOS

---

## Conclusão

**A otimização do sinal V8.0 funcionou parcialmente:**
- ✅ Conseguimos virar de negativo para positivo OOS
- ✅ Identificamos parâmetros ótimos (S=0, Z=3.0, R=0.5)
- ⚠️ Overfit alto — necessita validação mais rigorosa
- ❌ Stress test falhou (C=60 = negativo)

**Recomendação:** Não adicionar ao ensemble ainda. Precisamos:
1. Investigar o WR=87% em IS (possível bug na simulação)
2. Rodar F3 com BE/HP/CD variados para melhorar robustez
3. Verificar se há algum dia/horário dominando o PnL
4. Considerar que C=30 pode ser otimista — o spread real no WIN pode ser maior

---

*Gerado automaticamente em 2026-05-03*
