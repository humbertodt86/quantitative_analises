# GRID SEARCH PERSONALIZADO — 23 SINAIS PA_*

**Objetivo**: Definir grid de otimizacao personalizado para CADA sinal PA_*, baseado em seus parametros especificos.

**Total de Sinais**: 23 familias
**Grid Base V8_***: 27 variantes (3×3×3) — ja implementado
**Grids Especificos**: Variam por sinal (detalhado abaixo)

**Arquivo Analisado**: `scripts/build_win_signals_v81.py`
**Data da Analise**: 2026-05-04

---

## METODOLOGIA

Para cada sinal, analisamos:
1. **Formula de calculo** — Como o sinal e gerado
2. **Parametros hardcoded** — Thresholds, periodos, multiplicadores
3. **Grid recomendado** — Valores para testar em GS

---

## PARAMETROS DE BASE (INDICADORES COMPARTILHADOS)

Estes parâmetros vêm de `add_indicators()` e `compute_raw_indicators()`:

| Indicador | Parâmetro | Valor | Local |
|-----------|-----------|-------|-------|
| EMA5 | span | 5 | `indicators.py:103` |
| EMA20 | span | 20 | `indicators.py:102` |
| ATR | window | 14 | `indicators.py:105-109` |
| ADX7 | period | 7 | `build_win_signals_v81.py:84` |
| EMA_SLOPE | diff shift | 3 | `indicators.py:110` |
| EMA5_SLOPE | diff shift | 1 | `indicators.py:111` |
| VWAP_Z std | rolling | 20 | `build_win_signals_v81.py:180` |
| ATR_STRETCH | divisor | ATR (replace 0→1) | `build_win_signals_v81.py:185` |
| Z_SCORE_EMA20 std | rolling | 20 | `build_win_signals_v81.py:176` |
| GK_RATIO | formula | 0.5×log_hl² − (2ln2−1)×log_co² | `build_win_signals_v81.py:162-165` |

---

## GRUPO 1: SINAIS BASE (3 sinais)

### 1. PA_SIGNAL_DIR

**Memoria de Calculo**:
```python
# V8.0 Core — Trend following com filtros
noise_ok = range_ratio >= r_min  # r_min: [0.3, 0.5, 0.7]

v8_buy = (
    (close > EMA20) &           # Preco acima da EMA20
    (EMA_SLOPE > s_min) &       # Slope positivo (min: s_min)
    (Z_SCORE_EMA20 < z_max) &   # Nao esticado (max: z_max std)
    noise_ok
)

v8_sell = (
    (close < EMA20) &
    (EMA_SLOPE < -s_min) &
    (Z_SCORE_EMA20 > -z_max) &
    noise_ok
)

PA_SIGNAL_DIR = 1 se v8_buy, -1 se v8_sell, 0 caso contrario
```

**Parametros Atuais**:
| Parametro | Valor | Tipo | Local |
|-----------|-------|------|-------|
| `EMA20 span` | 20 | Periodo | `indicators.py:102` |
| `s_min` (V8_S_MIN) | 0.0 | Threshold | `v81.py:218` |
| `z_max` (V8_Z_MAX) | 3.0 | Threshold | `v81.py:218` |
| `r_min` (V8_R_MIN) | 0.5 | Threshold | `v81.py:218` |
| `EMA_SLOPE diff` | 3 | Periodo | `indicators.py:110` |
| `range_ma20` | 20 | Periodo | `v81.py:173` |
| `Z_SCORE std` | 20 | Periodo | `v81.py:176` |

**Grid Recomendado**:
```python
EMA_PERIOD   = [10, 15, 20, 30, 50]        # 5 valores
V8_S_MIN     = [0.0, 0.5, 1.0, 2.0, 5.0]  # 5 valores
V8_Z_MAX     = [1.5, 2.0, 2.5, 3.0, 4.0]  # 5 valores
V8_R_MIN     = [0.3, 0.4, 0.5, 0.6, 0.8]  # 5 valores
EMA_SLOPE_DIFF = [1, 2, 3, 5, 8]          # 5 valores
```

**Total Variantes**: 5 × 5 × 5 × 5 × 5 = **3,125 variantes**

**Justificativa**: Sinal principal — merece grid mais denso. EMA period afeta sensibilidade da tendencia. Slope diff afeta velocidade da deteccao.

---

### 2. PA_SIGNAL_DIR_V2

**Memoria de Calculo**:
```python
# Fresh Cross + Acceleration
sig_prev = PA_SIGNAL_DIR.shift(1)
slope = EMA5_SLOPE
slope_prev = slope.shift(1)
atr_min_v2 = 150  # HARDCODED

fresh_cross_buy = (PA_SIGNAL_DIR == 1) & (sig_prev != 1)
fresh_cross_sell = (PA_SIGNAL_DIR == -1) & (sig_prev != -1)
slope_accel_buy = (slope > 0) & (slope > slope_prev)
slope_accel_sell = (slope < 0) & (slope < slope_prev)
atr_ok = ATR >= atr_min_v2

PA_SIGNAL_DIR_V2 = 1 se (fresh_cross_buy & slope_accel_buy & atr_ok)
                   -1 se (fresh_cross_sell & slope_accel_sell & atr_ok)
                   0 caso contrario
```

**Parametros Atuais**:
| Parametro | Valor | Tipo | Local |
|-----------|-------|------|-------|
| `atr_min_v2` | 150 | Threshold | `v81.py:252` |
| `EMA5_SLOPE diff` | 1 | Periodo | `indicators.py:111` |

**Grid Recomendado**:
```python
ATR_MIN_V2 = [50, 100, 150, 200, 300]  # 5 valores
```

**Depende de**: PA_SIGNAL_DIR (herda params do V8.0)

**Total Variantes**: 5 (ATR_MIN_V2) × 3,125 (PA_SIGNAL_DIR base) = **15,625 variantes**

**Justificativa**: Filtra apenas cruzamentos frescos com aceleracao e volatilidade minima.

---

### 3. PA_SIGNAL_REV

**Memoria de Calculo**:
```python
# Inverso do PA_SIGNAL_DIR
PA_SIGNAL_REV = -PA_SIGNAL_DIR
```

**Parametros**: Nenhum proprio — herda do PA_SIGNAL_DIR

**Grid Recomendado**: Mesmo que PA_SIGNAL_DIR — **3,125 variantes**

**Justificativa**: Mean reversion — usa mesmos filtros mas na direcao oposta.

---

## GRUPO 2: TREND FOLLOWING (2 sinais)

### 4. PA_STRONG_TREND_A25_S20

**Memoria de Calculo**:
```python
# Trend forte com ADX e Slope
PA_STRONG_TREND_A25_S20 = np.where(
    (ADX7 >= 25) &              # ADX minimo (tendencia forte)
    (EMA5_SLOPE_ABS >= 20) &    # Slope absoluto minimo
    (PA_SIGNAL_DIR != 0),       # Direcao definida
    PA_SIGNAL_DIR, 0
)
```

**Parametros Atuais**:
| Parametro | Valor | Tipo | Local |
|-----------|-------|------|-------|
| `ADX_MIN` | 25 | Threshold | `v81.py:266` |
| `SLOPE_MIN` | 20 | Threshold | `v81.py:267` |
| `ADX7 period` | 7 | Periodo | `v81.py:84` |
| `EMA5_SLOPE diff` | 1 | Periodo | `indicators.py:111` |

**Grid Recomendado**:
```python
ADX_MIN      = [20, 25, 30, 35, 40]      # 5 valores
SLOPE_MIN    = [10, 15, 20, 25, 30]      # 5 valores
ADX_PERIOD   = [7, 10, 14, 20]           # 4 valores
```

**Total Variantes**: 5 × 5 × 4 = **100 variantes** (mais 3,125 do PA_SIGNAL_DIR base = **312,500**)

**Justificativa**: Filtra apenas tendencias fortes. ADX e slope altos reduzem falsos sinais.

---

### 5. PA_SLOPE_TREND_S25_A25

**Memoria de Calculo**:
```python
# Trend com foco no slope
PA_SLOPE_TREND_S25_A25 = np.where(
    (EMA5_SLOPE_ABS >= 25) &      # Slope minimo
    (ADX7 >= 25) &                # ADX minimo
    (PA_SIGNAL_DIR != 0),
    PA_SIGNAL_DIR, 0
)
```

**Parametros Atuais**:
| Parametro | Valor | Tipo | Local |
|-----------|-------|------|-------|
| `SLOPE_MIN` | 25 | Threshold | `v81.py:272` |
| `ADX_MIN` | 25 | Threshold | `v81.py:273` |
| `ADX7 period` | 7 | Periodo | `v81.py:84` |

**Grid Recomendado**:
```python
SLOPE_MIN  = [10, 15, 20, 25, 30]  # 5 valores
ADX_MIN    = [20, 25, 30, 35, 40]  # 5 valores
ADX_PERIOD = [7, 10, 14, 20]       # 4 valores
```

**Total Variantes**: 5 × 5 × 4 = **100 variantes** (mais 3,125 do base = **312,500**)

**Justificativa**: Similar ao STRONG_TREND mas com pesos diferentes.

---

## GRUPO 3: BREAKOUT / EXHAUSTAO (3 sinais)

### 6. PA_ADX_BREAK_A25

**Memoria de Calculo**:
```python
# Breakout com ADX crescendo
adx_delta = ADX7 - ADX7.shift(3)  # Mudanca em 3 candles

PA_ADX_BREAK_A25 = np.where(
    (adx_delta > 0) &             # ADX subindo
    (ADX7 > 25) &                 # ADX acima de 25
    (PA_SIGNAL_DIR != 0),
    PA_SIGNAL_DIR, 0
)
```

**Parametros Atuais**:
| Parametro | Valor | Tipo | Local |
|-----------|-------|------|-------|
| `ADX_MIN` | 25 | Threshold | `v81.py:282` |
| `adx_delta_min` | 0 | Threshold | `v81.py:281` |
| `adx_delta shift` | 3 | Periodo | `v81.py:280` |
| `ADX7 period` | 7 | Periodo | `v81.py:84` |

**Grid Recomendado**:
```python
ADX_MIN        = [20, 25, 30, 35, 40]   # 5 valores
ADX_DELTA_MIN  = [0, 0.5, 1.0, 2.0]     # 4 valores
ADX_DELTA_SHIFT = [1, 2, 3, 5]          # 4 valores
```

**Total Variantes**: 5 × 4 × 4 = **80 variantes** (mais 3,125 do base = **250,000**)

**Justificativa**: Captura inicio de tendencias (ADX comecando a subir).

---

### 7. PA_EXHAUST_Dn1_0_M40

**Memoria de Calculo**:
```python
# Exaustao de tendencia (ADX caindo)
adx_delta = ADX7 - ADX7.shift(3)

PA_EXHAUST_Dn1_0_M40 = np.where(
    (adx_delta < -1.0) &          # ADX caindo rapido
    (ADX7 > 25) &                 # Ainda em tendencia
    (ADX7 < 40) &                 # Mas nao extrema
    (PA_SIGNAL_DIR != 0),
    PA_SIGNAL_DIR, 0
)
```

**Parametros Atuais**:
| Parametro | Valor | Tipo | Local |
|-----------|-------|------|-------|
| `ADX_MIN` | 25 | Threshold | `v81.py:288` |
| `ADX_MAX` | 40 | Threshold | `v81.py:289` |
| `adx_delta_max` | -1.0 | Threshold | `v81.py:287` |
| `adx_delta shift` | 3 | Periodo | `v81.py:286` |

**Grid Recomendado**:
```python
ADX_MIN       = [20, 25, 30, 35]        # 4 valores
ADX_MAX       = [35, 40, 45, 50]        # 4 valores
ADX_DELTA_MAX = [-0.5, -1.0, -2.0, -3.0]  # 4 valores
ADX_DELTA_SHIFT = [1, 2, 3, 5]          # 4 valores
```

**Total Variantes**: 4 × 4 × 4 × 4 = **256 variantes** (mais 3,125 do base = **800,000**)

**Justificativa**: Sinal de reversao por exaustao — ADX caindo indica enfraquecimento.

---

### 8. PA_GK_BREAK_G0_001

**Memoria de Calculo**:
```python
# Breakout Garman-Klass (volatilidade)
PA_GK_BREAK_G0_001 = np.where(
    (GK_RATIO > 0.001) &          # GK minimo (volatilidade)
    (ADX7 > 25) &                 # Tendencia presente
    (PA_SIGNAL_DIR != 0),
    PA_SIGNAL_DIR, 0
)
```

**Parametros Atuais**:
| Parametro | Valor | Tipo | Local |
|-----------|-------|------|-------|
| `GK_MIN` | 0.001 | Threshold | `v81.py:293` |
| `ADX_MIN` | 25 | Threshold | `v81.py:294` |
| `ADX7 period` | 7 | Periodo | `v81.py:84` |

**Grid Recomendado**:
```python
GK_MIN   = [0.0005, 0.001, 0.002, 0.005]  # 4 valores
ADX_MIN  = [20, 25, 30, 35, 40]           # 5 valores
```

**Total Variantes**: 4 × 5 = **20 variantes** (mais 3,125 do base = **62,500**)

**Justificativa**: GK_RATIO mede volatilidade intraday — breakouts com GK alto sao mais fortes.

---

## GRUPO 4: PATTERNS (2 sinais)

### 9. PA_VCP_C0_6

**Memoria de Calculo**:
```python
# Volatility Contraction Pattern
range_ratio = (high - low) / range_ma20

PA_VCP_C0_6 = np.where(
    (range_ratio < 0.6) &           # Candle atual muito estreito
    (range_ratio.shift(1) < 0.7) &  # Anterior tambem estreito
    (PA_SIGNAL_DIR != 0),
    PA_SIGNAL_DIR, 0
)
```

**Parametros Atuais**:
| Parametro | Valor | Tipo | Local |
|-----------|-------|------|-------|
| `range_curr_max` | 0.6 | Threshold | `v81.py:299` |
| `range_prev_max` | 0.7 | Threshold | `v81.py:300` |
| `range_ma20` | 20 | Periodo | `v81.py:173` |

**Grid Recomendado**:
```python
RANGE_CURR_MAX = [0.4, 0.5, 0.6, 0.7, 0.8]  # 5 valores
RANGE_PREV_MAX = [0.5, 0.6, 0.7, 0.8, 1.0]  # 5 valores
RANGE_MA_PERIOD = [10, 14, 20, 30]          # 4 valores
```

**Total Variantes**: 5 × 5 × 4 = **100 variantes** (mais 3,125 do base = **312,500**)

**Justificativa**: VCP = contracao de volatilidade antes de explosao. Thresholds afetam quao "apertado" e o pattern.

---

### 10. PA_LIQ_GRAB

**Memoria de Calculo**:
```python
# Liquidity Grab / False Breakout
prev_10_high = rolling(10).max()
prev_10_low = rolling(10).min()

grab_buy = (high > prev_10_high.shift(1)) & (close < prev_10_high.shift(1))
grab_sell = (low < prev_10_low.shift(1)) & (close > prev_10_low.shift(1))

PA_LIQ_GRAB = 1 se grab_buy, -1 se grab_sell, 0 caso contrario
```

**Parametros Atuais**:
| Parametro | Valor | Tipo | Local |
|-----------|-------|------|-------|
| `lookback` | 10 | Periodo | `v81.py:370-371` |

**Grid Recomendado**:
```python
LOOKBACK = [5, 8, 10, 14, 20]  # 5 valores
```

**Total Variantes**: **5 variantes** (nao depende do PA_SIGNAL_DIR)

**Justificativa**: Lookback afeta quao recente e o high/low de referencia.

---

## GRUPO 5: CRUZAMENTOS (2 sinais)

### 11. PA_MA_CROSS_F9_S21

**Memoria de Calculo**:
```python
# Cruzamento de medias moveis
ma_fast = close.rolling(9).mean()
ma_slow = close.rolling(21).mean()
cross = (ma_fast > ma_slow).astype(int) - (ma_fast > ma_slow).astype(int).shift(1)

PA_MA_CROSS_F9_S21 = cross  # 1 = cruzou pra cima, -1 = cruzou pra baixo
```

**Parametros Atuais**:
| Parametro | Valor | Tipo | Local |
|-----------|-------|------|-------|
| `fast_period` | 9 | Periodo | `v81.py:304` |
| `slow_period` | 21 | Periodo | `v81.py:305` |

**Grid Recomendado**:
```python
FAST_PERIOD = [5, 7, 9, 10, 14]    # 5 valores
SLOW_PERIOD = [14, 20, 21, 30, 50] # 5 valores
```

**Total Variantes**: 5 × 5 = **25 variantes** (independente)

**Justificativa**: Periodos afetam sensibilidade do cruzamento.

---

### 12. PA_HMA_CROSS_F5_S10

**Memoria de Calculo**:
```python
# Cruzamento de medias (na verdade SMA, nao HMA)
hma_fast = close.rolling(5).mean()
hma_slow = close.rolling(10).mean()
hma_cross = (hma_fast > hma_slow).astype(int) - (hma_fast > hma_slow).astype(int).shift(1)

PA_HMA_CROSS_F5_S10 = hma_cross
```

**Parametros Atuais**:
| Parametro | Valor | Tipo | Local |
|-----------|-------|------|-------|
| `fast_period` | 5 | Periodo | `v81.py:310` |
| `slow_period` | 10 | Periodo | `v81.py:311` |

⚠️ **OBS**: O nome e incorreto — usa SMA, nao HMA (ver comentario linha 309).

**Grid Recomendado**:
```python
FAST_PERIOD = [3, 5, 7, 9, 10]   # 5 valores
SLOW_PERIOD = [8, 10, 14, 20, 30] # 5 valores
```

**Total Variantes**: 5 × 5 = **25 variantes** (independente)

**Justificativa**: Cruzamento mais rapido que MA_CROSS (periodos menores).

---

## GRUPO 6: REGIME / QUALIDADE (2 sinais)

### 13. PA_EFF_RATIO_E0_6

**Memoria de Calculo**:
```python
# Kaufman Efficiency Ratio
PA_EFF_RATIO_E0_6 = np.where(
    (EFF_RATIO_10 > 0.6) &        # Eficiencia minima
    (PA_SIGNAL_DIR != 0),
    PA_SIGNAL_DIR, 0
)
```

**Parametros Atuais**:
| Parametro | Valor | Tipo | Local |
|-----------|-------|------|-------|
| `ER_MIN` | 0.6 | Threshold | `v81.py:317` |
| `ER_PERIOD` | 10 | Periodo | `v81.py:316` |

**Grid Recomendado**:
```python
ER_MIN    = [0.3, 0.4, 0.5, 0.6, 0.7]  # 5 valores
ER_PERIOD = [5, 8, 10, 14, 20]         # 5 valores
```

**Total Variantes**: 5 × 5 = **25 variantes** (mais 3,125 do base = **78,125**)

**Justificativa**: ER mede eficiencia da tendencia (0 = ruido, 1 = tendencia pura).

---

### 14. PA_CHOP_C38_2

**Memoria de Calculo**:
```python
# Choppiness Index (mercado lateral vs tendencia)
PA_CHOP_C38_2 = np.where(
    (CHOP_INDEX < 38.2) &         # Abaixo de 38.2 = tendencia
    (PA_SIGNAL_DIR != 0),
    PA_SIGNAL_DIR, 0
)
```

**Parametros Atuais**:
| Parametro | Valor | Tipo | Local |
|-----------|-------|------|-------|
| `CHOP_MAX` | 38.2 | Threshold | `v81.py:323` |
| `CHOP_PERIOD` | 14 | Periodo | `v81.py:322` |

**Grid Recomendado**:
```python
CHOP_MAX    = [30.0, 38.2, 45.0, 50.0, 61.8]  # 5 valores
CHOP_PERIOD = [7, 10, 14, 20, 30]             # 5 valores
```

**Total Variantes**: 5 × 5 = **25 variantes** (mais 3,125 do base = **78,125**)

**Justificativa**: CHOP < 38.2 = tendencia, > 50 = range. Threshold define o corte.

---

## GRUPO 7: REVERSAO RSI (2 sinais)

### 15. PA_REV_RSI_B10

**Memoria de Calculo**:
```python
# Reversao com RSI curto (2 periodos)
rsi2 = calc_rsi(close, 2)

PA_REV_RSI_B10 = np.where(
    rsi2 < 10, 1,          # RSI muito baixo = compra
    np.where(rsi2 > 90, -1, 0)  # RSI muito alto = venda
)
```

**Parametros Atuais**:
| Parametro | Valor | Tipo | Local |
|-----------|-------|------|-------|
| `RSI_PERIOD` | 2 | Periodo | `v81.py:332` |
| `RSI_BUY_MAX` | 10 | Threshold | `v81.py:333` |
| `RSI_SELL_MIN` | 90 | Threshold | `v81.py:333` |

**Grid Recomendado**:
```python
RSI_PERIOD   = [2, 3, 5, 7, 9]        # 5 valores
RSI_BUY_MAX  = [5, 10, 15, 20, 30]    # 5 valores
RSI_SELL_MIN = [70, 80, 85, 90, 95]   # 5 valores
```

**Total Variantes**: 5 × 5 × 5 = **125 variantes** (independente)

**Justificativa**: RSI curto (2) e muito sensivel — thresholds definem extremos.

---

### 16. PA_REV_RSI_S90

⚠️ **IDENTICO AO PA_REV_RSI_B10** — linhas 333-334 geram exatamente a mesma condicao.

**Memoria de Calculo**:
```python
# Mesma logica que B10 (nome diferente, mesma implementacao)
rsi2 = calc_rsi(close, 2)

PA_REV_RSI_S90 = np.where(
    rsi2 < 10, 1,
    np.where(rsi2 > 90, -1, 0)
)
```

**Parametros**: Mesmos que B10

**Grid Recomendado**: Mesmo que B10 — **125 variantes**

**Acao Recomendada**: Unificar os dois sinais ou corrigir thresholds (provavelmente S90 deveria ter thresholds invertidos).

**Justificativa**: Redundante com B10 — considerar unificar.

---

## GRUPO 8: VWAP / Z-SCORE (3 sinais)

### 17. PA_VWAP_Z_Z2_0

**Memoria de Calculo**:
```python
# Distancia da VWAP em unidades de std (Z-score)
VWAP_Z = (close - VWAP) / VWAP_std.rolling(20)

PA_VWAP_Z_Z2_0 = np.where(
    VWAP_Z < -2.0, 1,      # VWAP muito abaixo = compra
    np.where(VWAP_Z > 2.0, -1, 0)  # VWAP muito acima = venda
)
```

**Parametros Atuais**:
| Parametro | Valor | Tipo | Local |
|-----------|-------|------|-------|
| `Z_THRESHOLD` | 2.0 | Threshold | `v81.py:337` |
| `Z_PERIOD` | 20 | Periodo | `v81.py:180` |
| `Z_CLIP` | [-5, 5] | Clip | `v81.py:181` |

**Grid Recomendado**:
```python
Z_THRESHOLD = [1.0, 1.5, 2.0, 2.5, 3.0]  # 5 valores
Z_PERIOD    = [10, 14, 20, 30]            # 4 valores
Z_CLIP      = [[-3,3], [-5,5], [-10,10]]  # 3 valores
```

**Total Variantes**: 5 × 4 × 3 = **60 variantes** (independente)

**Justificativa**: Z-score alto indica esticamento — threshold define o que e "extremo".

---

### 18. PA_VWAP_REV_D1_0

**Memoria de Calculo**:
```python
# Reversao VWAP com filtro ADX
dist = ATR * 1.0  # Distancia em ATR

PA_VWAP_REV_D1_0 = np.where(
    (close < VWAP - dist) & (ADX7 < 25), 1,  # VWAP muito abaixo, sem tendencia
    np.where((close > VWAP + dist) & (ADX7 < 25), -1, 0)
)
```

**Parametros Atuais**:
| Parametro | Valor | Tipo | Local |
|-----------|-------|------|-------|
| `dist_mult` | 1.0 | Multiplicador ATR | `v81.py:341` |
| `ADX_MAX` | 25 | Threshold | `v81.py:342` |
| `ADX7 period` | 7 | Periodo | `v81.py:84` |

**Grid Recomendado**:
```python
DIST_MULT = [0.5, 1.0, 1.5, 2.0, 3.0]  # 5 valores
ADX_MAX   = [20, 25, 30, 35]            # 4 valores
```

**Total Variantes**: 5 × 4 = **20 variantes** (independente)

**Justificativa**: Distancia da VWAP + filtro de regime (ADX baixo = range).

---

### 19. PA_VWAP_STRETCH

**Memoria de Calculo**:
```python
# Esticamento VWAP com filtro de range
ATR_STRETCH = (close - VWAP) / ATR

PA_VWAP_STRETCH = np.where(
    (ATR_STRETCH < -2.0) & (range_ratio < 0.8), 1,  # VWAP esticado, candle estreito
    np.where((ATR_STRETCH > 2.0) & (range_ratio < 0.8), -1, 0)
)
```

**Parametros Atuais**:
| Parametro | Valor | Tipo | Local |
|-----------|-------|------|-------|
| `stretch_threshold` | 2.0 | Threshold | `v81.py:355` |
| `range_max` | 0.8 | Threshold | `v81.py:356` |

**Grid Recomendado**:
```python
STRETCH_THRESHOLD = [1.0, 1.5, 2.0, 2.5, 3.0]  # 5 valores
RANGE_MAX         = [0.5, 0.6, 0.7, 0.8, 1.0]  # 5 valores
```

**Total Variantes**: 5 × 5 = **25 variantes** (independente)

**Justificativa**: Combina esticamento VWAP com contracao de range.

---

## GRUPO 9: CANAIS / ENVELOPES (2 sinais)

### 20. PA_KELT_ATR_M2_0

**Memoria de Calculo**:
```python
# Canais de Keltner (EMA + ATR)
KELT_UPPER = EMA20 + ATR * 2.0
KELT_LOWER = EMA20 - ATR * 2.0

PA_KELT_ATR_M2_0 = np.where(
    close < KELT_LOWER, 1,   # Abaixo do canal = compra
    np.where(close > KELT_UPPER, -1, 0)  # Acima do canal = venda
)
```

**Parametros Atuais**:
| Parametro | Valor | Tipo | Local |
|-----------|-------|------|-------|
| `ATR_MULT` | 2.0 | Multiplicador | `v81.py:349` |
| `EMA_PERIOD` | 20 | Periodo | `v81.py:348` |
| `ATR window` | 14 | Periodo | `indicators.py:105` |

**Grid Recomendado**:
```python
ATR_MULT   = [1.0, 1.5, 2.0, 2.5, 3.0]  # 5 valores
EMA_PERIOD = [10, 14, 20, 30]            # 4 valores
ATR_WINDOW = [7, 10, 14, 20]             # 4 valores
```

**Total Variantes**: 5 × 4 × 4 = **80 variantes** (independente)

**Justificativa**: Multiplicador define largura do canal — afeta frequencia de sinais.

---

### 21. PA_MFI_B20

**Memoria de Calculo**:
```python
# Money Flow Index (volume + preco)
PA_MFI_B20 = np.where(
    MFI14 < 20, 1,      # MFI muito baixo = compra
    np.where(MFI14 > 80, -1, 0)  # MFI muito alto = venda
)
```

**Parametros Atuais**:
| Parametro | Valor | Tipo | Local |
|-----------|-------|------|-------|
| `MFI_PERIOD` | 14 | Periodo | `v81.py:363` |
| `MFI_BUY_MAX` | 20 | Threshold | `v81.py:364` |
| `MFI_SELL_MIN` | 80 | Threshold | `v81.py:364` |

**Grid Recomendado**:
```python
MFI_PERIOD   = [7, 10, 14, 20, 30]     # 5 valores
MFI_BUY_MAX  = [10, 15, 20, 25, 30]    # 5 valores
MFI_SELL_MIN = [70, 75, 80, 85, 90]    # 5 valores
```

**Total Variantes**: 5 × 5 × 5 = **125 variantes** (independente)

**Justificativa**: MFI combina preco e volume — thresholds definem extremos.

---

## GRUPO 10: MOMENTUM (1 sinal)

### 22. PA_TSI_T25

**Memoria de Calculo**:
```python
# True Strength Index (momentum suavizado)
PA_TSI_T25 = np.where(
    TSI < -25, 1,      # TSI muito negativo = compra
    np.where(TSI > 25, -1, 0)  # TSI muito positivo = venda
)
```

**Parametros Atuais**:
| Parametro | Valor | Tipo | Local |
|-----------|-------|------|-------|
| `TSI_THRESHOLD` | 25 | Threshold | `v81.py:367` |
| `TSI_R` | 25 | Periodo 1 | `v81.py:366` |
| `TSI_S` | 13 | Periodo 2 | `v81.py:366` |

**Grid Recomendado**:
```python
TSI_THRESHOLD = [10, 15, 25, 30, 50]   # 5 valores
TSI_R         = [13, 20, 25, 30, 50]   # 5 valores
TSI_S         = [7, 10, 13, 20, 25]    # 5 valores
```

**Total Variantes**: 5 × 5 × 5 = **125 variantes** (independente)

**Justificativa**: TSI e momentum de segunda ordem — thresholds e periodos afetam sensibilidade.

---

## GRUPO 11: CALENDARIO (1 sinal)

### 23. PA_TUESDAY

**Memoria de Calculo**:
```python
# Efeito calendario (terca-feira)
day_of_week = dt.weekday()  # 0=seg, 1=ter, ..., 4=sex

PA_TUESDAY = np.where(
    day_of_week == 1,      # Apenas terca-feira
    PA_SIGNAL_DIR,         # Herda direcao
    0
)
```

**Parametros Atuais**:
| Parametro | Valor | Tipo | Local |
|-----------|-------|------|-------|
| `day_of_week` | 1 (terca) | Fixo | `v81.py:376` |

**Grid Recomendado**:
```python
DAY_OF_WEEK = [0, 1, 2, 3, 4]  # Seg a Sex (5 valores)
```

**Total Variantes**: **5 variantes** (independente)

**Justificativa**: Testar outros dias da semana — efeito calendario pode variar.

---

## RESUMO GERAL

| Grupo | Sinais | Variantes Base | Total com Base (PA_SIGNAL_DIR) |
|-------|--------|----------------|--------------------------------|
| 1. Base | 3 | 3,125 + 15,625 + 3,125 | 21,875 |
| 2. Trend | 2 | 312,500 + 312,500 | 625,000 |
| 3. Breakout | 3 | 250,000 + 800,000 + 62,500 | 1,112,500 |
| 4. Patterns | 2 | 312,500 + 5 | 312,505 |
| 5. Cross | 2 | 25 + 25 | 50 |
| 6. Regime | 2 | 78,125 + 78,125 | 156,250 |
| 7. RSI | 2 | 125 + 125 | 250 |
| 8. VWAP | 3 | 60 + 20 + 25 | 105 |
| 9. Channels | 2 | 80 + 125 | 205 |
| 10. Momentum | 1 | 125 | 125 |
| 11. Calendar | 1 | 5 | 5 |

**Total Geral (sem TP/SL/ATR)**: ~**2,228,615 variantes**

**Com TP/SL/ATR (4,032 combos da V8.6)**: 2,228,615 × 4,032 × 2 (BUY+SELL) = **18.0 BILHOES combos**

---

## PARAMETROS MAIS FREQUENTES (PRIORIDADE DE OTIMIZACAO)

| Parametro | Aparece em N sinais | Valor Atual | Faixa Sugerida |
|-----------|---------------------|-------------|----------------|
| **ADX7 threshold** | 6 (STRONG, SLOPE, ADX_BREAK, EXHAUST, GK_BREAK, VWAP_REV) | 25 | [20, 25, 30, 35, 40] |
| **ADX7 period** | 6 | 7 | [7, 10, 14, 20] |
| **EMA20 span** | 3 (DIR, KELT, + heranca) | 20 | [10, 15, 20, 30, 50] |
| **ATR multiplier** | 2 (KELT=2.0, VWAP_REV=1.0) | 1.0-2.0 | [0.5, 1.0, 1.5, 2.0, 2.5, 3.0] |
| **range_ratio threshold** | 3 (DIR, VCP, VWAP_STRETCH) | 0.5-0.8 | [0.3, 0.4, 0.5, 0.6, 0.7, 0.8] |
| **RSI period** | 2 (REV_RSI_B10/S90) | 2 | [2, 3, 5, 7, 9] |
| **RSI oversold threshold** | 2 | 10 | [5, 10, 15, 20] |
| **RSI overbought threshold** | 2 | 90 | [80, 85, 90, 95] |
| **Z_SCORE threshold** | 1 (DIR) | 3.0 | [1.5, 2.0, 2.5, 3.0, 4.0] |
| **EMA_SLOPE diff** | 1 (DIR) | 3 | [1, 2, 3, 5, 8] |
| **adx_delta shift** | 2 (ADX_BREAK, EXHAUST) | 3 | [1, 2, 3, 5] |
| **adx_delta threshold** | 2 | 0 / -1.0 | [-3, -2, -1, 0, 1, 2] |
| **MA cross periods** | 2 (MA_CROSS, HMA_CROSS) | 9/21, 5/10 | multiplas combinacoes |
| **CHOP threshold** | 1 | 38.2 | [30, 38.2, 45, 50, 61.8] |
| **EFF_RATIO threshold** | 1 | 0.6 | [0.3, 0.4, 0.5, 0.6, 0.7] |
| **MFI thresholds** | 1 | 20/80 | [10/90, 15/85, 20/80, 25/75, 30/70] |
| **TSI thresholds** | 1 | -25/25 | [-10/10, -15/15, -25/25, -30/30, -50/50] |
| **TSI periods (r/s)** | 1 | 25/13 | [13/7, 20/10, 25/13, 30/20, 50/25] |
| **VWAP_Z threshold** | 1 | 2.0 | [1.0, 1.5, 2.0, 2.5, 3.0] |
| **ATR_STRETCH threshold** | 1 | 2.0 | [1.0, 1.5, 2.0, 2.5, 3.0] |
| **GK_RATIO threshold** | 1 | 0.001 | [0.0005, 0.001, 0.002, 0.005] |
| **LIQ_GRAB lookback** | 1 | 10 | [5, 8, 10, 14, 20] |
| **DAY_OF_WEEK** | 1 | 1 (Terca) | [0, 1, 2, 3, 4] |

---

## OBSERVACOES CRITICAS

1. **PA_REV_RSI_B10 e PA_REV_RSI_S90 sao DUPLICADOS** — linhas 333-334 geram exatamente a mesma condicao (`rsi2 < 10 → 1, rsi2 > 90 → -1`). Isso precisa ser corrigido (provavelmente PA_REV_RSI_S90 deveria ter thresholds invertidos ou ser removido).

2. **PA_HMA_CROSS_F5_S10 usa SMA, nao HMA** — conforme comentario na linha 309. O nome esta incorreto.

3. **V8_S_MIN=0.0** significa que QUALQUER inclinacao positiva/negativa passa — parametro sem efeito pratico.

4. **Muitos sinais herdam `PA_SIGNAL_DIR != 0`** como filtro de direcao — otimizar PA_SIGNAL_DIR tem efeito cascata em 13 sinais.

5. **Nenhum parametro e configuravel via argumento de funcao** — todos estao hardcoded, sem suporte a grid search externo.

6. **Total de 18B combos e IMPRACTICAVEL** — necessario estrategia hierarquica ou amostragem.

---

## IMPLEMENTACAO SUGERIDA

### Opcao A: Grid Completo (18B combos) — NAO RECOMENDADO
- **Tempo estimado**: 18B / 18K/s = 11.5 dias
- **Cobertura**: 100% dos parametros
- **Recomendacao**: **INVIABIL** — apenas com cluster distribuido

### Opcao B: Grid Reduzido (Top 10 sinais) — RECOMENDADO
- Focar nos 10 sinais com maior edge no V8.6
- **Tempo estimado**: ~4 horas
- **Recomendacao**: Melhor custo-beneficio

### Opcao C: Grid Hierarquico (RECOMENDADO)
1. **Fase 1**: Grid grosso (50% dos valores) — ~4.5B combos (~3 dias)
2. **Fase 2**: Grid fino apenas no top 20% — ~900M combos (~14 horas)
3. **Total**: ~3.5 dias

### Opcao D: Otimizacao por Sinal (MAIS PRATICO)
- Otimizar CADA sinal separadamente (independente)
- **Tempo por sinal**: 50-500M combos / 18K/s = 1-8 horas
- **Total**: 23 sinais × ~4 horas = ~4 dias (mas pode ser feito em paralelo)
- **Vantagem**: Permite early stopping por sinal, mais flexivel

---

## PROXIMOS PASSOS

1. **Validar este plano** — Confirmar grids propostos
2. **Corrigir bugs identificados**:
   - Unificar PA_REV_RSI_B10/S90 ou corrigir thresholds
   - Renomear PA_HMA_CROSS para PA_SMA_CROSS
3. **Implementar gerador de variantes** — Um script por grupo de sinais
4. **Escolher estrategia**:
   - Opcao B (Top 10 sinais) — mais rapido
   - Opcao D (Por sinal) — mais flexivel
5. **Executar F1** — Grid personalizado
6. **Consolidar resultados** — Top config por sinal
7. **OOS validation** — Testar top configs em Abril 2026
