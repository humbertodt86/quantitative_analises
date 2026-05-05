# Propostas de Novas Estrategias e Indicadores — WIN M5 (V5.0)

## 1. Estrategias Adicionais (Novos Regimes)

### A. Microestrutura e Liquidez

**Liquidity Grab (Stop Run)**
- Rompimento falso de máxima/mínima anterior seguido de reversão rápida com aumento de volume
- "Pega carona" na liquidez institucional que limpou stops do varejo
- Sinal: PA_LIQUIDITY_GRAB

**Order Book Imbalance (Static)**
- Disparidade entre volume de ordens de compra vs. venda nos 5 primeiros níveis do book
- Sinal: PA_BOOK_IMBALANCE

**Absorption at S/R**
- Preço atinge S/R, volume sobe drasticamente, mas preço não desloca
- "Baleia" absorvendo fluxo → reversão iminente
- Sinal: PA_ABSORPTION

### B. Leilão (Market Profile)

**POC Reversion (Point of Control)**
- POC = preço de maior volume negociado no dia anterior
- Preço tende a ser "atraído" para esse nível em dias laterais
- Sinal: PA_POC_REV

**Value Area Fill**
- Se preço abre fora da Value Area (70% volume dia anterior) e retorna, tende a atravessar toda a área
- Sinal: PA_VA_FILL

### C. Estatísticas e Volatilidade

**Volatility Contraction (VCP — Mark Minervini)**
- Amplitude dos candles diminui (mola comprimida) antes de rompimento explosivo
- Sinal: PA_VCP

**Mean Reversion Z-Score**
- Distanciamento do preço vs VWAP em desvios padrão (2.5-3.0σ)
- Similar ao PA_VWAP_Z existente mas com thresholds mais extremos

## 2. Indicadores Adicionais

### A. Momentum e Força

**Hull Moving Average (HMA)**
- Mais rápida e menos lag que EMA/SMA
- Sinaliza mudanças de direção de micro-tendência sem ruído do ADX
- Colunas: HMA_FAST (9), HMA_SLOW (20), HMA_SIGNAL (cruzamento)

**True Strength Index (TSI)**
- Oscilador de momentum com médias duplas
- Sobrecompra/sobrevenda com maior precisão direcional
- Colunas: TSI, TSI_SIGNAL

**Efficiency Ratio (Kaufman)**
- Mede "ruído" do movimento: 1 = linha reta, 0 = ziguezague
- Filtro para Hunter (tendência)
- Colunas: EFF_RATIO (10), EFF_RATIO_20

### B. Volume e Fluxo

**Cumulative Volume Delta (CVD)**
- Diferença acumulada entre agressão de compra e venda
- Revela se movimento é sustentado por agressão real
- Colunas: CVD, CVD_SMA, CVD_DIVERGENCE

**On-Balance Volume (OBV) Slope**
- Inclinação do OBV confirma rompimentos antes do preço
- Rompimento com OBV lateral = bull trap
- Colunas: OBV, OBV_SLOPE, OBV_DIVERGENCE

**Money Flow Index (MFI)**
- RSI que considera volume. Mais robusto que RSI puro para WIN.
- Colunas: MFI14, MFI21

### C. Volatilidade e Canais

**Keltner Channels**
- Superior a Bollinger em mercados de tendência (usa ATR para largura)
- Colunas: KELT_UPPER, KELT_LOWER, KELT_BASE, KELT_WIDTH

**Choppiness Index**
- Baseado em Fibonacci, define mercado em tendência (baixo) vs consolidação (alto)
- Liga/desliga robôs de range
- Colunas: CHOP_INDEX, CHOP_ZONE (0=range, 1=trend)

## 3. Sugestão de Sinais (Draft V5.0)

| Categoria | Sinal/Coluna | Lógica |
|-----------|-------------|--------|
| Contexto | MARKET_EFFICIENCY | Efficiency Ratio (Kaufman) para filtrar tendência |
| Fluxo | DELTA_ACCUM | Cumulative Volume Delta (CVD) intradiário |
| Volatilidade | ATR_STRETCH | Preço atual vs (VWAP ± 2.5*ATR) |
| Exaustão | VOL_SPIKE | Volume atual > 3x média últimos 20 candles |
| Estrutura | DIST_TO_POC | Distância em pontos até o POC do dia anterior |

## 4. Pipeline de Teste

Para cada novo sinal/estratégia:
```
1. Adicionar indicador ao build_continuous_indicators.py
2. Recalcular super_win_continuous.parquet
3. F1 (Fevereiro, 15k combos) → top 50
4. F2 (Jan-Mar IS, last-only) → top 3
5. F3 (Mar30-Abr29 OOS, bid/ask) → resultado final
```

## 5. Categorias Existentes + Novas

### EXISTENTES (14 sinais)
1. REVERSAO À MÉDIA: PA_REV_RSI, PA_VWAP_REV, PA_BB, PA_BB_SQZ, PA_EXHAUST, PA_MA_CROSS
2. TENDENCIA/MOMENTUM: PA_SIGNAL_DIR, PA_STRONG_TREND, PA_ADX_BREAK, PA_GK_BREAK, PA_RIB_TREND, PA_SLOPE_TREND
3. SNIPER/EXAUSTÃO: PA_SIGNAL_REV

### NOVAS CATEGORIAS (propostas)
4. MICROESTRUTURA: PA_LIQUIDITY_GRAB, PA_BOOK_IMBALANCE, PA_ABSORPTION
5. LEILÃO (MP): PA_POC_REV, PA_VA_FILL
6. VOLATILIDADE: PA_VCP
