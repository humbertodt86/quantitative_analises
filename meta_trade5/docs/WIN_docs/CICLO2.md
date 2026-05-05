# Ciclo 2: Refinamento TP + Filtros
Grid: 174,720 combos IS (218s)

## Top 10 IS
| # | TP | SL | DIST | HORA | ATRmin | Fri | VWAP_Z | IS Trades | IS Net | IS WR | IS PF |
|---|---|----|------|-------|--------|-----|--------|-----------|--------|-------|------|
| 1 | 6.0 | 0.7 | 50 | 9-11 | 300 | True | None | 300 | +45187 | 32.3% | 1.82 |
| 2 | 6.0 | 0.7 | 100 | 9-11 | 300 | True | None | 287 | +44466 | 32.8% | 1.85 |
| 3 | 6.0 | 0.7 | 200 | 9-11 | 300 | True | None | 255 | +44150 | 33.7% | 1.93 |
| 4 | 6.0 | 0.7 | 0 | 9-11 | 300 | True | None | 313 | +43739 | 31.3% | 1.77 |
| 5 | 6.0 | 0.7 | 150 | 9-11 | 300 | True | None | 266 | +43659 | 33.5% | 1.89 |
| 6 | 6.0 | 1.11 | 200 | 9-11 | 300 | True | None | 255 | +42881 | 42.0% | 1.67 |
| 7 | 6.0 | 0.7 | 300 | 9-11 | 300 | True | None | 237 | +42070 | 34.6% | 1.97 |
| 8 | 6.0 | 1.0 | 200 | 9-11 | 300 | True | None | 255 | +42034 | 40.0% | 1.69 |
| 9 | 6.0 | 0.7 | 200 | 9-11 | 200 | True | None | 295 | +41910 | 31.9% | 1.83 |
| 10 | 6.0 | 0.7 | 50 | 9-11 | 200 | True | None | 348 | +41793 | 30.5% | 1.72 |

## OOS Validation (Top 8)
| # | Config | IS Net | OOS Trades | OOS Net | OOS WR | OOS PF |
|---|--------|--------|-----------|---------|--------|--------|
| 1 | TP6.0 SL0.7 D0 H9-11 A300 | +43739 | 76 | +97050 | 63.2% | 13.85 |
| 2 | TP6.0 SL0.7 D50 H9-11 A300 | +45187 | 68 | +83839 | 61.8% | 12.58 |
| 3 | TP6.0 SL0.7 D100 H9-11 A300 | +44466 | 66 | +81627 | 62.1% | 12.75 |
| 4 | TP6.0 SL0.7 D150 H9-11 A300 | +43659 | 65 | +79259 | 63.1% | 14.41 |
| 5 | TP6.0 SL1.0 D200 H9-11 A300 | +42034 | 59 | +71106 | 59.3% | 11.81 |
| 6 | TP6.0 SL0.7 D200 H9-11 A300 | +44150 | 59 | +71091 | 59.3% | 11.79 |
| 7 | TP6.0 SL1.11 D200 H9-11 A300 | +42881 | 59 | +70946 | 59.3% | 11.54 |
| 8 | TP6.0 SL0.7 D300 H9-11 A300 | +42070 | 47 | +60448 | 61.7% | 12.79 |

## Best OOS Trade Table
Trades: 76 | Gross: +99330 | Net: +97050 | WR: 63.2%
Avg Win: 2230
Avg Loss: -286

## Verificacao
IS -> OOS consistency: checking if top IS configs maintain OOS performance
- TP6.0 SL0.7: IS=+43739 OOS=+97050 ratio=2.2x
- TP6.0 SL0.7: IS=+45187 OOS=+83839 ratio=1.9x
- TP6.0 SL0.7: IS=+44466 OOS=+81627 ratio=1.8x
- TP6.0 SL0.7: IS=+43659 OOS=+79259 ratio=1.8x
- TP6.0 SL1.0: IS=+42034 OOS=+71106 ratio=1.7x
- TP6.0 SL0.7: IS=+44150 OOS=+71091 ratio=1.6x
- TP6.0 SL1.11: IS=+42881 OOS=+70946 ratio=1.7x
- TP6.0 SL0.7: IS=+42070 OOS=+60448 ratio=1.4x

## Plano Ciclo 3
1. Testar PA_GK_BREAK como segundo filtro (confirmacao de tendencia)
2. Testar saida condicional via PA_SIGNAL_REV
3. Testar ATR_MIN=300 como padrao (melhorou no C2)
4. Expandir TP para 10-15x para ver limite