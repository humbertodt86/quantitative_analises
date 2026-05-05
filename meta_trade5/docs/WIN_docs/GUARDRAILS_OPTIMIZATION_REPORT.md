# Relatorio: Guardrails Otimizados vs Nao Otimizados — Modelos TREND

**Data:** 2026-05-03
**Sinais analisados:** PA_SIGNAL_DIR_TREND_SELL, PA_VWAP_Z_Z2_0_TREND_SELL, PA_EXHAUST_Dn1_0_M40_TREND_SELL

---

## 1. Resumo Executivo

| Guardrail | Otimizado? | Como? | Onde estao os dados |
|-----------|:----------:|-------|---------------------|
| **BE (Breakeven)** | **SIM** | Grid [100,200,300,400,500] | guardrail_rank_c1_*.csv |
| **HP (Hit-and-Run)** | **SIM** | Grid [1,2,3] candles | guardrail_rank_c1_*.csv |
| **CD (Cooldown)** | **SIM** | Grid [0,1,2] | guardrail_rank_c1_*.csv |
| **TP/SL/ATR** | **SIM** | Grid F1→F2→F3 | f3_rank_c1_*.csv |
| **Hora (9:30-12h)** | **NAO** | Hardcoded no F1 apenas | NAO salvo no cycle_memory |
| **Tape Reading** | **NAO** | Apenas logging | NAO otimizavel |
| **S/R (Suporte/Resistencia)** | **NAO** | Default=0 (desligado) | NAO otimizavel |
| **Circuit Breaker** | **NAO** | Default=5 (hardcoded) | NAO otimizavel |
| **Daily Stop** | **NAO** | Default=-999999 (desligado) | NAO otimizavel |
| **Slope Decay** | **NAO** | Default=0.50 (hardcoded) | NAO otimizavel |

---

## 2. O que FOI Otimizado

### 2.1 Guardrail Sweep (BE/HP/CD)

**45 combinacoes testadas por sinal:**
- BE_TRIGGERS = [100, 200, 300, 400, 500]
- HP_CANDLES = [1, 2, 3]
- COOLDOWN_CANDLES = [0, 1, 2]

**Resultados (ciclo 1):**

| Sinal | Melhor BE | Melhor HP | Melhor CD | Net IS | WR IS | Sharpe |
|-------|:---------:|:---------:|:---------:|:------:|:-----:|:------:|
| SIGNAL_DIR | 500 | 2 | 0 | +85,997 | 71.1% | 11.55 |
| VWAP_Z | 500 | 3 | 0 | +462,769 | 83.3% | 21.96 |
| EXHAUST | 500 | 3 | 0 | +32,327 | 68.9% | 5.35 |

**Arquivo:** `docs/WIN_docs/guardrail_rank_c1_{SIGNAL}.csv`

### 2.2 F3 Search (TP/SL/ATR)

**Top configs do F3 (IS):**

| Sinal | TP | SL | ATR | F3 Net | F3 WR |
|-------|:--:|:--:|:---:|:------:|:-----:|
| SIGNAL_DIR | 2.0 | 5.0 | [50,800] | +82,538 | 71.6% |
| VWAP_Z | 15.0 | 6.0 | [50,400] | — | — |
| EXHAUST | 5.0 | 2.0 | [50,800] | +30,016 | 64.9% |

**Arquivo:** `docs/WIN_docs/f3_rank_c1_{SIGNAL}.csv`

---

## 3. O que NAO Foi Otimizado

### 3.1 Filtro de Horario

**Problema:** O filtro 9:30-12h foi hardcoded no F1 (`orchestrator_v65.py` linha 433-436), mas:
- **NUNCA foi salvo** no `cycle_memory.json`
- **NUNCA foi passado** para o `build_config()`
- **NUNCA foi otimizado** via grid search
- **NAO existe** em `allowed_hours` ou `exclude_hours` no config

**Prova:**
```python
# No cycle_memory.json:
"config": {
  "tp": 5.0, "sl": 2.0, "atr_min": 50, "atr_max": 800,
  "be_trigger": 500, "hp_candles": 3, "cooldown_candles": 0
  # hour_min, hour_max, allowed_hours, exclude_hours = AUSENTES
}
```

**O filtro de horario esta APENAS no F1**, nao no pipeline completo.

### 3.2 Tape Reading

**Status:** Disponivel no engine (logging), mas **NAO usado como filtro**.

O engine calcula:
- `book_imbalance`
- `tape_delta_pct` (AGGRESSIVE/MODERATE/ABSORPTION)
- `whale_count`

Mas **NAO existe parametro** para ativar/desativar ou otimizar. E puramente informativo.

### 3.3 S/R (Suporte/Resistencia)

**Status:** `tp_sr_pct=0`, `sl_sr_pct=0` (desligado).

O engine suporta blend entre ATR-based e S/R-based TP/SL, mas:
- **Default = 0** (100% ATR, 0% S/R)
- **NUNCA foi testado** > 0
- **NAO esta no grid** de otimizacao

### 3.4 Circuit Breaker / Daily Stop / Slope Decay

| Guardrail | Default | Onde esta |
|-----------|---------|-----------|
| Circuit Breaker | 5 SLs consecutivos | Hardcoded no engine |
| Daily Stop | -999999 (desligado) | Hardcoded no engine |
| Slope Decay | 0.50 (50%) | Hardcoded no build_config |
| Grace Period | 2 candles | Hardcoded no build_config |
| BE Offset | 25 pts | Hardcoded no build_config |
| HP Threshold | 0.15 (15%) | Hardcoded no build_config |
| TP30 PCT | 0.30 (30%) | Hardcoded no build_config |
| Hard Stop | 500 pts | Hardcoded no build_config |

---

## 4. Onde Estao os Dados

| Tipo de Dado | Arquivo | Conteudo |
|-------------|---------|----------|
| **Config final** | `cycle_memory/cycle_memory.json` | TP, SL, ATR, BE, HP, CD |
| **Guardrail sweep** | `guardrail_rank_c1_{SIGNAL}.csv` | 45 combos BE/HP/CD com scores |
| **F3 ranking** | `f3_rank_c1_{SIGNAL}.csv` | Top 3 TP/SL/ATR |
| **F2 ranking** | `f2_rank_c1_{SIGNAL}.csv` | Top 10-30 com metricas mensais |
| **F1 ranking** | `f1_rank_c1_{SIGNAL}.csv` | Top 10-30 TP/SL/ATR |
| **Log completo** | `v67_{SIGNAL}_cycle1_log.txt` | F1→F2→F3→GR→OOS passo a passo |
| **DNA analysis** | `v67_{SIGNAL}_cycle1_dna.json` | 5 estagios de analise |
| **Resumo** | `v67_{SIGNAL}_summary.json` | Config + OOS final |

---

## 5. Conclusao e Recomendacoes

### O que voce tem:
- BE/HP/CD **otimizados** (mas todos deram BE=500 como melhor)
- TP/SL/ATR **otimizados** (mas overfitam ao IS)

### O que voce NAO tem:
- **Filtro de horario** no pipeline completo (apenas no F1)
- **Tape reading** como filtro ativo
- **S/R blend** testado
- **Circuit breaker** ajustavel
- **Multiplos ciclos** de otimizacao (so tem ciclo 1)

### Para otimizar horario:
Adicionar ao `build_config()` e ao grid de otimizacao:
```python
# Em orchestrator_v65.py:
if s.get('hour_min') is not None:
    cfg['hour_min'] = s['hour_min']
if s.get('hour_max') is not None:
    cfg['hour_max'] = s['hour_max']

# Adicionar ao guardrail sweep:
HOUR_MIN_GRID = [9.5, 10.0, 10.5]
HOUR_MAX_GRID = [11.0, 12.0, 13.0]
```

### Para otimizar BE (que voce disse que e alto):
O guardrail sweep JA testou BE=[100,200,300,400,500]. O melhor foi 500. Mas isso foi no **IS** (fevereiro). No **OOS** (abril), BE=500 pode ser muito alto. Precisaria de **WFA por fold** ou **testar BE dinamico** (ex: BE = 0.5x ATR).

---

## Arquivos

| Arquivo | Descricao |
|---------|-----------|
| `docs/WIN_docs/guardrail_rank_c1_PA_SIGNAL_DIR_TREND_SELL.csv` | 45 combos BE/HP/CD |
| `docs/WIN_docs/guardrail_rank_c1_PA_VWAP_Z_Z2_0_TREND_SELL.csv` | 45 combos BE/HP/CD |
| `docs/WIN_docs/guardrail_rank_c1_PA_EXHAUST_Dn1_0_M40_TREND_SELL.csv` | 45 combos BE/HP/CD |
| `docs/WIN_docs/f3_rank_c1_PA_SIGNAL_DIR_TREND_SELL.csv` | Top 3 TP/SL/ATR |
| `docs/WIN_docs/f3_rank_c1_PA_EXHAUST_Dn1_0_M40_TREND_SELL.csv` | Top 3 TP/SL/ATR |
| `scripts/check_guardrails.py` | Script que gerou este relatorio |
