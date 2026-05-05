"""Carregamento de dados: ticks CSV → M1/M5 OHLCV, e candles CSV do MT5."""
from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd


# ── Tick data ─────────────────────────────────────────────────────────────────

def load_ticks(tick_file: str | Path) -> pd.DataFrame:
    """
    Carrega arquivo de ticks exportado pelo MT5.
    Usa o campo 'last' (price); descarta linhas com last <= 0.

    Retorna DataFrame com colunas: dt, price, volume
    """
    times, prices, volumes = [], [], []
    with open(tick_file, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            last = float(row.get("last") or 0)
            if last <= 0:
                continue
            times.append(int(row["time_msc"]))
            prices.append(last)
            volumes.append(float(row.get("volume_real") or 1.0) or 1.0)

    df = pd.DataFrame({"time_msc": times, "price": prices, "volume": volumes})
    df["dt"] = pd.to_datetime(df["time_msc"], unit="ms")
    df = df.sort_values("dt").reset_index(drop=True)
    return df


def load_ticks_raw(tick_file: str | Path) -> pd.DataFrame:
    """
    Carrega ticks com bid, ask e last (modo tick-real).

    Mantém apenas linhas com bid > 0 E ask > 0 E spread razoável (< 500 pts).
    Retorna DataFrame com colunas: dt, bid, ask, last, volume
    """
    rows_t, rows_bid, rows_ask, rows_last, rows_vol = [], [], [], [], []
    with open(tick_file, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            bid  = float(row.get("bid")  or 0)
            ask  = float(row.get("ask")  or 0)
            last = float(row.get("last") or 0)
            if bid <= 0 or ask <= 0:
                continue
            if ask - bid > 500:   # spread aberrante → descarta
                continue
            rows_t.append(int(row["time_msc"]))
            rows_bid.append(bid)
            rows_ask.append(ask)
            rows_last.append(last if last > 0 else (bid + ask) / 2)
            rows_vol.append(float(row.get("volume_real") or 1.0) or 1.0)

    df = pd.DataFrame({
        "time_msc": rows_t,
        "bid":  rows_bid,
        "ask":  rows_ask,
        "last": rows_last,
        "volume": rows_vol,
    })
    df["dt"] = pd.to_datetime(df["time_msc"], unit="ms")
    df = df.sort_values("dt").reset_index(drop=True)
    return df


def ticks_to_ohlcv(ticks: pd.DataFrame, freq: str) -> pd.DataFrame:
    """
    Reconstrói barras OHLCV a partir de ticks.

    freq: '1min', '5min', '15min', etc.
    Retorna DataFrame com colunas: dt, open, high, low, close, volume
    """
    t = ticks.set_index("dt")
    ohlcv = t["price"].resample(freq).ohlc()
    ohlcv["volume"] = t["volume"].resample(freq).sum()
    ohlcv = ohlcv.dropna()
    ohlcv.columns = ["open", "high", "low", "close", "volume"]
    return ohlcv.reset_index().rename(columns={"index": "dt"})


def load_tick_bars(
    tick_file: str | Path,
    freqs: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """
    Carrega ticks e reconstrói barras para cada frequência em `freqs`.

    Returns dict: {freq: DataFrame}
    Exemplo: load_tick_bars("ticks.csv", ["1min", "5min"])
    """
    if freqs is None:
        freqs = ["1min", "5min"]
    print(f"[INFO] Carregando ticks de {tick_file}...", flush=True)
    ticks = load_ticks(tick_file)
    print(f"[INFO] {len(ticks):,} trade ticks carregados", flush=True)

    bars = {}
    for freq in freqs:
        bars[freq] = ticks_to_ohlcv(ticks, freq)
        n = len(bars[freq])
        start = bars[freq]["dt"].iloc[0] if n else "-"
        end   = bars[freq]["dt"].iloc[-1] if n else "-"
        label = freq.replace("min", "M").replace("T", "M")
        print(f"[INFO] {label}: {n} barras | {start} a {end}", flush=True)

    return bars


# ── M1 price sequence (para simulação intrabar) ───────────────────────────────

def build_m1_price_seq(m1: pd.DataFrame) -> dict:
    """
    Cria mapa: dt_m5 (floor 5min) → lista de (dt_m1, low, high, close).
    Usado para simular preços intrabar com granularidade M1 dentro de cada M5.
    """
    from collections import defaultdict
    result: dict = defaultdict(list)
    for _, row in m1.iterrows():
        m5_key = row["dt"].floor("5min")
        result[m5_key].append(
            (row["dt"], float(row["low"]), float(row["high"]), float(row["close"]))
        )
    return dict(result)


# ── Candle CSV (MetaTrader export) ────────────────────────────────────────────

def load_candle_csv(candle_file: str | Path) -> pd.DataFrame:
    """
    Carrega arquivo CSV de candles exportado pelo MT5 (formato padrão IND$/WDO$).
    Detecta automaticamente o separador e o formato de data/hora.

    Retorna DataFrame com colunas: dt, open, high, low, close, volume
    """
    path = Path(candle_file)
    # Detectar separador
    with open(path, encoding="utf-8", errors="replace") as f:
        first = f.readline()
    sep = "\t" if "\t" in first else ","

    df = pd.read_csv(path, sep=sep, encoding="utf-8", encoding_errors="replace")
    # Normaliza nomes: strip, lower e remove < > (formato MT5: <DATE>, <OPEN>, etc.)
    df.columns = [c.strip().lower().lstrip("<").rstrip(">").strip() for c in df.columns]

    # Suporte a formatos de coluna data e hora separados ou combinados
    if "date" in df.columns and "time" in df.columns:
        df["dt"] = pd.to_datetime(df["date"].astype(str) + " " + df["time"].astype(str))
    elif "datetime" in df.columns:
        df["dt"] = pd.to_datetime(df["datetime"])
    else:
        # tenta primeira coluna
        df["dt"] = pd.to_datetime(df.iloc[:, 0])

    # Renomear colunas OHLCV — inclui variantes com tickvol
    # Prioridade: "volume" > "tickvol" > "vol" (usa apenas o primeiro disponível)
    rename = {}
    vol_mapped = False
    for c in df.columns:
        cl = c.lower()
        if cl in ("open", "high", "low", "close"):
            rename[c] = cl
        elif cl == "volume":
            rename[c] = "volume"
            vol_mapped = True
        elif cl in ("tick volume", "tickvol") and not vol_mapped:
            rename[c] = "volume"
            vol_mapped = True
        elif cl == "vol" and not vol_mapped:
            rename[c] = "volume"
            vol_mapped = True
    df = df.rename(columns=rename)
    if "tick_volume" in df.columns and "volume" not in df.columns:
        df = df.rename(columns={"tick_volume": "volume"})

    required = ["open", "high", "low", "close"]
    missing  = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Colunas não encontradas em {candle_file}: {missing}\n"
                         f"Disponíveis: {list(df.columns)}")

    for c in required + (["volume"] if "volume" in df.columns else []):
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df[["dt"] + required + (["volume"] if "volume" in df.columns else [])].dropna().reset_index(drop=True)


# ── Indicators CSV (exportado pelo ExportIndicators.mq5) ──────────────────────

def load_indicators_csv(indicators_file: str | Path) -> pd.DataFrame:
    """
    Carrega arquivo CSV de indicadores exportado pelo EA ExportIndicators.mq5.
    Colunas: datetime, open, high, low, close, ATR, ADX7, EMA20, EMA5,
             dist, EMA_slope, EMA5_slope

    Retorna DataFrame com coluna 'dt' + todas as colunas de indicadores.
    Permite substituir o cálculo Python por valores exatos do MT5.
    """
    path = Path(indicators_file)
    df = pd.read_csv(path, encoding="utf-8", encoding_errors="replace")
    df.columns = [c.strip() for c in df.columns]
    df["dt"] = pd.to_datetime(df["datetime"])

    # Renomear para compatibilidade com o engine
    rename = {
        "open": "open", "high": "high", "low": "low", "close": "close",
        "ATR": "ATR", "ADX7": "ADX7",
        "EMA20": "EMA20", "EMA5": "EMA5",
        "dist": "dist",
        "EMA_slope": "EMA_SLOPE",
        "EMA5_slope": "EMA5_SLOPE",
        # V92+ indicadores exportados pelo bot
        "RSI14": "RSI14",
        "BB_UPPER": "BB_UPPER",
        "BB_LOWER": "BB_LOWER",
        "VWAP": "VWAP",
    }
    df = df.rename(columns=rename)

    # hora (float BRT) para filtro de horário no engine
    df["hora"] = df["dt"].dt.hour + df["dt"].dt.minute / 60.0

    # ADX14 como alias de ADX7 (engine usa adx_col() que pode pedir ADX14)
    if "ADX7" in df.columns and "ADX14" not in df.columns:
        df["ADX14"] = df["ADX7"]

    # BB_WIDTH_PCT e DIST_VWAP calculados na carga (derivados de valores exportados)
    if "BB_UPPER" in df.columns and "BB_LOWER" in df.columns and "EMA20" in df.columns:
        ema20_safe = df["EMA20"].replace(0, float("nan"))
        df["BB_WIDTH_PCT"] = (df["BB_UPPER"] - df["BB_LOWER"]) / ema20_safe
    if "VWAP" in df.columns and "close" in df.columns:
        df["DIST_VWAP"] = df["close"] - df["VWAP"]

    cols = ["dt", "open", "high", "low", "close",
            "ATR", "ADX7", "ADX14", "EMA20", "EMA5",
            "dist", "EMA_SLOPE", "EMA5_SLOPE", "hora",
            # V92+
            "RSI14", "BB_UPPER", "BB_LOWER", "BB_WIDTH_PCT", "VWAP", "DIST_VWAP"]
    return df[[c for c in cols if c in df.columns]].dropna(subset=["ATR", "ADX7"]).reset_index(drop=True)
