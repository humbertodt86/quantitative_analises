# Guia de Ciclos — Pipeline de Otimizacao WIN

**Versao:** V7.5.0
**Atualizado:** 2026-05-03

---

## Visao Geral

O pipeline de otimizacao segue 6 fases sequenciais, de discovery a deploy. Cada fase tem objetivo, entrada, saida e criterio de passagem.

```
FASE 0: Signal Discovery     -> Ranking de sinais por regime
FASE 1: F1 Fast Screener     -> 200K+ combos/seg (vetorizado)
FASE 2: F2 Validation        -> Tick-level IS (top 10 F1)
FASE 3: F3 Guardrails        -> Grid BE/HP/TP30/SD (top 3 F2)
FASE 4: Microstructure       -> Filtros BOOK_IMB/VWAP/SR (F3 expandido)
FASE 5: OOS Final            -> Tick-level OOS (dados nunca vistos)
FASE 6: WFA                  -> Walk-Forward Analysis (3 folds)
FASE 7: DNA Analysis         -> Analise trade a trade
FASE 8: Deploy               -> MT5 + Monitoramento
```

---

## FASE 0: Signal Discovery

**Objetivo:** Encontrar sinais PA_ promissores por regime (TREND, RANGE, HYBRID)

**Entrada:** `data/super_win_continuous.parquet`
**Saida:** Ranking de sinais por Sharpe/PnL
**Script:** `scripts/signal_discovery.py`

**Criterio de passagem:**
- Sinal com WR > 35% e N > 50 em pelo menos 1 regime

---

## FASE 1: F1 Fast Screener

**Objetivo:** Pre-filtrar 200K+ combinacoes de parametros rapidamente

**Entrada:** Cache Fev (`data/_fev_cache_v2.npz`) ou IS completo
**Saida:** Top 10 configs por sinal
**Script:** `scripts/f1_fast_screener.py` ou `scripts/f1_screen_signal_dir_variants.py`

**Grid F1:**
- TP: [1.0, 2.0, 3.0, 4.0, 5.0]
- SL: [1.0, 2.0, 3.0, 4.0, 5.0]
- ATR_MIN: [100, 200, 300, 400]
- ATR_MAX: [400, 600, 800, 1000]
- COST: 30 pts (simulado)

**Criterio de passagem:**
- PnL IS > 0
- WR > 35%
- N > 20

**Regras que EU SEMPRE ESQUECO:**
- F1 NAO tem guardrails (sem BE, HP, CD, TP30)
- F1 usa last prices sampleados (15/candle), NAO bid/ask
- F1 NAO filtra hora
- F1 serve APENAS como pre-filtro

---

## FASE 2: F2 Validation

**Objetivo:** Validar top 10 F1 com ticks reais (IS)

**Entrada:** Top 10 configs F1 + `data/WIN_merged_all.parquet` (ticks IS)
**Saida:** Top 3 configs validadas
**Script:** `scripts/f2_validate_signal_dir_variants.py`

**Criterio de passagem:**
- PnL IS > 0 (tick-level)
- WR > 35%
- Stress (C=60) > -1000

---

## FASE 3: F3 Guardrails

**Objetivo:** Otimizar guardrails (BE, HP, TP30, Slope Decay)

**Entrada:** Top 3 configs F2
**Saida:** Config otimizada com guardrails
**Script:** `scripts/f3_guardgrid_signal_dir.py`

**Grid F3 (basico):**
- BE Trigger: [60, 80, 100, 150]
- BE Offset: [25, 50]
- HP: [1, 2]
- Cooldown: [0, 2]
- TP30: [0.20, 0.30, 0.40]
- Slope Decay: [0.50]

**Criterio de passagem:**
- PnL OOS > 0
- WR > 35%
- Stress (C=60) > -500

---

## FASE 4: Microstructure (NOVO V7.5.0)

**Objetivo:** Testar filtros avancados de microestrutura

**Entrada:** Config F3 otimizada
**Saida:** Config com/sem filtros microestrutura
**Script:** `scripts/f3_microstructure_grid.py` / `scripts/f3_v751_grid.py`

**Filtros testados:**
- Book Imbalance (BOOK_IMB < -0.3 para SELL) — **NAO FUNCIONOU**
- VWAP_Z (`<= -0.3` para SELL) — **FUNCIONOU (+7%)**
- S/R Buffer (tp_sr_pct=0.3, sl_sr_pct=0.5) — **FUNCIONOU parcialmente**

**ATENCAO — Lições V7.5.1:**
- VWAP_Z para SELL deve ser **NEGATIVO** (`{'max': -0.3}`), nao positivo. Filtro invertido mata o sinal.
- S/R Buffer com prev_10 (50 min) funciona melhor que prev_30/60 para WIN intradiário.
- Slope Decay Dinâmico (recalcula TP a cada candle) **PIOROU** resultado. Manter estático (move SL para BE).

**Grid expandido:**
- TP30: [0%, 10%, 20%, 40%, 60%, 80%, 100%]
- Slope Decay: [0.0, 0.3, 0.5, 0.7, 1.0]

**Criterio de passagem:**
- PnL OOS > config F3 anterior
- N >= 20 (nao matar o trade count)

---

## FASE 5: OOS Final

**Objetivo:** Validar config final em dados NUNCA vistos

**Entrada:** Config final + `data/ticks/WIN*.parquet` (ticks OOS reais)
**Saida:** Relatorio OOS final
**Script:** Rodar `scripts/f3_guardgrid_signal_dir.py` com periodo OOS

**Periodo OOS:** 30/Mar a 29/Abr (ticks bid/ask REAIS)
**Criterio de passagem:**
- PnL OOS > 0
- WR > 35%
- Stress (C=60) > -500

---

## FASE 6: WFA (Walk-Forward)

**Objetivo:** Validar robustez temporal

**Entrada:** Config final
**Saida:** WFA report
**Metodo:** 3 folds mensais (Jan, Fev, Mar)
**Script:** `scripts/wfa_v751.py`

**Criterio de passagem:**
- 2+ folds positivos
- Media PnL/dia > 0

**Resultados V7.5.2 (executado):**
| Config | Jan | Fev | Mar | Total | +/3 | PnL/dia | Passou |
|--------|-----|-----|-----|-------|-----|---------|--------|
| BASE | +5,019 | +15,719 | +4,208 | +24,946 | 3/3 | +2,239.9 | SIM |
| VWAP_M03 | +5,019 | +15,719 | +5,328 | +26,066 | 3/3 | +2,273.3 | SIM |

**Observacoes:**
- Jan/Fev tiveram poucos trades (3-11) mas WR alto (90-100%).
- Mar foi mais ativo (57-60 trades, WR ~43-45%).
- Ambas passaram WFA. VWAP_M03 escolhida como oficial (melhor em Mar).

---

## FASE 7: DNA Analysis

**Objetivo:** Analise trade a trade para entender comportamento

**Entrada:** Trades do top 1 (salvos em CSV)
**Saida:** Relatorio DNA completo
**Script:** `scripts/dna_analysis_best_variant.py`

**Analises:**
- Impacto de cada guardrail (BE, TP30, Slope Decay)
- MFE/MAE por trade
- Duracao (candles held)
- Segmentacao por hora/dia

---

## FASE 8: Deploy

**Objetivo:** Deploy MT5 + monitoramento

**Entrada:** Config oficial validada
**Saida:** EA MT5 + dashboard

**Monitoramento:**
- DNA semanal (comparar com baseline)
- Alerta se WR cair abaixo de 30% por 2 semanas
- Alerta se PnL/dia < 0 por 5 dias consecutivos

---

## Checklist por Ciclo

- [ ] F0: Signal Discovery completo
- [ ] F1: Top 10 selecionados
- [ ] F2: Top 3 validados (tick-level IS)
- [ ] F3: Guardrails otimizados
- [ ] F4: Microestrutura testada
- [ ] F5: OOS validado (PnL > 0)
- [ ] F6: WFA passou (2+ folds positivos)
- [ ] F7: DNA analysis completo
- [ ] F8: Deploy MT5

---

## Arquivos do Pipeline

| Fase | Script | Output |
|------|--------|--------|
| F0 | `scripts/signal_discovery.py` | Ranking CSV |
| F1 | `scripts/f1_screen_signal_dir_variants.py` | `F1_SCREEN_SIGNAL_DIR_VARIANTS.csv` |
| F2 | `scripts/f2_validate_signal_dir_variants.py` | `F2_VALIDATION_SIGNAL_DIR_VARIANTS.csv` |
| F3 | `scripts/f3_guardgrid_signal_dir.py` | `F3_GUARDGRID_SIGNAL_DIR_S0_Z30_R05.csv` |
| F4 | `scripts/f3_microstructure_grid.py` | `F3_MICROSTRUCTURE_GRID.csv` |
| F5 | Manual (mesmo script F3, periodo OOS) | Relatorio OOS |
| F6 | `scripts/wfa_analysis.py` (a criar) | WFA report |
| F7 | `scripts/dna_analysis_best_variant.py` | `DNA_SIGNAL_DIR_S0_Z30_R05_REPORT.md` |
| F8 | MT5 EA | Live trading |

---

*Guia de Ciclos V7.5.0*
*Criado em 2026-05-03*
