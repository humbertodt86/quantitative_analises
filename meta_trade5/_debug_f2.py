import sys, os
sys.path.insert(0, '.')
import numpy as np
import pandas as pd
from datetime import datetime
from engines.f2_optimization_gpu import optimize_all_combos_gpu, analyze_f1_stability, generate_refined_grid
from scripts.family_classifier import get_family_config

IS_S, IS_E = datetime(2026, 2, 1), datetime(2026, 3, 1)
df = pd.read_parquet('data/variants_v87/PA_SIGNAL_DIR.parquet')
df['dt'] = pd.to_datetime(df['dt'])
df = df[(df['dt'] >= IS_S) & (df['dt'] <= IS_E)].reset_index(drop=True)
print(f'DF shape: {df.shape}')
print(f'Signal s0_z1p5_r0p5 sum SELL: {(df["s0_z1p5_r0p5"] == -1).sum()}')

family_config = get_family_config('trend')
print(f'SR buffers: {family_config["sr_buffers"]}')
print(f'Guardrails: {family_config["guardrails"]}')
print(f'Filters: {family_config["filters"]}')

f1_best = {'tp_mult': 2.0, 'sl_mult': 1.5, 'atr_min': 150, 'atr_max': 1000}
refined = generate_refined_grid(f1_best, factor=0.20, num_values=5)
# Ajusta filtros para escala dos dados
delta_vals = df['cum_delta'].values if 'cum_delta' in df.columns else np.array([0])
if np.abs(delta_vals).max() > 10:
    family_config['filters']['cum_delta_thresh'] = [-999.0, 0.0, 999.0]

grid = {
    'tp_sl_atr': refined,
    'sr_buffers': family_config['sr_buffers'],
    'guardrails': family_config['guardrails'],
    'filters': family_config['filters'],
}

import numpy as np
tp_sl = len(grid['tp_sl_atr']['tp_mult'])*len(grid['tp_sl_atr']['sl_mult'])*len(grid['tp_sl_atr']['atr_min'])*len(grid['tp_sl_atr']['atr_max'])
sr = len(grid['sr_buffers']['tp_sr_pct'])*len(grid['sr_buffers']['sl_sr_pct'])
grd = len(grid['guardrails']['be_offset'])*len(grid['guardrails']['grace_candles'])*len(grid['guardrails']['cooldown_candles'])*len(grid['guardrails']['max_sl_consec'])*len(grid['guardrails']['slope_decay'])
filt = len(grid['filters']['book_imb_thresh'])*len(grid['filters']['cum_delta_thresh'])
print(f'Combos: TP/SL={tp_sl} S/R={sr} GRD={grd} FILT={filt} TOTAL={tp_sl*sr*grd*filt}')

df_res, elapsed = optimize_all_combos_gpu(df, 's0_z1p5_r0p5', -1, grid, batch_size=500000)
print(f'F2 result: {len(df_res)} validos em {elapsed:.2f}s')
if len(df_res) > 0:
    print(df_res.head(3)[['tp_mult','sl_mult','net_pnl','n_trades','win_rate']].to_string())
else:
    print('No valid results from F2 GPU')
