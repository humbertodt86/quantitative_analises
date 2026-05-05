"""
F1 Fast Screener Vetorizado v2 — Usando OHLC (sem samples)
===========================================================
Versao vetorizada que usa high/low reais em vez de samples.
Elimina erro de amostragem e eh mais rapida (sem build_M).
"""
import sys, os, time
import numpy as np
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import polars as pl

BASE = os.path.join(ROOT, 'data')
SUPER = os.path.join(BASE, 'super_win_continuous.parquet')
SINAL = 'PA_SIGNAL_DIR'
COST = 30

def evaluate_ohlc(high, low, close, atr, signal, direction, tp, sl, hm=9, hx=12, atr_min=200):
    """
    F1 vetorizado usando OHLC (sem samples, sem ticks).
    Mais rapido e mais preciso que amostragem.
    """
    n_rows = len(close)
    
    # Mascara de sinal + ATR
    if direction == 1:
        sig_mask = signal == 1
    else:
        sig_mask = signal == -1
    
    valid = sig_mask & (atr >= atr_min) & (atr <= 800) & ~np.isnan(atr)
    
    # Entry prices
    entries = close[valid]
    atrs = atr[valid]
    indices = np.where(valid)[0]
    
    n_entries = len(entries)
    if n_entries == 0:
        return 0, 0
    
    # Calcular TP/SL para todas as entradas
    if direction == 1:
        tp_prices = entries + tp * atrs
        sl_prices = entries - sl * atrs
    else:
        tp_prices = entries - tp * atrs
        sl_prices = entries + sl * atrs
    
    # Para cada entrada, verificar se TP ou SL eh atingido nas proximas candles
    # Vamos fazer um loop simplificado (pode ser otimizado com numpy strides)
    pnls = []
    skip_until = -1
    
    for i in range(n_entries):
        idx = indices[i]
        
        if idx <= skip_until:
            continue
        
        entry = entries[i]
        tp_price = tp_prices[i]
        sl_price = sl_prices[i]
        atr_i = atrs[i]
        
        first_tp = -1
        first_sl = -1
        
        for la in range(1, min(50, n_rows - idx)):
            future_idx = idx + la
            if future_idx >= n_rows:
                break
            
            if direction == 1:
                if first_tp == -1 and high[future_idx] >= tp_price:
                    first_tp = la
                if first_sl == -1 and low[future_idx] <= sl_price:
                    first_sl = la
            else:
                if first_tp == -1 and low[future_idx] <= tp_price:
                    first_tp = la
                if first_sl == -1 and high[future_idx] >= sl_price:
                    first_sl = la
            
            if first_tp != -1 and first_sl != -1:
                break
        
        if first_tp == -1 and first_sl == -1:
            pnl = -COST
            exit_la = 50
        elif first_tp >= 0 and first_sl == -1:
            pnl = tp * atr_i - COST
            exit_la = first_tp
        elif first_sl >= 0 and first_tp == -1:
            pnl = -sl * atr_i - COST
            exit_la = first_sl
        else:
            if first_tp < first_sl:
                pnl = tp * atr_i - COST
                exit_la = first_tp
            else:
                pnl = -sl * atr_i - COST
                exit_la = first_sl
        
        pnls.append(pnl)
        skip_until = idx + exit_la + 1
    
    total_pnl = sum(pnls)
    n_trades = len(pnls)
    return int(total_pnl), n_trades


print("="*80)
print("F1 FAST SCREENER v2 — OHLC (sem samples, sem ticks)")
print("="*80)

# 1. Carregar dados
df = pl.read_parquet(SUPER).filter((pl.col('dt') >= datetime(2026,2,1)) & (pl.col('dt') < datetime(2026,3,1))).to_pandas()
df['dt'] = pd.to_datetime(df['dt'])
N = len(df)

close = df['close'].to_numpy()
high = df['high'].to_numpy()
low = df['low'].to_numpy()
atr = df['ATR'].to_numpy()
signal = df[SINAL].to_numpy()

print(f"1. Dados: {N} candles")

# 2. Grid
TP_GRID = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 15.0, 20.0]
SL_GRID = [0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0]
ATR_MIN_GRID = [50, 100, 150, 200, 300, 400]
ATR_MAX_GRID = [400, 600, 800, 1000, 1500, 2000, 9999]

total = len(TP_GRID) * len(SL_GRID) * len(ATR_MIN_GRID) * len(ATR_MAX_GRID)
print(f"2. Grid: {total} combos")

# 3. Executar
t0 = time.time()
results = []
for tp in TP_GRID:
    for sl in SL_GRID:
        for atr_min in ATR_MIN_GRID:
            for atr_max in ATR_MAX_GRID:
                # Usar atr_max como filtro (simulado)
                atr_filtered = atr.copy()
                atr_filtered[atr > atr_max] = np.nan
                net, n = evaluate_ohlc(high, low, close, atr_filtered, signal, 1, tp, sl, hm=0, hx=24, atr_min=atr_min)
                if n >= 3:
                    results.append((tp, sl, atr_min, atr_max, net, n))

dt = time.time() - t0
speed = total / dt

print(f"\n3. Resultado:")
print(f"   Tempo: {dt:.2f}s")
print(f"   Velocidade: {speed:.0f} combos/s")
print(f"   Resultados validos: {len(results)}")

# Top 10
results.sort(key=lambda x: x[4], reverse=True)
print(f"\n   Top 10:")
for i, (tp, sl, amin, amax, net, n) in enumerate(results[:10]):
    print(f"   {i+1:2}. TP={tp:.1f} SL={sl:.1f} ATR=[{amin:.0f}-{amax:.0f}] PnL={net:+10.0f} N={n:3}")

print("\n" + "="*80)
print("F1 v2 COMPLETE")
print("="*80)
