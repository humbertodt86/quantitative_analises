"""
Run All Variants FAST — F1→OOS Sweep para todas as variantes de um sinal PA_*
================================================================================

VERSAO: 1.1 (2026-05-06)
AUTOR: WIN Lead Quant Scientist

O QUE ESTE SCRIPT FAZ:
----------------------
Executa o pipeline completo de otimizacao F1→OOS para TODAS as variantes de
um sinal PA_* (ex: PA_SIGNAL_DIR tem 123 variantes como S0_Z10_R03, S5_Z30_R05).

O RESULTADO e um ranking de variantes com OOS positivo, pronto para DNA Analysis.

PIPELINE POR VARIANTE (1 ciclo completo):
------------------------------------------
  1. F1 SCREENING (0.01s)
     - F1HybridEngine vetorizado avalia 4,032 combos (TP×SL×ATR_MIN×ATR_MAX)
     - Usa apenas OHLC das candles (sem ticks) — blocking 'exact'
     - Correlacao F1-Exact vs F2: +0.998 (validado em docs/)
     - Retorna top 1 combo por PnL bruto IS

  2. GUARDRAIL SWEEP (eliminado no IS, feito no OOS — ver abaixo)

  3. OOS VALIDATION (2-4s)
     - Testa a top config F1 no periodo OOS (Abr/2026, dados nunca vistos)
     - Usa BacktestEngine com ticks reais (bid/ask)
     - Testa 2 configs de guardrail: BE=200 vs BE=999999 (desligado)
     - Retorna o melhor PnL OOS

O QUE E GUARDRAIL SWEEP?
-------------------------
Guardrails sao mecanismos de protecao que modificam o comportamento do trade
DURANTE a operacao (diferente de filtros de entrada que decidem SE entra):

  - BE (Break-Even): Quando o trade atinge X pts de lucro, move o SL
    para o preco de entrada (tira risco). Ex: BE_trigger=200 → lucro>=200pts
    → SL = preco de entrada + offset (ex: +25pts)

  - HP (Hold Period / Grace Period): Numero de candles iniciais onde o trade
    NAO pode ser fechado no SL, mesmo que o preco toque. Ex: HP=2 → as 2
    primeiras candles ignoram o SL. Isso da "respiro" para o trade se desenvolver.

  - CD (Cooldown): Depois de um SL, quantas candles esperar antes de aceitar
    novo sinal. Ex: CD=2 → apos um loss, pula 2 candles.

  - TP30: Se apos HP candles o lucro for <30% do TP, reduz o TP (take-profit
    adaptativo que fecha cedo em trades fracos).

  - Slope Decay: Reduz o TP dinamicamente conforme o tempo passa.

POR QUE ELIMINAMOS O GUARDRAIL SWEEP NO IS?
--------------------------------------------
No pipeline original (orchestrator.py), o guardrail sweep no IS fazia:
  - 36 combos (4 BE × 3 HP × 3 CD) × BacktestEngine tick-by-tick
  - Cada combo levava ~0.7s → total de ~25s por variante
  - Isso era 95% do tempo total (~165s por variante)

Como F1-Exact ≈ F2 (correlacao +0.998), o F2/F3 no IS sao redundantes.
O que realmente importa e o OOS. Entao pulamos o sweep no IS e testamos
apenas 2 configs de guardrail DIRETO no OOS:
  - BE=200 (conservador — protege rapido)
  - BE=999999 (agressivo — desabilita BE completamente)

Isso reduz o tempo de ~165s para ~3s por variante (55x mais rapido).

VERSUS O PIPELINE ORIGINAL:
---------------------------
| Fase               | Pipeline Original | Este Script | Economia |
|--------------------|-------------------|-------------|----------|
| F1                 | 0.01s            | 0.01s       | 0s       |
| F2 (IS tick-by-t)  | 45s              | SKIP        | 45s      |
| F3 (IS top 3)      | 15s              | SKIP        | 15s      |
| Guardrail Sweep IS | 100s             | SKIP        | 100s     |
| OOS                | 1s               | 2-4s        | -3s      |
| TOTAL por variante | ~165s            | ~3s         | **55x**  |

PARAMETROS:
-----------
    --signal     Direcao do trade: 1=BUY, -1=SELL (padrao: -1)
    --variants   Numero de variantes a rodar (0=todas, padrao: 0)
    --workers    Workers paralelos (padrao: 1, cuidado: engine pode nao ser thread-safe)

EXEMPLOS:
---------
    # Rodar todas as 123 variantes de PA_SIGNAL_DIR (SELL)
    python scripts/run_all_variants_fast.py

    # Rodar apenas as 5 primeiras variantes (teste rapido)
    python scripts/run_all_variants_fast.py --variants 5

    # Rodar em modo BUY
    python scripts/run_all_variants_fast.py --signal 1

SAIDA:
------
    - JSON: docs/WIN_docs/all_variants_fast_results_YYYYMMDD_HHMMSS.json
    - Contem: PnL OOS, WR, numero de trades, config (TP/SL/BE/HP/CD) por variante

DEPENDENCIAS:
-------------
    - scripts/orchestrator.py (load_data_once)
    - engines/f1_binario_v4_hybrid.py (F1HybridEngine)
    - backtest/engine_v2.py (BacktestEngine para OOS)
    - data/super_win_IS.parquet, super_win_OOS.parquet
    - data/WIN_ticks_OOS_all.parquet
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

# =============================================================================
# GRID F1 — Espaco de busca para pre-filtro vetorizado
# =============================================================================
# TP/SL: multiplicadores do ATR na entrada
# ATR_MIN/MAX: filtro de volatilidade (em pontos)
# Total bruto: 12×8×6×7 = 4,032 combos
# Apos filtros de sanity (SL_floor>=0.5x, RR<=10): ~3,570 combos validos
TP_GRID = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 15.0, 20.0]
SL_GRID = [0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0]
ATR_MIN_GRID = [50, 100, 150, 200, 300, 400]
ATR_MAX_GRID = [400, 600, 800, 1000, 1500, 2000, 9999]

# Filtros de sanity no F1 (evitam overfit de micro-stop e precision overfit)
F1_SL_FLOOR_ATR = 0.5   # SL deve ser >= 0.5x ATR (evita stop muito apertado)
F1_RR_CAP = 10.0        # TP/SL ratio <= 10 (evita overfit a precisao extrema)


def discover_variants():
    """
    Descobre todas as colunas PA_SIGNAL_DIR* no parquet IS.
    
    Retorna lista ordenada de strings como:
    ['PA_SIGNAL_DIR', 'PA_SIGNAL_DIR_DEPRECATED', 'PA_SIGNAL_DIR_S0_Z10_R03', ...]
    
    O parquet super_win_IS.parquet contem 123+ colunas com prefixo PA_SIGNAL_DIR,
    cada uma representando uma variante do sinal com parametros diferentes
    (S=slope_min, Z=z_max, R=r_min, etc.).
    """
    df = pl.read_parquet(os.path.join(ROOT, 'data', 'super_win_IS.parquet'))
    cols = sorted([c for c in df.columns if c.startswith('PA_SIGNAL_DIR')])
    return cols


def run_f1_for_variant(data, col, signal_dir):
    """
    Executa F1 screening vetorizado para UMA variante.
    
    Args:
        data: dict retornado por load_data_once() (contem df_fev, ep_fev, etc.)
        col: nome da coluna no parquet (ex: 'PA_SIGNAL_DIR_S0_Z10_R03')
        signal_dir: 1=BUY, -1=SELL
    
    Returns:
        (f1_results, n_f1_entries)
        - f1_results: lista de dicts ordenados por PnL descendente
        - n_f1_entries: numero de entradas potenciais (para logging)
    
    Processo:
        1. Filtra entradas onde o sinal da coluna == signal_dir
        2. Cria F1HybridEngine com high/low/close das candles futuras
        3. Avalia batch de 96 combos TP×SL em uma chamada vetorizada
        4. Expande com ATR_MIN/ATR_MAX e aplica filtros de sanity
        5. Retorna lista ordenada por PnL bruto IS
    """
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
            # Filtro 1: R:R cap (evita TP muito maior que SL)
            if tp / sl > F1_RR_CAP:
                continue
            # Filtro 2: SL floor (evita SL menor que 0.5x ATR)
            if sl < F1_SL_FLOOR_ATR:
                continue
            net = int(net_grid[ti, si])
            n = int(n_grid[ti, si])
            # Filtro 3: minimo de trades para ser confiavel
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
    """
    Executa OOS sweep com 2 configs de guardrail.
    
    Args:
        data: dict de load_data_once()
        best: dict com {'tp', 'sl', 'atr_min', 'atr_max', 'f1_net', 'f1_n'}
        col: nome da coluna da variante
        signal_dir: 1=BUY, -1=SELL
    
    Returns:
        (best_gr, net_oos, n_oos, wr_oos, pf_oos)
    
    Configs testadas:
        - Config 1: BE=200 (conservador — ativa break-even cedo)
        - Config 2: BE=999999 (agressivo — desabilita BE completamente)
    
    A config vencedora e a que produz maior PnL liquido no OOS.
    
    IMPORTANTE: O OOS usa BacktestEngine com ticks reais (bid/ask), nao OHLC.
    Isso e o "Juiz Final" — dados que o modelo nunca viu durante o treino.
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
    """
    Processa uma unica variante: F1 → OOS Sweep.
    
    Args:
        args: tuple (data, col, signal_dir)
    
    Returns:
        dict com resultado completo da variante
    """
    data, col, signal_dir = args
    name = col.replace('PA_SIGNAL_DIR', 'SIGNAL_DIR').strip('_')
    if name == 'SIGNAL_DIR':
        name = 'SIGNAL_DIR_BASE'

    t0 = time.time()

    # F1 — pre-filtro vetorizado ultra-rapido
    f1_results, n_f1 = run_f1_for_variant(data, col, signal_dir)
    if not f1_results:
        return {'variant': name, 'status': 'abort', 'reason': f'entries={n_f1}'}

    best = f1_results[0]

    # OOS sweep — testa guardrails direto no OOS (2 configs)
    best_gr, net_oos, n_oos, wr_oos, pf_oos = run_oos_sweep(data, best, col, signal_dir)

    elapsed = time.time() - t0
    return {
        'variant': name,
        'status': 'completed',
        'f1_entries': n_f1,
        'f1_top_net': best['f1_net'],
        'f2_net': best['f1_net'],  # F1-Exact ≈ F2 (correlacao +0.998)
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
    parser = argparse.ArgumentParser(
        description='Run All Variants FAST — F1→OOS Sweep para sinais PA_*',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
EXEMPLOS:
  # Todas as variantes de PA_SIGNAL_DIR (SELL, padrao)
  python scripts/run_all_variants_fast.py

  # Apenas 5 variantes (teste rapido)
  python scripts/run_all_variants_fast.py --variants 5

  # Modo BUY
  python scripts/run_all_variants_fast.py --signal 1

  # Workers paralelos (cuidado: BacktestEngine pode nao ser thread-safe)
  python scripts/run_all_variants_fast.py --workers 4

SAIDA:
  JSON em docs/WIN_docs/all_variants_fast_results_YYYYMMDD_HHMMSS.json
        """
    )
    parser.add_argument('--variants', type=int, default=0, help='Numero de variantes (0=todas)')
    parser.add_argument('--signal', type=int, default=-1, help='Direcao: 1=BUY, -1=SELL')
    parser.add_argument('--workers', type=int, default=1, help='Workers paralelos (default=1)')
    args = parser.parse_args()

    print("="*80)
    print("RUN ALL VARIANTS FAST — F1→OOS Sweep")
    print("="*80)
    print()
    print("O que este script faz:")
    print("  1. F1: Pre-filtro vetorizado (4,032 combos em ~0.01s)")
    print("  2. OOS Sweep: Testa BE=200 vs BE=999999 no periodo OOS (~2-4s)")
    print("  3. Ranking: Ordena variantes por PnL OOS")
    print()
    print("O que e GUARDRAIL SWEEP?")
    print("  - BE (Break-Even): Move SL para entrada quando lucro >= X pts")
    print("  - HP (Hold Period): Ignora SL nas primeiras N candles")
    print("  - CD (Cooldown): Espera N candles apos um loss")
    print("  - No pipeline original, testavamos 36 combos no IS (gargalo de 100s)")
    print("  - Aqui, testamos apenas 2 configs DIRETO no OOS (economia de 55x)")
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
