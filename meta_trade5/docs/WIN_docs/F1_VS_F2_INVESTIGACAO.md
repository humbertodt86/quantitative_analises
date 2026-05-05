# F1 vs F2 — INVESTIGAÇÃO DE DIFERENÇA (615 → 40 trades)

**Data:** 2026-05-04  
**Status:** 🔍 Em investigação (causa raiz NÃO identificada)  
**Impacto:** F1 615 trades → F2 40 trades (-93.5%)

---

## 1. RESUMO DO PROBLEMA

### Testes Realizados

| Engine | Config | Trades | PnL | WR |
|--------|--------|--------|-----|-----|
| **F1** | TP=2.0, SL=5.0, ATR 200-800, hm=9-12 | 615 | +136K | 52% |
| **F2** | TP=2.0, SL=5.0, ATR 200-800, SEM guardrails, SEM S/R | 40 | +12.7K | 85% |

**Diferença:** -575 trades (-93.5%), -123K PnL (-90.7%)

### Hipóteses Testadas

| Hipótese | Teste | Resultado | Status |
|----------|-------|-----------|--------|
| **Guardrails (BE, GRACE, SLOPE)** | Todos desativados | Trades: 40 (igual) | ❌ NÃO ERA |
| **S/R Buffers** | tp_sr_pct=1.00, sr_threshold=999 | Trades: 40 (igual) | ❌ NÃO ERA |
| **Filtros (BOOK, DELTA)** | thresh=0.0 | Trades: 40 (igual) | ❌ NÃO ERA |
| **Cooldown** | cooldown_candles=0 | Trades: 40 (igual) | ❌ NÃO ERA |
| **Filtro de Hora** | F1 tem (hm=9,hx=12), F2 não | F1 deveria ter MENOS trades | ❌ NÃO ERA |
| **Lógica de Entrada** | **NÃO TESTADA DIRETAMENTE** | **?** | 🔍 **SUSPEITO #1** |
| **Position Blocking** | **NÃO TESTADO DIRETAMENTE** | **?** | 🔍 **SUSPEITO #2** |

---

## 2. DIFERENÇAS CONFIRMADAS

### Diferença #1: Filtro de Hora

**F1:**
```python
# f1_fast_screener.py, linha 183
mask = (hour >= hm) & (hour < hx) & (atr >= atr_min) & (atr <= 800)
# Default: hm=9, hx=12
```

**F2:**
```python
# f2_optimization_v87.py — NÃO TEM FILTRO DE HORA
# Apenas ATR filter
if atr[i] < atr_min or atr[i] > atr_max:
    continue
```

**Impacto:**
- F1 com hm=9,hx=12: **279 candles** (dentro do horário)
- F2 sem filtro: **944 candles** (todas)
- **F1 deveria ter MENOS trades, não mais!**
- **Conclusão:** NÃO explica 615 → 40

---

### Diferença #2: Estrutura de Dados

**F1:**
```python
# Matriz M: (n_entries, 225 samples)
M[i, :] = [tick_1, tick_2, ..., tick_225]  # 15 candles x 15 ticks
# TP/SL checa TODOS os 225 samples
sl_hit = M >= sl_th[:, None]  # Broadcast em 225 samples
tp_hit = M <= tp_th_final[:, None]
```

**F2:**
```python
# Candle-a-candle: usa HIGH/LOW
for i in range(n_rows):
    if direction == 1:
        tp_hit = high[i] >= tp_price
        sl_hit = low[i] <= sl_price
```

**Impacto:**
- F1: Vê 225 ticks por entrada
- F2: Vê apenas HIGH/LOW da candle
- **F1 pode detectar TP/SL em ticks intermediários que F2 não vê**
- **Conclusão:** PROVÁVEL causa da diferença

---

### Diferença #3: Position Blocking

**F1:**
```python
# f1_fast_screener.py, linhas 186-193
skip = -1
blocked = []
for idx in idx_order:
    if not mask[idx]: continue
    if sell_idx[idx] <= skip: continue  # Pula se dentro do blocking
    if had[idx]:
        skip = sell_idx[idx] + 1  # Bloqueia 1 candle
    blocked.append(pnl[idx])
```

**F2:**
```python
# f2_optimization_v87.py, linhas 75-122
in_position = False
cooldown_counter = 0

for i in range(n_rows):
    if cooldown_counter > 0:
        cooldown_counter -= 1
        continue
    
    if not in_position:
        # ... filters ...
        entry_price = close[i]
        in_position = True
    else:
        # Check exit
        if tp_hit or sl_hit:
            in_position = False
            # ... cooldown logic ...
```

**Impacto:**
- F1: Blocking é **pós-processamento** (após avaliar TODAS as entries)
- F2: Blocking é **state machine** (in_position=True durante o trade)
- **F2 pode bloquear entries enquanto está em posição**
- **Conclusão:** PROVÁVEL causa da diferença

---

## 3. HIPÓTESE PRINCIPAL

### F2 Está em Posição Por Muito Tempo

**Suspeita:** F2 entra em um trade e **fica em posição por muitas candles**, bloqueando todas as outras entries.

**Cenário:**
```
Candle 100: F2 entra BUY (TP=1050, SL=950)
Candle 101-150: Preço fica entre 950-1050 (nem TP, nem SL)
Candle 151: TP hit (preço=1050)

F1: Durante candle 100-150, avalia NOVAS entries (matriz M)
   → Pode entrar em candles 105, 110, 120, etc.
   → Total: 10 trades simultâneos/overlap

F2: Durante candle 100-150, in_position=True
   → BLOQUEIA todas as entries
   → Total: 1 trade (o original)
```

**Teste necessário:**
- Contar quantas candles F2 fica `in_position=True`
- Comparar com número de trades F1

---

### F1 Permite Overlap de Trades

**F1 não tem estado `in_position`**. Cada entrada é avaliada independentemente:

```python
# F1 avalia TODAS as entries de uma vez (broadcast numpy)
# Depois aplica position blocking como pós-processamento
for idx in idx_order:
    if sell_idx[idx] <= skip: continue  # Só bloqueia se overlap exato
```

**F2 tem estado `in_position`**. Avalia entrada-a-entrada sequencialmente:

```python
# F2 itera candle por candle
for i in range(n_rows):
    if in_position:
        # Só checa exit, NÃO checa entry
        continue
```

---

## 4. TESTE NECESSÁRIO

### Adicionar Log de Entries/Exits ao F2

```python
# Inserir no F2 para debug
entry_log = []
exit_log = []

for i in range(n_rows):
    if not in_position:
        if signal[i] == direction and atr_min <= atr[i] <= atr_max:
            entry_log.append(i)
            in_position = True
    else:
        if tp_hit or sl_hit:
            exit_log.append(i)
            in_position = False

print(f"Entries: {len(entry_log)}")
print(f"Exits: {len(exit_log)}")
print(f"Average candles in position: {sum(exit_log) - sum(entry_log) / len(exit_log)}")
```

### Comparar com F1

```python
# F1: sell_idx são as entries
print(f"F1 entries: {len(sell_idx)}")
print(f"F1 trades (apos blocking): {trades}")
```

---

## 5. CAUSA RAIZ PROVÁVEL

**Hipótese:** F2 está com **lógica de entrada muito conservadora** devido ao state machine `in_position`.

**Possíveis bugs:**

1. **F2 não está saindo do trade** (TP/SL não hit) → fica em posição para sempre
2. **F2 está entrando em poucas candles** (signal filter muito restritivo)
3. **F2 está usando signal field errado** (não `PA_SIGNAL_DIR`)

**Próximo passo:** Adicionar logs e rodar F2 candle-a-candle para ver entries/exits.

---

## 6. ARQUIVOS PARA DEBUG

| Arquivo | Linhas | Descrição |
|---------|--------|-----------|
| `engines/f1_fast_screener.py` | 112-196 | F1 `evaluate()` function |
| `engines/f2_optimization_v87.py` | 53-183 | F2 `backtest_f2_numba()` function |
| `scripts/f1_vs_f2_comparacao.py` | — | Script de comparação |

---

## 7. PRÓXIMOS PASSOS

### Imediato
1. ⏳ **Adicionar logs ao F2** — Contar entries/exits
2. ⏳ **Rodar F2 com logs** — Verificar quantas entries são bloqueadas por `in_position`
3. ⏳ **Comparar com F1** — Verificar se F1 entries >> F2 entries

### Curto Prazo
1. ⏳ **Corrigir lógica F2** — Se bug for confirmado
2. ⏳ **Re-testar F1 vs F2** — Validar correção
3. ⏳ **Documentar** — Atualizar `F1_F2_F3_ARQUITETURA.md`

---

**Última atualização:** 2026-05-04  
**Próxima revisão:** Após testes com logs de entries/exits
