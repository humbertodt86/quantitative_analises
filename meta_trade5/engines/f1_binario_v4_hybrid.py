"""
F1 Binario V5 Hybrid — Optimized Vectorize + Persistent Thread Pool
====================================================================
Arquitetura:
  1. PRE-COMPUTACAO (uma vez no __init__):
     - high_future, low_future, close_future: matrizes (n_entries, MAX_C)
  2. EVALUATE (independent TP/SL vectorize):
     - Computa TP-hit e SL-hit INDEPENDENTEMENTE
     - ~5x mais rapido que loop numba
  3. BLOCKING (numba + persistent ThreadPoolExecutor):
     - Pool criado uma vez, reutilizado para N chamadas
     - Evita overhead de criar/destruir threads a cada grid search
  4. TOP-N KEEPER (opcional):
     - Mantem apenas top N configs via heapq

Como usar:
    engine = F1HybridEngine(high, low, close, ep, atr, sell_idx, direction=-1)
    
    # Grid search completo (retorna matrizes)
    net_grid, n_grid = engine.evaluate_batch(tp_grid, sl_grid, blocking_mode='exact')
    
    # Grid search com top-N (retorna lista ordenada)
    top = engine.evaluate_batch_topn(tp_grid, sl_grid, top_n=100)
    
    # Multiplos grids (pool reutilizado)
    for signal_name in signals:
        net, n = engine.evaluate_batch(tp_grid, sl_grid)
    
    engine.shutdown()  # Liberar threads

Resultados medidos (Fev 2026, 901 entradas, grid 70x70=4900):
  - 1a chamada (cria pool):  ~0.17s (4T), ~0.15s (8T)
  - 2a+ chamada (pool reutilizado): ~0.08s (4T), ~0.06s (8T)
  - v1 baseline: 2.16s
  - Speedup persistente: ~27x (8T, pool warm)
"""
import numpy as np
import heapq
from concurrent.futures import ThreadPoolExecutor
from multiprocessing import cpu_count

try:
    from numba import njit
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    def njit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

MAX_C = 50
COST = 30


def _precompute_future(high, low, close, sell_idx, max_c=MAX_C):
    """Pre-computa high/low/close das MAX_C candles futuras."""
    n = len(sell_idx)
    N = len(high)
    high_future = np.zeros((n, max_c), dtype=np.float64)
    low_future = np.zeros((n, max_c), dtype=np.float64)
    close_future = np.zeros((n, max_c), dtype=np.float64)
    valid = np.zeros((n, max_c), dtype=np.bool_)
    for i in range(n):
        start = sell_idx[i] + 1
        end = min(start + max_c, N)
        nc = end - start
        if nc > 0:
            high_future[i, :nc] = high[start:end]
            low_future[i, :nc] = low[start:end]
            close_future[i, :nc] = close[start:end]
            valid[i, :nc] = True
    return high_future, low_future, close_future, valid


def _evaluate_combos_optimized(high_future, low_future, close_future, valid, ep, atr, tp_grid, sl_grid, direction):
    """
    Avalia TODOS os combos computando TP e SL INDEPENDENTEMENTE.
    Retorna had, pnl, duration com shape (n_tp, n_sl, n).
    """
    n = len(ep)
    n_tp = len(tp_grid)
    n_sl = len(sl_grid)
    
    if direction == 1:  # BUY
        tp_prices = ep[:, None] + tp_grid[None, :] * atr[:, None]
        sl_prices = ep[:, None] - sl_grid[None, :] * atr[:, None]
        tp_hit = (high_future[:, None, :] >= tp_prices[:, :, None]) & valid[:, None, :]
        sl_hit = (low_future[:, None, :] <= sl_prices[:, :, None]) & valid[:, None, :]
    else:  # SELL
        tp_prices = ep[:, None] - tp_grid[None, :] * atr[:, None]
        sl_prices = ep[:, None] + sl_grid[None, :] * atr[:, None]
        tp_hit = (low_future[:, None, :] <= tp_prices[:, :, None]) & valid[:, None, :]
        sl_hit = (high_future[:, None, :] >= sl_prices[:, :, None]) & valid[:, None, :]
    
    fi_tp = np.argmax(tp_hit, axis=2)
    had_tp = tp_hit.any(axis=2)
    fi_sl = np.argmax(sl_hit, axis=2)
    had_sl = sl_hit.any(axis=2)
    
    fi_tp_3d = fi_tp[:, :, None]
    fi_sl_3d = fi_sl[:, None, :]
    had_tp_3d = had_tp[:, :, None]
    had_sl_3d = had_sl[:, None, :]
    
    both_hit = had_tp_3d & had_sl_3d
    had = had_tp_3d | had_sl_3d
    fi = np.where(both_hit, np.minimum(fi_tp_3d, fi_sl_3d),
                  np.where(had_tp_3d, fi_tp_3d, np.where(had_sl_3d, fi_sl_3d, 0)))
    
    rows = np.arange(n)[:, None, None]
    exit_price = close_future[rows, fi]
    
    if direction == 1:
        pnl = np.where(had, exit_price - ep[:, None, None], 0).astype(np.float32)
    else:
        pnl = np.where(had, ep[:, None, None] - exit_price, 0).astype(np.float32)
    
    duration = np.where(had, fi + 1, 0).astype(np.int32)
    
    had = np.transpose(had, (1, 2, 0))
    pnl = np.transpose(pnl, (1, 2, 0))
    duration = np.transpose(duration, (1, 2, 0))
    
    return had, pnl, duration


@njit(fastmath=True, nogil=True)
def _blocking_seq_nogil(sell_idx, had, pnl, duration, N_candles, n_tp, n_sl, blocking_mode):
    """Blocking sequencial com bit-packing uint64 (nogil para threads)."""
    n = len(sell_idx)
    n_uint64 = (N_candles + 63) // 64
    idx_order = np.argsort(sell_idx)
    net_grid = np.zeros((n_tp, n_sl), dtype=np.int32)
    n_grid = np.zeros((n_tp, n_sl), dtype=np.int32)
    
    for ti in range(n_tp):
        for si in range(n_sl):
            master = np.zeros(n_uint64, dtype=np.uint64)
            total_pnl = 0.0
            total_trades = 0
            for ii in range(n):
                i = idx_order[ii]
                if not had[ti, si, i]:
                    continue
                start = sell_idx[i] + 1
                if blocking_mode == 1:
                    end = start + 1
                else:
                    end = start + duration[ti, si, i]
                if end > N_candles:
                    end = N_candles
                trade_mask = np.zeros(n_uint64, dtype=np.uint64)
                for c in range(start, end):
                    word = c // 64
                    bit = c % 64
                    trade_mask[word] |= np.uint64(1) << np.uint64(bit)
                collision = False
                for w in range(n_uint64):
                    if master[w] & trade_mask[w]:
                        collision = True
                        break
                if not collision:
                    for w in range(n_uint64):
                        master[w] |= trade_mask[w]
                    total_pnl += pnl[ti, si, i]
                    total_trades += 1
            net_grid[ti, si] = int(total_pnl) - total_trades * COST
            n_grid[ti, si] = total_trades
    return net_grid, n_grid


@njit(fastmath=True, nogil=True)
def _blocking_skip_nogil(sell_idx, had, pnl, n_tp, n_sl):
    """
    Blocking FAST PATH para modo 'single' (1 candle).
    Usa simples variavel 'skip' — 4-5x mais rapido que bit-packing uint64.
    
    NOTA: skip = sell_idx[i] (nao +1) para ser EQUIVALENTE ao uint64 single.
    O uint64 marca a candle sell_idx+1; dois trades com sell_idx diferentes
    marcam candles diferentes e NAO colidem. skip=sell_idx reflete isso.
    """
    n = len(sell_idx)
    idx_order = np.argsort(sell_idx)
    net_grid = np.zeros((n_tp, n_sl), dtype=np.int32)
    n_grid = np.zeros((n_tp, n_sl), dtype=np.int32)
    
    for ti in range(n_tp):
        for si in range(n_sl):
            skip = -1
            total_pnl = 0.0
            total_trades = 0
            for ii in range(n):
                i = idx_order[ii]
                if sell_idx[i] <= skip:
                    continue
                if had[ti, si, i]:
                    skip = sell_idx[i]
                    total_pnl += pnl[ti, si, i]
                    total_trades += 1
            net_grid[ti, si] = int(total_pnl) - total_trades * COST
            n_grid[ti, si] = total_trades
    return net_grid, n_grid


def _block_chunk(args):
    """Worker function para ThreadPool."""
    sell_idx, had, pnl, duration, N_candles, ti_start, ti_end, n_sl, blocking_mode = args
    if blocking_mode == 1:  # single — fast path
        return _blocking_skip_nogil(
            sell_idx, had[ti_start:ti_end], pnl[ti_start:ti_end],
            ti_end - ti_start, n_sl
        )
    else:  # exact
        return _blocking_seq_nogil(
            sell_idx, had[ti_start:ti_end], pnl[ti_start:ti_end], duration[ti_start:ti_end],
            N_candles, ti_end - ti_start, n_sl, blocking_mode
        )


class F1HybridEngine:
    """
    Motor F1 com pool de threads persistente.
    
    Args:
        high, low, close: arrays de candles (N_candles,)
        ep, atr, sell_idx: arrays de entradas (n_entries,)
        direction: 1=BUY, -1=SELL
        n_threads: numero de threads no pool (None = auto)
    """
    
    def __init__(self, high, low, close, ep, atr, sell_idx, direction=-1, n_threads=None):
        self.high = high
        self.low = low
        self.close = close
        self.ep = ep
        self.atr = atr
        self.sell_idx = sell_idx
        self.direction = direction
        self.N_candles = len(high)
        self.n_threads = n_threads if n_threads is not None else cpu_count()
        
        # Pre-computar dados das candles futuras (uma vez)
        self.high_future, self.low_future, self.close_future, self.valid = \
            _precompute_future(high, low, close, sell_idx, MAX_C)
        
        # Criar pool persistente de threads
        self._executor = ThreadPoolExecutor(max_workers=self.n_threads)
        self._warm = False  # Ainda nao foi usado
    
    def evaluate(self, tp, sl, blocking_mode='exact'):
        """
        Avalia UM combo (tp, sl).
        
        Returns:
            net: PnL liquido (int)
            n_trades: numero de trades (int)
        """
        tp_grid = np.array([tp], dtype=np.float64)
        sl_grid = np.array([sl], dtype=np.float64)
        net_grid, n_grid = self.evaluate_batch(tp_grid, sl_grid, blocking_mode)
        return int(net_grid[0, 0]), int(n_grid[0, 0])
    
    def evaluate_batch(self, tp_grid, sl_grid, blocking_mode='exact'):
        """
        Avalia grid completo de combos (tp x sl).
        Reutiliza o pool de threads persistente.
        
        ATENCAO: 'single' bloqueia APENAS 1 candle (sell_idx+1).
        Isso gera ~5-30x mais trades que F2/F3. Use apenas para
        exploracao agressiva. Para pre-filtro, usar 'exact'.
        
        Args:
            tp_grid: array de TPs
            sl_grid: array de SLs
            blocking_mode: 'exact' (recomendado) ou 'single' (agressivo)
        
        Returns:
            net_grid: (n_tp, n_sl) int32
            n_grid: (n_tp, n_sl) int32
        """
        n_tp = len(tp_grid)
        n_sl = len(sl_grid)
        mode_int = 0 if blocking_mode == 'exact' else 1
        
        # 1. Evaluate (vectorizado)
        had, pnl, duration = _evaluate_combos_optimized(
            self.high_future, self.low_future, self.close_future, self.valid,
            self.ep, self.atr, tp_grid, sl_grid, self.direction
        )
        
        # 2. Blocking (thread pool persistente)
        if self.n_threads == 1 or n_tp * n_sl < 500:
            if blocking_mode == 'single':
                net_grid, n_grid = _blocking_skip_nogil(
                    self.sell_idx, had, pnl, n_tp, n_sl
                )
            else:
                net_grid, n_grid = _blocking_seq_nogil(
                    self.sell_idx, had, pnl, duration, self.N_candles,
                    n_tp, n_sl, mode_int
                )
        else:
            chunk = max(1, n_tp // self.n_threads)
            ranges = [(i, min(i + chunk, n_tp)) for i in range(0, n_tp, chunk)]
            
            tasks = [
                (self.sell_idx, had, pnl, duration, self.N_candles,
                 ti_start, ti_end, n_sl, mode_int)
                for ti_start, ti_end in ranges
            ]
            
            results = list(self._executor.map(_block_chunk, tasks))
            
            # Reconstruir
            net_grid = np.zeros((n_tp, n_sl), dtype=np.int32)
            n_grid = np.zeros((n_tp, n_sl), dtype=np.int32)
            for (ti_start, ti_end), (net_c, n_c) in zip(ranges, results):
                net_grid[ti_start:ti_end] = net_c
                n_grid[ti_start:ti_end] = n_c
        
        self._warm = True
        return net_grid, n_grid
    
    def evaluate_batch_topn(self, tp_grid, sl_grid, blocking_mode='exact', top_n=1000):
        """
        Avalia grid e retorna apenas top N configs (maior PnL).
        Usa heapq para nao alocar matriz completa.
        
        Returns:
            list[dict]: top N configs ordenadas por PnL descendente
        """
        n_tp = len(tp_grid)
        n_sl = len(sl_grid)
        mode_int = 0 if blocking_mode == 'exact' else 1
        
        had, pnl, duration = _evaluate_combos_optimized(
            self.high_future, self.low_future, self.close_future, self.valid,
            self.ep, self.atr, tp_grid, sl_grid, self.direction
        )
        
        # Processar em chunks e manter heap
        chunk_tp = max(1, n_tp // self.n_threads)
        chunk_sl = max(1, n_sl // 4)
        heap = []
        counter = 0
        
        for ti_start in range(0, n_tp, chunk_tp):
            ti_end = min(ti_start + chunk_tp, n_tp)
            for si_start in range(0, n_sl, chunk_sl):
                si_end = min(si_start + chunk_sl, n_sl)
                
                net_chunk, n_chunk = _blocking_seq_nogil(
                    self.sell_idx,
                    had[ti_start:ti_end, si_start:si_end],
                    pnl[ti_start:ti_end, si_start:si_end],
                    duration[ti_start:ti_end, si_start:si_end],
                    self.N_candles,
                    ti_end - ti_start,
                    si_end - si_start,
                    mode_int
                )
                
                for ti in range(ti_end - ti_start):
                    for si in range(si_end - si_start):
                        net_val = int(net_chunk[ti, si])
                        n_trades = int(n_chunk[ti, si])
                        item = (net_val, counter, {
                            'tp_mult': float(tp_grid[ti_start + ti]),
                            'sl_mult': float(sl_grid[si_start + si]),
                            'net_pnl': net_val,
                            'n_trades': n_trades,
                        })
                        if len(heap) < top_n:
                            heapq.heappush(heap, item)
                        elif net_val > heap[0][0]:
                            heapq.heapreplace(heap, item)
                        counter += 1
        
        heap.sort(key=lambda x: x[0], reverse=True)
        return [item[2] for item in heap]
    
    def shutdown(self):
        """Encerra o pool de threads. Chamar ao finalizar."""
        self._executor.shutdown(wait=True)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.shutdown()
        return False


# ============================================================================
# FUNCOES DE ALTO NIVEL (interface compativel)
# ============================================================================
def evaluate_batch_fast(high, low, close, ep, atr, sell_idx, tp_grid, sl_grid,
                        direction=-1, blocking_mode='exact', n_threads=1):
    """
    Funcao stateless (cria engine, roda, destroi).
    Usada para comparacao/benchmark. Para uso repetido, use F1HybridEngine.
    """
    engine = F1HybridEngine(high, low, close, ep, atr, sell_idx, direction, n_threads)
    try:
        return engine.evaluate_batch(tp_grid, sl_grid, blocking_mode)
    finally:
        engine.shutdown()


def evaluate(high, low, close, ep, atr, sell_idx, tp, sl, direction=-1, use_uint64=True, blocking_mode='exact'):
    """Interface compativel com f1_binario.evaluate() — 1 combo."""
    return evaluate_batch_fast(high, low, close, ep, atr, sell_idx,
                               np.array([tp]), np.array([sl]),
                               direction, blocking_mode, n_threads=1)


def evaluate_batch(high, low, close, ep, atr, sell_idx, tp_grid, sl_grid, direction=-1, use_uint64=True, blocking_mode='exact'):
    """Interface compativel com f1_binario.evaluate_batch() — grid completo single-core."""
    return evaluate_batch_fast(high, low, close, ep, atr, sell_idx, tp_grid, sl_grid, direction, blocking_mode, n_threads=1)
