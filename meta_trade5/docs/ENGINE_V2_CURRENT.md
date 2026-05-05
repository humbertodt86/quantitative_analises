# Engine V2 — Documentacao Tecnica
## Versao V139+ (Atualizado: 2026-05-02)

**Documento anterior:** `ENGINE_V2_DOCUMENTATION.md` (V134, desatualizado)

---

## Visao Geral

O **Engine V2** (`backtest/engine_v2.py`) e a arquitetura atual de backtesting:
- Indicadores pre-calculados em Parquet (performance ~18x melhor)
- Configuracao via JSON/dict (sem hardcoding)
- Simulacao tick-level precisa com bid/ask real
- **4 Layers**: Base -> Ensemble Voting -> Day Filter -> Risk Manager
- Suporte a multi-signal com modo SELECTOR

---

## Arquitetura em 4 Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                    BacktestEngine V139+                          │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 1: BASE (V134)                                           │
│    - load_indicators()  → DataFrame com indicadores pre-calc    │
│    - load_ticks()       → Ticks para simulacao tick-level       │
│    - load_config_dict() → Configuracao dos modos (JSON/dict)    │
│    - simulate()         → Executa simulacao completa            │
│    - calculate_metrics() → Calcula metricas de performance      │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 2: ENSEMBLE VOTING (V6.3+)                               │
│    - Coleta votos de TODOS os modos habilitados                 │
│    - Soma ponderada: vote_sum = Σ(signal_dir * weight)          │
│    - Normaliza: vote_norm = vote_sum / total_weight             │
│    - Threshold: abs(vote_norm) >= ensemble_threshold            │
│    - Min votes: len(voting_modes) >= ensemble_min_votes         │
│    - Modo SELECTOR: escolhe melhor modo em vez de consenso       │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 3: DAY OF WEEK FILTER (V6.3+)                            │
│    - Filtro: day_of_week: {"exclude": [5]}  # sem sexta         │
│    - Valores: 0=Seg, 1=Ter, ..., 4=Sex, 5=Sab, 6=Dom           │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 4: RISK MANAGER (V6.3+)                                  │
│    - daily_stop: max perda diaria antes de parar                 │
│    - consecutive_sl_limit: SLs antes do circuit breaker          │
│    - consecutive_sl_cooldown: candles extras apos circuit        │
│    - Circuit Breaker: 5 SLs consecutivos no mesmo dia            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Dados

### Parquet de Indicadores

**Localizacao:** `data/super_win_continuous.parquet`

**Colunas principais (154 total):**

| Coluna | Descricao |
|--------|-----------|
| `dt` | Datetime da barra M5 |
| `open`, `high`, `low`, `close` | OHLC |
| `ATR` | Average True Range |
| `ADX7`, `ADX14`, `ADX20`, `ADX30` | ADX multi-periodo |
| `EMA5_SLOPE` | Inclinacao EMA5 |
| `efficiency_ratio` | ER (Efficiency Ratio) de Kaufman |
| `regime_label` | 1=trend, 0=range |
| `PA_SIGNAL_DIR` | Direcao: 1 (compra), -1 (venda), 0 (sem sinal) |
| `PA_SIGNAL_REV` | Reverso de PA_SIGNAL_DIR |
| `PA_STRONG_TREND_A25_S20` | Trend following com ADX>=25 |
| `PA_REV_RSI_B15` | Reversao em RSI |
| `PA_VWAP_Z_Z2_0` | Sinal de VWAP Z-score |
| `PA_LIQ_GRAB` | Liquidity grab |
| `PA_MFI_B20` | Money Flow Index |
| `PA_TSI_T25` | True Strength Index |
| `Book_Imbalance`, `CVD` | Microestrutura |
| `hour`, `minute` | Hora e minuto |

### Periodos

| Periodo | Data | Uso |
|---------|------|-----|
| IS (treino) | 02 Jan - 27 Mar | Fast-screener (F1), F2/F3 search |
| OOS (validacao) | 30 Mar - 29 Abr | Validacao final com ticks bid/ask |

### Ticks

- IS: `data/WIN_merged_all.parquet` (last prices, bid=ask=last)
- OOS: `data/ticks/WIN*.parquet` (bid/ask real, por dia)

---

## Configuracao dos Modos

```python
config = {
    'name': 'MinhaEstrategia',
    'hour_min': 0.0,
    'hour_max': 24.0,
    'modo_busca': False,  # True = sem guardrails (proibido no F3)
    'ensemble_threshold': 0.5,  # 0-1, apenas para ensemble
    'ensemble_min_votes': 1,    # minimo de modos que devem concordar
    'risk_manager': {
        'daily_stop': -5000,
        'consecutive_sl_limit': 5,
        'consecutive_sl_cooldown': 0
    },
    'modes': {
        'M': {
            'enabled': True,
            'priority': 1,
            'signal_field': 'PA_SIGNAL_DIR',
            'tp_mult': 3.0,
            'sl_mult': 1.0,
            'min_sl': 50,
            'max_sl': 500,
            'filters': {
                'ATR': {'min': 100, 'max': 400},
                'PA_SIGNAL_DIR': {'eq': 1},
                'regime_label': {'eq': 1},  # 1=trend, 0=range
            },
            'behp': {
                'be_trigger': 200,
                'be_offset': 25,
                'hp_candles': 2,
                'hp_th': 0.15,
                'tp30_pct': 0.30,
                'grace_candles': 2,
                'hard_stop': 500,
                'cooldown_candles': 1,
                'slope_decay': 0.50
            }
        }
    }
}
```

### Filtros Disponiveis

| Filtro | Descricao | Exemplo |
|--------|-----------|---------|
| `{'min': N}` | Valor >= N | `{'ATR': {'min': 100}}` |
| `{'max': N}` | Valor <= N | `{'ATR': {'max': 400}}` |
| `{'eq': N}` | Valor == N | `{'PA_SIGNAL_DIR': {'eq': 1}}` |
| `{'neq': N}` | Valor != N | `{'PA_SIGNAL_DIR': {'neq': 0}}` |
| `{'gt': N}` | Valor > N | `{'EMA5_SLOPE': {'gt': 0}}` |
| `{'lt': N}` | Valor < N | `{'RSI': {'lt': 30}}` |
| `{'exclude': [N1, N2]}` | Valor nao esta na lista | `{'hour': {'exclude': [9, 15]}}` |
| `{'in': [N1, N2]}` | Valor esta na lista | `{'day_of_week': {'in': [1, 2, 3]}}` |

### Guardrails (behp)

| Parametro | Descricao | Valor Tipico |
|-----------|-----------|--------------|
| `be_trigger` | Pontos para acionar break-even | 100-500 |
| `be_offset` | Offset do BE em pontos | 25 |
| `hp_candles` | Candles de hold-profit | 1-3 |
| `hp_th` | Threshold de hold-profit | 0.15 |
| `tp30_pct` | % do TP para acionar TP30 | 0.30 |
| `grace_candles` | Candles de graca apos TP30 | 2 |
| `hard_stop` | SL maximo absoluto | 500 |
| `cooldown_candles` | Candles de espera apos SL | 0-2 |
| `slope_decay` | Decaimento de slope para BE | 0.50 |

---

## Layer 2: Ensemble Voting

### Modo Consenso (Antigo)

```python
# Todos os modos votam, media ponderada deve passar threshold
voting_modes = []  # modos que passaram filtros
vote_sum = sum(s_dir * weight for _, _, s_dir in voting_modes)
vote_norm = vote_sum / total_weight

if abs(vote_norm) < threshold:
    continue  # Consenso fraco -> nao entra
if len(voting_modes) < min_votes:
    continue  # Poucos votos -> nao entra
```

### Modo SELECTOR (Novo V6.6)

```python
# Se 1 modo quer entrar -> entra
# Se multiplos querem -> escolhe o de maior peso/PnL
if len(voting_modes) == 1:
    mode = voting_modes[0]
elif len(voting_modes) > 1:
    mode = max(voting_modes, key=lambda m: m.weight)
```

### Configuracao de Ensemble

```python
config = {
    'ensemble_threshold': 0.0,  # 0 = qualquer sinal dispara
    'ensemble_min_votes': 1,     # 1 = modo selector
    'modes': {
        'PA_LIQ_GRAB': {'enabled': True, 'weight': 2.0, ...},
        'PA_TSI_T25': {'enabled': True, 'weight': 1.82, ...},
    }
}
```

---

## Layer 4: Risk Manager

```python
'risk_manager': {
    'daily_stop': -5000,          # Parar se perder > 5000 no dia
    'consecutive_sl_limit': 5,    # Circuit breaker apos 5 SLs
    'consecutive_sl_cooldown': 0  # Candles extras apos circuit
}
```

---

## Uso Basico

```python
from backtest.engine_v2 import BacktestEngine

# Criar engine (1x por periodo!)
engine = BacktestEngine(None)
engine.df = df_is
engine.load_ticks_for_simulation(ticks_is)

# Carregar configuracao
engine.load_config_dict(config)

# Executar simulacao
results = engine.simulate()

# Calcular metricas
metrics = engine.calculate_metrics(results)
print(f"Trades: {metrics['n']}, PnL: {metrics['pnl']}, WR: {metrics['wr']:.1%}")

# Trocar config sem recriar engine
config2 = dict(config)
config2['modes']['M']['tp_mult'] = 5.0
engine.load_config_dict(config2)  # 1ms, nao recarrega ticks!
results2 = engine.simulate()
```

---

## Performance

| Metrica | Valor |
|---------|-------|
| Tempo de execucao (tick-level) | ~2s por estrategia |
| Grid search F1 | 200K combos/s (vetorizado) |
| Engine unico | Deve ser criado 1x por periodo |
| load_config_dict() | ~1ms |
| load_ticks_for_simulation() | ~15-30s (nao repetir!) |

---

## Changelog do Engine

| Versao | Mudancas |
|--------|----------|
| V139+ | 4 Layers (Base, Ensemble, Day Filter, Risk Manager), TP30, Grace Period, Slope Decay, Circuit Breaker |
| V136 | S/R Buffers, Daily PnL tracking |
| V134 | Baseline com SNIPER/HUNTER/SCALPER |
| V130 | Engine original (V129/V130) |

---

## Referencias

| Documento | Versao | Conteudo |
|-----------|--------|----------|
| `ENGINE_V2_DOCUMENTATION.md` | V134 | **DESATUALIZADO** — usar este documento |
| `ENGINE_V2_TECHNICAL_REFERENCE.md` | WDO | Legado WDO |
| `AGENTS.md` | V6.6 | Regras de operacao |
| `GUIA_CICLOS_V66.md` | V6.6 | Pipeline de ciclos |
