# RELATORIO F1 FULL SCAN — V8.1
## Grid Search Completo + DNA Analysis

**Data:** 2026-05-04  
**Periodo IS:** 2026-02-01 a 2026-03-01  
**Sinais Analisados:** 23 (21 com trades validos)  
**Total Configs Testadas:** 92,736 (79,107 com trades)  
**Tempo de Execucao:** 157.2s  

---

## 1. RESUMO EXECUTIVO

### Top 5 Sinais por PnL IS
| Rank | Sinal | PnL | Trades | WR | Avg Win | Avg Loss | Max DD |
|------|-------|-----|--------|-----|---------|----------|--------|
| 1 | **PA_SIGNAL_REV** | +103,620 | 707 | 42.9% | +557 | -162 | -7,220 |
| 2 | **PA_SIGNAL_DIR** | +100,560 | 797 | 51.3% | +412 | -175 | -4,401 |
| 3 | **PA_VWAP_Z_Z2_0** | +94,576 | 575 | 57.0% | +408 | -159 | -4,791 |
| 4 | **PA_STRONG_TREND_A25_S20** | +75,123 | 508 | 55.3% | +414 | -181 | -3,573 |
| 5 | **PA_SLOPE_TREND_S25_A25** | +71,920 | 485 | 54.8% | +420 | -182 | -3,573 |

### Melhores Configs por Sinal
| Sinal | TP | SL | ATR_MIN | ATR_MAX | PnL | N | WR |
|-------|----|----|---------|---------|-----|---|-----|
| PA_SIGNAL_DIR | 1.5 | 0.5 | 50 | 1000 | +100,860 | 787 | 52.0% |
| PA_SIGNAL_REV | 2.5 | 0.5 | 50 | 400 | +103,980 | 695 | 43.6% |
| PA_VWAP_Z_Z2_0 | 2.0 | 0.5 | 50 | 800 | +94,606 | 574 | 57.1% |
| PA_STRONG_TREND_A25_S20 | 1.5 | 0.5 | 50 | 800 | +75,363 | 500 | 56.2% |
| PA_SLOPE_TREND_S25_A25 | 1.5 | 0.5 | 50 | 800 | +72,160 | 477 | 55.8% |

---

## 2. ANALISE DE MEMORIA

**Monitoramento durante execucao:**
- Inicio (load parquet): 94.3 MB
- Apos filtro IS: 130.8 MB
- Apos 5 sinais: 141.2 MB
- Apos 10 sinais: 149.6 MB
- Apos 15 sinais: 158.6 MB
- Apos 20 sinais: 169.5 MB
- Final: 175.2 MB

**Pico de memoria:** 175.2 MB  
**Media por sinal:** ~3.5 MB adicional  
**Status:** ✅ Dentro do limite ( < 1 GB)

---

## 3. DNA ANALYSIS — PADROES POR ESTRATEGIA

### 3.1 PA_SIGNAL_REV (Top PnL)
- **Edge:** Maior avg win (+557) mas menor WR (42.9%)
- **Padrao:** Wins grandes, losses pequenas (ratio 3.45)
- **Drawdown:** -7,220 (mais alto do top 5)
- **Recomendacao:** Requer guardrails agressivos (BE, HP)

### 3.2 PA_SIGNAL_DIR (Mais trades)
- **Edge:** Balanceado — 51.3% WR, 797 trades
- **Padrao:** Execucao consistente, menor DD relativo
- **Drawdown:** -4,401 (4.4% do PnL)
- **Recomendacao:** Candidato ideal para ensemble

### 3.3 PA_VWAP_Z_Z2_0 (Melhor WR)
- **Edge:** 57.0% WR com bom PnL
- **Padrao:** Reversao a VWAP com Z>=2
- **Drawdown:** -4,791
- **Recomendacao:** Forte candidato para F2/F3

### 3.4 PA_STRONG_TREND_A25_S20
- **Edge:** Trend following com filtro de slope
- **Padrao:** WR 55.3%, avg win consistente
- **Drawdown:** -3,573 (menor do top 5)
- **Recomendacao:** Menor risco, bom para diversificacao

### 3.5 PA_SLOPE_TREND_S25_A25
- **Edge:** Similar ao STRONG_TREND mas com slope absoluto
- **Padrao:** WR 54.8%, performance consistente
- **Drawdown:** -3,573
- **Recomendacao:** Complementar ao STRONG_TREND

---

## 4. SINAIS SEM EDGE (PnL < +20,000)

| Sinal | PnL | N | WR | Problema |
|-------|-----|---|-----|----------|
| PA_VCP_C0_6 | +6,010 | 24 | 41.7% | Trade count muito baixo |
| PA_MA_CROSS_F9_S21 | +9,460 | 50 | 64.0% | Trade count baixo |
| PA_SIGNAL_DIR_V2 | +11,042 | 72 | 50.0% | Trade count baixo |
| PA_TUESDAY | +12,097 | 112 | 58.0% | Calendar edge fraco |
| PA_MFI_B20 | +13,430 | 33 | 68.1% | Trade count muito baixo |
| PA_VWAP_REV_D1_0 | +13,261 | 118 | 45.8% | Edge marginal |
| PA_EFF_RATIO_E0_6 | +15,744 | 36 | 47.2% | Trade count baixo |
| PA_HMA_CROSS_F5_S10 | +15,560 | 105 | 59.0% | Trade count baixo |

**Recomendacao:** Remover do ensemble ou manter apenas para diversificacao.

---

## 5. SINAIS COM PROBLEMAS

### 5.1 PA_TSI_T25 (Alto Drawdown)
- **PnL:** +32,491 (8o lugar)
- **Max DD:** -15,679 (48% do PnL!)
- **Problema:** Drawdown desproporcional
- **Acao:** Requer guardrails muito agressivos ou remover

### 5.2 PA_KELT_ATR_M2_0 (SL frequente)
- **PnL:** +24,360
- **SL outcomes:** 54.7% (mais da metade!)
- **Problema:** Edge vem de wins grandes, mas SL e frequente
- **Acao:** Ajustar SL ou remover

### 5.3 PA_GK_BREAK_G0_001, PA_CHOP_C38_2
- **Problema:** ZERO configs validas
- **Causa:** Sinais muito restritivos ou bugs
- **Acao:** Investigar logica ou remover

---

## 6. TOP 10 GLOBAL — CONFIGS PARA F2

| Rank | Sinal | TP | SL | ATR_MIN | ATR_MAX | PnL | N | WR |
|------|-------|----|----|---------|---------|-----|---|-----|
| 1 | PA_SIGNAL_REV | 2.5 | 0.5 | 50 | 400 | +103,980 | 695 | 43.6% |
| 2 | PA_SIGNAL_REV | 2.5 | 0.5 | 100 | 400 | +103,980 | 695 | 43.6% |
| 3 | PA_SIGNAL_REV | 2.0 | 0.5 | 100 | 400 | +103,165 | 704 | 50.4% |
| 4 | PA_SIGNAL_REV | 2.0 | 0.5 | 50 | 400 | +103,165 | 704 | 50.4% |
| 5 | PA_SIGNAL_DIR | 1.5 | 0.5 | 50 | 1000 | +100,860 | 787 | 52.0% |
| 6 | PA_SIGNAL_DIR | 1.5 | 0.5 | 100 | 1000 | +100,860 | 787 | 52.0% |
| 7 | PA_SIGNAL_DIR | 1.5 | 0.5 | 150 | 1000 | +100,495 | 755 | 52.5% |
| 8 | PA_SIGNAL_DIR | 1.5 | 0.5 | 50 | 800 | +100,140 | 785 | 52.0% |
| 9 | PA_SIGNAL_DIR | 1.5 | 0.5 | 100 | 800 | +100,140 | 785 | 52.0% |
| 10 | PA_SIGNAL_DIR | 1.5 | 0.5 | 150 | 800 | +99,775 | 753 | 52.5% |

**Observacao:** Top 10 dominado por PA_SIGNAL_REV e PA_SIGNAL_DIR.

---

## 7. ARQUIVOS GERADOS

### F1 Results
- `docs/WIN_docs/F1_FULL_RESULTS.csv` — 79,107 configs
- `docs/WIN_docs/F1_BEST_PER_SIGNAL.csv` — 21 sinais
- `docs/WIN_docs/F1_TOP100_GLOBAL.csv` — Top 100 global
- `docs/WIN_docs/F1_PARTIAL_10.csv` — Partial (10 sinais)
- `docs/WIN_docs/F1_PARTIAL_20.csv` — Partial (20 sinais)
- `docs/WIN_docs/f1_monitor.txt` — Log de memoria

### DNA Analysis
- `docs/WIN_docs/DNA/DNA_ALL_summary.csv` — Consolidado
- `docs/WIN_docs/DNA/DNA_{SIGNAL}_trades.csv` — Trade-by-trade (21 arquivos)
- `docs/WIN_docs/DNA/DNA_{SIGNAL}_hours.csv` — Hour distribution (21 arquivos)
- `docs/WIN_docs/DNA/DNA_{SIGNAL}_summary.txt` — Resumo por sinal (21 arquivos)

---

## 8. PROXIMOS PASSOS (F2/F3/OOS)

### F2 Validation (Tick-Level Backtest)
**Top 10 configs para validar:**
1. PA_SIGNAL_REV TP=2.5/SL=0.5/ATR=50-400
2. PA_SIGNAL_DIR TP=1.5/SL=0.5/ATR=50-1000
3. PA_VWAP_Z_Z2_0 TP=2.0/SL=0.5/ATR=50-800
4. PA_STRONG_TREND_A25_S20 TP=1.5/SL=0.5/ATR=50-800
5. PA_SLOPE_TREND_S25_A25 TP=1.5/SL=0.5/ATR=50-800

**Criterio de aprovacao:**
- OOS PnL > 0
- OOS WR > 45%
- Max DD < 20% do PnL
- Trade count > 20

### F3 Guardrails Optimization
**Parametros para otimizar:**
- BE (Break-even): [0, 0.5, 1.0, 1.5] x ATR
- HP (Hold Period): [5, 10, 15, 20] candles
- TP30 (Partial): [0, 0.3, 0.5] do tamanho

**Objetivo:** Melhorar WR e reduzir DD.

### OOS Validation
**Periodo:** 2026-03-01 a 2026-04-01  
**Criterio:** PnL positivo com WR > 45%

---

## 9. CONCLUSOES

### ✅ Sucessos
1. **Grid search completo:** 92,736 configs testadas
2. **Top sinais identificados:** PA_SIGNAL_REV, PA_SIGNAL_DIR, PA_VWAP_Z_Z2_0
3. **DNA analysis gerada:** Padroes de execucao mapeados
4. **Memoria controlada:** Pico 175 MB (seguro)

### ⚠️ Atencao
1. **PA_TSI_T25:** Drawdown de 48% do PnL — risco alto
2. **PA_KELT_ATR_M2_0:** 54.7% SL outcomes — edge fragil
3. **PA_GK_BREAK_G0_001, PA_CHOP_C38_2:** Zero trades — investigar

### 📋 Recomendacoes
1. **Focar F2 no top 5:** PA_SIGNAL_REV, PA_SIGNAL_DIR, PA_VWAP_Z_Z2_0, STRONG_TREND, SLOPE_TREND
2. **Remover sinais fracos:** Trade count < 50 ou PnL < +15,000
3. **Investigar sinais zerados:** GK_BREAK, CHOP
4. **Guardrails agressivos:** PA_SIGNAL_REV precisa de BE/HP

---

**Status:** F1 completo. Pronto para F2 validation.
