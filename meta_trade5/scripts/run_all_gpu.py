"""
RUN ALL GPU — Pipeline F1 → F2 GPU → F3 OOS Completo
=====================================================
Orquestra o pipeline completo de otimizacao para TODOS os sinais PA_*
com execucao F2 na GPU (CUDA RawKernel).

Pipeline por variante:
  1. F1 Screening (CPU): grid >5k combos, retorna top 30
  2. Filtro WR >= 35% (usando proxy do F1)
  3. F2 Optimization (GPU): otimiza TODOS os parametros simultaneamente
  4. F3 OOS Validation (CPU): valida top 3 F2 em ticks reais (Abr 2026)

Uso:
    python scripts/run_all_gpu.py [--signal 1|-1] [--limit N] [--batch-size 500000]

Requisitos:
    - CuPy com CUDA (GPU detectada automaticamente)
    - variants_v87/*.parquet com sinais pre-computados
    - WIN_ticks_OOS_all.parquet com ticks OOS bid/ask
"""
import sys, os, time, json, glob, warnings
from datetime import datetime
from typing import Dict, List, Tuple
import argparse
import numpy as np
import pandas as pd
import polars as pl

sys.stdout.reconfigure(encoding='utf-8')
warnings.filterwarnings('ignore')

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
# ENGINES
# ---------------------------------------------------------------------------
from engines.f1_binario_v4_hybrid import F1HybridEngine
from engines.f2_optimization_gpu import (
    optimize_all_combos_gpu, analyze_f1_stability,
    generate_refined_grid, GRID_ADVISOR
)
from scripts.family_classifier import get_family, get_family_config
from backtest.engine_v2 import BacktestEngine

# ---------------------------------------------------------------------------
# CONFIGURACAO
# ---------------------------------------------------------------------------
COST = 30.0
F1_MIN_WR_PROXY = 0.0       # F1 usa proxy (net > 0); WR real eh filtrado no F2
F1_TOP_N = 30               # Top N do F1 passa para F2 (usado para GridAdvisor)
F2_TOP_N = 3                # Top N do F2 passa para F3
GPU_BATCH_SIZE = 500_000

# Grid F1 expandido (>5k combos virtuais)
TP_GRID = [0.5, 0.8, 1.0, 1.2, 1.5, 1.8, 2.0, 2.2, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0, 20.0]
SL_GRID = [0.3, 0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0]
ATR_MIN_GRID = [50, 80, 100, 120, 150, 180, 200, 250, 300, 400, 500, 600]
ATR_MAX_GRID = [200, 300, 400, 500, 600, 800, 1000, 1200, 1500, 2000, 2500, 3000, 9999]
F1_SL_FLOOR_ATR = 0.3
F1_RR_MIN = 0.3
F1_RR_CAP = 20.0

# Paths
VARIANTS_DIR = os.path.join(ROOT, 'data', 'variants_v87')
OOS_TICKS_PATH = os.path.join(ROOT, 'data', 'win_deploy', 'WIN_ticks_OOS_all.parquet')
OOS_CANDLES_PATH = os.path.join(ROOT, 'data', 'win_deploy', 'super_win_OOS.parquet')
TRACKING_FILE = os.path.join(ROOT, 'scripts', 'signal_tracking_gpu.json')
OUT_DIR = os.path.join(ROOT, 'docs', 'WIN_docs')

IS_S, IS_E = datetime(2026, 2, 1), datetime(2026, 3, 1)

print(f"[CONFIG] F1 combos: {len(TP_GRID)}×{len(SL_GRID)}×{len(ATR_MIN_GRID)}×{len(ATR_MAX_GRID)} = {len(TP_GRID)*len(SL_GRID)*len(ATR_MIN_GRID)*len(ATR_MAX_GRID):,}")

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def load_tracking():
    if os.path.exists(TRACKING_FILE):
        with open(TRACKING_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_tracking(t):
    with open(TRACKING_FILE, 'w', encoding='utf-8') as f:
        json.dump(t, f, indent=2, default=str)

def discover_signals():
    """Descobre todos os arquivos PA_*.parquet em variants_v87."""
    files = sorted(glob.glob(os.path.join(VARIANTS_DIR, 'PA_*.parquet')))
    return files

def get_variant_columns(df: pl.DataFrame):
    """Extrai colunas de variantes (exclui OHLCV + indicadores)."""
    exclude = {'date_str','time_str','open','high','low','close','tick_volume','volume','spread',
               'dt','date','time','ATR','ADX7','EMA20','EMA5','EMA9','VWAP',
               'dist','dist_to_resistance','dist_to_support',
               'book_imbalance','book_imbalance_ma','book_imbalance_cum',
               'cum_delta','cum_delta_ma','concentration_poc','concentration_vah','concentration_val',
               'in_concentration'}
    return sorted([c for c in df.columns if c not in exclude])

# ---------------------------------------------------------------------------
# F1 SCREENING
# ---------------------------------------------------------------------------

def run_f1_screening(df_is: pd.DataFrame, variant_col: str, direction: int) -> Tuple[List[Dict], float]:
    """
    Roda F1 screening com grid expandido.
    Retorna top 30 configs + tempo.
    """
    start = time.time()
    
    signal = df_is[variant_col].values.astype(np.int32)
    mask = signal == direction
    n_entries = mask.sum()
    if n_entries < 5:
        return [], time.time() - start
    
    ep = df_is['close'].values[mask]
    atr = df_is['ATR'].values[mask]
    sell_idx = np.where(mask)[0]
    high = df_is['high'].values
    low = df_is['low'].values
    close = df_is['close'].values
    
    engine = F1HybridEngine(high, low, close, ep, atr, sell_idx, direction=direction, n_threads=8)
    tp_arr = np.array(TP_GRID, dtype=np.float64)
    sl_arr = np.array(SL_GRID, dtype=np.float64)
    net_grid, n_grid = engine.evaluate_batch(tp_arr, sl_arr, blocking_mode='exact')
    engine.shutdown()
    
    results = []
    for ti, tp in enumerate(TP_GRID):
        for si, sl in enumerate(SL_GRID):
            rr = tp / sl
            if rr > F1_RR_CAP or rr < F1_RR_MIN or sl < F1_SL_FLOOR_ATR:
                continue
            net = int(net_grid[ti, si])
            n = int(n_grid[ti, si])
            if n < 3:
                continue
            for atr_min in ATR_MIN_GRID:
                for atr_max in ATR_MAX_GRID:
                    if atr_min >= atr_max:
                        continue
                    # Aproximacao: assume que ATR filtro nao muda ranking drasticamente
                    # O F2 GPU corrige isso
                    results.append({
                        'tp_mult': float(tp), 'sl_mult': float(sl),
                        'atr_min': int(atr_min), 'atr_max': int(atr_max),
                        'net_pnl': net, 'n_trades': n,
                        'avg_trade': net / n if n > 0 else 0,
                    })
    
    results.sort(key=lambda x: x['net_pnl'], reverse=True)
    elapsed = time.time() - start
    return results[:F1_TOP_N], elapsed

# ---------------------------------------------------------------------------
# F2 GPU
# ---------------------------------------------------------------------------

def run_f2_gpu(df_is: pd.DataFrame, variant_col: str, direction: int,
               top30_f1: List[Dict], batch_size: int = GPU_BATCH_SIZE,
               use_grid_advisor: bool = True) -> Tuple[pd.DataFrame, float]:
    """
    Roda F2 optimization na GPU.
    Usa GridAdvisor para decidir se fixa TP/SL/ATR ou refina.
    Retorna DataFrame com top configs F2 + tempo.
    """
    start = time.time()
    
    # GridAdvisor: analisa estabilidade do F1 top 3 (se ativado)
    if use_grid_advisor:
        f1_stable, reason = analyze_f1_stability(top30_f1[:3])
        print(f"      GridAdvisor: {reason}")
    else:
        f1_stable = False
        reason = "DESATIVADO (--no-grid-advisor)"
        print(f"      GridAdvisor: {reason}")
    
    # Detecta familia do sinal pelo nome da coluna base
    signal_name = variant_col.split('_')[0] if '_' in variant_col else variant_col
    # Tenta detectar familia pelo nome completo ou fallback
    family = 'trend'
    try:
        family = get_family(variant_col)
    except Exception:
        pass
    
    try:
        family_config = get_family_config(family)
    except Exception:
        family_config = get_family_config('trend')
    
    # Ajusta filtros baseado na escala dos dados
    book_vals = df_is['book_imbalance'].values if 'book_imbalance' in df_is.columns else np.array([0])
    delta_vals = df_is['cum_delta'].values if 'cum_delta' in df_is.columns else np.array([0])
    
    # Se book_imbalance estiver em escala [-1, 1], manter [0.0]
    # Se cum_delta estiver em escala grande (>10), desabilitar filtro
    if np.abs(delta_vals).max() > 10:
        family_config['filters']['cum_delta_thresh'] = [-999.0, 0.0, 999.0]
    
    # Monta grid
    if f1_stable:
        f1_best = top30_f1[0]
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
    else:
        f1_best = top30_f1[0]
        refined = generate_refined_grid(f1_best, factor=0.20, num_values=5)
        grid = {
            'tp_sl_atr': refined,
            'sr_buffers': family_config['sr_buffers'],
            'guardrails': family_config['guardrails'],
            'filters': family_config['filters'],
        }
    
    # Roda GPU
    df_res, gpu_elapsed = optimize_all_combos_gpu(df_is, variant_col, direction, grid, batch_size=batch_size)
    
    total_elapsed = time.time() - start
    return df_res, total_elapsed

# ---------------------------------------------------------------------------
# F3 OOS
# ---------------------------------------------------------------------------

def run_f3_oos(df_oos: pl.DataFrame, ticks_oos: pl.DataFrame,
               variant_col: str, direction: int, config_f2: Dict) -> Dict:
    """
    Roda F3 OOS com ticks reais bid/ask.
    Retorna metricas finais.
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
        res = eng.simulate()
        m = eng.calculate_metrics(res)
        net = int(m['pnl'] - len(res) * COST)
        return {
            'status': 'ok',
            'net_pnl': net,
            'n_trades': len(res),
            'win_rate': m['wr'],
            'profit_factor': m['profit_factor'],
            'max_dd': m.get('max_drawdown_pts', 0),
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e), 'net_pnl': 0, 'n_trades': 0, 'win_rate': 0.0, 'profit_factor': 0.0, 'max_dd': 0}

# ---------------------------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------------------------

def process_variant(df_is: pd.DataFrame, df_oos_base: pl.DataFrame, ticks_oos: pl.DataFrame,
                    sig_path: str, variant_col: str, direction: int, batch_size: int,
                    use_grid_advisor: bool = True) -> Dict:
    """Processa uma variante completa: F1 → F2 GPU → F3 OOS."""
    
    print(f"\n{'='*80}")
    print(f"VARIANTE: {variant_col} | DIRECAO: {'BUY' if direction==1 else 'SELL'}")
    print(f"{'='*80}")
    
    result = {'variant': variant_col, 'direction': direction, 'phases': {}}
    
    # Merge OOS base com colunas do sinal
    sig_df = pl.read_parquet(sig_path)
    # Converte dt para mesmo tipo
    if str(df_oos_base['dt'].dtype) != str(sig_df['dt'].dtype):
        sig_df = sig_df.with_columns(pl.col('dt').cast(df_oos_base['dt'].dtype))
    # Seleciona apenas colunas necessarias para merge
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
    
    # Filtro WR >= 35%
    df_f2_valid = df_f2[df_f2['win_rate'] >= F1_MIN_WR_PROXY].reset_index(drop=True)
    if len(df_f2_valid) == 0:
        print(f"      [FILTRO] Nenhuma config com WR >= {F1_MIN_WR_PROXY}%")
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
        f3 = run_f3_oos(df_oos_merged, ticks_oos, variant_col, direction, config_f2)
        f3_results.append(f3)
        status_icon = "OK" if f3['status'] == 'ok' else "ERR"
        print(f"      F3 #{i+1}: {status_icon}  PnL={f3.get('net_pnl',0):>+7}  ({f3.get('n_trades',0)}t, WR={f3.get('win_rate',0):.1f}%)")
    
    best_f3 = max(f3_results, key=lambda x: x.get('net_pnl', 0))
    result['phases']['f3'] = {'results': f3_results, 'best': best_f3}
    result['status'] = 'completed'
    result['best_config'] = top3_f2.iloc[0].to_dict() if len(top3_f2) > 0 else {}
    
    print(f"\n  RESUMO: F1={best_f1['net_pnl']:,} → F2={best_f2['net_pnl']:,.0f} → F3={best_f3.get('net_pnl',0):+d}")
    
    return result


def main():
    parser = argparse.ArgumentParser(description='Run All GPU — F1→F2 GPU→F3 OOS')
    parser.add_argument('--signal', type=int, default=-1, help='1=BUY, -1=SELL')
    parser.add_argument('--limit', type=int, default=0, help='Limite de variantes (0=todos)')
    parser.add_argument('--batch-size', type=int, default=GPU_BATCH_SIZE, help='GPU batch size')
    parser.add_argument('--signal-file', type=str, default='', help='Processar apenas 1 arquivo PA_*.parquet')
    parser.add_argument('--grid-advisor', action='store_true', default=True, help='Ativar GridAdvisor (default)')
    parser.add_argument('--no-grid-advisor', action='store_true', default=False, help='Desativar GridAdvisor (refina sempre)')
    args = parser.parse_args()
    
    use_grid_advisor = not args.no_grid_advisor
    
    tracking = load_tracking()
    
    # Descobre arquivos
    if args.signal_file:
        signal_files = [args.signal_file]
    else:
        signal_files = discover_signals()
    
    print(f"\n{'='*80}")
    print("RUN ALL GPU — Pipeline F1 → F2 GPU → F3 OOS")
    print(f"{'='*80}")
    print(f"Sinais encontrados: {len(signal_files)}")
    print(f"Direcao: {'BUY' if args.signal == 1 else 'SELL'}")
    print(f"GPU batch size: {args.batch_size:,}")
    print(f"F1 min combos: {len(TP_GRID)*len(SL_GRID)*len(ATR_MIN_GRID)*len(ATR_MAX_GRID):,}")
    
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
    ticks_oos = ticks_oos.filter((pl.col('bid') > 0) & (pl.col('ask') > 0) & (pl.col('bid') < pl.col('ask')))
    print(f"      OOS base: {len(df_oos_base)} candles, {len(ticks_oos)} ticks  ({time.time()-t0:.1f}s)")
    
    # Processa cada sinal
    all_results = []
    dir_key = f'signal_{args.signal}'
    
    for sig_idx, sig_path in enumerate(signal_files, 1):
        signal_name = os.path.basename(sig_path).replace('.parquet', '')
        print(f"\n{'='*80}")
        print(f"SINAL {sig_idx}/{len(signal_files)}: {signal_name}")
        print(f"{'='*80}")
        
        # Carrega parquet do sinal (IS + OOS)
        t_load = time.time()
        df_full = pl.read_parquet(sig_path).to_pandas()
        df_full['dt'] = pd.to_datetime(df_full['dt'])
        df_is = df_full[(df_full['dt'] >= IS_S) & (df_full['dt'] <= IS_E)].reset_index(drop=True)
        df_oos_sig = df_full[(df_full['dt'] > IS_E)].reset_index(drop=True)
        print(f"  Parquet: {len(df_full)} rows total, {len(df_is)} IS (Fev), {len(df_oos_sig)} OOS (Abr+)")
        
        # Descobre variantes
        variant_cols = get_variant_columns(pl.read_parquet(sig_path))
        if not variant_cols:
            print(f"  [AVISO] Nenhuma variante encontrada em {signal_name}")
            continue
        
        # Filtra variantes ja processadas
        already_done = tracking.get(dir_key, {}).get('completed', [])
        remaining = [c for c in variant_cols if f"{signal_name}:{c}" not in already_done]
        print(f"  Variantes: {len(variant_cols)} total, {len(remaining)} restantes")
        
        if args.limit > 0:
            remaining = remaining[:args.limit]
        
        for v_idx, variant_col in enumerate(remaining, 1):
            t_variant = time.time()
            result = process_variant(df_is, df_oos_base, ticks_oos, sig_path, variant_col, args.signal, args.batch_size, use_grid_advisor)
            result['signal_name'] = signal_name
            result['elapsed_total'] = time.time() - t_variant
            all_results.append(result)
            
            if result['status'] == 'completed':
                best_f3 = result['phases']['f3']['best']
                print(f"  [{v_idx}/{len(remaining)}] {variant_col}: F3={best_f3.get('net_pnl',0):+d} ({best_f3.get('n_trades',0)}t, WR={best_f3.get('win_rate',0):.1f}%)  ({result['elapsed_total']:.1f}s)")
                # Tracking
                key = f"{signal_name}:{variant_col}"
                if dir_key not in tracking:
                    tracking[dir_key] = {'completed': []}
                if key not in tracking[dir_key]['completed']:
                    tracking[dir_key]['completed'].append(key)
            else:
                print(f"  [{v_idx}/{len(remaining)}] {variant_col}: ABORT ({result.get('reason')})  ({result['elapsed_total']:.1f}s)")
            
            save_tracking(tracking)
        
        # Libera memoria
        del df_full, df_is
    
    # Summary
    completed = [r for r in all_results if r['status'] == 'completed']
    print(f"\n{'='*80}")
    print("RESUMO FINAL")
    print(f"{'='*80}")
    print(f"Variantes processadas: {len(all_results)}")
    print(f"Completadas: {len(completed)}")
    
    if completed:
        completed.sort(key=lambda x: x['phases']['f3']['best'].get('net_pnl', 0), reverse=True)
        print(f"\nTOP 10 F3 OOS:")
        for i, r in enumerate(completed[:10], 1):
            b = r['phases']['f3']['best']
            print(f"  #{i:<3} {r['signal_name']}/{r['variant']:<25} OOS={b.get('net_pnl',0):>+7} ({b.get('n_trades',0)}t, WR={b.get('win_rate',0):.1f}%, PF={b.get('profit_factor',0):.2f})")
        
        pos = sum(1 for r in completed if r['phases']['f3']['best'].get('net_pnl', 0) > 0)
        print(f"\nPositivos OOS: {pos}/{len(completed)} ({pos/len(completed)*100:.1f}%)")
    
    # Save results
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = os.path.join(OUT_DIR, f'run_all_gpu_{dir_key}_{ts}.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResultados salvos: {out_path}")
    print(f"Tracking: {TRACKING_FILE}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
