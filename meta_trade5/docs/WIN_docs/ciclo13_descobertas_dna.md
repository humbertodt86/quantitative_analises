# Relatorio de Descobertas Ciclo 13 — DNA dos Trades e Padroes de Mercado

## 1. Resposta: Overfit Nao eh Causado por Falta de Tick Simulado

**Concordancia:** O custo de 30 pts/trade no F1/F2 eh suficiente como aproximacao. O overfit eh causado por:
- Diferenca de regime entre IS (Jan-Mar, misto) e OOS (Abril, tendencia de baixa)
- F2 sem guardrails realistas (corrigido no Ciclo 13)
- Otimizacao de BE=999999/CD=0 (corrigido no Ciclo 13)

A ausencia de spread nos ticks IS eh uma limitacao conhecida, mas nao o fator determinante do overfit.

---

## 2. Quais Indicadores Tem Correlacao com Lucro?

### REV_RSI_S70 (194 trades OOS)
| Indicador | Correlacao | Forca | Interpretacao |
|-----------|-----------|-------|---------------|
| **EMA5_SLOPE** | **-0.631** | FORTE | Mercado flat = lucro |
| PA_REV_RSI_B15 | +0.538 | Moderada | BUY signals (reversao) |
| PA_REV_RSI_S85 | +0.538 | Moderada | SELL extremo |
| PA_REV_RSI_S80 | +0.538 | Moderada | SELL extremo |
| PA_REV_RSI_B5 | +0.534 | Moderada | BUY leve |
| PA_REV_RSI_B10 | +0.534 | Moderada | BUY leve |
| PA_REV_RSI_S75 | +0.528 | Moderada | SELL forte |

### VWAP_REV (75 trades OOS)
| Indicador | Correlacao | Forca | Interpretacao |
|-----------|-----------|-------|---------------|
| **EMA5_SLOPE** | **-0.706** | FORTE | Mercado flat = lucro |
| **dist** | **-0.607** | Moderada | Perto do VWAP = lucro |
| PA_REV_RSI_B25 | +0.552 | Moderada | BUY reversao |
| PA_REV_RSI_S80 | +0.537 | Moderada | SELL extremo |
| PA_KELT_M1_0 | +0.524 | Moderada | Keltner squeeze |

**Resposta:** NAO, nao sao so EMA5_SLOPE e PA_REV. PA_REV_RSI_B* (BUY signals) tambem correlacionam positivamente, indicando que a reversao de RSI funciona em ambas as direcoes (embora so SELL tenha sido lucrativo no OOS de Abril).

---

## 3. Quantos Combos F1 por Estrategia?

```
TP_GRID = [1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]  → 9 valores
SL_GRID = [0.1, 0.15, 0.2, 0.3, 0.5, 0.8, 1.0, 1.5]        → 8 valores
ATR_MIN_GRID = [100, 200, 300]                                → 3 valores
ATR_MAX_GRID = [600, 1000, 9999]                              → 3 valores

Total: 9 × 8 × 3 × 3 = 648 combos por estrategia
Tempo F1: ~0.5s por estrategia (vetorizado numpy)
```

---

## 4. DNA dos Trades Vencedores vs Perdedores

### EMA5_SLOPE (Preditor Mais Forte)
| Modelo | TP (media) | SL (media) | Delta | Cohen's d |
|--------|-----------|-----------|-------|-----------|
| REV_RSI_S70 | 1.86 | 69.56 | -67.71 | **-1.08** |
| VWAP_REV | -22.27 | 59.77 | -82.03 | **-1.14** |

**Regra:** Trades lucrativos ocorrem quando |EMA5_SLOPE| < ~20. Trades perdedores ocorrem quando |EMA5_SLOPE| > ~60.

### dist (Distancia ao VWAP)
| Modelo | TP (media) | SL (media) | Delta | Cohen's d |
|--------|-----------|-----------|-------|-----------|
| REV_RSI_S70 | 37.80 | 199.52 | -161.73 | -0.57 |
| VWAP_REV | 11.13 | 195.78 | -184.65 | -0.83 |

**Regra:** Trades lucrativos entram perto do VWAP (< 40 pts). Trades perdedores entram longe (> 195 pts).

---

## 5. Segmentacao Temporal

### "Dia Magico": Terca-Feira
| Modelo | Dia | Trades | WR | Net |
|--------|-----|--------|-----|-----|
| REV_RSI_S70 | Ter | 38 | 55.3% | +3,421 |
| VWAP_REV | Ter | 36 | 77.8% | +6,283 |

**Terca eh o unico dia com WR > 55% para ambas as estrategias.**

### "Horario Mortal": Almoço (12h-13h)
| Modelo | Hora | Trades | WR | Net |
|--------|------|--------|-----|-----|
| REV_RSI_S70 | 12h | 7 | 14.3% | -899 |
| REV_RSI_S70 | 13h | 7 | 14.3% | -756 |
| VWAP_REV | 13h | 3 | 0.0% | -1,145 |

### Melhores Horarios
| Modelo | Hora | WR | Net |
|--------|------|-----|-----|
| REV_RSI_S70 | 15h | 45.2% | +2,140 |
| REV_RSI_S70 | 16h | 50.0% | +1,244 |
| VWAP_REV | 11h | 72.7% | +2,109 |
| VWAP_REV | 15h | 88.9% | +1,917 |

---

## 6. Tipo de Saida (BE/HP nunca ativados)

| Modelo | TP | SL | BE | HP |
|--------|----|----|----|----|
| REV_RSI_S70 | 68 | 126 | **0** | **0** |
| VWAP_REV | 38 | 37 | **0** | **0** |

**BE/HP nunca foram ativados no OOS.** Possiveis causas:
1. Preco nunca subiu o suficiente para acionar BE (200-300 pts)
2. `_simulate_exit_v119` pode nao estar reportando BE/HP no `hit_type`
3. BE trigger pode estar muito alto para o ATR do periodo

---

## 7. Conclusoes e Proximos Passos

1. **EMA5_SLOPE eh o DNA do sucesso** — Filtro |EMA5_SLOPE| < 50 deve ser testado
2. **dist ao VWAP prediz resultado** — Filtro dist < 150 para VWAP_REV
3. **Terca eh "dia magico"** — Boost de peso ou filtro de dia
4. **Almoco (12h-13h) eh letal** — Excluir ou reduzir exposicao
5. **BE/HP nunca ativados** — Investigar implementacao no engine
6. **F2 custo de 30 pts eh suficiente** — Nao priorizar simulacao de spread agora
