# WDO Engine V2 — Technical Reference for LLM Agents

## 1. Project Architecture

```
meta_trade5/
├── backtest/
│   ├── engine_v2.py          # Fast backtest engine (core)
│   ├── engine_v119_v2.py     # Tick-level exit simulation (HSTAG, BE)
│   ├── engine_tick_real.py    # Tick index builder
│   ├── indicators.py          # Technical indicators (ATR, ADX, RSI, BB, VWAP)
│   ├── config.py              # InstrumentConfig
│   └── strategies/            # Strategy base classes
├── scripts/
│   ├── build_wdo_indicators.py   # Step 1: Build base indicators (M5/M15)
│   ├── build_indicators.py       # Alt: Build M1/M5/M15 indicators with signals
│   ├── build_super_table.py      # Step 2: Build super table (67+ cols, all signals)
│   ├── build_wdo_ticks.py        # Build merged tick parquet
│   ├── fix_is_spread.py          # Fix IS ticks with OOS spread
│   ├── fix_sr.py                 # Step 3: Add S/R levels to super table
│   ├── gen_tabelao.py            # Trade table + correlation analysis
│   ├── analise_diaria.py         # Per-day breakdown reports
│   ├── grid_v3.py                # Parallel grid search (worker pool)
│   ├── test_sr.py                # S/R buffer test
│   └── rebuild_oos.py            # Rebuild OOS tick timeframe
├── data/
│   ├── candles/
│   │   ├── WDO$_M1.csv       # Raw MT5 candles (tab-separated)
│   │   ├── WDO$_M5.csv
│   │   └── WDO$_M15.csv
│   ├── ticks/
│   │   └── WDOK26_ticks_*.parquet  # Raw tick files
│   ├── WDO_ticks_is.parquet       # IS ticks (Jan-Mar, last-only)
│   ├── WDO_ticks_is_fixed.parquet # IS ticks with corrected spread
│   ├── WDO_ticks_oos.parquet      # OOS ticks (Mar30-Apr28, real bid/ask)
│   └── WDO_merged_all.parquet     # All ticks merged
├── super_wdo_M5.parquet      # Master indicator table (101k rows, 104 cols)
├── super_wdo_M1.parquet
├── super_wdo_M15.parquet
├── indicators_wdo_M5.parquet # Base indicators only
└── docs/                     # Reports
```

## 2. Data Pipeline (Build Order)

### Step 1: Raw Candles → Indicators Parquet
**Script**: `scripts/build_wdo_indicators.py`
```
Input:  data/candles/WDO$_M5.csv (MT5 export, tab-separated)
Output: data/indicators_wdo_M5.parquet
```
Columns: `dt, open, high, low, close, volume, ADX7, ATR, EMA5_SLOPE, EMA5_SLOPE_ABS, GK_RATIO, VWAP, MA9/21/50, RIBBON_STATE, PA_SIGNAL_DIR, hour, minute, VWAP_distance, dist, DIST_ABS`

Uses `backtest.indicators.add_indicators()` which adds: EMA20, EMA5, ATR (daily reset), EMA_SLOPE, ADX, RSI14, BB_UPPER/LOWER, BB_WIDTH_PCT, VWAP, DIST_VWAP.

ATR convention (`indicators.py:76-121`): `daily_atr=True` — ATR recalculates each day independently (rolling 14 within groupby date). This replicates MT5 live bot behavior which loads only current day's candles.

### Step 2: Base Indicators → Super Table
**Script**: `scripts/build_super_table.py`
```
Input:  data/candles/WDO$_M5.csv
Output: super_wdo_M5.parquet (67+ cols)
```
Adds:
- **VWAP_Z-Score**: rolling 20-period z-score of VWAP distance
- **RSI2, RSI3**: ultra-short Wilder RSI
- **Initial Balance**: first hour high/low, distances
- **Value Area / POC**: previous day volume profile (VAH, VAL, POC)
- **Gap Detection**: opening gap vs previous close, normalized by ATR
- **Signal columns**: PA_SIGNAL_DIR, PA_SIGNAL_REV, PA_REV_RSI, PA_VWAP_Z, PA_IB_BOUNCE, PA_BB, PA_BREAKOUT, PA_VWAP_REV

### Step 3: Super Table → Final with S/R
**Script**: `scripts/fix_sr.py`
```
Input:  super_wdo_M5.parquet
Output: super_wdo_M5.parquet (104 cols)
```
Adds proper Support/Resistance levels:
- **D1/D2/D3 daily levels**: previous 1/2/3 day high/low, close (shifted by date, not rolling)
- **Distances**: close - level, normalized by ATR
- **Nearest S/R**: closest of D1/D2/D3 levels
- **Pivot Points**: (H+L+C)/3 per day, R1/R2/S1/S2
- **Psychological Levels**: round 50s (psych_up, psych_down)
- **S/R Buffer Targets**: TP at 90% of dist to resistance, SL at 110% of dist to support
- **tp_sr_pts, sl_sr_pts**: point values for S/R-based TP/SL

### Step 4: Tick Data
**Script**: `scripts/build_wdo_ticks.py`
```
Input:  data/ticks/WDOK26_ticks_*.parquet
Output: data/WDO_merged_all.parquet
```
Columns: `time_msc, last, bid, ask, volume`

**Script**: `scripts/fix_is_spread.py`
```
Input:  data/WDO_ticks_is.parquet (last-only)
Output: data/WDO_ticks_is_fixed.parquet
```
Adds synthetic bid/ask based on OOS median spread (~1.0 pt). IS has no real bid/ask because in-sample period was not traded in real-time.

## 3. Engine V2 Architecture

### File: `backtest/engine_v2.py` (531 lines)

#### Core Classes

**ModeConfig** — configuration for one strategy "mode":
```python
@dataclass
class ModeConfig:
    enabled: bool = True
    priority: int = 0                    # Higher = evaluated first
    filters: dict = None                 # Filter conditions on indicators
    behp: dict = None                    # BE/HP (HSTAG) parameters
    tp_mult: float = 1.0                 # ATR multiplier for TP
    sl_mult: float = 1.0                 # ATR multiplier for SL
    tp_sr_pct: float = 0.0              # Blend: 0=pure ATR, 1=pure S/R
    sl_sr_pct: float = 0.0
    tp_buffer: float = 0.90             # S/R TP buffer (90% of distance)
    sl_buffer: float = 1.10             # S/R SL buffer (110% of distance)
    min_sl: int = 50                     # Minimum SL in pts
    max_sl: int = 200                    # Maximum SL in pts
```

**BacktestConfig**:
```python
@dataclass
class BacktestConfig:
    name: str = "Untitled"
    modes: dict = None          # Dict[str, ModeConfig]
    hour_min: float = 9.75      # Entry window start
    hour_max: float = 17.5      # Entry window end
```

**BacktestEngine**:
```python
class BacktestEngine:
    def __init__(self, indicators_path: str):
        self.df = None           # Polars DataFrame with indicators
        self.config = None       # BacktestConfig
        self.ticks_raw = None    # Raw tick data
        self.tick_idx = None     # List of (start, end) per candle
        self.bid_arr = None      # numpy array of bid prices
        self.ask_arr = None      # numpy array of ask prices
```

#### Lifecycle

1. **`load_indicators(path)`** — Read parquet file (Polars)
2. **`load_config(path)` or `load_config_dict(dict)`** — Parse JSON or dict into config
3. **`load_ticks_for_simulation(path)`** — Load ticks, build index aligning tick time to candle time. Each bar `i` maps to `(tick_start_idx, tick_end_idx)` via `np.searchsorted(tick_timestamp, bar_timestamp)`
4. **`simulate(mode_filter=None)`** — Main simulation loop:
   - Iterates rows 20..N-1
   - Applies time filter `hour_min..hour_max`
   - Sorts modes by priority (descending)
   - Checks SCALPER blocking logic (`_sniper_blocks_scalper`)
   - Applies mode filters (indicator conditions)
   - Calculates TP/SL: blend of ATR-based and S/R-based
   - Calls `_simulate_exit_v119()` for tick-level simulation
5. **`calculate_metrics(results)`** — Returns: n, pnl, exp, wr, profit_factor, max_dd, be_saved, hstag_count

#### Filter System

Filters in `_apply_filter(value, spec)`:
```python
{"min": N}    # value >= N
{"max": N}    # value <= N
{"eq": N}     # value == N
{"neq": N}    # value != N
{"gt": N}     # value > N
{"lt": N}     # value < N
{"exclude": [N1, N2]}  # value not in list
```

Filters are applied per indicator column name:
```python
mode_cfg.filters = {
    "ATR": {"min": 2, "max": 15},
    "PA_REV_RSI": {"neq": 0},
    "VWAP_Z": {"max": -1.0}
}
```

#### S/R Blended TP/SL Calculation
```python
tp_atr = atr_val * tp_mult
tp_sr = dist_to_resistance * tp_buffer (if tp_sr_pct > 0)
tp = tp_atr * (1 - tp_sr_pct) + tp_sr * tp_sr_pct

sl_atr = atr_val * sl_mult
sl_sr = dist_to_support * sl_buffer (if sl_sr_pct > 0)
sl = sl_atr * (1 - sl_sr_pct) + sl_sr * sl_sr_pct
sl = max(min_sl, min(sl, max_sl))
```

## 4. Tick-Level Exit Simulation

The actual exit simulation happens in `engine_v119_v2.py:_simulate_exit_v119()`. Engine V2 wraps this function.

**Tick index building** (`engine_v2.py:84-101`):
```python
tick_sec = ticks_ts / 1000  # convert ms to seconds
bar_starts_sec = df['dt'].dt.timestamp() // 1_000_000
bar_ends_sec = [bar_starts_sec[1:], last+300]
for i: tick_idx[i] = (searchsorted(tick_sec, bar_start), searchsorted(tick_sec, bar_end))
```

**Simulation flow** per trade:
1. Entry at candle open price
2. For each tick in candle range (bid_arr/ask_arr):
   - Check TP hit (ask >= entry + tp for BUY)
   - Check SL hit (bid <= entry - sl for BUY)
   - Check BE triggered (profit > be_trigger, move SL to entry + be_offset)
   - Check HSTAG (H-Progress Inertia): if duration >= hp_candles AND profit < hp_th, close at market
   - Check hard_stop
3. If no exit during ticks, exit at candle close

**Returns**: `(pnl, hit_type, mfe, mae)`

## 5. Grid Search (Worker Pool Pattern)

### File: `scripts/grid_v3.py`

**Pattern**: Each worker process loads data ONCE via `worker_init()`, then handles combos via `worker_run(params)`.

```python
def worker_init():
    global _worker_eng
    df = pl.read_parquet(IND).filter(IS period)
    _worker_eng = BacktestEngine(None)  # bypass load_indicators
    _worker_eng.df = df
    _worker_eng.load_ticks_for_simulation(TICKS_IS)

def worker_run(params):
    global _worker_eng
    # Build config dict from params tuple
    # eng.load_config_dict(cfg)
    # eng.simulate() → calculate_metrics() → return dict
```

**Execution**:
```python
with Pool(processes=n_workers, initializer=worker_init) as pool:
    results = pool.map(worker_run, grid, chunksize=50)
```

**Key params tuple**: `(tp, sl, vz, hsc, hsth, hard, atr_min, dist, dxy_min, poc, ib_min, hh, hl)`

**Chunksize**: 50 (reduces IPC overhead)

**Performance**: ~0.2s per combo, 10 workers → ~50 combos/s

### Typical Grid Dimensions

| Param | Range | Values | Combos |
|-------|-------|--------|--------|
| tp_mult | 3.0-8.0 | 5 | × |
| sl_mult | 0.6-1.5 | 5 | × |
| VWAP_Z | -1.0 to -2.0 | 3 | × |
| HSC (candles) | 2-6 | 3 | × |
| HSTH (pts) | 5-15 | 3 | × |
| Hard Stop | 10-20 | 3 | × |
| DIST | 0-8 | 2 | × |
| Hours | 9-12, 9-14 | 2 | |
| Total | | | ~24k |

### Cost Model
```python
COST = 1.2  # pts per trade (0.5 entry slip + 0.5 exit + 0.2 brokerage)
net = gross_pnl - N_trades * COST
```

### IS/OOS Split
- **IS**: Jan 2, 2026 to Mar 29, 2026 (60 trading days)
- **OOS**: Mar 30, 2026 to Apr 28, 2026 (22 trading days)
- Filters applied via `pl.col('dt') >= IS_S & pl.col('dt') < IS_E`

## 6. Best Known Configuration (Baseline)

```
PA_REV_RSI strategy (RSI2 < 15 = BUY signal) + VWAP_Z < -1.0

IS (308 trades):  +7,325 pts gross,  WR 81.2%,  PF 39.2
OOS (99 trades):  +   49 pts net,    WR 59.6%,  PF 2.39

Config:
  Hour range:   9-12h
  TP_mult:      8.0 (but HSTAG exits before TP — never hits)
  SL_mult:      1.0
  HSTAG:        2 candles, 10 pts threshold
  Hard stop:    15 pts
  ATR filter:   min 2, max 15
  BE trigger:   10 pts
  BE offset:    1 pt
  min_sl:       3 pts
  max_sl:       40 pts
```

### Key Insights
- **ATR low = better**: corr -0.48 (reversals work in low vol)
- **dxy_trend NEGATIVE = better**: corr -0.29 (buy WDO when DXY weak)
- **dist_to_poc low = better**: near previous day POC
- **VWAP_Z more negative = better**: winners avg -1.99, losers avg -0.95
- **HSTAG = 100% of exits**: TP is never hit, all exits via HSTAG or SL
- **Morning only (9-12h) outperforms**: ATR drops 65% after lunch

## 7. Correlation Analysis

Run via `scripts/gen_tabelao.py`:
- Reads super_wdo_M5.parquet (IS period)
- Runs best strategy
- For each indicator column, calculates correlation with PnL
- Outputs `docs/WDO_TRADE_TABLE_BEST.csv` (308 trades × 85 indicators)
- Outputs `docs/WDO_CORRELATIONS.csv`

Top positive correlates (with PnL):
- `vwap_monthly` +0.70, `d3_low_prev` +0.67, `d2_low_prev` +0.64
- `sl_sr_target` +0.62, `nearest_support` +0.62

Top negative correlates:
- `ATR` -0.48, `vwap_monthly_z` -0.38, `dist_to_d2_low` -0.34
- `dist_to_nearest_sup` -0.33, `sl_sr_pts` -0.33

## 8. S/R Buffer Test

Run via `scripts/test_sr.py`:
- Tests tp_sr_pct ∈ [0, 0.1, 0.2, 0.3, 0.4, 0.5]
- Tests sl_sr_pct ∈ [0, 0.1, 0.2, 0.3, 0.4, 0.5]
- Tests tp_buffer ∈ [0.8, 0.9, 1.0]
- Tests sl_buffer ∈ [1.0, 1.1, 1.2]

Result (WDO S/R Buffer Report):
- Baseline (pure ATR): OOS +49 pts
- Best (tp_sr=0.2, sl_sr=0.2): OOS +53 pts (+8.2%)
- Higher S/R percentages degrade OOS

## 9. Per-Day Analysis Reports

Run via `scripts/analise_diaria.py`:
- Tests 6 strategy variants
- Per day breakdown: trades, gross, cost, net, TP/SL/BE/HP counts
- Outputs to `docs/WDO_ANALISE_*.txt`

## 10. Adding a New Strategy

### Pattern:
1. Add signal column to `build_super_table.py` (e.g., PA_MY_SIGNAL)
2. Rebuild super table: `python scripts/build_super_table.py`
3. Run `scripts/fix_sr.py` to recalculate S/R on top
4. Test correlation: `python scripts/gen_tabelao.py`
5. Grid search: Add new filter to existing `grid_v3.py` or write new grid
6. Run `scripts/analise_diaria.py` for day breakdown
7. If promising, test with S/R buffers via `scripts/test_sr.py`

## 11. Signal Columns Reference

| Signal | Logic | Used In |
|--------|-------|---------|
| PA_SIGNAL_DIR | close > EMA20 = +1, close < EMA20 = -1 | Base trend |
| PA_SIGNAL_REV | -PA_SIGNAL_DIR | Mean reversion |
| PA_REV_RSI | RSI2 < 15 = +1, RSI2 > 85 = -1 | **Best strategy** |
| PA_VWAP_Z | VWAP_Z < -2.0 = +1, > 2.0 = -1 | Often combined |
| PA_IB_BOUNCE | close near IB low + RSI2 < 20 = +1 | Initial balance |
| PA_BB | close below BB_LOWER = +1 | Bollinger reversal |
| PA_BREAKOUT | ADX > 30 + slope ≥ 3 + ribbon = direction | Trend |
| PA_VWAP_REV | VWAP distance > 0.6×ATR + ADX < 25 | VWAP pullback |

## 12. Engine V2 Configuration JSON Format

```json
{
  "name": "MY_STRATEGY",
  "hour_min": 9,
  "hour_max": 12,
  "modes": {
    "REVERSAL": {
      "enabled": true,
      "priority": 3,
      "tp_mult": 8.0,
      "sl_mult": 1.0,
      "tp_sr_pct": 0.0,
      "sl_sr_pct": 0.0,
      "tp_buffer": 0.9,
      "sl_buffer": 1.1,
      "min_sl": 3,
      "max_sl": 40,
      "filters": {
        "ATR": {"min": 2, "max": 15},
        "PA_REV_RSI": {"neq": 0},
        "VWAP_Z": {"max": -1.0}
      },
      "behp": {
        "be_trigger": 10,
        "be_offset": 1,
        "hp_th": 10,
        "hp_candles": 2,
        "hard_stop": 15
      }
    }
  }
}
```

## 13. Environment
- **Python**: 3.11+, venv at `.venv/`
- **Dependencies**: polars, pandas, numpy
- **OS**: Windows (PowerShell paths)
- **GPU**: None needed (CPU-bound, 14 cores / 20 logical)
- **RAM**: ~16GB (8.5 used by OS, 7.5GB available for ML)

## 14. Quick Start for LLM Agents

```bash
# Step 1: Rebuild indicators from candles
python scripts/build_wdo_indicators.py

# Step 2: Build super table with signals
python scripts/build_super_table.py

# Step 3: Add S/R levels
python scripts/fix_sr.py

# Step 4: Test correlation
python scripts/gen_tabelao.py

# Step 5: Create a grid search
python scripts/grid_v3.py

# Step 6: Analyze per day
python scripts/analise_diaria.py

# Step 7: Test S/R buffers
python scripts/test_sr.py
```

### Direct Engine Usage (Python)
```python
from backtest.engine_v2 import BacktestEngine
from datetime import datetime
import polars as pl

IND = 'super_wdo_M5.parquet'
TICKS = 'data/WDO_ticks_is_fixed.parquet'
IS_S, IS_E = datetime(2026,1,2), datetime(2026,3,29)

df = pl.read_parquet(IND).filter(
    (pl.col('dt') >= IS_S) & (pl.col('dt') < IS_E)
)

eng = BacktestEngine(None)
eng.df = df
eng.load_ticks_for_simulation(TICKS)
eng.load_config_dict(cfg_dict)
results = eng.simulate()
metrics = eng.calculate_metrics(results)
```

### Direct Engine V2 Usage (JSON config)
```python
eng = BacktestEngine('super_wdo_M5.parquet')
eng.load_indicators()
eng.load_config('my_config.json')
eng.load_ticks_for_simulation('data/WDO_ticks_is_fixed.parquet')
results = eng.simulate()
metrics = eng.calculate_metrics(results)
```
