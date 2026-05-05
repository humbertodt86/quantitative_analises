# V139 Grid Search Results (IS -> OOS)

**Date**: 2026-04-30
**IS (training)**: 2026-01-02 to 2026-03-27 (fast screener)
**OOS (validation)**: 2026-03-30 to 2026-04-29 (tick-level)
**Cost**: 30 pts/trade

## Arquivos de Dados

| Arquivo | Conteudo | Periodo |
|---------|----------|---------|
| `data/indicators_winm26_complete.parquet` | Indicadores completos (44 colunas) | Jan 2 - Abr 29 |
| `data/ticks/WINJ26_ticks_YYYYMMDD.parquet` | Ticks WINJ26 (bid/ask real) | Mar 30 - Abr 15 |
| `data/ticks/WINM26_ticks_YYYYMMDD.parquet` | Ticks WINM26 (bid/ask real) | Abr 14 - 29 |
| `configs/v139_best_oos.json` | Melhor config do grid | - |

## ADX Periodos Disponiveis

- **ADX7**: 7-period (35 min) - rapido, reativo
- **ADX14**: 14-period (70 min) - padrao
- **ADX20**: 20-period (100 min) - lento
- **ADX30**: 30-period (150 min) - muito lento

## Resultado Final (OOS tick validation)

**201 trades, gross +23.300, net +17.270, WR 44.8%, PF 1.49**

### Melhor Config

```json
{
  "HUNTER": { "adx7": 25, "tp": 2.0, "sl": 1.0, "slope": 30, "dist_abs": 260 },
  "SNIPER": { "adx7": "22-26", "tp": 3.5, "slope": 20, "dist_abs": 160 },
  "SCALPER": { "adx7": 25, "tp": 2.5, "hour": 10, "dist_abs": 100 },
  "NORMAL": { "adx7": "15-24", "tp": 2.5, "dist_abs": 220 }
}
```
