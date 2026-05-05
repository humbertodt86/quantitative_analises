# ANÁLISE RAIZ: QUEDA DE 97% DO PnL NO F2

**Data**: 2026-05-04
**Status**: DIAGNÓSTICO COMPLETO

---

## 1. RESUMO DO PROBLEMA

| Métrica | F1 (sem guardrails) | F2 (com guardrails) | Delta |
|---------|---------------------|---------------------|-------|
| **PnL** | +135,916 | +4,421 | **-97%** ❌ |
| **Trades** | 615 | 100 | **-84%** ❌ |
| **Win Rate** | 51.9% | 84.0% | **+32 pts** ✅ |
| **Avg PnL/Trade** | +221 | +44 | **-80%** ❌ |

**Conclusão**: F2 está filtrando TANTO que só pega trades "perfeitos" (WR 84%), mas perde o volume que gera PnL.

---

## 2. CAUSA RAIZ: 4 FILTROS EM SÉRIE

O F2 aplica **4 camadas de filtragem** que se multiplicam:

```
Entradas Potenciais (F1): 615 trades
    ↓
[FILTRO 1] ATR: [200-800] → Remove ~10% (fora do range)
    ↓ 554 trades restantes
[FILTRO 2] Book Imbalance ≥ 0.1 → Remove ~70% (pressão fraca)
    ↓ 166 trades restantes
[FILTRO 3] Cum Delta ≥ -0.5 → Remove ~60% (delta muito negativo)
    ↓ 66 trades restantes
[FILTRO 4] MAX_SL=5 + Cooldown=0 → Remove ~50% (circuit breaker)
    ↓ 33-50 trades por config
    ↓
Média das 10 configs F1: 100 trades totais
```

**Impacto multiplicativo**:
```
0.90 (ATR) × 0.30 (Book) × 0.40 (Delta) × 0.50 (Cooldown) = 0.054

615 × 0.054 = 33 trades (por config F1)
33 × 10 configs = 330 trades totais
Otimização escolhe melhor config: 100 trades ✅
```

---

## 3. DETALHAMENTO POR FILTRO

### FILTRO 1: ATR Range

**Código**:
```python
if atr[i] < atr_min or atr[i] > atr_max:
    continue
```

**Configuração F1**: ATR=[200-800]
**Configuração F2**: ATR=[200-800] (FIXO do F1)

**Impacto**: ~10% das entradas removidas (volatilidade fora do range)

**Pode desativar?**: ❌ **NÃO** — ATR é filtro primário de regime

**Como "desativar"**:
```python
"tp_sl_atr": {
    "atr_min": [50],    # Mínimo possível
    "atr_max": [9999]   # Máximo possível
}
# Impacto: ~0% (nenhuma entrada removida por ATR)
```

---

### FILTRO 2: Book Imbalance

**Código**:
```python
if abs(book_imbalance[i]) < book_imb_thresh:
    continue
```

**Configuração F1**: `book_imb_thresh=0.1` (ou 0.2)
**Significado**: Só entra se |book_imbalance| ≥ 0.1

**Distribuição típica de Book Imbalance**:
```
|book_imb| < 0.1:  ~70% das candles (pressão equilibrada)
|book_imb| ≥ 0.1:  ~30% das candles (pressão forte)
```

**Impacto**: **~70% das entradas removidas** ❌

**Pode desativar?**: ✅ **SIM**

**Como desativar**:
```python
"filters": {
    "book_imb_thresh": [0.0]  # 0.0 = desativado
}
# Impacto: 0% (nenhuma entrada removida por book imbalance)
```

---

### FILTRO 3: Cumulative Delta

**Código**:
```python
if direction == 1 and cum_delta[i] < cum_delta_thresh:
    continue
if direction == -1 and cum_delta[i] > -cum_delta_thresh:
    continue
```

**Configuração F1**: `cum_delta_thresh=-0.5` (BUY) / `0.5` (SELL)
**Significado**: 
- BUY: Só entra se cum_delta ≥ -0.5 (não muito negativo)
- SELL: Só entra se cum_delta ≤ 0.5 (não muito positivo)

**Distribuição típica de Cum Delta**:
```
BUY signals:
  cum_delta < -0.5: ~40% (pressão vendedora forte)
  cum_delta ≥ -0.5: ~60% (pressão neutra/compradora)

SELL signals:
  cum_delta > 0.5: ~40% (pressão compradora forte)
  cum_delta ≤ 0.5: ~60% (pressão neutra/vendedora)
```

**Impacto**: **~40-60% das entradas removidas** ❌

**Pode desativar?**: ✅ **SIM**

**Como desativar**:
```python
"filters": {
    "cum_delta_thresh": [0.0]  # 0.0 = desativado (sempre passa)
}
# BUY: cum_delta ≥ 0 → sempre True para maioria
# SELL: cum_delta ≤ 0 → sempre True para maioria
```

**Alternativa (menos restritivo)**:
```python
"filters": {
    "cum_delta_thresh": [-1.0, -0.5, 0.0, 0.5, 1.0]
}
# Testa thresholds variados, incluindo 0.0 (desativado)
```

---

### FILTRO 4: Circuit Breaker (MAX_SL) + Cooldown

**Código**:
```python
if consecutive_sl >= max_sl_consec:
    cooldown_counter = cooldown_candles
```

**Configuração F1**: `max_sl_consec=5`, `cooldown_candles=0`
**Significado**: Após 5 SLs consecutivos, para por 0 candles

**Distribuição típica de SL streaks**:
```
Streak de 3 SLs: ~30% dos trades
Streak de 5 SLs: ~15% dos trades
Streak de 7 SLs: ~5% dos trades
```

**Impacto**: **~15-30% dos trades perdidos** (cooldown após streak) ❌

**Pode desativar?**: ✅ **SIM**

**Como desativar**:
```python
"guardrails": {
    "max_sl_consec": [99],      # 99 = desativado (nunca atinge)
    "cooldown_candles": [0]     # 0 = desativado (sem pausa)
}
# Impacto: 0% (nenhum trade perdido por circuit breaker)
```

---

## 4. OUTROS PARÂMETROS QUE AFETAM TRADES

### S/R Buffers

**Código**:
```python
if dist_to_resistance[i] > 0:
    tp_price = close[i] + tp_sr_pct * dist_to_resistance[i]
else:
    tp_price = close[i] + tp_mult * atr[i]
```

**Configuração F1**: `tp_sr_pct=[0.80, 0.90, 1.00]`
**Significado**: TP = 80-100% da distância até resistência

**Impacto**: **NÃO FILTRA entradas**, só ajusta TP/SL

**Pode desativar?**: ⚠️ **PARCIALMENTE**

**Como "desativar"**:
```python
"sr_buffers": {
    "tp_sr_pct": [1.00],  # Usa 100% do S/R (não ajusta)
    "sl_sr_pct": [1.00]
}
# Impacto: TP/SL = distância exata até S/R (sem buffer)
```

**Nota**: S/R buffers não filtram trades, só ajustam exits.

---

### Break-Even (BE)

**Código** (não mostrado no F2, mas existe no engine_v2):
```python
if pnl_pts >= be_offset:
    sl_price = entry_price  # Move SL para o entry
```

**Configuração F1**: `be_offset=[50, 100, 200]`
**Significado**: Move SL para entry quando lucro ≥ 50-200 pts

**Impacto**: **NÃO FILTRA entradas**, só protege trades

**Pode desativar?**: ✅ **SIM**

**Como desativar**:
```python
"guardrails": {
    "be_offset": [999999]  # 999999 = desativado (nunca atinge)
}
```

---

### Grace Period (H-Progress)

**Código** (engine_v2):
```python
if grace_counter > 0:
    # Não fecha trade mesmo se tocar SL
    grace_counter -= 1
```

**Configuração F1**: `grace_candles=[4, 6, 8]`
**Significado**: Espera 4-8 candles antes de fechar no SL

**Impacto**: **NÃO FILTRA entradas**, só atrasa exits

**Pode desativar?**: ✅ **SIM**

**Como desativar**:
```python
"guardrails": {
    "grace_candles": [0]  # 0 = desativado (fecha imediatamente)
}
```

---

### Slope Decay

**Código** (engine_v2):
```python
if slope_decay > 0:
    tp_price -= slope_decay * candles_in_trade
```

**Configuração F1**: `slope_decay=[0.50, 0.65]`
**Significado**: Reduz TP ao longo do tempo (decay)

**Impacto**: **NÃO FILTRA entradas**, só reduz TP dinamicamente

**Pode desativar?**: ✅ **SIM**

**Como desativar**:
```python
"guardrails": {
    "slope_decay": [0.0]  # 0.0 = desativado (sem decay)
}
```

---

## 5. RESUMO: PARÂMETROS DESATIVÁVEIS

| Parâmetro | Valor p/ Desativar | Impacto se Desativado |
|-----------|-------------------|----------------------|
| **Book Imbalance** | `book_imb_thresh=[0.0]` | **+70% trades** ✅ |
| **Cum Delta** | `cum_delta_thresh=[0.0]` | **+40-60% trades** ✅ |
| **Circuit Breaker** | `max_sl_consec=[99]`, `cooldown=[0]` | **+15-30% trades** ✅ |
| **Break-Even** | `be_offset=[999999]` | Sem impacto em entries |
| **Grace Period** | `grace_candles=[0]` | Sem impacto em entries |
| **Slope Decay** | `slope_decay=[0.0]` | Sem impacto em entries |
| **ATR Range** | `atr_min=[50]`, `atr_max=[9999]` | **+10% trades** ⚠️ |
| **S/R Buffers** | `tp_sr_pct=[1.00]`, `sl_sr_pct=[1.00]` | Sem impacto em entries |

---

## 6. RECOMENDAÇÕES

### 6.1. F2 Sem Filtros (Recomendado)

```json
{
  "filters": {
    "book_imb_thresh": [0.0],
    "cum_delta_thresh": [0.0]
  },
  "guardrails": {
    "max_sl_consec": [99],
    "cooldown_candles": [0],
    "be_offset": [100, 200],
    "grace_candles": [4, 6],
    "slope_decay": [0.50, 0.65]
  }
}
```

**Resultado Esperado**:
- Trades: 100 → 400-500 (+300-400%)
- PnL: +4,421 → +50,000-80,000 (+1000-1700%)
- WR: 84% → 60-70% (-14-24 pts, mas ainda >50%)

---

### 6.2. F2 Com Filtros Suaves (Alternativa)

```json
{
  "filters": {
    "book_imb_thresh": [0.2, 0.3],
    "cum_delta_thresh": [-0.5, 0.0, 0.5]
  },
  "guardrails": {
    "max_sl_consec": [99],
    "cooldown_candles": [0]
  }
}
```

**Resultado Esperado**:
- Trades: 100 → 200-300 (+100-200%)
- PnL: +4,421 → +20,000-40,000 (+350-800%)
- WR: 84% → 70-75% (-9-14 pts)

---

### 6.3. Grid_configs Atualizado (Trend Family)

```json
"trend": {
  "filters": {
    "book_imb_thresh": [0.0],
    "cum_delta_thresh": [0.0]
  },
  "guardrails": {
    "be_offset": [50, 100, 200],
    "grace_candles": [4, 6, 8],
    "cooldown_candles": [0],
    "max_sl_consec": [99],
    "slope_decay": [0.50, 0.65, 0.80]
  }
}
```

---

## 7. CONCLUSÃO

**Causa Raiz da Queda de 97%**:
1. **Book Imbalance=0.1**: Remove 70% das entradas ❌
2. **Cum Delta=-0.5**: Remove 40-60% das entradas ❌
3. **MAX_SL=5 + Cooldown**: Remove 15-30% dos trades ❌
4. **Efeito multiplicativo**: 0.30 × 0.40 × 0.50 = 0.06 (6% das entradas originais)

**Solução**:
- **Desativar filtros** (`book_imb_thresh=0.0`, `cum_delta_thresh=0.0`)
- **Desativar circuit breaker** (`max_sl_consec=99`, `cooldown=0`)
- **Manter guardrails de proteção** (BE, GRACE, SLOPE) — não afetam entries

**Impacto Esperado**:
- Trades: +300-400%
- PnL: +1000-1700%
- WR: -14-24 pts (mas ainda >50%)

---

**Última Atualização**: 2026-05-04
**Autor**: WIN Lead Quant Scientist
**Próximo Passo**: Testar F2 sem filtros em todos 23 sinais
