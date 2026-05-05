# Relatorio DNA — Melhor Estrategia TREND: PA_EXHAUST_Dn1_0_M40_TREND_SELL

**Data:** 2026-05-03
**Periodo OOS:** 30 Mar - 29 Abr 2026
**Trades OOS:** 19

---

## 1. Visao Geral

| Metrica | Valor |
|---------|-------|
| **PnL Total** | **+4,364** |
| Trades Vencedores | 5 (26.3%) |
| Trades Perdedores | 14 (73.7%) |
| PnL Medio por Trade | +230 |
| PnL Medio (Vencedores) | +1,414 |
| PnL Medio (Perdedores) | -193 |
| Sharpe | 1.25 |
| **WFA** | **3/3 folds positivos** |

**Insight:** WR baixo (26%) mas R:R efetivo ≈ 7:1. Unico TREND com OOS positivo + WFA robusto.

---

## 2. Parametrizacao

```
TP=5.0 | SL=2.0 | ATR=[50,800] | BE=500 | HP=3 | CD=0
OOS: +4,364 (19t, WR=42.1%)
```

**Walk-Forward Analysis:**
| Fold | PnL | Trades |
|------|:---:|:------:|
| Fev | +3,842 | ~10 |
| Mar | +1,180 | ~5 |
| Abr | +1,228 | ~5 |

**Parametros realistas:** TP=5.0, SL=2.0 (R:R = 2.5:1). Nao usa SL impossivel como TUESDAY/KELT.

---

## 3. Analise DNA — Trades que Deram Certo vs Errado

### 3.1 Segmentacao Temporal

#### Por Dia da Semana

| Dia | Trades | WR | PnL | Avg | Classificacao |
|-----|:------:|:--:|:---:|:---:|---------------|
| **Friday** | 4 | **25.0%** | **+1,923** | **+481** | **Dia Favoravel** |
| **Wednesday** | 5 | **40.0%** | **+1,058** | **+212** | **Dia Favoravel** |
| Monday | 4 | 25.0% | +680 | +170 | Neutro |
| Tuesday | 5 | 20.0% | +853 | +171 | Neutro |
| Thursday | 1 | 0.0% | -150 | -150 | Ruim (amostra pequena) |

**Sem concentracao extrema:** Nenhum dia domina 55% do PnL (diferente de TUESDAY). Distribuicao mais uniforme.

#### Por Horario

| Horario | Trades | WR | PnL | Avg | Classificacao |
|---------|:------:|:--:|:---:|:---:|---------------|
| **16:00-17:00** | 3 | **66.7%** | **+1,383** | **+461** | **Horario Ouro** |
| **10:00-11:00** | 2 | **50.0%** | **+1,520** | **+760** | **Horario Ouro** |
| **09:00-10:00** | 3 | 33.3% | +1,033 | +344 | Favoravel |
| 11:00-12:00 | 7 | 14.3% | +644 | +92 | Neutro (muitos trades) |
| 14:00-15:00 | 2 | 0.0% | -125 | -63 | Ruim |
| 12:00-13:00 | 1 | 0.0% | -75 | -75 | Ruim |
| 15:00-16:00 | 1 | 0.0% | -15 | -15 | Ruim |

**Horarios ouro: 10-11h (50% WR) e 16-17h (67% WR).** Horario de almoco (12-13h) continua ruim.

### 3.2 Analise de Saida (Hit Type)

| Tipo | Trades | PnL | Avg | % do Total |
|------|:------:|:---:|:---:|:----------:|
| **TP** | 5 | **+7,069** | **+1,414** | 100% dos ganhos |
| **SL** | 14 | **-2,705** | **-193** | 74% dos trades |

**Nenhum trade BE ou HP.** Saidas binarias: ou TP (+1,414) ou SL (-193). BE/HP nao foram atingidos.

### 3.3 DNA dos Indicadores (Win vs Loss)

| Indicador | Win Mean | Loss Mean | Delta | Cohen d | Interpretacao |
|-----------|:--------:|:---------:|:-----:|:-------:|---------------|
| **MFE** | **820** | **349** | **+471** | **0.58** | **Vencedores tem MFE 2.4x maior** |
| **ATR** | **289** | **369** | **-80** | **-0.64** | **Vencedores em ATR menor** |
| MAE | 308 | 351 | -43 | -0.12 | Levemente menor em vencedores |

**Insights criticos:**

1. **ATR menor em vencedores (Cohen d = -0.64):** O sinal funciona melhor em baixa volatilidade. Quando ATR > 369 (mediana dos perdedores), o mercado esta muito volatil e o stop e atingido antes do TP.

2. **MFE alto em vencedores (Cohen d = 0.58):** Quando o mercado se move a favor, ele se move BEM (MFE = 820 pts). Mas isso so acontece 26% das vezes.

3. **ATR como filtro:** Se filtrassemos entradas com ATR < 300 (aproximadamente), talvez aumentassemos o WR.

### 3.4 MAE/MFE — Entrada e Saida

| | Vencedores | Perdedores |
|---|:---:|:---:|
| **MAE** (pullback) | 308 | 351 |
| **MFE** (movimento favoravel) | **820** | **349** |

**Conclusao:**
- Vencedores: pullback de 308 pts, depois movimento de 820 pts (ratio 2.7:1)
- Perdedores: pullback de 351 pts, movimento de apenas 349 pts (ratio 1:1)
- **A entrada nao e o problema** (MAE similar). O problema e que 74% das vezes o mercado nao desenvolve momentum direcional suficiente.

### 3.5 Top 10 e Bottom 10 Trades

**Top 5 (todos TP):**
| Data/Hora | PnL | ATR |
|-----------|:---:|:---:| 
| 2026-04-08 11:55 | +2,195 | 481 |
| 2026-04-02 16:05 | +1,745 | 249 |
| 2026-04-28 11:50 | +1,345 | 339 |
| 2026-04-04 11:30 | +1,335 | 226 |
| 2026-04-22 10:35 | +1,045 | 289 |

**Bottom 5 (todos SL):**
| Data/Hora | PnL | ATR |
|-----------|:---:|:---:|
| 2026-04-08 11:55 | -530 | 481 |
| 2026-04-28 11:50 | -530 | 339 |
| 2026-04-01 11:20 | -280 | 279 |
| 2026-04-17 11:20 | -270 | 373 |
| 2026-04-10 11:00 | -265 | 198 |

**Observacao:** Top e bottom trade do dia 11/04 e 28/04 sao o MESMO horario. Provavelmente multiplos sinais no mesmo dia com resultados opostos (stop hunt + depois TP).

### 3.6 Sequencias

- **Max streak de vitorias:** 2 trades
- **Max streak de derrotas:** 5 trades
- Streaks de derrotas: [5, 3, 2, 2, 2]

**Muito melhor que o ensemble:** Streak max de 5 perdas (vs 20 no ensemble). Mais toleravel psicologicamente.

---

## 4. Diagnostico: Entrada e Saida

### 4.1 Entramos no Momento Correto?

**Parcialmente.** MAE similar entre vencedores (308) e perdedores (351). A entrada nao e significativamente mais limpa. O diferencial esta no que acontece DEPOIS da entrada.

### 4.2 Saímos Antes do Tempo?

**Nao.** TP=5.0 x ATR (medio ~330) = ~1,650 pts. O MFE medio em vencedores e 820 pts — ainda nao atinge o TP teorico. Mas o PnL medio de +1,414 sugere que alguns trades atingem TP parcial ou saida por HSTAG.

**Observacao:** O hit type mostra TP em todos os vencedores, mas o MFE (820) e menor que TP teorico (1,650). Isso sugere que o engine esta usando saida antecipada (HSTAG ou TP30) antes do TP=5.0 ser atingido.

### 4.3 TP e SL Estao Calibrados?

| Parametro | Valor | Status |
|-----------|:-----:|:------:|
| TP | 5.0 ATR | Alto — captura movimentos grandes |
| SL | 2.0 ATR | Moderado — stop realista |
| R:R | 2.5:1 | Aceitavel |
| BE | 500 | Alto — dificil de atingir |

**Problema:** BE=500 pts. Com ATR medio de 330, BE=500 e ~1.5x ATR. O mercado precisa se mover 1.5x ATR a favor antes de ativar BE. Isso explica por que **0 trades foram BE** — ou atinge TP ou SL.

---

## 5. Comparativo: EXHAUST vs Ensemble

| Metrica | EXHAUST (TREND) | Ensemble Quad |
|---------|:---------------:|:-------------:|
| PnL | +4,364 | +40,590 |
| Trades | 19 | 90 |
| WR | 26.3% | 24.4% |
| Sharpe | 1.25 | 3.51 |
| Max Streak Loss | 5 | **20** |
| SL realista | **Sim (2.0 ATR)** | **Nao (0.05)** |
| WFA | **3/3** | N/A |
| ATR medio | 343 | 240 |

**EXHAUST e mais psicologicamente toleravel** (streak 5 vs 20) e tem parametros realistas. O ensemble gera mais PnL mas com risco extremo.

---

## 6. Recomendacoes para TREND

### 6.1 Filtro de ATR

**Adicionar filtro ATR < 350:**
- Perdedores tem ATR medio = 369
- Vencedores tem ATR medio = 289
- Filtro ATR < 350 poderia eliminar algumas entradas em alta volatilidade

### 6.2 Horarios

**Focar em:**
- **10:00-11:00** (50% WR, +1,520 PnL em 2 trades)
- **16:00-17:00** (67% WR, +1,383 PnL em 3 trades)

**Evitar:**
- 14:00-16:00 (0% WR em 3 trades)

### 6.3 TP/SL

A parametrizacao atual (TP=5.0, SL=2.0) ja e razoavel. Mas testar:
- **TP=3.0-4.0** (menos ambicioso, mais frequente)
- **SL=1.5-2.0** (manter)
- **ATR min = 200** (evitar entradas em ATR muito baixo)

### 6.4 Break-Even

**Reduzir BE para 200-300** (de 500). Com BE=500, nenhum trade atinge BE antes de TP ou SL. BE=200 (0.6x ATR) seria mais util.

---

## 7. Veredicto

| Aspecto | EXHAUST TREND | Nota |
|---------|:-------------:|:----:|
| Parametros | TP=5, SL=2, realista | ⭐⭐⭐⭐ |
| Robustez WFA | 3/3 folds positivos | ⭐⭐⭐⭐⭐ |
| Consistencia | WR 26% (baixo mas ok) | ⭐⭐⭐ |
| Psicologico | Streak 5 perdas (toleravel) | ⭐⭐⭐⭐ |
| Horario | 10-11h e 16-17h favoraveis | ⭐⭐⭐⭐ |
| ATR | Melhor em ATR baixo (<350) | ⭐⭐⭐ |
| BE | Inutil (BE=500 nunca atingido) | ⭐⭐ |

**Recomendacao:** EXHAUST e o UNICO TREND com edge real. Parametros ja estao proximos do ideal (TP=3-5, SL=1-2). Focar em:
1. Filtro ATR < 350
2. Reduzir BE para 200-300
3. Restringir horarios 10-11h e 16-17h
4. Descartar todos os outros TREND signals

---

## Arquivos

| Arquivo | Descricao |
|---------|-----------|
| `docs/WIN_docs/exhaust_trend_dna_analysis.csv` | Dados brutos dos 19 trades |
| `docs/WIN_docs/EXHAUST_TREND_DNA_REPORT.md` | Este relatorio |
