# F2 OTIMIZAÇÃO COM GRID ADVISOR — DOCUMENTAÇÃO TÉCNICA

**Data**: 2026-05-04
**Versão**: V8.7 (GridAdvisor integrado)

---

## 1. VISÃO GERAL

O **F2 Optimization V8.7** agora integra o **GridAdvisor** — sistema de refinamento iterativo com ZOOM/EXPAND.

### Fluxo com Grid Advisor

```
┌─────────────────────────────────────────────────────────────┐
│  SUB-CICLO 1: Grid Inicial Esparso                          │
│  TP: [1.5, 2.5, 4.0, 6.0, 8.0, 12.0, 18.0] — 7 valores     │
│  SL: [3.0, 5.0, 8.0, 12.0] — 4 valores                      │
│  ATR_MIN: [100, 200, 400] — 3 valores                       │
│  ATR_MAX: [600, 1000, 9999] — 3 valores                     │
│                                                             │
│  Total combos F1: 7×4×3×3 = 252                             │
│  Total combos F2: 252 × 34,992 = 8.8M                       │
│                                                             │
│  GridAdvisor analisa resultados → decide:                   │
│  - ZOOM: reduzir grid em torno do ótimo                     │
│  - EXPAND: expandir grid na direção da borda                │
│  - STOP: convergiu ou spinning detectado                    │
│  - CONTINUE: grids OK, prosseguir                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  SUB-CICLO 2: Grid Refinado (ZOOM)                          │
│  TP: [1.8, 2.0, 2.2, 2.5, 2.8] — 5 valores (zoom em 2.5)   │
│  SL: [4.0, 4.5, 5.0, 5.5, 6.0] — 5 valores (zoom em 5.0)   │
│  ATR_MIN: [150, 180, 200, 220, 250] — 5 valores             │
│  ATR_MAX: [700, 750, 800, 850, 900] — 5 valores             │
│                                                             │
│  Total combos F1: 5×5×5×5 = 625                             │
│  Total combos F2: 625 × 34,992 = 21.9M                      │
│                                                             │
│  GridAdvisor analisa novamente → decide                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  SUB-CICLO 3: Grid Final (ou STOP)                          │
│  GridAdvisor decide STOP ou CONTINUE                        │
│  Top 3 configs → F3                                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. GRID ADVISOR — DECISÕES

### ZOOM

**Quando**: CV% > 20% ou pico instável detectado

**Ação**: Reduz grid em ±20% ao redor do ótimo

**Exemplo**:
```python
# Grid original
TP: [1.5, 2.5, 4.0, 6.0, 8.0]
SL: [3.0, 5.0, 8.0, 12.0]

# Melhor config: TP=2.5, SL=5.0

# Grid após ZOOM
TP: [2.0, 2.25, 2.5, 2.75, 3.0]  # ±20% em torno de 2.5
SL: [4.0, 4.5, 5.0, 5.5, 6.0]    # ±20% em torno de 5.0
```

### EXPAND

**Quando**: Melhor config está na borda do grid

**Ação**: Expande grid na direção da borda

**Exemplo**:
```python
# Grid original
TP: [1.5, 2.5, 4.0, 6.0, 8.0]  # Melhor: TP=8.0 (borda!)

# Grid após EXPAND
TP: [1.5, 2.5, 4.0, 6.0, 8.0, 10.0, 12.0, 15.0, 20.0]
```

### STOP

**Quando**:
- Spinning detectado (delta PnL < 500 pts entre sub-ciclos)
- Max zoom levels atingido (3 níveis)
- SL < floor (0.5x ATR) e max zoom atingido

**Ação**: Interrompe sub-ciclos, prossegue para F3

### CONTINUE

**Quando**:
- CV% < 20% (grid estável)
- Não está na borda
- Planalto estável (vizinhos com drop < 15%)

**Ação**: Prossegue para F3

---

## 3. COMPARAÇÃO: F2 SEM vs COM GRID ADVISOR

| Aspecto | F2 Sem GridAdvisor | F2 Com GridAdvisor |
|---------|-------------------|-------------------|
| **Grid TP/SL/ATR** | Fixo (3×3×3×3 = 81) | Iterativo (esparso → refinado) |
| **Combos F1** | 81 | 252 → 625 → 125 (variável) |
| **Combos F2 total** | 81 × 34,992 = 2.8M | 252 × 34,992 = 8.8M (sub-ciclo 1) |
| **Tempo** | 6 segundos | 15-30s por sub-ciclo |
| **Qualidade** | Grid fixo, pode perder ótimos | Refinamento automático |
| **Risco** | Grid muito fino ou grosso | Auto-ajustável |

---

## 4. ESTRUTURA DO CÓDIGO

### Arquivo: `engines/f2_optimization_v87.py`

```python
# Grids INICIAIS ESPARSOS
TP_GRID = [1.5, 2.5, 4.0, 6.0, 8.0, 12.0, 18.0]  # 7 valores
SL_GRID = [3.0, 5.0, 8.0, 12.0]                   # 4 valores
ATR_MIN_GRID = [100, 200, 400]                    # 3 valores
ATR_MAX_GRID = [600, 1000, 9999]                  # 3 valores

# Grids FIXOS (não refinam)
GRID_TP_SR = [0.70, 0.80, 0.90, 1.00]             # 4 valores
GRID_SL_SR = [1.05, 1.10, 1.15, 1.20]             # 4 valores
GRID_BE = [20, 50, 100]                           # 3 valores
GRID_GRACE = [2, 4, 6]                            # 3 valores
GRID_COOLDOWN = [0, 2, 5]                         # 3 valores
GRID_MAX_SL = [3, 5, 99]                          # 3 valores
GRID_SLOPE = [0.50, 0.65, 0.80]                   # 3 valores
GRID_BOOK_IMB = [0.1, 0.2, 0.3]                   # 3 valores
GRID_CUM_DELTA = [-0.5, 0.0, 0.5]                 # 3 valores

# Total F2 (fixo): 4×4 × 3×3×3×3×3 × 3×3 = 34,992 combos
```

### Função Principal: `run_f2_with_grid_advisor()`

```python
def run_f2_with_grid_advisor(
    parquet_path: str,
    signal_name: str,
    variant_name: str,
    top10_f1: List[Dict],
    direction: int = 1,
    max_subcycles: int = 3
) -> Dict:
    """
    Roda otimização F2 com Grid Advisor (sub-ciclos ZOOM/EXPAND).
    """
    # 1. Carregar parquet
    # 2. Inicializar GridAdvisor
    # 3. Loop de sub-ciclos (max 3)
    #    a. Avaliar todos combos F2
    #    b. GridAdvisor analisa → decide ZOOM/EXPAND/STOP/CONTINUE
    #    c. Se ZOOM/EXPAND: atualiza grids → volta para a
    #    d. Se STOP/CONTINUE: break
    # 4. Retornar top 3 configs + histórico
```

---

## 5. EXEMPLO DE EXECUÇÃO

```bash
python engines/f2_optimization_v87.py \
  --signal PA_SIGNAL_DIR \
  --variant s10_z4p0_r0p5 \
  --direction BUY \
  --max-subcycles 3
```

### Output Esperado

```
================================================================================
F2 OPTIMIZATION COM GRID ADVISOR — PA_SIGNAL_DIR BUY
================================================================================

Loading PA_SIGNAL_DIR.parquet...
  Loaded: 1986 rows (Fevereiro 2026)

================================================================================
SUB-CICLO 1/3
================================================================================
  TP grid: [1.5 2.5 4.  6.  8.  12.  18. ]
  SL grid: [3. 5. 8. 12.]
  ATR_MIN grid: [100 200 400]
  ATR_MAX grid: [600 1000 9999]

  Total combos F1: 252
  Total combos F2 (por config F1): ~34,992

Running optimization (10 configs F1 × 34,992 combos F2)...
  Workers: 10

  Tempo total: 18.5s

  GridAdvisor: ZOOM — F2 CV=28.5% > 20.0% (zoom_level=0)

  🔍 Zoomed grids around best config
     TP: [2.0 2.25 2.5  2.75 3.0 ]
     SL: [4.  4.5 5.  5.5 6. ]

================================================================================
SUB-CICLO 2/3
================================================================================
  TP grid: [2.0 2.25 2.5  2.75 3.0 ]
  SL grid: [4.  4.5 5.  5.5 6. ]
  ATR_MIN grid: [150 180 200 220 250]
  ATR_MAX grid: [700 750 800 850 900]

  Total combos F1: 625
  Total combos F2 (por config F1): ~34,992

Running optimization (10 configs F1 × 34,992 combos F2)...
  Workers: 10

  Tempo total: 22.1s

  GridAdvisor: CONTINUE — F2 CV=12.3%, stable=True, nivel=1

  ✅ GridAdvisor CONTINUE: grids convergiram

================================================================================
TOP 3 CONFIGS F2:
================================================================================

  #1:
     TP/SL/ATR: TP=2.5, SL=5.0, ATR=[180-800]
     S/R Buffers: TP_SR=0.80, SL_SR=1.10
     Gestão Custo: BE=50, GRACE=2, CD=2, MAX_SL=99, SLOPE=0.65
     Filtros: BOOK_IMB=0.2, CUM_DELTA=0.0
     Stats: PnL=R$ 125,450, Trades=580, WR=50.2%

  #2: ...
  #3: ...

================================================================================
SUB-CYCLE HISTORY:
================================================================================
  Sub-cycle 1: ZOOM — Best Net=R$ 118,230
  Sub-cycle 2: CONTINUE — Best Net=R$ 125,450
```

---

## 6. PARÂMETROS DO GRID ADVISOR

| Parâmetro | Valor | Descrição |
|-----------|-------|-----------|
| `zoom_cv_threshold` | 20.0% | CV% mínimo para ZOOM |
| `plateau_drop_threshold` | 15.0% | Drop% máximo para vizinhos (planalto) |
| `spinning_threshold` | 500 | Delta PnL mínimo entre sub-ciclos |
| `max_zoom_levels` | 3 | Máximo de níveis de ZOOM |
| `max_subcycles` | 3 | Máximo de sub-ciclos totais |
| `sl_floor` | 0.5 | SL mínimo (x ATR) |

---

## 7. VANTAGENS DO GRID ADVISOR

1. **Auto-ajustável**: Grid fino só onde precisa, grosso onde não importa
2. **Eficiente**: Começa esparso, refina gradualmente
3. **Robusto**: Detecta spinning, evita overfitting
4. **Transparente**: Cada decisão é logada e justificada

---

## 8. LIÇÕES APRENDIDAS

### Problema Anterior (F2 sem GridAdvisor)

- Grid fixo de 3×3×3×3 = 81 combos TP/SL/ATR
- Melhor config podia estar **entre** os valores do grid
- Sem mecanismo de refinamento

### Solução (F2 com GridAdvisor)

- Grid inicial esparso: 7×4×3×3 = 252 combos
- GridAdvisor decide ZOOM se CV% > 20%
- Refinamento automático em torno do ótimo
- Máximo 3 sub-ciclos (evita spinning)

### Resultado Esperado

- **Melhor qualidade**: Grid fino onde importa
- **Tempo similar**: 30-60s totais (2-3 sub-ciclos)
- **Mais robusto**: Detecta e evita overfitting

---

**Última Atualização**: 2026-05-04
**Autor**: WIN Lead Quant Scientist
