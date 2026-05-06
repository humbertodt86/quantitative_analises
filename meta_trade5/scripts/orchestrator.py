"""
Orquestrador V7.6 — Autopilot de Ciclos para WIN
=================================================
Executa ciclos automaticamente com Fase 1-5:
  F1: Go/No-Go (viability filter) — F1Hybrid V5 (~39K combos/s, exact)
  F2: DNA -> Acao (If/Then matrix)
  F3: Ranking de hipoteses
  F4: Ensemble (quando aplicavel)
  F5: Loop autopilot (gera proximo ciclo automaticamente)

Performance:
  - Dados carregados UMA vez no inicio
  - Engines criados UMA vez por periodo
  - F1 usa F1HybridEngine (OHLC, sem tick samples)
  - Medicoes de tempo e memoria em cada fase

Uso:
  python scripts/orchestrator.py --strategy=SIGNAL_DIR_SELL --col=PA_SIGNAL_DIR --signal=-1 --regime=trend --max-cycles=2
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import time
import json
import argparse
import traceback
from datetime import datetime
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import polars as pl
import numpy as np
from scipy import stats
from backtest.engine_v2 import BacktestEngine
from engines.f1_binario_v4_hybrid import F1HybridEngine
from engines.check_dist import calc_efficiency_ratio

# ===== PERF MONITORING =====
class PerfMonitor:
    def __init__(self):
        self.timings = {}
        self.start_time = time.time()
    
    def tick(self, label):
        now = time.time()
        elapsed = now - self.start_time
        self.timings[label] = elapsed
        print(f"  [PERF] {label}: {elapsed:.2f}s")
        return elapsed
    
    def report(self):
        print("\n" + "="*60)
        print("PERFORMANCE REPORT")
        print("="*60)
        prev = 0
        for label, t in self.timings.items():
            delta = t - prev
            print(f"  {label:<30} +{delta:>6.2f}s (total: {t:>7.2f}s)")
            prev = t
        print("="*60)

# ===== CONFIG =====
COST = 30
BASE = os.path.join(ROOT, 'data')
TICK_DIR = os.path.join(BASE, 'ticks')
SUPER = os.path.join(BASE, 'super_win_continuous.parquet')
OUT_DIR = os.path.join(ROOT, 'docs', 'WIN_docs')
FEV_CACHE = os.path.join(BASE, '_fev_cache_v2.npz')

# Periods
IS_S, IS_E = datetime(2026, 1, 2), datetime(2026, 3, 28)
OOS_S, OOS_E = datetime(2026, 3, 30), datetime(2026, 4, 29)
FEV_S, FEV_E = datetime(2026, 2, 1), datetime(2026, 3, 1)

# Go/No-Go thresholds
MIN_TRADES = 10
MAX_OVERFIT_RATIO = 10.0
MAX_DIRECTION_BIAS = 95.0
TARGET_PNL = 1000
MAX_CYCLES = 10

# Fixed guardrails for F2/F3 search
F2_BE = 200
F2_HP = 2
F2_CD = 1

# Guardrail sweep grid
BE_TRIGGERS = [100, 200, 300, 999999]
HP_CANDLES = [1, 2, 3]
COOLDOWN_CANDLES = [0, 1, 2]

# Conservative F1 grid (4,032 combos — sanity-first approach)
TP_GRID = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 15.0, 20.0]
SL_GRID = [0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0]
ATR_MIN_GRID = [50, 100, 150, 200, 300, 400]
ATR_MAX_GRID = [400, 600, 800, 1000, 1500, 2000, 9999]

# F1 sanity filters (prevent overfit at the screening level)
F1_SL_FLOOR_ATR = 0.5      # SL must be >= 0.5x ATR (prevents micro-stop overfit)
F1_RR_CAP = 10.0           # TP/SL ratio must be <= 10 (prevents precision overfit)

N_TOP_F2 = 30
N_TOP_F3 = 3

# ===== LOGGING =====
def log(msg, log_path=None):
    ts = datetime.now().strftime('%H:%M:%S')
    line = f"{ts} {msg}"
    print(line)
    if log_path:
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(line + '\n')

# ===== PHASE 0: LOAD DATA (ONCE) =====
_data_cache = {}

def load_data_once():
    """Load all data exactly once. Returns dict with all dataframes/arrays.
    
    Supports two modes:
    1. Unified: super_win_continuous.parquet (IS+OOS+Fev in one file)
    2. Split: super_win_IS.parquet + super_win_OOS.parquet + super_win_Fev.parquet
    """
    if 'loaded' in _data_cache:
        return _data_cache
    
    print("\n" + "="*60)
    print("PHASE 0: LOADING DATA (ONCE)")
    print("="*60)
    perf = PerfMonitor()
    
    # Detect split mode (IS/OOS/Fev as separate files)
    is_path = os.path.join(BASE, 'super_win_IS.parquet')
    oos_path = os.path.join(BASE, 'super_win_OOS.parquet')
    fev_path = os.path.join(BASE, 'super_win_Fev.parquet')
    split_mode = os.path.exists(is_path) and os.path.exists(oos_path)
    
    if split_mode:
        print("  [SPLIT MODE] Using separate IS/OOS/Fev parquets")
        df_is = pl.read_parquet(is_path)
        df_oos = pl.read_parquet(oos_path)
        df_fev = pl.read_parquet(fev_path) if os.path.exists(fev_path) else df_is.filter(
            (pl.col('dt') >= FEV_S) & (pl.col('dt') < FEV_E)
        )
        # Reconstruct df_full for regime recalculation support
        df_full = pl.concat([df_is, df_oos]).sort('dt')
        perf.tick('super_loaded')
    else:
        print("  [UNIFIED MODE] Using super_win_continuous.parquet")
        # Super parquet
        df_full = pl.read_parquet(SUPER)
        perf.tick('super_loaded')
        
        # Filter periods
        df_is = df_full.filter((pl.col('dt') >= IS_S) & (pl.col('dt') <= IS_E))
        df_oos = df_full.filter((pl.col('dt') >= OOS_S) & (pl.col('dt') <= OOS_E))
        df_fev = df_full.filter((pl.col('dt') >= FEV_S) & (pl.col('dt') < FEV_E))
    
    # Regime calculation (on full dataset for consistency)
    close_all = df_full['close'].to_numpy().astype(np.float64)
    adx_all = df_full['ADX7'].to_numpy().astype(np.float64)
    er_all = calc_efficiency_ratio(close_all, window=10)
    regime_all = np.where((er_all > 0.4) & (adx_all > 25) & (~np.isnan(er_all)), 1, 0).astype(np.int32)
    df_full = df_full.with_columns([
        pl.Series('efficiency_ratio', np.where(np.isnan(er_all), 0.0, er_all)),
        pl.Series('regime_label', regime_all),
    ])
    # Propagate regime to IS/OOS if split mode (they may not have it)
    if split_mode:
        # Re-read with regime
        df_is = pl.read_parquet(is_path)
        df_oos = pl.read_parquet(oos_path)
        df_fev = pl.read_parquet(fev_path) if os.path.exists(fev_path) else df_is.filter(
            (pl.col('dt') >= FEV_S) & (pl.col('dt') < FEV_E)
        )
    perf.tick('regime_calc')
    perf.tick('periods_filtered')
    
    # F1 data (cache for ep/atr/hour/entry_idx; OHLC from df_fev for new Hybrid)
    data = np.load(FEV_CACHE)
    ep_fev = data['ep']; atr_fev = data['atr']
    hour_fev = data['hour']; entry_idx_fev = data['entry_idx']
    regime_fev = df_fev['regime_label'].to_numpy().astype(np.int32)
    regime_at_entry = regime_fev[entry_idx_fev.astype(int)]
    close_arr_fev = df_fev['close'].to_numpy().astype(np.float32)
    ema5_slope_fev = df_fev['EMA5_SLOPE'].to_numpy().astype(np.float32)
    ema5_at_entry = ema5_slope_fev[entry_idx_fev.astype(int)]
    dist_fev = df_fev['dist'].to_numpy().astype(np.float32)
    dist_at_entry = np.abs(dist_fev[entry_idx_fev.astype(int)])
    # OHLC arrays for F1Hybrid (no tick samples needed)
    high_fev = df_fev['high'].to_numpy().astype(np.float64)
    low_fev = df_fev['low'].to_numpy().astype(np.float64)
    close_fev = df_fev['close'].to_numpy().astype(np.float64)
    perf.tick('f1_cache_loaded')
    
    # IS ticks (last prices)
    ticks_is = pl.read_parquet(os.path.join(BASE, 'WIN_merged_all.parquet'))
    ticks_is = ticks_is.with_columns([pl.col('last').alias('bid'), pl.col('last').alias('ask')])
    perf.tick('is_ticks_loaded')
    
    # OOS ticks (real bid/ask) - prefer unified file, fallback to directory
    oos_ticks_unified = os.path.join(BASE, 'WIN_ticks_OOS_all.parquet')
    if os.path.exists(oos_ticks_unified):
        print(f"  [OOS TICKS] Using unified file: WIN_ticks_OOS_all.parquet")
        ticks_oos = pl.read_parquet(oos_ticks_unified)
        ticks_oos = ticks_oos.with_columns([
            pl.col('bid').cast(pl.Float64), pl.col('ask').cast(pl.Float64), pl.col('last').cast(pl.Float64),
        ])
    else:
        print(f"  [OOS TICKS] Scanning directory: {TICK_DIR}")
        all_files = [os.path.join(TICK_DIR, f) for f in os.listdir(TICK_DIR)
                     if f.startswith('WIN') and f.endswith('.parquet')]
        all_files.sort()
        oos_parts = []
        for p in all_files:
            part = pl.read_parquet(p)
            part = part.with_columns([
                pl.col('bid').cast(pl.Float64), pl.col('ask').cast(pl.Float64), pl.col('last').cast(pl.Float64),
            ])
            oos_parts.append(part)
        ticks_oos = pl.concat(oos_parts).sort('time_msc')
    ticks_oos = ticks_oos.filter((pl.col('bid') > 0) & (pl.col('ask') > 0) & (pl.col('bid') < pl.col('ask')))
    perf.tick('oos_ticks_loaded')
    
    # Create engines (ONCE)
    engines = {}
    for name, df, ticks in [('f2', df_is, ticks_is), ('f3_search', df_is, ticks_is),
                             ('gr', df_is, ticks_is), ('f3_oos', df_oos, ticks_oos)]:
        eng = BacktestEngine(None)
        eng.df = df
        eng.load_ticks_for_simulation(ticks)
        engines[name] = eng
    perf.tick('engines_created')
    
    _data_cache.update({
        'loaded': True,
        'df_full': df_full, 'df_is': df_is, 'df_oos': df_oos, 'df_fev': df_fev,
        'ep_fev': ep_fev, 'atr_fev': atr_fev,
        'hour_fev': hour_fev, 'entry_idx_fev': entry_idx_fev,
        'regime_at_entry': regime_at_entry, 'close_arr_fev': close_arr_fev,
        'ema5_at_entry': ema5_at_entry, 'dist_at_entry': dist_at_entry,
        'high_fev': high_fev, 'low_fev': low_fev, 'close_fev': close_fev,
        'N_fe': len(df_fev),
        'engines': engines,
    })
    
    perf.report()
    print(f"Data loaded. Trend={regime_all.sum()/len(regime_all)*100:.1f}%")
    return _data_cache

# ===== PHASE 1: RUN CYCLE =====
def run_cycle(data, strategy_config, cycle_num, log_path, phases_to_run=None, prev_f1_top=None):
    """Execute cycle with optional phase skipping.
    
    phases_to_run: list of phases to execute (default: all)
        Example: ['F2', 'F3', 'GUARDRAIL', 'OOS'] — skips F1 for temporal filters
        Example: ['GUARDRAIL', 'OOS'] — sub-cycle for guardrail tuning
    prev_f1_top: f1_top from previous cycle (used when F1 is skipped)
    """
    if phases_to_run is None:
        phases_to_run = ['F1', 'F2', 'F3', 'GUARDRAIL', 'OOS']
    
    perf = PerfMonitor()
    
    sname = strategy_config['name']
    col = strategy_config['col']
    signal_dir = strategy_config['signal']
    regime = strategy_config['regime']
    regime_filter = {'eq': 1} if regime == 'trend' else {'eq': 0}
    current_config = strategy_config  # alias for apply_temporal_filters
    
    # Extract optional patches from previous cycles
    regime_er_threshold = strategy_config.get('regime_er_threshold', 0.4)
    regime_adx_threshold = strategy_config.get('regime_adx_threshold', 25)
    allowed_hours = strategy_config.get('allowed_hours', None)
    be_multiplier = strategy_config.get('be_multiplier', 1.0)
    
    log(f"\n{'='*60}", log_path)
    log(f"CYCLE {cycle_num}: {sname}", log_path)
    log(f"Config: signal={signal_dir}, regime={regime}", log_path)
    log(f"Patches: ER>{regime_er_threshold}, ADX>{regime_adx_threshold}, hours={allowed_hours}, BE_mult={be_multiplier}", log_path)
    log(f"{'='*60}", log_path)
    
    # Recalculate regime if thresholds changed
    if regime_er_threshold != 0.4 or regime_adx_threshold != 25:
        close_all = data['df_full']['close'].to_numpy().astype(np.float64)
        adx_all = data['df_full']['ADX7'].to_numpy().astype(np.float64)
        er_all = calc_efficiency_ratio(close_all, window=10)
        regime_all = np.where((er_all > regime_er_threshold) & (adx_all > regime_adx_threshold) & (~np.isnan(er_all)), 1, 0).astype(np.int32)
        # Update df_oos regime
        df_oos = data['df_oos'].with_columns([pl.Series('regime_label', regime_all[(data['df_full']['dt'] >= OOS_S) & (data['df_full']['dt'] <= OOS_E)])])
        data['df_oos'] = df_oos
    
    # --- F1: Filter by signal ---
    f1_results = []
    f1_top = []
    
    if 'F1' in phases_to_run:
        use_mask = (data['regime_at_entry'] == 1) if regime == 'trend' else (data['regime_at_entry'] == 0)
        sig_vals = data['df_fev'][col].to_numpy().astype(np.int32)
        sig_at_entry = sig_vals[data['entry_idx_fev'].astype(int)]
        final_mask = use_mask & (sig_at_entry == signal_dir)
        
        f1_idx = np.where(final_mask)[0]
        n_f1 = len(f1_idx)
        log(f"  F1 entries: {n_f1}", log_path)
        
        if n_f1 < 5:
            log(f"  ABORT: too few entries ({n_f1})", log_path)
            return {'status': 'abort', 'reason': f'entries={n_f1}'}
        
        sub_ep = data['ep_fev'][f1_idx]
        sub_atr = data['atr_fev'][f1_idx]
        sub_sell_idx = data['entry_idx_fev'][f1_idx].astype(int)
        # --- F1: Grid Search (F1Hybrid V5) ---
        n_combos_raw = len(TP_GRID) * len(SL_GRID) * len(ATR_MIN_GRID) * len(ATR_MAX_GRID)
        n_combos_f1 = len(TP_GRID) * len(SL_GRID)
        log(f"  F1: {n_combos_f1} TPxSL combos → {n_combos_raw} raw with ATR, filters: SL_floor>={F1_SL_FLOOR_ATR}x, RR<={F1_RR_CAP} (Hybrid V5, exact)...", log_path)
        f1_results = []
        tp_grid_arr = np.array(TP_GRID, dtype=np.float64)
        sl_grid_arr = np.array(SL_GRID, dtype=np.float64)
        engine = F1HybridEngine(
            data['high_fev'], data['low_fev'], data['close_fev'],
            sub_ep, sub_atr, sub_sell_idx,
            direction=signal_dir, n_threads=8
        )
        net_grid, n_grid = engine.evaluate_batch(tp_grid_arr, sl_grid_arr, blocking_mode='exact')
        engine.shutdown()
        # Expand with ATR_MIN/ATR_MAX + sanity filters
        for ti, tp in enumerate(TP_GRID):
            for si, sl in enumerate(SL_GRID):
                # Filter 1: R:R cap <= 10 (prevents precision overfit)
                if tp / sl > F1_RR_CAP:
                    continue
                # Filter 2: SL floor >= 0.5x ATR (prevents micro-stop overfit)
                if sl < F1_SL_FLOOR_ATR:
                    continue
                net = int(net_grid[ti, si])
                n = int(n_grid[ti, si])
                if n >= 3:
                    for atr_mn in ATR_MIN_GRID:
                        for atr_mx in ATR_MAX_GRID:
                            f1_results.append({'tp': tp, 'sl': sl,
                                               'atr_min': int(atr_mn), 'atr_max': int(atr_mx),
                                               'f1_net': net, 'f1_n': n})
        f1_results.sort(key=lambda x: x['f1_net'], reverse=True)
        f1_top = f1_results[:N_TOP_F2]
        log(f"  F1: {len(f1_results)} valid, top={f1_top[0]['f1_net']:+d}", log_path)
        perf.tick('f1_done')
    else:
        log("  [SKIP] F1 — using previous F1 results", log_path)
        # Reuse previous F1 results if available, or extract from config
        if prev_f1_top:
            f1_top = prev_f1_top
        else:
            # Extract from strategy_config if available
            cfg = strategy_config.get('config', {})
            f1_top = [{
                'tp': cfg.get('tp', 3.0),
                'sl': cfg.get('sl', 1.0),
                'atr_min': cfg.get('atr_min', 100),
                'atr_max': cfg.get('atr_max', 9999),
                'f1_net': 0, 'f1_n': 0
            }]
        perf.tick('f1_done')
    
    # Helper to apply temporal filters
    def apply_temporal_filters(cfg, config):
        if config.get('allowed_hours'):
            cfg['modes']['M']['filters']['hour'] = {'in': config['allowed_hours']}
        if config.get('exclude_hours'):
            cfg['modes']['M']['filters']['hour'] = {'exclude': config['exclude_hours']}
        if config.get('exclude_dow'):
            cfg['modes']['M']['filters']['day_of_week'] = {'exclude': config['exclude_dow']}
        return cfg
    
    # --- F2: IS validation ---
    f2_results = []
    if 'F2' in phases_to_run:
        eng_f2 = data['engines']['f2']
        for r in f1_top:
            behp = {
                'be_trigger': int(F2_BE * be_multiplier), 'be_offset': 25,
                'hp_candles': F2_HP, 'hp_th': 0.15,
                'tp30_pct': 0.30, 'grace_candles': 2,
                'hard_stop': 500, 'cooldown_candles': F2_CD, 'slope_decay': 0.50
            }
            cfg = {
                'name': 'F2', 'hour_min': 0.0, 'hour_max': 24.0, 'modo_busca': False,
                'modes': {
                    'M': {
                        'enabled': True, 'priority': 1, 'signal_field': col,
                        'tp_mult': r['tp'], 'sl_mult': r['sl'],
                        'min_sl': 50, 'max_sl': min(500, r['atr_max']),
                        'filters': {
                            'ATR': {'min': r['atr_min'], 'max': r['atr_max']},
                            col: {'eq': signal_dir},
                            'regime_label': regime_filter,
                        },
                        'behp': behp
                    }
                }
            }
            cfg = apply_temporal_filters(cfg, current_config)
            
            try:
                eng_f2.load_config_dict(cfg)
                res = eng_f2.simulate()
                m = eng_f2.calculate_metrics(res)
                r['f2_net'] = int(m['pnl'] - len(res) * COST)
                r['f2_n'] = len(res)
                r['f2_wr'] = m['wr']
                r['f2_pf'] = m['profit_factor']
            except Exception as e:
                r['f2_net'] = 0; r['f2_n'] = 0; r['f2_wr'] = 0.0; r['f2_pf'] = 0.0
            f2_results.append(r)
        
        f2_results.sort(key=lambda x: x['f2_net'], reverse=True)
        log(f"  F2 top: net={f2_results[0]['f2_net']:+d} ({f2_results[0]['f2_n']}t, WR={f2_results[0]['f2_wr']:.1f}%)", log_path)
        perf.tick('f2_done')
    else:
        log("  [SKIP] F2 — using previous F2 results", log_path)
        f2_results = f1_top  # pass through
        perf.tick('f2_done')
    
    # --- F3 search: IS ---
    f3_results = []
    if 'F3' in phases_to_run:
        eng_f3_search = data['engines']['f3_search']
        for r in f2_results[:N_TOP_F3]:
            behp = {
                'be_trigger': int(F2_BE * be_multiplier), 'be_offset': 25,
                'hp_candles': F2_HP, 'hp_th': 0.15,
                'tp30_pct': 0.30, 'grace_candles': 2,
                'hard_stop': 500, 'cooldown_candles': F2_CD, 'slope_decay': 0.50
            }
            cfg = {
                'name': 'F3_search', 'hour_min': 0.0, 'hour_max': 24.0, 'modo_busca': False,
                'modes': {
                    'M': {
                        'enabled': True, 'priority': 1, 'signal_field': col,
                        'tp_mult': r['tp'], 'sl_mult': r['sl'],
                        'min_sl': 50, 'max_sl': min(500, r['atr_max']),
                        'filters': {
                            'ATR': {'min': r['atr_min'], 'max': r['atr_max']},
                            col: {'eq': signal_dir},
                            'regime_label': regime_filter,
                        },
                        'behp': behp
                    }
                }
            }
            cfg = apply_temporal_filters(cfg, current_config)
            
            try:
                eng_f3_search.load_config_dict(cfg)
                res = eng_f3_search.simulate()
                m = eng_f3_search.calculate_metrics(res)
                r['f3_net'] = int(m['pnl'] - len(res) * COST)
                r['f3_n'] = len(res)
                r['f3_wr'] = m['wr']
                r['f3_pf'] = m['profit_factor']
            except Exception:
                r['f3_net'] = 0; r['f3_n'] = 0; r['f3_wr'] = 0.0; r['f3_pf'] = 0.0
            f3_results.append(r)
        
        f3_results.sort(key=lambda x: x['f3_net'], reverse=True)
        best = f3_results[0]
        log(f"  F3 IS: top={best['f3_net']:+d} ({best['f3_n']}t)", log_path)
        perf.tick('f3_done')
    else:
        log("  [SKIP] F3 — using previous F3 results", log_path)
        f3_results = f2_results[:N_TOP_F3] if f2_results else f1_top[:N_TOP_F3]
        best = f3_results[0] if f3_results else f1_top[0]
        perf.tick('f3_done')
    
    # --- Guardrail sweep ---
    gr_results = []
    if 'GUARDRAIL' in phases_to_run:
        eng_gr = data['engines']['gr']
        for be_trig in BE_TRIGGERS:
            for hp_c in HP_CANDLES:
                for cd_c in COOLDOWN_CANDLES:
                    behp_gr = {
                        'be_trigger': int(be_trig * be_multiplier), 'be_offset': 25,
                        'hp_candles': hp_c, 'hp_th': 0.15,
                        'tp30_pct': 0.30, 'grace_candles': 2,
                        'hard_stop': min(500, best['atr_max']),
                        'cooldown_candles': cd_c, 'slope_decay': 0.50
                    }
                    cfg_gr = {
                        'name': f'C{cycle_num}', 'hour_min': 0.0, 'hour_max': 24.0, 'modo_busca': False,
                        'modes': {
                            'M': {
                                'enabled': True, 'priority': 1, 'signal_field': col,
                                'tp_mult': best['tp'], 'sl_mult': best['sl'],
                                'min_sl': 50, 'max_sl': min(500, best['atr_max']),
                                'filters': {
                                    'ATR': {'min': best['atr_min'], 'max': best['atr_max']},
                                    col: {'eq': signal_dir},
                                    'regime_label': regime_filter,
                                },
                                'behp': behp_gr
                            }
                        }
                    }
                    cfg_gr = apply_temporal_filters(cfg_gr, current_config)
                    
                    try:
                        eng_gr.load_config_dict(cfg_gr)
                        res_gr = eng_gr.simulate()
                        m_gr = eng_gr.calculate_metrics(res_gr)
                        net_gr = int(m_gr['pnl'] - len(res_gr) * COST)
                        gr_results.append({
                            'be_trigger': be_trig, 'hp_candles': hp_c, 'cooldown_candles': cd_c,
                            'net': net_gr, 'n': len(res_gr), 'wr': m_gr['wr'], 'pf': m_gr['profit_factor'],
                        })
                    except Exception:
                        gr_results.append({
                            'be_trigger': be_trig, 'hp_candles': hp_c, 'cooldown_candles': cd_c,
                            'net': 0, 'n': 0, 'wr': 0.0, 'pf': 0.0,
                        })
        
        gr_results.sort(key=lambda x: -x['net'])
        best_gr = gr_results[0]
        log(f"  Guardrail best: BE={best_gr['be_trigger']} HP={best_gr['hp_candles']} CD={best_gr['cooldown_candles']} net={best_gr['net']:+d}", log_path)
        perf.tick('guardrail_done')
    else:
        log("  [SKIP] Guardrail — using previous guardrail config", log_path)
        best_gr = {'be_trigger': F2_BE, 'hp_candles': F2_HP, 'cooldown_candles': F2_CD, 'net': 0, 'n': 0, 'wr': 0.0, 'pf': 0.0}
        perf.tick('guardrail_done')
    
    # --- F3 OOS ---
    net_oos = 0; n_oos = 0; wr_oos = 0.0; pf_oos = 0.0; res_oos = []
    if 'OOS' in phases_to_run:
        eng_f3_oos = data['engines']['f3_oos']
        behp_oos = {
            'be_trigger': int(best_gr['be_trigger'] * be_multiplier), 'be_offset': 25,
            'hp_candles': best_gr['hp_candles'], 'hp_th': 0.15,
            'tp30_pct': 0.30, 'grace_candles': 2,
            'hard_stop': min(500, best['atr_max']),
            'cooldown_candles': best_gr['cooldown_candles'], 'slope_decay': 0.50
        }
        cfg_oos = {
            'name': f'C{cycle_num}_{sname}', 'hour_min': 0.0, 'hour_max': 24.0, 'modo_busca': False,
            'modes': {
                'M': {
                    'enabled': True, 'priority': 1, 'signal_field': col,
                    'tp_mult': best['tp'], 'sl_mult': best['sl'],
                    'min_sl': 50, 'max_sl': min(500, best['atr_max']),
                    'filters': {
                        'ATR': {'min': best['atr_min'], 'max': best['atr_max']},
                        col: {'eq': signal_dir},
                        'regime_label': regime_filter,
                    },
                    'behp': behp_oos
                }
            }
        }
        cfg_oos = apply_temporal_filters(cfg_oos, current_config)
        
        try:
            eng_f3_oos.load_config_dict(cfg_oos)
            res_oos = eng_f3_oos.simulate()
            m_oos = eng_f3_oos.calculate_metrics(res_oos)
            net_oos = int(m_oos['pnl'] - len(res_oos) * COST)
            n_oos = len(res_oos)
            wr_oos = m_oos['wr']
            pf_oos = m_oos['profit_factor']
            
            if res_oos:
                for t in res_oos:
                    t['cycle'] = cycle_num
                    t['strategy'] = sname
                trades_df = pl.DataFrame(res_oos)
                trades_path = os.path.join(OUT_DIR, f'trades_ciclo{cycle_num}_{sname}.parquet')
                trades_df.write_parquet(trades_path)
                
            log(f"  OOS: net={net_oos:+d} ({n_oos}t, WR={wr_oos:.1f}%, PF={pf_oos:.2f})", log_path)
        except Exception as e:
            log(f"  OOS ERROR: {e}", log_path)
            net_oos = 0; n_oos = 0; wr_oos = 0.0; pf_oos = 0.0
            res_oos = []
        
        perf.tick('oos_done')
    else:
        log("  [SKIP] OOS — no production run", log_path)
        perf.tick('oos_done')
    
    result = {
        'status': 'completed',
        'cycle': cycle_num,
        'strategy': sname,
        'f1_top_net': f1_top[0]['f1_net'] if f1_top else 0,
        'f2_top_net': f2_results[0]['f2_net'],
        'f2_top_n': f2_results[0]['f2_n'],
        'f3_top_net': best['f3_net'],
        'f3_top_n': best['f3_n'],
        'gr_be': best_gr['be_trigger'],
        'gr_hp': best_gr['hp_candles'],
        'gr_cd': best_gr['cooldown_candles'],
        'oos_net': net_oos,
        'oos_n': n_oos,
        'oos_wr': wr_oos,
        'oos_pf': pf_oos,
        'trades': res_oos,
        'config': {
            'tp': best['tp'], 'sl': best['sl'],
            'atr_min': best['atr_min'], 'atr_max': best['atr_max'],
            'be_trigger': best_gr['be_trigger'],
            'hp_candles': best_gr['hp_candles'],
            'cooldown_candles': best_gr['cooldown_candles'],
        },
        'timings': perf.timings,
    }
    
    perf.report()
    return result

# ===== PHASE 1: GO/NO-GO =====
def phase1_go_no_go(result, is_net):
    """Apply Go/No-Go filters."""
    oos_n = result['oos_n']
    oos_net = result['oos_net']
    
    # Gatilho 1: Trade count
    if oos_n < MIN_TRADES:
        return {'status': 'ABORT', 'reason': f'trades={oos_n}<{MIN_TRADES}'}
    
    # Gatilho 2: Overfit (only when IS positive and OOS much smaller, or IS positive and OOS negative)
    if is_net > 0 and oos_net > 0:
        overfit = is_net / max(oos_net, 1)
        if overfit > MAX_OVERFIT_RATIO:
            return {'status': 'ABORT', 'reason': f'overfit={overfit:.1f}x>{MAX_OVERFIT_RATIO}x'}
    elif is_net > 0 and oos_net <= 0:
        overfit = abs(is_net) / max(abs(oos_net), 1)
        if overfit > MAX_OVERFIT_RATIO:
            return {'status': 'ABORT', 'reason': f'overfit={overfit:.1f}x>{MAX_OVERFIT_RATIO}x (IS>0, OOS<=0)'}
    else:
        # Both negative or IS <= 0: not overfit, just bad signal
        overfit = 0.0
    
    # Gatilho 3: Direction bias (only for ensemble)
    # For single strategies, we don't check direction bias
    
    return {'status': 'PASS', 'overfit': overfit}

# ===== PHASE 2: DNA ANALYSIS =====
def phase2_dna(result, data):
    """Analyze DNA of OOS trades and return metrics."""
    trades = result['trades']
    if not trades:
        return {}
    
    # Merge with OOS indicators
    trades_df = pl.DataFrame(trades)
    trades_df = trades_df.with_columns([pl.col('entry_dt').cast(pl.Datetime('ns')).alias('dt')])
    df_oos_ns = data['df_oos'].with_columns([pl.col('dt').cast(pl.Datetime('ns'))])
    merged = trades_df.join(df_oos_ns, on='dt', how='left')
    merged = merged.with_columns([
        pl.col('entry_dt').dt.weekday().alias('dow'),
        pl.col('entry_dt').dt.hour().alias('hour'),
        (pl.col('pnl') > 0).alias('win'),
    ])
    
    dna = {}
    
    # Regime-specific
    for r_val, r_name in [(1, 'trend'), (0, 'range')]:
        subset = merged.filter(pl.col('regime_label') == r_val)
        if len(subset) > 0:
            dna[f'pnl_{r_name}'] = int(subset['pnl'].sum())
            dna[f'wr_{r_name}'] = subset['win'].sum() / len(subset) * 100
            dna[f'n_{r_name}'] = len(subset)
        else:
            dna[f'pnl_{r_name}'] = 0
            dna[f'wr_{r_name}'] = 0.0
            dna[f'n_{r_name}'] = 0
    
    # Hourly analysis
    hourly = {}
    for h in range(9, 19):
        subset = merged.filter(pl.col('hour') == h)
        if len(subset) > 0:
            hourly[h] = {
                'n': len(subset),
                'wr': subset['win'].sum() / len(subset) * 100,
                'net': int(subset['pnl'].sum()),
            }
    dna['hourly'] = hourly
    
    # Day of week
    dow_stats = {}
    for d in range(1, 6):
        subset = merged.filter(pl.col('dow') == d)
        if len(subset) > 0:
            dow_stats[d] = {
                'n': len(subset),
                'wr': subset['win'].sum() / len(subset) * 100,
                'net': int(subset['pnl'].sum()),
            }
    dna['dow'] = dow_stats
    
    # Skew and serial correlation
    pnls = merged['pnl'].to_numpy()
    dna['skew'] = float(stats.skew(pnls)) if len(pnls) > 2 else 0.0
    dna['serial_corr'] = float(np.corrcoef(pnls[:-1], pnls[1:])[0, 1]) if len(pnls) > 1 and np.std(pnls[:-1]) > 0 else 0.0
    
    # BE hit count
    hit_types = merged['hit_type'].to_list()
    dna['be_hit_count'] = hit_types.count('BE')
    dna['tp_count'] = hit_types.count('TP')
    dna['sl_count'] = hit_types.count('SL')
    dna['hp_count'] = hit_types.count('HP')
    
    # Avg MFE
    mfe_vals = merged['mfe'].to_numpy()
    dna['avg_mfe'] = float(np.mean(mfe_vals)) if len(mfe_vals) > 0 else 0.0
    
    # Cohen's d for key indicators
    wins_df = merged.filter(pl.col('win') == True)
    losses_df = merged.filter(pl.col('win') == False)
    
    def cohen_d(x, y):
        nx, ny = len(x), len(y)
        if nx < 2 or ny < 2:
            return 0.0
        pooled_std = np.sqrt(((nx-1)*np.var(x, ddof=1) + (ny-1)*np.var(y, ddof=1)) / (nx+ny-2))
        if pooled_std == 0:
            return 0.0
        return (np.mean(x) - np.mean(y)) / pooled_std
    
    indicators = ['EMA5_SLOPE', 'dist', 'ATR', 'ADX7', 'RSI14']
    cohen_results = {}
    for ind in indicators:
        if ind in merged.columns:
            tp_vals = wins_df[ind].drop_nulls().to_numpy()
            sl_vals = losses_df[ind].drop_nulls().to_numpy()
            cohen_results[ind] = cohen_d(tp_vals, sl_vals)
    dna['cohen_d'] = cohen_results
    
    return dna

# ===== PHASE CONTROLLER: Map hypothesis type to required phases =====
HYPOTHESIS_PHASE_MAP = {
    # Type A: Parameter changes — requires full cycle including F1
    'tighten_regime':     ['F1', 'F2', 'F3', 'GUARDRAIL', 'OOS'],
    'tp_change':          ['F1', 'F2', 'F3', 'GUARDRAIL', 'OOS'],
    'sl_change':          ['F1', 'F2', 'F3', 'GUARDRAIL', 'OOS'],
    'atr_change':         ['F1', 'F2', 'F3', 'GUARDRAIL', 'OOS'],
    # Type B: Temporal/heuristic filters — skip F1 (F1 doesn't use these)
    'exclude_hour':       ['F2', 'F3', 'GUARDRAIL', 'OOS'],
    'exclude_dow':        ['F2', 'F3', 'GUARDRAIL', 'OOS'],
    'focus_hours':        ['F2', 'F3', 'GUARDRAIL', 'OOS'],
    'ema5_filter':        ['F2', 'F3', 'GUARDRAIL', 'OOS'],
    # Type C: Guardrail tuning — sub-cycle, skip F1/F2/F3
    'reduce_be':          ['GUARDRAIL', 'OOS'],
    'increase_be':        ['GUARDRAIL', 'OOS'],
    'hp_change':          ['GUARDRAIL', 'OOS'],
    'cd_change':          ['GUARDRAIL', 'OOS'],
    # Type D: Ensemble — separate phase (not a cycle)
    'ensemble_assembly':  ['ENSEMBLE'],
    'min_votes_change':   ['ENSEMBLE'],
}

# ===== PHASE 3: RANK HYPOTHESES =====
def phase3_rank_hypotheses(dna, result):
    """Rank hypotheses by effect size and priority.
    
    Each hypothesis includes 'phases_needed' so the orchestrator knows
    which pipeline stages to run (e.g., skip F1 for temporal filters).
    """
    hypotheses = []
    
    # P1: Limpeza - exclude bad hours
    if 'hourly' in dna:
        for h, stats in dna['hourly'].items():
            if stats['wr'] < 30 and stats['n'] > 5:
                hypotheses.append({
                    'priority': 1,
                    'type': 'exclude_hour',
                    'target': h,
                    'effect_size': stats['n'],
                    'description': f'Excluir hora {h}: WR={stats["wr"]:.1f}% ({stats["n"]}t)',
                    'patch': {'exclude_hours': [h]},
                    'phases_needed': ['F2', 'F3', 'GUARDRAIL', 'OOS'],
                })
    
    # P1: Exclude bad days
    if 'dow' in dna:
        for d, stats in dna['dow'].items():
            if stats['wr'] < 30 and stats['n'] > 5:
                hypotheses.append({
                    'priority': 1,
                    'type': 'exclude_dow',
                    'target': d,
                    'effect_size': stats['n'],
                    'description': f'Excluir dow {d}: WR={stats["wr"]:.1f}% ({stats["n"]}t)',
                    'patch': {'exclude_dow': [d]},
                    'phases_needed': ['F2', 'F3', 'GUARDRAIL', 'OOS'],
                })
    
    # P2: Foco - tighten regime
    pnl_range = dna.get('pnl_range', 0)
    pnl_trend = dna.get('pnl_trend', 0)
    if pnl_range < -500 and pnl_trend > 0:
        hypotheses.append({
            'priority': 2,
            'type': 'tighten_regime',
            'target': 'regime_filter',
            'effect_size': abs(pnl_range),
            'description': f'Apertar regime: range={pnl_range:+d}, trend={pnl_trend:+d}',
            'patch': {'regime_er_threshold': 0.5, 'regime_adx_threshold': 30},
            'phases_needed': ['F1', 'F2', 'F3', 'GUARDRAIL', 'OOS'],
        })
    
    # P2: Focus on good hours
    if 'hourly' in dna:
        good_hours = [h for h, s in dna['hourly'].items() if s['wr'] > 55 and s['n'] > 3]
        if good_hours and result['oos_wr'] < 45:
            hypotheses.append({
                'priority': 2,
                'type': 'focus_hours',
                'target': good_hours,
                'effect_size': max(dna['hourly'][h]['n'] for h in good_hours),
                'description': f'Focar horas {good_hours}: WR>55%',
                'patch': {'allowed_hours': good_hours},
                'phases_needed': ['F2', 'F3', 'GUARDRAIL', 'OOS'],
            })
    
    # P3: Extração - reduce BE
    if dna.get('skew', 0) > 2.0 and dna.get('be_hit_count', 0) == 0 and dna.get('avg_mfe', 0) > 100:
        hypotheses.append({
            'priority': 3,
            'type': 'reduce_be',
            'target': 'be_trigger',
            'effect_size': dna['skew'],
            'description': f'Reduzir BE: skew={dna["skew"]:.2f}, avg_mfe={dna["avg_mfe"]:.0f}',
            'patch': {'be_multiplier': 0.75},
            'phases_needed': ['GUARDRAIL', 'OOS'],
        })
    
    # P3: EMA5_SLOPE filter
    ema5_d = dna.get('cohen_d', {}).get('EMA5_SLOPE', 0)
    if abs(ema5_d) > 0.5:
        hypotheses.append({
            'priority': 3,
            'type': 'ema5_filter',
            'target': 'EMA5_SLOPE',
            'effect_size': abs(ema5_d),
            'description': f'Filtrar EMA5_SLOPE: d={ema5_d:+.2f}',
            'patch': {'ema5_threshold': 50 if ema5_d > 0 else -50},
            'phases_needed': ['F2', 'F3', 'GUARDRAIL', 'OOS'],
        })
    
    # Sort by priority, then effect_size desc
    hypotheses.sort(key=lambda h: (h['priority'], -h['effect_size']))
    return hypotheses

# ===== PHASE 5: APPLY HYPOTHESIS =====
def phase5_apply_hypothesis(strategy_config, hypothesis):
    """Apply hypothesis patch to strategy config."""
    new_config = dict(strategy_config)
    patch = hypothesis['patch']
    
    if 'exclude_hours' in patch:
        current = set(new_config.get('exclude_hours', []))
        current.update(patch['exclude_hours'])
        new_config['exclude_hours'] = sorted(list(current))
    
    if 'exclude_dow' in patch:
        current = set(new_config.get('exclude_dow', []))
        current.update(patch['exclude_dow'])
        new_config['exclude_dow'] = sorted(list(current))
    
    if 'allowed_hours' in patch:
        new_config['allowed_hours'] = patch['allowed_hours']
    
    if 'regime_er_threshold' in patch:
        new_config['regime_er_threshold'] = patch['regime_er_threshold']
    
    if 'regime_adx_threshold' in patch:
        new_config['regime_adx_threshold'] = patch['regime_adx_threshold']
    
    if 'be_multiplier' in patch:
        new_config['be_multiplier'] = patch['be_multiplier']
    
    if 'ema5_threshold' in patch:
        new_config['ema5_threshold'] = patch['ema5_threshold']
    
    return new_config

# ===== MAIN AUTOPILOT LOOP =====
def autopilot(strategy_config, max_cycles=2):
    """Run autopilot loop for a strategy."""
    print("\n" + "="*70)
    print(f"ORQUESTRADOR V7.6 — AUTOPILOT")
    print(f"Strategy: {strategy_config['name']}")
    print(f"Max cycles: {max_cycles}")
    print("="*70)
    
    # Load data ONCE
    data = load_data_once()
    
    # Load IS net from first run (approximate using F3 IS)
    is_net_approx = 0
    
    all_results = []
    current_config = dict(strategy_config)
    prev_f1_top = None  # Track f1_top from previous cycle for reuse
    
    for cycle in range(1, max_cycles + 1):
        log_path = os.path.join(OUT_DIR, f'orchestrator_cycle{cycle}_log.txt')
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"Cycle {cycle} log\n")
        
        # Determine phases to run based on hypothesis from previous cycle
        phases_to_run = ['F1', 'F2', 'F3', 'GUARDRAIL', 'OOS']
        if cycle > 1 and all_results:
            prev_hypothesis = all_results[-1]['best_hypothesis']
            phases_to_run = prev_hypothesis.get('phases_needed', phases_to_run)
            print(f"\n🎛️ PHASE CONTROLLER: Running {phases_to_run} (based on hypothesis '{prev_hypothesis['type']}')")
        
        # Run cycle with selected phases
        result = run_cycle(data, current_config, cycle, log_path, phases_to_run=phases_to_run, prev_f1_top=prev_f1_top)
        
        # Save f1_top for next cycle if F1 was run
        if 'F1' in phases_to_run and result.get('config'):
            prev_f1_top = [{
                'tp': result['config']['tp'],
                'sl': result['config']['sl'],
                'atr_min': result['config']['atr_min'],
                'atr_max': result['config']['atr_max'],
                'f1_net': result['f1_top_net'],
                'f1_n': 0
            }]
        
        if result['status'] == 'abort':
            print(f"\n🛑 CYCLE {cycle} ABORTED: {result.get('reason', 'unknown')}")
            break
        
        # Phase 1: Go/No-Go
        is_net_approx = result['f3_top_net']
        gng = phase1_go_no_go(result, is_net_approx)
        print(f"\n📊 PHASE 1 Go/No-Go: {gng['status']}")
        if gng['status'] == 'ABORT':
            print(f"   Reason: {gng['reason']}")
            break
        
        # Phase 2: DNA Analysis
        print(f"\n🔬 PHASE 2 DNA Analysis...")
        dna = phase2_dna(result, data)
        print(f"   Regime Trend: {dna.get('pnl_trend', 0):+d} (WR={dna.get('wr_trend', 0):.1f}%)")
        print(f"   Regime Range: {dna.get('pnl_range', 0):+d} (WR={dna.get('wr_range', 0):.1f}%)")
        print(f"   Skew: {dna.get('skew', 0):.2f} | Serial Corr: {dna.get('serial_corr', 0):.3f}")
        print(f"   BE hits: {dna.get('be_hit_count', 0)} | TP: {dna.get('tp_count', 0)} | SL: {dna.get('sl_count', 0)}")
        
        # Phase 3: Rank Hypotheses
        print(f"\n🎯 PHASE 3 Ranking Hypotheses...")
        hypotheses = phase3_rank_hypotheses(dna, result)
        if not hypotheses:
            print(f"   No hypotheses generated. Signal exhausted.")
            break
        
        print(f"   Generated {len(hypotheses)} hypotheses:")
        for i, h in enumerate(hypotheses[:5]):
            phases = ','.join(h.get('phases_needed', ['ALL']))
            print(f"   #{i+1} [P{h['priority']}] [{phases}] {h['description']}")
        
        best = hypotheses[0]
        print(f"\n⭐ Best hypothesis: {best['description']}")
        print(f"   Phases needed: {best.get('phases_needed', ['ALL'])}")
        
        # Save results
        all_results.append({
            'cycle': cycle,
            'config': current_config,
            'result': result,
            'dna': dna,
            'hypotheses': hypotheses,
            'best_hypothesis': best,
        })
        
        # Check target
        if result['oos_net'] >= TARGET_PNL:
            print(f"\n🎉 SUCCESS! Target reached: {result['oos_net']:+d} >= {TARGET_PNL}")
            break
        
        # Phase 5: Apply hypothesis for next cycle
        print(f"\n🔄 PHASE 5: Applying hypothesis for next cycle...")
        current_config = phase5_apply_hypothesis(current_config, best)
        print(f"   New config: {json.dumps(current_config, indent=2, default=str)}")
    
    # Final summary
    print("\n" + "="*70)
    print("AUTOPILOT COMPLETE")
    print("="*70)
    for r in all_results:
        phases_run = ','.join(r['best_hypothesis'].get('phases_needed', ['ALL']))
        print(f"Cycle {r['cycle']}: OOS={r['result']['oos_net']:+d} ({r['result']['oos_n']}t, WR={r['result']['oos_wr']:.1f}%) [{phases_run}]")
        print(f"  Hypothesis: {r['best_hypothesis']['description']}")
    print("="*70)
    
    return all_results

# ===== CLI =====
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Orquestrador V7.6 - Autopilot de Ciclos')
    parser.add_argument('--strategy', default='SIGNAL_DIR_BUY', help='Strategy name')
    parser.add_argument('--col', default='PA_SIGNAL_DIR', help='Signal column')
    parser.add_argument('--signal', type=int, default=1, help='Signal direction')
    parser.add_argument('--regime', default='trend', help='Regime filter')
    parser.add_argument('--max-cycles', type=int, default=2, help='Max autopilot cycles')
    args = parser.parse_args()
    
    strategy_config = {
        'name': args.strategy,
        'col': args.col,
        'signal': args.signal,
        'regime': args.regime,
    }
    
    autopilot(strategy_config, max_cycles=args.max_cycles)
