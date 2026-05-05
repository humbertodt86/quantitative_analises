# Classificacao Conceitual das Estrategias WDO

## As 8 Estrategias Positivas

| # | Estrategia | OOS | Conceito | Regime | Timeframe | Direcao | Captura |
|---|-----------|-----|----------|--------|-----------|---------|---------|
| 1 | **Channel Breakout** | +455 | Breakout de canal curto (5p) | Transicao Range→Trend | 5-25min | Ambos | Rompimento do micro-canal |
| 2 | **ATR Surge** | +189 | Range > ATR (volatilidade disparou) | Range / Trend | 5-15min | Ambos | expansao de volatilidade |
| 3 | **Vol Breakout** | +160 | Range/ATR > 1.5 (explosao) | Trend / Breakout | 15-40min | Ambos | Continuacao apos expansao |
| 4 | **Range Bounce** | +237 | Compra no fundo do canal de 2h | **Range puro** | 10-30min | Ambos | Reversao no S/R do canal |
| 5 | **ORB** | +88 | Rompimento do IB da 1h | Transicao Range→Trend | 30-90min | Ambos | Direcao do dia |
| 6 | **RSI MA Confirm** | +161 | RSI extremo + MA9<MA21 | **Reversao** | 10-30min | Ambos | Reversao com confirmacao |
| 7 | **ER Trend** | +69 | Eficiencia de movimento > 0.6 | **Trend** | 30-60min | Ambos | Movimento eficiente |
| 8 | **ZZ Break** | +106 | Rompimento de topo/fundo swing | Transicao Range→Trend | 20-60min | Ambos | Continuacao apos correcao |

## Arvore de Decisao Conceitual

```
MOVIMENTO DO WDO
│
├── MERCADO OSCILANDO (75% do tempo)
│   ├── Range Bounce ← compra no fundo, vende no topo do canal de 2h
│   ├── ATR Surge ← volatilidade aumentando dentro do range
│   └── RSI MA Confirm ← reversao nos extremos do range
│
├── TRANSICAO Range→Trend (184 ocorrencias/22d)
│   ├── Channel Breakout ← rompeu o micro-canal de 5p (25min)
│   ├── ORB ← rompeu o Initial Balance (1h)
│   └── ZZ Break ← rompeu o ultimo topo/fundo swing
│
├── TREND CONFIRMADA (25% do tempo)
│   ├── Vol Breakout ← volatilidade alta, continuar na direcao
│   └── ER Trend ← movimento eficiente, continuar na direcao
```

## Conflitos e Sobreposicao

| Conflito | Estrategias | Impacto |
|----------|------------|---------|
| 🔴 **Alto** | Channel Breakout vs ZZ Break | Ambas disparam em breakouts. Channel (5p, mais rapido) vs ZZ (swing, mais lento). Se ambas entrarem no mesmo candle, uma fecha antes da outra. |
| 🟡 **Medio** | Range Bounce vs RSI MA Confirm | Range Bounce usa canal de 2h + RSI, RSI MA Confirm usa RSI + MA. Podem entrar juntas em reversoes. |
| 🟢 **Baixo** | ATR Surge vs Vol Breakout | ATR Surge (HSC=1, rapido) vs Vol Break (HSC=3, mais lento). Timing diferente. |
| 🟢 **Nulo** | ORB vs Range Bounce | ORB opera no inicio da manha (10-16h, breakouts), Range Bounce opera dia todo (bounces). Nao concorrem. |
| 🟢 **Nulo** | ER Trend vs todas | ER Trend opera tendencias eficientes (30-60min). Escopo diferente. |

## O Que Estamos PERDENDO (gaps conceituais)

| Movimento | Ocorrencia | Estrategia atual | Lacuna |
|-----------|-----------|-----------------|--------|
| **Gap de abertura** | 565 gaps (0.55%) | Nenhuma | Nao capturamos gaps |
| **Movimento lento e continuo (>2h)** | Existe (25% tendencias) | ER Trend (fraca) | Nenhuma estrategia forte para trends longas |
| **Reversao abrupta apos tendencia** | Existe (transicoes trend→range) | Nenhuma | Nao capturamos exaustao de tendencia |
| **Micro-scalping (1-2 candles)** | Existe (65% em canais de 10pts) | Range Bounce (10-30min) | Poderiamos ter algo mais agressivo |
| **Hora especifica do dia** | Padroes intraday | ORB (10-16h) | So uma estrategia tem restricao horaria |

## Resumo

**As 3 principais sao complementares e cobrem 3 regimes diferentes:**
1. **Channel Breakout**: captura a SAIDA do range (maior PnL +455)
2. **Range Bounce**: captura o DENTRO do range (PnL +237)
3. **ATR Surge / Vol Break**: captura a VOLATILIDADE (PnL +189/+160)

Nao ha conflitos graves. O maior gap e nao termos uma estrategia forte para **tendencias longas (>2h)** — a ER Trend e muito fraca (+69) para isso.
