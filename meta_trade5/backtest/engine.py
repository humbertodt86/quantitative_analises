"""Motor de backtest tick-aware.

Refatorado a partir de thamila_v84_tick_research.py.
Suporta qualquer Strategy (V84, V85, etc.) e qualquer instrumento.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd

from .config import InstrumentConfig
from .strategies.base import Strategy


# =============================================================================
# Position
# =============================================================================

class Position:
    __slots__ = (
        "signal", "mode", "entry", "tp_pts_orig", "sl_pts",
        "tp_pts", "tp_price", "sl_price",
        "entry_hora", "entry_slope", "entry_dt",
        "be_active", "be_reason",
        "m5_candles", "m1_candles",
        "tp30_mode", "tp30_grace",
        "_be_offset",
    )

    def __init__(
        self,
        signal: str,
        mode: str,
        entry: float,
        tp_pts: int,
        sl_pts: int,
        entry_hora: str,
        entry_slope: float,
        entry_dt,
        be_offset: int,
    ):
        self.signal      = signal
        self.mode        = mode
        self.entry       = entry
        self.tp_pts_orig = tp_pts
        self.sl_pts      = sl_pts
        self.tp_pts      = tp_pts
        self.tp_price    = entry + tp_pts if signal == "BUY" else entry - tp_pts
        self.sl_price    = entry - sl_pts if signal == "BUY" else entry + sl_pts
        self.entry_hora  = entry_hora
        self.entry_slope = entry_slope
        self.entry_dt    = entry_dt
        self.be_active   = False
        self.be_reason   = ""
        self.m5_candles  = 0
        self.m1_candles  = 0
        self.tp30_mode   = False
        self.tp30_grace  = 0
        self._be_offset  = be_offset

    def progress(self, current_close: float) -> float:
        return current_close - self.entry if self.signal == "BUY" else self.entry - current_close

    def move_to_be(self, reason: str, current_price: float = None) -> None:
        offset = self._be_offset if self.signal == "BUY" else -self._be_offset
        new_sl = self.entry + offset
        better = (self.signal == "BUY" and new_sl > self.sl_price) or \
                 (self.signal == "SELL" and new_sl < self.sl_price)
        if not better:
            return
        # Rejeita BE se a posição ainda não chegou no nível de lucro mínimo.
        # Replica o comportamento do MT5: broker rejeita SL modification quando
        # o novo SL está além do preço atual (BUY: new_sl > ask; SELL: new_sl < bid).
        if current_price is not None:
            if self.signal == "BUY"  and current_price < new_sl:
                return
            if self.signal == "SELL" and current_price > new_sl:
                return
        self.sl_price  = new_sl
        self.be_active = True
        self.be_reason = reason


def _check_sl_tp(pos: Position, low: float, high: float) -> Optional[str]:
    if pos.signal == "BUY":
        sl_hit = low  <= pos.sl_price
        tp_hit = high >= pos.tp_price
    else:
        sl_hit = high >= pos.sl_price
        tp_hit = low  <= pos.tp_price
    if sl_hit and tp_hit:
        return "SL"  # conservador: assume SL primeiro
    if tp_hit:
        return "TP"
    if sl_hit:
        return "SL"
    return None


# =============================================================================
# Motor principal
# =============================================================================

def run_backtest(
    m5_ind: pd.DataFrame,
    m1_price: dict,
    strategy: Strategy,
    instrument: InstrumentConfig,
) -> list[dict]:
    """
    Roda o backtest de uma estratégia sobre os dados já indicados.

    m5_ind   : DataFrame M5 com colunas EMA20, ATR, EMA_SLOPE, EMA5_SLOPE,
               ADX<period>, ADX7 (se necessário), hora, dist
               — saída de indicators.add_indicators()
    m1_price : mapa dt_m5 → lista (dt_m1, low, high, close)
               — saída de data_loader.build_m1_price_seq()
    strategy : instância de Strategy (V84..V87, ou custom)
    instrument: InstrumentConfig do símbolo

    Retorna lista de dicts com uma entrada por trade.

    Filtros suportados (V87):
      - adx_max         : bloqueia entrada se ADX > adx_max
      - cooldown_candles: pula N candles M5 após cada SL
      - gatilho_min_range/trend: limites separados por modo
      - gatilho_max_atr_mult   : GMAX dinâmico = ATR × mult (aplicado em RANGE e TREND)
    """
    s   = strategy
    cfg = instrument

    adx_col = s.adx_col()
    records = m5_ind.to_dict("records")
    N       = len(records)
    trades: list[dict] = []
    pos: Optional[Position] = None
    sl_consec   = 0
    cb_day: Optional[date] = None
    cooldown_until = 0   # índice de barra até o qual o cooldown está ativo

    for i in range(20, N - 1):
        c  = records[i]
        c1 = records[i + 1]
        bar_dt  = c["dt"]
        hora_c  = float(c["hora"])
        cur_day = bar_dt.date()

        # ── Gerenciar posição aberta ──────────────────────────────────────────
        if pos is not None:
            pos.m5_candles += 1

            m1_bars = m1_price.get(bar_dt, [])
            hit: Optional[str] = None
            exit_hora = bar_dt.strftime("%H:%M")

            for (m1_dt, m1_low, m1_high, m1_close) in m1_bars:
                if s.use_m1_progress:
                    pos.m1_candles += 1

                # H-Progress M1
                if s.use_m1_progress and not pos.be_active and not pos.tp30_mode:
                    if pos.m1_candles >= s.progress_m1_candles:
                        prog = pos.progress(m1_close)
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
                                pos.move_to_be("PROG_M1", m1_close)

                # TP30 grace decay M1 (só decrementa se estamos no modo M1)
                if s.use_m1_progress and pos.tp30_mode and not pos.be_active:
                    pos.tp30_grace -= 1
                    if pos.tp30_grace <= 0:
                        be_sl = pos.entry + (pos._be_offset if pos.signal == "BUY" else -pos._be_offset)
                        # Replica rejeição do broker MT5: BE só se preço já atingiu o nível
                        price_ok = (pos.signal == "BUY"  and m1_close >= be_sl) or \
                                   (pos.signal == "SELL" and m1_close <= be_sl)
                        if price_ok:
                            pos.sl_price  = be_sl
                            pos.be_active = True
                            pos.be_reason = "TP30_GRACE"
                        pos.tp30_mode = False

                hit = _check_sl_tp(pos, m1_low, m1_high)
                if hit:
                    exit_hora = m1_dt.strftime("%H:%M")
                    break

            # H-Progress M5
            if not s.use_m1_progress and not pos.be_active and not pos.tp30_mode:
                if pos.m5_candles >= s.progress_candles:
                    prog = pos.progress(float(c["close"]))
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
                            pos.move_to_be("PROG_M5", float(c["close"]))

            # TP30 grace decay M5
            if not s.use_m1_progress and pos.tp30_mode and not pos.be_active:
                pos.tp30_grace -= 1
                if pos.tp30_grace <= 0:
                    be_sl = pos.entry + (pos._be_offset if pos.signal == "BUY" else -pos._be_offset)
                    cur_close = float(c["close"])
                    price_ok = (pos.signal == "BUY"  and cur_close >= be_sl) or \
                               (pos.signal == "SELL" and cur_close <= be_sl)
                    if price_ok:
                        pos.sl_price  = be_sl
                        pos.be_active = True
                        pos.be_reason = "TP30_GRACE"
                    pos.tp30_mode = False

            # H-Slope Decay (TREND only)
            if not pos.be_active and pos.mode == "TREND":
                e_slope   = pos.entry_slope or 0
                cur_slope = float(c.get("EMA5_SLOPE") or 0)
                exp_dir   = 1 if pos.signal == "BUY" else -1
                if e_slope * exp_dir > 0:
                    if cur_slope * exp_dir < e_slope * exp_dir * s.slope_decay_factor:
                        # move_to_be aplica be_offset (igual ao GRACE) — fix realismo
                        pos.move_to_be("SLOPE", float(c["close"]))

            # BE antecipado 17:30
            if hora_c >= cfg.hora_limit and not pos.be_active:
                lucro = pos.progress(float(c["close"]))
                if lucro > 0:
                    pos.sl_price  = pos.entry
                    pos.be_active = True
                    pos.be_reason = "EOD"

            # Panic close
            if hora_c >= cfg.hora_panic:
                pnl = (round(float(c["open"]) - pos.entry)
                       if pos.signal == "BUY"
                       else round(pos.entry - float(c["open"])))
                trades.append(_make_trade(pos, bar_dt, bar_dt.strftime("%H:%M"), "PANIC", pnl))
                pos = None
                sl_consec = 0
                continue

            # Fallback OHLC M5
            if hit is None:
                hit = _check_sl_tp(pos, float(c["low"]), float(c["high"]))
                if hit:
                    exit_hora = bar_dt.strftime("%H:%M")

            if hit:
                if hit == "TP":
                    pnl = pos.tp_pts
                    sl_consec = 0
                elif pos.be_active:
                    pnl = (round(pos.sl_price - pos.entry) if pos.signal == "BUY"
                           else round(pos.entry - pos.sl_price))
                    sl_consec = 0
                else:
                    pnl = -pos.sl_pts
                    sl_consec += 1
                    cb_day = cur_day
                    # ── Cooldown pós-SL (V87) ─────────────────────────────────
                    if s.cooldown_candles > 0:
                        cooldown_until = i + s.cooldown_candles

                trades.append(_make_trade(pos, bar_dt, exit_hora, hit, pnl))
                pos = None
            continue

        # ── Circuit Breaker ───────────────────────────────────────────────────
        if cb_day != cur_day:
            sl_consec = 0
        if cb_day == cur_day and sl_consec >= s.max_sl_consec:
            continue

        # ── Cooldown pós-SL (V87) ────────────────────────────────────────────
        if s.cooldown_candles > 0 and i <= cooldown_until:
            continue

        # ── Filtros de entrada ────────────────────────────────────────────────
        if hora_c < cfg.hora_start or hora_c >= cfg.hora_limit:
            continue
        atr_v = c.get("ATR")
        if atr_v is None or pd.isna(atr_v) or float(atr_v) > s.atr_max:
            continue
        # ── ATR mínimo (V88+) — filtra sessões de baixa volatilidade ─────────
        if getattr(s, "atr_min", 0) > 0 and float(atr_v) < s.atr_min:
            continue

        adx_v = float(c.get(adx_col) or float("nan"))
        if pd.isna(adx_v):
            continue

        # ── ADX_MAX (V87) ─────────────────────────────────────────────────────
        if adx_v > s.adx_max:
            continue

        dist_v   = float(c["dist"])
        atr_f    = float(atr_v)

        # ── Dual-mode EMA20 ───────────────────────────────────────────────────
        if adx_v <= s.adx_threshold:
            mode        = "RANGE"
            gmax_eff    = s.resolve_gatilho_max(atr_f, "RANGE")  # pode diferir do TREND
            # ── Bloqueio de horário para RANGE (V88+) ────────────────────────
            range_bloqueio = getattr(s, "range_hora_bloqueio", None)
            if range_bloqueio:
                blocked = any(lo <= hora_c < hi for lo, hi in range_bloqueio)
                if blocked:
                    continue
            gmin_mode   = s.resolve_gatilho_min("RANGE")
            if abs(dist_v) <= gmin_mode or abs(dist_v) > gmax_eff:
                continue
            signal = "SELL" if dist_v > 0 else "BUY"
            sl_v   = float(c.get("EMA_SLOPE") or 0)
            if signal == "SELL" and sl_v >  s.ema_slope_max:
                continue
            if signal == "BUY"  and sl_v < -s.ema_slope_max:
                continue
            tp_pts = round(atr_f * s.tp_range_mult)
            sl_pts = round(atr_f * s.sl_range_mult)
        else:
            mode        = "TREND"
            gmax_eff    = s.resolve_gatilho_max(atr_f, "TREND")
            gmin_mode   = s.resolve_gatilho_min("TREND")
            if abs(dist_v) <= gmin_mode or abs(dist_v) > gmax_eff:
                continue
            signal = "BUY" if dist_v > 0 else "SELL"
            tp_pts = round(atr_f * s.tp_trend_mult)
            sl_pts = round(atr_f * s.sl_trend_mult)

        if tp_pts <= 0 or sl_pts <= 0:
            continue

        # ── Filtros extras V92+ (RSI, BB, VWAP) ──────────────────────────────
        if not s.entry_allowed(c, mode, signal):
            continue

        entry_price = float(c1["open"])
        e_slope     = float(c.get("EMA5_SLOPE") or 0)
        entry_dt    = c1["dt"]

        pos = Position(
            signal=signal, mode=mode, entry=entry_price,
            tp_pts=tp_pts, sl_pts=sl_pts,
            entry_hora=bar_dt.strftime("%H:%M"),
            entry_slope=e_slope, entry_dt=entry_dt,
            be_offset=s.be_offset,
        )

    return trades


def _make_trade(pos: Position, exit_dt, exit_hora: str, res: str, pnl: int) -> dict:
    return {
        "entry_dt":   pos.entry_dt,
        "exit_dt":    exit_dt,
        "entry_hora": pos.entry_hora,
        "exit_hora":  exit_hora,
        "signal":     pos.signal,
        "mode":       pos.mode,
        "res":        res,
        "pnl":        pnl,
        "tp_pts":     pos.tp_pts,
        "sl_pts":     pos.sl_pts,
        "tp30_used":  pos.tp30_mode or pos.be_reason == "TP30_GRACE",
        "be_reason":  pos.be_reason,
    }
