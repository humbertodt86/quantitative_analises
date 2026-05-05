"""Interface de linha de comando do framework de backtest.

Uso:
    python -m backtest run   --strategy v85 --symbol WIN [--mode tick|candle]
    python -m backtest compare --strategies v84,v85 --symbol WIN
    python -m backtest grid  --strategy v85 --symbol WIN --param adx_period=7,14 ...
    python -m backtest today --strategy v85 --symbol WIN
    python -m backtest replay --strategy v85 --symbol WIN --date 2026-04-07
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Garante encoding UTF-8 no Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _load_strategy(name: str, overrides: dict | None = None):
    name = name.lower()
    overrides = overrides or {}
    if name == "v84":
        from .strategies.v84 import V84
        return V84(**overrides)
    if name == "v85":
        from .strategies.v85 import V85
        return V85(**overrides)
    if name == "v86":
        from .strategies.v86 import V86
        return V86(**overrides)
    if name == "v87":
        from .strategies.v87 import V87
        return V87(**overrides)
    if name == "v88":
        from .strategies.v88 import V88
        return V88(**overrides)
    if name == "v88_norange":
        from .strategies.v88 import V88NoRange
        return V88NoRange(**overrides)
    if name == "v88_live":
        from .strategies.v88 import V88Live
        return V88Live(**overrides)
    if name == "v88_live_norange":
        from .strategies.v88 import V88LiveNoRange
        return V88LiveNoRange(**overrides)
    if name == "v89":
        from .strategies.v89 import V89
        return V89(**overrides)
    if name == "v89_nohourf":
        from .strategies.v89 import V89NoRangeHour
        return V89NoRangeHour(**overrides)
    if name == "v90":
        from .strategies.v90 import V90
        return V90(**overrides)
    if name == "v91":
        from .strategies.v91 import V91
        return V91(**overrides)
    if name == "v92":
        from .strategies.v92 import V92
        return V92(**overrides)
    if name == "v94":
        from .strategies.v94 import V94
        return V94(**overrides)
    if name == "v95":
        from .strategies.v95 import V95
        return V95(**overrides)
    if name == "v96":
        from .strategies.v96 import V96
        return V96(**overrides)
    raise ValueError(
        f"Estratégia desconhecida: {name!r}. "
        f"Disponíveis: v84..v96, v88_norange, v88_live, v88_live_norange"
    )


def _load_data(symbol: str, mode: str, recent: bool = False, daily_atr: bool = True,
               date_from: str = None, date_to: str = None, true_range_atr: bool = False):
    """
    Carrega dados e retorna (m5_ind, m1_price, instrument).

    recent         : se True e mode='candle', usa candle_file_recent (contrato atual).
    daily_atr      : se True (padrão), ATR com reset diário (replica live bot).
    true_range_atr : se True (V95+), ATR com True Range contínuo (prioridade sobre daily_atr).
    """
    from .config import INSTRUMENTS
    from .data_loader import load_tick_bars, build_m1_price_seq, load_candle_csv, load_indicators_csv
    from .indicators import add_indicators, add_extra_adx

    if symbol not in INSTRUMENTS:
        raise ValueError(f"Símbolo desconhecido: {symbol!r}. Disponíveis: {list(INSTRUMENTS)}")

    cfg = INSTRUMENTS[symbol]

    if mode == "mt5":
        # Usa indicadores exportados diretamente do MT5 — ground truth exato
        ind_src = getattr(cfg, "indicators_file", "")
        if not ind_src:
            raise ValueError(f"indicators_file não configurado para {symbol!r}.")
        print(f"[INFO] Carregando indicadores MT5 de {ind_src}...", flush=True)
        m5_ind = load_indicators_csv(ind_src)
        if date_from:
            m5_ind = m5_ind[m5_ind["dt"].dt.date.astype(str) >= date_from].reset_index(drop=True)
        if date_to:
            m5_ind = m5_ind[m5_ind["dt"].dt.date.astype(str) <= date_to].reset_index(drop=True)
        print(f"[INFO] MT5 indicators: {len(m5_ind)} barras "
              f"({m5_ind['dt'].iloc[0].date()} → {m5_ind['dt'].iloc[-1].date()})", flush=True)

        # Tenta carregar M1 para H-Progress
        m1_price = {}
        m1_src = getattr(cfg, "candle_m1_recent", "")
        if m1_src:
            from pathlib import Path as _Path
            if _Path(m1_src).exists():
                m1_candles = load_candle_csv(m1_src)
                m1_price   = build_m1_price_seq(m1_candles)
                print(f"[INFO] M1: {len(m1_candles)} barras → {len(m1_price)} grupos M5", flush=True)
        return m5_ind, m1_price, cfg

    if mode in ("tick", "tick-real"):
        bars = load_tick_bars(cfg.tick_file, freqs=["1min", "5min"])
        m1   = bars["1min"]
        m5   = bars["5min"]
        m1_price = build_m1_price_seq(m1)
    else:
        candle_src = cfg.candle_file_recent if recent and cfg.candle_file_recent else cfg.candle_file
        if not candle_src:
            raise ValueError(
                f"candle_file não configurado para {symbol!r}. "
                f"Exporte o CSV do MT5 e atualize backtest/config.py."
            )
        print(f"[INFO] Carregando candles M5 de {candle_src}...", flush=True)
        m5 = load_candle_csv(candle_src)
        mode_label = "recent" if recent and cfg.candle_file_recent else "histórico"
        print(f"[INFO] Candles M5 {mode_label}: {len(m5)} barras "
              f"({m5['dt'].iloc[0].date()} → {m5['dt'].iloc[-1].date()})", flush=True)
        # Aplica filtros de data para modo candle (mesmo que mt5)
        if date_from:
            m5 = m5[m5["dt"].dt.date.astype(str) >= date_from].reset_index(drop=True)
        if date_to:
            m5 = m5[m5["dt"].dt.date.astype(str) <= date_to].reset_index(drop=True)

        # Tenta carregar M1 para H-Progress intrabar (opcional)
        m1_price = {}
        m1_src = getattr(cfg, "candle_m1_recent", "") if recent else ""
        if m1_src:
            from pathlib import Path as _Path
            if _Path(m1_src).exists():
                print(f"[INFO] Carregando candles M1 de {m1_src}...", flush=True)
                m1_candles = load_candle_csv(m1_src)
                m1_price   = build_m1_price_seq(m1_candles)
                print(f"[INFO] M1: {len(m1_candles)} barras → {len(m1_price)} grupos M5", flush=True)
            else:
                print(f"[WARN] M1 candle file não encontrado: {m1_src} (H-Progress desativado)", flush=True)

    atr_label = 'true_range' if true_range_atr else ('daily' if daily_atr else 'cross-day')
    print(f"[INFO] Calculando indicadores (atr={atr_label}, volume={'sim' if 'volume' in m5.columns else 'não'})...", flush=True)
    m5_ind = add_indicators(m5, adx_period=14, daily_atr=daily_atr, true_range_atr=true_range_atr)
    m5_ind = add_extra_adx(m5_ind, 7)  # ADX7 para V85+
    # V92+: RSI, BB, VWAP já calculados em add_indicators quando volume disponível

    return m5_ind, m1_price, cfg


def cmd_run(args):
    from .engine import run_backtest
    from .report import analyze, print_summary

    daily_atr = not getattr(args, "no_daily_atr", False)
    recent    = getattr(args, "recent", False)
    strategy  = _load_strategy(args.strategy)
    true_range = getattr(strategy, "use_true_range_atr", False)

    if args.mode == "tick-real":
        _run_tick_real(args, strategy, daily_atr)
        return

    m5_ind, m1_price, cfg = _load_data(args.symbol, args.mode, recent=recent, daily_atr=daily_atr,
                                        date_from=getattr(args, "from_date", None),
                                        date_to=getattr(args, "to_date", None),
                                        true_range_atr=true_range)
    print(f"[RUN] {strategy.name.upper()} | {args.symbol} | {args.mode}", flush=True)
    trades = run_backtest(m5_ind, m1_price, strategy, cfg)
    stats  = analyze(trades, strategy.name.upper(), cfg)
    print_summary(stats, trades, strategy.name.upper(), args.symbol, cfg)


def _run_tick_real(args, strategy, daily_atr: bool):
    """Modo tick-real: execução tick-a-tick com bid/ask reais."""
    from .config import INSTRUMENTS
    from .data_loader import load_ticks_raw
    from .indicators import add_indicators, add_extra_adx
    from .engine_tick_real import run_backtest_tick_real
    from .report import analyze, print_summary

    cfg = INSTRUMENTS[args.symbol]
    date_from = getattr(args, "from_date", None)
    date_to   = getattr(args, "to_date",   None)

    print(f"[INFO] Carregando ticks com bid/ask de {cfg.tick_file}...", flush=True)
    ticks_raw = load_ticks_raw(cfg.tick_file)
    if date_from:
        ticks_raw = ticks_raw[ticks_raw["dt"].dt.date.astype(str) >= date_from].reset_index(drop=True)
    if date_to:
        ticks_raw = ticks_raw[ticks_raw["dt"].dt.date.astype(str) <= date_to].reset_index(drop=True)
    print(f"[INFO] {len(ticks_raw):,} ticks | "
          f"{ticks_raw['dt'].iloc[0]} → {ticks_raw['dt'].iloc[-1]}", flush=True)

    # Reconstruir M5 dos ticks e calcular indicadores (cold-start)
    print("[INFO] Reconstruindo barras M5 e calculando indicadores...", flush=True)
    from .data_loader import ticks_to_ohlcv
    m5_raw = ticks_to_ohlcv(ticks_raw[["dt", "bid"]].rename(columns={"bid": "price"})
                             .assign(volume=1.0), "5min")
    # Rebuild usando last price para compatibilidade com add_indicators
    from .data_loader import load_ticks
    ticks_last = load_ticks(cfg.tick_file)
    if date_from:
        ticks_last = ticks_last[ticks_last["dt"].dt.date.astype(str) >= date_from].reset_index(drop=True)
    if date_to:
        ticks_last = ticks_last[ticks_last["dt"].dt.date.astype(str) <= date_to].reset_index(drop=True)
    m5_from_last = ticks_to_ohlcv(ticks_last, "5min")
    # Merge m5 OHLCV (preços last) com tick count
    true_range = getattr(strategy, "use_true_range_atr", False)
    m5_ind = add_indicators(m5_from_last, adx_period=14, daily_atr=daily_atr, true_range_atr=true_range)
    m5_ind = add_extra_adx(m5_ind, 7)

    print(f"[INFO] M5: {len(m5_ind)} barras | "
          f"{m5_ind['dt'].iloc[0].date()} → {m5_ind['dt'].iloc[-1].date()}", flush=True)
    print(f"[RUN] {strategy.name.upper()} | {args.symbol} | tick-real", flush=True)

    trades = run_backtest_tick_real(ticks_raw, m5_ind, strategy, cfg)
    stats  = analyze(trades, strategy.name.upper(), cfg)
    print_summary(stats, trades, strategy.name.upper(), args.symbol, cfg)


def cmd_compare(args):
    from .engine import run_backtest
    from .report import analyze, print_table, print_summary

    daily_atr = not getattr(args, "no_daily_atr", False)
    names = [s.strip() for s in args.strategies.split(",")]
    m5_ind, m1_price, cfg = _load_data(args.symbol, args.mode, daily_atr=daily_atr)

    all_stats  = []
    all_trades = {}
    for name in names:
        strategy = _load_strategy(name)
        print(f"[RUN] {name.upper()}...", flush=True)
        trades = run_backtest(m5_ind, m1_price, strategy, cfg)
        stats  = analyze(trades, name.upper(), cfg)
        all_stats.append(stats)
        all_trades[name] = (trades, stats)

    print_table(all_stats)

    if args.detail:
        for name, (trades, stats) in all_trades.items():
            print_summary(stats, trades, name.upper(), args.symbol, cfg)


def cmd_grid(args):
    """Grid search sobre parâmetros da estratégia."""
    from itertools import product
    from .engine import run_backtest
    from .report import analyze, print_table

    # Parse --param adx_period=7,14 → {"adx_period": [7, 14]}
    param_grid: dict[str, list] = {}
    for p in (args.param or []):
        key, vals = p.split("=", 1)
        parsed = []
        for v in vals.split(","):
            v = v.strip()
            try:
                parsed.append(int(v))
            except ValueError:
                try:
                    parsed.append(float(v))
                except ValueError:
                    parsed.append(v)
        param_grid[key.strip()] = parsed

    daily_atr = not getattr(args, "no_daily_atr", False)
    recent    = getattr(args, "recent", False)
    # Detecta true_range_atr da strategy base (pode ser sobrescrito pelo grid)
    base_strategy = _load_strategy(args.strategy)
    true_range = getattr(base_strategy, "use_true_range_atr", False)
    m5_ind, m1_price, cfg = _load_data(args.symbol, args.mode, recent=recent,
                                        daily_atr=daily_atr,
                                        date_from=getattr(args, "from_date", None),
                                        date_to=getattr(args, "to_date", None),
                                        true_range_atr=true_range)

    keys   = list(param_grid.keys())
    combos = list(product(*[param_grid[k] for k in keys]))
    print(f"[GRID] {len(combos)} combinações | {args.strategy.upper()} | {args.symbol}", flush=True)

    results = []
    for combo in combos:
        overrides = dict(zip(keys, combo))
        label = args.strategy.upper() + " " + " ".join(f"{k}={v}" for k, v in overrides.items())
        strategy = _load_strategy(args.strategy, overrides)
        trades   = run_backtest(m5_ind, m1_price, strategy, cfg)
        stats    = analyze(trades, label, cfg)
        results.append(stats)
        print(f"  {label}: {stats.get('daily_pts', 0):+.1f} pts/dia | PF={stats.get('PF',0):.2f} | SL={stats.get('SL_true',0)}", flush=True)

    results.sort(key=lambda r: r.get("daily_pts", float("-inf")), reverse=True)
    print("\n=== TOP 10 CONFIGURAÇÕES ===")
    print_table(results[:10])


def _day_with_warmup(m5_ind: "pd.DataFrame", day_filter, n_warmup: int = 50):
    """
    Retorna DataFrame com N barras de warmup do dia anterior + todas as barras
    do dia alvo. Usado por replay e today para evitar cold-start de indicadores
    (replicar comportamento do bot que carrega últimas 50 barras do MT5).

    day_filter: máscara booleana ou comparador (date string ou date object)
    Retorna (m5_with_warmup, idx_day_start) onde idx_day_start é o índice
    dentro do DataFrame retornado onde o dia alvo começa.
    """
    import numpy as np
    mask_day = m5_ind["dt"].dt.date.astype(str) == str(day_filter)
    if not mask_day.any():
        return None, None
    first_pos = int(np.where(mask_day)[0][0])
    warmup_start = max(0, first_pos - n_warmup)
    m5_out = m5_ind.iloc[warmup_start:].reset_index(drop=True)
    idx_day_start = first_pos - warmup_start
    return m5_out, idx_day_start


def cmd_today(args):
    """Simula o dia de hoje nos dados de tick disponíveis."""
    from .engine import run_backtest
    from .report import analyze, print_summary

    daily_atr = not getattr(args, "no_daily_atr", False)
    strategy  = _load_strategy(args.strategy)
    m5_ind, m1_price, cfg = _load_data(args.symbol, "tick", daily_atr=daily_atr)

    # Usa o último dia disponível nos dados (não usa relógio local)
    last_day = m5_ind["dt"].dt.date.max()
    m5_today, idx_start = _day_with_warmup(m5_ind, last_day)
    if m5_today is None:
        print("[ERRO] Nenhuma barra M5 disponível nos dados de tick.")
        return

    print(f"[TODAY] {strategy.name.upper()} | {args.symbol} | {last_day} (warmup={idx_start} barras)", flush=True)
    all_trades = run_backtest(m5_today, m1_price, strategy, cfg)
    trades = [t for t in all_trades if str(getattr(t["entry_dt"], "date", lambda: t["entry_dt"])()) == str(last_day)]
    stats  = analyze(trades, strategy.name.upper(), cfg)
    print_summary(stats, trades, strategy.name.upper(), args.symbol, cfg)


def cmd_replay(args):
    """Replay de uma data específica, com warmup do dia anterior."""
    from .engine import run_backtest
    from .report import analyze, print_summary

    daily_atr = not getattr(args, "no_daily_atr", False)
    strategy  = _load_strategy(args.strategy)
    m5_ind, m1_price, cfg = _load_data(args.symbol, "tick", daily_atr=daily_atr)

    m5_replay, idx_start = _day_with_warmup(m5_ind, args.date)
    if m5_replay is None:
        print(f"[ERRO] Nenhuma barra para a data {args.date}.")
        return

    print(f"[REPLAY] {strategy.name.upper()} | {args.symbol} | {args.date} (warmup={idx_start} barras)", flush=True)
    all_trades = run_backtest(m5_replay, m1_price, strategy, cfg)
    # Filtra apenas os trades do dia alvo (descarta trades do período de warmup)
    trades = [t for t in all_trades if str(getattr(t["entry_dt"], "date", lambda: t["entry_dt"])()) == args.date]
    stats  = analyze(trades, strategy.name.upper(), cfg)
    print_summary(stats, trades, strategy.name.upper(), args.symbol, cfg)


def cmd_trace(args):
    """Exporta CSV com avaliação de cada barra M5 — análogo ao Trace_V91 do MT5.

    Colunas: Data/Hora, ATR, ADX, dist, EMA20, EMA5_slope, EMA20_slope,
             hora_hhmm, modo, abs_dist, gmin, gmax, filtro
    filtro: HORA | ATR_BAIXO | ATR_ALTO | ADX_MAX | COOLDOWN | EM_POSICAO |
            RANGE_HORA | DIST_RANGE | EMA_SLOPE | DIST_TREND | ENTRADA
    """
    import csv
    import pandas as pd

    strategy = _load_strategy(args.strategy)
    m5_ind, _, cfg = _load_data(args.symbol, args.mode, recent=False, daily_atr=True,
                                date_from=getattr(args, "from_date", None),
                                date_to=getattr(args, "to_date", None))

    s   = strategy
    records = m5_ind.to_dict("records")
    N       = len(records)

    out_path = args.output or f"trace_{args.strategy}_{args.symbol}_{args.mode}.csv"
    adx_col = s.adx_col()

    rows = []
    from datetime import date as _date
    in_position   = False
    cooldown_until_idx = 0
    sl_consec = 0
    cb_day = None

    from .engine import Position, _check_sl_tp
    from typing import Optional
    pos: Optional[Position] = None

    # No modo mt5, indicadores já estão pré-calculados — sem warmup necessário.
    # No modo candle/tick, 20 barras de warmup para estabilizar EMA/ADX.
    warmup = 1 if args.mode == "mt5" else 20
    for i in range(warmup, N - 1):
        c       = records[i]
        c1      = records[i + 1]
        bar_dt  = c["dt"]
        hora_c  = float(c["hora"])
        cur_day = bar_dt.date()
        hora_hhmm = int(hora_c) * 100 + int((hora_c % 1) * 60)

        # Atualizar posição (simplificado — apenas para tracking de EM_POSICAO)
        if pos is not None:
            hit = _check_sl_tp(pos, float(c["low"]), float(c["high"]))
            if hit:
                pos = None
                if hit == "SL":
                    cooldown_until_idx = i + s.cooldown_candles
            continue  # não avalia entrada enquanto em posição (tratado abaixo)

        # ── ATR e indicadores ─────────────────────────────────────────────────
        atr_v = c.get("ATR")
        adx_v = float(c.get(adx_col) or float("nan"))
        dist_v = float(c["dist"])
        ema20_v = float(c.get("EMA20") or 0)
        ema5_slope = float(c.get("EMA5_SLOPE") or 0)
        ema20_slope = float(c.get("EMA_SLOPE") or 0)
        abs_dist = abs(dist_v)
        import math
        if pd.isna(adx_v) or math.isnan(adx_v):
            continue

        modo_str = "RANGE" if adx_v <= s.adx_threshold else "TREND"
        atr_f = float(atr_v) if atr_v is not None and not pd.isna(atr_v) else 0.0
        gmin = s.resolve_gatilho_min(modo_str)
        gmax = s.resolve_gatilho_max(atr_f, modo_str)

        def row(filtro):
            return {
                "Data/Hora":   bar_dt.strftime("%Y-%m-%d %H:%M"),
                "ATR_py":      round(atr_f, 2),
                "ADX_py":      round(adx_v, 2),
                "dist_py":     round(dist_v, 2),
                "EMA20_py":    round(ema20_v, 2),
                "EMA5_slope":  round(ema5_slope, 2),
                "EMA20_slope": round(ema20_slope, 2),
                "hora_hhmm":   hora_hhmm,
                "modo":        modo_str,
                "abs_dist":    round(abs_dist, 2),
                "gmin":        round(gmin, 2),
                "gmax":        round(gmax, 2),
                "filtro":      filtro,
            }

        # Filtros — mesma ordem do engine
        if hora_c < cfg.hora_start or hora_c >= cfg.hora_limit:
            rows.append(row("HORA")); continue
        if atr_v is None or pd.isna(atr_v) or atr_f > s.atr_max:
            rows.append(row("ATR_ALTO")); continue
        if getattr(s, "atr_min", 0) > 0 and atr_f < s.atr_min:
            rows.append(row("ATR_BAIXO")); continue
        if adx_v > s.adx_max:
            rows.append(row("ADX_MAX")); continue
        if s.cooldown_candles > 0 and i <= cooldown_until_idx:
            rows.append(row("COOLDOWN")); continue

        # Modo
        if modo_str == "RANGE":
            range_bloq = getattr(s, "range_hora_bloqueio", None)
            if range_bloq and any(lo <= hora_c < hi for lo, hi in range_bloq):
                rows.append(row("RANGE_HORA")); continue
            if abs_dist <= gmin or abs_dist > gmax:
                rows.append(row("DIST_RANGE")); continue
            sl_v = float(c.get("EMA_SLOPE") or 0)
            signal = "SELL" if dist_v > 0 else "BUY"
            if signal == "SELL" and sl_v > s.ema_slope_max:
                rows.append(row("EMA_SLOPE")); continue
            if signal == "BUY"  and sl_v < -s.ema_slope_max:
                rows.append(row("EMA_SLOPE")); continue
        else:
            if abs_dist <= gmin or abs_dist > gmax:
                rows.append(row("DIST_TREND")); continue

        # Entrada
        rows.append(row("ENTRADA"))
        tp_pts = round(atr_f * (s.tp_range_mult if modo_str == "RANGE" else s.tp_trend_mult))
        sl_pts = round(atr_f * (s.sl_range_mult if modo_str == "RANGE" else s.sl_trend_mult))
        signal_dir = ("SELL" if dist_v > 0 else "BUY") if modo_str == "RANGE" else ("BUY" if dist_v > 0 else "SELL")
        if tp_pts > 0 and sl_pts > 0:
            pos = Position(
                signal=signal_dir, mode=modo_str, entry=float(c1["open"]),
                tp_pts=tp_pts, sl_pts=sl_pts,
                entry_hora=bar_dt.strftime("%H:%M"),
                entry_slope=ema5_slope, entry_dt=c1["dt"],
                be_offset=s.be_offset,
            )

    df_out = pd.DataFrame(rows)
    df_out.to_csv(out_path, index=False)
    # Resumo do filtro
    print(f"[TRACE] {len(df_out)} barras → {out_path}")
    print(df_out["filtro"].value_counts().to_string())


def main():
    parser = argparse.ArgumentParser(
        prog="python -m backtest",
        description="Framework de backtest WIN/WDO",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def _add_common(p):
        """Flags comuns a todos os subcomandos."""
        p.add_argument("--no-daily-atr", dest="no_daily_atr", action="store_true",
                       help="Desativa ATR com reset diário (usa ATR cross-day legado)")

    # run
    p = sub.add_parser("run", help="Roda backtest de uma estratégia")
    p.add_argument("--strategy", required=True, help="v84, v85, v86 ou v87")
    p.add_argument("--symbol",   required=True, help="WIN ou WDO")
    p.add_argument("--mode",      default="mt5", choices=["tick", "candle", "mt5", "tick-real"])
    p.add_argument("--recent",    action="store_true",
                   help="Modo candle: usa contrato atual (WINJ26) em vez do histórico longo (IND$)")
    p.add_argument("--from-date", dest="from_date", default=None, help="Filtro início ex: 2026-04-01")
    p.add_argument("--to-date",   dest="to_date",   default=None, help="Filtro fim   ex: 2026-04-11")
    _add_common(p)

    # compare
    p = sub.add_parser("compare", help="Compara múltiplas estratégias")
    p.add_argument("--strategies", required=True, help="ex: v86,v87")
    p.add_argument("--symbol",     required=True)
    p.add_argument("--mode",       default="tick", choices=["tick", "candle", "mt5"])
    p.add_argument("--detail",     action="store_true")
    _add_common(p)

    # grid
    p = sub.add_parser("grid", help="Grid search de parâmetros")
    p.add_argument("--strategy",  required=True)
    p.add_argument("--symbol",    required=True)
    p.add_argument("--mode",      default="mt5", choices=["tick", "candle", "mt5"])
    p.add_argument("--recent",    action="store_true",
                   help="Modo candle: usa contrato atual (WINJ26) em vez do histórico longo")
    p.add_argument("--param",     action="append", help="ex: --param cooldown_candles=0,1,2")
    p.add_argument("--from-date", dest="from_date", default=None)
    p.add_argument("--to-date",   dest="to_date",   default=None)
    _add_common(p)

    # today
    p = sub.add_parser("today", help="Último dia disponível nos dados de tick")
    p.add_argument("--strategy", required=True)
    p.add_argument("--symbol",   required=True)
    _add_common(p)

    # replay
    p = sub.add_parser("replay", help="Replay de uma data específica")
    p.add_argument("--strategy", required=True)
    p.add_argument("--symbol",   required=True)
    p.add_argument("--date",     required=True, help="ex: 2026-04-10")
    _add_common(p)

    # trace
    p = sub.add_parser("trace", help="Exporta CSV de avaliação barra-a-barra para alinhar com MT5")
    p.add_argument("--strategy",  required=True)
    p.add_argument("--symbol",    required=True)
    p.add_argument("--mode",      default="mt5", choices=["tick", "candle", "mt5"])
    p.add_argument("--from-date", dest="from_date", default=None)
    p.add_argument("--to-date",   dest="to_date",   default=None)
    p.add_argument("--output",    default=None, help="Caminho do CSV de saída")
    _add_common(p)

    args = parser.parse_args()
    {
        "run":     cmd_run,
        "compare": cmd_compare,
        "grid":    cmd_grid,
        "today":   cmd_today,
        "replay":  cmd_replay,
        "trace":   cmd_trace,
    }[args.command](args)


if __name__ == "__main__":
    main()
