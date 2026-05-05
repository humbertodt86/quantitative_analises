# ARQUITETURA V8.6 — PIPELINE COMPLETO

**Data**: 2026-05-04
**Correção**: V8.6 = F1 Engine | V8.7 Signals = Construtor de Sinais Otimizado

---

## 📊 VISÃO GERAL

```
┌─────────────────────────────────────────────────────────────┐
│                    PIPELINE V8.6                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. BUILD SINAIS (V8.7 Signals)                            │
│     scripts/build_win_signals_v81.py                        │
│     ↓                                                       │
│     Gera 23 parquet files com sinais PA_*                   │
│     (3,150 variantes otimizadas × 23 sinais)                │
│                                                             │
│  2. F1 FAST SCREENER (V8.6 Engine)                         │
│     scripts/f1_full_scan_v86.py                             │
│     ↓                                                       │
│     Avalia 7.26M combos @ 50k/s = 2.4 minutos               │
│     (TP × SL × ATR × Sinais)                                │
│                                                             │
│  3. F2 VALIDATION                                          │
│     engines/f2_tick_last.py                                 │
│     ↓                                                       │
│     Top 10 do F1 com ticks reais (last prices)              │
│                                                             │
│  4. F3 GUARDRAILS                                          │
│     engines/f3_tick_ba.py                                   │
│     ↓                                                       │
│     Top 3 do F2 com bid/ask reais + guardrails              │
│                                                             │
│  5. OOS VALIDATION                                         │
│     Dados Abril 2026 (nunca vistos)                         │
│     ↓                                                       │
│     Validação final                                         │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. V8.7 SIGNALS — CONSTRUTOR DE SINAIS

**Arquivo**: `scripts/build_win_signals_v81.py` (atualizar para V8.7)

**Função**: Gerar sinais PA_* com grids otimizados para alimentar F1.

### Otimizações V8.7

#### A. Poda por Correlação
| Sinal | Original | V8.7 | Redução |
|-------|----------|------|---------|
| PA_SIGNAL_DIR | 3,125 | **18** | 173x |
| PA_REV_RSI | 125 | **12** | 10x |
| Trend Following | 625,000 | **648** | 964x |
| **Total** | 2.2M | **3,150** | 707x |

#### B. Bugs Corrigidos
1. **PA_REV_RSI_B10/S90** → Unificar em `PA_REV_RSI_UNIFIED`
2. **PA_HMA_CROSS** → Renomear para `PA_SMA_CROSS`
3. **V8_S_MIN=0.0** → Grid `[0, 10, 20]`

#### C. Escalonamento Geométrico
```python
# EMA_PERIOD (linear → geométrico)
[10,15,20,30,50] → [10,21,50,100,200]

# TP/SL (passos 0.5x → 1.0x)
TP: [1.0,1.5,2.0,2.5,3.0] → [1.0,2.0,3.0,4.0]
SL: [2.0,2.5,3.0,3.5,4.0,4.5,5.0] → [2.0,3.0,5.0,7.0]

# MA Cross
FAST: [5,7,9,10,14] → [5,9,21]
SLOW: [14,20,21,30,50] → [21,50,100]
```

#### D. Binning de Volatilidade (ATR)
```python
# 42 combinações → 3 regimes
ATR_REGIME = {
    'low': (50, 300),      # ATR 50-300
    'normal': (300, 800),  # ATR 300-800
    'high': (800, 9999)    # ATR 800+
}
```

#### E. Filtro Piso de Viabilidade (Anti-HFT)
```python
def is_viable(tp_pts, sl_pts, atr):
    if sl_pts < 150: return False           # SL mínimo 150 pts
    if sl_pts < atr * 1.0: return False     # SL >= 1.0×ATR
    if tp_pts < 100: return False           # TP mínimo 100 pts
    if sl_pts / tp_pts > 4.0: return False  # SL/TP ratio
    if tp_pts / sl_pts > 2.0: return False  # TP/SL ratio
    return True
```

### Output V8.7 Signals
```
data/variants/
├── PA_SIGNAL_DIR.parquet          (3,150 variantes)
├── PA_SIGNAL_DIR_V2.parquet       (54 variantes)
├── PA_SIGNAL_REV.parquet          (18 variantes)
├── PA_STRONG_TREND_A25_S20.parquet (324 variantes)
├── PA_SLOPE_TREND_S25_A25.parquet  (324 variantes)
├── ... (23 arquivos total)
└── total: ~70MB
```

**Tempo de geração**: ~5 minutos

---

## 2. V8.6 F1 — FAST SCREENER

**Arquivo**: `scripts/f1_full_scan_v86.py`

**Função**: Avaliar 7.26M combos em 2.4 minutos.

### Características V8.6 F1

| Característica | V8.5 | V8.6 |
|----------------|------|------|
| **Gatilho Min Range** | 150 pts | **200 pts** |
| **Progress M1 Candles** | 4 | **2 candles** |
| **BE Offset** | 10 pts | **50 pts** |
| **Max SL Consec** | ativo | **99 (desativado)** |
| **Combos/s** | ~200k | **~50k** (mais guards) |

### Parâmetros V8.6

```python
# ADX7
adx_period: int      = 14
adx_threshold: float = 25.0
use_adx7: bool       = True

# Gatilhos
gatilho_min_range: int   = 200   # RANGE: dist mínima 200pts
gatilho_min_trend: int   = 150   # TREND: dist mínima 150pts
gatilho_max: int         = 700   # fixo (RANGE only)

# TP/SL
tp_range_mult: float = 1.4
sl_range_mult: float = 0.8
tp_trend_mult: float = 1.5
sl_trend_mult: float = 0.8

# H-Progress M1
progress_m1_candles: int = 2      # 2 candles M1 (~2min)
progress_threshold: float = 0.15
progress_mode: str       = "TP30"
be_offset: int           = 50     # BE+50pts = R$8 líquido

# H-Slope
slope_decay_factor: float = 0.65
```

### Grid Search V8.6 F1

**Combos Totais**:
```
3,150 (sinais) × 1,152 (TP/SL/ATR) × 2 (BUY+SELL) = 7,257,600 combos
```

**Tempo**: 7.26M / 50k/s = **145 segundos = 2.4 minutos**

### Output V8.6 F1
```
data/results/
└── F1_FULL_RESULTS_V86.csv
    ├── signal_name
    ├── tp_mult
    ├── sl_mult
    ├── atr_regime
    ├── direction (BUY/SELL)
    ├── net_pnl
    ├── win_rate
    ├── n_trades
    └── sharpe
```

---

## 3. F2 VALIDATION — TICK_LAST

**Arquivo**: `engines/f2_tick_last.py`

**Função**: Validar top 10 do F1 com ticks reais (last prices).

### Características
- **Dados**: `data/WIN_merged_all.parquet` (last ticks)
- **Período**: IS (Jan-Mar 2026)
- **Velocidade**: ~2 combos/s
- **Guardrails**: BE, Grace Period, Circuit Breaker ativos

### Output F2
```
data/results/
└── F2_VALIDATION_TOP10.csv
    ├── rank
    ├── signal_name
    ├── config_hash
    ├── f1_pnl
    ├── f2_pnl
    ├── pnl_delta (%)
    └── validated (bool)
```

**Tempo**: 10 configs × ~5 min = **~50 minutos**

---

## 4. F3 GUARDRAILS — TICK_BA

**Arquivo**: `engines/f3_tick_ba.py`

**Função**: Validar top 3 do F2 com bid/ask reais + guardrails completos.

### Características
- **Dados**: `data/ticks/WIN*.parquet` (bid/ask reais)
- **Período**: IS (Jan-Mar 2026)
- **Velocidade**: ~2 combos/s
- **Guardrails**: TODOS ativos

### Guardrails F3
```python
# Break Even
be_trigger: int = 200      # Ativa BE com 200 pts lucro
be_offset: int  = 50       # Sai a 50 pts do BE

# Grace Period
grace_candles: int = 2     # 2 candles sem sair no SL
hp_candles: int      = 2   # H-Progress M1
hp_threshold: float  = 0.15

# Circuit Breaker
max_sl_consec: int = 5     # Stop após 5 SLs seguidos
cooldown_candles: int = 2  # Espera 2 candles após SL

# Slope Decay
slope_decay_factor: float = 0.65

# Hour Filter
start_hour: int = 10       # Inicia às 10:00
last_entry_hour: int = 17  # Última entrada às 17:00
panic_close_hour: int = 17 # Panic close às 17:55
```

### Output F3
```
data/results/
└── F3_GUARDRAILS_TOP3.csv
    ├── rank
    ├── signal_name
    ├── config_hash
    ├── f2_pnl
    ├── f3_pnl
    ├── pnl_delta (%)
    ├── sharpe
    ├── max_dd
    └── validated (bool)
```

**Tempo**: 3 configs × ~10 min = **~30 minutos**

---

## 5. OOS VALIDATION

**Função**: Testar top 3 do F3 em dados nunca vistos.

### Dados OOS
- **Período**: Abril 2026
- **Arquivos**: `data/ticks/WIN_2026-04-*.parquet`
- **Tipo**: bid/ask reais

### Output OOS
```
data/results/
└── OOS_VALIDATION_FINAL.csv
    ├── signal_name
    ├── config_hash
    ├── is_pnl (Jan-Mar)
    ├── oos_pnl (Abril)
    ├── pnl_delta (%)
    ├── is_wr
    ├── oos_wr
    ├── is_trades
    ├── oos_trades
    └── passed (bool)
```

**Critério de Aprovação**:
- OOS PnL > 0
- OOS WR > 35%
- OOS N > 10 trades
- PnL Delta < 50% (não degradar >50% vs IS)

---

## 📊 RESUMO DO PIPELINE

| Fase | Input | Output | Tempo |
|------|-------|--------|-------|
| **V8.7 Signals** | `super_win_continuous.parquet` | 23 parquets (3,150 variantes) | 5 min |
| **V8.6 F1** | 23 parquets + `_fev_cache_v2.npz` | `F1_FULL_RESULTS_V86.csv` (7.26M combos) | 2.4 min |
| **F2 Validation** | Top 10 F1 | `F2_VALIDATION_TOP10.csv` | 50 min |
| **F3 Guardrails** | Top 3 F2 | `F3_GUARDRAILS_TOP3.csv` | 30 min |
| **OOS Validation** | Top 3 F3 | `OOS_VALIDATION_FINAL.csv` | 30 min |
| **TOTAL** | — | **Top configs validadas** | **~2 horas** |

---

## 🚀 COMANDOS DE EXECUÇÃO

### 1. Gerar Sinais V8.7
```bash
python scripts/build_win_signals_v81_variants.py \
    --version v87 \
    --output data/variants/
```

### 2. Executar F1 V8.6
```bash
python scripts/f1_full_scan_v86.py \
    --all-signals \
    --mode HYBRID \
    --output data/results/F1_FULL_RESULTS_V86.csv
```

### 3. Validar F2 (Top 10)
```bash
python engines/f2_tick_last.py \
    --input data/results/F1_FULL_RESULTS_V86.csv \
    --top-10 \
    --output data/results/F2_VALIDATION_TOP10.csv
```

### 4. Guardrails F3 (Top 3)
```bash
python engines/f3_tick_ba.py \
    --input data/results/F2_VALIDATION_TOP10.csv \
    --top-3 \
    --com-guardrails \
    --output data/results/F3_GUARDRAILS_TOP3.csv
```

### 5. OOS Validation
```bash
python engines/f3_tick_ba.py \
    --input data/results/F3_GUARDRAILS_TOP3.csv \
    --oos-period 2026-04 \
    --output data/results/OOS_VALIDATION_FINAL.csv
```

---

## 📝 ARQUIVOS DO PIPELINE

### Estratégias
| Arquivo | Descrição |
|---------|-----------|
| `backtest/strategies/v86.py` | Estratégia V8.6 (F1 engine) |
| `backtest/strategies/v87.py` | ⏳ Estratégia V8.7 (se houver) |

### Sinais
| Arquivo | Descrição |
|---------|-----------|
| `scripts/build_win_signals_v81.py` | Construtor de sinais (atualizar para V8.7) |
| `scripts/build_win_signals_v81_variants.py` | Gerador de parquets |

### F1
| Arquivo | Descrição |
|---------|-----------|
| `scripts/f1_full_scan_v86.py` | F1 V8.6 (7.26M combos, 2.4 min) |
| `scripts/f1_full_scan_v85.py` | F1 V8.5 (legado) |

### F2/F3
| Arquivo | Descrição |
|---------|-----------|
| `engines/f2_tick_last.py` | F2 validation (last ticks) |
| `engines/f3_tick_ba.py` | F3 guardrails (bid/ask) |
| `engines/f1_fast_screener.py` | F1 alternativo (200k combos/s) |

### Dados
| Arquivo | Descrição |
|---------|-----------|
| `data/super_win_continuous.parquet` | Indicadores master (154 cols) |
| `data/WIN_merged_all.parquet` | Ticks IS (last prices) |
| `data/ticks/WIN*.parquet` | Ticks OOS (bid/ask) |
| `data/_fev_cache_v2.npz` | Cache Fev para F1 |
| `data/variants/*.parquet` | Sinais V8.7 (23 arquivos) |

### Resultados
| Arquivo | Descrição |
|---------|-----------|
| `data/results/F1_FULL_RESULTS_V86.csv` | 7.26M combos F1 |
| `data/results/F2_VALIDATION_TOP10.csv` | Top 10 F2 |
| `data/results/F3_GUARDRAILS_TOP3.csv` | Top 3 F3 |
| `data/results/OOS_VALIDATION_FINAL.csv` | Validação OOS |

---

## 🎯 PRÓXIMOS PASSOS

### Imediato
1. ✅ **Documentação criada**: Este arquivo
2. ⏳ **Atualizar `build_win_signals_v81.py`** com V8.7 optimizations
3. ⏳ **Gerar parquets V8.7** (23 arquivos)
4. ⏳ **Executar F1 V8.6** (2.4 min)

### Validação
5. ⏳ **F2 Top 10** (50 min)
6. ⏳ **F3 Top 3** (30 min)
7. ⏳ **OOS April 2026** (30 min)

### Total: ~2 horas para pipeline completo

---

**Última Atualização**: 2026-05-04
**Autor**: WIN Lead Quant Scientist
