# Guia de Ciclos — Pipeline de Otimizacao WIN

**Versao:** V7.6.0
**Atualizado:** 2026-05-05

**Documentacao relacionada:**
- [`engines/README.md`](../engines/README.md) — Motores F1/F2/F3, como escolher e regras de ouro
- [`data/README_DADOS.md`](../data/README_DADOS.md) — Dados disponiveis, periodos e colunas
- [`README_ENGINES.md`](README_ENGINES.md) — Arquitetura detalhada dos engines
- [`AGENTS.md`](../AGENTS.md) — Regras operacionais e checklist anti-erro

---

## Visao Geral

O pipeline de otimizacao segue fases sequenciais, de discovery a deploy. Cada fase tem objetivo, entrada, saida e criterio de passagem.

```
FASE 0: Signal Discovery     -> Ranking de sinais PA_ por regime (TREND, RANGE, HYBRID)
FASE 1: F1 Fast Screener     -> ~55K combos/s (OHLC, sem guardrails)
FASE 2: F2 Validation (IS)   -> Tick-level IS, guardrails basicos (top 10 F1)
FASE 3: F3 Search (IS)       -> Grid de guardrails (BE/HP/TP30) no IS (top 3 F2)
FASE 4: Microstructure       -> Filtros BOOK_IMB/VWAP/SR (F3 expandido)
FASE 5: F3 OOS Final         -> Tick-level OOS, guardrails completos (dados nunca vistos)
FASE 6: WFA                  -> Walk-Forward Analysis (3 folds mensais)
FASE 7: DNA Analysis         -> Analise trade a trade
FASE 8: Deploy               -> MT5 + Monitoramento
```

**Fluxo de dados:**
```
super_win_continuous.parquet (candles OHLC + indicadores)
         |
         v
    +----+----+
    |         |
    v         v
  F1(OHLC)  F2/F3(ticks)
    |         |
    v         v
Top configs  Validacao
    |         |
    +---->----+
         |
         v
     F3 OOS (bid/ask real)
```

---

## FASE 0: Signal Discovery

**Objetivo:** Encontrar sinais PA_ promissores por regime (TREND, RANGE, HYBRID)

**Entrada:** `data/super_win_continuous.parquet`
**Saida:** Rankings JSON/CSV por regime (`docs/WIN_docs/f1_rank_*.json`)
**Script:** `scripts/signal_discovery.py`

**Criterio de passagem:**
- Sinal com WR > 35% e N > 50 em pelo menos 1 regime

**Detalhes:**
- Calcula Sharpe e PnL para cada sinal PA_* em cada regime
- Usa `engines/f1_fast_screener.py` (LEGADO) para screening rapido
- Para novo pipeline, substituir por `engines/f1_binario_v4_hybrid.py` (ver FASE 1)

---

## FASE 1: F1 Fast Screener

**Objetivo:** Pre-filtrar combinacoes de parametros rapidamente (~39K-55K combos/s)

**Entrada:** `data/super_win_continuous.parquet` (candles OHLC — NAO precisa de ticks)
**Saida:** Top 30 configs por sinal
**Engine:** `engines/f1_binario_v4_hybrid.py` (classe `F1HybridEngine`) — **RECOMENDADO**
**Alternativa legado:** `engines/f1_binario.py` (baseline, single-core)

**Grid F1 (orchestrator padrao):**
- TP: [1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0, 18.0, 20.0, 25.0, 30.0] (15 valores)
- SL: [0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 5.0] (12 valores)
- ATR_MIN: [50, 100, 150, 200, 300] (5 valores)
- ATR_MAX: [400, 600, 800, 1000, 9999, 15000] (6 valores)
- Total: **5,400 combos** (15 x 12 x 5 x 6)

**COST:** 30 pts/trade (simulado, NAO calculado do spread)

**Criterio de passagem:**
- PnL IS > 0
- WR > 35%
- N > 20

**Implementacao recomendada (V5 Hybrid):**
```python
from engines.f1_binario_v4_hybrid import F1HybridEngine

engine = F1HybridEngine(high, low, close, ep, atr, sell_idx, direction=-1, n_threads=8)
net_grid, n_grid = engine.evaluate_batch(tp_grid, sl_grid, blocking_mode='exact')
top_100 = engine.evaluate_batch_topn(tp_grid, sl_grid, top_n=100, blocking_mode='exact')
engine.shutdown()
```

**Velocidades (grid 19,600 combos, Fev 2026):**
| Modo | Threads | Combos/s | Uso |
|------|---------|----------|-----|
| exact | 8T | ~39K | **Pre-filtro (RECOMENDADO)** |
| single | 8T | ~55K | Exploracao agressiva apenas |
| exact | 1T | ~15K | Baseline / comparacao |

**Blocking modes:**
- `exact`: bloqueia duracao real do trade (correlacao +0.998 com F2) — **SEMPRE usar para rankeamento**
- `single`: bloqueia apenas 1 candle (sell_idx+1). Gera 2-28x mais trades que F2/F3. **NUNCA usar para rankeamento.**

**Regras que EU SEMPRE ESQUECO:**
- F1 NAO tem guardrails (sem BE, HP, CD, TP30, Slope Decay)
- F1 usa APENAS `high`/`low`/`close` das candles (sem tick samples desde V7.6)
- F1 NAO filtra hora — filtros externos no DataFrame
- F1 serve APENAS como **pre-filtro** — NUNCA confiar no PnL absoluto
- F1-Exact e F2 sao identicos (correlacao +0.998)
- F3 sem guardrails se alinha com F2 (correlacao +0.987)

**ATENCAO — f1_fast_screener.py:**
- Usa tick samples (15/candle) — legado do pipeline antigo
- Ainda funciona mas **nao e recomendado** para novo desenvolvimento
- O cache `_fev_cache_v2.npz` foi construido para este engine (ver [`data/README_DADOS.md`](../data/README_DADOS.md) secao 1.4)

---

## FASE 2: F2 Validation (IS)

**Objetivo:** Validar top 10 F1 com ticks reais no periodo IS (Jan-Mar)

**Entrada:** Top 10 configs F1 + `data/WIN_merged_all.parquet` (last ticks IS)
**Saida:** Top 3 configs validadas
**Script:** `scripts/f2_validate_signal_dir_variants.py` (standalone)
**Engine:** `backtest/engine_v2.py` (BacktestEngine)

**Caracteristicas:**
- Tick-level usando `last` prices (bid=ask=last, sintetico)
- Guardrails basicos: BE trigger, HP, TP30, Grace Period, Slope Decay, Cooldown
- Custo real calculado do spread (30 pts simulado quando nao ha bid/ask)

**Criterio de passagem:**
- PnL IS > 0 (tick-level)
- WR > 35%
- Stress (C=60) > -1000

**Diferenca F1 -> F2:**
- F1: OHLC puro, sem guardrails, ~55K combos/s
- F2: Tick-level (last), COM guardrails, valida config a config (~1-2s por config)

---

## FASE 3: F3 Search — Otimizacao de Guardrails (IS)

**Objetivo:** Otimizar guardrails (BE, HP, TP30, Slope Decay, Cooldown) no IS

**Entrada:** Top 3 configs F2
**Saida:** Config otimizada com guardrails
**Script:** `scripts/f3_guardgrid_signal_dir.py`
**Engine:** `backtest/engine_v2.py` (BacktestEngine) — mesmo engine F2, dados IS

**Grid F3 (basico):**
- BE Trigger: [100, 200, 300, 999999]
- BE Offset: [25]
- HP: [1, 2, 3]
- Cooldown: [0, 1, 2]
- TP30: [0.30]
- Slope Decay: [0.50]

**Criterio de passagem:**
- PnL IS > 0
- WR > 35%
- N >= 20 (nao matar trade count)

**Nota:** Esta fase roda no IS. A validacao final em OOS e a FASE 5.

---

## FASE 4: Microstructure (V7.5+)

**Objetivo:** Testar filtros avancados de microestrutura no IS

**Entrada:** Config F3 otimizada
**Saida:** Config com/sem filtros microestrutura
**Scripts:** `scripts/f3_microstructure_grid.py`, `scripts/f3_v751_grid.py`

**Filtros testados (resultados historicos):**
- Book Imbalance (BOOK_IMB < -0.3 para SELL) — **NAO FUNCIONOU**
- VWAP_Z (`<= -0.3` para SELL) — **FUNCIONOU (+7% em testes V7.5)**
- S/R Buffer (tp_sr_pct=0.3, sl_sr_pct=0.5, prev_10) — **FUNCIONOU parcialmente**

**ATENCAO — Licoes V7.5.1:**
- VWAP_Z para SELL deve ser **NEGATIVO** (`{'max': -0.3}`), nao positivo. Filtro invertido mata o sinal.
- S/R Buffer com `prev_10` (50 min) funciona melhor que `prev_30/60` para WIN intradiario.
- Slope Decay Dinamico (recalcula TP a cada candle) **PIOROU** resultado. Manter estatico.

**Criterio de passagem:**
- PnL IS > config F3 anterior
- N >= 20 (nao matar o trade count)

---

## FASE 5: F3 OOS Final (Juiz Final)

**Objetivo:** Validar config final em dados NUNCA vistos (OOS)

**Entrada:** Config final + `data/ticks/WIN*.parquet` (ticks OOS bid/ask REAIS)
**Saida:** Relatorio OOS final
**Script:** Rodar `scripts/f3_guardgrid_signal_dir.py` com periodo OOS
**Engine:** `backtest/engine_v119_v2.py` (simulacao tick-level com bid/ask real)

**Periodo OOS:** 30/Mar a 29/Abr (ticks bid/ask REAIS)
**Criterio de passagem:**
- PnL OOS > 0
- WR > 35%
- Stress (C=60) > -500

**Diferenca F2 -> F3 OOS:**
- F2: Ticks IS = `last` prices (sintetico, bid=ask=last)
- F3 OOS: Ticks OOS = bid/ask REAIS da plataforma
- F3 OOS tem filtro INLINE obrigatorio para ticks invalidos (preco 0, absurdos)
- F3 OOS usa fallback high/low da candle quando nenhum tick valido cruza (~12% das candles)

**Qualidade dos ticks OOS (ver [`engines/README.md`](../engines/README.md)):**
- ~0.001% ticks com preco = 0.0
- ~0.001% ticks absurdos (bid > 200K quando preco ~195K)
- ~12% das candles sem tick do high/low real
- **NUNCA pre-processar ticks externos** — quebra `_build_tick_index`. Usar filtro inline.

---

## FASE 6: WFA (Walk-Forward)

**Objetivo:** Validar robustez temporal

**Entrada:** Config final
**Saida:** WFA report
**Metodo:** 3 folds mensais (Jan, Fev, Mar)
**Script:** `scripts/wfa_v751.py`

**Criterio de passagem:**
- 2+ folds positivos
- Media PnL/dia > 0

**Resultados historicos V7.5.2:**
| Config | Jan | Fev | Mar | Total | +/3 | PnL/dia | Passou |
|--------|-----|-----|-----|-------|-----|---------|--------|
| BASE | +5,019 | +15,719 | +4,208 | +24,946 | 3/3 | +2,239.9 | SIM |
| VWAP_M03 | +5,019 | +15,719 | +5,328 | +26,066 | 3/3 | +2,273.3 | SIM |

---

## FASE 7: DNA Analysis

**Objetivo:** Analise trade a trade para entender comportamento

**Entrada:** Trades do top 1 (salvos em CSV)
**Saida:** Relatorio DNA completo
**Script:** `scripts/dna_analysis_best_variant.py`

**Analises:**
- Impacto de cada guardrail (BE, TP30, Slope Decay)
- MFE/MAE por trade
- Duracao (candles held)
- Segmentacao por hora/dia

---

## FASE 8: Deploy

**Objetivo:** Deploy MT5 + monitoramento

**Entrada:** Config oficial validada
**Saida:** EA MT5 + dashboard

**Monitoramento:**
- DNA semanal (comparar com baseline)
- Alerta se WR cair abaixo de 30% por 2 semanas
- Alerta se PnL/dia < 0 por 5 dias consecutivos

---

## Checklist por Ciclo

- [ ] F0: Signal Discovery completo
- [ ] F1: Top 30 selecionados (F1 Hybrid, blocking='exact')
- [ ] F2: Top 10 validados (tick-level IS)
- [ ] F3: Guardrails otimizados (IS)
- [ ] F4: Microestrutura testada
- [ ] F5: OOS validado (PnL > 0, bid/ask real)
- [ ] F6: WFA passou (2+ folds positivos)
- [ ] F7: DNA analysis completo
- [ ] F8: Deploy MT5

---

## Arquitetura F1 -> F2 -> F3 (Resumo)

| Motor | Dados | Guardrails | Ticks | Velocidade | Uso |
|-------|-------|------------|-------|------------|-----|
| **F1 Hybrid** | OHLC candles | NENHUM | Nao usa | ~55K combos/s (single) / ~39K combos/s (exact) | Pre-filtro massivo |
| **F2** | `WIN_merged_all.parquet` (last) | Basicos (BE, HP, TP30) | `last` prices | ~1-2s por config | Validacao IS |
| **F3 OOS** | `data/ticks/WIN*.parquet` | Completos | bid/ask REAIS | ~1s por config | Juiz Final |

**Regras de Ouro:**
1. F1-Exact = F2 (correlacao +0.998) — F1 serve como pre-filtro rapido
2. F3 sem GR se alinha com F2 (correlacao +0.987) — validacao de saida
3. F3 com GR eh diferente por design — nao comparar PnL absoluto com F2
4. NUNCA usar F1-Single para rankeamento (2-28x mais trades, distorce tudo)

---

## Arquivos do Pipeline

| Fase | Script | Engine | Output |
|------|--------|--------|--------|
| F0 | `scripts/signal_discovery.py` | f1_fast_screener (legado) | `docs/WIN_docs/f1_rank_*.json` |
| F1 | `scripts/f1_screen_signal_dir_variants.py` | f1_binario_v4_hybrid | `F1_SCREEN_SIGNAL_DIR_VARIANTS.csv` |
| F2 | `scripts/f2_validate_signal_dir_variants.py` | engine_v2 | `F2_VALIDATION_SIGNAL_DIR_VARIANTS.csv` |
| F3 | `scripts/f3_guardgrid_signal_dir.py` | engine_v2 | `F3_GUARDGRID_SIGNAL_DIR_*.csv` |
| F4 | `scripts/f3_microstructure_grid.py` | engine_v2 | `F3_MICROSTRUCTURE_GRID.csv` |
| F5 | `scripts/f3_guardgrid_signal_dir.py` (periodo OOS) | engine_v119_v2 | Relatorio OOS |
| F6 | `scripts/wfa_v751.py` | engine_v2 | WFA report |
| F7 | `scripts/dna_analysis_best_variant.py` | — | `DNA_*_REPORT.md` |
| F8 | MT5 EA | — | Live trading |

---

*Guia de Ciclos V7.6.0*
*Atualizado em 2026-05-05*
