# MAPEAMENTO DE GAPS: GUIA_CICLOS.md vs orchestrator_v65.py

## Data: 2026-05-03
## Versao: V7.4.5 — Gap Analysis

---

## Resumo Executivo

O pipeline atual (`orchestrator_v65.py`) executa apenas **30-40%** do processo descrito em `GUIA_CICLOS.md`. As etapas de otimizacao de guardrails avancados (F1 Multi-Grid, tape reading, S/R, hour filter no pipeline completo) foram omitidas ou hardcoded. Isso explica por que:
- BE/HP sao "otimizados" em Guardrail Sweep isolado (pos-F3), nao no F1 Multi-Grid
- Filtro de horario (9:30-12h) so existe no F1, mas **76% dos trades escapam** em F2/F3/OOS
- Tape reading (CVD/Book) e S/R nunca foram testados no pipeline
- Matriz de Veto e Dynamic Weighting nao existem no codigo

---

## Gap 1: F1 Multi-Grid Ausente [CRITICO]

### O que o guia diz (GUIA_CICLOS.md, Etapa 1):
```
F1 Multi-Grid otimiza simultaneamente:
- TP (x ATR): 11 valores
- SL (x ATR): 9 valores  
- ATR min/max: 3x3
- BE trigger: 3 valores (100, 200, 999999)
- H-Progress candles: 3 valores
- Cooldown candles: 3 valores
- CVD filter: 2 modos (on/off)
- Book Imbalance filter: 2 modos (on/off)
Total: ~288K combos por estrategia
```

### O que o orchestrator faz (linhas 425-443):
```python
# APENAS TP x SL x ATR_MIN x ATR_MAX
for tp in current_tp_grid:           # 15 valores
    for sl in current_sl_grid:       # 10 valores
        for atr_mn in current_atr_min_grid:   # 5 valores
            for atr_mx in current_atr_max_grid: # 9 valores
                net, n = f1_eval(...)
```
**Total real: ~6.750 combos por estrategia (vs 288K do guia)**

### Impacto:
- BE/HP/CD sao otimizados SEPARADAMENTE no Guardrail Sweep (pos-F3), ignorando correlacao com TP/SL
- CVD/Book nunca sao testados
- O grid nao explora interacoes criticas (ex: BE=100 com HP=1 vs BE=100 com HP=3)

### Correcao necessaria:
Incluir BE_TRIGGERS, HP_CANDLES, COOLDOWN_CANDLES no broadcast do F1. Avaliar se CVD/Book columns existem nos dados antes de ativar.

---

## Gap 2: Filtro de Horario SOMENTE no F1 [CRITICO]

### O que o orchestrator faz (linhas 433-439):
```python
# V7.4: Time filter for TREND signals (9:30-12:00)
hm_val = 9.5 if regime == 'trend' else 0.0
hx_val = 12.0 if regime == 'trend' else 24.0
net, n = f1_eval(..., hm=hm_val, hx=hx_val, ...)
```

### O que build_config faz (linha 323):
```python
cfg = {'name': s['name'], 'hour_min': 0.0, 'hour_max': 24.0, ...}
```

### Impacto:
- F1 filtra entradas em Feb (hm=9.5, hx=12.0)
- F2/F3/OOS usam hour_min=0.0, hour_max=24.0
- **Resultado: 76% dos trades OOS ocorrem FORA do horario filtrado**
- Overfit massivo: F1 +124K -> OOS -2.8K

### Correcao necessaria:
Passar `hour_min`/`hour_max` para `build_config()` e para o engine em TODAS as fases (F1, F2, F3, Guardrail, OOS).

---

## Gap 3: Tape Reading (CVD/Book) Nao Implementado [ALTO]

### O que o guia diz:
```
CVD filter: 2 modos (on/off)
Book Imbalance filter: 2 modos (on/off)
```

### O que o orchestrator faz:
**NENHUMA referencia a CVD ou Book_Imbalance no codigo.**

### Impacto:
- Dados de microestrutura (Book_Imbalance, CVD) existem em `super_win_continuous.parquet` mas nao sao usados
- Potencial edge nao explorado

### Correcao necessaria:
Adicionar `use_cvd` e `use_book` ao F1 Multi-Grid. Verificar se colunas existem nos dados.

---

## Gap 4: S/R (Support/Resistance) Nao Implementado [ALTO]

### O que o guia diz:
O guia menciona S/R buffers como parte da gestao de risco, mas nao detalha implementacao.

### O que o orchestrator faz:
**Nenhum codigo de S/R.**

### Impacto:
- Entradas proximas a niveis de suporte/resistencia nao sao filtradas
- SL pode ser colocado em niveis invalidos

### Correcao necessaria:
Investigar se o engine suporta S/R. Se sim, adicionar ao pipeline. Se nao, documentar como limitacao.

---

## Gap 5: Matriz de Veto Ausente [MEDIO]

### O que o guia diz (Etapa 2):
```
Matriz de Veto: calcula correlacao de ERROS entre pares de estrategias
Se correlacao > 0.7: a de menor Sharpe eh removida
```

### O que o orchestrator faz:
**Nenhum codigo de correlacao de erros.** O ensemble usa modo SELECTOR (prioriza por peso), nao veto.

### Impacto:
- Estrategias redundantes podem entrar no ensemble
- Amplificacao de erros quando 2+ estrategias erram juntas

### Correcao necessaria:
Implementar `matriz_veto.py` e integrar ao ensemble assembly.

---

## Gap 6: Dynamic Weighting Ausente [MEDIO]

### O que o guia diz (Etapa 3):
```
peso_i = Sharpe_i / (1 + max_corr_i)
```

### O que o orchestrator faz:
Pesos sao fixos por `oos_net` (linha 1121):
```python
'weight': max(0.5, min(2.0, result['oos_net'] / 500))
```

### Impacto:
- Pesos nao consideram volatilidade (Sharpe) nem correlacao de erros
- Estrategia com PnL alto mas volatilidade extrema pode dominar

### Correcao necessaria:
Implementar calculo de pesos por Sharpe penalizado por correlacao.

---

## Gap 7: Circuit Breaker / Daily Stop Hardcoded [MEDIO]

### O que o guia diz:
```
Sanity check: rejeitar configs com overfit_ratio > 10x
Sanity check: rejeitar BE > 500
```

### O que o orchestrator faz:
- `hard_stop: 500` hardcoded em build_config()
- `slope_decay: 0.50` hardcoded
- `grace_candles: 2` hardcoded
- Overfit ratio check existe apenas em `should_stop_per_signal` (indireto)
- Daily stop loss: **nao implementado**
- Circuit breaker (max consecutive losses): **nao implementado**

### Impacto:
- Guardrails fixos podem nao ser otimos para todas as estrategias
- Sem daily stop: um dia ruim pode zerar o mes

### Correcao necessaria:
Adicionar daily_stop e circuit_breaker ao Guardrail Sweep.

---

## Gap 8: F3 Trades Nao Sao Todos Salvos [BAIXO]

### O que o usuario pediu:
```
sempre que executar o f3 tem que ser salvo o arquivo com todos os trades do top 1 de cada estrategia
```

### O que o orchestrator faz (linhas 597-608):
Salva F3 trades do BEST config apenas para unified file.
Mas OOS trades SAO salvos individualmente (linha 663: `save_trades(res_oos, ...)`).

### Verificacao:
O arquivo `V71_UNIFIED_TRADES_F3.csv` existe e tem trades F3 do top 1.
O arquivo de trades OOS `trades_c{cycle}_{signal}.csv` tambem existe.

### Status:
**NAO EH GAP.** Os trades estao sendo salvos. O usuario pode estar confuso sobre qual arquivo contem qual dados.

---

## Prioridade de Correcoes para E2E

Para o teste E2E com PA_SIGNAL_DIR_TREND_SELL, precisamos:

1. **[CRITICO]** Passar hour_min/hour_max para build_config() e engine (F2/F3/OOS)
2. **[CRITICO]** Incluir BE/HP/CD no F1 grid (multi-grid)
3. **[ALTO]** Adicionar CVD/Book ao grid (se dados existirem)
4. **[MEDIO]** Adicionar daily_stop e circuit_breaker ao Guardrail Sweep
5. **[BAIXO]** Documentar que Matriz de Veto e Dynamic Weighting sao features futuras

---

## Justificativa para o Usuario

**Por que esses gaps existem?**

1. **F1 Multi-Grid omitido por performance:** O guia V6.3 menciona 288K combos processados em 1.5s (200K/s). Mas o F1 atual (`f1_fast_screener`) processa ~6K combos/s. 288K levariam ~48s por estrategia — aceitavel, mas nao foi implementado.

2. **Hour filter no F1 apenas:** Foi adicionado como patch rapido (V7.4) para conter overfit de TREND signals, mas nao foi propagado para o engine. Esqueceu-se de passar hm/hx para `build_config()`.

3. **Tape/SR omitidos:** O pipeline foi construido iterativamente (V6.1 -> V6.8). CVD/Book foram adicionados aos dados (V139+) mas nunca integrados ao orquestrador.

4. **Matriz de Veto / Dynamic Weighting:** Sao etapas de "Etapa 2/3" do guia V6.3, mas o pipeline evoluiu para modo SELECTOR (V6.6+). Essas features ficaram para "implementacao futura".

---

## Proximos Passos

1. Modificar `orchestrator_v65.py`:
   - `build_config()`: aceitar hour_min/hour_max
   - `run_grid_cycle()`: passar hm/hx para build_config em F2/F3/OOS
   - `run_grid_cycle()`: expandir F1 para incluir BE/HP/CD

2. Verificar existencia de colunas CVD/Book nos dados

3. Adicionar daily_stop e circuit_breaker ao Guardrail Sweep

4. Executar E2E com PA_SIGNAL_DIR_TREND_SELL

5. Salvar relatorio em .md
