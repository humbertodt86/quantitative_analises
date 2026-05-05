"""Check DIST_ABS distribution."""
import polars as pl
import numpy as np
from datetime import datetime

df = pl.read_parquet('data/indicators_winm26_abril.parquet')
o = df.filter((pl.col('dt')>=datetime(2026,3,30))&(pl.col('dt')<datetime(2026,4,29)))
print(f'Abril: {len(o)} candles')

for nome, f in [
    ('ADX>22.7', pl.col('ADX7')>=22.72),
    ('ADX 17.7-22.7', (pl.col('ADX7')>=17.72)&(pl.col('ADX7')<22.72)),
    ('ADX<17.7', pl.col('ADX7')<17.72),
]:
    s = o.filter(f)
    d = s['DIST_ABS']
    atr_m = s['ATR'].mean()
    p25 = np.percentile(d, 25)
    p50 = np.percentile(d, 50)
    p75 = np.percentile(d, 75)
    print(f'  {nome:15s}: {len(s):5d} candles DIST_ABS p25={p25:.0f} p50={p50:.0f} p75={p75:.0f} ATR medio={atr_m:.0f}')
