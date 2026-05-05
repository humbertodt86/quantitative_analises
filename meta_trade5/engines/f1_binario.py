"""
F1 Binario — Fast Screener com Blocking Bitwise
================================================
Cada trade e um vetor binario (0/1) de candles ocupadas.
Blocking via operacoes bitwise (AND/OR) — extremamente rapido.

Vantagens:
- Blocking em O(1) por trade via operacoes bitwise (uint64)
- Duração real do trade (N candles) OU 1 candle fixo (compatível F1/F2/F3)
- Facil escalonamento para milhoes de combos

Arquitetura:
-----------
1. evaluate_combo(): vetorizado numpy — calcula SL/TP hit, PnL, duração em candles
2. blocking_binario_uint64(): numba sequencial — bit-packing uint64, AND/OR
3. evaluate_batch(): loop sobre grid de TP/SL, reusa evaluate_combo()

Modos de Blocking:
------------------
- 'exact': marca as candles REALMENTE ocupadas pelo trade ([sell_idx+1, sell_idx+duration])
- 'single': marca apenas 1 candle (sell_idx+1), identico ao F1 Original/F2/F3

Bit-Packing:
------------
Cada candle = 1 bit. 64 candles = 1 uint64.
Para 108 candles (dia WIN M5): apenas 2 uint64 por trade.
Colisao = (master & trade_mask) != 0 → resolvido em 2 operacoes CPU.

Interface compativel com f1_fast_screener.evaluate():
    evaluate(M, ep, atr, sell_idx, tp, sl, direction=-1, blocking_mode='single')
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

SAMP = 15
MAX_C = 50
N_SAMPLES = MAX_C * SAMP
COST = 30


def evaluate_combo(M, ep, atr, sell_idx, tp, sl, direction=-1):
    """
    Avalia UMA config (tp, sl) via broadcast numpy.
    Retorna had, pnl, duration (em candles).

    Args:
        M: (n_entries, N_SAMPLES) — sampled last ticks
        ep: (n_entries,) — precos de entrada
        atr: (n_entries,) — ATR na entrada
        sell_idx: (n_entries,) — indices das candles de entrada
        tp, sl: multiplicadores
        direction: -1 = SELL, 1 = BUY

    Returns:
        had: (n_entries,) bool — teve exit?
        pnl: (n_entries,) float32 — PnL bruto
        duration: (n_entries,) int32 — duracao em candles (1..MAX_C)
    """
    n = len(ep)

    tp_pts = tp * atr
    sl_pts = sl * atr

    if direction == -1:  # SELL
        sl_th = ep + sl_pts
        tp_th = ep - tp_pts
        sl_hit = M >= sl_th[:, None]
        tp_hit = M <= tp_th[:, None]
    else:  # BUY
        sl_th = ep - sl_pts
        tp_th = ep + tp_pts
        sl_hit = M <= sl_th[:, None]
        tp_hit = M >= tp_th[:, None]

    hit = sl_hit | tp_hit
    fi = np.argmax(hit, axis=1)
    rows = np.arange(n)
    had = hit.any(axis=1)

    # PnL: preco real do sample que cruzou
    pnl = np.zeros(n, dtype=np.float32)
    cross_price = M[rows, fi]
    if direction == -1:
        pnl[had] = ep[had] - cross_price[had]
    else:
        pnl[had] = cross_price[had] - ep[had]

    # Duracao em candles: fi // SAMP + 1, limitado a MAX_C
    duration = np.zeros(n, dtype=np.int32)
    duration[had] = np.minimum(fi[had] // SAMP + 1, MAX_C)

    return had, pnl, duration


@njit(fastmath=True)
def blocking_binario_uint64(sell_idx, had, pnl, duration, N_candles, blocking_mode=1):
    """
    Blocking sequencial com bit-packing em uint64.

    Cada candle = 1 bit. Verificacao de colisao via AND bit-a-bit.
    Para 108 candles (dia WIN M5): apenas 2 uint64.

    Args:
        sell_idx: (n_entries,) — indices das candles de entrada
        had: (n_entries,) bool — teve exit?
        pnl: (n_entries,) float32 — PnL bruto
        duration: (n_entries,) int32 — duracao em candles
        N_candles: total de candles no periodo
        blocking_mode: 0 = exact (duracao real), 1 = single (1 candle, compativel F1)

    Returns:
        net: PnL liquido (com COST=30)
        n_trades: numero de trades aceitos
    """
    n = len(sell_idx)
    idx_order = np.argsort(sell_idx)

    # Numero de uint64 necessarios para cobrir N_candles
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
            # Modo 'single': bloqueia apenas 1 candle (identico ao F1 Original)
            end = start + 1
        else:
            # Modo 'exact': bloqueia a duracao real do trade
            end = start + duration[i]
        if end > N_candles:
            end = N_candles

        # Criar mascara do trade (quais bits acender)
        trade_mask = np.zeros(n_uint64, dtype=np.uint64)
        for c in range(start, end):
            word = c // 64
            bit = c % 64
            trade_mask[word] |= np.uint64(1) << np.uint64(bit)

        # Verificar colisao: (master & trade_mask) != 0 ?
        collision = False
        for w in range(n_uint64):
            if master[w] & trade_mask[w]:
                collision = True
                break

        if not collision:
            # Aceitar trade: OR na mascara mestre
            for w in range(n_uint64):
                master[w] |= trade_mask[w]
            total_pnl += pnl[i]
            total_trades += 1

    return int(total_pnl) - total_trades * COST, total_trades


@njit(fastmath=True)
def blocking_binario_uint8(sell_idx, had, pnl, duration, N_candles, blocking_mode=1):
    """
    Blocking sequencial com array uint8 (0/1) — versao simples sem bit-packing.
    Usada para comparacao de velocidade.
    """
    n = len(sell_idx)
    idx_order = np.argsort(sell_idx)
    master = np.zeros(N_candles, dtype=np.uint8)

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

        # Verificar colisao
        collision = False
        for c in range(start, end):
            if master[c] != 0:
                collision = True
                break

        if not collision:
            for c in range(start, end):
                master[c] = 1
            total_pnl += pnl[i]
            total_trades += 1

    return int(total_pnl) - total_trades * COST, total_trades


def evaluate(M, ep, atr, sell_idx, tp, sl, direction=-1, use_uint64=True, blocking_mode='single'):
    """
    Interface compativel com f1_fast_screener.evaluate().

    Args:
        M, ep, atr, sell_idx: arrays do F1
        tp, sl: multiplicadores
        direction: -1 = SELL, 1 = BUY
        use_uint64: True = bit-packing uint64, False = uint8 simples
        blocking_mode: 'single' = 1 candle (compativel F1 Original/F2/F3),
                       'exact' = duracao real

    Returns:
        net: PnL liquido
        n_trades: numero de trades
    """
    had, pnl, duration = evaluate_combo(M, ep, atr, sell_idx, tp, sl, direction)
    N_candles = int(sell_idx.max()) + MAX_C + 2
    mode_int = 0 if blocking_mode == 'exact' else 1

    if use_uint64:
        return blocking_binario_uint64(sell_idx, had, pnl, duration, N_candles, mode_int)
    else:
        return blocking_binario_uint8(sell_idx, had, pnl, duration, N_candles, mode_int)


def evaluate_batch(M, ep, atr, sell_idx, tp_grid, sl_grid, direction=-1, use_uint64=True, blocking_mode='single'):
    """
    Avalia multiplos combos (tp x sl) simultaneamente.

    Args:
        M: (n_entries, N_SAMPLES)
        ep, atr, sell_idx: (n_entries,)
        tp_grid: array de TPs (ex: np.array([1.0, 1.5, 2.0]))
        sl_grid: array de SLs
        direction: -1 ou 1
        use_uint64: True = bit-packing uint64
        blocking_mode: 'single' ou 'exact'

    Returns:
        net_grid: (n_tp, n_sl) — PnL liquido por combo
        n_grid: (n_tp, n_sl) — numero de trades por combo
    """
    n_tp = len(tp_grid)
    n_sl = len(sl_grid)

    net_grid = np.zeros((n_tp, n_sl), dtype=np.int32)
    n_grid = np.zeros((n_tp, n_sl), dtype=np.int32)

    N_candles = int(sell_idx.max()) + MAX_C + 2
    mode_int = 0 if blocking_mode == 'exact' else 1

    for i, tp in enumerate(tp_grid):
        for j, sl in enumerate(sl_grid):
            had, pnl, duration = evaluate_combo(M, ep, atr, sell_idx, tp, sl, direction)
            if use_uint64:
                net, n_trades = blocking_binario_uint64(sell_idx, had, pnl, duration, N_candles, mode_int)
            else:
                net, n_trades = blocking_binario_uint8(sell_idx, had, pnl, duration, N_candles, mode_int)
            net_grid[i, j] = net
            n_grid[i, j] = n_trades

    return net_grid, n_grid
