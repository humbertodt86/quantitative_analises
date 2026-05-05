"""
Benchmark F1 Binario vs F1 Fast Screener Original
==================================================
Compara velocidade e resultados entre as duas versoes do F1.
"""
import sys, os, time
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import polars as pl
from datetime import datetime
from backtest.engine_v2 import BacktestEngine
from engines.f1_fast_screener import build_M_close, evaluate as evaluate_original
from engines.f1_binario import evaluate as evaluate_binario, evaluate_combo, blocking_binario_uint64, blocking_binario_uint8

BASE = os.path.join(ROOT, 'data')
SUPER = os.path.join(BASE, 'super_win_continuous.parquet')
SINAL = 'PA_SIGNAL_DIR'

print("="*80)
print("BENCHMARK F1 BINARIO vs F1 ORIGINAL")
print("="*80)

# 1. Carregar dados de Fevereiro 2026
print("\n1. Carregando dados...")
df_fev_pl = pl.read_parquet(SUPER).filter(
    (pl.col('dt') >= datetime(2026, 2, 1)) & (pl.col('dt') < datetime(2026, 3, 1))
)
N_fe = len(df_fev_pl)
close_arr = df_fev_pl['close'].to_numpy().astype(np.float32)
signal_dir = df_fev_pl[SINAL].to_numpy().astype(np.int32)
sell_idx = np.where(signal_dir == 1)[0].astype(np.int32)
ep_arr = np.array([
    df_fev_pl['open'].to_numpy()[i+1] if i+1 < N_fe else df_fev_pl['close'].to_numpy()[i]
    for i in sell_idx
], dtype=np.float32)
atr_arr = df_fev_pl['ATR'].to_numpy().astype(np.float32)[sell_idx]

print(f"   Candles: {N_fe}")
print(f"   Entradas BUY: {len(sell_idx)}")

# 2. Carregar ticks e build M
print("\n2. Carregando ticks e construindo matriz M...")
win = pl.read_parquet(os.path.join(BASE, 'WIN_merged_all.parquet'))
win = win.with_columns(pl.from_epoch(pl.col('time_msc') // 1000, time_unit='s').alias('dt'))
fev_ticks = win.filter(pl.col('dt').dt.month() == 2).filter(pl.col('dt').dt.year() == 2026).sort('time_msc')
tick_last = fev_ticks['last'].to_numpy().astype(np.float32)

eng = BacktestEngine(None)
eng.df = df_fev_pl
eng.load_ticks_for_simulation(fev_ticks)

M, closes = build_M_close(tick_last, eng.tick_idx, sell_idx, N_fe, close_arr, incluir_extremos=False)
print(f"   M shape: {M.shape}")

# Parametros de teste
TP_TEST = 2.0
SL_TEST = 5.0
DIRECTION = 1  # BUY

# 3. Resultados F1 Original
print("\n3. F1 ORIGINAL (fast_screener)")
net_orig, n_orig = evaluate_original(M, ep_arr, atr_arr, sell_idx, TP_TEST, SL_TEST, direction=DIRECTION)
print(f"   PnL: {net_orig:+,}  |  Trades: {n_orig}")

# 4. Resultados F1 Binario (uint8, modo single = compativel F1)
print("\n4. F1 BINARIO (uint8, single)")
net_u8s, n_u8s = evaluate_binario(M, ep_arr, atr_arr, sell_idx, TP_TEST, SL_TEST, direction=DIRECTION, use_uint64=False, blocking_mode='single')
print(f"   PnL: {net_u8s:+,}  |  Trades: {n_u8s}")

# 5. Resultados F1 Binario (uint64, modo single)
print("\n5. F1 BINARIO (uint64, single)")
net_u64s, n_u64s = evaluate_binario(M, ep_arr, atr_arr, sell_idx, TP_TEST, SL_TEST, direction=DIRECTION, use_uint64=True, blocking_mode='single')
print(f"   PnL: {net_u64s:+,}  |  Trades: {n_u64s}")

# 6. Resultados F1 Binario (uint64, modo exact = duracao real)
print("\n6. F1 BINARIO (uint64, exact)")
net_u64e, n_u64e = evaluate_binario(M, ep_arr, atr_arr, sell_idx, TP_TEST, SL_TEST, direction=DIRECTION, use_uint64=True, blocking_mode='exact')
print(f"   PnL: {net_u64e:+,}  |  Trades: {n_u64e}")

# 7. Comparacao de resultados
print("\n" + "="*80)
print("COMPARACAO DE RESULTADOS")
print("="*80)
print(f"{'Motor':<30} {'PnL':<15} {'Trades':<10} {'Diff PnL':<12} {'Diff Trades':<12}")
print("-"*80)
print(f"{'F1 Original':<30} {net_orig:<+15} {n_orig:<10} {'—':<12} {'—':<12}")
print(f"{'F1 Binario uint8 single':<30} {net_u8s:<+15} {n_u8s:<10} {net_u8s-net_orig:<+12} {n_u8s-n_orig:<+12}")
print(f"{'F1 Binario uint64 single':<30} {net_u64s:<+15} {n_u64s:<10} {net_u64s-net_orig:<+12} {n_u64s-n_orig:<+12}")
print(f"{'F1 Binario uint64 exact':<30} {net_u64e:<+15} {n_u64e:<10} {net_u64e-net_orig:<+12} {n_u64e-n_orig:<+12}")

# 8. Benchmark de velocidade
print("\n" + "="*80)
print("BENCHMARK DE VELOCIDADE")
print("="*80)

N_RUNS = 100

# F1 Original
t0 = time.time()
for _ in range(N_RUNS):
    evaluate_original(M, ep_arr, atr_arr, sell_idx, TP_TEST, SL_TEST, direction=DIRECTION)
dt_orig = time.time() - t0
ms_orig = dt_orig / N_RUNS * 1000

# F1 Binario uint8 single
t0 = time.time()
for _ in range(N_RUNS):
    evaluate_binario(M, ep_arr, atr_arr, sell_idx, TP_TEST, SL_TEST, direction=DIRECTION, use_uint64=False, blocking_mode='single')
dt_u8s = time.time() - t0
ms_u8s = dt_u8s / N_RUNS * 1000

# F1 Binario uint64 single
t0 = time.time()
for _ in range(N_RUNS):
    evaluate_binario(M, ep_arr, atr_arr, sell_idx, TP_TEST, SL_TEST, direction=DIRECTION, use_uint64=True, blocking_mode='single')
dt_u64s = time.time() - t0
ms_u64s = dt_u64s / N_RUNS * 1000

# F1 Binario uint64 exact
t0 = time.time()
for _ in range(N_RUNS):
    evaluate_binario(M, ep_arr, atr_arr, sell_idx, TP_TEST, SL_TEST, direction=DIRECTION, use_uint64=True, blocking_mode='exact')
dt_u64e = time.time() - t0
ms_u64e = dt_u64e / N_RUNS * 1000

# Evaluate combo (apenas calculo numpy, sem blocking)
t0 = time.time()
for _ in range(N_RUNS):
    had, pnl, duration = evaluate_combo(M, ep_arr, atr_arr, sell_idx, TP_TEST, SL_TEST, direction=DIRECTION)
dt_combo = time.time() - t0
ms_combo = dt_combo / N_RUNS * 1000

# Blocking uint64 single sozinho
had, pnl, duration = evaluate_combo(M, ep_arr, atr_arr, sell_idx, TP_TEST, SL_TEST, direction=DIRECTION)
N_candles = int(sell_idx.max()) + 50 + 2
t0 = time.time()
for _ in range(N_RUNS):
    blocking_binario_uint64(sell_idx, had, pnl, duration, N_candles, 1)
dt_block64s = time.time() - t0
ms_block64s = dt_block64s / N_RUNS * 1000

# Blocking uint64 exact sozinho
t0 = time.time()
for _ in range(N_RUNS):
    blocking_binario_uint64(sell_idx, had, pnl, duration, N_candles, 0)
dt_block64e = time.time() - t0
ms_block64e = dt_block64e / N_RUNS * 1000

print(f"{'Componente':<35} {'Tempo (ms/run)':<15} {'Speedup vs Orig':<15}")
print("-"*65)
print(f"{'F1 Original (total)':<35} {ms_orig:<15.2f} {'1.0x':<15}")
print(f"{'F1 Binario uint8 single':<35} {ms_u8s:<15.2f} {ms_orig/ms_u8s:<15.1f}x")
print(f"{'F1 Binario uint64 single':<35} {ms_u64s:<15.2f} {ms_orig/ms_u64s:<15.1f}x")
print(f"{'F1 Binario uint64 exact':<35} {ms_u64e:<15.2f} {ms_orig/ms_u64e:<15.1f}x")
print(f"{'— evaluate_combo() sozinho':<35} {ms_combo:<15.2f} {'—':<15}")
print(f"{'— blocking uint64 single':<35} {ms_block64s:<15.2f} {'—':<15}")
print(f"{'— blocking uint64 exact':<35} {ms_block64e:<15.2f} {'—':<15}")

# 9. Grid search batch (sequencial)
print("\n" + "="*80)
print("GRID SEARCH BATCH — SEQUENCIAL (96 combos)")
print("="*80)

TP_GRID = np.array([1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 15.0, 20.0])
SL_GRID = np.array([0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0])

# F1 Original: loop puro
t0 = time.time()
for tp in TP_GRID:
    for sl in SL_GRID:
        evaluate_original(M, ep_arr, atr_arr, sell_idx, tp, sl, direction=DIRECTION)
dt_grid_orig = time.time() - t0

# F1 Binario batch (single)
t0 = time.time()
from engines.f1_binario import evaluate_batch
net_grid_s, n_grid_s = evaluate_batch(M, ep_arr, atr_arr, sell_idx, TP_GRID, SL_GRID, direction=DIRECTION, use_uint64=True, blocking_mode='single')
dt_grid_bins = time.time() - t0

print(f"{'Metodo':<35} {'Tempo':<12} {'Speedup':<12}")
print("-"*60)
print(f"{'F1 Original (loop puro)':<35} {dt_grid_orig:<12.3f}s {'1.0x':<12}")
print(f"{'F1 Binario batch single':<35} {dt_grid_bins:<12.3f}s {dt_grid_orig/dt_grid_bins:<12.1f}x")

# 10. F1 Binario com Threads
print("\n" + "="*80)
print("GRID SEARCH BATCH — THREADPOOL (96 combos, 4 workers)")
print("="*80)

from scripts.f1_binario_threads import run_f1_binario_threads

t0 = time.time()
top_results, stats = run_f1_binario_threads(
    M, ep_arr, atr_arr, sell_idx, TP_GRID, SL_GRID,
    direction=DIRECTION, n_workers=4, top_n=100
)
dt_threads = time.time() - t0

print(f"{'Metodo':<35} {'Tempo':<12} {'Speedup':<12}")
print("-"*60)
print(f"{'F1 Original (loop puro)':<35} {dt_grid_orig:<12.3f}s {'1.0x':<12}")
print(f"{'F1 Binario ThreadPool (4 workers)':<35} {dt_threads:<12.3f}s {dt_grid_orig/dt_threads:<12.1f}x")

print("\n" + "="*80)
print("BENCHMARK COMPLETE")
print("="*80)
