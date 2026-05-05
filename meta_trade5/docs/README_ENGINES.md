# Documentacao dos Engines

**Versao:** V7.5.0
**Engine Principal:** `backtest/engine_v2.py`
**Engine Tick-Level:** `backtest/engine_v119_v2.py`

---

## Arquitetura

```
BacktestEngine v2
├── load_indicators()      -> Carrega parquet
├── load_config()          -> Carrega JSON
├── load_config_dict()     -> Carrega dict Python
├── load_ticks_for_simulation() -> Carrega ticks para OOS
├── simulate()             -> Loop principal
│   ├── _check_filters()   -> Filtros de entrada
│   ├── Ensemble Voting    -> Layer 2 (multi-modo)
│   ├── Calculo TP/SL      -> ATR-based + S/R Buffer
│   └── _simulate_exit_v119() -> Simulacao tick-level
└── Resultados             -> Lista de trades
```

---

## BacktestEngine v2

### Inicializacao

```python
from backtest.engine_v2 import BacktestEngine

eng = BacktestEngine('data/super_win_continuous.parquet')
eng.load_indicators()
eng.load_config('config.json')
# OU
eng.load_config_dict({...})
```

### Simulacao Basica

```python
trades = eng.simulate()
for t in trades:
    print(t['pnl'], t['hit_type'], t['mfe'], t['mae'])
```

---

## Filtros

Filtros sao definidos no `ModeConfig.filters`:

```python
'filters': {
    'ATR': {'min': 400, 'max': 600},
    'PA_SIGNAL_DIR': {'eq': -1},
    'regime_label': {'eq': 1},
    'BOOK_IMB': {'lt': -0.3},      # Book Imbalance < -0.3
    'VWAP_Z': {'min': 0.5},         # VWAP_Z >= 0.5
    'HOUR': {'min': 9.5, 'max': 12.0},
}
```

**Operadores suportados:**
- `min` / `max`: valor >= ou <=
- `eq` / `neq`: igual / diferente
- `gt` / `lt`: maior / menor (estrito)
- `exclude`: lista de valores excluidos
- `max_atr_mult` / `min_atr_mult`: dinamico baseado em ATR

---

## BE/HP/TP30 (Guardrails)

Definidos em `ModeConfig.behp`:

```python
'behp': {
    'be_trigger': 60,        # BE ativa apos 60 pts de lucro
    'be_offset': 50,         # SL move para entry ± 50 pts
    'hp_candles': 2,         # Hold Period = 2 candles
    'hp_th': 0.15,           # Threshold de progresso (15% do TP)
    'tp30_pct': 0.20,        # Reduz TP em 80% apos HP se prog < 15%
    'grace_candles': 2,      # Candles de graca apos TP30
    'cooldown_candles': 0,   # Cooldown apos loss
    'slope_decay': 0.50,     # Move SL para BE se slope cair 50%
    'trailing_pct': 0.0,     # Trailing stop (0% = desligado)
}
```

**Regras:**
1. **BE (Break-Even):** Quando profit >= be_trigger, move SL para entry ± be_offset
2. **HP (Hold Period):** Apos hp_candles, verifica se progrediu >= hp_th * tp_pts
3. **TP30:** Se nao progrediu suficiente apos HP, reduz TP para tp_pts * tp30_pct
4. **Grace:** Apos TP30, espera grace_candles antes de mover SL para BE
5. **Slope Decay:** Se EMA5_SLOPE < entry_slope * slope_decay_pct, move SL para BE
6. **Trailing Stop:** Apos BE ativar, move SL para lock in X% do MFE

---

## S/R Buffer (NOVO V7.5.0)

Ajusta TP/SL com base em suportes/resistencias (prev_10_high/low):

```python
'tp_sr_pct': 0.3,    # 30% do TP vem de S/R distance
'sl_sr_pct': 0.5,    # 50% do SL vem de S/R distance
'tp_buffer': 0.90,   # TP em 90% da distancia S/R
'sl_buffer': 1.10,   # SL em 110% da distancia S/R
```

**Como funciona:**
- Para SELL: `dist_resistance = close - prev_10_low`, `dist_support = prev_10_high - close`
- TP = `tp_atr * (1 - tp_sr_pct) + dist_resistance * tp_buffer * tp_sr_pct`
- SL = `sl_atr * (1 - sl_sr_pct) + dist_support * sl_buffer * sl_sr_pct`

---

## Ensemble Voting (Layer 2)

Modo SELECTOR (threshold <= 0): Qualquer modo pode disparar
Modo CONSENSUS (threshold > 0): Soma ponderada deve exceder threshold

```python
'ensemble_threshold': 0.5,   # CONSENSUS
'ensemble_min_votes': 1,     # Minimo de modos concordando
```

---

## Risk Manager (Layer 4)

```python
'risk_manager': {
    'daily_stop': -5000,          # Max loss diario
    'consecutive_sl_limit': 5,    # Circuit breaker (5 SLs)
    'consecutive_sl_cooldown': 0, # Candles extras apos CB
}
```

---

## Slope Decay Dinâmico (NOVO V7.5.1)

**Atenção:** Testado e **NAO RECOMENDADO** para este sinal. Piorou resultado em -14%.

Implementado mas mantido para referência:

```python
# Mt = max(min_tp_pct, 1.0 - decay_factor * (S0 - St) / S0)
# TP_effective = TP_original * Mt
# Recalculado a cada candle M5
'behp': {
    'decay_factor': 0.50,      # Agressividade do decay
    'min_tp_pct': 0.20,        # Piso do TP (nunca abaixo de 20%)
    'use_dynamic_decay': False, # LIGAR = dynamic decay (NAO RECOMENDADO)
}
```

**Funcionamento:**
- `S0` = EMA20_SLOPE no candle de entrada (referência estática)
- `St` = EMA20_SLOPE do candle atual
- Se St acelera (maior momentum): TP pode expandir (Mt > 1.0)
- Se St desacelera: TP encolhe (Mt < 1.0, mínimo = min_tp_pct)
- Se |S0| < epsilon: Mt = 1.0 (sem decay, momentum neutro)

**Por que piorou?** O TP encolhido sai cedo demais nas oscilações intradiárias do WIN. O mercado oscila antes de continuar, e o TP dinâmico captura apenas a oscilação inicial.

---

## S/R Buffer Dinâmico (NOVO V7.5.1)

Ajusta TP/SL com base em suportes/resistências usando janela configurável:

```python
'sr_window': 10,  # 10, 30, ou 60 candles (default: 10)
'tp_sr_pct': 0.3,  # % do TP baseado em S/R
'sl_sr_pct': 0.5,  # % do SL baseado em S/R
```

**Colunas usadas:**
- `prev_10_high` / `prev_10_low` (50 min no M5)
- `prev_30_high` / `prev_30_low` (2.5h no M5)
- `prev_60_high` / `prev_60_low` (5h no M5)

**Lição:** Para WIN intradiário, `sr_window=10` funciona melhor que 30/60. Suportes de curto prazo são mais relevantes.

---

## _simulate_exit_v119

Simulacao tick-level para OOS (bid/ask reais):

```python
pnl, hit_type, mfe, mae, exit_idx, candles_in_trade, \
    be_triggered, tp30_triggered, slope_decay_triggered, \
    progressed, trailing_triggered = _simulate_exit_v119(
    records, bid_arr, ask_arr, tick_idx,
    entry_idx, N, direction, ep, tp, sl,
    use_be, be_offset, mode_name, hard_stop, atr_val,
    hp_candles=2, hp_th=0.15, tp30_pct=0.30,
    grace_candles=2, be_trigger_pts=200,
    entry_slope=0, slope_decay_pct=0.50,
    trailing_pct=0.0,
    decay_factor=0.50, min_tp_pct=0.20,
    use_dynamic_decay=False,
)
```

---

## Campos do Trade (Retorno)

```python
{
    'mode': 'M',
    'entry_dt': datetime,
    'exit_dt': datetime,
    'entry_idx': int,
    'exit_idx': int,
    'candles_held': int,
    'direction': 'BUY'/'SELL',
    'signal_dir': 1/-1,
    'pnl': float,           # Bruto (sem custo)
    'hit_type': 'TP'/'SL'/'BE'/'CLOSE',
    'mfe': float,           # Max Favorable Excursion
    'mae': float,           # Max Adverse Excursion
    'atr': float,
    'tp': int,
    'sl': int,
    # Guardrail diagnostics
    'be_triggered': bool,
    'tp30_triggered': bool,
    'slope_decay_triggered': bool,
    'progressed': bool,
    'trailing_triggered': bool,
    # Microestrutura
    'book_imbalance': float,
    'buy_ratio': float,
    'whale_count': int,
    'tick_delta': int,
    'tick_volume': int,
    'trade_count': int,
    # Ensemble
    'ensemble_votes': int,
    'vote_sum': float,
    'voting_modes': str,
}
```

---

## Modo Busca

```python
'modo_busca': True  # Desliga guardrails para exploracao
```

Quando `modo_busca=True`:
- Circuit Breaker DESLIGADO
- Lunch filter DESLIGADO
- Restricao 9:00-9:30 DESLIGADA
- Cooldown DESLIGADO

---

## Exemplo de Config Completa

```python
config = {
    'name': 'PA_SIGNAL_DIR_S0_Z30_R05_V750',
    'hour_min': 9.5,
    'hour_max': 12.0,
    'modo_busca': False,
    'modes': {
        'M': {
            'enabled': True,
            'priority': 1,
            'signal_field': 'PA_SIGNAL_DIR_S0_Z30_R05',
            'tp_mult': 4.0,
            'sl_mult': 4.0,
            'min_sl': 50,
            'max_sl': 2000,
            'tp_sr_pct': 0.3,      # S/R Buffer
            'sl_sr_pct': 0.5,      # S/R Buffer
            'filters': {
                'ATR': {'min': 400, 'max': 600},
                'PA_SIGNAL_DIR_S0_Z30_R05': {'eq': -1},
                'regime_label': {'eq': 1},
            },
            'behp': {
                'be_trigger': 60,
                'be_offset': 50,
                'hp_candles': 2,
                'hp_th': 0.15,
                'tp30_pct': 0.20,
                'grace_candles': 2,
                'hard_stop': 999999,
                'cooldown_candles': 0,
                'slope_decay': 0.0,
                'trailing_pct': 0.0,
            }
        }
    },
    'risk_manager': {
        'daily_stop': -999999,
        'consecutive_sl_limit': 5,
        'consecutive_sl_cooldown': 0,
    }
}
```

---

*Documentacao dos Engines V7.5.2*
*Atualizado em 2026-05-03*

**Changelog:**
- V7.5.0: S/R Buffer, microstructure filters (Book Imb, VWAP_Z)
- V7.5.1: Dynamic slope decay (testado, nao recomendado), VWAP_Z corrigido, S/R 30/60
- V7.5.2: WFA passou (3/3 folds positivos para BASE e VWAP_M03)
