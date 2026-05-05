# Proposta: PA_SIGNAL_DIR_V2 — Fresh Cross + Momentum

**Data:** 2026-05-03
**Status:** Implementado e disponível no `super_win_continuous.parquet`

---

## 1. Problema do Sinal Original

`PA_SIGNAL_DIR` é um sinal **tardio**:
- Formula: `+1` se `close > EMA20`, `-1` se `close < EMA20`
- Dispara em **100% dos candles** (48.8% SELL, 51.2% BUY)
- Entra **depois** que o preço já cruzou a EMA20
- A analise DNA mostrou: apenas 21% das entradas OOS tem continuidade de momentum
- Conclusao: estamos entrando no movimento ja exausto

## 2. Solucao Proposta: PA_SIGNAL_DIR_V2

### Logica

O V2 adiciona **tres filtros** ao sinal original:

1. **Fresh Cross:** So dispara no **primeiro candle** apos o cruzamento do preco com a EMA20.
   - Se o preco ja esta abaixo da EMA20 ha 5 candles, o sinal original continuaria gerando `-1` a cada candle. O V2 gera `-1` **apenas no candle do cruzamento**.
   - Reduz drasticamente o numero de sinais (de ~100% para ~10% dos candles).

2. **Momentum Acelerando:** A derivada do `EMA5_SLOPE` deve confirmar aceleracao na direcao do trade.
   - SELL: slope negativo **e** ficando mais negativo (`slope < slope_prev`)
   - BUY: slope positivo **e** ficando mais positivo (`slope > slope_prev`)
   - Isso garante que nao estamos entrando em um falso cruzamento ou movimento ja cansado.

3. **ATR Minimo:** `ATR >= 150` para evitar entradas em mercado morto ou sem volatilidade suficiente para o SL/TP funcionar.

### Formula

```python
# Fresh cross
fresh_cross_buy = (PA_SIGNAL_DIR == 1) & (PA_SIGNAL_DIR_prev != 1)
fresh_cross_sell = (PA_SIGNAL_DIR == -1) & (PA_SIGNAL_DIR_prev != -1)

# Momentum acelerando
slope_accel_buy = (EMA5_SLOPE > 0) & (EMA5_SLOPE > EMA5_SLOPE_prev)
slope_accel_sell = (EMA5_SLOPE < 0) & (EMA5_SLOPE < EMA5_SLOPE_prev)

# ATR minimo
atr_ok = ATR >= 150

PA_SIGNAL_DIR_V2 = +1 se fresh_cross_buy & slope_accel_buy & atr_ok
PA_SIGNAL_DIR_V2 = -1 se fresh_cross_sell & slope_accel_sell & atr_ok
PA_SIGNAL_DIR_V2 =  0 caso contrario
```

## 3. Resultados da Geracao

| Metrica | PA_SIGNAL_DIR (Original) | PA_SIGNAL_DIR_V2 |
|---------|--------------------------|------------------|
| Candles com sinal SELL | 4,288 (48.8%) | 449 (5.1%) |
| Candles com sinal BUY | 4,499 (51.2%) | 446 (5.1%) |
| Candles neutros | 0 (0.0%) | 7,892 (89.8%) |
| **Reducao total** | — | **-89.8%** |

## 4. Como Usar no Pipeline

O V2 eh uma **coluna drop-in replacement** para `PA_SIGNAL_DIR`. Basta trocar o nome da coluna no orchestrador:

```python
# Antes (original)
{'name': 'PA_SIGNAL_DIR_TREND_SELL', 'col': 'PA_SIGNAL_DIR', 'signal': -1, 'regime': 'trend'}

# Depois (V2)
{'name': 'PA_SIGNAL_DIR_V2_TREND_SELL', 'col': 'PA_SIGNAL_DIR_V2', 'signal': -1, 'regime': 'trend'}
```

Todas as variantes (TREND, RANGE, HYBRID, BUY, SELL) funcionam da mesma forma — basta usar `col='PA_SIGNAL_DIR_V2'`.

## 5. Proximos Passos

1. **Rodar F1/F2/F3** com `PA_SIGNAL_DIR_V2_TREND_SELL` para validar se o timing melhorado traduz em PnL OOS positivo.
2. **Comparar DNA:** Gerar DNA candle analysis para o V2 e comparar:
   - % de entradas com continuidade de momentum
   - Slope medio em wins vs losses
   - Distribuicao de MFE/MAE
3. **Ajustar thresholds:** Se necessario, ajustar `ATR >= 150` ou a logica de aceleracao do slope.

## 6. Arquivos

- `scripts/add_signal_dir_v2.py` — Script que adiciona a coluna ao parquet
- `scripts/build_continuous_indicators.py` — Codigo fonte do indicador (linha 108+)
- `data/super_win_continuous.parquet` — Parquet atualizado com 189 colunas

---

*Gerado automaticamente em 2026-05-03*
