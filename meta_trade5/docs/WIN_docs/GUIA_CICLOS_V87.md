# GUIA DE CICLOS V8.7 — PIPELINE COM GRID ADVISOR

**Data**: 2026-05-04
**Versão**: V8.7 (GridAdvisor integrado, F0→F6 pipeline)
**Status**: ATUALIZADO — Reflete arquitetura completa com sub-ciclos iterativos

---

## ⚠️ LEIA PRIMEIRO: ESTADO ATUAL DO SISTEMA

Este documento reflete a **arquitetura V8.7 COMPLETA** com:

1. **GridAdvisor integrado no F2** — Sub-ciclos ZOOM/EXPAND para refinamento automático de grids
2. **Pipeline F0→F6** — 6 fases de otimização + ensemble
3. **Microestrutura** — S/R levels, Book Imbalance, Cumulative Delta, Concentration Zones
4. **Guardrails heurísticos NÃO otimizados** — DNA sugere, humano decide

### Principais Mudanças V6.6 → V8.7

| V6.6 (antigo) | V8.7 (novo) | Por quê |
|---------------|-------------|---------|
| F1→F2→F3→Guardrail→OOS | **F0→F1→F2→F3→F4→F5→F6** | Pipeline modular com responsabilidades claras |
| Grid fixo TP/SL/ATR | **GridAdvisor com ZOOM/EXPAND** | Refinamento automático onde importa |
| Otimização separada por fase | **F2 = Otimização completa** (TP/SL/ATR + S/R + Custo + Filtros) | Consolidação para evitar overfitting |
| Guardrails otimizados | **Guardrails heurísticos (NÃO otimizados)** | DNA Analysis sugere, humano decide custo-benefício |
| Sem microestrutura | **S/R, Book, Tape, Concentration** | Edge de microestrutura comprovado em V136b/c |

---

## 📚 DOCUMENTAÇÃO DE REFERÊNCIA (ATUALIZADA)

| Documento | Onde | Conteúdo | Status |
|-----------|------|----------|--------|
| **CLAUDE.md** | Raiz do projeto | Regras de engine, períodos, custos, sinais | ✅ Atualizado |
| **AGENTS.md** | Raiz do projeto | Persona, pipeline de dados, implementação | ✅ Atualizado |
| **FLUXO_OTIMIZACAO_V87_FINAL.md** | `docs/WIN_docs/` | **Arquitetura completa F0→F6** | ✅ **CRÍTICO** |
| **F2_GRID_ADVISOR_INTEGRACAO.md** | `docs/WIN_docs/` | **GridAdvisor: ZOOM/EXPAND/STOP** | ✅ **NOVO** |
| **PLANO_IMPLEMENTACAO_F2.md** | `docs/WIN_docs/` | Plano de implementação F2 | ✅ Atualizado |
| **ARQUITETURA_V86_PIPELINE.md** | `docs/WIN_docs/` | Pipeline V8.6 (legado) | ⚠️ Legado |
| **V86_HYBRID_DOCUMENTACAO.md** | `docs/WIN_docs/` | V8.6 Hybrid (legado) | ⚠️ Legado |
| **GRID_SEARCH_OTIMIZADO_V87.md** | `docs/WIN_docs/` | Grid search V8.7 | ✅ Atualizado |
| **engines/README.md** | `engines/` | Motores F1/F2/F3, sampling study | ✅ Atualizado |
| **backtest/README_INDICATORS.md** | `backtest/` | Indicadores base + microestrutura | ✅ Atualizado |
| **data/README_DADOS.md** | `data/` | Inventário de dados, períodos | ✅ Atualizado |
| **este documento** | `docs/WIN_docs/GUIA_CICLOS.md` | **Guia de execução V8.7** | ✅ **ATUALIZADO** |

---

## 🎯 CRITÉRIOS DE ACEITE V8.7

| Métrica | Target | Onde Validar |
|---------|--------|--------------|
| **PnL OOS** | +R$ 1.000/dia líquido | F3 OOS (Abril 2026) |
| **Win Rate OOS** | > 45% | F3 OOS |
| **Sharpe OOS** | > 1.5 | F3 OOS |
| **Positive Days** | > 65% (14/21 dias) | F3 OOS |
| **Trade Count** | > 100 trades/mês | F3 IS |
| **Overfit Ratio** | < 2.0 (IS/OOS) | F3 IS vs OOS |

**PASS** apenas se TODOS critérios simultaneamente.

---

## 🔄 ARQUITETURA V8.7 — PIPELINE F0→F6

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         PIPELINE V8.7 COMPLETO                           │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  FASE 0: CONSTRUÇÃO DE SINAIS                                            │
│  📍 scripts/build_win_signals_v87.py                                     │
│  Input:  WINJ26_M5.csv + WINM26_M5.csv                                  │
│  Output: data/variants_v87/*.parquet (22 sinais × 18 variantes)         │
│  Tempo: ~5 minutos                                                       │
│  Status: ✅ IMPLEMENTADO                                                 │
│                                                                          │
│  FASE 1: SCREENING RÁPIDO (TP/SL/ATR)                                    │
│  📍 scripts/f1_full_scan_v87_test.py                                     │
│  Input:  data/variants_v87/PA_SIGNAL_DIR.parquet                        │
│  Output: docs/WIN_docs/F1_V87_TEST_PA_SIGNAL_DIR.csv                    │
│  Combos: 4,032 por variante × 18 = 72,576 configs                       │
│  Tempo: ~45 segundos                                                     │
│  Status: ✅ IMPLEMENTADO                                                 │
│                                                                          │
│  FASE 2: OTIMIZAÇÃO COMPLETA (COM GRID ADVISOR)                          │
│  📍 engines/f2_optimization_v87.py                                       │
│  Input:  Top 10 configs do F1                                           │
│  Output: docs/WIN_docs/F2_OPTIMIZATION_PA_SIGNAL_DIR_BUY.csv            │
│  Otimiza: TP/SL/ATR (refino) + S/R Buffers + Gestão Custo + Filtros     │
│  Grid Advisor: ZOOM/EXPAND/STOP iterativo (max 3 sub-ciclos)            │
│  Combos: 252 → 625 → 125 (variável) × 34,992 F2                         │
│  Tempo: 15-30s por sub-ciclo                                             │
│  Status: ✅ IMPLEMENTADO                                                 │
│                                                                          │
│  FASE 3: VALIDAÇÃO FIEL (TICK-BY-TICK)                                   │
│  📍 engines/f3_tick_ba.py (JÁ EXISTE)                                    │
│  Input:  Top 3 configs do F2                                            │
│  Output: docs/WIN_docs/F3_VALIDATION_FINAL.csv                          │
│  Dados:  Tick-by-tick bid/ask reais                                     │
│  Tempo: ~2 segundos por config                                           │
│  Status: ✅ JÁ EXISTE                                                    │
│                                                                          │
│  FASE 4: DNA ANALYSIS + GUARDRAILS                                       │
│  📍 scripts/dna_analysis_v87_final.py                                    │
│  Input:  Trades F3 (candle-a-candle)                                    │
│  Output: docs/WIN_docs/DNA_ANALYSIS_FINAL_PA_SIGNAL_DIR_BUY.md          │
│  Análise: Hora, dia da semana, ATR, streaks, PnL distribution           │
│  Guardrails: Sugere (NÃO otimiza) hour filter, day filter, ATR block    │
│  Tempo: ~5 segundos                                                      │
│  Status: ✅ IMPLEMENTADO                                                 │
│                                                                          │
│  FASE 5: ENSEMBLE OVERLAP MATRIX                                         │
│  📍 scripts/ensemble_overlap_matrix.py                                   │
│  Input:  23 modelos validados (F3)                                      │
│  Output: docs/WIN_docs/ENSEMBLE_OVERLAP_MATRIX.csv                      │
│  Análise: Quais candles cada modelo opera, overlap matrix               │
│  Tempo: ~10 segundos                                                     │
│  Status: ❌ A CRIAR                                                      │
│                                                                          │
│  FASE 6: ENSEMBLE OPTIMIZATION                                           │
│  📍 engines/f3_ensemble_optimization.py                                  │
│  Input:  Overlap matrix + 23 modelos                                    │
│  Output: docs/WIN_docs/ENSEMBLE_WEIGHTS.csv                             │
│  Otimiza: Pesos por modelo, threshold de consenso                       │
│  Tempo: ~30 segundos                                                     │
│  Status: ❌ A CRIAR                                                      │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 DADOS DISPONÍVEIS (ATUALIZADO 04/MAI/2026)

| Período | Uso | Dados | Status |
|---------|-----|-------|--------|
| **Jan-Fev 2026** | F1 (grid) | `data/variants_v87/*.parquet` (22 sinais × 18 variantes) | ✅ Disponível |
| **Jan-Mar 2026** | F2/F3 (IS) | `super_win_continuous.parquet` + `WIN_merged_all.parquet` | ✅ Disponível |
| **30/Mar-29/Abr 2026** | F3 (OOS) | Ticks diários em `data/ticks/WIN*_ticks_*.parquet` | ✅ Disponível |
| **Mai 2026** | OOS Cego | **NÃO DISPONÍVEL** — Aguardando contrato N26 | ⏳ Pendente |

---

## 🔍 GRID ADVISOR — SISTEMA DE REFINAMENTO ITERATIVO

### Visão Geral

O **GridAdvisor** é um sistema automático de decisão que analisa resultados de grid search e decide:

| Ação | Quando | O que Faz |
|------|--------|-----------|
| **ZOOM** | CV% > 20% ou pico instável | Reduz grid em ±20% ao redor do ótimo |
| **EXPAND** | Melhor config na borda | Expande grid na direção da borda |
| **STOP** | Spinning (delta < 500) ou max zoom | Interrompe, prossegue para F3 |
| **CONTINUE** | CV% < 20%, estável | Grids convergiram, prossegue para F3 |

### Parâmetros do GridAdvisor

```python
advisor = GridAdvisor(
    zoom_cv_threshold=20.0,      # CV% mínimo para ZOOM
    plateau_drop_threshold=15.0, # Drop% máximo para vizinhos
    spinning_threshold=500,      # Delta PnL mínimo entre ciclos
    max_zoom_levels=3,           # Máximo de níveis de ZOOM
    max_subcycles=3,             # Máximo de sub-ciclos totais
    sl_floor=0.5                 # SL mínimo (x ATR)
)
```

### Grids por Família de Sinal

**Cada família tem grids específicos** — Trend, Mean Reversion, Breakout, Liquidity Grab, Regime.

**Referência completa**: `F2_GRIDS_POR_FAMILIA.md` (grids detalhados por família)

| Família | TP/SL/ATR (Refino) | S/R Buffers | Gestão Custo | Filtros | Total | Tempo |
|---------|-------------------|-------------|--------------|---------|-------|-------|
| **Trend** | 5×5×5×5 = 625 | 3×3 = 9 | 72 | 4 | 1.62M | 2.7 min |
| **Mean Rev** | 5×5×5×5 = 625 | 3×3 = 9 | 108 | 4 | 2.43M | 4.0 min |
| **Breakout** | 5×5×5×5 = 625 | 3×3 = 9 | 243 | 9 | 12.3M | 20.5 min |
| **Liq Grab** | 5×5×5×5 = 625 | 3×3 = 9 | 108 | 4 | 2.43M | 4.0 min |
| **Regime** | 5×5×5×5 = 625 | 3×3 = 9 | 162 | 1 | 0.91M | 1.5 min |

**Com GridAdvisor (F1 estável, TP/SL/ATR fixos)**:

| Família | TP/SL/ATR | S/R | Gestão | Filtros | TOTAL | Tempo |
|---------|-----------|-----|--------|---------|-------|-------|
| **Trend** | 1 | 9 | 72 | 4 | 2,592 | 0.3s |
| **Mean Rev** | 1 | 9 | 108 | 4 | 3,888 | 0.4s |
| **Breakout** | 1 | 9 | 243 | 9 | 19,683 | 2.0s |
| **Liq Grab** | 1 | 9 | 108 | 4 | 3,888 | 0.4s |
| **Regime** | 1 | 9 | 162 | 1 | 1,458 | 0.1s |

**Redução**: 625x menos combos quando F1 é estável!

### Exemplo de Execução

```
================================================================================
SUB-CICLO 1/3
================================================================================
  TP grid: [1.5, 2.5, 4.0, 6.0, 8.0, 12.0, 18.0]
  SL grid: [3.0, 5.0, 8.0, 12.0]
  ATR_MIN grid: [100, 200, 400]
  ATR_MAX grid: [600, 1000, 9999]

  Total combos F1: 252
  Total combos F2: 8.8M

  GridAdvisor: EXPAND — ATR_MAX na borda (600.0)

  [EXPAND] Expanded atr_max grid: [200, 600, 1000]...[600, 1000, 9999]

================================================================================
SUB-CICLO 2/3
================================================================================
  TP grid: [1.5, 2.5, 4.0, 6.0, 8.0, 12.0, 18.0]
  SL grid: [3.0, 5.0, 8.0, 12.0]
  ATR_MIN grid: [100, 200, 400]
  ATR_MAX grid: [200, 600, 1000, 9999]

  Total combos F1: 336
  Total combos F2: 11.8M

  GridAdvisor: STOP — Spinning: delta=0 < 500

  [STOP] GridAdvisor: Spinning detectado
```

**Referência completa**: `docs/WIN_docs/F2_GRID_ADVISOR_INTEGRACAO.md`

---

## 📝 FLUXO DE EXECUÇÃO DE 1 CICLO V8.7

### Passo-a-Passo

```bash
# 1. F0 — Construir sinais (UMA VEZ)
python scripts/build_win_signals_v87.py

# 2. F1 — Screening rápido
python scripts/f1_full_scan_v87_test.py \
  --signal PA_SIGNAL_DIR \
  --variant s10_z4p0_r0p5

# 3. F2 — Otimização completa com GridAdvisor
python engines/f2_optimization_v87.py \
  --signal PA_SIGNAL_DIR \
  --variant s10_z4p0_r0p5 \
  --direction BUY \
  --max-subcycles 3

# 4. F3 — Validação tick-by-tick (TOP 3 do F2)
python engines/f3_tick_ba.py \
  --configs F2_OPTIMIZATION_PA_SIGNAL_DIR_BUY.csv \
  --mode search

# 5. F4 — DNA Analysis + Guardrails
python scripts/dna_analysis_v87_final.py \
  --signal PA_SIGNAL_DIR \
  --variant s10_z4p0_r0p5 \
  --direction BUY

# 6. F5 — Ensemble Overlap Matrix (23 sinais)
python scripts/ensemble_overlap_matrix.py

# 7. F6 — Ensemble Optimization
python engines/f3_ensemble_optimization.py
```

---

## 🧪 EXEMPLO: CICLO COMPLETO PA_SIGNAL_DIR

### F0 — Construção

```bash
python scripts/build_win_signals_v87.py
# Output: 22 sinais × 18 variantes = 396 parquets
# Tempo: 5 minutos
```

### F1 — Screening

```bash
python scripts/f1_full_scan_v87_test.py --signal PA_SIGNAL_DIR --variant s10_z4p0_r0p5
# Output: F1_V87_TEST_PA_SIGNAL_DIR.csv
# Top 1: TP=2.0, SL=5.0, ATR=[200-800], PnL=+135,916, Trades=615, WR=51.9%
# Tempo: 45 segundos
```

### F2 — Otimização com GridAdvisor

```bash
python engines/f2_optimization_v87.py --signal PA_SIGNAL_DIR --variant s10_z4p0_r0p5 --direction BUY
# Output: F2_OPTIMIZATION_PA_SIGNAL_DIR_BUY.csv
# Sub-ciclo 1: EXPAND (ATR_MAX na borda)
# Sub-ciclo 2: STOP (Spinning detectado)
# Top 1: TP=2.0, SL=5.0, ATR=[200-600], PnL=+5,302, Trades=101, WR=83.2%
# Tempo: 2×2.6s = 5.2s
```

### F3 — Validação

```bash
python engines/f3_tick_ba.py --configs F2_OPTIMIZATION_PA_SIGNAL_DIR_BUY.csv --mode search
# Output: F3_VALIDATION_FINAL.csv
# Valida top 3 configs com ticks bid/ask reais
# Tempo: ~6 segundos
```

### F4 — DNA Analysis

```bash
python scripts/dna_analysis_v87_final.py --signal PA_SIGNAL_DIR --variant s10_z4p0_r0p5 --direction BUY
# Output: DNA_ANALYSIS_FINAL_PA_SIGNAL_DIR_BUY.md
# Sugere: Hour filter [9,10,14,15,16], Day filter [2,3,4], ATR_MIN > 250
# Tempo: 5 segundos
```

---

## 📋 ARQUIVOS DE AUDITORIA OBRIGATÓRIOS

| Arquivo | Conteúdo | Critério de Bloqueio |
|---------|----------|---------------------|
| `F1_V87_TEST_{signal}.csv` | Top 10 configs F1, PnL, Trades, WR | Nenhum |
| `F2_OPTIMIZATION_{signal}_{dir}.csv` | Top 3 configs F2 + histórico sub-ciclos | Nenhum |
| `F3_VALIDATION_FINAL.csv` | Validação tick-by-tick top 3 | WR < 40% → WARN |
| `DNA_ANALYSIS_FINAL_{signal}_{dir}.md` | DNA + guardrails sugeridos | Nenhum |
| `ciclo{N}_log.txt` | Log completo da execução | Última linha indica crash |

---

## 🚨 HIERARQUIA DE ERROS E RECUPERAÇÃO

| Erro | Severidade | Ação |
|------|------------|------|
| **F0 falha** | CRÍTICO | Abortar pipeline, verificar CSVs raw |
| **F1 sem trades** | ALTO | Expandir grid TP/SL/ATR |
| **F2 PnL < 0** | ALTO | Verificar filtros (Book Imbalance, Cum Delta) |
| **F3 WR < 40%** | MÉDIO | Revisar guardrails de custo |
| **GridAdvisor STOP prematuro** | MÉDIO | Aumentar `max_subcycles` para 4-5 |
| **F4 sem sugestões** | BAIXO | Prosseguir sem guardrails heurísticos |

---

## 🔧 TROUBLESHOOTING

### F2 PnL muito menor que F1

**Sintoma**: F1 PnL=+136K, F2 PnL=+5K

**Causa**: Filtros de microestrutura muito agressivos

**Solução**:
1. Testar F2 sem filtros (`GRID_BOOK_IMB=[0.0]`, `GRID_CUM_DELTA=[0.0]`)
2. Aumentar thresholds: `BOOK_IMB=[0.2, 0.3]`, `CUM_DELTA=[0.0, 0.5]`
3. Verificar se colunas de microestrutura estão no parquet

### GridAdvisor EXPAND em loop

**Sintoma**: Múltiplos EXPANDs na mesma dimensão

**Causa**: Grid inicial muito restritivo

**Solução**:
1. Aumentar grid inicial (ex: `ATR_MAX_GRID=[400, 800, 1200, 9999]`)
2. Verificar `_expanded_dims` no GridAdvisor (proteção anti-loop)

### F4 sem sugestões de guardrails

**Sintoma**: DNA Analysis não sugere filtros

**Causa**: Dados muito homogêneos (sem variação por hora/dia/ATR)

**Solução**:
1. Prosseguir sem guardrails heurísticos
2. Testar F5/F6 (ensemble) para diversificação

---

## 📚 LIÇÕES APRENDIDAS V8.7

### 1. GridAdvisor Economiza Tempo

**Antes**: Grid fixo 12×8×6×7 = 4,032 combos TP/SL/ATR
**Depois**: Grid esparso 7×4×3×3 = 252 combos → ZOOM automático

**Resultado**: 16x menos combos, mesma qualidade de otimização

### 2. Filtros de Microestrutura São Poderosos (mas Perigosos)

**Book Imbalance=0.1**: Bloqueia ~70% das entradas
**Cum Delta=-0.5**: Bloqueia ~60% das entradas

**Resultado**: WR sobe de 52% → 83%, mas PnL cai 90% (trade count muito baixo)

**Solução**: Usar thresholds mais altos (0.2-0.3) ou remover filtros

### 3. Guardrails Heurísticos NÃO São Otimizados

**Decisão de design**: DNA sugere, humano decide

**Por quê**: Guardrails são binários (ON/OFF) — não há "meio-termo" para otimizar

**Exemplo**: Hour filter [9,10,14,15,16] bloqueia 11,12,17,18
- +R$ 2,252 PnL
- -15 trades
- **Humano decide**: Vale a pena?

---

## ✅ CHECKLIST PRÉ-CICLO

Antes de iniciar um ciclo V8.7:

- [ ] F0: Parquets gerados com microestrutura?
- [ ] F1: Top 10 configs extraídas?
- [ ] F2: GridAdvisor configurado (max_subcycles=3)?
- [ ] F3: Ticks bid/ask disponíveis para OOS?
- [ ] F4: DNA Analysis script testado?
- [ ] F5/F6: Ensemble scripts criados?

---

## 📊 STATUS ATUAL (04/MAI/2026)

| Fase | Status | Próximo Passo |
|------|--------|---------------|
| **F0** | ✅ Implementado | Testar em todos 22 sinais |
| **F1** | ✅ Implementado | Testar em todos 22 sinais |
| **F2** | ✅ GridAdvisor integrado | Ajustar filtros (muito agressivos) |
| **F3** | ✅ Já existe | Validar top 3 do F2 |
| **F4** | ✅ Implementado | Testar com dados reais |
| **F5** | ❌ A criar | Implementar overlap matrix |
| **F6** | ❌ A criar | Implementar ensemble optimization |

---

**Última Atualização**: 2026-05-04
**Autor**: WIN Lead Quant Scientist
**Próxima Revisão**: Após teste completo F0→F6 em todos 22 sinais
