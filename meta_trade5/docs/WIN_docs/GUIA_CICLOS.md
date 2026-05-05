# ✅ ATUALIZADO — Guia de Execução de Ciclos — V8.7

> **Versão Atual:** **V8.7** (Maio 2026)
>
> **Versões anteriores:**
> - V6.6 → Pipeline multi-signal, Grid Advisor
> - V6.3 → Regime detector, Matriz de veto
> - V6.2 → Guardrails separados
>
> **Principais mudanças da V6.6 → V8.7:**
> - **F2 = Otimização Completa** (não só validação)
> - **S/R Buffers com threshold** (`sr_threshold_pct` otimizado)
> - **Guardrails integrados no F2** (não fase separada)
> - **F4 = DNA + Guardrails + Projeção** (não só DNA)
> - **Parte 2: Ensemble** (F5→F9)
>
> **Documentação de Referência:**
> - `FLUXO_OTIMIZACAO_V87_FINAL.md` — Fluxo completo F0→F9
> - `F2_GRIDS_POR_FAMILIA.md` — Grids por família de sinal
> - `F2_ANALISE_QUEDA_PNL_V2.md` — Correção S/R buffers

---

## Documentação de Referência

| Documento | Onde | Conteúdo |
|-----------|------|----------|
| **FLUXO_OTIMIZACAO_V87_FINAL.md** | `docs/WIN_docs/` | **Fluxo completo F0→F9 (Parte 1 + Parte 2)** |
| **F2_GRIDS_POR_FAMILIA.md** | `docs/WIN_docs/` | **Grids por família (Trend, Mean Rev, Breakout, etc.)** |
| **F2_ANALISE_QUEDA_PNL_V2.md** | `docs/WIN_docs/` | **Análise causa raiz S/R + correção threshold 15%** |
| CLAUDE.md | Raiz do projeto | Regras de engine, períodos, custos, sinais, lições |
| engines/README.md | `engines/README.md` | F1/F2/F3 comparação, sampling study, modo busca/produção |
| data/README_DADOS.md | `data/README_DADOS.md` | Inventário de dados, períodos, colunas, ticks |
| ARQUITETURA_BOT.md | `docs/WIN_docs/` | Arquitetura do bot em 4 camadas (V139+) |
| este documento | `docs/WIN_docs/GUIA_CICLOS.md` | **Guia de execução de ciclos V8.7** |

---

## Meta e Critérios de Aceite

- **+1.000 pts/dia** líquido (COST=30)
- **90% dias positivos** (19/21 OOS)
- **OU** 50 ciclos esgotados

PASS apenas se AMBOS simultaneamente.

### Regra Fundamental: UM ciclo por vez

**Ciclos NÃO são executados em lote.** Cada ciclo deve ser seguido de análise antes do próximo.

```
Ciclo N → Análise → Hipótese → Ciclo N+1 → Análise → Hipótese → ...
```

---

## Arquitetura V8.7 — Fluxo Completo

### PARTE 1: 23 Modelos Individuais

```
F0: Geração de Sinais (5 min) ✅
   ↓
F1: Grid Search TP/SL/ATR (45 seg) ✅
   ↓
F2: Otimização Completa (5-10 min) ⚠️
   ├─ TP/SL/ATR (refinamento ±20%)
   ├─ S/R Buffers (tp_sr_pct, sl_sr_pct, sr_threshold_pct)
   ├─ Gestão de Custo (BE, HP, CD, Slope, Cooldown)
   └─ Filtros (Book Imbalance, Cum Delta)
   ↓
F3: Validação Tick-by-Tick (2 min) ✅
   ↓
F4: DNA + Guardrails + Projeção (2 min) ⚠️
```

### PARTE 2: Ensemble

```
F5: Matriz de Sobreposição (2 min) ❌
   ↓
F6: Otimização Ensemble (50 min) ❌
   ↓
F7: Modelo MT5 (1 min) ❌
   ↓
F8: Simulação MT5 (manual) ❌
   ↓
F9: Command Center (1 min) ❌
```

**Total Parte 1 (23 sinais):** ~10 min por sinal × 23 = **3-4 horas**  
**Total Parte 2 (Ensemble):** ~55 min por ensemble × 5 ensembles = **4-5 horas**

---

## Etapas do Ciclo V8.7

### Etapa 0: Geração de Sinais — `scripts/build_win_signals_v87.py`

**O que faz:** Gera os 23 sinais `PA_*` e indicadores no parquet master.

**Output:** `data/super_win_continuous.parquet` (154 colunas, ~101k linhas)

**Indicadores Gerados:**
- **Sinais PA_ (23 famílias):** `PA_SIGNAL_DIR`, `PA_SIGNAL_REV`, `PA_ADX_BREAK`, `PA_LIQ_GRAB`, etc.
- **Regime:** `efficiency_ratio`, `regime_label`, `ADX7`, `ADX14`, `ADX20`, `ADX30`
- **S/R Buffers:** `dist_to_resistance`, `dist_to_support`
- **Tape Reading:** `book_imbalance`, `book_imbalance_ma`, `book_imbalance_cum`
- **Fluxo:** `cum_delta`, `cum_delta_ma`
- **Concentration Zones:** `concentration_poc`, `concentration_vah`, `concentration_val`, `in_concentration`
- **Outros:** `ATR`, `EMA20`, `EMA5`, `EMA9`, `VWAP`

**Tempo:** ~5 minutos

---

### Etapa 1: F1 Grid Search — `engines/f1_fast_screener.py`

**O que faz:** Pre-filtro ultra-rápido para eliminar combos obviamente ruins.

**Espaço de Busca:**
```python
TP_MULT:     [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]           # 6 valores
SL_MULT:     [2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]      # 7 valores
ATR_MIN:     [100, 150, 200, 250, 300]                # 5 valores
ATR_MAX:     [400, 600, 800, 1000]                    # 4 valores
# Total: 6×7×5×4 = 840 combos
```

**Guardrails:** ❌ NENHUM
- Sem BE, Grace Period, Circuit Breaker, Slope Decay
- Sem S/R buffers, sem filtros de hora/dia
- Sem cooldown após SL
- Sem TP30 (take-profit adaptativo)
- Apenas SL/TP fixo + position blocking (skip=1)

**Dados:**
- Last prices sampleados (15/candle)
- Custo simulado de 30 pts/trade (não calculado do spread)

**Output:** Top 10 configs por sinal (ordenadas por PnL líquido)

**Tempo:** ~45 segundos por sinal (23 sinais = 17 min total)

---

### Etapa 2: F2 Otimização Completa — `engines/f2_optimization_v87.py`

**O que faz:** Otimiza TODOS os parâmetros simultaneamente:
- TP/SL/ATR (refinamento fino ±20%)
- S/R Buffers (`tp_sr_pct`, `sl_sr_pct`, `sr_threshold_pct`)
- Gestão de Custo (BE, HP, CD, Slope, Cooldown)
- Filtros (Book Imbalance, Cum Delta)

**Espaço de Busca (exemplo: TREND):**
```python
# TP/SL/ATR (Refinamento ±20%)
TP_MULT:     [1.5, 1.8, 2.0, 2.2, 2.5]              # 5 valores
SL_MULT:     [4.0, 4.5, 5.0, 5.5, 6.0]              # 5 valores
ATR_MIN:     [150, 180, 200, 220, 250]              # 5 valores
ATR_MAX:     [600, 680, 800, 920, 1000]             # 5 valores
# Subtotal: 625 combos

# S/R Buffers
TP_SR_PCT:   [0.80, 0.90, 1.00]                     # 3 valores
SL_SR_PCT:   [1.10, 1.15, 1.20]                     # 3 valores
SR_THRESHOLD_PCT: [1.05, 1.10, 1.15, 1.20, 1.25]    # 5 valores (NOVO!)
# Subtotal: 3×3×5 = 45 combos

# Gestão de Custo
BE_OFFSET:   [50, 100, 200]                         # 3 valores
GRACE_CANDLES: [4, 6, 8]                            # 3 valores
COOLDOWN_CANDLES: [0, 2]                            # 2 valores
MAX_SL_CONSEC: [5, 99]                              # 2 valores
SLOPE_DECAY: [0.50, 0.65, 0.80]                     # 3 valores
# Subtotal: 3×3×2×2×3 = 108 combos

# Filtros (Tape Reading, Book Imbalance)
BOOK_IMB_THRESH: [0.0, 0.1, 0.2]                    # 3 valores
CUM_DELTA_THRESH: [-0.5, 0.0, 0.5]                  # 3 valores
# Subtotal: 3×3 = 9 combos

# TOTAL: 625 × 45 × 108 × 9 = 27,337,500 combos
```

**GridAdvisor (Redutor de Espaço):**
Se F1 foi estável (CV% < 15%):
- TP/SL/ATR → FIXO (1 combo, usa melhor do F1)
- Total reduzido: 1 × 45 × 108 × 9 = **43,740 combos** (4.4s)

**S/R Buffers com Threshold (CORREÇÃO V8.7):**
```python
# S/R só aplica se estiver dentro de sr_threshold_pct do TP base
sr_distance = dist_to_resistance / (tp_mult * atr)
if sr_distance < sr_threshold_pct:  # Ex: 1.15 = dentro de 15%
    tp_price = close + tp_sr_pct * dist_to_resistance
else:
    tp_price = close + tp_mult * atr  # Usa TP base
```

**Dados:**
- Ticks reais (last prices, todos os ticks)
- Custo calculado do spread real
- COM guardrails (BE, HP, CD, etc.)

**Output:** Top 3 configs por sinal (PnL, WR, Sharpe, DD)

**Tempo:**
- F1 estável: ~5 segundos por sinal
- F1 instável: ~45 min por sinal (GridAdvisor reduz para 1 combo TP/SL/ATR)

---

### Etapa 3: F3 Validação Tick-by-Tick — `backtest/engine_v2.py`

**O que faz:** Valida top 3 do F2 com ticks bid/ask reais (referência ouro).

**Modo de Operação:**
- **Modo Busca** (`modo_busca=True`):
  - Desliga Circuit Breaker, lunch filter, 9:00-9:30 restriction
  - Mantém BE, HP, CD, Slope (otimizados no F2)
  - Valida top 3 do F2

- **Modo Produção** (`modo_busca=False`):
  - Todos os guardrails ativos
  - Apenas top 1 config (vencedora do F2)
  - Gera `trades_ciclo{N}.parquet`

**Output:**
- `docs/WIN_docs/F3_VALIDACAO_{SINAL}.md` — Relatório de validação
- `trades_ciclo{N}.parquet` — Trades candle a candle (para DNA)

**Tempo:** ~2 min por sinal (top 3 configs)

---

### Etapa 4: F4 DNA + Guardrails + Projeção — `scripts/dna_analysis_v87_final.py`

**O que faz:**
1. Analisa trades do F3 (DNA Analysis)
2. Sugere guardrails heurísticos (BE, HP, CD)
3. Projetar PnL OOS
4. Documentar tudo

**Análise DNA:**
- Segmentação por hora, dia da semana, regime
- Identificação de padrões (ex: "perde às 14h", "ganha em trend")
- Sugestão de guardrails (ex: "bloquear 12-14h", "BE=100")

**Projeção PnL:**
- Baseado em WR, Sharpe, DD do IS
- Projeção conservadora (desconta 30-50%)

**Output:**
- `docs/WIN_docs/DNA_{SINAL}.md` — Análise completa
- `docs/WIN_docs/GUARDRAILS_{SINAL}.md` — Sugestões de guardrails
- `docs/WIN_docs/PROJECAO_{SINAL}.md` — Projeção PnL OOS

**Tempo:** ~2 min por sinal

---

## Exemplo: Fluxo de 1 Ciclo Completo

```
CICLO N — Hipótese: "PA_REV_RSI_S70 funciona melhor em range com CVD baixo"

[Etapa 0] check_dist.py
  → REGIME_TREND_V2 no Fev: 0% trend, 100% range → ABORT
  → Alternativa: usar ADX7 > 30 como regime filter
  → ADX7 no Fev: 15% > 30 → OK, pode prosseguir

[Etapa 1] numba_f1.py para PA_REV_RSI_S70
  → Grid: TP(11) × SL(9) × ATR(3×3) × BE(3) × HP(3) × CD(3) = 24K combos
  → F1: 24K combos em 0.12s
  → Top 20: filtrados por alpha (PnL - risco)

[Etapa 2] correlation.py
  → Carregar trades IS das top 5 estratégias
  → Matriz de correlação de erros
  → PA_REV_RSI_S70 e PA_REV_RSI_S75: err_corr=0.82 → REMOVER S75

[Etapa 3] ensemble_v2.py
  → Calcular pesos: PA_REV_RSI_S70 (0.45 range), PA_SIGNAL_DIR (0.55 trend)
  → Congelar pesos

[Etapa 4] F3 OOS Abril (próximo contrato pendente)
  → Ensemble no OOS: Net=+45.000, 70% positive days
  → Status: PROVISIONAL (aguardando Maio para confirmar)
```

## Dados Disponíveis (Atualizado 01/Mai/2026)

Consulte `data/README_DADOS.md` para o inventário completo. Resumo:

| Período | Uso | Dados |
|---------|-----|-------|
| **Jan-Fev 2026** | F1 (grid) | `super_win_continuous.parquet` filtrado para Fev. Cache `_fev_cache.npz` disponível (941 entries SELL). |
| **Jan-Mar 2026** | F2 (IS) | `super_win_continuous.parquet` + `WIN_merged_all.parquet` (240M ticks, last prices, bid=ask=last) |
| **30/Mar-29/Abr 2026** | F3 (OOS) | `super_win_continuous.parquet` + ticks diários em `data/ticks/WIN*_ticks_*.parquet` (41M ticks, bid/ask real) |
| **Mai 2026** | OOS Cego | **NÃO DISPONÍVEL.** Último dado: 30/Abr. Aguardando acumular candles+ticks do contrato N26. |

---

## Calibração do Detector de Regime

O detector foi calibrado contra o **Realized Trend Proxy** (ER_forward > 0.5) em 36 combinações de threshold.

### Resultados da Calibração

| Threshold | Precision | Recall | F1 | Accuracy | Uso |
|-----------|:---------:|:------:|:--:|:--------:|:---:|
| ADX>20, ER>0.30 (best F1) | 21.7% | 44.3% | **0.291** | 50.5% | Máximo de captura de tendências |
| **ADX>25, ER>0.40 (default)** | **21.2%** | **29.9%** | **0.248** | **58.5%** | **Equilíbrio recomendado** |
| ADX>30, ER>0.50 (strict) | 20.3% | 17.9% | 0.190 | 65.0% | Máximo de acurácia |

Os thresholds default (ADX > 25, ER > 0.40) foram escolhidos por oferecerem o melhor equilíbrio entre:
- **Precisão de 21%** — quando o detector acusa Trend, ~1 em cada 5 eventos realmente se realiza como tendência
- **Acurácia de 58%** — evita classificar tudo como range ou trend
- **Recall de 30%** — captura eventos de trend sem excesso de falsos positivos

### Validação de Estacionaridade

A calibração provou que o detector mantém distribuições de regime consistentes entre IS e OOS:
- **Fev (IS)**: 33.5% trend, 66.5% range
- **Jan-Mar (IS full)**: 32.7% trend, 67.3% range
- **Abr (OOS)**: 30.3% trend, 69.7% range

Variação de apenas 3 pp entre períodos — o detector não está "viciado" em um mês específico.

### O "Teto" de 21% de Precisão

A precisão máxima de ~21% confirma que o WIN é movido por eventos de curtíssimo prazo que o M5 às vezes não captura. Isso valida a decisão de usar o F1 com 15 samples para não perder a microestrutura.

O detector é usado como **filtro de regime** (Camada 2), não como sinal de entrada. Combinado com estratégias de entry, a precisão de 21% é suficiente para melhorar o resultado geral — como visto no Ciclo 3, onde range strategies filtradas por regime tiveram performance consistente no OOS (+55K no modo produção).

Referência: `engines/calibrate_regime.py` (script de calibração) e `engines/REGIME_DETECTOR.md` (documentação completa).

## Arquivos de Auditoria Obrigatórios

| Arquivo | Conteúdo | Critério de Bloqueio |
|---------|----------|---------------------|
| `regime_dist_{N}.json` | % trend vs range, p-values Mann-Whitney, ATR médio por regime | Trend < 10% → ABORT |
| `matriz_veto_{N}.csv` | Correlação de erros par-a-par, ações tomadas | Nenhum (apenas auditoria) |
| `pesos_{N}.csv` | Peso final de cada estratégia por regime | Estratégia com peso > 50% → WARN |
| `audit_trades_{N}.parquet` | Todos os trades com `selector_score` (peso do ensemble no momento do trade) | Nenhum (apenas auditoria) |
| `ciclo{N}_log.txt` | Log completo da execução | Última linha indica local do crash |

---

## Hierarquia de Erros e Recuperação

Nem todo erro deve interromper um ciclo. A falha do Ciclo 5 (parâmetros incorretos do Ciclo 4 não foram propagados) é um exemplo de **erro recuperável** que deveria ter sido corrigido dentro do ciclo e reexecutado, não aceito como resultado final.

### Classificação de Erros

| Tipo | Exemplo | Ação | Quem corrige |
|------|---------|------|-------------|
| **Erro de parâmetro/config** | TP/SL não encontrado, checkpoint corrompido, caminho de arquivo errado | **Corrigir e reexecutar** dentro do mesmo ciclo. O ciclo só termina quando roda com os parâmetros corretos. | O script do ciclo deve ter fallbacks e validação de parâmetros |
| **Erro de engine** | Bug no engine_v2, exceção no F3.eval(), schema mismatch nos ticks | **INTERROMPER o ciclo.** Requer correção no código do motor antes de prosseguir. | Desenvolvedor (não o script) |
| **Erro de checkpoint** | Checkpoint parcial corrompido, estratégia falhou no meio | **Retomar da última estratégia bem-sucedida.** O checkpoint existe justamente para isso. | O script automaticamente via checkpoint |
| **Erro de dados** | Coluna não encontrada, período sem candles, parquet vazio | **INTERROMPER** com diagnóstico claro do problema. | Desenvolvedor (dado faltante ou schema mudou) |

### Regra de Ouro

> **Se o erro está na configuração/parâmetros/lógica de coordenação entre módulos, corrija e reexecute.**
> **Se o erro está no motor de simulação (engine_v2, F3, F1), interrompa.**

### Implementação: Validação de Parâmetros Entre Etapas

Para evitar que um ciclo subsequente receba parâmetros errados do ciclo anterior:

```python
def validar_parametros_estrategia(params: dict) -> bool:
    """Verifica se os parametros de uma estrategia sao consistentes."""
    requisitos = ['tp', 'sl', 'atr_min', 'atr_max', 'col']
    for r in requisitos:
        if r not in params or params[r] is None:
            log(f"  ERRO: parametro {r} ausente para estrategia {params.get('name', '?')}")
            return False
    if params['tp'] <= 0 or params['sl'] <= 0:
        log(f"  ERRO: TP={params['tp']} ou SL={params['sl']} invalido")
        return False
    return True

# No ciclo N+1, ao carregar resultados do ciclo N:
for strategy in ciclo_anterior_results:
    if not validar_parametros_estrategia(strategy):
        log(f"REEXECUTANDO: fallback para parametros default da estrategia {strategy['name']}")
        strategy['tp'] = DEFAULT_TP  # fallback
        strategy['sl'] = DEFAULT_SL
```

### Quando Reexecutar Automaticamente

| Situação | Ação |
|----------|------|
| Estratégia do Ciclo N tem TP=0 ou SL=0 | Usar default (TP=5.0, SL=1.0) e logar WARN |
| Checkpoint do ciclo anterior não encontrado | Reexecutar grid search completo (F1→F2→F3) |
| trades_ciclo{N}.parquet vazio | Reextrair trades rodando F3 produção novamente |
| Parâmetro de regime (ADX, ER) fora do range esperado | Usar thresholds default validados (ADX>25, ER>0.40) |
| F3.eval() retorna erro de schema | **INTERROMPER** (erro de engine/dados) |

---

## Validação F1 vs F2 (Checkpoint Obrigatório)

### Regra Fundamental

> **F1 e F2 devem ter lógica idêntica (sem guardrails), diferindo apenas nos dados.**
> **Diferença aceitável: < 5% em trades e PnL.**

| Engine | Dados | Guardrails | Velocidade Real | Notas |
|--------|-------|-----------|----------------|-------|
| **F1** (Numba paralelizado) | 15 samples/candle (last) | **NENHUM** | ~200K combos/s | ⚠️ **SEM position blocking** — resultados inúteis |
| **F1** (Python sequencial) | 15 samples/candle (last) | **NENHUM** | **~458 combos/s** | ✅ **COM position blocking** — resultados corretos |
| **F2** (Numba + MP) | Todos ticks (high/low) | **NENHUM** (modo busca) | **~15K combos/s** | ✅ Com blocking + guardrails |
| **F3** (engine_v2) | Todos ticks (bid/ask) | **TODOS** (modo produção) | ~2 combos/s | ✅ Referência ouro |

### Correções Históricas (V8.7)

**Bug 1: Position Blocking (linha 193)**
- `blocked.append(pnl[idx])` estava FORA do `if had[idx]`
- F1 contava entries SEM exit como trades
- **Fix:** Mover para dentro do `if had[idx]`
- **Impacto:** 608 trades → 47 trades (Fev 2026, PA_SIGNAL_DIR BUY)

**Bug 2: Limite Artificial de Candles**
- `MAX_C = 15` no fast_screener, `max_la = min(20, ...)` no numba
- F2 não tinha limite → trades ficavam abertos até TP/SL
- **Fix:** `MAX_C = 15 → 50`, remover `min(20, ...)`
- **Impacto:** F1 passou a refletir F2 corretamente

### Como Validar

```bash
# 1. Rodar F1 full scan
python scripts/f1_full_scan_v87_test.py --signal PA_SIGNAL_DIR

# 2. Pegar melhor config do F1 e rodar F2 (modo busca)
# Config: TP=15.0, SL=2.0, ATR=[300-600]

# 3. Comparar resultados
# Esperado: Trades F1 ≈ Trades F2 (±5%)
#           PnL F1 ≈ PnL F2 (±5%)
```

### Exemplo de Validação (PA_SIGNAL_DIR, Fev 2026)

| Métrica | F1 | F2 | Diferença |
|---------|----|----|-----------|
| Trades | 8 | 8 | **0%** ✅ |
| PnL | +18,651 | +18,651 | **0%** ✅ |
| WR | 37.5% | 37.5% | **0%** ✅ |

**Status: VALIDADO** — F1 e F2 estão 100% alinhados.

### Se F1 e F2 Divergirem (> 5%)

1. Verificar se `f1_full_scan_v87_test.py` usa position blocking
2. Verificar se `MAX_C` é consistente (≥ 50)
3. Verificar se `evaluate()` do `f1_fast_screener.py` está correto
4. Documentar divergência em `docs/WIN_docs/F1_BUG_FIX.md`

---

## Aprendizados da Execução E2E (PA_SIGNAL_DIR, Maio 2026)

### Velocidades Reais do Pipeline

**Execução completa:** `scripts/e2e_pipeline_v87.py`

| Fase | Combos | Tempo | Velocidade | Notas |
|------|--------|-------|------------|-------|
| **F1** (Python puro) | 70,014 | 152s | **458 combos/s** | Sequencial, com blocking correto |
| **F2** (Numba + MP 8 workers) | 36,450 | 2.3s | **15,602 combos/s** | Paralelização massiva |
| **F3** (OOS tick-by-tick) | 3 | ~1s | ~3 combos/s | Preciso, lento |
| **Total E2E** | — | **~2.5 min** | — | 1 sinal, 1 direção |

**F1 Numba (legado) vs F1 Python:**
- **F1 Numba paralelizado:** ~200K combos/s, mas **SEM position blocking** — resultados inúteis (745K PnL falso)
- **F1 Python sequencial:** 458 combos/s, **COM position blocking** — resultados corretos (+19K PnL real)
- **Trade-off:** Para ter blocking correto, precisamos de lógica sequencial. Solução futura: pré-processar blocking e depois usar numba.

### Causas da Divergência IS/OOS

**Resultados (PA_SIGNAL_DIR BUY):**
| Fase | PnL | Trades | WR |
|------|-----|--------|----|
| F1 (IS - Fev) | +19,993 | 8 | 87.5% |
| F2 (IS - Fev) | +20,023 | 7 | 100% |
| F3 (OOS - Abr) | **-3,235** | 18 | 27.8% |

**Por que +20K virou prejuízo?**

1. **Período IS muito curto:** Apenas 1 mês (1986 candles)
   - Amostra estatística insuficiente para validar uma estratégia
   - Recomendação: usar **mínimo 3 meses** para IS

2. **Poucos trades no IS:** 7-8 trades
   - WR de 87% com 8 trades = ~7 acertos. Sorte, não skill.
   - Para confiança estatística, precisa de **mínimo 30 trades**

3. **Overfitting à variante:** `s20_z1p5_r1p0` foi "sortuda" em Fevereiro
   - Variantes são pré-computadas — algumas podem se alinhar por acaso ao período IS
   - Solução: testar múltiplos períodos IS ou usar walk-forward

4. **Condições de mercado diferentes:**
   - Fevereiro pode ter tido tendência clara (favorável ao sinal de trend)
   - Abril pode ter sido range/consolidação (desfavorável)
   - PA_SIGNAL_DIR é **sinal de tendência** — falha quando não há tendência

5. **Aumento de trades no OOS sem aumento de qualidade:**
   - IS: 7-8 trades (selecionados pelo sinal)
   - OOS: 10-18 trades (mais entradas, mas mais perdedoras)
   - O sinal gerou mais oportunidades em Abril, mas a maioria foi ruim

### O que Tornou o F1 "Ruim"?

**O F1 NÃO é ruim.** O problema é a **aplicação:**

| Problema | Causa Real | Solução |
|----------|-----------|---------|
| Resultado OOS ruim | Período IS curto + amostra pequena | Usar 3+ meses IS |
| PnL inflacionado no IS | Poucos trades com alta variância | Filtrar configs com N≥30 |
| Overfitting à variante | 18 variantes, algumas se alinham por acaso | Cross-validation temporal |
| WR alto não generaliza | 87% com 8 trades é sorte | Requerer WR>50% com N≥30 |

### Novas Regras para o Pipeline

**Regra 1: Período IS mínimo de 3 meses**
```python
# ANTES (ruim):
IS_S, IS_E = datetime(2026, 2, 1), datetime(2026, 3, 1)  # 1 mês

# DEPOIS (bom):
IS_S, IS_E = datetime(2026, 1, 1), datetime(2026, 4, 1)  # 3 meses
```

**Regra 2: Mínimo de 30 trades no F1**
```python
# No F1, filtrar configs:
if n_trades < 30:
    continue  # Descarta configs com amostra insuficiente
```

**Regra 3: Testar ambas as direções**
```bash
# BUY pode falhar, mas SELL pode funcionar
python e2e_pipeline_v87.py --signal PA_SIGNAL_DIR --direction 1   # BUY
python e2e_pipeline_v87.py --signal PA_SIGNAL_DIR --direction -1  # SELL
```

**Regra 4: Métrica de score no F2**
```python
# Não usar apenas PnL. Usar score composto:
score = (pnl * 0.5) + (wr * 100 * 0.3) + (min(n_trades, 50) * 10 * 0.2)
# Isso penaliza configs com poucos trades ou WR baixo
```

### Checklist Antes de Aceitar uma Config

- [ ] Período IS ≥ 3 meses
- [ ] Trades no IS ≥ 30
- [ ] WR no IS ≥ 50%
- [ ] PnL OOS > 0 (validado em pelo menos 1 mês)
- [ ] WR OOS ≥ 35%
- [ ] Profit Factor IS > 1.5
- [ ] Profit Factor OOS > 1.2
- [ ] Testado em ambas as direções (BUY e SELL)

---

## Otimização de Performance

| Problema | Causa | Solução |
|----------|-------|---------|
| Engine recriado no loop | `BacktestEngine()` dentro do for → recarrega 240M ticks cada vez | Criar engine UMA vez, reusar com `load_config_dict()` → ganho de 400x |
| F2 lento | engine_v2 não é vetorizado | F1 resolve 200K combos/s. F2 só valida top 20. |
| Checkpoint perdido | Crash no meio → restart do zero | `checkpoint.json` após cada estratégia |
| Schema mismatch | Arquivos de tick com tipos diferentes (Int64 vs Float64) | Cast uniforme: `.cast(pl.Float64)` em bid/ask/last |
| Parâmetro não encontrado entre ciclos | Ciclo N+1 tenta usar TP/SL do Ciclo N mas não encontra no checkpoint | `validar_parametros_estrategia()` com fallback para defaults + WARN no log |

---

## Diretriz: Engine Único (ZERO Recriações)

### Regra Absoluta

> **Cada período (IS e OOS) deve ter EXATAMENTE UM BacktestEngine.**
> **Zero engines criados dentro de loops. Zero engines criados por estratégia. Zero engines criados por cenário de teste.**

### Violação do Ciclo 8

O Ciclo 8 criou **6 engines** para testar 7 cenários. Cada engine recarregou 41M ticks desnecessariamente. O `load_config_dict()` permite trocar `ensemble_threshold`, `modes`, e qualquer parâmetro sem recriar o engine. A violação ocorreu porque cada cenário foi tratado como "execução independente" em vez de "configuração diferente no mesmo engine".

```python
# ERRADO (Ciclo 8):
for threshold in [0.0, 0.3, 0.5]:
    eng = BacktestEngine(None)      # RECRIANDO!
    eng.df = df_oos
    eng.load_ticks_for_simulation(ticks)  # 0.4s perdido cada vez
    eng.load_config_dict({'ensemble_threshold': threshold, ...})
    eng.simulate()

# CERTO:
eng = BacktestEngine(None)            # UMA VEZ
eng.df = df_oos
eng.load_ticks_for_simulation(ticks)  # UMA VEZ

for threshold in [0.0, 0.3, 0.5]:
    eng.load_config_dict({'ensemble_threshold': threshold, ...})  # 1ms
    eng.simulate()
```

**Regra:** Se você escreve `BacktestEngine(None)` em qualquer lugar que não seja a linha 1 do script, é um erro.

---

## Distinção: Ciclo Completo vs Teste Rápido

Nem toda execução é um "ciclo completo". O guia define dois tipos de execução:

| Aspecto | Ciclo Completo | Teste Rápido |
|---------|---------------|--------------|
| **Pipeline** | F1 → F2 → F3 | Pula F1/F2, vai direto ao F3 |
| **Grid search** | Obrigatório (TP×SL×ATR) | Pular (parâmetros fixos) |
| **Guardrail sweep** | Obrigatório (36 combos BE×HP×CD) | Opcional |
| **Checkpoint** | Obrigatório (por estratégia) | Opcional |
| **Relatório** | Completo (PnL, WR, dias, top2) | Apenas PnL básico |
| **Conta para limite de 50** | **SIM** | **NÃO** (não é ciclo) |
| **Engine único** | Obrigatório | Obrigatório (sempre) |

### Regras

1. **Ciclo Completo** = Segue todas as etapas do fluxograma. Gera `trades_ciclo{N}.parquet`, `ciclo{N}_checkpoint.json`, relatório completo. **Conta para o limite de 50.**

2. **Teste Rápido** = Valida um conceito (ex: "o ensemble voting funciona?"). Pula grid e guardrails. Gera apenas relatório básico. **NÃO conta para o limite de 50.** Deve ser identificado com sufixo `_test` no nome do script (ex: `ciclo8_ensemble_engine_test.py`).

3. **Um teste rápido bem-sucedido deve virar um ciclo completo.** Se o conceito funcionou (como o ensemble MIXED no Ciclo 8), o próximo passo OBRIGATORIAMENTE é executar um ciclo completo com F1→F2→F3 + guardrail sweep usando aquele conceito.

---

## Guardrail Sweep Obrigatório

Todo **ciclo completo** deve incluir a varredura de guardrails para a config vencedora.

### Por que é obrigatório

O Ciclo 8 usou guardrails fixos do Cycle 4 (BE=200, HP=2, CD=2 para RANGE_REV; BE=999999 para as trend strategies). Mas esses guardrails foram otimizados para estratégias ISOLADAS. No ensemble, os guardrails podem precisar de ajustes:
- Se o ensemble entra em mais trades, o cooldown pode precisar ser maior
- Se o ensemble tem mais acertos, o BE pode ser mais agressivo
- Se estratégias de regime diferente entram juntas, o H-Progress pode precisar variar

### O que testar

Para a config vencedora do ensemble (modos + pesos + thresholds), testar:

```python
GUARDRAIL_GRID = {
    'be_trigger': [100, 200, 300, 999999],
    'hp_candles': [1, 2, 3],
    'cooldown_candles': [0, 1, 2],
}
# 4 x 3 x 3 = 36 combinacoes

# Engine criado 1x unico fora do loop:
eng = BacktestEngine(None)
eng.df = df_oos
eng.load_ticks_for_simulation(ticks)

for be in GUARDRAIL_GRID['be_trigger']:
    for hp in GUARDRAIL_GRID['hp_candles']:
        for cd in GUARDRAIL_GRID['cooldown_candles']:
            # Só troca o behp — engine reusado
            cfg['modes']['RANGE_REV']['behp'] = {
                'be_trigger': be, 'hp_candles': hp, 'cooldown_candles': cd
            }
            eng.load_config_dict(cfg)
            trades = eng.simulate()
```

**Sem guardrail sweep, o ciclo é considerado INCOMPLETO e não conta para o limite de 50.**

---

## Anti-Overfit: Sanity Checks Automáticos (V6.3+ Correção)

### Problema Identificado

Ciclos 10 e 11 geraram resultados OOS aparentemente bons (+62K/+63K), mas uma auditoria revelou:
- **Threshold inoperante:** Com todas as estratégias SELL-only, `vote_norm` é sempre -1.0, tornando `ensemble_threshold` inútil
- **Guardrails desligados:** BE=999999 (efetivamente desativado) e CD=0 (sem pausa após SL) foram "otimizados" no IS com last ticks
- **Viés direcional 100% SELL:** 396 trades, zero BUY. O robô lucrou porque o mercado caiu, não por edge
- **Overfit gap:** IS net ~+1.3M vs OOS net ~+63K (razão >20×)

### Regras de Sanity Check (Obrigatórias)

Todo ciclo completo deve aplicar estas verificações automáticas:

| Check | Limite | Ação se Falhar |
|-------|--------|----------------|
| BE trigger | ≤ 500 pts | **REJEITAR config**. BE > 500 é efetivamente desligado |
| Cooldown | ≥ 0 (warn se 0) | WARN se CD=0. Recomendado CD≥1 para operação real |
| Direção | SELL% ≤ 95% | **REJEITAR config** se >95% trades na mesma direção (aposta direcional, não estratégia) |
| Overfit ratio | IS/OOS ≤ 10× | **REJEITAR config** se IS net > 10× OOS net |
| Trade count | ≥ 10 trades | **REJEITAR config** (estatisticamente insignificante) |
| modo_busca no F3 search | PROIBIDO | F3 search DEVE rodar com `modo_busca=False` + guardrails fixos |

### F3 Search: Guardrails Fixos

**ANTES (errado — Ciclos 10/11):**
```python
# F3 search com modo_busca=True → guardrails DESLIGADOS
# O sweep encontra parâmetros que só funcionam sem atrito
cfg = build_ensemble_config(..., modo_busca=True, ensemble_threshold=th)
```

**DEPOIS (correto — Ciclo 12+):**
```python
# F3 search com modo_busca=False + guardrails fixos realistas
# O sweep encontra parâmetros que funcionam COM proteção
behp_fixed = {
    'be_trigger': 200, 'hp_candles': 2, 'cooldown_candles': 1,
    'be_offset': 25, 'hp_th': 0.15, 'tp30_pct': 0.30,
    'grace_candles': 2, 'hard_stop': 500, 'slope_decay': 0.50
}
cfg = build_ensemble_config(..., modo_busca=False, ensemble_min_votes=min_v, behp_override=behp_fixed)
```

**Por que:** O objetivo do F3 search é encontrar TP/SL e níveis de convicção (`min_votes`) que funcionam em condições realistas. Rodar sem guardrails cria um cenário irreal que infla artificialmente o IS net.

### ensemble_min_votes vs ensemble_threshold

**`ensemble_threshold` (antigo):** Normalizado [-1, 1]. Inoperante quando todas as estratégias votam na mesma direção (SELL-only → vote_norm sempre = -1.0).

**`ensemble_min_votes` (novo):** Inteiro. Número mínimo de estratégias que devem concordar para entrar no trade.

```python
# Exemplo com 3 estratégias:
# min_votes=1: qualquer estratégia dispara → mesmo comportamento antigo
# min_votes=2: pelo menos 2 estratégias devem concordar → filtra sinais fracos
# min_votes=3: todas as 3 estratégias devem concordar → máxima convicção
```

### Guardrails Heurísticos vs BE/HP

**Distinção fundamental:**

| Tipo | Exemplos | Quando são definidos | Como são definidos |
|------|----------|---------------------|-------------------|
| **Guardrails Heurísticos** | Filtro de horário (9:00-9:30), dia da semana, lunch filter, regime filter | **APÓS validação** do ciclo | Análise manual do arquivo de trades. NÃO são parâmetros para otimizar. |
| **Gestão de Risco (BE/HP/CD)** | BE trigger, H-Progress candles, Cooldown, Circuit Breaker | **DURANTE o ciclo** | Guardrail sweep (36 combos). São parâmetros para otimizar. |

**Regra:**
- **BE/HP/CD** são parâmetros de risco → otimizar via sweep no ciclo
- **Filtros de horário/dia/regime** são heurísticas → analisar trades pós-ciclo e decidir se aplicam
- **NUNCA** otimizar heurísticas no mesmo grid que BE/HP — isso multiplica o overfit

---

## Análise Pós-Ciclo: DNA dos Trades (Novo V6.3+)

**Documentação completa:** `docs/WIN_docs/GUIA_ANALISE_DNA.md`

Todo ciclo completo DEVE ser seguido de uma análise do DNA dos trades OOS. Esta análise extrai padrões dos trades vencedores para planejar o próximo ciclo com base em dados, não intuição.

### Por que é obrigatória

Sem análise pós-ciclo, cada ciclo é um tiro no escuro. A análise DNA transforma resultados brutos em hipóteses testáveis:

```
Ciclo N → Análise DNA → Hipótese N+1 → Ciclo N+1 → Análise DNA → ...
```

### O que analisar

1. **Correlação indicador × PnL** — Quais indicadores predizem lucro?
2. **Segmentação temporal** — Quais dias/horários funcionam?
3. **Tipo de saída** — TP/SL/BE/HP ratios
4. **DNA dos trades** — Indicadores no momento da entrada (TP vs SL)

### Artefatos obrigatórios

| Arquivo | Conteúdo |
|---------|----------|
| `ciclo{N}_descobertas_dna.md` | Hipóteses para próximo ciclo |
| `ciclo{N}_analise_completa.txt` | Tabelas de segmentação e DNA |

### Fase de Validação de Sinais

Antes de qualquer ensemble, cada estratégia deve passar por ciclos individuais até gerar um relatório com a melhor versão:

```
Fase 1 - Validação de Sinais (ciclos 1-N):
  Para cada estratégia candidata:
    Ciclo: F1→F2→F3→Guardrail→OOS
    Análise DNA
    Ajustar params/guardrails/heurísticas
    Repetir até estabilizar
  
  Critério de aceite: WR OOS > 40%, Net OOS > 0, overfit < 10x

Fase 2 - Assembly/Ensemble (ciclos N+1...):
  Combinar estratégias validadas
  Testar min_votes, pesos, correlação de erros
  Validar diversidade de direção (BUY+SELL)
```

**Regra:** Não montar ensemble com estratégias que não foram validadas individualmente.

### Alpha Além do PnL

O PnL bruto pode matar estratégias com alpha real. Métodos para identificar alpha:

1. **Hit Rate por Regime:** A estratégia funciona em range mas não em trend? Isso é alpha direcional.
2. **Distribuição de PnL:** Skew positivo (poucos ganhos grandes, muitas perdas pequenas) pode ser lucrativo com sizing.
3. **Serial Correlation:** Se a estratégia ganha em clusters (2-3 dias seguidos), há timing alpha.
4. **PnL Simulado com Heurísticas:** Aplicar filtros de dia/hora descobertos na análise DNA e recalcular PnL.

```python
# Exemplo: PnL simulado com filtros de dia/hora
filtered_trades = trades[
    (trades['dow'].isin([2, 3])) &  # Terça, Qua
    (~trades['hour'].isin([12, 13])) &  # Sem almoço
    (abs(trades['EMA5_SLOPE']) < 50)  # Flat market
]
simulated_pnl = filtered_trades['pnl'].sum() - len(filtered_trades) * COST
```

Se o PnL simulado com heurísticas for significativamente melhor que o PnL bruto, a estratégia tem alpha latente.

---

## Problemas Conhecidos (Atualizado V6.3)

| # | Problema | Causa | Solução |
|---|----------|-------|---------|
| 1 | Classifier 100% range | REGIME_TREND_V2 não-estacionário | Validar separação com Mann-Whitney antes de usar |
| 2 | Estratégias redundantes | Todas usam PA_SIGNAL_DIR como direção | Matriz de veto remove correlação > 0.7 |
| 3 | Outliers dominam | 2 dias explicam >100% do PnL | Relatório obrigatório de top-2-days % |
| 4 | Guardrails isolados | BE e H-Progress otimizados separados ignoram interação | F1 Multi-Grid com ambos no mesmo broadcast |
| 5 | Janela fixa 20 dias | Peso do ensemble arbitrário | Substituído por correlação de erros + Sharpe |
| 6 | OOS só Abril | Overfit no período de teste | Triplicar o número de PASS consecutivos; OOS Cego no próximo contrato (N26) quando disponível |
| 7 | Parâmetros não propagados entre ciclos | Ciclo 5 reexecutou F3 com parâmetros default, ignorando os thresholds otimizados do Ciclo 4 | Validar parâmetros de cada estratégia antes de usar; fallback para defaults com WARN |
| 8 | Erro de parâmetro tratado como erro fatal | Ciclo abortado por parâmetro incorreto quando deveria ter corrigido e continuado | Classificar erro como "recuperável" vs "fatal" |
| 9 | Engine recriado a cada cenário de teste | Ciclo 8 criou 6 engines para 7 cenários, recarregando 41M ticks cada | Engine único por período. `load_config_dict()` troca qualquer parâmetro |
| 10 | Ciclo sem guardrail sweep | Ciclo 8 usou guardrails fixos do Cycle 4 sem reotimizar para o ensemble | Guardrail sweep (36 combos) obrigatório em TODO ciclo completo |
| 11 | Teste rápido contando como ciclo | Ciclo 8 pulou F1→F2→F3 e foi registrado como "ciclo" | Distinguir "ciclo completo" vs "teste rápido". Só completo conta para o limite |
| 12 | Ensemble threshold inoperante | Com todas as estratégias SELL-only, vote_norm é sempre -1.0, tornando threshold inútil | Usar `ensemble_min_votes` (inteiro) em vez de `ensemble_threshold` normalizado |
| 13 | F3 search com modo_busca=True | Guardrails desligados no F3 search → parâmetros otimizados para cenário irreal | F3 search DEVE rodar com `modo_busca=False` + guardrails fixos (BE=200, HP=2, CD=1) |
| 14 | BE=999999 aceito como "vencedor" | Sweep selecionou BE efetivamente desligado. Sem proteção de lucro = inflação de backtest | Sanity check automático: rejeitar BE > 500. Logar warning se BE > 2×ATR |
| 15 | Viés direcional 100% SELL | 396 trades, zero BUY. Robô lucrou porque mercado caiu, não por edge | Sanity check: rejeitar configs com >95% trades na mesma direção. Adicionar estratégia BUY obrigatória no ensemble |
| 16 | Overfit gap não quantificado | IS net +1.3M vs OOS net +63K. Razão >20×, mas não foi flagado | Sanity check: rejeitar configs com overfit_ratio = IS_net/OOS_net > 10× |
| 17 | F2 sem spread simulado | Ticks IS têm bid=ask=last (zero spread). O engine simula saída sem slippage real | Custo fixo de 30 pts/trade é suficiente como aproximação. Não priorizar spread sintético agora |
| 18 | Análise pós-ciclo ausente | Ciclos anteriores não analisavam DNA dos trades vencedores | OBRIGATÓRIO: Análise DNA após todo ciclo completo (GUIA_ANALISE_DNA.md) |
| 19 | EMA5_SLOPE prediz resultado | Trades TP ocorrem com slope ≈ 0, SL com slope > 60 (Cohen's d = -1.08) | Adicionar filtro heurístico |EMA5_SLOPE| < 50 no próximo ciclo |
| 20 | "Dia mágico" não explorado | Terça: WR 55-78% para ambas as estratégias. Segunda/Quinta: consistentemente ruins | Testar boost de exposição em Terça, filtro de exclusão em Segunda/Quinta |
| 21 | BE/HP nunca ativados no OOS | hit_type mostra BE=0, HP=0 em todos os trades | Investigar _simulate_exit_v119 ou reduzir BE trigger |
| 22 | Apenas PnL usado para seleção | Estratégias com alpha real (ex: skew positivo, serial correlation) são descartadas | Adicionar métricas: hit rate por regime, skew, serial correlation, PnL simulado com heurísticas |
| 23 | Ensemble antes da validação | Ciclos 10-11 montaram ensemble com estratégias não validadas individualmente | Fase 1: validar cada estratégia individualmente. Fase 2: montar ensemble só com validadas |

### O que o BacktestEngine carrega

Quando você cria um engine, ele carrega dois componentes pesados:

```python
eng = BacktestEngine(None)
eng.df = df_is              # 1. Dados de candle (6.517 linhas)
eng.load_ticks_for_simulation(ticks)  # 2. Ticks (240 MILHÕES de linhas)
```

**Passo 1** (df) é rápido. **Passo 2** (load_ticks) é **lento** — ele constrói um índice binário para localizar rapidamente quais ticks pertencem a cada candle. Esse índice leva **15-30 segundos** para ser construído e não pode ser compartilhado entre engines.

### O que load_config_dict NÃO recarrega

```python
eng.load_config_dict(cfg)  # Só troca PARÂMETROS — 1ms
```

`load_config_dict()` atualiza APENAS:
- `signal_field` — qual coluna usar como sinal
- `tp_mult`, `sl_mult` — thresholds de TP/SL
- `filters` — filtros ATR, regime_label, etc.
- `behp` — guardrails (BE, H-Progress, Cooldown)

**NÃO recarrega:** df, ticks, índice de ticks.

Portanto, **UM engine serve para TODAS as estratégias e TODAS as suas configurações.**

### Implementação Correta

```python
# ╔══════════════════════════════════════════════╗
# ║  ERRADO: engine recriado a cada config       ║
# ╚══════════════════════════════════════════════╝
for config in todas_as_configs:
    eng = BacktestEngine(None)            # RECRIANDO!
    eng.df = df_is
    eng.load_ticks_for_simulation(ticks)  # 18s PERDIDOS!
    eng.load_config_dict(config)
    eng.simulate()                        # 2s
# Tempo: 20s x 236 configs = 4.720s (78 min)

# ╔══════════════════════════════════════════════╗
# ║  CERTO: engine único, reusado               ║
# ╚══════════════════════════════════════════════╝
eng = BacktestEngine(None)                # UMA VEZ
eng.df = df_is
eng.load_ticks_for_simulation(ticks)      # UMA VEZ — 18s

for config in todas_as_configs:
    eng.load_config_dict(config)           # 1ms
    eng.simulate()                         # 2s
# Tempo: 18s + 236 x 2s = 490s (8 min) — 9.6x mais rápido!
```

### O Mesmo Vale para o F3 (OOS)

```python
# ╔══════════════════════════════════════════════╗
# ║  F3 engine único — NUNCA recriar            ║
# ╚══════════════════════════════════════════════╝
f3_eng = F3(df_oos, ticks_oos)  # 1x — carrega OOS ticks

# Guardrail sweep (36 combos) — NÃO recriar engine
for be in be_values:
    for hp in hp_values:
        for cd in cd_values:
            f3_eng.eval(sinal, tp, sl, ...)  # usa o MESMO engine
            # NÃO: F3(...) dentro do loop!
```

**Regra prática:** Se você vê `BacktestEngine(None)` ou `F3(...)` dentro de um `for`, é um erro de performance.

### Verificação no Code Review

```
[ ] BacktestEngine criado APENAS 1x por período (IS, OOS)
[ ] NENHUM BacktestEngine dentro de for/while
[ ] NENHUM F3() dentro de for/while
[ ] load_ticks_for_simulation chamado APENAS 1x por engine
[ ] Trocas de parâmetro usam load_config_dict(), não novo engine
```

---

## Esclarecimento: Múltiplas Estratégias no Mesmo Engine

### Pergunta: O engine suporta testar várias estratégias de uma vez?

**Sim.** O `BacktestEngine` aceita múltiplos `modes` na configuração:

```python
cfg = {
    'name': 'Multi-estrategia',
    'modes': {
        'REV_RSI': {
            'enabled': True, 'priority': 1,
            'signal_field': 'PA_REV_RSI_S70',
            'tp_mult': 8.0, 'sl_mult': 0.10,
            'filters': {'ATR': {'min': 100, 'max': 1000},
                        'PA_REV_RSI_S70': {'eq': -1},
                        'regime_label': {'eq': 0}},  # range only
        },
        'TREND_DIR': {
            'enabled': True, 'priority': 2,
            'signal_field': 'PA_SIGNAL_DIR',
            'tp_mult': 2.0, 'sl_mult': 1.50,
            'filters': {'ATR': {'min': 100, 'max': 1000},
                        'PA_SIGNAL_DIR': {'eq': -1},
                        'regime_label': {'eq': 1}},  # trend only
        },
    }
}
```

Cada modo é avaliado independentemente para cada candle. O engine retorna trades mesclados de todos os modos, cada um com sua tag.

### Quando usar múltiplos modes vs separado

| Cenário | Abordagem | Motivo |
|---------|-----------|--------|
| **Otimizar parâmetros (grid search)** | 1 modo por vez | Precisamos saber qual config gerou qual trade |
| **Ensemble final (produção)** | Múltiplos modes | Queremos que todas as estratégias votem no mesmo candle |
| **Testar correlação entre estratégias** | Ambos servem | Múltiplos modes é mais rápido (1 simulate vs N simulates) |
| **Validar estratégia individualmente** | 1 modo por vez | Métricas isoladas por estratégia |

### Na prática (ciclo atual)

O Ciclo 6 faz otimização individual → **1 modo por vez**. O Ciclo 7 combinaria as estratégias → **múltiplos modes** seria ideal, mas o ciclo 7 usa o atalho de combinar trades existentes por simplicidade.

**Independente da abordagem:** O engine é criado 1x único e reusado com `load_config_dict()` para trocar os modes. Veja `engines/README.md` para detalhes da arquitetura do `BacktestEngine` e suporte a múltiplos modes.

Para uma visão completa da arquitetura pretendida (4 camadas: enriquecimento → seleção → guardrails → risco global), consulte `docs/WIN_docs/ARQUITETURA_BOT.md`. Este documento mapeia o que o engine atual suporta e o que precisa ser modificado para atingir a arquitetura V139+.

---

## Code Review: Checklist Pré-Execução

Antes de executar qualquer ciclo, verificar no código:

```
BacktestEngine criado APENAS 1x por período?
  [ ] IS: 1 engine para TODAS as estratégias
  [ ] OOS: 1 engine para TODAS as estratégias e cenários de teste
  [ ] load_ticks_for_simulation chamado 1x por engine
  [ ] Troca de threshold/cenario usa load_config_dict(), não novo engine

NENHUM BacktestEngine dentro de loop?
  [ ] Sem BacktestEngine() dentro de for/while
  [ ] Sem F3() dentro de for/while
  [ ] load_config_dict() usado para trocar parâmetros

F3 engine reusado para guardrail sweep?
  [ ] Guardrail sweep usa o MESMO F3 engine
  [ ] Guardrail sweep NÃO recria engine a cada combo

É ciclo completo ou teste rápido?
  [ ] Ciclo completo: segue F1→F2→F3, guardrail sweep, checkpoint, relatório
  [ ] Teste rápido: identificado com sufixo _test no nome

Guardrail sweep executado?
  [ ] BE_trigger [100, 200, 300, 999999] testado
  [ ] H-Progress candles [1, 2, 3] testado
  [ ] Cooldown candles [0, 1, 2] testado
  [ ] 36 combos rodados com engine ÚNICO reusado

Parâmetros propagados corretamente?
  [ ] validar_parametros_estrategia() presente
  [ ] Fallback defaults definidos
  [ ] WARN logado se fallback acionado
```

---

## Fluxograma: UM Ciclo por Vez

```
┌───────────── INÍCIO ──────────────┐
│         DADOS IS (Jan-Mar)        │
│                                    │
│   Etapa 0: Validar regime + dados  │
│   Etapa 1: F1 grid search (Fev)   │
│   Etapa 2: F2 IS validation       │
│   Etapa 3: F3 search (IS bid/ask) │
│   Etapa 4: Guardrail sweep (IS)   │
│   ──── Final IS: melhor config ── │
│                                    │
│   Etapa 5: F3 OOS (UMA execução)  │
│            Salva trades_ciclo{N}   │
│   Etapa 6: ANÁLISE dos trades     │
│   Etapa 7: HIPÓTESE para próximo  │
│   Etapa 8: Relatório + status     │
│                                    │
└─────────── CICLO N ───────────────┘
              │
              ▼
    ┌─────────────────┐
    │ Critérios       │
    │ batidos?        │── SIM → SUCESSO (fim)
    └─────────────────┘
              │
              NÃO
              ▼
    ┌─────────────────────────┐
    │ Análise dos trades OOS │
    │ foi feita?             │
    └─────────────────────────┘
       │              │
      SIM             NÃO
       │              │
       ▼              ▼
    ┌───────────┐  ┌──────────────────┐
    │ Hipótese  │  │ ANALISAR OOS     │
    │ para N+1  │  │ ANTES DE CRIAR   │
    │ pronta?   │  │ CICLO N+1        │
    └───────────┘  └──────────────────┘
       │      │            │
      SIM     NÃO          │
       │      │            │
       ▼      ▼            │
    ┌─────┐ ┌──────────┐   │
    │INÍCIO│ │FORMULAR  │   │
    │CICLO │ │HIPÓTESE  │   │
    │ N+1  │ │PRIMEIRO  │   │
    └─────┘ └──────────┘   │
              │            │
              └────────────┘
```

**Regras:**
1. **NUNCA** crie o script do Ciclo N+1 antes de analisar os resultados do Ciclo N
2. **NUNCA** execute 2 ciclos em sequência sem análise entre eles
3. **SEMPRE** formule a hipótese do Ciclo N+1 baseada nos DADOS do Ciclo N
4. Se a hipótese for "vaga" ou "genérica", volte e analise mais dados

**Sanção para violação:** O "Ciclo N+1" é reclassificado como "Fase 2 do Ciclo N" e não conta para o limite de 50 ciclos.

---

---

# Orquestrador Automático de Ciclos — V6.4 (Autopilot)

## Por que Autopilot?

O processo manual de "um ciclo por vez com análise entre" funciona, mas não escala. Com dezenas de sinais para analisar, precisamos de um **orquestrador que execute ciclos automaticamente**, aplique regras de Go/No-Go, analise DNA, formule hipóteses e gere o próximo ciclo **sem intervenção humana**.

## Arquitetura: 5 Fases

```
┌─────────────────────────────────────────────────────────────────┐
│  FASE 1: GO/NO-GO (Filtro de Viabilidade)                       │
│  ├── Gatilho Aborto: Trades < 10                                │
│  ├── Gatilho Overfit: IS/OOS > 10×                              │
│  └── Gatilho Direção: Bias > 95%                                │
├─────────────────────────────────────────────────────────────────┤
│  FASE 2: MATRIZ DNA → AÇÃO (If/Then)                            │
│  ├── Condição DNA + Contexto → Ação Automática                  │
│  └── Gera config_patch.json                                     │
├─────────────────────────────────────────────────────────────────┤
│  FASE 3: RANKING DE HIPÓTESES                                   │
│  ├── Prioridade 1: Limpeza (excluir horários mortais)           │
│  ├── Prioridade 2: Foco (refinar regime)                        │
│  └── Prioridade 3: Extração (capturar quase-vencedores)         │
├─────────────────────────────────────────────────────────────────┤
│  FASE 4: ENSEMBLE ASSEMBLY (quando N sinais passam Go/No-Go)    │
│  ├── Correlação de erros > 0.7 → veto                           │
│  ├── min_votes = [1, 2, ceil(N/2)]                              │
│  └── Pesos por Sharpe ratio                                     │
├─────────────────────────────────────────────────────────────────┤
│  FASE 5: LOOP AUTOPILOT                                         │
│  ├── Ciclo N+1 = Ciclo N + melhor hipótese                      │
│  ├── Max 10 iterações por sinal                                 │
│  └── Meta: +1000 pts/dia ou "sinal esgotado"                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## Fase 1: Go/No-Go (Filtro de Viabilidade)

Após rodar OOS e gerar `trades_ciclo{N}.parquet`, o orquestrador aplica 3 gatilhos binários:

### Gatilho 1: Aborto por Trade Count
```python
if oos_n_trades < 10:
    status = "ABORT"
    reason = "Trades < 10: sinal muito raro para validação estatística"
    action = "Descartar sinal. Não gera próximo ciclo."
```

### Gatilho 2: Aborto por Overfit
```python
overfit_ratio = abs(is_net) / max(abs(oos_net), 1)
if overfit_ratio > 10.0:
    status = "ABORT"
    reason = f"Overfit: IS/OOS = {overfit_ratio:.1f}x > 10×"
    action = "Descartar sinal. Estratégia 'decorou' o passado."
```

### Gatilho 3: Aviso por Direção Bias
```python
direction_bias = max(buy_pct, sell_pct)
if direction_bias > 95:
    status = "WARNING"
    reason = f"Bias direcional {direction_bias:.0f}%"
    action = "Marcar como 'Aposta Direcional'. Exigir validação em regime oposto."
```

**Resultado da Fase 1:**
- `PASS` → segue para Fase 2
- `ABORT` → sinal descartado, não gera próximo ciclo
- `WARNING` → segue para Fase 2 com flag de aposta direcional

---

## Fase 2: Matriz de Decisão DNA (If/Then)

O orquestrador processa o DNA dos trades OOS e aplica regras lógicas para formular a próxima hipótese:

### Matriz de Regras

| Se (Condição DNA) | E (Contexto) | Então (Ação Automática) |
|---|---|---|
| PnL_Regime_Range << 0 | PnL_Regime_Trend > 0 | Aplicar `Hard_Filter: Regime == Trend` |
| WR_Tuesday > 55% | WR_Other_Days < 45% | Adicionar `Heuristic: Tuesday_Only_Boost` |
| WR_Hour_X < 30% | Trades_Hour_X > 5 | Adicionar `Hour_X` à `Blacklist_Temporal` |
| Cohen_d(EMA5_SLOPE) > 0.5 | Skew > 2.0 | Apertar `Entry_Filter: EMA5_SLOPE > Threshold` |
| Serial_Corr > 0.3 | PnL < 0 | Propor `Momentum_Sizing: Scale_Up_On_Win` |
| BE_Hit_Count == 0 | Avg_MFE > BE_Trigger | Reduzir `BE_Trigger` em 25% |
| Skew > 3.0 | WR < 40% | Testar `BE_Reduction` para capturar quase-vencedores |
| TP_Count < 5% | SL_Count > 90% | Testar `TP_Reduction` ou `SL_Widening` |

### Exemplo de Aplicação (Ciclo 14 → 15)

```python
# DNA do Ciclo 14:
dna = {
    'pnl_trend': +796, 'wr_trend': 44.6,
    'pnl_range': -1271, 'wr_range': 17.9,
    'serial_corr': 0.347, 'skew': 3.52,
    'be_hit_count': 0, 'avg_mfe': 180,
    'wr_tuesday': 44.8, 'wr_other': 31.2,
    'wr_17h': 64.7, 'wr_10h': 0.0,
}

# Fase 2 aplica regras:
actions = []
if dna['pnl_range'] < -500 and dna['pnl_trend'] > 0:
    actions.append({'type': 'regime_filter', 'value': 'tighten'})
if dna['serial_corr'] > 0.3 and dna['pnl_trend'] > 0:
    actions.append({'type': 'momentum_sizing', 'value': 'scale_up'})
if dna['be_hit_count'] == 0 and dna['avg_mfe'] > 150:
    actions.append({'type': 'be_reduction', 'value': 0.75})
if dna['wr_17h'] > 60 and dna['wr_10h'] < 30:
    actions.append({'type': 'hour_filter', 'value': [16, 17, 18]})

# Gera config_patch.json:
# {
#   "regime_filter": "tighten",
#   "momentum_sizing": "scale_up",
#   "be_multiplier": 0.75,
#   "allowed_hours": [16, 17, 18]
# }
```

---

## Fase 3: Ranking de Hipóteses

Se o ciclo atual falhar na meta (+1000 pts/dia), o sistema ranqueia hipóteses por "Tamanho do Efeito" (Cohen's d):

### Prioridade 1: Limpeza
**Quando:** Há "Horários Mortais" (WR < 30% com >5 trades)
**Ação:** Exclusão Temporal
**Por que primeiro:** Remove ruído antes de otimizar o sinal

### Prioridade 2: Foco
**Quando:** PnL_Trend > 0 mas PnL_Range << 0
**Ação:** Refinar filtro de regime (ER>0.5, ADX>30)
**Por que segundo:** Foca o sinal onde ele funciona

### Prioridade 3: Extração
**Quando:** Skew alto (>2.0) mas WR baixo (<40%)
**Ação:** Encurtar BE para capturar quase-vencedores
**Por que terceiro:** Otimiza a cauda da distribuição

### Algoritmo de Seleção
```python
def rank_hypotheses(dna_results):
    hypotheses = []
    
    # P1: Limpeza
    for hour, stats in dna_results['hourly'].items():
        if stats['wr'] < 30 and stats['n'] > 5:
            hypotheses.append({
                'priority': 1, 'type': 'exclude_hour',
                'target': hour, 'effect_size': stats['n'],
                'description': f'Excluir hora {hour}: WR={stats["wr"]:.1f}%'
            })
    
    # P2: Foco
    if dna_results['pnl_range'] < -500 and dna_results['pnl_trend'] > 0:
        hypotheses.append({
            'priority': 2, 'type': 'tighten_regime',
            'target': 'regime_filter', 'effect_size': abs(dna_results['pnl_range']),
            'description': f'Apertar regime: range={dna_results["pnl_range"]:+d}, trend={dna_results["pnl_trend"]:+d}'
        })
    
    # P3: Extração
    if dna_results['skew'] > 2.0 and dna_results['wr'] < 40:
        hypotheses.append({
            'priority': 3, 'type': 'reduce_be',
            'target': 'be_trigger', 'effect_size': dna_results['skew'],
            'description': f'Reduzir BE: skew={dna_results["skew"]:.2f}, WR={dna_results["wr"]:.1f}%'
        })
    
    # Sort by priority, then by effect_size descending
    hypotheses.sort(key=lambda h: (h['priority'], -h['effect_size']))
    return hypotheses
```

---

## Fase 4: Ensemble Assembly

Quando N sinais passam o Go/No-Go, o orquestrador monta ensemble automaticamente:

### Regras de Assembly
```python
# 4.1: Filtrar sinais validados
valid_signals = [s for s in signals 
                 if s['oos_wr'] > 40 and s['oos_net'] > 0 and s['overfit'] < 10]

# 4.2: Matriz de correlação de erros
for i, s1 in enumerate(valid_signals):
    for s2 in valid_signals[i+1:]:
        corr = error_correlation(s1['trades'], s2['trades'])
        if corr > 0.7:
            # Remover de menor Sharpe
            if s1['sharpe'] < s2['sharpe']:
                valid_signals.remove(s1)
            else:
                valid_signals.remove(s2)

# 4.3: Testar min_votes
for min_v in [1, 2, math.ceil(len(valid_signals)/2)]:
    ensemble = build_ensemble(valid_signals, min_votes=min_v)
    result = simulate_ensemble(ensemble)
    
# 4.4: Direction bias check
if ensemble_direction_bias > 95:
    log("WARNING: Ensemble bias > 95%. Adicionar sinal BUY obrigatório.")

# 4.5: Pesos por Sharpe
weights = {s['name']: s['sharpe'] / sum_sharpe for s in valid_signals}
```

---

## Fase 5: Loop Autopilot

```python
def autopilot_loop(strategy, max_cycles=10, target_pnl=1000):
    """
    Roda ciclos automaticamente até atingir meta ou esgotar hipóteses.
    """
    for cycle in range(1, max_cycles + 1):
        # 1. Roda ciclo completo
        result = run_cycle(strategy, cycle)
        
        # 2. Fase 1: Go/No-Go
        go_no_go = evaluate_viability(result)
        if go_no_go['status'] == 'ABORT':
            log(f"Sinal {strategy} ABORTADO: {go_no_go['reason']}")
            return {'status': 'aborted', 'cycle': cycle, 'reason': go_no_go['reason']}
        
        # 3. Fase 2: DNA → Ação
        dna = analyze_dna(result['trades'])
        actions = apply_dna_matrix(dna)
        
        # 4. Fase 3: Ranking
        hypotheses = rank_hypotheses(dna)
        if not hypotheses:
            log(f"Sinal {strategy} ESGOTADO: sem hipóteses na ciclo {cycle}")
            return {'status': 'exhausted', 'cycle': cycle}
        
        best_hypothesis = hypotheses[0]
        
        # 5. Verificar meta
        if result['oos_net'] >= target_pnl:
            log(f"Sinal {strategy} SUCESSO: {result['oos_net']:+d} pts na ciclo {cycle}")
            return {'status': 'success', 'cycle': cycle, 'pnl': result['oos_net']}
        
        # 6. Aplicar melhor hipótese e continuar
        log(f"Ciclo {cycle}: aplicando hipótese '{best_hypothesis['description']}'")
        strategy = apply_hypothesis(strategy, best_hypothesis)
    
    log(f"Sinal {strategy} ESGOTADO: {max_cycles} ciclos sem atingir meta")
    return {'status': 'exhausted', 'cycle': max_cycles}
```

---

## Artefatos do Orquestrador

| Arquivo | Conteúdo |
|---------|----------|
| `orchestrator.py` | Script principal do orquestrador |
| `orchestrator_config.json` | Configuração global (targets, thresholds, max_cycles) |
| `cycle_{N}_patch.json` | Patch gerado pela Fase 2 para aplicar no ciclo N+1 |
| `cycle_{N}_hypotheses.json` | Ranking de hipóteses da Fase 3 |
| `cycle_{N}_status.json` | Status final (success/aborted/exhausted) |

---

## Resumo dos Aprendizados

1. **Regime sem separação = ciclo inválido.** Se o classifier não separa os dados no IS, não use.
2. **Multi-Grid > grids separados.** Guardrails e features interagem — otimize junto.
3. **Correlação de erros > correlação de PnL.** Duas estratégias que perdem junto são piores que duas que perdem em dias diferentes.
4. **Sharpe > PnL bruto.** PnL bruto é enganoso (outliers). Sharpe normaliza pelo risco.
5. **OOS cego pendente.** Hoje só temos Abril. Quando Maio chegar, será o juiz final. Até lá, múltiplos ciclos consecutivos com resultado positivo mitigam o risco de overfit.
6. **Engine 1x, checkpoint a cada passo.** Performance e resiliência.
7. **Abortar cedo é melhor que gastar ciclo inválido.** Etapa 0 pode cancelar o ciclo em 1 segundo.
8. **Erro de parâmetro não é erro de engine.** Se o parâmetro está incorreto, corrija e reexecute. Só interrompa o ciclo se o motor de simulação quebrou. Ciclo 5 falhou por parâmetros não propagados — deveria ter fallback e reexecução automática.
9. **Engine uma vez, ponto final.** Um BacktestEngine por período (IS, OOS). NUNCA dentro de loop. `load_config_dict()` resolve qualquer troca de parâmetro. Ciclo 6 perdeu 72s recriando engines desnecessariamente.
10. **Teste rápido não é ciclo.** Ciclo 8 foi um teste funcional — não seguiu F1→F2→F3, não teve guardrail sweep. Só ciclos completos contam para o limite de 50.
11. **Guardrail sweep não é opcional.** Mesmo que o conceito funcione sem (ex: ensemble MIXED), os guardrails precisam ser reotimizados. O que funciona para uma estratégia isolada pode não funcionar no ensemble.
12. **Autopilot elimina gargalo manual.** O orquestrador V6.4 transforma análise DNA em ações automáticas, eliminando a necessidade de intervenção humana entre ciclos.
