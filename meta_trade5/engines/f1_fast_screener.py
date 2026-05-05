"""
F1 — Fast Screener Vetorizado
=============================
Proposito: Pre-filtro ultra-rapido para grids de parametros.
NAO substitui F3 para validacao final.

ATENCAO: F1 NAO TEM GUARDRAILS
  - NAO tem Break Even, Grace Period, Circuit Breaker, Slope Decay
  - NAO tem filtro de hora, dia, S/R buffers
  - NAO tem cooldown apos SL
  - NAO tem TP30 (take-profit adaptativo)
  - TEM apenas: SL/TP fixo + position blocking (skip = sell_idx + 1)
  - Usa last prices sampleados (15/candle), NAO bid/ask
  - Custo simulado de 30 pts/trade (nao calculado do spread)

PnL: usa preco REAL do sample que cruzou (ep - cross_price), nao distancia fixa.
     Diferenca vs engine_v2 e APENAS a amostragem (15 vs todos ticks).

Filtros de hora/dia/ATR devem ser aplicados EXTERNAMENTE (filtrar o DataFrame/parquet
antes de chamar o F1). O F1 e a pura simulacao de entrada/saida.

Amostragem (SAMP=15 otimo, vide README):
  - SAMP=15: 15 uniformes por candle → erro +34% vs F3, 18ms build (RECOMENDADO)
  - SAMP=60: 60 uniformes → erro +26%, 15ms build (melhora marginal de 8%)
  - Outras tecnicas (micro-OHLC, LTTB, P60) PIORAM o erro devido a vies de extremos
  - Conclusao: SAMP=15 melhor custo-beneficio para pre-filtro
"""
import numpy as np

try:
    from numba import njit, prange
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    def njit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    prange = range

SAMP = 15     # Amostras de last por candle
MAX_C = 50    # Maximo de candles futuras (aumentado de 15 para 50 para alinhar com F2/F3)
N_SAMPLES = MAX_C * SAMP  # 750
COST = 30     # Custo fixo simulado (15 entry + 15 exit)

def _sample_candle(ticks, incluir_extremos=False):
    """Amostra SAMP pontos de um array de ticks de uma candle.
    
    Sempre retorna exatamente SAMP valores.
    Se incluir_extremos=True, garante que min e max estejam entre os SAMP pontos.
    """
    n = len(ticks)
    if n <= SAMP:
        # Padding com o ultimo valor para ter exatamente SAMP
        pad = SAMP - n
        return np.pad(ticks, (0, pad), mode='edge') if pad > 0 else ticks.copy()
    
    if not incluir_extremos:
        step = max(1, n // SAMP)
        out = ticks[:n:step].copy()
        # Padding se step irregular deu menos que SAMP
        if len(out) < SAMP:
            out = np.pad(out, (0, SAMP - len(out)), mode='edge')
        return out[:SAMP]
    
    # Com extremos: SAMP-2 uniformes + min + max
    idx = set(np.linspace(0, n - 1, SAMP - 2, dtype=int).tolist())
    idx.add(int(np.argmin(ticks)))
    idx.add(int(np.argmax(ticks)))
    sorted_idx = sorted(idx)
    # Garantir exatamente SAMP valores (preencher com interpolacao se necessario)
    if len(sorted_idx) < SAMP:
        # Inserir pontos medios nos maiores gaps
        while len(sorted_idx) < SAMP:
            gaps = [(sorted_idx[i+1] - sorted_idx[i], i) for i in range(len(sorted_idx)-1)]
            if not gaps:
                break
            max_gap = max(gaps, key=lambda x: x[0])
            mid = (sorted_idx[max_gap[1]] + sorted_idx[max_gap[1] + 1]) // 2
            sorted_idx.insert(max_gap[1] + 1, mid)
    return ticks[sorted_idx[:SAMP]].copy()

def build_M_close(tick_last, tick_idx, sell_idx, N_candles, close_arr, incluir_extremos=False):
    """
    Pre-processa ticks para matriz M e vetor closes.
    
    Args:
        tick_last: array de todos os last prices (float32)
        tick_idx: lista de (start, end) por candle (do engine_v2)
        sell_idx: indices das candles de entrada SHORT
        N_candles: total de candles no periodo
        close_arr: closes de cada candle (para TP30)
        incluir_extremos: se True, garante min/max em cada amostra
    
    Returns:
        M: (n_entries, 225) float32 — sampled last ticks
        closes: (n_entries, MAX_C) float32 — closes das MAX_C candles futuras
    """
    n_entries = len(sell_idx)
    M = np.zeros((n_entries, N_SAMPLES), dtype=np.float32)
    closes = np.zeros((n_entries, MAX_C), dtype=np.float32)
    
    # Pre-processar samples de cada candle (UMA vez)
    candle_samples = []
    for j in range(N_candles):
        s, e = tick_idx[j]
        if e - s > SAMP:
            candle_samples.append(_sample_candle(tick_last[s:e], incluir_extremos))
        elif e > s:
            candle_samples.append(tick_last[s:e].copy())  # menos que SAMP ticks
        else:
            candle_samples.append(np.array([], dtype=np.float32))  # sem ticks
    
    # Construir matriz M por entrada (cada entrada = 1 trade potencial)
    for idx, i in enumerate(sell_idx):
        col = 0
        for ck, j in enumerate(range(i+1, min(i+MAX_C+1, N_candles))):
            cs = candle_samples[j]
            if len(cs) > 0:
                n_pts = min(len(cs), SAMP)
                M[idx, col:col+n_pts] = cs[:n_pts]
            col += SAMP
            closes[idx, ck] = close_arr[j]
    
    return M, closes

def evaluate(M, ep, atr, sell_idx, tp, sl, direction=-1):
    """
    Avalia uma config (tp, sl) via broadcast numpy + position blocking.

    F1 puro: NENHUM guardrail, NENHUM filtro de hora/ATR, NENHUM TP30.
    Filtros devem ser aplicados EXTERNAMENTE (filtrar o DataFrame antes).

    Args:
        M: (n_entries, N_SAMPLES) — sampled last ticks
        ep: (n_entries,) — precos de entrada (open da prox candle)
        atr: (n_entries,) — ATR na entrada
        sell_idx: (n_entries,) — indices das candles de entrada
        tp, sl: multiplicadores (ex: 1.5x, 0.3x)
        direction: -1 = SELL (default), 1 = BUY

    Returns:
        net: PnL liquido (com COST=30)
        n_trades: numero de trades apos position blocking
    """
    n = len(ep)
    idx_order = np.argsort(sell_idx)  # ordem cronologica

    # Calcular thresholds
    tp_pts = tp * atr
    sl_pts = sl * atr

    if direction == -1:  # SELL
        sl_th = ep + sl_pts          # SELL: preco sobe = perda
        tp_th = ep - tp_pts          # SELL: preco desce = ganho
        sl_hit = M >= sl_th[:, None]
        tp_hit = M <= tp_th[:, None]
    else:  # BUY
        sl_th = ep - sl_pts          # BUY: preco desce = perda
        tp_th = ep + tp_pts          # BUY: preco sobe = ganho
        sl_hit = M <= sl_th[:, None]
        tp_hit = M >= tp_th[:, None]

    hit = sl_hit | tp_hit
    fi = np.argmax(hit, axis=1)
    rows = np.arange(n)
    had = hit.any(axis=1)

    # --- PnL base (preco real do sample que cruzou) ---
    pnl = np.zeros(n, dtype=np.float32)
    cross_price = M[rows, fi]
    if direction == -1:  # SELL
        pnl[had] = ep[had] - cross_price[had]
    else:  # BUY
        pnl[had] = cross_price[had] - ep[had]

    # --- Position blocking (numba sequencial - sem parallel!) ---
    net, n_trades = _blocking_seq(had, pnl, sell_idx, idx_order)
    return net, n_trades


@njit(fastmath=True)
def _blocking_seq(had, pnl, sell_idx, idx_order):
    """Blocking sequencial compilado (SEM parallel - preserva ordem)."""
    skip = -1
    total_pnl = 0.0
    total_trades = 0
    for i in range(len(idx_order)):
        idx = idx_order[i]
        if sell_idx[idx] <= skip:
            continue
        if had[idx]:
            skip = sell_idx[idx] + 1
            total_pnl += pnl[idx]
            total_trades += 1
    return int(total_pnl) - total_trades * COST, total_trades
