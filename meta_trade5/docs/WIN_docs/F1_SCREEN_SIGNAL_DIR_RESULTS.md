# F1 Screening: PA_SIGNAL_DIR Variants — Resultados

**Data:** 2026-05-03
**Grid:** 120 variantes × 2,464 combos = 295,680 combos avaliados
**Período IS:** Jan 2 — Mar 27, 2026

---

## Top 5 Resultados F1 (IS)

| Rank | Variante | TP | SL | ATR Min | ATR Max | Trades | Net IS | WR |
|------|----------|----|----|---------|---------|--------|--------|-----|
| 1 | PA_SIGNAL_DIR_S0_Z30_R05 | 4.0 | 4.0 | 400 | 600 | 207 | **+47,378** | 59.4% |
| 2 | PA_SIGNAL_DIR_S0_Z30_R03 | 4.0 | 4.0 | 400 | 600 | 212 | **+47,043** | 59.0% |
| 3 | PA_SIGNAL_DIR_S0_Z25_R05 | 4.0 | 4.0 | 400 | 600 | 204 | **+46,801** | 59.8% |
| 4 | PA_SIGNAL_DIR_S0_Z25_R03 | 4.0 | 4.0 | 400 | 600 | 209 | **+46,466** | 59.3% |
| 5 | PA_SIGNAL_DIR_S0_Z9990_R05 | 4.0 | 4.0 | 400 | 600 | 213 | **+46,258** | 58.7% |

**Observação:** TODOS os top 5 usam **S=0** (slope mínimo = 0, apenas exige que EMA20 esteja inclinada na direção correta), **Z>=2.5** (z-score relaxado ou desligado), e **R<=0.5** (range ratio baixo).

---

## Análise de Sensibilidade (Top 100 resultados)

### Slope (S) — Inércia da EMA20

| Slope Min | Ocorrências no Top 100 | % |
|-----------|------------------------|---|
| 0 | 48 | 48% |
| 5 | 18 | 18% |
| 10 | 30 | 30% |
| 20 | 4 | 4% |

**Conclusão:** Slope mínimo **0** domina. Exigir slope > 5, 10 ou 20 reduz a performance. O filtro de "EMA20 inclinada na direção do trade" (S>0) já é suficiente — não precisa exigir inclinação forte.

### Z-Score (Z) — Exaustão

| Z-Score Max | Ocorrências | % |
|-------------|-------------|---|
| 1.0 | 0 | 0% |
| 1.5 | 0 | 0% |
| 2.0 | 0 | 0% |
| 2.5 | 41 | 41% |
| 3.0 | 36 | 36% |
| 999 (off) | 23 | 23% |

**Conclusão:** Z-Score restritivo (1.0–2.0) **não aparece no top 100**. Os melhores resultados usam Z>=2.5 ou desligado. Isso contradiz a hipótese inicial de que z-score < 2.0 seria ideal.

**Por que Z restritivo piora?**
- Em tendências fortes, o preço fica "esticado" por longos períodos
- Z < 2.0 bloqueia entradas justamente quando o momentum é mais forte
- O mercado "sobe mais do que deveria" em tendência (momentum behavioral)

### Range Ratio (R) — Volume/Volatilidade

| Range Min | Ocorrências | % |
|-----------|-------------|---|
| 0.3 | 51 | 51% |
| 0.5 | 48 | 48% |
| 0.8 | 1 | 1% |
| 1.0 | 0 | 0% |
| 1.5 | 0 | 0% |

**Conclusão:** Range_ratio **baixo** (0.3–0.5) é melhor. O V8.0 original usava R=0.8, que é muito restritivo e elimina a maioria das oportunidades.

---

## Descoberta Surpreendente

### O V8.0 Original Estava Muito Restritivo

O V8.0 implementado usava:
- S=0 ✅ (correto)
- Z=2.0 ❌ (muito restritivo — top 100 usa Z>=2.5)
- R=0.8 ❌ (muito restritivo — top 100 usa R<=0.5)

**Resultado:** O V8.0 filtrava demais, perdendo as melhores oportunidades.

---

## Melhor Config Encontrada

**Variante:** PA_SIGNAL_DIR_S0_Z30_R05
**Parâmetros do sinal:**
- Slope mínimo: 0 (qualquer inclinação positiva/negativa)
- Z-Score máximo: 3.0 (relativo — permite preço mais esticado)
- Range ratio mínimo: 0.5 (candle com metade do range médio)

**Parâmetros de risco (F1):**
- TP: 4.0x ATR
- SL: 4.0x ATR
- ATR Min: 400
- ATR Max: 600

**Resultados IS:**
- Net: +47,378
- Trades: 207
- WR: 59.4%

---

## Próximos Passos

1. **Rodar F2** nas top 30 variantes para validar com ticks reais
2. **Verificar overfit:** O F1 é OHLC e otimizado — precisamos ver se os resultados se mantêm no F2 (ticks reais + custo real)
3. **Ajustar o V8.0 base:** Com base nos resultados F1, atualizar o `PA_SIGNAL_DIR` para usar Z=3.0 e R=0.5 como defaults

---

*Gerado automaticamente em 2026-05-03*
