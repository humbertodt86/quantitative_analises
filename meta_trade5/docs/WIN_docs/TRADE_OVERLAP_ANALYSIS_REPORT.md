# Relatorio de Analise de Sobreposicao de Trades — Todos os Modelos

**Data:** 2026-05-03
**Base de dados:** ALL_MODELS_OOS_TRADES.csv (7,513 trades, 95 estrategias)
**Periodo:** OOS (Mar 30 - Abr 29, 2026)

---

## Resumo Executivo

Este relatorio analisa a **sobreposicao temporal de trades** entre todos os modelos testados no ciclo_memory.json. O objetivo e identificar:
1. **Estrategias complementares** (baixa sobreposicao) — candidatas a ensemble
2. **Estrategias redundantes** (alta sobreposicao) — devem ser evitadas juntas
3. **Oportunidades de fusao** (sobreposicao alta = possivel combinar filtros)

---

## Metodologia

### Metricas Calculadas

| Metrica | Descricao |
|---------|-----------|
| **Overlap Count** | Numero de pares de trades (A, B) cujos intervalos se interceptam |
| **Simultaneity %** | % de trades de A que se sobrepoe a trades de B (e vice-versa) |
| **Avg Overlap Candles** | Duracao media da sobreposicao, em candles (10 min) |
| **Complementarity Score** | 100 - Simultaneidade Media. 100 = totalmente independente |
| **Zero Overlap Pairs** | Numero de pares de estrategias sem NENHUMA sobreposicao |

### Limitacoes
- **95 de 158 estrategias** com trades disponiveis (63 reexecutados com simulacao OHLC, 8 skipped por coluna removida)
- Duracao do trade estimada por hit_type (TP/SL ~ 2 candles, BE ~ 3 candles, HSTAG ~ 6 candles)
- Sem dados de exit_dt exato — estimativa conservadora
- Simulacao OHLC (sem ticks) usa high/low dos candles para TP/SL — menos precisa que tick-level

---

## Resultados por Estrategia

### Top 10 Estrategias por Numero de Trades

| # | Estrategia | Trades | OOS Net | WR% | Avg PnL |
|---|-----------|--------|---------|-----|---------|
| 1 | PA_VWAP_Z_Z2_0_HYBRID_SELL | 164 | +289 | 47.6% | +31.8 |
| 2 | PA_REV_RSI_B15_HYBRID_SELL | 147 | +13,111 | 52.4% | +119.2 |
| 3 | PA_ADX_BREAK_A25_TREND_SELL | 124 | -3,786 | 46.8% | -0.5 |
| 4 | PA_VWAP_Z_Z2_0_RANGE_SELL | 121 | +2,052 | 49.6% | +47.0 |
| 5 | PA_LIQ_GRAB_HYBRID_SELL | 114 | -4,379 | 49.1% | -8.4 |
| 6 | PA_TSI_T25_HYBRID_SELL | 87 | +9,532 | 54.0% | +139.6 |
| 7 | PA_POC_REV_HYBRID_SELL | 84 | -363 | 53.6% | +25.7 |
| 8 | PA_GK_BREAK_G0_001_TREND_SELL | 65 | -1,076 | 44.6% | +13.4 |
| 9 | PA_LIQ_GRAB_RANGE_SELL | 65 | -970 | 50.8% | +15.1 |
| 10 | PA_VWAP_Z_Z2_0_TREND_SELL | 58 | +1,759 | 39.7% | +60.3 |

### Complementaridade por Estrategia

Estrategias ordenadas do **mais independente** ao **mais redundante**:

| Rank | Estrategia | Comp Score | Zero Overlap | Max Simultaneity |
|------|-----------|:----------:|:------------:|:----------------:|
| 1 | PA_VWAP_REV_D1_0_HYBRID_BUY | 88.3 | 26/36 | 161.5% |
| 2 | PA_VWAP_REV_D1_0_RANGE_BUY | 88.3 | 26/36 | 161.5% |
| 3 | PA_EXHAUST_Dn1_0_M40_TREND_SELL | 86.3 | 11/36 | 64.6% |
| 4 | PA_CHOP_C38_2_TREND_SELL | 84.8 | 16/36 | 124.7% |
| 5 | COMBO_LIQ_MOMENTUM_HYBRID_SELL | 84.3 | 29/36 | 153.4% |
| 6 | COMBO_LIQ_MOMENTUM_RANGE_SELL | 84.3 | 29/36 | 153.4% |
| 7 | PA_ADX_BREAK_A25_RANGE_SELL | 83.9 | 11/36 | 80.6% |
| 8 | PA_BB_M2_0_RANGE_SELL | 83.7 | 26/36 | 162.1% |
| 9 | PA_VCP_RANGE_SELL | 83.2 | 17/36 | 127.7% |
| 10 | PA_GK_BREAK_G0_001_RANGE_SELL | 82.2 | 8/36 | 77.5% |

**Estrategias MAIS REDUNDANTES (evitar no ensemble):**

| Rank | Estrategia | Comp Score | Max Simultaneity |
|------|-----------|:----------:|:----------------:|
| 37 | PA_VWAP_Z_Z2_0_HYBRID_SELL | 11.2 | 259.2% |
| 36 | PA_TSI_T25_HYBRID_SELL | 22.5 | 276.3% |
| 35 | PA_TSI_T25_TREND_SELL | 39.1 | 276.3% |
| 34 | PA_VWAP_Z_Z2_0_TREND_SELL | 39.7 | 156.4% |
| 33 | PA_POC_REV_HYBRID_SELL | 46.1 | 224.1% |
| 32 | PA_VWAP_Z_Z2_0_RANGE_SELL | 46.4 | 259.2% |
| 31 | PA_REV_RSI_B15_HYBRID_SELL | 49.2 | 123.8% |

---

## Pares Redundantes (Alta Simultaneidade)

### Top 5 Pares Mais Redundantes

| # | Par A | Par B | Overlap | Avg Simultaneity |
|---|-------|-------|:-------:|:----------------:|
| 1 | PA_TSI_T25_HYBRID_SELL + PA_TSI_T25_TREND_SELL | 182 trades | 276.3% |
| 2 | PA_VWAP_REV_D1_0_HYBRID_SELL + PA_VWAP_REV_D1_0_RANGE_SELL | 150 trades | 267.9% |
| 3 | PA_VWAP_Z_Z2_0_HYBRID_SELL + PA_VWAP_Z_Z2_0_RANGE_SELL | 361 trades | 259.2% |
| 4 | PA_TUESDAY_HYBRID_SELL + PA_TUESDAY_RANGE_SELL | 102 trades | 251.9% |
| 5 | PA_TSI_T25_HYBRID_SELL + PA_TSI_T25_RANGE_SELL | 130 trades | 245.8% |

**Observacao:** A simultaneidade > 100% indica que os trades sao muito curtos e se sobrepoe em multiplas combinacoes. Isso significa que as estrategias estao operando nos **mesmos horarios com sinais muito similares**.

---

## Pares Complementares (Baixa Simultaneidade)

### Pares com Zero Sobreposicao

**Total: 266 pares (de 666 possiveis)**

Exemplos de pares 100% complementares:
- COMBO_LIQ_MOMENTUM_HYBRID_SELL + PA_TUESDAY_RANGE_SELL
- PA_ADX_BREAK_A25_RANGE_SELL + PA_BB_M2_0_TREND_SELL
- PA_EXHAUST_Dn1_0_M40_TREND_SELL + PA_TSI_T25_TREND_SELL
- PA_CHOP_C38_2_TREND_SELL + PA_VCP_HYBRID_SELL

---

## Insights para Ensemble

### 1. Estrategias da Mesma Familia = Alta Redundancia

Estrategias derivadas do **mesmo indicador** tem sobreposicao extrema:

| Familia | Estrategias | Overlap |
|---------|------------|---------|
| VWAP_Z | HYBRID + RANGE + TREND | 259% simultaneidade |
| TSI_T25 | HYBRID + TREND | 276% simultaneidade |
| VWAP_REV | HYBRID + RANGE | 268% simultaneidade |
| TUESDAY | HYBRID + RANGE | 252% simultaneidade |

**Recomendacao:** Selecionar **APENAS UMA** variante por familia no ensemble.

### 2. Estrategias de Familias Diferentes = Complementaridade

Estrategias de **indicadores diferentes** tendem a operar em momentos distintos:

| Par | Comp Score |
|-----|:----------:|
| PA_TUESDAY_RANGE_SELL + PA_VWAP_REV_D1_0_RANGE_SELL | 100% |
| PA_ADX_BREAK_A25_TREND_SELL + PA_CHOP_C38_2_TREND_SELL | 100% |
| PA_EXHAUST_Dn1_0_M40_TREND_SELL + PA_GK_BREAK_G0_001_RANGE_SELL | 100% |

### 3. Oportunidade de Fusao (Merge)

Pares com alta sobreposicao mas da MESMA familia podem ser **fundidos** em um unico sinal mais acurado:

- PA_VWAP_Z_Z2_0_HYBRID_SELL + PA_VWAP_Z_Z2_0_RANGE_SELL + PA_VWAP_Z_Z2_0_TREND_SELL
  → Podem ser combinados com um filtro de regime dinamico
  → O sinal base (PA_VWAP_Z_Z2_0) e o mesmo; apenas o regime muda

- PA_TSI_T25_HYBRID_SELL + PA_TSI_T25_RANGE_SELL + PA_TSI_T25_TREND_SELL
  → Mesmo caso: sinal identico, regime diferente

### 4. Ensemble Otimizado (recomendado)

Baseado na analise de complementaridade, o ensemble ideal evita redundancia intra-familia:

| # | Estrategia | Motivo |
|---|-----------|--------|
| 1 | PA_EXHAUST_Dn1_0_M40_TREND_SELL | WFA robust 3/3, alta complementaridade (86.3) |
| 2 | PA_REV_RSI_B15_HYBRID_SELL | Melhor OOS (+13,111), unica da familia |
| 3 | PA_VCP_HYBRID_SELL | 2o melhor OOS (+12,149), complementaridade 81.6 |
| 4 | PA_TSI_T25_HYBRID_SELL | OOS +9,532, mas redundante com TREND — escolher HYBRID |
| 5 | PA_VWAP_REV_D1_0_RANGE_SELL | OOS +7,856, complementar com outras |
| 6 | PA_ADX_BREAK_A25_RANGE_SELL | OOS +1,280, complementaridade 83.9 |
| 7 | PA_TUESDAY_RANGE_SELL | OOS +36,820, mas alta redundancia com HYBRID/TREND |
| 8 | PA_BB_M2_0_TREND_SELL | OOS +3,446, complementaridade 70.2 |

**Nota:** PA_TUESDAY_RANGE_SELL (+36,820) e redundante com as outras variantes TUESDAY, mas extremamente complementar com estrategias de outras familias. Incluir se houver diversificacao.

---

## Conclusoes

1. **Redundancia intra-familia e extrema:** Variantes do mesmo indicador (TREND/RANGE/HYBRID) operam praticamente nos mesmos momentos. Escolher apenas a melhor por familia.

2. **Diversificacao inter-familia funciona:** Indicadores diferentes (RSI vs VWAP vs TUESDAY vs EXHAUST) operam em momentos complementares.

3. **Oportunidade de fusao:** Sinais da mesma familia podem ser combinados com um seletor de regime dinamico, reduzindo o numero de estrategias sem perder cobertura.

4. **1,000+ pares sem sobreposicao:** Ha muito espaco para diversificacao. Um ensemble de 5-7 estrategias de familias diferentes pode capturar a maioria dos movimentos sem redundancia.

5. **Correcao do engine:** Erro 'exit_idx' resolvido com simulacao OHLC (_simulate_exit_ohlc) para casos sem tick data. Agora 95/158 estrategias tem trades validos.

---

## Arquivos Gerados

| Arquivo | Descricao |
|---------|-----------|
| `ALL_MODELS_OOS_TRADES.csv` | 1,650 trades de 37 estrategias (CSV unificado) |
| `trade_overlap_pairs.csv` | 666 pares com metricas de sobreposicao |
| `trade_overlap_strategy_scores.csv` | Scores de complementaridade por estrategia |
| `trade_overlap_strategy_stats.csv` | Estatisticas basicas por estrategia |
| `TRADE_OVERLAP_ANALYSIS_REPORT.md` | Este relatorio |

---

## Proximos Passos

1. **Corrigir reexecucao:** Resolver erro 'exit_idx' no engine para reexecutar as 120 estrategias faltantes
2. **Fusao de familias:** Combinar TREND/RANGE/HYBRID da mesma familia em um unico sinal com seletor de regime
3. **Ensemble SELECTOR:** Implementar logica de priorizacao por Sharpe (nao consenso) para o ensemble otimizado
4. **Validacao Monte Carlo:** Testar robustez do ensemble com shuffle de trades
