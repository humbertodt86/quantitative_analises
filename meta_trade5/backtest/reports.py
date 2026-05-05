"""
V134 Standardized Reports
=========================
Gerador de relatórios padronizados para backtests V134.

Saídas:
- Resumo geral (n, PnL, WR, PF, MaxDD)
- Aberturas por modo
- Aberturas por dia
- Aberturas por hora
- Análise de indicadores
- TP/SL/BE/HP por modo
"""
import sys
sys.path.insert(0, '.')

from collections import defaultdict
from datetime import datetime
import numpy as np


def calculate_metrics(results):
    """Calcular métricas básicas de uma lista de resultados."""
    if not results:
        return {'n': 0, 'pnl': 0, 'exp': 0, 'wr': 0, 'pf': 0, 'max_dd': 0}

    pnls = [r['pnl'] for r in results]
    hits = [1 if r['hit_type'] == 'TP' else 0 for r in results]

    n = len(pnls)
    total_pnl = sum(pnls)
    win_rate = sum(hits) / n if n > 0 else 0
    avg_pnl = total_pnl / n if n > 0 else 0

    # Max drawdown
    cumsum = np.cumsum(pnls)
    peak = np.maximum.accumulate(cumsum)
    drawdown = peak - cumsum
    max_dd = np.max(drawdown) if len(drawdown) > 0 else 0

    # Profit factor
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    gross_win = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    pf = gross_win / gross_loss if gross_loss > 0 else float('inf')

    return {
        'n': n,
        'pnl': total_pnl,
        'exp': avg_pnl,
        'wr': win_rate * 100,
        'pf': pf,
        'max_dd': max_dd,
        'wins': len(wins),
        'losses': len(losses),
        'avg_win': sum(wins) / len(wins) if wins else 0,
        'avg_loss': sum(losses) / len(losses) if losses else 0,
    }


def format_metrics(m, indent=0):
    """Formatar métricas para impressão."""
    pad = ' ' * indent
    return [
        f"{pad}  n: {m['n']}",
        f"{pad}  PnL: {m['pnl']:+.0f}",
        f"{pad}  Exp: {m['exp']:+.1f}",
        f"{pad}  WR: {m['wr']:.1f}%",
        f"{pad}  PF: {m['pf']:.2f}",
        f"{pad}  MaxDD: {m['max_dd']:+.0f}",
        f"{pad}  Wins: {m['wins']}, Losses: {m['losses']}",
        f"{pad}  Avg Win: {m['avg_win']:+.0f}, Avg Loss: {m['avg_loss']:+.0f}",
    ]


def report_by_mode(results, behp_configs):
    """Relatório por modo de operação."""
    report = []
    report.append("=" * 60)
    report.append("ABERTURAS POR MODO")
    report.append("=" * 60)

    modes = ['SNIPER', 'HUNTER', 'SCALPER']

    for mode in modes:
        mode_results = [r for r in results if r['mode'] == mode]
        if not mode_results:
            report.append(f"\n{mode}: Sem aberturas")
            continue

        m = calculate_metrics(mode_results)
        behp = behp_configs.get(mode, {})

        report.append(f"\n{mode}:")
        report.append(f"  n: {m['n']}")
        report.append(f"  PnL: {m['pnl']:+.0f}")
        report.append(f"  Exp: {m['exp']:+.1f}")
        report.append(f"  WR: {m['wr']:.1f}%")
        report.append(f"  PF: {m['pf']:.2f}")
        report.append(f"  MaxDD: {m['max_dd']:+.0f}")

        # BE/HP config
        if behp:
            report.append(f"\n  BE/HP Config:")
            report.append(f"    be_trigger: {behp.get('be_trigger', 'N/A')}")
            report.append(f"    be_offset: {behp.get('be_offset', 'N/A')}")
            report.append(f"    hp_th: {behp.get('hp_th', 'N/A')}")
            report.append(f"    hp_candles: {behp.get('hp_candles', 'N/A')}")
            report.append(f"    hard_stop: {behp.get('hard_stop', 'N/A')}")

    return '\n'.join(report)


def report_by_day(results):
    """Relatório de aberturas por dia."""
    by_day = defaultdict(list)
    for r in results:
        dt = r['entry_dt']
        if isinstance(dt, str):
            day = dt[:10]  # YYYY-MM-DD
        else:
            day = dt.strftime('%Y-%m-%d')
        by_day[day].append(r)

    report = []
    report.append("=" * 60)
    report.append("ABERTURAS POR DIA")
    report.append("=" * 60)

    sorted_days = sorted(by_day.keys())

    total_pnl = 0
    for day in sorted_days:
        day_results = by_day[day]
        m = calculate_metrics(day_results)
        total_pnl += m['pnl']

        mode_counts = defaultdict(int)
        for r in day_results:
            mode_counts[r['mode']] += 1

        modes_str = ', '.join([f"{k}: {v}" for k, v in sorted(mode_counts.items())])

        report.append(f"\n{day}:")
        report.append(f"  n: {m['n']}, PnL: {m['pnl']:+.0f}, Exp: {m['exp']:+.1f}, WR: {m['wr']:.1f}%")
        report.append(f"  Modos: {modes_str}")

    report.append(f"\n{'='*40}")
    report.append(f"Total: n={len(results)}, PnL={total_pnl:+.0f}")

    return '\n'.join(report)


def report_by_hour(results):
    """Relatório de aberturas por hora."""
    by_hour = defaultdict(list)
    for r in results:
        dt = r['entry_dt']
        if isinstance(dt, str):
            hour = int(dt[11:13])
        else:
            hour = dt.hour
        by_hour[hour].append(r)

    report = []
    report.append("=" * 60)
    report.append("ABERTURAS POR HORA")
    report.append("=" * 60)

    for hour in sorted(by_hour.keys()):
        hour_results = by_hour[hour]
        m = calculate_metrics(hour_results)

        mode_counts = defaultdict(int)
        for r in hour_results:
            mode_counts[r['mode']] += 1

        modes_str = ', '.join([f"{k}: {v}" for k, v in sorted(mode_counts.items())])

        report.append(f"\n{hour:02d}h:")
        report.append(f"  n: {m['n']}, PnL: {m['pnl']:+.0f}, Exp: {m['exp']:+.1f}, WR: {m['wr']:.1f}%")
        report.append(f"  Modos: {modes_str}")

    return '\n'.join(report)


def report_by_indicator(results, indicators_df):
    """Relatório de indicadores por modo."""
    report = []
    report.append("=" * 60)
    report.append("INDICADORES POR MODO")
    report.append("=" * 60)

    # Create lookup for indicator values at entry time
    dt_to_idx = {}
    for i, row in indicators_df.iterrows():
        dt_to_idx[str(row['dt'])] = i

    modes = ['SNIPER', 'HUNTER', 'SCALPER']
    indicator_cols = ['ADX7', 'ATR', 'GK_RATIO', 'EMA5_SLOPE_ABS', 'RSI', 'RIBBON_STATE']

    for mode in modes:
        mode_results = [r for r in results if r['mode'] == mode]
        if not mode_results:
            continue

        report.append(f"\n{mode}:")
        report.append("-" * 40)

        # Collect indicator values for this mode
        for col in indicator_cols:
            if col not in indicators_df.columns:
                continue

            values = []
            for r in mode_results:
                dt = str(r['entry_dt'])
                if dt in dt_to_idx:
                    val = indicators_df.loc[dt_to_idx[dt], col]
                    if val is not None and not np.isnan(val):
                        values.append(val)

            if values:
                report.append(f"\n  {col}:")
                report.append(f"    Min: {min(values):.2f}")
                report.append(f"    Max: {max(values):.2f}")
                report.append(f"    Avg: {np.mean(values):.2f}")
                report.append(f"    Median: {np.median(values):.2f}")

    return '\n'.join(report)


def report_tp_sl_behp(results, config_dict):
    """Relatório de TP/SL/BE/HP por modo."""
    report = []
    report.append("=" * 60)
    report.append("TP / SL / BE / HP POR MODO")
    report.append("=" * 60)

    modes = ['SNIPER', 'HUNTER', 'SCALPER']

    for mode in modes:
        mode_results = [r for r in results if r['mode'] == mode]
        if not mode_results:
            continue

        report.append(f"\n{mode}:")

        # Config values
        mode_cfg = config_dict.get('modes', {}).get(mode, {})
        behp_cfg = mode_cfg.get('behp', {})

        report.append(f"  TP mult: {mode_cfg.get('tp_mult', 'N/A')}")
        report.append(f"  SL mult: {mode_cfg.get('sl_mult', 'N/A')}")
        report.append(f"  ATR avg: {np.mean([r['atr'] for r in mode_results]):.1f}")

        # Actual TP/SL from trades
        tps = [r.get('tp', 0) for r in mode_results]
        sls = [r.get('sl', 0) for r in mode_results]

        if tps:
            report.append(f"\n  TP (actual):")
            report.append(f"    Min: {min(tps):.0f}")
            report.append(f"    Max: {max(tps):.0f}")
            report.append(f"    Avg: {np.mean(tps):.0f}")

        if sls:
            report.append(f"\n  SL (actual):")
            report.append(f"    Min: {min(sls):.0f}")
            report.append(f"    Max: {max(sls):.0f}")
            report.append(f"    Avg: {np.mean(sls):.0f}")

        # BE/HP from config
        report.append(f"\n  BE/HP (config):")
        report.append(f"    be_trigger: {behp_cfg.get('be_trigger', 'N/A')}")
        report.append(f"    be_offset: {behp_cfg.get('be_offset', 'N/A')}")
        report.append(f"    hp_th: {behp_cfg.get('hp_th', 'N/A')}")
        report.append(f"    hp_candles: {behp_cfg.get('hp_candles', 'N/A')}")
        report.append(f"    hard_stop: {behp_cfg.get('hard_stop', 'N/A')}")

        # MFE/MAE from trades
        mfe = [r.get('mfe', 0) for r in mode_results]
        mae = [r.get('mae', 0) for r in mode_results]

        report.append(f"\n  MFE/MAE (actual):")
        report.append(f"    MFE avg: {np.mean(mfe):+.0f}")
        report.append(f"    MAE avg: {np.mean(mae):+.0f}")

    return '\n'.join(report)


def generate_full_report(results, config_dict, indicators_df=None, title="V134 REPORT"):
    """Gerar relatório completo."""
    lines = []

    # Header
    lines.append("=" * 70)
    lines.append(title)
    lines.append("=" * 70)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # Overall metrics
    overall = calculate_metrics(results)
    lines.append("RESUMO GERAL")
    lines.append("-" * 40)
    for line in format_metrics(overall):
        lines.append(line)

    # By mode
    lines.append("")
    lines.append(report_by_mode(results, {
        mode: config_dict.get('modes', {}).get(mode, {}).get('behp', {})
        for mode in ['SNIPER', 'HUNTER', 'SCALPER']
    }))

    # By day
    lines.append("")
    lines.append(report_by_day(results))

    # By hour
    lines.append("")
    lines.append(report_by_hour(results))

    # TP/SL/BE/HP
    lines.append("")
    lines.append(report_tp_sl_behp(results, config_dict))

    # Indicators (if df provided)
    if indicators_df is not None:
        lines.append("")
        lines.append(report_by_indicator(results, indicators_df))

    return '\n'.join(lines)


def save_report(report_text, filepath):
    """Salvar relatório em arquivo."""
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report_text)
    print(f"Report saved to: {filepath}")
