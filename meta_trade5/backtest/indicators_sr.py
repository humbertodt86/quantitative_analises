"""
INDICADORES SR — SUPORTE/RESISTÊNCIA, BOOK IMBALANCE, TAPE READING
===================================================================
Calcula indicadores de microestrutura para F2 optimization.

Indicadores:
1. S/R Levels (intraday + sessões anteriores)
2. Book Imbalance (bid vs ask volume)
3. Cumulative Delta (tape reading)
4. Concentration Zones (POC, Value Area)
"""
import pandas as pd
import numpy as np
from typing import Tuple, List


def calc_sr_levels(df: pd.DataFrame, lookback_days: int = 5) -> pd.DataFrame:
    """
    Calcula Suporte e Resistência intraday + sessões anteriores.
    
    S/R Levels:
    - Intraday: High/Low das últimas N candles (20-50)
    - Sessões anteriores: High/Low de dias anteriores
    - POC (Point of Control): Preço com maior volume
    
    Args:
        df: DataFrame com OHLCV + volume
        lookback_days: Dias para buscar S/R (padrão: 5)
    
    Returns:
        df: DataFrame com colunas adicionais:
            - sr_resistance_intraday: Resistência intraday
            - sr_support_intraday: Suporte intraday
            - sr_resistance_daily: Resistência de sessões
            - sr_support_daily: Suporte de sessões
            - sr_poc: Point of Control
            - dist_to_resistance: Distância até resistência (pts)
            - dist_to_support: Distância até suporte (pts)
    """
    df = df.copy()
    
    # Intraday S/R (últimas 50 candles)
    df['sr_resistance_intraday'] = df['high'].rolling(50, min_periods=20).max()
    df['sr_support_intraday'] = df['low'].rolling(50, min_periods=20).min()
    
    # Daily S/R (sessões anteriores)
    # Agrupar por dia e pegar high/low
    df['date'] = pd.to_datetime(df['dt']).dt.date
    daily_high = df.groupby('date')['high'].max()
    daily_low = df.groupby('date')['low'].min()
    
    # Rolling high/low dos últimos N dias
    df['sr_resistance_daily'] = np.nan
    df['sr_support_daily'] = np.nan
    
    for i in range(len(df)):
        if i < 50:  # Warmup
            continue
        
        current_date = df.iloc[i]['date']
        prev_dates = df.iloc[:i]['date'].unique()
        prev_dates = prev_dates[prev_dates < current_date][-lookback_days:]
        
        if len(prev_dates) > 0:
            df.iloc[i, df.columns.get_loc('sr_resistance_daily')] = daily_high[prev_dates].max()
            df.iloc[i, df.columns.get_loc('sr_support_daily')] = daily_low[prev_dates].min()
    
    # POC (Point of Control) — preço com maior volume nas últimas 100 candles
    def calc_poc(group):
        # Simplificado: preço médio da candle com maior volume
        max_vol_idx = group['volume'].idxmax()
        return group.loc[max_vol_idx, 'close']
    
    df['sr_poc'] = df['close'].rolling(100, min_periods=50).apply(
        lambda x: df.loc[x.index[-1], 'close'] if len(x) > 0 else np.nan
    )
    
    # Distância até S/R
    df['dist_to_resistance'] = df['sr_resistance_intraday'] - df['close']
    df['dist_to_support'] = df['close'] - df['sr_support_intraday']
    
    # Limpeza (NÃO remover 'date' — pode ser necessário)
    # df = df.drop(columns=['date'], errors='ignore')
    
    return df


def calc_book_imbalance(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """
    Calcula Book Imbalance (pressão de compra vs venda).
    
    Fórmula:
    book_imbalance = (buy_volume - sell_volume) / (buy_volume + sell_volume)
    
    Onde:
    - buy_volume: volume em candles de alta (close > open)
    - sell_volume: volume em candles de baixa (close < open)
    
    Args:
        df: DataFrame com OHLCV
        period: Período para média móvel (padrão: 20)
    
    Returns:
        df: DataFrame com colunas adicionais:
            - book_imbalance: Imbalance bruto (-1 a +1)
            - book_imbalance_ma: Média móvel do imbalance
            - book_imbalance_cum: Cumulative imbalance
    """
    df = df.copy()
    
    # Volume de compra (candles de alta)
    buy_volume = np.where(df['close'] > df['open'], df['volume'], 0)
    
    # Volume de venda (candles de baixa)
    sell_volume = np.where(df['close'] < df['open'], df['volume'], 0)
    
    # Book imbalance bruto
    total_volume = buy_volume + sell_volume
    total_volume = np.where(total_volume == 0, 1, total_volume)  # Evitar divisão por zero
    
    df['book_imbalance'] = (buy_volume - sell_volume) / total_volume
    
    # Média móvel do imbalance
    df['book_imbalance_ma'] = df['book_imbalance'].rolling(period).mean()
    
    # Cumulative imbalance
    df['book_imbalance_cum'] = df['book_imbalance'].cumsum()
    
    return df


def calc_cumulative_delta(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula Cumulative Delta (tape reading).
    
    Delta = direção do tick (compra=+1, venda=-1)
    Cumulative Delta = soma acumulada do delta
    
    Como não temos tick data, usamos proxy:
    - Delta = +1 se close > open (candle de alta)
    - Delta = -1 se close < open (candle de baixa)
    - Delta = 0 se close == open
    
    Args:
        df: DataFrame com OHLC
    
    Returns:
        df: DataFrame com colunas adicionais:
            - tick_delta: Delta por candle (+1/-1/0)
            - cum_delta: Cumulative delta
            - cum_delta_ma: Média móvel do cum_delta (20 períodos)
    """
    df = df.copy()
    
    # Delta por candle
    df['tick_delta'] = np.sign(df['close'] - df['open'])
    
    # Cumulative delta
    df['cum_delta'] = df['tick_delta'].cumsum()
    
    # Média móvel (para detectar divergência)
    df['cum_delta_ma'] = df['cum_delta'].rolling(20).mean()
    
    # Divergência (preço sobe, delta desce = bearish)
    df['price_change'] = df['close'].diff(20)
    df['delta_change'] = df['cum_delta'].diff(20)
    df['divergence'] = np.sign(df['price_change']) != np.sign(df['delta_change'])
    
    return df


def calc_concentration_zones(df: pd.DataFrame, period: int = 100) -> pd.DataFrame:
    """
    Calcula Concentration Zones (áreas de alta concentração de volume).
    
    Zonas de concentração:
    - POC (Point of Control): Preço com maior volume
    - Value Area High: Preço onde acumula 70% do volume (acima do POC)
    - Value Area Low: Preço onde acumula 70% do volume (abaixo do POC)
    
    Args:
        df: DataFrame com OHLCV
        period: Período para cálculo (padrão: 100 candles)
    
    Returns:
        df: DataFrame com colunas adicionais:
            - concentration_poc: Point of Control
            - concentration_vah: Value Area High
            - concentration_val: Value Area Low
            - in_concentration: 1 se preço está na zona de concentração
    """
    df = df.copy()
    
    # Inicializar colunas
    df['concentration_poc'] = np.nan
    df['concentration_vah'] = np.nan
    df['concentration_val'] = np.nan
    df['in_concentration'] = 0
    
    # Calcular para cada janela rolling
    for i in range(period, len(df)):
        window = df.iloc[i-period:i]
        
        # POC: preço médio da candle com maior volume
        max_vol_idx = window['volume'].idxmax()
        poc = window.loc[max_vol_idx, 'close']
        
        # Value Area: 70% do volume total
        total_vol = window['volume'].sum()
        target_vol = total_vol * 0.70
        
        # Ordenar candles por distância do POC
        window = window.copy()
        window['dist_from_poc'] = np.abs(window['close'] - poc)
        window = window.sort_values('dist_from_poc')
        
        # Acumular volume até atingir 70%
        cum_vol = 0
        vah = poc
        val = poc
        
        for _, row in window.iterrows():
            cum_vol += row['volume']
            if row['close'] > poc:
                vah = row['high']
            else:
                val = row['low']
            
            if cum_vol >= target_vol:
                break
        
        df.iloc[i, df.columns.get_loc('concentration_poc')] = poc
        df.iloc[i, df.columns.get_loc('concentration_vah')] = vah
        df.iloc[i, df.columns.get_loc('concentration_val')] = val
        
        # Preço está na zona de concentração?
        current_price = df.iloc[i]['close']
        df.iloc[i, df.columns.get_loc('in_concentration')] = 1 if val <= current_price <= vah else 0
    
    return df


def add_microstructure_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adiciona TODOS os indicadores de microestrutura de uma vez.
    
    Args:
        df: DataFrame com OHLCV
    
    Returns:
        df: DataFrame com todos os indicadores de microestrutura
    """
    print("  Calculando S/R levels...")
    df = calc_sr_levels(df)
    
    print("  Calculando Book Imbalance...")
    df = calc_book_imbalance(df)
    
    print("  Calculando Cumulative Delta...")
    df = calc_cumulative_delta(df)
    
    print("  Calculando Concentration Zones...")
    df = calc_concentration_zones(df)
    
    # Colunas adicionadas
    new_cols = [
        'sr_resistance_intraday', 'sr_support_intraday',
        'sr_resistance_daily', 'sr_support_daily', 'sr_poc',
        'dist_to_resistance', 'dist_to_support',
        'book_imbalance', 'book_imbalance_ma', 'book_imbalance_cum',
        'tick_delta', 'cum_delta', 'cum_delta_ma', 'divergence',
        'concentration_poc', 'concentration_vah', 'concentration_val', 'in_concentration'
    ]
    
    print(f"  Adicionadas {len(new_cols)} colunas de microestrutura")
    
    return df


if __name__ == '__main__':
    # Teste rápido
    import os
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Carregar dados de teste
    parquet_path = os.path.join(ROOT, 'data', 'super_win_continuous_v81.parquet')
    if os.path.exists(parquet_path):
        df = pd.read_parquet(parquet_path, nrows=1000)
        df = add_microstructure_indicators(df)
        print("\nColunas adicionadas:")
        for col in df.columns:
            if col.startswith('sr_') or col.startswith('book_') or col.startswith('cum_') or col.startswith('concentration_'):
                print(f"  - {col}")
    else:
        print(f"Arquivo não encontrado: {parquet_path}")
