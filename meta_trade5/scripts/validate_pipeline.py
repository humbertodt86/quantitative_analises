"""
Validate Pipeline — Script de validação rápida do pipeline F1→F2→F3→OOS
=======================================================================

Executa 1 variante com grid CURTO para validar que todo o pipeline funciona.
Ideal para testar em nova máquina ou depois de alterações no código.

Uso:
    python scripts/validate_pipeline.py

Grid curto (rápido):
    F1: 9 combos (3 TP x 3 SL) → ~0.01s
    F2: top 5 do F1 → ~5-15s (tick-by-tick IS)
    F3: top 2 do F2 → ~2-6s (validação)
    Guardrail: 1 combo (BE=999999) → ~2-5s
    OOS: 1 config → ~1-3s

Total esperado: 10-30s (vs 2-5 min do pipeline completo)
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import time
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.orchestrator import load_data_once, run_cycle

# ===== CONFIGURAÇÃO DE VALIDAÇÃO (GRID CURTO) =====
VALIDATION_VARIANT = {
    'name': 'VALIDATE_SIGNAL_DIR',
    'col': 'PA_SIGNAL_DIR',
    'signal': -1,
    'regime': 'trend',
}

# Reduzir tops para acelerar F2/F3
N_TOP_F2_VAL = 5
N_TOP_F3_VAL = 2

# Guardrail mínimo (apenas BE desabilitado)
BE_TRIGGERS_VAL = [999999]
HP_CANDLES_VAL = [1]
COOLDOWN_CANDLES_VAL = [0]

def patch_for_validation():
    """Monkey-patch orchestrator constants for validation run."""
    import scripts.orchestrator as orch
    orch.N_TOP_F2 = N_TOP_F2_VAL
    orch.N_TOP_F3 = N_TOP_F3_VAL
    orch.BE_TRIGGERS = BE_TRIGGERS_VAL
    orch.HP_CANDLES = HP_CANDLES_VAL
    orch.COOLDOWN_CANDLES = COOLDOWN_CANDLES_VAL
    # Grid curto para F1
    orch.TP_GRID = [1.5, 2.5, 3.5]
    orch.SL_GRID = [1.0, 2.0, 3.0]
    orch.ATR_MIN_GRID = [100, 200]
    orch.ATR_MAX_GRID = [600, 9999]
    print(f"[VALIDATION MODE] Grid: {len(orch.TP_GRID)}x{len(orch.SL_GRID)}x{len(orch.ATR_MIN_GRID)}x{len(orch.ATR_MAX_GRID)} = {len(orch.TP_GRID)*len(orch.SL_GRID)*len(orch.ATR_MIN_GRID)*len(orch.ATR_MAX_GRID)} combos")
    print(f"[VALIDATION MODE] F2 top: {N_TOP_F2_VAL}, F3 top: {N_TOP_F3_VAL}")
    print(f"[VALIDATION MODE] Guardrail: {len(BE_TRIGGERS_VAL)}x{len(HP_CANDLES_VAL)}x{len(COOLDOWN_CANDLES_VAL)} = {len(BE_TRIGGERS_VAL)*len(HP_CANDLES_VAL)*len(COOLDOWN_CANDLES_VAL)} combo")

def main():
    print("="*70)
    print("VALIDATE PIPELINE V7.6 — Grid Curto + 1 Variante")
    print("="*70)
    
    t0 = time.time()
    
    # Patch para modo validação
    patch_for_validation()
    
    # Load data
    print("\n[1/5] Carregando dados...")
    t1 = time.time()
    data = load_data_once()
    print(f"      Dados carregados em {time.time()-t1:.2f}s")
    
    # Run cycle
    print("\n[2/5] Executando ciclo completo...")
    log_path = os.path.join(ROOT, 'docs', 'WIN_docs', 'validate_pipeline_log.txt')
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write("Validation pipeline log\n")
    
    t2 = time.time()
    result = run_cycle(
        data, VALIDATION_VARIANT,
        cycle_num=1, log_path=log_path,
        phases_to_run=['F1', 'F2', 'F3', 'GUARDRAIL', 'OOS']
    )
    t_total = time.time() - t2
    
    # Report
    print("\n" + "="*70)
    print("RESULTADO DA VALIDAÇÃO")
    print("="*70)
    
    if result['status'] == 'abort':
        print(f"❌ ABORTADO: {result.get('reason', 'unknown')}")
        return 1
    
    print(f"\nVariante: {VALIDATION_VARIANT['name']}")
    print(f"Coluna: {VALIDATION_VARIANT['col']}")
    print(f"Sinal: {VALIDATION_VARIANT['signal']} ({'BUY' if VALIDATION_VARIANT['signal']==1 else 'SELL'})")
    print(f"Regime: {VALIDATION_VARIANT['regime']}")
    
    print(f"\n📊 F1: top_net={result['f1_top_net']:+d}")
    print(f"📊 F2: net={result['f2_top_net']:+d} ({result['f2_top_n']} trades)")
    print(f"📊 F3 IS: net={result['f3_top_net']:+d} ({result['f3_top_n']} trades)")
    print(f"🛡️  Guardrail: BE={result['gr_be']} HP={result['gr_hp']} CD={result['gr_cd']}")
    print(f"📈 OOS: net={result['oos_net']:+d} ({result['oos_n']} trades, WR={result['oos_wr']:.1f}%)")
    
    cfg = result['config']
    print(f"\n🔧 Config Final:")
    print(f"   TP={cfg['tp']:.1f}x ATR | SL={cfg['sl']:.1f}x ATR")
    print(f"   ATR_MIN={cfg['atr_min']} | ATR_MAX={cfg['atr_max']}")
    print(f"   BE_trigger={cfg['be_trigger']} | HP={cfg['hp_candles']} | CD={cfg['cooldown_candles']}")
    
    # Timings
    timings = result.get('timings', {})
    print(f"\n⏱️  Tempos por Fase:")
    prev = 0
    for label, t in timings.items():
        delta = t - prev
        print(f"   {label:<20} +{delta:>6.2f}s (total: {t:>7.2f}s)")
        prev = t
    print(f"   {'TOTAL CICLO':<20}  {t_total:>7.2f}s")
    print(f"   {'TOTAL GERAL':<20}  {time.time()-t0:>7.2f}s (inclui load)")
    
    # Save result
    out_path = os.path.join(ROOT, 'docs', 'WIN_docs', 'validate_pipeline_result.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n💾 Resultado salvo em: {out_path}")
    
    # Pass/Fail
    print("\n" + "="*70)
    if result['oos_n'] >= 3:
        print("✅ VALIDAÇÃO PASSOU — Pipeline funcional!")
        print(f"   OOS: {result['oos_n']} trades (mínimo recomendado: 10)")
    else:
        print("⚠️  VALIDAÇÃO INCONCLUSIVA — Poucos trades no OOS")
        print(f"   OOS: {result['oos_n']} trades (mínimo recomendado: 10)")
        print("   Isso é NORMAL com grid curto em período curto.")
    print("="*70)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
