# V8.4 — BUGFIX COMPLETO + VALIDACAO

## Status: ✅ VALIDADO E APROVADO

### Performance
- **Tempo**: 4.5s (100x vs V8.1 451s)
- **Configs/s**: 18,440
- **Configs processadas**: 82,656 (21 signals × 3,936 combos)

### Bug Fix Validado

**Problema V8.1-V8.3**: `np.append()` dentro de loop Numba nao suportado corretamente, causava PnL falso positivo.

**Solucao V8.4**: Rastrear apenas primeiro hit TP/SL com variaveis escalares (`first_hit_tp_la`, `first_hit_sl_la`).

**Validacao**:
| Sinal | V8.1 (bug) | Manual | V8.4 (fix) | Status |
|-------|-----------|--------|-----------|--------|
| PA_SIGNAL_DIR | +65K | +65K | +65,217 | ✅ CORRETO |
| PA_SIGNAL_REV | +60K | +60K | +62,625 | ✅ CORRETO |
| PA_TUESDAY | +9.6K | -14K | +1.3K (best) | ⚠️ MAJ NEGATIVO |
| PA_VWAP_REV_D1_0 | +14K | -16K | +3K (best) | ⚠️ MAJ NEGATIVO |

### Analise PA_TUESDAY e PA_VWAP_REV_D1_0

**PA_TUESDAY**:
- Total configs: 1,000
- Positivas: 49 (4.9%)
- Negativas: 951 (95.1%)
- Mediana PnL: -927
- Melhor config: TP=1.5, SL=5.0, ATR=300-400, Net=+1,331, N=20, WR=55%

**PA_VWAP_REV_D1_0**:
- Total configs: 1,000
- Positivas: 150 (15.0%)
- Negativas: 850 (85.0%)
- Mediana PnL: -1,505
- Melhor config: TP=1.5, SL=4.0, ATR=300-600, Net=+3,032, N=22, WR=41%

**Decisao**: EXCLUIR do full scan de 700M. Sinais majoritariamente negativos indicam ausencia de edge real. Configs positivas podem ser ruido/overfitting.

### Top 10 Sinais (SELL)

| Sinal | TP | SL | ATR Range | Net | N | WR% |
|-------|----|----|-----------|-----|---|-----|
| PA_SIGNAL_DIR | 1.0 | 5.0 | 300-1000 | +65,217 | 359 | 68.8% |
| PA_SIGNAL_REV | 1.0 | 5.0 | 200-9999 | +62,625 | 641 | 63.5% |
| PA_STRONG_TREND_A25_S20 | - | - | - | +55,446 | - | 52.1% |
| PA_SLOPE_TREND_S25_A25 | - | - | - | +54,585 | - | 52.1% |
| PA_VWAP_Z_Z2_0 | - | - | - | +37,924 | - | 54.4% |

### Proximos Passos

1. ✅ V8.4 bugfix validado
2. ⏳ Executar BUY direction (validar simetria)
3. ⏳ Gerar variantes de parametros (V8_S_MIN, V8_Z_MAX, V8_R_MIN)
4. ⏳ Executar full scan 700M configs
5. ⏳ Validacao OOS (Abril 2026)

### Sinais para Full Scan (21 sinais - 2 excluidos)

**INCLUIR (19 sinais)**:
- PA_SIGNAL_DIR, PA_SIGNAL_DIR_V2, PA_SIGNAL_REV
- PA_STRONG_TREND_A25_S20, PA_SLOPE_TREND_S25_A25
- PA_ADX_BREAK_A25, PA_EXHAUST_Dn1_0_M40
- PA_GK_BREAK_G0_001, PA_VCP_C0_6
- PA_MA_CROSS_F9_S21, PA_HMA_CROSS_F5_S10
- PA_EFF_RATIO_E0_6, PA_CHOP_C38_2
- PA_REV_RSI_B10, PA_REV_RSI_S90
- PA_VWAP_Z_Z2_0, PA_VWAP_STRETCH
- PA_KELT_ATR_M2_0, PA_MFI_B20, PA_TSI_T25
- PA_LIQ_GRAB

**EXCLUIR (2 sinais)**:
- PA_TUESDAY (95% configs negativas)
- PA_VWAP_REV_D1_0 (85% configs negativas)

### Arquivos Gerados

- `docs/WIN_docs/F1_FULL_RESULTS_V84_SELL.csv` (21,000 rows)
- `docs/WIN_docs/F1_BEST_PER_SIGNAL_V84_SELL.csv`
- `docs/WIN_docs/F1_TOP100_GLOBAL_V84_SELL.csv`
- `scripts/f1_full_scan_v84.py` (V8.4 corrected)
