# V139 Baseline - Oficial

**Versao**: 1.0 (2026-04-30)
**Status**: ✅ Validado e Fechado

## Arquivos

| Arquivo | Descricao |
|---------|-----------|
| `bots/WIN_bot/bot_mt5_v139.py` | Bot Python MT5 (command center) |
| `bots/WIN_bot/configs/v139_baseline.json` | Config JSON oficial |
| `configs/v139_original.json` | Config original (mesmo conteudo) |
| `bot_mt5_mql/V139_BASELINE.mq5` | Codigo MQL5 para compilar no MT5 |
| `backtest/engine_v2.py` | Engine de backtest validado |
| `docs/WIN_docs/V139_BASELINE.md` | Este documento |

## Resultados OOS (30 Mar - 29 Abr 2026)

| Metrica | Valor |
|---------|-------|
| Trades | 306 |
| Gross | +26.708 pts |
| Net (cost=30) | +17.528 pts |
| Win Rate | 44,8% |
| Profit Factor | 1,42 |
| Max Drawdown | -10.083 pts |
| Dias lucrativos | 9/21 (43%) |

## Modos

| Modo | Prioridade | ADX7 | TP | SL | DIST_ABS | Sinal |
|------|-----------|------|----|----|----------|-------|
| HUNTER | 4 (max) | >= 25 | 2.0x | 1.0x | >= 260 | Trend (PA_SIGNAL_DIR) |
| SNIPER | 3 | 20-30 | 3.5x | 1.11x | >= 160 | Reversal (-PA_SIGNAL_DIR) |
| SCALPER | 2 | >= 25 | 2.0x | 0.8x | >= 100 | Reversal, H10-12 |
| NORMAL | 1 (min) | 17.72-22.72 | 1.5x | 1.0x | >= 220 | Trend (PA_SIGNAL_DIR) |

## Guardrails

- ATR: 200-800
- ADX max: 61.76
- Horario: 9:30-17:30
- TP30: 2 candles com progresso < 15% -> reduz TP para 30%
- Grace Period BE: 2 candles apos TP30 -> SL = entry + offset
- Slope Decay BE: slope < 50% do entry -> BE
- Circuit Breaker: 5 SLs consecutivos no mesmo dia
- Cooldown: 2 candles apos SL

## Historico de Correcoes

1. **Look-ahead bias**: Entry agora usa open do candle SEGUINTE (nao do mesmo candle). Engine_v2 implementa `ep = records[i+1]['open']`.
2. **ADX period**: Usa ADX7 (7-period, 35min em M5). ADX14/20/30 disponiveis no parquet completo.
3. **TP30**: Substituiu HSTAG. Nao fecha prematuramente trades que estao se desenvolvendo.
4. **Full OOS ticks**: WINJ26 (30 Mar - 14 Abr) + WINM26 (14-29 Abr) com bid/ask real.

## Performance por Direcao

| Direcao | Trades | PnL | WR |
|---------|--------|-----|----|
| SELL | 185 | +68.545 | 68,1% |
| BUY | 121 | -41.837 | 9,1% |

**Nota**: Estrategia e fortemente short-biased. Short-only testado nos Ciclos 1-5 mostra resultados
superiores (+97K OOS) mas com alta dependencia de regime de mercado.

## Ciclos de Otimizacao

Ver `docs/WIN_docs/RELATORIO_FINAL.md` para resultados completos dos 5 ciclos.
