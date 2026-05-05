# Relatorio E2E Pipeline V8.7 — PA_SIGNAL_DIR (BUY)

**Data:** 2026-05-04  
**Sinal:** PA_SIGNAL_DIR  
**Direcao:** BUY  
**Status:** ✅ Pipeline executado com sucesso

---

## 1. RESUMO EXECUTIVO

| Fase | Combos | Tempo | Velocidade | Melhor PnL | Status |
|------|--------|-------|------------|------------|--------|
| **F1** (Pre-Filtro) | 70,014 | 152.8s | **458 combos/s** | +19,993 | ✅ Rápido |
| **F2** (GridAdvisor) | 36,450 | 2.3s | **15,602 combos/s** | +20,023 | ✅ Ultra-rápido |
| **F3** (OOS) | 3 | ~1s | N/A | -5,970 | ⚠️ Prejuizo OOS |

**Tempo Total E2E: ~2.5 minutos**

---

## 2. F1 — FULL SCAN (Pre-Filtro)

### Configuracao
- **Variantes:** 18 (s0_z1p5_r0p5 a s20_z4p0_r1p0)
- **Grid:** 12 TP x 8 SL x 6 ATR_MIN x 7 ATR_MAX = 4,032 combos/variante
- **Direcao:** BUY
- **Total:** 72,576 combos → 70,014 resultados válidos (≥3 trades)

### Performance
- **Tempo:** 152.8 segundos
- **Velocidade:** 458 combos/s (Python puro, sequencial)
- **Eficiencia:** Processou todas as variantes sem paralelizacao

### Top 5 Configs F1

| Rank | Variante | TP | SL | ATR | PnL | Trades | WR |
|------|----------|----|----|-----|-----|--------|----|
| 1 | s20_z1p5_r1p0 | 5.0 | 5.0 | [400-800] | +19,993 | 8 | 87.5% |
| 2 | s20_z1p5_r1p0 | 5.0 | 2.0 | [400-800] | +19,136 | 8 | 87.5% |
| 3 | s20_z1p5_r1p0 | 5.0 | 5.0 | [400-600] | +18,828 | 8 | 87.5% |
| 4 | s20_z1p5_r1p0 | 5.0 | 3.0 | [400-800] | +18,708 | 8 | 87.5% |
| 5 | s20_z1p5_r1p0 | 15.0 | 1.5 | [300-600] | +18,693 | 10 | 30.0% |

### Observacoes
- **Todas as top 5 usam a mesma variante:** `s20_z1p5_r1p0` (s_min=20, z_max=1.5, r_min=1.0)
- **TP=5.0 dominante:** Configuracoes com TP=5.0 e SL alto tiveram melhor performance
- **WR alto (87.5%):** Mas com poucos trades (8), pode ser overfitting ao periodo

---

## 3. F2 — GRID ADVISOR (Otimizacao)

### Configuracao
- **Top N do F1:** 30 configs
- **Grid F2:** 3 tp_sr x 3 sl_sr x 5 sr_thresh x 3 BE x 3 Grace x 3 Slope = 1,215 combos/config
- **Total:** 30 x 1,215 = 36,450 combos
- **Paralelizacao:** 8 workers (multiprocessing)

### Performance
- **Tempo:** 2.3 segundos (!!!)
- **Velocidade:** 15,602 combos/s (numba + multiprocessing)
- **Speedup vs F1:** 34x mais rápido!

### Top 3 Configs F2

| Rank | Variante | TP/SL | S/R | Guardrails | PnL | Trades | WR |
|------|----------|-------|-----|------------|-----|--------|----|
| 1 | s20_z1p5_r1p0 | 5.0/5.0 | tp_sr=0.80 sl_sr=1.10 thresh=1.05 | BE=50 Grace=4 Slope=0.50 | +20,023 | 7 | 100% |
| 2 | s20_z1p5_r1p0 | 5.0/2.0 | tp_sr=0.80 sl_sr=1.10 thresh=1.05 | BE=50 Grace=4 Slope=0.50 | +19,136 | 8 | 87.5% |
| 3 | s20_z1p5_r1p0 | 5.0/5.0 | tp_sr=0.80 sl_sr=1.10 thresh=1.05 | BE=50 Grace=4 Slope=0.50 | +18,858 | 7 | 100% |

### Observacoes
- **S/R otimo:** tp_sr=0.80, sl_sr=1.10, thresh=1.05 (sempre)
- **Guardrails otimo:** BE=50, Grace=4, Slope=0.50 (sempre)
- **Melhora marginal:** F2 melhorou +0.15% vs F1 (ganho de 30 pts)

---

## 4. F3 — VALIDACAO OOS (Abril 2026)

### Configuracao
- **Periodo:** 2026-04-01 a 2026-04-30
- **Dados:** 2,044 candles
- **Sinal:** PA_SIGNAL_DIR (sinal base, sem variantes)

### Resultados OOS

| Rank | Config F2 | PnL OOS | Trades | WR OOS | vs IS |
|------|-----------|---------|--------|--------|-------|
| 1 | TP=5.0 SL=5.0 BE=50 | **-5,970** | 10 | 40.0% | 🔴 -125% |
| 2 | TP=5.0 SL=2.0 BE=50 | **-3,235** | 18 | 27.8% | 🔴 -117% |
| 3 | TP=5.0 SL=5.0 BE=50 | **-7,364** | 12 | 41.7% | 🔴 -139% |

### Analise OOS
- **Todas as configs deram prejuizo:** Melhor foi -3,235 (config #2)
- **WR caiu drasticamente:** De 87-100% (IS) para 28-42% (OOS)
- **Overfitting ao periodo IS:** Fevereiro teve condicoes favoráveis que nao se repetiram em Abril
- **Trade count aumentou:** De 7-8 (IS) para 10-18 (OOS), mas qualidade piorou

---

## 5. VELOCIDADES DO PIPELINE

| Engine | Velocidade | Fator vs Anterior | Notas |
|--------|------------|-------------------|-------|
| **F1** (Python sequencial) | 458 combos/s | 1x | Simples, confiável |
| **F2** (Numba + MP) | 15,602 combos/s | **34x** | Paralelizacao massiva |
| **F3** (OOS) | ~3 combos/s | 0.0002x | Tick-by-tick, preciso |

**Insight:** O F2 com paralelizacao é 34x mais rápido que o F1! Isso permite testar grids muito maiores em tempo real.

---

## 6. LIÇOES APRENDIDAS

### 6.1 Sobre o Pipeline
1. **F1 é rápido o suficiente:** 458 combos/s permite testar milhares de combos em minutos
2. **F2 é ultra-rápido:** 15K combos/s permite testar 100K combos em ~6 segundos
3. **GridAdvisor funciona:** Reduziu de 50K combos para 36K combos com mesmo resultado

### 6.2 Sobre a Estrategia
1. **Overfitting ao IS:** PnL positivo em Fev, negativo em Abr
2. **WR não generaliza:** 87% IS → 28% OOS
3. **Poucos trades no IS:** 7-8 trades não são estatisticamente significativos

### 6.3 O que Funcionou
1. **Pipeline E2E funcional:** F1→F2→F3 executa em ~2.5 minutos
2. **Paralelizacao eficiente:** 8 workers no F2 reduziram tempo de minutos para segundos
3. **GridAdvisor inteligente:** Foco nos parâmetros que realmente importam (S/R + guardrails)

---

## 7. PROXIMOS PASSOS

1. **Testar outros sinais:** PA_SIGNAL_DIR falhou OOS, mas outros 22 sinais podem funcionar
2. **Aumentar top N:** Testar top 100 do F1 no F2 para encontrar configs mais robustas
3. **Testar SELL:** BUY falhou, mas SELL pode ter funcionado (mercado em queda em Abril?)
4. **Mais dados OOS:** Validar em Maio/Junho para confirmar tendência

---

## 8. ARQUIVOS

- **Script:** `scripts/e2e_pipeline_v87.py`
- **F1 Output:** `docs/WIN_docs/F1_V87_TEST_PA_SIGNAL_DIR.csv`
- **Relatorio:** `docs/WIN_docs/E2E_REPORTS/E2E_PA_SIGNAL_DIR_BUY_REPORT.md`

---

**Pipeline executado com sucesso em ~2.5 minutos!**  
**Status:** E2E funcional, mas estratégia não generaliza para OOS.
