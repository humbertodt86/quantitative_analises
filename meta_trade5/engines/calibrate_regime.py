"""
calibrate_regime.py — Calibracao de Deteccao de Regime V6.3
===========================================================
Ground Truth: Realized Trend Proxy usando Efficiency Ratio FUTURO.
Nao usa futuro para treinar o detector — apenas para AVALIAR.

Metodologia:
  1. Detector atual (inercia): ER_backward(window) > er_threshold AND ADX7 > adx_threshold
  2. Ground truth (realizacao): ER_forward(forward_window) > 0.5
  3. Matriz de confusao: comparar detector vs realizacao
  4. Threshold sweep: encontrar melhor combo (ADX x ER) por F1

Diferenca critica vs V6.2:
  - V6.2: ground truth = abs(close[i+5]/close[i] - 1) > 0.3 → LOOK-AHEAD, ruidoso
  - V6.3: ground truth = ER_forward(T0, T0+N) > 0.5 → suavizado, mede EFICIENCIA real

Uso:
    python engines/calibrate_regime.py

    from engines.calibrate_regime import calibrate
    resultados = calibrate()
"""
import sys, os, json
from datetime import datetime
import numpy as np
import polars as pl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engines.check_dist import calc_efficiency_ratio, label_regime

# ============================================================
# CONFIGURACAO
# ============================================================
ASSET = 'WIN'
SUPER = os.path.join(ROOT, 'data', f'super_{ASSET.lower()}_continuous.parquet')
OUT_DIR = os.path.join(ROOT, 'docs', 'WIN_docs')
ENGINES_DIR = os.path.join(ROOT, 'engines')

# Forward windows para ground truth
FORWARD_WINDOWS = [10, 15]

# Grid de thresholds para varredura
ADX_VALUES = [20, 22, 25, 28, 30, 35]
ER_THRESHOLDS = [0.30, 0.35, 0.40, 0.45, 0.50, 0.60]

# Ground truth: forward ER > GT_THRESHOLD = realized trend
GT_THRESHOLD = 0.5

# Backward ER window (para o detector)
ER_WINDOW = 10


def calc_forward_efficiency_ratio(close: np.ndarray, window: int = 10) -> np.ndarray:
    """
    Efficiency Ratio FUTURO — mede a eficiencia do movimento APOS o candle T0.
    
    ER_forward[T0] = |close[T0+N] - close[T0]| / sum(|close[T0+k] - close[T0+k-1]| for k=1..N)
    
    1.0 = o preco foi em linha reta de T0 a T0+N
    0.0 = o preco zig-zagueou sem sair do lugar
    
    Returns NaN para os ultimos `window` candles (nao ha futuro suficiente).
    NAO usado para treino — apenas para AVALIACAO (gabarito).
    """
    n = len(close)
    er_fwd = np.full(n, np.nan, dtype=np.float64)
    
    abs_ret = np.abs(np.diff(close))
    
    for i in range(n - window):
        direction = abs(close[i + window] - close[i])
        volatility = np.sum(abs_ret[i:i + window])
        if volatility > 0:
            er_fwd[i] = direction / volatility
    
    return er_fwd


def compute_confusion_matrix(predicted: np.ndarray, realized: np.ndarray) -> dict:
    """
    Matriz de confusao entre detector (predicted) e ground truth (realized).
    
    Retorna TP, FP, TN, FN, precision, recall, f1, accuracy.
    """
    mask = ~(np.isnan(predicted) | np.isnan(realized))
    p = predicted[mask].astype(bool)
    r = realized[mask].astype(bool)
    
    tp = int(np.sum(p & r))
    fp = int(np.sum(p & ~r))
    tn = int(np.sum(~p & ~r))
    fn = int(np.sum(~p & r))
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / (tp + fp + tn + fn) if (tp + fp + tn + fn) > 0 else 0.0
    
    return {
        'tp': tp, 'fp': fp, 'tn': tn, 'fn': fn,
        'precision': round(precision, 4),
        'recall': round(recall, 4),
        'f1': round(f1, 4),
        'accuracy': round(accuracy, 4),
        'n_valid': int(mask.sum()),
        'n_trend_realized': int(r.sum()),
        'n_trend_predicted': int(p.sum()),
    }


def threshold_sweep(df: pl.DataFrame,
                    adx_values: list = None,
                    er_values: list = None,
                    forward_window: int = 10,
                    er_window_backward: int = 10) -> list:
    """
    Varredura de thresholds ADX x ER.
    
    Para cada combo:
      1. Predicao: ER_backward > er_th AND ADX7 > adx_th
      2. Ground truth: ER_forward > GT_THRESHOLD
      3. Matriz de confusao
      4. Metricas precision/recall/F1
    
    Retorna lista de dicts ordenada por F1 descendente.
    """
    if adx_values is None:
        adx_values = ADX_VALUES
    if er_values is None:
        er_values = ER_THRESHOLDS
    
    close = df['close'].to_numpy().astype(np.float64)
    adx = df['ADX7'].to_numpy().astype(np.float64)
    
    # Pre-computar ER backward e forward (UMA vez)
    er_back = calc_efficiency_ratio(close, window=er_window_backward)
    er_fwd = calc_forward_efficiency_ratio(close, window=forward_window)
    
    # Ground truth
    realized = (er_fwd > GT_THRESHOLD).astype(np.int32)
    
    results = []
    for adx_th in adx_values:
        for er_th in er_values:
            # Predicao
            predicted = np.where(
                (er_back > er_th) & (adx > adx_th) & (~np.isnan(er_back)),
                1, 0
            ).astype(np.int32)
            # NaN nos primeiros ER_WINDOW candles
            predicted[:er_window_backward] = -1  # marca para exclusao
            
            cm = compute_confusion_matrix(predicted, realized)
            results.append({
                'adx_threshold': adx_th,
                'er_threshold': er_th,
                **cm,
            })
    
    results.sort(key=lambda x: x['f1'], reverse=True)
    return results


def calibrate(data_path: str = None,
              forward_window: int = 10,
              er_window_backward: int = 10,
              adx_values: list = None,
              er_values: list = None) -> dict:
    """
    Pipeline completo de calibracao.
    
    Args:
        data_path: caminho para o parquet (default: super_asset_continuous.parquet)
        forward_window: janela do ER futuro (ground truth)
        er_window_backward: janela do ER passado (detector)
        adx_values: lista de thresholds ADX7 para testar
        er_values: lista de thresholds ER para testar
    
    Returns:
        dict com resultados completos + melhor combo
    """
    if data_path is None:
        data_path = SUPER
    
    if adx_values is None:
        adx_values = ADX_VALUES
    if er_values is None:
        er_values = ER_THRESHOLDS
    
    # Carregar dados
    print(f"Loading {data_path}...")
    df = pl.read_parquet(data_path)
    n = len(df)
    print(f"  {n} rows, {df['dt'].min()} to {df['dt'].max()}")
    
    # Calcular ER forward
    close = df['close'].to_numpy().astype(np.float64)
    er_fwd = calc_forward_efficiency_ratio(close, window=forward_window)
    
    # Estatisticas do ground truth
    gt_valid = er_fwd[~np.isnan(er_fwd)]
    pct_trend_realized = float(np.mean(gt_valid > GT_THRESHOLD) * 100)
    print(f"  Forward ER (window={forward_window}): mean={np.nanmean(er_fwd):.3f}, "
          f"pct realized trend (>0.5): {pct_trend_realized:.1f}%")
    
    # Varredura de thresholds
    print(f"\nThreshold sweep: {len(adx_values)} ADX x {len(er_values)} ER = "
          f"{len(adx_values) * len(er_values)} combos...")
    sweep_results = threshold_sweep(df, adx_values, er_values,
                                     forward_window, er_window_backward)
    print(f"  Done.")
    
    # Melhor combo (por F1)
    best = sweep_results[0] if sweep_results else None
    
    # Montar resultado
    result = {
        'calibration_version': '1.0',
        'generated_at': datetime.now().isoformat(),
        'data_path': data_path,
        'n_rows': n,
        'date_range': {'min': str(df['dt'].min()), 'max': str(df['dt'].max())},
        'detector': {
            'type': 'ER_backward + ADX7',
            'er_window_backward': er_window_backward,
            'default_er_threshold': 0.4,
            'default_adx_threshold': 25,
        },
        'ground_truth': {
            'type': 'ER_forward (Realized Trend Proxy)',
            'forward_window': forward_window,
            'gt_threshold': GT_THRESHOLD,
            'pct_realized_trend': round(pct_trend_realized, 2),
        },
        'sweep_summary': {
            'n_adx_values': len(adx_values),
            'n_er_values': len(er_values),
            'n_combos': len(sweep_results),
        },
        'sweep_results': sweep_results,
        'best_combo': best,
    }
    
    return result


def save_json_report(result: dict, output_path: str = None):
    """Salva relatorio JSON."""
    if output_path is None:
        output_path = os.path.join(OUT_DIR, 'regime_calibration.json')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nJSON report: {output_path}")


def save_markdown_report(result: dict, output_path: str = None):
    """Salva relatorio Markdown em engines/REGIME_DETECTOR.md."""
    if output_path is None:
        output_path = os.path.join(ENGINES_DIR, 'REGIME_DETECTOR.md')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    best = result.get('best_combo', {})
    gt = result['ground_truth']
    det = result['detector']
    
    lines = []
    lines.append(f"# Regime Detector V6.3 — Documentacao")
    lines.append(f"")
    lines.append(f"**Gerado em:** {result['generated_at']}")
    lines.append(f"**Calibracao versao:** {result['calibration_version']}")
    lines.append(f"**Dados:** {result['n_rows']} linhas, {result['date_range']['min']} a {result['date_range']['max']}")
    lines.append(f"")
    
    # Secao 1: Especificacoes do Detector Atual
    lines.append(f"## 1. Especificacoes do Detector Atual (v1.0)")
    lines.append(f"")
    lines.append(f"| Parametro | Valor |")
    lines.append(f"|-----------|-------|")
    lines.append(f"| Metodo | {det['type']} |")
    lines.append(f"| Janela ER backward | {det['er_window_backward']} candles |")
    lines.append(f"| Threshold ER (default) | {det['default_er_threshold']} |")
    lines.append(f"| Threshold ADX7 (default) | {det['default_adx_threshold']} |")
    lines.append(f"| Features usadas | close, ADX7 |")
    lines.append(f"")
    
    # Secao 2: Ground Truth
    lines.append(f"## 2. Ground Truth — Realized Trend Proxy")
    lines.append(f"")
    lines.append(f"O gabarito de realizacao (post-hoc) usa o Efficiency Ratio **futuro** para")
    lines.append(f"medir se o movimento APOS o candle T0 foi eficiente (direcional) ou ruidoso (zig-zag).")
    lines.append(f"")
    lines.append(f"| Parametro | Valor |")
    lines.append(f"|-----------|-------|")
    lines.append(f"| Metodo | {gt['type']} |")
    lines.append(f"| Janela forward | {gt['forward_window']} candles |")
    lines.append(f"| Threshold de trend | ER_forward > {gt['gt_threshold']} |")
    lines.append(f"| %% candles classificados como trend (realizado) | {gt['pct_realized_trend']:.1f}% |")
    lines.append(f"")
    lines.append(f"**Atencao:** Este ground truth e usado APENAS para avaliacao, NUNCA para treino.")
    lines.append(f"O detector continua usando apenas dados passados (ER backward + ADX7).")
    lines.append(f"")
    
    # Secao 3: Metodologia
    lines.append(f"## 3. Metodologia de Calibracao")
    lines.append(f"")
    lines.append(f"1. Para cada candle T0, calcular:")
    lines.append(f"   - **Predicao**: ER_backward(T0-{det['er_window_backward']}, T0) > er_threshold AND ADX7(T0) > adx_threshold")
    lines.append(f"   - **Realizacao**: ER_forward(T0, T0+{gt['forward_window']}) > {gt['gt_threshold']}")
    lines.append(f"2. Construir matriz de confusao (TP, FP, TN, FN)")
    lines.append(f"3. Calcular precision, recall, F1, accuracy")
    lines.append(f"4. Varrer grid ADX x ER para encontrar o melhor F1")
    lines.append(f"")
    
    # Secao 4: Resultados
    lines.append(f"## 4. Resultados do Threshold Sweep")
    lines.append(f"")
    lines.append(f"Grid: {len(result['sweep_results'])} combinacoes")
    lines.append(f"")
    lines.append(f"### Melhor Combo (por F1)")
    lines.append(f"")
    if best:
        lines.append(f"| Metrica | Valor |")
        lines.append(f"|---------|-------|")
        lines.append(f"| ADX7 threshold | {best['adx_threshold']} |")
        lines.append(f"| ER threshold | {best['er_threshold']} |")
        lines.append(f"| Precision | {best['precision']:.4f} |")
        lines.append(f"| Recall | {best['recall']:.4f} |")
        lines.append(f"| F1 | {best['f1']:.4f} |")
        lines.append(f"| Accuracy | {best['accuracy']:.4f} |")
        lines.append(f"| TP | {best['tp']} |")
        lines.append(f"| FP | {best['fp']} |")
        lines.append(f"| TN | {best['tn']} |")
        lines.append(f"| FN | {best['fn']} |")
        lines.append(f"")
    
    # Tabela completa
    lines.append(f"### Tabela Completa ({len(result['sweep_results'])} combinacoes)")
    lines.append(f"")
    lines.append(f"| ADX | ER | Precision | Recall | F1 | Accuracy | TP | FP | TN | FN |")
    lines.append(f"|-----|----|-----------|--------|----|----------|----|----|----|----|")
    for r in result['sweep_results']:
        lines.append(f"| {r['adx_threshold']} | {r['er_threshold']:.2f} | "
                     f"{r['precision']:.4f} | {r['recall']:.4f} | {r['f1']:.4f} | "
                     f"{r['accuracy']:.4f} | {r['tp']} | {r['fp']} | "
                     f"{r['tn']} | {r['fn']} |")
    lines.append(f"")
    
    # Secao 5: Analise
    lines.append(f"## 5. Analise Precision-Recall")
    lines.append(f"")
    lines.append(f"### Como interpretar")
    lines.append(f"")
    lines.append(f"- **Precision alta** (> 0.5): Quando o detector diz 'Trend', a probabilidade de")
    lines.append(f"  o movimento futuro ser realmente direcional e alta. Porem, pode perder")
    lines.append(f"  tendencias reais (recall baixo).")
    lines.append(f"- **Recall alto** (> 0.5): O detector captura a maioria das tendencias reais,")
    lines.append(f"  mas com muitos falsos positivos (precision baixa), entrando em 'violinos'.")
    lines.append(f"- **F1**: Media harmonica entre precision e recall. Melhor equilibrio.")
    lines.append(f"")
    
    if best:
        lines.append(f"### Recomendacao")
        lines.append(f"")
        default_f1 = None
        for r in result['sweep_results']:
            if r['adx_threshold'] == det['default_adx_threshold'] and \
               abs(r['er_threshold'] - det['default_er_threshold']) < 0.001:
                default_f1 = r['f1']
                break
        
        lines.append(f"- **Thresholds default atuais**: ADX7 > {det['default_adx_threshold']} + "
                     f"ER > {det['default_er_threshold']} → F1={default_f1:.4f}" if default_f1 else
                     f"- **Thresholds default atuais**: ADX7 > {det['default_adx_threshold']} + "
                     f"ER > {det['default_er_threshold']}")
        lines.append(f"- **Thresholds calibrados**: ADX7 > {best['adx_threshold']} + "
                     f"ER > {best['er_threshold']} → F1={best['f1']:.4f}")
        f1_gain = best['f1'] - (default_f1 or 0)
        lines.append(f"- **Ganho de F1**: {f1_gain:+.4f}")
        lines.append(f"")
        
        if best['precision'] > 0.5:
            lines.append(f"> A precisao de {best['precision']:.1%} significa que, quando o detector")
            lines.append(f"> acusa TREND, ha {best['precision']:.0%} de chance de o movimento futuro")
            lines.append(f"> ser realmente direcional. Recall de {best['recall']:.1%} significa que")
            lines.append(f"> o detector captura {best['recall']:.0%} de todas as tendencias reais.")
    
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"*Documentacao gerada automaticamente por `engines/calibrate_regime.py`*")
    
    content = '\n'.join(lines)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Markdown report: {output_path}")


# ===== CLI =====
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Calibrate regime detector thresholds')
    parser.add_argument('--forward-window', type=int, default=10,
                        help='Forward window for ground truth ER (default: 10)')
    parser.add_argument('--er-window', type=int, default=10,
                        help='Backward window for detector ER (default: 10)')
    parser.add_argument('--asset', type=str, default='WIN',
                        help='Asset: WIN or WDO (default: WIN)')
    parser.add_argument('--out-json', type=str, default=None,
                        help='Output JSON path (default: docs/WIN_docs/regime_calibration.json)')
    parser.add_argument('--out-md', type=str, default=None,
                        help='Output Markdown path (default: engines/REGIME_DETECTOR.md)')
    
    args = parser.parse_args()
    
    # Atualizar paths para o asset
    ASSET = args.asset
    SUPER = os.path.join(ROOT, 'data', f'super_{ASSET.lower()}_continuous.parquet')
    OUT_DIR = os.path.join(ROOT, 'docs', f'{ASSET}_docs')
    
    print(f"{'='*60}")
    print(f"REGIME DETECTOR CALIBRATION v1.0")
    print(f"{'='*60}")
    print(f"Asset: {ASSET}")
    print(f"Forward window: {args.forward_window}")
    print(f"ER backward window: {args.er_window}")
    print(f"Ground truth threshold: ER_forward > {GT_THRESHOLD}")
    print(f"Threshold sweep: {len(ADX_VALUES)} ADX x {len(ER_THRESHOLDS)} ER = {len(ADX_VALUES)*len(ER_THRESHOLDS)} combos")
    print(f"{'='*60}\n")
    
    # Rodar calibracao
    resultados = calibrate(
        data_path=SUPER,
        forward_window=args.forward_window,
        er_window_backward=args.er_window,
    )
    
    # Salvar relatorios
    save_json_report(resultados, args.out_json)
    save_markdown_report(resultados, args.out_md)
    
    # Print best combo
    best = resultados.get('best_combo', {})
    print(f"\n{'='*60}")
    print(f"BEST COMBO (by F1)")
    print(f"{'='*60}")
    print(f"  ADX7 > {best.get('adx_threshold', '?')}  |  ER > {best.get('er_threshold', '?'):.2f}")
    print(f"  Precision: {best.get('precision', 0):.4f}")
    print(f"  Recall:    {best.get('recall', 0):.4f}")
    print(f"  F1:        {best.get('f1', 0):.4f}")
    print(f"  Accuracy:  {best.get('accuracy', 0):.4f}")
    print(f"  TP={best.get('tp',0)} FP={best.get('fp',0)} TN={best.get('tn',0)} FN={best.get('fn',0)}")
    print(f"{'='*60}")
    
    # Salvar script copy
    script_copy = os.path.join(ROOT, 'docs', 'WIN_docs', 'calibrate_regime_script.py')
    with open(__file__, 'r', encoding='utf-8') as src:
        content = src.read()
    os.makedirs(os.path.dirname(script_copy), exist_ok=True)
    with open(script_copy, 'w', encoding='utf-8') as dst:
        dst.write(content)
    print(f"  Script copy: {script_copy}")
    
    print(f"\nDONE.")
