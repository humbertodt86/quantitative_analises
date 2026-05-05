"""
check_dist.py — Etapa 0: Validação de Separação de Regime (V6.3)
===============================================================
Substitui o classificador V6.2 (baseado em close[i+5] com look-ahead)
por Indicadores de Inércia baseados em Efficiency Ratio (Kaufman).

Proposito: Provar que os grupos Trend e Range sao estatisticamente
diferentes ANTES de iniciar o ciclo. Se nao separam, aborta.

Mudanca principal (vs V6.2):
  - Antes: trend_truth = abs(close[i+5]/close[i] - 1) > 0.3  → LOOK-AHEAD
  - Agora:  regime = ER(10) > threshold AND ADX7 > adx_th   → INERCIA

Zero look-ahead: ER usa diff(window) (atrasado), nao close[i+window] (futuro).

Para calibracao dos thresholds, vide engines/calibrate_regime.py e REGIME_DETECTOR.md.

Uso:
    from engines.check_dist import check_dist
    resultado = check_dist(df, periodo_label='Fev 2026', er_window=10)
    if resultado['abort']:
        print(f"ABORT: {resultado['motivo']}")
    else:
        print(f"Trend: {resultado['trend_pct']:.1f}% das candles, prosseguir")
"""
__version__ = "1.0"
import numpy as np
import polars as pl
from scipy.stats import mannwhitneyu

def calc_efficiency_ratio(close: np.ndarray, window: int = 10) -> np.ndarray:
    """
    Kaufman Efficiency Ratio: mede 'retilinearidade' do movimento.
    
    ER = |close[i] - close[i-window]| / sum(|close[i-k] - close[i-k-1]| for k=0..window-1)
    
    1.0 = movimento perfeitamente retilineo (preco foi em linha reta de A ate B)
    0.0 = movimento zig-zagueante (preco andou muito mas nao saiu do lugar)
    
    Nao usa futuro. Lookback puro de `window` candles.
    Primeiros `window` candles retornam NaN (insuficientes para calcular).
    """
    n = len(close)
    er = np.full(n, np.nan, dtype=np.float64)
    
    # Abs returns entre candles consecutivos
    abs_ret = np.abs(np.diff(close))  # len = n-1, abs_ret[k] = |close[k+1] - close[k]|
    
    for i in range(window, n):
        direction = abs(close[i] - close[i - window])
        volatility = np.sum(abs_ret[i - window:i])  # soma dos window passos
        if volatility > 0:
            er[i] = direction / volatility
    
    return er

def calc_dominant_er(close: np.ndarray) -> dict:
    """
    Testa varias janelas de ER (5, 10, 15, 20) e retorna a que tem
    melhor separacao nos extremos (p10 vs p90).
    """
    best = {'window': 10, 'spread': 0}
    for w in [5, 10, 15, 20]:
        er = calc_efficiency_ratio(close, window=w)
        valid = er[~np.isnan(er)]
        if len(valid) < 100:
            continue
        spread = np.percentile(valid, 90) - np.percentile(valid, 10)
        if spread > best['spread']:
            best = {'window': w, 'spread': spread, 'p10': np.percentile(valid, 10),
                    'p90': np.percentile(valid, 90)}
    return best

def label_regime(df: pl.DataFrame, er_window: int = 10,
                 trend_threshold: float = 0.4, adx_threshold: int = 25,
                 col_regime_out: str = 'regime_label') -> pl.DataFrame:
    """
    Rotula cada candle como TREND (1) ou RANGE (0) usando inercia.
    
    Criterio TREND:
      1. Efficiency Ratio(er_window) > trend_threshold
      2. ADX7 > adx_threshold
      Ambos precisam ser verdadeiros.
    
    Criterio RANGE:
      Caso contrario. Inclui:
      - ER baixo (zig-zag)
      - ADX baixo (sem tendencia)
      - ER alto mas ADX baixo (ruido direcional sem forca)
    
    Retorna o DataFrame original com coluna adicional `col_regime_out`.
    """
    close = df['close'].to_numpy().astype(np.float64)
    adx = df['ADX7'].to_numpy().astype(np.float64)
    
    er = calc_efficiency_ratio(close, window=er_window)
    
    regime = np.where((er > trend_threshold) & (adx > adx_threshold), 1, 0).astype(np.int32)
    
    return df.with_columns(pl.Series(col_regime_out, regime))

def validate_separation(df: pl.DataFrame, regime_col: str = 'regime_label',
                        feature_cols: list = None) -> dict:
    """
    Testa se os grupos Trend e Range têm distribuicoes diferentes.
    
    Usa Mann-Whitney U test (nao-parametrico, nao assume normalidade).
    H0: as duas amostras vem da mesma distribuicao.
    Se p < 0.05, rejeitamos H0 → grupos sao diferentes.
    
    Args:
        df: DataFrame com coluna regime_label
        regime_col: nome da coluna de regime (0=range, 1=trend)
        feature_cols: colunas a testar (default: ATR, EMA5_SLOPE_ABS, EFF_RATIO_10)
    
    Returns:
        dict com resultados por feature + decisao
    """
    if feature_cols is None:
        feature_cols = ['ATR', 'EMA5_SLOPE_ABS', 'ADX7', 'efficiency_ratio']
    
    # Garantir que efficiency_ratio existe
    if 'efficiency_ratio' not in df.columns:
        close = df['close'].to_numpy().astype(np.float64)
        er = calc_efficiency_ratio(close, window=10)
        df = df.with_columns(pl.Series('efficiency_ratio', er))
    
    trend = df.filter(pl.col(regime_col) == 1)
    range_ = df.filter(pl.col(regime_col) == 0)
    n_trend = len(trend)
    n_range = len(range_)
    
    results = {}
    all_significant = []
    all_not_significant = []
    
    for col in feature_cols:
        if col not in df.columns:
            continue
        
        t = trend[col].to_numpy().astype(np.float64)
        r = range_[col].to_numpy().astype(np.float64)
        t = t[~np.isnan(t)]
        r = r[~np.isnan(r)]
        
        if len(t) < 5 or len(r) < 5:
            results[col] = {'status': 'insufficient_data', 'n_trend': len(t), 'n_range': len(r)}
            all_not_significant.append(col)
            continue
        
        stat, p = mannwhitneyu(t, r, alternative='two-sided')
        significant = p < 0.05
        
        feat = {
            'trend_mean': float(np.mean(t)),
            'range_mean': float(np.mean(r)),
            'ratio': float(np.mean(t) / max(np.mean(r), 0.001)),
            'p_value': float(p),
            'significant': bool(significant),
        }
        results[col] = feat
        
        if significant:
            all_significant.append(col)
        else:
            all_not_significant.append(col)
    
    # Decisao
    pct_trend = n_trend / max(n_trend + n_range, 1) * 100
    abort_reasons = []
    
    if pct_trend < 10.0:
        abort_reasons.append(f"Trend representa apenas {pct_trend:.1f}% das candles (min 10%)")
    if pct_trend > 90.0:
        abort_reasons.append(f"Trend representa {pct_trend:.1f}% das candles (max 90%)")
    if len(all_significant) == 0:
        abort_reasons.append("Nenhuma feature tem separacao significativa (p < 0.05)")
    
    # Pelo menos metade das features precisa ser significante
    min_significant = max(1, len(feature_cols) // 2)
    if len(all_significant) < min_significant:
        abort_reasons.append(
            f"Apenas {len(all_significant)}/{len(feature_cols)} features sao significantes "
            f"(min {min_significant})"
        )
    
    return {
        'n_trend': n_trend,
        'n_range': n_range,
        'pct_trend': round(pct_trend, 2),
        'pct_range': round(100.0 - pct_trend, 2),
        'features': results,
        'n_significant': len(all_significant),
        'n_features': len(feature_cols),
        'abort': len(abort_reasons) > 0,
        'abort_reasons': abort_reasons,
        'all_significant': all_significant,
    }

def check_dist(df: pl.DataFrame, er_window: int = 10,
               trend_threshold: float = 0.4, adx_threshold: int = 25,
               periodo_label: str = 'IS') -> dict:
    """
    Etapa 0 completa: valida separacao de regime e retorna auditoria.
    
    Fluxo:
      1. Calcular Efficiency Ratio para o periodo
      2. Encontrar melhor janela de ER (se er_window='auto')
      3. Rotular regime
      4. Validar separacao estatistica
      5. Salvar auditoria em dict (pronto para JSON)
    
    Args:
        df: DataFrame super_win_continuous (polars)
        er_window: janela do ER (int) ou 'auto'
        trend_threshold: ER minimo para considerar trend
        adx_threshold: ADX7 minimo para considerar trend
        periodo_label: rotulo para o relatorio (ex: 'Fev 2026', 'Jan-Mar')
    
    Returns:
        dict com resultados, pronto para salvar como JSON
    
    Raises:
        ValueError: se a separacao falhar (para uso em pipeline automatico)
    """
    import json
    
    # 1. Calcular ER
    close = df['close'].to_numpy().astype(np.float64)
    
    if er_window == 'auto':
        best = calc_dominant_er(close)
        er_window = best['window']
    
    er = calc_efficiency_ratio(close, window=er_window)
    df = df.with_columns(pl.Series('efficiency_ratio', np.where(np.isnan(er), 0.0, er)))
    
    # 2. Calcular estatisticas descritivas do ER
    er_valid = er[~np.isnan(er)]
    er_stats = {
        'mean': float(np.mean(er_valid)),
        'median': float(np.median(er_valid)),
        'p10': float(np.percentile(er_valid, 10)),
        'p25': float(np.percentile(er_valid, 25)),
        'p75': float(np.percentile(er_valid, 75)),
        'p90': float(np.percentile(er_valid, 90)),
    }
    
    # 3. Rotular regime
    df = label_regime(df, er_window=er_window, trend_threshold=trend_threshold,
                      adx_threshold=adx_threshold)
    
    # 4. Validar separacao
    validation = validate_separation(df)
    
    # 5. Montar resultado
    result = {
        'check_dist_v': '1.0',
        'periodo': periodo_label,
        'n_candles': len(df),
        'er_window': er_window,
        'trend_threshold': trend_threshold,
        'adx_threshold': adx_threshold,
        'er_stats': er_stats,
        'validation': validation,
        'abort': validation['abort'],
        'abort_reasons': validation['abort_reasons'],
    }
    
    if validation['abort']:
        # Sugerir thresholds alternativos
        suggestions = []
        for er_t in [0.3, 0.4, 0.5, 0.6]:
            for adx_t in [20, 25, 30]:
                df_tmp = label_regime(df, er_window=er_window,
                                      trend_threshold=er_t, adx_threshold=adx_t)
                v = validate_separation(df_tmp)
                if not v['abort']:
                    suggestions.append({
                        'trend_threshold': er_t,
                        'adx_threshold': adx_t,
                        'pct_trend': v['pct_trend'],
                        'n_significant': v['n_significant'],
                    })
        result['suggestions'] = suggestions[:5]
    
    return result

def print_report(result: dict):
    """Imprime relatorio formatado de check_dist."""
    print(f"\n{'='*60}")
    print(f"CHECK DIST — Etapa 0: Validacao de Regime")
    print(f"Periodo: {result['periodo']}")
    print(f"Candles: {result['n_candles']}")
    print(f"ER window: {result['er_window']} | Threshold: {result['trend_threshold']} | ADX: {result['adx_threshold']}")
    print(f"{'='*60}")
    
    v = result['validation']
    print(f"\nDistribuicao: Trend={v['pct_trend']:.1f}% ({v['n_trend']}) | "
          f"Range={v['pct_range']:.1f}% ({v['n_range']})")
    
    print(f"\nEfficiency Ratio stats:")
    er = result['er_stats']
    print(f"  mean={er['mean']:.3f} median={er['median']:.3f} "
          f"p10={er['p10']:.3f} p25={er['p25']:.3f} p75={er['p75']:.3f} p90={er['p90']:.3f}")
    
    print(f"\nSeparacao por feature:")
    for col, feat in v['features'].items():
        if feat.get('status') == 'insufficient_data':
            print(f"  {col:20s}: INSUFICIENTE (trend={feat['n_trend']}, range={feat['n_range']})")
            continue
        sig = "SIGNIFICANTE" if feat['significant'] else "nao significativo"
        print(f"  {col:20s}: trend={feat['trend_mean']:.2f} range={feat['range_mean']:.2f} "
              f"ratio={feat['ratio']:.2f}x p={feat['p_value']:.2e} [{sig}]")
    
    print(f"\nFeatures significantes: {v['n_significant']}/{v['n_features']}")
    
    if result['abort']:
        print(f"\n{'!'*60}")
        print(f"ABORT: {', '.join(result['abort_reasons'])}")
        print(f"{'!'*60}")
        if result.get('suggestions'):
            print(f"\nSugestoes de threshold que passariam:")
            for s in result['suggestions'][:3]:
                print(f"  ER>{s['trend_threshold']} + ADX>{s['adx_threshold']} → "
                      f"Trend={s['pct_trend']:.1f}% ({s['n_significant']} features sig)")
    else:
        print(f"\n{'='*60}")
        print(f"PASS: Regime valido para prosseguir")
        print(f"{'='*60}")

# ===== CLI =====
if __name__ == '__main__':
    import sys, os, json
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Args
    args = sys.argv[1:]
    asset = 'WIN'
    er_window = 10
    trend_threshold = 0.4
    adx_threshold = 25
    periodo = 'IS'
    out = None
    
    for a in args:
        if a.startswith('--asset='): asset = a.split('=')[1]
        if a.startswith('--er='): er_window = int(a.split('=')[1])
        if a.startswith('--th='): trend_threshold = float(a.split('=')[1])
        if a.startswith('--adx='): adx_threshold = int(a.split('=')[1])
        if a.startswith('--period='): periodo = a.split('=')[1]
        if a.startswith('--out='): out = a.split('=')[1]
    
    # Load data
    from datetime import datetime
    parquet_map = {
        'WIN': os.path.join(ROOT, 'data', 'super_win_continuous.parquet'),
        'WDO': os.path.join(ROOT, 'data', 'super_wdo_continuous.parquet'),
    }
    path = parquet_map.get(asset, parquet_map['WIN'])
    print(f"Loading {asset} from {path}...")
    df = pl.read_parquet(path)
    
    # Filtrar por periodo
    if periodo == 'Fev':
        df = df.filter(pl.col('dt').dt.month() == 2)
    elif periodo == 'Jan-Mar':
        df = df.filter((pl.col('dt').dt.month() >= 1) & (pl.col('dt').dt.month() <= 3))
    elif periodo == 'IS':
        df = df.filter((pl.col('dt') >= datetime(2026,1,2)) & (pl.col('dt') <= datetime(2026,3,28)))
    elif periodo == 'OOS':
        df = df.filter((pl.col('dt') >= datetime(2026,3,30)) & (pl.col('dt') <= datetime(2026,4,30)))
    
    periodo_label = f"{asset} {periodo}"
    
    # Run
    result = check_dist(df, er_window=er_window, trend_threshold=trend_threshold,
                        adx_threshold=adx_threshold, periodo_label=periodo_label)
    
    print_report(result)
    
    if out:
        with open(out, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nRelatorio salvo: {out}")
    
    if result['abort']:
        sys.exit(1)
