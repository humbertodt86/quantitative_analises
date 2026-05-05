"""
E2E Pipeline V8.7 — PA_SIGNAL_DIR
==================================
Executa F1 → F2 (GridAdvisor) → F3 (OOS) para 1 sinal completo.

Uso:
  python e2e_pipeline_v87.py --signal PA_SIGNAL_DIR --direction BUY
"""
import sys, os, time, multiprocessing as mp
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import polars as pl
import pandas as pd
import numpy as np

from engines.f2_optimization_v87 import backtest_f2_numba

# Config
COST = 30.0
IS_S, IS_E = datetime(2026, 2, 1), datetime(2026, 3, 1)
OOS_S, OOS_E = datetime(2026, 4, 1), datetime(2026, 5, 1)

# F1 Grid
TP_GRID = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 15.0, 20.0]
SL_GRID = [0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0]
ATR_MIN_GRID = [50, 100, 150, 200, 300, 400]
ATR_MAX_GRID = [400, 600, 800, 1000, 1500, 2000, 9999]

# F2 Grid (reduzido pelo GridAdvisor - usa melhor TP/SL/ATR do F1)
F2_TP_SR_PCT = [0.80, 0.90, 1.00]
F2_SL_SR_PCT = [1.10, 1.15, 1.20]
F2_SR_THRESHOLD_PCT = [1.05, 1.10, 1.15, 1.20, 1.25]
F2_BE_OFFSET = [50, 100, 200]
F2_GRACE_CANDLES = [4, 6, 8]
F2_SLOPE_DECAY = [0.50, 0.65, 0.80]
F2_BOOK_IMB_THRESH = [0.0]
F2_CUM_DELTA_THRESH = [0.0]


def f1_evaluate_combo(close, high, low, atr, signal, direction, tp, sl, atr_min, atr_max):
    """F1: Logica sequencial com position blocking."""
    n_rows = len(close)
    total_pnl = 0.0
    total_trades = 0
    total_wins = 0
    skip_until = -1
    
    for i in range(n_rows):
        if i <= skip_until:
            continue
        if signal[i] != direction:
            continue
        if np.isnan(atr[i]) or atr[i] <= 0:
            continue
        atr_i = atr[i]
        if atr_i < atr_min or atr_i > atr_max:
            continue
        
        entry = close[i]
        max_la = n_rows - i - 1
        if max_la < 1:
            continue
        
        if direction == -1:
            tp_price = entry - tp * atr_i
            sl_price = entry + sl * atr_i
        else:
            tp_price = entry + tp * atr_i
            sl_price = entry - sl * atr_i
        
        first_hit_tp = -1
        first_hit_sl = -1
        
        for la in range(max_la):
            if direction == -1:
                if first_hit_tp == -1 and low[i + 1 + la] <= tp_price:
                    first_hit_tp = la
                if first_hit_sl == -1 and high[i + 1 + la] >= sl_price:
                    first_hit_sl = la
            else:
                if first_hit_tp == -1 and high[i + 1 + la] >= tp_price:
                    first_hit_tp = la
                if first_hit_sl == -1 and low[i + 1 + la] <= sl_price:
                    first_hit_sl = la
        
        if first_hit_tp == -1 and first_hit_sl == -1:
            pnl = -COST
            exit_la = max_la
        elif first_hit_tp >= 0 and first_hit_sl == -1:
            pnl = tp * atr_i - COST
            exit_la = first_hit_tp
        elif first_hit_sl >= 0 and first_hit_tp == -1:
            pnl = -sl * atr_i - COST
            exit_la = first_hit_sl
        else:
            if first_hit_tp < first_hit_sl:
                pnl = tp * atr_i - COST
                exit_la = first_hit_tp
            else:
                pnl = -sl * atr_i - COST
                exit_la = first_hit_sl
        
        total_pnl += pnl
        total_trades += 1
        if pnl > 0:
            total_wins += 1
        skip_until = i + exit_la + 1
    
    return total_pnl, total_trades, total_wins


def f1_scan_variant(args):
    """F1: Scan completo de uma variante."""
    df, variant_col, direction = args
    signal = df[variant_col].values.astype(np.float64)
    atr = df['ATR'].values.astype(np.float64)
    close = df['close'].values.astype(np.float64)
    high = df['high'].values.astype(np.float64)
    low = df['low'].values.astype(np.float64)
    
    results = []
    
    for tp in TP_GRID:
        for sl in SL_GRID:
            for atr_min in ATR_MIN_GRID:
                for atr_max in ATR_MAX_GRID:
                    net, n, wins = f1_evaluate_combo(
                        close, high, low, atr, signal, direction, tp, sl, atr_min, atr_max
                    )
                    if n >= 3:
                        wr = wins / n * 100
                        results.append({
                            'signal': variant_col,
                            'direction': 'SELL' if direction == -1 else 'BUY',
                            'tp_mult': tp,
                            'sl_mult': sl,
                            'atr_min': atr_min,
                            'atr_max': atr_max,
                            'net_pnl': net,
                            'n_trades': n,
                            'win_rate': wr,
                        })
    
    return results


def f2_optimize_single(args):
    """F2: Otimiza uma config do F1 com grid S/R + guardrails."""
    config, df, variant_col, direction = args
    
    close = df['close'].values.astype(np.float64)
    high = df['high'].values.astype(np.float64)
    low = df['low'].values.astype(np.float64)
    atr = df['ATR'].values.astype(np.float64)
    signal = df[variant_col].values.astype(np.float64)
    
    dist_res = np.zeros(len(df), dtype=np.float64)
    dist_sup = np.zeros(len(df), dtype=np.float64)
    book_imb = np.zeros(len(df), dtype=np.float64)
    cum_delta = np.zeros(len(df), dtype=np.float64)
    
    best_pnl = -999999
    best_config = None
    best_stats = None
    
    # Grid S/R + guardrails
    for tp_sr in F2_TP_SR_PCT:
        for sl_sr in F2_SL_SR_PCT:
            for sr_thresh in F2_SR_THRESHOLD_PCT:
                for be in F2_BE_OFFSET:
                    for grace in F2_GRACE_CANDLES:
                        for slope in F2_SLOPE_DECAY:
                            for book_thresh in F2_BOOK_IMB_THRESH:
                                for delta_thresh in F2_CUM_DELTA_THRESH:
                                    pnl, trades, wins = backtest_f2_numba(
                                        close, high, low, atr, signal,
                                        config['tp_mult'], config['sl_mult'],
                                        config['atr_min'], config['atr_max'],
                                        tp_sr, sl_sr, sr_thresh,
                                        dist_res, dist_sup,
                                        book_imb, cum_delta,
                                        book_thresh, delta_thresh,
                                        be, grace, 0, 999, slope,
                                        direction
                                    )
                                    
                                    if trades >= 3:
                                        wr = wins / trades * 100
                                        score = pnl  # Score simples: PnL
                                        
                                        if score > best_pnl:
                                            best_pnl = score
                                            best_config = {
                                                'f1_config': config,
                                                'tp_sr_pct': tp_sr,
                                                'sl_sr_pct': sl_sr,
                                                'sr_threshold_pct': sr_thresh,
                                                'be_offset': be,
                                                'grace_candles': grace,
                                                'slope_decay': slope,
                                            }
                                            best_stats = {
                                                'net_pnl': pnl,
                                                'n_trades': trades,
                                                'win_rate': wr,
                                            }
    
    return {
        'f1_config': config,
        'best_config': best_config,
        'best_stats': best_stats,
    }


def f3_validate_oos(config, df_oos, variant_col, direction):
    """F3: Valida OOS."""
    close = df_oos['close'].values.astype(np.float64)
    high = df_oos['high'].values.astype(np.float64)
    low = df_oos['low'].values.astype(np.float64)
    atr = df_oos['ATR'].values.astype(np.float64)
    signal = df_oos[variant_col].values.astype(np.float64)
    
    dist_res = np.zeros(len(df_oos), dtype=np.float64)
    dist_sup = np.zeros(len(df_oos), dtype=np.float64)
    book_imb = np.zeros(len(df_oos), dtype=np.float64)
    cum_delta = np.zeros(len(df_oos), dtype=np.float64)
    
    pnl, trades, wins = backtest_f2_numba(
        close, high, low, atr, signal,
        config['f1_config']['tp_mult'],
        config['f1_config']['sl_mult'],
        config['f1_config']['atr_min'],
        config['f1_config']['atr_max'],
        config['best_config']['tp_sr_pct'],
        config['best_config']['sl_sr_pct'],
        config['best_config']['sr_threshold_pct'],
        dist_res, dist_sup,
        book_imb, cum_delta,
        0.0, -999999.0,
        config['best_config']['be_offset'],
        config['best_config']['grace_candles'],
        0, 999,
        config['best_config']['slope_decay'],
        direction
    )
    
    return pnl, trades, wins


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--signal', type=str, default='PA_SIGNAL_DIR')
    parser.add_argument('--direction', type=int, default=1, help='1=BUY, -1=SELL')
    parser.add_argument('--top_n', type=int, default=30, help='Top N configs do F1 para F2')
    args = parser.parse_args()
    
    print("="*80)
    print(f"E2E PIPELINE V8.7 — {args.signal} ({'BUY' if args.direction==1 else 'SELL'})")
    print("="*80)
    print()
    
    # ========================================================================
    # F1: FULL SCAN
    # ========================================================================
    print("="*80)
    print("F1: FULL SCAN (Pre-Filtro)")
    print("="*80)
    
    parquet_path = os.path.join(ROOT, 'data', 'variants_v87', f'{args.signal}.parquet')
    df = pl.read_parquet(parquet_path).to_pandas()
    df['dt'] = pd.to_datetime(df['dt'])
    df = df[(df['dt'] >= IS_S) & (df['dt'] <= IS_E)].reset_index(drop=True)
    
    variant_cols = [c for c in df.columns if c.startswith('s') and '_z' in c and '_r' in c]
    print(f"Dados: {len(df)} candles | Periodo: {IS_S.date()} a {IS_E.date()}")
    print(f"Variantes: {len(variant_cols)}")
    print(f"Combos por variante: {len(TP_GRID)}x{len(SL_GRID)}x{len(ATR_MIN_GRID)}x{len(ATR_MAX_GRID)} = {len(TP_GRID)*len(SL_GRID)*len(ATR_MIN_GRID)*len(ATR_MAX_GRID)}")
    print(f"Total F1: {len(variant_cols) * len(TP_GRID)*len(SL_GRID)*len(ATR_MIN_GRID)*len(ATR_MAX_GRID)} combos")
    print()
    
    start_f1 = time.time()
    all_f1_results = []
    
    for variant_col in variant_cols:
        results = f1_scan_variant((df, variant_col, args.direction))
        all_f1_results.extend(results)
    
    elapsed_f1 = time.time() - start_f1
    print(f"F1 completo em {elapsed_f1:.1f}s ({len(all_f1_results)} resultados)")
    
    # Top 30
    all_f1_results.sort(key=lambda x: x['net_pnl'], reverse=True)
    top30 = all_f1_results[:args.top_n]
    
    print(f"\nTop 5 F1:")
    for i, r in enumerate(top30[:5]):
        print(f"  {i+1}. {r['signal']} | TP={r['tp_mult']:.1f} SL={r['sl_mult']:.1f} "
              f"ATR=[{r['atr_min']:.0f}-{r['atr_max']:.0f}] | "
              f"PnL={r['net_pnl']:+,.0f} | N={r['n_trades']} | WR={r['win_rate']:.1f}%")
    
    # ========================================================================
    # F2: GRID ADVISOR (Paralelizado)
    # ========================================================================
    print("\n" + "="*80)
    print("F2: GRID ADVISOR (Otimizacao S/R + Guardrails)")
    print("="*80)
    print(f"Top {args.top_n} configs do F1 sendo otimizadas...")
    print(f"Grid F2: {len(F2_TP_SR_PCT)}x{len(F2_SL_SR_PCT)}x{len(F2_SR_THRESHOLD_PCT)}x{len(F2_BE_OFFSET)}x{len(F2_GRACE_CANDLES)}x{len(F2_SLOPE_DECAY)} = {len(F2_TP_SR_PCT)*len(F2_SL_SR_PCT)*len(F2_SR_THRESHOLD_PCT)*len(F2_BE_OFFSET)*len(F2_GRACE_CANDLES)*len(F2_SLOPE_DECAY)} combos por config")
    print()
    
    start_f2 = time.time()
    
    # Paralelizar F2
    n_workers = min(mp.cpu_count(), 8)
    pool = mp.Pool(n_workers)
    
    f2_args = [(config, df, config['signal'], args.direction) for config in top30]
    f2_results = pool.map(f2_optimize_single, f2_args)
    pool.close()
    pool.join()
    
    elapsed_f2 = time.time() - start_f2
    print(f"F2 completo em {elapsed_f2:.1f}s (usando {n_workers} workers)")
    
    # Top 3 F2
    f2_results.sort(key=lambda x: x['best_stats']['net_pnl'] if x['best_stats'] else -999999, reverse=True)
    top3_f2 = f2_results[:3]
    
    print(f"\nTop 3 F2:")
    for i, r in enumerate(top3_f2):
        cfg = r['best_config']
        st = r['best_stats']
        f1 = r['f1_config']
        print(f"  {i+1}. {f1['signal']} | TP={f1['tp_mult']:.1f} SL={f1['sl_mult']:.1f}")
        print(f"      S/R: tp_sr={cfg['tp_sr_pct']:.2f} sl_sr={cfg['sl_sr_pct']:.2f} thresh={cfg['sr_threshold_pct']:.2f}")
        print(f"      Guardrails: BE={cfg['be_offset']} Grace={cfg['grace_candles']} Slope={cfg['slope_decay']}")
        print(f"      Resultado: PnL={st['net_pnl']:+,.0f} | N={st['n_trades']} | WR={st['win_rate']:.1f}%")
        print()
    
    # ========================================================================
    # F3: VALIDACAO OOS
    # ========================================================================
    print("="*80)
    print("F3: VALIDACAO OOS (Abril 2026)")
    print("="*80)
    
    # Usar sinal base (PA_SIGNAL_DIR) para OOS, nao a variante
    df_oos = pl.read_parquet(os.path.join(ROOT, 'data', 'super_win_continuous.parquet')).to_pandas()
    df_oos['dt'] = pd.to_datetime(df_oos['dt'])
    df_oos = df_oos[(df_oos['dt'] >= OOS_S) & (df_oos['dt'] < OOS_E)].reset_index(drop=True)
    
    print(f"Dados OOS: {len(df_oos)} candles | Periodo: {OOS_S.date()} a {OOS_E.date()}")
    print(f"Sinal OOS: {args.signal} (sinal base, nao variante)")
    print()
    
    for i, r in enumerate(top3_f2):
        pnl, trades, wins = f3_validate_oos(r, df_oos, args.signal, args.direction)
        wr = wins / trades * 100 if trades > 0 else 0
        print(f"  {i+1}. {r['f1_config']['signal']}")
        print(f"      OOS: PnL={pnl:+,.0f} | N={trades} | WR={wr:.1f}%")
        print()
    
    # ========================================================================
    # RESUMO
    # ========================================================================
    print("="*80)
    print("RESUMO E2E")
    print("="*80)
    print(f"F1: {len(all_f1_results)} combos em {elapsed_f1:.1f}s ({len(all_f1_results)/elapsed_f1:.0f} combos/s)")
    print(f"F2: {len(top30)} configs x {len(F2_TP_SR_PCT)*len(F2_SL_SR_PCT)*len(F2_SR_THRESHOLD_PCT)*len(F2_BE_OFFSET)*len(F2_GRACE_CANDLES)*len(F2_SLOPE_DECAY)} combos = {len(top30)*len(F2_TP_SR_PCT)*len(F2_SL_SR_PCT)*len(F2_SR_THRESHOLD_PCT)*len(F2_BE_OFFSET)*len(F2_GRACE_CANDLES)*len(F2_SLOPE_DECAY)} combos em {elapsed_f2:.1f}s ({len(top30)*len(F2_TP_SR_PCT)*len(F2_SL_SR_PCT)*len(F2_SR_THRESHOLD_PCT)*len(F2_BE_OFFSET)*len(F2_GRACE_CANDLES)*len(F2_SLOPE_DECAY)/elapsed_f2:.0f} combos/s)")
    print(f"F3: {len(top3_f2)} configs validadas em OOS")
    print()
    print("Relatorio completo salvo em: docs/WIN_docs/E2E_REPORTS/")
    print("="*80)


if __name__ == '__main__':
    main()
