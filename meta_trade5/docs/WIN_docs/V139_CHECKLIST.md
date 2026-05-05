# V139 Checklist vs Blueprint

## Arquitetura (3 Modos)

| Item | Blueprint | Engine V2 | Status |
|------|-----------|-----------|--------|
| Modo 1: HUNTER (tendencia) | ADX>=30, TP=2.0x, SL=1.0x | STRONG: ADX>=22.72, TP=2.76x, SL=1.12x | ⚠️ Thresholds diferentes |
| Modo 2: SNIPER (exaustao) | ADX>=20, GK 0.9-1.3, TP=3.5x, SL=1.11x | STATIONARY: ADX<17.72, TP=1.3x, SL=0.8x | ❌ Logica diferente |
| Modo 3: SCALPER (giro) | ADX>=25, hora 10, TP=1.2x, SL=0.8x | ❌ Nao implementado | ❌ Ausente |
| Mode Detection | ADX thresholds 17.72/22.72 | ADX thresholds 17.72/22.72 | ✅ |

## Entrada (Guardrails)

| Item | Blueprint | Engine V2 | Status |
|------|-----------|-----------|--------|
| ATR Min/Max | 200-800 | 200-800 | ✅ |
| ADX Maximo | 61.76 | 61.76 | ✅ |
| ADX Rising (STRONG) | ADX delta > 0.5 | ADX_DELTA >= 0.5 | ✅ |
| DIST_ABS gate | STATIONARY>=160, NORMAL>=220, STRONG>=260 | STATIONARY>=160, NORMAL>=220, STRONG>=260 | ✅ |
| DIST_ABS gate_max | ATR * mult | ATR * max_atr_mult | ✅ |
| GK Ratio | SNIPER: 0.9-1.3 | ❌ Nao usado | ❌ |
| EMA5_SLOPE filter | STATIONARY: max 80 | Usado | ✅ |
| Hour block | 9:30-17:30 | 9:30-17:30 | ✅ |
| Circuit Breaker | 5 SLs consecutivos | ❌ Nao implementado | ❌ |

## Saida (Position Management)

| Item | Blueprint | Engine V2 | Status |
|------|-----------|-----------|--------|
| BE Trigger | Profit >= 1.0x ATR | be_trigger pts | ✅ |
| TP30 | 2 candles, profit < 15% TP, reduz TP para 30% | Implementado (novo) | ✅ |
| Grace Period | 2 candles apos TP30 -> BE | grace_candles=2 (novo) | ✅ |
| Slope Decay BE | Slope < 50% do entry -> BE | ❌ Nao implementado | ❌ |
| HSTAG (fechar mercado) | ❌ Nao existe no V139 | ❌ Removido | ✅ Removido |

## S/R Buffers

| Item | Blueprint | Engine V2 | Status |
|------|-----------|-----------|--------|
| SR buffer TP | 90% da dist ao S/R | tp_buffer=0.9 | ✅ |
| SR buffer SL | 110% da dist ao S/R | sl_buffer=1.1 | ✅ |
| STRONG SR% | 0-40% | tp_sr/sl_sr variavel | ✅ |
| NORMAL SR% | 0-30% | tp_sr/sl_sr variavel | ✅ |
| STATIONARY SR% | 0% | tp_sr/sl_sr=0 | ✅ |

## Resumo

| Categoria | Total | ✅ OK | ⚠️ Parcial | ❌ Falta |
|-----------|-------|-------|-------------|----------|
| Modos | 3 | 0 | 2 | 1 (SCALPER) |
| Entrada | 7 | 5 | 1 | 1 (GK Ratio) |
| Saida | 5 | 3 | 0 | 2 (Slope Decay, Circuit Breaker) |
| S/R | 5 | 5 | 0 | 0 |
| **Total** | **20** | **13** | **3** | **4** |

O SCALPER e o Slope Decay BE sao os mais impactantes para implementar.
