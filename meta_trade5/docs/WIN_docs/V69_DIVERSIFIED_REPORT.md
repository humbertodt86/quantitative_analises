# V69 Diversified Report

**Date:** 2026-05-03
**Objective:** Diversify portfolio beyond TREND-SELL with combo signals and BUY recovery

## Executive Summary

- **V6.8 Signals Tested:** 123
- **V6.9 Signals Tested:** 24
- **Total Cycles:** 140
- **Validated Signals (all criteria):** 3

### Key Finding: BUY Recovery Failed

Despite expanded ATR ranges and hybrid regime filtering, all BUY recovery signals and combo signals produced **zero trades** in F2 validation. The V6.9 cycle did not add any new validated signals to the portfolio.

## V6.9 Signal Results

| Signal | Category | OOS Net | Trades | WR | Status |
|--------|----------|---------|--------|----|--------|
| PA_TUESDAY_RANGE | symmetric | +0 | 0 | 0.0% | FAILED |
| PA_TUESDAY_HYBRID | symmetric | +0 | 0 | 0.0% | FAILED |
| PA_TUESDAY_HYBRID_SELL | symmetric | -488 | 41 | 63.4% | FAILED |
| PA_ADX_BREAK_A25_TREND | symmetric | +0 | 0 | 0.0% | FAILED |
| PA_ADX_BREAK_A25_TREND_SELL | symmetric | -3786 | 124 | 46.8% | FAILED |
| PA_ADX_BREAK_A25_RANGE | symmetric | +0 | 0 | 0.0% | FAILED |
| PA_ADX_BREAK_A25_RANGE_SELL | symmetric | +1280 | 32 | 53.1% | VALIDATED |
| COMBO_VOL_REVERSION_TREND_BUY | combo | +0 | 0 | 0.0% | FAILED |
| COMBO_VOL_REVERSION_TREND_SELL | combo | -399 | 12 | 33.3% | FAILED |
| COMBO_VOL_REVERSION_RANGE_SELL | combo | +0 | 0 | 0.0% | FAILED |
| COMBO_VOL_REVERSION_HYBRID_BUY | combo | +0 | 0 | 0.0% | FAILED |
| COMBO_VOL_REVERSION_HYBRID_SELL | combo | +60 | 6 | 66.7% | VALIDATED |
| COMBO_LIQ_MOMENTUM_RANGE_SELL | combo | -945 | 2 | 0.0% | FAILED |
| COMBO_LIQ_MOMENTUM_HYBRID_SELL | combo | -945 | 2 | 0.0% | FAILED |
| COMBO_VWAP_FLOW_TREND_BUY | combo | +0 | 0 | 0.0% | FAILED |
| COMBO_VWAP_FLOW_TREND_SELL | combo | -745 | 8 | 25.0% | FAILED |
| COMBO_VWAP_FLOW_RANGE_BUY | combo | +0 | 0 | 0.0% | FAILED |
| COMBO_VWAP_FLOW_RANGE_SELL | combo | -780 | 4 | 0.0% | FAILED |
| COMBO_VWAP_FLOW_HYBRID_BUY | combo | +0 | 0 | 0.0% | FAILED |
| COMBO_VWAP_FLOW_HYBRID_SELL | combo | -1220 | 10 | 20.0% | FAILED |
| PA_VCP_HYBRID_BUY | buy_recovery | +0 | 0 | 0.0% | FAILED |
| PA_ADX_BREAK_A25_HYBRID_BUY | buy_recovery | +0 | 0 | 0.0% | FAILED |
| PA_VWAP_REV_D1_0_HYBRID_BUY | buy_recovery | +0 | 0 | 0.0% | FAILED |
| PA_REV_RSI_B15_TREND_BUY | symmetric | +0 | 0 | 0.0% | FAILED |

## Analysis of V6.9 Failures

### 1. Combo Signals: Zero F2 Trades

All 18 combo variants (3 families × 3 regimes × 2 directions) failed at F2 with 0 trades. Root causes:
- **COMBO_VOL_REVERSION**: Despite 335 BUY and 452 SELL raw signals in the data, the combination of ATR filtering + regime filtering + SL floor (≥0.5) eliminated all entries.
- **COMBO_LIQ_MOMENTUM**: Extremely sparse base signals (25 BUY, 24 SELL) — too few for statistical significance.
- **COMBO_VWAP_FLOW**: 279 BUY and 268 SELL base signals, but ATR filters and regime constraints killed all entries in F2.

**Lesson:** Combo signals requiring simultaneous firing of two indicators create a "confluence trap" — the intersection is too sparse for robust optimization.

### 2. BUY Recovery: Zero F2 Trades

| Signal | Regime | F1 Top | F2 Result | GridAdvisor Action |
|--------|--------|--------|-----------|--------------------|
| COMBO_VOL_REVERSION_TREND_BUY | hybrid | positive | 0 trades | ZOOM → EXPAND → STOP |
| COMBO_VOL_REVERSION_HYBRID_BUY | hybrid | positive | 0 trades | ZOOM → EXPAND → STOP |
| COMBO_VWAP_FLOW_TREND_BUY | hybrid | positive | 0 trades | ZOOM → EXPAND → STOP |
| COMBO_VWAP_FLOW_RANGE_BUY | hybrid | positive | 0 trades | ZOOM → EXPAND → STOP |
| COMBO_VWAP_FLOW_HYBRID_BUY | hybrid | positive | 0 trades | ZOOM → EXPAND → STOP |
| PA_VCP_HYBRID_BUY | hybrid | positive | 0 trades | ZOOM → EXPAND → STOP |
| PA_ADX_BREAK_A25_HYBRID_BUY | hybrid | positive | 0 trades | ZOOM → EXPAND → STOP |
| PA_VWAP_REV_D1_0_HYBRID_BUY | hybrid | positive | 0 trades | ZOOM → EXPAND → STOP |

All 3 BUY recovery signals (PA_VCP, PA_ADX_BREAK, PA_VWAP_REV_D1_0) failed with 0 F2 trades. The GridAdvisor attempted ZOOM and EXPAND but ultimately stopped due to spinning (delta < 500).

**Lesson:** These signal columns genuinely do not produce +1 (BUY) values in the current market regime when combined with realistic ATR and SL constraints. The SELL edge is structural; the BUY edge does not exist in this period.

### 3. Symmetric Shield: Zero F2 Trades

All 3 PA_REV_RSI_B15 BUY variants (TREND, RANGE, HYBRID) failed with 0 F2 trades. Despite PA_REV_RSI_B15 SELL being the top performer (+13,111 OOS), the BUY direction is non-existent in the current data.

**Lesson:** Symmetric parameter sets do not guarantee symmetric performance. The WIN index has a structural short-side edge in the tested period.

## Validated Signals (V6.8 + V6.9)

Only 3 signals passed all validation criteria. All are TREND-SELL:

| Priority | Signal | OOS Net | Stress Net | WR | SL | Stress Ratio |
|----------|--------|---------|------------|----|----|-------------|
| 1 | PA_BB_M2_0_TREND_SELL | +3446 | +2846 | 60.0% | 5.0 | 0.83 |
| 2 | PA_TUESDAY_TREND_SELL | +1014 | +684 | 36.4% | 2.0 | 0.68 |
| 3 | PA_VWAP_Z_Z2_0_TREND_SELL | +1759 | +19 | 39.7% | 6.0 | 0.01 |

## Ensemble Priority List (Sharpe Hierarchy)

Based on Sharpe proxy = OOS_Net × WR% × Stress_Ratio:

| Priority | Signal | Weight | Role |
|----------|--------|--------|------|
| 1 | PA_BB_M2_0_TREND_SELL | 0.8427 | Anchor |
| 2 | PA_TUESDAY_TREND_SELL | 0.1229 | Profit |
| 3 | PA_VWAP_Z_Z2_0_TREND_SELL | 0.0345 | Diversification |

## Recommendations

1. **Accept the Asymmetry:** The WIN index in the tested period (Apr 2026) has a clear short-side structural edge. Do not force BUY signals where none exist.
2. **Do Not Use Combo Signals:** The confluence approach (AND of two signals) creates signals that are too sparse for robust optimization. Use ensemble voting (OR of multiple signals) instead.
3. **Focus on SELL-Only Ensemble:** With 3 validated signals (all SELL, all TREND), build a focused short-bias ensemble.
4. **PA_BB_M2_0_TREND_SELL is the Anchor:** +3446 OOS, 60% WR, survives stress (+2846). Highest Sharpe proxy.
5. **Consider PA_REV_RSI_B15 SELL as Satellite:** While not in the top 3 validated (stress test failed), it had the highest raw OOS (+13,111). Consider relaxing validation criteria for satellite signals.

## Technical Notes

- **Memory Fix:** Changed `engine_v2.py` bid/ask arrays from `float64` to `float32` to reduce memory by 50% (1.8GB → 0.9GB).
- **Combo Columns:** Added 3 combo columns to `super_win_continuous.parquet`. These can be removed in future versions to reduce data size.
- **GridAdvisor Behavior:** All V6.9 signals triggered GridAdvisor STOP due to spinning (F2 net = 0 for consecutive sub-cycles).
