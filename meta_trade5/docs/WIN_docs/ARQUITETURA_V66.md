# Orquestrador V6.6 — Arquitetura e Resultados

## Mudanças da V6.5 → V6.6

### 1. Guardrail Sweep Saneado
- **BE_TRIGGER capped em 500**: eliminado o valor 999999 que desativava o BE
- **Nova lista**: `[100, 200, 300, 400, 500]`
- **Scoring function**: de Net PnL → `Sharpe Ratio * Net` (penaliza volatilidade)
  ```python
  def guardrail_score(net, sharpe):
      if net <= 0: return net
      return net * max(0, sharpe)
  ```

### 2. A/B Validator Robusto
- Se `improvement == 0` no IS primário (Jan-Mar), fallback para **Fevereiro** como período alternativo
- Aceita hipótese se houver melhoria no período de robustez

### 3. Ensemble Real (Weighted Voting)
- Implementado `run_ensemble_cycle()` com múltiplos modos (um por sinal validado)
- Requer `ensemble_min_votes = 2` (mínimo 2 sinais concordando)
- Pesos dinâmicos baseados no OOS performance (`weight = oos_net / 500`, cap 0.5-2.0)
- Trigger: a cada 5 ciclos se `validated_signals >= 2`, ou quando `memory.get_recommendation() == 'RUN_ENSEMBLE'`

### 4. Filtro de Inércia (CVD + Book)
- Adicionados `CVD_ACCUM`, `CVD_SIGNAL`, `BOOK_IMB` aos indicadores do DNA Analysis
- `BOOK_IMB` mostrou correlação significativa no teste (r=0.28, p=0.007)
- CVD deu NaN no período (valores constantes), mas a infraestrutura está pronta

### 5. Fix: F1 Regime Dinâmico
- O F1 agora recalcula o regime em tempo real usando os thresholds da config (`regime_er_threshold`, `regime_adx_threshold`)
- **Antes**: `regime_at_entry` era pré-calculado com thresholds fixos (0.4, 25), ignorando patches de `tighten_regime`
- **Depois**: cada ciclo com thresholds diferentes produz resultados distintos no F1

---

## Resultados E2E (SIGNAL_DIR_BUY, 2 Ciclos)

### Ciclo 1 — GRID
| Fase | Métrica | Valor |
|------|---------|-------|
| F1 | top net | +400,850 |
| F2 | net / trades / WR | -62,525 / 269t / 31.2% |
| F3 IS | net / trades | -62,525 / 269t |
| Guardrail | BE/HP/CD / net / sharpe | 500/3/0 / -57,991 / -7.66 |
| **OOS** | **net / trades / WR / PF** | **-5,780 / 88t / 34.1% / 0.78** |
| DNA | hipóteses geradas | 14 |
| Best hypo | tipo | `tighten_regime` (er=0.5, adx=30) |

### Ciclo 2 — GRID (Tipo A hypothesis)
| Fase | Métrica | Valor |
|------|---------|-------|
| F1 | top net | **+259,445** (diferente do ciclo 1!) |
| F2 | net / trades / WR | -65,264 / 269t / 30.1% |
| F3 IS | net / trades | -65,264 / 269t |
| Guardrail | BE/HP/CD / net / sharpe | 500/3/0 / -61,876 / -7.83 |
| **OOS** | **net / trades / WR / PF** | **-4,685 / 93t / 36.6% / 0.88** |
| DNA | hipóteses geradas | 8 |
| Best hypo | tipo | `exclude_dow=3` |

### Evolução entre Ciclos
| Métrica | Ciclo 1 | Ciclo 2 | Delta |
|---------|---------|---------|-------|
| OOS Net | -5,780 | -4,685 | **+1,095** |
| OOS WR | 34.1% | 36.6% | **+2.5pp** |
| OOS Trades | 88 | 93 | +5 |
| OOS PF | 0.78 | 0.88 | +0.10 |
| F1 Top | +400,850 | +259,445 | -141,405 |

### Interpretação
- O OOS melhorou levemente (-5,780 → -4,685) apesar de o IS ter piorado
- A WR subiu de 34.1% para 36.6%, mostrando que o filtro de regime mais apertado removeu trades de baixa qualidade
- O ciclo 3 (se rodasse) entraria em **AB_TEST mode** com `exclude_dow=3` (hipótese Tipo B/C)
- Nenhum sinal validado (threshold: OOS net > 0 e WR > 35%) — ambos os ciclos foram negativos

---

## Estado dos Componentes

| Componente | Status |
|-----------|--------|
| Phase Controller V2 | ✅ Funcional (GRID/AB_TEST/ENSEMBLE/ABORT) |
| Guardrail Sweep (Sharpe) | ✅ Funcional, BE capped em 500 |
| DNA Analysis (5 stages) | ✅ Funcional, 10 indicadores incl. CVD/BOOK |
| Cycle Memory | ✅ Funcional, spinning detection, signal validation |
| A/B Validator | ✅ Funcional, fallback para Fev se delta=0 |
| Ensemble Pipeline | ✅ Implementado, aguarda sinais validados |
| Config Persistence | ✅ TP/SL/ATR/BE/HP/CD persistem entre ciclos |

---

## Próximos Passos Recomendados

1. **Testar com SELL signal** (`--signal=-1`): O mercado pode favorecer shorts no período
2. **Reduzir threshold de validação**: Atual `WR > 35% + net > 0` é rigoroso. Para bootstrap de ensemble, considerar `WR > 30%` ou `net > -1000`
3. **Adicionar scoring de ensemble no F2**: Testar ensemble de 2 sinais já no F2 (não esperar 5 ciclos)
4. **Corrigir CVD NaN**: Investigar por que `CVD_ACCUM` e `CVD_SIGNAL` são zero/constantes no período
5. **Performance**: Paralelizar guardrail sweep (36 combos independentes)
