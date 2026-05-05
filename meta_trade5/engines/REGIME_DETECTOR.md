# Regime Detector V6.3 — Documentacao

**Gerado em:** 2026-05-01T16:48:42.083554
**Calibracao versao:** 1.0
**Dados:** 8787 linhas, 2026-01-02 14:05:00 a 2026-04-29 18:30:00

## 1. Especificacoes do Detector Atual (v1.0)

| Parametro | Valor |
|-----------|-------|
| Metodo | ER_backward + ADX7 |
| Janela ER backward | 10 candles |
| Threshold ER (default) | 0.4 |
| Threshold ADX7 (default) | 25 |
| Features usadas | close, ADX7 |

## 2. Ground Truth — Realized Trend Proxy

O gabarito de realizacao (post-hoc) usa o Efficiency Ratio **futuro** para
medir se o movimento APOS o candle T0 foi eficiente (direcional) ou ruidoso (zig-zag).

| Parametro | Valor |
|-----------|-------|
| Metodo | ER_forward (Realized Trend Proxy) |
| Janela forward | 10 candles |
| Threshold de trend | ER_forward > 0.5 |
| %% candles classificados como trend (realizado) | 23.0% |

**Atencao:** Este ground truth e usado APENAS para avaliacao, NUNCA para treino.
O detector continua usando apenas dados passados (ER backward + ADX7).

## 3. Metodologia de Calibracao

1. Para cada candle T0, calcular:
   - **Predicao**: ER_backward(T0-10, T0) > er_threshold AND ADX7(T0) > adx_threshold
   - **Realizacao**: ER_forward(T0, T0+10) > 0.5
2. Construir matriz de confusao (TP, FP, TN, FN)
3. Calcular precision, recall, F1, accuracy
4. Varrer grid ADX x ER para encontrar o melhor F1

## 4. Resultados do Threshold Sweep

Grid: 36 combinacoes

### Melhor Combo (por F1)

| Metrica | Valor |
|---------|-------|
| ADX7 threshold | 20 |
| ER threshold | 0.3 |
| Precision | 0.2170 |
| Recall | 0.4430 |
| F1 | 0.2913 |
| Accuracy | 0.5051 |
| TP | 894 |
| FP | 3225 |
| TN | 3544 |
| FN | 1124 |

### Tabela Completa (36 combinacoes)

| ADX | ER | Precision | Recall | F1 | Accuracy | TP | FP | TN | FN |
|-----|----|-----------|--------|----|----------|----|----|----|----|
| 20 | 0.30 | 0.2170 | 0.4430 | 0.2913 | 0.5051 | 894 | 3225 | 3544 | 1124 |
| 22 | 0.30 | 0.2175 | 0.4316 | 0.2892 | 0.5128 | 871 | 3134 | 3635 | 1147 |
| 25 | 0.30 | 0.2183 | 0.4108 | 0.2851 | 0.5268 | 829 | 2969 | 3800 | 1189 |
| 28 | 0.30 | 0.2191 | 0.3791 | 0.2777 | 0.5471 | 765 | 2727 | 4042 | 1253 |
| 30 | 0.30 | 0.2194 | 0.3563 | 0.2716 | 0.5611 | 719 | 2558 | 4211 | 1299 |
| 20 | 0.35 | 0.2116 | 0.3731 | 0.2701 | 0.5368 | 753 | 2805 | 3964 | 1265 |
| 22 | 0.35 | 0.2110 | 0.3627 | 0.2668 | 0.5422 | 732 | 2737 | 4032 | 1286 |
| 25 | 0.35 | 0.2128 | 0.3494 | 0.2645 | 0.5538 | 705 | 2608 | 4161 | 1313 |
| 28 | 0.35 | 0.2120 | 0.3216 | 0.2555 | 0.5696 | 649 | 2413 | 4356 | 1369 |
| 35 | 0.30 | 0.2236 | 0.2929 | 0.2536 | 0.6041 | 591 | 2052 | 4717 | 1427 |
| 20 | 0.40 | 0.2108 | 0.3142 | 0.2523 | 0.5723 | 634 | 2374 | 4395 | 1384 |
| 22 | 0.40 | 0.2107 | 0.3077 | 0.2502 | 0.5763 | 621 | 2326 | 4443 | 1397 |
| 30 | 0.35 | 0.2117 | 0.3038 | 0.2495 | 0.5803 | 613 | 2283 | 4486 | 1405 |
| 25 | 0.40 | 0.2124 | 0.2988 | 0.2483 | 0.5845 | 603 | 2236 | 4533 | 1415 |
| 28 | 0.40 | 0.2109 | 0.2775 | 0.2397 | 0.5957 | 560 | 2095 | 4674 | 1458 |
| 30 | 0.40 | 0.2108 | 0.2641 | 0.2345 | 0.6040 | 533 | 1995 | 4774 | 1485 |
| 35 | 0.35 | 0.2160 | 0.2537 | 0.2334 | 0.6172 | 512 | 1858 | 4911 | 1506 |
| 20 | 0.45 | 0.2049 | 0.2522 | 0.2261 | 0.6035 | 509 | 1975 | 4794 | 1509 |
| 22 | 0.45 | 0.2060 | 0.2493 | 0.2256 | 0.6069 | 503 | 1939 | 4830 | 1515 |
| 25 | 0.45 | 0.2079 | 0.2448 | 0.2249 | 0.6124 | 494 | 1882 | 4887 | 1524 |
| 28 | 0.45 | 0.2066 | 0.2304 | 0.2178 | 0.6200 | 465 | 1786 | 4983 | 1553 |
| 35 | 0.40 | 0.2137 | 0.2215 | 0.2175 | 0.6340 | 447 | 1645 | 5124 | 1571 |
| 30 | 0.45 | 0.2063 | 0.2200 | 0.2129 | 0.6265 | 444 | 1708 | 5061 | 1574 |
| 20 | 0.50 | 0.2039 | 0.2022 | 0.2030 | 0.6355 | 408 | 1593 | 5176 | 1610 |
| 22 | 0.50 | 0.2038 | 0.1997 | 0.2018 | 0.6371 | 403 | 1574 | 5195 | 1615 |
| 25 | 0.50 | 0.2047 | 0.1962 | 0.2004 | 0.6403 | 396 | 1539 | 5230 | 1622 |
| 35 | 0.45 | 0.2080 | 0.1858 | 0.1963 | 0.6505 | 375 | 1428 | 5341 | 1643 |
| 28 | 0.50 | 0.2040 | 0.1868 | 0.1950 | 0.6458 | 377 | 1471 | 5298 | 1641 |
| 30 | 0.50 | 0.2028 | 0.1789 | 0.1901 | 0.6499 | 361 | 1419 | 5350 | 1657 |
| 35 | 0.50 | 0.2045 | 0.1546 | 0.1761 | 0.6677 | 312 | 1214 | 5555 | 1706 |
| 22 | 0.60 | 0.2154 | 0.1333 | 0.1647 | 0.6894 | 269 | 980 | 5789 | 1749 |
| 20 | 0.60 | 0.2140 | 0.1333 | 0.1643 | 0.6885 | 269 | 988 | 5781 | 1749 |
| 25 | 0.60 | 0.2145 | 0.1308 | 0.1625 | 0.6903 | 264 | 967 | 5802 | 1754 |
| 28 | 0.60 | 0.2118 | 0.1244 | 0.1567 | 0.6926 | 251 | 934 | 5835 | 1767 |
| 30 | 0.60 | 0.2101 | 0.1194 | 0.1523 | 0.6947 | 241 | 906 | 5863 | 1777 |
| 35 | 0.60 | 0.2145 | 0.1085 | 0.1441 | 0.7040 | 219 | 802 | 5967 | 1799 |

## 5. Analise Precision-Recall

### Como interpretar

- **Precision alta** (> 0.5): Quando o detector diz 'Trend', a probabilidade de
  o movimento futuro ser realmente direcional e alta. Porem, pode perder
  tendencias reais (recall baixo).
- **Recall alto** (> 0.5): O detector captura a maioria das tendencias reais,
  mas com muitos falsos positivos (precision baixa), entrando em 'violinos'.
- **F1**: Media harmonica entre precision e recall. Melhor equilibrio.

### Recomendacao

- **Thresholds default atuais**: ADX7 > 25 + ER > 0.4 → F1=0.2483
- **Thresholds calibrados**: ADX7 > 20 + ER > 0.3 → F1=0.2913
- **Ganho de F1**: +0.0430


---
*Documentacao gerada automaticamente por `engines/calibrate_regime.py`*