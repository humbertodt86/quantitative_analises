"""
F1 Binario — Fast Screener com Blocking Bitwise (OHLC-Based)
=============================================================
VERSAO NOVA (2026-05-05): Usa APENAS high/low das candles.
NAO usa tick samples. NAO precisa de WIN_merged_all.parquet.

Cada trade e um vetor binario (0/1) de candles ocupadas.
Blocking via operacoes bitwise (AND/OR) — extremamente rapido.

Dados usados:
  - high, low, close, atr: arrays 1D do super_win_continuous.parquet
  - sell_idx: indices das candles de entrada
  - direction: -1 = SELL, 1 = BUY

Logica de entrada/saida IDENTICA ao F2:
  BUY:  TP se high >= tp_price, SL se low <= sl_price
  SELL: TP se low <= tp_price, SL se high >= sl_price
  PnL = threshold fixo (tp_pts ou -sl_pts)

Vantagens:
  - Mesma fonte de dados do F2 (candles OHLC)
  - PnL no threshold (nao no tick sampleado) → correlacao positiva com F2
  - Sem dependencia de tick samples para IS
  - Blocking em O(1) por trade via operacoes bitwise (uint64)

Arquitetura:
-----------
1. evaluate_combo(): numba — loop sobre entradas, verifica high/low futuros
2. blocking_binario_uint64(): numba — bit-packing uint64, AND/OR
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
    evaluate(high, low, close, ep, atr, sell_idx, tp, sl, direction=-1, blocking_mode='single')
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

MAX_C = 50    # Maximo de candles futuras (igual F2)
COST = 30     # Custo fixo simulado


@njit(fastmath=True)
def _evaluate_combo_numba(high, low, close, ep, atr, sell_idx, tp, sl, direction):
    """
    Avalia UMA config (tp, sl) via loop numba sobre entradas.
    Usa high/low para DETECTAR cruzamento e close (tick last) para PnL.

    Args:
        high, low, close: (N_candles,) — arrays de cada candle
        ep: (n_entries,) — precos de entrada (close da candle de sinal)
        atr: (n_entries,) — ATR na entrada
        sell_idx: (n_entries,) — indices das candles de entrada
        tp, sl: multiplicadores
        direction: -1 = SELL, 1 = BUY

    Returns:
        had: (n_entries,) bool — teve exit?
        pnl: (n_entries,) float32 — PnL bruto (close[c] - entry)
        duration: (n_entries,) int32 — duracao em candles (1..MAX_C)
    """
    n = len(ep)
    had = np.zeros(n, dtype=np.bool_)
    pnl = np.zeros(n, dtype=np.float32)
    duration = np.zeros(n, dtype=np.int32)

    for i in range(n):
        entry_price = ep[i]
        atr_i = atr[i]
        tp_price = entry_price + tp * atr_i if direction == 1 else entry_price - tp * atr_i
        sl_price = entry_price - sl * atr_i if direction == 1 else entry_price + sl * atr_i

        start_candle = sell_idx[i] + 1
        end_candle = min(start_candle + MAX_C, len(high))

        for c in range(start_candle, end_candle):
            exit_price = close[c]  # tick last da candle de saida

            if direction == 1:  # BUY
                if high[c] >= tp_price:
                    had[i] = True
                    pnl[i] = exit_price - entry_price
                    duration[i] = c - start_candle + 1
                    break
                if low[c] <= sl_price:
                    had[i] = True
                    pnl[i] = exit_price - entry_price
                    duration[i] = c - start_candle + 1
                    break
            else:  # SELL
                if low[c] <= tp_price:
                    had[i] = True
                    pnl[i] = entry_price - exit_price
                    duration[i] = c - start_candle + 1
                    break
                if high[c] >= sl_price:
                    had[i] = True
                    pnl[i] = entry_price - exit_price
                    duration[i] = c - start_candle + 1
                    break

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


def evaluate(high, low, close, ep, atr, sell_idx, tp, sl, direction=-1, use_uint64=True, blocking_mode='exact'):
    """
    Interface compativel com f1_fast_screener.evaluate().

    Args:
        high, low, close: (N_candles,) — arrays de candles (close = tick last)
        ep: (n_entries,) — precos de entrada
        atr: (n_entries,) — ATR na entrada
        sell_idx: (n_entries,) — indices das candles de entrada
        tp, sl: multiplicadores
        direction: -1 = SELL, 1 = BUY
        use_uint64: True = bit-packing uint64, False = uint8 simples
        blocking_mode: 'exact' = duracao real (padrao, alinhado com F2/F3),
                       'single' = 1 candle (compativel F1 Original legacy)

    Returns:
        net: PnL liquido
        n_trades: numero de trades
    """
    had, pnl, duration = _evaluate_combo_numba(high, low, close, ep, atr, sell_idx, tp, sl, direction)
    N_candles = len(high)
    mode_int = 0 if blocking_mode == 'exact' else 1

    if use_uint64:
        return blocking_binario_uint64(sell_idx, had, pnl, duration, N_candles, mode_int)
    else:
        return blocking_binario_uint8(sell_idx, had, pnl, duration, N_candles, mode_int)


def evaluate_batch(high, low, close, ep, atr, sell_idx, tp_grid, sl_grid, direction=-1, use_uint64=True, blocking_mode='exact'):
    """
    Avalia multiplos combos (tp x sl) simultaneamente.

    Args:
        high, low, close: (N_candles,) — arrays de candles
        ep, atr, sell_idx: (n_entries,)
        tp_grid: array de TPs (ex: np.array([1.0, 1.5, 2.0]))
        sl_grid: array de SLs
        direction: -1 ou 1
        use_uint64: True = bit-packing uint64
        blocking_mode: 'exact' (padrao, alinhado F2) ou 'single' (legacy)

    Returns:
        net_grid: (n_tp, n_sl) — PnL liquido por combo
        n_grid: (n_tp, n_sl) — numero de trades por combo
    """
    n_tp = len(tp_grid)
    n_sl = len(sl_grid)

    net_grid = np.zeros((n_tp, n_sl), dtype=np.int32)
    n_grid = np.zeros((n_tp, n_sl), dtype=np.int32)

    N_candles = len(high)
    mode_int = 0 if blocking_mode == 'exact' else 1

    for i, tp in enumerate(tp_grid):
        for j, sl in enumerate(sl_grid):
            had, pnl, duration = _evaluate_combo_numba(high, low, close, ep, atr, sell_idx, tp, sl, direction)
            if use_uint64:
                net, n_trades = blocking_binario_uint64(sell_idx, had, pnl, duration, N_candles, mode_int)
            else:
                net, n_trades = blocking_binario_uint8(sell_idx, had, pnl, duration, N_candles, mode_int)
            net_grid[i, j] = net
            n_grid[i, j] = n_trades

    return net_grid, n_grid
