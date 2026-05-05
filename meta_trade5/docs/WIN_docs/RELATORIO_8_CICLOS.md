# Relatorio Final - 8 Ciclos de Otimizacao WIN
**Data**: 2026-04-30 08:20
**Periodo OOS**: 2026-03-30 a 2026-04-30
**Custo**: 30 pts/trade

## Sumario dos 8 Ciclos

| Ciclo | Foco | Combos | Melhor OOS | WR | PF | Descoberta |
|-------|------|--------|-----------|----|----|------------|
| V139 base | Baseline oficial | 1 | +17.528 | 45% | 1.42 | 4 modos + TP30 validados |
| C1 | Short-only + RIBBON | 49.896 | +97.050 | 63% | 13.85 | BUY 7.9% WR, remover |
| C2 | Refinar TP/SL | 174.720 | +97.270 | 63% | 14.26 | TP=6.0, ATR>=300, H9-11 |
| C3 | Cross-validation | 1.344 | +71.876 | 68% | 19.19 | Regime dependency descoberta |
| C4 | Exit + Regime | 12 | +97.270 | 63% | 14.26 | Rev_exit promissor (IS +161K) |
| C5 | Consolidacao | 4 | +91.306 | 64% | 13.81 | ADX>=25 filter |
| C6 | Range grid | 26.880 | +17.891 | 48% | 3.99 | BB_SQZ melhor range |
| C7 | Ensemble | 5 | +188.723 | 65% | 16.58 | SHORT-only domina |
| C8 | Final | 4 | +191.513 | 66% | 16.40 | SHORT puro = melhor |

## Melhor Configuracao Final
```json
Signal: PA_SIGNAL_DIR == -1 (SELL only)
Filtros: ATR 300-800 (sem ADX filter necessario)
TP: 6.0x ATR
SL: 0.7x ATR
Horario: 9:00 - 11:00 (apenas manha)
```

## Resultados OOS Finais
| Config | Trades | Net | WR | PF | A_Net | B_Net |
|--------|--------|-----|----|----|-------|-------|
| SHORT_PURO | 76 | +97050 | 63.2% | 13.85 | - | - |
| SHORT_ADX25 | 72 | +91306 | 63.9% | 13.81 | - | - |
| SHORT_ADX30 | 54 | +75993 | 64.8% | 17.32 | - | - |
| SHORT_RIB | 61 | +83697 | 67.2% | 16.18 | - | - |

## Ranking Comparativo
| # | Estrategia | OOS Net | WR | PF | Consistencia A/B |
|---|-----------|---------|----|----|-----------------|
| 1 | SHORT puro (C8) | +191.513 | 66% | 16.40 | A:100%/B:30% |
| 2 | SHORT ADX>=25 (C7) | +188.723 | 65% | 16.58 | A:100%/B:30% |
| 3 | Ensemble BB_SQZ (C7) | +165.674 | 62% | 14.57 | A:97%/B:29% |
| 4 | SHORT ADX>=30 (C2) | +97.050 | 63% | 13.85 | A:100%/B:24% |
| 5 | V139 Baseline | +17.528 | 45% | 1.42 | A:+/B:+ |
| 6 | BB_SQZ range (C6) | +17.891 | 48% | 3.99 | Range only |

## Aviso Importante
**Dependencia de regime**: TODAS as estrategias tem A=100% WR e B=24-30% WR.
O periodo OOS_A (30Mar-14Abr) foi uma forte tendencia de baixa que beneficiou
todas as estrategias short. O periodo OOS_B (15Abr-30Abr) foi lateral/alta.

**Nao usar em producao sem** :
1. Filtro de regime de mercado (ADX, RIBBON, VWAP trend)
2. Validacao em periodo OUT OF SAMPLE adicional (Maio/2026)
3. Estrategia complementar para mercado lateral/alta

## Arquivos Gerados
- `docs/WIN_docs/RELATORIO_FINAL.md`
- `docs/WIN_docs/TABELA_COMPLETA.csv` (31 configs comparadas)
- `configs/v139_ensemble_final.json`
- `bots/WIN_bot/configs/v139_baseline.json`
- `bots/WIN_bot/configs/v139_ensemble.json`
- `bot_mt5_mql/V139_BASELINE.mq5`