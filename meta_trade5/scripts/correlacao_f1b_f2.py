"""
Correlacao de Rankeamento F1b vs F2
====================================
Avalia se F1b e F2 rankeiam configs na mesma ordem.
Se correlacao > 0.7, F1b serve como pre-filtro.
"""
import sys, os, time
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import polars as pl
from datetime import datetime
from backtest.engine_v2 import BacktestEngine
from engines.f1_fast_screener import build_M_close
from engines.f1_binario import evaluate as evaluate_binario
from engines.f2_optimization_v87 import backtest_f2_numba

BASE = os.path.join(ROOT, 'data')
SUPER = os.path.join(BASE, 'super_win_continuous.parquet')
SINAL = 'PA_SIGNAL_DIR'

print("="*80)
print("CORRELACAO DE RANKEAMENTO F1b vs F2")
print("="*80)

# 1. Carregar dados
print("\n[1/2] Carregando dados...")
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

# Ticks para F1b
win = pl.read_parquet(os.path.join(BASE, 'WIN_merged_all.parquet'))
win = win.with_columns(pl.from_epoch(pl.col('time_msc')//1000, time_unit='s').alias('dt'))
fev = win.filter(pl.col('dt').dt.month() == 2).filter(pl.col('dt').dt.year() == 2026).sort('time_msc')
tick_last = fev['last'].to_numpy().astype(np.float32)
eng = BacktestEngine(None)
eng.df = df
eng.load_ticks_for_simulation(fev)
M, closes = build_M_close(tick_last, eng.tick_idx, sell_idx, N, close_arr.astype(np.float32), incluir_extremos=False)
print(f"  M: {M.shape}")

# 2. Grid de teste
print("\n[2/2] Avaliando grid...")
TP_GRID = np.array([1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0])
SL_GRID = np.array([0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0])
DIRECTION = 1

results_f1b = []
results_f2 = []

for tp in TP_GRID:
    for sl in SL_GRID:
        # F1b
        net_f1b, n_f1b = evaluate_binario(M, ep, atr, sell_idx, tp, sl, direction=DIRECTION, use_uint64=True, blocking_mode='single')
        results_f1b.append((tp, sl, net_f1b, n_f1b))

        # F2
        net_f2, n_f2, wins_f2 = backtest_f2_numba(
            close_arr, high_arr, low_arr, atr_arr, signal,
            tp, sl, 0, 99999,
            1.0, 1.0, 999.0,
            zeros, zeros,
            zeros, zeros,
            0.0, -999.0,
            999999, 999, 0,
            99, 0.0,
            DIRECTION
        )
        results_f2.append((tp, sl, net_f2, n_f2))

# 3. Correlacao
print("\n" + "="*80)
print("RESULTADOS")
print("="*80)

# Ordenar por PnL
results_f1b.sort(key=lambda x: x[2], reverse=True)
results_f2.sort(key=lambda x: x[2], reverse=True)

# Criar rankings
f1b_rank = { (r[0], r[1]): i for i, r in enumerate(results_f1b) }
f2_rank = { (r[0], r[1]): i for i, r in enumerate(results_f2) }

# Calcular Spearman correlation
from scipy.stats import spearmanr

keys = [(r[0], r[1]) for r in results_f1b]
f1b_scores = [r[2] for r in results_f1b]
f2_scores = [next(r[2] for r in results_f2 if r[0]==k[0] and r[1]==k[1]) for k in keys]

corr_spearman, p_value = spearmanr(f1b_scores, f2_scores)

print(f"Total configs: {len(results_f1b)}")
print(f"Correlacao Spearman: {corr_spearman:.3f} (p={p_value:.4f})")

# Top 5 de cada um
print(f"\nTop 5 F1b:")
for i, r in enumerate(results_f1b[:5]):
    print(f"  {i+1}. TP={r[0]:.1f} SL={r[1]:.1f} PnL={r[2]:+12,} N={r[3]}")

print(f"\nTop 5 F2:")
for i, r in enumerate(results_f2[:5]):
    print(f"  {i+1}. TP={r[0]:.1f} SL={r[1]:.1f} PnL={r[2]:+12,} N={r[3]}")

# Overlap top 10
top_f1b = set((r[0], r[1]) for r in results_f1b[:10])
top_f2 = set((r[0], r[1]) for r in results_f2[:10])
overlap = len(top_f1b & top_f2)
print(f"\nOverlap Top 10: {overlap}/10 ({overlap*10}%)")

if abs(corr_spearman) > 0.7:
    print(f"\n!!! F1b tem correlacao forte com F2 (|rho|={abs(corr_spearman):.3f})")
    if corr_spearman > 0:
        print("    Mesma direcao — serve como pre-filtro")
    else:
        print("    DIRECAO OPOSTA — NAO serve como pre-filtro!")
else:
    print(f"\n!!! F1b tem correlacao fraca com F2 (|rho|={abs(corr_spearman):.3f})")

print("\n" + "="*80)
print("CORRELACAO COMPLETE")
print("="*80)
