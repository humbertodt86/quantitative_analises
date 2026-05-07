"""
F2 OPTIMIZATION GPU — V9.0 CUDA ACCELERATED
============================================
Versão completa e corrigida da otimização F2 com execução na GPU via CuPy RawKernel.

CORREÇÕES vs v8.7:
- Implementa TODOS os guardrails que v8.7 ignorava:
  * BE (Break Even): move SL -> entrada quando lucro >= be_offset
  * Grace Candles: ignora SL nos primeiros N candles
  * Slope Decay: move SL -> BE quando EMA5 slope cai abaixo do threshold
- GPU batching: processa até 1M combos simultâneos na RTX 4060
- Flattened grid: gera todas as combinações como arrays 1D para coalesced access

Input:  Top 10 configs do F1 (por sinal)
Output: Top 3 configs por sinal

Tempo alvo:
- F1 estável (43K combos): ~0.5–2s
- F1 instável (27M combos): ~15–60s (batches de 1M)
"""
import sys, os, time, warnings, glob
from datetime import datetime
from typing import Dict, List, Any, Tuple
from itertools import product
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# CUDA PATH FIX — detecta nvrtc do PyTorch se CuPy não achar sozinho
# ---------------------------------------------------------------------------
if os.name == 'nt':
    _torch_lib = None
    try:
        import torch
        _torch_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
    except Exception:
        pass
    if _torch_lib and os.path.isdir(_torch_lib) and _torch_lib not in os.environ.get('PATH', ''):
        os.environ['PATH'] = _torch_lib + os.pathsep + os.environ.get('PATH', '')

import cupy as cp

ROOT = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(ROOT) == 'engines':
    ROOT = os.path.dirname(ROOT)
sys.path.insert(0, ROOT)

import polars as pl
from scripts.family_classifier import get_family, get_family_config

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO GLOBAL
# ---------------------------------------------------------------------------
COST = 30.0
GPU_BATCH_SIZE = 1_000_000   # combos por batch (ajustável pela VRAM)
BLOCK_SIZE = 256             # threads por bloco CUDA

GRID_ADVISOR = {
    'cv_threshold_stable': 15.0,
    'pnl_drop_threshold': 0.30,
    'trade_drop_threshold': 0.50,
}

IS_S, IS_E = datetime(2026, 2, 1), datetime(2026, 3, 1)

# ---------------------------------------------------------------------------
# KERNEL CUDA — backtest F2 completo
# ---------------------------------------------------------------------------
CUDA_KERNEL = r'''
extern "C" __global__
void backtest_f2_kernel(
    const double* __restrict__ close,
    const double* __restrict__ high,
    const double* __restrict__ low,
    const double* __restrict__ atr,
    const double* __restrict__ signal,
    const double* __restrict__ dist_res,
    const double* __restrict__ dist_sup,
    const double* __restrict__ book_imb,
    const double* __restrict__ cum_delta,
    const double* __restrict__ ema5,
    int n_candles,
    int n_combos,
    int direction,
    const double* __restrict__ tp_mult,
    const double* __restrict__ sl_mult,
    const double* __restrict__ atr_min,
    const double* __restrict__ atr_max,
    const double* __restrict__ tp_sr_pct,
    const double* __restrict__ sl_sr_pct,
    const double* __restrict__ sr_threshold_pct,
    const double* __restrict__ book_imb_thresh,
    const double* __restrict__ cum_delta_thresh,
    const double* __restrict__ be_offset,
    const int*    __restrict__ grace_candles,
    const int*    __restrict__ cooldown_candles,
    const int*    __restrict__ max_sl_consec,
    const double* __restrict__ slope_decay,
    double* __restrict__ out_pnl,
    double* __restrict__ out_trades,
    double* __restrict__ out_wins)
{
    int idx = blockDim.x * blockIdx.x + threadIdx.x;
    if (idx >= n_combos) return;

    double d_tp_mult     = tp_mult[idx];
    double d_sl_mult     = sl_mult[idx];
    double d_atr_min     = atr_min[idx];
    double d_atr_max     = atr_max[idx];
    double d_tp_sr_pct   = tp_sr_pct[idx];
    double d_sl_sr_pct   = sl_sr_pct[idx];
    double d_sr_thresh   = sr_threshold_pct[idx];
    double d_book_thresh = book_imb_thresh[idx];
    double d_delta_thresh= cum_delta_thresh[idx];
    double d_be_offset   = be_offset[idx];
    int    d_grace       = grace_candles[idx];
    int    d_cooldown    = cooldown_candles[idx];
    int    d_max_sl      = max_sl_consec[idx];
    double d_slope_decay = slope_decay[idx];

    double total_pnl = 0.0;
    int    total_trades = 0;
    int    total_wins = 0;
    int    consecutive_sl = 0;
    bool   in_position = false;
    double entry_price = 0.0;
    double tp_price = 0.0;
    double sl_price = 0.0;
    int    cooldown_counter = 0;
    int    entry_idx = 0;
    double entry_slope = 0.0;

    for (int i = 0; i < n_candles; ++i) {
        if (cooldown_counter > 0) {
            cooldown_counter--;
            continue;
        }

        if (!in_position) {
            // filtros de microestrutura
            if (fabs(book_imb[i]) < d_book_thresh) continue;
            if (direction == 1 && cum_delta[i] < d_delta_thresh) continue;
            if (direction == -1 && cum_delta[i] > -d_delta_thresh) continue;

            if (signal[i] != direction) continue;
            if (atr[i] < d_atr_min || atr[i] > d_atr_max) continue;

            // entrada
            entry_price = close[i];
            entry_idx = i;
            entry_slope = (i > 0) ? (ema5[i] - ema5[i - 1]) : 0.0;

            if (direction == 1) {
                double tp_base = close[i] + d_tp_mult * atr[i];
                double sl_base = close[i] - d_sl_mult * atr[i];
                // TP c/ resistência
                if (dist_res[i] > 0.0) {
                    double denom = d_tp_mult * atr[i];
                    double sr_dist = (denom > 0.0) ? (dist_res[i] / denom) : 999.0;
                    tp_price = (sr_dist < d_sr_thresh) ? (close[i] + d_tp_sr_pct * dist_res[i]) : tp_base;
                } else {
                    tp_price = tp_base;
                }
                // SL c/ suporte
                if (dist_sup[i] > 0.0) {
                    double denom = d_sl_mult * atr[i];
                    double sr_dist = (denom > 0.0) ? (dist_sup[i] / denom) : 999.0;
                    sl_price = (sr_dist < d_sr_thresh) ? (close[i] - d_sl_sr_pct * dist_sup[i]) : sl_base;
                } else {
                    sl_price = sl_base;
                }
            } else {  // SELL
                double tp_base = close[i] - d_tp_mult * atr[i];
                double sl_base = close[i] + d_sl_mult * atr[i];
                // TP c/ suporte
                if (dist_sup[i] > 0.0) {
                    double denom = d_tp_mult * atr[i];
                    double sr_dist = (denom > 0.0) ? (dist_sup[i] / denom) : 999.0;
                    tp_price = (sr_dist < d_sr_thresh) ? (close[i] - d_tp_sr_pct * dist_sup[i]) : tp_base;
                } else {
                    tp_price = tp_base;
                }
                // SL c/ resistência
                if (dist_res[i] > 0.0) {
                    double denom = d_sl_mult * atr[i];
                    double sr_dist = (denom > 0.0) ? (dist_res[i] / denom) : 999.0;
                    sl_price = (sr_dist < d_sr_thresh) ? (close[i] + d_sl_sr_pct * dist_res[i]) : sl_base;
                } else {
                    sl_price = sl_base;
                }
            }
            in_position = true;
            continue;
        }

        // === em posição ===
        bool tp_hit, sl_hit;
        if (direction == 1) {
            tp_hit = high[i] >= tp_price;
            sl_hit = low[i] <= sl_price;
        } else {
            tp_hit = low[i] <= tp_price;
            sl_hit = high[i] >= sl_price;
        }

        // grace candles: só verifica TP, ignora SL
        if ((i - entry_idx) <= d_grace) {
            if (tp_hit) {
                double exit_p = tp_price;
                double pnl_pts = (direction == 1) ? (exit_p - entry_price) : (entry_price - exit_p);
                double pnl_liq = pnl_pts - 30.0;
                total_pnl += pnl_liq;
                total_trades++;
                if (pnl_liq > 0.0) {
                    total_wins++;
                    consecutive_sl = 0;
                } else {
                    consecutive_sl++;
                    if (consecutive_sl >= d_max_sl)
                        cooldown_counter = d_cooldown;
                }
                in_position = false;
            }
            continue;
        }

        // BE: move SL para entrada se lucro >= be_offset
        double current_sl = sl_price;
        if (d_be_offset > 0.0) {
            double profit_pts = (direction == 1) ? (high[i] - entry_price) : (entry_price - low[i]);
            if (profit_pts >= d_be_offset)
                current_sl = entry_price;
        }

        // Slope Decay: move SL -> BE se slope cair abaixo do threshold
        if (d_slope_decay > 0.0 && i > 0) {
            double cur_slope = ema5[i] - ema5[i - 1];
            if (fabs(entry_slope) > 1e-12) {
                double decay_thresh = fabs(entry_slope) * d_slope_decay;
                if (cur_slope * (direction == 1 ? 1.0 : -1.0) < decay_thresh)
                    current_sl = entry_price;
            }
        }

        // re-check SL com possível ajuste BE / slope decay
        if (direction == 1)
            sl_hit = low[i] <= current_sl;
        else
            sl_hit = high[i] >= current_sl;

        if (tp_hit || sl_hit) {
            double exit_p = tp_hit ? tp_price : current_sl;
            double pnl_pts = (direction == 1) ? (exit_p - entry_price) : (entry_price - exit_p);
            double pnl_liq = pnl_pts - 30.0;
            total_pnl += pnl_liq;
            total_trades++;
            if (pnl_liq > 0.0) {
                total_wins++;
                consecutive_sl = 0;
            } else {
                consecutive_sl++;
                if (consecutive_sl >= d_max_sl)
                    cooldown_counter = d_cooldown;
            }
            in_position = false;
        }
    }

    out_pnl[idx]    = total_pnl;
    out_trades[idx] = (double)total_trades;
    out_wins[idx]   = (double)total_wins;
}
'''

# Compila kernel
_backtest_kernel = cp.RawKernel(CUDA_KERNEL, 'backtest_f2_kernel')

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def analyze_f1_stability(f1_top_3: List[Dict]) -> Tuple[bool, str]:
    if len(f1_top_3) < 3:
        return False, "F1 top 3 insuficiente"
    pnls = np.array([r['net_pnl'] for r in f1_top_3])
    tps  = np.array([r['tp_mult'] for r in f1_top_3])
    sls  = np.array([r['sl_mult'] for r in f1_top_3])
    cv_pnl = np.std(pnls, ddof=1) / np.mean(pnls) * 100 if np.mean(pnls) != 0 else 0
    tp_range = float(np.max(tps) - np.min(tps))
    sl_range = float(np.max(sls) - np.min(sls))
    if cv_pnl < GRID_ADVISOR['cv_threshold_stable'] and tp_range < 0.2 and sl_range < 0.5:
        return True, f"F1 estável (CV={cv_pnl:.1f}%, TP range={tp_range:.2f}, SL range={sl_range:.2f})"
    return False, f"F1 instável (CV={cv_pnl:.1f}%, TP range={tp_range:.2f}, SL range={sl_range:.2f})"


def generate_refined_grid(f1_best: Dict, factor: float = 0.20, num_values: int = 5) -> Dict:
    return {
        'tp_mult': np.linspace(f1_best['tp_mult'] * (1 - factor), f1_best['tp_mult'] * (1 + factor), num_values),
        'sl_mult': np.linspace(f1_best['sl_mult'] * (1 - factor), f1_best['sl_mult'] * (1 + factor), num_values),
        'atr_min': np.linspace(f1_best['atr_min'] * (1 - factor), f1_best['atr_min'] * (1 + factor), num_values),
        'atr_max': np.linspace(f1_best['atr_max'] * (1 - factor), f1_best['atr_max'] * (1 + factor), num_values),
    }


def build_flat_grid(grid: Dict) -> Tuple[Dict[str, np.ndarray], int]:
    """Flatten grid N-dim -> arrays 1D de tamanho n_combos."""
    keys = [
        'tp_mult', 'sl_mult', 'atr_min', 'atr_max',
        'tp_sr_pct', 'sl_sr_pct', 'sr_threshold_pct',
        'book_imb_thresh', 'cum_delta_thresh',
        'be_offset', 'grace_candles', 'cooldown_candles',
        'max_sl_consec', 'slope_decay'
    ]

    ranges = []
    for k in keys:
        if k in grid.get('tp_sl_atr', {}):
            ranges.append(grid['tp_sl_atr'][k])
        elif k in grid.get('sr_buffers', {}):
            ranges.append(grid['sr_buffers'][k])
        elif k in grid.get('guardrails', {}):
            ranges.append(grid['guardrails'][k])
        elif k in grid.get('filters', {}):
            ranges.append(grid['filters'][k])
        else:
            if k == 'sr_threshold_pct':
                ranges.append([1.15])
            else:
                ranges.append([0])

    combos = list(product(*ranges))
    n = len(combos)
    out = {k: np.zeros(n, dtype=np.float64) for k in keys}
    out['grace_candles'] = np.zeros(n, dtype=np.int32)
    out['cooldown_candles'] = np.zeros(n, dtype=np.int32)
    out['max_sl_consec'] = np.zeros(n, dtype=np.int32)

    for i, combo in enumerate(combos):
        for j, k in enumerate(keys):
            if k in ('grace_candles', 'cooldown_candles', 'max_sl_consec'):
                out[k][i] = int(combo[j])
            else:
                out[k][i] = float(combo[j])
    return out, n


# ---------------------------------------------------------------------------
# GPU ENGINE
# ---------------------------------------------------------------------------

def run_gpu_batch(
    d_close, d_high, d_low, d_atr, d_signal,
    d_dist_res, d_dist_sup, d_book_imb, d_cum_delta, d_ema5,
    n_rows: int, direction: int,
    flat_grid: Dict[str, np.ndarray], start_idx: int, end_idx: int
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Executa um batch de combos na GPU."""
    batch_sz = end_idx - start_idx

    # slice arrays
    def _slice(k):
        arr = flat_grid[k][start_idx:end_idx]
        if k in ('grace_candles', 'cooldown_candles', 'max_sl_consec'):
            return cp.asarray(arr, dtype=cp.int32)
        return cp.asarray(arr, dtype=cp.float64)

    d_tp_mult      = _slice('tp_mult')
    d_sl_mult      = _slice('sl_mult')
    d_atr_min      = _slice('atr_min')
    d_atr_max      = _slice('atr_max')
    d_tp_sr_pct    = _slice('tp_sr_pct')
    d_sl_sr_pct    = _slice('sl_sr_pct')
    d_sr_thresh    = _slice('sr_threshold_pct')
    d_book_thresh  = _slice('book_imb_thresh')
    d_delta_thresh = _slice('cum_delta_thresh')
    d_be_offset    = _slice('be_offset')
    d_grace        = _slice('grace_candles')
    d_cooldown     = _slice('cooldown_candles')
    d_max_sl       = _slice('max_sl_consec')
    d_slope_decay  = _slice('slope_decay')

    d_out_pnl    = cp.empty(batch_sz, dtype=cp.float64)
    d_out_trades = cp.empty(batch_sz, dtype=cp.float64)
    d_out_wins   = cp.empty(batch_sz, dtype=cp.float64)

    threads = BLOCK_SIZE
    blocks  = (batch_sz + threads - 1) // threads

    _backtest_kernel(
        (blocks,), (threads,),
        (d_close, d_high, d_low, d_atr, d_signal,
         d_dist_res, d_dist_sup, d_book_imb, d_cum_delta, d_ema5,
         np.int32(n_rows), np.int32(batch_sz), np.int32(direction),
         d_tp_mult, d_sl_mult, d_atr_min, d_atr_max,
         d_tp_sr_pct, d_sl_sr_pct, d_sr_thresh,
         d_book_thresh, d_delta_thresh,
         d_be_offset, d_grace, d_cooldown, d_max_sl, d_slope_decay,
         d_out_pnl, d_out_trades, d_out_wins)
    )

    cp.cuda.Device().synchronize()
    return cp.asnumpy(d_out_pnl), cp.asnumpy(d_out_trades), cp.asnumpy(d_out_wins)


def optimize_all_combos_gpu(
    df: pd.DataFrame,
    variant_col: str,
    direction: int,
    grid: Dict,
    batch_size: int = GPU_BATCH_SIZE
) -> Tuple[pd.DataFrame, float]:
    """
    Roda TODAS as combinações do grid na GPU e retorna DataFrame rankeado por score.
    """
    start_total = time.time()
    n_rows = len(df)

    # transfer candle data uma única vez
    d_close    = cp.asarray(df['close'].values, dtype=cp.float64)
    d_high     = cp.asarray(df['high'].values, dtype=cp.float64)
    d_low      = cp.asarray(df['low'].values, dtype=cp.float64)
    d_atr      = cp.asarray(df['ATR'].values, dtype=cp.float64)
    d_signal   = cp.asarray(df[variant_col].values, dtype=cp.float64)
    d_dist_res = cp.asarray(df['dist_to_resistance'].values, dtype=cp.float64) if 'dist_to_resistance' in df.columns else cp.zeros(n_rows, dtype=cp.float64)
    d_dist_sup = cp.asarray(df['dist_to_support'].values, dtype=cp.float64) if 'dist_to_support' in df.columns else cp.zeros(n_rows, dtype=cp.float64)
    d_book_imb = cp.asarray(df['book_imbalance'].values, dtype=cp.float64) if 'book_imbalance' in df.columns else cp.zeros(n_rows, dtype=cp.float64)
    d_cum_delta= cp.asarray(df['cum_delta'].values, dtype=cp.float64) if 'cum_delta' in df.columns else cp.zeros(n_rows, dtype=cp.float64)
    d_ema5     = cp.asarray(df['EMA5'].values, dtype=cp.float64) if 'EMA5' in df.columns else cp.zeros(n_rows, dtype=cp.float64)

    # flatten grid
    flat_grid, n_combos = build_flat_grid(grid)
    print(f"  GPU batches: {(n_combos + batch_size - 1)//batch_size} × max {batch_size:,} combos")

    all_pnl    = np.empty(n_combos, dtype=np.float64)
    all_trades = np.empty(n_combos, dtype=np.float64)
    all_wins   = np.empty(n_combos, dtype=np.float64)

    for b_start in range(0, n_combos, batch_size):
        b_end = min(b_start + batch_size, n_combos)
        pnl, trades, wins = run_gpu_batch(
            d_close, d_high, d_low, d_atr, d_signal,
            d_dist_res, d_dist_sup, d_book_imb, d_cum_delta, d_ema5,
            n_rows, direction, flat_grid, b_start, b_end
        )
        all_pnl[b_start:b_end]    = pnl
        all_trades[b_start:b_end] = trades
        all_wins[b_start:b_end]   = wins

    elapsed = time.time() - start_total

    # montar resultado
    results = []
    keys = list(flat_grid.keys())
    for i in range(n_combos):
        trades = int(all_trades[i])
        if trades < 10:
            continue
        wins = int(all_wins[i])
        pnl  = all_pnl[i]
        wr   = wins / trades * 100 if trades > 0 else 0
        avg  = pnl / trades
        avg_trade = pnl / trades
        score = pnl * 0.7 + avg_trade * 0.3
        row = {k: flat_grid[k][i] for k in keys}
        row.update({'net_pnl': pnl, 'n_trades': trades, 'win_rate': wr,
                    'score': score})
        results.append(row)

    if not results:
        return pd.DataFrame(), elapsed

    df_res = pd.DataFrame(results).sort_values('score', ascending=False).reset_index(drop=True)
    return df_res, elapsed


# ---------------------------------------------------------------------------
# ORQUESTRAÇÃO (compatível com interface v8.7)
# ---------------------------------------------------------------------------

def run_f2_optimization(
    parquet_path: str,
    signal_name: str,
    variant_name: str,
    top10_f1: List[Dict],
    direction: int = 1
) -> Dict:
    print(f"\n{'='*80}")
    print(f"F2 OPTIMIZATION GPU — {signal_name} {'BUY' if direction==1 else 'SELL'}")
    print(f"{'='*80}")

    # 1. Família
    family = get_family(signal_name)
    print(f"\nFamília: {family}")

    # 2. Grid config
    try:
        family_config = get_family_config(family)
    except Exception as e:
        print(f"  [WARN] Erro: {e}")
        family_config = get_family_config('trend')

    # 3. GridAdvisor
    f1_stable, reason = analyze_f1_stability(top10_f1[:3])
    print(f"  GridAdvisor: {reason}")

    if f1_stable:
        f1_best = top10_f1[0]
        grid = {
            'tp_sl_atr': {
                'tp_mult': [f1_best['tp_mult']],
                'sl_mult': [f1_best['sl_mult']],
                'atr_min': [f1_best['atr_min']],
                'atr_max': [f1_best['atr_max']]
            },
            'sr_buffers': family_config['sr_buffers'],
            'guardrails': family_config['guardrails'],
            'filters': family_config['filters'],
        }
        print(f"  TP/SL/ATR: FIXO (1 combo)")
    else:
        f1_best = top10_f1[0]
        refined = generate_refined_grid(f1_best, factor=0.20, num_values=5)
        grid = {
            'tp_sl_atr': refined,
            'sr_buffers': family_config['sr_buffers'],
            'guardrails': family_config['guardrails'],
            'filters': family_config['filters'],
        }
        print(f"  TP/SL/ATR: REFINO (±20%)")

    # calcular combos
    tp_sl_atr_combos = len(grid['tp_sl_atr']['tp_mult']) * len(grid['tp_sl_atr']['sl_mult']) * len(grid['tp_sl_atr']['atr_min']) * len(grid['tp_sl_atr']['atr_max'])
    sr_combos = len(grid['sr_buffers']['tp_sr_pct']) * len(grid['sr_buffers']['sl_sr_pct'])
    guardrail_combos = len(grid['guardrails']['be_offset']) * len(grid['guardrails']['grace_candles']) * len(grid['guardrails']['cooldown_candles']) * len(grid['guardrails']['max_sl_consec']) * len(grid['guardrails']['slope_decay'])
    filter_combos = len(grid['filters']['book_imb_thresh']) * len(grid['filters']['cum_delta_thresh'])
    total_combos = tp_sl_atr_combos * sr_combos * guardrail_combos * filter_combos
    print(f"\n  Combos TP/SL/ATR: {tp_sl_atr_combos:,}")
    print(f"  Combos S/R: {sr_combos:,}")
    print(f"  Combos Guardrails: {guardrail_combos:,}")
    print(f"  Combos Filtros: {filter_combos:,}")
    print(f"  TOTAL: {total_combos:,} combos")

    # 4. Carregar parquet
    print(f"\nLoading {parquet_path}...")
    df = pl.read_parquet(parquet_path).to_pandas()
    df['dt'] = pd.to_datetime(df['dt'])
    df = df[(df['dt'] >= IS_S) & (df['dt'] <= IS_E)].reset_index(drop=True)
    print(f"  Loaded: {len(df)} rows (Fevereiro 2026)")

    # 5. Rodar GPU
    print(f"\nRunning GPU optimization ({total_combos:,} combos)...")
    df_res, elapsed = optimize_all_combos_gpu(df, variant_name, direction, grid)
    print(f"  GPU tempo real: {elapsed:.2f}s")
    print(f"  Válidos (>=10 trades): {len(df_res):,}")

    if len(df_res) == 0:
        print("  [ERRO] Nenhuma config válida encontrada.")
        return {}

    # 6. GridAdvisor check
    f2_best = df_res.iloc[0]
    f1_best_pnl = top10_f1[0]['net_pnl']
    f1_best_trades = top10_f1[0]['n_trades']
    pnl_ratio = f2_best['net_pnl'] / f1_best_pnl if f1_best_pnl != 0 else 0
    trade_ratio = f2_best['n_trades'] / f1_best_trades if f1_best_trades != 0 else 0
    if pnl_ratio < (1 - GRID_ADVISOR['pnl_drop_threshold']):
        print(f"\n  [WARN] GridAdvisor: PnL caiu {(1-pnl_ratio)*100:.0f}%")
    elif trade_ratio < (1 - GRID_ADVISOR['trade_drop_threshold']):
        print(f"\n  [WARN] GridAdvisor: Trades cairam {(1-trade_ratio)*100:.0f}%")
    else:
        print(f"\n  [OK] GridAdvisor: OK (PnL {pnl_ratio*100:.0f}%, Trades {trade_ratio*100:.0f}%)")

    # 7. Top 3
    top3 = []
    for i in range(min(3, len(df_res))):
        r = df_res.iloc[i]
        top3.append({
            'config_f1': {
                'tp_mult': r['tp_mult'], 'sl_mult': r['sl_mult'],
                'atr_min': r['atr_min'], 'atr_max': r['atr_max']
            },
            'config_f2': {
                'tp_sr_pct': r['tp_sr_pct'], 'sl_sr_pct': r['sl_sr_pct'],
                'sr_threshold_pct': r.get('sr_threshold_pct', 1.15),
                'be_offset': r['be_offset'], 'grace_candles': int(r['grace_candles']),
                'cooldown_candles': int(r['cooldown_candles']),
                'max_sl_consec': int(r['max_sl_consec']), 'slope_decay': r['slope_decay'],
                'book_imb_thresh': r['book_imb_thresh'], 'cum_delta_thresh': r['cum_delta_thresh'],
            },
            'stats': {
                'net_pnl': r['net_pnl'], 'n_trades': int(r['n_trades']),
                'win_rate': r['win_rate'], 'score': r['score'],
            }
        })

    # 8. Salvar CSV
    out_dir = os.path.join(ROOT, 'docs', 'WIN_docs')
    os.makedirs(out_dir, exist_ok=True)
    output_path = os.path.join(out_dir, f'F2_OPTIMIZATION_{signal_name}_{"BUY" if direction==1 else "SELL"}.csv')

    out_records = []
    for i, r in enumerate(top3):
        out_records.append({
            'rank': i+1,
            'tp_mult': r['config_f1']['tp_mult'],
            'sl_mult': r['config_f1']['sl_mult'],
            'atr_min': r['config_f1']['atr_min'],
            'atr_max': r['config_f1']['atr_max'],
            'tp_sr_pct': r['config_f2']['tp_sr_pct'],
            'sl_sr_pct': r['config_f2']['sl_sr_pct'],
            'sr_threshold_pct': r['config_f2']['sr_threshold_pct'],
            'be_offset': r['config_f2']['be_offset'],
            'grace_candles': r['config_f2']['grace_candles'],
            'cooldown_candles': r['config_f2']['cooldown_candles'],
            'max_sl_consec': r['config_f2']['max_sl_consec'],
            'slope_decay': r['config_f2']['slope_decay'],
            'book_imb_thresh': r['config_f2']['book_imb_thresh'],
            'cum_delta_thresh': r['config_f2']['cum_delta_thresh'],
            'net_pnl': r['stats']['net_pnl'],
            'n_trades': r['stats']['n_trades'],
            'win_rate': r['stats']['win_rate'],
            # 'sharpe': r['stats'].get('sharpe', 0),
            'score': r['stats']['score'],
        })
    pd.DataFrame(out_records).to_csv(output_path, index=False)
    print(f"\n  Saved: {output_path}")

    # 9. Print
    print(f"\n{'='*80}")
    print("TOP 3 CONFIGS F2:")
    print(f"{'='*80}")
    for i, r in enumerate(top3):
        print(f"\n  #{i+1}:")
        print(f"     TP/SL/ATR: TP={r['config_f1']['tp_mult']:.1f}, SL={r['config_f1']['sl_mult']:.1f}, ATR=[{r['config_f1']['atr_min']:.0f}-{r['config_f1']['atr_max']:.0f}]")
        print(f"     S/R: TP_SR={r['config_f2']['tp_sr_pct']:.2f}, SL_SR={r['config_f2']['sl_sr_pct']:.2f}, SR_THRESH={r['config_f2']['sr_threshold_pct']:.2f}")
        print(f"     Guarda: BE={r['config_f2']['be_offset']:.0f}, GRACE={r['config_f2']['grace_candles']}, CD={r['config_f2']['cooldown_candles']}, MAX_SL={r['config_f2']['max_sl_consec']}, SLOPE={r['config_f2']['slope_decay']:.2f}")
        print(f"     Filtros: BOOK={r['config_f2']['book_imb_thresh']:.1f}, DELTA={r['config_f2']['cum_delta_thresh']:.1f}")
        print(f"     Stats: PnL=R$ {r['stats']['net_pnl']:,.0f}, Trades={r['stats']['n_trades']}, WR={r['stats']['win_rate']:.1f}%, Score={r['stats']['score']:.0f}")

    return {
        'signal': signal_name,
        'direction': 'BUY' if direction==1 else 'SELL',
        'top3': top3,
        'output_path': output_path,
        'elapsed': elapsed,
        'n_combos_evaluated': total_combos,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='F2 Optimization GPU V9.0')
    parser.add_argument('--signal', type=str, default='PA_SIGNAL_DIR', help='Signal name')
    parser.add_argument('--variant', type=str, default='s10_z4p0_r0p5', help='V8 variant')
    parser.add_argument('--direction', type=str, default='BUY', help='BUY or SELL')
    parser.add_argument('--batch-size', type=int, default=GPU_BATCH_SIZE, help='GPU batch size')
    args = parser.parse_args()

    # Carregar F1
    f1_results_path = os.path.join(ROOT, 'docs', 'WIN_docs', f'F1_V87_TEST_{args.signal}.csv')
    if not os.path.exists(f1_results_path):
        print(f"\n[ERRO] F1 results não encontrado: {f1_results_path}")
        exit(1)

    f1_df = pd.read_csv(f1_results_path)
    f1_df = f1_df[f1_df['signal'] == args.variant]
    f1_df = f1_df[f1_df['direction'] == args.direction]
    f1_df = f1_df.sort_values('net_pnl', ascending=False).head(10)

    if len(f1_df) == 0:
        print(f"\n[ERRO] Nenhuma config F1")
        exit(1)

    top10_f1 = f1_df[['tp_mult', 'sl_mult', 'atr_min', 'atr_max', 'net_pnl', 'n_trades']].to_dict('records')
    print(f"\nLoaded {len(top10_f1)} configs from F1:")
    for i, cfg in enumerate(top10_f1[:3]):
        print(f"  #{i+1}: TP={cfg['tp_mult']:.1f}, SL={cfg['sl_mult']:.1f}, ATR=[{cfg['atr_min']:.0f}-{cfg['atr_max']:.0f}], PnL={cfg['net_pnl']:,.0f}")

    # Parquet
    parquet_path = os.path.join(ROOT, 'data', 'variants_v87', f'{args.signal}.parquet')
    if not os.path.exists(parquet_path):
        print(f"\n[ERRO] Parquet não encontrado: {parquet_path}")
        exit(1)

    GPU_BATCH_SIZE = args.batch_size
    direction = 1 if args.direction == 'BUY' else -1
    run_f2_optimization(parquet_path, args.signal, args.variant, top10_f1, direction)
