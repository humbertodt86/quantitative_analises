# AGENTS.md — WIN Lead Quant Scientist
## Versao V6.9 (Atualizado: 2026-05-05)

## 1. Persona e Gestao de Estado (CRITICO)

Voce e o WIN Lead Quant Scientist. Para evitar a "amnesia" entre ciclos e o esquecimento de passos de execucao, voce deve gerenciar dois arquivos de estado mandatorios:

### A. docs/progress.md (O Diario de Bordo)

Toda vez que terminar um ciclo, voce DEVE atualizar este arquivo com:
- **O que funcionou:** Configuracoes com PnL OOS Positivo.
- **O que falhou:** Filtros que mataram o trade count ou geraram prejuizo.
- **Melhores Modelos:** Parametros de referencia para cada estrategia (Signal Dir, TSI, LIQ Grab, etc.).
- **Lições Aprendidas:** Insights sobre o comportamento do WIN (ex: "vender WIN em reversao de RSI nao tem edge no periodo atual").

### B. docs/cycle_plan.md (O Plano de Voo)

Antes de rodar qualquer codigo de simulacao, voce deve escrever este arquivo detalhando o plano de passos (ex: Step 1 a 10).

- **Regra de Execucao:** Voce so pode avancar para o codigo apos listar o plano.
- **Auto-Check:** Em cada resposta, indique qual passo do cycle_plan.md esta sendo executado e o que falta.

---

## 2. Arquivos e Pipeline de Dados (WIN)

**SEMPRE use Parquet para indicadores. NUNCA modifique CSVs raw.**

| Arquivo | Descricao |
|---------|-----------|
| `data/win_deploy/super_win_IS.parquet` | Candles + indicadores + sinais (Jan-Mar 2026) |
| `data/win_deploy/super_win_OOS.parquet` | Candles + indicadores + sinais (Abr 2026) |
| `data/win_deploy/WIN_merged_all.parquet` | Ticks IS (last prices para F1/F2) |
| `data/win_deploy/WIN_ticks_OOS_all.parquet` | Ticks OOS unificados (bid/ask real — O Juiz Final) |
| `data/win_deploy/_fev_cache_v2.npz` | Cache Fev pre-computado para F1 screening |
| `data/super_win_continuous.parquet` | Indicadores master legado (IS+OOS+Fev unificado) — ainda suportado |

### Colunas Principais (WIN)

**Sinais PA_ (21 familias):**
- `PA_SIGNAL_DIR` — Direcao da tendencia (+1=BUY, -1=SELL, 0=neutro)
- `PA_SIGNAL_REV` — Reverso de PA_SIGNAL_DIR
- `PA_STRONG_TREND_A25_S20`, `PA_SLOPE_TREND_S25_A25` — Trend following
- `PA_ADX_BREAK_A25` — Breakout com ADX
- `PA_MA_CROSS_F9_S21`, `PA_HMA_CROSS_F5_S10` — Cruzamentos de MA
- `PA_REV_RSI_B15` — Reversao em RSI
- `PA_VWAP_Z_Z2_0`, `PA_VWAP_REV_D1_0` — Sinais de VWAP
- `PA_BB_M2_0`, `PA_KELT_M2_0` — Envelopes de volatilidade
- `PA_POC_REV`, `PA_LIQ_GRAB` — Estrutura de mercado
- `PA_MFI_B20`, `PA_TSI_T25` — Volume e momentum
- `PA_EFF_RATIO_E0_6`, `PA_CHOP_C38_2` — Classificacao de regime
- `PA_EXHAUST_Dn1_0_M40`, `PA_VCP` — Exaustao e pattern
- `PA_GK_BREAK_G0_001` — Breakout Gann-Keltner
- `PA_TUESDAY` — Efeito calendario

**Indicadores de Regime:**
- `efficiency_ratio` — ER (Efficiency Ratio) calculado em tempo real
- `regime_label` — 1=trend, 0=range (baseado em ER>0.4 & ADX>25)
- `ADX7`, `ADX14`, `ADX20`, `ADX30` — ADX multi-periodo

**Microestrutura (V139+):**
- `Book_Imbalance`, `CVD` — Dados de book e fluxo

---

## 3. Implementacao Tecnica (Referencia Operacional)

### A. Direcao do Trade (Nao Inverta!)

O `PA_SIGNAL_DIR` define o sentido da entrada, nao o filtro.

```
PA_SIGNAL_DIR = 1  -> BUY (Preço > EMA20)
PA_SIGNAL_DIR = -1 -> SELL (Preço < EMA20)
```

Filtros (ex: `PA_REV_RSI != 0`) apenas selecionam o candle. A direcao vem do sinal configurado (`--signal=1` para BUY, `--signal=-1` para SELL).

### B. Grid Search (F1 Fast Screener)

O F1 usa `engines/f1_fast_screener.py` (avaliação vetorizada, ~200K combos/segundo).

**Carregamento de Dados:** Feito uma unica vez no `load_data_once()`. Usa `super_win_IS.parquet` + `super_win_OOS.parquet` (modo split) ou `super_win_continuous.parquet` (modo legado unificado).

### C. Modelo de Custo (WIN)

**CUSTO = 30 pts por trade** (custo simulado no F1, calculado do spread real no F2/F3/OOS).

Nao confundir com WDO (1.2 pts). WIN tem custo maior devido a maior volatilidade e spread.

---

## 4. Arquitetura V6.6 — Pipeline de Otimizacao

O pipeline atual e baseado em sinais (nao em robos multi-modo):

```
FASE 0: Signal Discovery (signal_discovery.py)
   -> Gera 3 rankings F1: Trend, Range, Hybrid

FASE 1: F1 Screening (f1_fast_screener.py)
   -> 5,400 combos (TP x SL x ATR_MIN x ATR_MAX)
   -> Sem guardrails, last prices sampleados, custo=30

FASE 2: F2 Validation (BacktestEngine IS)
   -> Top 10 do F1 com ticks reais
   -> Com BE/HP/CD basicos

FASE 3: F3 Search (BacktestEngine IS)
   -> Top 3 do F2
   -> Validacao mais rigorosa

FASE 4: Guardrail Sweep
   -> 45 combos (BE x HP x CD)
   -> Scoring: Sharpe Ratio x Net PnL

FASE 5: OOS (Out-of-Sample)
   -> Dados nunca vistos (Abril 2026)
   -> Ticks bid/ask reais

FASE 6: DNA Analysis (dna_analysis.py)
   -> 5 estagios: metadata, segmentacao, indicadores, hipoteses

FASE 7: Cycle Memory (cycle_memory.py)
   -> Persistencia per-signal, deteccao de spinning

FASE 8: Ensemble (se 2+ sinais validados)
   -> Modo SELECTOR (nao consenso)
   -> Prioriza por PnL historico
```

**Robos nao sao mais usados.** O foco e otimizacao de sinais PA_ com regime-aware filtering.

---

## 5. Checklist de Verificacao (Anti-Erro)

- [ ] Criou/Atualizou o cycle_plan.md antes de rodar?
- [ ] Os arquivos de dados estao em `data/` (copiados de `data/win_deploy/`)?
- [ ] O custo de 30 pts esta incluido no calculo do PnL Liquido?
- [ ] O relatorio segmenta por hora e dia da semana (Sempre OOS)?
- [ ] O Win Rate OOS e superior a 35% com trades > 10?
- [ ] Verificou se o melhor resultado do F1/F2 esta na BORDA do grid?
- [ ] Aplicou GridAdvisor para decidir zoom/expand/stop?

---

## 6. Liçoes Aprendidas Consolidadas (V6.6)

**Overfiltering:** Filtros de regime muito rigidos matam o trade count (ex: ER>0.6 + ADX>30 = apenas 3 trades).

**Short-side:** SELL-only historicamente teve melhor performance no WIN (+91K OOS, 63.9% WR em ciclos anteriores), mas no periodo atual (Abril 2026) BUY trend-following funcionou melhor.

**HSTAG:** Em baixa volatilidade (Abril), o HSTAG e responsavel por quase 100% das saidas. TP curto (1.0-2.0) funciona melhor que TP longo.

**Regime Importa:** Sinais de TREND funcionam em TREND. Sinais de RANGE funcionam em RANGE. Nao force um sinal de reversao em um mercado trending (e vice-versa).

**HYBRID nao e RANGE:** HYBRID usa TODOS os dados (sem filtro de regime), nao e a mesma coisa que RANGE. Isso foi um bug corrigido na V6.6.

**Grid Borda:** 69% das estrategias tem melhor resultado com SL=5.0 (borda do grid). SL precisa de valores > 5.0. 66% tem ATR_MAX=400 (minimo). ATR_MAX precisa comecar em 100.

---

## 7. WIN F1 — Regras que EU SEMPRE ESQUECO (NAO ESQUECER)

- **F1 NAO TEM guardrails:** sem BE, Grace Period, Circuit Breaker, Slope Decay, cooldown, filtro de hora
- **F1 usa APENAS high/low das candles** (OHLC), NAO tick samples (15/candle foi removido)
- **F1 tem custo simulado de 30 pts**, nao calculado do spread
- **F1 NAO filtra hora** — filtro de hora e guardrail EXTERNO
- **F1-Exact = F2** (correlacao +0.998) — use F1-Exact como pre-filtro confiavel
- **F1-Single gera 2-28x mais trades que F2** — NUNCA usar para rankeamento (apenas exploracao)
- **F1 serve APENAS como pre-filtro**, NUNCA confiar no PnL absoluto
- **F3 ≈ F2** (correlacao +0.987) quando SEM guardrails e com filtro inline de ticks
- **F3 com guardrails eh diferente por design** — NAO comparar PnL absoluto com F1/F2
- **Ticks da plataforma tem problemas:** ~0.001% com preco 0, ~0.001% absurdos (>200K). Filtro INLINE obrigatorio.
- **~12% das candles sem tick do high/low real** — fallback para candle OHLC essencial
- **NAO pre-processar ticks externos** — quebra `_build_tick_index`, use filtro inline
- **Fluxo correto:** F1-Exact (pre-filtro ~50K combos/s) → F2 (validacao top 10, SEM GR) → F3 (OOS top 3, COM GR) → Deploy

---

## 8. Changelog

| Versao | Data | Mudancas |
|--------|------|----------|
| V6.9 | 2026-05-05 | F3: Filtro inline de ticks invalidos (<=0, absurdos) + fallback high/low. F2 vs F3 correlacao +0.987 (SEM GR). Ticks originais, NAO pre-processados. |
| V6.8 | 2026-05-05 | F3 corrigido: TP usa tick real (bid/ask), nao threshold fixo. Corrigido em _simulate_exit_v119 e _simulate_exit_ohlc. |
| V6.7 | 2026-05-05 | F1 refatorado para OHLC-based (sem tick samples). Correlacao +0.431 com F2. f1_binario_deprecated.py backup. |
| V6.6 | 2026-05-02 | Removido WDO, foco WIN. Custo=30. Pipeline V6.6. Adicionado GridAdvisor, Signal Discovery, Cycle Memory per-signal. |
| V6.3 | 2026-04-15 | Multi-robo (Sniper/PTAX/IB), custo=1.2 (WDO). |
| V5.1 | 2026-04-01 | Pipeline basico F1→F2→F3, 17 estrategias. |
