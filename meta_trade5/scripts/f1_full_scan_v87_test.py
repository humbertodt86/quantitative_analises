"""
F1 FULL SCAN V8.7 — COM POSITION BLOCKING CORRETO
==================================================
Executa F1 full scan em APENAS 1 parquet para validacao.
USA: Logica sequencial com position blocking (igual F2).

Uso:
  python f1_full_scan_v87_test.py --signal PA_SIGNAL_DIR

Output:
  docs/WIN_docs/F1_V87_TEST_PA_SIGNAL_DIR.csv
"""
import sys, os, time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import polars as pl
import pandas as pd
import numpy as np

# Config
COST = 30.0
IS_S, IS_E = datetime(2026, 2, 1), datetime(2026, 3, 1)

# Grid
TP_GRID = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 15.0, 20.0]
SL_GRID = [0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0]
ATR_MIN_GRID = [50, 100, 150, 200, 300, 400]
ATR_MAX_GRID = [400, 600, 800, 1000, 1500, 2000, 9999]


def evaluate_combo_sequential(close, high, low, atr, signal, direction, tp, sl, atr_min, atr_max):
    """
    Avalia UMA combo com position blocking sequencial (igual F2).
    """
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


def evaluate_variant(df, signal_col, direction):
    """Avalia uma variante V8.7."""
    signal = df[signal_col].values.astype(np.float64)
    atr = df['ATR'].values.astype(np.float64)
    close = df['close'].values.astype(np.float64)
    high = df['high'].values.astype(np.float64)
    low = df['low'].values.astype(np.float64)
    
    results = []
    
    for tp in TP_GRID:
        for sl in SL_GRID:
            for atr_min in ATR_MIN_GRID:
                for atr_max in ATR_MAX_GRID:
                    net, n, wins = evaluate_combo_sequential(
                        close, high, low, atr, signal, direction, tp, sl, atr_min, atr_max
                    )
                    
                    if n >= 3:
                        wr = wins / n * 100
                        results.append({
                            'signal': signal_col,
                            'direction': 'SELL' if direction == -1 else 'BUY',
                            'tp_mult': tp,
                            'sl_mult': sl,
                            'atr_min': atr_min,
                            'atr_max': atr_max,
                            'net_pnl': net,
                            'n_trades': n,
                            'win_rate': wr,
                        })
    
    results.sort(key=lambda x: x['net_pnl'], reverse=True)
    return results[:10]


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--signal', type=str, default='PA_SIGNAL_DIR')
    parser.add_argument('--variants', nargs='*', default=None)
    args = parser.parse_args()
    
    print("="*80)
    print("F1 FULL SCAN V8.7 — COM POSITION BLOCKING (validado vs F2)")
    print("="*80)
    print(f"Signal: {args.signal}")
    print(f"Grid: {len(TP_GRID)} TP x {len(SL_GRID)} SL x {len(ATR_MIN_GRID)} ATR_MIN x {len(ATR_MAX_GRID)} ATR_MAX")
    print(f"Total combos: {len(TP_GRID) * len(SL_GRID) * len(ATR_MIN_GRID) * len(ATR_MAX_GRID)}")
    print()
    
    parquet_path = os.path.join(ROOT, 'data', 'variants_v87', f'{args.signal}.parquet')
    df = pl.read_parquet(parquet_path).to_pandas()
    df['dt'] = pd.to_datetime(df['dt'])
    df = df[(df['dt'] >= IS_S) & (df['dt'] <= IS_E)]
    print(f"Loaded: {len(df)} rows (Fevereiro 2026)")
    print()
    
    variant_cols = [c for c in df.columns if c.startswith('s') and '_z' in c and '_r' in c]
    print(f"Found {len(variant_cols)} variantes")
    print()
    
    all_results = []
    
    for variant_col in variant_cols[:3]:  # Limitar a 3 variantes para teste rapido
        print(f"Evaluating {variant_col}...")
        start = time.time()
        
        buy_top10 = evaluate_variant(df, variant_col, direction=+1)
        sell_top10 = evaluate_variant(df, variant_col, direction=-1)
        
        elapsed = time.time() - start
        if buy_top10:
            print(f"  BUY:  Top PnL = {buy_top10[0]['net_pnl']:+,.0f} ({buy_top10[0]['n_trades']} trades, {buy_top10[0]['win_rate']:.1f}% WR) — {elapsed:.1f}s")
        if sell_top10:
            print(f"  SELL: Top PnL = {sell_top10[0]['net_pnl']:+,.0f} ({sell_top10[0]['n_trades']} trades, {sell_top10[0]['win_rate']:.1f}% WR)")
        print()
        
        all_results.extend(buy_top10)
        all_results.extend(sell_top10)
    
    # Salvar
    results_df = pd.DataFrame(all_results)
    output_path = os.path.join(ROOT, 'docs', 'WIN_docs', f'F1_V87_TEST_{args.signal}.csv')
    results_df.to_csv(output_path, index=False)
    print(f"Saved: {output_path} ({len(results_df)} rows)")
    
    # Top 10
    print("\n" + "="*80)
    print("TOP 10 GERAL:")
    print("="*80)
    results_df.sort_values('net_pnl', ascending=False, inplace=True)
    for i, row in results_df.head(10).iterrows():
        print(f"{i+1:2}. {row['signal']:20} {row['direction']:4} | "
              f"TP={row['tp_mult']:.1f} SL={row['sl_mult']:.1f} | "
              f"ATR=[{row['atr_min']:.0f}-{row['atr_max']:.0f}] | "
              f"PnL={row['net_pnl']:+10.0f} | N={row['n_trades']:3} | WR={row['win_rate']:.1f}%")


if __name__ == '__main__':
    main()
