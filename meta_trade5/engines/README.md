# Motores de Backtest WIN

## Visão Geral

| Motor | Nome | Dados | Velocidade | Guardrails | Uso |
|-------|------|-------|-----------|------------|-----|
| **F1** | Fast Screener | last ticks (15 amostras/candle) | ~1.000/s | **NENHUM** (apenas SL/TP fixo + blocking) | Pre-filtro |
| **F1b** | Fast Screener Binario | last ticks (15 amostras/candle) | ~1.000/s | **NENHUM** (SL/TP + blocking bitwise) | Pre-filtro (blocking correto) |
| **F2** | TICK_LAST | last ticks (todos) | 2/s | Completos | Validacao IS |
| **F3** | TICK_BA | bid/ask real | 2/s | Completos | **Referencia Ouro** |

## REGRA FUNDAMENTAL: F1 NAO TEM GUARDRAILS

F1 **NAO** implementa **NENHUM** guardrail:
- ❌ Break Even (BE)
- ❌ Grace Period
- ❌ Circuit Breaker
- ❌ Slope Decay
- ❌ Filtro de hora (hour filter)
- ❌ Filtro de dia da semana
- ❌ Cooldown apos SL
- ❌ S/R buffers
- ❌ TP30 (take-profit adaptativo)
- ✅ **APENAS** SL/TP fixo (calculado como tp*ATR, sl*ATR)
- ✅ **APENAS** Position blocking (skip = sell_idx + 1)

### Consequencias:
- F1 usa **last prices sampleados** (15/candle) → diferenca de ~5 pts no PnL vs bid/ask
- F1 tem **custo simulado de 30 pts/trade** (nao calculado do spread real)
- F1 **nao filtra hora/dia/ATR** — filtros devem ser aplicados EXTERNAMENTE (filtrar o DataFrame/parquet antes)
- F1 pode entrar em trades em qualquer horario (precisa de pre-filtro por hora)
- F1 pode gerar ate 5-10x mais trades que F3 pela ausencia de guardrails
- F1 e a **pura simulacao de entrada/saida** sem qualquer gestao de risco

### Quando usar o F1:
- **UNICAMENTE** como pre-filtro para eliminar configs obviamente ruins
- **NUNCA** confiar no PnL absoluto do F1 (sempre superestima)
- Usar correlacao de rankeamento (~0.5-0.6), nao valor exato

## F1 — Fast Screener (`f1_fast_screener.py`)

Pre-processa ticks UMA vez, cria matriz M (entries x 750 amostras = 50 candles x 15 samples).

**Pipeline:**
1. `build_M_close()`: processa ticks → candle samples (15/candle) → matriz M
2. `evaluate()`: para cada (tp, sl) → broadcast numpy → hit SL/TP nos samples → position blocking (pos-processamento)

**Arquitetura:**
```python
M[i, :] = [tick1, tick2, ..., tick750]  # 750 sampled prices pos-entrada (50 candles x 15 samples)
```

**SL/TP:** Fixo baseado em multiplicadores do ATR (tp_pts = tp * atr, sl_pts = sl * atr).

**Blocking:** `skip = sell_idx + 1` (1 candle, SEM cooldown adicional).

## F1b — Fast Screener Binario (`f1_binario.py`)

Variante do F1 com blocking bitwise via vetores binarios (0/1).

**Vantagens:**
- Blocking MAIS CORRETO que o F1 Original
- Suporta duracao real do trade (N candles), nao apenas 1 candle fixo
- Bit-packing em uint64: 64 candles por inteiro, colisao verificada via AND

**Dois modos de blocking:**
- `'single'`: bloqueia apenas 1 candle (sell_idx+1) — **compativel com F2/F3**
- `'exact'`: bloqueia a duracao real do trade ([sell_idx+1, sell_idx+duration])

**Descoberta:** O F1 Original tem blocking impreciso que bloqueia trades desnecessariamente. O F1b single gera ~77% mais trades que o F1 Original (blocking correto).

**Arquitetura:**
```python
1. evaluate_combo(): numpy broadcast → had, pnl, duration
2. blocking_binario_uint64(): numba → bit-packing, AND/OR
3. evaluate_batch(): loop sobre grid TP×SL
```

**Interface:**
```python
evaluate(M, ep, atr, sell_idx, tp, sl, direction=-1, blocking_mode='single')
```

## F2 — TICK_LAST (`f2_tick_last.py`)

Wrapper do engine_v2 usando ticks com last prices (bid=ask=last).

Usado para validar no periodo IS (Jan-Mar), onde so ha last ticks.

**Correlacao com F3:** 0.988 (spread de 5 pts do WIN e irrelevante).

## F3 — TICK_BA (`f3_tick_ba.py`)

Wrapper do engine_v2 usando ticks reais com bid/ask.

**Referencia Ouro** para validacao final. TEM todos os guardrails.

## DOIS MODOS DE USO DO F3 (e comparacao com F1)

### Modo Busca (`com_guardrails=False`)
Usado para **comparar F1 com F3** e selecionar estrategias. F3 opera IGUAL ao F1:
- Desliga BE (be_trigger=999999)
- Desliga Grace Period (grace_candles=999)
- Desliga Cooldown (cooldown_candles=0)
- Desliga Circuit Breaker
- Desliga Slope Decay
- Desliga lunch filter (12-14h)
- Desliga restricao 9:00-9:30
- Desliga TP30 (half-profit adaptativo)
- **Apenas SL/TP fixo + position blocking (igual ao F1)**

**Neste modo, F2 e F3 batem com correlacao >0.99** (diferenca so do spread bid/ask).

### Modo Producao (`com_guardrails=True`)
Usado para **validacao final** dos parametros otimizados no OOS:
- BE ativo (be_trigger=200)
- Grace Period ativo (grace_candles=2)
- Cooldown ativo (cooldown_candles=2)
- Circuit Breaker ativo (max 5 SLs consecutivos)
- Slope Decay ativo (0.50)
- Lunch filter e restricao 9:00-9:30 ativos
- TP30 ativo (hp_candles=2, hp_th=0.15)

## Fixes Recentes

### 1. Engine V2 — Exit tick-a-tick (engine_v119_v2.py)
**Antes:** `if max(ask_bar) >= sl: pnl = ep - max(ask_bar)`  
Usava o **maximo/minimo da candle inteira** para calcular o PnL de saida. Superestimava perdas em SL e ganhos em TP.

**Depois:** Itera tick por tick dentro da candle, sai no **primeiro** que cruza SL ou TP:
```python
for t in range(s_tick, e_tick):
    if ask_arr[t] >= effective_sl:
        pnl = ep - ask_arr[t]; break
```

**Impacto:** F2 vs F3 passaram de diferenca de ~5-10% para <1%.

### 2. F1 — PnL real do sample (f1_fast_screener.py)
**Antes:** `pnl[SL] = -sl_pts` (distancia fixa do SL)  
**Depois:** `pnl = ep - cross_price` (preco real do sample que cruzou)

**Impacto:** PnL agora reflete o preco real de saida. A unica diferenca vs F2/F3 e a amostragem (15 vs todos ticks).

### 3. Modo Busca (engine_v2.py)
Adicionado `modo_busca=True` ao `BacktestConfig`. Desliga:
- Circuit Breaker (5 SLs consecutivos)
- Lunch filter (12-14h, DIST_ABS<300)
- Restricao 9:00-9:30 (so HUNTER)

### 4. F3: `apenas_sell` (f3_tick_ba.py)
- `apenas_sell=True`: filtra `PA_SIGNAL_DIR = -1` (so SELL, igual F1)
- `apenas_sell=False`: `PA_SIGNAL_DIR != 0` (ambos sentidos)

## Estudo de Amostragem F1 (30 Abr 2026)

Testamos 7 técnicas de amostragem para o F1 no OOS (TP=10.0 SL=0.2, PA_SIGNAL_DIR SELL):

| Técnica | PnL | Erro vs F3 | Build | Descricao |
|---------|-----|-----------|-------|-----------|
| **F3 (bid/ask)** | **+46.740** | **ref** | — | tick-a-tick (padrao ouro) |
| F2 (last-only) | +46.465 | -0,6% | — | tick-a-tick, sem spread |
| **F1_60** | **+59.085** | **+26%** | **15ms** | 60 amostras uniformes |
| **F1_15** | **+62.460** | **+34%** | **18ms** | 15 amostras uniformes |
| F1_60m micro-OHLC | +72.825 | +56% | 1,8s | high+low por bucket |
| F1_60l LTTB | +74.765 | +60% | 18s | downsampling forma |
| F1_60p P10/P50/P90 | +76.310 | +63% | 4,3s | percentis 10/50/90 |
| F1_60s smooth | +19M | invalido | 3min | media movel |

### Conclusoes:
1. **Nenhuma tecnica de amostragem substitui tick-by-tick.** A perda de informacao entre amostras e inevitavel.
2. **F1_15 e o melhor custo-beneficio:** 18ms build, 3ms para 70 configs, 34% de erro (aceitavel para pre-filtro).
3. **F1_60 melhora apenas 8%:** 4x mais dados reduziu o erro de +34% para +26%. Ganho marginal decrescente.
4. **Micro-OHLC, LTTB, P60 PIORAM o erro:** Tecnicas que preservam extremos introduzem vies de superestimacao.
5. **Suavizacao e invalida:** Media movel achata os picos, nunca atinge SL/TP.
6. **F2 e quase identico ao F3** (correlacao 0.9934, diferenca <1%). A unica diferenca e o spread bid/ask.

### Fluxo recomendado:
```
1. F1_15 no periodo de treino → 200K configs/s → elimina 80% piores
2. F3 modo BUSCA (sem guardrails) → valida top 10-20
3. F3 modo PRODUCAO (com guardrails) → report final top 3-5
```

F1_15 NAO substitui F3 para validacao final. Use apenas como pre-filtro de velocidade.

### Fluxo Correto
```
1. F1 no periodo de treino → 200K configs/s → elimina 80% piores
2. F3 modo BUSCA no mesmo periodo → valida top 10-20 (compara com F1)
3. F3 modo PRODUCAO no OOS → report final top 3-5
```

Guardrails (hour filter, BE, Grace, etc.) sao aplicados APENAS no F3 modo PRODUCAO.
F1 e F3 modo BUSCA OPERAM SEM GUARDRAILS.

## Arquivos

| Arquivo | Descricao |
|---------|-----------|
| `f1_fast_screener.py` | Motor F1 (sem guardrails) |
| `f2_tick_last.py` | Wrapper F2 (= F3 com last ticks) |
| `f3_tick_ba.py` | Wrapper F3 (referencia) |
| `README.md` | Este arquivo |

## Estrategias Implementadas

| Versao | Estrategia | Arquivo | Status | Documentacao |
|--------|------------|---------|--------|--------------|
| **V8.4** | Hybrid com bug fix | `backtest/strategies/v84.py` | ✅ | `docs/WIN_docs/V84_VALIDACAO.md` |
| **V8.5** | Grid search 144 combos | `backtest/strategies/v85.py` | ✅ | `docs/WIN_docs/` |
| **V8.6** | RANGE gmin=200, H-Progress=2c, BE=50 | `backtest/strategies/v86.py` | ✅ | `docs/WIN_docs/V86_HYBRID_DOCUMENTACAO.md` |
| **V8.7** | Grid otimizado (7.26M combos) | `backtest/strategies/v87.py` | ⏳ | `docs/WIN_docs/GRID_SEARCH_OTIMIZADO_V87.md` |

### Scripts F1/F2/F3 por Versao

| Versao | F1 Script | F2 Script | F3 Script | Local |
|--------|-----------|-----------|-----------|-------|
| **V8.4** | `f1_full_scan_v84.py` | — | — | `scripts/` |
| **V8.5** | `f1_full_scan_v85.py` | — | — | `scripts/` |
| **V8.6** | `f1_full_scan_v86.py` | — | — | `scripts/` (mover para `engines/`) |
| **V8.7** | ⏳ `f1_full_scan_v87.py` | ⏳ | ⏳ | ⏳ (criar em `engines/`) |

## Motor Interno: engine_v2 (backtest/engine_v2.py)

O `BacktestEngine` em `backtest/engine_v2.py` é o motor real usado por F2 e F3. A partir da V6.3, suporta:

- **Layer 2 — Ensemble Voting**: `mode.weight` + `ensemble_threshold` para votação ponderada entre múltiplos modos
- **Layer 4 — Risk Manager**: `risk_manager.daily_stop`, `consecutive_sl_limit`, `consecutive_sl_cooldown`
- **Layer 3 — day_of_week filter**: Já funcionava, agora documentado

Detalhes em `docs/WIN_docs/ARQUITETURA_BOT.md`.

> ⚠️ Backup da versão original salvo em `backtest/engine_v2_BACKUP_ORIGINAL.py`.
