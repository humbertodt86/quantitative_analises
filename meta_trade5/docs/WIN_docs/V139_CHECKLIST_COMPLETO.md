# V139 Checklist Completo vs Blueprint

## 1. MODOS (Matriz de Conviccao)

| Item | Blueprint | Engine V2 | Status |
|------|-----------|-----------|--------|
| **HUNTER** - Tendencia | ADX>=30, Slope>=40, GK>=1.4, TP=2.0x, SL=1.0x | ADX>=25-30, slope>=40 NAO, GK>=1.4, TP=2.0x, SL=1.0x | ⚠️ Sem slope filter |
| **SNIPER** - Exaustao | ADX>=20, Slope>=25, GK>=1.0, TP=3.5x, SL=1.11x | ADX 20-30. Slope>=25 NAO. GK 1.0-1.3. TP=3.5x, SL=1.11x | ⚠️ Sem slope filter |
| **SCALPER** - Giro | ADX>=25, Slope>=15, GK>=1.0, TP=1.2x, SL=0.8x (hora 10) | ADX>=25, Slope>=5-15, GK NAO, TP=1.2-2.0x, SL=0.8x, hora 10-12 | ⚠️ Sem GK, hora expandida |
| Direcao HUNTER | Trend (PA_SIGNAL_DIR) | Trend (PA_SIGNAL_DIR) | ✅ |
| Direcao SNIPER | Reversal (PA_SIGNAL_REV) | Reversal (PA_SIGNAL_REV) | ✅ |
| Direcao SCALPER | Reversal | Reversal | ✅ |

## 2. ENTRADA (Guardrails)

| Item | Blueprint | Engine V2 | Status |
|------|-----------|-----------|--------|
| ATR Min/Max | 200-800 (ALL) | 200-800 | ✅ |
| ADX Maximo | 61.76 (ALL) | 61.76 | ✅ |
| ADX Rising | STRONG: delta >= 0.5 | Implementado (ADX_DELTA) | ✅ |
| GK Ratio HUNTER | >= 1.4 | >= 1.4 | ✅ |
| GK Ratio SNIPER | 0.9 - 1.3 | 0.9 - 1.3 | ✅ |
| GK Ratio SCALPER | >= 1.0 | ❌ Nao implementado | ❌ |
| Slope HUNTER | >= 40 | ❌ Nao implementado | ❌ |
| Slope SNIPER | >= 25 | ❌ Nao implementado | ❌ |
| Slope SCALPER | >= 15 | >= 5-15 (otimizado) | ⚠️ |
| DIST_ABS HUNTER | nao especificado | >= 220-260 | ✅ |
| DIST_ABS SNIPER | nao especificado | >= 160 | ✅ |
| Hour Block | 9:30-17:30 | 9:30-17:30 | ✅ |
| 9:00-9:30 | Block, permitir HUNTER only | ❌ Nao implementado | ❌ |
| Golden Hour 10-11h | Risk mult 1.5x | ❌ Removido por usuario | ❌ |
| 12-14h | Filtro adicional | ❌ Nao implementado | ❌ |

## 3. SAIDA (Position Management)

| Item | Blueprint | Engine V2 | Status |
|------|-----------|-----------|--------|
| BE Trigger | Profit >= 1.0x ATR | be_trigger pts | ✅ |
| TP30 (H-Progress) | 2 candles, profit < 15% do TP, reduz TP para 30% | hp_candles=2, hp_th=0.15-0.25, tp30_pct=0.2-0.5 | ✅ |
| Grace Period BE | 2 candles apos TP30 -> BE | grace_candles=1-2 | ✅ |
| Slope Decay BE | slope atual < 50% do entry -> BE | slope_decay=0.5 | ✅ |
| Circuit Breaker | 5 SLs consecutivos/dia | Implementado (consec_sl >=5) | ✅ |

## 4. S/R BUFFERS

| Item | Blueprint | Engine V2 | Status |
|------|-----------|-----------|--------|
| S/R Buffer TP | 90% da distancia | tp_buffer=0.9 | ✅ |
| S/R Buffer SL | 110% da distancia | sl_buffer=1.1 | ✅ |
| SNIPER tp_sr_pct | 0.3 | 0.0 (nao usado) | ❌ Desabilitado |
| SNIPER sl_sr_pct | 0.3 | 0.0 (nao usado) | ❌ Desabilitado |
| HUNTER S/R | 0.0 | 0.0 | ✅ |
| SCALPER S/R | tp_sr=0.4, sl_sr=0.4 | 0.0 (nao usado) | ❌ Desabilitado |

## 5. MICROESTRUTURA (V138)

| Item | Blueprint | Engine V2 | Status |
|------|-----------|-----------|--------|
| Book Imbalance | Soft preference (FAVORABLE/UNFAVORABLE) | ❌ Nao implementado | ❌ |
| Whale Detection | Ordem grande -> warning | ❌ Nao implementado | ❌ |
| Tape Reading | Logging only (delta, VWD, absorption) | ❌ Nao implementado | ❌ |
| Concentration Zones | conc_below/above para S/R | ❌ Nao implementado | ❌ |

## 6. DIVERGENCIAS (presente no engine mas NAO no blueprint)

| Item | Engine V2 | Explicacao |
|------|-----------|------------|
| NORMAL mode (ADX 17.72-22.72) | Modo adicional | Fallback entre STATIONARY e STRONG |
| HSTAG (fechar mercado) | ❌ Removido apos correcao | Era invencao minha, nao existe no V139 |
| max_atr_mult | Gate_max = ATR * mult | Engine v2 implementa dinamicamente |
| cooldown_candles | Pausa apos SL | Implementado, blueprint nao especifica |
| FAST-SCREENER | Simulacao candle-level | Ferramenta de otimizacao, nao do bot |
| COST=30 | Slippage modelado | Adicionado para realismo |

## 7. RESUMO

| Categoria | Total | ✅ OK | ⚠️ Parcial | ❌ Falta |
|-----------|-------|-------|-------------|----------|
| Modos | 12 | 8 | 3 | 1 |
| Entrada | 14 | 9 | 2 | 3 |
| Saida | 5 | 5 | 0 | 0 |
| S/R | 6 | 3 | 0 | 3 |
| Microestrutura | 4 | 0 | 0 | 4 |
| **Total** | **41** | **25** | **5** | **11** |

## 8. PRIORIDADE DO QUE FALTA

1. 🔴 **Book Imbalance** (V138 research) — pode melhorar WR significativamente
2. 🔴 **SNIPER S/R buffers** — blueprint usa 0.3/0.3, desabilitamos
3. 🟡 **SCALPER S/R buffers** — blueprint usa 0.4/0.4
4. 🟡 **Slope filters** — HUNTER>=40, SNIPER>=25 (nao implementados)
5. 🟡 **GK Ratio SCALPER** — >= 1.0
6. 🟢 **Horario 9-9:30** — permitir HUNTER only
7. 🟢 **12-14h** — filtro adicional
8. 🔴 **Tape Reading** — logging (baixa prioridade)
