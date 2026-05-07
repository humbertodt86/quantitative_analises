"""
Run All Variants — Full Cycle F1→F2(optimized)→OOS para todas as variantes PA_SIGNAL_DIR
=======================================================================================

Versao sequencial (dados carregados 1x, motores reutilizados).
Mais estavel que paralelizacao (evita problemas de memoria com ticks).

Para 123 variantes: ~4-6 horas (rode overnight).

Uso:
    python scripts/run_all_variants.py [--variants N] [--signal 1|-1]

Exemplo (teste rapido com 5 variantes):
    python scripts/run_all_variants.py --variants 5

Exemplo (todas as 123 variantes):
    python scripts/run_all_variants.py
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import time
import json
import argparse
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.orchestrator import load_data_once, run_cycle

# ===== F2 OTIMIZADO: Grid expandido de guardrails =====
# Monkey-patch para F2 otimizado
import scripts.orchestrator as orch

# Grid F1 padrao (pode ser ajustado)
# orch.TP_GRID = [...]  # ja definido no orchestrator
# orch.SL_GRID = [...]

# F2: top 15 do F1 (mais configs testadas)
orch.N_TOP_F2 = 15
orch.N_TOP_F3 = 5

# Guardrail expandido: mais combinacoes testadas em F2
orch.BE_TRIGGERS = [50, 100, 200, 999999]
orch.HP_CANDLES = [1, 2, 3]
orch.COOLDOWN_CANDLES = [0, 1, 2]

def discover_variants():
    """Descobre todas as colunas PA_SIGNAL_DIR no parquet."""
    import polars as pl
    df = pl.read_parquet(os.path.join(ROOT, 'data', 'super_win_IS.parquet'))
    cols = sorted([c for c in df.columns if c.startswith('PA_SIGNAL_DIR')])
    return cols

def main():
    parser = argparse.ArgumentParser(description='Run All Variants — Full Cycle')
    parser.add_argument('--variants', type=int, default=0, help='Numero de variantes (0=todas)')
    parser.add_argument('--signal', type=int, default=-1, help='Direcao: 1=BUY, -1=SELL')
    parser.add_argument('--regime', default='trend', help='Filtro de regime')
    args = parser.parse_args()
    
    print("="*80)
    print("RUN ALL VARIANTS — Full Cycle F1→F2(optimized)→OOS")
    print("="*80)
    print()
    print("Configuracao F2 Otimizado:")
    print(f"  F1 Grid: {len(orch.TP_GRID)} TP × {len(orch.SL_GRID)} SL × {len(orch.ATR_MIN_GRID)} ATR_MIN × {len(orch.ATR_MAX_GRID)} ATR_MAX = {len(orch.TP_GRID)*len(orch.SL_GRID)*len(orch.ATR_MIN_GRID)*len(orch.ATR_MAX_GRID)} combos")
    print(f"  F2: top {orch.N_TOP_F2} do F1, cada um testado com guardrails fixos")
    print(f"  F3: top {orch.N_TOP_F3} do F2")
    print(f"  Guardrail Sweep: {len(orch.BE_TRIGGERS)} BE × {len(orch.HP_CANDLES)} HP × {len(orch.COOLDOWN_CANDLES)} CD = {len(orch.BE_TRIGGERS)*len(orch.HP_CANDLES)*len(orch.COOLDOWN_CANDLES)} combos")
    print()
    
    # Discover variants
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
    
    for idx, col in enumerate(all_cols, 1):
        name = col.replace('PA_SIGNAL_DIR', 'SIGNAL_DIR').strip('_')
        if name == 'SIGNAL_DIR':
            name = 'SIGNAL_DIR_BASE'
        
        variant = {
            'name': name,
            'col': col,
            'signal': args.signal,
            'regime': args.regime,
        }
        
        print(f"[{idx}/{len(all_cols)}] 🔄 {name} ...", end=' ', flush=True)
        t_variant = time.time()
        
        log_path = os.path.join(ROOT, 'docs', 'WIN_docs', f'variant_{name}_log.txt')
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"Variant {name} log\n")
        
        try:
            result = run_cycle(
                data, variant,
                cycle_num=1, log_path=log_path,
                phases_to_run=['F1', 'F2', 'F3', 'GUARDRAIL', 'OOS']
            )
            
            if result['status'] == 'abort':
                print(f"ABORT ({result.get('reason', 'unknown')}) — {time.time()-t_variant:.1f}s")
                results.append({
                    'variant': name, 'status': 'abort',
                    'reason': result.get('reason'),
                })
            else:
                print(f"OOS={result['oos_net']:>+6} ({result['oos_n']:>3}t, WR={result['oos_wr']:.1f}%) — {time.time()-t_variant:.1f}s")
                results.append({
                    'variant': name,
                    'status': 'completed',
                    'f1_entries': result.get('f2_top_n', 0),  # proxy
                    'f1_top_net': result['f1_top_net'],
                    'f2_net': result['f2_top_net'],
                    'f2_n': result['f2_top_n'],
                    'f3_net': result['f3_top_net'],
                    'f3_n': result['f3_top_n'],
                    'oos_net': result['oos_net'],
                    'oos_n': result['oos_n'],
                    'oos_wr': result['oos_wr'],
                    'config': result['config'],
                })
        except Exception as e:
            print(f"ERROR: {e} — {time.time()-t_variant:.1f}s")
            import traceback
            traceback.print_exc()
            results.append({
                'variant': name, 'status': 'error',
                'reason': str(e),
            })
    
    t_total = time.time() - t0
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY — ALL VARIANTS")
    print("="*80)
    
    completed = [r for r in results if r['status'] == 'completed']
    aborted = [r for r in results if r['status'] == 'abort']
    errors = [r for r in results if r['status'] == 'error']
    
    if completed:
        completed.sort(key=lambda x: x['oos_net'], reverse=True)
        
        print(f"\n{'Variant':<30} {'F2 Net':>8} {'F2 N':>5} {'OOS Net':>8} {'OOS N':>5} {'OOS WR':>7}")
        print("-"*70)
        for r in completed:
            print(f"{r['variant']:<30} {r['f2_net']:>+8} {r['f2_n']:>5} {r['oos_net']:>+8} {r['oos_n']:>5} {r['oos_wr']:>6.1f}%")
        
        # Top 10 OOS
        print("\n🏆 TOP 10 OOS:")
        for i, r in enumerate(completed[:10], 1):
            cfg = r['config']
            print(f"  #{i:<3} {r['variant']:<25} OOS={r['oos_net']:>+7} ({r['oos_n']}t, WR={r['oos_wr']:.1f}%)  "
                  f"TP={cfg['tp']:.1f} SL={cfg['sl']:.1f} BE={cfg['be_trigger']}")
        
        # Stats
        oos_nets = [r['oos_net'] for r in completed]
        positive = sum(1 for n in oos_nets if n > 0)
        print(f"\n📊 Estatisticas OOS:")
        print(f"   Positivos: {positive}/{len(completed)} ({positive/len(completed)*100:.1f}%)")
        print(f"   Melhor:    {max(oos_nets):+d}")
        print(f"   Pior:      {min(oos_nets):+d}")
        print(f"   Media:     {sum(oos_nets)/len(oos_nets):+.0f}")
    
    print(f"\n{'='*80}")
    print(f"Completed: {len(completed)} | Aborted: {len(aborted)} | Errors: {len(errors)}")
    print(f"Tempo total: {t_total:.1f}s ({t_total/60:.1f}min | {t_total/3600:.1f}h)")
    if completed:
        print(f"Tempo medio por variante: {t_total/len(completed):.1f}s")
    print(f"{'='*80}")
    
    # Save
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = os.path.join(ROOT, 'docs', 'WIN_docs', f'all_variants_results_{timestamp}.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n💾 Resultados salvos em: {out_path}")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
