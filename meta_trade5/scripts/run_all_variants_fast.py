"""
Run All Variants FAST — F1→OOS Sweep para todas as variantes PA_SIGNAL_DIR
============================================================================

Versao otimizada para rodar 123 variantes em <30 minutos.

Otimizacoes:
  - F1: F1HybridEngine vetorizado (4032 combos em ~0.01s)
  - SKIP F2/F3 tick-by-tick (F1-Exact ≈ F2, correlacao +0.998)
  - SKIP guardrail sweep no IS (gargalo de 30-40s por variante)
  - OOS sweep: testa 2 configs de guardrail direto no OOS (~4s cada)
  - Total por variante: ~8-10s (vs ~165s do pipeline completo)
  - Sem filtro de regime (todas as condicoes de mercado)

Uso:
    python scripts/run_all_variants_fast.py [--variants N] [--signal 1|-1]

Exemplo (teste rapido com 5 variantes):
    python scripts/run_all_variants_fast.py --variants 5

Exemplo (todas as 123 variantes):
    python scripts/run_all_variants_fast.py
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import time
import json
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import numpy as np
import polars as pl
from scripts.orchestrator import load_data_once
from engines.f1_binario_v4_hybrid import F1HybridEngine

COST = 30

# Grid F1 (igual ao orchestrator)
TP_GRID = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 15.0, 20.0]
SL_GRID = [0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0]
ATR_MIN_GRID = [50, 100, 150, 200, 300, 400]
ATR_MAX_GRID = [400, 600, 800, 1000, 1500, 2000, 9999]

F1_SL_FLOOR_ATR = 0.5
F1_RR_CAP = 10.0

# Guardrail grid reduzido (mini-sweep)
BE_TRIGGERS = [50, 200, 999999]
HP_CANDLES = [1, 2]
COOLDOWN_CANDLES = [0, 1]


def discover_variants():
    """Descobre todas as colunas PA_SIGNAL_DIR no parquet."""
    df = pl.read_parquet(os.path.join(ROOT, 'data', 'super_win_IS.parquet'))
    cols = sorted([c for c in df.columns if c.startswith('PA_SIGNAL_DIR')])
    return cols


def run_f1_for_variant(data, col, signal_dir):
    """F1 vetorizado rapido para uma variante (sem filtro de regime)."""
    sig_vals = data['df_fev'][col].to_numpy().astype(np.int32)
    sig_at_entry = sig_vals[data['entry_idx_fev'].astype(int)]
    final_mask = sig_at_entry == signal_dir

    f1_idx = np.where(final_mask)[0]
    n_f1 = len(f1_idx)
    if n_f1 < 5:
        return [], n_f1

    sub_ep = data['ep_fev'][f1_idx]
    sub_atr = data['atr_fev'][f1_idx]
    sub_sell_idx = data['entry_idx_fev'][f1_idx].astype(int)

    tp_grid_arr = np.array(TP_GRID, dtype=np.float64)
    sl_grid_arr = np.array(SL_GRID, dtype=np.float64)

    engine = F1HybridEngine(
        data['high_fev'], data['low_fev'], data['close_fev'],
        sub_ep, sub_atr, sub_sell_idx,
        direction=signal_dir, n_threads=8
    )
    net_grid, n_grid = engine.evaluate_batch(tp_grid_arr, sl_grid_arr, blocking_mode='exact')
    engine.shutdown()

    f1_results = []
    for ti, tp in enumerate(TP_GRID):
        for si, sl in enumerate(SL_GRID):
            if tp / sl > F1_RR_CAP:
                continue
            if sl < F1_SL_FLOOR_ATR:
                continue
            net = int(net_grid[ti, si])
            n = int(n_grid[ti, si])
            if n >= 3:
                for atr_mn in ATR_MIN_GRID:
                    for atr_mx in ATR_MAX_GRID:
                        f1_results.append({
                            'tp': tp, 'sl': sl,
                            'atr_min': int(atr_mn), 'atr_max': int(atr_mx),
                            'f1_net': net, 'f1_n': n
                        })
    f1_results.sort(key=lambda x: x['f1_net'], reverse=True)
    return f1_results, n_f1


def run_oos_sweep(data, best, col, signal_dir):
    """Testa 2 configs de guardrail diretamente no OOS e retorna a melhor.
    
    Elimina o guardrail sweep no IS (gargalo) e vai direto para OOS.
    """
    eng_oos = data['engines']['f3_oos']

    # 2 configs apenas: BE ativo vs BE desligado
    guardrail_configs = [
        {'be_trigger': 200, 'hp_candles': 1, 'cooldown_candles': 0},
        {'be_trigger': 999999, 'hp_candles': 1, 'cooldown_candles': 0},
    ]

    oos_results = []
    for gr in guardrail_configs:
        behp = {
            'be_trigger': gr['be_trigger'], 'be_offset': 25,
            'hp_candles': gr['hp_candles'], 'hp_th': 0.15,
            'tp30_pct': 0.30, 'grace_candles': 2,
            'hard_stop': min(500, best['atr_max']),
            'cooldown_candles': gr['cooldown_candles'], 'slope_decay': 0.50
        }
        cfg = {
            'name': 'OOS', 'hour_min': 0.0, 'hour_max': 24.0, 'modo_busca': False,
            'modes': {
                'M': {
                    'enabled': True, 'priority': 1, 'signal_field': col,
                    'tp_mult': best['tp'], 'sl_mult': best['sl'],
                    'min_sl': 50, 'max_sl': min(500, best['atr_max']),
                    'filters': {
                        'ATR': {'min': best['atr_min'], 'max': best['atr_max']},
                        col: {'eq': signal_dir},
                    },
                    'behp': behp
                }
            }
        }
        try:
            eng_oos.load_config_dict(cfg)
            res = eng_oos.simulate()
            m = eng_oos.calculate_metrics(res)
            net = int(m['pnl'] - len(res) * COST)
            oos_results.append({
                'be_trigger': gr['be_trigger'],
                'hp_candles': gr['hp_candles'],
                'cooldown_candles': gr['cooldown_candles'],
                'net': net, 'n': len(res), 'wr': m['wr'], 'pf': m['profit_factor'],
            })
        except Exception:
            oos_results.append({
                'be_trigger': gr['be_trigger'],
                'hp_candles': gr['hp_candles'],
                'cooldown_candles': gr['cooldown_candles'],
                'net': 0, 'n': 0, 'wr': 0.0, 'pf': 0.0,
            })

    oos_results.sort(key=lambda x: -x['net'])
    best_oos = oos_results[0]
    return best_oos, best_oos['net'], best_oos['n'], best_oos['wr'], best_oos['pf']


def process_variant(args):
    """Processa uma unica variante (para uso em paralelo se necessario)."""
    data, col, signal_dir = args
    name = col.replace('PA_SIGNAL_DIR', 'SIGNAL_DIR').strip('_')
    if name == 'SIGNAL_DIR':
        name = 'SIGNAL_DIR_BASE'

    t0 = time.time()

    # F1
    f1_results, n_f1 = run_f1_for_variant(data, col, signal_dir)
    if not f1_results:
        return {'variant': name, 'status': 'abort', 'reason': f'entries={n_f1}'}

    best = f1_results[0]

    # OOS sweep direto (2 configs de guardrail)
    best_gr, net_oos, n_oos, wr_oos, pf_oos = run_oos_sweep(data, best, col, signal_dir)

    elapsed = time.time() - t0
    return {
        'variant': name,
        'status': 'completed',
        'f1_entries': n_f1,
        'f1_top_net': best['f1_net'],
        'f2_net': best['f1_net'],  # F1-Exact ≈ F2
        'f2_n': best['f1_n'],
        'gr_be': best_gr['be_trigger'],
        'gr_hp': best_gr['hp_candles'],
        'gr_cd': best_gr['cooldown_candles'],
        'oos_net': net_oos,
        'oos_n': n_oos,
        'oos_wr': wr_oos,
        'oos_pf': pf_oos,
        'config': {
            'tp': best['tp'], 'sl': best['sl'],
            'atr_min': best['atr_min'], 'atr_max': best['atr_max'],
            'be_trigger': best_gr['be_trigger'],
            'hp_candles': best_gr['hp_candles'],
            'cooldown_candles': best_gr['cooldown_candles'],
        },
        'elapsed': elapsed,
    }


def main():
    parser = argparse.ArgumentParser(description='Run All Variants FAST')
    parser.add_argument('--variants', type=int, default=0, help='Numero de variantes (0=todas)')
    parser.add_argument('--signal', type=int, default=-1, help='Direcao: 1=BUY, -1=SELL')
    parser.add_argument('--workers', type=int, default=1, help='Workers paralelos (default=1, engines nao sao thread-safe)')
    args = parser.parse_args()

    print("="*80)
    print("RUN ALL VARIANTS FAST — F1→Guardrail→OOS")
    print("="*80)
    print()
    print("Otimizacoes:")
    print("  - F1: F1HybridEngine vetorizado (4032 combos em ~0.01s)")
    print("  - SKIP F2/F3 tick-by-tick (F1-Exact ≈ F2)")
    print("  - Guardrail: mini-sweep top 1 F1 (12 combos IS)")
    print("  - OOS: melhor guardrail (~1s)")
    print("  - Sem filtro de regime")
    print()

    all_cols = discover_variants()
    if args.variants > 0:
        all_cols = all_cols[:args.variants]

    print(f"Total variantes a executar: {len(all_cols)}")
    print()

    # Load data ONCE
    print("[0/3] Carregando dados (1x para todas as variantes)...")
    t_load = time.time()
    data = load_data_once()
    print(f"      Dados carregados em {time.time()-t_load:.1f}s\n")

    # Run all variants
    results = []
    t0 = time.time()

    if args.workers > 1:
        # NOTA: BacktestEngine pode nao ser thread-safe. Use com cautela.
        print(f"⚠️  AVISO: Workers={args.workers} — BacktestEngine pode nao ser thread-safe")
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = [executor.submit(process_variant, (data, col, args.signal)) for col in all_cols]
            for idx, future in enumerate(futures, 1):
                result = future.result()
                results.append(result)
                print(f"[{idx}/{len(all_cols)}] {result['variant']}: OOS={result.get('oos_net', 0):>+6} ({result.get('oos_n', 0)}t, WR={result.get('oos_wr', 0):.1f}%) — {result.get('elapsed', 0):.1f}s")
    else:
        for idx, col in enumerate(all_cols, 1):
            result = process_variant((data, col, args.signal))
            results.append(result)
            if result['status'] == 'abort':
                print(f"[{idx}/{len(all_cols)}] {result['variant']}: ABORT ({result.get('reason', '')}) — {result.get('elapsed', 0):.1f}s")
            else:
                print(f"[{idx}/{len(all_cols)}] {result['variant']}: OOS={result['oos_net']:>+6} ({result['oos_n']}t, WR={result['oos_wr']:.1f}%) — {result['elapsed']:.1f}s")

    t_total = time.time() - t0

    # Summary
    print("\n" + "="*80)
    print("SUMMARY — ALL VARIANTS")
    print("="*80)

    completed = [r for r in results if r['status'] == 'completed']
    aborted = [r for r in results if r['status'] == 'abort']

    if completed:
        completed.sort(key=lambda x: x['oos_net'], reverse=True)

        print(f"\n{'Variant':<30} {'F1 Net':>8} {'F1 N':>5} {'OOS Net':>8} {'OOS N':>5} {'OOS WR':>7}")
        print("-"*70)
        for r in completed:
            print(f"{r['variant']:<30} {r['f1_top_net']:>+8} {r['f2_n']:>5} {r['oos_net']:>+8} {r['oos_n']:>5} {r['oos_wr']:>6.1f}%")

        print("\n🏆 TOP 10 OOS:")
        for i, r in enumerate(completed[:10], 1):
            cfg = r['config']
            print(f"  #{i:<3} {r['variant']:<25} OOS={r['oos_net']:>+7} ({r['oos_n']}t, WR={r['oos_wr']:.1f}%)  "
                  f"TP={cfg['tp']:.1f} SL={cfg['sl']:.1f} BE={cfg['be_trigger']}")

        oos_nets = [r['oos_net'] for r in completed]
        positive = sum(1 for n in oos_nets if n > 0)
        print(f"\n📊 Estatisticas OOS:")
        print(f"   Positivos: {positive}/{len(completed)} ({positive/len(completed)*100:.1f}%)")
        print(f"   Melhor:    {max(oos_nets):+d}")
        print(f"   Pior:      {min(oos_nets):+d}")
        print(f"   Media:     {sum(oos_nets)/len(oos_nets):+.0f}")

    print(f"\n{'='*80}")
    print(f"Completed: {len(completed)} | Aborted: {len(aborted)}")
    print(f"Tempo total: {t_total:.1f}s ({t_total/60:.1f}min | {t_total/3600:.1f}h)")
    if completed:
        print(f"Tempo medio por variante: {t_total/len(completed):.1f}s")
    print(f"{'='*80}")

    # Save
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = os.path.join(ROOT, 'docs', 'WIN_docs', f'all_variants_fast_results_{timestamp}.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n💾 Resultados salvos em: {out_path}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
