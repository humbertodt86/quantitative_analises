# TESTE F2 SEM FILTROS — RESULTADOS

**Data**: 2026-05-04
**Status**: ⚠️ PROBLEMA PERSISTE

---

## 1. RESULTADOS DO TESTE

| Config | Filtros | Guardrails | Trades | PnL | WR |
|--------|---------|------------|--------|-----|----|
| **F1** | Nenhum | Nenhum | 615 | +135,916 | 52% |
| **F2 (original)** | BOOK=0.1, DELTA=-0.5 | MAX_SL=5, CD=0 | 100 | +4,421 | 84% |
| **F2 (sem filtros)** | BOOK=0.0, DELTA=0.0 | MAX_SL=99, CD=0 | 101 | +3,742 | 83% |

**Conclusão**: Remover filtros **NÃO aumentou trades** (100 → 101 = +1%).

---

## 2. CAUSA RAIZ: NÃO SÃO OS FILTROS

**Hipótese descartada**: Filtros (BOOK_IMB, CUM_DELTA) NÃO eram a causa principal da queda de 97%.

**Nova hipótese**: Guardrails (BE, GRACE, SLOPE) ou lógica de S/R buffers estão matando trades.

---

## 3. PRÓXIMOS TESTES

### Teste A: F2 Sem Guardrails

```json
"guardrails": {
  "be_offset": [999999],      // Desativar BE
  "grace_candles": [0],       // Desativar GRACE
  "slope_decay": [0.0]        // Desativar SLOPE
}
```

**Resultado esperado**: Trades 101 → 400-600 (se guardrails forem a causa)

### Teste B: F2 Sem S/R Buffers

```json
"sr_buffers": {
  "tp_sr_pct": [1.00],        // Usa 100% (não ajusta)
  "sl_sr_pct": [1.00]
}
```

**Resultado esperado**: Trades 101 → 200-300 (se S/R buffers forem a causa)

### Teste C: Comparar Lógica F1 vs F2

**Ação**: Rodar F1 e F2 com MESMOS parâmetros (TP=2.0, SL=5.0, ATR=[200-800])

**Objetivo**: Isolar diferença na lógica de backtest

---

## 4. LIÇÕES APRENDIDAS

1. **Filtros NÃO eram problema principal** — Remover BOOK/DELTA não aumentou trades
2. **Guardrails são suspeitos** — BE=50, GRACE=4 podem estar fechando trades cedo
3. **S/R Buffers podem distorcer** — TP_SR=0.80 pode estar reduzindo TP demais
4. **Lógica F1 ≠ F2** — Pode haver diferença na implementação do backtest

---

**Próximo Passo**: Teste A (sem guardrails) para isolar causa raiz.
