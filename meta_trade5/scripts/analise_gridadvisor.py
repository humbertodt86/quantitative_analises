"""
ANALISE PROFUNDA — GridAdvisor ON vs OFF
=========================================
Responde:
1. Por que OFF foi mais rapido com 500x combos?
2. Vitória do ON no OOS: coincidencia ou padrao?
3. Quais variaveis foram otimizadas no F2?
4. Top 5 configs F2 → F3 OOS para ambos os modos
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

def analyze_variant(sig_path: str, variant_col: str, direction: int):
    print(f"\n{'='*80}")
    print("ANALISE PROFUNDA: GridAdvisor ON vs OFF")
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
    print(f"\nF1: {len(top30_f1)} configs | Top 1: PnL={top30_f1[0]['net_pnl']:,} TP={top30_f1[0]['tp_mult']:.1f} SL={top30_f1[0]['sl_mult']:.1f}")
    
    results = {}
    
    for mode_name, use_ga in [("ON", True), ("OFF", False)]:
        print(f"\n{'='*80}")
        print(f"MODO: GridAdvisor {mode_name}")
        print(f"{'='*80}")
        
        # --- F2 isolado (3 rodadas para media) ---
        f2_times = []
        for _ in range(3):
            t0 = time.time()
            df_f2, _ = run_f2_gpu(df_is, variant_col, direction, top30_f1, batch_size=500000, use_grid_advisor=use_ga)
            f2_times.append(time.time() - t0)
        f2_time_avg = np.mean(f2_times)
        f2_time_std = np.std(f2_times)
        
        print(f"\n[1] TEMPO F2 GPU (media de 3 rodadas): {f2_time_avg:.3f}s (+/- {f2_time_std:.3f}s)")
        print(f"    Combos avaliados: {len(df_f2):,}")
        
        # --- Top 5 configs F2 ---
        top5 = df_f2.head(5)
        print(f"\n[2] TOP 5 CONFIGS F2:")
        print(f"{'Rank':>6} {'TP':>6} {'SL':>6} {'ATR_MIN':>8} {'ATR_MAX':>8} {'TP_SR':>7} {'SL_SR':>7} {'BE':>6} {'GRACE':>7} {'SLOPE':>7} {'PnL':>10} {'Trades':>8} {'WR%':>6}")
        for i, (_, row) in enumerate(top5.iterrows(), 1):
            print(f"{i:>6} {row['tp_mult']:>6.1f} {row['sl_mult']:>6.1f} {row['atr_min']:>8.0f} {row['atr_max']:>8.0f} {row.get('tp_sr_pct',0):>7.2f} {row.get('sl_sr_pct',0):>7.2f} {row.get('be_offset',0):>6.0f} {row.get('grace_candles',0):>7.0f} {row.get('slope_decay',0):>7.2f} {row['net_pnl']:>10,.0f} {int(row['n_trades']):>8} {row['win_rate']:>6.1f}")
        
        # --- F3 OOS nas top 5 ---
        print(f"\n[3] F3 OOS VALIDATION (top 5 configs):")
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
                'rank': i,
                'f2_pnl': row['net_pnl'],
                'f2_trades': int(row['n_trades']),
                'f2_wr': row['win_rate'],
                'f3_pnl': f3.get('net_pnl', 0),
                'f3_trades': f3.get('n_trades', 0),
                'f3_wr': f3.get('win_rate', 0.0),
                'f3_pf': f3.get('profit_factor', 0.0),
            })
            status = "OK" if f3['status'] == 'ok' else "ERR"
            print(f"  #{i} F2→F3: {status}  F2_PnL={row['net_pnl']:>8,.0f} → F3_PnL={f3.get('net_pnl',0):>+8}  ({f3.get('n_trades',0)}t, WR={f3.get('win_rate',0):.1f}%, PF={f3.get('profit_factor',0):.2f})")
        
        results[mode_name] = {
            'f2_time_avg': f2_time_avg,
            'f2_time_std': f2_time_std,
            'n_combos': len(df_f2),
            'top5_f2': top5.to_dict('records'),
            'top5_f3': f3_results,
        }
    
    # --- Comparacao das top 5 ---
    print(f"\n{'='*80}")
    print("COMPARACAO: Top 5 F2 → F3 OOS")
    print(f"{'='*80}")
    
    on_f3 = results['ON']['top5_f3']
    off_f3 = results['OFF']['top5_f3']
    
    print(f"\n{'Rank':>6} {'ON_F2':>10} {'ON_F3':>10} {'OFF_F2':>10} {'OFF_F3':>10} {'Delta_F3':>10}")
    print(f"{'-'*6} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
    for i in range(5):
        on = on_f3[i]
        off = off_f3[i]
        delta = on['f3_pnl'] - off['f3_pnl']
        print(f"{i+1:>6} {on['f2_pnl']:>10,.0f} {on['f3_pnl']:>+10,d} {off['f2_pnl']:>10,.0f} {off['f3_pnl']:>+10,d} {delta:>+10,d}")
    
    # Estatisticas agregadas
    on_f3_pnls = [r['f3_pnl'] for r in on_f3]
    off_f3_pnls = [r['f3_pnl'] for r in off_f3]
    on_f3_wrs = [r['f3_wr'] for r in on_f3]
    off_f3_wrs = [r['f3_wr'] for r in off_f3]
    
    print(f"\n{'='*80}")
    print("ESTATISTICAS AGREGADAS (Top 5)")
    print(f"{'='*80}")
    print(f"{'Metrica':<30} {'GridAdvisor ON':>15} {'GridAdvisor OFF':>15} {'Delta':>12}")
    print(f"{'-'*30} {'-'*15} {'-'*15} {'-'*12}")
    print(f"{'F2 Time (s)':<30} {results['ON']['f2_time_avg']:>15.3f} {results['OFF']['f2_time_avg']:>15.3f} {results['ON']['f2_time_avg']-results['OFF']['f2_time_avg']:>+12.3f}")
    print(f"{'F2 Combos':<30} {results['ON']['n_combos']:>15,} {results['OFF']['n_combos']:>15,} {results['ON']['n_combos']-results['OFF']['n_combos']:>+12,}")
    print(f"{'F3 PnL Medio (top 5)':<30} {np.mean(on_f3_pnls):>15,.0f} {np.mean(off_f3_pnls):>15,.0f} {np.mean(on_f3_pnls)-np.mean(off_f3_pnls):>+12,.0f}")
    print(f"{'F3 PnL Max (top 5)':<30} {max(on_f3_pnls):>15,d} {max(off_f3_pnls):>15,d} {max(on_f3_pnls)-max(off_f3_pnls):>+12,d}")
    print(f"{'F3 WR Medio (top 5)':<30} {np.mean(on_f3_wrs):>15.1f} {np.mean(off_f3_wrs):>15.1f} {np.mean(on_f3_wrs)-np.mean(off_f3_wrs):>+12.1f}")
    print(f"{'F3 # Positivos (top 5)':<30} {sum(1 for x in on_f3_pnls if x>0):>15} {sum(1 for x in off_f3_pnls if x>0):>15}")
    
    # Correlacao F2 → F3
    on_f2_pnls = [r['f2_pnl'] for r in on_f3]
    off_f2_pnls = [r['f2_pnl'] for r in off_f3]
    
    if len(on_f2_pnls) > 2 and np.std(on_f2_pnls) > 0 and np.std(on_f3_pnls) > 0:
        corr_on = np.corrcoef(on_f2_pnls, on_f3_pnls)[0,1]
        print(f"{'F2→F3 Correlacao (ON)':<30} {corr_on:>15.3f}")
    if len(off_f2_pnls) > 2 and np.std(off_f2_pnls) > 0 and np.std(off_f3_pnls) > 0:
        corr_off = np.corrcoef(off_f2_pnls, off_f3_pnls)[0,1]
        print(f"{'F2→F3 Correlacao (OFF)':<30} {corr_off:>15.3f}")
    
    # Salva
    out = os.path.join(ROOT, 'docs', 'WIN_docs', f'analise_gridadvisor_{variant_col}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Analise salva: {out}")
    
    return results


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Analise profunda GridAdvisor')
    parser.add_argument('--signal-file', type=str, required=True)
    parser.add_argument('--variant', type=str, required=True)
    parser.add_argument('--direction', type=int, default=-1)
    args = parser.parse_args()
    
    analyze_variant(args.signal_file, args.variant, args.direction)
