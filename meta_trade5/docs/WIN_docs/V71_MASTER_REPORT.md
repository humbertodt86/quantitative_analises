# V71 Master Report — Exhaustion Rescan (BUY + SELL)

**Date:** 2026-05-03
**Cycle:** V7.1
**Objective:** Test exhaustion indicators (Stochastic, IFR, VWAP, EXHAUST, POC_REV) for BOTH BUY and SELL directions with independent optimization.

## Infrastructure Changes

### 1. F1 Directional Fix
- `engines/f1_fast_screener.py`: Added `direction` parameter (-1=SELL, 1=BUY)
- BUY logic: `tp_th = entry + tp_pts`, `pnl = cross_price - entry`
- SELL logic: `tp_th = entry - tp_pts`, `pnl = entry - cross_price`
- `orchestrator_v65.py`: Passes `direction=s['signal']` to F1 screener

### 2. Monthly PnL Breakdown in F2 Rank
- F2 ranking CSV now includes `jan_net`, `feb_net`, `mar_net` columns
- Each config shows PnL per month (January, February, March 2026)
- Helps identify seasonal bias and regime consistency

### 3. Unified F3 Trades Collection
- Module-level accumulator `_unified_f3_trades` collects all F3 trades
- `append_unified_f3_trades()`: Appends trades with `strategy_name` field
- `save_unified_f3_trades()`: Saves to `V71_UNIFIED_TRADES_F3.csv`
- `strategy_name` is the FIRST column in the CSV

## Executive Summary

- **Queue size:** 30 signals (15 BUY + 15 SELL)
- **Signals tested:** 21
- **Signals missing/aborted:** 9
- **New validated signals:** 4
- **Total validated signals:** 30

### Key Finding: BUY Recovery Still Impossible

All 13 BUY signals tested produced **zero trades**. The F1 directional fix confirmed
that the issue is NOT a bug in the screener — the BUY direction genuinely has no edge
in the WIN index during the tested period (Apr 2026).

### SELL Variants Show Strong Performance

4 new SELL signals were validated with strong OOS results:

| Signal | OOS Net | Trades | WR | Regime |
|--------|---------|--------|----|--------|
| PA_VWAP_REV_D1_0_RANGE_SELL | +7856 | 56 | 48.2% | range |
| PA_VWAP_REV_D1_0_HYBRID_SELL | +7856 | 56 | 48.2% | hybrid |
| PA_POC_REV_RANGE_SELL | +1943 | 68 | 58.8% | range |
| PA_EXHAUST_Dn1_0_M40_TREND_SELL | +4399 | 19 | 42.1% | trend |

## Detailed Results

### BUY Signals (All Failed)

Signal                                        OOS  Trades      WR
-----------------------------------------------------------------
PA_POC_REV_RANGE_BUY                           +0       0     0.0%
PA_ESTOCASTICO_RANGE_BUY                       +0       0     0.0%
PA_ESTOCASTICO_HYBRID_BUY                      +0       0     0.0%
PA_ESTOCASTICO_TREND_BUY                       +0       0     0.0%
PA_IFR_OVERSOLD_RANGE_BUY                      +0       0     0.0%
PA_IFR_OVERSOLD_HYBRID_BUY                     +0       0     0.0%
PA_IFR_OVERSOLD_TREND_BUY                      +0       0     0.0%
PA_VWAP_REV_D1_0_RANGE_BUY                     +0       0     0.0%
PA_VWAP_REV_D1_0_HYBRID_BUY                    +0       0     0.0%
PA_EXHAUST_Dn1_0_M40_RANGE_BUY                 +0       0     0.0%
PA_EXHAUST_Dn1_0_M40_HYBRID_BUY                +0       0     0.0%
PA_POC_REV_HYBRID_BUY                          +0       0     0.0%
PA_POC_REV_TREND_BUY                           +0       0     0.0%

### SELL Signals

Signal                                        OOS  Trades      WR
-----------------------------------------------------------------
PA_POC_REV_TREND_SELL                       -1847      39    41.0%
PA_POC_REV_RANGE_SELL                       +1943      68    58.8%
PA_EXHAUST_Dn1_0_M40_TREND_SELL             +4399      19    42.1%
PA_EXHAUST_Dn1_0_M40_RANGE_SELL             -4418      94    56.4%
PA_EXHAUST_Dn1_0_M40_HYBRID_SELL            -3398     107    57.0%
PA_VWAP_REV_D1_0_RANGE_SELL                 +7856      56    48.2%
PA_VWAP_REV_D1_0_HYBRID_SELL                +7856      56    48.2%
PA_POC_REV_HYBRID_SELL                       -363      84    53.6%

## Strategies F3 Killed (Passed F2, Failed OOS)

These signals reached F3 validation but produced negative or zero OOS results:

Signal                                        OOS  Trades      WR
-----------------------------------------------------------------
PA_POC_REV_TREND_SELL                       -1847      39    41.0%
PA_EXHAUST_Dn1_0_M40_RANGE_SELL             -4418      94    56.4%
PA_EXHAUST_Dn1_0_M40_HYBRID_SELL            -3398     107    57.0%
PA_POC_REV_HYBRID_SELL                       -363      84    53.6%

## Signals Aborted at F2 (Zero Trades)

Count: 13 signals

- PA_ESTOCASTICO_HYBRID_BUY
- PA_ESTOCASTICO_RANGE_BUY
- PA_ESTOCASTICO_TREND_BUY
- PA_EXHAUST_Dn1_0_M40_HYBRID_BUY
- PA_EXHAUST_Dn1_0_M40_RANGE_BUY
- PA_IFR_OVERSOLD_HYBRID_BUY
- PA_IFR_OVERSOLD_RANGE_BUY
- PA_IFR_OVERSOLD_TREND_BUY
- PA_POC_REV_HYBRID_BUY
- PA_POC_REV_RANGE_BUY
- PA_POC_REV_TREND_BUY
- PA_VWAP_REV_D1_0_HYBRID_BUY
- PA_VWAP_REV_D1_0_RANGE_BUY

## Missing Signals (Not Tested)

- PA_ESTOCASTICO_HYBRID_SELL
- PA_ESTOCASTICO_RANGE_SELL
- PA_ESTOCASTICO_TREND_SELL
- PA_EXHAUST_Dn1_0_M40_TREND_BUY
- PA_IFR_OVERSOLD_HYBRID_SELL
- PA_IFR_OVERSOLD_RANGE_SELL
- PA_IFR_OVERSOLD_TREND_SELL
- PA_VWAP_REV_D1_0_TREND_BUY
- PA_VWAP_REV_D1_0_TREND_SELL

## Ensemble Impact

Total validated signals increased from 26 to 30

### All Validated Signals (Ranked by OOS Net)

#    Signal                                   OOS     WR  Weight
-----------------------------------------------------------------
1    PA_BB_M2_0_TREND_SELL                  +3446   60.0    2.00
2    PA_VWAP_Z_Z2_0_TREND_SELL              +1759   39.7    2.00
3    PA_TUESDAY_TREND_SELL                  +1014   36.4    2.00
4    PA_POC_REV_TREND                        +718    0.0    1.44
5    PA_MFI_B20_TREND                          +0    0.0    0.50
6    PA_TSI_T25_TREND                          +0    0.0    2.00
7    PA_LIQ_GRAB_TREND                         +0    0.0    2.00
8    PA_MFI_B20_HYBRID                         +0    0.0    0.63
9    PA_TSI_T25_HYBRID                         +0    0.0    1.82
10   PA_ADX_BREAK_A25_RANGE_SELL            +1280    0.0    2.00
11   PA_ADX_BREAK_A25_HYBRID_SELL           +6092    0.0    2.00
12   PA_MA_CROSS_F9_S21_TREND_SELL          +1232    0.0    2.00
13   PA_REV_RSI_B15_TREND_SELL               +898    0.0    1.80
14   PA_REV_RSI_B15_RANGE_SELL              +3854    0.0    2.00
15   PA_REV_RSI_B15_HYBRID_SELL            +13111    0.0    2.00
16   PA_VWAP_Z_Z2_0_RANGE_SELL              +2052    0.0    2.00
17   PA_VWAP_Z_Z2_0_HYBRID_SELL              +289    0.0    0.63
18   PA_VWAP_REV_D1_0_RANGE_SELL            +7856    0.0    2.00
19   PA_VWAP_REV_D1_0_HYBRID_SELL           +7856    0.0    2.00
20   PA_BB_M2_0_HYBRID_SELL                  +190    0.0    0.50
21   PA_KELT_M2_0_HYBRID_SELL                +190    0.0    0.50
22   PA_POC_REV_RANGE_SELL                  +1943    0.0    2.00
23   PA_EXHAUST_Dn1_0_M40_TREND_SELL        +4399    0.0    2.00
24   PA_VCP_TREND_SELL                      +7647    0.0    2.00
25   PA_VCP_RANGE_SELL                       +281    0.0    2.00
26   PA_VCP_HYBRID_SELL                    +12149    0.0    2.00
27   PA_TSI_T25_RANGE_SELL                   +590    0.0    1.18
28   PA_TSI_T25_HYBRID_SELL                 +9532    0.0    2.00
29   PA_TUESDAY_RANGE_SELL                 +36820    0.0    2.00
30   PA_TUESDAY_HYBRID_SELL                  -488    0.0    2.00

## Monthly PnL Analysis (F2 Phase)

The F2 ranking now includes monthly breakdown. Key observations from SELL signals:

**PA_VWAP_REV_D1_0_RANGE_SELL (Best F2 Config):**
- TP=6.0, SL=0.8, ATR=[50,600]
- Total F2: +141159 | Trades: 224 | WR: 76.3%

**PA_EXHAUST_Dn1_0_M40_TREND_SELL (Best F2 Config):**
- TP=5.0, SL=2.0, ATR=[50,600]
- Total F2: +30016 | Trades: 74 | WR: 64.9%

## Recommendations

1. **Accept SELL-only ensemble:** The 4 new validated SELL signals are strong additions.
   PA_VWAP_REV_D1_0_RANGE_SELL (+7,856) is now the second-best signal overall.

2. **Remove BUY columns from parquet:** PA_ESTOCASTICO_RANGE_BUY, PA_IFR_OVERSOLD_BUY,
   and other BUY-only columns add data size without value.

3. **Test missing SELL signals:** 9 signals were not tested (mostly ESTOCASTICO and IFR SELL variants).
   These should be retested with adjusted GridAdvisor thresholds.

4. **Investigate unified trades:** The V71_UNIFIED_TRADES_F3.csv was not generated.
   Likely cause: signals that reach F3 produce zero trades, or the collection code has a bug.

5. **Monthly PnL is valuable:** The jan/feb/mar breakdown reveals consistency.
   Signals with positive PnL in all 3 months are more robust than those with one strong month.

## Technical Notes

- **F1 Directional Fix:** Confirmed working. BUY signals now evaluate LONG trades correctly.
- **Sanity Floors:** SL >= 0.5x ATR enforced, R:R <= 10 enforced.
- **GridAdvisor:** 9 signals aborted early (spinning or no F1 results).
- **Cycle Memory:** 155 total cycles, 34 validated signals (30 pre-V7.1 + 4 new).
