# WIN Backtest & Optimization Pipeline

Pipeline de otimizacao e backtest para WIN (Indice Bovespa) — F1 Hybrid V5 + Orchestrator V7.6.

**Versao atual:** V7.6.0 (2026-05-06)
**Foco:** WIN (custo 30 pts/trade), M5 candles

---

## Arquitetura do Pipeline

```
FASE 0: Signal Discovery     -> Ranking de sinais PA_ por regime
FASE 1: F1 Fast Screener     -> ~39K-55K combos/s (OHLC, sem guardrails)
FASE 2: F2 Validation (IS)   -> Tick-level IS, guardrails basicos (top 30 F1)
FASE 3: F3 Search (IS)       -> Validacao rigorosa (top 3 F2)
FASE 4: Guardrail Sweep      -> Grid BE/HP/CD (36 combos)
FASE 5: F3 OOS Final         -> Tick-level OOS, bid/ask reais (dados nunca vistos)
FASE 6: DNA Analysis         -> Analise trade a trade
```

---

## Estrutura do Projeto

```
meta_trade5/
├── scripts/
│   ├── orchestrator.py              # Orchestrator V7.6 — Autopilot de Ciclos
│   ├── run_signal_variants.py       # Batch execution para variantes
│   ├── grid_advisor.py              # GridAdvisor (ZOOM/EXPAND/STOP)
│   ├── signal_discovery.py          # F0: Signal Discovery
│   ├── f2_validate_signal_dir_variants.py  # F2 Validation standalone
│   ├── f3_guardgrid_signal_dir.py   # F3 Guardrail Grid
│   ├── dna_analysis_best_variant.py # F6: DNA Analysis
│   └── ... (demais scripts auxiliares)
├── engines/
│   ├── f1_binario_v4_hybrid.py      # F1 Hybrid V5 (~55K combos/s)
│   ├── f3_tick_ba.py                # F3 Tick-by-tick bid/ask
│   └── arquivados/                  # Engines legados
├── backtest/
│   ├── engine_v2.py                 # BacktestEngine IS (last prices)
│   └── engine_v119_v2.py            # BacktestEngine OOS (bid/ask real)
├── data/
│   └── win_deploy/                  # PACOTE DE DEPLOY — copiar para data/ na nova maquina
│       ├── super_win_IS.parquet     # Candles + indicadores + sinais (Jan-Mar 2026)
│       ├── super_win_OOS.parquet    # Candles + indicadores + sinais (Abr 2026)
│       ├── WIN_merged_all.parquet   # Ticks IS (last prices, Jan-Mar 2026)
│       ├── WIN_ticks_OOS_all.parquet# Ticks OOS (bid/ask real, Abr 2026)
│       └── _fev_cache_v2.npz        # Cache Fev pre-computado para F1 screening
│   # (outros arquivos de dados nao estao no Git — ver secao Dados)
├── docs/
│   ├── GUIA_DE_CICLOS.md           # Pipeline F0-F8 completo
│   ├── AGENTS.md                    # Regras operacionais e checklist
│   ├── cycle_plan.md                # Plano de voo do ciclo atual
│   ├── progress.md                  # Diario de bordo com resultados
│   └── WIN_docs/                    # Resultados, logs, relatorios
└── README.md                        # Este arquivo
```

---

## Como Rodar

### 1. Dependencias

```bash
pip install -r requirements.txt
```

Principais: `polars`, `numpy`, `scipy`, `pandas`, `pyarrow`

### 2. Dados Necessarios

Copie o conteudo de `data/win_deploy/` para `data/` na nova maquina:

```bash
# No ambiente de destino, apos clonar o repo
cp data/win_deploy/* data/
```

Isso coloca os 5 arquivos essenciais no lugar correto para o pipeline rodar.

### 3. Executar Ciclo Completo (1 variante)

```bash
python scripts/orchestrator.py --strategy=SIGNAL_DIR_SELL --col=PA_SIGNAL_DIR --signal=-1 --regime=trend --max-cycles=2
```

### 4. Executar Batch (multiplas variantes)

```bash
python scripts/run_signal_variants.py
```

Edite `VARIANTS` no script para escolher quais variantes rodar.

### 5. Signal Discovery (F0)

```bash
python scripts/signal_discovery.py
```

### 6. Validacao Rapida (grid curto, 1 variante)

Use este script para validar que o pipeline funciona em uma nova maquina ou depois de alteracoes no codigo.

```bash
python scripts/validate_pipeline.py
```

**O que faz:**
- Grid F1: 3x3x2x2 = 36 combos (vs 4,032 do pipeline completo)
- F2: top 5 do F1 (vs 30 do pipeline completo)
- Guardrail: 1 combo (vs 36 do pipeline completo)
- Total esperado: 90-180s (vs 2-5 min do pipeline completo)

**Output:**
- Tempos detalhados por fase
- Resultado OOS com trade count e WR
- Arquivo JSON em `docs/WIN_docs/validate_pipeline_result.json`

---

## Tutorial: Troubleshooting na Nova Maquina

### Erro: "ModuleNotFoundError: No module named 'engines.f1_binario_v4_hybrid'"

**Causa:** O arquivo `engines/f1_binario_v4_hybrid.py` nao esta no GitHub (foi adicionado no commit `14d1a8b`).

**Solucao:**
```bash
git pull origin master
# Verifique se o arquivo existe:
ls engines/f1_binario_v4_hybrid.py
```

### Erro: "FileNotFoundError: super_win_IS.parquet"

**Causa:** Arquivos de dados nao foram copiados para `data/`.

**Solucao:**
```bash
cp data/win_deploy/* data/
# Verifique:
ls data/super_win_IS.parquet
ls data/WIN_merged_all.parquet
ls data/WIN_ticks_OOS_all.parquet
```

### O F2 esta muito lento (minutos por variante)

**Normal.** O F2 roda simulacao tick-by-tick no BacktestEngine. Cada config leva ~2-5s. Com top 30 do F1, sao 30 configs = 60-150s. O guardrail sweep adiciona 36 combos = mais 72-180s.

**Para acelerar:**
1. Use `validate_pipeline.py` (grid curto, top 5)
2. Ou edite `N_TOP_F2` e `N_TOP_F3` no `scripts/orchestrator.py`
3. Ou use `run_signal_variants.py` em vez do autopilot (evita multiplos ciclos)

### Por que o F1 e rapido (~0.01s) mas o F2 e lento (~60s)?

| Fase | Motor | Tipo de Simulacao | Velocidade |
|------|-------|-------------------|------------|
| F1 | F1HybridEngine | OHLC puro (high/low) | ~39K combos/s |
| F2 | BacktestEngine | Tick-by-tick (last prices) | ~0.4 combos/s |
| F3 OOS | BacktestEngine | Tick-by-tick (bid/ask real) | ~0.5 combos/s |

O F1 e vetorizado (NumPy, multi-thread). O F2/F3 simula cada trade individualmente, verificando cada tick para TP/SL/BE/HP.

---

## Configuracao Atual do Orchestrator V7.6

### F1 Grid (Conservador)
- TP: [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 15.0, 20.0] (12 valores)
- SL: [0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0] (8 valores)
- ATR_MIN: [50, 100, 150, 200, 300, 400] (6 valores)
- ATR_MAX: [400, 600, 800, 1000, 1500, 2000, 9999] (7 valores)
- **Total: 4,032 combos por variante**

### Filtros F1
- SL floor >= 0.5x ATR (prevents micro-stop overfit)
- R:R cap <= 10 (prevents precision overfit)

### F2/F3 Config
- Custo: 30 pts/trade
- BE/HP/CD: fixos no F2, grid sweep no guardrail (BE=[100,200,300,999999], HP=[1,2,3], CD=[0,1,2])

---

## Periodos

| Periodo | Dados | Uso |
|---------|-------|-----|
| Jan-Mar 2026 | `super_win_IS.parquet` + `WIN_merged_all.parquet` | IS (In-Sample) |
| Fev 2026 | `super_win_IS.parquet` (subset) + `_fev_cache_v2.npz` | F1 Screening |
| 30/Mar-29/Abr 2026 | `super_win_OOS.parquet` + `WIN_ticks_OOS_all.parquet` | OOS (Out-of-Sample) |

---

## Arquivos de Dados

**Nenhum arquivo de dados esta no Git** (ignorados por `.gitignore`).

### Pacote de Deploy (`data/win_deploy/`)

Esta pasta contem **apenas os arquivos essenciais** para rodar o pipeline V7.6. Copie todo o conteudo para `data/` na nova maquina.

| Arquivo | Tamanho (~) | Descricao |
|---------|-------------|-----------|
| `super_win_IS.parquet` | 2.0 MB | Candles M5 + 317 indicadores/sinais (Jan-Mar 2026) |
| `super_win_OOS.parquet` | 0.8 MB | Candles M5 + 317 indicadores/sinais (Abr 2026) |
| `WIN_merged_all.parquet` | 545 MB | Ticks IS (last prices, Jan-Mar 2026) |
| `WIN_ticks_OOS_all.parquet` | 161 MB | Ticks OOS unificados (bid/ask real, Abr 2026) |
| `_fev_cache_v2.npz` | ~50 MB | Cache Fev pre-computado para F1 screening |

**Total do pacote: ~759 MB**

### Arquivos Legados (ainda suportados, mas nao no pacote deploy)

O orchestrator tambem suporta modo "unificado" (antigo):
- `super_win_continuous.parquet` — IS+OOS+Fev em um unico arquivo
- `data/ticks/WIN*_ticks_*.parquet` — Ticks OOS diarios (em vez do unificado)

Se esses arquivos existirem, o orchestrator os usa automaticamente. O modo split (`super_win_IS.parquet` + `super_win_OOS.parquet`) tem prioridade.

### Cache/Tmp (gerado automaticamente, nao precisa copiar)
| Arquivo | Tamanho (~) | Nota |
|---------|-------------|------|
| `data/_candle_vec_cache.pkl` | 6.8 GB | **NAO copiar** — gera automaticamente |
| `data/_cvec_*.pkl` | 3.2-6.8 GB | **NAO copiar** — cache temporario |

---

## Principais Resultados Recentes

### Ciclo 3 (2026-05-06) — Grid Conservador 4,032 combos + Filtros

| Variante | OOS Net | OOS N | OOS WR | Config |
|----------|---------|-------|--------|--------|
| SIGNAL_DIR_BASE | -2,050 | 66 | 42.4% | TP=1.5 SL=5.0 BE=off |
| SIGNAL_DIR_V2 | +1,350 | 4 | 50.0% | TP=2.5 SL=1.0 BE=100 |
| SIGNAL_DIR_DEPRECATED | -1,840 | 68 | 42.6% | TP=1.5 SL=5.0 BE=off |
| S5_Z30_R05 | -1,450 | 64 | 43.8% | TP=1.5 SL=5.0 BE=off |
| S10_Z30_R05 | -4,795 | 29 | 20.7% | TP=2.5 SL=0.5 BE=off |
| S20_Z30_R05 | -2,935 | 61 | 41.0% | TP=1.5 SL=5.0 BE=off |

**Conclusao:** Nenhuma variante de PA_SIGNAL_DIR SELL tem edge robusto no periodo Abr/2026. Melhor OOS: S5_Z30_R05 (-1,450).

---

## Documentacao

- [`docs/GUIA_DE_CICLOS.md`](docs/GUIA_DE_CICLOS.md) — Pipeline F0-F8 completo
- [`docs/AGENTS.md`](AGENTS.md) — Regras operacionais, checklist anti-erro
- [`docs/cycle_plan.md`](docs/cycle_plan.md) — Plano de voo do ciclo atual
- [`docs/progress.md`](docs/progress.md) — Diario de bordo com todos os resultados
- [`engines/README.md`](engines/README.md) — Documentacao dos motores F1/F2/F3

---

## Licoes Aprendidas

1. **F1-Exact = F2** (correlacao +0.998) — F1 serve como pre-filtro confiavel
2. **SL muito alto (>5.0x ATR) degrada OOS** — grid conservador e melhor
3. **BE desabilitado (999999) converge em 6/7 variantes** — BE esta matando performance
4. **Grid expandido (54K combos) nao melhorou OOS** vs grid 5K/4K
5. **Sinais SELL nao tem edge em Abr/2026** — testar BUY ou outros sinais PA_*

---

*Atualizado em 2026-05-06*
*Pipeline V7.6.0 — Orchestrator + F1Hybrid V5*
