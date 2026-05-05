# Resumo Final — Todas as Estrategias Testadas

## Ranking de Robustez (Top 100 configs validadas OOS)

| # | Estrategia | OOS medio | Max | Min | %Pos | Trades | pts/dia | Confianca |
|---|-----------|-----------|-----|-----|------|--------|---------|-----------|
| 1 | **Channel Breakout** | **+239** | +347 | +145 | **100%** | 249 | **+10.9** | 💎 |
| 2 | **ATR Surge** | **+180** | +251 | +66 | **100%** | 194 | **+8.2** | 💎 |
| 3 | **Vol Break** | **+164** | +196 | +137 | **100%** | 93 | **+7.5** | 💎 |
| 4 | **Range Bounce** | — | +237 | — | — | 144 | +10.8 | ✅ |
| 5 | **ORB** | **+77** | +88 | +54 | **100%** | 52 | +3.5 | 💎 |
| 6 | **ZigZag Break** | **+22** | +179 | -322 | **68%** | 447 | +1.0 | ⚠️ |
| 7 | ER Trend | +69 | +105 | -35 | 94% | 140 | +3.1 | ✅ |
| 8 | RSI MA Confirm | +88 | +180 | -91 | 91% | 120 | +4.0 | ✅ |
| 9 | Dual Signal | +21 | +187 | -287 | 55% | 217 | +1.0 | ❌ |

## Top 3 Definitivas (100% robustas, PnL > +150 OOS)

| Estrategia | Parametros | OOS | pts/dia | WR | Trades | DNA |
|-----------|-----------|-----|---------|----|--------|-----|
| **Channel Breakout** | TP=2.0, SL=1.0, HSC=1, TH=20, 9-17h | **+455** | **+20.7** | 77.5% | 249 | Breakout |
| **ATR Surge** | TP=2.0, SL=1.0, HSC=1, TH=5, 9-17h | **+189** | **+8.2** | 68.6% | 194 | Volatilidade |
| **Vol Breakout** | TP=6.0, SL=1.0, HSC=3, TH=10, 9-17h | **+160** | **+7.3** | 69.9% | 93 | Volatilidade |

## Total de Testes
- ~30 estrategias testadas
- ~500.000 combinacoes de parametros
- ~1.500 validacoes OOS com tick engine
- 3 estrategias de alto PnL e 100% robustas
