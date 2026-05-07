"""
COMPARE GRID ADVISOR — Benchmark F2 com/sen GridAdvisor
========================================================
Roda a mesma variante duas vezes:
  1. GridAdvisor ATIVO (default)
  2. GridAdvisor DESATIVADO (refina sempre ±20%)

Compara tempo de execucao e qualidade dos resultados (PnL, WR, PF, trades).

Uso:
    python scripts/compare_grid_advisor.py --signal-file data/variants_v87/PA_SIGNAL_DIR.parquet --variant s10_z1p5_r0p5 --direction -1
"""
import sys, os, time, json
from datetime import datetime
import numpy as np
import pandas as pd
import polars as pl

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# CUDA PATH FIX
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
    IS_S, IS_E, COST, OOS_CANDLES_PATH, OOS_TICKS_PATH
)

def compare_grid_advisor(sig_path: str, variant_col: str, direction: int):
    print(f"\n{'='*80}")
    print("BENCHMARK: GridAdvisor ON vs OFF")
    print(f"{'='*80}")
    print(f"Sinal: {os.path.basename(sig_path)}")
    print(f"Variante: {variant_col}")
    print(f"Direcao: {'BUY' if direction==1 else 'SELL'}")
    
    # Carrega dados 1x
    print("\n[0/3] Carregando dados...")
    df_full = pl.read_parquet(sig_path).to_pandas()
    df_full['dt'] = pd.to_datetime(df_full['dt'])
    df_is = df_full[(df_full['dt'] >= IS_S) & (df_full['dt'] <= IS_E)].reset_index(drop=True)
    
    df_oos_base = pl.read_parquet(OOS_CANDLES_PATH)
    ticks_oos = pl.read_parquet(OOS_TICKS_PATH)
    ticks_oos = ticks_oos.with_columns([
        pl.col('bid').cast(pl.Float64), pl.col('ask').cast(pl.Float64), pl.col('last').cast(pl.Float64),
    ]).filter((pl.col('bid') > 0) & (pl.col('ask') > 0) & (pl.col('bid') < pl.col('ask')))
    
    # Merge OOS
    sig_df = pl.read_parquet(sig_path)
    if str(df_oos_base['dt'].dtype) != str(sig_df['dt'].dtype):
        sig_df = sig_df.with_columns(pl.col('dt').cast(df_oos_base['dt'].dtype))
    merge_cols = ['dt', variant_col, 'ATR', 'dist_to_resistance', 'dist_to_support',
                  'book_imbalance', 'cum_delta', 'EMA5']
    merge_cols = [c for c in merge_cols if c in sig_df.columns]
    df_oos_merged = df_oos_base.join(sig_df.select(merge_cols), on='dt', how='left')
    
    print(f"  IS: {len(df_is)} candles | OOS: {len(df_oos_merged)} candles")
    
    # F1 (1x)
    print("\n[1/3] F1 Screening (CPU)...")
    top30_f1, t_f1 = run_f1_screening(df_is, variant_col, direction)
    print(f"      F1: {len(top30_f1)} configs em {t_f1:.2f}s")
    if not top30_f1:
        print("[ERRO] F1 sem resultados")
        return
    best_f1 = top30_f1[0]
    print(f"      Top 1 F1: PnL={best_f1['net_pnl']:,}  Trades={best_f1['n_trades']}  TP={best_f1['tp_mult']:.1f} SL={best_f1['sl_mult']:.1f}")
    
    results = {}
    
    for mode_name, use_ga in [("ON", True), ("OFF", False)]:
        print(f"\n{'='*80}")
        print(f"MODO: GridAdvisor {mode_name}")
        print(f"{'='*80}")
        
        t_start = time.time()
        
        # F2
        print("\n[2/3] F2 Optimization (GPU)...")
        df_f2, t_f2 = run_f2_gpu(df_is, variant_col, direction, top30_f1, batch_size=500000, use_grid_advisor=use_ga)
        print(f"      F2: {len(df_f2)} validos em {t_f2:.2f}s")
        if len(df_f2) == 0:
            print(f"      [SKIP] Sem resultados F2")
            continue
        
        best_f2 = df_f2.iloc[0]
        print(f"      Top 1 F2: PnL={best_f2['net_pnl']:,.0f}  Trades={int(best_f2['n_trades'])}  WR={best_f2['win_rate']:.1f}%")
        
        # F3
        print("\n[3/3] F3 OOS Validation (CPU)...")
        config_f2 = {
            'tp_mult': best_f2['tp_mult'], 'sl_mult': best_f2['sl_mult'],
            'atr_min': best_f2['atr_min'], 'atr_max': best_f2['atr_max'],
            'be_offset': best_f2.get('be_offset', 999999),
            'grace_candles': int(best_f2.get('grace_candles', 2)),
            'cooldown_candles': int(best_f2.get('cooldown_candles', 0)),
            'slope_decay': float(best_f2.get('slope_decay', 0.50)),
        }
        f3 = run_f3_oos(df_oos_merged, ticks_oos, variant_col, direction, config_f2)
        t_total = time.time() - t_start
        
        status = "OK" if f3['status'] == 'ok' else "ERR"
        print(f"      F3: {status}  PnL={f3.get('net_pnl',0):>+7}  ({f3.get('n_trades',0)}t, WR={f3.get('win_rate',0):.1f}%, PF={f3.get('profit_factor',0):.2f})")
        print(f"\n  TEMPO TOTAL: {t_total:.2f}s")
        
        results[mode_name] = {
            'f2_n_valid': len(df_f2),
            'f2_top_pnl': best_f2['net_pnl'],
            'f2_top_trades': int(best_f2['n_trades']),
            'f2_top_wr': best_f2['win_rate'],
            'f3_pnl': f3.get('net_pnl', 0),
            'f3_trades': f3.get('n_trades', 0),
            'f3_wr': f3.get('win_rate', 0.0),
            'f3_pf': f3.get('profit_factor', 0.0),
            'elapsed': t_total,
            'config': {
                'tp': best_f2['tp_mult'], 'sl': best_f2['sl_mult'],
                'atr_min': best_f2['atr_min'], 'atr_max': best_f2['atr_max'],
                'be': best_f2.get('be_offset', 999999),
                'grace': int(best_f2.get('grace_candles', 2)),
                'slope': float(best_f2.get('slope_decay', 0.50)),
            }
        }
    
    # Comparacao
    print(f"\n{'='*80}")
    print("COMPARACAO FINAL")
    print(f"{'='*80}")
    
    if 'ON' not in results or 'OFF' not in results:
        print("[ERRO] Um dos modos nao completou. Abortando comparacao.")
        return
    
    on = results['ON']
    off = results['OFF']
    
    print(f"\n{'Metrica':<25} {'GridAdvisor ON':>18} {'GridAdvisor OFF':>18} {'Delta':>12}")
    print(f"{'-'*25} {'-'*18} {'-'*18} {'-'*12}")
    
    def _row(label, on_val, off_val, fmt=".0f"):
        delta = off_val - on_val
        pct = (delta / abs(on_val) * 100) if on_val != 0 else 0
        print(f"{label:<25} {on_val:>18,{fmt}} {off_val:>18,{fmt}} {delta:>+11,.0f} ({pct:+.1f}%)")
    
    print(f"{'Tempo Total (s)':<25} {on['elapsed']:>18.2f} {off['elapsed']:>18.2f} {off['elapsed']-on['elapsed']:>+11.2f}s")
    print(f"{'F2 Validos':<25} {on['f2_n_valid']:>18,} {off['f2_n_valid']:>18,} {off['f2_n_valid']-on['f2_n_valid']:>+11,}")
    print(f"{'F2 Top PnL':<25} {on['f2_top_pnl']:>18,.0f} {off['f2_top_pnl']:>18,.0f} {off['f2_top_pnl']-on['f2_top_pnl']:>+11,.0f}")
    print(f"{'F2 Top Trades':<25} {on['f2_top_trades']:>18,} {off['f2_top_trades']:>18,} {off['f2_top_trades']-on['f2_top_trades']:>+11,}")
    print(f"{'F2 Top WR%':<25} {on['f2_top_wr']:>18.1f} {off['f2_top_wr']:>18.1f} {off['f2_top_wr']-on['f2_top_wr']:>+11.1f}")
    print(f"{'F3 OOS PnL':<25} {on['f3_pnl']:>+18,d} {off['f3_pnl']:>+18,d} {off['f3_pnl']-on['f3_pnl']:>+11,d}")
    print(f"{'F3 OOS Trades':<25} {on['f3_trades']:>18,} {off['f3_trades']:>18,} {off['f3_trades']-on['f3_trades']:>+11,}")
    print(f"{'F3 OOS WR%':<25} {on['f3_wr']:>18.1f} {off['f3_wr']:>18.1f} {off['f3_wr']-on['f3_wr']:>+11.1f}")
    print(f"{'F3 OOS PF':<25} {on['f3_pf']:>18.2f} {off['f3_pf']:>18.2f} {off['f3_pf']-on['f3_pf']:>+11.2f}")
    
    # Configuracoes
    print(f"\n{'='*80}")
    print("CONFIGURACOES")
    print(f"{'='*80}")
    for mode in ['ON', 'OFF']:
        cfg = results[mode]['config']
        print(f"\n  GridAdvisor {mode}:")
        print(f"    TP={cfg['tp']:.1f} SL={cfg['sl']:.1f} ATR=[{cfg['atr_min']:.0f}-{cfg['atr_max']:.0f}]")
        print(f"    BE={cfg['be']:.0f} Grace={cfg['grace']} Slope={cfg['slope']:.2f}")
    
    # Vencedor
    f3_delta = off['f3_pnl'] - on['f3_pnl']
    time_delta = off['elapsed'] - on['elapsed']
    
    print(f"\n{'='*80}")
    print("CONCLUSAO")
    print(f"{'='*80}")
    if f3_delta > 0:
        print(f"  GridAdvisor OFF encontrou MELHOR PnL OOS: +{f3_delta:,} pts")
    elif f3_delta < 0:
        print(f"  GridAdvisor ON encontrou MELHOR PnL OOS: +{-f3_delta:,} pts")
    else:
        print(f"  EMPATE no PnL OOS")
    
    if time_delta > 0:
        print(f"  GridAdvisor ON foi {time_delta:.1f}s mais rapido ({(1-time_delta/off['elapsed'])*100:.1f}% speedup)")
    elif time_delta < 0:
        print(f"  GridAdvisor OFF foi {-time_delta:.1f}s mais rapido")
    
    # Salva comparacao
    out = os.path.join(ROOT, 'docs', 'WIN_docs', f'compare_grid_advisor_{variant_col}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Comparacao salva: {out}")


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Compare GridAdvisor ON vs OFF')
    parser.add_argument('--signal-file', type=str, required=True, help='Arquivo PA_*.parquet')
    parser.add_argument('--variant', type=str, required=True, help='Nome da variante')
    parser.add_argument('--direction', type=int, default=-1, help='1=BUY, -1=SELL')
    args = parser.parse_args()
    
    compare_grid_advisor(args.signal_file, args.variant, args.direction)
