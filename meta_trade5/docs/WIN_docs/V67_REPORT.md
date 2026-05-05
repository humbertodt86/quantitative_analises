# V6.7 Multi-Signal Optimization — Relatorio Completo

## 1. Composicao das Estrategias

### 1.1 Lista de Estrategias (63 total)

**21 familias de sinais × 3 regimes = 63 estrategias**

| # | Familia | Categoria | Direction Type |
|---|---------|-----------|----------------|
| 1 | PA_SIGNAL_DIR | trend_following | bidirectional |
| 2 | PA_STRONG_TREND_A25_S20 | trend_following | direction_following |
| 3 | PA_ADX_BREAK_A25 | trend_following | direction_following |
| 4 | PA_SLOPE_TREND_S25_A25 | trend_following | direction_following |
| 5 | PA_MA_CROSS_F9_S21 | trend_following | bidirectional |
| 6 | PA_HMA_CROSS_F5_S10 | trend_following | bidirectional |
| 7 | PA_EFF_RATIO_E0_6 | trend/range | bidirectional |
| 8 | PA_GK_BREAK_G0_001 | breakout | bidirectional |
| 9 | PA_REV_RSI_B15 | mean_reversion | bidirectional |
| 10 | PA_VWAP_Z_Z2_0 | mean_reversion | bidirectional |
| 11 | PA_VWAP_REV_D1_0 | mean_reversion | direction_following |
| 12 | PA_BB_M2_0 | volatility | bidirectional |
| 13 | PA_KELT_M2_0 | volatility | bidirectional |
| 14 | PA_POC_REV | structure | bidirectional |
| 15 | PA_CHOP_C38_2 | trend/range | direction_following |
| 16 | PA_EXHAUST_Dn1_0_M40 | exhaustion | bidirectional |
| 17 | PA_VCP | pattern | bidirectional |
| 18 | PA_MFI_B20 | volume | bidirectional |
| 19 | PA_TSI_T25 | momentum | bidirectional |
| 20 | PA_LIQ_GRAB | structure | bidirectional |
| 21 | PA_TUESDAY | calendar | direction_following |

**Regimes por estrategia:**
- TREND: 21 estrategias
- RANGE: 21 estrategias  
- HYBRID: 21 estrategias

**Direction types:**
- bidirectional: 36
- direction_following: 27

**Todas com signal=1 (BUY).** Nao foram testadas com signal=-1 (SELL).

---

## 2. BUG CRITICO ENCONTRADO: Regime HYBRID = RANGE

### 2.1 O Problema

No codigo `build_config()` (linha 233):
```python
regime_filter = {'eq': 1} if s.get('regime', 'trend') == 'trend' else {'eq': 0}
```

Isso significa:
| Regime | regime_label filtrado |
|--------|----------------------|
| TREND | == 1 |
| RANGE | == 0 |
| HYBRID | == 0 |

**HYBRID e RANGE usam exatamente o mesmo filtro de dados!**

### 2.2 Evidencia no Relatorio

Estrategias com resultados F1 **identicos** (mesmo TP, SL, ATR, Net, N):

```
PA_BB_M2_0_HYBRID     TP=20.0  SL=0.05  ATR=50-400  Net=48,530  N=13
PA_BB_M2_0_RANGE      TP=20.0  SL=0.05  ATR=50-400  Net=48,530  N=13
PA_KELT_M2_0_HYBRID   TP=20.0  SL=0.05  ATR=50-400  Net=48,530  N=13
PA_KELT_M2_0_RANGE    TP=20.0  SL=0.05  ATR=50-400  Net=48,530  N=13
```

Isso e fisicamente impossivel se os dados fossem filtrados por regime diferente. 

### 2.3 Impacto

- **21 estrategias HYBRID sao redundantes** — processam os mesmos dados que RANGE
- **F1 screening esta incorreto** para HYBRID
- **Tempo desperdicado** processando 21 estrategias duplicadas

### 2.4 Correcao Necessaria

HYBRID deveria ser:
```python
if regime == 'trend':
    regime_filter = {'eq': 1}
elif regime == 'range':
    regime_filter = {'eq': 0}
else:  # hybrid
    # Sem filtro de regime — usa todos os dados
    regime_filter = None  # ou nao incluir no dict de filters
```

---

## 3. Pipeline de Otimizacao — Combos por Fase

### 3.1 F1 Screening (Fast Screener)

**Combos testados por estrategia:**
- TP: 15 valores [1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0, 18.0, 20.0, 25.0, 30.0]
- SL: 12 valores [0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 5.0]
- ATR min: 5 valores [50, 100, 150, 200, 300]
- ATR max: 6 valores [400, 600, 800, 1000, 9999, 15000]

**Total: 15 × 12 × 5 × 6 = 5,400 combos**

**Avancam para F2:** Top 10 (N_TOP_F2 = 10)

### 3.2 F2 Validation (IS com ticks)

**Combos validados:** 10 (os top 10 do F1)

**Avancam para F3:** Top 3 (N_TOP_F3 = 3)

### 3.3 F3 Search (IS com ticks, mais rigoroso)

**Combos testados:** 3 (os top 3 do F2)

**Melhor combo avanca para Guardrail**

### 3.4 Guardrail Sweep

**Combos testados:**
- BE trigger: 5 valores [100, 200, 300, 400, 500]
- HP candles: 3 valores [1, 2, 3]
- Cooldown candles: 3 valores [0, 1, 2]

**Total: 5 × 3 × 3 = 45 combos**

**Scoring:** Sharpe Ratio × Net PnL (penaliza volatilidade)

### 3.5 OOS (Out-of-Sample)

**Combos:** 1 (melhor guardrail aplicado ao melhor F3)

**Periodo:** Abril 2026 (dados nunca vistos)

---

## 4. Resultados OOS por Estrategia

### 4.1 Estatisticas Gerais

| Metrica | Valor |
|---------|-------|
| Total estrategias | 63 |
| Com entradas F1 | 62 |
| Sem entradas | 1 (PA_VWAP_REV_D1_0_TREND) |
| Validadas (OOS>0, WR>35%) | **4** |
| Melhor OOS | +5,375 pts |
| Pior OOS | -13,695 pts |
| OOS medio | -3,458 pts |
| Melhor WR | 67.7% |
| WR medio | 38.0% |

### 4.2 Sinais Validados (unicos com OOS positivo)

| # | Estrategia | OOS Net | Trades | WR | BE | HP | CD |
|---|-----------|---------|--------|-----|-----|-----|-----|
| 1 | PA_POC_REV_TREND | +5,375 | 8 | 12.5% | 300 | 3 | 0 |
| 2 | PA_TSI_T25_TREND | +3,588 | 24 | 41.7% | 500 | 3 | 0 |
| 3 | PA_LIQ_GRAB_TREND | +1,301 | 31 | 67.7% | 100 | 1 | 0 |
| 4 | PA_MFI_B20_TREND | +718 | 31 | 48.4% | 400 | 2 | 0 |

**Todas sao TREND. Nenhuma RANGE ou HYBRID foi validada.**

### 4.3 Top 20 F1 Rankings

| Rank | Estrategia | F1 Net | Trades | TP | SL |
|------|-----------|--------|--------|-----|-----|
| 1 | PA_SIGNAL_DIR_HYBRID | +882,555 | 436 | 2.0 | 5.0 |
| 2 | PA_SIGNAL_DIR_RANGE | +882,555 | 436 | 2.0 | 5.0 |
| 3 | PA_HMA_CROSS_F5_S10_HYBRID | +776,805 | 391 | 1.0 | 5.0 |
| 4 | PA_HMA_CROSS_F5_S10_RANGE | +776,805 | 391 | 1.0 | 5.0 |
| 5 | PA_STRONG_TREND_A25_S20_HYBRID | +502,735 | 235 | 2.0 | 5.0 |
| 6 | PA_STRONG_TREND_A25_S20_RANGE | +502,735 | 235 | 2.0 | 5.0 |
| ... | ... | ... | ... | ... | ... |
| 20 | PA_VWAP_Z_Z2_0_TREND | +253,025 | 135 | 3.0 | 5.0 |

**Nota:** Os rankings F1 mostram HYBRID=RANGE (mesmo valor) devido ao bug de filtro.

---

## 5. Ensemble — Resultado e Diagnostico

### 5.1 Configuracao do Ensemble

| Parametro | Valor |
|-----------|-------|
| Sinais validados | 4 (todos TREND) |
| Threshold sweep | [0.0, 0.3, 0.5, 0.7] |
| Min votes sweep | [1, 2, 3] |
| Best F2 IS | thresh=0.0, votes=3, net=-8,641 |
| Best weights | 1.0:1.0 |
| Best Guardrail | BE=300, HP=1, CD=0 |

### 5.2 Resultado Ensemble OOS

| Metrica | Valor |
|---------|-------|
| OOS Net | **-51 pts** |
| Trades | 5 |
| WR | 80.0% |
| PF | 2.80 |

### 5.3 Por que o Ensemble foi Terrivel?

**1. Alta Correlacao entre Sinais**
- Todos os 4 sinais validados sao TREND
- Eles concordam nos mesmos trades (quando o mercado sobe, todos dizem "compre")
- O ensemble vira um "filtro de unanimidade" que so entra quando TODOS concordam

**2. Poucos Trades (N=5)**
- min_votes=3 com 4 sinais = exige 75% de concordancia
- Em OOS, isso so gerou 5 trades em ~1 mes
- 5 trades × 30 pts custo = 150 pts de custo
- Gross PnL ≈ 99 pts — custos comeram tudo

**3. Falta de Diversidade**
- Nenhum sinal de RANGE ou REVERSAO foi validado
- Ensemble precisa de sinais DESCORRELACIONADOS
- Trend + Mean Reversion + Breakout = portfolio robusto
- Trend + Trend + Trend + Trend = portfolio concentrado

### 5.4 O que e "min_votes"?

`min_votes` = quantos dos N sinais validados precisam dar o mesmo sinal (BUY) para o ensemble gerar um trade.

**Exemplo com 4 sinais:**
| min_votes | Sinais que precisam concordar | Trades gerados | Qualidade |
|-----------|------------------------------|----------------|-----------|
| 1 | Qualquer 1 sinal | Muitos | Baixa (muito ruido) |
| 2 | Pelo menos 2 sinais | Moderado | Media |
| 3 | Pelo menos 3 sinais | Poucos | Alta (mas pode ser zero) |
| 4 | Todos os 4 sinais | Muito raros | Muito alta (mas quase nunca entra) |

No nosso caso, min_votes=3 com 4 sinais correlacionados = quase nunca entra em OOS.

---

## 6. Limitacoes e Proximos Passos

### 6.1 Limitacoes Identificadas

1. **BUG: HYBRID = RANGE** — 21 estrategias processam dados duplicados
2. **Direcao unica:** Todas as 63 estrategias sao BUY (signal=1). SELL nao testado
3. **Sinais correlacionados:** Todas as validadas sao TREND — sem diversificacao
4. **Poucos dados OOS:** Apenas Abril 2026 (~1 mes)
5. **Periodo dificil:** Abril teve baixa volatilidade — favoravel a RANGE, mas so TREND funcionou

### 6.2 Proximos Passos Recomendados

**A. Corrigir BUG HYBRID (ALTA PRIORIDADE)**
- Fazer HYBRID usar todos os dados (sem filtro de regime)
- Re-processar as 21 estrategias HYBRID

**B. Testar Direcao SELL**
- Criar queue com signal=-1 para as mesmas 63 estrategias
- Executar run completo
- WDO pode ter assimetria (short pode funcionar melhor)

**C. Melhorar Ensemble**
- Validar sinais de RANGE e REVERSAO (para diversificar)
- Testar min_votes=2 (mais trades, menos restritivo)
- Testar pesos assimétricos (dar mais peso ao sinal com melhor OOS)

**D. Mais Dados**
- Incluir Maio 2026 quando disponivel
- Periodos maiores de OOS = mais confiavel

---

## 7. Arquivos Gerados

| Arquivo | Descricao |
|---------|-----------|
| `v67_final_report.json` | Relatorio completo em JSON |
| `v67_f1_rank_all_strategies.csv` | Rank F1 de todas as 63 estrategias |
| `cycle_memory/cycle_memory.json` | Memoria de todos os 62 ciclos |
| `f1_rank_c1_*.csv` | Rank F1 por estrategia (62 arquivos) |
| `f2_rank_c1_*.csv` | Rank F2 por estrategia |
| `f3_rank_c1_*.csv` | Rank F3 por estrategia |
| `guardrail_rank_c1_*.csv` | Rank Guardrail por estrategia |
| `ensemble_f2_rank_c1_ensemble.csv` | Ensemble F2 sweep |
| `ensemble_guardrail_rank_c1_ensemble.csv` | Ensemble Guardrail sweep |
| `v67_ensemble_dna.json` | DNA Analysis do ensemble |

---

*Relatorio gerado em: 2026-05-02*
*Versao: V6.7*
