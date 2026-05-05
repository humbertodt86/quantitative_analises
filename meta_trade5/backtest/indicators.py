"""Indicadores técnicos compartilhados: EMA, ATR, ADX, RSI, BB, VWAP.

Convenção de ATR:
    daily_atr=True (padrão):
        ATR calculado com rolling(14) DENTRO DE CADA DIA via groupby(date).
        Replica o comportamento do live bot, que carrega apenas as últimas 50
        barras do dia corrente (copy_rates_from_pos com pos=1), sem herdar a
        volatilidade do dia anterior.

    daily_atr=False:
        ATR calculado sobre toda a série histórica (cross-day).
        Útil apenas para análise de longo prazo onde a continuidade importa.

Indicadores V92+:
    RSI14     — RSI Wilder (alpha=1/14). Equivalente a iRSI do MT5.
    BB_UPPER/LOWER — Bollinger Bands(20, 2). Equivalente a iBands do MT5.
    BB_WIDTH_PCT   — (upper-lower)/EMA20 — largura relativa.
    VWAP      — VWAP diário (reset à meia-noite). Usa coluna 'volume' (tickvol).
    DIST_VWAP — close - VWAP (positivo = acima do VWAP).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def calc_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """ADX Wilder suavizado via EWM (equivalente ao Wilder smoothing com alpha=1/period)."""
    prev_close = close.shift(1)
    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    up   = high - high.shift(1)
    down = low.shift(1) - low
    pdm  = np.where((up > down) & (up > 0), up, 0.0)
    mdm  = np.where((down > up) & (down > 0), down, 0.0)
    a    = 1.0 / period
    atr_s = tr.ewm(alpha=a, adjust=False).mean()
    pdi   = 100 * pd.Series(pdm, index=high.index).ewm(alpha=a, adjust=False).mean() / atr_s
    mdi   = 100 * pd.Series(mdm, index=high.index).ewm(alpha=a, adjust=False).mean() / atr_s
    dx    = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=a, adjust=False).mean()


def _calc_daily_atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """
    ATR com rolling(window) reiniciado a cada dia.
    Replica o comportamento do live bot que carrega apenas candles do dia atual.
    """
    hl = df["high"] - df["low"]
    date_col = df["dt"].dt.date
    # groupby date, rolling dentro de cada dia
    result = (
        hl.groupby(date_col, group_keys=False)
          .apply(lambda s: s.rolling(window=window, min_periods=1).mean())
    )
    return result


def _calc_true_range_atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """
    ATR com True Range contínuo (sem reset diário).
    True Range = max(H-L, |H-prev_close|, |L-prev_close|)
    Captura gaps de abertura. Rolling contínuo cross-day.
    Alinhado com V95 MQL5 que usa a mesma fórmula.
    """
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"]  - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=window, min_periods=1).mean()


def add_indicators(
    df: pd.DataFrame,
    adx_period: int = 14,
    daily_atr: bool = True,
    true_range_atr: bool = False,
) -> pd.DataFrame:
    """
    Adiciona indicadores padrão ao DataFrame OHLCV.

    Parâmetros
    ----------
    df         : DataFrame com colunas dt, open, high, low, close
    adx_period : período do ADX principal (coluna ADX<period>)
    daily_atr  : se True (padrão), ATR é resetado por dia (replica live bot).
                 Se False, ATR cross-day sobre toda a série.

    IMPORTANTE: Indicadores sao calculados com TODO o historico disponivel.
    Para simular lookback limitado do MT5, usar warmup no builder.
    EWM converge em ~20 periodos, MA50 precisa de 50. 
    Warmup de 150 candles garante convergencia para todos os indicadores.

    Colunas adicionadas:
        EMA20, EMA5, ATR, EMA_SLOPE (EMA20 - EMA20[t-3]),
        EMA5_SLOPE (EMA5 - EMA5[t-1]), ADX<period>, hora, dist
    """
    df = df.copy()
    df["EMA20"]      = df["close"].ewm(span=20, adjust=False).mean()
    df["EMA5"]       = df["close"].ewm(span=5,  adjust=False).mean()
    if true_range_atr:
        df["ATR"]    = _calc_true_range_atr(df, window=14)
    elif daily_atr:
        df["ATR"]    = _calc_daily_atr(df, window=14)
    else:
        df["ATR"]    = (df["high"] - df["low"]).rolling(14).mean()
    df["EMA_SLOPE"]  = df["EMA20"] - df["EMA20"].shift(3)
    df["EMA5_SLOPE"] = df["EMA5"]  - df["EMA5"].shift(1)
    df[f"ADX{adx_period}"] = calc_adx(df["high"], df["low"], df["close"], adx_period)
    df["hora"]       = df["dt"].dt.hour + df["dt"].dt.minute / 60.0
    df["dist"]       = df["close"] - df["EMA20"]

    # ── Indicadores V92+ ──────────────────────────────────────────────────────
    df["RSI14"] = calc_rsi(df["close"], 14)
    bb_upper, bb_lower = calc_bb(df["close"], 20, 2.0)
    df["BB_UPPER"]     = bb_upper
    df["BB_LOWER"]     = bb_lower
    # BB_WIDTH_PCT = (upper - lower) / EMA20  (largura relativa para filtro de compressão)
    ema20_safe = df["EMA20"].replace(0, np.nan)
    df["BB_WIDTH_PCT"] = (bb_upper - bb_lower) / ema20_safe
    df["VWAP"]         = calc_vwap_daily(df)
    df["DIST_VWAP"]    = df["close"] - df["VWAP"]
    return df


def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI Wilder via EWM (alpha=1/period) — equivalente ao iRSI do MT5."""
    delta = close.diff()
    up   = delta.clip(lower=0)
    down = (-delta).clip(lower=0)
    alpha = 1.0 / period
    avg_up = up.ewm(alpha=alpha, adjust=False).mean()
    avg_dn = down.ewm(alpha=alpha, adjust=False).mean()
    rs = avg_up / avg_dn.replace(0, 1e-10)
    return 100.0 - 100.0 / (1.0 + rs)


def calc_bb(close: pd.Series, period: int = 20, std_dev: float = 2.0):
    """Bollinger Bands(period, std_dev). Retorna (upper, lower).

    Usa ddof=0 (população), equivalente ao iBands do MT5.
    """
    ma  = close.rolling(period, min_periods=1).mean()
    std = close.rolling(period, min_periods=1).std(ddof=0)
    return ma + std_dev * std, ma - std_dev * std


def calc_vwap_daily(df: pd.DataFrame) -> pd.Series:
    """VWAP diário com reset a cada dia (equivalent ao VWAP do MT5 com período diário).

    Usa coluna 'volume' (tickvol do MT5 — iVolume por padrão).
    Se 'volume' estiver ausente ou zerado, retorna close (sem peso de volume).
    """
    if "volume" not in df.columns or df["volume"].fillna(0).sum() == 0:
        return df["close"].copy()
    tp   = (df["high"] + df["low"] + df["close"]) / 3.0
    tpv  = tp * df["volume"].fillna(0)
    dates = df["dt"].dt.date
    cum_tpv = tpv.groupby(dates, group_keys=False).cumsum()
    cum_vol = df["volume"].fillna(0).groupby(dates, group_keys=False).cumsum()
    vwap = (cum_tpv / cum_vol.replace(0, np.nan)).fillna(df["close"])
    return vwap


def add_extra_adx(df: pd.DataFrame, period: int) -> pd.DataFrame:
    """Adiciona uma coluna ADX<period> extra sem sobrescrever outras."""
    col = f"ADX{period}"
    if col not in df.columns:
        df = df.copy()
        df[col] = calc_adx(df["high"], df["low"], df["close"], period)
    return df
