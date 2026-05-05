# Guia de Execucao de Ciclos — V6.6 (ATUAL)

**Data:** 2026-05-02
**Versao:** V6.6 (anterior: V6.3)
**Documento anterior:** `GUIA_CICLOS.md` (V6.3, desatualizado)

---

## O que Mudou da V6.3 para V6.6

| V6.3 (antigo) | V6.6 (atual) | Motivo |
|---------------|--------------|--------|
| F1 via `numba_f1.py` | F1 via `engines/f1_fast_screener.py` | `numba_f1.py` nunca existiu |
| Matriz de veto via `correlation.py` | DNA Analysis via `scripts/dna_analysis.py` | `correlation.py` nunca existiu |
| Dynamic weighting via `ensemble_v2.py` | Ensemble interno no `orchestrator_v65.py` | `ensemble_v2.py` nunca existiu |
| Ciclo unico por vez, manual | Multi-signal pipeline automatico | Escalabilidade para 63 estrategias |
| Regime apenas Trend/Range | Regime: Trend/Range/Hybrid | Hybrid = sem filtro de regime |
| Guardrail BE=999999 permitido | BE capped em 500 | Sanity check obrigatorio |
| V6.4 Autopilot como "futuro" | Orquestrador V6.6 ja implementa autopilot | Foi construido incrementalmente |

---

## Arquitetura V6.6

```
FASE 0: Signal Discovery (signal_discovery.py)
   -> 21 familias de sinais x 3 regimes = 63 estrategias
   -> Gera 3 rankings F1: Trend, Range, Hybrid
   -> Cria `strategy_queue_60.json`

FASE 1: F1 Screening (f1_fast_screener.py)
   -> 5,400 combos (TP x SL x ATR_MIN x ATR_MAX)
   -> Sem guardrails, last prices sampleados, custo=30
   -> Pre-filtro: 200K combos/segundo

FASE 2: F2 Validation (BacktestEngine IS)
   -> Top 10 do F1 com ticks reais (last prices)
   -> Com BE/HP/CD basicos
   -> Grid Advisor analisa: borda? variancia? planalto?

FASE 3: F3 Search (BacktestEngine IS)
   -> Top 3 do F2
   -> Validacao mais rigorosa com bid/ask
   -> Modo busca PROIBIDO (guardrails fixos)

FASE 4: Guardrail Sweep
   -> 45 combos (BE x HP x CD)
   -> Scoring: Sharpe Ratio x Net PnL
   -> BE capped em 500 (sanity check)

FASE 5: OOS (Out-of-Sample)
   -> Dados nunca vistos (Abril 2026)
   -> Ticks bid/ask reais
   -> UMA execucao apenas (nao otimizar no OOS!)

FASE 6: DNA Analysis (dna_analysis.py)
   -> 5 estagios: metadata, segmentacao, indicadores, hipoteses
   -> Gera `v67_{signal}_cycle{N}_dna.json`

FASE 7: Cycle Memory (cycle_memory.py)
   -> Persistencia per-signal (nao global)
   -> Deteccao de spinning por sinal
   -> Validacao: OOS>0 e WR>35%

FASE 8: Ensemble (se 2+ sinais validados)
   -> Modo SELECTOR (nao consenso)
   -> Se 1 sinal quer entrar -> entra
   -> Se multiplos querem -> escolhe por peso/PnL
```

---

## Pipeline de Otimizacao por Sinal

### Check 1: Borda do Grid (Fronteira)

Antes de aceitar o melhor resultado, verificar se esta na borda:

```python
# Verificar se best_tp esta na borda do grid
if best_tp in [min(TP_GRID), max(TP_GRID)]:
    return EXPAND  # Expandir grid na direcao da borda

# Verificar se best_sl esta na borda
if best_sl in [min(SL_GRID), max(SL_GRID)]:
    return EXPAND

# Verificar ATR_MIN/ATR_MAX
if best_atr_min == min(ATR_MIN_GRID) or best_atr_max == max(ATR_MAX_GRID):
    return EXPAND
```

**Grid atual:**
- TP: [1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0, 18.0, 20.0, 25.0, 30.0]
- SL: [0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 5.0]
- ATR_MIN: [50, 100, 150, 200, 300]
- ATR_MAX: [400, 600, 800, 1000, 9999, 15000]

**Problema identificado:** 69% das estrategias tem best SL=5.0 (borda). 66% tem best ATR_MAX=400 (borda).
**Recomendacao:** Expandir grids base.

### Check 2: Variancia (Coeficiente de Variacao)

```python
# Calcular CV do top 10 F2
nets = [r['f2_net'] for r in f2_top10]
cv = np.std(nets) / abs(np.mean(nets)) * 100

if cv > 20:
    return ZOOM  # Zoom no grid (mais granularidade)
```

**Observacao:** F1 geralmente tem CV=0% porque ATR nao afeta o fast screener. A variancia real aparece no F2.

### Check 3: Planalto vs Pico

```python
# Verificar se o top 1 e um pico instavel
best_net = f2_top3[0]['f2_net']
for r in f2_top3[1:]:
    drop = abs(best_net - r['f2_net']) / abs(best_net) * 100
    if drop > 15:
        return ZOOM  # Pico instavel, precisa mapear vizinhos
```

### Check 4: Spinning

```python
# Se em 3 subciclos o ganho < 500 pts
if delta_oos < 500:
    return STOP  # Sinal esgotado
```

---

## Multi-Signal Pipeline (Novo na V6.6)

### Execucao Sequencial por Sinal

```python
# 63 estrategias, 1 de cada vez
for signal in strategy_queue:
    for cycle in range(1, max_cycles + 1):
        # Check stop criteria
        if should_stop_per_signal(memory, signal_name):
            break
        
        # Run full cycle: F1->F2->F3->Guardrail->OOS
        result = run_grid_cycle(data, signal, cycle)
        
        # DNA Analysis
        dna = analyze_dna(result['trades'])
        
        # Validate if OOS>0 and WR>35%
        if result['oos_net'] > 0 and result['oos_wr'] > 35:
            memory.add_validated_signal(signal)
        
        # Generate hypothesis for next cycle
        hypothesis = dna['stage5_hypotheses'][0]
        
        # Check target
        if result['oos_net'] >= TARGET_PNL:
            break
```

### Arquivos Gerados por Estrategia

| Arquivo | Descricao |
|---------|-----------|
| `f1_rank_c{N}_{signal}.csv` | Rank F1 (top 10) |
| `f2_rank_c{N}_{signal}.csv` | Rank F2 (top 10) |
| `f3_rank_c{N}_{signal}.csv` | Rank F3 (top 3) |
| `guardrail_rank_c{N}_{signal}.csv` | Rank Guardrail (45 combos) |
| `v67_{signal}_cycle{N}_dna.json` | DNA Analysis completo |
| `v67_{signal}_cycle{N}_log.txt` | Log da execucao |

### Estado Global: Cycle Memory

```json
{
  "cycles": [
    {"cycle": 1, "signal_name": "PA_LIQ_GRAB_TREND", "config": {...}, "result": {...}}
  ],
  "validated_signals": [
    {"name": "PA_LIQ_GRAB_TREND", "weight": 2.0, "regime": "trend"}
  ],
  "ensemble_results": []
}
```

---

## Sanity Checks Obrigatorios (V6.6)

| Check | Limite | Acao se Falhar |
|-------|--------|----------------|
| BE trigger | <= 500 | **REJEITAR** config |
| Cooldown | >= 0 (warn se 0) | WARN se CD=0 |
| Direcao bias | <= 95% | **REJEITAR** se >95% trades na mesma direcao |
| Overfit ratio | IS/OOS <= 10x | **REJEITAR** se >10x |
| Trade count | >= 10 | **REJEITAR** se <10 |
| Modo busca F3 | PROIBIDO | F3 search DEVE rodar com `modo_busca=False` |
| Engine recriado | ZERO | Criar 1x e reusar com `load_config_dict()` |

---

## Checklist Pre-Execucao

```
[ ] cycle_plan.md atualizado
[ ] super_win_continuous.parquet verificado
[ ] Custo=30 pts configurado
[ ] Grid definitions verificados (bordas?)
[ ] Engine unico por periodo (IS/OOS)
[ ] NENHUM BacktestEngine dentro de loop
[ ] F3 search com modo_busca=False
[ ] Guardrail sweep incluido (45 combos)
[ ] Validacao de parametros com fallback
[ ] Relatorio segmenta por hora/dia (OOS)
```

---

## Problemas Conhecidos (V6.6)

| # | Problema | Causa | Solucao |
|---|----------|-------|---------|
| 1 | Grid borda: SL=5.0 para 69% das estrategias | SL_GRID max=5.0 | Expandir para [7.0, 10.0] |
| 2 | Grid borda: ATR_MAX=400 para 66% | ATR_MAX_GRID min=400 | Adicionar [100, 200, 300] |
| 3 | HYBRID = RANGE (bug corrigido) | Filtro regime_label==0 para hybrid | Hybrid usa todos os dados (sem filtro) |
| 4 | Ensemble min_votes muito restritivo | min_votes=3 com 4 sinais | Usar modo SELECTOR (min_votes=1) |
| 5 | Apenas TREND validado | RANGE e HYBRID negativos | Testar SELL (--signal=-1) |
| 6 | 63 estrategias, 1 sem entradas | PA_VWAP_REV_D1_0_TREND sem sinais Fev | Investigar sinal no parquet |

---

## Referencias

| Documento | Versao | Status |
|-----------|--------|--------|
| `AGENTS.md` | V6.6 | Atualizado |
| `ENGINE_V2_DOCUMENTATION.md` | V134 | Desatualizado (ver ENGINE_V2_TECHNICAL_REFERENCE.md) |
| `ARQUITETURA_V67_DRAFT.md` | Draft | Parcialmente implementado |
| `GUIA_CICLOS.md` | V6.3 | **DESATUALIZADO** — usar este documento |

---

## Changelog

| Versao | Data | Mudancas |
|--------|------|----------|
| V6.6 | 2026-05-02 | Multi-signal pipeline, GridAdvisor, Cycle Memory per-signal, ensemble SELECTOR, bug HYBRID corrigido |
| V6.3 | 2026-04-15 | Detector de regime, F1 Multi-Grid, Matriz de Veto, Dynamic Weighting, DNA Analysis |
| V6.2 | 2026-04-01 | Pipeline basico F1->F2->F3, guardrails simples |
| V5.1 | 2026-03-20 | 17 estrategias, resultados iniciais |
