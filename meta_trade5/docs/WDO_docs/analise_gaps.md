# Analise de Gaps Conceituais — WDO

## Gaps Identificados

### 1. Micro-Scalping (canais de 10pts)
**Status**: ❌ Testado e falhou
**OOS**: -1.664 pts (55,9% WR, PF 0,96)
**Problema**: 82% dos candles geram sinal — sinais demais, WR insuficiente para compensar custo.
**Conclusao**: O micro-movimento de 1-2 candles nao tem edge detectavel com indicadores simples.

### 2. Trend Exhaustion (reversao apos tendencia)
**Status**: ❌ Testado e falhou
**OOS**: -315 pts (39,7% WR, PF 0,56)
**Problema**: WR muito baixa. Quando o Channel dispara e falha, a reversao nao e viavel.
**Conclusao**: Apostar contra a tendencia no WDO perde dinheiro (consistente com short-side).

### 3. Gaps de Abertura
**Status**: 🔲 Potencial nao explorado
**Ocorrencias**: 565 gaps em 101k candles (0,55%)
**Problema**: Muito raro para ser uma estrategia standalone.
**Tentativas**:
  - PA_GAP_FADE: 561 sinais (muito raro)
  - PA_GAP_VOL: 0 sinais (gap + volume nunca coexistem no M5)
  - PA_CHANNEL_NOGAP: Channel filtrado por "sem gap" funciona (+435 OOS) mas e praticamente igual ao original.
**Conclusao**: Gap como filtro nao mudou o resultado. Gap como sinal e raro demais.

### 4. Tendencias Longas (>2h)
**Status**: ⚠️ Parcialmente coberto
**Cobertura atual**: ER Trend (+69 pts, fraca), Channel Breakout (captura entrada mas nao a tendencia toda)
**Problema**: Nenhuma estrategia captura o movemento completo de 20-30 pts das trends de 2h.
**Tentativas**:
  - HSTAG mais paciente com Channel: testado, PIOROU o resultado (o WDO reverte antes)
  - ER Trend: funciona mas PnL baixo (+69)
**Conclusao**: O WDO reverte rapido demais para capturar tendencias longas com stop-loss viavel.

### 5. Multi-Timeframe Confirmation
**Status**: ✅ Testado e POSITIVO
**Resultado**: PA_CONFIRMED (Channel + MA50) = OOS **+400**, WR **81,3%**, PF **8,44**
**Ganho**: WR sobe de 77,5% para 81,3%, PF de 7,73 para 8,44
**Custo**: Trades caem de 249 para 193 (22% menos)
**Conclusao**: Confirmar sinais com timeframe maior (MA50 como proxy de M15) MELHORA a qualidade.
**Nao testado**: Confirmacao com M15 real (usar candles M15 em vez de MA50).

### 6. Order Flow / Book Imbalance / Tick Delta
**Status**: 🔲 Nao testado (precisa de dados de book)
**Potencial**: Alto — seria uma fonte de alpha totalmente nova
**Problema**: Nao temos dados de book nos tick files atuais.

### 7. Sazonalidade (dia da semana, feriados)
**Status**: 🔲 Nao testado
**Problema**: Precisaria adicionar coluna day_of_week e dados de feriados.

### 8. Correlacao Macro (TNX, VIX, commodities)
**Status**: 🔲 Nao testado
**Problema**: Precisaria de dados externos sincronizados.

## Matriz de Impacto vs Esforco

| Gap | Impacto potencial | Esforco para testar | Prioridade |
|-----|------------------|-------------------|------------|
| Multi-timeframe (M15) | Alto (+400 via MA50, M15 real pode ser melhor) | Medio (precisa M15) | 🥇 |
| Order Flow / Book | Muito alto (fonte nova de alpha) | Alto (precisa dados novos) | 🥈 |
| Sazonalidade | Medio | Baixo (so adicionar coluna) | 🥉 |
| Correlacao Macro | Medio | Alto (fontes externas) | 4 |
| Micro-scalping | ❌ Testado e falhou | — | Descartado |
| Trend exhaustion | ❌ Testado e falhou | — | Descartado |
| Gaps | ❌ Muito raro | — | Descartado |
| Tendencias longas | ⚠️ WDO reverte rapido | — | Descartado |
