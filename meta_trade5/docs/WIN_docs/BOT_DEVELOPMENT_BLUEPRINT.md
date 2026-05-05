# BLUEPRINT: Framework de Desenvolvimento de Bots de Trading
**Foco**: WIN → WDO / Novos Ativos
**Metodologia**: Matriz de Convicção + Guardrails Cirúrgicos + Microestrutura

---

## INTRODUÇÃO

Este blueprint documenta o processo de desenvolvimento do bot V139 para WIN, servindo como guia para implementar bots em outros ativos. O processo combina **backtest histórico**, **análise de guardrails**, **tape reading**, **book imbalance** e **deploy com telemetria**.

### Princípios Fundamentais

1. **Qualidade do Movimento > Quantidade de Filtros**: Over-filtering mata o lucro. Cada guardrail deve justificar sua existência com dados.
2. **Seletividade Assimétrica**: Não trate todos os modos igualmente — cada um tem dinâmica própria.
3. **Ceticismo sobre Backtest**: Simulação tick-a-tick é mais realista que candle-close. Resultados de backtest são "mentirosos" por natureza.
4. **Custos são Reais**: Defina slippage e corretagem real ANTES de começar a otimização.
5. **Microestrutura é Alpha**: Tape reading e book imbalance capturam informação que candles perdem.

---

## ARQUITETURA DO SISTEMA

### 1. Arquitetura Multi-Estratégia (3 Pilares)

O sistema não é uma estratégia única, mas **três estratégias complementares** que operam em condições diferentes de mercado.

```
┌─────────────────────────────────────────────────────────────┐
│                    MATRIZ DE CONVICÇÃO                       │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   HUNTER     │  │    SNIPER     │  │   SCALPER    │     │
│  │              │  │              │  │              │     │
│  │ Tendência    │  │ Exaustão/    │  │ Giro Rápido  │     │
│  │ Confirmada   │  │ Ignição       │  │ em Range     │     │
│  │              │  │              │  │              │     │
│  │ ADX≥30      │  │ ADX≥20       │  │ ADX≥25       │     │
│  │ Slope≥40    │  │ Slope≥25     │  │ Slope≥15    │     │
│  │ GK≥1.4      │  │ GK≥1.0       │  │ GK≥1.0       │     │
│  │              │  │              │  │              │     │
│  │ TP: 2.0x   │  │ TP: 3.5x    │  │ TP: 1.2x   │     │
│  │ SL: 1.0x   │  │ SL: 1.11x   │  │ SL: 0.8x  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                              │
│  Mercado:           Range/Lateral      Tendência Forte       │
│  Favorável:         Scalper            Hunter                 │
│  Transição:         Sniper             (ambos adaptam)      │
└─────────────────────────────────────────────────────────────┘
```

#### 1.1 HUNTER — Tendência Pura

| Característica | Valor |
|---------------|-------|
| **Velocidade** | Lenta (confirmação requer mais sinais) |
| **Win Rate** | ~48% (mais winners, menos frequentes) |
| **Avg Win** | Alto (~400 pts) |
| **Avg Loss** | Moderado (~200 pts) |
| **Melhor Condição** | Tendência forte, ATR alto |
| **Pior Condição** | Mercado lateral, ATR baixo |

#### 1.2 SNIPER — Exaustão / Ignição

| Característica | Valor |
|---------------|-------|
| **Velocidade** | Rápida (entra em exaustão) |
| **Win Rate** | ~53% (maior WR, menos trades) |
| **Avg Win** | Muito Alto (~628 pts) |
| **Avg Loss** | Baixo (~111 pts) |
| **Melhor Condição** | Range definido, GK 0.9-1.3 |
| **Pior Condição** | Tendência forte, ATR fora do range |

#### 1.3 SCALPER — Giro Rápido

| Característica | Valor |
|---------------|-------|
| **Velocidade** | Muito Rápida |
| **Win Rate** | ~41% |
| **Avg Win** | Baixo (~42 pts) |
| **Avg Loss** | Baixo (~60 pts) |
| **Melhor Condição** | 10h ONLY, liquidez alta |
| **Pior Condição** | Volatilidade baixa, horário ruim |

---

## GESTÃO DE RISCO

### 2. Break-Even (BE)

O BE é acionado quando o trade está em profit suficiente.

**Trigger**: Profit >= 1.0x ATR

**Triggers de BE**:

| Trigger | Condição | Prioridade |
|---------|----------|------------|
| **Slope Decay** | Slope atual < 50% do slope na entrada | Alta |
| **Grace Period** | 2 candles após TP30 ativado | Média |
| **Time-based** | M5 candles >= threshold | Baixa |

### 2.1 H-Progress — Gestão de Estagnação

Detecta quando um trade está "estagnado".

```python
PROGRESS_M5_CANDLES = 2
PROGRESS_THRESHOLD = 0.15  # 15% do alvo
PROGRESS_TP_PCT = 0.30    # mover TP para 30%
```

### 2.2 Circuit Breaker (CB)

**Trigger**: 5 SL consecutivos no mesmo dia

---

## SUPORTE E RESISTÊNCIA (S/R) BUFFERS

### 3. Lógica de S/R Buffers

S/R buffers permitem que TP/SL sejam definidos baseado na distância até resistência/suporte em vez de puramente ATR.

#### 3.1 Configuração Validada (V136-V139)

| Modo    | tp_sr_pct | sl_sr_pct | Buffer TP | Buffer SL |
|---------|-----------|-----------|-----------|-----------|
| SNIPER  | 0.3       | 0.3       | 90%       | 110%      |
| HUNTER  | 0.0       | 0.0       | -         | -         |
| SCALPER | 0.4       | 0.4       | 90%       | 110%      |

#### 3.2 Fórmula

```python
# TP baseado em S/R
tp_sr = int(round(dist_to_resistance * tp_buffer))
tp = int(round(tp_atr * (1 - tp_sr_pct) + tp_sr * tp_sr_pct))

# SL baseado em S/R
sl_sr = int(round(dist_to_support * sl_buffer))
sl = int(round(sl_atr * (1 - sl_sr_pct) + sl_sr * sl_sr_pct))
```

#### 3.3 Resultado Validado (V136e)

- **PnL**: +31,323 (+8.8% vs baseline)
- **MaxDD**: 500 (-36% vs baseline)
- **Win Rate**: 50.0%

---

## TAPE READING E BOOK IMBALANCE

### 4. Fundamento de Tape Reading (V137-V138)

Tape reading é a análise de **quem está negociando** observando o fluxo de ordens no book.

#### 4.1 Indicadores de Tape Reading

| Indicador | Descrição | Interpretação |
|-----------|-----------|---------------|
| `tape_net_delta` | Delta líquido (buy - sell) no tick | Positivo = pressão compradora |
| `tape_cum_delta` | Delta acumulado no candle | Confirma direção |
| `tape_tick_count` | Número de trades no candle | Volume proxy |
| `tape_vwd` | Volume-Weighted Delta | Delta ponderado por volume |
| `tape_absorption` | Taxa de absorção de volume | Absorção alta = acumulação |
| `tape_whale` | Detecção de ordem grande | Alerta de atividade institucional |
| `tape_score` | Score composto de tape | + = bullish, - = bearish |

#### 4.2 Cálculo

```python
# Delta por tick
tick_delta = 1 if last > prev else -1  # assumption: trade at ask = buy
if volume > whale_threshold:
    tape_whale = True

# Dwell Time (concentração)
dwell = tick_count * avg_tick_duration
```

#### 4.3 Uso em Entrada

**Achado V138**: Tape reading cumulativo **NÃO** bloqueia entries porque o delta cumulativo nunca é negativo no momento de entrada.

**Uso recomendado**: Apenas para logging e análise, não como filtro.

---

### 5. Book Imbalance e Concentration Zones (V138)

Book imbalance é a análise de **onde** o volume está concentrado no book de ofertas.

#### 5.1 Indicadores de Concentração

| Indicador | Descrição | Interpretação |
|-----------|-----------|---------------|
| `conc_at_price` | Concentração no nível do preço | Winners têm conc_at_price maior |
| `dwell_at_price` | Tempo no nível do preço | Winners passam mais tempo |
| `conc_below` | Concentração abaixo do preço | Suporte |
| `conc_above` | Concentração acima do preço | Resistência |
| `book_imbalance` | Categoria do imbalance | STRONG_BELOW, STRONG_ABOVE, etc |

#### 5.2 Categorias de Book Imbalance

| Categoria | Trades | Win Rate | Avg PnL | Interpretação |
|-----------|--------|----------|---------|---------------|
| **LONG_STRONG_BELOW** | 59 | 61.0% | +297 | BUY + suporte abaixo = 61% WR |
| **SHORT_STRONG_ABOVE** | 42 | 69.0% | +228 | SELL + resistência acima = 69% WR |
| LONG_STRONG_ABOVE | 19 | 15.8% | +20 | BUY + resistência acima = 16% WR |
| SHORT_STRONG_BELOW | 19 | 31.6% | +56 | SELL + suporte abaixo = 32% WR |

#### 5.3 Dicas de Performance - Book Imbalance

1. **PREFERIR**: LONG quando concentração está ABAIXO do preço (suporte)
2. **PREFERIR**: SHORT quando concentração está ACIMA do preço (resistência)
3. **EVITAR**: Entries quando whale presente E imbalance desfavorável
4. **WARNING**: Unfavorable + Whale = WR 5.9%, PnL -171 (quase perda total)

```python
def check_book_imbalance_warning(row, signal):
    book_imb = str(row.get("book_imbalance", ""))
    has_whale = bool(row.get("tape_whale", 0))

    if signal == "BUY":
        if "STRONG_BELOW" in book_imb:
            return "FAVORABLE"
        elif "STRONG_ABOVE" in book_imb:
            return "UNFAVORABLE"
    elif signal == "SELL":
        if "STRONG_ABOVE" in book_imb:
            return "FAVORABLE"
        elif "STRONG_BELOW" in book_imb:
            return "UNFAVORABLE"
    return "NEUTRAL"
```

---

### 6. Concentration Zones como Suporte/Resistência

#### 6.1 Níveis de Concentração

```python
conc_levels = [25, 50, 75, 100, 150, 200]
# Nível indica "dwell time" acumulado no nível
```

#### 6.2 Interpretação

- **High conc_at_price**: Preço está em nível de acumulação
- **High conc_below**: Suporte forte
- **High conc_above**: Resistência forte
- **Winners** têm mais concentração abaixo na entrada

#### 6.3 Métricas Vencedoras vs Perdedores

| Métrica | Winners | Losers | Edge |
|---------|---------|--------|------|
| conc_at_price | 0.84 | 0.55 | WINNER |
| dwell_at_price | 1,902,740 | 1,235,271 | WINNER |
| conc_below | 25.0 | 12.1 | WINNER |

---

## DICAS DE PERFORMANCE (V138 Research)

### 7. Regras de Ouro Aprendidas

#### 7.1 Position Sizing - NÃO IMPLEMENTAR

**Achado**: Position sizing melhoraria PnL em +33.5%, MAS:

| Problema | Impacto |
|----------|---------|
| Imprevisibilidade estatística | Não sabemos expectancy por trade |
| Mudança de perfil | Variância aumenta |
| Complexidade | Gera overfitting |

**Decisão**: Manter **lote fixo** = previsibilidade estatística.

#### 7.2 Book Imbalance como Soft Preference

| Uso | Como |
|-----|------|
| **Filtro de entrada** | PREFERIR entries quando edge_type=FAVORABLE |
| **Aviso de risco** | ALERTA quando unfavorable + whale |
| **Confirmação de saída** | Se concentração muda de lado, considerar saída |

#### 7.3 Whale como Amplificador de Risco

| Condição | WR | PnL | Ação |
|----------|-----|-----|------|
| Unfavorable + No Whale | 38.1% | +1,622 | Normal |
| Unfavorable + Has Whale | 5.9% | -171 | Reduzir exposição |

#### 7.4 S/R Buffer como Melhoria

| Config | PnL | MaxDD | WR |
|--------|------|-------|-----|
| Baseline (sem S/R) | 28,789 | 780 | 47.5% |
| S/R 90%/110% | 31,323 | 500 | 50.0% |
| **Melhoria** | **+8.8%** | **-36%** | **+2.5%** |

---

## GUARDRAILS - CAMADA DE FILTRO

### 8. Dimensões de Guardrails

| Dimensão | Indicadores | O que filtra |
|----------|------------|--------------|
| **Volatilidade** | ATR, GK Ratio | Mercados muito calmos ou muito agitados |
| **Direção** | Slope, Ribbon, ADX | Sinais contra a tendência predominante |
| **Tempo** | Hour, Minute, Day of Week | Horários com dinâmica institucional diferente |
| **Movimento** | ER, RVol, ADX Slope | Movimentos sem força/volume |
| **Estrutura** | VWAP distance, Z-Score | Preço longe da referência |
| **Behavioral** | SL Consecutivos, Circuit Breaker | Condições anormais de mercado |
| **Microestrutura** | Book Imbalance, Whale | Condições de liquidity |

### 8.1 Tabela Completa de Guardrails

| Guardrail | Tipo | Modo | Condição |
|-----------|------|------|----------|
| ATR Min | Volatilidade | ALL | ATR >= 200 |
| ATR Max | Volatilidade | ALL | ATR <= 800 |
| ADX Max | Volatilidade | ALL | ADX <= 61 |
| Circuit Breaker | Behavioral | ALL | sl_consec < 5 |
| Cooldown | Behavioral | ALL | time > cooldown |
| ADX Slope | Movimento | STRONG | adx_delta > 0.5 |
| ATR Range | Volatilidade | SNIPER | ATR 200-800 |
| GK Ratio | Volatilidade | SNIPER | 0.9 <= GK <= 1.3 |
| Hour Block | Tempo | ALL | 9:30 <= hour < 17:30 |

### 8.2 Guardrails de Horário (Detalhado)

| Horário | Comportamento | Guardrail |
|---------|---------------|-----------|
| 9:00-9:30 | Abertura: gaps, ordens institucionais | Block, permitir HUNTER |
| 10:00 | Pico de liquidez, melhor slippage | SCALPER Only |
| 10:00-11:00 | Golden Hour | Risk mult 1.5x |
| 10:00-11:00 | Tendência da manhã | HUNTER ideal |
| 12:00-14:00 | "Ressaca": volume baixo | Exigir filtro adicional |
| 17:30+ | After-hours | Bloqueio total |

---

## PROCESSO DE OTIMIZAÇÃO

### 9. Ciclo de Desenvolvimento

```
┌─────────────────────────────────────────────────────────────────┐
│                    CICLO DE OTIMIZAÇÃO                            │
│                                                                  │
│    ┌──────────┐    ┌──────────┐    ┌──────────┐               │
│    │  ANÁLISE │───▶│ HIPÓTESES│───▶│  TESTE   │               │
│    │  (O QUE  │    │ (O QUE   │    │ (RODAR   │               │
│    │   ACONTECEU)   │   MUDAR)  │    │  BACKTEST)  │
│    └──────────┘    └──────────┘    └──────────┘               │
│         ▲                                    │                   │
│         │                                    ▼                   │
│         │                            ┌──────────────┐            │
│         │                            │   RESULTADO  │            │
│         │                            │ (VALIDOU OU  │            │
│         │                            │   REJEITOU)  │            │
│         │                            └──────────────┘            │
│         │                                    │                   │
│         └────────────────────────────────────┘                   │
│                    PRÓXIMO CICLO                                │
└─────────────────────────────────────────────────────────────────┘
```

### 10. Validação com Monte Carlo (V138g)

Após otimização, validar com 1000 simulações Monte Carlo:

```python
results = []
for i in range(1000):
    sim_trades = np.random.choice(trade_pnls, size=len(trade_pnls), replace=True)
    sim_pnl = sim_trades.sum()
    results.append(sim_pnl)

results = np.array(results)
ci_95 = np.percentile(results, [2.5, 97.5])
```

**Critério**: 95% das simulações devem ser positivas.

---

## ARQUITETURA: ROBÔ BASEADO EM MOVIMENTO E MICROESTRUTURA

### 11. Fundamento: Movimento + Microestrutura

O robô **não é baseado em guardrails**. Guardrails são uma **camada de filtro**.

O fundamento é **entender como o preço se move** e **operar na direção do movimento institucional**.

#### 11.1 O Que Significa "Movimento"

- **Slope**: Velocidade da EMA (inércia)
- **ADX**: Força da tendência
- **Ribbon**: Alinhamento de médias (confirmação)

#### 11.2 O Que Significa "Microestrutura"

- Range vs Tendência (GK Ratio)
- Participação institucional (RVol, Whale)
- Eficiência do movimento (ER)
- Distância do preço à média (VWAP)
- Concentração de volume (Book Imbalance)

---

## WALK-FORWARD VALIDATION

### 12. Validação Walk-Forward

Dividir dados em períodos e validar performance em cada:

| Período | Trades | PnL | WR | Validado |
|---------|--------|-----|-----|----------|
| H1 2025 | 81 | +12,847 | 48.1% | ✓ |
| H2 2025 | 81 | +18,476 | 51.9% | ✓ |

**Critério**: Ambos os períodos devem ser positivos.

---

## ARQUITETURA DE ARQUIVOS E GRID SEARCH

### 12. Estrutura de Diretórios

```
backtest/
├── engine_v2.py              # Engine principal - executa backtest dado config
├── engine_v119_v2.py        # Simulação de exit tick-level
├── config.py                 # Configuração de instrumentos
├── data_loader.py            # Loader de dados CSV
├── data_loader_parquet.py    # Loader de dados Parquet
├── indicators.py             # Cálculo de indicadores
├── grid_search.py            # Paralelização multiprocessing
├── strategies/
│   ├── base.py               # Classe base de estratégia
│   └── v100_ga.py           # Estratégia V100
└── run_*.py                  # Scripts de execução (grid, teste, validação)

bot/
└── bot_mt5_v139.py           # Bot para MT5/Command Center

configs/
└── v134_default.json         # Configuração padrão

data/
├── indicators/               # Indicadores pré-calculados (.parquet)
│   └── indicators_jan2026_v138.parquet
└── raw/ticks/               # Ticks raw
    └── WIN_merged_all.parquet
```

### 12.1 Papel de Cada Arquivo

| Arquivo | Responsabilidade |
|---------|-----------------|
| `engine_v2.py` | **Executa** o backtest. Recebe config, retorna resultados. Não tem inteligência de o que testar. |
| `run_*.py` | **Define o que testar**. Parameter space, grid de combinações, execução. |
| `grid_search.py` | **Paraleliza** a execução usando multiprocessing. |
| `data_loader_parquet.py` | **Carrega** indicadores pré-calculados do Parquet. |

### 12.2 Fluxo de Execução

```
┌─────────────────────────────────────────────────────────────┐
│                    run_v136e_buffer_test.py                  │
│                                                              │
│  1. Define parameter space                                    │
│     tp_buffer: [0.85, 0.90, 0.95]                           │
│     sl_buffer: [1.05, 1.10, 1.15]                           │
│                                                              │
│  2. Gera todas combinações (9)                               │
│                                                              │
│  3. Para cada combinação:                                     │
│     cfg = get_cfg(tp_buffer=x, sl_buffer=y)                  │
│     engine = BacktestEngine(indicators_path)                 │
│     engine.load_indicators()                                 │
│     result = engine.run(cfg)                                 │
│     results.append(result)                                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       engine_v2.py                            │
│                                                              │
│  - Carrega indicadores do Parquet                            │
│  - Itera sobre candles                                       │
│  - Aplica filtros e guardrails                               │
│  - Calcula TP/SL baseado na config                           │
│  - Simula exit (tick-level se disponível)                     │
│  - Retorna: n_trades, pnl, expectancy, win_rate, etc        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     results.json                             │
│                                                              │
│  [                                                           │
│    {"tp_buffer": 0.85, "sl_buffer": 1.05, "pnl": 28500, ...}│
│    {"tp_buffer": 0.85, "sl_buffer": 1.10, "pnl": 29100, ...}│
│    ...                                                       │
│  ]                                                           │
└─────────────────────────────────────────────────────────────┘
```

### 12.3 Exemplo de Script run_*.py

```python
# run_v136e_buffer_test.py
from backtest.engine_v2 import BacktestEngine, BacktestConfig, ModeConfig

def get_cfg(tp_buffer=0.90, sl_buffer=1.10):
    return BacktestConfig(
        name="V136e",
        modes={
            "SNIPER": ModeConfig(
                enabled=True,
                tp_sr_pct=0.3, sl_sr_pct=0.3,
                tp_buffer=tp_buffer, sl_buffer=sl_buffer,
            ),
            "HUNTER": ModeConfig(enabled=False),
            "SCALPER": ModeConfig(
                enabled=True,
                tp_sr_pct=0.4, sl_sr_pct=0.4,
                tp_buffer=tp_buffer, sl_buffer=sl_buffer,
            ),
        }
    )

# Grid search
results = []
for tp_buf in [0.85, 0.90, 0.95]:
    for sl_buf in [1.05, 1.10, 1.15]:
        cfg = get_cfg(tp_buffer=tp_buf, sl_buffer=sl_buf)
        engine = BacktestEngine("data/indicators/indicators_jan2026_v138.parquet")
        engine.load_indicators()
        result = engine.run(cfg)
        results.append({
            "tp_buffer": tp_buf,
            "sl_buffer": sl_buf,
            "pnl": result["total_pnl"],
            "wr": result["win_rate"],
            "n": result["total_trades"],
        })

# Ordenar por PnL
best = sorted(results, key=lambda x: x["pnl"], reverse=True)[0]
print(f"Best: {best}")
```

### 12.4 Grid Search Paralelo

```python
# grid_search.py
from multiprocessing import Pool, cpu_count

def run_single_config(args):
    cfg, indicators_path = args
    engine = BacktestEngine(indicators_path)
    engine.load_indicators()
    return engine.run(cfg)

# Execução paralela
with Pool(processes=cpu_count()) as pool:
    args = [(cfg, indicators_path) for cfg in all_configs]
    results = pool.map(run_single_config, args)
```

### 12.5 BacktestEngine.run()

```python
# engine_v2.py - método run()
def run(self, config: BacktestConfig) -> dict:
    self.config = config
    self._prepare_mode_filters()

    results = []
    for i, row in enumerate(self.records):
        if not self._check_guardrails(row):
            continue

        signal = self._detect_signal(row)
        if not signal:
            continue

        tp, sl = self._calc_tp_sl(row, config)
        pnl, hit_type = self._simulate_exit(signal, tp, sl)

        results.append({
            "mode": config.mode_assigned,
            "pnl": pnl,
            "hit": hit_type,
            ...
        })

    return self._aggregate_results(results)
```

### 12.6 Dados de Input

O engine espera um arquivo Parquet com colunas:

```
dt, open, high, low, close, volume,
ADX, ATR, EMA5_SLOPE, EMA20_SLOPE,
GK_RATIO, PA_SIGNAL_DIR, VWAP,
RIBBON_STATE, MA9, MA21, MA50,
dist_to_resistance, dist_to_support,
book_imbalance, tape_whale, tape_score,
conc_at_price, dwell_at_price, ...
```

Ver arquivo `data/indicators/indicators_jan2026_v138.parquet` para indicadores completos.

---

## LIÇÕES APRENDIDAS (V134-V138)

### O Que Funcionou

1. **S/R Buffers 90%/110%**: PnL +8.8%, MaxDD -36%
2. **Lote fixo**: Mantém previsibilidade estatística
3. **ATR floor 200**: Garante espaço para TP
4. **Circuit Breaker em 5**: Bloqueio após 5 losses
5. **Golden Hour 10h**: Risk mult 1.5x

### O Que NÃO Funcionou

1. **Position sizing**: +33.5% PnL mas imprevisível
2. **Tape reading como filtro**: Delta nunca negativo na entrada
3. **Over-filtering**: Mata volume e lucro

### Regras de Ouro

1. **Qualidade > Quantidade**: 30 trades bons > 200 ruins
2. **Lote fixo = Previsibilidade**: Não saber expectancy por trade é fatal
3. **Ceticismo**: Backtest é hint, não verdade
4. **Custos Reais**: Slippage e corretagem destroem sistemas marginalmente lucrativos
5. **Book Imbalance é Soft**: Preferência, não bloqueio

---

## DEPLOY DO BOT (V139)

### 13. Estrutura de Arquivos

```
bot_mt5_v139.py       # Bot principal
bot_status_v139.json  # Status file (Command Center)
logs/
  v139_YYYYMMDD.log           # Log de texto
  v139_telemetry_YYYYMMDD.jsonl  # Telemetria JSONL
```

### 13.1 Configuração

```python
VERSION = "v139.1"
MAGIC = 202702

# S/R Buffers
SNIPER_TP_SR_PCT = 0.3
HUNTER_TP_SR_PCT = 0.0
SCALPER_TP_SR_PCT = 0.4
TP_BUFFER = 0.90
SL_BUFFER = 1.10

# Guards
ATR_MIN = 200
ATR_MAX = 800
ADX_MAXIMO = 61.76
```

### 13.2 Telemetria

| Evento | Quando |
|--------|--------|
| `startup` | Inicialização |
| `candle_decision` | Cada candle M5 |
| `signal_eval` | Sinal avaliado |
| `order_filled` | Ordem executada |
| `order_reject` | Ordem rejeitada |
| `deal_exit` | Trade fechado |
| `heartbeat` | A cada 60s |

### 13.3 Indicadores Logados por Candle

```python
candle_decision = {
    "atr": 350.5,
    "adx": 25.3,
    "dist": +120,
    "book_imbalance": "STRONG_BELOW",
    "tape_whale": False,
    "edge_type": "FAVORABLE",
    "conc_at_price": 0.84,
    "tape_score": 1.2,
    ...
}
```

---

## CHECKLIST DE DEPLOY

### Pré-Deploy
- [ ] MAGIC = 202702
- [ ] VERSION = "v139.1"
- [ ] `mt5.order_send(req)` posicional (não nomeado)
- [ ] `"comment": f"..."[:31]` truncado
- [ ] Nenhuma posição aberta com magic 202702

### Pós-Deploy
- [ ] `version=v139.1 | magic=202702` no log
- [ ] Status file atualizando
- [ ] Telemetria gerando JSONL
- [ ] slippage < 5 pts
- [ ] order_latency < 100ms

---

## APÊNDICE: FÓRMULAS

### Efficiency Ratio (ER)
```
ER = abs(Preço[0] - Preço[n]) / Sum(abs(ΔPreço))
```

### Relative Volume (RVol)
```
RVol = Volume[0] / SMA(Volume, 20)
```

### Garman-Klass Ratio
```
GK = sqrt(0.5 * log(High/Low)^2 - (2*log(2)-1) * log(Close/Open)^2)
```

### ADX Slope
```
ADX_Slope = (ADX[0] - ADX[n]) / n
```

### Book Imbalance Detection
```python
# Concentration zone analysis
if conc_below > conc_above * 2:
    imbalance = "STRONG_BELOW"
elif conc_above > conc_below * 2:
    imbalance = "STRONG_ABOVE"
else:
    imbalance = "NEUTRAL"
```

---

## APÊNDICE: MODE DETECTION (V139)

```python
MODE_STATIONARY: ADX < 17.72
MODE_NORMAL: 17.72 <= ADX < 22.72
MODE_STRONG: ADX >= 22.72
```

## APÊNDICE: TP/SL MULTIPLIERS (V139)

| Mode | TP Mult | SL Mult | S/R % |
|------|---------|---------|--------|
| STATIONARY | 1.3 | 0.8 | 0% |
| NORMAL | 2.1 | 1.0 | 0-30% |
| STRONG | 2.76 | 1.12 | 0-40% |

---

*Documento criado em: 2026-04-28*
*Versão: 3.0*
*Baseado em: V139 WIN Bot com Book Imbalance e Concentration Zones*
*Research: V134, V136, V137, V138, V138g*