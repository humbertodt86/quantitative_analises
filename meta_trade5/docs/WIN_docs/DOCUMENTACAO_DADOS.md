# Documentacao dos Dados WIN
**Data**: 2026-04-30 09:54

## 1. Parquets de Indicadores Disponiveis

| Arquivo | Descricao | Colunas | Periodo | Uso |
|---------|-----------|---------|---------|-----|
| `data/super_win_continuous.parquet` | **Indicadores continuos (RECOMENDADO)** - WINJ26 (Jan-13Abr) + WINM26 (14Abr-29Abr) mergeados | **154** | Jan 2 - Abr 29 | **Todos os backtests** |
| `data/super_win_M5.parquet` | Apenas WINM26 (super table com 21 sinais PA_) | 54 | Jan 2 - Abr 29 | Exploracao de sinais (sem J26) |

> **NOTA:** A lista completa de 154 colunas precisa ser atualizada. A lista abaixo (Secao 6) mostra apenas as colunas documentadas ate Abr/2026. Novas colunas incluem: ADX14/ADX20/ADX30, microestrutura (Book_Imbalance, CVD), regime_label, efficiency_ratio, e mais.
| `data/indicators_winm26_abril.parquet` | Apenas WINM26, 23 colunas basicas | 23 | Jan 2 - Abr 29 | Legado |
| `data/indicators_winm26_complete.parquet` | WINM26 + ADX7/14/20/30 + microestrutura | 44 | Jan 2 - Abr 29 | Legado |

## 2. Compatibilizacao J26 -> M26

### Motivo
O contrato WINJ26 (Jan-Jun 2026) era o mais liquido de Janeiro a meados de Abril.
O contrato WINM26 (Mar-Jun 2026) tornou-se o liquido a partir de meados de Abril.
Para replicar o comportamento real de migracao de contrato, o parquet continuo usa:
- **WINJ26 candles** para o periodo 02 Jan - 13 Abr
- **WINM26 candles** para o periodo 14 Abr - 29 Abr

### Processo
1. Carregar `WINJ26_M5.csv` -> `add_indicators()` + sinais PA_ -> salvar Polars
2. Carregar `WINM26_M5_*.csv` -> `add_indicators()` + sinais PA_ -> salvar Polars
3. Merge: `J26[dt < 2026-04-14] + M26[dt >= 2026-04-14]`
4. Remover duplicatas na fronteira
5. Salvar `super_win_continuous.parquet`

### Gap na Fronteira
| Data | Contrato | Close |
|------|----------|-------|
| 13 Abr 09:40 | J26 | 196.480 |
| 14 Abr 09:00 | M26 | 202.750 |
| **Gap** | | **6.270 pts** |

Este gap e o diferencial de precos entre contratos (cost of carry + liquidez). 
Nao afeta os backtests porque cada trade comeca e termina dentro do mesmo contrato.

## 3. Periodos Disponiveis

| Periodo | Data | Candles | Ticks | Indicadores | USO |
|---------|------|---------|-------|-------------|-----|
| **IS (treino)** | 02 Jan - 27 Mar | 4.147 | Nao (apenas last) | super_win_continuous | Fast-screener para otimizacao |
| **OOS (validacao)** | 30 Mar - 29 Abr | 2.270 | 37,4M (bid/ask) | super_win_continuous | **Validacao final com ticks** |
| OOS_A | 30 Mar - 13 Abr (J26) | 1.144 | ~20M J26 ticks | super_win_continuous | Subperiodo (tendencia baixa) |
| OOS_B | 14 Abr - 29 Abr (M26) | 1.126 | ~17.5M M26 ticks | super_win_continuous | Subperiodo (lateral/alta) |

## 4. Niveis de Preco por Periodo

| Periodo | Contrato | Preco Min | Preco Max | Preco Medio |
|---------|----------|-----------|-----------|-------------|
| IS (Jan-Mar) | J26 | 165905 | 197585 | 182676 |
| OOS (30Mar-29Abr) | J26+M26 | 182220 | 203640 | 193963 |
| OOS_A (30Mar-13Abr) | J26 | 182220 | 198580 | 190118 |
| OOS_B (14-29Abr) | M26 | 186885 | 203640 | 197134 |

## 5. Dados de Tick

### Ticks com bid/ask real
| Arquivo | Contrato | Periodo | Ticks | Qualidade |
|---------|----------|---------|-------|-----------|
| `WINJ26_ticks_20260330.parquet` | J26 | 2026-03-30 | 1,905,070 | 99% validos |
| `WINJ26_ticks_20260331.parquet` | J26 | 2026-03-31 | 2,278,605 | 99% validos |
| `WINJ26_ticks_20260401.parquet` | J26 | 2026-04-01 | 2,139,931 | 99% validos |
| `WINJ26_ticks_20260402.parquet` | J26 | 2026-04-02 | 2,092,548 | 99% validos |
| `WINJ26_ticks_20260406.parquet` | J26 | 2026-04-06 | 1,782,259 | 99% validos |
| `WINJ26_ticks_20260407.parquet` | J26 | 2026-04-07 | 2,137,711 | 99% validos |
| `WINJ26_ticks_20260408.parquet` | J26 | 2026-04-08 | 2,177,397 | 99% validos |
| `WINJ26_ticks_20260409.parquet` | J26 | 2026-04-09 | 2,002,722 | 99% validos |
| `WINJ26_ticks_20260410.parquet` | J26 | 2026-04-10 | 1,844,150 | 99% validos |
| `WINJ26_ticks_20260413.parquet` | J26 | 2026-04-13 | 1,823,264 | 99% validos |
| `WINJ26_ticks_20260414.parquet` | J26 | 2026-04-14 | 1,722,269 | 100% validos |
| `WINJ26_ticks_20260415.parquet` | J26 | 2026-04-15 | 384,880 | 99% validos |
| `WINM26_ticks_20260414.parquet` | M26 | 2026-04-14 | 242,649 | 96% validos |
| `WINM26_ticks_20260415.parquet` | M26 | 2026-04-15 | 1,558,757 | 99% validos |
| `WINM26_ticks_20260416.parquet` | M26 | 2026-04-16 | 1,755,129 | 100% validos |
| `WINM26_ticks_20260417.parquet` | M26 | 2026-04-17 | 1,808,241 | 99% validos |
| `WINM26_ticks_20260420.parquet` | M26 | 2026-04-20 | 1,600,880 | 99% validos |
| `WINM26_ticks_20260422.parquet` | M26 | 2026-04-22 | 1,794,586 | 99% validos |
| `WINM26_ticks_20260423.parquet` | M26 | 2026-04-23 | 1,898,842 | 99% validos |
| `WINM26_ticks_20260424.parquet` | M26 | 2026-04-24 | 1,670,567 | 99% validos |
| `WINM26_ticks_20260427.parquet` | M26 | 2026-04-27 | 1,905,188 | 99% validos |
| `WINM26_ticks_20260428.parquet` | M26 | 2026-04-28 | 1,637,872 | 99% validos |
| `WINM26_ticks_20260429.parquet` | M26 | 2026-04-29 | 1,621,448 | 99% validos |

### Ticks com apenas last (sintetico)
| Arquivo | Periodo | Ticks |
|---------|---------|-------|
| `WIN_ticks_bt_2026_01_02.csv` | Pre-30 Mar (apenas last) | CSV (last-only) |

## 6. M5 Reconstruido a partir de ticks

Nao ha M5 reconstruido de ticks. Os candles M5 sao exportados diretamente do MT5:
| Arquivo | Contrato | Periodo | Fonte |
|---------|----------|---------|-------|
| `candles/WINJ26_M5.csv` | J26 | Jan 2 - Abr 15 | Export MT5 (tab-separated) |
| `candles/WINM26_M5_202601020910_202604291830.csv` | M26 | Jan 2 - Abr 29 | Export MT5 |

## 7. Colunas do `super_win_continuous.parquet`

Total: 43 colunas

### Indicadores Base
| Coluna | Descricao |
|--------|-----------|
| `ADX7` | - |
| `ATR` | - |
| `EMA20` | - |
| `EMA5_SLOPE` | - |
| `EMA5_SLOPE_ABS` | - |
| `GK_RATIO` | - |
| `VWAP` | - |
| `VWAP_Z` | - |
| `RSI2` | - |
| `RSI14` | - |
| `BB_UPPER` | - |
| `BB_LOWER` | - |
| `BB_WIDTH_PCT` | - |
| `MA9` | - |
| `MA21` | - |
| `MA50` | - |
| `RIBBON_STATE` | - |
| `dist` | - |
| `DIST_ABS` | - |

### Sinais PA_ (21)
Total: 14 sinais
| `PA_SIGNAL_DIR` | 8847/8847 candles ativos |
| `PA_SIGNAL_REV` | 8847/8847 candles ativos |
| `PA_REV_RSI` | 3220/8847 candles ativos |
| `PA_BB` | 1069/8847 candles ativos |
| `PA_VWAP_REV` | 1657/8847 candles ativos |
| `PA_VWAP_Z` | 4876/8847 candles ativos |
| `PA_STRONG_TREND` | 4123/8847 candles ativos |
| `PA_ADX_BREAK` | 3723/8847 candles ativos |
| `PA_GK_BREAK` | 2535/8847 candles ativos |
| `PA_RIB_TREND` | 4757/8847 candles ativos |
| `PA_BB_SQZ` | 952/8847 candles ativos |
| `PA_EXHAUST` | 1826/8847 candles ativos |
| `PA_MA_CROSS` | 452/8847 candles ativos |
| `PA_SLOPE_TREND` | 4495/8847 candles ativos |

### Colunas de Data
| `dt` | Timestamp do candle M5 |
| `date` | Data (YYYY-MM-DD) |
| `hour` | Hora (0-23) |
| `minute` | Minuto (0-59) |
| `open/high/low/close/volume` | OHLCV classico |

## 8. Recomendacoes de Uso

1. **Sempre usar** `super_win_continuous.parquet` para backtests
2. **IS (fast-screener)**: 02 Jan - 27 Mar (candle-level, sem ticks)
3. **OOS (tick validation)**: 30 Mar - 29 Abr (J26 ticks para 30Mar-13Abr, M26 ticks para 14-29Abr)
4. **Nao misturar** J26 ticks com M26 candles (contratos diferentes)
5. **Ticks com bid/ask** existem apenas apos 30 Mar. Antes disso, apenas last (CSV)