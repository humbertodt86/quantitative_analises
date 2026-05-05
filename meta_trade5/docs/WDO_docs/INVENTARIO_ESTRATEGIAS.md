# Inventario de Estrategias WDO - V5.1
**Pipeline:** 132.000 combos F1 (Fev) -> Top 50 F2 (IS) -> Top 3 F3 (OOS)
**17 estrategias, custo 1.2 pts/trade**

## Ranking Final (F3 OOS)

| # | Estrategia | Variante | TP | SL | F3_net | WR | PF | Trades |
|---|-----------|----------|----|----|--------|----|----|--------|
| 1 | PA_REV_RSI | PA_REV_RSI_S70 | 12.0 | 2.00 | +376 | 22.5% | 1.15 | 311 |
| 2 | PA_KELT | PA_KELT_M1_0 | 8.0 | 2.00 | +318 | 24.1% | 1.12 | 287 |
| 3 | PA_BB | PA_BB_M1_5 | 8.0 | 2.00 | +142 | 23.4% | 1.08 | 265 |
| 4 | PA_VWAP_Z | PA_VWAP_Z_Z1_0 | 10.0 | 1.50 | +110 | 22.8% | 1.06 | 255 |
| 5 | PA_TSI | PA_TSI_T15 | 12.0 | 0.05 | +44 | 21.5% | 1.03 | 195 |
| 6 | PA_VWAP_REV | PA_VWAP_REV_D0_3 | 12.0 | 2.00 | +17 | 22.1% | 1.01 | 182 |
| 7 | PA_MFI | PA_MFI_B30 | 12.0 | 0.05 | +3 | 22.0% | 1.00 | 155 |
| 8 | PA_GK_BREAK | PA_GK_BREAK_G0_0005 | 10.0 | 0.20 | -599 | 19.7% | 0.95 | 275 |
| 9 | PA_CHOP | PA_CHOP_C50 | 12.0 | 2.00 | -712 | 20.1% | 0.94 | 289 |
| 10 | PA_HMA_CROSS | PA_HMA_CROSS_F9_S20 | 12.0 | 2.00 | -789 | 19.5% | 0.92 | 301 |
| 11 | PA_SIGNAL_DIR | PA_SIGNAL_DIR | 12.0 | 2.00 | -1072 | 17.8% | 0.88 | 315 |
| 12 | PA_ADX_BREAK | PA_ADX_BREAK_A20 | 10.0 | 0.05 | -522 | 20.3% | 0.91 | 245 |
| 13 | PA_EFF_RATIO | PA_EFF_RATIO_E0_4 | 12.0 | 2.00 | -488 | 21.2% | 0.90 | 265 |
| 14 | PA_EXHAUST | PA_EXHAUST_Dn1_0_M50 | 12.0 | 2.00 | -275 | 21.5% | 0.96 | 235 |
| 15 | PA_MA_CROSS | PA_MA_CROSS_F5_S13 | 6.0 | 0.05 | -235 | 22.0% | 0.94 | 215 |

## Observacoes
- WDO tem menos tendencia que WIN, resultados OOS sao marginalmente positivos
- PA_REV_RSI (RSI2 > 70) e a melhor estrategia (+376 pts)
- Guardrails (BE, Grace, Cooldown) podem melhorar significativamente o resultado liquido
- Periodo OOS: 30 Mar a 28 Abr 2026
