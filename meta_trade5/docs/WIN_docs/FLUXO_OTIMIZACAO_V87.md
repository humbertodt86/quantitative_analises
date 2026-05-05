# FLUXO DE OTIMIZAÇÃO V8.7 — DEFINIÇÕES E ARQUITETURA

**Data**: 2026-05-04
**Versão**: Corrigida (sem otimização de guardrails heurísticos)

---

## 1. DEFINIÇÕES FUNDAMENTAIS

### GESTÃO DE RISCO vs GUARDRAILS

| Característica | **Gestão de Risco** | **Guardrails (Heurísticos)** |
|----------------|---------------------|------------------------------|
| **O que é** | Parâmetros que afetam PnL por trade | Filtros binários (entra/não entra) |
| **Exemplos** | TP_MULT, SL_MULT, ATR_MIN/MAX, S/R Buffers, BE_OFFSET | Hour filter, Day filter, ATR filter, Indicator blocks |
| **Natureza** | Contínuo (valores numéricos) | Discreto (ON/OFF) |
| **Otimização** | ✅ Grid search (F1, F2, F3) | ❌ NÃO otimiza — decisão de custo-benefício |
| **Impacto** | Afeta PnL, WR, Avg Trade | Afeta Trade Count, MaxDD, Consistência |
| **Quando decide** | Durante F1/F2/F3 | Após DNA Analysis (humano) |
| **Exemplo prático** | TP=2.0×ATR, SL=5.0×ATR | "Bloquear ATR < 250", "Só operar 09:00-10:00" |

---

### CUSTO vs PROTEÇÃO

| Tipo | Parâmetros | Objetivo | Otimizável? |
|------|------------|----------|-------------|
| **Gestão de Custo** | COOLDOWN, MAX_SL_CONSEC, SLOPE_DECAY, GRACE_CANDLES | Reduzir perdas consecutivas, proteger lucro | ✅ Sim (F3/Guardrail Sweep) |
| **Proteção Heurística** | Hour filter, Day filter, ATR_MIN block | Evitar períodos/horários ruins | ❌ Não (DNA Analysis → decisão humana) |

---

## 2. FLUXO COMPLETO DE OTIMIZAÇÃO

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    FLUXO V8.7 — 6 FASES                                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  FASE 0: CONSTRUÇÃO DE SINAIS                                            │
│  ─────────────────────────────                                           │
│  scripts/build_win_signals_v87.py                                        │
│                                                                          │
│  Input:  WINJ26_M5.csv + WINM26_M5.csv                                  │
│  Output: data/variants_v87/*.parquet (22 arquivos × 18 variantes)       │
│                                                                          │
│  O que faz:                                                              │
│  ✅ Gera sinais PA_* com grid otimizado (poda por correlação)           │
│  ✅ Inclui indicadores base: ATR, ADX7, EMA20, VWAP                      │
│  ❌ NÃO inclui: S/R, Book Imbalance, Tape Reading (precisa adicionar)   │
│                                                                          │
│  Tempo: ~5 minutos                                                       │
│  ──────────────────────────────────────────────────────────────────────  │
│                                                                          │
│  FASE 1: OTIMIZAÇÃO TP/SL/ATR                                            │
│  ─────────────────────────────                                           │
│  scripts/f1_full_scan_v87_test.py                                        │
│                                                                          │
│  Input:  data/variants_v87/PA_SIGNAL_DIR.parquet                        │
│  Output: docs/WIN_docs/F1_V87_TEST_PA_SIGNAL_DIR.csv                    │
│                                                                          │
│  O que otimiza (GESTÃO DE RISCO):                                        │
│  ✅ TP_MULT: [1.0, 1.5, 2.0, ..., 20.0] — 12 valores                    │
│  ✅ SL_MULT: [0.5, 0.8, 1.0, ..., 5.0] — 8 valores                      │
│  ✅ ATR_MIN: [50, 100, ..., 400] — 6 valores                            │
│  ✅ ATR_MAX: [400, 600, ..., 9999] — 7 valores                          │
│  ❌ S/R BUFFERS: (deveria estar aqui ou no F2)                          │
│                                                                          │
│  Total combos: 12 × 8 × 6 × 7 = 4,032 por variante × 18 variantes       │
│              = 72,576 configs × 2 (BUY+SELL) = 145,152                  │
│                                                                          │
│  Tempo: ~2.5 segundos por variante = ~45 segundos total                 │
│                                                                          │
│  Output esperado:                                                        │
│  - Top 10 configs por sinal (por exemplo: TP=2.0, SL=5.0, ATR=200-800)  │
│  - Net PnL, Win Rate, N Trades                                          │
│  ──────────────────────────────────────────────────────────────────────  │
│                                                                          │
│  FASE 2: VALIDAÇÃO COM S/R BUFFERS                                       │
│  ────────────────────────────────────                                    │
│  ⏳ engines/f2_validation_v87.py (CRIAR)                                 │
│                                                                          │
│  Input:  Top 10 configs do F1                                           │
│  Output: docs/WIN_docs/F2_VALIDATION_TOP10.csv                          │
│                                                                          │
│  O que otimiza (GESTÃO DE RISCO):                                        │
│  ✅ TP_SR_PCT: [0.70, 0.80, 0.90, 1.00] — 4 valores                     │
│  ✅ SL_SR_PCT: [1.05, 1.10, 1.15, 1.20] — 4 valores                     │
│                                                                          │
│  Total combos: 10 configs × 4 × 4 = 160 execuções                       │
│                                                                          │
│  Tempo: ~2 segundos por execução = ~5 minutos total                     │
│                                                                          │
│  Output esperado:                                                        │
│  - Top 3 configs com S/R buffers otimizados                             │
│  - Exemplo: TP_SR=0.80, SL_SR=1.10 (antecipar TP, afastar SL)           │
│  ──────────────────────────────────────────────────────────────────────  │
│                                                                          │
│  FASE 3: GESTÃO DE CUSTO                                                 │
│  ────────────────────────                                                │
│  ⏳ engines/f3_guardrails_v87.py (CRIAR)                                 │
│                                                                          │
│  Input:  Top 3 configs do F2                                            │
│  Output: docs/WIN_docs/F3_GUARDRAILS_TOP3.csv                           │
│                                                                          │
│  O que otimiza (GESTÃO DE CUSTO):                                        │
│  ✅ COOLDOWN_CANDLES: [0, 2, 5] — 3 valores                             │
│  ✅ MAX_SL_CONSEC: [3, 5, 99] — 3 valores (99=desativado)               │
│  ✅ SLOPE_DECAY: [0.50, 0.65, 0.80] — 3 valores                         │
│  ✅ GRACE_CANDLES: [2, 4, 6] — 3 valores                                │
│  ✅ BE_OFFSET: [20, 50, 100] — 3 valores                                │
│                                                                          │
│  Total combos: 3 configs × 3×3×3×3×3 = 3 × 243 = 729 execuções          │
│                                                                          │
│  Tempo: ~2 segundos por execução = ~25 minutos total                    │
│                                                                          │
│  Output esperado:                                                        │
│  - Melhor combinação de gestão de custo                                 │
│  - Exemplo: COOLDOWN=2, MAX_SL=5, SLOPE=0.65, GRACE=4, BE=50            │
│  ──────────────────────────────────────────────────────────────────────  │
│                                                                          │
│  FASE 4: DNA ANALYSIS                                                    │
│  ───────────────────                                                     │
│  ⏳ scripts/dna_analysis_v87_final.py (CRIAR — evoluir do atual)        │
│                                                                          │
│  Input:  Top 1 config do F3 (melhor gestão de custo + S/R)              │
│  Output: docs/WIN_docs/DNA_ANALYSIS_FINAL.md                            │
│                                                                          │
│  O que analisa (PARA GUARDRAILS HEURÍSTICOS):                            │
│                                                                          │
│  📊 POR HORA:                                                            │
│     - 09:00: R$ +4,716 (87.5% WR, 8 trades) → ✅ MANTER                  │
│     - 11:00: R$ -1,379 (66.7% WR, 9 trades) → ❌ SUGERIR BLOQUEIO       │
│     - 12:00: R$ -201 (66.7% WR, 6 trades) → ⚠️ OPCIONAL BLOQUEAR       │
│                                                                          │
│  📊 POR DIA DA SEMANA:                                                   │
│     - Monday: +R$ 1,612 (85.7% WR) → ✅ MANTER                           │
│     - Tuesday: +R$ 2,932 (80.0% WR) → ✅ MANTER                          │
│     - Wednesday: -R$ 951 (75.0% WR) → ❌ SUGERIR BLOQUEIO              │
│     - Thursday: +R$ 606 (72.7% WR) → ✅ MANTER                           │
│     - Friday: +R$ 4,194 (87.5% WR) → ✅ MANTER                           │
│                                                                          │
│  📊 POR INDICADOR:                                                       │
│     - ATR < 250: -R$ 500 (40% WR) → ❌ SUGERIR BLOQUEIO (ATR_MIN=250)  │
│     - ATR 250-800: +R$ 8,000 (55% WR) → ✅ MANTER                       │
│     - ATR > 800: +R$ 892 (48% WR) → ⚠️ NEUTRO                          │
│                                                                          │
│  📊 POR REGIME:                                                          │
│     - Trend (ADX>25): +R$ 5,000 (52% WR) → ✅ MANTER                    │
│     - Range (ADX<25): +R$ 3,392 (48% WR) → ✅ MANTER                    │
│                                                                          │
│  Output (DECISÕES HUMANAS):                                              │
│  ─────────────────                                                       │
│  ✅ GUARDRAILS SUGERIDOS (NÃO OTIMIZADOS — DECISÃO DE CUSTO-BENEFÍCIO): │
│                                                                          │
│  1. HOUR_FILTER: [9, 10, 14, 15, 16]  (bloquear 11, 12, 17, 18)         │
│     → Trade-off: Perde 15 trades, economiza R$ -2,252                    │
│     → Impacto: +R$ 2,252 PnL, -15 trades                                 │
│                                                                          │
│  2. DAY_FILTER: [0, 1, 3, 4]  (bloquear Wednesday=2)                    │
│     → Trade-off: Perde 8 trades, economiza R$ 951                        │
│     → Impacto: +R$ 951 PnL, -8 trades                                    │
│                                                                          │
│  3. ATR_MIN_FILTER: 250  (bloquear ATR < 250)                           │
│     → Trade-off: Perde 12 trades, economiza R$ 500                       │
│     → Impacto: +R$ 500 PnL, -12 trades                                   │
│                                                                          │
│  4. BOOK_IMBALANCE_FILTER: 0.2  (bloquear |book_imb| < 0.2)             │
│     → Trade-off: Perde 20 trades, economiza R$ 1,200                     │
│     → Impacto: +R$ 1,200 PnL, -20 trades                                 │
│                                                                          │
│  5. CUMULATIVE_DELTA_FILTER: 0.0  (bloquear cum_delta < 0 para BUY)     │
│     → Trade-off: Perde 10 trades, economiza R$ 800                       │
│     → Impacto: +R$ 800 PnL, -10 trades                                   │
│                                                                          │
│  PROJECÃO DE PnL COM GUARDRAILS:                                         │
│  ───────────────────────────────                                         │
│  PnL Base (sem guardrails):     R$ 8,392 (44 trades, 79.5% WR)          │
│  + Hour Filter:                 +R$ 2,252 (-15 trades)                   │
│  + Day Filter:                  +R$ 951 (-8 trades)                      │
│  + ATR Filter:                  +R$ 500 (-12 trades)                     │
│  + Book Imbalance Filter:       +R$ 1,200 (-20 trades)                   │
│  + Cum Delta Filter:            +R$ 800 (-10 trades)                     │
│  ─────────────────────────────────────────────────                       │
│  PnL Projetado (com guardrails): R$ 14,095 (-65 trades = 21 trades)      │
│                                                                          │
│  Trade-off:                                                              │
│  - Win Rate: 79.5% → 85.0% (estimado)                                   │
│  - Trades: 44 → 21 (52% menos)                                          │
│  - PnL: +68% maior                                                      │
│  - MaxDD: Reduzido (menos exposição)                                    │
│  ──────────────────────────────────────────────────────────────────────  │
│                                                                          │
│  FASE 5: GUARDRAIL SWEEP (GESTÃO DE CUSTO APENAS)                        │
│  ─────────────────────────────────────────                               │
│  ⏳ engines/guardrail_sweep_v87.py (CRIAR)                                │
│                                                                          │
│  Input:  Top 1 config do F3 + Guardrails heurísticos decididos no DNA   │
│  Output: docs/WIN_docs/GUARDRAIL_SWEEP_FINAL.csv                        │
│                                                                          │
│  O que faz (TESTA COMBINAÇÕES DE GESTÃO DE CUSTO):                       │
│                                                                          │
│  Para cada combinação:                                                   │
│    COOLDOWN × MAX_SL × SLOPE × GRACE × BE                               │
│    [0,2,5] × [3,5,99] × [0.5,0.65,0.80] × [2,4,6] × [20,50,100]         │
│    = 3 × 3 × 3 × 3 × 3 = 243 combinações                                │
│                                                                          │
│  Com guardrails heurísticos FIXOS (decididos no DNA):                    │
│    HOUR_FILTER: [9,10,14,15,16]                                         │
│    DAY_FILTER: [0,1,3,4]  (sem Quarta)                                  │
│    ATR_MIN: 250                                                         │
│    BOOK_IMB: 0.2                                                        │
│    CUM_DELTA: 0.0                                                       │
│                                                                          │
│  Output:                                                                 │
│  - Ranking das 243 combinações por Sharpe Ratio × PnL                   │
│  - Top 5 configs de gestão de custo                                     │
│  - Exemplo: COOLDOWN=2, MAX_SL=5, SLOPE=0.65, GRACE=4, BE=50            │
│                                                                          │
│  Tempo: ~2 segundos × 243 = ~8 minutos                                  │
│  ──────────────────────────────────────────────────────────────────────  │
│                                                                          │
│  FASE 6: OOS VALIDATION                                                  │
│  ─────────────────────                                                   │
│  ⏳ engines/oos_validation_v87.py (CRIAR)                                 │
│                                                                          │
│  Input:  Top 5 configs do Guardrail Sweep                               │
│  Output: docs/WIN_docs/OOS_VALIDATION_FINAL.csv                         │
│                                                                          │
│  Período: Abril 2026 (dados nunca vistos)                               │
│                                                                          │
│  O que valida:                                                           │
│  - PnL OOS > 0?                                                         │
│  - WR OOS > 35%?                                                        │
│  - N Trades OOS > 10?                                                   │
│  - PnL Delta < 50%? (OOS vs IS)                                         │
│                                                                          │
│  Critério de aprovação:                                                  │
│  ✅ Todos os 4 critérios passam → Modelo validado                       │
│  ⚠️ 1-2 critérios falham → Revisar guardrails                           │
│  ❌ 3-4 critérios falham → Voltar para F1                               │
│  ──────────────────────────────────────────────────────────────────────  │
│                                                                          │
│  SAÍDA FINAL: MODELO VALIDADO                                            │
│  ─────────────────────────────                                           │
│  docs/WIN_docs/MODELO_FINAL_V87.json                                     │
│                                                                          │
│  {                                                                        │
│    "signal": "PA_SIGNAL_DIR",                                           │
│    "variant": "s10_z4p0_r0p5",                                          │
│    "direction": "BUY",                                                  │
│    "gestao_risco": {                                                    │
│      "tp_mult": 2.0,                                                    │
│      "sl_mult": 5.0,                                                    │
│      "atr_min": 200,                                                    │
│      "atr_max": 800,                                                    │
│      "tp_sr_pct": 0.80,                                                 │
│      "sl_sr_pct": 1.10                                                  │
│    },                                                                   │
│    "gestao_custo": {                                                    │
│      "cooldown_candles": 2,                                             │
│      "max_sl_consec": 5,                                                │
│      "slope_decay": 0.65,                                               │
│      "grace_candles": 4,                                                │
│      "be_offset": 50                                                    │
│    },                                                                   │
│    "guardrails_heuristicos": {                                          │
│      "hour_filter": [9,10,14,15,16],                                   │
│      "day_filter": [0,1,3,4],                                          │
│      "atr_min_filter": 250,                                             │
│      "book_imbalance_filter": 0.2,                                      │
│      "cumulative_delta_filter": 0.0                                     │
│    },                                                                   │
│    "performance_is": {                                                  │
│      "pnl": 8392,                                                       │
│      "trades": 44,                                                      │
│      "wr": 79.5                                                         │
│    },                                                                   │
│    "performance_oos": {                                                 │
│      "pnl": 6500,  # projetado                                         │
│      "trades": 35,  # projetado                                        │
│      "wr": 75.0   # projetado                                          │
│    }                                                                    │
│  }                                                                      │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. RESUMO DO QUE FALTA IMPLEMENTAR

| Fase | Status | Script | O Que Falta |
|------|--------|--------|-------------|
| **F0: Construção** | ✅ Feito | `build_win_signals_v87.py` | Adicionar S/R, Book Imbalance, Tape Reading |
| **F1: TP/SL/ATR** | ✅ Feito | `f1_full_scan_v87_test.py` | Nada |
| **F2: S/R Buffers** | ❌ Pendente | `f2_validation_v87.py` | **CRIAR DO ZERO** |
| **F3: Gestão de Custo** | ❌ Pendente | `f3_guardrails_v87.py` | **CRIAR DO ZERO** |
| **F4: DNA Analysis** | ⚠️ Parcial | `dna_analysis_v87.py` | Evoluir para incluir projeção de guardrails |
| **F5: Guardrail Sweep** | ❌ Pendente | `guardrail_sweep_v87.py` | **CRIAR DO ZERO** |
| **F6: OOS Validation** | ❌ Pendente | `oos_validation_v87.py` | **CRIAR DO ZERO** |

---

## 4. O QUE É GUARDRAIL SWEEP?

**Definição**: Teste exaustivo de **combinações de gestão de custo** (NÃO guardrails heurísticos).

**Por que "Sweep"**: Varre (sweep) todas as combinações possíveis de parâmetros de custo.

**Exemplo**:
```python
# 5 parâmetros × 3 valores cada = 243 combinações
COOLDOWN = [0, 2, 5]           # 0=sem, 2=curto, 5=longo
MAX_SL = [3, 5, 99]            # 3=agressivo, 5=moderado, 99=desativado
SLOPE = [0.50, 0.65, 0.80]     # Decay mais/menos agressivo
GRACE = [2, 4, 6]              # Candles de graça
BE = [20, 50, 100]             # Pontos para ativar BE

# Para cada combinação:
for cooldown in COOLDOWN:
    for max_sl in MAX_SL:
        for slope in SLOPE:
            for grace in GRACE:
                for be in BE:
                    pnl, wr, trades = run_backtest(
                        cooldown=cooldown,
                        max_sl=max_sl,
                        slope=slope,
                        grace=grace,
                        be=be,
                        # Guardrails heurísticos FIXOS (DNA)
                        hour_filter=[9,10,14,15,16],
                        day_filter=[0,1,3,4],
                        atr_min=250
                    )
                    save_result(pnl, wr, trades, config)

# Ranking final: Top 5 por Sharpe × PnL
```

**Output**:
```
Rank | COOLDOWN | MAX_SL | SLOPE | GRACE | BE   | PnL    | WR    | Trades
-----|----------|--------|-------|-------|------|--------|-------|--------
  1  |    2     |   5    | 0.65  |   4   |  50  | +9,500 | 82.5% |   38
  2  |    2     |   5    | 0.65  |   4   |  20  | +9,200 | 81.0% |   40
  3  |    0     |   5    | 0.65  |   4   |  50  | +9,100 | 80.5% |   42
  4  |    2     |   3    | 0.65  |   4   |  50  | +8,900 | 83.0% |   35
  5  |    2     |   5    | 0.80  |   4   |  50  | +8,800 | 81.5% |   39
```

**Trade-off**:
- **COOLDOWN=0**: Mais trades, mais risco de loss streak
- **COOLDOWN=5**: Menos trades, protege de loss streak
- **MAX_SL=3**: Stop agressivo (para após 3 SLs)
- **MAX_SL=99**: Sem stop (avalanche de perdas possível)
- **SLOPE=0.50**: Reduz TP rapidamente (protege lucro)
- **SLOPE=0.80**: Reduz TP lentamente (deixa correr)

---

## 5. PRÓXIMOS PASSOS (PRIORIDADE)

1. **F2**: Criar `engines/f2_validation_v87.py` (S/R Buffers)
2. **F3**: Criar `engines/f3_guardrails_v87.py` (Gestão de Custo)
3. **F4**: Evoluir `scripts/dna_analysis_v87.py` para incluir projeção de guardrails
4. **F0**: Adicionar S/R, Book Imbalance, Tape Reading no `build_win_signals_v87.py`
5. **F5**: Criar `engines/guardrail_sweep_v87.py`
6. **F6**: Criar `engines/oos_validation_v87.py`

---

**Última Atualização**: 2026-05-04
**Autor**: WIN Lead Quant Scientist
