# PLANO DE IMPLEMENTAÇÃO V8.7 — F2 OTIMIZAÇÃO

**Data**: 2026-05-04
**Status**: Em execução

---

## OBJETIVO

Implementar **F2 — Otimização Completa** que consolida TODAS as otimizações de gestão de risco em um único script.

---

## ESCOPO DO F2

### O Que F2 Otimiza

| Categoria | Parâmetros | Valores | Total |
|-----------|------------|---------|-------|
| **TP/SL/ATR (Refino)** | TP_MULT, SL_MULT, ATR_MIN, ATR_MAX | 3 valores cada | 81 combos |
| **S/R Buffers** | TP_SR_PCT, SL_SR_PCT | 4×4 valores | 16 combos |
| **Gestão de Custo** | BE, GRACE, COOLDOWN, MAX_SL, SLOPE | 3×3×3×3×3 | 243 combos |
| **Filtros** | BOOK_IMB, CUM_DELTA | 3×3 valores | 9 combos |

**Total por config F1**: 81 × 16 × 243 × 9 = **2,834,352 combinações**

**COMO FAZER VIÁVEL**:
- Grid hierárquico (grosso → fino)
- Early stopping (descarta ruins rápido)
- Paralelização (10 workers)
- **Tempo alvo**: 5-10 minutos por sinal

---

## ARQUIVOS A CRIAR/MODIFICAR

### 1. `engines/f2_optimization_v87.py` (CRIAR)

**Função**: Otimização completa de gestão de risco.

**Input**: Top 10 configs do F1 (por sinal)

**Output**: Top 3 configs por sinal

**Estrutura**:
```python
# F2_OPTIMIZATION_V87.PY
# =======================

def optimize_f2(config_f1, df_variants):
    """
    Otimiza todos parâmetros de gestão de risco.
    
    Args:
        config_f1: Dict com TP/SL/ATR do F1
        df_variants: DataFrame com sinais + indicadores
    
    Returns:
        top3_configs: Lista com 3 melhores configs
    """
    # 1. Grid hierárquico
    # 2. Execução paralela
    # 3. Early stopping
    # 4. Ranking por Sharpe × PnL
    pass
```

---

### 2. `backtest/indicators_sr.py` (CRIAR)

**Função**: Calcular S/R, Book Imbalance, Tape Reading, Concentration Zones.

**Indicadores**:
- S/R levels intraday
- Book imbalance
- Cumulative delta
- Concentration zones (POC)

**Output**: Adiciona colunas ao DataFrame

---

### 3. `build_win_signals_v87.py` (MODIFICAR)

**Adicionar**:
- Import de `indicators_sr.py`
- Cálculo de S/R, Book Imbalance, Tape Reading
- Salvar no parquet de saída

---

### 4. `dna_analysis_v87_final.py` (CRIAR)

**Evoluir de**: `dna_analysis_v87.py`

**Adicionar**:
- Projeção de PnL com guardrails
- Sugestão de guardrails heurísticos
- Trade-off analysis (PnL vs Trades)

---

## CRITÉRIOS DE ACEITAÇÃO

- [ ] F2 executa em < 10 minutos por sinal
- [ ] Top 3 configs são estáveis (reprodutíveis)
- [ ] S/R buffers estão funcionando
- [ ] Book Imbalance e Tape Reading estão no parquet
- [ ] DNA Analysis gera projeção de guardrails
- [ ] Documentação atualizada (FLUXO_OTIMIZACAO_V87_FINAL.md)

---

## RISCOS E MITIGAÇÃO

| Risco | Mitigação |
|-------|-----------|
| F2 muito lento (> 30 min) | Grid hierárquico + early stopping |
| S/R não funciona em backtest | Usar S/R de sessões anteriores (lookback 1-5 dias) |
| Book Imbalance sem dados | Usar proxy (tick direction) |
| Memória estoura | Processar em batches, salvar intermediários |

---

## TIMELINE ESTIMADA

| Tarefa | Tempo | Status |
|--------|-------|--------|
| Criar f2_optimization_v87.py | 30 min | ✅ Concluído |
| Integrar GridAdvisor no F2 | 25 min | ✅ Concluído |
| Criar indicators_sr.py | 20 min | ✅ Concluído |
| Modificar build_win_signals_v87.py | 15 min | ✅ Concluído |
| Criar dna_analysis_v87_final.py | 25 min | ✅ Concluído |
| Testar F0 (build_win_signals_v87.py) | 15 min | ✅ Concluído — 22 sinais × 18 variantes |
| Testar F1 (f1_full_scan_v87_test.py) | 15 min | ✅ Concluído — PA_SIGNAL_DIR: +136K PnL, 615 trades, 51.9% WR |
| Testar F2 com GridAdvisor | 30 min | ⏳ Pendente |
| Testar F4 (dna_analysis_v87_final.py) | 15 min | ⏳ Pendente |
| **Total** | **~3.5 horas** | **70% concluído** |

---

## PRÓXIMOS PASSOS

1. **Executar F2 com GridAdvisor**: `engines/f2_optimization_v87.py` (sub-ciclos ZOOM/EXPAND)
2. **Executar F4**: `scripts/dna_analysis_v87_final.py` (DNA + projeção de guardrails)
3. **Criar F5**: `scripts/ensemble_overlap_matrix.py` (matriz de overlap para 23 sinais)
4. **Criar F6**: `engines/f3_ensemble_optimization.py` (otimização de pesos do ensemble)

---

## ARQUIVOS ATUALIZADOS

| Arquivo | Descrição | Status |
|---------|-----------|--------|
| `engines/f2_optimization_v87.py` | F2 com GridAdvisor integrado | ✅ Reescrito |
| `docs/WIN_docs/F2_GRID_ADVISOR_INTEGRACAO.md` | Documentação técnica do GridAdvisor | ✅ Criado |
| `docs/WIN_docs/FLUXO_OTIMIZACAO_V87_FINAL.md` | Fluxo completo atualizado | ✅ Atualizado |
| `docs/WIN_docs/PLANO_IMPLEMENTACAO_F2.md` | Plano de implementação | ✅ Atualizado |


---

**Próxima Ação**: Implementar `engines/f2_optimization_v87.py`
