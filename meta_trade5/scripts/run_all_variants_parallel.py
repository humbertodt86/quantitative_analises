"""
Run All Variants Parallel — Full Cycle F1→F2(optimized)→OOS for all PA_SIGNAL_DIR variants
==========================================================================================

Executa ciclo completo para TODAS as variantes de PA_SIGNAL_DIR em paralelo.

F2 Otimizado:
  - F1: Grid completo (~4,032 combos) → top 10
  - F2: Para cada top 10, testa grid de guardrails (BE×HP×CD)
        Total: 10 × 36 = 360 combos por variante
  - OOS: Melhor config geral (TP/SL/ATR/BE/HP/CD)

Paralelização:
  - Usa multiprocessing.Pool (1 worker por variante)
  - Cada worker carrega dados independentemente
  - Workers = min(CPU cores, variantes)

Uso:
    python scripts/run_all_variants_parallel.py [--max-workers N] [--variants N]

Exemplo (teste com 5 variantes, 3 workers):
    python scripts/run_all_variants_parallel.py --max-workers 3 --variants 5

Exemplo (todas as 123 variantes, auto workers):
    python scripts/run_all_variants_parallel.py
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import time
import json
import argparse
from datetime import datetime
from multiprocessing import Pool, cpu_count
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# ===== CONFIGURAÇÃO DO F2 OTIMIZADO =====
# Grid expandido de guardrails para testar em F2
F2_BE_TRIGGERS = [50, 100, 200, 999999]
F2_HP_CANDLES = [1, 2, 3]
F2_CD_CANDLES = [0, 1, 2]
N_TOP_F1 = 10  # Top 10 do F1 passam para F2 otimizado

def run_single_variant(variant_config):
    """
    Worker function: roda 1 variante completa (F1→F2→OOS).
    Cada worker carrega dados independentemente.
    """
    import polars as pl
    import numpy as np
    from backtest.engine_v2 import BacktestEngine
    from engines.f1_binario_v4_hybrid import F1HybridEngine
    from engines.check_dist import calc_efficiency_ratio
    
    sname = variant_config['name']
    col = variant_config['col']
    signal_dir = variant_config['signal']
    regime = variant_config['regime']
    regime_filter = {'eq': 1} if regime == 'trend' else {'eq': 0}
    
    COST = 30
    BASE = os.path.join(ROOT, 'data')
    TICK_DIR = os.path.join(BASE, 'ticks')
    
    # Detect split mode
    is_path = os.path.join(BASE, 'super_win_IS.parquet')
    oos_path = os.path.join(BASE, 'super_win_OOS.parquet')
    split_mode = os.path.exists(is_path) and os.path.exists(oos_path)
    
    if split_mode:
        df_is = pl.read_parquet(is_path)
        df_oos = pl.read_parquet(oos_path)
        df_fev = df_is.filter((pl.col('dt') >= datetime(2026, 2, 1)) & (pl.col('dt') < datetime(2026, 3, 1)))
        df_full = pl.concat([df_is, df_oos]).sort('dt')
    else:
        SUPER = os.path.join(BASE, 'super_win_continuous.parquet')
        df_full = pl.read_parquet(SUPER)
        df_is = df_full.filter((pl.col('dt') >= datetime(2026, 1, 2)) & (pl.col('dt') <= datetime(2026, 3, 28)))
        df_oos = df_full.filter((pl.col('dt') >= datetime(2026, 3, 30)) & (pl.col('dt') <= datetime(2026, 4, 29)))
        df_fev = df_full.filter((pl.col('dt') >= datetime(2026, 2, 1)) & (pl.col('dt') < datetime(2026, 3, 1)))
    
    # Regime
    close_all = df_full['close'].to_numpy().astype(np.float64)
    adx_all = df_full['ADX7'].to_numpy().astype(np.float64)
    er_all = calc_efficiency_ratio(close_all, window=10)
    regime_all = np.where((er_all > 0.4) & (adx_all > 25) & (~np.isnan(er_all)), 1, 0).astype(np.int32)
    df_full = df_full.with_columns([
        pl.Series('efficiency_ratio', np.where(np.isnan(er_all), 0.0, er_all)),
        pl.Series('regime_label', regime_all),
    ])
    if split_mode:
        df_is = pl.read_parquet(is_path)
        df_oos = pl.read_parquet(oos_path)
        df_fev = df_is.filter((pl.col('dt') >= datetime(2026, 2, 1)) & (pl.col('dt') < datetime(2026, 3, 1)))
    
    # F1 cache
    FEV_CACHE = os.path.join(BASE, '_fev_cache_v2.npz')
    data = np.load(FEV_CACHE)
    ep_fev = data['ep']; atr_fev = data['atr']
    hour_fev = data['hour']; entry_idx_fev = data['entry_idx']
    regime_fev = df_fev['regime_label'].to_numpy().astype(np.int32)
    regime_at_entry = regime_fev[entry_idx_fev.astype(int)]
    sub_sell_idx = entry_idx_fev.astype(int)
    high_fev = df_fev['high'].to_numpy().astype(np.float64)
    low_fev = df_fev['low'].to_numpy().astype(np.float64)
    close_fev = df_fev['close'].to_numpy().astype(np.float64)
    
    # F1 Grid
    TP_GRID = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 15.0, 20.0]
    SL_GRID = [0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0]
    ATR_MIN_GRID = [50, 100, 150, 200, 300, 400]
    ATR_MAX_GRID = [400, 600, 800, 1000, 1500, 2000, 9999]
    F1_SL_FLOOR_ATR = 0.5
    F1_RR_CAP = 10.0
    
    # F1 Filter
    use_mask = (regime_at_entry == 1) if regime == 'trend' else (regime_at_entry == 0)
    sig_vals = df_fev[col].to_numpy().astype(np.int32)
    sig_at_entry = sig_vals[entry_idx_fev.astype(int)]
    final_mask = use_mask & (sig_at_entry == signal_dir)
    f1_idx = np.where(final_mask)[0]
    n_f1 = len(f1_idx)
    
    if n_f1 < 5:
        return {'variant': sname, 'status': 'abort', 'reason': f'entries={n_f1}'}
    
    sub_ep = ep_fev[f1_idx]
    sub_atr = atr_fev[f1_idx]
    sub_sell_idx = entry_idx_fev[f1_idx].astype(int)
    
    # F1 Execution
    engine = F1HybridEngine(high_fev, low_fev, close_fev, sub_ep, sub_atr, sub_sell_idx,
                            direction=signal_dir, n_threads=8)
    tp_grid_arr = np.array(TP_GRID, dtype=np.float64)
    sl_grid_arr = np.array(SL_GRID, dtype=np.float64)
    net_grid, n_grid = engine.evaluate_batch(tp_grid_arr, sl_grid_arr, blocking_mode='exact')
    engine.shutdown()
    
    f1_results = []
    for ti, tp in enumerate(TP_GRID):
        for si, sl in enumerate(SL_GRID):
            if tp / sl > F1_RR_CAP or sl < F1_SL_FLOOR_ATR:
                continue
            net = int(net_grid[ti, si])
            n = int(n_grid[ti, si])
            if n >= 3:
                for atr_mn in ATR_MIN_GRID:
                    for atr_mx in ATR_MAX_GRID:
                        f1_results.append({'tp': tp, 'sl': sl, 'atr_min': int(atr_mn), 'atr_max': int(atr_mx),
                                           'f1_net': net, 'f1_n': n})
    f1_results.sort(key=lambda x: x['f1_net'], reverse=True)
    f1_top = f1_results[:N_TOP_F1]
    
    if not f1_top:
        return {'variant': sname, 'status': 'abort', 'reason': 'no_f1_results'}
    
    # Ticks
    ticks_is = pl.read_parquet(os.path.join(BASE, 'WIN_merged_all.parquet'))
    ticks_is = ticks_is.with_columns([pl.col('last').alias('bid'), pl.col('last').alias('ask')])
    
    oos_ticks_unified = os.path.join(BASE, 'WIN_ticks_OOS_all.parquet')
    if os.path.exists(oos_ticks_unified):
        ticks_oos = pl.read_parquet(oos_ticks_unified)
    else:
        all_files = [os.path.join(TICK_DIR, f) for f in os.listdir(TICK_DIR)
                     if f.startswith('WIN') and f.endswith('.parquet')]
        all_files.sort()
        oos_parts = []
        for p in all_files:
            part = pl.read_parquet(p)
            part = part.with_columns([pl.col('bid').cast(pl.Float64), pl.col('ask').cast(pl.Float64), pl.col('last').cast(pl.Float64)])
            oos_parts.append(part)
        ticks_oos = pl.concat(oos_parts).sort('time_msc')
    ticks_oos = ticks_oos.filter((pl.col('bid') > 0) & (pl.col('ask') > 0) & (pl.col('bid') < pl.col('ask')))
    
    # Create engines
    eng_f2 = BacktestEngine(None)
    eng_f2.df = df_is
    eng_f2.load_ticks_for_simulation(ticks_is)
    
    eng_oos = BacktestEngine(None)
    eng_oos.df = df_oos
    eng_oos.load_ticks_for_simulation(ticks_oos)
    
    # F2 Optimization: para cada top F1, testa grid de guardrails
    best_overall = None
    best_net = -999999
    
    for r in f1_top:
        for be_trig in F2_BE_TRIGGERS:
            for hp_c in F2_HP_CANDLES:
                for cd_c in F2_CD_CANDLES:
                    behp = {
                        'be_trigger': be_trig, 'be_offset': 25,
                        'hp_candles': hp_c, 'hp_th': 0.15,
                        'tp30_pct': 0.30, 'grace_candles': 2,
                        'hard_stop': 500, 'cooldown_candles': cd_c, 'slope_decay': 0.50
                    }
                    cfg = {
                        'name': 'F2_opt', 'hour_min': 0.0, 'hour_max': 24.0, 'modo_busca': False,
                        'modes': {
                            'M': {
                                'enabled': True, 'priority': 1, 'signal_field': col,
                                'tp_mult': r['tp'], 'sl_mult': r['sl'],
                                'min_sl': 50, 'max_sl': min(500, r['atr_max']),
                                'filters': {
                                    'ATR': {'min': r['atr_min'], 'max': r['atr_max']},
                                    col: {'eq': signal_dir},
                                    'regime_label': regime_filter,
                                },
                                'behp': behp
                            }
                        }
                    }
                    try:
                        eng_f2.load_config_dict(cfg)
                        res = eng_f2.simulate()
                        m = eng_f2.calculate_metrics(res)
                        net = int(m['pnl'] - len(res) * COST)
                        
                        if net > best_net:
                            best_net = net
                            best_overall = {
                                'tp': r['tp'], 'sl': r['sl'],
                                'atr_min': r['atr_min'], 'atr_max': r['atr_max'],
                                'be_trigger': be_trig, 'hp_candles': hp_c, 'cooldown_candles': cd_c,
                                'f2_net': net, 'f2_n': len(res), 'f2_wr': m['wr'],
                            }
                    except Exception:
                        pass
    
    if not best_overall:
        return {'variant': sname, 'status': 'abort', 'reason': 'no_f2_results'}
    
    # OOS
    behp_oos = {
        'be_trigger': best_overall['be_trigger'], 'be_offset': 25,
        'hp_candles': best_overall['hp_candles'], 'hp_th': 0.15,
        'tp30_pct': 0.30, 'grace_candles': 2,
        'hard_stop': min(500, best_overall['atr_max']),
        'cooldown_candles': best_overall['cooldown_candles'], 'slope_decay': 0.50
    }
    cfg_oos = {
        'name': f'OOS_{sname}', 'hour_min': 0.0, 'hour_max': 24.0, 'modo_busca': False,
        'modes': {
            'M': {
                'enabled': True, 'priority': 1, 'signal_field': col,
                'tp_mult': best_overall['tp'], 'sl_mult': best_overall['sl'],
                'min_sl': 50, 'max_sl': min(500, best_overall['atr_max']),
                'filters': {
                    'ATR': {'min': best_overall['atr_min'], 'max': best_overall['atr_max']},
                    col: {'eq': signal_dir},
                    'regime_label': regime_filter,
                },
                'behp': behp_oos
            }
        }
    }
    
    try:
        eng_oos.load_config_dict(cfg_oos)
        res_oos = eng_oos.simulate()
        m_oos = eng_oos.calculate_metrics(res_oos)
        oos_net = int(m_oos['pnl'] - len(res_oos) * COST)
        oos_n = len(res_oos)
        oos_wr = m_oos['wr']
    except Exception:
        oos_net = 0; oos_n = 0; oos_wr = 0.0
    
    return {
        'variant': sname,
        'status': 'completed',
        'f1_entries': n_f1,
        'f1_top_net': f1_top[0]['f1_net'] if f1_top else 0,
        'f2_net': best_overall['f2_net'],
        'f2_n': best_overall['f2_n'],
        'f2_wr': best_overall['f2_wr'],
        'oos_net': oos_net,
        'oos_n': oos_n,
        'oos_wr': oos_wr,
        'config': {
            'tp': best_overall['tp'], 'sl': best_overall['sl'],
            'atr_min': best_overall['atr_min'], 'atr_max': best_overall['atr_max'],
            'be_trigger': best_overall['be_trigger'],
            'hp_candles': best_overall['hp_candles'],
            'cooldown_candles': best_overall['cooldown_candles'],
        }
    }

def main():
    parser = argparse.ArgumentParser(description='Run All Variants Parallel — Full Cycle')
    parser.add_argument('--max-workers', type=int, default=min(cpu_count(), 8),
                        help='Max parallel workers (default: min(CPU, 8))')
    parser.add_argument('--variants', type=int, default=0,
                        help='Number of variants to run (0=all)')
    parser.add_argument('--signal', type=int, default=-1, help='Signal direction: 1=BUY, -1=SELL')
    parser.add_argument('--regime', default='trend', help='Regime filter')
    args = parser.parse_args()
    
    print("="*80)
    print("RUN ALL VARIANTS PARALLEL — Full Cycle F1→F2(optimized)→OOS")
    print("="*80)
    
    # Discover all PA_SIGNAL_DIR variants
    import polars as pl
    df = pl.read_parquet(os.path.join(ROOT, 'data', 'super_win_IS.parquet'))
    all_cols = sorted([c for c in df.columns if c.startswith('PA_SIGNAL_DIR')])
    
    if args.variants > 0:
        all_cols = all_cols[:args.variants]
    
    print(f"\nTotal variantes: {len(all_cols)}")
    print(f"Workers: {args.max_workers}")
    print(f"F2 Grid: top {N_TOP_F1} F1 × {len(F2_BE_TRIGGERS)} BE × {len(F2_HP_CANDLES)} HP × {len(F2_CD_CANDLES)} CD = {N_TOP_F1 * len(F2_BE_TRIGGERS) * len(F2_HP_CANDLES) * len(F2_CD_CANDLES)} combos")
    print()
    
    # Build variant configs
    variant_configs = []
    for col in all_cols:
        name = col.replace('PA_SIGNAL_DIR', 'SIGNAL_DIR').strip('_')
        if name == 'SIGNAL_DIR':
            name = 'SIGNAL_DIR_BASE'
        variant_configs.append({
            'name': name,
            'col': col,
            'signal': args.signal,
            'regime': args.regime,
        })
    
    t0 = time.time()
    
    # Run in parallel
    results = []
    completed = 0
    aborted = 0
    
    with Pool(processes=args.max_workers) as pool:
        for i, result in enumerate(pool.imap_unordered(run_single_variant, variant_configs), 1):
            results.append(result)
            if result['status'] == 'completed':
                completed += 1
                print(f"[{i}/{len(variant_configs)}] ✅ {result['variant']:<30} F2={result['f2_net']:>+7} ({result['f2_n']:>3}t) OOS={result['oos_net']:>+7} ({result['oos_n']:>3}t, WR={result['oos_wr']:.1f}%)")
            else:
                aborted += 1
                print(f"[{i}/{len(variant_configs)}] ❌ {result['variant']:<30} ABORT: {result.get('reason', 'unknown')}")
    
    t_total = time.time() - t0
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY — ALL VARIANTS")
    print("="*80)
    
    completed_results = [r for r in results if r['status'] == 'completed']
    if completed_results:
        completed_results.sort(key=lambda x: x['oos_net'], reverse=True)
        
        print(f"\n{'Variant':<30} {'F2 Net':>8} {'F2 N':>5} {'OOS Net':>8} {'OOS N':>5} {'OOS WR':>7}")
        print("-"*70)
        for r in completed_results:
            print(f"{r['variant']:<30} {r['f2_net']:>+8} {r['f2_n']:>5} {r['oos_net']:>+8} {r['oos_n']:>5} {r['oos_wr']:>6.1f}%")
        
        # Top 5 OOS
        print("\n🏆 TOP 5 OOS:")
        for i, r in enumerate(completed_results[:5], 1):
            cfg = r['config']
            print(f"  #{i} {r['variant']:<25} OOS={r['oos_net']:>+7} ({r['oos_n']}t, WR={r['oos_wr']:.1f}%)  "
                  f"TP={cfg['tp']:.1f} SL={cfg['sl']:.1f} BE={cfg['be_trigger']}")
    
    print(f"\n{'='*80}")
    print(f"Completed: {completed} | Aborted: {aborted} | Total: {len(results)}")
    print(f"Tempo total: {t_total:.1f}s ({t_total/60:.1f}min)")
    print(f"Tempo médio por variante: {t_total/len(results):.1f}s")
    print(f"{'='*80}")
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = os.path.join(ROOT, 'docs', 'WIN_docs', f'all_variants_results_{timestamp}.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n💾 Resultados salvos em: {out_path}")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
