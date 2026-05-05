# Seletor V6.1 — Plano de Implementação

## Arquitetura em Camadas (Ajustada)

```
┌─────────────────────────────────────────────┐
│  CAMADA 4: Global Risk Manager              │
│  (Regime shift protection, posição única)   │
├─────────────────────────────────────────────┤
│  CAMADA 3: Guardrails Individuais           │
│  (BE, Grace, H-Progress, Slope, cooldown)   │
│  *** H-Progress é individual por estratégia ***│
├─────────────────────────────────────────────┤
│  CAMADA 2: Ensemble Selector                │
│  (Soma ponderada dos votos > threshold)     │
│  *** 1 posição por vez ***                  │
├─────────────────────────────────────────────┤
│  CAMADA 1: 21 Estratégias Individuais       │
│  (Cada uma com TP/SL + H-Progress próprio)  │
└─────────────────────────────────────────────┘
```

## Restrições do Robô

| Item | Regra |
|------|-------|
| **Lote** | Sempre **1** (sem position sizing) |
| **Posições simultâneas** | **No máximo 1** (blocking até o fechamento) |
| **H-Progress (TP30)** | Individual por estratégia (cada uma tem seu próprio `hp_candles` e `hp_th`) |
| **Guarda-chuva** | Cooldown, Circuit Breaker, BE, Grace, Slope Decay |
| **Entrada** | Próximo candle após o sinal (sem look-ahead) |

---

## FASE 1 — Leading Indicators + Regimes (parquet)

Adicionar ao `build_continuous_indicators.py`:

| Coluna | Descrição | Lógica |
|--------|-----------|--------|
| `CVD_DELTA` | Cumulative Volume Delta | Soma acumulada dos last ticks no candle: if tick[i] > tick[i-1] → +volume, else → -volume |
| `BOOK_IMB` | Book imbalance proxy | `eff_high_last / eff_low_last` ratio (pressão compradora vs vendedora) |
| `REGIME_TREND` | Regime de tendência | ADX7 > 25 → 1 (tendência), senão 0 (range) |
| `REGIME_VOL` | Regime de volatilidade | ATR percentil 30/70 → -1 (baixa), 0 (média), 1 (alta) |
| `REGIME_STRETCH` | Distância do VWAP | ATR_STRETCH: -2 a +2 desvios padrão |
| `REGIME_DOW` | Dia da semana | 0=segunda .. 4=sexta |

**Dados de treino:** Janeiro a Março (IS total).  
**Dados de validação:** Maio (OOS cego, não usado em nenhum grid anterior).

---

## FASE 2 — Matriz de Pesos Treinada no IS

Para cada regime (tendência/range/vol alta/vol baixa/manhã/tarde/dia da semana), medir no **IS** o desempenho de cada estratégia.

O resultado é uma **matriz de pesos**:

```
Estratégia      | Tendência | Range | Vol Alta | Vol Baixa | Manhã | Tarde
PA_SIGNAL_DIR   | 2.0       | -0.5  | 1.5      | 0.5       | 1.0   | 0.8
PA_VCP          | -0.3      | 2.0   | -0.5     | 1.5       | 1.2   | 0.3
PA_REV_RSI      | -1.0      | 1.0   | 0.5      | 2.0       | 0.5   | 1.5
PA_TUESDAY      | 0.5       | 0.5   | 0.3      | 0.5       | 0.0   | 0.0
```

**Regras:**
- Peso **negativo** = veta a estratégia naquele regime
- Peso **zero** = ignora (estratégia não opera naquele contexto)
- Peso **maior** = mais influência no voto

---

## FASE 3 — Ensemble Selector

### Algoritmo

```python
def decidir_entrada(row, pesos, threshold=2.0):
    """
    A cada candle:
    1. Determinar regime atual (via row)
    2. Cada estratégia gera voto (-1, 0, 1)
    3. Multiplicar pelo peso do regime
    4. Se |soma| >= threshold → entrar
    """
    regime = classificar_regime(row)
    
    score = 0.0
    for est in estrategias:
        sinal = est.get_sinal(row)  # -1, 0, 1
        peso = pesos[est.nome][regime]  # da matriz
        score += sinal * peso
    
    if abs(score) >= CONVICCAO_THRESHOLD:
        return 1 if score > 0 else -1
    return 0
```

### Validação em 3 Camadas

| Camada | Período | Uso |
|--------|---------|-----|
| **Treino** | Janeiro | Calibrar pesos + thresholds |
| **Teste** | Fevereiro + Março | Medir estabilidade, ajustar guardrails |
| **Cego** | Maio | **Validação final** (nunca usado antes) |

---

## FASE 4 — Guardrails por Estratégia

Cada estratégia mantém seus próprios parâmetros de guardrails, otimizados na pipeline V5.1/V6.0:

| Estratégia | BE_trigger | BE_offset | H-Progress | Cooldown | 
|-----------|------------|-----------|------------|----------|
| PA_SIGNAL_DIR | 200 | 25 | hp=2, th=0.15 | 2 |
| PA_VCP | 150 | 15 | hp=1, th=0.20 | 1 |
| PA_REV_RSI | 100 | 10 | hp=3, th=0.10 | 2 |
| PA_TUESDAY | 80 | 8 | hp=1, th=0.25 | 1 |

**H-Progress é individual** porque estratégias de reversão (PA_REV_RSI) precisam de mais tempo para o TP se desenvolver do que estratégias de momentum (PA_VCP).

---

## FASE 5 — Global Risk Manager

Atua sobre a posição já aberta:

```
SE regime muda de 'trend' para 'chop' durante trade aberto
  → ativar H-Progress imediatamente (reduzir TP para 30%)

SE CVD_DELTA diverge do preço (preço sobe, CVD cai)
  → mover SL para BE

SE Circuit Breaker atingiu 5 SLs consecutivos
  → bloquear novas entradas até o próximo dia
```

**Não há gestão de lote** (sempre 1) e **não há trades simultâneos** (1 posição por vez).

---

## FASE 6 — Meta-Backtest Vetorizado

```python
# Matriz M_signals: (n_candles, n_estrategias) com -1, 0, 1
# Matriz M_pesos: (n_estrategias, n_regimes)
# Vetor regimes: (n_candles,)

# Score por candle (vetorizado)
scores = (M_signals * M_pesos[regimes]).sum(axis=1)

# Entradas onde |score| >= threshold
entradas = np.where(np.abs(scores) >= CONVICCAO_THRESHOLD)

# Position blocking (1 por vez)
skip = -1
for i in entradas[0]:
    if i <= skip: continue
    # trade executado
    skip = i + duracao_esperada
```

---

## Timeline

| Fase | O que | Tempo |
|------|-------|-------|
| **1** | build_v61.py (CVD, Book Imb, regimes) | ~20min |
| **2** | Matriz de pesos no IS | ~10min |
| **3** | Ensemble select + meta-backtest | ~20min |
| **4** | Guardrails + Risk Manager | ~15min |
| **5** | Relatório e validação | ~15min |
| **Total** | | **~1,5h** |

---

## Arquivos

| Arquivo | Descrição |
|---------|-----------|
| `scripts/build_v61.py` | Build do parquet com regimes + leading indicators |
| `scripts/_ensemble_v61.py` | Seletor + meta-backtest |
| `docs/WIN_docs/SELETOR_V61_PLANO.md` | Este arquivo |
