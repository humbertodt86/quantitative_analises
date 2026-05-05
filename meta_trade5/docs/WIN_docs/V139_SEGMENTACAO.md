
## Guardrails Implementados

| Guardrail | Status | Descricao |
|-----------|--------|-----------|
| ATR Min/Max 200-800 | ✅ | engine_v2 filter |
| ADX Max 61.76 | ✅ | engine_v2 filter |
| ADX Rising (DELTA>=0.5) | ✅ | HUNTER filter |
| GK Ratio HUNTER >=0.0009 | ✅ | engine_v2 filter |
| GK Ratio SNIPER 0.0009-0.0013 | ✅ | engine_v2 filter |
| GK Ratio SCALPER >=0.0010 | ✅ | engine_v2 filter |
| Hour Block 9:30-17:30 | ✅ | engine_v2 loop |
| 9:00-9:30 HUNTER only | ✅ | engine_v2 loop |
| 12-14h Lunch Filter DIST>=300 | ✅ | engine_v2 loop |
| Circuit Breaker 5 SLs/dia | ✅ | engine_v2 loop |
| Cooldown after SL | ✅ | engine_v2 loop |
| S/R Buffers (TP=90% SL=110%) | ✅ | SNIPER/SCALPER |

## Segmentacao (130 trades OOS)

### Por Direcao
| Direcao | Trades | WR | Net |
|---------|--------|----|-----|
| BUY | 54 | 11.1% | -20.926 |
| SELL | 76 | 78.9% | +50.976 |

### Por Modo
| Modo | Trades | WR | Net |
|------|--------|----|-----|
| SCALPER | 78 | 51.3% | +19.901 |
| NORMAL | 40 | 47.5% | +4.240 |
| SNIPER | 12 | 58.3% | +5.909 |

### Por Dia
| Dia | Trades | WR | Net |
|-----|--------|----|-----|
| Seg | 29 | 44.8% | +4.127 |
| Ter | 30 | 43.3% | +5.036 |
| Qua | 29 | 55.2% | +9.199 |
| Qui | 23 | 47.8% | +4.726 |
| Sex | 19 | 68.4% | +6.962 |

### Top Correlacoes com PnL
1. RIBBON_STATE: +0.18
2. DIST_ABS: +0.16
3. ATR: +0.11
4. EMA5_SLOPE_ABS: +0.11

## Arquivos Gerados
- `docs/WIN_docs/WIN_TRADE_TABLE_V139.csv` - 130 trades com indicadores
- `docs/WIN_docs/INVENTARIO_ESTRATEGIAS.md` - Inventario completo
- `configs/v139_best_oos.json` - Melhor config
- `data/indicators_winm26_complete.parquet` - 44 colunas, ADX7/14/20/30
