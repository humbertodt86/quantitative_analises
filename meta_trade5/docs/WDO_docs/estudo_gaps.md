# Estudo de Gap de Abertura — WDO

## Resumo
Analise detalhada de gaps de abertura no WDO (Jan-Abr 2026).
Conclusao: gap fill nao tem edge consistente como estrategia standalone.

## Dados Base

| Metrica | IS (Jan-Mar) | OOS (Mar-Abr) | Total |
|---------|-------------|---------------|-------|
| Dias de negociacao | 59 | 22 | 81 |
| Gaps > ATR*0.3 | 45 (76%) | 16 (73%) | 61 (75%) |
| Threshold: 61 gaps em 81 dias = ~75% dos dias tem gap significativo |

## Comportamento dos Gaps

### WR por tamanho do gap (61 ocorrencias)

| Tamanho | WR (fechou) | Ocorrencias | Decisao |
|---------|-------------|-------------|---------|
| ≤ 5pts | **100%** | 11 | ✅ FILL sempre |
| ≤ 8pts | 86% | 22 | ✅ FILL |
| ≤ 10pts | **81%** | 26 | ✅ FILL |
| ≤ 15pts | 80% | 40 | ✅ FILL |
| > 15pts | **52%** | 21 | ⚠️ Aleatorio |
| > 20pts | **44%** | 16 | ❌ Perde dinheiro |

### Tempo para o gap fechar (quando fecha)

| Percentil | Candles | Minutos |
|-----------|---------|---------|
| P10 | 1 | 5min |
| P25 | 3 | 15min |
| **P50** | **7** | **35min** |
| P75 | 21 | 105min |
| P90 | 41 | 205min |

### Gap fill vs Continuacao (caracteristicas)

| Caracteristica | Gaps que fecharam | Gaps que viraram tendencia | Diferenca |
|---------------|-------------------|---------------------------|-----------|
| Tamanho medio | 12,4 pts | 27,0 pts | -14,6 pts |
| Gap/ATR | 1,1 | 2,0 | -0,9 |
| Gap DOWN | 42% | **78%** | Gaps de baixa viram tendencia |
| Gap vs MA5 | +0,3 ATR | -1,2 ATR | Abriu abaixo da media = trend |

## Testes Realizados

### 1. Gap Fill puro (TP=gap_size, SL=ATR*0.5-1.0)
- **Grid**: 1.800+ combos (gap_th, tp_mult, sl_mult, hold, S/R buffer)
- **Resultado**: IS negativo em 100% das combinacoes
- **Melhor OOS**: +72 pts (16 trades, 75% WR) mas IS = -130
- **Veredito**: ❌ Inconsistente (IS vs OOS opostos)

### 2. Order Flow (book 5min)
- **Dados**: Ticks bid/ask reais do OOS (3,2M ticks)
- **Delta**: aggressive buys - aggressive sells nos primeiros 5 min
- **Acerto**: **44%** (pior que aleatorio)
- **Problema**: 11/16 aberturas tem delta positivo (vies comprador natural)
- **Veredito**: ❌ Sem poder preditivo

### 3. Alinhamento book + gap
- **Logica**: gap DOWN + book compra = FILL; gap DOWN + book vende = CONTINUACAO
- **Resultado**: 44% acerto (mesmo que aleatorio)
- **Veredito**: ❌ Book 5min nao prediz o dia

### 4. Regra do usuario (gap ≤ 10 FILL, > 15 book decide)
- **PnL teorico**: +84 pts em 22 dias (+3,8 pts/dia)
- **Problema**: Apenas 16 ocorrencias OOS (amostra insuficiente)
- **Veredito**: ⚠️ Promissor mas nao validado estatisticamente

## Aprendizados

1. **ATR na abertura nao e confiavel**: ATR diario reseta, primeiro candle tem ATR inflado (12,8 pts vs 3,6 pts real). Usar ATR do dia anterior.
2. **Gaps > 15pts viram tendencia**: WR cai para 52% (aleatorio). Evitar fill em gaps grandes.
3. **Gaps DOWN viram tendencia com mais frequencia**: 78% dos trends sao gap DOWN.
4. **Book de 5min nao prediz o dia**: Vies comprador natural na abertura. Book verdadeiro (depth) seria necessario.
5. **Amostra pequena**: 61 gaps totais, 16 no OOS. Insuficiente para validacao estatistica robusta.

## Arquivos de Referencia

| Arquivo | Conteudo |
|---------|----------|
| `scripts/grid_gap_fill.py` | Grid V1 (TP=1.5x gap, SL=1.0x gap) |
| `scripts/grid_gap_fill_v2.py` | Grid V2 (parametros corretos) |
| `scripts/grid_gap_fill_v3.py` | Grid V3 (TP=gap, SL=ATR) |
| `scripts/analise_gaps_detalhada.py` | Analise de aberturas e thresholds |
| `scripts/analise_gaps_2.py` | Comportamento dos gaps (fill vs trend) |
| `scripts/analise_gaps_3.py` | ATR, threshold, preditores |
| `scripts/analise_orderflow.py` | Order flow na abertura |
| `scripts/analise_orderflow2.py` | Regra de alinhamento (corrigida) |
| `scripts/analise_orderflow3.py` | Book decide todos os gaps |
| `scripts/analise_orderflow4.py` | Alinhamento correto final |
| `docs/backtest/trades/grid_gap_fill.csv` | Resultados V1 (parcial 5k combos) |
| `docs/backtest/trades/grid_gap_fill_v2.csv` | Resultados V2 (1.800 combos) |
| `docs/backtest/trades/grid_gap_fill_v3.csv` | Resultados V3 (108 combos) |
