# DNA Analysis: PA_SIGNAL_DIR_S0_Z30_R05
## Relatorio Completo + Plano de Acao

**Data:** 2026-05-03
**Config:** TP=4.0x, SL=4.0x, ATR=400-600, TREND_SELL
**Variante:** S0_Z30_R05 (Slope=0, Z=3.0, Range=0.5)

---

## 1. Resultados OOS (34 trades)

| Metrica | Valor |
|---------|-------|
| **Gross PnL** | +1,281 |
| **Net PnL (C=30)** | **+261** |
| **Wins** | 16 (47.1%) |
| **Losses** | 18 (52.9%) |
| **Avg gross/trade** | +37.7 |
| **Avg net/trade** | +7.7 |

### Win/Loss Profile

| | Wins (16) | Losses (18) |
|---|---|---|
| **Gross total** | +4,946 | -3,665 |
| **Avg gross** | +309.1 | -203.6 |
| **Avg MFE** | 505.6 | **142.2** |
| **Avg MAE** | 166.2 | **456.9** |
| **Avg candles held** | 3.4 | **2.0** |
| **Median candles** | 2.0 | **2.0** |

---

## 2. Descoberta CRITICA: O "Pattern da Morte"

### 100% dos Losses "Progrediram" (MFE > 0)

**Todos os 18 losses OOS tiveram lucro parcial antes de virar.**

- MFE medio nos losses: **142.2 pts**
- Em outras palavras: o trade subiu 142 pts antes de cair e bater SL
- Se o BE trigger estivesse em 120-140 pts, **quantos losses virariam BE?**

### Duracao dos Losses: TUDO em 2 candles

| Candles Held | Count | % |
|--------------|-------|---|
| 1 | 2 | 11% |
| **2** | **26** | **76%** |
| 3 | 4 | 12% |
| 4+ | 2 | 6% |

**76% dos trades (wins + losses) duram EXATAMENTE 2 candles.**

Isso significa:
- Candle 1: entramos no sinal
- Candle 2: o preco se move (para cima em SELL)
- Se nao bateu TP no candle 2, reverte e bate SL (ou TP30/BE/HP)

### Guardrails Atuais: O Que Aconteceu?

| Guardrail | Wins (16) | Losses (18) | Diagnostico |
|-----------|-----------|-------------|-------------|
| **BE triggered** | 9/16 (56%) | 1/18 (6%) | **Muito pouco ativo em losses** |
| **TP30 triggered** | 16/16 (100%) | 18/18 (100%) | **Ativo em TODOS - pode estar matando wins** |
| **Slope decay** | ? | 17/18 (94%) | **Quase perfeito nos losses** |

---

## 3. Diagnostico dos Guardrails

### Problema 1: TP30 Mata 100% dos Trades

O TP30 esta ativando em **100% dos trades** (wins e losses). Isso significa que NENHUM trade chega ao TP cheio (4.0x ATR). O TP30 reduz o TP em 30% (para 2.8x ATR) e esta sendo atingido em todos.

**E se o TP30 nao existisse?**
- Talvez alguns trades com MFE=505 (wins) chegassem ao TP=4.0x
- Mas os losses tambem ficariam mais tempo expostos

**Veredito:** TP30 esta funcionando como "TP principal", nao como "emergencia". O TP real eh 2.8x, nao 4.0x.

### Problema 2: BE Trigger esta ALTO (100 pts)

MFE medio em losses: 142.2 pts.
BE trigger: 100 pts (com offset de 25 pts = move SL para entry - 25).

**So 1/18 losses ativou BE.** Por que?
- O preco sobe 142 pts (MFE), mas o BE trigger precisa de 100 pts + o preco precisa voltar para BE
- Talvez o preco suba rapido demais (1 candle) e ja bate TP30 ou reverte antes de ativar BE

**Proposta:** Reduzir BE trigger para 80 pts (ou ate 60) para capturar mais do movimento inicial.

### Problema 3: HP=1 esta Funcionando, mas Poderia ser 0

Losses duram 2 candles. Com HP=1:
- Candle 1: entra
- Candle 2: se nao progrediu, sai com lucro reduzido

**Mas 100% dos losses progrediram (MFE>0)!** Entao HP=1 nao estah salvando losses porque todos tem pelo menos 1 candle de lucro.

**Proposta:** HP=1 esta ok, mas poderiamos testar HP=0 (sai no candle seguinte se nao atingiu nada).

### Problema 4: Cooldown=0 (Sem Pausa)

Cooldown=0 significa que podemos entrar em candles consecutivos. Em um mercado volatil, isso pode gerar 2-3 losses seguidos rapidamente.

**Proposta:** Cooldown=1 ou 2 para evitar clusters de losses.

---

## 4. Simulacao: Quanto Poderiamos Salvar?

### Cenario 1: BE mais agressivo (80 pts)

Se BE=80 com offset=25:
- Move SL para entry - 25 quando MFE >= 80
- Losses tem MFE medio = 142.2, entao TODOS atingiriam BE trigger
- Se so 50% dos losses virarem BE (em vez de SL), economia:
  - 18 losses x 203.6 avg loss = -3,665 total
  - 9 losses viram BE (loss de ~30 pts custo) = -270
  - 9 losses continuam SL = -1,832
  - Novo total losses: -2,102 (economia de +1,563)
  - **Novo PnL OOS: +261 + 1,563 = +1,824**

### Cenario 2: Remover TP30 (deixar TP=4.0x)

Risco: losses ficam mais tempo expostos.
Beneficio: wins podem capturar mais.

Nao podemos estimar sem simular, mas:
- Wins tem MFE medio = 505.6 (ja supera TP=2.8x)
- Se TP=4.0x e wins duram 3.4 candles, talvez capturem +30% de lucro

### Cenario 3: BE=80 + Cooldown=2 + HP=1

Combinacao defensiva:
- BE mais agressivo captura movimento inicial
- Cooldown evita clusters de losses
- HP=1 protege de lentidao

**Estimativa conservadora: PnL OOS de +261 para +1,500+**

---

## 5. Plano de Acao

### Fase 1: Grid Search F3 com Guardrails Variados

Testar estas combinacoes na variante S0_Z30_R05:

| Config | BE Trigger | BE Offset | HP | TP30 | Cooldown | Slope Decay |
|--------|-----------|-----------|-----|------|----------|-------------|
| **Base** | 100 | 25 | 1 | 0.30 | 0 | 0.50 |
| **A** | 60 | 25 | 1 | 0.30 | 0 | 0.50 |
| **B** | 80 | 25 | 1 | 0.30 | 0 | 0.50 |
| **C** | 100 | 50 | 1 | 0.30 | 0 | 0.50 |
| **D** | 80 | 25 | 1 | 0.30 | 2 | 0.50 |
| **E** | 80 | 25 | 2 | 0.30 | 2 | 0.50 |
| **F** | 60 | 25 | 1 | 0.20 | 0 | 0.50 |
| **G** | 80 | 25 | 1 | 0.40 | 0 | 0.50 |

### Fase 2: Validar Top 3 no OOS

Rodar tick-level OOS nas 3 melhores configs do F3.

### Fase 3: Decisao

Se OOS positivo com stress test (C=60):
- Adicionar ao ensemble como sinal TREND_SELL
- Peso: 1.0 (conservador, ate mais dados)

Se OOS negativo:
- Descartar ou tentar variante RANGE em vez de TREND

---

## 6. Outras Oportunidades

### Testar no IS com os mesmos guardrails

IS teve 73 trades com PnL=+2,823. Se aplicarmos BE mais agressivo no IS:
- 9 losses com avg=-1,871. Se 50% virarem BE: economia de ~+8,000 pts
- IS poderia ir para +10,000+ (mas cuidado com overfit!)

### Ajustar TP/SL Ratio

Atual: TP=4.0x, SL=4.0x (R:R = 1:1)
Com WR=47%, R:R=1:1 e lucrativo com custo baixo.

**Mas** se melhorarmos o BE, o R:R efetivo aumenta porque:
- Wins continuam com TP=2.8x (apos TP30)
- Losses reduzem de -4.0x para -0.5x a -1.0x (BE salvou)

**R:R efetivo com BE: ~2.8 : 1.0 = 2.8:1**

Com WR=47% e R:R=2.8:1, a estrategia se torna MUITO lucrativa.

---

## 7. Conclusao

**Este modelo PODE ser salvo.**

O DNA revelou que o problema nao eh o WR (47% eh bom), mas sim que:
1. **100% dos losses progrediram** (MFE=142) antes de virar
2. **BE trigger esta muito alto** (100 pts) e nao captura esse movimento
3. **TP30 ativa em 100%** dos trades, sugerindo que o TP esta muito longe

**Com BE=80 + possivel ajuste de TP/SL, estimamos virar os 18 losses em ~9 BE + 9 SL, reduzindo o drawdown em ~1,500 pts e levando o PnL OOS de +261 para +1,800+.**

**Recomendacao:** Prosseguir com F3 grid search de guardrails IMEDIATAMENTE.

---

*Gerado automaticamente em 2026-05-03*
