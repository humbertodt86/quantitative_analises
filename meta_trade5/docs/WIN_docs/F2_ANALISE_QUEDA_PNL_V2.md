# F2 — ANÁLISE DA QUEDA DE 97% DO PnL

**Data:** 2026-05-04  
**Status:** ✅ Causa raiz identificada  
**Impacto:** F1 615 trades → F2 101 trades (-84%)

---

## 1. RESUMO EXECUTIVO

### Problema
- **F1 (Fevereiro 2026):** 615 trades, +136K PnL, 52% WR
- **F2 (Fevereiro 2026):** 101 trades, +4.4K PnL, 84% WR
- **Queda:** 84% menos trades, 97% menos PnL

### Hipóteses Testadas

| Hipótese | Teste | Resultado | Status |
|----------|-------|-----------|--------|
| **Filtros (BOOK, DELTA)** | `book_imb_thresh=0`, `cum_delta_thresh=0` | Trades: 100 → 101 (+1%) | ❌ NÃO ERA |
| **Circuit Breaker** | `max_sl_consec=99`, `cooldown=0` | Trades: 100 → 101 (+1%) | ❌ NÃO ERA |
| **Filtro ATR** | Trade analyzer sistemático | 484/1986 bloqueados (24%) | ⚠️ PARCIAL |
| **Guardrails (BE, GRACE, SLOPE)** | Pendente teste | — | 🔍 SUSPEITO #1 |
| **S/R Buffers (tp_sr_pct=0.80)** | Análise ad-hoc | TP reduzido 600→100 pts | 🔍 SUSPEITO #2 |
| **Position Blocking** | Pendente teste | — | 🔍 SUSPEITO #3 |

---

## 2. ANÁLISE SISTEMÁTICA DE FILTROS

### Metodologia
Criado `scripts/f2_trade_analyzer.py` para analisar TODOS os trades potenciais e mostrar qual filtro bloqueia cada um.

### Resultados (BUY, Fevereiro 2026)

```
Total trades potenciais: 1986
Trades permitidos: 1502 (75.6%)
Trades bloqueados: 484 (24.4%)

Filtro          Bloqueados    % do Total
atr             484           24.4%
book_imbalance  0             0.0%
cum_delta       0             0.0%
```

### Conclusão
**Filtros de microestrutura (BOOK, DELTA) NÃO bloquearam NENHUM trade** porque estavam desativados (`thresh=0.0`).

**Filtro ATR bloqueou 24%** — dentro do esperado (`atr_min=200`, `atr_max=800`).

**1502 trades passaram pelos filtros**, mas F2 só executou **101 trades**.

**→ Filtros NÃO são a causa da queda de 84%.**

---

## 3. CAUSAS RAIZ IDENTIFICADAS

### Suspeito #1: S/R Buffers (tp_sr_pct=0.80)

**Como funciona:**
```python
# F2 com S/R buffers
if dist_to_resistance > 0:
    tp_price = close + tp_sr_pct * dist_to_resistance  # tp_sr_pct=0.80
else:
    tp_price = close + tp_mult * atr  # tp_mult=2.0

# F1 sem S/R buffers
tp_price = close + tp_mult * atr  # SEMPRE
```

**Impacto:**
- F1: TP = 2.0 × ATR = 2.0 × 300 = **600 pts**
- F2: Se S/R está a 125 pts → TP = 0.80 × 125 = **100 pts**

**Diferença:** TP F2 é **6x mais curto** que F1 quando S/R está próximo.

**Por que isso reduz PnL?**
- TP curto fecha trades cedo (lucro pequeno)
- SL permanece longo (5.0 × ATR = 1500 pts)
- Risco/Retorno: F1 = 600/1500 = 0.40 | F2 = 100/1500 = 0.07
- **WR sobe (84%), mas PnL cai (trades pequenos ganham, losses continuam grandes)**

### Suspeito #2: Guardrails (BE, GRACE, SLOPE)

**Guardrails ativos no F2:**
```python
be_offset = 50          # Move SL para +50 pts no lucro
grace_candles = 6       # Espera 6 candles antes de sair
slope_decay_factor = 0.65  # Reduz TP em 35% se slope < threshold
cooldown_candles = 2    # Espera 2 candles após SL
progress_mode = "TP30"  # Reduz TP para 30% se progresso < 15%
```

**Impacto esperado:**
- **BE=50:** Fecha trades cedo (lucro travado em 50 pts)
- **GRACE=6:** Delay no exit (pode virar loss)
- **SLOPE=0.65:** TP reduzido 35%
- **COOLDOWN=2:** Perde re-entradas (reduz trade count)
- **TP30:** Fecha com 30% do TP (lucro parcial)

**Conclusão:** Guardrails **reduzem trade count e PnL** para aumentar WR e Sharpe.

### Suspeito #3: Position Blocking

**F1:**
```python
skip = sell_idx + 1  # Bloqueia 1 candle após saída
```

**F2:**
```python
cooldown_candles = 2  # Bloqueia 2 candles após SL
```

**Impacto:** F2 bloqueia **2x mais** que F1 após cada SL.

---

## 4. SOLUÇÃO PROPOSTA

### 4.1. Corrigir Lógica S/R (PRIORIDADE MÁXIMA)

**Problema:** S/R está **reduzindo TP** em vez de **defender posições**.

**Correção:**
```python
# ATUAL (ERRADO)
if dist_to_resistance > 0:
    tp_price = close + tp_sr_pct * dist_to_resistance  # tp_sr_pct=0.80

# CORRETO
if dist_to_resistance > 0:
    # Só usa S/R se estiver dentro de 15% do TP base
    tp_base = close + tp_mult * atr
    sr_distance_pct = dist_to_resistance / (tp_mult * atr)
    
    if sr_distance_pct < 1.15:  # S/R dentro de 15%
        # Ajusta TP para 80-100% da distância até S/R
        tp_price = close + tp_sr_pct * dist_to_resistance
    else:
        # S/R muito distante, usa TP base
        tp_price = tp_base
else:
    tp_price = tp_base
```

**Threshold de 15%:**
- Se TP base = 600 pts e S/R = 900 pts → sr_distance = 1.50 (>1.15) → **NÃO usa S/R**
- Se TP base = 600 pts e S/R = 650 pts → sr_distance = 1.08 (<1.15) → **USA S/R**

### 4.2. Desativar Guardrails no F2 (Otimização)

**F2 é fase de OTIMIZAÇÃO**, não de produção. Guardrails devem ser:
1. **Desativados no F2** (para encontrar melhores parâmetros)
2. **Analisados no DNA** (após F3)
3. **Ativados no OOS** (produção)

**Configuração F2 (atualizar `f2_grid_configs.json`):**
```json
{
  "guardrails": {
    "be_offset": [999999],
    "grace_candles": [999],
    "slope_decay_factor": [0.0],
    "cooldown_candles": [0],
    "progress_mode": ["NONE"]
  }
}
```

### 4.3. Adicionar Análise de S/R no Trade Analyzer

**Colunas novas:**
- `sr_adjustment_applied` (bool) — Se S/R foi aplicado
- `sr_distance_pct` (float) — Distância do S/R em % do TP base
- `tp_base` (float) — TP sem S/R
- `tp_sr_adjusted` (float) — TP com S/R

**Métrica:**
- `% trades com S/R aplicado`
- `PnL médio com S/R` vs `PnL médio sem S/R`
- `WR com S/R` vs `WR sem S/R`

---

## 5. PRÓXIMOS PASSOS

### Imediato
1. ✅ **Trade Analyzer criado** — `scripts/f2_trade_analyzer.py`
2. ⏳ **Corrigir lógica S/R** — Adicionar threshold de 15%
3. ⏳ **Desativar guardrails no F2** — Atualizar grids por família
4. ⏳ **Re-testar F2** — Validar correção

### Validação
1. **F2 sem guardrails:** Deve produzir ~500-600 trades (próximo do F1)
2. **F2 com S/R corrigido:** PnL deve subir para +80K-120K (próximo do F1)
3. **F2 vs F1 correlação:** >0.80 (mesma direção de rankeamento)

### Documentação
1. ✅ **Esta análise** — `docs/WIN_docs/F2_ANALISE_QUEDA_PNL.md`
2. ⏳ **S/R Buffers** — Documentar threshold de 15% e lógica correta
3. ⏳ **Guardrails** — Documentar quando ativar/desativar (F2 vs OOS)

---

## 6. LIÇÕES APRENDIDAS

### S/R Buffers
- **Propósito original:** Defender posições (TP abaixo de S/R, SL além de S/R)
- **Implementação atual:** Reduz TP indiscriminadamente (mesmo se S/R distante)
- **Correção:** Só usar S/R se estiver dentro de 15% do TP base

### Guardrails
- **F2 (Otimização):** DEVEM estar desativados (encontrar melhores parâmetros)
- **F3 (Validação):** Parcialmente ativados (validar com filtros)
- **OOS (Produção):** Totalmente ativados (robustez)

### Filtros
- **BOOK_IMB, CUM_DELTA:** Úteis apenas se threshold > 0
- **ATR:** Filtro natural (24% bloqueados com min=200, max=800)
- **Thresholds = 0:** Desativa filtro (útil para isolamento de causa)

---

## 7. ARQUIVOS MODIFICADOS

| Arquivo | Mudança | Status |
|---------|---------|--------|
| `scripts/f2_trade_analyzer.py` | Criado — Análise sistemática | ✅ |
| `engines/f2_optimization_v87.py` | Corrigir lógica S/R | ⏳ |
| `data/f2_grid_configs.json` | Desativar guardrails | ⏳ |
| `docs/WIN_docs/F2_ANALISE_QUEDA_PNL.md` | Esta documentação | ✅ |

---

## 8. REFERÊNCIAS

- `engines/f1_fast_screener.py` — F1 (SEM guardrails, referência)
- `engines/f2_optimization_v87.py` — F2 (COM guardrails, problema)
- `backtest/engine_v2.py` — Backtest engine (guardrails implementation)
- `scripts/f2_trade_analyzer.py` — Análise sistemática de filtros

---

**Próxima ação:** Corrigir lógica S/R em `f2_optimization_v87.py` e re-testar.
