# Engines — Documentacao da Pasta

**Versao:** V7.6.0
**Atualizado:** 2026-05-05

**Documentacao relacionada:**
- [`docs/GUIA_DE_CICLOS.md`](../docs/GUIA_DE_CICLOS.md) — Pipeline completo F0-F8
- [`data/README_DADOS.md`](../data/README_DADOS.md) — Dados, periodos e colunas
- [`docs/README_ENGINES.md`](../docs/README_ENGINES.md) — Arquitetura detalhada BacktestEngine v2
- [`AGENTS.md`](../AGENTS.md) — Regras operacionais e checklist

---

## Arquivos Ativos

| Arquivo | Descricao | Status |
|---------|-----------|--------|
| `f1_binario_v4_hybrid.py` | F1 Hybrid V5 (vectorize + thread pool persistente) | **RECOMENDADO** |
| `f1_binario.py` | F1 baseline (OHLC, loop numba, single-core) | ATIVO (baseline/comparacao) |
| `f1_fast_screener.py` | F1 original (com tick samples, 15/candle) | **LEGADO** — nao usar para novo desenvolvimento |
| `f2_tick_last.py` | F2 com tick last | ATIVO |
| `f3_tick_ba.py` | F3 com bid/ask real | ATIVO |
| `calibrate_regime.py` | Calibracao de regime (ER/ADX) | ATIVO |
| `check_dist.py` | Utilitario de distribuicao | ATIVO |

## Arquivos Arquivados

Versoes antigas movidas para `engines/arquivados/`:

| Arquivo | Motivo |
|---------|--------|
| `f1_binario_v2.py` | Superado pelo v3/v4 |
| `f1_binario_v3.py` | Superado pelo v4 |
| `f1_binario_v4.py` | Superado pelo v4b/hybrid |
| `f1_binario_v4b.py` | Superado pelo hybrid |
| `f1_ohlc.py` | Integrado no f1_binario.py |
| `f1_binario_deprecated.py` | Backup da versao com tick samples |
| `f2_optimization_v87.py` | Versao antiga do F2 |

---

## Como Escolher o Motor F1

```
Grid pequeno (< 1K combos)  -> f1_binario.py (simples, confiavel, sem thread pool)
Grid medio (< 20K combos)   -> f1_binario_v4_hybrid.py (1T ou 4T, blocking='exact')
Grid grande (> 20K combos)  -> f1_binario_v4_hybrid.py (8T, pool persistente, blocking='exact')
Top-N apenas (sem matriz)   -> engine.evaluate_batch_topn(blocking_mode='exact')
```

**IMPORTANTE:** Use sempre `blocking_mode='exact'`. O modo 'single' gera 2-28x mais trades que F2/F3 e distorce o rankeamento. Ver [`docs/GUIA_DE_CICLOS.md`](../docs/GUIA_DE_CICLOS.md) — FASE 1.

---

## Interface Comum

Todos os motores F1 compartilham a mesma interface stateless para compatibilidade:

```python
# Stateless (1 combo)
net, n_trades = evaluate(high, low, close, ep, atr, sell_idx, tp, sl, direction=-1)

# Stateless (grid completo, single-core)
net_grid, n_grid = evaluate_batch(high, low, close, ep, atr, sell_idx, tp_grid, sl_grid, direction=-1)

# Stateful (pool persistente — RECOMENDADO para uso repetido)
engine = F1HybridEngine(high, low, close, ep, atr, sell_idx, direction=-1, n_threads=8)
net_grid, n_grid = engine.evaluate_batch(tp_grid, sl_grid, blocking_mode='exact')
engine.shutdown()
```

**Dados de entrada:**
- `high`, `low`, `close`: arrays 1D do `super_win_continuous.parquet` (ver [`data/README_DADOS.md`](../data/README_DADOS.md) secao 1.1)
- `ep`, `atr`, `sell_idx`: arrays das entradas filtradas
- NAO e necessario carregar ticks para F1 — usa apenas OHLC

---

## Dependencias

- `numpy`
- `numba` (para funcoes `@njit`)
- `concurrent.futures` (apenas para Hybrid com threads > 1)

---

## Pipeline F1 -> F2 -> F3

```
F1 (Pre-Filtro)        F2 (Validacao IS)        F3 OOS (Juiz Final)
    |                       |                           |
    v                       v                           v
 OHLC, exact          Tick-level (last)          Tick-level (bid/ask real)
 ~55K combos/s         Guardrails basicos          Guardrails completos
 Top 30 configs        Top 10 configs              Top 3 configs
 Sem custo real        Custo 30 pts simulado       Custo do spread real
```

**Detalhamento:**

| Motor | Dados de Entrada | Guardrails | Ticks | Correlacao com anterior |
|-------|------------------|------------|-------|-------------------------|
| F1-Exact | `super_win_continuous.parquet` (OHLC) | NENHUM | Nao usa | — |
| F2 | `WIN_merged_all.parquet` (last prices) | BE, HP, TP30, Grace, Slope Decay, CD | `last` (sintetico) | +0.998 vs F1-Exact |
| F3 OOS | `data/ticks/WIN*.parquet` (bid/ask) | Guardrails completos | bid/ask REAIS | +0.987 vs F2 (sem GR) |

**Regras de Ouro:**
1. F1-Exact e F2 sao identicos (correlacao +0.998) — F1 serve como pre-filtro rapido
2. F3 sem GR se alinha com F2 (correlacao +0.987) — validacao de saida
3. F3 com GR eh diferente por design — nao comparar PnL absoluto com F2
4. NUNCA usar F1-Single para rankeamento (2-28x mais trades, distorce tudo)

---

## Qualidade dos Dados de Tick

**Problemas encontrados nos ticks da plataforma (OOS):**
- **0.001%** com preco = 0.0 (causa SL falso com pnl = -ep)
- **0.001%** com valores absurdos (bid = 214,585 quando preco ~195,000)
- **~12%** das candles sem tick do high/low real (amostragem incompleta)

**Solucao:** Filtro INLINE no `_simulate_exit_v119` (`backtest/engine_v119_v2.py`):
```python
# Ignora ticks fora do range da candle +/- 1000 pts
if bt <= 0 or bt < float(cj["low"]) - 1000 or bt > float(cj["high"]) + 1000:
    continue

# Fallback para high/low da candle quando nenhum tick valido cruza
if float(cj["high"]) >= ep + current_tp:
    pnl = round(float(cj["high"]) - ep)
```

**NAO pre-processar ticks externos** — quebra `_build_tick_index`. Use filtro inline.

Para mais detalhes sobre os ticks, ver [`data/README_DADOS.md`](../data/README_DADOS.md) secoes 1.2 e 1.3.

---

## Changelog

- **2026-05-05 (V7.6.0):** Documentacao revisada. Referencias cruzadas adicionadas. F1 fast screener marcado como LEGADO.
- **2026-05-05:** F3 — Filtro inline de ticks invalidos + fallback high/low
- **2026-05-05:** F1 Hybrid V5 adicionado (~55K combos/s single, ~39K combos/s exact)
- **2026-05-05:** Versoes antigas arquivadas em `engines/arquivados/`
- **2026-05-05:** F1 refatorado para OHLC (sem tick samples)
- **2026-05-05:** F3 corrigido (TP usa tick real bid/ask)
