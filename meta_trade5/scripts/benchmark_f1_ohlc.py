"""
Benchmark F1 OHLC vs F2
=======================
Compara rankeamento entre F1 OHLC e F2.
"""
import sys, os, time
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import polars as pl
from datetime import datetime
from backtest.engine_v2 import BacktestEngine
from engines.f1_fast_screener import build_M_close
from engines.f1_ohlc import build_M_ohlc, evaluate as evaluate_ohlc
from engines.f2_optimization_v87 import backtest_f2_numba
from scipy.stats import spearmanr

BASE = os.path.join(ROOT, 'data')
SUPER = os.path.join(BASE, 'super_win_continuous.parquet')
SINAL = 'PA_SIGNAL_DIR'

print("="*80)
print("BENCHMARK F1 OHLC vs F2")
print("="*80)

# Dados
print("\n[1/3] Carregando dados...")
df = pl.read_parquet(SUPER).filter(
    (pl.col('dt') >= datetime(2026, 2, 1)) & (pl.col('dt') < datetime(2026, 3, 1))
)
N = len(df)
close_arr = df['close'].to_numpy().astype(np.float64)
high_arr = df['high'].to_numpy().astype(np.float64)
low_arr = df['low'].to_numpy().astype(np.float64)
atr_arr = df['ATR'].to_numpy().astype(np.float64)
signal = df[SINAL].to_numpy().astype(np.float64)
zeros = np.zeros(N, dtype=np.float64)

sell_idx = np.where(signal == 1)[0].astype(np.int32)
ep = np.array([df['open'].to_numpy()[i+1] if i+1 < N else df['close'].to_numpy()[i] for i in sell_idx], dtype=np.float32)
atr = atr_arr[sell_idx].astype(np.float32)

print(f"  Candles: {N} | Entradas BUY: {len(sell_idx)}")

# Ticks para F1 original (comparacao)
win = pl.read_parquet(os.path.join(BASE, 'WIN_merged_all.parquet'))
win = win.with_columns(pl.from_epoch(pl.col('time_msc')//1000, time_unit='s').alias('dt'))
fev = win.filter(pl.col('dt').dt.month() == 2).filter(pl.col('dt').dt.year() == 2026).sort('time_msc')
tick_last = fev['last'].to_numpy().astype(np.float32)
eng = BacktestEngine(None)
eng.df = df
eng.load_ticks_for_simulation(fev)
M_samples, closes = build_M_close(tick_last, eng.tick_idx, sell_idx, N, close_arr.astype(np.float32), incluir_extremos=True)

# M_hlc para F1 OHLC
M_hl = build_M_ohlc(high_arr.astype(np.float32), low_arr.astype(np.float32), sell_idx, N)
print(f"  M_samples: {M_samples.shape} | M_hl: {M_hl.shape}")

# Grid
TP_GRID = np.array([1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0])
SL_GRID = np.array([0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0])
DIRECTION = 1

# Avaliar
print("\n[2/3] Avaliando grid...")
results_f1s = []  # F1 samples
results_f1o = []  # F1 OHLC
results_f2 = []

for tp in TP_GRID:
    for sl in SL_GRID:
        # F1 Samples (15 samples + extremos)
        from engines.f1_binario import evaluate as eval_bin
        net_f1s, n_f1s = eval_bin(M_samples, ep, atr, sell_idx, tp, sl, direction=DIRECTION, use_uint64=True, blocking_mode='exact')
        results_f1s.append((tp, sl, net_f1s, n_f1s))

        # F1 OHLC
        net_f1o, n_f1o = evaluate_ohlc(M_hl, ep, atr, sell_idx, tp, sl, direction=DIRECTION)
        results_f1o.append((tp, sl, net_f1o, n_f1o))

        # F2
        net_f2, n_f2, _ = backtest_f2_numba(
            close_arr, high_arr, low_arr, atr_arr, signal,
            tp, sl, 0, 99999, 1.0, 1.0, 999.0, zeros, zeros, zeros, zeros,
            0.0, -999.0, 999999, 999, 0, 99, 0.0, DIRECTION
        )
        results_f2.append((tp, sl, net_f2, n_f2))

# Correlacoes
print("\n[3/3] Calculando correlacoes...")

f1s_scores = [r[2] for r in results_f1s]
f1o_scores = [r[2] for r in results_f1o]
f2_scores = [r[2] for r in results_f2]

corr_f1s_f2, _ = spearmanr(f1s_scores, f2_scores)
corr_f1o_f2, _ = spearmanr(f1o_scores, f2_scores)
corr_f1s_f1o, _ = spearmanr(f1s_scores, f1o_scores)

print("\n" + "="*80)
print("RESULTADOS")
print("="*80)
print(f"Total configs: {len(results_f1s)}")
print(f"\nCorrelacao Spearman:")
print(f"  F1 Samples  vs F2: {corr_f1s_f2:+.3f}")
print(f"  F1 OHLC     vs F2: {corr_f1o_f2:+.3f}")
print(f"  F1 Samples  vs F1 OHLC: {corr_f1s_f1o:+.3f}")

# Top 5 de cada um
for name, results in [('F1 Samples', results_f1s), ('F1 OHLC', results_f1o), ('F2', results_f2)]:
    results.sort(key=lambda x: x[2], reverse=True)
    print(f"\nTop 5 {name}:")
    for i, r in enumerate(results[:5]):
        print(f"  {i+1}. TP={r[0]:.1f} SL={r[1]:.1f} PnL={r[2]:+12,.0f} N={r[3]}")

# Overlaps
for name, results in [('F1 Samples', results_f1s), ('F1 OHLC', results_f1o)]:
    top_a = set((r[0], r[1]) for r in results[:10])
    top_f2 = set((r[0], r[1]) for r in sorted(results_f2, key=lambda x: x[2], reverse=True)[:10])
    overlap = len(top_a & top_f2)
    print(f"\nOverlap Top 10 ({name} vs F2): {overlap}/10")

# Velocidade
print("\n" + "="*80)
print("VELOCIDADE")
print("="*80)

N_RUNS = 100
# F1 Samples
t0 = time.time()
for _ in range(N_RUNS):
    eval_bin(M_samples, ep, atr, sell_idx, 2.0, 5.0, direction=DIRECTION, use_uint64=True, blocking_mode='exact')
dt_f1s = time.time() - t0

# F1 OHLC
t0 = time.time()
for _ in range(N_RUNS):
    evaluate_ohlc(M_hl, ep, atr, sell_idx, 2.0, 5.0, direction=DIRECTION)
dt_f1o = time.time() - t0

print(f"F1 Samples:  {dt_f1s*1000/N_RUNS:.2f} ms/run")
print(f"F1 OHLC:     {dt_f1o*1000/N_RUNS:.2f} ms/run")
print(f"Speedup:     {dt_f1s/dt_f1o:.1f}x")

print("\n" + "="*80)
print("BENCHMARK COMPLETE")
print("="*80)
