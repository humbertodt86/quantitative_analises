"""
F2 OPTIMIZATION V8.7 — COM GRIDS POR FAMÍLIA E GRID ADVISOR INTELIGENTE
=========================================================================
Otimização completa de gestão de risco com grids específicos por família de sinal.

GridAdvisor Inteligente:
- Fixa TP/SL/ATR se F1 estável (CV% < 15%)
- Expande guardrails se PnL caiu >30%
- Zoom em S/R se ótimo no meio do grid

Input: Top 10 configs do F1 (por sinal)
Output: Top 3 configs por sinal

Tempo alvo: 0.3s (F1 estável) a 20min (F1 instável, breakout)
"""
import sys, os, gc, time, multiprocessing as mp
from datetime import datetime
from typing import Dict, List, Any, Tuple
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import polars as pl
from numba import njit
from scripts.family_classifier import (
    get_family, get_family_config, calculate_combos, estimate_time
)

# ============================================================================
# CONFIGURAÇÃO GLOBAL
# ============================================================================

COST = 30.0  # Custo por trade
N_WORKERS = min(mp.cpu_count(), 10)  # Máximo 10 workers
MAX_SUBCYCLES = 2  # Máximo de sub-ciclos (GridAdvisor)

# GridAdvisor thresholds
GRID_ADVISOR = {
    'cv_threshold_stable': 15.0,      # CV% < 15% → F1 estável
    'pnl_drop_threshold': 0.30,       # PnL caiu >30% → EXPAND guardrails
    'trade_drop_threshold': 0.50,     # Trades caíram >50% → EXPAND guardrails
}

# Período de teste (Fevereiro 2026)
IS_S, IS_E = datetime(2026, 2, 1), datetime(2026, 3, 1)

# ============================================================================
# ENGINE DE BACKTEST VETORIZADO
# ============================================================================

@njit(fastmath=True)
def backtest_f2_numba(
    close, high, low, atr, signal,
    tp_mult, sl_mult, atr_min, atr_max,
    tp_sr_pct, sl_sr_pct, sr_threshold_pct,
    dist_to_resistance, dist_to_support,
    book_imbalance, cum_delta,
    book_imb_thresh, cum_delta_thresh,
    be_offset, grace_candles, cooldown_candles, max_sl_consec, slope_decay,
    direction
):
    """Backtest vetorizado para F2.
    
    sr_threshold_pct: Só usa S/R se dist_to_sr < (tp_mult*atr * sr_threshold_pct)
                      Ex: sr_threshold_pct=1.15 → S/R só se estiver dentro de 15% do TP base
    """
    n_rows = len(close)
    
    total_pnl = 0.0
    total_trades = 0
    total_wins = 0
    consecutive_sl = 0
    in_position = False
    entry_price = 0.0
    tp_price = 0.0
    sl_price = 0.0
    cooldown_counter = 0
    
    for i in range(n_rows):
        if cooldown_counter > 0:
            cooldown_counter -= 1
            continue
        
        if not in_position:
            if abs(book_imbalance[i]) < book_imb_thresh:
                continue
            if direction == 1 and cum_delta[i] < cum_delta_thresh:
                continue
            if direction == -1 and cum_delta[i] > -cum_delta_thresh:
                continue
        
        if in_position:
            if direction == 1:
                tp_hit = high[i] >= tp_price
                sl_hit = low[i] <= sl_price
            else:
                tp_hit = low[i] <= tp_price
                sl_hit = high[i] >= sl_price
            
            if tp_hit or sl_hit:
                if direction == 1:
                    exit_price = tp_price if tp_hit else sl_price
                    pnl_pts = exit_price - entry_price
                else:
                    exit_price = tp_price if tp_hit else sl_price
                    pnl_pts = entry_price - exit_price
                
                pnl_liquid = pnl_pts - COST
                total_pnl += pnl_liquid
                total_trades += 1
                
                if pnl_liquid > 0:
                    total_wins += 1
                    consecutive_sl = 0
                else:
                    consecutive_sl += 1
                    if consecutive_sl >= max_sl_consec:
                        cooldown_counter = cooldown_candles
                
                in_position = False
        else:
            if signal[i] != direction:
                continue
            
            if atr[i] < atr_min or atr[i] > atr_max:
                continue
            
            # Calcula TP/SL base (sem S/R)
            if direction == 1:
                tp_base = close[i] + tp_mult * atr[i]
                sl_base = close[i] - sl_mult * atr[i]
                
                # TP com S/R: só aplica se S/R estiver dentro do threshold
                if dist_to_resistance[i] > 0:
                    sr_distance = dist_to_resistance[i] / (tp_mult * atr[i]) if (tp_mult * atr[i]) > 0 else 999
                    if sr_distance < sr_threshold_pct:
                        # S/R dentro do threshold → usa tp_sr_pct da distância
                        tp_price = close[i] + tp_sr_pct * dist_to_resistance[i]
                    else:
                        # S/R muito distante → usa TP base
                        tp_price = tp_base
                else:
                    tp_price = tp_base
                
                # SL com S/R: só aplica se S/R estiver dentro do threshold
                if dist_to_support[i] > 0:
                    sr_distance = dist_to_support[i] / (sl_mult * atr[i]) if (sl_mult * atr[i]) > 0 else 999
                    if sr_distance < sr_threshold_pct:
                        sl_price = close[i] - sl_sr_pct * dist_to_support[i]
                    else:
                        sl_price = sl_base
                else:
                    sl_price = sl_base
            else:  # SELL
                tp_base = close[i] - tp_mult * atr[i]
                sl_base = close[i] + sl_mult * atr[i]
                
                # TP com S/R (suporte)
                if dist_to_support[i] > 0:
                    sr_distance = dist_to_support[i] / (tp_mult * atr[i]) if (tp_mult * atr[i]) > 0 else 999
                    if sr_distance < sr_threshold_pct:
                        tp_price = close[i] - tp_sr_pct * dist_to_support[i]
                    else:
                        tp_price = tp_base
                else:
                    tp_price = tp_base
                
                # SL com S/R (resistência)
                if dist_to_resistance[i] > 0:
                    sr_distance = dist_to_resistance[i] / (sl_mult * atr[i]) if (sl_mult * atr[i]) > 0 else 999
                    if sr_distance < sr_threshold_pct:
                        sl_price = close[i] + sl_sr_pct * dist_to_resistance[i]
                    else:
                        sl_price = sl_base
                else:
                    sl_price = sl_base
            
            entry_price = close[i]
            in_position = True
    
    return total_pnl, total_trades, total_wins


def analyze_f1_stability(f1_top_3: List[Dict]) -> Tuple[bool, str]:
    """Analisa se F1 foi estável (CV% < 15%)."""
    if len(f1_top_3) < 3:
        return False, "F1 top 3 insuficiente"
    
    pnls = np.array([r['net_pnl'] for r in f1_top_3])
    tps = np.array([r['tp_mult'] for r in f1_top_3])
    sls = np.array([r['sl_mult'] for r in f1_top_3])
    
    cv_pnl = np.std(pnls, ddof=1) / np.mean(pnls) * 100 if np.mean(pnls) != 0 else 0
    tp_range = max(tps) - min(tps)
    sl_range = max(sls) - min(sls)
    
    # ATR_MAX varia naturalmente no F1, não usar como critério
    if cv_pnl < GRID_ADVISOR['cv_threshold_stable'] and tp_range < 0.2 and sl_range < 0.5:
        return True, f"F1 estável (CV={cv_pnl:.1f}%, TP range={tp_range:.2f}, SL range={sl_range:.2f})"
    else:
        return False, f"F1 instável (CV={cv_pnl:.1f}%, TP range={tp_range:.2f}, SL range={sl_range:.2f})"


def generate_refined_grid(f1_best: Dict, factor: float = 0.20, num_values: int = 5) -> Dict:
    """Gera grid refinado (±factor) ao redor do melhor do F1."""
    tp = f1_best['tp_mult']
    sl = f1_best['sl_mult']
    atr_min = f1_best['atr_min']
    atr_max = f1_best['atr_max']
    
    return {
        'tp_mult': np.linspace(tp * (1 - factor), tp * (1 + factor), num_values),
        'sl_mult': np.linspace(sl * (1 - factor), sl * (1 + factor), num_values),
        'atr_min': np.linspace(atr_min * (1 - factor), atr_min * (1 + factor), num_values),
        'atr_max': np.linspace(atr_max * (1 - factor), atr_max * (1 + factor), num_values),
    }


def optimize_single_config(args):
    """Otimiza uma única config F1."""
    (config_idx, config_f1, df, variant_col, direction, grid) = args
    
    start = time.time()
    
    close = df['close'].values.astype(np.float64)
    high = df['high'].values.astype(np.float64)
    low = df['low'].values.astype(np.float64)
    atr = df['ATR'].values.astype(np.float64)
    signal = df[variant_col].values.astype(np.float64)
    
    dist_res = df['dist_to_resistance'].values.astype(np.float64) if 'dist_to_resistance' in df.columns else np.zeros(len(df))
    dist_sup = df['dist_to_support'].values.astype(np.float64) if 'dist_to_support' in df.columns else np.zeros(len(df))
    book_imb = df['book_imbalance'].values.astype(np.float64) if 'book_imbalance' in df.columns else np.zeros(len(df))
    cum_delta = df['cum_delta'].values.astype(np.float64) if 'cum_delta' in df.columns else np.zeros(len(df))
    
    best_pnl = -999999
    best_config = None
    best_stats = None
    
    tp_sl_atr = grid['tp_sl_atr']
    sr_buffers = grid['sr_buffers']
    guardrails = grid['guardrails']
    filters = grid['filters']
    
    for tp_mult in tp_sl_atr['tp_mult']:
        for sl_mult in tp_sl_atr['sl_mult']:
            for atr_min in tp_sl_atr['atr_min']:
                for atr_max in tp_sl_atr['atr_max']:
                    for tp_sr in sr_buffers['tp_sr_pct']:
                        for sl_sr in sr_buffers['sl_sr_pct']:
                            for sr_thresh in sr_buffers.get('sr_threshold_pct', [1.15]):  # Default 15%
                                for be in guardrails['be_offset']:
                                    for grace in guardrails['grace_candles']:
                                        for cooldown in guardrails['cooldown_candles']:
                                            for max_sl in guardrails['max_sl_consec']:
                                                for slope in guardrails['slope_decay']:
                                                    for book_thresh in filters['book_imb_thresh']:
                                                        for delta_thresh in filters['cum_delta_thresh']:
                                                            pnl, trades, wins = backtest_f2_numba(
                                                                close, high, low, atr, signal,
                                                                tp_mult, sl_mult, atr_min, atr_max,
                                                                tp_sr, sl_sr, sr_thresh,
                                                                dist_res, dist_sup,
                                                            book_imb, cum_delta,
                                                            book_thresh, delta_thresh,
                                                            be, grace, cooldown, max_sl, slope,
                                                            direction
                                                        )
                                                        
                                                        if trades >= 10:
                                                            wr = wins / trades * 100
                                                            sharpe = (pnl / trades) / max(1, np.std([pnl/trades])) if trades > 1 else 0
                                                            score = pnl * 0.7 + sharpe * 100 * 0.3
                                                            
                                                            if score > best_pnl:
                                                                best_pnl = score
                                                                best_config = {
                                                                    'tp_mult': tp_mult,
                                                                    'sl_mult': sl_mult,
                                                                    'atr_min': atr_min,
                                                                    'atr_max': atr_max,
                                                                    'tp_sr_pct': tp_sr,
                                                                    'sl_sr_pct': sl_sr,
                                                                    'be_offset': be,
                                                                    'grace_candles': grace,
                                                                    'cooldown_candles': cooldown,
                                                                    'max_sl_consec': max_sl,
                                                                    'slope_decay': slope,
                                                                    'book_imb_thresh': book_thresh,
                                                                    'cum_delta_thresh': delta_thresh,
                                                                }
                                                                best_stats = {
                                                                    'net_pnl': pnl,
                                                                    'n_trades': trades,
                                                                    'win_rate': wr,
                                                                    'score': score,
                                                                }
    
    elapsed = time.time() - start
    
    return {
        'config_idx': config_idx,
        'config_f1': config_f1,
        'best_config': best_config,
        'best_stats': best_stats,
        'elapsed': elapsed,
    }


def run_f2_optimization(
    parquet_path: str,
    signal_name: str,
    variant_name: str,
    top10_f1: List[Dict],
    direction: int = 1
) -> Dict:
    """Roda otimização F2 com grids por família e GridAdvisor."""
    print(f"\n{'='*80}")
    print(f"F2 OPTIMIZATION — {signal_name} {'BUY' if direction==1 else 'SELL'}")
    print(f"{'='*80}")
    
    # 1. Classificar família
    family = get_family(signal_name)
    print(f"\nFamília: {family}")
    
    # 2. Carregar grid config da família
    try:
        family_config = get_family_config(family)
    except Exception as e:
        print(f"  [WARN] Erro: {e}")
        family_config = get_family_config('trend')
    
    # 3. GridAdvisor analisa F1
    f1_stable, reason = analyze_f1_stability(top10_f1[:3])
    print(f"  GridAdvisor: {reason}")
    
    # 4. Montar grid
    if f1_stable:
        f1_best = top10_f1[0]
        grid = {
            'tp_sl_atr': {
                'tp_mult': [f1_best['tp_mult']],
                'sl_mult': [f1_best['sl_mult']],
                'atr_min': [f1_best['atr_min']],
                'atr_max': [f1_best['atr_max']]
            },
            'sr_buffers': family_config['sr_buffers'],
            'guardrails': family_config['guardrails'],
            'filters': family_config['filters'],
        }
        print(f"  TP/SL/ATR: FIXO (1 combo)")
    else:
        f1_best = top10_f1[0]
        refined = generate_refined_grid(f1_best, factor=0.20, num_values=5)
        grid = {
            'tp_sl_atr': refined,
            'sr_buffers': family_config['sr_buffers'],
            'guardrails': family_config['guardrails'],
            'filters': family_config['filters'],
        }
        print(f"  TP/SL/ATR: REFINO (±20%)")
    
    # 5. Calcular combos e tempo
    tp_sl_atr_combos = len(grid['tp_sl_atr']['tp_mult']) * len(grid['tp_sl_atr']['sl_mult']) * len(grid['tp_sl_atr']['atr_min']) * len(grid['tp_sl_atr']['atr_max'])
    sr_combos = len(grid['sr_buffers']['tp_sr_pct']) * len(grid['sr_buffers']['sl_sr_pct'])
    guardrail_combos = len(grid['guardrails']['be_offset']) * len(grid['guardrails']['grace_candles']) * len(grid['guardrails']['cooldown_candles']) * len(grid['guardrails']['max_sl_consec']) * len(grid['guardrails']['slope_decay'])
    filter_combos = len(grid['filters']['book_imb_thresh']) * len(grid['filters']['cum_delta_thresh'])
    total_combos = tp_sl_atr_combos * sr_combos * guardrail_combos * filter_combos
    
    estimated_time = total_combos / 10000
    print(f"\n  Combos TP/SL/ATR: {tp_sl_atr_combos:,}")
    print(f"  Combos S/R: {sr_combos:,}")
    print(f"  Combos Guardrails: {guardrail_combos:,}")
    print(f"  Combos Filtros: {filter_combos:,}")
    print(f"  TOTAL: {total_combos:,} combos")
    print(f"  Tempo estimado: {estimated_time:.1f}s")
    
    # 6. Carregar parquet
    print(f"\nLoading {parquet_path}...")
    df = pl.read_parquet(parquet_path).to_pandas()
    df['dt'] = pd.to_datetime(df['dt'])
    df = df[(df['dt'] >= IS_S) & (df['dt'] <= IS_E)].reset_index(drop=True)
    print(f"  Loaded: {len(df)} rows (Fevereiro 2026)")
    
    # 7. Preparar jobs
    jobs = []
    for i, config in enumerate(top10_f1):
        jobs.append((i, config, df, variant_name, direction, grid))
    
    # 8. Executar
    print(f"\nRunning optimization ({len(jobs)} configs F1 × {total_combos:,} combos F2)...")
    print(f"  Workers: {N_WORKERS}")
    
    start_total = time.time()
    
    with mp.Pool(N_WORKERS) as pool:
        results = pool.map(optimize_single_config, jobs)
    
    elapsed_total = time.time() - start_total
    print(f"\n  Tempo real: {elapsed_total:.1f}s")
    
    # 9. Consolidar
    results_sorted = sorted(results, key=lambda x: x['best_stats']['score'] if x['best_stats'] else 0, reverse=True)
    
    # 10. GridAdvisor analisa resultado
    if results_sorted and results_sorted[0]['best_stats']:
        f2_best = results_sorted[0]['best_stats']
        f1_best_pnl = top10_f1[0]['net_pnl']
        f1_best_trades = top10_f1[0]['n_trades']
        
        pnl_ratio = f2_best['net_pnl'] / f1_best_pnl if f1_best_pnl != 0 else 0
        trade_ratio = f2_best['n_trades'] / f1_best_trades if f1_best_trades != 0 else 0
        
        if pnl_ratio < (1 - GRID_ADVISOR['pnl_drop_threshold']):
            print(f"\n  [WARN] GridAdvisor: PnL caiu {(1-pnl_ratio)*100:.0f}% (F1={f1_best_pnl:,.0f}, F2={f2_best['net_pnl']:,.0f})")
        elif trade_ratio < (1 - GRID_ADVISOR['trade_drop_threshold']):
            print(f"\n  [WARN] GridAdvisor: Trades cairam {(1-trade_ratio)*100:.0f}% (F1={f1_best_trades}, F2={f2_best['n_trades']})")
        else:
            print(f"\n  [OK] GridAdvisor: OK (PnL {pnl_ratio*100:.0f}%, Trades {trade_ratio*100:.0f}%)")
    
    # 11. Top 3
    top3 = []
    for r in results_sorted[:3]:
        if r['best_config']:
            top3.append({
                'config_f1': r['config_f1'],
                'config_f2': r['best_config'],
                'stats': r['best_stats'],
            })
    
    # 12. Salvar
    output_path = os.path.join(ROOT, 'docs', 'WIN_docs', f'F2_OPTIMIZATION_{signal_name}_{"BUY" if direction==1 else "SELL"}.csv')
    
    results_df = pd.DataFrame([
        {
            'rank': i+1,
            'tp_mult': r['config_f1']['tp_mult'],
            'sl_mult': r['config_f1']['sl_mult'],
            'atr_min': r['config_f1']['atr_min'],
            'atr_max': r['config_f1']['atr_max'],
            'tp_sr_pct': r['config_f2']['tp_sr_pct'],
            'sl_sr_pct': r['config_f2']['sl_sr_pct'],
            'be_offset': r['config_f2']['be_offset'],
            'grace_candles': r['config_f2']['grace_candles'],
            'cooldown_candles': r['config_f2']['cooldown_candles'],
            'max_sl_consec': r['config_f2']['max_sl_consec'],
            'slope_decay': r['config_f2']['slope_decay'],
            'book_imb_thresh': r['config_f2']['book_imb_thresh'],
            'cum_delta_thresh': r['config_f2']['cum_delta_thresh'],
            'net_pnl': r['stats']['net_pnl'],
            'n_trades': r['stats']['n_trades'],
            'win_rate': r['stats']['win_rate'],
        }
        for r in top3
    ])
    
    results_df.to_csv(output_path, index=False)
    print(f"\n  Saved: {output_path}")
    
    # 13. Print top 3
    print(f"\n{'='*80}")
    print("TOP 3 CONFIGS F2:")
    print(f"{'='*80}")
    for i, r in enumerate(top3):
        print(f"\n  #{i+1}:")
        print(f"     TP/SL/ATR: TP={r['config_f1']['tp_mult']:.1f}, SL={r['config_f1']['sl_mult']:.1f}, ATR=[{r['config_f1']['atr_min']:.0f}-{r['config_f1']['atr_max']:.0f}]")
        print(f"     S/R: TP_SR={r['config_f2']['tp_sr_pct']:.2f}, SL_SR={r['config_f2']['sl_sr_pct']:.2f}")
        print(f"     Guarda: BE={r['config_f2']['be_offset']:.0f}, GRACE={r['config_f2']['grace_candles']}, CD={r['config_f2']['cooldown_candles']}, MAX_SL={r['config_f2']['max_sl_consec']}")
        print(f"     Filtros: BOOK={r['config_f2']['book_imb_thresh']:.1f}, DELTA={r['config_f2']['cum_delta_thresh']:.1f}")
        print(f"     Stats: PnL=R$ {r['stats']['net_pnl']:,.0f}, Trades={r['stats']['n_trades']}, WR={r['stats']['win_rate']:.1f}%")
    
    return {
        'signal': signal_name,
        'direction': 'BUY' if direction==1 else 'SELL',
        'top3': top3,
        'output_path': output_path,
    }


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='F2 Optimization V8.7')
    parser.add_argument('--signal', type=str, default='PA_SIGNAL_DIR', help='Signal name')
    parser.add_argument('--variant', type=str, default='s10_z4p0_r0p5', help='V8 variant')
    parser.add_argument('--direction', type=str, default='BUY', help='BUY or SELL')
    args = parser.parse_args()
    
    # Carregar F1
    f1_results_path = os.path.join(ROOT, 'docs', 'WIN_docs', f'F1_V87_TEST_{args.signal}.csv')
    
    if not os.path.exists(f1_results_path):
        print(f"\n[ERRO] F1 results nao encontrado: {f1_results_path}")
        exit(1)
    
    f1_df = pd.read_csv(f1_results_path)
    f1_df = f1_df[f1_df['signal'] == args.variant]
    f1_df = f1_df[f1_df['direction'] == args.direction]
    f1_df = f1_df.sort_values('net_pnl', ascending=False).head(10)
    
    if len(f1_df) == 0:
        print(f"\n[ERRO] Nenhuma config F1")
        exit(1)
    
    top10_f1 = f1_df[['tp_mult', 'sl_mult', 'atr_min', 'atr_max', 'net_pnl', 'n_trades']].to_dict('records')
    
    print(f"\nLoaded {len(top10_f1)} configs from F1:")
    for i, cfg in enumerate(top10_f1[:3]):
        print(f"  #{i+1}: TP={cfg['tp_mult']:.1f}, SL={cfg['sl_mult']:.1f}, ATR=[{cfg['atr_min']:.0f}-{cfg['atr_max']:.0f}], PnL={cfg['net_pnl']:,.0f}")
    
    # Carregar parquet
    parquet_path = os.path.join(ROOT, 'data', 'variants_v87', f'{args.signal}.parquet')
    
    if not os.path.exists(parquet_path):
        print(f"\n[ERRO] Parquet nao encontrado: {parquet_path}")
        exit(1)
    
    # Rodar
    direction = 1 if args.direction == 'BUY' else -1
    run_f2_optimization(parquet_path, args.signal, args.variant, top10_f1, direction)
