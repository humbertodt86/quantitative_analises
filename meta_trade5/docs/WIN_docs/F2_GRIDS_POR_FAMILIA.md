# F2 GRID SEARCH — ANÁLISE CONCEITUAL E PROPOSTA

**Data**: 2026-05-04
**Versão**: V8.7 (GridAdvisor como redutor de espaço)
**Status**: PROPOSTA TÉCNICA

---

## 1. FILOSOFIA DO F2

### Princípio Fundamental

> **F1 descarta o lixo, F2 refina o ouro.**

O F1 já eliminou ~95% dos combos ruins. O F2 não precisa (e não deve) refazer essa busca.

### Papel de Cada Fase

| Fase | Objetivo | Espaço de Busca | Critério de Sucesso |
|------|----------|-----------------|---------------------|
| **F1** | Encontrar **REGIÃO ÓTIMA** de TP/SL/ATR | Amplo (4,032 combos) | Top 10 configs com PnL > 0 |
| **F2** | **Refinar TP/SL/ATR** + Otimizar **GESTÃO DE RISCO** | Curto (35K-315K combos) | PnL -10%, WR +10pts, Sharpe +50%, DD -30% |
| **F3** | Validar com ticks reais | Nenhum (só valida top 3) | PnL OOS > 0, WR > 40% |

---

## 2. ANÁLISE POR FAMÍLIA DE SINAL

### Por Que Seeds Diferentes?

Cada família de sinal tem **características operacionais distintas**:

| Família | Estilo | TP Típico | SL Típico | ATR Típico | Guardrails Ideais |
|---------|--------|-----------|-----------|------------|-------------------|
| **PA_SIGNAL_DIR** | Trend Following | Alto (2.0-3.0) | Alto (4.0-6.0) | Amplo (200-800) | BE alto, Grace longo |
| **PA_REV_RSI** | Mean Reversion | Baixo (1.0-1.5) | Baixo (2.0-3.0) | Estreito (150-400) | BE baixo, Grace curto |
| **PA_ADX_BREAK** | Breakout | Médio (1.5-2.0) | Médio (3.0-4.0) | Médio (200-600) | Sem cooldown |
| **PA_VWAP_REV** | VWAP Mean Rev | Baixo (0.8-1.2) | Baixo (1.5-2.5) | Estreito (100-300) | BE agressivo |
| **PA_LIQ_GRAB** | Liquidity Grab | Alto (2.5-4.0) | Alto (5.0-8.0) | Amplo (300-1000) | MAX_SL baixo |

**Conclusão**: Não existe grid único ótimo para todas as famílias.

---

## 3. PROPOSTA DE GRIDS POR FAMÍLIA

### 3.1. TREND FOLLOWING (PA_SIGNAL_DIR, PA_STRONG_TREND, PA_SLOPE_TREND)

**Características**:
- Trades duram mais tempo (10-30 candles)
- TP alto necessário (deixa lucro correr)
- SL alto para não ser stopado em pullbacks
- ATR varia muito (mercado trending pode ter volatilidade alta)

```python
# SEED F1 típica: TP=2.0, SL=5.0, ATR=[200-800]

# Grid F2 — TP/SL/ATR (REFINO, ±25%)
TP_MULT_GRID = [1.5, 1.8, 2.0, 2.2, 2.5]        # 5 valores
SL_MULT_GRID = [4.0, 4.5, 5.0, 5.5, 6.0]        # 5 valores
ATR_MIN_GRID = [150, 180, 200, 220, 250]        # 5 valores
ATR_MAX_GRID = [600, 680, 800, 920, 1000]       # 5 valores
# Total TP/SL/ATR: 5×5×5×5 = 625 combos

# S/R Buffers (Trend: TP mais agressivo, SL mais conservador)
TP_SR_PCT_GRID = [0.80, 0.90, 1.00]             # 3 valores (TP = 80-100% do S/R)
SL_SR_PCT_GRID = [1.10, 1.15, 1.20]             # 3 valores (SL = 110-120% do S/R)
# Total S/R: 3×3 = 9 combos

# Gestão de Custo (Trend: BE alto, Grace longo)
BE_OFFSET_GRID = [50, 100, 200]                 # 3 valores (BE mais conservador)
GRACE_CANDLES_GRID = [4, 6, 8]                  # 3 valores (deixa trade respirar)
COOLDOWN_CANDLES_GRID = [0, 2]                  # 2 valores (pouco cooldown)
MAX_SL_CONSEC_GRID = [5, 99]                    # 2 valores (tolera mais SLs)
SLOPE_DECAY_GRID = [0.50, 0.65]                 # 2 valores (slope moderado)
# Total Gestão: 3×3×2×2×2 = 72 combos

# Filtros (Trend: filtros mais fracos para não perder entradas)
BOOK_IMB_THRESH_GRID = [0.1, 0.2]               # 2 valores
CUM_DELTA_THRESH_GRID = [-0.5, 0.0]             # 2 valores
# Total Filtros: 2×2 = 4 combos

# TOTAL TREND: 625 × 9 × 72 × 4 = 1,620,000 combos
# Tempo estimado: 162 segundos (2.7 minutos)
```

---

### 3.2. MEAN REVERSION (PA_REV_RSI, PA_VWAP_REV, PA_POC_REV)

**Características**:
- Trades rápidos (2-8 candles)
- TP baixo (volta para média)
- SL baixo (se não voltou rápido, não é mean reversion)
- ATR estreito (opera em regime de baixa volatilidade)

```python
# SEED F1 típica: TP=1.0, SL=2.5, ATR=[150-400]

# Grid F2 — TP/SL/ATR (REFINO, ±20%)
TP_MULT_GRID = [0.8, 0.9, 1.0, 1.1, 1.2]        # 5 valores
SL_MULT_GRID = [2.0, 2.3, 2.5, 2.7, 3.0]        # 5 valores
ATR_MIN_GRID = [120, 140, 150, 160, 180]        # 5 valores
ATR_MAX_GRID = [320, 360, 400, 440, 480]        # 5 valores
# Total TP/SL/ATR: 5×5×5×5 = 625 combos

# S/R Buffers (Mean Rev: TP no S/R, SL além do S/R)
TP_SR_PCT_GRID = [0.70, 0.80, 0.90]             # 3 valores (TP = 70-90% do S/R)
SL_SR_PCT_GRID = [1.05, 1.10, 1.15]             # 3 valores (SL = 105-115% do S/R)
# Total S/R: 3×3 = 9 combos

# Gestão de Custo (Mean Rev: BE agressivo, Grace curto)
BE_OFFSET_GRID = [20, 50, 100]                  # 3 valores (BE mais agressivo)
GRACE_CANDLES_GRID = [2, 4, 6]                  # 3 valores (graça curta)
COOLDOWN_CANDLES_GRID = [2, 4, 6]               # 3 valores (mais cooldown)
MAX_SL_CONSEC_GRID = [3, 5]                     # 2 valores (tolera menos SLs)
SLOPE_DECAY_GRID = [0.65, 0.80]                 # 2 valores (slope alto)
# Total Gestão: 3×3×3×2×2 = 108 combos

# Filtros (Mean Rev: filtros mais fortes para evitar falsos)
BOOK_IMB_THRESH_GRID = [0.2, 0.3]               # 2 valores
CUM_DELTA_THRESH_GRID = [0.0, 0.5]              # 2 valores
# Total Filtros: 2×2 = 4 combos

# TOTAL MEAN REVERSION: 625 × 9 × 108 × 4 = 2,430,000 combos
# Tempo estimado: 243 segundos (4 minutos)
```

---

### 3.3. BREAKOUT (PA_ADX_BREAK, PA_GK_BREAK, PA_EXHAUST)

**Características**:
- Trades explosivos (1-5 candles)
- TP médio (captura expansão)
- SL médio (breakout falso é comum)
- ATR médio (opera em expansão de volatilidade)

```python
# SEED F1 típica: TP=1.5, SL=3.5, ATR=[200-600]

# Grid F2 — TP/SL/ATR (REFINO, ±20%)
TP_MULT_GRID = [1.2, 1.4, 1.5, 1.6, 1.8]        # 5 valores
SL_MULT_GRID = [2.8, 3.2, 3.5, 3.8, 4.2]        # 5 valores
ATR_MIN_GRID = [160, 180, 200, 220, 240]        # 5 valores
ATR_MAX_GRID = [480, 540, 600, 660, 720]        # 5 valores
# Total TP/SL/ATR: 5×5×5×5 = 625 combos

# S/R Buffers (Breakout: TP além do S/R, SL no S/R)
TP_SR_PCT_GRID = [0.90, 1.00, 1.10]             # 3 valores (TP = 90-110% do S/R)
SL_SR_PCT_GRID = [1.05, 1.10, 1.15]             # 3 valores (SL = 105-115% do S/R)
# Total S/R: 3×3 = 9 combos

# Gestão de Custo (Breakout: BE moderado, Grace médio)
BE_OFFSET_GRID = [50, 100, 150]                 # 3 valores
GRACE_CANDLES_GRID = [2, 4, 6]                  # 3 valores
COOLDOWN_CANDLES_GRID = [0, 2, 5]               # 3 valores
MAX_SL_CONSEC_GRID = [3, 5, 99]                 # 3 valores
SLOPE_DECAY_GRID = [0.50, 0.65, 0.80]           # 3 valores
# Total Gestão: 3×3×3×3×3 = 243 combos

# Filtros (Breakout: filtros moderados)
BOOK_IMB_THRESH_GRID = [0.1, 0.2, 0.3]          # 3 valores
CUM_DELTA_THRESH_GRID = [-0.5, 0.0, 0.5]        # 3 valores
# Total Filtros: 3×3 = 9 combos

# TOTAL BREAKOUT: 625 × 9 × 243 × 9 = 12,301,875 combos
# Tempo estimado: 1,230 segundos (20.5 minutos) — MUITO!
```

**Problema**: Breakout tem espaço muito grande.

**Solução**: GridAdvisor com CV% threshold mais baixo (10% em vez de 15%) para reduzir TP/SL/ATR para 1 valor se F1 foi estável.

---

### 3.4. LIQUIDITY GRAB (PA_LIQ_GRAB, PA_VCP)

**Características**:
- Trades de reversão após sweep
- TP alto (reversão pode ser forte)
- SL alto (sweep pode continuar)
- ATR amplo (alta volatilidade no sweep)

```python
# SEED F1 típica: TP=3.0, SL=6.0, ATR=[300-1000]

# Grid F2 — TP/SL/ATR (REFINO, ±20%)
TP_MULT_GRID = [2.4, 2.7, 3.0, 3.3, 3.6]        # 5 valores
SL_MULT_GRID = [4.8, 5.4, 6.0, 6.6, 7.2]        # 5 valores
ATR_MIN_GRID = [240, 270, 300, 330, 360]        # 5 valores
ATR_MAX_GRID = [800, 900, 1000, 1100, 1200]     # 5 valores
# Total TP/SL/ATR: 5×5×5×5 = 625 combos

# S/R Buffers (Liq Grab: TP no S/R, SL além do S/R)
TP_SR_PCT_GRID = [0.70, 0.80, 0.90]             # 3 valores
SL_SR_PCT_GRID = [1.15, 1.20, 1.25]             # 3 valores
# Total S/R: 3×3 = 9 combos

# Gestão de Custo (Liq Grab: BE conservador, Grace longo)
BE_OFFSET_GRID = [100, 200, 300]                # 3 valores
GRACE_CANDLES_GRID = [6, 8, 10]                 # 3 valores
COOLDOWN_CANDLES_GRID = [5, 7, 10]              # 3 valores
MAX_SL_CONSEC_GRID = [3, 5]                     # 2 valores
SLOPE_DECAY_GRID = [0.50, 0.65]                 # 2 valores
# Total Gestão: 3×3×3×2×2 = 108 combos

# Filtros (Liq Grab: filtros fortes para evitar sweep contínuo)
BOOK_IMB_THRESH_GRID = [0.2, 0.3]               # 2 valores
CUM_DELTA_THRESH_GRID = [0.0, 0.5]              # 2 valores
# Total Filtros: 2×2 = 4 combos

# TOTAL LIQ GRAB: 625 × 9 × 108 × 4 = 2,430,000 combos
# Tempo estimado: 243 segundos (4 minutos)
```

---

### 3.5. REGIME/CLASSIFICADOR (PA_EFF_RATIO, PA_CHOP, PA_TUESDAY)

**Características**:
- Operam em regime específico
- TP/SL variam conforme regime
- ATR secundário (filtro de regime é primário)

```python
# SEED F1 típica: TP=2.0, SL=4.0, ATR=[150-600]

# Grid F2 — TP/SL/ATR (REFINO, ±25% — mais amplo por incerteza)
TP_MULT_GRID = [1.5, 1.8, 2.0, 2.2, 2.5]        # 5 valores
SL_MULT_GRID = [3.0, 3.5, 4.0, 4.5, 5.0]        # 5 valores
ATR_MIN_GRID = [120, 140, 150, 160, 180]        # 5 valores
ATR_MAX_GRID = [480, 540, 600, 660, 720]        # 5 valores
# Total TP/SL/ATR: 5×5×5×5 = 625 combos

# S/R Buffers (Regime: neutro)
TP_SR_PCT_GRID = [0.80, 0.90, 1.00]             # 3 valores
SL_SR_PCT_GRID = [1.05, 1.10, 1.15]             # 3 valores
# Total S/R: 3×3 = 9 combos

# Gestão de Custo (Regime: conservador)
BE_OFFSET_GRID = [50, 100, 200]                 # 3 valores
GRACE_CANDLES_GRID = [4, 6, 8]                  # 3 valores
COOLDOWN_CANDLES_GRID = [2, 4, 6]               # 3 valores
MAX_SL_CONSEC_GRID = [5, 99]                    # 2 valores
SLOPE_DECAY_GRID = [0.50, 0.65, 0.80]           # 3 valores
# Total Gestão: 3×3×3×2×3 = 162 combos

# Filtros (Regime: sem filtros — regime já é filtro)
BOOK_IMB_THRESH_GRID = [0.0]                    # 1 valor (desativado)
CUM_DELTA_THRESH_GRID = [0.0]                   # 1 valor (desativado)
# Total Filtros: 1×1 = 1 combo

# TOTAL REGIME: 625 × 9 × 162 × 1 = 911,250 combos
# Tempo estimado: 91 segundos (1.5 minutos)
```

---

## 4. GRID ADVISOR — CRITÉRIOS DE DECISÃO

### 4.1. Quando FIXAR TP/SL/ATR (1 valor cada)

```python
def should_fix_tp_sl_atr(f1_top_3):
    """
    Fixa TP/SL/ATR se F1 foi estável.
    
    Critérios:
    - CV% do PnL < 15%
    - Top 3 configs têm mesmo TP (±0.2)
    - Top 3 configs têm mesmo SL (±0.5)
    - Top 3 configs têm ATR_MAX similar (±200)
    """
    pnls = [r['net_pnl'] for r in f1_top_3]
    tps = [r['tp_mult'] for r in f1_top_3]
    sls = [r['sl_mult'] for r in f1_top_3]
    atr_maxs = [r['atr_max'] for r in f1_top_3]
    
    cv_pnl = np.std(pnls) / np.mean(pnls) * 100
    tp_range = max(tps) - min(tps)
    sl_range = max(sls) - min(sls)
    atr_range = max(atr_maxs) - min(atr_maxs)
    
    if cv_pnl < 15 and tp_range < 0.2 and sl_range < 0.5 and atr_range < 200:
        return True, "F1 estável"
    else:
        return False, "F1 instável"
```

**Resultado**:
- Se `True`: TP/SL/ATR = 1 valor cada → 1 combo
- Se `False`: TP/SL/ATR = 5 valores cada → 625 combos

**Redução**: 625x menos combos quando F1 é estável!

---

### 4.2. Quando EXPANDIR Grid de Guardrails

```python
def should_expand_guardrails(f2_results, f1_best):
    """
    Expande guardrails se F2 piorou muito vs F1.
    
    Critérios:
    - PnL F2 < 0.70 × PnL F1 (piorou >30%)
    - Trades F2 < 0.50 × Trades F1 (piorou >50%)
    """
    pnl_ratio = f2_results[0]['net_pnl'] / f1_best['net_pnl']
    trade_ratio = f2_results[0]['n_trades'] / f1_best['n_trades']
    
    if pnl_ratio < 0.70 or trade_ratio < 0.50:
        return True, "Guardrails muito agressivos"
    else:
        return False, "Guardrails OK"
```

**Ação**:
- Se `True`: Reduz BE_OFFSET, reduz GRACE, remove filtros
- Se `False`: Mantém grids atuais

---

### 4.3. Quando ZOOM em S/R Buffers

```python
def should_zoom_sr_buffers(f2_results):
    """
    Zoom em S/R buffers se melhor config está no meio do grid.
    
    Critérios:
    - Melhor TP_SR_PCT não é borda (não é 0.70 nem 1.00)
    - Melhor SL_SR_PCT não é borda (não é 1.05 nem 1.20)
    """
    best = f2_results[0]
    tp_sr = best['tp_sr_pct']
    sl_sr = best['sl_sr_pct']
    
    if 0.80 <= tp_sr <= 0.90 and 1.10 <= sl_sr <= 1.15:
        return True, "S/RBuffers no meio do grid"
    else:
        return False, "S/R Buffers na borda"
```

**Ação**:
- Se `True`: Gera grid ±10% ao redor do ótimo
- Se `False`: Mantém grid ou EXPANDE

---

## 5. RESUMO DE GRIDS POR FAMÍLIA

| Família | TP/SL/ATR | S/R | Gestão | Filtros | TOTAL | Tempo |
|---------|-----------|-----|--------|---------|-------|-------|
| **Trend** | 625 | 9 | 72 | 4 | 1.62M | 2.7 min |
| **Mean Rev** | 625 | 9 | 108 | 4 | 2.43M | 4.0 min |
| **Breakout** | 625 | 9 | 243 | 9 | 12.3M | 20.5 min |
| **Liq Grab** | 625 | 9 | 108 | 4 | 2.43M | 4.0 min |
| **Regime** | 625 | 9 | 162 | 1 | 0.91M | 1.5 min |

**Com GridAdvisor (F1 estável)**:

| Família | TP/SL/ATR | S/R | Gestão | Filtros | TOTAL | Tempo |
|---------|-----------|-----|--------|---------|-------|-------|
| **Trend** | 1 | 9 | 72 | 4 | 2,592 | 0.3s |
| **Mean Rev** | 1 | 9 | 108 | 4 | 3,888 | 0.4s |
| **Breakout** | 1 | 9 | 243 | 9 | 19,683 | 2.0s |
| **Liq Grab** | 1 | 9 | 108 | 4 | 3,888 | 0.4s |
| **Regime** | 1 | 9 | 162 | 1 | 1,458 | 0.1s |

**Redução**: 625x quando F1 é estável!

---

## 6. ARQUIVOS DE CONFIGURAÇÃO

### 6.1. `data/f2_grid_configs.json`

```json
{
  "trend": {
    "tp_sl_atr": {
      "tp_mult": [1.5, 1.8, 2.0, 2.2, 2.5],
      "sl_mult": [4.0, 4.5, 5.0, 5.5, 6.0],
      "atr_min": [150, 180, 200, 220, 250],
      "atr_max": [600, 680, 800, 920, 1000]
    },
    "sr_buffers": {
      "tp_sr_pct": [0.80, 0.90, 1.00],
      "sl_sr_pct": [1.10, 1.15, 1.20]
    },
    "guardrails": {
      "be_offset": [50, 100, 200],
      "grace_candles": [4, 6, 8],
      "cooldown_candles": [0, 2],
      "max_sl_consec": [5, 99],
      "slope_decay": [0.50, 0.65]
    },
    "filters": {
      "book_imb_thresh": [0.1, 0.2],
      "cum_delta_thresh": [-0.5, 0.0]
    },
    "family_signals": ["PA_SIGNAL_DIR", "PA_STRONG_TREND", "PA_SLOPE_TREND"]
  },
  "mean_reversion": {
    ...
  },
  "breakout": {
    ...
  },
  "liquidity_grab": {
    ...
  },
  "regime": {
    ...
  }
}
```

### 6.2. `scripts/family_classifier.py`

```python
"""
Classifica sinais por família para usar grid F2 correto.
"""

FAMILY_MAP = {
    'PA_SIGNAL_DIR': 'trend',
    'PA_SIGNAL_REV': 'mean_reversion',
    'PA_STRONG_TREND_A25_S20': 'trend',
    'PA_SLOPE_TREND_S25_A25': 'trend',
    'PA_ADX_BREAK_A25': 'breakout',
    'PA_REV_RSI_UNIFIED': 'mean_reversion',
    'PA_VWAP_REV_D1_0': 'mean_reversion',
    'PA_VWAP_Z_Z2_0': 'mean_reversion',
    'PA_LIQ_GRAB': 'liquidity_grab',
    'PA_VCP_C0_6': 'liquidity_grab',
    'PA_EFF_RATIO_E0_6': 'regime',
    'PA_CHOP_C38_2': 'regime',
    'PA_TUESDAY': 'regime',
    # ... demais sinais
}

def get_family(signal_name):
    return FAMILY_MAP.get(signal_name, 'trend')  # Default: trend
```

---

## 7. FLUXO DO F2 COM GRIDS POR FAMÍLIA

```python
def run_f2_optimization(parquet_path, signal_name, variant_name, top10_f1, direction):
    # 1. Classificar família
    family = get_family(signal_name)
    
    # 2. Carregar grid config da família
    grid_config = load_grid_config(family)
    
    # 3. GridAdvisor analisa F1
    fix_tp_sl_atr, reason = should_fix_tp_sl_atr(top10_f1[:3])
    print(f"GridAdvisor: {reason}")
    
    if fix_tp_sl_atr:
        # FIXAR TP/SL/ATR no melhor do F1
        f1_best = top10_f1[0]
        tp_sl_atr_grid = {
            'tp_mult': [f1_best['tp_mult']],
            'sl_mult': [f1_best['sl_mult']],
            'atr_min': [f1_best['atr_min']],
            'atr_max': [f1_best['atr_max']]
        }
        print(f"  TP/SL/ATR: FIXO (1 combo)")
    else:
        # REFINAR TP/SL/ATR (±20%)
        tp_sl_atr_grid = generate_refined_grid(top10_f1[0], factor=0.20, num=5)
        print(f"  TP/SL/ATR: REFINO ({len(tp_sl_atr_grid['tp_mult'])**4} combos)")
    
    # 4. Montar grid completo
    full_grid = {
        **tp_sl_atr_grid,
        **grid_config['sr_buffers'],
        **grid_config['guardrails'],
        **grid_config['filters']
    }
    
    # 5. Calcular total combos
    total_combos = np.prod([len(v) for v in full_grid.values()])
    estimated_time = total_combos / 10000  # 10K combos/s
    print(f"  Total combos: {total_combos:,}")
    print(f"  Tempo estimado: {estimated_time:.1f}s")
    
    # 6. Executar F2
    results = evaluate_f2(parquet_path, full_grid, direction)
    
    # 7. GridAdvisor analisa resultado
    expand_guardrails, reason = should_expand_guardrails(results, top10_f1[0])
    if expand_guardrails:
        print(f"GridAdvisor: {reason} — re-executar com guardrails reduzidos")
        # Re-executar com guardrails reduzidos...
    
    return results[0]
```

---

## 8. REFERÊNCIAS

- **GUIA_CICLOS_V87.md**: Guia de execução completo
- **F2_GRID_ADVISOR_INTEGRACAO.md**: Documentação técnica do GridAdvisor
- **FLUXO_OTIMIZACAO_V87_FINAL.md**: Arquitetura F0→F6
- **data/f2_grid_configs.json**: Configs de grids por família (a criar)
- **scripts/family_classifier.py**: Classificador de famílias (a criar)

---

**Última Atualização**: 2026-05-04
**Autor**: WIN Lead Quant Scientist
**Próximo Passo**: Implementar grids por família no `f2_optimization_v87.py`
