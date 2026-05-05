# Arquitetura V6.7 — Multi-Signal Optimization Pipeline

## O Problema do V6.6

O V6.6 é um **otimizador de sinal único**. Ele recebe `--col=PA_SIGNAL_DIR --signal=1` e roda ciclos F1→F2→F3→Guardrail→OOS para ESSE sinal apenas. Ele nunca descobre que `PA_REV_RSI` ou `PA_SLOPE_TREND` poderiam ser melhores. E quando termina, não tem mecanismo para "passar para o próximo sinal".

## O Fluxo Correto (Multi-Signal)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  FASE 0: SIGNAL DISCOVERY (Por Regime)                                      │
│  ├── Carrega parquet e calcula regime (Trend vs Range)                     │
│  ├── F1 Grid Search em TODOS os sinais (3 execuções por sinal):            │
│  │   ├── F1 Trend: apenas candles em regime de tendência                  │
│  │   ├── F1 Range: apenas candles em regime de range                      │
│  │   └── F1 Híbrido: todos os candles, ranqueado por Sharpe               │
│  ├── Gera 3 rankings distintos:                                            │
│  │   ├── docs/WIN_docs/f1_rank_trend.json                                  │
│  │   ├── docs/WIN_docs/f1_rank_range.json                                  │
│  │   └── docs/WIN_docs/f1_rank_hybrid.json                                 │
│  └── Seleciona top N de cada categoria para otimização                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  FASE 1: INDIVIDUAL OPTIMIZATION (um sinal por vez)                         │
│  ├── Para cada sinal na queue:                                              │
│  │   ├── Ciclo 1: GRID (F1→F2→F3→Guardrail→OOS)                            │
│  │   ├── Ciclo 2+: AB_TEST com hipóteses DNA                                │
│  │   ├── Critério de parada por sinal:                                      │
│  │   │   • Spinning detectado (3 ciclos sem melhora)                        │
│  │   │   • OOS > 0 e WR > 35% (sinal validado!)                            │
│  │   │   • Hipóteses esgotadas                                              │
│  │   │   • Max ciclos atingido                                              │
│  │   └── Ao parar: salva config otimizada em validated_signals              │
│  └── Salva: docs/WIN_docs/signal_configs_optimized.json                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  FASE 2: ENSEMBLE BUILD (só após todos os sinais otimizados)               │
│  ├── Lê validated_signals (sinais com OOS > 0)                              │
│  ├── Análise de complementaridade:                                          │
│  │   • Correlação dos trades por dia/hora                                   │
│  │   • Regime-specific performance (trend vs range)                         │
│  │   • Identifica sinais concorrentes (mesmos candles) vs complementares   │
│  ├── Gera combinações de 3-5 sinais complementares                          │
│  └── Salva: docs/WIN_docs/ensemble_candidates.json                          │
├─────────────────────────────────────────────────────────────────────────────┤
│  FASE 3: ENSEMBLE OPTIMIZATION                                              │
│  ├── Para cada combinação candidata:                                        │
│  │   ├── F2 IS: Sweep ensemble_threshold [0.0, 0.3, 0.5, 0.7]              │
│  │   ├── F2 IS: Sweep ensemble_min_votes [1, 2, 3]                          │
│  │   ├── F2 IS: Sweep weight ratios [1:1, 2:1, 1:2, 1.5:0.5]              │
│  │   ├── F3 IS: Valida top-3 configs de ensemble                            │
│  │   ├── Guardrail: Grid BE/HP/CD para o ensemble vencedor                 │
│  │   ├── OOS: Validação final                                               │
│  │   └── DNA Analysis nos trades do ensemble                                │
│  └── Salva: docs/WIN_docs/ensemble_f3_rank.json                            │
├─────────────────────────────────────────────────────────────────────────────┤
│  FASE 4: DECISÃO MANUAL                                                     │
│  ├── Review dos arquivos:                                                   │
│  │   • f1_rank_all_signals.json (rank inicial)                              │
│  │   • signal_configs_optimized.json (sinais individualmente otimizados)   │
│  │   • ensemble_candidates.json (combinações complementares)               │
│  │   • ensemble_f3_rank.json (rank dos ensembles otimizados)               │
│  ├── Decide: qual ensemble (ou sinal solo) ir para produção                │
│  └── Opcional: mais ciclos no ensemble escolhido                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Ajustes Necessários no Código

### 1. `scripts/orchestrator_v65.py` — Refatoração do Loop Principal

**Problema atual**: Um único loop `for cycle in range(1, max_cycles+1)` para um único sinal.

**Mudança**: Dois loops aninhados:
```python
def orchestrator_v67(signal_queue, max_cycles_per_signal=3):
    for signal_config in signal_queue:
        current_config = dict(signal_config)
        previous_hypothesis = None
        
        for cycle in range(1, max_cycles_per_signal + 1):
            # ... ciclo atual ...
            
            # Critério de parada POR SINAL
            if should_stop_per_signal(memory, signal_config['name']):
                log(f"Signal {signal_config['name']} done. Moving to next.")
                break  # sai do loop interno, vai para próximo sinal
```

**Critérios de parada por sinal**:
```python
def should_stop_per_signal(memory, signal_name):
    signal_cycles = [c for c in memory.cycles if c.get('signal_name') == signal_name]
    
    # 1. Sinal validado (OOS > 0, WR > 35%)
    validated = [s for s in memory.validated_signals if s['name'] == signal_name]
    if validated: return True
    
    # 2. Spinning (3 ciclos sem melhora)
    if len(signal_cycles) >= 3:
        recent_nets = [c['result']['oos_net'] for c in signal_cycles[-3:]]
        if max(recent_nets) - min(recent_nets) < 500:  # plateau
            return True
    
    # 3. Hipóteses esgotadas
    last_cycle = signal_cycles[-1] if signal_cycles else None
    if last_cycle and last_cycle.get('hypothesis', {}).get('type') == 'none':
        return True
    
    return False
```

### 2. `scripts/cycle_memory.py` — Tracking Per-Signal

**Problema atual**: `add_cycle()` não guarda de qual sinal o ciclo veio. `is_spinning()` é global.

**Mudanças**:
```python
def add_cycle(self, cycle_result):
    cycle_result['signal_name'] = cycle_result.get('signal_name', 'default')
    # ... resto igual ...

def is_spinning(self, signal_name=None, max_cycles=3, threshold=100):
    cycles = self.cycles
    if signal_name:
        cycles = [c for c in cycles if c.get('signal_name') == signal_name]
    # ... resto igual, mas usando cycles filtrado ...

def get_recommendation(self, signal_name=None):
    if signal_name:
        signal_cycles = [c for c in self.cycles if c.get('signal_name') == signal_name]
        # retorna recomendação baseada só nos ciclos desse sinal
```

### 3. `scripts/orchestrator_v65.py` — Persistência de Rank F1/F3

**Problema atual**: `f1_results`, `f2_results`, `f3_results` são descartados após uso.

**Mudança**: Salvar após cada sort:
```python
def save_ranking(results, columns, out_dir, label, cycle_num, signal_name):
    import csv
    path = os.path.join(out_dir, f'{label}_c{cycle_num}_{signal_name}.csv')
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['rank'] + columns)
        for i, r in enumerate(results):
            w.writerow([i+1] + [r.get(c, '') for c in columns])

# No run_grid_cycle, após cada sort:
save_ranking(f1_results[:N_TOP_F2], ['tp','sl','atr_min','atr_max','f1_net','f1_n'], 
             OUT_DIR, 'f1_rank', cycle_num, s['name'])
```

### 4. `scripts/orchestrator_v65.py` — Ensemble Optimization Real

**Problema atual**: `run_ensemble_cycle()` é one-shot, sem sweep de parâmetros.

**Mudança**: Pipeline completo de otimização do ensemble:
```python
def run_ensemble_cycle(data, memory, cycle_num, log_path):
    signals = memory.validated_signals
    if len(signals) < 2:
        return {'status': 'abort', 'reason': 'insufficient_signals'}
    
    # Fase 1: Sweep de threshold e min_votes no F2 IS
    ensemble_f2_results = []
    for thresh in [0.0, 0.3, 0.5, 0.7]:
        for min_votes in [1, 2, 3]:
            cfg = build_ensemble_config(signals, threshold=thresh, min_votes=min_votes)
            eng_f2 = data['engines']['f2']
            eng_f2.load_config_dict(cfg)
            res = eng_f2.simulate()
            m = eng_f2.calculate_metrics(res)
            net = int(m['pnl'] - len(res) * COST)
            ensemble_f2_results.append({
                'threshold': thresh, 'min_votes': min_votes,
                'net': net, 'n': len(res), 'wr': m['wr']
            })
    
    ensemble_f2_results.sort(key=lambda x: -x['net'])
    best_ensemble_f2 = ensemble_f2_results[0]
    
    # Fase 2: F3 IS com top-3 configs
    # Fase 3: Guardrail sweep
    # Fase 4: OOS
    # Fase 5: DNA Analysis
    
    # Salvar rank do ensemble
    save_ranking(ensemble_f2_results, ['threshold','min_votes','net','n','wr'],
                 OUT_DIR, 'ensemble_f2_rank', cycle_num, 'ensemble')
    
    return result
```

### 5. CLI — Signal Queue

**Mudança**: Aceitar arquivo JSON com lista de sinais:
```bash
# Modo single-signal (backward compatible)
python orchestrator_v65.py --strategy=SIGNAL_DIR_BUY --signal=1

# Modo multi-signal (novo)
python orchestrator_v65.py --signals-file=signals_queue.json
```

**Formato do signals_queue.json**:
```json
[
  {"name": "SIGNAL_DIR_BUY", "col": "PA_SIGNAL_DIR", "signal": 1, "regime": "trend", "max_cycles": 3},
  {"name": "SIGNAL_DIR_SELL", "col": "PA_SIGNAL_DIR", "signal": -1, "regime": "trend", "max_cycles": 3},
  {"name": "REV_RSI_BUY", "col": "PA_REV_RSI", "signal": 1, "regime": "range", "max_cycles": 5}
]
```

### 6. FASE 0: Signal Discovery (Novo Script)

**Novo arquivo**: `scripts/signal_discovery.py`
```python
"""
FASE 0: Descoberta de sinais.
Roda F1 para todos os sinais do parquet e gera rank.
"""
def discover_signals(data, signals_list, out_dir):
    results = []
    for sig in signals_list:
        # Roda F1 para este sinal
        f1_results = run_f1_for_signal(data, sig)
        best = max(f1_results, key=lambda x: x['f1_net'])
        avg_net = sum(r['f1_net'] for r in f1_results) / len(f1_results)
        results.append({
            'name': sig['name'], 'col': sig['col'], 'signal': sig['signal'],
            'best_f1_net': best['f1_net'], 'best_f1_n': best['f1_n'],
            'avg_f1_net': avg_net, 'n_configs': len(f1_results)
        })
    
    results.sort(key=lambda x: -x['best_f1_net'])
    with open(os.path.join(out_dir, 'f1_rank_all_signals.json'), 'w') as f:
        json.dump(results, f, indent=2)
    
    return results[:10]  # retorna top 10 para otimização
```

### 7. FASE 2: Análise de Complementaridade (Novo)

**Novo arquivo**: `scripts/ensemble_analyzer.py`
```python
"""
FASE 2: Análise de complementaridade entre sinais validados.
Identifica se sinais são concorrentes (mesmos candles) ou complementares.
"""
def analyze_complementarity(trades_by_signal):
    """
    trades_by_signal: dict {signal_name: [trades]}
    
    Retorna:
    - correlation_matrix: correlação de PnL diário entre sinais
    - overlap_matrix: % de trades no mesmo candle (concorrência)
    - regime_coverage: cobertura por regime (trend vs range)
    """
    # Calcular PnL diário por sinal
    # Calcular overlap de candles
    # Identificar complementares (baixa correlação, baixo overlap, cobertura de regimes diferente)
    pass
```

## Arquivos que Precisam Ser Modificados

| Arquivo | Linhas | Mudança |
|---------|--------|---------|
| `scripts/orchestrator_v65.py` | 633-756 | Dois loops: externo por sinal, interno por ciclo |
| `scripts/orchestrator_v65.py` | 253-412 | Salvar rank F1/F2/F3/GD em CSV |
| `scripts/orchestrator_v65.py` | 564-630 | Ensemble como pipeline completo F2→F3→GD→OOS |
| `scripts/cycle_memory.py` | 21-27 | Adicionar signal_name aos ciclos |
| `scripts/cycle_memory.py` | 71-108 | is_spinning() per-signal |
| `scripts/cycle_memory.py` | 131-152 | get_recommendation() per-signal |
| `scripts/cycle_memory.py` | 174-197 | Popular ensemble_results |
| `scripts/dna_analysis.py` | 220-253 | Aceitar múltiplos sinais na análise |
| **NOVO** `scripts/signal_discovery.py` | — | FASE 0: F1 em todos os sinais |
| **NOVO** `scripts/ensemble_analyzer.py` | — | FASE 2: Análise de complementaridade |

## Decisão: Continuar ou Próximo Sinal

O orquestrador decide automaticamente:

```
Para cada sinal na queue:
    Para cada ciclo até max_cycles:
        Executa ciclo (GRID ou AB_TEST)
        
        SE OOS > 0 e WR > 35%:
            → Sinal VALIDADO! Para este sinal. Vai para próximo.
        
        SE spinning detectado (3 ciclos, variação < 500 pts):
            → Sinal estagnou. Para este sinal. Vai para próximo.
        
        SE hipóteses esgotadas:
            → Sem mais o que testar. Para este sinal. Vai para próximo.
    
    SE chegou em max_cycles sem validar:
        → Sinal não foi validado. Ainda assim, vai para próximo.

SE todos os sinais processados:
    → FASE 2: Ensemble Build
```

## Arquivos de Saída Persistidos

| Arquivo | Conteúdo | Fase |
|---------|----------|------|
| `f1_rank_trend.json` | Rank F1 em regime Trend | Discovery |
| `f1_rank_range.json` | Rank F1 em regime Range | Discovery |
| `f1_rank_hybrid.json` | Rank F1 Híbrido (Sharpe) | Discovery |
| `signal_queue.json` | Queue de sinais selecionados para otimização | Discovery |
| `f1_rank_c{N}_{signal}.csv` | Top N configs F1 por ciclo | Individual |
| `f3_rank_c{N}_{signal}.csv` | Top N configs F3 por ciclo | Individual |
| `signal_configs_optimized.json` | Configs otimizadas dos sinais validados | Individual |
| `ensemble_candidates.json` | Combinações de 3-5 sinais complementares | Ensemble Build |
| `ensemble_f2_rank.json` | Rank dos ensembles no F2 | Ensemble Opt |
| `ensemble_f3_rank.json` | Rank dos ensembles no F3 | Ensemble Opt |

## Resumo

O V6.6 atual é um **otimizador single-signal**. Para atingir o fluxo descrito, precisamos de:

1. **Loop externo por sinal** (queue)
2. **Critérios de parada por sinal** (não global)
3. **Persistência de ranks** (F1, F3, ensemble)
4. **FASE 0: Signal Discovery** (F1 em todos os sinais)
5. **FASE 2: Ensemble Build** (análise de complementaridade)
6. **FASE 3: Ensemble Optimization** (pipeline completo de otimização)
7. **Arquivos de saída** para decisão manual

Isso é o **V6.7**.
