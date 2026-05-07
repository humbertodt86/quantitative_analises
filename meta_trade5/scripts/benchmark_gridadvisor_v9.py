"""
BENCHMARK RAPIDO — GridAdvisor ON vs OFF (Grid Completo)
==========================================================
Versao rapida do benchmark, roda 1x por modo (sem media de 3).
"""
import sys, os, time, json
from datetime import datetime
import numpy as np
import pandas as pd
import polars as pl

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

if os.name == 'nt':
    try:
        import torch
        _torch_lib = os.path.join(os.path.dirname(torch.__file__), 'lib')
        if os.path.isdir(_torch_lib) and _torch_lib not in os.environ.get('PATH', ''):
            os.environ['PATH'] = _torch_lib + os.pathsep + os.environ.get('PATH', '')
    except Exception:
        pass

from scripts.run_all_gpu import (
    run_f1_screening, run_f2_gpu, run_f3_oos,
    IS_S, IS_E, OOS_CANDLES_PATH, OOS_TICKS_PATH
)

def benchmark_fast(sig_path: str, variant_col: str, direction: int):
    print(f"\n{'='*80}")
    print("BENCHMARK RAPIDO: GridAdvisor ON vs OFF (Grid Completo V9.0)")
    print(f"{'='*80}")
    print(f"Variante: {variant_col} | Direcao: {'BUY' if direction==1 else 'SELL'}")
    
    # Carrega dados
    df_full = pl.read_parquet(sig_path).to_pandas()
    df_full['dt'] = pd.to_datetime(df_full['dt'])
    df_is = df_full[(df_full['dt'] >= IS_S) & (df_full['dt'] <= IS_E)].reset_index(drop=True)
    
    df_oos_base = pl.read_parquet(OOS_CANDLES_PATH)
    ticks_oos = pl.read_parquet(OOS_TICKS_PATH)
    ticks_oos = ticks_oos.with_columns([
        pl.col('bid').cast(pl.Float64), pl.col('ask').cast(pl.Float64), pl.col('last').cast(pl.Float64),
    ]).filter((pl.col('bid') > 0) & (pl.col('ask') > 0) & (pl.col('bid') < pl.col('ask')))
    
    sig_df = pl.read_parquet(sig_path)
    if str(df_oos_base['dt'].dtype) != str(sig_df['dt'].dtype):
        sig_df = sig_df.with_columns(pl.col('dt').cast(df_oos_base['dt'].dtype))
    merge_cols = ['dt', variant_col, 'ATR', 'dist_to_resistance', 'dist_to_support',
                  'book_imbalance', 'cum_delta', 'EMA5']
    merge_cols = [c for c in merge_cols if c in sig_df.columns]
    df_oos_merged = df_oos_base.join(sig_df.select(merge_cols), on='dt', how='left')
    
    # F1
    top30_f1, t_f1 = run_f1_screening(df_is, variant_col, direction)
    print(f"\nF1: {len(top30_f1)} configs em {t_f1:.2f}s | Top 1: PnL={top30_f1[0]['net_pnl']:,} TP={top30_f1[0]['tp_mult']:.1f} SL={top30_f1[0]['sl_mult']:.1f}")
    
    results = {}
    
    for mode_name, use_ga in [("ON", True), ("OFF", False)]:
        print(f"\n{'='*80}")
        print(f"MODO: GridAdvisor {mode_name}")
        print(f"{'='*80}")
        
        t_start = time.time()
        
        # F2
        df_f2, t_f2 = run_f2_gpu(df_is, variant_col, direction, top30_f1, batch_size=500000, use_grid_advisor=use_ga)
        print(f"\n[1] F2 GPU: {len(df_f2):,} combos em {t_f2:.2f}s")
        
        if len(df_f2) == 0:
            print("  [SKIP] Sem resultados F2")
            continue
        
        top5 = df_f2.head(5)
        print(f"\n[2] TOP 5 F2:")
        print(f"{'Rank':>6} {'TP':>6} {'SL':>6} {'ATR_MIN':>8} {'ATR_MAX':>8} {'TP_SR':>7} {'SL_SR':>7} {'SR_THR':>7} {'BE':>6} {'GRACE':>7} {'SLOPE':>7} {'PnL':>10} {'Trades':>8} {'WR%':>6}")
        for i, (_, row) in enumerate(top5.iterrows(), 1):
            print(f"{i:>6} {row['tp_mult']:>6.1f} {row['sl_mult']:>6.1f} {row['atr_min']:>8.0f} {row['atr_max']:>8.0f} {row.get('tp_sr_pct',0):>7.2f} {row.get('sl_sr_pct',0):>7.2f} {row.get('sr_threshold_pct',0):>7.2f} {row.get('be_offset',0):>6.0f} {row.get('grace_candles',0):>7.0f} {row.get('slope_decay',0):>7.2f} {row['net_pnl']:>10,.0f} {int(row['n_trades']):>8} {row['win_rate']:>6.1f}")
        
        # F3 top 5
        print(f"\n[3] F3 OOS (top 5):")
        f3_results = []
        for i, (_, row) in enumerate(top5.iterrows(), 1):
            config_f2 = {
                'tp_mult': row['tp_mult'], 'sl_mult': row['sl_mult'],
                'atr_min': row['atr_min'], 'atr_max': row['atr_max'],
                'be_offset': row.get('be_offset', 999999),
                'grace_candles': int(row.get('grace_candles', 2)),
                'cooldown_candles': int(row.get('cooldown_candles', 0)),
                'slope_decay': float(row.get('slope_decay', 0.50)),
            }
            f3 = run_f3_oos(df_oos_merged, ticks_oos, variant_col, direction, config_f2)
            f3_results.append({
                'rank': i, 'f2_pnl': row['net_pnl'], 'f2_trades': int(row['n_trades']), 'f2_wr': row['win_rate'],
                'f3_pnl': f3.get('net_pnl', 0), 'f3_trades': f3.get('n_trades', 0),
                'f3_wr': f3.get('win_rate', 0.0), 'f3_pf': f3.get('profit_factor', 0.0),
            })
            status = "OK" if f3['status'] == 'ok' else "ERR"
            print(f"  #{i} {status}  F2={row['net_pnl']:>8,.0f} → F3={f3.get('net_pnl',0):>+8}  ({f3.get('n_trades',0)}t, WR={f3.get('win_rate',0):.1f}%, PF={f3.get('profit_factor',0):.2f})")
        
        t_total = time.time() - t_start
        print(f"\n  TEMPO TOTAL: {t_total:.2f}s")
        
        results[mode_name] = {
            'f2_time': t_f2, 'n_combos': len(df_f2), 'top5_f3': f3_results,
        }
    
    # Comparacao
    print(f"\n{'='*80}")
    print("COMPARACAO FINAL")
    print(f"{'='*80}")
    
    if 'ON' not in results or 'OFF' not in results:
        print("[ERRO] Um dos modos nao completou")
        return
    
    on = results['ON']
    off = results['OFF']
    
    on_f3 = on['top5_f3']
    off_f3 = off['top5_f3']
    
    print(f"\n{'Rank':>6} {'ON_F2':>10} {'ON_F3':>10} {'OFF_F2':>10} {'OFF_F3':>10} {'Delta_F3':>10}")
    print(f"{'-'*6} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
    for i in range(5):
        o = on_f3[i]
        f = off_f3[i]
        delta = o['f3_pnl'] - f['f3_pnl']
        print(f"{i+1:>6} {o['f2_pnl']:>10,.0f} {o['f3_pnl']:>+10,d} {f['f2_pnl']:>10,.0f} {f['f3_pnl']:>+10,d} {delta:>+10,d}")
    
    print(f"\n{'Metrica':<30} {'GridAdvisor ON':>15} {'GridAdvisor OFF':>15} {'Delta':>12}")
    print(f"{'-'*30} {'-'*15} {'-'*15} {'-'*12}")
    print(f"{'F2 Combos':<30} {on['n_combos']:>15,} {off['n_combos']:>15,} {on['n_combos']-off['n_combos']:>+12,}")
    print(f"{'F2 Time (s)':<30} {on['f2_time']:>15.2f} {off['f2_time']:>15.2f} {on['f2_time']-off['f2_time']:>+12.2f}")
    print(f"{'F3 PnL Medio (top 5)':<30} {np.mean([r['f3_pnl'] for r in on_f3]):>15,.0f} {np.mean([r['f3_pnl'] for r in off_f3]):>15,.0f} {np.mean([r['f3_pnl'] for r in on_f3])-np.mean([r['f3_pnl'] for r in off_f3]):>+12,.0f}")
    print(f"{'F3 PnL Max (top 5)':<30} {max([r['f3_pnl'] for r in on_f3]):>15,d} {max([r['f3_pnl'] for r in off_f3]):>15,d} {max([r['f3_pnl'] for r in on_f3])-max([r['f3_pnl'] for r in off_f3]):>+12,d}")
    print(f"{'F3 WR Medio (top 5)':<30} {np.mean([r['f3_wr'] for r in on_f3]):>15.1f} {np.mean([r['f3_wr'] for r in off_f3]):>15.1f} {np.mean([r['f3_wr'] for r in on_f3])-np.mean([r['f3_wr'] for r in off_f3]):>+12.1f}")
    
    out = os.path.join(ROOT, 'docs', 'WIN_docs', f'benchmark_gridadvisor_v9_{variant_col}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Resultados: {out}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--signal-file', type=str, required=True)
    parser.add_argument('--variant', type=str, required=True)
    parser.add_argument('--direction', type=int, default=-1)
    args = parser.parse_args()
    benchmark_fast(args.signal_file, args.variant, args.direction)
