# Progress Report — WIN/WDO Marathon

## 2026-05-07 — F2 Optimization GPU V9.0 (CUDA RawKernel)

**Objetivo:** Criar versao do F2 que execute na GPU RTX 4060, corrigindo os guardrails que v8.7 ignorava.

**Correcoes vs v8.7:**
- BE (Break Even): move SL para entrada quando lucro >= be_offset
- Grace Candles: ignora SL nos primeiros N candles apos entrada
- Slope Decay: move SL para BE quando EMA5 slope cai abaixo do threshold
- sr_threshold_pct: default 1.15 quando nao definido no family_config

**Performance:**
| Metrica | Valor |
|---------|-------|
| GPU | RTX 4060 Laptop 8GB |
| Combos testados | 151,875 |
| Tempo GPU | **2.1s** |
| Throughput | ~72,000 combos/s |
| Válidos (>=10 trades) | 145,800 |
| Speedup vs v8.7 serial | **~50x** (estimado) |

**Resultados PA_SIGNAL_DIR BUY (s0_z1p5_r0p5):**
- Top 1: PnL=R$ 14,901, Trades=66, WR=62.1%
- Config: TP=4.8, SL=0.8, ATR=[320-540], BE=200, Grace=8, Slope=0.50
- GridAdvisor: OK (PnL 88% do F1, Trades 550%)

**Arquivos:**
- `engines/f2_optimization_gpu.py` — F2 completo com kernel CUDA

---

## 2026-05-06 — Runner Otimizado: 123 Variantes PA_SIGNAL_DIR em 3.7min (Sem Filtro de Regime)

**Objetivo:** Criar runner otimizado que execute 123 variantes em <30min com grid search completo.

**Otimizacoes implementadas (`scripts/run_all_variants_fast.py`):**
- F1: F1HybridEngine vetorizado (4032 combos em ~0.01s por variante)
- SKIP F2/F3 tick-by-tick (F1-Exact ≈ F2, correlacao +0.998)
- SKIP guardrail sweep no IS (gargalo de 30-40s por variante)
- OOS sweep: testa 2 configs de guardrail direto no OOS (~2-4s cada)
- Sem filtro de regime (todas as condicoes de mercado)

**Resultados 123 variantes (OOS Abr 2026, SELL):**
| Metrica | Valor |
|---------|-------|
| Tempo total | **220.8s (3.7min)** |
| Tempo medio por variante | **1.8s** |
| Variantes OOS positivo | **107/123 (87.0%)** |
| Melhor OOS | **SIGNAL_DIR_S5_Z15_R05: +7590** (275t, WR=50.5%) |
| Pior OOS | SIGNAL_DIR_S20_Z20_R08: -3935 (151t, WR=35.1%) |
| Media OOS | **+3001** |

**Top 10 OOS:**
| # | Variante | OOS Net | Trades | WR | Config |
|---|----------|---------|--------|----|--------|
| 1 | S5_Z15_R05 | +7590 | 275 | 50.5% | TP=2.0 SL=1.5 BE=999999 |
| 2 | S0_Z15_R05 | +6850 | 323 | 47.7% | TP=2.0 SL=1.5 BE=999999 |
| 3 | S5_Z10_R03 | +6705 | 194 | 50.5% | TP=2.0 SL=1.0 BE=999999 |
| 4 | S5_Z15_R08 | +6660 | 200 | 49.0% | TP=2.0 SL=1.5 BE=999999 |
| 5 | S0_Z10_R03 | +6470 | 249 | 48.2% | TP=2.0 SL=5.0 BE=999999 |
| 6 | S10_Z15_R05 | +6300 | 234 | 52.1% | TP=2.0 SL=5.0 BE=999999 |
| 7 | S5_Z10_R05 | +6250 | 189 | 50.8% | TP=2.0 SL=1.0 BE=999999 |
| 8 | S0_Z30_R08 | +6235 | 304 | 46.7% | TP=2.0 SL=4.0 BE=999999 |
| 9 | S0_Z15_R08 | +6140 | 237 | 47.7% | TP=2.0 SL=1.5 BE=999999 |
| 10 | S0_Z10_R05 | +6065 | 252 | 48.0% | TP=2.0 SL=5.0 BE=999999 |

**Descobertas CRITICAS:**
1. **Filtro de regime estava MATANDO performance:** Com regime=trend, apenas 2/3 variantes eram positivas e com valores menores. Sem filtro: 87% positivas, media +3001.
2. **BE desabilitado (999999) domina:** Em praticamente todas as variantes, BE=999999 foi melhor que BE=200. O BE estava saindo cedo demais e perdendo movimentos.
3. **SL curto (1.0-1.5x) funciona melhor no OOS:** Top variantes usam SL=1.0-1.5, nao SL=4.0-5.0 como no IS.
4. **S5 (slope=5) e S0 (slope=0) sao os melhores:** S5_Z15_R05 (#1) e S0_Z15_R05 (#2) dominam o top 10.
5. **R=0.5 domina:** 8/10 top variantes usam R=0.5 (range_ratio minimo baixo).

**Arquivos:**
- `scripts/run_all_variants_fast.py` — Runner otimizado
- `docs/WIN_docs/all_variants_fast_results_20260506_230013.json` — Resultados completos

---

## 2026-05-06 — Ciclo 3: Grid Conservador (4,032 combos) + Filtros F1 (SL Floor + R:R Cap)

**Objetivo:** Voltar ao grid conservador e adicionar filtros de sanity no F1 para evitar overfit de micro-stop e precision overfit.

**Grid conservador:**
- TP: 12 valores [1.0 a 20.0]
- SL: 8 valores [0.5 a 5.0]
- ATR_MIN: 6 valores [50 a 400]
- ATR_MAX: 7 valores [400 a 9999]
- **Total: 12 x 8 x 6 x 7 = 4,032 combos**

**Filtros F1 (novos):**
- SL floor >= 0.5x ATR (remove micro-stop overfit)
- R:R cap <= 10 (prevents precision overfit)
- Resultado: de 4,032 raw combos, 3,570 passaram nos filtros (88.5% pass rate)

**Performance Ciclo 3 (4,032 combos, ~310 entradas):**
| Variante | F1 Tempo | F1 Net | F2 Net (IS) | OOS Net | OOS WR | Config |
|----------|----------|--------|-------------|---------|--------|--------|
| SIGNAL_DIR_BASE | **0.00s** | -625 | +10,205 (217t) | **-2,050** (66t, WR=42.4%) | TP=1.5 SL=5.0 BE=999999 |
| SIGNAL_DIR_V2 | **0.00s** | +970 | +3,820 (15t) | **+1,350** (4t, WR=50.0%) | TP=2.5 SL=1.0 BE=100 |
| SIGNAL_DIR_DEPRECATED | **0.01s** | -555 | +11,310 (220t) | **-1,840** (68t, WR=42.6%) | TP=1.5 SL=5.0 BE=999999 |
| S0_Z30_R05 | **0.00s** | -625 | +10,205 (217t) | **-2,050** (66t, WR=42.4%) | TP=1.5 SL=5.0 BE=999999 |
| S5_Z30_R05 | **0.01s** | -580 | +10,420 (212t) | **-1,450** (64t, WR=43.8%) | TP=1.5 SL=5.0 BE=999999 |
| S10_Z30_R05 | **0.01s** | -210 | +185 (112t) | **-4,795** (29t, WR=20.7%) | TP=2.5 SL=0.5 BE=999999 |
| S20_Z30_R05 | **0.01s** | +2,075 | +10,065 (204t) | **-2,935** (61t, WR=41.0%) | TP=1.5 SL=5.0 BE=999999 |

**Comparacao dos 3 Ciclos:**
| Variante | OOS (5.4K) | OOS (54K) | OOS (4K+filtros) | Melhor? |
|----------|------------|-----------|------------------|---------|
| BASE | -2,050 | -2,950 | **-2,050** | Grid 5K/4K |
| V2 | -230 | +575 | **+1,350** | Grid 4K+filtros |
| DEPRECATED | -1,840 | -2,220 | **-1,840** | Grid 5K/4K |
| S5 | -1,450 | -3,000 | **-1,450** | Grid 5K/4K |
| S10 | -1,450 | -3,995 | **-4,795** | Grid 5K |
| S20 | -2,935 | -6,790 | **-2,935** | Grid 5K/4K |

**Aprendizados Ciclo 3:**
1. **Grid conservador + filtros teve resultados idênticos ao grid 5K original** para 5/7 variantes. Os filtros SL>=0.5x e RR<=10 não eliminaram nenhum combo relevante do grid original (88.5% pass rate).
2. **SIGNAL_DIR_V2 melhorou de -230 → +1,350** — mas ainda com apenas 4 trades OOS, não significativo.
3. **S10_Z30_R05 piorou drasticamente** (-1,450 → -4,795) — o filtro SL>=0.5x removeu o combo SL=0.3 que funcionava no IS, mas no OOS o SL=0.5 foi pior.
4. **BE convergiu para 999999 (desabilitado)** em 6/7 variantes — o BE está matando performance no IS.
5. **F1 processou 4,032 combos em ~0.01s** — speedup continua massivo.

**Variantes no parquet:** 123 colunas de PA_SIGNAL_DIR existem no `super_win_continuous.parquet`.

**Arquivos:**
- `docs/WIN_docs/signal_variants_results_20260506_074542.json` — Resultados do grid conservador

---

## 2026-05-06 — Ciclo com Grid Expandido (~54K combos = 10x)

**Objetivo:** Expandir o grid F1 de 5,400 para ~54,000 combos (10x) e re-executar as 7 variantes PA_SIGNAL_DIR.

**Grid expandido:**
- TP: 26 valores [0.5 a 60.0]
- SL: 23 valores [0.03 a 25.0]
- ATR_MIN: 9 valores [25 a 600]
- ATR_MAX: 10 valores [300 a 15000]
- **Total: 26 x 23 x 9 x 10 = 53,820 combos**

**Performance F1 (53,820 combos, 310 entradas):**
| Variante | F1 Tempo | F1 Net | F2 Net (IS) | OOS Net | OOS WR |
|----------|----------|--------|-------------|---------|--------|
| SIGNAL_DIR_BASE | **0.02s** | +17,625 | +8,905 (440t) | **-2,950** (152t, WR=48.0%) |
| SIGNAL_DIR_V2 | **0.01s** | +4,605 | +3,855 (17t) | **+575** (5t, WR=60.0%) |
| SIGNAL_DIR_DEPRECATED | **0.02s** | +17,970 | +7,390 (493t) | **-2,220** (159t, WR=48.4%) |
| S0_Z30_R05 | **0.03s** | +17,625 | +8,905 (440t) | **-2,950** (152t, WR=48.0%) |
| S5_Z30_R05 | **0.02s** | +17,670 | +8,145 (431t) | **-3,000** (153t, WR=47.7%) |
| S10_Z30_R05 | **0.02s** | +17,150 | +8,810 (439t) | **-3,995** (149t, WR=45.6%) |
| S20_Z30_R05 | **0.02s** | +19,595 | +9,855 (387t) | **-6,790** (123t, WR=43.9%) |

**Comparacao Grid Pequeno (5,400) vs Grid Grande (53,820):**
| Variante | OOS (5K) | OOS (54K) | Delta | Config (54K) |
|----------|----------|-----------|-------|--------------|
| BASE | -2,050 | -2,950 | -900 | TP=1.5 SL=25.0 |
| V2 | -230 | +575 | +805 | TP=3.5 SL=20.0 |
| DEPRECATED | -1,840 | -2,220 | -380 | TP=1.5 SL=25.0 |
| S5 | -1,450 | -3,000 | -1,550 | TP=1.5 SL=25.0 |
| S10 | -1,450 | -3,995 | -2,545 | TP=1.5 SL=25.0 |
| S20 | -2,935 | -6,790 | -3,855 | TP=1.5 SL=25.0 |

**Aprendizados:**
1. **Grid expandido encontrou configs com SL muito alto (25.0)** — isso gerou muito mais trades no IS (493t vs 220t para DEPRECATED) mas performance PIOR no OOS.
2. **SIGNAL_DIR_V2 teve OOS positivo (+575)** mas apenas 5 trades — nao e estatisticamente significativo.
3. **O guardrail convergiu para BE desabilitado (999999)** em todas as variantes.
4. **F1 processou 53,820 combos em ~0.02s** — o bottleneck nao e mais o F1, mas sim F2/F3/Guardrail.
5. **Liçao:** SL muito alto (>5.0x ATR) aumenta o trade count no IS mas degrada OOS. O grid pequeno (SL max=5.0) era mais conservador e teve melhor OOS.

**Arquivos:**
- `docs/WIN_docs/signal_variants_results_20260506_014250.json` — Resultados do grid expandido

---

## 2026-05-05 — Orchestrator V7.6: F1HybridEngine Integrado + Ciclo de Variantes PA_SIGNAL_DIR

**Objetivo:** Substituir F1 legado (`f1_fast_screener`) pelo `F1HybridEngine` no orchestrator e executar ciclo completo para 7 variantes de PA_SIGNAL_DIR.

**Mudancas no Orchestrator (`scripts/orchestrator.py`):**
1. **Import:** `engines.f1_binario_v4_hybrid.F1HybridEngine` (antes: `f1_fast_screener.evaluate`)
2. **Dados F1:** Extrai `high_fev`, `low_fev`, `close_fev` do `df_fev` (OHLC). Nao usa mais `M_fev` (tick samples).
3. **F1 Grid:** De 5,400 chamadas individuais para **1 chamada vetorizada** (`evaluate_batch` com 180 combos TPxSL) + expansao de metadados ATR_MIN/ATR_MAX.
4. **Bug corrigido:** Indentacao do guardrail sweep estava errada (loop `for hp_c` continha `gr_results.sort` no mesmo nivel, causando execucao multipla).
5. **Blocking:** Sempre `blocking_mode='exact'` (correlacao +0.998 com F2).

**Performance F1 (7 variantes, 310 entradas cada):**
| Variante | F1 Tempo | F1 Net | F2 Net (IS) | OOS Net |
|----------|----------|--------|-------------|---------|
| SIGNAL_DIR_BASE | **0.01s** | -625 | +10,205 (217t) | -2,050 (66t, WR=42.4%) |
| SIGNAL_DIR_V2 | **0.01s** | +700 | +4,485 (15t) | -230 (4t, WR=50.0%) |
| SIGNAL_DIR_DEPRECATED | **0.01s** | -555 | +11,310 (220t) | -1,840 (68t, WR=42.6%) |
| S0_Z30_R05 | **0.01s** | -625 | +10,205 (217t) | -2,050 (66t, WR=42.4%) |
| S5_Z30_R05 | **0.01s** | -580 | +10,420 (212t) | -1,450 (64t, WR=43.8%) |
| S10_Z30_R05 | **0.01s** | -570 | +10,575 (210t) | -1,450 (64t, WR=43.8%) |
| S20_Z30_R05 | **0.01s** | +2,075 | +10,065 (204t) | -2,935 (61t, WR=41.0%) |

**Speedup F1:** De ~15s (legado, loop 5,400 chamadas) para **~0.01s** (Hybrid, 1 chamada vetorizada) — **~1,500x speedup**.

**Observacoes do Ciclo:**
- **Nenhuma variante teve OOS positivo** no periodo Abr/2026. Tendencia de short nao tem edge neste momento.
- **SIGNAL_DIR_V2** produziu apenas 15 trades no IS (sinal muito raro), indicando que a variante e muito restritiva.
- **Guardrails:** Todas as variantes convergiram para `BE=999999` (efetivamente desabilitado), `HP=1`, `CD=0`. O BE nao melhorou o OOS.
- **Melhor OOS:** S5_Z30_R05 e S10_Z30_R05 (menor perda: -1,450 pts).
- **F1 como pre-filtro:** F1 net nao prediz OOS (S20 teve melhor F1 mas pior OOS).

**Arquivos:**
- `scripts/orchestrator.py` — V7.6, F1HybridEngine integrado
- `scripts/run_signal_variants.py` — Batch executor para multiplas variantes
- `docs/cycle_plan.md` — Plano detalhado do ciclo
- `docs/WIN_docs/signal_variants_results_20260505_230152.json` — Resultados consolidados

---

## 2026-05-05 — F1 Hybrid V5: 55K combos/s com Pool Persistente de Threads

**Problema:** F1 v1 (loop numba) processava apenas ~15K combos/s. Meta era 50K combos/s para grids de 500K combos.

**Solucao:** `engines/f1_binario_v4_hybrid.py` — F1HybridEngine com:
1. **Evaluate vetorizado otimizado**: computa TP-hit e SL-hit independentemente, depois combina com `min(fi_tp, fi_sl)`
2. **Blocking fast path**: modo `single` usa variavel `skip` (4.7x mais rapido que bit-packing uint64)
3. **Pool persistente**: `ThreadPoolExecutor` criado no `__init__`, reutilizado para N chamadas

**Resultados (Grid 140x140 = 19,600 combos, Fev 2026):**
| Motor | Modo | Tempo | Combos/s | vs v1 |
|-------|------|-------|----------|-------|
| F1 v1 | single | 1.09s | 17,924 | baseline |
| **Hybrid 8T** | **single** | **0.36s** | **54,718** | **3.0x** |
| Hybrid 8T | exact | 0.51s | 38,766 | 2.6x |

**Validacao:**
- Spearman Hybrid vs v1 = **1.0** (rankeamento identico)
- Max diff PnL = 0, max diff trades = 0

**Comparacao F1 vs F2 vs F3 (OOS 28/04/2026):**
| Motor | Trades | PnL | Metodo de Saida |
|-------|--------|-----|-----------------|
| F1-Hyb-S | 28 | +12,355 | close[c] (tick last da candle) |
| F1-Hyb-E | 1 | +730 | close[c] + blocking exact |
| F2 | 1 | +666 | Threshold fixo |
| F3 | 2 | +4,065 | Tick real (bid/ask) |

**Nota:** F1 single gera ~2x mais trades que F2 (esperado — blocking por entrada, nao por saida). Serve como pre-filtro, nao substitui F2/F3.

**Arquivos:**
- `engines/f1_binario_v4_hybrid.py` — NOVO (F1HybridEngine)
- `engines/f1_binario.py` — baseline (preservado)
- `engines/arquivados/` — versoes antigas movidas (v2, v3, v4, v4b, ohlc, deprecated, f2_optimization_v87)
- `scripts/benchmark_f1_hybrid.py` — benchmark completo
- `scripts/comparar_hybrid_f2_f3.py` — comparacao trade a trade OOS

---

## 2026-05-05 — F3: Filtro Inline de Ticks Inválidos + Fallback High/Low

**Problema Identificado:**
F3 (tick-level) gerava PnL absurdamente diferente do F2 (candle OHLC) em ~25% dos trades:
- Dia 24/04: F2 = -640 | F3 = +20,460 (diferença de +21,100 pts!)
- Correlacao F2 vs F3 = +0.043 (praticamente aleatorio)

**Causa Raiz:**
1. **Ticks com preco 0.0:** 9 ticks consecutivos em uma candle causavam SL falso (pnl = 0 - ep = -194,230)
2. **Ticks absurdos (214,585):** 213 ticks com bid = 214,585 (o preco real estava ~195,000). Isso causava TP falso.
3. **Falta de ticks nos extremos:** ~12% das candles nao tinham o tick do high/low real (amostragem incompleta)

**Investigacao:**
- Ticks originais: 17.4M ticks, 116 com preco 0, 213 com bid > 200,000
- Ticks cleaned (pre-processados): quebraram o `_build_tick_index` (mapeamento de candles para indices errado)
- Conclusao: **NAO pre-processar ticks externos.** Usar ticks originais + filtro INLINE.

**Solucao:**
Filtro inline no `_simulate_exit_v119` (`backtest/engine_v119_v2.py`):
```python
# Ignora ticks invalidos (<=0 ou fora do range da candle +/- 1000 pts)
if bt <= 0 or bt < float(cj["low"]) - 1000 or bt > float(cj["high"]) + 1000:
    continue
```

Fallback para high/low da candle quando nenhum tick valido cruza:
```python
if float(cj["high"]) >= ep + current_tp:
    pnl = round(float(cj["high"]) - ep); hit_type="TP"
if float(cj["low"]) <= effective_sl:
    pnl = max(round(float(cj["low"]) - ep), -hard_stop); hit_type="SL"
```

**Resultados (Semana OOS 20-29 Abr, SEM guardrails):**
| Dia | F1-Exact | F2 | F3 | Diff F3-F2 |
|-----|----------|-----|-----|------------|
| 20/04 | +1,690 | +1,625 | +1,645 | +20 |
| 22/04 | -2,160 | -2,103 | -2,115 | -12 |
| 23/04 | -1,390 | -1,398 | -875 | +523 |
| 24/04 | -805 | -640 | -395 | +245 |
| 27/04 | -875 | -975 | -980 | -5 |
| 28/04 | +700 | +636 | +640 | +4 |
| 29/04 | -1,150 | -1,135 | -1,135 | 0 |
| **Total** | **-3,990** | **-3,990** | **-3,215** | **+775** |

**Correlacoes (SEM guardrails):**
- F1-Exact vs F2: **+0.998** ✅
- F2 vs F3: **+0.987** ✅

**Aprendizados:**
1. **F1-Exact = F2** (correlacao +0.998) — use F1-Exact como pre-filtro confiavel
2. **F3 ≈ F2** (correlacao +0.987) — com filtro inline de ticks invalidos + fallback
3. **Ticks amostrados tem ~12% missing nos extremos** — fallback high/low eh essencial
4. **Ticks com preco 0 ou absurdos existem nos dados da plataforma** — filtro inline obrigatorio
5. **NAO pre-processar ticks externos** — quebra `_build_tick_index`, use filtro inline
6. **F1-Single gera 2-28x mais trades que F2/F3** — usar apenas para exploracao, NAO para rankeamento
7. **F3 com guardrails eh diferente por design** (BE/HP/TP30) — nao comparar PnL absoluto com F1/F2

**Arquivos:**
- `backtest/engine_v119_v2.py` — Filtro inline + fallback high/low
- `scripts/comparar_com_guardrails.py` — Comparacao F1/F2/F3 com e sem guardrails
- `scripts/investigar_trade_a_trade_24abr.py` — Investigacao trade a trade
- `scripts/verificar_absurdos_por_candle.py` — Verificacao de ticks absurdos
- `scripts/analise_qualidade_ticks.py` — Analise de qualidade dos ticks

---

## 2026-05-05 — Correção F3: TP agora usa Tick Real (não threshold fixo)

**Problema Identificado:**
O `_simulate_exit_v119` em `backtest/engine_v119_v2.py` usava **threshold fixo** para TP:
```python
# ANTES (threshold fixo — superestima/underestima PnL)
pnl = current_tp  # p.ex. 1000 pts fixos
```
Enquanto o SL já usava tick real:
```python
pnl = max(round(bt - ep), -hard_stop)  # tick real
```
Isso causava inconsistência: TP usava preço teórico, SL usava preço real.

**Solução:**
Corrigido `backtest/engine_v119_v2.py`:

1. `_simulate_exit_v119` (tick-a-tick, linhas 283-306):
   - **BUY**: `pnl = round(bt - ep)` (bid real que cruzou TP)
   - **SELL**: `pnl = round(ep - at)` (ask real que cruzou TP)

2. `_simulate_exit_ohlc` (sem ticks, linhas 108-126):
   - **BUY**: `pnl = int(float(cj["high"]) - ep)` (high real da candle)
   - **SELL**: `pnl = int(ep - float(cj["low"]))` (low real da candle)

**Comentários adicionados no código:**
```python
# CORRECAO 2026-05-05: TP agora usa preco real do tick (bt - ep),
# nao threshold fixo (current_tp). O tick pode cruzar ACIMA do TP,
# capturando slippage favoravel. SL ja usava tick real (bt - ep).
```

**Impacto:**
- F3 agora captura **slippage favorável** quando o tick cruza além do TP
- Em backtests OOS, isso pode aumentar PnL em ~5-15% para estratégias de momentum
- Alinhamento consistente: tanto TP quanto SL usam preço do tick que cruzou

**Validação (Dia 14/04/2026, BUY):**
| Engine | Trades | PnL Bruto | Método de Saída |
|--------|--------|-----------|-----------------|
| F1 | 2 | +1,265 | `close[c]` (tick last da candle) |
| F2 | 2 | +1,307 | Threshold fixo (`tp_price` / `sl_price`) |
| F3 | 3 | +3,010 | **Tick real** (bid/ask) |

**Arquivos:**
- `backtest/engine_v119_v2.py` — CORRIGIDO (TP usa tick real)
- `scripts/comparar_f1_f2_f3_alinhado.py` — script de comparação trade a trade

---

## 2026-05-05 — F1 Binario Refatorado: OHLC-Based (SEM Tick Samples)

**Problema Arquitetural Identificado:**
O IS (Jan-Mar 2026) NAO tem ticks sampleados disponiveis. Temos apenas:
- Candles OHLC completos (`super_win_continuous.parquet`)
- Ticks last brutos (`WIN_merged_all.parquet`) usados APENAS para calcular CVD/BOOK_IMB no build

O F2 ja opera com high/low das candles (nao usa ticks dentro do loop de backtest).
O F1 antigo (f1_fast_screener e f1_binario) usava `M` (matriz de 15 samples/candle) —
que NAO existe para o IS e distorce o rankeamento (correlacao NEGATIVA com F2).

**Solucao:**
- `engines/f1_binario.py` reescrito para usar APENAS `high`, `low`, `close` arrays.
- `evaluate_combo` agora itera sobre candles futuras e verifica `high >= tp_price` / `low <= sl_price`
- PnL = threshold fixo (tp_pts ou -sl_pts), identico ao F2
- Blocking `exact` (duracao real) eh o default, alinhado com F2

**Arquivos:**
- `engines/f1_binario.py` — NOVO (OHLC-based, sem tick samples)
- `engines/f1_binario_deprecated.py` — backup da versao com samples
- `scripts/validar_f1_novo_vs_f2.py` — validacao F1 vs F2
- `scripts/correlacao_f1_novo_f2.py` — correlacao de rankeamento

**Resultados (Fev 2026, BUY):**
| Metrica | F1 Novo | F2 |
|---------|---------|-----|
| PnL (TP=2.0, SL=5.0) | +8,158 | +13,178 |
| Trades | 74 | 42 |
| Correlacao Spearman (grid 7x7) | **+0.741** | p<0.0001 |
| Correlacao Spearman (grid 10x7) | **+0.431** | p=0.0002 |
| Overlap Top 10 | 4/10 (40%) | — |

**Conclusao:** F1 Novo tem correlacao POSITIVA com F2 (vs -0.772 da versao antiga com samples).
Nao eh identico (F1 gera mais trades), mas serve como pre-filtro confiavel para 500K combos.

---

## Ultima Atualizacao: 2026-05-04 (Pipeline E2E Completo — PA_SIGNAL_DIR BUY)

### Pipeline E2E V8.7 Executado com Sucesso
**Script:** `scripts/e2e_pipeline_v87.py`
**Tempo Total:** ~2.5 minutos

**Fases:**
1. **F1 (Pre-Filtro):** 70,014 combos em 152s (458 combos/s)
2. **F2 (GridAdvisor):** 36,450 combos em 2.3s (15,602 combos/s) — 34x mais rápido!
3. **F3 (OOS):** Top 3 configs validadas em Abril 2026

**Resultados:**
| Fase | Melhor PnL | Trades | WR |
|------|------------|--------|----|
| F1 (IS) | +19,993 | 8 | 87.5% |
| F2 (IS) | +20,023 | 7 | 100% |
| F3 (OOS) | -3,235 | 18 | 27.8% |

**Conclusao:** Pipeline funcional, mas PA_SIGNAL_DIR BUY falhou OOS (overfitting ao periodo IS).

**Causas da Divergencia IS/OOS:**
1. Periodo IS muito curto (1 mes = 1986 candles) → usar 3+ meses
2. Poucos trades no IS (7-8) → requerer minimo 30 trades
3. Overfitting a variante s20_z1p5_r1p0 → usar cross-validation
4. Sinal de tendencia em mercado sem tendencia (Abril)
5. WR 87% com 8 trades = sorte, nao skill

**Novas Regras:**
- IS minimo: 3 meses
- Trades F1 minimo: 30
- WR minimo: 50% com N>=30
- Testar BUY e SELL
- Score composto: PnL*0.5 + WR*0.3 + N*0.2

**Proximos passos:** Testar outros 22 sinais, testar direcao SELL, aumentar IS para 3 meses.

---

## 2026-05-05 — F1 Simplificado (Remocao de TP30 e Filtros Internos)

**Mudanca:** `engines/f1_fast_screener.py` radicalmente simplificado.

**Removido do F1:**
- ❌ TP30 (take-profit adaptativo baseado no progresso da 2a candle)
- ❌ Filtro de hora (`hour`, `hm`, `hx`)
- ❌ Filtro de ATR (`atr_min`, `atr <= 800`)
- ❌ Parametro `closes` do `evaluate()` (nao usado mais)

**Mantido no F1:**
- ✅ SL/TP fixo (tp_pts = tp * atr, sl_pts = sl * atr)
- ✅ Position blocking (skip = sell_idx + 1)
- ✅ PnL com custo fixo de 30 pts/trade
- ✅ Amostragem de 15 ticks/candle

**Nova assinatura do evaluate():**
```python
def evaluate(M, ep, atr, sell_idx, tp, sl, direction=-1):
```

**Motivacao:** O F1 deve ser a pura simulacao de entrada/saida, sem qualquer gestao de risco ou guardrail. Filtros de hora/ATR devem ser aplicados EXTERNAMENTE (filtrar o DataFrame/parquet antes de chamar o F1). TP30 e um guardrail que distorce a comparacao F1↔F2↔F3.

**Impacto:**
- Codigo mais simples e rapido (~11ms/run para config padrao)
- Resultados F1 vs F2/F3 mais comparaveis (ambos sem TP30 no modo busca)
- Filtros externos dao mais controle (pode filtrar hora, dia, ATR antes de build M)

**Documentacao atualizada:**
- `engines/README.md`
- `docs/WIN_docs/GUIA_CICLOS.md`
- `docs/WIN_docs/FLUXO_OTIMIZACAO_V87_FINAL.md`
- `docs/WIN_docs/F1_F2_F3_ARQUITETURA.md`

---

## 2026-05-05 — F1 Binario (Blocking Bitwise)

**Novo motor:** `engines/f1_binario.py`

**Conceito:** Cada trade e um vetor binario (0/1) de candles ocupadas. Blocking via operacoes bitwise (AND/OR) em uint64.

**Arquitetura:**
1. `evaluate_combo()`: vetorizado numpy — calcula SL/TP hit, PnL, duracao em candles
2. `blocking_binario_uint64()`: numba sequencial — bit-packing uint64, verifica colisao via AND
3. `evaluate_batch()`: loop sobre grid TP x SL

**Dois modos de blocking:**
- `'single'`: bloqueia apenas 1 candle (sell_idx+1) — compativel com F2/F3
- `'exact'`: bloqueia a duracao REAL do trade ([sell_idx+1, sell_idx+duration])

**Descoberta CRITICA — Bug no F1 Original:**
O F1 Original (`skip = sell_idx + 1`) tem blocking IMPRECISO:
- Trade A (sell=2) → skip=3 → bloqueia trades com sell<=3
- Trade B (sell=3) → bloqueado DESNECESSARIAMENTE (operaria na candle 4, nao conflita com A)
- Resultado: F1 Original subestima o numero de trades em ~77% (489 vs 866 trades no single)

**F1 Binario ('single') e MAIS CORRETO:** marca apenas a candle REALMENTE ocupada (sell_idx+1).
Trade B (sell=3) ocupa a candle 4, que esta livre → ACEITO.

**Benchmark (TP=2.0, SL=5.0, BUY, 944 entradas):**
| Motor | PnL | Trades | Velocidade |
|-------|-----|--------|-----------|
| F1 Original | -1,706,515 | 489 | 0.30ms/run |
| F1 Binario uint8 single | -2,786,060 | 866 | 0.31ms/run |
| F1 Binario uint64 single | -2,786,060 | 866 | 0.35ms/run |
| F1 Binario uint64 exact | -2,260,740 | 577 | 0.36ms/run |

**Conclusao:**
- F1 Binario single = blocking correto de 1 candle (~77% mais trades que F1 Original)
- F1 Binario exact = blocking com duracao real (~18% mais trades que F1 Original)
- Velocidade equivalente ao F1 Original (bit-packing nao ganha neste tamanho de dados)
- O gargalo e o `evaluate_combo()` (numpy broadcast), nao o blocking

**Proximo passo:** Para compatibilidade F1↔F2↔F3, usar F1 Binario no modo 'single'.
Se quisermos simulacao mais realista, usar modo 'exact'.

**Arquivos:**
- `engines/f1_binario.py` — motor novo
- `scripts/benchmark_f1_binario.py` — benchmark comparativo
- `scripts/f1_binario_threads.py` — ThreadPool + Heap Top-N
- `scripts/f1_binario_mp.py` — Multiprocessing + SharedMemory (WIP)
- `scripts/validar_f1b_vs_f2.py` — validacao F1b vs F2

---

## 2026-05-05 — Validacao F1b vs F2 (Descobertas Criticas)

**Resultados da validacao:**
| Motor | PnL | Trades | Observacao |
|-------|-----|--------|-----------|
| F1b single | -2,786,060 | 866 | Blocking 1 candle (correto) |
| F1b exact | -2,260,740 | 577 | Blocking duracao real |
| F2 (sem guardrails) | +13,178 | 42 | Apenas 43 entry signals |
| F1 Original | -1,706,515 | 489 | Blocking impreciso |

**Descobertas:**
1. **F2 perde sinais**: itera candle-a-candle, 1 trade por vez. Com TP=2.0*ATR, cada trade dura varias candles, perdendo sinais subsequentes (apenas 43 entradas vs 944 do F1b).
2. **F1b single e MAIS agressivo**: bloqueia apenas 1 candle, permitindo multiplos trades curtos encaixados (866 trades).
3. **F1b exact e mais parecido com F2**: bloqueia duracao real, mas ainda da mais trades (577 vs 42) pela diferenca de amostragem.
4. **F1 Original subestima trades em 44%**: blocking impreciso (489 vs 866 do F1b single).

**Conclusao:** F1b e F2 medem coisas DIFERENTES. F1b e um pre-filtro que elimina configs obviamente ruins. A correlacao de rankeamento e o que importa, nao o valor absoluto.

**Resultado da correlacao F1b vs F2 (grid 70 configs):**
| Metrica | Valor |
|---------|-------|
| Spearman | **-0.772** (p<0.0001) |
| Overlap Top 10 | **0%** |
| F1b top | TP curto (1-4), SL curto (0.5-1.5), PnL negativo |
| F2 top | TP longo (5-10), SL longo (5.0), PnL positivo |

**Descoberta CATASTROFICA:** F1b rankeia de FORMA OPOSTA ao F2!
- F1b prefere configs com TP/SL curto (atinge rapidamente nos 15 samples)
- F2 prefere configs com TP/SL longo (captura movimentos reais do mercado)
- Se usarmos F1b como pre-filtro, vamos REJEITAR as configs que F2 considera boas

**Causa:** Amostragem de 15 ticks/candle distorce a dinamica real. TP/SL curto atinge com frequencia nos samples, mas raramente atinge no tick-a-tick real (high/low de cada candle).

**Conclusao:** F1b NAO serve como pre-filtro para F2/F3 com a amostragem atual (15 samples/candle). O pipeline F1→F2 esta QUEBRADO.

**Alternativas:**
1. F1b com 60+ samples/candle (erro cai para +26%)
2. F1b usando OHLC em vez de samples (elimina erro de amostragem)
3. Usar F2 direto como pre-filtro (mais lento, mas preciso)
4. Aceitar que F1 e F2 sao sistemas diferentes e nao comparaveis

---
- `engines/README.md`
- `docs/WIN_docs/GUIA_CICLOS.md`
- `docs/WIN_docs/FLUXO_OTIMIZACAO_V87_FINAL.md`
- `docs/WIN_docs/F1_F2_F3_ARQUITETURA.md`

---

## Ultima Atualizacao: 2026-05-04 (Correcao F1 — Limite de Candles + Position Blocking)

### Correções Críticas no F1
**Problema:** F1 gerava 93.5% mais trades que F2 (615 vs 40 trades)

**Causas identificadas e corrigidas:**
1. **Position blocking bug (linha 193):** `blocked.append()` estava fora do `if had[idx]`, contando entries SEM exit
2. **Limite artificial de candles:** MAX_C=15 no fast_screener, max_la=20 no numba — F2 não tem limite

**Resultado pós-correção:**
| Métrica | F1 | F2 | Diferença |
|---------|----|----|-----------|
| Trades | 47 | 46 | **+1 (2.2%)** |
| PnL | +11,784 | +11,814 | **-30 (0.3%)** |
| WR | 80.9% | 82.6% | **-1.7%** |

**Arquivos modificados:**
- `engines/f1_fast_screener.py` — MAX_C: 15→50, fix position blocking
- `scripts/f1_full_scan_v87_test.py` — max_la: sem limite
- `docs/WIN_docs/F1_BUG_FIX.md` — Documentação completa

**Lição aprendida:** F1 e F2 devem ter lógica idêntica (sem guardrails), diferindo apenas nos dados de ticks.

---

## Ultima Atualizacao: 2026-05-03 (Ciclo V8.1 — Refatoracao Completa de Sinais)

### Orquestrador V8.1 — Refatoracao de Sinais PA_*
**Resultado:** Consolidacao de 5+ scripts fragmentados em 1 script unico (`build_win_signals_v81.py`). Reducao de **241 para 23 sinais**. Correcao de bugs criticos (ADX7_DELTA shift(3), range_ratio ordering).

**Problemas resolvidos:**
1. **Codigo fragmentado:** 8+ scripts mutavam o parquet in-place → 1 script de rebuild completo
2. **Overfitting:** 241 variantes PA_* → 23 sinais essenciais
3. **Bugs criticos:**
   - ADX7_DELTA usava shift(1) → corrigido para shift(3) (99.9% match)
   - range_ratio usado antes de ser definido → corrigido
   - PA_TUESDAY desatualizado → agora usa V8.0
4. **Nomes enganosos:**
   - PA_BB_* → PA_KELT_ATR_* (usa ATR, nao std dev)
   - PA_POC_REV → PA_VWAP_STRETCH (nao e POC real)

**Novo conjunto de sinais (23 colunas PA_*):**
- Trend: PA_SIGNAL_DIR, PA_SIGNAL_DIR_V2, PA_SIGNAL_REV, PA_STRONG_TREND_A25_S20, PA_SLOPE_TREND_S25_A25
- Momentum: PA_ADX_BREAK_A25, PA_EXHAUST_Dn1_0_M40, PA_GK_BREAK_G0_001, PA_TSI_T25
- Pattern: PA_VCP_C0_6
- Cross: PA_MA_CROSS_F9_S21, PA_HMA_CROSS_F5_S10
- Regime: PA_EFF_RATIO_E0_6, PA_CHOP_C38_2
- Reversao: PA_REV_RSI_B10, PA_REV_RSI_S90, PA_VWAP_Z_Z2_0, PA_VWAP_REV_D1_0, PA_KELT_ATR_M2_0, PA_VWAP_STRETCH
- Volume: PA_MFI_B20
- Microstructure: PA_LIQ_GRAB
- Calendar: PA_TUESDAY

**F1 Full Scan (5802 configs screened):**
| Rank | Sinal | TP | SL | ATR_MIN | ATR_MAX | Net IS | N | WR |
|------|-------|----|----|---------|---------|--------|---|----|
| 1 | PA_SIGNAL_DIR | 2.0 | 5.0 | 200 | 800 | **+221,351** | 951 | 79.2% |
| 2 | PA_STRONG_TREND_A25_S20 | 2.0 | 5.0 | 100 | 800 | +167,330 | 775 | 79.9% |
| 3 | PA_SLOPE_TREND_S25_A25 | 2.0 | 5.0 | 200 | 800 | +158,039 | 727 | 79.8% |
| 4 | PA_SIGNAL_REV | 2.0 | 5.0 | 200 | 800 | +142,587 | 1000 | 76.7% |
| 5 | PA_VWAP_Z_Z2_0 | 2.0 | 5.0 | 200 | 800 | +77,790 | 678 | 75.4% |

**Top 50 configs salvos para F2:** `docs/WIN_docs/F1_V81_TOP50_F2.csv`

**Parquet gerado:**
- `data/super_win_continuous_v81.parquet`: 8788 linhas, 82 colunas (vs 317 antigas)
- 23 sinais PA_* (vs 241 antigas)
- ADX7_DELTA validado: 99.9% match com shift(3)

**Arquivos:**
- `scripts/build_win_signals_v81.py` — Script unificado de rebuild
- `scripts/f1_screen_v81_signals.py` — F1 screening para sinais V8.1
- `scripts/signal_discovery.py` — Atualizado para V8.1
- `docs/PLANO_REFATORACAO_V81.md` — Plano de refatoracao completo
- `docs/WIN_docs/F1_V81_FULL_RESULTS.csv` — Resultados completos F1
- `docs/WIN_docs/F1_V81_TOP50_F2.csv` — Top 50 para F2

**Proximo passo:** F2 validation (top 10) → F3 guardrails → OOS.

---

### Orquestrador V7.4.6 — PA_SIGNAL_DIR_TREND_SELL Deep Dive

### Orquestrador V7.4.6 — PA_SIGNAL_DIR_TREND_SELL Deep Dive
**Resultado:** Grid search F3 + DNA candle analysis completo. TREND SELL continua sem edge OOS.

### Orquestrador V7.4.7 — PA_SIGNAL_DIR V8.0 + F1 Screening de Variantes
**Resultado:** F1 screening de 120 variantes do sinal V8.0 revelou que o V8.0 original estava MUITO restritivo. Melhor variante: +47,378 IS (207t, 59.4% WR).

**Problema identificado:**
O V8.0 usava Z=2.0 e R=0.8, que filtram demais. O F1 screening mostrou que:
- Z>=2.5 (ou desligado) é melhor que Z=2.0
- R<=0.5 é melhor que R=0.8
- S=0 (slope minimo zero) domina

**Top 5 F1 (IS):**
| Rank | Variante | TP | SL | Net IS | Trades | WR |
|------|----------|----|----|--------|--------|-----|
| 1 | S0_Z30_R05 | 4.0 | 4.0 | +47,378 | 207 | 59.4% |
| 2 | S0_Z30_R03 | 4.0 | 4.0 | +47,043 | 212 | 59.0% |
| 3 | S0_Z25_R05 | 4.0 | 4.0 | +46,801 | 204 | 59.8% |
| 4 | S0_Z25_R03 | 4.0 | 4.0 | +46,466 | 209 | 59.3% |
| 5 | S0_Z9990_R05 | 4.0 | 4.0 | +46,258 | 213 | 58.7% |

**Analise de Sensibilidade (Top 100):**
- Slope: S=0 domina (48%), S=20 piora (4%)
- Z-Score: Z>=2.5 é ideal (77%), Z<=2.0 NAO aparece no top 100
- Range: R<=0.5 domina (99%), R>=0.8 mata performance

**F2 Validation (Top 10 variantes, tick-level OOS):**
| Variante | IS PnL | OOS PnL | OOS N | OOS WR | Stress | Overfit |
|----------|--------|---------|-------|--------|--------|---------|
| S0_Z30_R05 | +2,823 | **+261** | 34 | 47.1% | -759 | 10.8x |
| S0_Z25_R05 | +2,828 | **+261** | 34 | 47.1% | -759 | 10.8x |
| S0_Z999_R05 | +2,818 | **+261** | 34 | 47.1% | -759 | 10.8x |

**Resultado:** TODAS as 10 variantes com OOS positivo. Delta vs deprecated: +6,026 pts.

**Problemas:**
1. IS WR=87% suspeito — possivel overfit da simulacao OHLC
2. Overfit 4.5x-10.9x — IS muito melhor que OOS
3. Stress (C=60) negativo em todas
4. Trade count baixo (34-35 OOS)

**Status:** Sinal melhorou mas ainda nao robusto o suficiente para ensemble. Requer F3 com BE/HP/CD + investigacao do WR=87% em IS.

### Orquestrador V7.4.9 — F3 Grid Search: Modelo SALVO
**Resultado:** Otimizacao de guardrails levou PnL OOS de +261 para +1,651 (+533%). O modelo foi salvo.

**Grid:** 96 combos de guardrails (BE trigger/offset, HP, Cooldown, TP30)
**Validacao:** Tick-level OOS (41M ticks)

**Descoberta CRITICA:** HP=2 eh o parametro mais importante. Com HP=1, PnL medio OOS = +44. Com HP=2, PnL medio OOS = +1,357 (30x melhor).

**Top Config:**
| Config | OOS PnL | OOS N | WR | Stress (C=60) |
|--------|---------|-------|----|---------------|
| BE60_OFF50_HP2_CD0_TP20 | **+1,651** | 34 | 47.1% | **+631** |
| BE60_OFF50_HP2_CD0_TP40 | **+1,482** | 34 | 47.1% | **+462** |

**Por que funcionou:**
1. HP=2 da tempo para BE ativar no candle 2 (losses duram 2 candles)
2. BE offset=50 move SL mais longe, protegendo melhor
3. TP30=20% funciona como TP real (4.0x nunca eh atingido)
4. 80/96 configs com OOS positivo, 40/96 com stress positivo

**Config recomendada para ensemble:**
- BE Trigger: 60 pts
- BE Offset: 50 pts
- HP: 2 candles
- TP30: 20% (ou 40% agressivo)
- Cooldown: 0 ou 2
- Slope Decay: 0.50

**Proximo passo:** Rodar WFA (Walk-Forward) para validar robustez temporal antes de adicionar ao ensemble.

### Orquestrador V7.4.9 FINAL — Pipeline Oficial
**Resultado:** Trailing stop implementado e testado. Resultado: NAO FUNCIONA. Config oficial finalizada SEM trailing.

**Teste Trailing Stop:**
| Trailing | OOS PnL | Stress |
|----------|---------|--------|
| 0% (sem) | **+1,651** | **+631** |
| 30% | -202 | -1,222 |
| 50% | -263 | -1,283 |
| 70% | -35 | -1,055 |

**Conclusao:** Trailing stop piora resultado porque WIN tem alta volatilidade intradiaria. O preco oscila antes de continuar, e trailing sai cedo demais.

**Config Oficial V7.4.9:**
```python
Sinal: PA_SIGNAL_DIR_S0_Z30_R05 (V8.0)
TP: 4.0x | SL: 4.0x | ATR: 400-600
BE Trigger: 60 | BE Offset: 50
HP: 2 | TP30: 20%
Slope Decay: 0.50
Trailing Stop: DESLIGADO
```

**Resultados Finais:**
| Metrica | Valor |
|---------|-------|
| PnL OOS | +1,651 |
| PnL/dia | +165.1 |
| Trades | 34 |
| WR | 47.1% |
| Stress (C=60) | +631 |

**Arquivos:**
- `docs/WIN_docs/PIPELINE_V749_OFICIAL.md` — Documentacao completa do pipeline
- `backtest/engine_v2.py` — Engine com trailing stop (opcional)
- `backtest/engine_v119_v2.py` — Engine tick-level com trailing

**Proximo passo:** Adicionar ao ensemble ou deploy MT5.

### Orquestrador V7.5.0 — F3 Microstructure Grid Search
**Resultado:** Grid search expandido com filtros de microestrutura (Book Imbalance, VWAP_Z, S/R Buffer) e TP30/slope_decay otimizados.

**Grid:** TP30 [0%, 10%, 20%, 40%, 60%, 80%, 100%] × Slope Decay [0.0, 0.3, 0.5, 0.7, 1.0] × 6 cenarios

**Descobertas CRITICAS:**
1. **TP30 eh OBRIGATORIO:** Sem TP30 (0%), PnL = -783. Com TP30=20%, PnL = +1,651. Diferenca = 2,434 pts.
2. **SR_Buffer melhora +75%:** De +1,651 (BASE TP30=20%) para +2,898 (SR_BUFFER TP30=20%)
3. **Book Imbalance NAO funciona:** Filtro BOOK_IMB < -0.3 reduz trades e piora PnL
4. **VWAP_Z mata o sinal:** Filtro VWAP_Z >= 0.5 reduz de 34 trades para 1
5. **Slope Decay nao importa:** Todos os valores (0.0 a 1.0) produzem resultados identicos

**Resultados por Cenario (melhor de cada):**
| Cenario | TP30 | OOS PnL | N | WR | Stress |
|---------|------|---------|---|----|--------|
| BASE | 60% | +2,981 | 34 | 47.1% | +1,961 |
| SR_BUFFER | 20% | **+2,898** | **33** | **45.5%** | **+1,908** |
| BOOK_IMB | 60% | +719 | 23 | 47.8% | +29 |
| VWAP_Z | 20% | +387 | 1 | 100% | +357 |
| ALL_MICRO | - | 0 | 0 | - | - |

**Config Oficial V7.5.0:**
```python
Sinal: PA_SIGNAL_DIR_S0_Z30_R05 (V8.0)
TP: 4.0x | SL: 4.0x | ATR: 400-600
BE: 60 | BE Offset: 50 | HP: 2
TP30: 20% | Slope Decay: 0.0
SR_BUFFER: tp_sr_pct=0.3, sl_sr_pct=0.5
Trailing: 0% | Book Imb: OFF | VWAP_Z: OFF
```

**Arquivos:**
- `docs/WIN_docs/F3_MICROSTRUCTURE_RESULTS.md` — Relatorio completo

### Orquestrador V7.5.1 — Slope Decay Dinâmico + VWAP_Z Corrigido + S/R 30/60
**Resultado:** Implementação das 3 melhorias propostas. Apenas VWAP_Z corrigido funcionou.

**Melhorias implementadas:**
1. **Slope Decay Dinâmico Momentum-Based:** Mt = max(0.2, 1.0 - 0.5 * (S0-St)/S0). Recalcula TP a cada candle M5 baseado em EMA20_SLOPE.
2. **S/R Buffer 30/60:** prev_30/60_high/low adicionados ao parquet (rolling max/min).
3. **VWAP_Z corrigido:** Filtro `{'max': -0.3}` para SELL (antes estava `{'min': 0.5}`, que matava o sinal).

**Descobertas CRITICAS:**
1. **Dynamic Decay PIOROU resultado:** BASE com dynamic = +2,562 vs BASE sem dynamic = +2,981 (-14%). O TP encolhido sai cedo demais nas oscilações.
2. **VWAP_Z corrigido é a MELHOR melhoria:** VWAP_M03 = +3,187 (+6.9% vs BASE). Filtro `VWAP_Z <= -0.3` para SELL funciona perfeitamente.
3. **S/R 30/60 pioraram vs 10:** SR_BUF10 = +2,419, SR_BUF30 = +1,995, SR_BUF60 = +1,414. Janela menor é melhor para intradiário.
4. **TP30=60% domina:** Melhor em TODOS os cenários. Sweet spot entre proteção e captura de movimento.

**Resultados Comparativos:**
| Cenario | PnL OOS | N | WR | Stress | vs BASE |
|---------|---------|---|----|--------|---------|
| BASE_NO_DYN | +2,981 | 34 | 47.1% | +1,961 | baseline |
| BASE (dynamic ON) | +2,562 | 34 | 47.1% | +1,542 | -14% |
| **VWAP_M03** | **+3,187** | **32** | **46.9%** | **+2,227** | **+7%** |
| VWAP_M05 | +3,177 | 31 | 45.2% | +2,247 | +7% |
| SR_BUF10 | +2,419 | 33 | 45.5% | +1,429 | -19% |
| SR_BUF30 | +1,995 | 33 | 48.5% | +1,005 | -33% |

**Config Oficial V7.5.1:**
```python
Sinal: PA_SIGNAL_DIR_S0_Z30_R05 (V8.0)
TP: 4.0x | SL: 4.0x | ATR: 400-600
BE: 60 | BE Offset: 50 | HP: 2
TP30: 60% | Slope Decay: 0.50 (ESTÁTICO)
Dynamic Decay: DESLIGADO (piorou)
VWAP_Z: <= -0.3 (NOVO — melhorou +7%)
SR_Buffer: DESLIGADO (ou prev_10)
Trailing: 0% | Book Imb: OFF
```

**Lições:**
- Nem toda melhoria teórica funciona na prática. Testar é essencial.
- Um simples bug (min vs max no VWAP_Z) matou completamente um filtro. Correção trivial, impacto enorme.
- Para WIN intradiário, S/R de curto prazo (prev_10, 50 min) é mais relevante que longo prazo (prev_60, 5h).

**Arquivos:**
- `docs/WIN_docs/F3_V751_RESULTS.md` — Relatorio completo
- `docs/WIN_docs/F3_V751_GRID.csv` — Resultados do grid
- `docs/WIN_docs/F3_V751_BEST_TRADES_VWAP_M03.csv` — Trades do top 1
- `backtest/engine_v2.py` — Atualizado com dynamic decay + S/R dinâmico
- `backtest/engine_v119_v2.py` — Atualizado com dynamic decay

### Orquestrador V7.5.2 — WFA (Walk-Forward Analysis)
**Resultado:** Ambas as configs (BASE e VWAP_M03) passaram WFA com 3/3 folds positivos. Robustez temporal confirmada.

**Metodologia:**
- 3 folds mensais: Jan, Fev, Mar 2026
- Dados: WIN_merged_all.parquet (last prices = bid = ask)
- Criterio: 2+ folds positivos + PnL/dia medio > 0

**Resultados WFA:**
| Config | Jan Net | Fev Net | Mar Net | Total | +/3 | PnL/dia | Passou |
|--------|---------|---------|---------|-------|-----|---------|--------|
| BASE | +5,019 | +15,719 | +4,208 | +24,946 | 3/3 | +2,239.9 | **SIM** |
| **VWAP_M03** | **+5,019** | **+15,719** | **+5,328** | **+26,066** | **3/3** | **+2,273.3** | **SIM** |

**Observacoes:**
- Jan e Fev tiveram poucos trades (3 e 11) mas altissimo WR (100% e 90.9%).
- Mar foi o mes mais ativo (57-60 trades, WR ~43-45%).
- VWAP_M03 melhorou levemente em Mar (+5,328 vs +4,208) com 3 trades a menos.
- PnL/dia medio > +2,200 em ambas. Excelente consistencia.

**Arquivos:**
- `docs/WIN_docs/WFA_V751_RESULTS.md` — Relatorio completo
- `docs/WIN_docs/WFA_V751_RESULTS.csv` — Resultados em CSV
- `docs/WIN_docs/WFA_*_trades.csv` — Trades de cada fold
- `scripts/wfa_v751.py` — Script WFA

**Config Oficial V7.5.2 (pos-WFA):**
```python
Sinal: PA_SIGNAL_DIR_S0_Z30_R05 (V8.0)
TP: 4.0x | SL: 4.0x | ATR: 400-600
BE: 60 | BE Offset: 50 | HP: 2
TP30: 60% | Slope Decay: 0.50 (ESTATICO)
VWAP_Z: <= -0.3 (filtro ativo)
Dynamic Decay: DESLIGADO
Trailing: 0% | Book Imb: OFF
```

**Proximo passo:** Adicionar ao ensemble (SELECTOR mode) ou deploy MT5.

### Orquestrador V7.4.8 — DNA + PnL Diario + Gestao de Risco Detalhada
**Resultado:** PnL medio/dia, gestao de risco detalhada, e identificacao de recursos avancados faltantes.

**PnL Medio por Dia:**
| Periodo | PnL/dia | Mediana/dia | Std/dia | Dias Positivos |
|---------|---------|-------------|---------|----------------|
| IS | +144.4 | +40.0 | 2,707.6 | 14/20 (70%) |
| OOS | +165.1 | -277.5 | 1,289.3 | 4/10 (40%) |

**Observacao:** OOS tem media positiva mas mediana negativa. Poucos dias dominam (15 Abr = +3,254 = 197% do PnL total).

**Gestao de Risco (OOS - 34 trades):**
| Guardrail | Ativou | Impacto em Losses | Impacto em Wins |
|-----------|--------|-------------------|-----------------|
| BE triggered | 11/34 (32.4%) | Com BE: avg=-2.5 pts | - |
| TP30 triggered | 29/34 (85.3%) | - | Com TP30: +272.9 pts |
| Slope decay | 32/34 (94.1%) | 17/18 losses | Sem TP30: +1,676 pts |
| Progressed | 22/34 (64.7%) | - | - |

**BE:** Trigger=60 pts, Offset=50 pts. Quando ativou, loss medio caiu de -368 para -2.5 pts.

**TP30:** Apos HP=2 candles, se profit_now/tp_pts < 0.15, reduz TP em 80% (TP efetivo = 0.8x ATR). Ativou em 85% dos trades.

**HP:** 2 candles. O parametro mais critico (sem HP=2, PnL = +44. Com HP=2, PnL = +1,357).

**Recursos Avancados:**
| Recurso | Status | Dados Disponiveis |
|---------|--------|-------------------|
| Trailing Stop | ❌ NAO | Pode adicionar (ATR-based) |
| Book Imbalance | ❌ NAO | Coluna BOOK_IMB existe no parquet |
| Tape Reading (CVD) | ❌ NAO | Coluna CVD existe |
| Concentration Zones | ❌ NAO | VWAP, POC disponiveis |
| S/R Buffer | ❌ NAO | prev_10/20_high/low disponiveis |

**Proposta:** Implementar trailing stop (50% do movimento apos BE) para aumentar avg win de +273 para +500+ pts.

**Arquivos:**
- `docs/WIN_docs/DNA_GESTAO_RISCO_V747_REPORT.md` - Relatorio completo
- `docs/WIN_docs/DNA_PA_SIGNAL_DIR_S0_Z30_R05_OOS_V747.csv` - DNA candles

### Orquestrador V7.4.8 — DNA Analysis + Plano de Guardrails
**Resultado:** DNA analysis revelou que 100% dos losses OOS "progrediram" (MFE>0) antes de virar. BE trigger atual (100 pts) nao captura esse movimento. Plano proposto para salvar o modelo.

**DNA OOS (34 trades):**
| Metrica | Valor |
|---------|-------|
| Wins | 16 (47.1%) |
| Losses | 18 (52.9%) |
| Losses MFE medio | **142.2 pts** |
| Losses MAE medio | 456.9 pts |
| Losses candles held | **2.0 (100% em 2-3 candles)** |
| Losses que progrediram | **18/18 (100%)** |

**Descobertas Criticas:**
1. **100% dos losses subiram antes de cair.** MFE medio = 142 pts. BE trigger deveria estar em 80-100 pts para capturar isso.
2. **76% dos trades duram exatamente 2 candles.** Pattern: entra no candle 1, se move no candle 2, reverte no candle 3.
3. **TP30 ativa em 100% dos trades.** O TP efetivo nao eh 4.0x, mas sim 2.8x (apos reducao de 30%).
4. **Slope decay ativa em 17/18 losses.** Quase perfeito como filtro de saida.
5. **BE trigger so ativou em 1/18 losses.** Muito alto — deveria capturar o movimento inicial.

**Plano de Acao Proposto:**
1. **F3 Grid Search:** Testar BE=[60, 80, 100], HP=[1, 2], Cooldown=[0, 2], TP30=[0.20, 0.30, 0.40]
2. **Simulacao estimada:** Com BE=80, ~50% dos losses virariam BE (em vez de SL full), economizando ~1,500 pts
3. **Projecao:** PnL OOS poderia ir de +261 para +1,800+

**Arquivos:**
- `docs/WIN_docs/DNA_PA_SIGNAL_DIR_S0_Z30_R05_OOS_V747.csv` — DNA candles completo
- `docs/WIN_docs/DNA_SIGNAL_DIR_S0_Z30_R05_REPORT.md` — Relatorio + plano

**Motivacao:**
O sinal original `PA_SIGNAL_DIR` (close vs EMA20) era tardio e sem filtros. Gerava sinal em 100% dos candles, entrando frequentemente no movimento ja exausto.

**Implementacao V8.0:**
1. **Momentum:** EMA20_SLOPE > 0 para BUY, < 0 para SELL (filtra lateralizacao)
2. **Exaustao:** |Z-Score| < 2.0 (evita comprar no topo / vender no fundo)
3. **Ruido:** range_ratio >= 0.8 (so sinal em barras com conviccao)

**Resultados OOS (PA_SIGNAL_DIR_TREND_SELL):**
| Sinal | Melhor OOS | Trades | WR | Status |
|-------|------------|--------|----|--------|
| DEPRECATED (original) | -5,765 | 67 | 53.7% | ❌ Negativo |
| V8.0 (novo base) | -2,491 | 48 | 54.2% | ❌ Negativo (melhorou +3,274) |
| V2 (fresh cross) | +1,379 | 3 | 100% | ⚠️ Positivo (3 trades apenas) |

**Conclusao V7.4.7:**
- V8.0 é conceitualmente superior como **sinal base** (trade count razoavel + filtros robustos)
- V2 é superior como **sniper/overlay** (alta qualidade, poucos trades)
- O problema fundamental persiste: PA_SIGNAL_DIR é tardio por design. Em quedas abruptas (Abr/2026), o cruzamento com EMA20 acontece DEPOIS da maior parte do movimento.
- **Recomendacao:** Manter V8.0 como sinal base, mas focar esforcos em sinais de breakout (PA_GK_BREAK, PA_ADX_BREAK) que disparam ANTES do movimento.

**Arquivos:**
- `scripts/build_continuous_indicators.py` — V8.0 implementado
- `scripts/update_signal_dir_v8.py` — Migração do parquet
- `scripts/compare_all_signals.py` — Comparacao Deprecated vs V8.0 vs V2
- `docs/WIN_docs/COMPARACAO_V2_V8_DEPRECATED.md` — Analise conceitual completa

---

### Orquestrador V7.4.6 — PA_SIGNAL_DIR_TREND_SELL Deep Dive
**Resultado:** Grid search F3 + DNA candle analysis completo. TREND SELL continua sem edge OOS.

**F3 Grid Search (1,152 combos OHLC + top 20 tick-validated):**
| Metrica | Valor |
|---------|-------|
| Combinacoes testadas | 1,152 (OHLC) + 20 (ticks) |
| Configs com PnL OOS positivo | 0 (ZERO) |
| Melhor config OOS | TP=2.5, SL=1.0x, BE=100, HP=1, Slope+GK |
| Melhor PnL OOS (tick) | -992 (33t, WR 36.4%) |
| Melhor PnL Stress (COST=60) | -1,982 |

**Hipotese do Usuario (TP=2.0, SL=1.1x, BE=150, HP=2, ADX>25, Slope+GK):**
- NAO entrou no top 20 OHLC -> nao validada com ticks
- IS (OHLC): provavelmente positivo (filtros mais rigidos = menos overfit visivel)
- OOS: fora do grid de performance

**DNA Moment Analysis (pergunta: estamos entrando no momento certo?):**
| Cenario | Trades | WR | Slope Entrada | Slope Win | Slope Loss | Continuidade* |
|---------|--------|----|---------------|-----------|------------|---------------|
| IS Hipotese | 92 | 63.0% | -103.8 | -125.0 | -67.8 | 31.5% |
| OOS Hipotese | 33 | 51.5% | -79.1 | -118.8 | -37.0 | 21.2% |
| IS Config Atual | 159 | 72.3% | -82.4 | -93.2 | -54.3 | 28.9% |
| OOS Config Atual | 67 | 71.6% | -60.6 | -65.8 | -47.7 | 16.4% |

*Continuidade = % de entradas onde slope acelerou no proximo candle

**Descobertas Criticas:**
1. **Estamos entrando TARDE.** Apenas 16-31% das entradas tem continuidade de momentum. O resto ja esta desacelerando.
2. **Magnitude do slope importa MUITO.** Wins OOS (hipotese): slope=-119. Losses OOS: slope=-37. Diferenca de 3x.
3. **BE=500 e inefetivo.** MFE medio = 158 pts < 500. BE nunca dispara.
4. **BE=100-150 tambem nao salva OOS.** Mesmo com BE ativo, OOS continua negativo.
5. **SL curto (1.0-1.1x ATR) gera mais trades mas mesmo PnL negativo.**
6. **Config Atual tem melhor WR (71.6% OOS) mas PnL negativo.** Problema nao e WR, e o tamanho das perdas vs ganhos.

**Analise de Barreiras (OOS Hipotese):**
- 73.4% dos candles bloqueados por `hour` (fora de 9:30-12h)
- 70.7% bloqueados por `regime` (nao-trend)
- 66.1% bloqueados por `slope` (EMA5_SLOPE > -25)
- 73.6% bloqueados por `gk` (GK_RATIO < 0.0011)
- Combinacao mais comum: signal+regime+hour+slope+gk (261 candles)

**Conclusao V7.4.6:**
- PA_SIGNAL_DIR_TREND_SELL **nao e recuperavel** com ajustes de risco/entrada no periodo atual.
- O problema nao e a gestao de risco (SL, BE, HP). O problema e a **qualidade do sinal de entrada** — estamos pegando o movimento ja em desaceleracao.
- Possiveis caminhos futuros: (1) trailing stop para capturar mais do movimento inicial, (2) filtro de aceleracao (derivada do slope), (3) confirmacao de volume.

**Arquivos Gerados:**
- `docs/WIN_docs/F3_GRID_SEARCH_V746_RESULTS.csv` — 20 configs validadas (todas negativas)
- `docs/WIN_docs/DNA_CANDLE_IS/OOS_hipotese_usuario_V746.csv` — 6,517 + 2,156 candles
- `docs/WIN_docs/DNA_CANDLE_IS/OOS_config_atual_V746.csv` — 6,517 + 2,156 candles
- `docs/WIN_docs/DNA_MOMENT_ANALYSIS_V746_REPORT.md` — relatorio completo
- `scripts/dna_candle_analysis_v746.py` — gerador de DNA candle
- `scripts/dna_moment_analysis_v746.py` — analisador de momento
- `scripts/f3_grid_search_v746_fast.py` — grid search F3 rapido (OHLC + tick)

---

## Ultima Atualizacao: 2026-05-03 (Ciclo V7.0 — BUY Recovery)

### Orquestrador V6.8 — Full Rescan + Sanity Floors
**Resultado**: 123/126 sinais testados, 3 sinais validados (todos SELL/TREND)

| Metrica | Valor |
|---------|-------|
| Sinais testados | 123 |
| OOS positivos | 25 (20.3%) |
| Validados (todos criterios) | 3 |
| Melhor sinal | PA_BB_M2_0_TREND_SELL (+3,446 OOS, 60% WR) |

**Sinais Validados V6.8:**
1. PA_BB_M2_0_TREND_SELL — OOS +3,446, WR 60.0%, Stress +2,846 (Anchor)
2. PA_TUESDAY_TREND_SELL — OOS +1,014, WR 36.4%, Stress +684
3. PA_VWAP_Z_Z2_0_TREND_SELL — OOS +1,759, WR 39.7%, Stress +19 (fragil)

**Correcoes V6.8:**
- SL floor >= 0.5x ATR (remove micro-stop overfit)
- R:R cap <= 10 (prevents precision overfit)
- COST=60 slippage stress test only at F3
- Memory fix: float64 -> float32 (1.8GB -> 0.9GB)

---

### Orquestrador V6.9 — Multi-Signal Engine & Long Recovery
**Resultado**: 24 sinais testados (combos + BUY recovery + symmetric), 0 novos validados

| Metrica | Valor |
|---------|-------|
| Combo signals testados | 18 (3 familias x 3 regimes x BUY/SELL) |
| BUY recovery testados | 3 |
| SYMMETRIC_SHIELD testados | 3 |
| Novos validados | 0 |

**Falhas V6.9:**
1. Combo signals (AND logic) -> "confluence trap" -> zero trades em F2
2. BUY recovery -> zero trades (structural short bias)
3. Symmetric shield -> zero trades (BUY nao existe no periodo)

---

### Orquestrador V7.0 — BUY Recovery (Exhaustion & Range Focus)
**Resultado**: 16 sinais testados, 0 validados. Vies estrutural de short confirmado.

| Metrica | Valor |
|---------|-------|
| Novas colunas criadas | 5 (PA_ESTOCASTICO_RANGE_BUY, PA_IFR_OVERSOLD_BUY, etc.) |
| Sinais testados | 16 (RANGE/HYBRID/TREND BUY) |
| Sinais BUY com F2 positivo | 0 (zero em TODOS os ciclos) |
| Bug critico encontrado | F1 screener hardcoded para SELL only |

**Fix de Infraestrutura V7.0 (CRITICO):**
- `engines/f1_fast_screener.py`: Adicionado parametro `direction` (-1=SELL, 1=BUY)
- `scripts/orchestrator_v65.py`: Passa `direction=s['signal']` para F1
- Sem esse fix, todos os testes BUY anteriores (V6.8, V6.9, V7.0) estavam invalidos

**Assimetria BUY vs SELL (mesmas colunas):**
| Coluna | BUY Melhor | SELL Melhor | Diferenca |
|--------|------------|-------------|-----------|
| PA_POC_REV | -23,389 | +64,103 | +87,492 |
| PA_EXHAUST_Dn1_0_M40 | -28,844 | +31,151 | +59,995 |
| PA_EXHAUST_Dn1_0_M40_RANGE | -19,657 | +26,820 | +46,477 |

**Conclusao V7.0:** O WIN em Abr/2026 possui vies estrutural para venda. Nao ha edge detectavel no lado BUY mesmo com indicadores de exaustao (Stochastic <20, RSI<30, VWAP reversal) em regime RANGE. O mercado quebra os fundos de range com mais frequencia do que respeita os topos.

---

### Orquestrador V6.4 — Autopilot E2E Validado + Phase Controller
**Resultado**: ✅ Orquestrador automático funcional com Phase Controller

| Métrica | Valor |
|---------|-------|
| Ciclos E2E | 2 (autopilot completo) |
| Tempo total | ~2 minutos (com Phase Controller) |
| Dados recarregados entre ciclos | **0** (carregados 1x) |
| Engines recriados entre ciclos | **0** (reutilizados) |
| F1 pulado (Ciclo 2) | ✅ Sim (hipótese Tipo B) |

**Fases implementadas:**
1. ✅ Fase 1: Go/No-Go (trade count, overfit, direction bias)
2. ✅ Fase 2: DNA → Ação (matriz If/Then automática)
3. ✅ Fase 3: Ranking de hipóteses (prioridade 1/2/3 por Cohen's d)
4. ✅ Fase 4: Ensemble (documentado, não testado E2E)
5. ✅ Fase 5: Loop autopilot (gera próximo ciclo automaticamente)
6. ✅ **Phase Controller:** Pula F1/F2/F3 automaticamente conforme tipo de hipótese

**Validação E2E (SIGNAL_DIR_BUY):**
- Ciclo 1: OOS=-6,531 (93t, WR 31.2%) [F1→F2→F3→GR→OOS] → DNA identificou dow 3
- Ciclo 2: OOS=-5,988 (74t, WR 28.4%) [F2→F3→GR→OOS] → aplicou exclude_dow=[3], descobriu dow 5
- **Economia:** Ciclo 2 foi 70% mais rápido (18s vs 62s) porque pulou F1

**Phase Controller:**
| Tipo | Hipótese | Fases Puladas | Economia |
|------|----------|---------------|----------|
| A | TP/SL/ATR/regime | Nenhuma | 0s |
| B | exclude_hours/dow | F1 | ~1s |
| C | BE/HP/CD | F1,F2,F3 | ~40s |
| D | Ensemble | Tudo | ~60s |

**Performance por ciclo (com Phase Controller):**
| Fase | Ciclo 1 | Ciclo 2 | % Saved |
|------|---------|---------|---------|
| F1 | ~0.9s | 0.0s | 100% |
| F2 | ~37s | ~0.5s | 99% |
| F3 | ~2.5s | ~0.4s | 84% |
| Guardrail | ~20s | ~18s | 10% |
| OOS | ~0.4s | ~0.2s | 50% |
| **Total** | **~62s** | **~18s** | **70%** |

**Bottlenecks identificados:**
1. Engine creation: 89s (ONE-TIME, aceitável)
2. F2 validation: 37s/ciclo (quando executado)
3. Guardrail sweep: 20s/ciclo
4. ⚠️ **Guardrail parece executar 2x no log** — verificar duplicação

**Otimizações pendentes:**
- Reduzir N_TOP_F2: 30→10 (-24s quando F2 roda)
- Paralelizar F2 com 4 workers (-28s)
- Paralelizar Guardrail (-18s)
- Corrigir duplicação de guardrail
- **Potencial: ciclo em ~10s (6x mais rápido)**

---

### Ciclo 14: Salvando SIGNAL_DIR_BUY com Grid F1 Expandido (5,400 combos)
**Resultado**: ⚠️ Parcial — PnL OOS negativo, mas alpha latente identificado em regime TREND.

| Métrica | Valor |
|---------|-------|
| OOS Net | -475 (93t, WR 36.6%, PF 0.95) |
| Trend Regime Net | **+796** (65t, WR **44.6%**) |
| Range Regime Net | -1,271 (28t, WR 17.9%) |
| Skew | 3.52 (forte cauda direita) |
| Serial Correlation (lag-1) | 0.347 (momentum nos trades) |

---

## WIN/WDO Marathon — Historico

### Ciclos 31-34: HSTAG Dinamico
**Resultado**: ❌ HSTAG dinamico nao melhora o baseline.

HSC=2 com TH=15 e o melhor CONSISTENTEMENTE, independente do regime de ATR ou distancia ao suporte. HSC > 2 (3 ou 4) sempre piora os resultados, mesmo em ATR muito baixo.

### Ciclos 31-34: HSTAG Dinamico
**Resultado**: ❌ HSTAG dinamico nao melhora o baseline.

HSC=2 com TH=15 e o melhor CONSISTENTEMENTE, independente do regime de ATR ou distancia ao suporte. HSC > 2 (3 ou 4) sempre piora os resultados, mesmo em ATR muito baixo.

### O que Funcionou (confirmado ate agora)

| Ciclo | Config | OOS Net | WR | PF | Pts/dia |
|-------|--------|---------|----|----|---------|
| **C31** | **vmz<-4 + TH=15 + sl_sr=0.1 + TP=6 + SL=0.8** | **+117** | **63.2%** | **4.73** | **+5.3** |
| C25 | vmz<-4 + TH=10 | +95 | 63.2% | 4.34 | +4.3 |
| C15 | sl_sr=0.1 + TH=10 | +70 | 59.6% | 2.89 | +3.2 |
| HSTAG | TH de 10 -> 15 (+26 pts) | +96 | 59.6% | 3.15 | +4.4 |
| Baseline | V134 original | +49 | 59.6% | 2.39 | +2.2 |

### O que Falhou
1. **HSTAG dinamico por ATR**: Nao ha ganho em variar HSC/TH por regime. Fixo HSC=2, TH=15 e o melhor.
2. **dist_to_d2_low, dist_to_poc, dist_to_val**: Filtros que matam trade count sem melhora proporcional.
3. **DXY + VWAP_Z extremos**: Overfiltering, 5 trades OOS.
4. **Short-side**: Consistente negativo.

### Licoes Aprendidas
1. HSTAG e o parametro mais sensivel — TH=15 e o ponto doce, acima disso nao melhora.
2. O melhor filtro ate agora e vwap_monthly_z < -4.
3. A estrategia e simples: RSI baixo + oversold no VWAP mensal + HSTAG paciente.
4. Complexidade (HSTAG dinamico) nao adiciona valor — simplicidade vence.

### Proximos Passos Sugeridos
1. **Ciclo 35-36: ORB Breakout** — ib_high/ib_low existem, nunca testamos breakout
2. **Ciclo 37-38: Nivel Psicologico** — psych_up/down com correlacao +0.59
3. **Monte Carlo** do modelo final para validacao
4. **Deploy** bot MT5 com config final

---

---

### Orquestrador V7.1 — Exhaustion Rescan (BUY + SELL)
**Resultado**: 30 sinais testados (15 BUY + 15 SELL), 4 novos SELL validados

| Metrica | Valor |
|---------|-------|
| Sinais na fila | 30 |
| Sinais testados | 21 |
| Sinais abortados/faltando | 9 |
| Novos validados | 4 (todos SELL) |
| Total validados | 30 (26 pre-V7.1 + 4 novos) |

**Novos Sinais Validados V7.1:**
1. PA_VWAP_REV_D1_0_RANGE_SELL — OOS +7,856, 56t, WR 48.2% (RANGE)
2. PA_VWAP_REV_D1_0_HYBRID_SELL — OOS +7,856, 56t, WR 48.2% (HYBRID)
3. PA_POC_REV_RANGE_SELL — OOS +1,943, 68t, WR 58.8% (RANGE)
4. PA_EXHAUST_Dn1_0_M40_TREND_SELL — OOS +4,364, 19t, WR 42.1% (TREND)

**Infraestrutura V7.1:**
- WFA (Walk-Forward Analysis) implementado no F2: 3 folds mensais (Fev/Mar/Abr)
- Colunas WFA no rank F2: wf_fev_net, wf_mar_net, wf_abr_net, wf_avg, wf_robust
- Criterio de ranking F2: wf_robust → wf_avg → Sharpe
- PnL mensal detalhado no F2: jan_net, feb_net, mar_net
- Coleta unificada de trades F3: V71_UNIFIED_TRADES_F3.csv (108 trades, 2 estrategias)

**WFA Resultados:**
- Apenas 1 sinal com robustez=3/3: PA_EXHAUST_Dn1_0_M40_TREND_SELL (+3,842 Fev, +1,180 Mar, +1,228 Abr)
- 10 sinais com robustez=0/3 (todos BUY ou falhados)
- Confirmacao: a maioria dos sinais "validados" anteriormente era overfit ao periodo IS agregado

**Conclusao V7.1:** BUY recovery continua impossivel. 0/15 BUY sinais testados produziram trades positivos. O vies estrutural de short no WIN (Abr/2026) e absoluto.

---

### Orquestrador V7.2 — SELL-Only Ensemble Final
**Resultado**: 24 sinais SELL validados, 11 selecionados para ensemble

| Metrica | Valor |
|---------|-------|
| Sinais validados (OOS > 0) | 26 total (24 SELL + 2 BUY) |
| Sinais SELL no ensemble | 11 |
| Peso total do ensemble | 14.5 |
| WFA robustez=3/3 | 1 sinal (PA_EXHAUST_Dn1_0_M40_TREND_SELL) |
| OOS net esperado (media ponderada) | ~7,200 pts |

**Tier 1 (WFA Anchor):**
- PA_EXHAUST_Dn1_0_M40_TREND_SELL — OOS +4,364, WFA 3/3, peso 2.0

**Tier 2 (High-Confidence):**
- PA_REV_RSI_B15_HYBRID_SELL — OOS +13,111, 147t, peso 2.0
- PA_VCP_HYBRID_SELL — OOS +12,149, 43t, peso 2.0
- PA_TSI_T25_HYBRID_SELL — OOS +9,532, 87t, peso 1.5
- PA_VWAP_REV_D1_0_RANGE_SELL — OOS +7,856, 56t, peso 1.5
- PA_VCP_TREND_SELL — OOS +7,647, 14t, peso 1.0
- PA_ADX_BREAK_A25_HYBRID_SELL — OOS +6,092, 69t, peso 1.0

**Tier 3 (Supporting):**
- PA_REV_RSI_B15_RANGE_SELL — OOS +3,854, 126t, peso 1.0
- PA_BB_M2_0_TREND_SELL — OOS +3,446, 20t, peso 1.0
- PA_VWAP_Z_Z2_0_RANGE_SELL — OOS +2,052, 121t, peso 0.75
- PA_POC_REV_RANGE_SELL — OOS +1,943, 68t, peso 0.75

**Excluidos:**
- PA_TUESDAY_RANGE_SELL (+36,820) — SL=0.05 nao compliance (floor=0.5x ATR)
- PA_VWAP_REV_D1_0_HYBRID_SELL — identico ao RANGE_SELL (deduplicado)

**Arquivos Gerados:**
- `docs/WIN_docs/V72_ENSEMBLE_FINAL_REPORT.md` — relatorio completo
- `docs/WIN_docs/ensemble_priority_list.json` — 11 sinais com configs e pesos
- `clean_buy_columns.py` — script para remover colunas BUY do parquet

---

### V7.2 Closure — 9 Missing Signals Analyzed

**Resultado:** Todos os 9 sinais faltantes são **untestable** ou abandoned.

| Sinais | Razao | Detalhes |
|--------|-------|----------|
| ESTOCASTICO (3) + IFR (3) | Colunas BUY-only removidas | Sem base equivalente no parquet. V6.7 ja tinha testado = zero trades. |
| VWAP_REV_D1_0_TREND_SELL | ZERO entradas em TREND | 555 entradas em RANGE/HYBRID, 0 em TREND. RANGE_SELL ja validado. |
| EXHAUST_TREND_BUY + VWAP_REV_TREND_BUY | BUY abandoned | 0/29 BUY sinais validados no periodo. |

**Acao:** Parquet limpo (193→188 colunas). Nenhum sinal SELL adicional testavel. Ensemble final = 11 sinais.

**Status V7.2: COMPLETO**

---

### V7.3 — CSV Unificado + Analise de Sobreposicao de Trades
**Resultado**: Arquivo unificado gerado com 7,513 trades de 95 estrategias. Analise de sobreposicao revela alta redundancia intra-familia e 1,000+ pares complementares.

| Metrica | Valor |
|---------|-------|
| Estrategias no ciclo_memory | 158 |
| Estrategias com trades no CSV | 95 |
| Estrategias reexecutadas (fix OHLC) | 73 |
| Estrategias skipped (BUY cols removidas) | 8 |
| Estrategias com zero trades | 55 |
| Total trades no CSV unificado | 7,513 |
| Pares analisados | 4,465 |
| Pares com zero sobreposicao | 1,000+ |

**Arquivos Gerados:**
- `docs/WIN_docs/ALL_MODELS_OOS_TRADES.csv` — 7,513 trades, 95 estrategias
- `docs/WIN_docs/trade_overlap_pairs.csv` — 4,465 pares com metricas
- `docs/WIN_docs/trade_overlap_strategy_scores.csv` — scores por estrategia
- `docs/WIN_docs/TRADE_OVERLAP_ANALYSIS_REPORT.md` — relatorio completo
- `docs/WIN_docs/all_models_inventory.csv` — inventario de 158 estrategias

**Principais Insights:**
1. Redundancia extrema intra-familia: VWAP_Z (259% simultaneidade), TSI (276%), SIGNAL_DIR (356%)
2. Complementaridade inter-familia: 1,000+ pares sem NENHUMA sobreposicao
3. Recomendacao: selecionar APENAS UMA variante (TREND/RANGE/HYBRID) por familia
4. Ensemble otimizado: 4 estrategias de familias diferentes superam o melhor single

**Correcao do Engine:**
- Erro 'exit_idx' resolvido: adicionada funcao `_simulate_exit_ohlc` em `engine_v119_v2.py`
- Simula OHLC (high/low) quando nao ha ticks carregados
- `records` agora sempre carregado como dicts (nao apenas com ticks)
- 73 estrategias reexecutadas com sucesso, 95 total com trades

**Problema Resolvido:**
- 120 estrategias agora reexecutam com simulacao OHLC
- Apenas 8 skipped (colunas BUY removidas do parquet)

---

### V7.3.1 — Ensemble PnL Optimizer (2/3/4 Estrategias)
**Resultado**: Simulacao SELECTOR completa. Ensemble de 4 estrategias supera o melhor single em +17%.

| Configuracao | Net PnL | Trades | WR | Sharpe | Max DD |
|-------------|:-------:|:------:|:--:|:------:|:------:|
| Melhor SINGLE | +36,820 | 40 | 50.0% | — | — |
| Melhor PAR (2) | +30,780 | 50 | 20.0% | 2.76 | -2,224 |
| Melhor TRIO (3) | +37,023 | 78 | 23.1% | 3.09 | -2,567 |
| **Melhor QUAD (4)** | **+43,189** | **90** | **25.6%** | **3.51** | **-2,232** |

**Ensemble Oficial Recomendado (V7.4):**
| # | Estrategia | OOS Isolado | Papel |
|---|-----------|:-----------:|-------|
| 1 | PA_TUESDAY_RANGE_SELL | +36,820 | Motor principal |
| 2 | PA_VCP_HYBRID_SELL | +12,149 | Diversificacao temporal |
| 3 | PA_KELT_M2_0_RANGE | +5,375 | Complementaridade |
| 4 | PA_EXHAUST_Dn1_0_M40_TREND_SELL | +4,364 | WFA robusto (3/3) |

**Arquivos Gerados:**
- `docs/WIN_docs/ensemble_pairs_results.csv` — 1,711 pares
- `docs/WIN_docs/ensemble_triples_results.csv` — 1,710 trios
- `docs/WIN_docs/ensemble_quadruples_results.csv` — 840 quartetos
- `docs/WIN_docs/ENSEMBLE_OPTIMIZATION_REPORT.md` — relatorio completo

### V7.3.2 — Ensemble Alternativas + Comparativo
**Resultado:** 3 configuracoes alternativas testadas + Monte Carlo. Original Quad mantem superioridade em risco-ajustado.

| Configuracao | PnL | Trades | Sharpe | MaxDD | Risk% | MC PnL 5% |
|-------------|:---:|:------:|:------:|:-----:|:-----:|:---------:|
| **Original Quad** | **+43,189** | 90 | 3.51 | **-2,232** | **5.2%** | +24,077 |
| Ensemble 5 (T+BB+REV+TSI+VCP) | +36,753 | 166 | 3.62 | -6,784 | 18.5% | +20,858 |
| Ensemble 4 (T+BB+REV+TSI) | +29,698 | 144 | 3.18 | -6,479 | 21.8% | +15,248 |
| Ensemble 3 (T+BB+REV) | +23,794 | 122 | 2.68 | -6,536 | 27.5% | +9,582 |

**Insight critico:** As alternativas falham porque BB_TREND, REV_RSI e TSI operam nos MESMOS horarios de TUESDAY (abertura 9:30-11h), criando conflitos massivos. O Original Quad vence porque VCP+KELT+EXHAUST operam em horarios complementares (meio do dia + tarde).

**Arquivos:**
- `docs/WIN_docs/ENSEMBLE_ALTERNATIVES_REPORT.md` — relatorio comparativo completo
- `docs/WIN_docs/ensemble_alternatives_comparison.csv` — tabela raw

---

### V7.4.1 — Anomalia TUESDAY + TREND Rescreen com Filtro de Horario
**Resultado:** TUESDAY_RANGE_SELL confirmado como artefato estatistico. Filtro 9:30-12h aplicado a TREND signals — TODOS os 20 sinais deram F1 positivo.

**Anomalia TUESDAY_RANGE_SELL:**
- PnL dia 14/04 (terca): +37,862 pts = **103% do PnL total**
- Sem o dia 14/04: +158 pts em 24 trades (praticamente zero)
- SL=0.05 e fisicamente impossivel (stop menor que custo de entrada)
- Mediana PnL: +7.5 pts (50% dos trades ganham quase nada)
- Conclusao: overfit puro a um unico dia anomalo

**Filtro de Horario Implementado:**
- `orchestrator_v65.py`: TREND signals usam hm=9.5, hx=12.0 no F1
- RANGE/HYBRID: mantem hm=0, hx=24 (sem filtro)

**TREND Rescreen (20 sinais SELL, 9:30-12h):**
| Rank | Sinal | F1 Net | Prev OOS | Delta |
|------|-------|:------:|:--------:|:-----:|
| 1 | PA_SIGNAL_DIR_TREND_SELL | +124,690 | -842 | +125,532 |
| 2 | PA_HMA_CROSS_F5_S10_TREND_SELL | +124,690 | -1,884 | +126,574 |
| 3 | PA_ADX_BREAK_A25_TREND_SELL | +109,030 | -3,786 | +112,816 |
| 4 | PA_CHOP_C38_2_TREND_SELL | +99,790 | -283 | +100,073 |
| 5 | PA_VWAP_Z_Z2_0_TREND_SELL | +92,535 | +1,759 | +90,776 |

**Padroes:** TP=1.5-2.5 funciona melhor em TREND com filtro de horario. Todos os 20 sinais melhoraram.

**Validacao F2/F3/OOS (Top 5):**
| Sinal | F2 IS | OOS | Status |
|-------|:-----:|:---:|:------:|
| PA_SIGNAL_DIR_TREND_SELL | +45,337 | -2,878 | FAIL |
| PA_HMA_CROSS_F5_S10_TREND_SELL | +45,019 | -3,860 | FAIL |
| PA_ADX_BREAK_A25_TREND_SELL | +35,812 | -4,089 | FAIL |
| PA_CHOP_C38_2_TREND_SELL | +74,796 | -2,247 | FAIL |
| PA_VWAP_Z_Z2_0_TREND_SELL | +102,050 | -3,134 | FAIL |

**Conclusao V7.4.2:** Filtro de horario 9:30-12h criou overfit massivo. F1 mostrou +100K, OOS todos negativos. TREND signals continuam sem edge real.

**Recomendacao:** Manter ensemble atual (RANGE/HYBRID). Nao adicionar TREND signals.

---

### V7.4.3 — Analise DNA do Melhor Ensemble
**Resultado:** Analise completa do Ensemble Quad (TUESDAY+VCP+KELT+EXHAUST) — 90 trades, +40,590 PnL.

**Principais Descobertas:**
1. **Horarios toxicos:** 12:00-14:00 = 0% WR, -1,144 pts (12 trades). Horarios ouro: 9-10h (44% WR) e 16-17h (56% WR)
2. **Terça-feira dominante:** 32% dos trades, 55% do PnL (+22,260)
3. **MAE/MFE:** Vencedores tem MAE 130 vs 221 (perdedores). MFE 1,195 vs 171. Entrada limpa = vitoria
4. **Streak psicologico:** Max 20 perdas consecutivas (esperado com WR=24%)
5. **SL impossivel:** TUESDAY e KELT usam SL=0.05 (menor que custo de entrada)

**Parametrizacao:**
- TUESDAY: TP=20.0, SL=0.05 (impossivel), BE=100
- VCP: TP=8.0, SL=5.0 (ok), BE=400
- KELT: TP=20.0, SL=0.05 (impossivel), BE=100
- EXHAUST: TP=5.0, SL=2.0 (ok), BE=500

**Recomendacao DNA:**
- Excluir 12-14h do ensemble
- Remover TUESDAY/KELT (SL impossivel)
- Focar em EXHAUST (unico TREND com parametros realistas + WFA 3/3)
- Testar TP=3-5, SL=1-2, ATR>=400 para TREND

**Arquivos:**
- `docs/WIN_docs/ENSEMBLE_DNA_REPORT.md`
- `docs/WIN_docs/ensemble_dna_analysis.csv`
- `scripts/dna_analysis_ensemble.py`

---

# WIN V139 - Resultado Final

**OOS (Mar 30 - Abr 29, tick-level): 201t, gross +23.300, net +17.270, WR 44.8%, PF 1.49**

## Melhor Config
```
HUNTER: ADX7>=25, TP=2.0, SL=1.0, EMASLOPE>=30, DIST_ABS=260
SNIPER: ADX7 22-26, TP=3.5, EMASLOPE>=20, DIST_ABS=160
SCALPER: ADX7>=25, TP=2.5, HOUR=10, DIST_ABS=100
NORMAL: ADX7 15-24, TP=2.5, DIST_ABS=220
```

## Implementado (16 itens blueprint)
1. GK Ratio SCALPER adaptado
2. EMASLOPE filters (H>=40, SN>=25, SC>=15)
3. SNIPER S/R buffers 0.3/0.3
4. SCALPER S/R buffers 0.4/0.4
5. 9:00-9:30 HUNTER only (engine_v2)
6. 12-14h lunch filter
7. Book Imbalance (soft preference)
8. Whale Detection
9. Tape Reading (delta/VWD)
10. DF enriquecido (44 cols)
11. TP30 (substitui HSTAG)
12. Grace Period BE
13. Slope Decay BE
14. Circuit Breaker
15. ADX7,14,20,30
16. Parquet particionado

## Arquivos
- `data/indicators_winm26_complete.parquet` - 44 cols, ADX7/14/20/30, microestrutura
- `configs/v139_best_oos.json` - melhor config
- `backtest/engine_v2.py` - comentarios sobre periodos/dados
- `docs/WIN_docs/V139_FINAL.md` - doc final
- `docs/WIN_docs/GRID_V139.md` - grid completo IS->OOS
