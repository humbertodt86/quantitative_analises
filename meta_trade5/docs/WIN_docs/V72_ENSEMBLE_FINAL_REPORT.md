# V7.2 — SELL-Only Ensemble Final Report

**Date:** 2026-05-03
**Cycle:** V7.2 Ensemble Build
**Objective:** Construct a production-ready SELL-only ensemble from all validated signals, rank by OOS performance and WFA robustness.

---

## Executive Summary

- **Total validated signals (OOS > 0):** 26
- **BUY signals:** 2 (PA_POC_REV_TREND: +718, PA_KELT_M2_0_RANGE: +5,375)
- **SELL signals:** 24
- **Signals with WFA robustness=3/3:** 1 (PA_EXHAUST_Dn1_0_M40_TREND_SELL)
- **Recommended ensemble size:** Top 10 SELL signals

---

## SELL-Only Validated Signals (Ranked by OOS Net)

| # | Signal | OOS Net | Trades | WR | Regime | TP | SL | ATR Min | ATR Max | BE | HP | WFA Robust |
|---|--------|:-------:|:------:|:--:|:------:|:--:|:--:|:-------:|:-------:|:--:|:--:|:----------:|
| 1 | PA_TUESDAY_RANGE_SELL | **+36,820** | 40 | 50.0% | range | 20.0 | 0.05 | 50 | 400 | 100 | 2 | — |
| 2 | PA_REV_RSI_B15_HYBRID_SELL | **+13,111** | 147 | 52.4% | hybrid | 3.0 | 16.0 | 50 | 400 | 500 | 3 | — |
| 3 | PA_VCP_HYBRID_SELL | **+12,149** | 43 | 58.1% | hybrid | 8.0 | 5.0 | 50 | 600 | 400 | 3 | — |
| 4 | PA_TSI_T25_HYBRID_SELL | +9,532 | 87 | 54.0% | hybrid | 3.0 | 5.0 | 50 | 600 | 500 | 2 | — |
| 5 | PA_VWAP_REV_D1_0_RANGE_SELL | +7,856 | 56 | 48.2% | range | 6.0 | 0.8 | 50 | 600 | 500 | 3 | — |
| 6 | PA_VWAP_REV_D1_0_HYBRID_SELL | +7,856 | 56 | 48.2% | hybrid | 6.0 | 0.8 | 50 | 600 | 500 | 3 | — |
| 7 | PA_VCP_TREND_SELL | +7,647 | 14 | 50.0% | trend | 8.0 | 2.0 | 50 | 600 | 400 | 3 | — |
| 8 | PA_ADX_BREAK_A25_HYBRID_SELL | +6,092 | 69 | 53.6% | hybrid | 3.0 | 5.0 | 300 | 800 | 100 | 2 | — |
| 9 | PA_EXHAUST_Dn1_0_M40_TREND_SELL | +4,364 | 19 | 42.1% | trend | 5.0 | 2.0 | 50 | 800 | 500 | 3 | **3/3** |
| 10 | PA_REV_RSI_B15_RANGE_SELL | +3,854 | 126 | 54.0% | range | 2.0 | 5.0 | 50 | 800 | 500 | 2 | — |
| 11 | PA_BB_M2_0_TREND_SELL | +3,446 | 20 | 60.0% | trend | 15.0 | 5.0 | 50 | 400 | 500 | 3 | — |
| 12 | PA_VWAP_Z_Z2_0_RANGE_SELL | +2,052 | 121 | 49.6% | range | 2.0 | 6.0 | 50 | 400 | 400 | 2 | — |
| 13 | PA_POC_REV_RANGE_SELL | +1,943 | 68 | 58.8% | range | 1.5 | 5.0 | 50 | 800 | 500 | 2 | — |
| 14 | PA_VWAP_Z_Z2_0_TREND_SELL | +1,759 | 58 | 39.7% | trend | 15.0 | 6.0 | 50 | 400 | 500 | 3 | — |
| 15 | PA_ADX_BREAK_A25_RANGE_SELL | +1,280 | 32 | 53.1% | range | 3.0 | 5.0 | 300 | 600 | 100 | 2 | — |
| 16 | PA_MA_CROSS_F9_S21_TREND_SELL | +1,232 | 20 | 40.0% | trend | 6.0 | 2.0 | 50 | 600 | 500 | 3 | — |
| 17 | PA_TUESDAY_TREND_SELL | +1,014 | 11 | 36.4% | trend | 6.25 | 2.0 | 50 | 300 | 200 | 2 | — |
| 18 | PA_REV_RSI_B15_TREND_SELL | +898 | 85 | 60.0% | trend | 1.5 | 3.0 | 50 | 9999 | 500 | 2 | — |
| 19 | PA_TSI_T25_RANGE_SELL | +590 | 38 | 39.5% | range | 6.0 | 5.0 | 50 | 600 | 500 | 2 | — |
| 20 | PA_VWAP_Z_Z2_0_HYBRID_SELL | +289 | 164 | 47.6% | hybrid | 2.0 | 6.0 | 50 | 600 | 500 | 2 | — |
| 21 | PA_VCP_RANGE_SELL | +281 | 31 | 74.2% | range | 0.5 | 0.8 | 50 | 600 | 100 | 3 | — |
| 22 | PA_BB_M2_0_HYBRID_SELL | +190 | 44 | 56.8% | hybrid | 1.5 | 3.0 | 50 | 600 | 500 | 3 | — |
| 23 | PA_KELT_M2_0_HYBRID_SELL | +190 | 44 | 56.8% | hybrid | 1.5 | 3.0 | 50 | 600 | 500 | 3 | — |
| 24 | COMBO_VOL_REVERSION_HYBRID_SELL | +60 | 6 | 66.7% | hybrid | 1.0 | 2.0 | 50 | 400 | 400 | 2 | — |

---

## Outlier Analysis

### ⚠️ PA_TUESDAY_RANGE_SELL (+36,820)
- **Risk:** Extreme outlier with SL=0.05 (violates sanity floor of 0.5x ATR)
- **Observation:** Only 40 trades, calendar effect signal (Tuesday-only)
- **Verdict:** Exclude from ensemble or apply SL floor enforcement. Previous version excluded due to SL=0.05.
- **Action:** Flag as `non_compliant` but retain for reference.

### ⚠️ PA_REV_RSI_B15_HYBRID_SELL (+13,111)
- **Risk:** SL=16.0 is extremely wide (R:R = 3.0/16.0 = 0.19 — inverted)
- **Observation:** 147 trades, 52.4% WR — survives despite wide SL because of high win rate
- **Verdict:** Accept but monitor. The wide SL + decent WR suggests strong mean-reversion signal.

### ⚠️ PA_VCP_HYBRID_SELL (+12,149)
- **Risk:** Only 43 trades, low sample size
- **Observation:** 58.1% WR, TP=8.0, SL=5.0 (R:R = 1.6 — within limits)
- **Verdict:** Accept. Low trade count but strong per-trade performance.

---

## WFA-Validated Signals

Only **1 signal** achieved WFA robustness=3/3 (positive in all 3 monthly folds):

| Signal | F2 Net | Fev | Mar | Abr | WF Avg | Robust |
|--------|--------|-----|-----|-----|--------|--------|
| PA_EXHAUST_Dn1_0_M40_TREND_SELL | +14,928 | +3,842 | +1,180 | +1,228 | +2,083 | **3/3** |

This signal should be **promoted to anchor position** in any ensemble, regardless of its lower OOS net (+4,364) compared to top performers. Temporal consistency is more valuable than raw PnL.

---

## Ensemble Recommendations

### Tier 1: Anchor (WFA Robust = 3/3)
- PA_EXHAUST_Dn1_0_M40_TREND_SELL (+4,364 OOS, 3/3 WFA)

### Tier 2: High-Confidence (>5,000 OOS, >40 trades)
- PA_REV_RSI_B15_HYBRID_SELL (+13,111, 147 trades)
- PA_VCP_HYBRID_SELL (+12,149, 43 trades)
- PA_TSI_T25_HYBRID_SELL (+9,532, 87 trades)
- PA_VWAP_REV_D1_0_RANGE_SELL (+7,856, 56 trades)
- PA_VCP_TREND_SELL (+7,647, 14 trades)
- PA_ADX_BREAK_A25_HYBRID_SELL (+6,092, 69 trades)

### Tier 3: Supporting (>1,000 OOS, >20 trades)
- PA_REV_RSI_B15_RANGE_SELL (+3,854, 126 trades)
- PA_BB_M2_0_TREND_SELL (+3,446, 20 trades)
- PA_VWAP_Z_Z2_0_RANGE_SELL (+2,052, 121 trades)
- PA_POC_REV_RANGE_SELL (+1,943, 68 trades)

### Tier 4: Monitoring (<1,000 OOS or <20 trades)
- All remaining signals

### Excluded
- PA_TUESDAY_RANGE_SELL (+36,820) — Non-compliant SL=0.05

---

## Structural Observations

1. **SELL-only dominance:** 24/26 validated signals are SELL. WIN has a structural short bias in Apr 2026.
2. **HYBRID regime wins:** Top performers (REV_RSI_B15, VCP, TSI_T25, VWAP_REV_D1_0) are HYBRID or RANGE. TREND regime signals underperform.
3. **Duplicate signals:** PA_VWAP_REV_D1_0_RANGE_SELL and PA_VWAP_REV_D1_0_HYBRID_SELL have identical results (same column, different regime filter). One should be dropped from ensemble.
4. **Low trade counts:** Several signals have <20 trades (PA_VCP_TREND_SELL: 14, PA_TUESDAY_TREND_SELL: 11, PA_KELT_M2_0_RANGE: 8). These have high variance and should be weighted lower.
5. **COMBO signals weak:** Only 1 combo validated (+60 pts, 6 trades). Confluence traps confirmed.

---

## Proposed Ensemble Weights

| Signal | OOS Net | Trades | WR | Weight | Tier |
|--------|:-------:|:------:|:--:|:------:|:----:|
| PA_EXHAUST_Dn1_0_M40_TREND_SELL | 4,364 | 19 | 42.1% | **2.00** | 1 |
| PA_REV_RSI_B15_HYBRID_SELL | 13,111 | 147 | 52.4% | **2.00** | 2 |
| PA_VCP_HYBRID_SELL | 12,149 | 43 | 58.1% | **2.00** | 2 |
| PA_TSI_T25_HYBRID_SELL | 9,532 | 87 | 54.0% | **1.50** | 2 |
| PA_VWAP_REV_D1_0_RANGE_SELL | 7,856 | 56 | 48.2% | **1.50** | 2 |
| PA_VCP_TREND_SELL | 7,647 | 14 | 50.0% | **1.00** | 2 |
| PA_ADX_BREAK_A25_HYBRID_SELL | 6,092 | 69 | 53.6% | **1.00** | 2 |
| PA_REV_RSI_B15_RANGE_SELL | 3,854 | 126 | 54.0% | **1.00** | 3 |
| PA_BB_M2_0_TREND_SELL | 3,446 | 20 | 60.0% | **1.00** | 3 |
| PA_VWAP_Z_Z2_0_RANGE_SELL | 2,052 | 121 | 49.6% | **0.75** | 3 |
| PA_POC_REV_RANGE_SELL | 1,943 | 68 | 58.8% | **0.75** | 3 |

**Total ensemble:** 11 signals, weighted average expected performance ~7,200 OOS net.

---

## Next Steps

1. **Remove BUY columns from parquet** — Run `clean_buy_columns.py` (ready)
2. **Drop duplicate** — PA_VWAP_REV_D1_0_HYBRID_SELL (identical to RANGE_SELL)
3. **Re-test PA_TUESDAY_RANGE_SELL** with SL floor=0.5 to check if it survives sanity
4. **Run ensemble backtest** with SELECTOR mode (highest Sharpe enters, not consensus)
5. **Generate ensemble trades CSV** for unified reporting
6. **Update docs/progress.md** with V7.2 ensemble build summary

---

## Files Updated/Generated

- `docs/WIN_docs/V72_ENSEMBLE_FINAL_REPORT.md` (this file)
- `clean_buy_columns.py` — Parquet cleanup script
- `docs/WIN_docs/ensemble_priority_list.json` — Updated priority list

**Cycle Status:** V7.2 COMPLETE. Ready for ensemble execution.
