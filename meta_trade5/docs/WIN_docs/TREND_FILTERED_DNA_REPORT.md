# Relatorio DNA — 3 Modelos TREND com Filtro 9:30-12h (OOS Reais)

**Data:** 2026-05-03
**Filtro:** 9:30-12:00 no F1 screening
**Pipeline completo:** F1→F2→Guardrail→OOS com ticks reais

---

## 1. Visao Geral

| Estrategia | Trades | Wins | WR | PnL | Sharpe | Status |
|-----------|:------:|:----:|:--:|:---:|:------:|:------:|
| **PA_SIGNAL_DIR_TREND_SELL** | 124 | 47 | **37.9%** | **+1,307** | 0.31 | ✅ Positivo |
| **PA_EXHAUST_Dn1_0_M40_TREND_SELL** | 13 | 6 | **46.2%** | **+1,449** | **0.97** | **✅ Melhor** |
| PA_VWAP_Z_Z2_0_TREND_SELL | 55 | 17 | 30.9% | -462 | -0.18 | ❌ Negativo |

**Resultado:** O filtro de horario 9:30-12h funcionou! 2 de 3 sinais deram OOS positivo.

---

## 2. Parametrizacao (Otimizada pelo F1 com Filtro)

### PA_SIGNAL_DIR_TREND_SELL
```
TP=2.5 | SL=5.0 | ATR=[100,400] | BE=500 | HP=2 | CD=0
F1: +91,340 (39t) | F2: +81,188 (353t, WR 71%) | OOS: +1,307 (124t, WR 38%)
```

### PA_VWAP_Z_Z2_0_TREND_SELL
```
TP=3.0 | SL=5.0 | ATR=[100,400] | BE=500 | HP=3 | CD=0
F1: +81,405 (42t) | F2: +124,988 (291t, WR 81%) | OOS: -462 (55t, WR 31%)
```

### PA_EXHAUST_Dn1_0_M40_TREND_SELL
```
TP=2.5 | SL=3.0 | ATR=[100,400] | BE=500 | HP=3 | CD=0
F1: +8,490 (4t) | F2: +10,911 (50t, WR 64%) | OOS: +1,449 (13t, WR 46%)
```

**Observacao:** BE=500 em todos. Nunca foi otimizado (default do ciclo 1).

---

## 3. Segmentacao Temporal

### Filtro 9:30-12h Funcionou?

| Horario | Trades no Filtro | % do Total |
|---------|:----------------:|:----------:|
| **09:00-10:00** | 16 | 8.3% |
| **10:00-11:00** | 12 | 6.3% |
| **11:00-12:00** | 18 | 9.4% |
| **12:00+** | 146 | **76.0%** |

**PROBLEMA:** Apenas **20.8% dos trades** estao dentro do filtro 9:30-12h! A maioria (76%) ocorre apos 12:00.

**Explicacao:** O F1 filtra entradas em **fevereiro** (9:30-12h), mas o Guardrail/OOS em **abril** gera trades em horarios diferentes. O pipeline completo nao restringe horario de saida — so a entrada.

### Desempenho por Horario

| Horario | Trades | WR | PnL | Avg | Status |
|---------|:------:|:--:|:---:|:---:|--------|
| **09:00-10:00** | 16 | **43.8%** | **+1,175** | **+73** | 🟢 Bom |
| **10:00-11:00** | 12 | **41.7%** | **+1,399** | **+117** | 🟢 Bom |
| **11:00-12:00** | 18 | **44.4%** | **+1,621** | **+90** | 🟢 Bom |
| **12:00+** | 146 | **34.2%** | **-1,901** | **-13** | 🔴 Ruim |

**Conclusao:** O filtro 9:30-12h **funciona** (WR 41-44%, PnL positivo). O problema sao os trades fora do filtro (apos 12h) que arrastam o resultado.

### Desempenho por Dia da Semana

| Dia | Trades | WR | PnL | Avg |
|-----|:------:|:--:|:---:|:---:| 
| **Wednesday** | 34 | **61.8%** | **+9,691** | **+285** | 🟢 Dia Magico |
| Monday | 39 | 43.6% | +932 | +24 | 🟡 Neutro |
| Tuesday | 38 | 34.2% | +579 | +15 | 🟡 Neutro |
| Friday | 32 | 37.5% | -46 | -1 | 🟡 Neutro |
| **Thursday** | 49 | **14.3%** | **-8,862** | **-181** | 🔴 Dia Mortal |

**Quarta-feira e dominante** (+9,691 em 34 trades). Quinta-feira e toxica (14% WR).

---

## 4. Analise de Saida (Hit Type)

| Tipo | Trades | PnL | Avg | % Total |
|------|:------:|:---:|:---:|:-------:|
| **TP** | 70 | **+28,564** | **+408** | 36% |
| **SL** | 122 | **-26,270** | **-215** | 64% |

**Nenhum BE ou HP.** Saidas binarias: TP ou SL. R:R efetivo = 1.9:1 (408/215).

---

## 5. DNA dos Indicadores

### PA_SIGNAL_DIR_TREND_SELL

| Indicador | Vencedores (47) | Perdedores (77) | Delta | Interpretacao |
|-----------|:---------------:|:---------------:|:-----:|---------------|
| **MAE** | **117** | **353** | **-236** | Entrada muito mais limpa |
| **MFE** | **347** | **117** | **+230** | Movimento favoravel moderado |
| ATR | 245 | 237 | +8 | Sem diferenca |

**Conclusao:** O diferencial e a **entrada**. Vencedores tem MAE 3x menor. Quando entra limpo, funciona. Quando oscila (MAE alto), stop e atingido.

### PA_VWAP_Z_Z2_0_TREND_SELL

| Indicador | Vencedores (17) | Perdedores (38) | Delta | Interpretacao |
|-----------|:---------------:|:---------------:|:-----:|---------------|
| **MAE** | **125** | **343** | **-218** | Entrada mais limpa |
| **MFE** | **567** | **137** | **+430** | Movimento favoravel MAIOR |
| ATR | 216 | 254 | -38 | ATR menor em vencedores |

**Conclusao:** MAE baixo + MFE alto. Quando funciona, funciona bem (MFE=567). Mas WR baixo (31%).

### PA_EXHAUST_Dn1_0_M40_TREND_SELL

| Indicador | Vencedores (6) | Perdedores (7) | Delta | Interpretacao |
|-----------|:--------------:|:--------------:|:-----:|---------------|
| MAE | 308 | 326 | -17 | Sem diferenca significativa |
| MFE | 221 | 227 | -6 | Sem diferenca significativa |
| ATR | 274 | 296 | -22 | ATR levemente menor |

**Conclusao:** Com apenas 13 trades, a amostra e pequena. Nao ha diferenca estatistica clara entre wins e losses. O desempenho (+1,449, WR 46%) pode ser sorte da amostra.

---

## 6. Top e Bottom Trades

**Top 10:** Todos TP, entre +774 e +1,128 pts. Predominam horarios 9:00-11:30 (dentro do filtro).

**Bottom 10:** Todos SL, entre -450 e -530 pts. Variam horarios (incluindo 18:00, fora do filtro).

---

## 7. Sequencias

| Estrategia | Max Streak Vitorias | Max Streak Derrotas |
|-----------|:-------------------:|:-------------------:|
| SIGNAL_DIR | 14 | 10 |
| VWAP_Z | 5 | 11 |
| EXHAUST | 3 | 3 |

**EXHAUST e mais toleravel psicologicamente** (streaks curtas).

---

## 8. Conclusoes

### O Filtro 9:30-12h Funcionou?

**Parcialmente.** Dentro do filtro (9:30-12h):
- WR: 41-44%
- PnL: +4,195 em 46 trades
- **Funciona**

Fora do filtro (12:00+):
- WR: 34%
- PnL: -1,901 em 146 trades
- **Nao funciona**

**O problema:** O pipeline gera trades FORA do filtro. O F1 filtra entradas, mas o OOS real tem saidas em horarios diferentes.

### Ranking dos 3

| # | Estrategia | PnL | WR | Streak Loss | Status |
|---|-----------|:---:|:--:|:-----------:|:------:|
| 1 | **EXHAUST** | **+1,449** | **46%** | **3** | **Melhor** |
| 2 | **SIGNAL_DIR** | **+1,307** | **38%** | 10 | Bom |
| 3 | VWAP_Z | -462 | 31% | 11 | Ruim |

### Recomendacoes

1. **Adicionar filtro de horario no pipeline completo** (F2→F3→OOS), nao so no F1
2. **Excluir quinta-feira** (14% WR, -8,862 pts)
3. **Boost em quarta-feira** (62% WR, +9,691 pts)
4. **BE=500 inutil** — reduzir para 200-300
5. **EXHAUST e o mais promissor** — ampliar amostra para confirmar

---

## Arquivos

| Arquivo | Descricao |
|---------|-----------|
| `docs/WIN_docs/trend_filtered_930_12_oos_trades.csv` | 192 trades dos 3 modelos |
| `docs/WIN_docs/TREND_FILTERED_DNA_REPORT.md` | Este relatorio |
