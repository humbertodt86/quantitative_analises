# V8.0 vs V8.1 — INCONSISTENCIAS CRITICAS

## 🚨 DESCOBERTA: 3 FONTES DE VERDADE CONFLITANTES

Existem **3 implementacoes diferentes** do V8.0 no codebase, com parametros **DIFERENTES**:

---

## 1. PARAMETROS V8.0 CORE — COMPARACAO

| Parametro | `build_win_signals_v81.py` (CANONICO) | `build_continuous_indicators.py` (ORIGINAL) | Diferenca |
|-----------|--------------------------------------|--------------------------------------------|-----------|
| **Slope calculation** | `EMA_SLOPE` (3-period) | `EMA20_SLOPE.diff()` (1-period) | **DIFFERENT CALCULATION** |
| **V8_S_MIN** | `0` (qualquer inclinacao) | Implicito `> 0` | **+infinity%** |
| **V8_Z_MAX** | `3.0` (relaxado) | `2.0` (padrao) | **+50%** |
| **V8_R_MIN** | `0.5` (menos restritivo) | `0.8` (padrao) | **-37.5%** |

---

## 2. IMPACTO NOS SINAIS

### PA_SIGNAL_DIR (V8.0 Core)

**V8.1 (canonico)**:
```python
noise_ok = range_ratio >= 0.5  # 50% dos candles passam
z_score < 3.0  # 99.7% passam (3 std)
ema_slope > 0  # 3-period slope
```

**V8.0 (original)**:
```python
noise_ok = range_ratio >= 0.8  # 20% dos candles passam
z_score < 2.0  # 95% passam (2 std)
ema_slope > 0  # 1-period slope
```

**Resultado**: V8.1 gera **MUITOS MAIS SINAIS** que V8.0 original.

---

## 3. OUTROS PARAMETROS FIXOS (23 sinais PA_*)

### PA_SIGNAL_DIR_V2
| Arquivo | Base | atr_min_v2 |
|---------|------|------------|
| `build_win_signals_v81.py` | V8.0 signal | 150 |
| `build_continuous_indicators.py` | DEPRECATED (close vs EMA20) | 150 |

### PA_STRONG_TREND_A25_S20
| Parametro | Valor Fixo |
|-----------|------------|
| ADX7 min | 25 |
| EMA5_SLOPE_ABS min | 20 |

### PA_SLOPE_TREND_S25_A25
| Parametro | Valor Fixo |
|-----------|------------|
| EMA5_SLOPE_ABS min | 25 |
| ADX7 min | 25 |

### PA_ADX_BREAK_A25
| Parametro | Valor Fixo |
|-----------|------------|
| ADX7 min | 25 |
| adx_delta | > 0 |

### PA_EXHAUST_Dn1_0_M40
| Parametro | Valor Fixo |
|-----------|------------|
| ADX7 max | 40 |
| adx_delta | < -1.0 |
| ADX7 min | 25 |

### PA_GK_BREAK_G0_001
| Parametro | Valor Fixo |
|-----------|------------|
| GK_RATIO min | 0.001 |
| ADX7 min | 25 |

### PA_VCP_C0_6
| Parametro | Valor Fixo |
|-----------|------------|
| range_ratio | < 0.6 |
| range_ratio.shift(1) | < 0.7 |

### PA_REV_RSI_B10 / S90
| Parametro | Valor Fixo |
|-----------|------------|
| RSI2 buy | < 10 |
| RSI2 sell | > 90 |

### PA_VWAP_Z_Z2_0
| Parametro | Valor Fixo |
|-----------|------------|
| VWAP_Z buy | < -2.0 |
| VWAP_Z sell | > 2.0 |

### PA_VWAP_REV_D1_0
| Parametro | Valor Fixo |
|-----------|------------|
| Distancia ATR | 1.0× |
| ADX7 max | 25 |

### PA_KELT_ATR_M2_0
| Parametro | Valor Fixo |
|-----------|------------|
| Multiplicador ATR | 2.0× |

### PA_VWAP_STRETCH
| Parametro | Valor Fixo |
|-----------|------------|
| ATR_STRETCH | ±2.0 |
| range_ratio | < 0.8 |

### PA_MFI_B20
| Parametro | Valor Fixo |
|-----------|------------|
| MFI14 buy | < 20 |
| MFI14 sell | > 80 |

### PA_TSI_T25
| Parametro | Valor Fixo |
|-----------|------------|
| TSI buy | < -25 |
| TSI sell | > 25 |

### PA_EFF_RATIO_E0_6
| Parametro | Valor Fixo |
|-----------|------------|
| EFF_RATIO min | 0.6 |

### PA_CHOP_C38_2
| Parametro | Valor Fixo |
|-----------|------------|
| CHOP_INDEX max | 38.2 |

### PA_LIQ_GRAB
| Parametro | Valor Fixo |
|-----------|------------|
| Lookback | 10 candles |

### PA_MA_CROSS_F9_S21
| Parametro | Valor Fixo |
|-----------|------------|
| MA fast | 9 |
| MA slow | 21 |

### PA_HMA_CROSS_F5_S10
| Parametro | Valor Fixo |
|-----------|------------|
| SMA fast | 5 |
| SMA slow | 10 |

---

## 4. VARIANTES EXISTENTES (NAO USADAS NO PARQUET ATUAL)

### `build_signal_dir_variants.py` — 120 variantes
```python
SLOPE_GRID = [0, 5, 10, 20]       # 4 valores
ZSCORE_GRID = [1.0, 1.5, 2.0, 2.5, 3.0, 999]  # 6 valores
RANGE_GRID = [0.3, 0.5, 0.8, 1.0, 1.5]  # 5 valores
# Total: 4 × 6 × 5 = 120 variantes
```

### `build_continuous_indicators.py` — Variantes geradas dinamicamente
| Familia | Grid | Total |
|---------|------|-------|
| PA_VCP_C{th} | [0.5, 0.6, 0.7, 0.8] | 4 |
| PA_REV_RSI_B{buy} | [5, 10, 15, 20, 25] | 5 |
| PA_REV_RSI_S{sell} | [70, 75, 80, 85, 90] | 5 |
| PA_BB_M{mult} | [1.5, 2.0, 2.5, 3.0] | 4 |
| PA_VWAP_REV_D{dist} | [0.3, 0.6, 1.0, 1.5, 2.0] | 5 |
| PA_VWAP_Z_Z{z} | [1.0, 1.5, 2.0, 2.5, 3.0] | 5 |
| PA_STRONG_TREND_A{adx}_S{slope} | [20,25,30,35] × [15,20,25,30] | 16 |
| PA_GK_BREAK_G{gk} | [0.0005, 0.001, 0.002, 0.005] | 4 |
| PA_EXHAUST_D{delta}_M{max} | [-0.5,-1.0,-2.0] × [35,40,45,50] | 12 |
| PA_MA_CROSS_F{fast}_S{slow} | [(7,14), (9,21), (10,30), (5,13)] | 4 |
| PA_SLOPE_TREND_S{slope}_A{adx} | [20,25,30,35,40] × [20,25,30] | 15 |
| PA_HMA_CROSS_F{fast}_S{slow} | [(5,10), (9,20), (7,14), (3,9)] | 4 |
| PA_TSI_T{tsi} | [15, 20, 25, 30, 35] | 5 |
| PA_EFF_RATIO_E{er} | [0.4, 0.5, 0.6, 0.7, 0.8] | 5 |
| PA_CHOP_C{chop} | [30, 35, 38.2, 45, 50] | 5 |
| PA_MFI_B{mfi} | [10, 15, 20, 25, 30] | 5 |
| PA_KELT_M{mult} | [1.0, 1.5, 2.0, 2.5, 3.0] | 5 |

**Total variantes**: ~100+ sinais PA_* diferentes

---

## 5. PROBLEMA CENTRAL

**Parquet atual** (`super_win_continuous_v81.parquet`):
- Usa APENAS `build_win_signals_v81.py` com params FIXOS
- V8_S_MIN=0, V8_Z_MAX=3.0, V8_R_MIN=0.5
- 23 sinais PA_* (subconjunto minimo)

**O que falta**:
- Variantes de V8_* params (27 combinacoes)
- Variantes de thresholds (100+ sinais)
- Consistencia entre V8.0 original e V8.1 canonico

---

## 6. PLANO DE ACAO

### Opcao A: Rebuild Completo (RECOMENDADO)
```bash
# 1. Gerar 27 parquets com variantes V8_*
python scripts/build_win_signals_v81_variants.py
# Gera: data/super_win_continuous_v81_s{s}_z{z}_r{r}.parquet

# 2. Rodar F1 em cada parquet
for parquet in data/super_win_continuous_v81_s*_z*_r*.parquet; do
    python scripts/f1_full_scan_v84.py --parquet $parquet --direction both
done

# 3. Consolidar resultados
python scripts/consolidate_v85_results.py
```

**Tempo estimado**:
- Build 27 parquets: ~27 × 30s = 13.5 min
- F1 27 parquets: 27 × 9.2s = 4.1 min
- Consolidacao: ~1 min
- **Total: ~19 min**

### Opcao B: Top Parquets Apenas (RAPIDO)
```bash
# Gerar apenas 3-5 parquets mais promissores
# Ex: s0_z3.0_r0.5 (atual), s10_z3.0_r0.5, s0_z2.5_r0.5
```

**Tempo estimado**: ~3 min

### Opcao C: Manter Fixo (NAO RECOMENDADO)
- Usar parquet atual (V8_* fixos)
- Assumir que otimizacao de TP/SL/ATR e suficiente
- Risco: sub-otimizacao, edge deixado na mesa

---

## 7. RECOMENDACAO

**Opcao A (Rebuild Completo)** — 19 min de investimento para garantir que nao estamos deixando edge na mesa.

**Justificativa**:
- V8.0 original vs V8.1 tem diferencas criticas (Z_MAX 2.0 vs 3.0, R_MIN 0.8 vs 0.5)
- 27 parquets cobrem todo o espaco de params V8_*
- Tempo total < 20 min e aceitavel para ganho potencial de edge

---

## 8. ARQUIVOS

- `scripts/build_win_signals_v81.py` — V8.1 canonico (params fixos)
- `scripts/build_continuous_indicators.py` — V8.0 original (params diferentes)
- `scripts/build_signal_dir_variants.py` — Grid de 120 variantes (nao usado)
- `data/super_win_continuous_v81.parquet` — Parquet atual (V8_* fixos)
- `scripts/f1_full_scan_v84.py` — F1 com BUY+SELL (funcional)
- `scripts/f1_v85_documentacao.py` — Este documento

---

## 9. CONCLUSAO

**BUG FIX V8.4**: ✅ Completado (PnL falso positivo corrigido)
**BUY+SELL**: ✅ Completado (ambas direcoes testadas)
**VARIANTES V8_***: ⚠️ Documentado, pendiente implementacao (27 parquets)

**Proximo passo**: Decidir entre Opcao A (completo), B (rapido), ou C (manter).
