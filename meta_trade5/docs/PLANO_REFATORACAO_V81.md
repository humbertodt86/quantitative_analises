# Plano de Refatoracao — Sinais PA_* WIN V8.1

**Versao:** V8.1-PLAN  
**Data:** 2026-05-03  
**Autor:** Sisyphus  
**Status:** Aprovado para implementacao

---

## 1. Objetivo

Consolidar o codigo de geracao de sinais de **5+ scripts fragmentados** em **1 script unico**, reduzir de **241 para ~30 variantes**, corrigir bugs, renomear sinais enganosos, e executar F1 full scan.

**Entregaveis:**
1. `scripts/build_win_signals_v81.py` — rebuild completo
2. `super_win_continuous.parquet` — ~30 colunas PA_*
3. F1 full scan executado
4. Documentacao atualizada

---

## 2. Problemas Atuais

| Problema | Impacto | Solucao |
|----------|---------|---------|
| 8+ scripts mutam parquet in-place | Fragil, ordem importa | 1 script rebuild |
| 241 variantes PA_* | Overfitting | ~30 variantes |
| Nomes enganosos | Confusao | Renomear |
| ADX7_DELTA shift(1) | 99.8% errado | shift(3) |
| PA_TUESDAY desatualizado | Usa DEPRECATED | Consolidar |

---

## 3. Fases

### FASE 1: Criar build_win_signals_v81.py
- Consolidar todos os scripts em 1
- Corrigir bugs (range_ratio, ADX7_DELTA)
- Gerar ~30 sinais (ver lista abaixo)

### FASE 2: Rebuild Parquet
- Executar script
- Validar PA_SIGNAL_DIR
- Backup + substituir

### FASE 3: Atualizar Consumidores
- f1_screen_signal_dir_variants.py
- signal_discovery.py
- build_strategy_queue.py
- Scripts F2/F3

### FASE 4: F1 Full Scan
- Rodar signal_discovery (~30 x 3 regimes)
- Top 10 → F2
- Top 3 → F3
- OOS final

### FASE 5: Documentacao
- progress.md
- GUIA_DE_CICLOS.md
- Relatorios F1/F2/F3/OOS

### FASE 6: Limpeza
- Remover scripts obsoletos
- Atualizar README

---

## 4. Sinais a Manter (~30)

| Sinal | Tipo | Herda DIR? | Variante |
|-------|------|------------|----------|
| PA_SIGNAL_DIR | Trend | N/A | V8.0 otimizado |
| PA_SIGNAL_DIR_V2 | Trend | N/A | Experimental |
| PA_SIGNAL_REV | Trend | N/A | Inverso DIR |
| PA_STRONG_TREND | Trend | Sim | A25_S20 |
| PA_SLOPE_TREND | Trend | Sim | S25_A25 |
| PA_ADX_BREAK | Momentum | Sim | A25 |
| PA_EXHAUST | Momentum | Sim | Dn1_0_M40 |
| PA_GK_BREAK | Breakout | Sim | G0_001 |
| PA_VCP | Pattern | Sim | C0_6 |
| PA_MA_CROSS | Trend | Nao | F9_S21 |
| PA_HMA_CROSS | Trend | Nao | F5_S10 |
| PA_EFF_RATIO | Regime | Sim | E0_6 |
| PA_CHOP | Regime | Sim | C38_2 |
| PA_REV_RSI | Reversao | Nao | B10, S90 (2) |
| PA_VWAP_Z | Reversao | Nao | Z2_0 |
| PA_VWAP_REV | Reversao | Nao | D1_0 |
| PA_KELT_ATR | Reversao | Nao | M2_0 |
| PA_VWAP_STRETCH | Reversao | Nao | base |
| PA_MFI | Volume | Nao | B20 |
| PA_TSI | Momentum | Nao | T25 |
| PA_LIQ_GRAB | Micro | Nao | base |
| PA_TUESDAY | Calendar | Sim | base |

**Total:** 22 sinais base + 2 variantes REV_RSI = **24 colunas PA_***

**Removidos:**
- PA_SIGNAL_DIR_DEPRECATED
- 118 variantes PA_SIGNAL_DIR
- 8 variantes PA_REV_RSI
- Todas variantes redundantes das outras familias
- PA_GK_BREAK_G0_005 (11 ocorrencias)
- PA_BB_* (renomeado para PA_KELT_ATR)
- PA_POC_REV (renomeado para PA_VWAP_STRETCH)

---

## 5. Renomeacoes

| Nome Antigo | Nome Novo | Motivo |
|-------------|-----------|--------|
| PA_BB_M* | PA_KELT_ATR_M* | Usa ATR, nao std dev |
| PA_POC_REV | PA_VWAP_STRETCH | Nao e POC real |
| PA_HMA_CROSS_* | PA_MA_CROSS_* | Usa SMA, nao HMA |

---

## 6. Bugs a Corrigir

1. **range_ratio ordering:** Mover definicao para antes do V8.0
2. **ADX7_DELTA:** Usar shift(3), nao shift(1)
3. **PA_TUESDAY:** Computar apos V8.0, nao DEPRECATED
4. **PA_SIGNAL_DIR_V2:** Usar V8.0 como base, nao DEPRECATED

---

## 7. Critérios de Sucesso

- [ ] build_win_signals_v81.py executa sem erros
- [ ] Parquet tem ~24-30 colunas PA_*
- [ ] PA_SIGNAL_DIR identico ao atual
- [ ] ADX7_DELTA = shift(3)
- [ ] F1 scan completo
- [ ] Documentacao atualizada
- [ ] Scripts obsoletos removidos

---

## 8. Timeline Estimada

| Fase | Duração |
|------|---------|
| FASE 1 | 1 dia |
| FASE 2 | 4-6 horas |
| FASE 3 | 1 dia |
| FASE 4 | 2-3 dias |
| FASE 5 | 1 dia |
| FASE 6 | 1/2 dia |
| **TOTAL** | **6-7 dias** |
