# 📚 ÍNDICE DE DOCUMENTAÇÃO V8.7

**Data**: 2026-05-04
**Versão Atual**: V8.7 (GridAdvisor integrado, pipeline F0→F6)

---

## 🎯 DOCUMENTAÇÃO PRINCIPAL (LEIA PRIMEIRO)

| Documento | Prioridade | Conteúdo | Status |
|-----------|------------|----------|--------|
| **[GUIA_CICLOS_V87.md](GUIA_CICLOS_V87.md)** | ⭐⭐⭐ | **Guia completo de execução V8.7** | ✅ ATUALIZADO |
| **[FLUXO_OTIMIZACAO_V87_FINAL.md](FLUXO_OTIMIZACAO_V87_FINAL.md)** | ⭐⭐⭐ | Arquitetura F0→F6, decisões de design | ✅ ATUALIZADO |
| **[F2_GRID_ADVISOR_INTEGRACAO.md](F2_GRID_ADVISOR_INTEGRACAO.md)** | ⭐⭐ | GridAdvisor: ZOOM/EXPAND/STOP | ✅ NOVO |
| **[PLANO_IMPLEMENTACAO_F2.md](PLANO_IMPLEMENTACAO_F2.md)** | ⭐⭐ | Plano de implementação F2 | ✅ ATUALIZADO |

---

## 📋 DOCUMENTAÇÃO POR FASE

### F0 — Construção de Sinais

| Documento | Conteúdo |
|-----------|----------|
| `scripts/build_win_signals_v87.py` | Script de construção (18 variantes, 22 sinais) |
| `backtest/indicators_sr.py` | Microestrutura: S/R, Book, Tape, Concentration |
| `data/variants_v87/` | Parquets gerados (396 arquivos) |

### F1 — Screening Rápido

| Documento | Conteúdo |
|-----------|----------|
| `scripts/f1_full_scan_v87_test.py` | Script de screening (4,032 combos/variante) |
| `docs/WIN_docs/F1_V87_TEST_*.csv` | Resultados F1 por sinal |
| `engines/README.md` | Motores F1/F2/F3, sampling study |

### F2 — Otimização Completa

| Documento | Conteúdo |
|-----------|----------|
| `engines/f2_optimization_v87.py` | Script de otimização com GridAdvisor |
| `scripts/grid_advisor.py` | GridAdvisor: ZOOM/EXPAND/STOP |
| `docs/WIN_docs/F2_GRID_ADVISOR_INTEGRACAO.md` | Documentação técnica do GridAdvisor |
| **`docs/WIN_docs/F2_GRIDS_POR_FAMILIA.md`** | **GRIDS POR FAMÍLIA: Trend, Mean Rev, Breakout, etc.** |
| `docs/WIN_docs/F2_OPTIMIZATION_*.csv` | Resultados F2 por sinal |

### F3 — Validação Tick-by-Tick

| Documento | Conteúdo |
|-----------|----------|
| `engines/f3_tick_ba.py` | Validação com ticks bid/ask reais |
| `engines/README.md` | Modo busca vs produção |
| `docs/WIN_docs/F3_VALIDATION_FINAL.csv` | Validação top 3 configs |

### F4 — DNA Analysis + Guardrails

| Documento | Conteúdo |
|-----------|----------|
| `scripts/dna_analysis_v87_final.py` | DNA + projeção de guardrails |
| `docs/WIN_docs/DNA_ANALYSIS_FINAL_*.md` | Relatórios DNA por sinal |
| `docs/WIN_docs/DNA_ANALYSIS_FINAL_*.json` | JSON com guardrails sugeridos |

### F5/F6 — Ensemble

| Documento | Conteúdo | Status |
|-----------|----------|--------|
| `scripts/ensemble_overlap_matrix.py` | Matriz de overlap (23 sinais) | ❌ A criar |
| `engines/f3_ensemble_optimization.py` | Otimização de pesos | ❌ A criar |

---

## 📚 DOCUMENTAÇÃO LEGADA (V6.6)

| Documento | Status | Nota |
|-----------|--------|------|
| `GUIA_CICLOS.md` | ⚠️ DESATUALIZADO | Use GUIA_CICLOS_V87.md |
| `ARQUITETURA_V86_PIPELINE.md` | ⚠️ LEGADO | Pipeline V6.6 (referência histórica) |
| `V86_HYBRID_DOCUMENTACAO.md` | ⚠️ LEGADO | V8.6 Hybrid (referência histórica) |
| `STATUS_V86_V87.md` | ⚠️ LEGADO | Comparação V6.6 vs V8.7 |

---

## 🔧 DOCUMENTAÇÃO TÉCNICA

| Documento | Conteúdo |
|-----------|----------|
| `CLAUDE.md` | Regras de engine, períodos, custos, sinais |
| `AGENTS.md` | Persona, pipeline de dados, implementação |
| `backtest/README_INDICATORS.md` | Indicadores base + microestrutura |
| `data/README_DADOS.md` | Inventário de dados, períodos |
| `engines/README.md` | Motores F1/F2/F3, fixes tick-a-tick |

---

## 📊 RESULTADOS E TESTES

| Documento | Conteúdo |
|-----------|----------|
| `docs/WIN_docs/F1_V87_TEST_PA_SIGNAL_DIR.csv` | F1: +136K PnL, 615 trades, 51.9% WR |
| `docs/WIN_docs/F2_OPTIMIZATION_PA_SIGNAL_DIR_BUY.csv` | F2: +5K PnL, 101 trades, 83.2% WR |
| `docs/WIN_docs/PLANO_IMPLEMENTACAO_F2.md` | Timeline e status de implementação |

---

## 🚀 PRÓXIMOS PASSOS

1. **Testar F2 em todos 22 sinais** — Ajustar filtros (muito agressivos)
2. **Testar F4 (DNA Analysis)** — Validar sugestões de guardrails
3. **Criar F5 (Overlap Matrix)** — Implementar matriz de sobreposição
4. **Criar F6 (Ensemble Optimization)** — Otimizar pesos do ensemble
5. **Testar pipeline completo F0→F6** — Todos 22 sinais

---

**Última Atualização**: 2026-05-04
**Autor**: WIN Lead Quant Scientist
