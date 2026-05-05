# Comparacao Conceitual: V2 vs V8.0 vs DEPRECATED

**Data:** 2026-05-03
**Status:** Implementado e testado em OHLC

---

## 1. Resultados OOS (Resumo)

| Sinal | Melhor OOS | Trades OOS | WR OOS | Status |
|-------|------------|------------|--------|--------|
| **DEPRECATED** (original) | -5,765 | 67 | 53.7% | ❌ Negativo |
| **V8.0** (proposta usuario) | -2,491 | 48 | 54.2% | ❌ Negativo (melhorou) |
| **V2** (fresh cross) | +1,379 | **3** | 100% | ✅ Positivo (mas 3 trades) |

**Delta V8.0 vs DEPRECATED:** +3,274 pts (48t vs 67t)
**Delta V2 vs DEPRECATED:** +7,144 pts (3t vs 67t)

---

## 2. Comparacao Conceitual

### DEPRECATED (Original)

**Logica:** `close > EMA20 → +1`, `close < EMA20 → -1`

**Problema:** Sinal **binario e tardio**. Nao distingue entre:
- Preço acabou de cruzar EMA20 (bom)
- Preço está acima da EMA20 há 20 candles (ruim — movimento exausto)
- EMA20 está subindo (bom) ou flat (ruim)
- Preço está esticado 3 desvios acima da média (ruim — pullback iminente)

**Resultado:** 100% dos candles geram sinal. Entra no movimento já em andamento, frequentemente no topo/fundo.

---

### V8.0 (Proposta do Usuario)

**Logica:** `close > EMA20` + `EMA20_SLOPE > 0` + `|Z-SCORE| < 2.0` + `range_ratio >= 0.8`

**Melhorias sobre DEPRECATED:**
1. **Momentum (EMA20_SLOPE):** Exige que a média esteja INCLINADA na direção do sinal. Se EMA20 está flat (consolidação), o sinal vai para 0. Isso elimina entradas em lateralização.
2. **Exaustao (Z-Score):** Bloqueia entradas quando o preço está estatisticamente longe da média (|z| > 2). Evita "comprar no topo" e "vender no fundo".
3. **Ruido (range_ratio):** Só gera sinal em candles com range significativo (>= 80% da média). Elimina barras de baixa convicção.

**Trade-offs:**
- **Mantém trade count razoável:** 48 trades OOS (vs 67 do original) — ainda testável estatisticamente
- **Melhora qualidade:** Filtra ~30% dos sinais mais fracos
- **Ainda negativo OOS:** A melhoria de +3,274 pts não é suficiente para virar lucrativo

**Por que ainda é negativo?**
O problema não é só a qualidade do sinal de entrada. É a **assimetria do mercado** no período OOS (Abr/2026). O WIN caiu fortemente no início de Abril, mas as estratégias SELL baseadas em PA_SIGNAL_DIR não capturaram esse movimento — provavelmente porque:
- O cruzamento do preço para baixo da EMA20 aconteceu TARDE (após a queda inicial)
- O Z-Score já estava < -2.0 (preco muito esticado para baixo), então o V8.0 BLOQUEOU a entrada justamente no melhor momento

**Conclusão sobre V8.0:** É conceitualmente superior ao DEPRECATED como **sinal base**. Mas como estratégia TREND_SELL standalone, ainda não funciona neste período.

---

### V2 (Fresh Cross + Aceleração)

**Logica:** Só dispara no **primeiro candle** após cruzamento, quando o slope está **acelerando**.

**Melhorias:**
1. **Timing perfeito:** Entra no impulso inicial, não no movimento exausto
2. **Alta qualidade:** 100% WR OOS, PF=999
3. **Baixo drawdown:** MaxDD=-10 pts

**Problema fatal:**
- **Apenas 3 trades OOS** — não estatisticamente significativo
- Em períodos de tendência contínua, o preço pode ficar do mesmo lado da EMA20 por dias. O V2 só pega o PRIMEIRO candle, perdendo todo o resto do movimento.
- Funciona como um **"sniper"** que acerta quando atira, mas atira pouquíssimo.

---

## 3. Qual é Conceitualmente Melhor?

| Critério | DEPRECATED | V8.0 | V2 |
|----------|-----------|------|-----|
| **Como sinal BASE** | ⭐ Ruim | ⭐⭐⭐ Bom | ⭐⭐ Muito restritivo |
| **Como sinal SNIPER** | ⭐ Ruim | ⭐⭐ Bom | ⭐⭐⭐ Excelente |
| **Trade count** | 67 OOS | 48 OOS | 3 OOS |
| **Qualidade por trade** | Baixa | Média-Alta | Muito alta |
| **Robustez estatística** | ✅ Alta | ✅ Alta | ❌ Baixa |
| **Filtra lateralização** | ❌ Não | ✅ Sim | ✅ Sim |
| **Evita exaustão** | ❌ Não | ✅ Sim | ✅ Sim |
| **Captura tendência continua** | ✅ Sim | ✅ Sim | ❌ Não |

### Veredito:

**V8.0 é conceitualmente superior como sinal BASE.**

Por quê?
- Um sinal base deve ter **trade count suficiente** para ser estatisticamente robusto (V8.0: 48 trades ✓, V2: 3 trades ✗)
- Deve **filtrar ruído** sem ser paranoico (V8.0 filtra 30%, V2 filtra 95%)
- Deve **herdar bem** para sinais derivados (PA_STRONG_TREND, PA_ADX_BREAK, etc.)

**V2 é superior como overlay/sniping.**
- Ideal para ser usado EM CONJUNTO com outro sinal
- Pode ser um modo "SNIPER" dentro do engine que só dispara quando V2 confirma

---

## 4. Recomendação de Uso

### Opção A: V8.0 como sinal base (RECOMENDADO)

Manter `PA_SIGNAL_DIR = V8.0` como está agora. Todos os sinais derivados (PA_STRONG_TREND, PA_ADX_BREAK, etc.) automaticamente herdam a lógica melhorada.

**Vantagens:**
- Todos os 20+ sinais PA_ beneficiam sem alteração de código
- Trade count mantido em nível testável
- Filtros de momentum e exaustão em todos os sinais

**Desvantagens:**
- INVALIDA todos os backtests anteriores (os sinais mudaram)
- Requer re-executar F1/F2/F3/OOS para TODOS os sinais

### Opção B: V2 como overlay

Manter `PA_SIGNAL_DIR = DEPRECATED` como base. Adicionar `PA_SIGNAL_DIR_V2` como coluna separada. No engine, usar V2 como confirmação adicional (ex: modo SNIPER só entra se V2 == -1).

**Vantagens:**
- Não invalida backtests existentes
- V2 pode ser ativado/desativado por modo

**Desvantagens:**
- Mais complexidade no engine
- Não resolve o problema fundamental do sinal base

---

## 5. Observação Crítica

**Nem V8.0 nem V2 tornam PA_SIGNAL_DIR_TREND_SELL lucrativo neste período.**

A análise mostra que o problema vai além da qualidade do sinal:
- O mercado OOS (Abr/2026) teve quedas abruptas nos primeiros dias
- PA_SIGNAL_DIR é **tardio por design** — só dispara após o cruzamento do preço com EMA20
- Em quedas abruptas, o preço cruza a EMA20 **depois** da maior parte da queda
- O Z-Score do V8.0 acaba **bloqueando** entradas nos melhores momentos (quando o preço já caiu muito)

**Sugestão:** Testar V8.0 com sinais de **breakout/continuação** (PA_GK_BREAK, PA_ADX_BREAK) em vez de sinais de **cruzamento** (PA_SIGNAL_DIR). Breakouts disparam ANTES ou DURANTE o movimento, não depois.

---

## 6. Arquivos

- `scripts/build_continuous_indicators.py` — Código fonte V8.0
- `scripts/update_signal_dir_v8.py` — Script de migração do parquet
- `data/super_win_continuous.parquet` — Parquet atualizado (192 colunas)
- `docs/WIN_docs/COMPARACAO_V2_V8_DEPRECATED.md` — Este relatório

---

*Gerado automaticamente em 2026-05-03*
