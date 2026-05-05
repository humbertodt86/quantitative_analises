# V7.2 Final Closure Report — Missing Signals Analysis

**Date:** 2026-05-03
**Cycle:** V7.2 Closure

---

## Executive Summary

The 9 "missing signals" from V7.1 were analyzed after BUY column removal. **Zero additional SELL signals are testable.**

| Category | Count | Signals | Reason |
|----------|-------|---------|--------|
| **Columns removed** | 6 | ESTOCASTICO (3) + IFR_OVERSOLD (3) | BUY-only columns removed from parquet. No base columns exist for SELL. |
| **Zero entries in TREND** | 1 | PA_VWAP_REV_D1_0_TREND_SELL | VWAP_REV never fires in TREND regime for SELL (0/555 entries). |
| **BUY direction** | 2 | EXHAUST_TREND_BUY + VWAP_REV_TREND_BUY | BUY recovery abandoned. |
| **Total untestable** | **9** | — | — |

---

## Detailed Analysis

### 1. ESTOCASTICO Signals (3) — UNTESTABLE

| Signal | Column | Status |
|--------|--------|--------|
| PA_ESTOCASTICO_RANGE_SELL | PA_ESTOCASTICO_RANGE_BUY | **REMOVED** |
| PA_ESTOCASTICO_HYBRID_SELL | PA_ESTOCASTICO_RANGE_BUY | **REMOVED** |
| PA_ESTOCASTICO_TREND_SELL | PA_ESTOCASTICO_RANGE_BUY | **REMOVED** |

**Root cause:** `PA_ESTOCASTICO_RANGE_BUY` was a BUY-only column (values 0 or 1, no -1). No base `PA_ESTOCASTICO` column exists. Without this column, these signals have no data source.

**Previous test result (V6.7):** All 3 ESTOCASTICO SELL variants were tested and produced **zero trades** (F1 aborted). Even with the column, there was no SELL edge.

---

### 2. IFR_OVERSOLD Signals (3) — UNTESTABLE

| Signal | Column | Status |
|--------|--------|--------|
| PA_IFR_OVERSOLD_RANGE_SELL | PA_IFR_OVERSOLD_BUY | **REMOVED** |
| PA_IFR_OVERSOLD_HYBRID_SELL | PA_IFR_OVERSOLD_BUY | **REMOVED** |
| PA_IFR_OVERSOLD_TREND_SELL | PA_IFR_OVERSOLD_BUY | **REMOVED** |

**Root cause:** `PA_IFR_OVERSOLD_BUY` was a BUY-only column (values 0 or 1, no -1). No base `PA_IFR_OVERSOLD` column exists.

**Previous test result (V6.7):** All 3 IFR_OVERSOLD SELL variants were tested and produced **zero trades** (F1 aborted).

---

### 3. PA_VWAP_REV_D1_0_TREND_SELL — UNTESTABLE

| Signal | Column | TREND Entries | RANGE Entries | HYBRID Entries |
|--------|--------|:-------------:|:-------------:|:--------------:|
| PA_VWAP_REV_D1_0_TREND_SELL | PA_VWAP_REV_D1_0 | **0** | 555 | 555 |

**Root cause:** The VWAP_REV indicator fires exclusively in **RANGE regime** for SELL direction. In TREND regime, it produces zero entries. This is by design — VWAP reversal signals occur when price deviates from VWAP and reverts, which happens more in ranging markets.

**Verification:**
```
IS period candles: 6,517
SELL signals (-1): 555
TREND candles: 97
TREND + SELL: 0
RANGE + SELL: 555
HYBRID + SELL: 555
```

**Conclusion:** The RANGE_SELL and HYBRID_SELL variants of this signal were already tested and validated (+7,856 OOS). The TREND variant is impossible by construction.

---

### 4. BUY Signals (2) — ABANDONED

| Signal | Direction | Status |
|--------|:---------:|--------|
| PA_EXHAUST_Dn1_0_M40_TREND_BUY | BUY | Abandoned |
| PA_VWAP_REV_D1_0_TREND_BUY | BUY | Abandoned |

**Root cause:** BUY recovery was abandoned after V7.0/V7.1. 0/29 BUY signals tested produced positive OOS. WIN has a structural short bias in Apr 2026.

---

## V7.2 Final Status

### Completed Tasks
- [x] Extract validated signals from cycle_memory.json (26 signals)
- [x] Build SELL-only ensemble report (11 signals, 3 tiers)
- [x] Generate updated ensemble_priority_list.json
- [x] Update docs/progress.md and docs/cycle_plan.md
- [x] Remove BUY-only columns from parquet (5 columns, 193→188)
- [x] Analyze missing 9 signals (all untestable/abandoned)

### Ensemble Summary
- **Signals in ensemble:** 11 SELL-only
- **WFA anchor:** PA_EXHAUST_Dn1_0_M40_TREND_SELL (3/3 robust)
- **Top performer:** PA_REV_RSI_B15_HYBRID_SELL (+13,111 OOS)
- **Expected ensemble OOS:** ~7,200 pts

### No Further SELL Signals to Test
All viable SELL signals have been tested. The remaining untested signals are either:
1. Dependent on removed BUY-only columns (ESTOCASTICO, IFR)
2. Impossible by construction (VWAP_REV in TREND)
3. BUY direction (abandoned)

---

## Recommendations

1. **Do NOT recreate BUY columns** — The ESTOCASTICO and IFR indicators showed no SELL edge in V6.7 tests. Recreating them would waste space.
2. **Accept the 11-signal ensemble** — This is the final set of testable, validated SELL signals for WIN Apr 2026.
3. **Move to V7.3** — Ensemble execution, Monte Carlo validation, and paper trading deployment.
4. **Consider new indicators** — If more signals are needed, develop new indicators with bidirectional columns (not BUY-only overlays).

---

## Files Status

| File | Status |
|------|--------|
| `super_win_continuous.parquet` | Cleaned (188 columns, backup saved) |
| `ensemble_priority_list.json` | Updated (11 signals) |
| `V72_ENSEMBLE_FINAL_REPORT.md` | Generated |
| `V72_MISSING_SIGNALS_CLOSURE.md` | Generated (this file) |
| `progress.md` | Updated |
| `cycle_plan.md` | Updated |

**V7.2 STATUS: COMPLETE**
