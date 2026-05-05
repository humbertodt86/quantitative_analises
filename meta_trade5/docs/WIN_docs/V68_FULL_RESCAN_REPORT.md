# V68 Full Rescan Report

**Date:** 2026-05-03
**Signals Tested:** 123 / 126
**Filters Applied:** SL>=0.5x ATR, R:R<=10, Sharpe-weighted, COST=60 stress test

## Executive Summary

- **Total Cycles:** 123
- **Positive OOS:** 25 (20.3%)
  - V6.8 Compliant (SL>=0.5): 23
  - Non-Compliant (SL<0.5): 2
- **Negative OOS:** 66 (53.7%)
- **Zero OOS:** 32 (26.0%)

- **Validated Signals (all criteria):** 3 / 30

## Validated Signals (Passed All Sanity Filters)

These signals passed ALL V6.8 criteria: positive OOS, WR>35%, slippage stress>0, SL>=0.5.

| Rank | Signal | OOS Net | Stress Net | OOS WR | TP | SL | ATR Range |
|------|--------|---------|------------|--------|----|----|-----------|
| 1 | PA_BB_M2_0_TREND_SELL | +3446 | 2846 | 60.0 | 15.0 | 5.0 | [50,400] |
| 2 | PA_VWAP_Z_Z2_0_TREND_SELL | +1759 | 19 | 39.7 | 15.0 | 6.0 | [50,400] |
| 3 | PA_TUESDAY_TREND_SELL | +1014 | 684 | 36.4 | 6.25 | 2.0 | [50,300] |

## Top V6.8 Compliant Performers (SL>=0.5, Positive OOS)

Signals with positive OOS that respect the SL>=0.5 floor. Sorted by OOS Net.

| Rank | Signal | OOS Net | OOS WR | Trades | Config |
|------|--------|---------|--------|--------|--------|
| 1 | PA_REV_RSI_B15_HYBRID_SELL | +13111 | 52.4 | 147 | TP=3.0 SL=16.0 ATR=[50,400] |
| 2 | PA_VCP_HYBRID_SELL | +12149 | 58.1 | 43 | TP=8.0 SL=5.0 ATR=[50,600] |
| 3 | PA_TSI_T25_HYBRID_SELL | +9532 | 54.0 | 87 | TP=3.0 SL=5.0 ATR=[50,600] |
| 4 | PA_VWAP_REV_D1_0_RANGE_SELL | +7856 | 48.2 | 56 | TP=6.0 SL=0.8 ATR=[50,600] |
| 5 | PA_VWAP_REV_D1_0_HYBRID_SELL | +7856 | 48.2 | 56 | TP=6.0 SL=0.8 ATR=[50,600] |
| 6 | PA_VCP_TREND_SELL | +7647 | 50.0 | 14 | TP=8.0 SL=2.0 ATR=[50,600] |
| 7 | PA_ADX_BREAK_A25_HYBRID_SELL | +6092 | 53.6 | 69 | TP=3.0 SL=5.0 ATR=[300,800] |
| 8 | PA_EXHAUST_Dn1_0_M40_TREND_SELL | +4399 | 42.1 | 19 | TP=5.0 SL=2.0 ATR=[50,600] |
| 9 | PA_REV_RSI_B15_RANGE_SELL | +3854 | 54.0 | 126 | TP=2.0 SL=5.0 ATR=[50,800] |
| 10 | PA_BB_M2_0_TREND_SELL | +3446 | 60.0 | 20 | TP=15.0 SL=5.0 ATR=[50,400] |
| 11 | PA_VWAP_Z_Z2_0_RANGE_SELL | +2052 | 49.6 | 121 | TP=2.0 SL=6.0 ATR=[50,400] |
| 12 | PA_POC_REV_RANGE_SELL | +1943 | 58.8 | 68 | TP=1.5 SL=5.0 ATR=[50,800] |
| 13 | PA_VWAP_Z_Z2_0_TREND_SELL | +1759 | 39.7 | 58 | TP=15.0 SL=6.0 ATR=[50,400] |
| 14 | PA_ADX_BREAK_A25_RANGE_SELL | +1280 | 53.1 | 32 | TP=3.0 SL=5.0 ATR=[300,600] |
| 15 | PA_MA_CROSS_F9_S21_TREND_SELL | +1232 | 40.0 | 20 | TP=6.0 SL=2.0 ATR=[50,600] |

## Non-Compliant Signals (SL<0.5) — EXCLUDED from Validation

These signals showed positive OOS but use micro-stops (SL<0.5) which are unrealistic in live trading.

| Signal | OOS Net | OOS WR | SL | Why Excluded |
|--------|---------|--------|----|-------------|
| PA_KELT_M2_0_RANGE | +5375 | 12.5 | 0.05 | SL below 0.5x ATR floor |
| PA_TUESDAY_RANGE_SELL | +36820 | 50.0 | 0.05 | SL below 0.5x ATR floor |

## Results by Signal Family

| Family | Tested | Pos | Neg | Zero | Best | Worst |
|--------|--------|-----|-----|------|------|-------|
| PA_TUESDAY_RANGE_SELL | 1 | 1 | 0 | 0 | +36820 | +36820 |
| PA_REV_RSI_B15_HYBRID_SELL | 1 | 1 | 0 | 0 | +13111 | +13111 |
| PA_VCP_HYBRID_SELL | 1 | 1 | 0 | 0 | +12149 | +12149 |
| PA_TSI_T25_HYBRID_SELL | 1 | 1 | 0 | 0 | +9532 | +9532 |
| PA_VWAP_REV_D1_0_RANGE_SELL | 1 | 1 | 0 | 0 | +7856 | +7856 |
| PA_VWAP_REV_D1_0_HYBRID_SELL | 1 | 1 | 0 | 0 | +7856 | +7856 |
| PA_VCP_TREND_SELL | 1 | 1 | 0 | 0 | +7647 | +7647 |
| PA_ADX_BREAK_A25_HYBRID_SELL | 1 | 1 | 0 | 0 | +6092 | +6092 |
| PA_KELT_M2_0_RANGE | 1 | 1 | 0 | 0 | +5375 | +5375 |
| PA_EXHAUST_Dn1_0_M40_TREND_SELL | 1 | 1 | 0 | 0 | +4399 | +4399 |
| PA_REV_RSI_B15_RANGE_SELL | 1 | 1 | 0 | 0 | +3854 | +3854 |
| PA_BB_M2_0_TREND_SELL | 1 | 1 | 0 | 0 | +3446 | +3446 |
| PA_VWAP_Z_Z2_0_RANGE_SELL | 1 | 1 | 0 | 0 | +2052 | +2052 |
| PA_POC_REV_RANGE_SELL | 1 | 1 | 0 | 0 | +1943 | +1943 |
| PA_VWAP_Z_Z2_0_TREND_SELL | 1 | 1 | 0 | 0 | +1759 | +1759 |
| PA_ADX_BREAK_A25_RANGE_SELL | 1 | 1 | 0 | 0 | +1280 | +1280 |
| PA_MA_CROSS_F9_S21_TREND_SELL | 1 | 1 | 0 | 0 | +1232 | +1232 |
| PA_TUESDAY_TREND_SELL | 1 | 1 | 0 | 0 | +1014 | +1014 |
| PA_REV_RSI_B15_TREND_SELL | 1 | 1 | 0 | 0 | +898 | +898 |
| PA_POC_REV_TREND | 1 | 1 | 0 | 0 | +718 | +718 |
| PA_TSI_T25_RANGE_SELL | 1 | 1 | 0 | 0 | +590 | +590 |
| PA_VWAP_Z_Z2_0_HYBRID_SELL | 1 | 1 | 0 | 0 | +289 | +289 |
| PA_VCP_RANGE_SELL | 1 | 1 | 0 | 0 | +281 | +281 |
| PA_BB_M2_0_HYBRID_SELL | 1 | 1 | 0 | 0 | +190 | +190 |
| PA_KELT_M2_0_HYBRID_SELL | 1 | 1 | 0 | 0 | +190 | +190 |
| PA_VWAP_Z_Z2_0_TREND | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_VWAP_Z_Z2_0_RANGE | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_VWAP_Z_Z2_0_HYBRID | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_VWAP_REV_D1_0_RANGE | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_VWAP_REV_D1_0_HYBRID | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_BB_M2_0_TREND | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_BB_M2_0_RANGE | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_BB_M2_0_HYBRID | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_POC_REV_HYBRID | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_LIQ_GRAB_TREND | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_LIQ_GRAB_RANGE | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_LIQ_GRAB_HYBRID | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_MFI_B20_TREND | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_MFI_B20_RANGE | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_MFI_B20_HYBRID | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_TSI_T25_TREND | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_TSI_T25_RANGE | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_TSI_T25_HYBRID | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_EFF_RATIO_E0_6_TREND | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_EFF_RATIO_E0_6_RANGE | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_EFF_RATIO_E0_6_HYBRID | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_CHOP_C38_2_RANGE | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_VCP_RANGE | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_VCP_HYBRID | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_GK_BREAK_G0_001_TREND | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_GK_BREAK_G0_001_RANGE | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_GK_BREAK_G0_001_HYBRID | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_TUESDAY_TREND | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_TUESDAY_RANGE | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_TUESDAY_HYBRID | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_ADX_BREAK_A25_TREND | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_ADX_BREAK_A25_RANGE | 1 | 0 | 0 | 1 | +0 | +0 |
| PA_VCP_TREND | 1 | 0 | 1 | 0 | -115 | -115 |
| PA_CHOP_C38_2_TREND | 1 | 0 | 1 | 0 | -164 | -164 |
| PA_EXHAUST_Dn1_0_M40_TREND | 1 | 0 | 1 | 0 | -199 | -199 |
| PA_CHOP_C38_2_TREND_SELL | 1 | 0 | 1 | 0 | -283 | -283 |
| PA_MFI_B20_HYBRID_SELL | 1 | 0 | 1 | 0 | -327 | -327 |
| PA_MFI_B20_TREND_SELL | 1 | 0 | 1 | 0 | -347 | -347 |
| PA_POC_REV_HYBRID_SELL | 1 | 0 | 1 | 0 | -363 | -363 |
| PA_TUESDAY_HYBRID_SELL | 1 | 0 | 1 | 0 | -488 | -488 |
| PA_REV_RSI_B15_TREND | 1 | 0 | 1 | 0 | -753 | -753 |
| PA_MA_CROSS_F9_S21_RANGE_SELL | 1 | 0 | 1 | 0 | -796 | -796 |
| PA_CHOP_C38_2_RANGE_SELL | 1 | 0 | 1 | 0 | -820 | -820 |
| PA_SIGNAL_DIR_TREND_SELL | 1 | 0 | 1 | 0 | -842 | -842 |
| PA_LIQ_GRAB_RANGE_SELL | 1 | 0 | 1 | 0 | -970 | -970 |
| PA_GK_BREAK_G0_001_TREND_SELL | 1 | 0 | 1 | 0 | -1076 | -1076 |
| PA_SLOPE_TREND_S25_A25_RANGE_SELL | 1 | 0 | 1 | 0 | -1082 | -1082 |
| PA_POC_REV_RANGE | 1 | 0 | 1 | 0 | -1175 | -1175 |
| PA_CHOP_C38_2_HYBRID_SELL | 1 | 0 | 1 | 0 | -1269 | -1269 |
| PA_MA_CROSS_F9_S21_RANGE | 1 | 0 | 1 | 0 | -1315 | -1315 |
| PA_CHOP_C38_2_HYBRID | 1 | 0 | 1 | 0 | -1323 | -1323 |
| PA_KELT_M2_0_TREND_SELL | 1 | 0 | 1 | 0 | -1354 | -1354 |
| PA_MA_CROSS_F9_S21_TREND | 1 | 0 | 1 | 0 | -1442 | -1442 |
| PA_TSI_T25_TREND_SELL | 1 | 0 | 1 | 0 | -1534 | -1534 |
| PA_MFI_B20_RANGE_SELL | 1 | 0 | 1 | 0 | -1740 | -1740 |
| PA_KELT_M2_0_HYBRID | 1 | 0 | 1 | 0 | -1810 | -1810 |
| PA_KELT_M2_0_RANGE_SELL | 1 | 0 | 1 | 0 | -1826 | -1826 |
| PA_BB_M2_0_RANGE_SELL | 1 | 0 | 1 | 0 | -1826 | -1826 |
| PA_KELT_M2_0_TREND | 1 | 0 | 1 | 0 | -1830 | -1830 |
| PA_POC_REV_TREND_SELL | 1 | 0 | 1 | 0 | -1847 | -1847 |
| PA_STRONG_TREND_A25_S20_RANGE_SELL | 1 | 0 | 1 | 0 | -1872 | -1872 |
| PA_HMA_CROSS_F5_S10_TREND_SELL | 1 | 0 | 1 | 0 | -1884 | -1884 |
| PA_MA_CROSS_F9_S21_HYBRID | 1 | 0 | 1 | 0 | -2065 | -2065 |
| PA_HMA_CROSS_F5_S10_RANGE_SELL | 1 | 0 | 1 | 0 | -2396 | -2396 |
| PA_GK_BREAK_G0_001_RANGE_SELL | 1 | 0 | 1 | 0 | -2980 | -2980 |
| PA_MA_CROSS_F9_S21_HYBRID_SELL | 1 | 0 | 1 | 0 | -3040 | -3040 |
| PA_EXHAUST_Dn1_0_M40_RANGE | 1 | 0 | 1 | 0 | -3299 | -3299 |
| PA_EXHAUST_Dn1_0_M40_HYBRID_SELL | 1 | 0 | 1 | 0 | -3398 | -3398 |
| PA_EXHAUST_Dn1_0_M40_HYBRID | 1 | 0 | 1 | 0 | -3668 | -3668 |
| PA_ADX_BREAK_A25_TREND_SELL | 1 | 0 | 1 | 0 | -3786 | -3786 |
| PA_GK_BREAK_G0_001_HYBRID_SELL | 1 | 0 | 1 | 0 | -4155 | -4155 |
| PA_LIQ_GRAB_TREND_SELL | 1 | 0 | 1 | 0 | -4225 | -4225 |
| PA_LIQ_GRAB_HYBRID_SELL | 1 | 0 | 1 | 0 | -4379 | -4379 |
| PA_HMA_CROSS_F5_S10_HYBRID_SELL | 1 | 0 | 1 | 0 | -4383 | -4383 |
| PA_EXHAUST_Dn1_0_M40_RANGE_SELL | 1 | 0 | 1 | 0 | -4418 | -4418 |
| PA_SLOPE_TREND_S25_A25_TREND_SELL | 1 | 0 | 1 | 0 | -5115 | -5115 |
| PA_SIGNAL_DIR_RANGE_SELL | 1 | 0 | 1 | 0 | -5134 | -5134 |
| PA_STRONG_TREND_A25_S20_TREND_SELL | 1 | 0 | 1 | 0 | -5580 | -5580 |
| PA_EFF_RATIO_E0_6_TREND_SELL | 1 | 0 | 1 | 0 | -5611 | -5611 |
| PA_SIGNAL_DIR_TREND | 1 | 0 | 1 | 0 | -5780 | -5780 |
| PA_REV_RSI_B15_HYBRID | 1 | 0 | 1 | 0 | -5831 | -5831 |
| PA_HMA_CROSS_F5_S10_TREND | 1 | 0 | 1 | 0 | -5856 | -5856 |
| PA_EFF_RATIO_E0_6_HYBRID_SELL | 1 | 0 | 1 | 0 | -5984 | -5984 |
| PA_REV_RSI_B15_RANGE | 1 | 0 | 1 | 0 | -6078 | -6078 |
| PA_SLOPE_TREND_S25_A25_HYBRID_SELL | 1 | 0 | 1 | 0 | -6966 | -6966 |
| PA_STRONG_TREND_A25_S20_HYBRID_SELL | 1 | 0 | 1 | 0 | -7834 | -7834 |
| PA_SLOPE_TREND_S25_A25_RANGE | 1 | 0 | 1 | 0 | -8034 | -8034 |
| PA_SLOPE_TREND_S25_A25_TREND | 1 | 0 | 1 | 0 | -8506 | -8506 |
| PA_SIGNAL_DIR_HYBRID_SELL | 1 | 0 | 1 | 0 | -8864 | -8864 |
| PA_STRONG_TREND_A25_S20_RANGE | 1 | 0 | 1 | 0 | -8961 | -8961 |
| PA_HMA_CROSS_F5_S10_RANGE | 1 | 0 | 1 | 0 | -8972 | -8972 |
| PA_STRONG_TREND_A25_S20_TREND | 1 | 0 | 1 | 0 | -9147 | -9147 |
| PA_ADX_BREAK_A25_HYBRID | 1 | 0 | 1 | 0 | -9515 | -9515 |
| PA_SIGNAL_DIR_RANGE | 1 | 0 | 1 | 0 | -13695 | -13695 |
| PA_HMA_CROSS_F5_S10_HYBRID | 1 | 0 | 1 | 0 | -14341 | -14341 |
| PA_SLOPE_TREND_S25_A25_HYBRID | 1 | 0 | 1 | 0 | -19856 | -19856 |
| PA_SIGNAL_DIR_HYBRID | 1 | 0 | 1 | 0 | -20656 | -20656 |
| PA_STRONG_TREND_A25_S20_HYBRID | 1 | 0 | 1 | 0 | -21399 | -21399 |

## Key Findings

1. **Aggressive Filtering Was Effective:** Only 3 signals passed ALL V6.8 validation criteria under realistic trading conditions (SL>=0.5x ATR, slippage stress test).
2. **SL Floor Eliminated Micro-Stop Overfitting:** 2 signals (PA_TUESDAY_RANGE_SELL +36820, PA_KELT_M2_0_RANGE +5375) showed massive OOS profits with SL=0.05, but these are artifacts — such tight stops are impossible to execute live due to slippage and order rejection.
3. **TREND Regime Dominates:** All 3 validated signals are TREND regime. RANGE and HYBRID signals generally failed the stress test or had insufficient WR.
4. **SELL Direction Stronger:** 2 of 3 validated signals are SELL-only (PA_BB_M2_0_TREND_SELL, PA_VWAP_Z_Z2_0_TREND_SELL), consistent with historical WIN short-side edge.
5. **PA_TUESDAY is Fragile:** PA_TUESDAY_TREND_SELL validated (+1014) but with lower WR (36.4%). It relies on calendar effects and may not be robust across different months.
6. **PA_BB_M2_0_TREND_SELL is the Standout:** +3446 OOS net, 60.0% WR, survives slippage stress (+2846). Strong candidate for ensemble anchor.
7. **PA_VWAP_Z_Z2_0_TREND_SELL is Marginal:** +1759 OOS but stress drops to +19 (barely survives 2x cost). Risk of degradation in higher-slippage environments.

## Worst Performers (Negative OOS)

| Rank | Signal | OOS Net | OOS WR | Trades |
|------|--------|---------|--------|--------|
| 1 | PA_STRONG_TREND_A25_S20_HYBRID | -21399 | 35.4 | 229 |
| 2 | PA_SIGNAL_DIR_HYBRID | -20656 | 39.1 | 294 |
| 3 | PA_SLOPE_TREND_S25_A25_HYBRID | -19856 | 35.8 | 218 |
| 4 | PA_HMA_CROSS_F5_S10_HYBRID | -14341 | 53.9 | 399 |
| 5 | PA_SIGNAL_DIR_RANGE | -13695 | 43.5 | 255 |
| 6 | PA_ADX_BREAK_A25_HYBRID | -9515 | 53.6 | 181 |
| 7 | PA_STRONG_TREND_A25_S20_TREND | -9147 | 30.5 | 82 |
| 8 | PA_HMA_CROSS_F5_S10_RANGE | -8972 | 55.0 | 318 |
| 9 | PA_STRONG_TREND_A25_S20_RANGE | -8961 | 43.5 | 170 |
| 10 | PA_SIGNAL_DIR_HYBRID_SELL | -8864 | 39.3 | 331 |

## Signals Not Tested

3 signals could not be tested due to memory allocation error (1.8GB numpy array):
- PA_VWAP_REV_D1_0_TREND
- PA_VWAP_REV_D1_0_TREND_SELL
- PA_EFF_RATIO_E0_6_RANGE_SELL

**Recommendation:** Run these individually with optimized memory (float32/mmap) or on a machine with more RAM.

## Recommendation

With only 3 validated signals, ensemble options are limited. Suggested paths:

1. **Conservative Ensemble:** Use only PA_BB_M2_0_TREND_SELL + PA_VWAP_Z_Z2_0_TREND_SELL (both SELL, TREND regime). This is a focused short-bias ensemble.
2. **Add PA_TUESDAY as Satellite:** Include PA_TUESDAY_TREND_SELL with lower weight due to its calendar-dependence and marginal WR.
3. **Expand Search:** Relax SL floor slightly (e.g., SL>=0.3) or test additional signal families to increase the candidate pool.
4. **Run Missing Signals:** Test the 3 memory-error signals to see if they add diversity.
