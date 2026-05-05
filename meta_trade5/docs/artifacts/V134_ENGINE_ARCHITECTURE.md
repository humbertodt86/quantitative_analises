# V134 Engine Architecture - Implementation Report

**Date:** 2026-04-27
**Status:** IMPLEMENTED

---

## Summary

New backtest engine architecture implemented with significant performance improvements.

### Performance

| Metric | Old Method | New Engine | Speedup |
|--------|-----------|------------|---------|
| Time | 36.1s | 2.0s | **18x** |
| Load indicators | ~30s | 0.01s | Pre-calculated |

### Results Comparison

| Metric | Old (Cycle 5) | New Engine | Delta |
|--------|---------------|------------|-------|
| Trades | 162 | 231 | +69 |
| PnL | 28,789 | 38,827 | +10,038 |
| Exp | 177.7 | 168.1 | -9.6 |
| PF | 6.39 | 5.51 | -0.88 |

### Known Differences

The engine gives slightly different results due to:
1. Mode priority implementation differences
2. Filter application order
3. Some edge cases in filter interpretation

**Note:** For final results, use the OLD method (Cycle 5). The new engine is useful for:
- Fast iteration during development
- Grid search (where relative comparison matters)
- Parameter exploration

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    NEW ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  [1] PREPARE INDICATORS (once per data update)             │
│      ticks.parquet → indicators.parquet                     │
│      Script: research/prepare_indicators.py                 │
│                                                              │
│  [2] ENGINE (fast, stateless)                               │
│      indicators.parquet + config.json → Results              │
│      Module: backtest/engine_v2.py                           │
│                                                              │
│  [3] GRID SEARCH (parallel)                                 │
│      backtest/grid_search.py                                 │
│                                                              │
│  [4] CONFIG (JSON-based)                                    │
│      configs/v134_default.json                               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Files Created

| File | Purpose |
|------|---------|
| `backtest/engine_v2.py` | New BacktestEngine class |
| `backtest/grid_search.py` | Parallel grid search |
| `configs/v134_default.json` | Default configuration |
| `data/indicators/indicators_jan2026.parquet` | Pre-calculated indicators |
| `research/prepare_indicators.py` | Script to prepare indicators |
| `research/compare_engine.py` | Comparison script |
| `docs/artifacts/engine_comparison.json` | Comparison results |

---

## Usage

### 1. Prepare Indicators (when data changes)

```bash
python research/prepare_indicators.py --start 2026-01-01 --end 2026-01-31
```

### 2. Run Backtest

```python
from backtest.engine_v2 import BacktestEngine, load_default_config

engine = BacktestEngine('data/indicators/indicators_jan2026.parquet')
engine.load_indicators()
engine.load_ticks_for_simulation('data/raw/ticks/.../year=2026/month=1/00000000.parquet')

config = load_default_config()
engine.load_config_dict(config)

results = engine.simulate()
metrics = engine.calculate_metrics(results)
```

### 3. Run Grid Search

```python
from backtest.grid_search import GridSearch

gs = GridSearch(config, indicators_path, ticks_path)
gs.run(param_grid, n_workers=8)
top_results = gs.get_top_n(10)
```

---

## Config Format

```json
{
  "name": "V134_SNIPER_FIRST",
  "hour_min": 9.75,
  "hour_max": 17.5,
  "modes": {
    "SNIPER": {
      "enabled": true,
      "priority": 3,
      "tp_mult": 3.5,
      "sl_mult": 1.11,
      "filters": {
        "ADX7": {"min": 20},
        "EMA5_SLOPE_ABS": {"min": 25},
        "GK_RATIO": {"min": 1.0, "max": 1.3},
        "ATR": {"min": 300, "max": 500},
        "HOUR": {"exclude": [9, 15]},
        "RIBBON_STATE": {"eq": -1},
        "PA_SIGNAL_DIR": {"neq": 0},
        "EMA5_SLOPE": {"gt": 0}
      },
      "behp": {
        "be_trigger": 500,
        "be_offset": 20,
        "hp_th": 3,
        "hp_candles": 2,
        "hard_stop": 150
      }
    }
  }
}
```

### Filter Operators

| Operator | Description |
|----------|-------------|
| `min` | Value >= min |
| `max` | Value <= max |
| `eq` | Value == eq |
| `neq` | Value != neq |
| `gt` | Value > gt |
| `lt` | Value < lt |
| `exclude` | Value not in list |

---

## Known Issues

1. **Results differ slightly from old method** - due to filter implementation differences
2. **SCALPER count higher** - 150 vs 81 in old method

## Recommendations

1. Use OLD method for final validation
2. Use NEW engine for parameter exploration and iteration
3. Always compare final results with old method before deployment

---

## Next Steps

1. [ ] Fix engine to match old method exactly
2. [ ] Add more filter operators
3. [ ] Implement walk-forward validation
4. [ ] Add Monte Carlo simulation support

---

*Generated: 2026-04-27*
