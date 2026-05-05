"""
F1 OHLC — Fast Screener usando High/Low Real
=============================================
Versao mais rapida e fiel ao F2/F3.

Em vez de 15 samples aleatorios, usa os 4 valores reais de cada candle:
- open, high, low, close

Vantagens:
1. NUNCA perde uma saida (se TP/SL esta entre low e high, detecta)
2. PnL calculado no THRESHOLD (SL ou TP), nao no tick sampleado
3. ~4x mais rapido (4 valores/candle vs 15 samples)
4. Blocking identico ao F2 (duracao real em candles)

Arquitetura:
-----------
1. build_M_ohlc(): constroi matriz de high/low para N candles futuras
2. evaluate_ohlc(): numpy broadcast → detecta hit, calcula PnL no threshold
3. blocking_ohlc(): numba bitwise → blocking com duracao real

Interface:
---------
evaluate(M_hl, ep, atr, sell_idx, tp, sl, direction=-1, blocking_mode='exact')

M_hl: (n_entries, MAX_C, 2) — [low, high] de cada candle futura
"""
import numpy as np

try:
    from numba import njit
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    def njit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

MAX_C = 50    # Maximo de candles futuras
COST = 30     # Custo fixo por trade


def build_M_ohlc(high_arr, low_arr, sell_idx, N_candles):
    """
    Constroi matriz M_hl com high/low de cada candle futura.

    Args:
        high_arr: (N_candles,) — high de cada candle
        low_arr: (N_candles,) — low de cada candle
        sell_idx: (n_entries,) — indices das candles de entrada
        N_candles: total de candles

    Returns:
        M_hl: (n_entries, MAX_C, 2) — [low, high] de cada candle futura
              M_hl[i, j, 0] = low da candle (sell_idx[i] + j + 1)
              M_hl[i, j, 1] = high da candle (sell_idx[i] + j + 1)
    """
    n_entries = len(sell_idx)
    M_hl = np.zeros((n_entries, MAX_C, 2), dtype=np.float32)

    for idx, i in enumerate(sell_idx):
        for ck, j in enumerate(range(i + 1, min(i + MAX_C + 1, N_candles))):
            M_hl[idx, ck, 0] = low_arr[j]   # low
            M_hl[idx, ck, 1] = high_arr[j]  # high

    return M_hl


def evaluate_ohlc(M_hl, ep, atr, sell_idx, tp, sl, direction=-1):
    """
    Avalia UMA config (tp, sl) usando high/low real.

    Logica:
    - Para cada entrada, verifica se TP ou SL e atingido em cada candle futura
    - TP atingido: high >= tp_th (BUY) ou low <= tp_th (SELL)
    - SL atingido: low <= sl_th (BUY) ou high >= sl_th (SELL)
    - PnL = tp_pts (ganho) ou -sl_pts (perda) — calculado no threshold

    Args:
        M_hl: (n_entries, MAX_C, 2) — [low, high]
        ep: (n_entries,) — precos de entrada
        atr: (n_entries,) — ATR
        sell_idx: (n_entries,) — indices de entrada
        tp, sl: multiplicadores
        direction: -1 = SELL, 1 = BUY

    Returns:
        had: (n_entries,) bool — teve exit?
        pnl: (n_entries,) float32 — PnL bruto (threshold)
        duration: (n_entries,) int32 — duracao em candles
    """
    n = len(ep)

    tp_pts = tp * atr
    sl_pts = sl * atr

    if direction == -1:  # SELL
        sl_th = ep + sl_pts
        tp_th = ep - tp_pts
        # SL: high >= sl_th, TP: low <= tp_th
        sl_hit = M_hl[:, :, 1] >= sl_th[:, None]   # high >= sl
        tp_hit = M_hl[:, :, 0] <= tp_th[:, None]   # low <= tp
    else:  # BUY
        sl_th = ep - sl_pts
        tp_th = ep + tp_pts
        # SL: low <= sl_th, TP: high >= tp_th
        sl_hit = M_hl[:, :, 0] <= sl_th[:, None]   # low <= sl
        tp_hit = M_hl[:, :, 1] >= tp_th[:, None]   # high >= tp

    hit = sl_hit | tp_hit
    had = hit.any(axis=1)

    # Primeira candle com hit
    fi = np.argmax(hit, axis=1)

    # PnL: no threshold (SL ou TP), nao no tick
    pnl = np.zeros(n, dtype=np.float32)
    was_sl = sl_hit[np.arange(n), fi]

    if direction == -1:  # SELL
        pnl[had & was_sl] = -sl_pts[had & was_sl]   # SL: perda = -sl_pts
        pnl[had & ~was_sl] = tp_pts[had & ~was_sl]  # TP: ganho = +tp_pts
    else:  # BUY
        pnl[had & was_sl] = -sl_pts[had & was_sl]   # SL: perda = -sl_pts
        pnl[had & ~was_sl] = tp_pts[had & ~was_sl]  # TP: ganho = +tp_pts

    # Duracao: fi + 1 (candles contadas de 1)
    duration = np.zeros(n, dtype=np.int32)
    duration[had] = fi[had] + 1

    return had, pnl, duration


@njit(fastmath=True)
def blocking_ohlc(sell_idx, had, pnl, duration, N_candles, blocking_mode=1):
    """
    Blocking sequencial com duracao real (compativel F2/F3).

    Args:
        sell_idx: (n_entries,)
        had: (n_entries,) bool
        pnl: (n_entries,) float32
        duration: (n_entries,) int32
        N_candles: total de candles
        blocking_mode: 0 = exact (duracao real), 1 = single (1 candle)

    Returns:
        net: PnL liquido
        n_trades: numero de trades
    """
    n = len(sell_idx)
    idx_order = np.argsort(sell_idx)

    n_uint64 = (N_candles + 63) // 64
    master = np.zeros(n_uint64, dtype=np.uint64)

    total_pnl = 0.0
    total_trades = 0

    for ii in range(n):
        i = idx_order[ii]
        if not had[i]:
            continue

        start = sell_idx[i] + 1
        if blocking_mode == 1:
            end = start + 1
        else:
            end = start + duration[i]
        if end > N_candles:
            end = N_candles

        # Criar mascara
        trade_mask = np.zeros(n_uint64, dtype=np.uint64)
        for c in range(start, end):
            word = c // 64
            bit = c % 64
            trade_mask[word] |= np.uint64(1) << np.uint64(bit)

        # Verificar colisao
        collision = False
        for w in range(n_uint64):
            if master[w] & trade_mask[w]:
                collision = True
                break

        if not collision:
            for w in range(n_uint64):
                master[w] |= trade_mask[w]
            total_pnl += pnl[i]
            total_trades += 1

    return int(total_pnl) - total_trades * COST, total_trades


def evaluate(M_hl, ep, atr, sell_idx, tp, sl, direction=-1, blocking_mode='exact'):
    """
    Interface unificada para F1 OHLC.

    Args:
        M_hl: (n_entries, MAX_C, 2) — matriz high/low
        ep, atr, sell_idx: arrays
        tp, sl: multiplicadores
        direction: -1 ou 1
        blocking_mode: 'exact' = duracao real (compativel F2),
                       'single' = 1 candle

    Returns:
        net: PnL liquido
        n_trades: numero de trades
    """
    had, pnl, duration = evaluate_ohlc(M_hl, ep, atr, sell_idx, tp, sl, direction)
    N_candles = int(sell_idx.max()) + MAX_C + 2
    mode_int = 0 if blocking_mode == 'exact' else 1
    return blocking_ohlc(sell_idx, had, pnl, duration, N_candles, mode_int)


def evaluate_batch(M_hl, ep, atr, sell_idx, tp_grid, sl_grid, direction=-1, blocking_mode='exact'):
    """
    Avalia grid TP×SL completo.

    Returns:
        net_grid: (n_tp, n_sl) — PnL por combo
        n_grid: (n_tp, n_sl) — trades por combo
    """
    n_tp = len(tp_grid)
    n_sl = len(sl_grid)
    net_grid = np.zeros((n_tp, n_sl), dtype=np.int32)
    n_grid = np.zeros((n_tp, n_sl), dtype=np.int32)

    N_candles = int(sell_idx.max()) + MAX_C + 2
    mode_int = 0 if blocking_mode == 'exact' else 1

    for i, tp in enumerate(tp_grid):
        for j, sl in enumerate(sl_grid):
            had, pnl, duration = evaluate_ohlc(M_hl, ep, atr, sell_idx, tp, sl, direction)
            net, n_trades = blocking_ohlc(sell_idx, had, pnl, duration, N_candles, mode_int)
            net_grid[i, j] = net
            n_grid[i, j] = n_trades

    return net_grid, n_grid
