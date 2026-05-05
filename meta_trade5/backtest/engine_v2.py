"""
BacktestEngine v2 - Fast backtesting with pre-calculated indicators.

⚠️ BACKUP DA VERSAO ORIGINAL: engine_v2_BACKUP_ORIGINAL.py
   Este arquivo foi modificado para suportar Layer 2 (ensemble voting) e
   Layer 4 (risk manager). Se os resultados nao baterem com o MT5, compare
   com o backup e desabilite as novas features via defaults (weight=1.0,
   ensemble_threshold=0.5, risk_manager vazio).

Architecture:

Architecture:
1. Load pre-calculated indicators from parquet (done once)
2. Load configuration from JSON
3. Apply filters from config
4. Run simulation
5. Return results

LAYER 2 - ENSEMBLE VOTING (V6.3):
  Instead of picking a single mode by priority, simulate() now collects
  votes from ALL enabled modes. Weighted sum must exceed threshold to enter.
  Config: each mode has a 'weight' field, and BacktestConfig has 
  'ensemble_threshold' (default 0.5, range 0-1).
  Example:
    "modes": {
        "REV_RSI": {"enabled": true, "priority": 1, "weight": 2.0, ...},
        "TREND":   {"enabled": true, "priority": 2, "weight": 1.0, ...}
    }
  With above, REV_RSI vote counts double vs TREND.

LAYER 3 - DAY OF WEEK FILTER (already supported):
  Add to mode filters:
    "day_of_week": {"exclude": [5]}  # exclude Friday
  Values: 0=Monday, 1=Tuesday, ..., 4=Friday, 5=Saturday, 6=Sunday
  Example:
    "filters": {
        "day_of_week": {"exclude": [4, 5]},
        "ATR": {"min": 200}
    }

LAYER 4 - RISK MANAGER (V6.3):
  Global risk rules that span across trades and days.
  Config in BacktestConfig:
    "risk_manager": {
        "daily_stop": -5000,          # Max daily loss before stopping
        "consecutive_sl_limit": 5,    # SLs before circuit breaker (was hardcoded 5)
        "consecutive_sl_cooldown": 0  # Extra candles to wait after hitting limit
    }
  Defaults match existing behavior (5 SLs, no daily stop, no extra cooldown).

DATA PERIODS:
  - IS (In-Sample / Training):  Jan 2 -> Mar 27  (fast-screener for params)
  - OOS (Out-of-Sample / Validation): Mar 30 -> Apr 29 (tick-level validation)
  - Full data: Jan 2 -> Apr 29

TICK DATA:
  - WINJ26: Mar 30 -> Apr 15 (data/ticks/WINJ26_ticks_YYYYMMDD.parquet)
  - WINM26: Apr 14 -> Apr 29 (data/ticks/WINM26_ticks_YYYYMMDD.parquet)
  - Merged: data/WINM26_ticks_abril.parquet (Apr 14-29 only, WINM26)
  - All daily ticks have real bid/ask

ADX PERIODS (all pre-calculated in indicators parquet):
  - ADX7: 7-period ADX (35 min on M5) - fast, responsive
  - ADX14: 14-period ADX (70 min) - standard, used in many blueprints
  - ADX20: 20-period ADX (100 min) - slower, smoother
  - ADX30: 30-period ADX (150 min) - very slow, only major trends

COST MODEL:
  - WIN: 30 pts/trade (15 entry + 15 exit slippage)
  - WDO: 1.2 pts/trade (0.5 entry + 0.5 exit + 0.2 fees)
  - Spread is already included in bid/ask ticks (OOS only)

KEY RULES:
  1. Entry at NEXT candle's open (no look-ahead bias)
  2. Exit with tick-level simulation when bid/ask data available
  3. TP30 replaces HSTAG (blueprint V139)
  4. Grace Period BE: 2 candles after TP30 -> move SL to BE
  5. Slope Decay BE: current slope < 50% of entry slope -> BE
  6. Circuit Breaker: 5 consecutive SLs in same day -> block
"""
import sys
sys.path.insert(0, '.')

import json
import time
from dataclasses import dataclass, asdict
from typing import Optional
from pathlib import Path

import polars as pl
import numpy as np

from backtest.engine_v119_v2 import _simulate_exit_v119, _simulate_exit_ohlc, _build_tick_index


@dataclass
class ModeConfig:
    """Configuration for a single mode (SNIPER, HUNTER, SCALPER)."""
    enabled: bool = True
    priority: int = 0  # Higher = evaluated first
    filters: dict = None  # Filter conditions
    behp: dict = None    # BE/HP parameters
    signal_field: str = None  # Column to use for trade direction (None=PA_SIGNAL_DIR)
    tp_mult: float = 1.0
    sl_mult: float = 1.0
    tp_sr_pct: float = 0.0  # % of TP based on S/R distance (0=pure ATR, 1=pure S/R)
    sl_sr_pct: float = 0.0  # % of SL based on S/R distance
    tp_buffer: float = 0.90  # Buffer for TP (0.90 = TP at 90% of S/R distance)
    sl_buffer: float = 1.10  # Buffer for SL (1.10 = SL at 110% of S/R distance)
    sr_window: int = 10  # S/R lookback window (10, 30, 60 candles)
    min_sl: int = 50  # Minimum SL
    max_sl: int = 200  # Maximum SL
    weight: float = 1.0  # Voting weight in ensemble (Layer 2)

    def __post_init__(self):
        if self.filters is None:
            self.filters = {}
        if self.behp is None:
            self.behp = {}


@dataclass
class BacktestConfig:
    """Top-level configuration."""
    name: str = ""
    modes: dict = None  # Dict of mode_name -> ModeConfig
    hour_min: float = 9.75
    hour_max: float = 17.5
    max_bars: int = 0  # Max historical bars for indicator calc (0=unlimited, simulate MT5 lookback)
    modo_busca: bool = False  # True = desliga Circuit Breaker, lunch filter, 9:00-9:30 restriction, cooldown
    risk_manager: dict = None  # Layer 4: daily_stop, consecutive_sl_limit, consecutive_sl_cooldown
    ensemble_threshold: float = 0.5  # Layer 2: min |normalized_vote| to enter
    ensemble_min_votes: int = 1      # Layer 2: min number of agreeing modes to enter (overrides threshold if > 1)

    def __post_init__(self):
        if self.modes is None:
            self.modes = {}
        if self.risk_manager is None:
            self.risk_manager = {}

    def get_risk_manager(self) -> dict:
        return {
            'daily_stop': self.risk_manager.get('daily_stop', -999999),
            'consecutive_sl_limit': self.risk_manager.get('consecutive_sl_limit', 5),
            'consecutive_sl_cooldown': self.risk_manager.get('consecutive_sl_cooldown', 0),
        }


class BacktestEngine:
    """Fast backtest engine using pre-calculated indicators."""

    def __init__(self, indicators_path: str):
        """Initialize engine with pre-calculated indicators.

        Args:
            indicators_path: Path to parquet file with pre-calculated indicators
        """
        self.indicators_path = indicators_path
        self.df = None
        self.records = None
        self.config = None
        self.ticks_raw = None
        self.tick_idx = None
        self.bid_arr = None
        self.ask_arr = None
        self.daily_pnl = 0  # Layer 4: cumulative daily PnL
        self.daily_stop_triggered = False  # Layer 4: global stop flag

    def load_indicators(self) -> 'BacktestEngine':
        """Load pre-calculated indicators from parquet."""
        t0 = time.time()
        self.df = pl.read_parquet(self.indicators_path)
        print(f"  Loaded {len(self.df):,} rows in {time.time()-t0:.2f}s")
        return self

    def load_config(self, config_path: str) -> 'BacktestEngine':
        """Load configuration from JSON file.

        Args:
            config_path: Path to JSON config file
        """
        with open(config_path, 'r') as f:
            config_dict = json.load(f)

        # Parse modes
        modes = {}
        for mode_name, mode_dict in config_dict.get('modes', {}).items():
            modes[mode_name] = ModeConfig(
                enabled=mode_dict.get('enabled', True),
                priority=mode_dict.get('priority', 0),
                filters=mode_dict.get('filters', {}),
                behp=mode_dict.get('behp', {}),
                signal_field=mode_dict.get('signal_field', None),
                tp_mult=mode_dict.get('tp_mult', 1.0),
                sl_mult=mode_dict.get('sl_mult', 1.0),
                tp_sr_pct=mode_dict.get('tp_sr_pct', 0.0),
                sl_sr_pct=mode_dict.get('sl_sr_pct', 0.0),
                tp_buffer=mode_dict.get('tp_buffer', 0.90),
                sl_buffer=mode_dict.get('sl_buffer', 1.10),
                sr_window=mode_dict.get('sr_window', 10),
                min_sl=mode_dict.get('min_sl', 50),
                max_sl=mode_dict.get('max_sl', 200),
                weight=mode_dict.get('weight', 1.0),
            )

        self.config = BacktestConfig(
            name=config_dict.get('name', 'Untitled'),
            modes=modes,
            hour_min=config_dict.get('hour_min', 9.75),
            hour_max=config_dict.get('hour_max', 17.5),
            modo_busca=config_dict.get('modo_busca', False),
            risk_manager=config_dict.get('risk_manager', {}),
            ensemble_threshold=config_dict.get('ensemble_threshold', 0.5),
            ensemble_min_votes=config_dict.get('ensemble_min_votes', 1),
        )
        return self

    def load_config_dict(self, config_dict: dict) -> 'BacktestEngine':
        """Load configuration from dictionary."""
        modes = {}
        for mode_name, mode_dict in config_dict.get('modes', {}).items():
            modes[mode_name] = ModeConfig(
                enabled=mode_dict.get('enabled', True),
                priority=mode_dict.get('priority', 0),
                filters=mode_dict.get('filters', {}),
                behp=mode_dict.get('behp', {}),
                signal_field=mode_dict.get('signal_field', None),
                tp_mult=mode_dict.get('tp_mult', 1.0),
                sl_mult=mode_dict.get('sl_mult', 1.0),
                tp_sr_pct=mode_dict.get('tp_sr_pct', 0.0),
                sl_sr_pct=mode_dict.get('sl_sr_pct', 0.0),
                tp_buffer=mode_dict.get('tp_buffer', 0.90),
                sl_buffer=mode_dict.get('sl_buffer', 1.10),
                sr_window=mode_dict.get('sr_window', 10),
                min_sl=mode_dict.get('min_sl', 50),
                max_sl=mode_dict.get('max_sl', 200),
                weight=mode_dict.get('weight', 1.0),
            )

        self.config = BacktestConfig(
            name=config_dict.get('name', 'Untitled'),
            modes=modes,
            hour_min=config_dict.get('hour_min', 9.75),
            hour_max=config_dict.get('hour_max', 17.5),
            modo_busca=config_dict.get('modo_busca', False),
            risk_manager=config_dict.get('risk_manager', {}),
            ensemble_threshold=config_dict.get('ensemble_threshold', 0.5),
            ensemble_min_votes=config_dict.get('ensemble_min_votes', 1),
        )
        return self

    def load_ticks_for_simulation(self, ticks_input) -> 'BacktestEngine':
        """Load raw ticks for tick-level simulation.

        This is needed for _simulate_exit_v119 which operates on tick data.

        Args:
            ticks_input: Path to ticks parquet file OR a Polars DataFrame
        """
        t0 = time.time()
        if isinstance(ticks_input, str):
            self.ticks_raw = pl.read_parquet(ticks_input)
        else:
            self.ticks_raw = ticks_input

        # Build tick index as list of (start, end) tuples
        # The index should be aligned with self.df
        ticks_ts = self.ticks_raw['time_msc'].to_numpy()

        # Convert to seconds (ticks are in milliseconds)
        tick_sec = ticks_ts / 1000

        # Convert Polars datetime to seconds since epoch
        # Polars .dt.timestamp() returns microseconds by default, so divide by 1_000_000
        # NOTE: datetime in parquet is stored in UTC, matching tick timestamps
        bar_starts_sec = (self.df['dt'].dt.timestamp() // 1_000_000).to_numpy().astype(np.int64)
        bar_ends_sec = np.append(bar_starts_sec[1:], bar_starts_sec[-1] + 300)

        self.tick_idx = []
        for i in range(len(bar_starts_sec)):
            bs = bar_starts_sec[i]
            be = bar_ends_sec[i]
            s = int(np.searchsorted(tick_sec, bs, side='left'))
            e = int(np.searchsorted(tick_sec, be, side='left'))
            self.tick_idx.append((s, e))

        self.bid_arr = self.ticks_raw['bid'].to_numpy().astype(np.float32)
        self.ask_arr = self.ticks_raw['ask'].to_numpy().astype(np.float32)
        print(f"  Loaded ticks for simulation in {time.time()-t0:.2f}s")
        return self

    def _apply_filter(self, value, filter_spec) -> bool:
        """Apply a single filter specification to a value.

        Filter specs:
            {"min": N} - value >= N
            {"max": N} - value <= N
            {"eq": N}  - value == N
            {"neq": N} - value != N
            {"gt": N}  - value > N
            {"lt": N}  - value < N
            {"exclude": [N1, N2]} - value not in list
        """
        if filter_spec is None:
            return True

        if isinstance(filter_spec, (int, float)):
            return bool(value == filter_spec)

        if not isinstance(filter_spec, dict):
            return True

        if 'min' in filter_spec and value < filter_spec['min']:
            return False
        if 'max' in filter_spec and value > filter_spec['max']:
            return False
        if 'eq' in filter_spec and value != filter_spec['eq']:
            return False
        if 'neq' in filter_spec and value == filter_spec['neq']:
            return False
        if 'gt' in filter_spec and value <= filter_spec['gt']:
            return False
        if 'lt' in filter_spec and value >= filter_spec['lt']:
            return False
        if 'exclude' in filter_spec and value in filter_spec['exclude']:
            return False

        return True

    def _check_filters(self, row, mode_config: ModeConfig) -> bool:
        """Check if a row passes all filters for a mode.
        
        Supports dynamic filters:
            {"max_atr_mult": N} - max = ATR * N (overrides static max if smaller)
            {"min_atr_mult": N} - min = ATR * N (overrides static min if larger)
        """
        for filter_name, filter_spec in mode_config.filters.items():
            if filter_name == 'HOUR':
                value = row.get('hour')
            elif filter_name == 'MINUTE':
                value = row.get('minute')
            else:
                value = row.get(filter_name)

            if value is None:
                return False

            # Handle ATR-dependent dynamic filters
            if isinstance(filter_spec, dict):
                atr_val = float(row.get('ATR', 0) or 0)
                spec = dict(filter_spec)  # copy to avoid mutating original
                
                if 'max_atr_mult' in spec and atr_val > 0:
                    dynamic_max = atr_val * spec['max_atr_mult']
                    static_max = spec.get('max', float('inf'))
                    spec['max'] = min(dynamic_max, static_max)
                    del spec['max_atr_mult']
                
                if 'min_atr_mult' in spec and atr_val > 0:
                    dynamic_min = atr_val * spec['min_atr_mult']
                    static_min = spec.get('min', 0)
                    spec['min'] = max(dynamic_min, static_min)
                    del spec['min_atr_mult']
                
                if not self._apply_filter(value, spec):
                    return False
            else:
                if not self._apply_filter(value, filter_spec):
                    return False

        return True

    def _sniper_blocks_scalper(self, row) -> bool:
        """Check if SNIPER base conditions are met but guardrail fails.
        
        In OLD logic, when can_sniper=True but SNIPER guardrail fails,
        SCALPER is blocked (but HUNTER is still allowed).
        """
        adx_val = float(row.get('ADX7', 20) or 20)
        slope_val = float(row.get('EMA5_SLOPE', 0) or 0)
        abs_slope = abs(slope_val)
        gk_val = float(row.get('GK_RATIO', 1.0) or 1.0)
        
        can_sniper = adx_val >= 20 and abs_slope >= 25 and gk_val >= 1.0
        
        if not can_sniper:
            return False
        
        atr_val = float(row.get('ATR', 300) or 300)
        hour = row['hour']
        ribbon = int(row.get('RIBBON_STATE', 0) or 0)
        signal_dir = int(row.get('PA_SIGNAL_DIR', 0) or 0)
        
        sniper_guardrail = (
            atr_val >= 300 and atr_val <= 500 and
            gk_val >= 0.9 and gk_val <= 1.3 and
            hour not in [9, 15] and
            slope_val > 0 and
            ribbon == -1 and
            signal_dir != 0
        )
        
        return can_sniper and not sniper_guardrail



    def simulate(self, mode_filter: Optional[str] = None) -> list:
        """Run simulation for specified mode(s).

        Args:
            mode_filter: If specified, only simulate this mode.
                        If None, simulate all enabled modes.

        Returns:
            List of trade results
        """
        if self.config is None:
            raise ValueError("Config not loaded. Call load_config() first.")
        if self.df is None:
            raise ValueError("Indicators not loaded. Call load_indicators() first.")

        results = []
        df = self.df
        config = self.config
        N = len(df)
        cooldown_idx = 0
        last_trade_day = None
        consec_sl = 0  # Circuit Breaker count  # Index before which no new trades are allowed

        # Layer 4: Risk manager config
        risk_cfg = config.get_risk_manager()
        sl_limit = risk_cfg['consecutive_sl_limit']
        sl_cooldown = risk_cfg['consecutive_sl_cooldown']
        daily_stop_pts = risk_cfg['daily_stop']

        # Sort modes by priority (higher first)
        sorted_modes = sorted(
            [(name, cfg) for name, cfg in config.modes.items() if cfg.enabled],
            key=lambda x: x[1].priority,
            reverse=True
        )

        # Log guardrail status once at start
        if not config.modo_busca:
            print(f"  [GUARDRAILS ON] BE/HP/CD active | CB_limit={sl_limit} | DailyStop={daily_stop_pts} | EnsembleMinVotes={config.ensemble_min_votes}")
        else:
            print(f"  [MODO BUSCA] Guardrails DISABLED | EnsembleMinVotes={config.ensemble_min_votes}")

        # Warn if any mode has BE trigger > 500 (effectively disabled)
        for mode_name, mode_cfg in sorted_modes:
            be_trig = mode_cfg.behp.get('be_trigger', 200)
            if be_trig > 500:
                print(f"  ⚠️ WARNING: Mode '{mode_name}' has BE_trigger={be_trig} (>500). BE effectively disabled.")

        # Convert to dicts for _simulate_exit_v119 / _simulate_exit_ohlc
        records = df.to_dicts()

        i = 19  # will start at 20 after first increment
        while i < N - 1:
            i += 1
            # Get row as dict (matching old method style)
            if records:
                row = records[i]
            else:
                row = df.row(i, named=True)

            row_dt = row['dt']
            hora_c = row['hour'] + row['minute'] / 60

            # Time filter inline (same as old method)
            if hora_c < config.hour_min or hora_c >= config.hour_max:
                continue

            # V139: 12:00-14:00 lunch filter (require higher DIST_ABS) — desliga em modo_busca
            if not config.modo_busca and 12.0 <= hora_c < 14.0:
                dist_abs_val = abs(float(row.get('dist', 0) or 0))
                min_lunch_dist = 300
                if dist_abs_val < min_lunch_dist:
                    continue

            # Circuit Breaker + Daily Stop: desliga em modo_busca
            if not config.modo_busca:
                trade_day = row_dt.date() if hasattr(row_dt, 'date') else str(row_dt)[:10]
                if trade_day != last_trade_day:
                    last_trade_day = trade_day
                    consec_sl = 0
                    self.daily_pnl = 0
                    self.daily_stop_triggered = False
                if self.daily_stop_triggered:
                    continue
                if consec_sl >= sl_limit:
                    continue

            # ====== LAYER 2: ENSEMBLE VOTING ======
            sniper_blocks_scalper = self._sniper_blocks_scalper(row)
            voting_modes = []
            for mode_name, mode_cfg in sorted_modes:
                if mode_filter and mode_name != mode_filter:
                    continue
                if sniper_blocks_scalper and mode_name == 'SCALPER':
                    continue
                if self._check_filters(row, mode_cfg):
                    s_dir = int(row.get('PA_SIGNAL_DIR', 0) or 0)
                    if 'PA_SIGNAL_REV' in mode_cfg.filters:
                        s_dir = -s_dir
                    sf = getattr(mode_cfg, 'signal_field', None)
                    if sf:
                        s_dir = int(row.get(sf, 0) or 0)
                    if s_dir != 0:
                        voting_modes.append((mode_name, mode_cfg, s_dir))

            if not voting_modes:
                continue

            vote_sum = 0.0
            total_w = 0.0
            for _, mc, sd in voting_modes:
                w = getattr(mc, 'weight', 1.0)
                vote_sum += sd * w
                total_w += w

            vote_norm = vote_sum / total_w if total_w > 0 else 0.0
            threshold = getattr(config, 'ensemble_threshold', 0.5)
            min_votes = getattr(config, 'ensemble_min_votes', 1)

            # Layer 2: SELECTOR mode (threshold <= 0) vs CONSENSUS mode
            if threshold <= 0:
                # SELECTOR: any mode can trigger; pick highest weight when multiple
                if len(voting_modes) == 1:
                    mode_name, mode_cfg, signal_dir = voting_modes[0]
                else:
                    mode_name, mode_cfg, signal_dir = max(
                        voting_modes, key=lambda vm: getattr(vm[1], 'weight', 1.0)
                    )
            else:
                # CONSENSUS: check threshold and min_votes
                if abs(vote_norm) < threshold:
                    continue
                if len(voting_modes) < min_votes:
                    continue
                final_dir = 1 if vote_norm > 0 else -1
                mode_name, mode_cfg, _ = voting_modes[0]
                signal_dir = final_dir

            # V139: 9:00-9:30 only HUNTER allowed — desliga em modo_busca
            if not config.modo_busca and mode_name != 'HUNTER' and 9.0 <= hora_c < 9.5:
                continue

            # Cooldown check (skip trade if within cooldown period after a loss) — desliga em modo_busca
            if i < cooldown_idx:
                continue

            # Calculate TP and SL
            atr_val = float(row.get('ATR', 300) or 300)
            tp_mult = mode_cfg.tp_mult
            sl_mult = mode_cfg.sl_mult
            tp_sr_pct = mode_cfg.tp_sr_pct
            sl_sr_pct = mode_cfg.sl_sr_pct
            min_sl = mode_cfg.min_sl
            max_sl = mode_cfg.max_sl

            # ATR-based TP/SL
            tp_atr = int(round(atr_val * tp_mult))
            sl_atr = int(round(atr_val * sl_mult))

            # S/R-based TP/SL (if configured)
            if tp_sr_pct > 0 or sl_sr_pct > 0:
                # Calculate S/R distances using configured window (10, 30, 60)
                sr_window = mode_cfg.sr_window
                prev_high_col = f'prev_{sr_window}_high'
                prev_low_col = f'prev_{sr_window}_low'
                prev_high = float(row.get(prev_high_col, 0) or 0)
                prev_low = float(row.get(prev_low_col, 0) or 0)
                close_val = float(row.get('close', 0) or 0)
                
                if prev_high > 0 and prev_low > 0:
                    if signal_dir > 0:  # BUY
                        dist_resistance = max(0, prev_high - close_val)
                        dist_support = max(0, close_val - prev_low)
                    else:  # SELL
                        dist_resistance = max(0, close_val - prev_low)
                        dist_support = max(0, prev_high - close_val)
                else:
                    dist_resistance = float(row.get('dist_to_resistance', 2000))
                    dist_support = float(row.get('dist_to_support', 2000))
            
            if tp_sr_pct > 0:
                tp_sr = int(round(dist_resistance * mode_cfg.tp_buffer))
                tp = int(round(tp_atr * (1 - tp_sr_pct) + tp_sr * tp_sr_pct))
            else:
                tp = tp_atr

            if sl_sr_pct > 0:
                sl_sr = int(round(dist_support * mode_cfg.sl_buffer))
                sl = int(round(sl_atr * (1 - sl_sr_pct) + sl_sr * sl_sr_pct))
            else:
                sl = sl_atr

            # Apply SL bounds
            sl = max(min_sl, min(sl, max_sl))
            hard_stop = mode_cfg.behp.get('hard_stop', 999999)
            sl = min(sl, hard_stop)

            ep = float(row['open'])
            # Entry at NEXT candle's open (no look-ahead bias)
            if records and i + 1 < len(records):
                ep = float(records[i + 1]['open'])

            # signal_dir already set by ensemble voting

            # Get BE/HP params
            behp = mode_cfg.behp

            # If we have tick data, use tick-level simulation
            sim_idx = i + 1 if (i + 1 < N) else i  # entry at next candle
            entry_dt = records[sim_idx]['dt'] if records else row_dt
            entry_idx = sim_idx
            if self.tick_idx is not None and self.bid_arr is not None:
                pnl, hit_type, mfe, mae, exit_idx, candles_in_trade, be_triggered, tp30_triggered, slope_decay_triggered, progressed, trailing_triggered = _simulate_exit_v119(
                    records, self.bid_arr, self.ask_arr, self.tick_idx,
                    sim_idx, N,
                    'BUY' if signal_dir > 0 else 'SELL',
                    ep, tp, sl,
                    True, behp.get('be_offset', 50), mode_name, hard_stop, atr_val,
                    hp_candles=behp.get('hp_candles', 2),
                    hp_th=behp.get('hp_th', 0.15),
                    tp30_pct=behp.get('tp30_pct', 0.30),
                    grace_candles=behp.get('grace_candles', 2),
                    be_trigger_pts=behp.get('be_trigger', 200),
                    entry_slope=row.get('EMA20_SLOPE', 0),
                    slope_decay_pct=behp.get('slope_decay', 0.50),
                    trailing_pct=behp.get('trailing_pct', 0.0),
                    decay_factor=behp.get('decay_factor', 0.50),
                    min_tp_pct=behp.get('min_tp_pct', 0.20),
                    use_dynamic_decay=behp.get('use_dynamic_decay', False),
                )
            else:
                # Simplified simulation using OHLC when no tick data
                direction = 'BUY' if signal_dir > 0 else 'SELL'
                pnl, hit_type, mfe, mae, exit_idx = _simulate_exit_ohlc(
                    records, sim_idx, N, direction, ep, tp, sl,
                    behp.get('hp_candles', 2), behp.get('hp_th', 0.15),
                    behp.get('be_trigger', 200), behp.get('be_offset', 50),
                )
                candles_in_trade = exit_idx - sim_idx if exit_idx else 0
                be_triggered = False
                tp30_triggered = False
                slope_decay_triggered = False
                progressed = False
                trailing_triggered = False

            # V7.4.6: Exit datetime
            exit_dt = records[exit_idx]['dt'] if records and exit_idx < len(records) else entry_dt

            results.append({
                'mode': mode_name,
                'entry_dt': entry_dt,
                'exit_dt': exit_dt,
                'entry_idx': entry_idx,
                'exit_idx': exit_idx,
                'candles_held': candles_in_trade,
                'direction': 'BUY' if signal_dir > 0 else 'SELL',
                'signal_dir': signal_dir,
                'pnl': pnl,
                'hit_type': hit_type,
                'mfe': mfe,
                'mae': mae,
                'atr': atr_val,
                'tp': tp,
                'sl': sl,
                # Guardrail diagnostics (V7.4.6)
                'be_triggered': be_triggered,
                'tp30_triggered': tp30_triggered,
                'slope_decay_triggered': slope_decay_triggered,
                'progressed': progressed,
                'trailing_triggered': trailing_triggered,
                # Microestrutura (V139: Book Imbalance, Whale, Tape Reading)
                'book_imbalance': float(row.get('book_imbalance', 0) or 0),
                'buy_ratio': float(row.get('buy_ratio', 0.5) or 0.5),
                'whale_count': int(row.get('whale_count', 0) or 0),
                'tick_delta': int(row.get('tick_delta', 0) or 0),
                'tick_volume': int(row.get('tick_volume', 0) or 0),
                'trade_count': int(row.get('trade_count', 0) or 0),
                # Layer 2: Ensemble voting metadata
                'ensemble_votes': len(voting_modes),
                'vote_sum': round(vote_sum, 3),
                'vote_sum_raw': round(vote_sum, 3),  # raw weighted sum before normalization
                'voting_modes': ','.join([vm[0] for vm in voting_modes]),  # which modes fired
            })

            # Microestrutura logging: Book Imbalance soft preference + Tape Reading
            bi = float(row.get('book_imbalance', 0) or 0)
            br = float(row.get('buy_ratio', 0.5) or 0.5)
            wc = int(row.get('whale_count', 0) or 0)

            # Book Imbalance soft check
            if signal_dir > 0:  # BUY
                if br > 0.55:
                    book_status = 'FAVORABLE'
                elif br < 0.45:
                    book_status = 'UNFAVORABLE'
                else:
                    book_status = 'NEUTRAL'
            else:  # SELL
                if br < 0.45:
                    book_status = 'FAVORABLE'
                elif br > 0.55:
                    book_status = 'UNFAVORABLE'
                else:
                    book_status = 'NEUTRAL'

            # Tape reading: delta analysis
            td = int(row.get('tick_delta', 0) or 0)
            tv = int(row.get('tick_volume', 0) or 1)
            delta_pct = td / tv * 100 if tv > 0 else 0
            if abs(delta_pct) > 5:
                tape_desc = 'AGGRESSIVE'
            elif abs(delta_pct) > 2:
                tape_desc = 'MODERATE'
            else:
                tape_desc = 'ABSORPTION'

            # Whale detection
            whale_desc = f'WHALE({wc})' if wc > 50 else ''

            # Attach microestrutura metadata
            results[-1]['book_status'] = book_status
            results[-1]['tape_delta_pct'] = round(delta_pct, 2)

            # Layer 4: Track daily PnL
            self.daily_pnl += pnl
            if self.daily_pnl <= daily_stop_pts and not config.modo_busca:
                self.daily_stop_triggered = True

            # Cooldown after SL loss (matches MT5: cooldown = progress_gate * 300s)
            if hit_type == 'SL' and pnl < 0:
                cd_candles = behp.get('cooldown_candles', 0)
                if sl_cooldown > 0 and consec_sl >= sl_limit - 1:
                    cd_candles = max(cd_candles, sl_cooldown)
                if cd_candles > 0:
                    cooldown_idx = i + cd_candles
                consec_sl += 1
            else:
                consec_sl = 0  # reset on any non-SL exit

            # Block new positions until the current trade exits
            # Only skip the entry candle, not the entire trade duration
            # (MT5 allows new entries after position closes, which can be same candle)
            if i + 1 < exit_idx:
                i = min(exit_idx - 1, i + 1)  # skip at most 1 candle to avoid blocking too much

        return results

    def calculate_metrics(self, results: list) -> dict:
        """Calculate metrics from simulation results."""
        if not results:
            return {'n': 0, 'pnl': 0, 'exp': 0, 'wr': 0, 'profit_factor': 0,
                    'max_dd': 0, 'be_saved': 0, 'hstag_count': 0, 'wins': 0, 'losses': 0}

        pnls = [r['pnl'] for r in results]
        wins = [p for p in pnls if p > 0]
        losses = [abs(p) for p in pnls if p < 0]
        total_pnl = sum(pnls)
        n = len(results)
        pf = sum(wins) / sum(losses) if losses else 999

        # Calculate Max DD
        cumsum = 0
        max_dd = 0
        peak = 0
        for p in pnls:
            cumsum += p
            peak = max(peak, cumsum)
            dd = peak - cumsum
            max_dd = max(max_dd, dd)

        be_saved = sum(1 for r in results if r.get('be_triggered', False) and r.get('hit_type') == 'SL')
        hstag_count = sum(1 for r in results if r.get('hit_type') == 'HSTAG')

        return {
            'n': n,
            'pnl': int(total_pnl),
            'exp': round(total_pnl / n, 1) if n > 0 else 0,
            'wr': round(len(wins) / n * 100, 1) if n > 0 else 0,
            'profit_factor': round(pf, 2) if pf != 999 else 999,
            'max_dd': int(max_dd),
            'be_saved': be_saved,
            'hstag_count': hstag_count,
            'wins': len(wins),
            'losses': len(losses),
        }


def load_default_config() -> dict:
    """Load default V134 configuration matching original Cycle 5."""
    return {
        "name": "V134_SNIPER_FIRST",
        "hour_min": 9.75,
        "hour_max": 17.5,
        "modes": {
            "SNIPER": {
                "enabled": True,
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
            },
            "HUNTER": {
                "enabled": True,
                "priority": 2,
                "tp_mult": 2.0,
                "sl_mult": 1.0,
                "filters": {
                    "ADX7": {"min": 30},
                    "EMA5_SLOPE_ABS": {"min": 40},
                    "GK_RATIO": {"min": 1.4},
                    "ATR": {"min": 200, "max": 500},
                    "PA_SIGNAL_DIR": {"neq": 0}
                },
                "behp": {
                    "be_trigger": 100,
                    "be_offset": 15,
                    "hp_th": 40,
                    "hp_candles": 2,
                    "hard_stop": 50
                }
            },
            "SCALPER": {
                "enabled": True,
                "priority": 1,
                "tp_mult": 1.2,
                "sl_mult": 0.8,
                "filters": {
                    "ADX7": {"min": 25},
                    "EMA5_SLOPE_ABS": {"min": 15},
                    "HOUR": {"eq": 10},
                    "PA_SIGNAL_DIR": {"neq": 0}
                },
                "behp": {
                    "be_trigger": 350,
                    "be_offset": 10,
                    "hp_th": 40,
                    "hp_candles": 2,
                    "hard_stop": 80
                }
            }
        }
    }
