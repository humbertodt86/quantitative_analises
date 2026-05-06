"""
Run Signal Variants — Batch execution for PA_SIGNAL_DIR variants
===============================================================
Executa ciclo completo (F1->F2->F3->Guardrail->OOS) para múltiplas variantes
de um sinal, usando dados carregados uma única vez.

Uso:
  python scripts/run_signal_variants.py

Variantes testadas (subconjunto representativo das 120+ variantes):
  - PA_SIGNAL_DIR (base)
  - PA_SIGNAL_DIR_V2
  - PA_SIGNAL_DIR_DEPRECATED
  - PA_SIGNAL_DIR_S0_Z30_R05
  - PA_SIGNAL_DIR_S5_Z30_R05
  - PA_SIGNAL_DIR_S10_Z30_R05
  - PA_SIGNAL_DIR_S20_Z30_R05
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import json
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.orchestrator import load_data_once, run_cycle, phase1_go_no_go, phase2_dna, phase3_rank_hypotheses

OUT_DIR = os.path.join(ROOT, 'docs', 'WIN_docs')

# Subconjunto representativo das variantes PA_SIGNAL_DIR
VARIANTS = [
    {'name': 'SIGNAL_DIR_BASE',      'col': 'PA_SIGNAL_DIR',              'signal': -1, 'regime': 'trend'},
    {'name': 'SIGNAL_DIR_V2',        'col': 'PA_SIGNAL_DIR_V2',           'signal': -1, 'regime': 'trend'},
    {'name': 'SIGNAL_DIR_DEPRECATED','col': 'PA_SIGNAL_DIR_DEPRECATED',   'signal': -1, 'regime': 'trend'},
    {'name': 'SIGNAL_DIR_S0_Z30_R05','col': 'PA_SIGNAL_DIR_S0_Z30_R05',   'signal': -1, 'regime': 'trend'},
    {'name': 'SIGNAL_DIR_S5_Z30_R05','col': 'PA_SIGNAL_DIR_S5_Z30_R05',   'signal': -1, 'regime': 'trend'},
    {'name': 'SIGNAL_DIR_S10_Z30_R05','col': 'PA_SIGNAL_DIR_S10_Z30_R05', 'signal': -1, 'regime': 'trend'},
    {'name': 'SIGNAL_DIR_S20_Z30_R05','col': 'PA_SIGNAL_DIR_S20_Z30_R05', 'signal': -1, 'regime': 'trend'},
]

def main():
    print("\n" + "="*70)
    print("RUN SIGNAL VARIANTS — Batch Execution")
    print(f"Total variants: {len(VARIANTS)}")
    print("="*70)
    
    # Load data ONCE
    data = load_data_once()
    
    results = []
    
    for idx, variant in enumerate(VARIANTS, 1):
        print(f"\n{'='*70}")
        print(f"VARIANT {idx}/{len(VARIANTS)}: {variant['name']}")
        print(f"Column: {variant['col']}")
        print("="*70)
        
        log_path = os.path.join(OUT_DIR, f"variant_{variant['name']}_log.txt")
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"Variant {variant['name']} log\n")
        
        try:
            result = run_cycle(data, variant, cycle_num=1, log_path=log_path,
                               phases_to_run=['F1', 'F2', 'F3', 'GUARDRAIL', 'OOS'])
            
            if result['status'] == 'abort':
                print(f"  ABORTED: {result.get('reason', 'unknown')}")
                results.append({
                    'variant': variant['name'],
                    'col': variant['col'],
                    'status': 'abort',
                    'reason': result.get('reason'),
                })
                continue
            
            # DNA Analysis
            dna = phase2_dna(result, data)
            
            # Rank Hypotheses
            hypotheses = phase3_rank_hypotheses(dna, result)
            
            results.append({
                'variant': variant['name'],
                'col': variant['col'],
                'status': 'completed',
                'f1_top_net': result['f1_top_net'],
                'f2_top_net': result['f2_top_net'],
                'f2_top_n': result['f2_top_n'],
                'f3_top_net': result['f3_top_net'],
                'f3_top_n': result['f3_top_n'],
                'gr_be': result['gr_be'],
                'gr_hp': result['gr_hp'],
                'gr_cd': result['gr_cd'],
                'oos_net': result['oos_net'],
                'oos_n': result['oos_n'],
                'oos_wr': result['oos_wr'],
                'oos_pf': result['oos_pf'],
                'config': result['config'],
                'timings': result['timings'],
                'dna': dna,
                'hypotheses': hypotheses,
            })
            
            print(f"\n  RESULT: OOS={result['oos_net']:+d} ({result['oos_n']}t, WR={result['oos_wr']:.1f}%)")
            print(f"  Best config: TP={result['config']['tp']:.1f} SL={result['config']['sl']:.2f} "
                  f"BE={result['config']['be_trigger']} HP={result['config']['hp_candles']} CD={result['config']['cooldown_candles']}")
            
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                'variant': variant['name'],
                'col': variant['col'],
                'status': 'error',
                'reason': str(e),
            })
    
    # Save consolidated results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = os.path.join(OUT_DIR, f'signal_variants_results_{timestamp}.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)
    
    # Summary table
    print("\n" + "="*70)
    print("SUMMARY — ALL VARIANTS")
    print("="*70)
    print(f"{'Variant':<25} {'F1 Net':>8} {'F2 Net':>8} {'F2 N':>5} {'OOS Net':>8} {'OOS N':>5} {'OOS WR':>7} {'Status':>10}")
    print("-"*70)
    for r in results:
        if r['status'] == 'completed':
            print(f"{r['variant']:<25} {r['f1_top_net']:>+8} {r['f2_top_net']:>+8} {r['f2_top_n']:>5} "
                  f"{r['oos_net']:>+8} {r['oos_n']:>5} {r['oos_wr']:>6.1f}% {r['status']:>10}")
        else:
            print(f"{r['variant']:<25} {'—':>8} {'—':>8} {'—':>5} {'—':>8} {'—':>5} {'—':>7} {r['status']:>10}")
    print("="*70)
    print(f"\nResults saved to: {out_path}")
    
    return results

if __name__ == '__main__':
    main()
