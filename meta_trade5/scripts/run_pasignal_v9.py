#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RUN PA_SIGNAL V9 — Pipeline F1 → F2 GPU → F3 OOS para PA_SIGNAL_DIR SELL
============================================================================
Re-executa o pipeline completo para TODAS as variantes de PA_SIGNAL_DIR
(signal=-1) nos arquivos:
  - data/variants/PA_SIGNAL_DIR_.parquet
  - data/variants/PA_SIGNAL_DIR_V.parquet

Saídas (docs/WIN_docs/v9/):
  1. f3_rank_{signal}_{variant}_SELL.csv      — Top 3 configs F3
  2. f3_trades_{signal}_{variant}_SELL.csv    — Trades do melhor F3
  3. ranking_consolidado_pasignal_sell.csv    — Ranking consolidado
  4. dna_top10_pasignal_sell.csv              — DNA breakdown top 10
  5. blocking_suggestion_pasignal_sell.csv    — Sugestão de bloqueio

Uso:
    python scripts/run_pasignal_v9.py [--limit N]
"""
import sys, os, time, json, warnings, argparse
from datetime import datetime
from typing import Dict, List, Tuple
import numpy as np
import pandas as pd
import polars as pl

warnings.filterwarnings('ignore')
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# ---------------------------------------------------------------------------
# CUDA PATH FIX
# ---------------------------------------------------------------------------
if os.name == 'nt':
    try:
        import torch
        _torch_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
        if os.path.isdir(_torch_lib) and _torch_lib not in os.environ.get('PATH', ''):
            os.environ['PATH'] = _torch_lib + os.pathsep + os.environ.get('PATH', '')
    except Exception:
        pass

# ---------------------------------------------------------------------------
# IMPORTS DO PIPELINE EXISTENTE
# ---------------------------------------------------------------------------
from scripts.run_all_gpu import (
    run_f1_screening, run_f2_gpu,
    COST, F1_TOP_N, F2_TOP_N, GPU_BATCH_SIZE,
    IS_S, IS_E,
    OOS_TICKS_PATH, OOS_CANDLES_PATH,
    load_tracking, save_tracking, TRACKING_FILE,
    get_variant_columns,
)
from backtest.engine_v2 import BacktestEngine

# ---------------------------------------------------------------------------
# CONFIGURAÇÃO
# ---------------------------------------------------------------------------
VARIANTS_DIR = os.path.join(ROOT, 'data', 'variants')
OUT_DIR = os.path.join(ROOT, 'docs', 'WIN_docs', 'v9')
os.makedirs(OUT_DIR, exist_ok=True)

SIGNAL_FILES = [
    os.path.join(VARIANTS_DIR, 'PA_SIGNAL_DIR_.parquet'),
    os.path.join(VARIANTS_DIR, 'PA_SIGNAL_DIR_V.parquet'),
]

DIRECTION = -1  # SELL

# ---------------------------------------------------------------------------
# F3 OOS MODIFICADO (retorna métricas + trades)
# ---------------------------------------------------------------------------

def run_f3_oos_with_trades(df_oos: pl.DataFrame, ticks_oos: pl.DataFrame,
                           variant_col: str, direction: int, config_f2: Dict) -> Tuple[Dict, List[Dict]]:
    """
    Roda F3 OOS com ticks reais bid/ask.
    Retorna (métricas, trades).
    """
    eng = BacktestEngine(None)
    eng.df = df_oos
    eng.load_ticks_for_simulation(ticks_oos)

    behp = {
        'be_trigger': int(config_f2.get('be_offset', 999999)),
        'be_offset': 25,
        'hp_candles': int(config_f2.get('grace_candles', 2)),
        'hp_th': 0.15,
        'tp30_pct': 0.30,
        'grace_candles': int(config_f2.get('grace_candles', 2)),
        'hard_stop': min(500, int(config_f2.get('atr_max', 500))),
        'cooldown_candles': int(config_f2.get('cooldown_candles', 0)),
        'slope_decay': float(config_f2.get('slope_decay', 0.50)),
    }

    cfg = {
        'name': f'F3_{variant_col}',
        'hour_min': 0.0, 'hour_max': 24.0, 'modo_busca': False,
        'modes': {
            'M': {
                'enabled': True, 'priority': 1, 'signal_field': variant_col,
                'tp_mult': float(config_f2['tp_mult']),
                'sl_mult': float(config_f2['sl_mult']),
                'min_sl': 50,
                'max_sl': min(500, int(config_f2.get('atr_max', 500))),
                'filters': {
                    'ATR': {'min': int(config_f2['atr_min']), 'max': int(config_f2['atr_max'])},
                    variant_col: {'eq': direction},
                },
                'behp': behp
            }
        }
    }

    try:
        eng.load_config_dict(cfg)
        trades = eng.simulate()
        m = eng.calculate_metrics(trades)
        net = int(m['pnl'] - len(trades) * COST)
        metrics = {
            'status': 'ok',
            'net_pnl': net,
            'n_trades': len(trades),
            'win_rate': m['wr'],
            'profit_factor': m['profit_factor'],
            'max_dd': m.get('max_drawdown_pts', 0),
        }
        return metrics, trades
    except Exception as e:
        return {
            'status': 'error', 'error': str(e),
            'net_pnl': 0, 'n_trades': 0,
            'win_rate': 0.0, 'profit_factor': 0.0, 'max_dd': 0
        }, []


# ---------------------------------------------------------------------------
# PROCESSAMENTO DE VARIANTE
# ---------------------------------------------------------------------------

def process_variant(df_is: pd.DataFrame, df_oos_base: pl.DataFrame, ticks_oos: pl.DataFrame,
                    sig_path: str, variant_col: str, direction: int, batch_size: int,
                    use_grid_advisor: bool = True) -> Dict:
    """Processa uma variante completa: F1 → F2 GPU → F3 OOS."""

    signal_name = os.path.basename(sig_path).replace('.parquet', '')
    print(f"\n{'='*80}")
    print(f"VARIANTE: {variant_col} | DIRECAO: {'BUY' if direction==1 else 'SELL'}")
    print(f"{'='*80}")

    result = {
        'variant': variant_col,
        'direction': direction,
        'signal_name': signal_name,
        'phases': {}
    }

    # Merge OOS base com colunas do sinal
    sig_df = pl.read_parquet(sig_path)
    if str(df_oos_base['dt'].dtype) != str(sig_df['dt'].dtype):
        sig_df = sig_df.with_columns(pl.col('dt').cast(df_oos_base['dt'].dtype))
    merge_cols = ['dt', variant_col, 'ATR', 'dist_to_resistance', 'dist_to_support',
                  'book_imbalance', 'cum_delta', 'EMA5']
    merge_cols = [c for c in merge_cols if c in sig_df.columns]
    df_oos_merged = df_oos_base.join(sig_df.select(merge_cols), on='dt', how='left')

    # --- F1 ---
    print("\n[1/3] F1 Screening (CPU)...")
    top30_f1, t_f1 = run_f1_screening(df_is, variant_col, direction)
    print(f"      F1: {len(top30_f1)} configs em {t_f1:.2f}s")
    if not top30_f1:
        return {**result, 'status': 'abort', 'reason': 'f1_no_results'}

    best_f1 = top30_f1[0]
    print(f"      F1 Top 1: PnL={best_f1['net_pnl']:,}  Trades={best_f1['n_trades']}  TP={best_f1['tp_mult']:.1f} SL={best_f1['sl_mult']:.1f}")
    result['phases']['f1'] = {'top30': top30_f1, 'elapsed': t_f1}

    # --- F2 GPU ---
    print("\n[2/3] F2 Optimization (GPU)...")
    df_f2, t_f2 = run_f2_gpu(df_is, variant_col, direction, top30_f1, batch_size, use_grid_advisor)
    print(f"      F2: {len(df_f2)} validos em {t_f2:.2f}s")
    if len(df_f2) == 0:
        return {**result, 'status': 'abort', 'reason': 'f2_no_results'}

    df_f2_valid = df_f2[df_f2['win_rate'] >= 0.0].reset_index(drop=True)
    if len(df_f2_valid) == 0:
        print(f"      [FILTRO] Nenhuma config com WR >= 0%")
        return {**result, 'status': 'abort', 'reason': 'f2_low_wr'}

    top3_f2 = df_f2_valid.head(F2_TOP_N)
    best_f2 = top3_f2.iloc[0]
    print(f"      F2 Top 1: PnL={best_f2['net_pnl']:,.0f}  Trades={int(best_f2['n_trades'])}  WR={best_f2['win_rate']:.1f}%")
    result['phases']['f2'] = {
        'top3': top3_f2.to_dict('records'),
        'elapsed': t_f2,
        'n_valid': len(df_f2_valid),
    }

    # --- F3 OOS ---
    print("\n[3/3] F3 OOS Validation (CPU)...")
    f3_results = []
    f3_trades_list = []
    for i in range(min(F2_TOP_N, len(top3_f2))):
        cfg = top3_f2.iloc[i]
        config_f2 = {
            'tp_mult': cfg['tp_mult'], 'sl_mult': cfg['sl_mult'],
            'atr_min': cfg['atr_min'], 'atr_max': cfg['atr_max'],
            'be_offset': cfg.get('be_offset', 999999),
            'grace_candles': int(cfg.get('grace_candles', 2)),
            'cooldown_candles': int(cfg.get('cooldown_candles', 0)),
            'slope_decay': float(cfg.get('slope_decay', 0.50)),
            'tp_sr_pct': cfg.get('tp_sr_pct', 0.9),
            'sl_sr_pct': cfg.get('sl_sr_pct', 1.15),
            'book_imb_thresh': cfg.get('book_imb_thresh', 0.0),
            'cum_delta_thresh': cfg.get('cum_delta_thresh', 0.0),
        }
        metrics, trades = run_f3_oos_with_trades(
            df_oos_merged, ticks_oos, variant_col, direction, config_f2
        )
        f3_results.append({**metrics, **config_f2, 'rank': i + 1})
        f3_trades_list.append(trades)
        status_icon = "OK" if metrics['status'] == 'ok' else "ERR"
        print(f"      F3 #{i+1}: {status_icon}  PnL={metrics.get('net_pnl', 0):>+7}  ({metrics.get('n_trades', 0)}t, WR={metrics.get('win_rate', 0):.1f}%)")

    best_idx = max(range(len(f3_results)), key=lambda i: f3_results[i].get('net_pnl', 0))
    best_f3 = f3_results[best_idx]
    best_trades = f3_trades_list[best_idx]

    result['phases']['f3'] = {
        'results': f3_results,
        'best': best_f3,
        'best_idx': best_idx,
        'trades': best_trades,
    }
    result['status'] = 'completed'
    result['best_config'] = top3_f2.iloc[0].to_dict() if len(top3_f2) > 0 else {}

    print(f"\n  RESUMO: F1={best_f1['net_pnl']:,} → F2={best_f2['net_pnl']:,.0f} → F3={best_f3.get('net_pnl', 0):+d}")

    return result


# ---------------------------------------------------------------------------
# SALVAR SAÍDAS POR VARIANTE
# ---------------------------------------------------------------------------

def save_variant_outputs(result: Dict):
    """Salva CSVs individuais da variante."""
    signal_name = result['signal_name']
    variant = result['variant']
    direction_str = 'SELL' if result['direction'] == -1 else 'BUY'

    f3_results = result['phases']['f3']['results']

    # 1. F3 Rank (top 3)
    rank_rows = []
    for r in f3_results:
        rank_rows.append({
            'rank': r['rank'],
            'tp': r['tp_mult'],
            'sl': r['sl_mult'],
            'atr_min': r['atr_min'],
            'atr_max': r['atr_max'],
            'f3_net': r['net_pnl'],
            'f3_n': r['n_trades'],
            'f3_wr': r['win_rate'],
            'f3_pf': r['profit_factor'],
        })
    rank_df = pd.DataFrame(rank_rows)
    rank_path = os.path.join(OUT_DIR, f'f3_rank_{signal_name}_{variant}_{direction_str}.csv')
    rank_df.to_csv(rank_path, index=False)
    print(f"      Salvo: {rank_path}")

    # 2. F3 Trades (melhor config)
    trades = result['phases']['f3']['trades']
    if trades:
        trades_df = pd.DataFrame(trades)
        desired_cols = [
            'entry_dt', 'exit_dt', 'direction', 'pnl', 'hit_type',
            'candles_held', 'mfe', 'mae', 'atr', 'tp', 'sl',
            'be_triggered', 'book_imbalance'
        ]
        avail_cols = [c for c in desired_cols if c in trades_df.columns]
        trades_df = trades_df[avail_cols]
        trades_path = os.path.join(OUT_DIR, f'f3_trades_{signal_name}_{variant}_{direction_str}.csv')
        trades_df.to_csv(trades_path, index=False)
        print(f"      Salvo: {trades_path}")


# ---------------------------------------------------------------------------
# RANKING CONSOLIDADO
# ---------------------------------------------------------------------------

def build_consolidated_ranking(all_results: List[Dict]) -> pd.DataFrame:
    """Monta ranking consolidado de todas as variantes."""
    rows = []
    for r in all_results:
        if r['status'] != 'completed':
            continue
        best = r['phases']['f3']['best']
        rows.append({
            'signal': r['signal_name'],
            'variant': r['variant'],
            'f3_net': best['net_pnl'],
            'f3_n': best['n_trades'],
            'f3_wr': best['win_rate'],
            'f3_pf': best['profit_factor'],
            'tp': best['tp_mult'],
            'sl': best['sl_mult'],
            'atr_min': best['atr_min'],
            'atr_max': best['atr_max'],
            'be_offset': best.get('be_offset', 999999),
            'grace_candles': best.get('grace_candles', 2),
            'cooldown_candles': best.get('cooldown_candles', 0),
            'slope_decay': best.get('slope_decay', 0.50),
        })
    df = pd.DataFrame(rows)
    df = df.sort_values('f3_net', ascending=False).reset_index(drop=True)
    df['rank'] = df.index + 1
    cols = [
        'rank', 'signal', 'variant', 'f3_net', 'f3_n', 'f3_wr', 'f3_pf',
        'tp', 'sl', 'atr_min', 'atr_max', 'be_offset',
        'grace_candles', 'cooldown_candles', 'slope_decay'
    ]
    df = df[cols]
    return df


# ---------------------------------------------------------------------------
# DNA ANALYSIS — TOP 10
# ---------------------------------------------------------------------------

def build_dna_top10(top10_results: List[Dict]) -> pd.DataFrame:
    """Gera breakdown DNA para as top 10 variantes."""
    rows = []
    for r in top10_results:
        trades = r['phases']['f3'].get('trades', [])
        sv = f"{r['signal_name']}/{r['variant']}"
        if not trades:
            continue

        pnls = [t['pnl'] for t in trades]
        hit_types = [t.get('hit_type', 'UNKNOWN') for t in trades]
        mfe_vals = [t.get('mfe', 0) for t in trades]
        mae_vals = [t.get('mae', 0) for t in trades]

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        pf = (sum(wins) / abs(sum(losses))) if losses else 999

        metrics = [
            ('total_pnl', sum(pnls)),
            ('n_trades', len(pnls)),
            ('win_rate', (len(wins) / len(pnls) * 100) if pnls else 0),
            ('profit_factor', pf),
            ('avg_trade', sum(pnls) / len(pnls) if pnls else 0),
            ('max_win', max(pnls) if pnls else 0),
            ('max_loss', min(pnls) if pnls else 0),
            ('be_hits', hit_types.count('BE')),
            ('sl_hits', hit_types.count('SL')),
            ('tp_hits', hit_types.count('TP')),
            ('avg_mfe', sum(mfe_vals) / len(mfe_vals) if mfe_vals else 0),
            ('avg_mae', sum(mae_vals) / len(mae_vals) if mae_vals else 0),
        ]
        for metric, value in metrics:
            rows.append({
                'signal_variant': sv,
                'metric': metric,
                'value': round(value, 4) if isinstance(value, float) else value
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# BLOCKING SUGGESTION
# ---------------------------------------------------------------------------

def build_blocking_suggestion(top10_results: List[Dict]) -> pd.DataFrame:
    """Gera sugestão de bloqueio por segmento negativo."""
    rows = []
    for r in top10_results:
        trades = r['phases']['f3'].get('trades', [])
        sv = f"{r['signal_name']}/{r['variant']}"
        if not trades:
            rows.append({
                'signal_variant': sv,
                'block_reason': 'no_trades',
                'pct_of_pnl': 0.0,
                'projected_pnl_if_blocked': 0,
            })
            continue

        df_trades = pd.DataFrame(trades)
        total_pnl = df_trades['pnl'].sum()

        candidates = []

        # Por hora
        df_trades['entry_hour'] = pd.to_datetime(df_trades['entry_dt']).dt.hour
        hourly = df_trades.groupby('entry_hour').agg(
            pnl=('pnl', 'sum'),
            n=('entry_dt', 'count')
        ).reset_index()
        for _, row in hourly.iterrows():
            if row['pnl'] < 0 and row['n'] >= 3:
                candidates.append({
                    'reason': f"hour_{int(row['entry_hour']):02d}_negative",
                    'pnl': row['pnl']
                })

        # Por dia da semana
        df_trades['entry_dow'] = pd.to_datetime(df_trades['entry_dt']).dt.day_name()
        dow = df_trades.groupby('entry_dow').agg(
            pnl=('pnl', 'sum'),
            n=('entry_dt', 'count')
        ).reset_index()
        for _, row in dow.iterrows():
            if row['pnl'] < 0 and row['n'] >= 3:
                candidates.append({
                    'reason': f"dow_{row['entry_dow']}_negative",
                    'pnl': row['pnl']
                })

        # Por hit_type
        hit = df_trades.groupby('hit_type').agg(
            pnl=('pnl', 'sum'),
            n=('entry_dt', 'count')
        ).reset_index()
        for _, row in hit.iterrows():
            if row['pnl'] < 0 and row['n'] >= 3:
                candidates.append({
                    'reason': f"hit_{row['hit_type']}_negative",
                    'pnl': row['pnl']
                })

        if candidates:
            # Pior segmento (mais negativo)
            candidates.sort(key=lambda x: x['pnl'])
            worst = candidates[0]
            pct = (abs(worst['pnl']) / abs(total_pnl) * 100) if total_pnl != 0 else 0
            projected = total_pnl - worst['pnl']
            rows.append({
                'signal_variant': sv,
                'block_reason': worst['reason'],
                'pct_of_pnl': round(pct, 2),
                'projected_pnl_if_blocked': round(projected, 2),
            })
        else:
            rows.append({
                'signal_variant': sv,
                'block_reason': 'none',
                'pct_of_pnl': 0.0,
                'projected_pnl_if_blocked': round(total_pnl, 2),
            })

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='RUN PA_SIGNAL V9')
    parser.add_argument('--limit', type=int, default=0, help='Limite de variantes por arquivo (0=todos)')
    parser.add_argument('--batch-size', type=int, default=GPU_BATCH_SIZE, help='GPU batch size')
    parser.add_argument('--no-grid-advisor', action='store_true', default=False, help='Desativar GridAdvisor')
    args = parser.parse_args()

    use_grid_advisor = not args.no_grid_advisor

    # Limpa tracking para PA_SIGNAL_DIR (evita skip)
    tracking = load_tracking()
    dir_key = f'signal_{DIRECTION}'
    if dir_key in tracking:
        tracking[dir_key]['completed'] = [
            k for k in tracking[dir_key].get('completed', [])
            if not k.startswith('PA_SIGNAL_DIR')
        ]
        save_tracking(tracking)
        print(f"[TRACKING] Limpado {dir_key} para PA_SIGNAL_DIR*")

    print(f"\n{'='*80}")
    print("RUN PA_SIGNAL V9 — Pipeline F1 → F2 GPU → F3 OOS")
    print(f"{'='*80}")
    print(f"Direcao: SELL (signal=-1)")
    print(f"GridAdvisor: {'ON' if use_grid_advisor else 'OFF'}")
    print(f"Arquivos: {len(SIGNAL_FILES)}")
    print(f"GPU batch size: {args.batch_size:,}")

    # Carrega dados OOS 1x
    print("\n[0/3] Carregando dados OOS...")
    t0 = time.time()

    if not os.path.exists(OOS_TICKS_PATH):
        print(f"[ERRO] OOS ticks nao encontrado: {OOS_TICKS_PATH}")
        return 1
    if not os.path.exists(OOS_CANDLES_PATH):
        print(f"[ERRO] OOS candles nao encontrado: {OOS_CANDLES_PATH}")
        return 1

    df_oos_base = pl.read_parquet(OOS_CANDLES_PATH)
    ticks_oos = pl.read_parquet(OOS_TICKS_PATH)
    ticks_oos = ticks_oos.with_columns([
        pl.col('bid').cast(pl.Float64),
        pl.col('ask').cast(pl.Float64),
        pl.col('last').cast(pl.Float64),
    ])
    ticks_oos = ticks_oos.filter(
        (pl.col('bid') > 0) & (pl.col('ask') > 0) & (pl.col('bid') < pl.col('ask'))
    )
    print(f"      OOS base: {len(df_oos_base)} candles, {len(ticks_oos)} ticks  ({time.time()-t0:.1f}s)")

    all_results = []

    for sig_idx, sig_path in enumerate(SIGNAL_FILES, 1):
        signal_name = os.path.basename(sig_path).replace('.parquet', '')
        print(f"\n{'='*80}")
        print(f"ARQUIVO {sig_idx}/{len(SIGNAL_FILES)}: {signal_name}")
        print(f"{'='*80}")

        # Carrega parquet completo (IS + OOS)
        t_load = time.time()
        df_full = pl.read_parquet(sig_path).to_pandas()
        df_full['dt'] = pd.to_datetime(df_full['dt'])
        df_is = df_full[(df_full['dt'] >= IS_S) & (df_full['dt'] <= IS_E)].reset_index(drop=True)
        print(f"  Parquet: {len(df_full)} rows total, {len(df_is)} IS (Fev)")

        # Descobre variantes
        variant_cols = get_variant_columns(pl.read_parquet(sig_path))
        if not variant_cols:
            print(f"  [AVISO] Nenhuma variante encontrada em {signal_name}")
            continue

        if args.limit > 0:
            variant_cols = variant_cols[:args.limit]

        print(f"  Variantes: {len(variant_cols)}")

        for v_idx, variant_col in enumerate(variant_cols, 1):
            t_variant = time.time()
            result = process_variant(
                df_is, df_oos_base, ticks_oos,
                sig_path, variant_col, DIRECTION, args.batch_size,
                use_grid_advisor
            )
            result['elapsed_total'] = time.time() - t_variant
            all_results.append(result)

            if result['status'] == 'completed':
                best_f3 = result['phases']['f3']['best']
                print(f"  [{v_idx}/{len(variant_cols)}] {variant_col}: F3={best_f3.get('net_pnl', 0):+d} ({best_f3.get('n_trades', 0)}t, WR={best_f3.get('win_rate', 0):.1f}%)  ({result['elapsed_total']:.1f}s)")
                save_variant_outputs(result)
            else:
                print(f"  [{v_idx}/{len(variant_cols)}] {variant_col}: ABORT ({result.get('reason')})  ({result['elapsed_total']:.1f}s)")

        del df_full, df_is

    # -----------------------------------------------------------------------
    # RESUMO
    # -----------------------------------------------------------------------
    completed = [r for r in all_results if r['status'] == 'completed']
    print(f"\n{'='*80}")
    print("RESUMO FINAL")
    print(f"{'='*80}")
    print(f"Variantes processadas: {len(all_results)}")
    print(f"Completadas: {len(completed)}")

    if not completed:
        print("[AVISO] Nenhuma variante completada com sucesso.")
        return 0

    completed.sort(key=lambda x: x['phases']['f3']['best'].get('net_pnl', 0), reverse=True)

    print(f"\nTOP 10 F3 OOS:")
    for i, r in enumerate(completed[:10], 1):
        b = r['phases']['f3']['best']
        print(f"  #{i:<3} {r['signal_name']}/{r['variant']:<35} OOS={b.get('net_pnl', 0):>+7} ({b.get('n_trades', 0)}t, WR={b.get('win_rate', 0):.1f}%, PF={b.get('profit_factor', 0):.2f})")

    pos = sum(1 for r in completed if r['phases']['f3']['best'].get('net_pnl', 0) > 0)
    print(f"\nPositivos OOS: {pos}/{len(completed)} ({pos/len(completed)*100:.1f}%)")

    # -----------------------------------------------------------------------
    # SALVAR RANKING CONSOLIDADO
    # -----------------------------------------------------------------------
    ranking_df = build_consolidated_ranking(all_results)
    ranking_path = os.path.join(OUT_DIR, 'ranking_consolidado_pasignal_sell.csv')
    ranking_df.to_csv(ranking_path, index=False)
    print(f"\n[SAVE] Ranking consolidado: {ranking_path}")

    # -----------------------------------------------------------------------
    # DNA + BLOCKING (TOP 10)
    # -----------------------------------------------------------------------
    top10 = completed[:10]
    dna_df = build_dna_top10(top10)
    dna_path = os.path.join(OUT_DIR, 'dna_top10_pasignal_sell.csv')
    dna_df.to_csv(dna_path, index=False)
    print(f"[SAVE] DNA top 10: {dna_path}")

    block_df = build_blocking_suggestion(top10)
    block_path = os.path.join(OUT_DIR, 'blocking_suggestion_pasignal_sell.csv')
    block_df.to_csv(block_path, index=False)
    print(f"[SAVE] Blocking suggestion: {block_path}")

    # JSON completo para referência
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_path = os.path.join(OUT_DIR, f'run_pasignal_v9_{ts}.json')
    with open(json_path, 'w', encoding='utf-8') as f:
        # Remove trades do JSON (muito grande)
        serializable = []
        for r in all_results:
            rc = dict(r)
            if 'phases' in rc and 'f3' in rc['phases']:
                rc['phases'] = dict(rc['phases'])
                rc['phases']['f3'] = dict(rc['phases']['f3'])
                rc['phases']['f3']['trades'] = f"<{len(rc['phases']['f3'].get('trades', []))} trades>"
            serializable.append(rc)
        json.dump(serializable, f, indent=2, default=str)
    print(f"[SAVE] JSON resumo: {json_path}")

    print(f"\n{'='*80}")
    print("EXECUÇÃO COMPLETA.")
    print(f"{'='*80}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
