# Cycle Plan v7: V7.1 Completo — V7.2 Em Andamento

## V7.0 — COMPLETADO

### O que foi feito
1. Criadas 5 novas colunas BUY no super_win_continuous.parquet
2. Testados 16 sinais BUY (exaustao em RANGE, HYBRID, TREND)
3. Corrigido bug critico no F1 fast screener (hardcoded SELL only)
4. Gerados relatorios V70_BUY_RECOVERY_REPORT.md e validated_buy_signals.json

### Resultado
- 0 sinais BUY validados
- Vies estrutural de short confirmado no WIN (Abr/2026)

---

## V7.1 — COMPLETADO

### O que foi feito
1. Testados 30 sinais (15 BUY + 15 SELL) com indicadores de exaustao
2. Implementado Walk-Forward Analysis (WFA) no F2: 3 folds mensais
3. Adicionado PnL mensal detalhado no rank F2 (jan_net, feb_net, mar_net)
4. Coleta unificada de trades F3 (V71_UNIFIED_TRADES_F3.csv)
5. Corrigido import csv em save_unified_f3_trades

### Resultado
- 4 novos sinais SELL validados
- 0 sinais BUY validados (0/15)
- 1 sinal com WFA robustez=3/3 (PA_EXHAUST_Dn1_0_M40_TREND_SELL)

### Arquivos Gerados
- V71_MASTER_REPORT.md
- V71_WFA_COMPARATIVE_REPORT.md
- V71_UNIFIED_TRADES_F3.csv

---

## V7.2 — COMPLETADO

### Objetivo
Construir ensemble SELL-only final com os 24 sinais validados, priorizando WFA e OOS.

### Concluido
1. [x] Extrair todos os sinais validados de cycle_memory.json (26 total)
2. [x] Classificar por OOS net e WFA robustez
3. [x] Gerar V72_ENSEMBLE_FINAL_REPORT.md
4. [x] Atualizar ensemble_priority_list.json (11 sinais, 3 tiers)
5. [x] Atualizar docs/progress.md e docs/cycle_plan.md
6. [x] Remover colunas BUY do parquet (193→188 colunas)
7. [x] Analisar 9 sinais faltantes — todos UNTESTABLE

### Analise dos 9 Sinais Faltantes
| Sinais | Razao |
|--------|-------|
| ESTOCASTICO (3) + IFR (3) | Colunas BUY-only removidas, sem base equivalente |
| VWAP_REV_D1_0_TREND_SELL | ZERO entradas em TREND (só RANGE/HYBRID) |
| EXHAUST_TREND_BUY + VWAP_REV_TREND_BUY | BUY abandoned |

**Conclusao:** Nenhum sinal SELL adicional é testável. Ensemble final = 11 sinais.

### Arquivos Gerados
- V72_ENSEMBLE_FINAL_REPORT.md
- V72_MISSING_SIGNALS_CLOSURE.md
- ensemble_priority_list.json (atualizado)

---

## V7.3 — COMPLETADO: CSV Unificado + Analise de Sobreposicao

### Objetivo
Gerar arquivo CSV com trades OOS de TODOS os modelos (~158) e analisar complementaridade.

### Concluido
1. [x] Inventario completo: 158 estrategias no ciclo_memory
2. [x] CSV unificado gerado: ALL_MODELS_OOS_TRADES.csv (7,513 trades, 95 estrategias)
3. [x] Analise de sobreposicao: 4,465 pares, 1,000+ com zero overlap
4. [x] Relatorio gerado: TRADE_OVERLAP_ANALYSIS_REPORT.md (atualizado)
5. [x] Scripts: generate_unified_all_models.py, analyze_trade_overlap.py
6. [x] Correcao do engine: _simulate_exit_ohlc para simulacao sem ticks
7. [x] Reexecutados 73 modelos, total 95 com trades validos

### Insights da Analise
- **Redundancia intra-familia extrema:** VWAP_Z (259% simultaneidade), TSI (276%)
- **1,000+ pares complementares:** sem NENHUMA sobreposicao
- **Recomendacao:** 1 variante por familia no ensemble

---

## V7.3.1 — COMPLETADO: Ensemble PnL Optimizer

### Objetivo
Simular combinacoes 2/3/4 estrategias com regra SELECTOR e identificar ensemble de maior PnL combinado.

### Concluido
1. [x] Simular 1,711 pares — top: +30,780 PnL
2. [x] Simular 1,710 trios — top: +37,023 PnL
3. [x] Simular 840 quartetos — top: +43,189 PnL (+17% vs melhor single)
4. [x] Gerar ENSEMBLE_OPTIMIZATION_REPORT.md
5. [x] Salvar CSVs: ensemble_pairs/triples/quadruples_results.csv

### Ensemble Recomendado (V7.4)
- PA_TUESDAY_RANGE_SELL + PA_VCP_HYBRID_SELL + PA_KELT_M2_0_RANGE + PA_EXHAUST_Dn1_0_M40_TREND_SELL
- PnL: +43,189 | Trades: 90 | Sharpe: 3.51 | MaxDD: -2,232

---

## V7.4 — COMPLETADO: TREND Recovery + Analise DNA + Deploy

### Objetivo
Validar TREND signals com filtro de horario 9:30-12h, analisar DNA do ensemble e reavaliar deploy.

### Concluido
1. [x] Filtro de horario 9:30-12h implementado no F1 para TREND signals
2. [x] F1 rescreen de 20 TREND SELL signals — TODOS positivos
3. [x] F2/F3/OOS validacao para top 5 TREND signals (ticks reais) — TODOS falharam
4. [x] Analise DNA do Ensemble Quad (TUESDAY+VCP+KELT+EXHAUST) — 90 trades
5. [x] Conclusao: TREND signals overfitam; ensemble atual mantem-se

### Resultado
- F1 IS TREND: +35K a +102K (overfit)
- OOS TREND: TODOS negativos (-2K a -4K)
- Ensemble DNA: +40,590 (90t, WR 24.4%), horarios 12-14h toxicos, TUESDAY/KELT com SL impossivel

### Proximos Passos
- [ ] Reverter filtro de horario no F1 ou tornar opcional
- [ ] Testar EXHAUST_TREND com TP=3-5, SL=1-2, ATR>=400 (unico TREND realista)
- [ ] Paper trading / deploy MT5 com ensemble V7.3 (sem TUESDAY/KELT?)
- [ ] Monitoramento de decay

---

## V7.3.3 — COMPLETADO: Ensemble Alternativas + Monte Carlo

### Concluido
1. [x] Comparar 3 configuracoes alternativas de ensemble
2. [x] Monte Carlo para cada alternativa
3. [x] Original Quad mantem superioridade (Sharpe 3.51, Risk 5.2%)

---

## Checklist Geral

- [x] V7.0: BUY recovery (completo, 0 validados)
- [x] V7.1: Exhaustion rescan + WFA (completo, 4 validados)
- [x] V7.2: Ensemble build (completo, 11 sinais)
- [x] V7.2: Parquet cleanup (completo, 193→188 colunas)
- [x] V7.3: CSV unificado + Analise de sobreposicao (completo, 95/158 estrategias)
- [x] V7.3: Corrigir reexecucao dos 120 modelos faltantes (completo, 73 reexecutados)
- [x] V7.3.1: Ensemble optimizer 2/3/4 (completo, ensemble recomendado identificado)
- [x] V7.3.2: Ensemble alternativas + Monte Carlo (completo)
- [x] V7.4.1: Filtro de horario TREND + F1 rescreen (completo, 20/20 positivos)
- [ ] V7.4.2: F2/F3/OOS validacao top TREND signals
