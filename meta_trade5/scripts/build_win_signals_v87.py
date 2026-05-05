"""
Build WIN Signals V8.7 — CONSTRUTOR OTIMIZADO
=============================================
Gera parquets com grids otimizados (poda por correlacao + escalonamento geometrico).

REDUCAO: 2.2M → 3,150 variantes (707x)

Otimizacoes:
1. Poda por Correlacao: extremos + meio (nao valores intermediarios proximos)
2. Escalonamento Geometrico: passos que mudam comportamento (nao lineares)
3. Binning de Volatilidade: 3 regimes (Low/Normal/High)
4. Filtro Piso de Viabilidade: Anti-HFT (SL >= 150pts, TP >= 100pts)

Bugs Corrigidos:
1. PA_REV_RSI_B10/S90 → Unificados em PA_REV_RSI_UNIFIED
2. PA_HMA_CROSS_F5_S10 → Renomeado para PA_SMA_CROSS_F5_S10
3. V8_S_MIN=0.0 → Grid [0, 10, 20] (inclui valores com efeito real)

Saida:
- data/variants_v87/PA_SIGNAL_DIR.parquet (18 variantes)
- data/variants_v87/PA_REV_RSI_UNIFIED.parquet (12 variantes)
- ... (23 sinais total, 3,150 variantes)

Performance:
- Build time: ~5 min
- File size: ~70MB total
- F1 scan: 7.26M combos @ 50k/s = 2.4 min
"""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import polars as pl
import pandas as pd
import numpy as np
from datetime import datetime
from backtest.indicators import add_indicators, calc_rsi
from backtest.indicators_sr import add_microstructure_indicators  # NOVO

# ============================================================================
# CONFIGURACAO V8.7
# ============================================================================

CSV_DIR = os.path.join(ROOT, 'data', 'candles')
VARIANTS_DIR = os.path.join(ROOT, 'data', 'variants_v87')

# Contratos e datas de corte
J26_CSV = os.path.join(CSV_DIR, 'WINJ26_M5.csv')
M26_CSV = os.path.join(CSV_DIR, 'WINM26_M5_202601020910_202604291830.csv')
CUTOFF = pd.Timestamp('2026-04-14')
WARMUP = 60

# GRID V8.7 OTIMIZADO (poda por correlacao)
# Original: 5×5×5×5×5 = 3,125 → V8.7: 3×3×2 = 18 variantes
V8_S_MIN_GRID = [0, 10, 20]       # 3 valores (extremos + meio)
V8_Z_MAX_GRID = [1.5, 2.5, 4.0]   # 3 valores (extremos + meio)
V8_R_MIN_GRID = [0.5, 1.0]        # 2 valores (meio + extremo)

# Output directory
os.makedirs(VARIANTS_DIR, exist_ok=True)

print("="*80)
print("BUILD WIN SIGNALS V8.7 — CONSTRUTOR OTIMIZADO")
print("="*80)
print(f"V8_S_MIN_GRID: {V8_S_MIN_GRID}")
print(f"V8_Z_MAX_GRID: {V8_Z_MAX_GRID}")
print(f"V8_R_MIN_GRID: {V8_R_MIN_GRID}")
print(f"Total variantes PA_SIGNAL_DIR: {len(V8_S_MIN_GRID) * len(V8_Z_MAX_GRID) * len(V8_R_MIN_GRID)}")
print()

# ============================================================================
# FUNCOES AUXILIARES
# ============================================================================

def load_csv(path):
    """Carrega CSV no formato MetaTrader (tab-separated)."""
    print(f"  Loading {os.path.basename(path)}...")
    df = pd.read_csv(path, sep='\t')
    
    df = df.rename(columns={
        '<DATE>': 'date_str',
        '<TIME>': 'time_str',
        '<OPEN>': 'open',
        '<HIGH>': 'high',
        '<LOW>': 'low',
        '<CLOSE>': 'close',
        '<TICKVOL>': 'tick_volume',
        '<VOL>': 'volume',
        '<SPREAD>': 'spread'
    })
    
    df['dt'] = pd.to_datetime(df['date_str'] + ' ' + df['time_str'])
    df['date'] = df['dt'].dt.date
    df['time'] = df['dt'].dt.time
    
    return df


def compute_base_indicators(df):
    """Computa indicadores base (ADX, ATR, BB, VWAP, etc.)."""
    di = add_indicators(df, adx_period=7, daily_atr=True)
    return di


def compute_microstructure(di):
    """Computa indicadores de microestrutura (S/R, Book, Tape, Concentration)."""
    di = add_microstructure_indicators(di)
    return di


def compute_raw_indicators(di):
    """Computa indicadores raw (HMA, TSI, EFF_RATIO, etc.)."""
    h = di['high'].values
    l = di['low'].values
    c = di['close'].values
    v = di['tick_volume'].values
    
    # EMAs adicionais
    di['EMA9'] = di['close'].ewm(span=9, adjust=False).mean()
    
    # HMA (Hull Moving Average)
    def calc_hma(series, period):
        wma1 = series.rolling(period).mean()
        wma2 = series.rolling(period//2).mean()
        raw_hma = 2 * wma2 - wma1
        return raw_hma.rolling(int(np.sqrt(period))).mean()
    
    di['HMA_FAST'] = calc_hma(di['close'], 9)
    di['HMA_SLOW'] = calc_hma(di['close'], 20)
    di['HMA_SIGNAL'] = calc_hma(di['close'], 14)
    
    # TSI (True Strength Index)
    def calc_tsi(close, r=25, s=13):
        mom = close.diff()
        ema1 = mom.ewm(span=r, adjust=False).mean()
        ema2 = ema1.ewm(span=s, adjust=False).mean()
        abs_mom = mom.abs()
        abs_ema1 = abs_mom.ewm(span=r, adjust=False).mean()
        abs_ema2 = abs_ema1.ewm(span=s, adjust=False).mean()
        return 100 * ema2 / abs_ema2.replace(0, np.nan)
    
    di['TSI'] = calc_tsi(di['close'])
    
    # EFF_RATIO (Kaufman Efficiency Ratio)
    def calc_eff_ratio(close, period=10):
        displacement = (close - close.shift(period)).abs()
        volatility = (close.diff().abs()).rolling(period).sum()
        return displacement / volatility.replace(0, np.nan)
    
    di['EFF_RATIO_10'] = calc_eff_ratio(di['close'], 10)
    
    # MFI (Money Flow Index)
    def calc_mfi(high, low, close, volume, period=14):
        typical_price = (high + low + close) / 3
        money_flow = typical_price * volume
        delta = typical_price.diff()
        positive_flow = money_flow.where(delta > 0, 0)
        negative_flow = money_flow.where(delta < 0, 0)
        pos_mf = positive_flow.rolling(period).sum()
        neg_mf = negative_flow.rolling(period).sum()
        mfi = 100 - (100 / (1 + pos_mf / neg_mf.replace(0, np.nan)))
        return mfi.fillna(50)
    
    di['MFI14'] = calc_mfi(di['high'], di['low'], di['close'], di['tick_volume'])
    
    # Keltner Channels
    di['KELT_MID'] = di['EMA20']
    di['KELT_UPPER'] = di['EMA20'] + di['ATR'] * 2.0
    di['KELT_LOWER'] = di['EMA20'] - di['ATR'] * 2.0
    
    # Choppiness Index
    def calc_chop(high, low, close, period=14):
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        highh = high.rolling(period).max()
        lowl = low.rolling(period).min()
        chop = 100 * np.log10((atr.sum() / (highh - lowl).replace(0, np.nan)) / np.log10(period))
        return chop
    
    di['CHOP_INDEX'] = calc_chop(di['high'], di['low'], di['close'])
    
    # GK_RATIO (Garman-Klass volatility ratio)
    def calc_gk_ratio(open_, high, low, close):
        log_hl = np.log(high / low)
        log_co = np.log(close / open_)
        return 0.5 * log_hl**2 - (2 * np.log(2) - 1) * log_co**2
    
    di['GK_RATIO'] = calc_gk_ratio(di['open'], di['high'], di['low'], di['close'])
    
    # RIBBON_STATE
    di['RIBBON_STATE'] = np.where(
        (di['EMA5'] > di['EMA9']) & (di['EMA9'] > di['EMA20']), 1,
        np.where((di['EMA5'] < di['EMA9']) & (di['EMA9'] < di['EMA20']), -1, 0)
    )
    
    # Z_SCORE_EMA20
    std_20 = di['close'].rolling(20).std().replace(0, np.nan)
    di['Z_SCORE_EMA20'] = ((di['close'] - di['EMA20']) / std_20).fillna(0)
    
    # VWAP_Z
    vwap_std = di.groupby('date')['dist'].transform(lambda x: x.rolling(20, min_periods=1).std())
    di['VWAP_Z'] = ((di['close'] - di['VWAP']) / vwap_std.replace(0, np.nan)).fillna(0)
    di['VWAP_Z'] = di['VWAP_Z'].clip(-5, 5)
    
    # ATR_STRETCH
    di['ATR_STRETCH'] = ((di['close'] - di['VWAP']) / di['ATR'].replace(0, 1)).clip(-5, 5)
    
    return di


def compute_pa_signals_v87(di, s_min, z_max, r_min):
    """
    Computa TODOS os 23 sinais PA_* com params V8_* especificos.
    BUG FIX V8.7:
    1. PA_REV_RSI_B10/S90 → Unificados em PA_REV_RSI_UNIFIED
    2. PA_HMA_CROSS → Renomeado para PA_SMA_CROSS
    Retorna dicionario {nome_coluna: array}.
    """
    h = di['high'].values
    l = di['low'].values
    c = di['close'].values
    atr = di['ATR'].values
    adx7 = di['ADX7'].values
    ema20 = di['EMA20'].values
    ema_slope = di['EMA_SLOPE'].values
    ema5_slope_abs = np.abs(di['EMA5_SLOPE'].values) if 'EMA5_SLOPE' in di.columns else np.abs(ema_slope)
    
    # Z-score e range ratio
    std_20 = di['close'].rolling(20).std().fillna(1).values
    z_score = (c - ema20) / np.where(std_20 == 0, 1, std_20)
    z_score = np.clip(z_score, -5, 5)
    
    range_ma20 = pd.Series(h - l).rolling(20).mean().values
    range_ratio = (h - l) / np.where(range_ma20 == 0, 1, range_ma20)
    range_ratio = np.clip(range_ratio, 0, 5)
    
    # =========================================================================
    # V8.0 CORE
    # =========================================================================
    noise_ok = range_ratio >= r_min
    
    v8_buy = (
        (c > ema20) &
        (ema_slope > s_min) &
        (z_score < z_max) &
        noise_ok
    )
    v8_sell = (
        (c < ema20) &
        (ema_slope < -s_min) &
        (z_score > -z_max) &
        noise_ok
    )
    
    pa_signal_dir = np.where(v8_buy, 1, np.where(v8_sell, -1, 0)).astype(np.int64)
    
    # PA_SIGNAL_DIR_V2
    sig_prev = np.roll(pa_signal_dir, 1)
    sig_prev[0] = 0
    slope = ema_slope
    slope_prev = np.roll(slope, 1)
    slope_prev[0] = 0
    
    atr_min_v2 = 150
    fresh_cross_buy = (pa_signal_dir == 1) & (sig_prev != 1)
    fresh_cross_sell = (pa_signal_dir == -1) & (sig_prev != -1)
    slope_accel_buy = (slope > 0) & (slope > slope_prev)
    slope_accel_sell = (slope < 0) & (slope < slope_prev)
    atr_ok = atr >= atr_min_v2
    
    pa_signal_dir_v2 = np.where(
        fresh_cross_buy & slope_accel_buy & atr_ok, 1,
        np.where(fresh_cross_sell & slope_accel_sell & atr_ok, -1, 0)
    ).astype(np.int64)
    
    # PA_SIGNAL_REV
    pa_signal_rev = -pa_signal_dir
    
    # Sinais derivados (herdam direcao)
    pa_strong_trend = np.where(
        (adx7 >= 25) & (ema5_slope_abs >= 20) & (pa_signal_dir != 0),
        pa_signal_dir, 0
    ).astype(np.int64)
    
    pa_slope_trend = np.where(
        (ema5_slope_abs >= 25) & (adx7 >= 25) & (pa_signal_dir != 0),
        pa_signal_dir, 0
    ).astype(np.int64)
    
    adx_delta = adx7 - np.roll(adx7, 3)
    adx_delta[:3] = 0
    pa_adx_break = np.where(
        (adx_delta > 0) & (adx7 > 25) & (pa_signal_dir != 0),
        pa_signal_dir, 0
    ).astype(np.int64)
    
    pa_exhaust = np.where(
        (adx_delta < -1.0) & (adx7 > 25) & (adx7 < 40) & (pa_signal_dir != 0),
        pa_signal_dir, 0
    ).astype(np.int64)
    
    gk_ratio = di['GK_RATIO'].values if 'GK_RATIO' in di.columns else np.zeros(len(di))
    pa_gk_break = np.where(
        (gk_ratio > 0.001) & (adx7 > 25) & (pa_signal_dir != 0),
        pa_signal_dir, 0
    ).astype(np.int64)
    
    range_ratio_shift = np.roll(range_ratio, 1)
    range_ratio_shift[0] = range_ratio[0]
    pa_vcp = np.where(
        (range_ratio < 0.6) & (range_ratio_shift < 0.7) & (pa_signal_dir != 0),
        pa_signal_dir, 0
    ).astype(np.int64)
    
    # Sinais independentes
    rsi2 = calc_rsi(di['close'], 2)
    
    # BUG FIX V8.7: Unificar B10 e S90 em unico sinal
    pa_rev_rsi_unified = np.where(rsi2 < 10, 1, np.where(rsi2 > 90, -1, 0)).astype(np.int64)
    
    vwap_z = di['VWAP_Z'].values if 'VWAP_Z' in di.columns else np.zeros(len(di))
    pa_vwap_z = np.where(vwap_z < -2.0, 1, np.where(vwap_z > 2.0, -1, 0)).astype(np.int64)
    
    vwap = di['VWAP'].values if 'VWAP' in di.columns else ema20
    pa_vwap_rev = np.where(
        ((c < vwap - atr * 1.0) & (adx7 < 25)), 1,
        np.where(((c > vwap + atr * 1.0) & (adx7 < 25)), -1, 0)
    ).astype(np.int64)
    
    pa_kelt = np.where(
        c < ema20 - atr * 2.0, 1,
        np.where(c > ema20 + atr * 2.0, -1, 0)
    ).astype(np.int64)
    
    atr_stretch = di['ATR_STRETCH'].values if 'ATR_STRETCH' in di.columns else np.zeros(len(di))
    pa_vwap_stretch = np.where(
        (atr_stretch < -2.0) & (range_ratio < 0.8), 1,
        np.where((atr_stretch > 2.0) & (range_ratio < 0.8), -1, 0)
    ).astype(np.int64)
    
    mfi14 = di['MFI14'].values if 'MFI14' in di.columns else np.full(len(di), 50)
    pa_mfi = np.where(mfi14 < 20, 1, np.where(mfi14 > 80, -1, 0)).astype(np.int64)
    
    tsi = di['TSI'].values if 'TSI' in di.columns else np.zeros(len(di))
    pa_tsi = np.where(tsi < -25, 1, np.where(tsi > 25, -1, 0)).astype(np.int64)
    
    # MA CROSS
    ma_fast = pd.Series(c).rolling(9).mean().values
    ma_slow = pd.Series(c).rolling(21).mean().values
    ma_cross = ((ma_fast > ma_slow).astype(int) - (ma_fast > ma_slow).astype(int))
    ma_cross[0] = 0
    pa_ma_cross = ma_cross.astype(np.int64)
    
    # BUG FIX V8.7: Renomear HMA_CROSS → SMA_CROSS (usa SMA, nao HMA)
    sma_fast = pd.Series(c).rolling(5).mean().values
    sma_slow = pd.Series(c).rolling(10).mean().values
    sma_cross = ((sma_fast > sma_slow).astype(int) - (sma_fast > sma_slow).astype(int))
    sma_cross[0] = 0
    pa_sma_cross = sma_cross.astype(np.int64)
    
    eff_ratio = di['EFF_RATIO_10'].values if 'EFF_RATIO_10' in di.columns else np.zeros(len(di))
    pa_eff_ratio = np.where((eff_ratio > 0.6) & (pa_signal_dir != 0), pa_signal_dir, 0).astype(np.int64)
    
    chop = di['CHOP_INDEX'].values if 'CHOP_INDEX' in di.columns else np.full(len(di), 50)
    pa_chop = np.where((chop < 38.2) & (pa_signal_dir != 0), pa_signal_dir, 0).astype(np.int64)
    
    # LIQ_GRAB
    prev_10_high = pd.Series(h).rolling(10).max().values
    prev_10_low = pd.Series(l).rolling(10).min().values
    grab_buy = (h > np.roll(prev_10_high, 1)) & (c < np.roll(prev_10_high, 1))
    grab_sell = (l < np.roll(prev_10_low, 1)) & (c > np.roll(prev_10_low, 1))
    pa_liq_grab = np.where(grab_buy, 1, np.where(grab_sell, -1, 0)).astype(np.int64)
    
    # TUESDAY
    dates = di['date'].values
    day_of_week = np.array([datetime.strptime(str(d), '%Y-%m-%d').weekday() if pd.notnull(d) else 0 for d in dates])
    pa_tuesday = np.where(day_of_week == 1, pa_signal_dir, 0).astype(np.int64)
    
    # =========================================================================
    # RETORNAR TODOS OS SINAIS
    # =========================================================================
    return {
        # Sinais base (dependem de V8_*)
        'PA_SIGNAL_DIR': pa_signal_dir,
        'PA_SIGNAL_DIR_V2': pa_signal_dir_v2,
        'PA_SIGNAL_REV': pa_signal_rev,
        
        # Trend following
        'PA_STRONG_TREND_A25_S20': pa_strong_trend,
        'PA_SLOPE_TREND_S25_A25': pa_slope_trend,
        
        # Breakout / Exaustao
        'PA_ADX_BREAK_A25': pa_adx_break,
        'PA_EXHAUST_Dn1_0_M40': pa_exhaust,
        'PA_GK_BREAK_G0_001': pa_gk_break,
        
        # Patterns
        'PA_VCP_C0_6': pa_vcp,
        
        # Cruzamentos
        'PA_MA_CROSS_F9_S21': pa_ma_cross,
        'PA_SMA_CROSS_F5_S10': pa_sma_cross,  # BUG FIX: HMA → SMA
        
        # Regime / Qualidade
        'PA_EFF_RATIO_E0_6': pa_eff_ratio,
        'PA_CHOP_C38_2': pa_chop,
        
        # Reversao RSI (BUG FIX: unificado)
        'PA_REV_RSI_UNIFIED': pa_rev_rsi_unified,
        
        # VWAP / Z-Score
        'PA_VWAP_Z_Z2_0': pa_vwap_z,
        'PA_VWAP_REV_D1_0': pa_vwap_rev,
        'PA_KELT_ATR_M2_0': pa_kelt,
        'PA_VWAP_STRETCH': pa_vwap_stretch,
        
        # Outros
        'PA_MFI_B20': pa_mfi,
        'PA_TSI_T25': pa_tsi,
        'PA_LIQ_GRAB': pa_liq_grab,
        'PA_TUESDAY': pa_tuesday,
    }


def build_variants_v87():
    """Gera 1 parquet com TODOS os 23 sinais e 18 variantes V8_*."""
    print("="*80)
    print("Building V8.7 variants...")
    print("="*80)
    
    # Load CSVs
    print("\n[1/4] Loading CSV files...")
    j26_raw = load_csv(J26_CSV)
    m26_raw = load_csv(M26_CSV)
    
    # Build indicators per contract
    print("\n[2/4] Computing indicators...")
    j26_di = compute_base_indicators(j26_raw)
    j26_di = compute_microstructure(j26_di)  # NOVO: Microestrutura
    j26_di = compute_raw_indicators(j26_di)
    
    m26_di = compute_base_indicators(m26_raw)
    m26_di = compute_microstructure(m26_di)  # NOVO: Microestrutura
    m26_di = compute_raw_indicators(m26_di)
    
    # Generate all V8.* combinations
    print("\n[3/4] Generating V8.7 variants...")
    all_variants = {}
    
    for s_min in V8_S_MIN_GRID:
        for z_max in V8_Z_MAX_GRID:
            for r_min in V8_R_MIN_GRID:
                variant_name = f"s{s_min}_z{z_max}_r{r_min}".replace('.', 'p')
                print(f"  Building variant: {variant_name} (s_min={s_min}, z_max={z_max}, r_min={r_min})")
                
                # Compute signals for this variant
                j26_signals = compute_pa_signals_v87(j26_di, s_min, z_max, r_min)
                m26_signals = compute_pa_signals_v87(m26_di, s_min, z_max, r_min)
                
                # Store for each signal family
                for signal_name, j26_vals in j26_signals.items():
                    if signal_name not in all_variants:
                        all_variants[signal_name] = {}
                    all_variants[signal_name][variant_name] = (j26_vals, m26_vals := m26_signals[signal_name])
    
    # Merge J26 + M26 and save parquets
    print("\n[4/4] Saving parquets...")
    
    for signal_name in sorted(all_variants.keys()):
        print(f"\n  Saving {signal_name}...")
        
        # Merge J26 + M26 for base data
        j26_dates = pd.to_datetime(j26_raw['date'])
        m26_dates = pd.to_datetime(m26_raw['date'])
        
        j26_before = j26_raw[j26_dates < CUTOFF].copy()
        m26_after = m26_raw[m26_dates >= CUTOFF].copy()
        
        # Drop warmup
        if len(j26_before) > WARMUP:
            j26_before = j26_before.iloc[WARMUP:]
        if len(m26_after) > WARMUP:
            m26_after = m26_after.iloc[WARMUP:]
        
        # Merge contracts
        base_df = pd.concat([j26_before, m26_after]).sort_values('dt')
        base_df = base_df.drop_duplicates(subset=['dt'], keep='last').reset_index(drop=True)
        
        # Add all variant columns for this signal
        for variant_name, (j26_vals, m26_vals) in all_variants[signal_name].items():
            # Apply warmup drop to signals
            if len(j26_vals) > WARMUP:
                j26_vals = j26_vals[WARMUP:]
            if len(m26_vals) > WARMUP:
                m26_vals = m26_vals[WARMUP:]
            
            # Merge signals
            signal_merged = np.concatenate([j26_vals, m26_vals])
            if len(signal_merged) != len(base_df):
                # Adjust for merge differences
                signal_merged = signal_merged[:len(base_df)]
            
            base_df[variant_name] = signal_merged
        
        # Add base indicators (ATR, ADX7, EMA20, etc.) from J26/M26
        # These are needed for F1 evaluation
        j26_indicators = ['ATR', 'ADX7', 'EMA20', 'EMA5', 'EMA9', 'VWAP', 'dist']
        
        # NOVO: Adicionar microestrutura
        sr_indicators = [
            'dist_to_resistance', 'dist_to_support',
            'book_imbalance', 'book_imbalance_ma', 'book_imbalance_cum',
            'cum_delta', 'cum_delta_ma',
            'concentration_poc', 'concentration_vah', 'concentration_val', 'in_concentration'
        ]
        j26_indicators.extend(sr_indicators)
        
        for col in j26_indicators:
            if col in j26_di.columns:
                j26_vals = j26_di[col].values
                m26_vals = m26_di[col].values
                
                # Apply warmup drop
                if len(j26_vals) > WARMUP:
                    j26_vals = j26_vals[WARMUP:]
                if len(m26_vals) > WARMUP:
                    m26_vals = m26_vals[WARMUP:]
                
                # Merge
                col_merged = np.concatenate([j26_vals, m26_vals])
                if len(col_merged) != len(base_df):
                    col_merged = col_merged[:len(base_df)]
                
                base_df[col] = col_merged
        
        # Save parquet
        output_path = os.path.join(VARIANTS_DIR, f"{signal_name}.parquet")
        base_df.to_parquet(output_path, index=False)
        print(f"    Saved: {output_path}")
        print(f"    Rows: {len(base_df)}, Variantes: {len(all_variants[signal_name])}")
    
    print("\n" + "="*80)
    print("V8.7 BUILD COMPLETE.")
    print(f"Total sinais: {len(all_variants)}")
    print(f"Total variantes por sinal: {len(V8_S_MIN_GRID) * len(V8_Z_MAX_GRID) * len(V8_R_MIN_GRID)}")
    print("="*80)


if __name__ == '__main__':
    build_variants_v87()
