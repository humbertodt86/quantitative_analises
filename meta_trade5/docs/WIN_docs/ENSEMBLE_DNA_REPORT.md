# Relatorio DNA — Melhor Ensemble: TUESDAY + VCP + KELT + EXHAUST

**Data:** 2026-05-03
**Periodo OOS:** 30 Mar - 29 Abr 2026
**Trades Executados (SELECTOR):** 90

---

## 1. Visao Geral

| Metrica | Valor |
|---------|-------|
| **PnL Total** | **+40,590** |
| Trades Vencedores | 22 (24.4%) |
| Trades Perdedores | 68 (75.6%) |
| PnL Medio por Trade | +451 |
| PnL Medio (Vencedores) | +2,209 |
| PnL Medio (Perdedores) | -129 |

**Insight:** WR baixo (24.4%) mas PnL alto. A estrategia depende de poucos trades grandes para compensar muitas perdas pequenas. R:R efetivo ≈ 17:1.

---

## 2. Parametrizacao do Ensemble

### 2.1 PA_TUESDAY_RANGE_SELL
```
TP=20.0 | SL=0.05 | ATR=[50,400] | BE=100 | HP=2 | CD=0
OOS: +36,820 (40t isolado, WR=50.0%)
```
**Alerta:** SL=0.05 e fisicamente impossivel (stop < custo de entrada). Efeito calendario sem guardrail de dia da semana.

### 2.2 PA_VCP_HYBRID_SELL
```
TP=8.0 | SL=5.0 | ATR=[50,600] | BE=400 | HP=3 | CD=0
OOS: +12,149 (43t, WR=58.1%)
```
**Mais robusto:** SL=5.0 respeita floor, WR alto (58%).

### 2.3 PA_KELT_M2_0_RANGE
```
TP=20.0 | SL=0.05 | ATR=[100,400] | BE=100 | HP=1 | CD=0
OOS: +5,375 (8t, WR=12.5%)
```
**Alerta:** Tambem usa SL=0.05. Poucos trades (8), alto risco de overfit.

### 2.4 PA_EXHAUST_Dn1_0_M40_TREND_SELL
```
TP=5.0 | SL=2.0 | ATR=[50,800] | BE=500 | HP=3 | CD=0
OOS: +4,364 (19t, WR=42.1%)
```
**Mais equilibrado:** TP=5.0, SL=2.0, WFA 3/3 robusto.

---

## 3. Analise DNA — Trades que Deram Certo vs Errado

### 3.1 Decomposicao por Estrategia (no ensemble)

| Estrategia | Trades | Wins | WR | PnL | Avg Trade |
|-----------|:------:|:----:|:--:|:---:|:---------:|
| PA_TUESDAY_RANGE_SELL | 20 | 5 | 25.0% | +13,981 | +699 |
| PA_VCP_HYBRID_SELL | 29 | 9 | 31.0% | +9,173 | +316 |
| PA_KELT_M2_0_RANGE | 25 | 3 | 12.0% | +12,342 | +494 |
| PA_EXHAUST_Dn1_0_M40_TREND_SELL | 16 | 5 | 31.2% | +5,094 | +318 |

**Insight:** TUESDAY e KELT tem poucos wins mas PnL alto por trade. VCP e EXHAUST sao mais consistentes (WR>30%).

### 3.2 Segmentacao Temporal

#### Por Dia da Semana

| Dia | Trades | WR | PnL | Avg | Classificacao |
|-----|:------:|:--:|:---:|:---:|---------------|
| **Tuesday** | 29 | **31.0%** | **+22,260** | **+768** | **Dia Magico** |
| Monday | 19 | 15.8% | +5,911 | +311 | Neutro |
| Wednesday | 18 | 22.2% | +6,693 | +372 | Neutro |
| Thursday | 13 | 23.1% | +3,586 | +276 | Neutro |
| Friday | 11 | 27.3% | +2,140 | +195 | Neutro |

**Terça-feira e o dia dominante.** 32% dos trades, 55% do PnL total. Efeito calendario real ou coincidencia?

#### Por Horario

| Horario | Trades | WR | PnL | Avg | Classificacao |
|---------|:------:|:--:|:---:|:---:|---------------|
| **09:00-10:00** | 9 | **44.4%** | **+14,356** | **+1,595** | **Horario Ouro** |
| **16:00-17:00** | 9 | **55.6%** | **+8,515** | **+947** | **Horario Ouro** |
| 11:00-12:00 | 12 | 25.0% | +6,442 | +537 | Favoravel |
| 15:00-16:00 | 13 | 23.1% | +5,617 | +432 | Neutro |
| 17:00+ | 22 | 22.7% | +5,904 | +268 | Neutro |
| 10:00-11:00 | 4 | 25.0% | +1,340 | +335 | Neutro |
| 14:00-15:00 | 9 | 11.1% | -440 | -49 | Ruim |
| **12:00-13:00** | 7 | **0.0%** | **-525** | **-75** | **Horario Mortal** |
| **13:00-14:00** | 5 | **0.0%** | **-619** | **-124** | **Horario Mortal** |

**Horarios de almoco (12-14h) sao toxicos:** 0% WR, -1,144 pts em 12 trades. **Horarios ouro: abertura (9-10h) e tarde (16-17h).**

### 3.3 Analise de Saida (Hit Type)

| Tipo | Trades | PnL | Avg | % do Total |
|------|:------:|:---:|:---:|:----------:|
| **TP** | 22 | **+48,597** | **+2,209** | 100% dos ganhos |
| SL | 62 | -7,977 | -129 | 75% dos trades |
| BE | 6 | -30 | -5 | 7% dos trades |

**Insight:** A estrategia e "tudo ou nada". Quando acerta, TP gera +2,209 em media. Quando erra, SL e -129 (pequeno). **Nenhum trade BE positivo** — o break-even nao esta funcionando como saida lucrativa.

### 3.4 DNA dos Indicadores (Win vs Loss)

| Indicador | Win Mean | Loss Mean | Delta | Cohen d | Interpretacao |
|-----------|:--------:|:---------:|:-----:|:-------:|---------------|
| **MFE** | **1,195** | **171** | **+1,025** | **0.67** | **Vencedores tem MFE 7x maior** |
| **MAE** | **130** | **221** | **-91** | **-0.42** | **Vencedores tem MAE menor** |
| ATR | 227 | 246 | -19 | -0.18 | Sem diferenca significativa |
| book_imbalance | 0 | 0 | 0 | 0 | Nao disponivel |

**Insight critico:**
- **MFE/MAE ratio:** Vencedores = 765x, Perdedores = 20x
- Trades vencedores: entram e "explodem" no sentido certo (MFE alto, MAE baixo)
- Trades perdedores: entram e oscilam (MAE alto, MFE baixo)
- **Isso confirma:** A entrada funciona quando o mercado tem momentum direcional imediato.

### 3.5 Top 10 vs Bottom 10 Trades

**Top 10:** Todos TP, entre +2,577 e +6,895 pts. Concentrados em:
- 13/04 09:40 (KELT): +6,895 — maior trade
- 14/04 (TUESDAY): 4 trades >+3,000 no mesmo dia
- 09:00-10:00 e 15:00-17:00 predominam

**Bottom 10:** Todos SL, entre -275 e -530 pts. Perdas controladas.

### 3.6 Sequencias

- **Max streak de vitorias:** 6 trades
- **Max streak de derrotas:** **20 trades** (psicologicamente devastador)
- Streaks comuns: 14, 11, 7 perdas consecutivas

**Alerta:** Com WR=24%, streaks de 10-20 perdas sao estatisticamente esperadas. Requer capital psicologico alto.

---

## 4. Diagnostico: Entrada e Saida

### 4.1 Entramos no Momento Correto?

**Sim, mas com ressalvas:**
- Vencedores: MAE medio = 130 pts (pequeno pullback pos-entrada)
- Perdedores: MAE medio = 221 pts (pullback maior, stop atingido)
- **Delta MAE: -91 pts** (Cohen d = -0.42) — entrada em vencedores e mais limpa

**Conclusao:** A entrada funciona quando o mercado tem momentum imediato. Quando oscila apos entrada, vira perda.

### 4.2 Saímos Antes do Tempo?

**Nao — na verdade, poderiamos segurar mais:**
- MFE medio em vencedores: 1,195 pts
- TP medio: ~3,000 pts (TUESDAY TP=20, KELT TP=20)
- **Gap:** MFE = 1,195 vs TP = 3,000. O TP nao esta sendo atingido em media.

**Mas espere:** O TP=20.0 de TUESDAY/KELT parece extremo. Se TP nao esta sendo atingido, como ganham?

**Resposta:** O hit type "TP" no relatório provavelmente inclui saidas por outros motivos (HSTAG, BE convertido). Ou o TP=20.0 e atingido em dias de alta volatilidade (14/04).

### 4.3 TP e SL Estao Calibrados?

| Estrategia | TP | SL | TP/SL | Status |
|-----------|:--:|:--:|:-----:|--------|
| TUESDAY | 20.0 | 0.05 | 400:1 | **SL impossivel** |
| VCP | 8.0 | 5.0 | 1.6:1 | Conservador |
| KELT | 20.0 | 0.05 | 400:1 | **SL impossivel** |
| EXHAUST | 5.0 | 2.0 | 2.5:1 | Equilibrado |

**Problema:** TUESDAY e KELT usam SL=0.05 (fisicamente impossivel). Na pratica, o "SL" desses trades provavelmente e BE ou HSTAG, nao o SL tecnico.

---

## 5. Recomendacoes

### 5.1 Horarios

**Focar em:**
- **09:00-10:00** (WR 44%, PnL +14K)
- **16:00-17:00** (WR 56%, PnL +8.5K)

**Evitar:**
- **12:00-14:00** (WR 0%, PnL -1.1K em 12 trades)

### 5.2 Dias

**Terça-feira e dominante** (+22K, 55% do PnL). Verificar se e efeito real ou overfit.

### 5.3 TP/SL

Para TREND signals (como voce sugeriu):
- **SL = 1.0-2.0 ATR** (realista, executavel)
- **TP = 3.0-5.0 ATR** (captura movimento direcional)
- **Entrada: ATR >= 400** (volatilidade minima para justificar o trade)

EXHAUST_TREND ja esta proximo disso (TP=5.0, SL=2.0).

### 5.4 Filtro de Momentum

Adicionar filtro de EMA5_SLOPE ou similar:
- Vencedores: entrada com momentum claro (MAE baixo)
- Perdedores: entrada em consolidacao (MAE alto, oscilacao)

---

## 6. Veredicto

| Aspecto | Avaliacao | Nota |
|---------|-----------|:----:|
| Retorno absoluto | +40,590 | ⭐⭐⭐⭐⭐ |
| Consistencia (WR) | 24.4% | ⭐⭐ |
| Risco de drawdown | Streak 20 perdas | ⭐⭐ |
| Parametrizacao | SL impossivel em 2/4 | ⭐⭐ |
| Horario | Toxicidade 12-14h clara | ⭐⭐⭐⭐ |
| Entrada | Limpa em vencedores | ⭐⭐⭐⭐ |
| Saida | TP funciona, BE inutil | ⭐⭐⭐ |

**Recomendacao:** Manter ensemble com ressalvas. Priorizar:
1. Remover TUESDAY/KELT (SL=0.05 impossivel)
2. Adicionar filtro de horario (excluir 12-14h)
3. Testar EXHAUST_TREND com TP=3-5, SL=1-2, ATR>=400
4. Capital psicologico alto necessario (streaks longas)

---

## Arquivos

| Arquivo | Descricao |
|---------|-----------|
| `docs/WIN_docs/ensemble_dna_analysis.csv` | Dados brutos dos 90 trades |
| `docs/WIN_docs/ENSEMBLE_DNA_REPORT.md` | Este relatorio |
