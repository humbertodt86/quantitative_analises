"""
Engine de backtest tick-real (modo 'tick-real').

Replica o comportamento do MT5 Strategy Tester em modo "Real Ticks":

  1. Path dependency: SL/TP verificados em cada tick com bid/ask real —
     o primeiro preço a ser tocado ganha (sem ambiguidade OHLC).

  2. Timing de H-Progress: usa o fechamento da BARRA ANTERIOR (bar-1),
     exatamente como o OnTick MQL5 com isNewBar — GerenciarPosicao roda
     no primeiro tick da nova barra com close_buf[0] = barra recém-fechada.

  3. price_ok gate: BE só é efetivado se o primeiro tick da nova barra
     já satisfaz o nível (bid >= be_price para BUY, ask <= be_price para
     SELL) — replica a condição price_ok do MQL5.

  4. Slope Decay: usa EMA5_SLOPE da barra anterior (mesma lógica de timing).

  5. Slippage de entrada: usa o primeiro tick válido da barra seguinte
     (ask para BUY, bid para SELL) + penalidade de atrito configurável
     (entry_slippage_pts). Modela latência real + spread de execução.

Fluxo (dois passes):
  Passo 1 — Indicadores
    Reconstrói barras M5 dos ticks e calcula indicadores (EMA20 cold-start,
    ADX7, ATR, RSI14, BB, VWAP).

  Passo 2 — Execução tick-a-tick
    Para cada barra M5 (barra i = "nova barra que acabou de abrir"):
      • Gerenciamento usa records[i-1] (barra recém-fechada) para
        H-Progress e Slope Decay, e primeiro tick de i para price_ok.
      • SL/TP scaneados em bid/ask dos ticks da barra i.
      • Sinal de entrada gerado no close de i → executa no primeiro tick
        de i+1.

Uso:
    from backtest.engine_tick_real import run_backtest_tick_real
    trades = run_backtest_tick_real(ticks_raw, m5_ind, strategy, instrument)
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from .config import InstrumentConfig
from .strategies.base import Strategy
from .engine import Position, _make_trade


# ──────────────────────────────────────────────────────────────────────────────
# Helpers tick-level
# ──────────────────────────────────────────────────────────────────────────────

def _find_exit_in_ticks(
    bid: np.ndarray,
    ask: np.ndarray,
    signal: str,
    sl_price: float,
    tp_price: float,
) -> Optional[tuple[int, str]]:
    """
    Percorre arrays bid/ask e retorna (idx, 'SL'|'TP') do primeiro hit.

    BUY  : fecha vendendo → usa bid. SL: bid <= sl; TP: bid >= tp.
    SELL : fecha comprando → usa ask. SL: ask >= sl; TP: ask <= tp.
    """
    if signal == "BUY":
        prices = bid
        sl_mask = prices <= sl_price
        tp_mask = prices >= tp_price
    else:
        prices = ask
        sl_mask = prices >= sl_price
        tp_mask = prices <= tp_price

    sl_idx = int(np.argmax(sl_mask)) if sl_mask.any() else len(prices)
    tp_idx = int(np.argmax(tp_mask)) if tp_mask.any() else len(prices)

    if sl_idx == len(prices) and tp_idx == len(prices):
        return None
    if tp_idx < sl_idx:
        return (tp_idx, "TP")
    return (sl_idx, "SL")


def _build_tick_index(
    ticks_raw: pd.DataFrame,
    m5_ind: pd.DataFrame,
) -> list[tuple[int, int]]:
    """
    Pré-computa [start, end) de ticks para cada barra M5.

    Retorna lista de (start_idx, end_idx) alinhada com m5_ind.
    """
    tick_sec = (ticks_raw["dt"].values.astype("int64") // 1_000_000_000).astype("int64")
    bar_starts = m5_ind["dt"].values.astype("int64") // 1_000_000_000
    bar_ends   = np.append(bar_starts[1:], bar_starts[-1] + 300)

    index = []
    for bs, be in zip(bar_starts, bar_ends):
        s = int(np.searchsorted(tick_sec, bs, side="left"))
        e = int(np.searchsorted(tick_sec, be, side="left"))
        index.append((s, e))
    return index


# ──────────────────────────────────────────────────────────────────────────────
# Motor principal
# ──────────────────────────────────────────────────────────────────────────────

def run_backtest_tick_real(
    ticks_raw: pd.DataFrame,
    m5_ind: pd.DataFrame,
    strategy: Strategy,
    instrument: InstrumentConfig,
    entry_slippage_pts: int = 5,
) -> list[dict]:
    """
    ticks_raw          : DataFrame com colunas dt, bid, ask, last.
    m5_ind             : DataFrame M5 com indicadores (saída de add_indicators).
    strategy           : instância de Strategy.
    instrument         : InstrumentConfig do símbolo.
    entry_slippage_pts : pontos de atrito base (fallback quando strategy não define
                         base_slippage_pts). Default=5 pts.

    Slippage dinâmico (V94+):
        Se a strategy tiver atributos base_slippage_pts e atr_slippage_mult,
        o slippage de entrada é calculado como:
            slip = base_slippage_pts + round(ATR × atr_slippage_mult)
        Isso penaliza entradas em barras de alta volatilidade, modelando
        spread e latência reais de forma proporcional ao ATR.
    """
    s   = strategy
    cfg = instrument

    # Parâmetros de slippage dinâmico — lidos da strategy se disponíveis
    base_slip      = int(getattr(s, "base_slippage_pts", entry_slippage_pts))
    atr_slip_mult  = float(getattr(s, "atr_slippage_mult", 0.0))

    adx_col = s.adx_col()
    records = m5_ind.to_dict("records")
    N       = len(records)

    # Arrays bid/ask para lookup rápido
    bid_arr = ticks_raw["bid"].values.astype("float32")
    ask_arr = ticks_raw["ask"].values.astype("float32")

    # Pré-computa índice M5 → faixa de ticks
    tick_idx = _build_tick_index(ticks_raw, m5_ind)

    trades: list[dict] = []
    pos: Optional[Position] = None
    sl_consec   = 0
    cb_day: Optional[date] = None
    cooldown_until = 0
    pending: Optional[dict] = None  # sinal gerado no close de i, executa em i+1

    for i in range(20, N - 1):
        c      = records[i]       # barra atual (ticks desta barra serão scaneados)
        c_prev = records[i - 1]   # barra anterior (recém-fechada — usada para gerenciamento)
        hora_c  = float(c["hora"])
        cur_day = c["dt"].date()
        t_start, t_end = tick_idx[i]

        # Primeiro tick da barra atual (bid e ask)
        first_bid = bid_arr[t_start] if t_start < t_end and bid_arr[t_start] > 0 else float(c["open"])
        first_ask = ask_arr[t_start] if t_start < t_end and ask_arr[t_start] > 0 else float(c["open"])

        bid_bar = bid_arr[t_start:t_end]
        ask_bar = ask_arr[t_start:t_end]

        # ── Executar entrada pendente no primeiro tick desta barra ─────────
        if pending is not None:
            sig = pending["signal"]
            # Preço base: ask para BUY, bid para SELL (melhor fill disponível)
            ep_raw = first_ask if sig == "BUY" else first_bid
            # Slippage dinâmico: base + ATR × mult (modela latência + spread real)
            slip   = base_slip + round(pending.get("atr", 0.0) * atr_slip_mult)
            ep = ep_raw + slip if sig == "BUY" else ep_raw - slip

            pos = Position(
                signal=sig,
                mode=pending["mode"],
                entry=ep,
                tp_pts=pending["tp_pts"],
                sl_pts=pending["sl_pts"],
                entry_hora=pending["entry_hora"],
                entry_slope=pending["entry_slope"],
                entry_dt=c["dt"],
                be_offset=s.be_offset,
            )
            pending = None

        # ── Gerenciar posição ──────────────────────────────────────────────
        if pos is not None:
            pos.m5_candles += 1

            # ── Panic close ───────────────────────────────────────────────
            if hora_c >= cfg.hora_panic:
                exit_price = first_bid if pos.signal == "BUY" else first_ask
                pnl = round(exit_price - pos.entry) if pos.signal == "BUY" \
                      else round(pos.entry - exit_price)
                trades.append(_make_trade(pos, c["dt"], c["dt"].strftime("%H:%M"), "PANIC", pnl))
                pos = None; sl_consec = 0
                continue

            # ── EOD: BE antecipado (17:30) ────────────────────────────────
            if hora_c >= cfg.hora_limit and not pos.be_active:
                if pos.progress(float(c_prev["close"])) > 0:
                    pos.sl_price  = pos.entry
                    pos.be_active = True
                    pos.be_reason = "EOD"

            # Usa dados da BARRA ANTERIOR (c_prev) para avaliação de gerenciamento.
            # Replica OnTick MQL5: GerenciarPosicao roda no 1º tick da nova barra
            # com close_buf[0] = barra recém-fechada, ema5_slope = barra recém-fechada.
            prev_close  = float(c_prev["close"])
            prev_slope  = float(c_prev.get("EMA5_SLOPE") or 0)
            entry_slope = pos.entry_slope or 0

            # Preço do primeiro tick da nova barra para price_ok gate
            # (mesma lógica do MQL5: curr_price = tick.bid para BUY, tick.ask para SELL)
            gate_price = first_bid if pos.signal == "BUY" else first_ask

            # ── H-Slope Decay (TREND) ─────────────────────────────────────
            if not pos.be_active and pos.mode == "TREND":
                exp_dir = 1 if pos.signal == "BUY" else -1
                if entry_slope * exp_dir > 0:
                    if prev_slope * exp_dir < entry_slope * exp_dir * s.slope_decay_factor:
                        be_sl = pos.entry + (pos._be_offset if pos.signal == "BUY" else -pos._be_offset)
                        price_ok = (pos.signal == "BUY" and gate_price >= be_sl) or \
                                   (pos.signal == "SELL" and gate_price <= be_sl)
                        if price_ok:
                            pos.move_to_be("SLOPE", gate_price)

            # ── TP30 grace decay M5 ───────────────────────────────────────
            if not pos.be_active and pos.tp30_mode:
                pos.tp30_grace -= 1
                if pos.tp30_grace <= 0:
                    be_sl = pos.entry + (pos._be_offset if pos.signal == "BUY" else -pos._be_offset)
                    price_ok = (pos.signal == "BUY" and gate_price >= be_sl) or \
                               (pos.signal == "SELL" and gate_price <= be_sl)
                    if price_ok:
                        pos.sl_price  = be_sl
                        pos.be_active = True
                        pos.be_reason = "TP30_GRACE"
                    pos.tp30_mode = False

            # ── H-Progress M5 ─────────────────────────────────────────────
            # Usa prev_close (barra recém-fechada) — alinhado com MQL5 close_buf[0]
            if not pos.be_active and not pos.tp30_mode:
                if pos.m5_candles >= s.progress_candles:
                    prog = pos.progress(prev_close)
                    if prog < pos.tp_pts_orig * s.progress_threshold:
                        if s.use_tp30():
                            partial = (pos.entry + pos.tp_pts_orig * s.progress_tp_pct
                                       if pos.signal == "BUY"
                                       else pos.entry - pos.tp_pts_orig * s.progress_tp_pct)
                            pos.tp_price  = partial
                            pos.tp_pts    = round(pos.tp_pts_orig * s.progress_tp_pct)
                            pos.tp30_mode  = True
                            pos.tp30_grace = s.grace_candles
                        else:
                            # price_ok gate: só move se gate_price já satisfaz o nível BE
                            pos.move_to_be("PROG_M5", gate_price)

            # ── Scan de ticks: SL/TP com bid/ask reais ────────────────────
            if len(bid_bar) > 0 and len(ask_bar) > 0:
                result = _find_exit_in_ticks(
                    bid_bar, ask_bar,
                    pos.signal, pos.sl_price, pos.tp_price
                )
            else:
                # Sem ticks na barra: fallback OHLC M5
                from .engine import _check_sl_tp
                hit_ohlc = _check_sl_tp(pos, float(c["low"]), float(c["high"]))
                result = (0, hit_ohlc) if hit_ohlc else None

            if result is not None:
                tick_idx_hit, hit_type = result
                if pos.signal == "BUY":
                    exit_price = float(bid_bar[tick_idx_hit]) if tick_idx_hit < len(bid_bar) else pos.sl_price
                else:
                    exit_price = float(ask_bar[tick_idx_hit]) if tick_idx_hit < len(ask_bar) else pos.sl_price

                pnl = round(exit_price - pos.entry) if pos.signal == "BUY" \
                      else round(pos.entry - exit_price)

                if hit_type == "TP":
                    sl_consec = 0
                elif pos.be_active:
                    sl_consec = 0
                else:
                    sl_consec += 1
                    cb_day = cur_day
                    if s.cooldown_candles > 0:
                        cooldown_until = i + s.cooldown_candles

                exit_hora = c["dt"].strftime("%H:%M")
                trades.append(_make_trade(pos, c["dt"], exit_hora, hit_type, pnl))
                pos = None
            continue

        # ── Circuit Breaker ────────────────────────────────────────────────
        if cb_day != cur_day:
            sl_consec = 0
        if cb_day == cur_day and sl_consec >= s.max_sl_consec:
            continue
        if s.cooldown_candles > 0 and i <= cooldown_until:
            continue

        # ── Filtros de entrada ─────────────────────────────────────────────
        if hora_c < cfg.hora_start or hora_c >= cfg.hora_limit:
            continue
        atr_v = c.get("ATR")
        if atr_v is None or pd.isna(atr_v) or float(atr_v) > s.atr_max:
            continue
        if getattr(s, "atr_min", 0) > 0 and float(atr_v) < s.atr_min:
            continue

        adx_v = float(c.get(adx_col) or float("nan"))
        if pd.isna(adx_v) or adx_v > s.adx_max:
            continue

        dist_v = float(c["dist"])
        atr_f  = float(atr_v)

        if adx_v <= s.adx_threshold:
            mode = "RANGE"
            gmax_eff = s.resolve_gatilho_max(atr_f, "RANGE")
            range_bloqueio = getattr(s, "range_hora_bloqueio", None)
            if range_bloqueio and any(lo <= hora_c < hi for lo, hi in range_bloqueio):
                continue
            gmin_mode = s.resolve_gatilho_min("RANGE")
            if abs(dist_v) <= gmin_mode or abs(dist_v) > gmax_eff:
                continue
            signal = "SELL" if dist_v > 0 else "BUY"
            sl_v = float(c.get("EMA_SLOPE") or 0)
            if signal == "SELL" and sl_v >  s.ema_slope_max: continue
            if signal == "BUY"  and sl_v < -s.ema_slope_max: continue
            tp_pts = round(atr_f * s.tp_range_mult)
            sl_pts = round(atr_f * s.sl_range_mult)
        else:
            mode = "TREND"
            gmax_eff  = s.resolve_gatilho_max(atr_f, "TREND")
            gmin_mode = s.resolve_gatilho_min("TREND")
            if abs(dist_v) <= gmin_mode or abs(dist_v) > gmax_eff:
                continue
            signal = "BUY" if dist_v > 0 else "SELL"
            tp_pts = round(atr_f * s.tp_trend_mult)
            sl_pts = round(atr_f * s.sl_trend_mult)

        if tp_pts <= 0 or sl_pts <= 0:
            continue
        if not s.entry_allowed(c, mode, signal):
            continue

        pending = {
            "signal":      signal,
            "mode":        mode,
            "tp_pts":      tp_pts,
            "sl_pts":      sl_pts,
            "entry_hora":  c["dt"].strftime("%H:%M"),
            "entry_slope": float(c.get("EMA5_SLOPE") or 0),
            "ref_close":   float(c["close"]),
            "atr":         float(c.get("ATR") or 0),  # para slippage dinâmico
        }

    return trades
