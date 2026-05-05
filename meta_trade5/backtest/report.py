"""Relatórios padronizados para backtest."""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from .config import InstrumentConfig


def analyze(
    trades: list[dict],
    label: str,
    instrument: InstrumentConfig,
) -> dict:
    """Analisa lista de trades e retorna dict com métricas."""
    if not trades:
        return {"label": label, "n": 0}

    n         = len(trades)
    pnl_pts   = [t["pnl"] for t in trades]
    total_pts = sum(pnl_pts)
    net_r     = total_pts * instrument.valor_ponto - n * instrument.custo_trade

    dates    = sorted(set(t["entry_dt"].date() for t in trades))
    n_days   = max(len(dates), 1)
    daily_pts = total_pts / n_days

    wins = sum(1 for p in pnl_pts if p > 0)

    tp_full = [t for t in trades if t["res"] == "TP" and not t.get("tp30_used")]
    tp30    = [t for t in trades if t["res"] == "TP" and t.get("tp30_used")]
    be_save = [t for t in trades if t["res"] == "SL" and t["pnl"] >= 0]
    sl_true = [t for t in trades if t["res"] == "SL" and t["pnl"] < 0]
    panic_t = [t for t in trades if t["res"] == "PANIC"]

    trend_t = [t for t in trades if t["mode"] == "TREND"]
    range_t = [t for t in trades if t["mode"] == "RANGE"]

    gross_profit = sum(p for p in pnl_pts if p > 0)
    gross_loss   = abs(sum(p for p in pnl_pts if p < 0))
    pf           = gross_profit / max(gross_loss, 1)
    true_wr      = (len(tp_full) + len(tp30)) / n * 100
    all_wr       = wins / n * 100

    # Recorte março 2026
    mar  = [t for t in trades if t["entry_dt"].month == 3 and t["entry_dt"].year == 2026]
    mar_pts = sum(t["pnl"] for t in mar)
    mar_days = max(len(set(t["entry_dt"].date() for t in mar)), 1) if mar else 1
    mar_daily = mar_pts / mar_days if mar else 0.0

    # Hoje (último dia do dataset)
    last_day = max(t["entry_dt"].date() for t in trades)
    hoje = [t for t in trades if t["entry_dt"].date() == last_day]
    hoje_pts = sum(t["pnl"] for t in hoje)

    return {
        "label":      label,
        "n":          n,
        "n_days":     n_days,
        "total_pts":  round(total_pts, 1),
        "daily_pts":  round(daily_pts, 2),
        "net_R":      round(net_r, 2),
        "WR_true":    round(true_wr, 1),
        "WR_all":     round(all_wr, 1),
        "PF":         round(pf, 2),
        "TP_full":    len(tp_full),
        "TP30":       len(tp30),
        "BE_save":    len(be_save),
        "SL_true":    len(sl_true),
        "PANIC":      len(panic_t),
        "TREND_n":    len(trend_t),
        "RANGE_n":    len(range_t),
        "mar26_pts":  round(mar_pts, 1),
        "mar26_daily": round(mar_daily, 1),
        "hoje_pts":   round(hoje_pts, 1),
        "trades_day": round(n / n_days, 1),
    }


def print_summary(
    stats: dict,
    trades: list[dict],
    label: str,
    symbol: str,
    instrument: InstrumentConfig,
) -> None:
    """Imprime relatório completo de um backtest."""
    s = stats
    if not s or s.get("n", 0) == 0:
        print(f"\n[{label}] Sem trades.")
        return

    n_trades = s["n"]
    dates = sorted(set(t["entry_dt"].date() for t in trades))
    date_range = f"{dates[0]} → {dates[-1]}" if dates else "-"

    print()
    print(f"=== BACKTEST {label} | {symbol} | {date_range} ===")
    print()
    print(f"  Resumo geral")
    print(f"  {'─'*55}")
    print(f"  N trades      : {n_trades:>5} ({s['trades_day']:.1f}/dia)")
    print(f"  PnL total     : {s['total_pts']:>+10.1f} pts")
    print(f"  PnL/dia       : {s['daily_pts']:>+10.1f} pts")
    print(f"  Net R$        : {s['net_R']:>+10.0f}")
    print(f"  WR_tp         : {s['WR_true']:>6.1f}%  (TP cheio + TP30%)")
    print(f"  WR_all        : {s['WR_all']:>6.1f}%  (inclui BEs positivos)")
    print(f"  PF            : {s['PF']:>6.2f}")

    print()
    print(f"  Breakdown de fechamentos")
    print(f"  {'─'*55}")
    pct = lambda x: x / n_trades * 100
    tp_avg  = _avg_pnl([t for t in trades if t["res"] == "TP" and not t.get("tp30_used")])
    tp30_avg = _avg_pnl([t for t in trades if t["res"] == "TP" and t.get("tp30_used")])
    be_avg  = _avg_pnl([t for t in trades if t["res"] == "SL" and t["pnl"] >= 0])
    sl_avg  = _avg_pnl([t for t in trades if t["res"] == "SL" and t["pnl"] < 0])
    print(f"  TP completo   : {s['TP_full']:>5} ({pct(s['TP_full']):5.1f}%)  avg {tp_avg:>+6.0f} pts")
    if s["TP30"]:
        print(f"  TP30% parcial : {s['TP30']:>5} ({pct(s['TP30']):5.1f}%)  avg {tp30_avg:>+6.0f} pts")
    print(f"  BE save       : {s['BE_save']:>5} ({pct(s['BE_save']):5.1f}%)  avg {be_avg:>+6.0f} pts")
    print(f"  SL real       : {s['SL_true']:>5} ({pct(s['SL_true']):5.1f}%)  avg {sl_avg:>+6.0f} pts")
    if s["PANIC"]:
        print(f"  PANIC         : {s['PANIC']:>5} ({pct(s['PANIC']):5.1f}%)")

    print()
    print(f"  Por modo")
    print(f"  {'─'*55}")
    trend_pts = sum(t["pnl"] for t in trades if t["mode"] == "TREND")
    range_pts = sum(t["pnl"] for t in trades if t["mode"] == "RANGE")
    print(f"  TREND         : {s['TREND_n']:>5} trades  | {trend_pts/s['n_days']:>+8.1f} pts/dia")
    print(f"  RANGE         : {s['RANGE_n']:>5} trades  | {range_pts/s['n_days']:>+8.1f} pts/dia")

    print()
    print(f"  Detalhe diário")
    print(f"  {'─'*55}")
    _print_daily(trades)
    print()


def print_table(rows: list[dict]) -> None:
    """Imprime tabela comparativa de múltiplas variantes."""
    print()
    header = (f"{'Variante':<20} {'N':>5} {'Pts/d':>8} {'NetR':>8} "
              f"{'WR_tp%':>7} {'WR_all%':>8} {'PF':>5} "
              f"{'TPf':>4} {'TP30':>5} {'BEsv':>5} {'SLtru':>6} "
              f"{'TRD':>4} {'RNG':>4} {'Mar':>8} {'Hoje':>6}")
    print(header)
    print("-" * len(header))
    for r in rows:
        if not r or r.get("n", 0) == 0:
            continue
        line = (
            f"{r['label']:<20} {r['n']:>5} {r['daily_pts']:>+8.1f} {r['net_R']:>+8.0f} "
            f"{r['WR_true']:>6.1f}% {r['WR_all']:>7.1f}% {r['PF']:>5.2f} "
            f"{r['TP_full']:>4} {r['TP30']:>5} {r['BE_save']:>5} {r['SL_true']:>6} "
            f"{r['TREND_n']:>4} {r['RANGE_n']:>4} "
            f"{r['mar26_pts']:>+8.1f} {r['hoje_pts']:>+6.1f}"
        )
        print(line)
    print()


def _avg_pnl(trades: list[dict]) -> float:
    if not trades:
        return 0.0
    return sum(t["pnl"] for t in trades) / len(trades)


def _print_daily(trades: list[dict]) -> None:
    by_day: dict = defaultdict(list)
    for t in trades:
        by_day[t["entry_dt"].date()].append(t["pnl"])
    for d in sorted(by_day):
        v   = by_day[d]
        wr  = sum(1 for p in v if p > 0) / max(len(v), 1) * 100
        marker = "  <- melhor" if sum(v) == max(sum(by_day[dd]) for dd in by_day) else ""
        marker = "  <- negativo" if sum(v) < 0 else marker
        print(f"  {d}  {sum(v):>+7.1f}  {len(v):>3} trades  {wr:>4.0f}% WR{marker}")
