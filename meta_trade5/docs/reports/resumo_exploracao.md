# Fim do Ciclo de Exploracao — 13 Estrategias Testadas Hoje

## Results

| # | Estrategia | OOS | WR | PF | Trades | Veredito |
|---|-----------|-----|----|----|--------|----------|
| 1 | **Channel Breakout (Donchian 5)** | **+455** | 77.5% | 7.73 | 249 | ✅✅ **MELHOR** |
| 2 | Volatility Breakout (ATR) | +160 | 69.9% | 2.88 | 93 | ✅✅ |
| 3 | Reversal (vmz<-4 + sl_sr=0.1) | +117 | 63.2% | 4.73 | 76 | ✅ |
| 4 | ORB Breakout | +88 | 76.9% | 7.77 | 52 | ✅ |
| 5 | ER Trend (Efficiency Ratio) | +23 | 62.1% | 2.26 | 140 | ⚠️ marginal |
| 6 | S/R sl_sr=0.1 (baseline) | +70 | 59.6% | 2.89 | 99 | ✅ |
| 7 | VWAP_Z<-2.5 | +55 | 72.4% | 2.67 | 58 | ✅ |
| 8 | 8-11h window | +67 | 59.0% | 3.09 | 78 | ✅ |
| -- | -- | -- | -- | -- | -- | -- |
| 9 | RVOL (Relative Volume) | -175 | 52.6% | 1.20 | 230 | ❌ |
| 10 | Narrow Range Breakout | -214 | 46.8% | 1.33 | 269 | ❌ |
| 11 | Inside Bar | -320 | 45.6% | 1.13 | 307 | ❌ |
| 12 | ADX Slope | -336 | 46.4% | 0.96 | 261 | ❌ |
| 13 | VWAP Weekly Trend | -356 | 51.6% | — | 626 | ❌ |
| 14 | MA Crossover | -58 | 53.5% | — | 101 | ❌ |
| 15 | Bollinger Band | -7 | 64.7% | — | 68 | ❌ |
| 16 | VA Breakout | IS -62 | 37.5% | — | — | ❌ |
| 17 | Gap+VWAP | 0 | — | — | 0 | 🔲 inativo |

## Top 3 Final

| Estrategia | Parametros | OOS | pts/dia |
|-----------|-----------|-----|---------|
| **Channel Breakout** | TP=2.0, SL=1.0, HSC=1, TH=20, 9-17h | **+455** | **+20.7** |
| Volatility Breakout | TP=6.0, SL=1.0, HSC=3, TH=10, 9-17h | +160 | +7.3 |
| ORB Breakout | TP=4.0, SL=0.7, HSC=1, TH=15, 10-16h | +88 | +4.0 |

## Combinacoes Hoje
- 5 estrategias no grid massivo (406k combos)
- 3 estrategias no grid medio (332k trades simulados)
- 3 estrategias menores (VWAP, BB, VA)
- 2 estrategias (Inside, Vol Break) 
- 5 estrategias (ADX, RVOL, Narrow, ER, GapVWAP)
- **Total: ~500k combinacoes, ~13 estrategias**

## Combinacoes Historicas
- ~15k (ciclos anteriores)
- ~500k (hoje)
- **Total: ~515k combinacoes**

Inventario atualizado em `docs/INVENTARIO_ESTRATEGIAS.md`
