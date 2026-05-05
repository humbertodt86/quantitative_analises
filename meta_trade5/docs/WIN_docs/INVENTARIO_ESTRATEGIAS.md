# Inventario de Estrategias WIN - V6.6
**Ultima atualizacao:** 2026-05-02
**Pipeline:** F1 (fast screener) → F2 (IS ticks) → F3 (IS validação) → Guardrail Sweep → OOS
**63 estrategias (21 famílias × 3 regimes), 154 colunas no parquet**
**Custo:** 30 pts por trade (WIN)
**Dados:** `super_win_continuous.parquet` (154 colunas)

---

## Pipeline V6.6

```
FASE 0: Signal Discovery (signal_discovery.py)
   -> Gera 3 rankings F1: Trend, Range, Hybrid

FASE 1: F1 Screening (f1_fast_screener.py)
   -> 5.400 combos (TP × SL × ATR_MIN × ATR_MAX)
   -> Sem guardrails, last prices sampleados, custo=30

FASE 2: F2 Validation (BacktestEngine IS)
   -> Top 10 do F1 com ticks reais
   -> Com BE/HP/CD basicos

FASE 3: F3 Search (BacktestEngine IS)
   -> Top 3 do F2
   -> Validacao mais rigorosa

FASE 4: Guardrail Sweep
   -> 45 combos (BE × HP × CD)
   -> Scoring: Sharpe Ratio × Net PnL

FASE 5: OOS (Out-of-Sample)
   -> Dados nunca vistos (Abril 2026)
   -> Ticks bid/ask reais
   -> Critério validação: OOS>0, WR>35%
```

---

## Sinais Validados (OOS>0, WR>35%)

| # | Estrategia | Regime | OOS Net | WR | Trades | TP | SL | BE | HP | Peso |
|---|-----------|--------|---------|-----|--------|-----|-----|-----|-----|------|
| 1 | PA_LIQ_GRAB_TREND | trend | +3.588 | 41.7% | 24 | 15.0 | 5.0 | 100 | 1 | 2.00 |
| 2 | PA_TSI_T25_TREND | trend | +1.301 | 67.7% | 31 | 1.0 | 5.0 | 500 | 3 | 2.00 |
| 3 | PA_POC_REV_TREND | trend | +718 | 48.4% | 31 | 3.0 | 5.0 | 300 | 3 | 1.44 |
| 4 | PA_TSI_T25_HYBRID | hybrid | +912 | 46.9% | 81 | 2.0 | 5.0 | 500 | 1 | 1.82 |
| 5 | PA_MFI_B20_HYBRID | hybrid | +314 | 50.0% | 20 | 3.0 | 3.0 | 500 | 2 | 0.63 |
| 6 | PA_MFI_B20_TREND | trend | +148 | 50.0% | 16 | 4.0 | 3.0 | 400 | 2 | 0.50 |

**Total validados:** 6 sinais (4 TREND, 2 HYBRID, 0 RANGE)

---

## Ranking Geral (63 Estrategias)

### TREND (21 estrategias)

| Rank | Estrategia | Categoria | OOS Net | WR | Trades | TP | SL | ATR | BE | HP | Validada |
|------|-----------|-----------|---------|-----|--------|-----|-----|------|-----|-----|----------|
| 1 | PA_LIQ_GRAB_TREND | structure | +3.588 | 41.7% | 24 | 15.0 | 5.0 | 100-400 | 100 | 1 | ✅ |
| 2 | PA_TSI_T25_TREND | momentum | +1.301 | 67.7% | 31 | 1.0 | 5.0 | 100-400 | 500 | 3 | ✅ |
| 3 | PA_POC_REV_TREND | mean_reversion | +718 | 48.4% | 31 | 3.0 | 5.0 | 100-400 | 300 | 3 | ✅ |
| 4 | PA_MFI_B20_TREND | volume | +148 | 50.0% | 16 | 4.0 | 3.0 | 100-400 | 400 | 2 | ✅ |
| 5 | PA_VCP_TREND | pattern | -115 | 40.0% | 5 | 2.0 | 0.3 | 100-400 | 100 | 1 | |
| 6 | PA_CHOP_C38_2_TREND | volatility | -164 | 40.0% | 20 | 1.5 | 3.0 | 100-800 | 500 | 1 | |
| 7 | PA_EXHAUST_Dn1_0_M40_TREND | exhaustion | -199 | 46.7% | 15 | 3.0 | 3.0 | 100-400 | 500 | 1 | |
| 8 | PA_REV_RSI_B15_TREND | mean_reversion | -753 | 50.7% | 67 | 2.0 | 5.0 | 100-400 | 500 | 3 | |
| 9 | PA_VWAP_Z_Z2_0_TREND | mean_reversion | -986 | 50.6% | 79 | 3.0 | 5.0 | 100-400 | 500 | 1 | |
| 10 | PA_MA_CROSS_F9_S21_TREND | trend_following | -1.442 | 38.5% | 13 | 2.0 | 0.8 | 50-600 | 500 | 1 | |
| 11 | PA_BB_M2_0_TREND | mean_reversion | -1.830 | 54.5% | 33 | 2.0 | 5.0 | 100-400 | 400 | 2 | |
| 12 | PA_KELT_M2_0_TREND | mean_reversion | -1.830 | 54.5% | 33 | 2.0 | 5.0 | 100-400 | 400 | 2 | |
| 13 | PA_TUESDAY_TREND | calendar | -2.823 | 32.4% | 37 | 1.0 | 0.05 | 100-600 | 100 | 1 | |
| 14 | PA_GK_BREAK_G0_001_TREND | breakout | -4.122 | 30.0% | 30 | 3.0 | 5.0 | 50-400 | 500 | 3 | |
| 15 | PA_EFF_RATIO_E0_6_TREND | trend_following | -5.771 | 20.0% | 35 | 10.0 | 5.0 | 100-400 | 400 | 2 | |
| 16 | PA_SIGNAL_DIR_TREND | trend_following | -5.780 | 34.1% | 88 | 3.0 | 5.0 | 100-400 | 500 | 3 | |
| 17 | PA_HMA_CROSS_F5_S10_TREND | trend_following | -5.856 | 34.5% | 87 | 3.0 | 5.0 | 100-400 | 500 | 3 | |
| 18 | PA_SLOPE_TREND_S25_A25_TREND | trend_following | -8.506 | 28.9% | 76 | 3.0 | 5.0 | 100-400 | 500 | 2 | |
| 19 | PA_STRONG_TREND_A25_S20_TREND | trend_following | -9.147 | 30.5% | 82 | 3.0 | 5.0 | 100-400 | 500 | 2 | |
| 20 | PA_ADX_BREAK_A25_TREND | momentum | -9.395 | 34.2% | 76 | 6.0 | 5.0 | 100-400 | 500 | 3 | |

### RANGE (21 estrategias)

| Rank | Estrategia | Categoria | OOS Net | WR | Trades | TP | SL | ATR | BE | HP | Validada |
|------|-----------|-----------|---------|-----|--------|-----|-----|------|-----|-----|----------|
| 1 | PA_BB_M2_0_RANGE | mean_reversion | +5.375 | 12.5% | 8 | 20.0 | 0.05 | 100-400 | 100 | 1 | |
| 2 | PA_KELT_M2_0_RANGE | mean_reversion | +5.375 | 12.5% | 8 | 20.0 | 0.05 | 100-400 | 100 | 1 | |
| 3 | PA_TSI_T25_RANGE | momentum | -221 | 45.7% | 35 | 2.0 | 5.0 | 100-400 | 500 | 3 | |
| 4 | PA_CHOP_C38_2_RANGE | volatility | -530 | 0.0% | 1 | 3.0 | 5.0 | 100-400 | 400 | 1 | |
| 5 | PA_MFI_B20_RANGE | volume | -866 | 28.6% | 7 | 3.0 | 3.0 | 100-400 | 400 | 3 | |
| 6 | PA_EFF_RATIO_E0_6_RANGE | trend_following | -1.175 | 0.0% | 3 | 18.0 | 2.0 | 50-400 | 100 | 1 | |
| 7 | PA_POC_REV_RANGE | mean_reversion | -1.175 | 33.3% | 9 | 4.0 | 1.0 | 300-400 | 500 | 1 | |
| 8 | PA_MA_CROSS_F9_S21_RANGE | trend_following | -1.315 | 51.9% | 27 | 1.0 | 5.0 | 100-400 | 400 | 1 | |
| 9 | PA_VCP_RANGE | pattern | -2.268 | 36.4% | 33 | 10.0 | 5.0 | 100-400 | 400 | 1 | |
| 10 | PA_LIQ_GRAB_RANGE | structure | -3.011 | 53.2% | 79 | 1.5 | 5.0 | 100-800 | 500 | 1 | |
| 11 | PA_EXHAUST_Dn1_0_M40_RANGE | exhaustion | -3.299 | 36.8% | 87 | 3.0 | 3.0 | 100-400 | 500 | 3 | |
| 12 | PA_VWAP_Z_Z2_0_RANGE | mean_reversion | -5.314 | 46.5% | 172 | 1.0 | 0.3 | 100-400 | 400 | 1 | |
| 13 | PA_ADX_BREAK_A25_RANGE | momentum | -5.582 | 50.6% | 79 | 1.0 | 5.0 | 100-400 | 500 | 1 | |
| 14 | PA_REV_RSI_B15_RANGE | mean_reversion | -6.078 | 45.7% | 116 | 1.5 | 0.8 | 100-400 | 400 | 1 | |
| 15 | PA_VWAP_REV_D1_0_RANGE | mean_reversion | -6.125 | 45.3% | 86 | 3.0 | 5.0 | 100-600 | 500 | 3 | |
| 16 | PA_TUESDAY_RANGE | calendar | -6.750 | 31.8% | 44 | 1.5 | 5.0 | 50-800 | 500 | 3 | |
| 17 | PA_SLOPE_TREND_S25_A25_RANGE | trend_following | -8.034 | 44.6% | 157 | 2.0 | 5.0 | 100-800 | 500 | 2 | |
| 18 | PA_GK_BREAK_G0_001_RANGE | breakout | -8.101 | 45.5% | 88 | 1.0 | 5.0 | 50-1000 | 500 | 2 | |
| 19 | PA_STRONG_TREND_A25_S20_RANGE | trend_following | -8.961 | 43.5% | 170 | 2.0 | 5.0 | 100-800 | 500 | 2 | |
| 20 | PA_HMA_CROSS_F5_S10_RANGE | trend_following | -8.972 | 55.0% | 318 | 1.0 | 5.0 | 100-1000 | 500 | 1 | |
| 21 | PA_SIGNAL_DIR_RANGE | trend_following | -13.695 | 43.5% | 255 | 2.0 | 5.0 | 100-800 | 500 | 2 | |

### HYBRID (21 estrategias)

| Rank | Estrategia | Categoria | OOS Net | WR | Trades | TP | SL | ATR | BE | HP | Validada |
|------|-----------|-----------|---------|-----|--------|-----|-----|------|-----|-----|----------|
| 1 | PA_TSI_T25_HYBRID | momentum | +912 | 46.9% | 81 | 2.0 | 5.0 | 100-1000 | 500 | 1 | ✅ |
| 2 | PA_MFI_B20_HYBRID | volume | +314 | 50.0% | 20 | 3.0 | 3.0 | 100-400 | 500 | 2 | ✅ |
| 3 | PA_CHOP_C38_2_HYBRID | volatility | -1.323 | 23.1% | 13 | 3.0 | 5.0 | 100-400 | 400 | 1 | |
| 4 | PA_POC_REV_HYBRID | mean_reversion | -1.700 | 38.5% | 13 | 5.0 | 1.5 | 300-400 | 500 | 1 | |
| 5 | PA_BB_M2_0_HYBRID | mean_reversion | -1.810 | 53.8% | 39 | 2.0 | 5.0 | 100-400 | 400 | 2 | |
| 6 | PA_KELT_M2_0_HYBRID | mean_reversion | -1.810 | 53.8% | 39 | 2.0 | 5.0 | 100-400 | 400 | 2 | |
| 7 | PA_MA_CROSS_F9_S21_HYBRID | trend_following | -2.065 | 43.2% | 37 | 1.5 | 5.0 | 100-400 | 500 | 1 | |
| 8 | PA_VCP_HYBRID | pattern | -2.834 | 41.7% | 36 | 8.0 | 5.0 | 100-400 | 400 | 1 | |
| 9 | PA_TUESDAY_HYBRID | calendar | -2.891 | 54.4% | 103 | 1.0 | 5.0 | 50-800 | 500 | 1 | |
| 10 | PA_LIQ_GRAB_HYBRID | structure | -2.954 | 51.3% | 113 | 1.5 | 5.0 | 100-800 | 500 | 1 | |
| 11 | PA_EXHAUST_Dn1_0_M40_HYBRID | exhaustion | -3.668 | 38.3% | 94 | 3.0 | 3.0 | 100-400 | 500 | 2 | |
| 12 | PA_VWAP_Z_Z2_0_HYBRID | mean_reversion | -4.701 | 52.9% | 238 | 1.0 | 0.3 | 100-400 | 400 | 1 | |
| 13 | PA_GK_BREAK_G0_001_HYBRID | breakout | -4.794 | 57.3% | 150 | 1.0 | 5.0 | 50-1000 | 500 | 1 | |
| 14 | PA_REV_RSI_B15_HYBRID | mean_reversion | -5.831 | 49.4% | 168 | 1.5 | 0.8 | 100-400 | 500 | 1 | |
| 15 | PA_VWAP_REV_D1_0_HYBRID | mean_reversion | -6.125 | 45.3% | 86 | 3.0 | 5.0 | 100-600 | 500 | 3 | |
| 16 | PA_EFF_RATIO_E0_6_HYBRID | trend_following | -6.416 | 18.9% | 37 | 10.0 | 5.0 | 100-400 | 400 | 2 | |
| 17 | PA_ADX_BREAK_A25_HYBRID | momentum | -9.515 | 53.6% | 181 | 1.0 | 5.0 | 100-1000 | 500 | 1 | |
| 18 | PA_HMA_CROSS_F5_S10_HYBRID | trend_following | -14.341 | 53.9% | 399 | 1.0 | 5.0 | 100-1000 | 500 | 1 | |
| 19 | PA_SLOPE_TREND_S25_A25_HYBRID | trend_following | -19.856 | 35.8% | 218 | 3.0 | 5.0 | 100-1000 | 500 | 2 | |
| 20 | PA_SIGNAL_DIR_HYBRID | trend_following | -20.656 | 39.1% | 294 | 2.0 | 5.0 | 100-1000 | 500 | 2 | |
| 21 | PA_STRONG_TREND_A25_S20_HYBRID | trend_following | -21.399 | 35.4% | 229 | 3.0 | 5.0 | 100-1000 | 500 | 2 | |

---

## Analise por Categoria

| Categoria | Melhor Estrategia | Regime | OOS Net | WR | Trades | Estrategias Testadas |
|-----------|-------------------|--------|---------|-----|--------|---------------------|
| mean_reversion | PA_BB_M2_0_RANGE | range | +5.375 | 12.5% | 8 | 17 |
| structure | PA_LIQ_GRAB_TREND | trend | +3.588 | 41.7% | 24 | 3 |
| momentum | PA_TSI_T25_TREND | trend | +1.301 | 67.7% | 31 | 6 |
| volume | PA_MFI_B20_HYBRID | hybrid | +314 | 50.0% | 20 | 3 |
| pattern | PA_VCP_TREND | trend | -115 | 40.0% | 5 | 3 |
| volatility | PA_CHOP_C38_2_TREND | trend | -164 | 40.0% | 20 | 3 |
| exhaustion | PA_EXHAUST_Dn1_0_M40_TREND | trend | -199 | 46.7% | 15 | 3 |
| trend_following | PA_EFF_RATIO_E0_6_RANGE | range | -1.175 | 0.0% | 3 | 18 |
| calendar | PA_TUESDAY_TREND | trend | -2.823 | 32.4% | 37 | 3 |
| breakout | PA_GK_BREAK_G0_001_TREND | trend | -4.122 | 30.0% | 30 | 3 |

---

## Grid Boundaries (Achados de Borda)

Analise das 63 estrategias revela concentracao nas bordas do grid:

| Parametro | Borda | Frequencia | Interpretacao |
|-----------|-------|------------|---------------|
| SL | 5.0 | 69% | Stop precisa de valores > 5.0 (grid insuficiente) |
| ATR_MAX | 400 | 66% | ATR_MAX precisa comecar em 100 (borda inferior) |

**Recomendacao:** Expandir grid para SL > 5.0 e ATR_MAX com minimo de 100.

---

## Correcoes V6.6

### Bug HYBRID = RANGE (Corrigido)

**Problema:** Estrategias HYBRID estavam retornando os mesmos resultados que RANGE.

**Causa:** Implementacao incorreta do filtro de regime. HYBRID deveria usar TODOS os dados (sem filtro), mas estava aplicando filtro RANGE.

**Solucao:** Correcao no filtro de regime. HYBRID agora usa todos os dados sem filtragem.

**Resultado:** Estrategias HYBRID agora tem resultados DIFERENTES de RANGE, permitindo validacao de 2 sinais HYBRID (TSI_T25, MFI_B20).

---

## Sumario Estatistico

| Metrica | Valor |
|---------|-------|
| Total estrategias | 63 |
| Executadas | 62 |
| Validadas (OOS>0, WR>35%) | 6 |
| Sem dados | 1 (PA_VWAP_REV_D1_0_TREND) |
| Melhor OOS | +5.375 pts (PA_BB_M2_0_RANGE) |
| Pior OOS | -21.399 pts (PA_STRONG_TREND_A25_S20_HYBRID) |
| OOS Medio | -4.309 pts |
| Melhor WR | 67.7% (PA_TSI_T25_TREND) |
| WR Medio | 40.8% |
| Total trades | 5.248 |

---

## Arquivos

| Arquivo | Descricao |
|---------|-----------|
| `V67_REPORT_COMPLETE.md` | Relatorio completo V6.7 pos-correcao HYBRID |
| `super_win_continuous.parquet` | 154 colunas, 63 estrategias com variantes |
| `data/WIN_merged_all.parquet` | Ticks IS (last prices para F1/F2) |
| `data/ticks/WIN*.parquet` | Ticks OOS (bid/ask real) |
| `data/_fev_cache_v2.npz` | Cache Fev pre-computado para F1 screening |

---

## Changelog

| Versao | Data | Estrategias | Pipeline | Notas |
|--------|------|-------------|----------|-------|
| V6.6 | 2026-05-02 | 63 | F1→F2→F3→Guardrail→OOS | Correcao HYBRID, 6 sinais validados |
| V5.1 | 2026-04-01 | 17 | F1→F2→F3 | Pipeline basico |
