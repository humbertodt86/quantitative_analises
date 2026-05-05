# V139 — Alinhamento Python vs MQL5

## Status Atual (29-Abr-2026)

O V139 existe em duas implementacoes:
- **Python**: `bots/WIN_bot/bot_mt5_v139.py` (live trading)
- **MQL5**: `bot_mt5_mql/v139_win_novo.mq5` (strategy tester)
- **Engine V2**: `backtest/engine_v2.py` (backtest offline)

## Mapa de Parametros

### Modos e Gates

| Parametro | Python bot | MQL5 | Engine V2 | Match? |
|-----------|-----------|-------|-----------|--------|
| STRONG gate_min (DIST_ABS) | 260 | InpMinStrong=260 | `DIST_ABS: {'min': 260}` | ✅ |
| NORMAL gate_min | 220 | InpMinNormal=220 | `DIST_ABS: {'min': 220}` | ✅ |
| STATIONARY gate_min | 160 | InpMinStationary=160 | `DIST_ABS: {'min': 160}` | ✅ |
| STRONG gate_max (ATR*2.5) | ATR*2.5 | InpMaxTrendATR=2.5 | `max_atr_mult: 2.5` | ✅ |
| NORMAL gate_max | ATR*2.5 | InpMaxTrendATR=2.5 | `max_atr_mult: 2.5` | ✅ |
| STATIONARY gate_max (ATR*0.74) | ATR*0.74 | InpMaxRangeATR=0.7439 | `max_atr_mult: 0.74` | ✅ |

### Modos e TP/SL

| Modo | Python bot | MQL5 | Engine V2 |
|------|-----------|-------|-----------|
| STRONG TP | 2.7572×ATR | InpTP_Strong=2.7572 | `tp_mult: 2.76` |
| STRONG SL | 1.1187×ATR | InpSL_Strong=1.1187 | `sl_mult: 1.12` |
| NORMAL TP | 2.1×ATR | InpTP_Normal=2.1 | `tp_mult: 2.1` |
| NORMAL SL | 1.0×ATR | InpSL_Normal=1.0 | `sl_mult: 1.0` |
| STATIONARY TP | 1.3×ATR | InpTP_Stationary=1.3 | `tp_mult: 1.3` |
| STATIONARY SL | 0.8×ATR | InpSL_Stationary=0.8 | `sl_mult: 0.8` |

### Filtros de Entrada

| Filtro | Python bot | MQL5 | Engine V2 | Match? |
|--------|-----------|-------|-----------|--------|
| ATR min | 200 | InpATRMin=200 | `ATR: {'min': 200}` | ✅ |
| ATR max | 800 | InpATRMax=800 | `ATR: {'max': 800}` | ✅ |
| ADX max | 61.76 | InpADXMaximo=61.76 | `ADX7: {'max': 61.76}` | ✅ |
| ADX STRONG threshold | 22.72 | InpADXStrong=22.72 | `ADX7: {'min': 22.72}` | ✅ |
| ADX NORMAL threshold | 17.72 | InpADXTrend=17.72 | `ADX7: {'min': 17.72}` | ✅ |
| ADX rising (STRONG) | ADX delta >= 0.5 | InpADXRising=true | `ADX_DELTA: {'min': 0.5}` | ✅ |
| EMA slope max (STATIONARY) | 80 | InpEMASlopeMax=80 | `EMA5_SLOPE_ABS: {'max': 80}` | ✅ |

### Saida (Position Management)

| Funcionalidade | Python bot | Engine V2 | MQL5 (novo) | Match? |
|---------------|-----------|-----------|-------------|--------|
| HSTAG | hp_candles=2, hp_th=3%TP | `hp_candles, hp_th` | InpProgressGate=2, InpProgThreshold=0.15 | ✅ |
| BE trigger | be_offset=25 | `be_trigger, be_offset` | InpProgressBEOff=25 | ✅ |
| TP30 | ❌ Nao tem | ❌ Nao tem | ❌ Removido | ✅ |
| Slope decay | ❌ Nao tem | ❌ Nao tem | ❌ Removido | ✅ |
| Cooldown apos SL | ❌ Nao tem | `cooldown_candles` | InpProgressGate*300s | ⚠️ |
| Golden hour (risk 1.5x) | Tem | ❌ Nao tem | InpGoldenHour=true | ❌ |

### Direcao do Sinal

| Modo | Python bot | Engine V2 |
|------|-----------|-----------|
| STRONG | Trend following (PA_SIGNAL_DIR) | PA_SIGNAL_DIR | ✅ |
| NORMAL | Trend following (PA_SIGNAL_DIR) | PA_SIGNAL_DIR | ✅ |
| STATIONARY | Reversal (oposto do PA_SIGNAL_DIR) | PA_SIGNAL_REV | ✅ |

## Diferencas Conhecidas

1. **Golden Hour**: ❌ Removido do MQL5 — lote sempre 1, sem multiplicador de risco. Engine V2 nao precisa implementar.
2. **Cooldown**: MQL5 usa tempo real (300s), engine_v2 usa candles (2 candles = 10min). Equivalente.
3. **Horario de entrada**: MQL5 9:30-17:30, engine_v2 usa `hour_min/hour_max` (decimal).
4. **Panic close**: MQL5 fecha as 17:55, engine_v2 nao tem panic (trade segue ate fechar).

## Arquivos de Referencia

| Arquivo | Descricao |
|---------|-----------|
| `bots/WIN_bot/bot_mt5_v139.py` | Python bot V139 (live) |
| `bot_mt5_mql/v139_win_novo.mq5` | MQL5 V139 (tester) |
| `backtest/engine_v2.py` | Engine V2 (backtest offline) |
| `scripts/run_win_v2.py` | Script de comparacao Python vs MT5 |
| `docs/backtest/trades/mt5_v139_log.csv` | Log do MT5 (Jan-Abr 2026) |
| `data/indicators_winm26_abril.parquet` | Indicadores WINM26 (Jan-Abr) |
| `data/WINM26_ticks_abril.parquet` | Ticks WINM26 (Abril) |
