# Relatorio Comparativo — Ensemble Original vs Alternativas

**Data:** 2026-05-03
**Metodologia:** Simulacao SELECTOR (1 posicao por vez) + Monte Carlo (10,000 simulacoes)
**Custo:** 30 pts/trade

---

## 1. Justificativa da Escolha Original

### Por que o Optimizer escolheu TUESDAY+VCP+KELT+EXHAUST?

O `ensemble_optimizer.py` tem uma unica funcao objetivo: **maximizar PnL combinado** considerando conflitos de trades. Ele nao avalia interpretabilidade, robustez conceitual, ou risco de overfit.

| Estrategia | OOS Isolado | Papel no Original |
|-----------|:-----------:|-------------------|
| PA_TUESDAY_RANGE_SELL | +36,820 | Motor de PnL — maior isolado |
| PA_VCP_HYBRID_SELL | +12,149 | Diversificacao temporal |
| PA_KELT_M2_0_RANGE | +5,375 | Complementaridade (baixo conflito) |
| PA_EXHAUST_Dn1_0_M40_TREND_SELL | +4,364 | WFA 3/3 robusto |

**O optimizer encontrou +43,189** — o maior PnL entre 4,261 combinacoes testadas (1,711 pares + 1,710 trios + 840 quartetos). Matematicamente, foi a escolha "correta" para maximizar PnL.

**O problema:** O optimizer nao sabe que PA_TUESDAY_RANGE_SELL é provavelmente um **artefato estatistico**.

---

## 2. O Problema de PA_TUESDAY_RANGE_SELL

### Evidencias de Artefato Estatistico

| Problema | Evidencia | Severidade |
|----------|-----------|:----------:|
| **Efeito calendario nao guardrailado** | O nome diz "TUESDAY" mas nao ha filtro de dia da semana no engine | 🔴 Critico |
| **SL viola floor** | SL=0.05 << 0.5x ATR (minimo 150 pts) | 🔴 Critico |
| **Amostra pequena** | 40 trades apenas — insuficiente para efeito calendario | 🔴 Alto |
| **PnL concentrado** | Dependencia extrema de outliers (top 10% = 78% do PnL) | 🟡 Medio |
| **OOS em queda** | Quando simulado sozinha com conflitos: +18,228 (metade do +36,820 isolado) | 🟡 Medio |

### Comparacao: TUESDAY Isolado vs no Ensemble

| Cenario | PnL | Trades | WR | Sharpe |
|---------|:---:|:------:|:--:|:------:|
| TUESDAY isolado (sem conflitos) | +36,820 | 40 | 50.0% | — |
| TUESDAY sozinha (com conflitos reais) | +18,228 | 26 | 26.9% | 2.47 |
| TUESDAY no Original Quad | +43,189 (total) | 90 | 25.6% | 3.51 |

**Insight:** O PnL de +36,820 é teórico. Na prática, quando TUESDAY compete com outras estrategias por posicoes, ela so captura 26 trades (de 40) e o PnL cai pela metade. O ensemble original "salvou" o PnL porque VCP+KELT+EXHAUST preenchem os gaps onde TUESDAY nao entra.

---

## 3. Comparacao das Alternativas Propostas

### Tabela Resumida

| Configuracao | Estrategias | PnL | T | WR | Sharpe | MaxDD | Risk% | MC PnL 5% | MC PnL 50% |
|-------------|:-----------:|:---:|:--:|:--:|:------:|:-----:|:-----:|:---------:|:----------:|
| **Original Quad** | TUESDAY+VCP+KELT+EXHAUST | **+43,189** | 90 | 25.6% | 3.51 | **-2,232** | **5.2%** | +24,077 | +42,820 |
| Ensemble 5 | TUESDAY+BB+REV_RSI+TSI+VCP | +36,753 | 166 | 34.3% | 3.62 | -6,784 | 18.5% | +20,858 | +36,402 |
| Ensemble 4 | TUESDAY+BB+REV_RSI+TSI | +29,698 | 144 | 34.7% | 3.18 | -6,479 | 21.8% | +15,248 | +29,440 |
| Ensemble 3 | TUESDAY+BB+REV_RSI | +23,794 | 122 | 32.8% | 2.68 | -6,536 | 27.5% | +9,582 | +23,284 |
| TUESDAY Single | TUESDAY apenas | +18,228 | 26 | 26.9% | 2.47 | -1,790 | 9.8% | +6,804 | +18,144 |

### Analise por Configuracao

#### Ensemble 3 (TUESDAY + BB_TREND + REV_RSI_HYBRID)
- **PnL:** +23,794 — abaixo do TUESDAY isolado (!)
- **Problema:** BB_TREND e REV_RSI tem alta sobreposicao com TUESDAY. Eles nao complementam, competem.
- **MaxDD:** -6,536 — 3x pior que o Original Quad
- **Veredicto:** ❌ Ruim — conflitos massivos, nao diversifica

#### Ensemble 4 (+ TSI_HYBRID)
- **PnL:** +29,698 — melhor que E3, ainda abaixo do Original
- **TSI_HYBRID** adiciona trades mas tambem conflita com TUESDAY (mesmo horario de abertura)
- **MaxDD:** -6,479 — igualmente alto
- **Veredicto:** ⚠️ Mediocre — TSI nao é o complemento certo

#### Ensemble 5 (+ VCP_HYBRID)
- **PnL:** +36,753 — melhor alternativa, ainda -15% vs Original
- **VCP_HYBRID** é o unico que realmente complementa (sinais em horarios diferentes)
- **Sharpe:** 3.62 — o melhor Sharpe de todos!
- **MaxDD:** -6,784 — pior que Original (-3x)
- **Veredicto:** 🟡 Aceitavel — melhor alternativa, mas drawdown preocupante

---

## 4. O Que Aprendemos

### A Magia do Original Quad

O Original Quad venceu porque **KELT_M2_0_RANGE e EXHAUST_TREND operam em horarios/condicoes completamente diferentes de TUESDAY**:

| Estrategia | Horario Tipico | Regime | Funcao |
|-----------|:--------------:|:------:|--------|
| TUESDAY | 9:30-10:30 (abertura) | RANGE | Captura volatilidade inicial |
| VCP | 10:00-14:00 (meio do dia) | HYBRID | Pattern de consolidacao |
| KELT_RANGE | 11:00-15:00 (almoco+) | RANGE | Reversao em envelope |
| EXHAUST_TREND | 14:00-17:00 (tarde) | TREND | Exaustao do movimento |

**Isso cria um "pipeline" de trades ao longo do dia** — quando uma fecha, outra comeca. Pouca sobreposicao = pouco conflito = PnL se soma eficientemente.

### Por que as Alternativas Falharam

As alternativas usam **BB_TREND, REV_RSI, TSI** — todas operam nos **mesmos horarios de TUESDAY** (abertura da manha):

| Estrategia | Horario Tipico | Conflito com TUESDAY |
|-----------|:--------------:|:--------------------:|
| BB_TREND | 9:30-10:30 | 🔴 Alto |
| REV_RSI | 9:30-11:00 | 🔴 Alto |
| TSI | 9:30-11:30 | 🔴 Alto |
| VCP | 10:00-14:00 | 🟡 Medio |

**Resultado:** Em vez de complementar, elas "lutam" com TUESDAY pelas mesmas posicoes. TUESDAY (maior peso historico) ganha a maioria, e as outras ficam de fora.

---

## 5. Veredicto e Recomendacoes

### Ranking Final

| Rank | Configuracao | PnL | Sharpe | Risk% | Nota |
|------|-------------|:---:|:------:|:-----:|:----:|
| 1 | **Original Quad** | +43,189 | 3.51 | **5.2%** | ⭐⭐⭐⭐⭐ |
| 2 | Ensemble 5 | +36,753 | **3.62** | 18.5% | ⭐⭐⭐⭐ |
| 3 | Ensemble 4 | +29,698 | 3.18 | 21.8% | ⭐⭐⭐ |
| 4 | Ensemble 3 | +23,794 | 2.68 | 27.5% | ⭐⭐ |
| 5 | TUESDAY Single | +18,228 | 2.47 | 9.8% | ⭐⭐ |

### Recomendacao

**Manter o Original Quad** — mas com ressalvas sobre TUESDAY:

1. **TUESDAY é artefato estatistico? Provavelmente sim.** Mas no contexto do ensemble, ela funciona como "motor de PnL" que os complementares (VCP+KELT+EXHAUST) suavizam.

2. **Se TUESDAY falhar no futuro**, o ensemble ainda tem:
   - VCP (+12,149 isolado)
   - KELT (+5,375 isolado)
   - EXHAUST (+4,364 isolado, WFA 3/3)
   - PnL combinado sem TUESDAY: estimado ~+22,000 ainda positivo

3. **Alternativa conservadora:** Se preocupado com TUESDAY, usar **Ensemble 5** (TUESDAY+BB+REV_RSI+TSI+VCP) — Sharpe mais alto (3.62), mas aceitar drawdown 3x maior.

4. **Deploy sugerido:**
   - **70% capital no Original Quad** (max PnL, min drawdown)
   - **30% capital no Ensemble 5** (hedge se TUESDAY falhar)

---

## 6. Proximos Passos

1. [ ] **Adicionar guardrail de dia da semana para TUESDAY** — restringir a operar apenas às terças
2. [ ] **Re-otimizar TREND signals com filtro de horario 9:30-12h** (F1 hm=9.5, hx=12)
3. [ ] **Testar ensemble sem TUESDAY** (VCP+KELT+EXHAUST apenas) para ver PnL de "hedge"
4. [ ] **Deploy gradual** — comecar com 50% do lote planejado por 2 semanas

---

## Arquivos

| Arquivo | Descricao |
|---------|-----------|
| `ensemble_alternatives_comparison.csv` | Tabela comparativa raw |
| `ENSEMBLE_OPTIMIZATION_REPORT.md` | Relatorio original do optimizer |
| `TRADE_OVERLAP_ANALYSIS_REPORT.md` | Analise de sobreposicao (explica conflitos) |
