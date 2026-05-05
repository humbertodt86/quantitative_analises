# V71+ Walk-Forward Analysis Report

**Date:** 2026-05-03
**Cycle:** V7.1+ with Walk-Forward enabled

## WFA Implementation Summary

### Infrastructure Changes
- **3 Fold Engines:** Fev (Feb 1-28), Mar (Mar 1-28), Abr (Mar 30-Apr 29)
- **WFA Columns in F2 Rank:** wf_fev_net, wf_mar_net, wf_abr_net, wf_avg, wf_robust
- **Ranking Criterion:** Primary=wf_robust (positive folds), Secondary=wf_avg, Tertiary=Sharpe
- **Robustness Threshold:** Positive in 2+ of 3 folds required for promotion

## Signals with WFA Data

Total F2 rank files with WFA: 15

| Signal | F2 Net | Fev | Mar | Abr | WF Avg | Robust | F2 WR |
|--------|--------|-----|-----|-----|--------|--------|-------|
| PA_EXHAUST_Dn1_0_M40_TREND_SELL | +14928 | +3842 | +1180 | +1228 | +2083 | 3/3 | 80.6% |
| PA_ESTOCASTICO_TREND_BUY | -19844 | -9939 | -2131 | +696 | -3791 | 1/3 | 34.3% |
| PA_POC_REV_TREND_BUY | -6071 | -3634 | +213 | -458 | -1293 | 1/3 | 55.3% |
| PA_VWAP_REV_D1_0_HYBRID_BUY | -10165 | -6457 | +1592 | -1181 | -2015 | 1/3 | 27.8% |
| PA_VWAP_REV_D1_0_RANGE_BUY | -10165 | -6457 | +1592 | -1181 | -2015 | 1/3 | 27.8% |
| PA_ESTOCASTICO_HYBRID_BUY | +0 | +0 | +0 | +0 | +0 | 0/3 | 0.0% |
| PA_ESTOCASTICO_RANGE_BUY | +0 | +0 | +0 | +0 | +0 | 0/3 | 0.0% |
| PA_EXHAUST_Dn1_0_M40_HYBRID_BUY | +0 | +0 | +0 | +0 | +0 | 0/3 | 0.0% |
| PA_EXHAUST_Dn1_0_M40_RANGE_BUY | +0 | +0 | +0 | +0 | +0 | 0/3 | 0.0% |
| PA_EXHAUST_Dn1_0_M40_TREND_BUY | +0 | +0 | +0 | +0 | +0 | 0/3 | 0.0% |
| PA_IFR_OVERSOLD_HYBRID_BUY | +0 | +0 | +0 | +0 | +0 | 0/3 | 0.0% |
| PA_IFR_OVERSOLD_RANGE_BUY | +0 | +0 | +0 | +0 | +0 | 0/3 | 0.0% |
| PA_IFR_OVERSOLD_TREND_BUY | +0 | +0 | +0 | +0 | +0 | 0/3 | 0.0% |
| PA_POC_REV_HYBRID_BUY | +0 | +0 | +0 | +0 | +0 | 0/3 | 0.0% |
| PA_POC_REV_RANGE_BUY | +0 | +0 | +0 | +0 | +0 | 0/3 | 0.0% |

### Robustness Distribution

- **3/3 folds positive:** 1 signals
  - PA_EXHAUST_Dn1_0_M40_TREND_SELL: Fev=+3842, Mar=+1180, Abr=+1228, Avg=+2083

- **2/3 folds positive:** 0 signals

- **1/3 folds positive:** 4 signals
  - PA_ESTOCASTICO_TREND_BUY: Fev=-9939, Mar=-2131, Abr=+696
  - PA_POC_REV_TREND_BUY: Fev=-3634, Mar=+213, Abr=-458
  - PA_VWAP_REV_D1_0_HYBRID_BUY: Fev=-6457, Mar=+1592, Abr=-1181
  - PA_VWAP_REV_D1_0_RANGE_BUY: Fev=-6457, Mar=+1592, Abr=-1181

- **0/3 folds positive:** 10 signals

## Unified F3 Trades

- **Total trades:** 108
- **Strategies represented:** 2
- **First column:** strategy_name

## V7.1 OOS Results

- **Signals tested:** 22
- **BUY signals:** 14
- **SELL signals:** 8

## WFA Impact on Ranking

Signals with `wf_robust=3` would be PROMOTED to top of F2 ranking.
Signals with `wf_robust=0` would be DEMOTED to bottom.

### Promoted by WFA (3/3 positive folds)
- PA_EXHAUST_Dn1_0_M40_TREND_SELL

### Demoted by WFA (0/3 positive folds)
- PA_ESTOCASTICO_HYBRID_BUY
- PA_ESTOCASTICO_RANGE_BUY
- PA_EXHAUST_Dn1_0_M40_HYBRID_BUY
- PA_EXHAUST_Dn1_0_M40_RANGE_BUY
- PA_EXHAUST_Dn1_0_M40_TREND_BUY
- PA_IFR_OVERSOLD_HYBRID_BUY
- PA_IFR_OVERSOLD_RANGE_BUY
- PA_IFR_OVERSOLD_TREND_BUY
- PA_POC_REV_HYBRID_BUY
- PA_POC_REV_RANGE_BUY

## Conclusion

Walk-Forward Analysis successfully integrated into F2 validation.
The ranking now prioritizes temporal consistency over raw PnL.
Signals with positive PnL in all 3 monthly folds are ranked highest,
regardless of their total IS PnL.
