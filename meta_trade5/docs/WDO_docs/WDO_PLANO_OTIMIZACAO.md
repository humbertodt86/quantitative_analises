# WDO Optimization Plan — Cycles 11-20

## Baseline (Current Best)
- **Strategy**: PA_REV_RSI + VWAP_Z < -1.0, TP=8.0, SL=1.0, HSC=2, HSTH=10
- **IS**: +7.423 pts, WR 82.1%, PF 39.20
- **OOS (22d)**: +49 pts, +2.2 pts/dia, WR 59%, PF 1.23
- **Problema**: HSTAG = 100% das saídas (TP nunca é atingido)

---

## Phase 1: Consolidate the Parquet
**Add missing columns:**
- `prev_vah`, `prev_val` (Value Area High/Low — foram perdidos)
- `vwap_monthly_z` (Z-Score da VWAP mensal)
- `PA_WIDE_IB` (IB False Break com thresholds mais largos)
- `PA_GAP` (gap-aware signal)

**File**: `super_wdo_M5.parquet` → rebuild with all 70+ columns.

---

## Phase 2: Grid Search — PTAX MAGNET
**Signal**: `PA_PTAX_MAGNET`
**Grid parameters (seed from user)**:

| Parameter | Range | Steps |
|-----------|-------|-------|
| `dist_to_ptax` min | 5 to 25 | [5, 8, 10, 12, 15, 20] |
| TP multiplier | 1.0 to 8.0 | [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0] |
| SL multiplier | 0.4 to 1.5 | [0.4, 0.6, 0.8, 1.0, 1.2, 1.5] |
| HSTAG candles | 1 to 8 | [1, 2, 3, 4, 6, 8] |
| HSTAG threshold | 3 to 20 | [3, 5, 8, 10, 15, 20] |
| Hours | 10-13h only | fixed (PTAX window) |
| Hard stop | 10 to 25 | [10, 15, 20, 25] |

**Expected combos**: 6×7×6×6×6×4 = 36,288
**Expected time**: ~10 min with 10 workers

---

## Phase 3: Grid Search — IB FALSE BREAK (Wide)
**Signal**: `PA_IB_FALSEBREAK` (need wider thresholds)
**Current**: only 38 signals in 101k candles (0.03%) — too rare
**Fix**: Relax thresholds:
- `prev_low < ib_low` → `prev_low < ib_low * 1.005` (5% tolerance)
- Remove GK_RATIO requirement (or lower to 1.05x)
- RSI2 < 40 instead of < 30

**Grid**:
| Parameter | Range |
|-----------|-------|
| RSI2 max | [30, 40, 50] |
| GK_RATIO min factor | [1.0, 1.05, 1.1] |
| IB tolerance | [0, 0.3, 0.5] |
| TP | [3.0, 4.0, 6.0, 8.0] |
| SL | [0.6, 0.8, 1.0, 1.2] |
| HSTAG | [2, 4, 6] × [5, 10, 15] |

**Expected combos**: ~2,000

---

## Phase 4: Grid Search — DXY CORRELATION
**Signal**: `PA_DXY_BUY` / `PA_DXY_REV`
**Already tested**: TP=8.0, SL=1.0 → OOS -9 pts (full day)
**Refine grid**:

| Parameter | Range |
|-----------|-------|
| `dxy_trend` min | [0, 0.5, 1.0, 2.0, 5.0] |
| TP | [3.0, 4.0, 6.0, 8.0] |
| SL | [0.6, 0.8, 1.0, 1.2] |
| Hours | [9-12, 9-14, 10-14] |
| HSTAG | [2, 4, 6] × [5, 10, 15] |

**Expected combos**: ~3,000

---

## Phase 5: ATR Dinâmico
**Not a separate signal** — modifies TP/SL based on ATR regime:

```
TP = tp_mult × ATR
If ATR < 5: TP = min(TP, 25)    # limit target in low vol
If ATR > 8: TP = max(TP, 30)    # ensure target in high vol
```

**Grid**: Test `tp_mult` range 1.0-8.0 (same as before), but add ATR filter:

| Parameter | Range |
|-----------|-------|
| `ATR` min for entry | [2, 3, 4, 5] |
| `ATR` max for entry | [10, 15, 20] |
| TP_mult | [1.0, 2.0, 3.0, 4.0, 6.0, 8.0] |
| SL_mult | [0.6, 0.8, 1.0, 1.2] |

**Hypothesis**: Higher ATR_min filters out low-vol days where HSTAG kills winners

---

## Phase 6: HSTAG Diferenciado (Gap vs No-Gap)
**The key insight**: WR with GAP = 85.7% vs without = 79%.
**Action**: Different HSTAG parameters depending on `is_gap`:

```
If is_gap == 1: hp_candles = 6, hp_th = 15  (patiente)
If is_gap == 0: hp_candles = 2, hp_th = 8   (rápido)
```

**Grid**: Test combinations:

| Parameter | Range |
|-----------|-------|
| Base HSTAG candles | [1, 2, 3, 4] |
| Base HSTAG threshold | [3, 5, 8, 10] |
| Gap HSTAG candles | [4, 6, 8, 12] |
| Gap HSTAG threshold | [8, 10, 15, 20] |

**Implementation note**: Engine V2 applies uniform HSTAG per mode. Need to test gap-filtered vs non-gap in separate runs.

---

## Phase 7: Combined Optimized Strategy
Take the best from each family and combine as multiple modes in Engine V2:

| Mode | Signal | Condition | Priority |
|------|--------|-----------|----------|
| **REVERSAL** | PA_REV_RSI + VWAP_Z < -1.5 | Always (9-12h) | 3 (highest) |
| **PTAX** | PA_PTAX_MAGNET | 10-13h, dist>10 | 2 |
| **DXY** | PA_DXY_BUY | dxy_trend > 0 | 1 |

**OOS test**: 22 days, bid/ask ticks

---

## Phase 8: Monte Carlo Validation
For the final best config:
```python
for i in range(1000):
    sim = np.random.choice(trade_pnls, size=N, replace=True)
    results.append(sim.sum())
ci_95 = np.percentile(results, [2.5, 97.5])
```
**Criteria**: 95% CI entirely positive.

---

## Phase 9: Deploy Bot
Generate `bot_mt5_wdo_v01.py` with:
- Multi-mode strategy (REVERSAL + PTAX + DXY)
- HSTAG-differentiated (gap vs no-gap)
- Status file + telemetry
- Register in Command Center

---

## Execution Order
```
Phase 1: Fix parquet (1 script, 2 min)
Phase 2: PTAX grid (10 min)
Phase 3: IB grid (5 min)
Phase 4: DXY grid (3 min)
Phase 5: ATR grid (10 min)
Phase 6: HSTAG grid (5 min)
Phase 7: Combined (2 min)
Phase 8: Monte Carlo (1 min)
Phase 9: Deploy (30 min)
```

**Total estimated time**: ~1 hour
**Total combos**: ~50,000
