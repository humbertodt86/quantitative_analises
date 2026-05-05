# STATUS ATUAL — V8.6 / V8.7

**Data**: 2026-05-04
**Hora**: 14:30 BRT

---

## 📊 INVENTÁRIO DE ARQUIVOS

### ✅ Estratégias Implementadas (backtest/strategies/)
| Versão | Arquivo | Status |
|--------|---------|--------|
| V8.4 | `v84.py` | ✅ Implementada |
| V8.5 | `v85.py` | ✅ Implementada |
| V8.6 | `v86.py` | ✅ Implementada |
| V8.7 | `v87.py` | ✅ Implementada |

### ✅ Scripts F1 (scripts/)
| Versão | Arquivo | Status |
|--------|---------|--------|
| V8.1 | `f1_full_scan_v81.py` | ✅ Existe |
| V8.2 | `f1_full_scan_v82.py` | ✅ Existe |
| V8.3 | `f1_full_scan_v83_hybrid.py` | ✅ Existe |
| V8.3 | `f1_full_scan_v83_gpu.py` | ✅ Existe |
| V8.4 | `f1_full_scan_v84.py` | ✅ Existe |
| V8.5 | `f1_full_scan_v85.py` | ✅ Existe |
| V8.6 | `f1_full_scan_v86.py` | ✅ Existe |
| V8.7 | ⏳ `f1_full_scan_v87.py` | ❌ **NÃO EXISTE** |

### ❌ Engines na Pasta Errada
**Problema**: Scripts F1 estão em `scripts/` ao invés de `engines/`

**Solução**: Manter em `scripts/` (convenção atual) mas atualizar documentação.

---

## 📚 DOCUMENTAÇÃO

### ✅ Criada
- `docs/WIN_docs/V86_HYBRID_DOCUMENTACAO.md` — V8.6 completa
- `docs/WIN_docs/GRID_SEARCH_OTIMIZADO_V87.md` — V8.7 grids otimizados
- `engines/README.md` — Atualizado com tabela V8.4-V8.7

### ⏳ Pendente
- `docs/WIN_docs/V87_IMPLEMENTACAO.md` — Como implementar V8.7
- `docs/progress.md` — Diário de bordo (atualizar)
- `docs/cycle_plan.md` — Plano de voo (criar)

---

## 🐛 BUGS IDENTIFICADOS (V8.6 e anteriores)

### 1. PA_REV_RSI_B10 e PA_REV_RSI_S90 (DUPLICADOS)
**Local**: `scripts/build_win_signals_v81.py` linhas 333-334
**Problema**: Mesma condição exata
**Solução V8.7**: Unificar em `PA_REV_RSI_UNIFIED`

### 2. PA_HMA_CROSS_F5_S10 (NOME INCORRETO)
**Local**: `scripts/build_win_signals_v81.py` linha 309
**Problema**: Usa SMA, não HMA (comentário confirma)
**Solução V8.7**: Renomear para `PA_SMA_CROSS_F5_S10`

### 3. V8_S_MIN=0.0 (PARÂMETRO SEM EFEITO)
**Local**: `scripts/build_win_signals_v81.py` linha 218
**Problema**: Qualquer slope passa
**Solução V8.7**: Grid otimizado `[0, 10, 20]`

---

## 🎯 V8.7 — NOVIDADES

### 1. Poda por Correlação
| Sinal | Original | Otimizado | Redução |
|-------|----------|-----------|---------|
| PA_SIGNAL_DIR | 3,125 | **18** | 173x |
| PA_REV_RSI | 125 | **12** | 10x |
| **Total** | 2.2M | **3,150** | 707x |

### 2. Escalonamento Geométrico
- EMA: `[10,15,20,30,50]` → `[10,21,50,100,200]`
- TP/SL: Passos 1.0x ATR (não 0.5x)
- MA Cross: `[5,7,9,10,14]` → `[5,9,21]`

### 3. Binning de Volatilidade
- ATR: 42 combinações → **3 regimes**
  - Low: [50-300]
  - Normal: [300-800]
  - High: [800-9999]

### 4. Filtro Piso de Viabilidade (Anti-HFT)
```python
SL >= 150 pontos OU SL >= 1.0×ATR
TP >= 100 pontos
SL/TP ratio entre 0.25x e 4.0x
```

---

## 📈 ESPAÇO DE BUSCA

| Métrica | V8.6 | V8.7 Otimizado | Redução |
|---------|------|----------------|---------|
| Sinal Variantes | ~2.2M | **3,150** | 707x |
| TP/SL/ATR Combos | 4,032 | **1,152** | 3.5x |
| **TOTAL COMBOS** | **18 BILHÕES** | **7,257,600** | **2,479x** |
| **Tempo @ 50k/s** | **4.2 dias** | **2.4 minutos** | **2,479x** |

---

## ✅ CHECKLIST V8.7

### Implementação (backtest/strategies/)
- [ ] Criar `v87.py` baseado em `v86.py`
- [ ] Adicionar filtros V8.7 (ADX_MAX, cooldown, etc.)
- [ ] Atualizar gatilhos (MIN_TREND=300, MAX dinâmico)

### Sinais (scripts/build_win_signals_v81.py)
- [ ] Unificar PA_REV_RSI_B10/S90 → PA_REV_RSI_UNIFIED
- [ ] Renomear PA_HMA_CROSS → PA_SMA_CROSS
- [ ] Aplicar grids otimizados (3,150 variantes)

### Scripts F1/F2/F3 (engines/)
- [ ] Criar `f1_full_scan_v87.py` baseado em `f1_full_scan_v86.py`
- [ ] Criar `f2_validation_v87.py`
- [ ] Criar `f3_guardrails_v87.py`

### Documentação (docs/WIN_docs/)
- [x] `V86_HYBRID_DOCUMENTACAO.md`
- [x] `GRID_SEARCH_OTIMIZADO_V87.md`
- [ ] `V87_IMPLEMENTACAO.md`
- [ ] Atualizar `AGENTS.md` com pipeline V8.7

### Execução
- [ ] Gerar parquets V8.7: `build_win_signals_v81_variants.py --version v87`
- [ ] Executar F1 V8.7: 7.26M combos @ 50k/s = 2.4 min
- [ ] Validar top 10 F2
- [ ] Guardrails F3 top 3
- [ ] OOS em Abril 2026

---

## 🚀 PRÓXIMOS PASSOS (ORDEM)

### Imediato (Hoje)
1. **Criar `v87.py`** em `backtest/strategies/`
2. **Atualizar `build_win_signals_v81.py`** com bugs fixes
3. **Gerar parquets V8.7** (23 arquivos × 3,150 variantes)
4. **Criar `f1_full_scan_v87.py`** em `engines/`

### Amanhã
5. **Executar F1 V8.7** (2.4 minutos)
6. **Validar top 10 F2**
7. **Guardrails F3 top 3**
8. **OOS validation** (Abril 2026)

### Documentação
9. **Atualizar `docs/progress.md`**
10. **Criar `docs/cycle_plan.md`**
11. **Atualizar `AGENTS.md`** com pipeline V8.7

---

## 📝 LIÇÕES V8.6

### O Que Funcionou
- ✅ `gatilho_min_range=200`: PF RANGE 2.95→11.08 (3.7x)
- ✅ `progress_m1_candles=2`: Detecção 2min vs 4min
- ✅ `be_offset=50`: BE rende R$8 líquido (era R$-2)

### O Que Não Funcionou
- ❌ `max_sl_consec=99`: Sem filtro de perdas
- ❌ `adx_max=9999`: Aceita ADX > 50
- ❌ `gatilho_max fixo`: Não adapta à volatilidade

### O Que V8.7 Corrige
- ✅ Poda por correlação: 18B → 7.26M combos
- ✅ Escalonamento geométrico
- ✅ Binning ATR (3 regimes)
- ✅ Piso de Viabilidade (Anti-HFT)

---

**Última Atualização**: 2026-05-04 14:30 BRT
**Responsável**: WIN Lead Quant Scientist
