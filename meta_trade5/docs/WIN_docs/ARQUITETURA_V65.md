# Arquitetura V6.5 — Orquestrador com Cycle Memory, A/B Validator e Ensemble Pipeline

## Problemas Identificados na V6.4

### 1. Análise DNA é Rasa
**Problema:** A "Fase 2" do orquestrador roda uma análise de 20 linhas que calcula apenas regime PnL, skew e hora/dow.
**Correto:** Deveria executar os 5 estágios do GUIA_ANALISE_DNA.md:
- Estágio 1: Processo Documentado (metadados do ciclo)
- Estágio 2: Correlação (indicador × PnL)
- Estágio 3: Segmentação (dow, hora, hit_type, regime, etc.)
- Estágio 4: DNA com Cohen's d (TP vs SL para cada indicador)
- Estágio 5: Síntese e Hipóteses

### 2. F2 Sempre Roda como Grid
**Problema:** Mesmo quando a hipótese é "excluir dow 3", o F2 roda 30 configs aleatórias do F1.
**Correto:** Quando temos uma hipótese específica, o F2 deve rodar como **teste A/B**:
- **Baseline:** Config vencedora do ciclo anterior SEM a hipótese
- **Hipótese:** Config vencedora do ciclo anterior COM a hipótese aplicada
- Compara direto: a hipótese melhorou ou piorou?

### 3. Ensemble Não Existe no Pipeline
**Problema:** O ensemble está documentado na Fase 4 mas nunca é executado.
**Correto:** Após N sinais passarem Go/No-Go individualmente, deve haver uma fase de **Ensemble Assembly** separada.

### 4. Sem Memória de Ciclos
**Problema:** O orquestrador não sabe o que aconteceu no Ciclo 1 quando está no Ciclo 3.
**Correto:** Cycle Memory mantém histórico completo com análise de progresso.

### 5. Sem Detecção de "Spinning"
**Problema:** Pode ficar excluindo dow 3, dow 5, dow 3, dow 5... para sempre.
**Correto:** Se o OOS não melhorar após 3 ciclos consecutivos, abortar ou mudar de abordagem.

---

## Nova Arquitetura V6.5

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 0: INIT (carrega dados, engines, cache — UMA VEZ)       │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 1: F1 GRID SEARCH (gera estratégias — só no ciclo 1)    │
│  ├── Para cada sinal: TP × SL × ATR grid (5,400 combos)        │
│  └── Salva top 30 configs por sinal                             │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 2: F2 VALIDATION (testa top configs com ticks IS)        │
│  ├── Ciclo 1: Grid dos top 30 do F1                            │
│  └── Ciclo N>1: Teste A/B (baseline vs hipótese)               │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 3: F3 SEARCH (refina top 3 configs)                      │
│  ├── Ciclo 1: Busca refinada nos top 20 do F2                  │
│  └── Ciclo N>1: Refina a config A/B vencedora                  │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 4: GUARDRAIL SWEEP (36 combos BE×HP×CD)                  │
│  └── Otimiza proteção de risco para a config vencedora         │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 5: OOS PRODUCTION (valida com ticks reais)              │
│  └── Gera trades_ciclo{N}.parquet                               │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 6: DNA ANALYSIS COMPLETA (GUIA_ANALISE_DNA.md)          │
│  ├── Estágio 1: Metadados do ciclo                             │
│  ├── Estágio 2: Correlação indicador × PnL                     │
│  ├── Estágio 3: Segmentação multidimensional                   │
│  ├── Estágio 4: DNA com Cohen's d (TP vs SL)                   │
│  └── Estágio 5: Síntese e formulação de hipóteses              │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 7: CYCLE MEMORY (análise de progresso)                  │
│  ├── Compara com ciclos anteriores                             │
│  ├── Detecta spinning (estagnação)                             │
│  └── Decide se continua, aborta, ou muda de abordagem          │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 8: ENSEMBLE ASSEMBLY (quando N sinais validados)        │
│  ├── Correlação de erros entre sinais                          │
│  ├── Testa min_votes [1, 2, ceil(N/2)]                         │
│  └── Otimiza pesos por Sharpe ratio                            │
├─────────────────────────────────────────────────────────────────┤
│  PHASE 9: HYPOTHESIS GENERATOR (próxima iteração)              │
│  ├── Ranking por efeito (Cohen's d)                            │
│  └── Phase Controller decide: F1? F2 A/B? Ensemble?            │
└─────────────────────────────────────────────────────────────────┘
```

---

## F2 A/B Validator (Novo)

Quando a hipótese é Tipo B (filtro temporal) ou Tipo C (guardrail):

```python
def f2_ab_test(engine, config_vencedora, hypothesis_patch, data_is):
    """Testa hipótese vs baseline com a mesma config."""
    
    # Baseline: config do ciclo anterior SEM a hipótese
    baseline_config = config_vencedora
    baseline_result = engine.simulate(baseline_config)
    
    # Hipótese: config do ciclo anterior COM a hipótese
    hypothesis_config = apply_patch(config_vencedora, hypothesis_patch)
    hypothesis_result = engine.simulate(hypothesis_config)
    
    # Comparação
    improvement = hypothesis_result['net'] - baseline_result['net']
    
    if improvement > 0:
        return {'status': 'ACCEPT', 'improvement': improvement}
    else:
        return {'status': 'REJECT', 'improvement': improvement}
```

**Vantagens:**
- Não roda 30 configs aleatórias — compara direto baseline vs hipótese
- Resultado em ~1s vs ~30s do grid
- Não depende do F1 quando a hipótese não muda TP/SL/ATR

---

## Cycle Memory (Novo)

```python
class CycleMemory:
    def __init__(self):
        self.cycles = []
    
    def add(self, cycle_result):
        self.cycles.append(cycle_result)
    
    def is_spinning(self, max_cycles=3):
        """Detecta se estamos girando em círculos."""
        if len(self.cycles) < max_cycles:
            return False
        
        recent = self.cycles[-max_cycles:]
        oos_nets = [c['oos_net'] for c in recent]
        
        # Se OOS não melhorou em N ciclos
        if all(n <= 0 for n in oos_nets):
            return True
        
        # Se estamos aplicando e removendo o mesmo filtro
        patches = [c['hypothesis']['patch'] for c in recent]
        # ... detecta oscilação
        
        return False
    
    def best_so_far(self):
        """Retorna o melhor ciclo até agora."""
        return max(self.cycles, key=lambda c: c['oos_net'])
```

---

## Phase Controller V2

```python
def phase_controller(previous_hypothesis, cycle_memory):
    """Decide QUAL pipeline rodar para a próxima iteração."""
    
    # Se estamos em spinning, aborta ou muda abordagem
    if cycle_memory.is_spinning():
        return {'action': 'ABORT', 'reason': 'Spinning detected'}
    
    # Se hipótese é Tipo A (parâmetros), precisa de F1
    if previous_hypothesis['type'] in ['tp_change', 'sl_change', 'tighten_regime']:
        return {
            'phases': ['F1', 'F2', 'F3', 'GUARDRAIL', 'OOS'],
            'mode': 'GRID',
            'reason': 'Parameter change requires full grid search'
        }
    
    # Se hipótese é Tipo B/C (filtro/guardrail), A/B test
    if previous_hypothesis['type'] in ['exclude_hour', 'exclude_dow', 'reduce_be']:
        return {
            'phases': ['F2', 'F3', 'GUARDRAIL', 'OOS'],
            'mode': 'AB_TEST',
            'reason': 'Temporal/guardrail hypothesis — A/B test'
        }
    
    # Se temos N sinais validados, ensemble
    if cycle_memory.n_validated_signals() >= 2:
        return {
            'phases': ['ENSEMBLE'],
            'mode': 'ENSEMBLE',
            'reason': 'Multiple signals validated — ensemble assembly'
        }
```

---

## Ensemble Pipeline (Nova Fase)

```python
def ensemble_pipeline(validated_signals, data):
    """Monta ensemble com sinais validados."""
    
    # 1. Filtra sinais com OOS_WR > 40% e OOS_Net > 0
    valid = [s for s in validated_signals 
             if s['oos_wr'] > 40 and s['oos_net'] > 0]
    
    # 2. Matriz de correlação de erros
    for i, s1 in enumerate(valid):
        for s2 in valid[i+1:]:
            corr = error_correlation(s1['trades'], s2['trades'])
            if corr > 0.7:
                # Remove de menor Sharpe
                remove = s1 if s1['sharpe'] < s2['sharpe'] else s2
                valid.remove(remove)
    
    # 3. Testa min_votes
    for min_v in [1, 2, math.ceil(len(valid)/2)]:
        ensemble = build_ensemble(valid, min_votes=min_v)
        result = simulate_ensemble(ensemble)
        print(f"min_votes={min_v}: OOS={result['net']:+d}")
    
    # 4. Pesos por Sharpe
    weights = {s['name']: s['sharpe'] / sum_sharpe for s in valid}
    
    return ensemble
```

---

## DNA Analysis Completa (Estágios 1-5)

```python
def dna_analysis_complete(trades, df_oos, cycle_num):
    """Executa análise DNA completa conforme GUIA_ANALISE_DNA.md."""
    
    report = {}
    
    # Estágio 1: Metadados
    report['metadata'] = {
        'cycle': cycle_num,
        'n_trades': len(trades),
        'oos_net': sum(t['pnl'] for t in trades),
        'date_range': get_date_range(trades),
    }
    
    # Estágio 2: Correlação
    report['correlation'] = {}
    for indicator in ['EMA5_SLOPE', 'dist', 'ATR', 'ADX7', 'RSI14']:
        corr = pearsonr(trades['pnl'], trades[indicator])
        report['correlation'][indicator] = {'r': corr[0], 'p': corr[1]}
    
    # Estágio 3: Segmentação
    report['segmentation'] = {}
    for dimension in ['dow', 'hour', 'regime_label', 'hit_type']:
        report['segmentation'][dimension] = segment_by_dimension(trades, dimension)
    
    # Estágio 4: DNA com Cohen's d
    report['dna'] = {}
    wins = trades[trades['pnl'] > 0]
    losses = trades[trades['pnl'] < 0]
    for indicator in ['EMA5_SLOPE', 'dist', 'ATR']:
        d = cohen_d(wins[indicator], losses[indicator])
        report['dna'][indicator] = {'d': d, 'effect': effect_size_label(d)}
    
    # Estágio 5: Síntese
    report['hypotheses'] = generate_hypotheses_from_dna(report)
    
    return report
```

---

## Mudanças no Orchestrator

### Estrutura de Dados
```python
# CycleResult — o que é salvo a cada ciclo
CycleResult = {
    'cycle': int,
    'config': dict,           # Config vencedora
    'baseline_config': dict,  # Config SEM hipótese (para A/B)
    'hypothesis': dict,       # Hipótese aplicada
    'result': dict,           # Resultados OOS
    'dna_report': dict,       # Análise DNA completa
    'phases_run': list,       # Quais fases rodaram
    'mode': str,              # 'GRID' | 'AB_TEST' | 'ENSEMBLE'
}

# CycleMemory — histórico completo
CycleMemory = {
    'cycles': [CycleResult],
    'best_cycle': CycleResult,
    'validated_signals': [SignalResult],
    'ensemble_result': EnsembleResult,
}
```

### Pipeline Principal
```python
def orchestrator_v65(strategy_config, max_cycles=10):
    data = load_data_once()
    memory = CycleMemory()
    
    for cycle in range(1, max_cycles + 1):
        # Phase Controller decide modo
        controller = phase_controller(memory)
        
        if controller['mode'] == 'GRID':
            result = run_grid_cycle(data, strategy_config, cycle)
        elif controller['mode'] == 'AB_TEST':
            result = run_ab_test_cycle(data, strategy_config, cycle, memory)
        elif controller['mode'] == 'ENSEMBLE':
            result = run_ensemble_cycle(data, memory)
        
        # DNA Analysis completa
        dna = dna_analysis_complete(result['trades'], data['df_oos'], cycle)
        
        # Cycle Memory
        memory.add({
            'cycle': cycle,
            'config': result['config'],
            'result': result,
            'dna': dna,
            'mode': controller['mode'],
        })
        
        # Detect spinning
        if memory.is_spinning():
            print("🛑 SPINNING DETECTED — aborting")
            break
        
        # Gerar hipótese
        hypothesis = generate_hypothesis(dna, memory)
        
        # Aplicar hipótese
        strategy_config = apply_hypothesis(strategy_config, hypothesis)
```

---

## Critérios de Sucesso da V6.5

1. ✅ F1 só roda no ciclo 1 (ou quando hipótese muda TP/SL/ATR)
2. ✅ F2 roda como A/B quando hipótese é filtro/guardrail
3. ✅ DNA Analysis executa os 5 estágios completos
4. ✅ Cycle Memory detecta spinning e aborta
5. ✅ Ensemble é uma fase separada após validação individual
6. ✅ Phase Controller decide automaticamente qual pipeline usar
7. ✅ Cada ciclo é comparável com ciclos anteriores
8. ✅ Resultados são salvos em formato estruturado (JSON)

---

## Arquivos a Modificar

1. `scripts/orchestrator.py` — Refatorar completamente
2. `scripts/dna_analysis.py` — Novo módulo com análise completa
3. `scripts/ensemble_pipeline.py` — Novo módulo para ensemble
4. `docs/WIN_docs/GUIA_CICLOS.md` — Atualizar documentação
5. `docs/WIN_docs/ciclo14_relatorio_final.md` — Referenciar nova arquitetura
