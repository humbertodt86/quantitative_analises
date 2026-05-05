# Ciclo 1: Short-only + RIBBON Guardrail
Grid: 49,896 combos IS | Valid: 49896 | 76s

## Top 5 OOS Tick Validation
| # | TP | SL | DIST | HORA | RIBBON | Trades | Gross | Net | WR | PF |
|---|---|----|------|------|--------|--------|-------|-----|----|----|
| 1 | 6.0 | 0.7 | 200 | 9-11 | None | - | - | - | - | - |
| 2 | 6.0 | 0.7 | 50 | 9-11 | None | - | - | - | - | - |
| 3 | 6.0 | 0.7 | 200 | 9-11 | leq0 | - | - | - | - | - |
| 4 | 6.0 | 0.7 | 100 | 9-11 | leq0 | - | - | - | - | - |
| 5 | 6.0 | 0.7 | 50 | 9-11 | leq0 | - | - | - | - | - |

## Best IS Config: TP=6.0 SL=0.7 D=200 H9-11 RIB=None
IS: 295t net=+41910 WR=31.9% PF=1.83

## Trade Table Analysis (OOS Best)
Trades: 71 | Gross: +75760 | Net: +73630 | WR: 53.5%
Avg Win: 2229
Avg Loss: -271

### By Day
- Mon: 15t gross=+16960 WR=60.0%
- Tue: 15t gross=+20127 WR=60.0%
- Wed: 22t gross=+23298 WR=50.0%
- Thu: 11t gross=+16631 WR=63.6%
- Fri: 8t gross=-1256 WR=25.0%

### Correlations
- ADX7: corr=+0.041 win_mean=44.15 los_mean=44.67
- ATR: corr=+0.441 win_mean=392.49 los_mean=354.90
- RIBBON_STATE: corr=-0.010 win_mean=-0.55 los_mean=-0.48
- DIST_ABS: corr=+0.050 win_mean=445.36 los_mean=481.25
- EMA5_SLOPE_ABS: corr=-0.029 win_mean=79.08 los_mean=97.61
- VWAP_Z: corr=+0.337 win_mean=-0.75 los_mean=-1.77
- RSI2: corr=+0.202 win_mean=46.99 los_mean=34.20

## Plano Ciclo 2
Baseado nos resultados do Ciclo 1 (short-only + RIBBON):
1. Testar PA_GK_BREAK como filtro adicional (confirmacao)
2. Testar saida por PA_SIGNAL_REV (reversao do sinal)
3. Testar janela 11-12h isolada (melhor WR em dados anteriores)
4. Aumentar grid para 199,584 combos combinando filtros