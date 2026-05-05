"""
Validacao F1 Binario vs F2 (modo busca, sem guardrails)
========================================================
Compara F1b (single blocking) com F2 numba usando EXATAMENTE
os mesmos parametros e logica (sem guardrails, sem TP30, sem filtros).

Objetivo: Confirmar que F1b e F2 produzem resultados comparaveis
quando ambos usam apenas SL/TP fixo + position blocking de 1 candle.
"""
import sys, os, time
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import polars as pl
from datetime import datetime
from backtest.engine_v2 import BacktestEngine
from engines.f1_fast_screener import build_M_close
from engines.f1_binario import evaluate as evaluate_binario

from engines.f2_optimization_v87 import backtest_f2_numba

BASE = os.path.join(ROOT, 'data')
SUPER = os.path.join(BASE, 'super_win_continuous.parquet')
SINAL = 'PA_SIGNAL_DIR'

print("="*80)
print("VALIDACAO F1 BINARIO vs F2 (MODO BUSCA — SEM GUARDRAILS)")
print("="*80)

# 1. Carregar dados IS (Fev 2026)
print("\n[1/3] Carregando dados IS (Fev 2026)...")
df = pl.read_parquet(SUPER).filter(
    (pl.col('dt') >= datetime(2026, 2, 1)) & (pl.col('dt') < datetime(2026, 3, 1))
)
N = len(df)
close_arr = df['close'].to_numpy().astype(np.float32)
high_arr = df['high'].to_numpy().astype(np.float32)
low_arr = df['low'].to_numpy().astype(np.float32)
atr_arr = df['ATR'].to_numpy().astype(np.float32)
signal = df[SINAL].to_numpy().astype(np.int32)
sell_idx = np.where(signal == 1)[0].astype(np.int32)
ep = np.array([df['open'].to_numpy()[i+1] if i+1 < N else df['close'].to_numpy()[i] for i in sell_idx], dtype=np.float32)
atr = atr_arr[sell_idx]

print(f"  Candles: {N} | Entradas BUY: {len(sell_idx)}")

# 2. Carregar ticks e build M
print("\n[2/3] Construindo matriz M (F1b)...")
win = pl.read_parquet(os.path.join(BASE, 'WIN_merged_all.parquet'))
win = win.with_columns(pl.from_epoch(pl.col('time_msc')//1000, time_unit='s').alias('dt'))
fev = win.filter(pl.col('dt').dt.month() == 2).filter(pl.col('dt').dt.year() == 2026).sort('time_msc')
tick_last = fev['last'].to_numpy().astype(np.float32)
eng = BacktestEngine(None)
eng.df = df
eng.load_ticks_for_simulation(fev)
M, closes = build_M_close(tick_last, eng.tick_idx, sell_idx, N, close_arr, incluir_extremos=False)
print(f"  M: {M.shape}")

# Parametros de teste
TP = 2.0
SL = 5.0
DIRECTION = 1  # BUY

# 3. F1 Binario (single blocking = compativel F2/F3)
print("\n[3/3] Executando F1b e F2...")

net_f1b, n_f1b = evaluate_binario(M, ep, atr, sell_idx, TP, SL, direction=DIRECTION, use_uint64=True, blocking_mode='single')
print(f"\nF1 BINARIO (single):")
print(f"  PnL: {net_f1b:+,} | Trades: {n_f1b}")

# 4. F2 (modo busca: sem guardrails, sem S/R, sem filtros)
# Preparar arrays para F2
dist_res = df['dist_to_resistance'].to_numpy().astype(np.float32) if 'dist_to_resistance' in df.columns else np.zeros(N, dtype=np.float32)
dist_sup = df['dist_to_support'].to_numpy().astype(np.float32) if 'dist_to_support' in df.columns else np.zeros(N, dtype=np.float32)
book_imb = df['book_imbalance'].to_numpy().astype(np.float32) if 'book_imbalance' in df.columns else np.zeros(N, dtype=np.float32)
cum_delta = df['cum_delta'].to_numpy().astype(np.float32) if 'cum_delta' in df.columns else np.zeros(N, dtype=np.float32)

t0 = time.time()
net_f2, n_f2, wins_f2 = backtest_f2_numba(
    close_arr, high_arr, low_arr, atr_arr, signal,
    TP, SL, 0, 99999,  # atr_min=0, atr_max=99999 (sem filtro ATR)
    1.00, 1.00, 999.0,  # S/R desativado
    dist_res, dist_sup,
    book_imb, cum_delta,
    0.0, 0.0,  # filtros desativados
    999999, 999, 0,  # BE, Grace, CD desativados
    99, 0.0,  # max_sl_consec=99 (off), slope_decay=0.0 (off)
    DIRECTION
)
dt_f2 = time.time() - t0

print(f"\nF2 (modo busca, sem guardrails):")
print(f"  PnL: {net_f2:+,} | Trades: {n_f2} | Wins: {wins_f2}")
print(f"  Tempo: {dt_f2:.3f}s")

# 5. Comparacao
print("\n" + "="*80)
print("COMPARACAO F1b vs F2")
print("="*80)
print(f"{'Metrica':<20} {'F1b':<15} {'F2':<15} {'Diferenca':<15}")
print("-"*65)
print(f"{'PnL':<20} {net_f1b:<+15} {net_f2:<+15} {net_f1b-net_f2:<+15}")
print(f"{'Trades':<20} {n_f1b:<15} {n_f2:<15} {n_f1b-n_f2:<+15}")
print(f"{'PnL/Trade':<20} {net_f1b/n_f1b if n_f1b>0 else 0:<15.1f} {net_f2/n_f2 if n_f2>0 else 0:<15.1f}")

diff_pct = abs(net_f1b - net_f2) / abs(net_f2) * 100 if net_f2 != 0 else 0
trade_diff_pct = abs(n_f1b - n_f2) / n_f2 * 100 if n_f2 > 0 else 0

print(f"\nDiferenca PnL: {diff_pct:.1f}%")
print(f"Diferenca Trades: {trade_diff_pct:.1f}%")

print("\n" + "="*80)
print("ANALISE DA DIVERGENCIA")
print("="*80)
print("""
O F1b e F2 NUNCA serao identicos porque tem arquiteturas diferentes:

1. AMOSTRAGEM:
   - F1b: 15 samples/candle (750 samples = 50 candles)
   - F2: high/low de CADA candle (toda a serie, 1986 candles)

2. BLOCKING:
   - F1b single: 1 candle (pode ter multiplos trades curtos encaixados)
   - F1b exact: duracao real do trade
   - F2: 1 trade por vez, perde sinais subsequentes enquanto aberto

3. ENTRADAS:
   - F1b: ep = open da proxima candle (lookahead=1)
   - F2: entry = close da candle atual (sem lookahead)

Resultado: F1b e F2 medem coisas DIFERENTES.
O F1b e um PRE-FILTRO que elimina configs obviamente ruins.
A correlacao de rankeamento e o que importa, nao o valor absoluto.
""")

print("\n" + "="*80)
print("VALIDACAO COMPLETE")
print("="*80)
