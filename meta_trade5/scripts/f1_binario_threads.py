"""
F1 Binario — Full Pipeline com ThreadPool + Heap Top-N
=======================================================
Versao thread-based (compartilha memoria nativamente, sem SharedMemory).
Numpy e Numba liberam o GIL, entao threads funcionam bem.

Arquitetura:
1. evaluate_combo(): numpy broadcast (libera GIL)
2. blocking_bitwise(): numba (libera GIL apos compilacao)
3. ThreadPoolExecutor: divide grid entre threads
4. Heap Top-N: mantem apenas melhores resultados
"""
import sys, os, time, heapq
import numpy as np
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import polars as pl
from datetime import datetime
from backtest.engine_v2 import BacktestEngine
from engines.f1_fast_screener import build_M_close
from engines.f1_binario import evaluate_combo

try:
    from numba import njit
except ImportError:
    def njit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

# =============================================================================
# NUMBA BLOCKING (libera GIL)
# =============================================================================
@njit(fastmath=True, nogil=True)
def blocking_bitwise_nogil(sell_idx, had, pnl, duration, n_candles, n_uint64):
    master_mask = np.zeros(n_uint64, dtype=np.uint64)
    total_pnl = 0.0
    total_trades = 0
    COST = 30
    idx_order = np.argsort(sell_idx)
    for ii in range(len(sell_idx)):
        i = idx_order[ii]
        if not had[i]:
            continue
        start = sell_idx[i] + 1
        end = start + duration[i]
        if end > n_candles:
            end = n_candles
        collision = False
        for c in range(start, end):
            word, bit = c // 64, c % 64
            if master_mask[word] & (np.uint64(1) << np.uint64(bit)):
                collision = True
                break
        if not collision:
            for c in range(start, end):
                word, bit = c // 64, c % 64
                master_mask[word] |= (np.uint64(1) << np.uint64(bit))
            total_pnl += pnl[i]
            total_trades += 1
    return int(total_pnl) - (total_trades * COST), total_trades


# =============================================================================
# WORKER THREAD
# =============================================================================
def worker_task(args):
    """Processa um chunk de combos em uma thread."""
    M, ep, atr, sell_idx, chunk, direction, n_candles, n_uint64, top_n, worker_id = args

    heap_local = []
    counter = 0
    t0 = time.time()

    for tp, sl in chunk:
        had, pnl, duration = evaluate_combo(M, ep, atr, sell_idx, tp, sl, direction)
        net, n_trades = blocking_bitwise_nogil(sell_idx, had, pnl, duration, n_candles, n_uint64)

        res = {'tp': float(tp), 'sl': float(sl), 'net': int(net), 'n': int(n_trades)}
        # Usar counter como tie-breaker para evitar comparar dicts
        if len(heap_local) < top_n:
            heapq.heappush(heap_local, (net, counter, res))
        elif net > heap_local[0][0]:
            heapq.heapreplace(heap_local, (net, counter, res))
        counter += 1

    dt = time.time() - t0
    print(f"  [Worker {worker_id}] {len(chunk)} combos em {dt:.2f}s ({len(chunk)/dt:.0f}/s)")
    return heap_local


# =============================================================================
# MAIN
# =============================================================================
def run_f1_binario_threads(M, ep, atr, sell_idx, tp_grid, sl_grid,
                           direction=-1, n_workers=4, top_n=1000):
    """Executa F1 Binario com ThreadPool + Heap Top-N."""

    n_candles = int(sell_idx.max()) + 50 + 2
    n_uint64 = (n_candles + 63) // 64
    total_combos = len(tp_grid) * len(sl_grid)

    print(f"\n[F1 Binario Threads]")
    print(f"  Total combos: {total_combos:,} | Workers: {n_workers} | Top-N: {top_n}")

    # Chunks
    all_combos = [(float(tp), float(sl)) for tp in tp_grid for sl in sl_grid]
    chunk_size = max(1, len(all_combos) // n_workers)
    chunks = [all_combos[i:i+chunk_size] for i in range(0, len(all_combos), chunk_size)]

    tasks = [(M, ep, atr, sell_idx, chunk, direction, n_candles, n_uint64, top_n, i)
             for i, chunk in enumerate(chunks)]

    # ThreadPool
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        all_heaps = list(executor.map(worker_task, tasks))
    dt = time.time() - t0

    # Merge heaps
    global_heap = []
    global_counter = 0
    for heap_local in all_heaps:
        for net, _, res in heap_local:
            if len(global_heap) < top_n:
                heapq.heappush(global_heap, (net, global_counter, res))
            elif net > global_heap[0][0]:
                heapq.heapreplace(global_heap, (net, global_counter, res))
            global_counter += 1

    top_results = [res for net, _, res in sorted(global_heap, key=lambda x: x[0], reverse=True)]

    stats = {
        'time_total': dt,
        'speed': total_combos / dt,
    }
    return top_results, stats


if __name__ == '__main__':
    print("="*80)
    print("F1 BINARIO — THREADPOOL + HEAP TOP-N")
    print("="*80)

    BASE = os.path.join(ROOT, 'data')
    SUPER = os.path.join(BASE, 'super_win_continuous.parquet')

    # Dados
    print("\n[1/3] Carregando dados...")
    df = pl.read_parquet(SUPER).filter(
        (pl.col('dt') >= datetime(2026, 2, 1)) & (pl.col('dt') < datetime(2026, 3, 1))
    )
    N = len(df)
    close_arr = df['close'].to_numpy().astype(np.float32)
    signal = df['PA_SIGNAL_DIR'].to_numpy().astype(np.int32)
    sell_idx = np.where(signal == 1)[0].astype(np.int32)
    ep = np.array([df['open'].to_numpy()[i+1] if i+1 < N else df['close'].to_numpy()[i] for i in sell_idx], dtype=np.float32)
    atr = df['ATR'].to_numpy().astype(np.float32)[sell_idx]

    print(f"  Candles: {N} | Entradas BUY: {len(sell_idx)}")

    # Ticks
    print("\n[2/3] Construindo matriz M...")
    win = pl.read_parquet(os.path.join(BASE, 'WIN_merged_all.parquet'))
    win = win.with_columns(pl.from_epoch(pl.col('time_msc')//1000, time_unit='s').alias('dt'))
    fev = win.filter(pl.col('dt').dt.month() == 2).filter(pl.col('dt').dt.year() == 2026).sort('time_msc')
    tick_last = fev['last'].to_numpy().astype(np.float32)
    eng = BacktestEngine(None)
    eng.df = df
    eng.load_ticks_for_simulation(fev)
    M, closes = build_M_close(tick_last, eng.tick_idx, sell_idx, N, close_arr)
    print(f"  M: {M.shape}")

    # Grid
    TP_GRID = np.array([1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 15.0, 20.0])
    SL_GRID = np.array([0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0])

    # Rodar
    print("\n[3/3] Executando F1 Binario (threads)...")
    top_results, stats = run_f1_binario_threads(
        M, ep, atr, sell_idx, TP_GRID, SL_GRID,
        direction=1, n_workers=4, top_n=100
    )

    print("\n" + "="*80)
    print("RESULTADOS")
    print("="*80)
    print(f"Tempo total: {stats['time_total']:.2f}s")
    print(f"Velocidade: {stats['speed']:.0f} combos/s")
    print(f"\nTop 10:")
    print(f"{'Rank':>4} {'TP':>6} {'SL':>6} {'PnL':>12} {'Trades':>8}")
    print("-"*45)
    for i, r in enumerate(top_results[:10]):
        print(f"{i+1:4} {r['tp']:6.1f} {r['sl']:6.1f} {r['net']:>+12,} {r['n']:8}")
    print("\n" + "="*80)
