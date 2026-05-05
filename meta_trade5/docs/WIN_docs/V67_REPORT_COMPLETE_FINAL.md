# V6.7 Relatorio Final Completo — BUY + SELL + Ensemble SELECTOR

**Data:** 2026-05-02 23:01
**Total estrategias testadas:** 126 (63 BUY + 63 SELL)
**Sinais validados:** 27 (6 BUY + 21 SELL)
**Engine:** V139+ com modo SELECTOR (threshold=0, min_votes=1)
**Custo:** 30 pts/trade (WIN)

---

## Sumario Executivo

| Metrica | Valor |
|---------|-------|
| Melhor OOS (BUY) | +0 pts (PA_POC_REV_TREND) |
| Melhor OOS (SELL) | +36,820 pts (PA_TUESDAY_RANGE_SELL) |
| Melhor OOS (Global) | +36,820 pts |
| Validados BUY | 6 |
| Validados SELL | 21 |

---

## Sinais Validados BUY

| # | Estrategia | Regime | OOS Net | WR | Trades | Peso |
|---|-----------|--------|---------|-----|--------|------|
| 1 | PA_POC_REV_TREND | trend | +0 | 0.0% | 0 | 1.44 |
| 2 | PA_MFI_B20_TREND | trend | +0 | 0.0% | 0 | 0.50 |
| 3 | PA_TSI_T25_TREND | trend | +0 | 0.0% | 0 | 2.00 |
| 4 | PA_LIQ_GRAB_TREND | trend | +0 | 0.0% | 0 | 2.00 |
| 5 | PA_MFI_B20_HYBRID | hybrid | +0 | 0.0% | 0 | 0.63 |
| 6 | PA_TSI_T25_HYBRID | hybrid | +0 | 0.0% | 0 | 1.82 |

---

## Sinais Validados SELL

| # | Estrategia | Regime | OOS Net | WR | Trades | Peso |
|---|-----------|--------|---------|-----|--------|------|
| 1 | PA_TUESDAY_RANGE_SELL | range | +36,820 | 50.0% | 40 | 2.00 |
| 2 | PA_TUESDAY_HYBRID_SELL | hybrid | +33,795 | 38.3% | 47 | 2.00 |
| 3 | PA_VCP_HYBRID_SELL | hybrid | +12,399 | 46.5% | 43 | 2.00 |
| 4 | PA_TSI_T25_HYBRID_SELL | hybrid | +9,532 | 54.0% | 87 | 2.00 |
| 5 | PA_VCP_TREND_SELL | trend | +7,647 | 50.0% | 14 | 2.00 |
| 6 | PA_VCP_RANGE_SELL | range | +7,043 | 45.2% | 31 | 2.00 |
| 7 | PA_ADX_BREAK_A25_HYBRID_SELL | hybrid | +6,092 | 53.6% | 69 | 2.00 |
| 8 | PA_VWAP_REV_D1_0_RANGE_SELL | range | +5,747 | 41.1% | 56 | 2.00 |
| 9 | PA_VWAP_REV_D1_0_HYBRID_SELL | hybrid | +5,747 | 41.1% | 56 | 2.00 |
| 10 | PA_EXHAUST_Dn1_0_M40_TREND_SELL | trend | +4,399 | 42.1% | 19 | 2.00 |
| 11 | PA_REV_RSI_B15_RANGE_SELL | range | +3,854 | 54.0% | 126 | 2.00 |
| 12 | PA_VWAP_Z_Z2_0_RANGE_SELL | range | +2,968 | 49.3% | 138 | 2.00 |
| 13 | PA_REV_RSI_B15_HYBRID_SELL | hybrid | +2,685 | 52.8% | 180 | 2.00 |
| 14 | PA_POC_REV_RANGE_SELL | range | +1,943 | 58.8% | 68 | 2.00 |
| 15 | PA_ADX_BREAK_A25_RANGE_SELL | range | +1,280 | 53.1% | 32 | 2.00 |
| 16 | PA_MA_CROSS_F9_S21_TREND_SELL | trend | +1,232 | 40.0% | 20 | 2.00 |
| 17 | PA_REV_RSI_B15_TREND_SELL | trend | +898 | 60.0% | 85 | 1.80 |
| 18 | PA_TSI_T25_RANGE_SELL | range | +590 | 39.5% | 38 | 1.18 |
| 19 | PA_VWAP_Z_Z2_0_HYBRID_SELL | hybrid | +314 | 47.6% | 164 | 0.63 |
| 20 | PA_BB_M2_0_HYBRID_SELL | hybrid | +190 | 56.8% | 44 | 0.50 |
| 21 | PA_KELT_M2_0_HYBRID_SELL | hybrid | +190 | 56.8% | 44 | 0.50 |

---

## Top 10 Estrategias Globais

| Rank | Estrategia | Direcao | OOS Net | WR | Trades |
|------|-----------|---------|---------|-----|--------|
| 1 | PA_TUESDAY_RANGE | SELL | +36,820 | 50.0% | 40 |
| 2 | PA_TUESDAY_HYBRID | SELL | +33,795 | 38.3% | 47 |
| 3 | PA_VCP_HYBRID | SELL | +12,399 | 46.5% | 43 |
| 4 | PA_TSI_T25_HYBRID | SELL | +9,532 | 54.0% | 87 |
| 5 | PA_VCP_TREND | SELL | +7,647 | 50.0% | 14 |
| 6 | PA_VCP_RANGE | SELL | +7,043 | 45.2% | 31 |
| 7 | PA_ADX_BREAK_A25_HYBRID | SELL | +6,092 | 53.6% | 69 |
| 8 | PA_VWAP_REV_D1_0_RANGE | SELL | +5,747 | 41.1% | 56 |
| 9 | PA_VWAP_REV_D1_0_HYBRID | SELL | +5,747 | 41.1% | 56 |
| 10 | PA_EXHAUST_Dn1_0_M40_TREND | SELL | +4,399 | 42.1% | 19 |

---

## Insights

1. **SELL domina:** 21 SELL vs 6 BUY validados
2. **Melhor global:** PA_TUESDAY_RANGE_SELL com +36,820 pts
3. **SELECTOR mode:** Ativado no engine (threshold=0, min_votes=1)
4. **Recomendacao:** Focar em SELL, especialmente PA_TUESDAY e PA_VCP

---

*Gerado pelo pipeline V6.7*