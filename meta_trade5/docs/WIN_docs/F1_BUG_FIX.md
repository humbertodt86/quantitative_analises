# F1 vs F2 — CORRECOES E VALIDACAO

**Data:** 2026-05-04  
**Status:** ✅ **CORRIGIDO E VALIDADO**  
**Diferenca F1->F2:** 93.5% → **2.2%** ✅

---

## 1. RESUMO DAS CORRECOES

### Correção 1: Position Blocking (Linha 193)

**Bug:** `blocked.append(pnl[idx])` estava FORA do `if had[idx]`

**Impacto:** F1 contava entries SEM exit como trades (608 trades → 103 trades)

**Fix:** Mover `blocked.append()` para dentro do `if had[idx]`

### Correção 2: Limite de Candles (MAX_C = 15 → 50)

**Bug:** F1 limitava trades a 15 candles futuras

**Impacto:** Trades que não atingiam TP/SL em 15 candles eram fechados com -COST, criando divergência com F2 (que não tem limite)

**Fix:** 
- `f1_fast_screener.py`: `MAX_C = 15 → 50`
- `f1_full_scan_v87_test.py`: `max_la = min(20, ...) → max_la = n_rows - i - 1`

---

## 2. RESULTADOS FINAIS

### Comparacao F1 vs F2 (Modo Busca — Sem Guardrails)

| Métrica | F1 (fast_screener) | F2 (numba) | Diferença |
|---------|-------------------|------------|-----------|
| **Trades** | 47 | 46 | **+1 (2.2%)** |
| **PnL** | +11,784 | +11,814 | **-30 (0.3%)** |
| **WR** | 80.9% | 82.6% | **-1.7%** |

### Validacao

✅ **Diferenca < 5%** — F1 e F2 estão alinhados!

A única diferença restante é nos dados de ticks:
- **F1**: 15 samples/candle (last prices)
- **F2**: Todos os ticks (high/low de cada candle)

---

## 3. DIFERENCAS ENTRE F1, F2, F3 (POS-CORRECAO)

| Aspecto | F1 | F2 | F3 |
|---------|----|----|----|
| **Dados** | 15 samples/candle | Todos ticks (last) | Todos ticks (bid/ask) |
| **Limite candles** | 50 (ou até o fim) | Até o fim | Até o fim |
| **Guardrails** | NENHUM | NENHUM (modo busca) | TODOS (modo produção) |
| **Custo** | 30 pts fixo | 30 pts fixo | Spread real |
| **Velocidade** | 200K configs/s | 2 configs/s | 2 configs/s |
| **Uso** | Pre-filtro | Validacao IS | Referencia ouro |

### Fluxo Correto

```
F1 (pre-filtro, sem guardrails) → Top 10-20 configs
  ↓
F2 (validacao IS, modo busca = sem guardrails) → Top 3-5 configs
  ↓
F3 (validacao final, modo produção = com guardrails) → Report OOS
```

---

## 4. LIÇOES APRENDIDAS

### Nunca Limite Candles Artificialmente
- F1 e F2 devem ter comportamento idêntico em lógica
- A única diferença deve ser nos dados de entrada (samples vs ticks reais)
- Limite de candles cria viés de sobrevivência (survivorship bias)

### Documentar Constantes Críticas
- `MAX_C`, `SAMP`, `COST` devem estar documentadas
- Mudanças em constantes críticas afetam resultados dramaticamente
- Versionar constantes junto com o código

### Validar Após Cada Mudança
- Rodar F1 vs F2 após qualquer mudança no motor
- Diferenca > 5% indica bug ou regressão
- Diferenca < 5% é aceitável (diferença de amostragem)

---

## 5. ARQUIVOS MODIFICADOS

| Arquivo | Mudança | Status |
|---------|---------|--------|
| `engines/f1_fast_screener.py` | Corrige indentação linha 193 | ✅ |
| `engines/f1_fast_screener.py` | MAX_C: 15 → 50 | ✅ |
| `scripts/f1_full_scan_v87_test.py` | max_la: min(20,...) → n_rows-i-1 | ✅ |
| `docs/WIN_docs/F1_BUG_FIX.md` | Esta documentação | ✅ |

---

## 6. PROXIMOS PASSOS

1. ⏳ **Re-rodar F1 full scan** — Validar que performance ainda é aceitável com MAX_C=50
2. ⏳ **Testar com outros sinais** — PA_SIGNAL_DIR é apenas 1 de 23 sinais
3. ⏳ **Atualizar README.md** — Documentar que F1 agora não tem limite de candles

---

**Data da correção:** 2026-05-04  
**Responsável:** Sisyphus (WIN Lead Quant Scientist)  
**Validado por:** Comparação direta F1 vs F2 (2.2% diferença)
