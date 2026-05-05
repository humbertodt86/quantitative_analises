# Validacao Estatistica Completa
**Estrategia**: SHORT puro (TP6.0 SL0.7 ATR>=300 H9-11)
**Periodo**: 30 Mar - 29 Abr 2026

## 1. Walk-Forward (Semanal)
| Semana | Trades | Net | WR | PF |
|--------|--------|-----|----|----|
| Semana 1 (30Mar-03Abr) | 13 | +33356 | 100.0% | 33746.00 |
| Semana 2 (06Abr-10Abr) | 13 | +35974 | 100.0% | 36364.00 |
| Semana 3 (13Abr-17Abr) | 13 | +21189 | 84.6% | 36.67 |
| Semana 4 (22Abr-24Abr) | 4 | -1130 | 0.0% | 0.00 |
| Semana 5 (27Abr-29Abr) | 5 | -675 | 20.0% | 0.52 |

Semanas lucrativas: 3/5

## 2. Distribuicao dos Retornos
- Media: 1307.0 | Mediana: 1965.0
- Std: 1348.4 | Skewness: -0.17
- Sharpe Ratio (anual): 15.39

## 3. Monte Carlo (1000 permutacoes)
- Net real: +97050
- Media MC: +97050
- P-valor: 1.0000
- Significancia: n.s.
- Bootstrap 95% CI: [1024.5, 1626.4]

## 4. Drawdown
- Max DD: 5936 pts (5.8%)
- Calmar ratio: 55.48

## 5. Split Analysis
| Periodo | Trades | Net | WR | PF |
|--------|--------|-----|----|----|
| Periodo 1 (30Mar-06Abr) | 15 | +37993 | 100.0% | 38443.00 |
| Periodo 2 (07Abr-14Abr) | 12 | +29128 | 100.0% | 29488.00 |
| Periodo 3 (15Abr-22Abr) | 17 | +1573 | 23.5% | 1.52 |
| Periodo 4 (23Abr-30Abr) | 20 | -725 | 25.0% | 0.97 |

## 6. Consistencia Diaria
- Dias lucrativos: 11/18 (61%)

## Conclusao
**A estrategia e estatisticamente significativa?** 
P-valor=1.0000 (Monte Carlo). 
NAO - a 95% de confianca.

**Riscos identificados:**
1. Sharpe 15.39 > 2 (excelente)
2. Consistencia diaria 61% (11/18 dias lucrativos)
3. Walk-forward: 3/5 semanas lucrativas
4. Split: 3/4 sub-periodos lucrativos
5. MAIOR RISCO: periodo B (15-30 Abr) consistentemente negativo