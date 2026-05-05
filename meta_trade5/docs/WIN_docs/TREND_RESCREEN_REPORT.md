# Relatorio: Anomalia TUESDAY + TREND Rescreen com Filtro de Horario

**Data:** 2026-05-03

---

## 1. Anomalia PA_TUESDAY_RANGE_SELL — Artefato Estatistico Confirmado

### Evidencias

| Metrica | Valor | Interpretacao |
|---------|-------|---------------|
| PnL total | +36,820 | Aparentemente excelente |
| **PnL dia 14/04** | **+37,862** | **103% do PnL total** |
| PnL sem 14/04 | +158 | Praticamente zero |
| Trades no dia 14/04 | 16 de 40 (40%) | Concentracao extrema |
| Mediana PnL | +7.5 pts | 50% dos trades ganham quase nada |
| Top 10% trades | +13,379 | 35% do PnL total |
| Hit type SL | 26/40 (65%) | Maioria stopada |
| Hit type TP | 14/40 (35%) | Minoria acerta |

### O que aconteceu

**Um unico dia (terca 14/04) gerou +37,862 pts.** Sem esse dia, a estrategia e basicamente zero (+158 pts em 24 trades).

No dia 14/04, 16 trades TODOS entre 11:40 e 18:15, com 13 TP positivos consecutivos de +1,734 a +3,350 pts. Isso foi um movimento direcional unico e irrepetivel.

### Por que SL=0.05 "funcionou"

Com SL=0.05 (provavelmente multiplicado por ATR ~100 = 5 pts efectivos):
- **Perdas sao minusculas:** A maioria dos SL sai entre -50 e -290 pts (incluindo custo)
- **Ganhos sao enormes:** Quando acerta, TP=3.0 * ATR = ~+3,000 pts
- **R:R real:** ~60:1 (violacao massiva do cap de 10)
- **Na pratica:** O stop e atingido instantaneamente em qualquer micro-movimento contrario. O backtest nao simula slippage real para stops tao apertados.

### Conclusao

**TUESDAY_RANGE_SELL e overfit puro.** Depende de:
1. Um unico dia anomalo
2. Stops fisicamente impossiveis de executar (5 pts de stop com 30 pts de custo)
3. Efeito calendario sem guardrail de dia da semana

---

## 2. Filtro de Horario Implementado

### Mudanca no codigo

**Arquivo:** `scripts/orchestrator_v65.py`, linha 433-436

```python
# V7.4: Time filter for TREND signals (9:30-12:00)
hm_val = 9.5 if regime == 'trend' else 0.0
hx_val = 12.0 if regime == 'trend' else 24.0
net, n = f1_eval(sub_M, sub_closes, sub_ep, sub_atr,
                 sub_entry_idx, sub_hour, tp, sl,
                 hm=hm_val, hx=hx_val, atr_min=atr_mn,
                 direction=s['signal'])
```

- TREND signals: F1 roda apenas 9:30-12:00 (hm=9.5, hx=12.0)
- RANGE/HYBRID: Sem filtro (hm=0, hx=24)

---

## 3. Resultados do F1 Rescreen (TREND SELL, 9:30-12h)

**20 sinais TREND SELL testados. TODOS deram F1 positivo.**

| Rank | Sinal | F1 Net (9:30-12h) | Prev OOS | Delta | TP | SL | Trades F1 |
|------|-------|:-----------------:|:--------:|:-----:|:--:|:--:|:---------:|
| 1 | PA_SIGNAL_DIR_TREND_SELL | +124,690 | -842 | **+125,532** | 1.5 | 5.0 | 54 |
| 2 | PA_HMA_CROSS_F5_S10_TREND_SELL | +124,690 | -1,884 | **+126,574** | 1.5 | 5.0 | 54 |
| 3 | PA_ADX_BREAK_A25_TREND_SELL | +109,030 | -3,786 | **+112,816** | 1.5 | 5.0 | 47 |
| 4 | PA_CHOP_C38_2_TREND_SELL | +99,790 | -283 | **+100,073** | 5.0 | 5.0 | 40 |
| 5 | PA_VWAP_Z_Z2_0_TREND_SELL | +92,535 | +1,759 | **+90,776** | 2.5 | 5.0 | 46 |
| 6 | PA_BB_M2_0_TREND_SELL | +90,325 | +3,446 | **+86,879** | 2.5 | 5.0 | 37 |
| 7 | PA_KELT_M2_0_TREND_SELL | +90,325 | -1,354 | **+91,679** | 2.5 | 5.0 | 37 |
| 8 | PA_EFF_RATIO_E0_6_TREND_SELL | +61,650 | -5,611 | **+67,261** | 1.5 | 5.0 | 29 |
| 9 | COMBO_VOL_REVERSION_TREND_SELL | +60,220 | -399 | **+60,619** | 2.5 | 5.0 | 28 |
| 10 | PA_TUESDAY_TREND_SELL | +48,390 | +1,014 | **+47,376** | 1.5 | 4.0 | 23 |

### Padroes observados

1. **TP curto funciona em TREND:** Top 3 usam TP=1.5 (vs TP=2.5-5.0 anterior)
2. **SL=5.0 e o padrao:** Maioria dos tops usa SL=5.0 (floor de 0.5x ATR)
3. **Todos melhoraram:** 19/20 sinais melhoraram vs OOS anterior
4. **Trade count baixo:** 30-50 trades no F1 (periodo de 1 mes) — esperado para janela de 2.5h

### Alerta

**F1 nao tem custo real, slippage, ou guardrails.** Esses numeros sao "brutos". O que importa e o OOS com ticks reais. Precisamos rodar F2/F3/OOS para validar.

---

## 4. Validacao F2/F3/OOS (Top 5 TREND Signals)

**Pipeline:** F2 (IS ticks reais) -> Guardrail Sweep (BE/HP/CD) -> OOS (ticks reais Abril)

| # | Sinal | F2 IS Net | F2 WR | F2 Sharpe | OOS Net | OOS WR | OOS Sharpe | Status |
|---|-------|:---------:|:-----:|:---------:|:-------:|:------:|:----------:|:------:|
| 1 | PA_SIGNAL_DIR_TREND_SELL | **+45,337** | 72.9% | **10.81** | **-2,878** | 49.2% | 0.26 | **FAIL** |
| 2 | PA_HMA_CROSS_F5_S10_TREND_SELL | **+45,019** | 72.8% | **10.58** | **-3,860** | 48.8% | -0.05 | **FAIL** |
| 3 | PA_ADX_BREAK_A25_TREND_SELL | **+35,812** | 73.1% | **9.32** | **-4,089** | 46.5% | -0.39 | **FAIL** |
| 4 | PA_CHOP_C38_2_TREND_SELL | **+74,796** | 81.0% | **11.46** | **-2,247** | 18.8% | -0.89 | **FAIL** |
| 5 | PA_VWAP_Z_Z2_0_TREND_SELL | **+102,050** | 81.8% | **16.89** | **-3,134** | 38.9% | -0.64 | **FAIL** |

### Padrao: Overfit Extremo

Todos os 5 sinais mostraram **overfit massivo:**
- **F2 IS:** +35K a +102K, WR 73-82%, Sharpe 9-17 (resultados "perfeitos")
- **OOS:** TODOS negativos (-2K a -4K), Sharpe proximo de zero ou negativo
- **Stress (COST=60):** -2.7K a -7.5K (ainda pior)

### O que aconteceu

O filtro de horario 9:30-12h no F1 **overfitou ao periodo de treino (Fevereiro)**:

1. **F1 usa last prices sampleados** (15/candle), sem slippage real
2. **Fevereiro 2026 teve um regime favoravel** para esses sinais na manha
3. **Abril 2026 (OOS) e um regime diferente** — os mesmos sinais falham
4. **TP=1.5 e curto demais** para capturar movimentos reais com ticks bid/ask

### Conclusao

**Filtro de horario 9:30-12h sozinho NAO resolve o problema de TREND signals.**

Os sinais TREND continuam sem edge real no OOS. O que parecia milagroso no F1 (+124K) virou derrota no OOS (-2.8K).

---

## 5. Conclusoes e Proximos Passos

### O que aprendemos

1. **TUESDAY_RANGE_SELL e artefato estatistico** — depende de 1 dia anomalo + stops impossiveis
2. **Filtro de horario nao e suficiente** — TREND signals overfitam mesmo com janela restrita
3. **F1 sem ticks reais e perigoso** — numeros de +100K no F1 viram -3K no OOS
4. **TP=1.5 e curto demais** para ticks reais (bid/ask spread + slippage)

### Recomendacao

**Manter ensemble SELL-only atual (V7.3) — nao adicionar TREND signals.**

Os unicos sinais validados com OOS positivo continua sendo:
- RANGE signals (TUESDAY_RANGE excluido por artefato)
- HYBRID signals
- EXHAUST_TREND (WFA 3/3 — unico TREND com robustez confirmada)

### Proximos Passos

1. [ ] **Reverter filtro de horario no F1** ou tornar opcional (nao hardcoded)
2. [ ] **Focar em RANGE/HYBRID signals** — sao os unicos com OOS positivo consistente
3. [ ] **Investigar EXHAUST_TREND** — por que e o unico TREND com WFA 3/3?
4. [ ] **Se quiser TREND:** Testar com TP maior (3.0-5.0) e menos trades no F1

---

## Arquivos

| Arquivo | Descricao |
|---------|-----------|
| `scripts/trend_f1_rescreen.py` | Script de rescreen F1 para TREND |
| `docs/WIN_docs/trend_f1_rescreen_results.csv` | Resultados F1 |
| `scripts/trend_f2f3oos_validator.py` | Script de validacao F2/F3/OOS |
| `docs/WIN_docs/trend_f2f3oos_validation.csv` | Resultados OOS |
| `scripts/analyze_tuesday.py` | Analise da anomalia TUESDAY |
