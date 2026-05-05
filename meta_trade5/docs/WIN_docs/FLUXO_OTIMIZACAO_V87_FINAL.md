# FLUXO DE OTIMIZAÇÃO V8.7 — ARQUITETURA COMPLETA

**Data:** 2026-05-04  
**Versão:** V8.7  
**Status:** ✅ Documentado

---

## 📊 VISÃO GERAL

```
PARTE 1: 23 Modelos Individuais
┌─────────────────────────────────────────────────────────────┐
│ F0 → F1 → F2 → F3 → F4                                      │
│ Sinais → TP/SL/ATR → OTIMIZAÇÃO COMPLETA → Validação → DNA │
└─────────────────────────────────────────────────────────────┘
                          ↓
PARTE 2: Ensemble
┌─────────────────────────────────────────────────────────────┐
│ F5 → F6 → F7 → F8 → F9                                      │
│ Matriz → Otimização → MT5 → Simulação → Command Center     │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 PARTE 1: 23 Modelos Individuais

### F0 — Geração de Sinais (5 min) ✅

**Propósito:** Gerar os 23 sinais `PA_*` e criar parquet.

**Arquivos:**
- `scripts/build_win_signals_v87.py` — Gera sinais
- `data/super_win_continuous.parquet` — Output (154 colunas, ~101k linhas)

**Sinais Gerados:**
| Família | Sinais |
|---------|--------|
| **Trend** | `PA_SIGNAL_DIR`, `PA_SIGNAL_DIR_V2`, `PA_STRONG_TREND_A25_S20`, `PA_SLOPE_TREND_S25_A25` |
| **Mean Reversion** | `PA_SIGNAL_REV`, `PA_REV_RSI_UNIFIED`, `PA_VWAP_REV_D1_0`, `PA_VWAP_Z_Z2_0`, `PA_POC_REV` |
| **Breakout** | `PA_ADX_BREAK_A25`, `PA_GK_BREAK_G0_001`, `PA_EXHAUST_Dn1_0_M40` |
| **Liquidity Grab** | `PA_LIQ_GRAB`, `PA_VCP_C0_6` |
| **Regime** | `PA_EFF_RATIO_E0_6`, `PA_CHOP_C38_2`, `PA_TUESDAY`, `PA_MFI_B20`, `PA_TSI_T25` |
| **Crossover** | `PA_MA_CROSS_F9_S21`, `PA_SMA_CROSS_F5_S10` |
| **Outros** | `PA_HMA_CROSS_F5_S10`, `PA_BB_M2_0`, `PA_KELT_M2_0`, `PA_TSI_T25` |

**Indicadores Adicionais:**
- `ATR`, `ADX7`, `EMA20`, `EMA5`, `EMA9`, `VWAP`
- `dist_to_resistance`, `dist_to_support` (S/R)
- `book_imbalance`, `book_imbalance_ma`, `book_imbalance_cum` (Tape Reading)
- `cum_delta`, `cum_delta_ma` (Fluxo)
- `concentration_poc`, `concentration_vah`, `concentration_val`, `in_concentration` (Concentration Zones)

**Output:** `data/super_win_continuous.parquet`

---

### F1 — Grid Search TP/SL/ATR (45 seg) ✅

**Propósito:** Pre-filtro ultra-rápido para eliminar combos obviamente ruins.

**Arquivos:**
- `engines/f1_fast_screener.py` — Motor vetorizado (200K combos/seg)
- `scripts/f1_full_scan_v87.py` — Executa scan completo

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

### F2 — Otimização Completa (5-10 min) ⚠️ EM IMPLEMENTAÇÃO

**Propósito:** Otimizar TODOS os parâmetros simultaneamente:
- TP/SL/ATR (refinamento fino)
- S/R Buffers
- Gestão de Custo (BE, HP, CD, Slope, Cooldown)
- Indicadores: S/R, Tape Reading, Book Imbalance, Concentration Zones

**Arquivos:**
- `engines/f2_optimization_v87.py` — Motor de otimização ✅
- `data/f2_grid_configs.json` — Grids por família ✅
- `engines/family_classifier.py` — Classifica sinal por família ✅

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
# Tempo estimado: 2,734 segundos (45 min) — MUITO!
```

**GridAdvisor (Redutor de Espaço):**
Se F1 foi estável (CV% < 15%):
- TP/SL/ATR → FIXO (1 combo, usa melhor do F1)
- Total reduzido: 1 × 45 × 108 × 9 = **43,740 combos** (4.4s)

**Dados:**
- Ticks reais (last prices, todos os ticks)
- Custo calculado do spread real
- COM guardrails (BE, HP, CD, etc.)

**Output:** Top 3 configs por sinal (PnL, WR, Sharpe, DD)

**Tempo:**
- F1 estável: ~5 segundos por sinal
- F1 instável: ~45 min por sinal (GridAdvisor reduz para 1 combo TP/SL/ATR)

---

### F3 — Validação Tick-by-Tick (2 min) ✅

**Propósito:** Validar top 3 do F2 com ticks bid/ask reais (referência ouro).

**Arquivos:**
- `backtest/engine_v2.py` — Backtest engine (tick-a-tick)
- `backtest/strategies/v87.py` — Estratégia V87
- `data/ticks/WIN*.parquet` — Ticks bid/ask reais

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

### F4 — DNA Analysis + Guardrails + Projeção (2 min) ⚠️ EVOLUIR

**Propósito:**
1. Analisar trades do F3 (DNA Analysis)
2. Sugerir guardrails heurísticos (BE, HP, CD)
3. Projetar PnL OOS
4. Documentar tudo

**Arquivos:**
- `scripts/dna_analysis_v87_final.py` — DNA Analysis ✅
- `scripts/dna_analysis_v87.py` — Versão anterior ⚠️

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

## 🎯 PARTE 2: Ensemble

### F5 — Matriz de Sobreposição (2 min) ❌

**Propósito:** Identificar quais sinais operam nos mesmos candles.

**Arquivos:**
- `scripts/ensemble_matrix.py` — A CRIAR

**Análise:**
- Matriz N×N (23×23 = 529 pares)
- Overlap = % candles operados por ambos sinais
- Correlação = Pearson entre sinais (+1/-1/0)

**Output:**
- `docs/WIN_docs/ENSEMBLE_MATRIX.md` — Matriz de sobreposição
- Lista de pares com baixo overlap (<20%) — candidatos a ensemble

**Tempo:** ~2 min

---

### F6 — Otimização Ensemble (50 min) ❌

**Propósito:** Otimizar ensemble de 2-5 sinais com espaço de busca limitado.

**Arquivos:**
- `engines/ensemble_optimization.py` — A CRIAR
- `backtest/engine_v2.py` — Suporta Layer 2 (ensemble voting) ✅

**Espaço de Busca:**
```python
# Ensemble de 3 sinais (ex: PA_SIGNAL_DIR + PA_ADX_BREAK + PA_LIQ_GRAB)
weights: [0.5, 1.0, 1.5, 2.0] para cada sinal  # 4^3 = 64 combos
ensemble_threshold: [0.3, 0.5, 0.7]             # 3 valores
# Total: 64 × 3 = 192 combos
```

**Modo de Operação:**
- **Votação Ponderada:** Cada sinal tem peso (weight)
- **Threshold:** |normalized_vote| > threshold → entra
- **Min Votos:** Opcional, mínimo de sinais concordando

**Output:**
- `docs/WIN_docs/ENSEMBLE_{SINAL1}_{SINAL2}_{SINAL3}.md` — Relatório
- Melhor config de ensemble (weights, threshold)

**Tempo:** ~50 min (192 combos × tick-a-tick)

---

### F7 — Modelo MT5 (1 min) ❌

**Propósito:** Gerar código Python para MetaTrader 5.

**Arquivos:**
- `scripts/export_mt5.py` — A CRIAR

**Output:**
- `mt5_export/{SINAL}_v87.py` — Código MT5
- `mt5_export/{ENSEMBLE}_v87.py` — Código MT5 (ensemble)

**Tempo:** ~1 min

---

### F8 — Simulação MT5 (Manual) ❌

**Propósito:** Validar que modelo MT5 bate com F3 tick-a-tick.

**Processo:**
1. Rodar `mt5_export/{SINAL}_v87.py` no MT5
2. Comparar trades com `trades_ciclo{N}.parquet`
3. Validar que PnL, WR, trades batem (±5%)

**Output:**
- `docs/WIN_docs/MT5_VALIDACAO_{SINAL}.md` — Validação

**Tempo:** Manual (30-60 min)

---

### F9 — Command Center (1 min) ❌

**Propósito:** Gerar código para operação via Command Center.

**Arquivos:**
- `scripts/export_command_center.py` — A CRIAR
- `src/command_center_v1.py` — Interface Tkinter ✅

**Output:**
- `mt5_export/{SINAL}_command_center.py` — Integração completa

**Tempo:** ~1 min

---

## 📋 RESUMO DO FLUXO

| Fase | Propósito | Tempo | Status |
|------|-----------|-------|--------|
| **F0** | Geração de Sinais | 5 min | ✅ |
| **F1** | Grid Search TP/SL/ATR | 45 seg | ✅ |
| **F2** | Otimização Completa | 5-10 min | ⚠️ Em implementação |
| **F3** | Validação Tick-by-Tick | 2 min | ✅ |
| **F4** | DNA + Guardrails + Projeção | 2 min | ⚠️ Evoluir |
| **F5** | Matriz Sobreposição | 2 min | ❌ |
| **F6** | Otimização Ensemble | 50 min | ❌ |
| **F7** | Modelo MT5 | 1 min | ❌ |
| **F8** | Simulação MT5 | Manual | ❌ |
| **F9** | Command Center | 1 min | ❌ |

**Total Parte 1 (23 sinais):** ~10 min por sinal × 23 = **3-4 horas**  
**Total Parte 2 (Ensemble):** ~55 min por ensemble × 5 ensembles = **4-5 horas**

---

## 🗂️ ARQUIVOS POR FASE

### F0
- `scripts/build_win_signals_v87.py`
- `data/super_win_continuous.parquet`

### F1
- `engines/f1_fast_screener.py`
- `scripts/f1_full_scan_v87.py`

### F2
- `engines/f2_optimization_v87.py` ✅
- `data/f2_grid_configs.json` ✅
- `engines/family_classifier.py` ✅

### F3
- `backtest/engine_v2.py` ✅
- `backtest/strategies/v87.py` ✅

### F4
- `scripts/dna_analysis_v87_final.py` ✅
- `scripts/dna_analysis_v87.py` ⚠️

### F5-F9
- `scripts/ensemble_matrix.py` ❌
- `engines/ensemble_optimization.py` ❌
- `scripts/export_mt5.py` ❌
- `scripts/export_command_center.py` ❌

---

## 📊 GRID SEARCH POR FAMÍLIA (F2)

| Família | TP/SL/ATR | S/R | Gestão | Filtros | Total Combos | Tempo (F1 estável) |
|---------|-----------|-----|--------|---------|--------------|-------------------|
| **Trend** | 625 | 45 | 108 | 9 | 27M | 4.4s |
| **Mean Reversion** | 625 | 45 | 108 | 9 | 27M | 4.4s |
| **Breakout** | 625 | 45 | 243 | 9 | 61M | 4.4s |
| **Liquidity Grab** | 625 | 45 | 108 | 9 | 27M | 4.4s |
| **Regime** | 625 | 45 | 108 | 9 | 27M | 4.4s |
| **Crossover** | 625 | 45 | 108 | 9 | 27M | 4.4s |

**GridAdvisor:** Se F1 estável (CV% < 15%) → TP/SL/ATR = 1 combo (fixo)

---

## 🎯 PRÓXIMOS PASSOS

### Imediato
1. ✅ **Corrigir lógica S/R** — Adicionar `sr_threshold_pct` ao grid
2. ⏳ **Atualizar `f2_grid_configs.json`** — Adicionar `sr_threshold_pct: [1.05, 1.10, 1.15, 1.20, 1.25]`
3. ⏳ **Re-testar F2** — Validar correção S/R

### Curto Prazo
1. ⏳ **F4 DNA Analysis** — Evoluir para incluir sugestão de guardrails
2. ⏳ **F5 Matriz** — Criar `ensemble_matrix.py`
3. ⏳ **F6 Ensemble** — Criar `ensemble_optimization.py`

### Longo Prazo
1. ❌ **F7-F9** — Export MT5, Simulação, Command Center

---

## 📝 LIÇÕES APRENDIDAS

### Nomenclatura Correta
- ❌ **F2 = Validação** → ✅ **F2 = Otimização Completa**
- ❌ **F4 = Guardrail Sweep** → ✅ **F4 = DNA + Guardrails + Projeção**
- ✅ **F3 = Validação Tick-by-Tick** (correto)

### Guardrails
- ✅ Otimizados no **F2** (junto com TP/SL/ATR, S/R, filtros)
- ✅ Sugestões heurísticas no **F4** (DNA Analysis)
- ❌ NÃO existe "F4 Guardrail Sweep" separado

### S/R Buffers
- ✅ Otimizados no **F2** (`tp_sr_pct`, `sl_sr_pct`, `sr_threshold_pct`)
- ✅ Threshold padrão: 1.15 (15%)
- ✅ Grid: `[1.05, 1.10, 1.15, 1.20, 1.25]` (5-25%)

---

## 🔗 REFERÊNCIAS

- `docs/WIN_docs/F2_GRIDS_POR_FAMILIA.md` — Grids detalhados por família
- `docs/WIN_docs/F2_ANALISE_QUEDA_PNL_V2.md` — Análise causa raiz S/R
- `data/f2_grid_configs.json` — Configuração atual dos grids
- `engines/f2_optimization_v87.py` — Implementação F2

---

**Última atualização:** 2026-05-04  
**Próxima revisão:** Após teste F2 com `sr_threshold_pct`
