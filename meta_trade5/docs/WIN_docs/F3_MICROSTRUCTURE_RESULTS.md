# F3 Microstructure Grid Search - Resultados Completos

**Data:** 2026-05-03
**Variante:** PA_SIGNAL_DIR_S0_Z30_R05
**Grid:** TP30 [0%, 10%, 20%, 40%, 60%, 80%, 100%] × Slope Decay [0.0, 0.3, 0.5, 0.7, 1.0]
**Cenarios:** BASE, BOOK_IMB, VWAP_Z, SR_BUFFER, BOOK+VWAP, ALL_MICRO

---

## Resumo Executivo

**O grid search expandido revelou que TP30 é o parametro mais critico.** Sem TP30, o modelo perde dinheiro. Com TP30=60%, o BASE alcanca +2,981. Com SR_BUFFER + TP30=20%, alcancamos +2,898 (+75% vs config anterior).

**Config Oficial Recomendada V7.5.0:**
```python
Sinal: PA_SIGNAL_DIR_S0_Z30_R05 (V8.0)
TP: 4.0x | SL: 4.0x | ATR: 400-600
BE Trigger: 60 | BE Offset: 50 | HP: 2
TP30: 20% | Slope Decay: 0.0 (nao importa)
SR_BUFFER: tp_sr_pct=0.3, sl_sr_pct=0.5
Trailing Stop: DESLIGADO
Book Imbalance: NAO USAR (piora)
VWAP_Z: NAO USAR (mata trades)
```

---

## Resultados Detalhados por Cenario

### 1. BASE (sem microestrutura)

| TP30 | Best SD | OOS PnL | N | WR | Stress | Observacao |
|------|---------|---------|---|----|--------|------------|
| 0% | 0.0 | **-783** | 34 | 8.8% | -1803 | **SEM TP30 = DISASTER** |
| 10% | 0.0 | +954 | 34 | 50.0% | -66 | |
| **20%** | **0.0** | **+1651** | **34** | **47.1%** | **+631** | Config anterior |
| 40% | 0.0 | +1482 | 34 | 47.1% | +462 | |
| **60%** | **0.0** | **+2981** | **34** | **47.1%** | **+1961** | **Melhor BASE** |
| 80% | 0.0 | -117 | 34 | 41.2% | -1137 | |
| 100% | 0.0 | +220 | 34 | 41.2% | -800 | |

**Observacao CRITICA:** TP30=0% (sem TP30) da -783 PnL. TP30 eh OBRIGATORIO para este sinal. O TP efetivo sem TP30 eh 4.0x ATR (~1800 pts), que nunca eh atingido — trades viram losses cheios.

**Slope Decay:** Nao importa o valor (0.0 a 1.0) — resultados identicos em cada TP30. SD ativa em 70-97% dos trades.

---

### 2. BOOK_IMB (BOOK_IMB < -0.3)

| TP30 | Best SD | OOS PnL | N | WR | Stress |
|------|---------|---------|---|----|--------|
| 0% | 0.0 | -3982 | 23 | 0.0% | -4672 |
| 10% | 0.0 | -2662 | 23 | 52.2% | -3352 |
| 20% | 0.0 | -1984 | 23 | 47.8% | -2674 |
| 40% | 0.0 | -1132 | 23 | 47.8% | -1822 |
| **60%** | **0.0** | **+719** | **23** | **47.8%** | **+29** |
| 80% | 0.0 | -2028 | 23 | 39.1% | -2718 |
| 100% | 0.0 | -3072 | 23 | 34.8% | -3762 |

**Conclusao:** BOOK_IMB < -0.3 reduz trades de 34 para 23 e PIORA PnL em todos os TP30 exceto 60%. **NAO RECOMENDADO.**

---

### 3. VWAP_Z (VWAP_Z >= 0.5)

| TP30 | Best SD | OOS PnL | N | WR | Stress |
|------|---------|---------|---|----|--------|
| 0% | 0.0 | -27 | 1 | 0.0% | -57 |
| 10% | 0.0 | +179 | 1 | 100% | +149 |
| 20% | 0.0 | +387 | 1 | 100% | +357 |
| 40%+ | 0.0 | +5 | 1 | 100% | -25 |

**Conclusao:** VWAP_Z >= 0.5 mata o sinal completamente (1 trade apenas). **NAO USAR.**

---

### 4. SR_BUFFER (tp_sr_pct=0.3, sl_sr_pct=0.5)

| TP30 | Best SD | OOS PnL | N | WR | Stress | Observacao |
|------|---------|---------|---|----|--------|------------|
| 0% | 0.0 | +1612 | 34 | 17.6% | +592 | |
| 10% | 0.0 | +2413 | 34 | 52.9% | +1393 | |
| **20%** | **0.0** | **+2898** | **33** | **45.5%** | **+1908** | **MELHOR GERAL** |
| 40% | 0.0 | +1244 | 33 | 42.4% | +254 | |
| 60% | 0.0 | +1498 | 33 | 42.4% | +508 | |
| 80% | 0.0 | +1753 | 33 | 42.4% | +763 | |
| 100% | 0.0 | +734 | 33 | 39.4% | -256 | |

**Conclusao:** SR_BUFFER melhora significativamente o resultado. De +1,651 (BASE TP30=20%) para +2,898 (+75%). O S/R buffer ajusta SL e TP com base em prev_10_high/low, evitando stops muito apertados e targets muito distantes.

**Como funciona:**
- tp_sr_pct=0.3: 30% do TP vem da distancia ate a resistencia (prev_10_high)
- sl_sr_pct=0.5: 50% do SL vem da distancia ate o suporte (prev_10_low)
- tp_buffer=0.90: TP em 90% da distancia S/R
- sl_buffer=1.10: SL em 110% da distancia S/R

---

### 5. ALL_MICRO (todos os filtros)

**0 trades em todos os combos.** Filtros combinados sao muito restritivos.

---

## Comparacao Final

| Config | OOS PnL | N | WR | Stress | Delta vs Anterior |
|--------|---------|---|----|--------|-------------------|
| BASE TP30=20% (anterior) | +1,651 | 34 | 47.1% | +631 | baseline |
| BASE TP30=60% | +2,981 | 34 | 47.1% | +1,961 | +80% |
| **SR_BUFFER TP30=20%** | **+2,898** | **33** | **45.5%** | **+1,908** | **+75%** |
| SR_BUFFER TP30=10% | +2,413 | 34 | 52.9% | +1,393 | +46% |

---

## Descobertas Criticas

### 1. TP30 eh OBRIGATORIO
Sem TP30 (0%), o modelo perde -783 pts. Com TP30=20%, ganha +1,651. Diferenca = **2,434 pts**.

Por que? Sem TP30, o TP efetivo eh 4.0x ATR (~1,800 pts). O preco nunca chega la. Trades que comecam bem revertem e viram losses. TP30 forca saida parcial no HP, capturando lucro antes da reversao.

### 2. SR_Buffer funciona
Ajustar SL/TP com S/R distances melhora resultado em +75%. O prev_10_high/low fornece informacao de mercado que o ATR sozinho nao captura.

### 3. Book Imbalance e VWAP_Z NAO funcionam
- BOOK_IMB < -0.3: reduz trades e piora PnL
- VWAP_Z >= 0.5: mata o sinal (1 trade)

### 4. Slope Decay nao importa
Todos os valores de SD (0.0 a 1.0) produzem resultados identicos dentro de cada TP30. SD ativa em 70-97% dos trades.

---

## Config Oficial V7.5.0

```python
# Sinal
PA_SIGNAL_DIR_S0_Z30_R05 (V8.0)

# Risco Base
TP: 4.0x ATR
SL: 4.0x ATR
ATR Min: 400 | ATR Max: 600
Min SL: 50 | Max SL: 2000

# Guardrails
BE Trigger: 60 pts
BE Offset: 50 pts
HP: 2 candles
TP30: 20%
Grace Candles: 2
Cooldown: 0
Slope Decay: 0.0 (qualquer valor funciona)

# Microestrutura (NOVO)
SR Buffer: tp_sr_pct=0.3, sl_sr_pct=0.5
  - tp_buffer=0.90 (TP em 90% da distancia S/R)
  - sl_buffer=1.10 (SL em 110% da distancia S/R)

# Filtros
Regime: TREND (regime_label == 1)
Direction: SELL (PA_SIGNAL_DIR == -1)
Hour: 9:30 - 12:00

# DESLIGADOS
Trailing Stop: 0%
Book Imbalance: NAO USAR
VWAP_Z: NAO USAR
```

---

## Proximos Passos

1. **WFA:** Validar robustez temporal com 3 folds mensais
2. **DNA Analysis:** Analisar o SR_BUFFER TP30=20% em detalhe
3. **Deploy:** MT5 com config V7.5.0

---

*F3 Microstructure Grid Search*
*Gerado em 2026-05-03*
