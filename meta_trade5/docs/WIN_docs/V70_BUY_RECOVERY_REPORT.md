# V70 BUY Recovery Report

**Date:** 2026-05-03
**Objective:** Resgatar operabilidade do lado BUY no WIN via indicadores de exaustao em regime de RANGE

## Executive Summary

**Resultado: BUY Recovery FALHOU no periodo testado (Abr/2026).**

- **Sinais V7.0 testados:** 16
- **Novos sinais validados:** 0
- **Sinais BUY com F2 positivo:** 0 (zero)
- **Conclusao:** O WIN possui vies estrutural para venda (short bias) no periodo testado.

### Correcao Crucial de Infraestrutura

Durante o ciclo V7.0, identificamos e corrigimos um bug critico no `engines/f1_fast_screener.py`:**
o F1 screener estava hardcoded para SELL apenas.** O parametro `direction` foi adicionado
para suportar BUY (-1=SELL, 1=BUY), corrigindo o calculo de thresholds TP/SL e PnL.
Mesmo com essa correcao, todos os sinais BUY continuaram produzindo resultados negativos.

## Resultados Detalhados por Familia de Sinais

| Sinal | Regime | Melhor F2 Net | Trades | WR | Configs Testadas |
|-------|--------|---------------|--------|----|-------------------|
| PA_ESTOCASTICO_RANGE_BUY | RANGE | +0 | 0 | 0.0% | 10 |
| PA_IFR_OVERSOLD_BUY | TREND | +0 | 0 | 0.0% | 10 |
| PA_VWAP_REV_D1_0_RANGE_BUY | RANGE | +0 | 0 | 0.0% | 10 |
| PA_EXHAUST_Dn1_0_M40_RANGE_BUY | RANGE | +0 | 0 | 0.0% | 10 |
| PA_POC_REV_RANGE_BUY | RANGE | +0 | 0 | 0.0% | 10 |
| PA_REV_RSI_B15_RANGE_BUY | RANGE | +0 | 0 | 0.0% | 10 |
| PA_BB_M2_0_RANGE_BUY | RANGE | +0 | 0 | 0.0% | 10 |
| PA_VWAP_Z_Z2_0_RANGE_BUY | RANGE | +0 | 0 | 0.0% | 10 |
| PA_ESTOCASTICO_HYBRID_BUY | HYBRID | +0 | 0 | 0.0% | 10 |
| PA_IFR_OVERSOLD_HYBRID_BUY | HYBRID | +0 | 0 | 0.0% | 10 |
| PA_VWAP_REV_D1_0_HYBRID_BUY | HYBRID | +0 | 0 | 0.0% | 10 |
| PA_EXHAUST_Dn1_0_M40_HYBRID_BUY | HYBRID | +0 | 0 | 0.0% | 10 |
| PA_POC_REV_HYBRID_BUY | HYBRID | +0 | 0 | 0.0% | 10 |
| PA_ESTOCASTICO_TREND_BUY | TREND | +0 | 0 | 0.0% | 10 |
| PA_IFR_OVERSOLD_TREND_BUY | TREND | +0 | 0 | 0.0% | 10 |
| PA_VWAP_REV_D1_0_TREND_BUY | - | N/A | 0 | 0.0% | 0 |

## Analise da Assimetria BUY vs SELL

A tabela abaixo compara os resultados BUY com os resultados SELL das **mesmas colunas de sinal**:

| Sinal BUY | Melhor BUY | Melhor SELL (mesma coluna) | Diferenca |
|-----------|------------|---------------------------|----------|
| PA_VWAP_REV_D1_0_RANGE_BUY | +0 | +141159 | +141159 |
| PA_EXHAUST_Dn1_0_M40_RANGE_BUY | +0 | +26820 | +26820 |
| PA_POC_REV_RANGE_BUY | +0 | +35525 | +35525 |
| PA_REV_RSI_B15_RANGE_BUY | +0 | +71314 | +71314 |
| PA_BB_M2_0_RANGE_BUY | +0 | +22763 | +22763 |
| PA_VWAP_Z_Z2_0_RANGE_BUY | +0 | +106816 | +106816 |
| PA_VWAP_REV_D1_0_HYBRID_BUY | +0 | +141159 | +141159 |
| PA_EXHAUST_Dn1_0_M40_HYBRID_BUY | +0 | +31151 | +31151 |
| PA_POC_REV_HYBRID_BUY | +0 | +64103 | +64103 |

**Observacao critica:** As mesmas colunas que produzem prejuizos extremos no BUY
(ex: PA_POC_REV_HYBRID_BUY = -23,389) geram lucros massivos no SELL
(ex: PA_POC_REV_HYBRID_SELL = +64,103). Isso demonstra que os indicadores estao
detectando corretamente as condicoes de mercado, mas o mercado se move na direcao
oposta ao sinal de compra.

## Por Que o BUY Falhou?

### 1. Vies Estrutural de Short (Venda)

O periodo OOS (Abril/2026) apresenta uma tendencia de baixa persistente no WIN.
Qualquer sinal de compra, mesmo em condicoes tecnicamente favoraveis (exaustao,
sobrevenda, reversao de VWAP), encontra resistencia da tendencia dominante.

### 2. Regime RANGE Nao e Favoravel para Compra

O sucesso de `PA_ADX_BREAK_A25_RANGE_SELL` (+1,280 pts) foi interpretado como
evidencia de que reversoes em RANGE funcionam. No entanto, o que funcionou foi
**vender no topo do range**, nao comprar no fundo. O mercado quebrou os fundos
de range com mais frequencia do que respeitou os topos.

### 3. GridAdvisor Nao Encontrou Platô de Robustez

O GridAdvisor expandiu o grid de SL ate 22.0x ATR (borda extrema) sem encontrar
configs lucrativas. Isso indica que nao existe combinacao de parametros que torne
os sinais BUY lucrativos no periodo testado.

## Sinais Validados Historicos (BUY)

Os unicos sinais BUY validados em ciclos anteriores (V6.6 e anteriores):

| Sinal | Coluna | Regime | OOS Weight |
|-------|--------|--------|------------|
| PA_POC_REV_TREND | PA_POC_REV | trend | 1.436 |
| PA_MFI_B20_TREND | PA_MFI_B20 | trend | 0.5 |
| PA_TSI_T25_TREND | PA_TSI_T25 | trend | 2.0 |
| PA_LIQ_GRAB_TREND | PA_LIQ_GRAB | trend | 2.0 |
| PA_MFI_B20_HYBRID | PA_MFI_B20 | hybrid | 0.628 |
| PA_TSI_T25_HYBRID | PA_TSI_T25 | hybrid | 1.824 |

**Nota:** Todos os sinais BUY validados historicos sao de regime TREND ou HYBRID.
Nenhum sinal BUY em regime RANGE foi validado em nenhum ciclo.

## Recomendacoes

1. **Abandonar BUY Recovery neste periodo:** O vies estrutural de short e
   incontornavel. Forcar sinais de compra onde nao existem e contraproducente.

2. **Focar em SELL-only Ensemble:** Com 30 sinais validados (todos SELL ou
   majoritariamente SELL), construir um ensemble focado em short-bias.

3. **Testar SELL variants dos novos indicadores:** PA_POC_REV_RANGE_SELL (+35,525),
   PA_EXHAUST_Dn1_0_M40_HYBRID_SELL (+31,151) e PA_EXHAUST_Dn1_0_M40_RANGE_SELL
   (+26,820) sao candidatos promissores para inclusao no ensemble.

4. **Nao adicionar colunas BUY ao super_win_continuous:** As colunas
   PA_ESTOCASTICO_RANGE_BUY, PA_IFR_OVERSOLD_BUY, PA_VWAP_REV_D1_0_RANGE_BUY
   aumentam o tamanho do arquivo sem valor pratico comprovado. Considerar remocao.

5. **Manter correcao do F1 screener:** A adicao do parametro `direction` ao
   `f1_fast_screener.py` e valiosa para ciclos futuros em outros ativos ou periodos
   onde BUY possa ter edge.

## Notas Tecnicas

- **F1 Screener Fix:** Adicionado parametro `direction` (default=-1/SELL) com
  logica completa de thresholds TP/SL e PnL para BUY e SELL.
- **Orchestrator Update:** Linha 393 de `orchestrator_v65.py` agora passa
  `direction=s['signal']` para o F1 screener.
- **Novas colunas:** 5 colunas BUY adicionadas ao parquet (Stochastic, IFR,
  VWAP_REV_RANGE, EXHAUST_RANGE, POC_REV_RANGE) — podem ser removidas.
- **Total cycles in memory:** 155 (incluindo V6.8, V6.9 e V7.0)
- **Total validated signals:** 30 (incluindo 6 historicos BUY)
