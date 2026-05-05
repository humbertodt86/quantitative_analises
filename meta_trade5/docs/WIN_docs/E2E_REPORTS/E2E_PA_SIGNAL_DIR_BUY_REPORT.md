# Relatorio E2E — PA_SIGNAL_DIR BUY
## Validacao F1 → F2 → F3 | Periodo: Fev-Abr 2026

**Data:** 2026-05-04  
**Signal:** PA_SIGNAL_DIR (s0_z4p0_r0p5)  
**Direction:** BUY  
**Config:** TP=15.0 | SL=5.0 | ATR=[100-600]

---

## 1. RESUMO EXECUTIVO

| Fase | Periodo | Trades | PnL | WR | Profit Factor | Status |
|------|---------|--------|-----|----|---------------|--------|
| **F1** (Full Scan) | Fev 2026 (IS) | 827 | **+745,182** | 39.7% | — | ✅ Pre-filtro |
| **F2** (Busca) | Fev 2026 (IS) | 7 | **+6,632** | 28.6% | 1.70 | ✅ Validacao IS |
| **F3** (OOS) | Abr 2026 (OOS) | 14 | **-8,818** | 14.3% | 0.60 | ⚠️ Prejuizo OOS |

**Conclusao:** A estrategia funcionou no periodo IS (Fev) mas **falhou no OOS** (Abr). 
- F1 superestima drasticamente (745K vs 6K real)
- F2 mostra o verdadeiro potencial IS (+6.6K com 7 trades)
- F3 OOS mostra que a estrategia **nao generaliza**

**Recomendacao:** Nao usar esta config para producao. Buscar configs mais robustas no F1 (menor TP, maior WR).

---

## 2. F1 — FULL SCAN (Pre-Filtro)

### Top 5 Configs (BUY)

| Rank | Variant | TP | SL | ATR_MIN | ATR_MAX | PnL | Trades | WR |
|------|---------|----|----|---------|---------|-----|--------|----|
| 1 | s0_z4p0_r0p5 | 15.0 | 5.0 | 100 | 600 | **+745,182** | 827 | 39.7% |
| 2 | s0_z2p5_r0p5 | 15.0 | 5.0 | 100 | 600 | **+728,188** | 812 | 39.7% |
| 3 | s0_z4p0_r0p5 | 15.0 | 5.0 | 50 | 800 | **+727,528** | 840 | 39.0% |
| 4 | s0_z2p5_r0p5 | 15.0 | 5.0 | 150 | 600 | **+727,325** | 782 | 40.2% |
| 5 | s10_z4p0_r0p5 | 15.0 | 5.0 | 150 | 600 | **+726,511** | 769 | 40.3% |

### Observacoes F1
- **Todas as top configs usam TP=15.0** (borda do grid) — sinal de overfitting
- **WR baixo (~40%)** — mais perdedores que vencedores
- **PnL inflacionado** — F1 nao tem guardrails, superestima resultados
- **SL=5.0 em todas** — borda do grid, precisa expandir

---

## 3. F2 — VALIDACAO IS (Modo Busca)

### Resultado com Melhor Config do F1

| Metrica | Valor |
|---------|-------|
| Trades | 7 |
| PnL | +6,632 |
| WR | 28.6% |
| Profit Factor | 1.70 |
| Duracao Media | 245 candles |
| Duracao Max | 839 candles |

### Trades Individuais (F2)

| # | Entrada | Saida | Tipo | PnL | Duracao | ATR |
|---|---------|-------|------|-----|---------|-----|
| 1 | 02/02 09:15 | 11/02 13:15 | TP | **+7,995** | 839c | 535 |
| 2 | 11/02 13:20 | 12/02 13:20 | SL | -1,575 | 113c | 309 |
| 3 | 12/02 14:35 | 12/02 15:20 | SL | -1,603 | 9c | 315 |
| 4 | 12/02 16:10 | 13/02 09:00 | SL | -1,501 | 27c | 294 |
| 5 | 13/02 12:25 | 25/02 09:00 | TP | **+8,070** | 589c | 540 |
| 6 | 25/02 09:45 | 26/02 10:30 | SL | -2,950 | 122c | 584 |
| 7 | 26/02 10:55 | 26/02 12:20 | SL | -1,803 | 17c | 355 |

### Padroes Observados (F2)
- **Trades vencedores:** Duracao MUITO longa (714c media), ganhos grandes (+8000)
- **Trades perdedores:** Duracao curta (58c media), perdas controladas (-1887)
- **WR baixo (28.6%)** compensado por **Profit Factor bom (1.70)**
- **Risco:** Trades ficam abertos por semanas (839 candles = ~7 dias)

---

## 4. F3 — VALIDACAO OOS (Abril 2026)

### Resultado

| Metrica | Valor |
|---------|-------|
| Trades | 14 |
| PnL | **-8,818** |
| WR | 14.3% |
| Profit Factor | 0.60 |
| Duracao Media | 129 candles |

### Top 5 Trades (OOS)

| # | Entrada | Saida | Tipo | PnL | Duracao |
|---|---------|-------|------|-----|---------|
| 1 | 02/04 10:30 | 08/04 09:00 | TP | **+6,645** | 321c |
| 2 | 08/04 12:10 | 14/04 09:00 | TP | **+6,399** | 310c |
| 3 | 17/04 17:05 | 22/04 09:10 | SL | -944 | 131c |
| 4 | 22/04 14:25 | 23/04 10:40 | SL | -1,076 | 68c |
| 5 | 17/04 13:20 | 17/04 15:50 | SL | -1,103 | 30c |

### Bottom 5 Trades (OOS)

| # | Entrada | Saida | Tipo | PnL | Duracao |
|---|---------|-------|------|-----|---------|
| 14 | 08/04 09:40 | 08/04 11:55 | SL | **-2,952** | 27c |
| 13 | 14/04 09:05 | 17/04 11:50 | SL | **-2,755** | 372c |
| 12 | 01/04 09:10 | 02/04 09:00 | SL | **-2,713** | 111c |
| 11 | 22/04 10:15 | 22/04 11:35 | SL | **-2,103** | 16c |
| 10 | 23/04 14:55 | 24/04 11:50 | SL | **-2,092** | 76c |

### Analise OOS
- **WR caiu de 28.6% (IS) para 14.3% (OOS)** — metade do desempenho
- **Profit Factor caiu de 1.70 para 0.60** — de positivo para negativo
- **Abril teve mais volatilidade** — SLs maiores e mais frequentes
- **Estrategia nao generaliza** — overfitting ao periodo IS

---

## 5. ANALISE DE DNA

### 5.1 Distribuicao por Hora (F2 IS)

| Hora | Trades | PnL Total | PnL Medio | Duracao Media |
|------|--------|-----------|-----------|---------------|
| 9h | 2 | +5,045 | +2,523 | 480c |
| 10h | 1 | -1,803 | -1,803 | 17c |
| 12h | 1 | +8,070 | +8,070 | 589c |
| 13h | 1 | -1,575 | -1,575 | 113c |
| 14h | 1 | -1,603 | -1,603 | 9c |
| 16h | 1 | -1,501 | -1,501 | 27c |

**Insight:** Entradas as 9h e 12h tiveram melhor resultado. Entradas a tarde (14h-16h) foram ruins.

### 5.2 Distribuicao por Dia da Semana (F2 IS)

| Dia | Trades | PnL Total | PnL Medio | Duracao Media |
|-----|--------|-----------|-----------|---------------|
| Segunda | 1 | +7,995 | +7,995 | 839c |
| Terca | 0 | 0 | 0 | 0 |
| Quarta | 2 | -4,525 | -2,262 | 118c |
| Quinta | 3 | -4,908 | -1,636 | 18c |
| Sexta | 1 | +8,070 | +8,070 | 589c |

**Insight:** Segunda e Sexta foram positivas. Quarta e Quinta foram negativas.

### 5.3 Distribuicao por Tipo de Saida (F2 IS)

| Tipo | Trades | PnL Total | PnL Medio | Duracao Media |
|------|--------|-----------|-----------|---------------|
| TP | 2 | +16,065 | +8,033 | 714c |
| SL | 5 | -9,433 | -1,887 | 58c |

**Insight:** Apenas 2 TP em 7 trades (28.6%), mas ganhos foram 4x maiores que perdas.

### 5.4 Distribuicao por ATR (Quartis) (F2 IS)

| Quartil | Faixa ATR | Trades | PnL Total | PnL Medio |
|---------|-----------|--------|-----------|-----------|
| Q1 | 294-309 | 2 | -3,076 | -1,538 |
| Q2 | 309-315 | 2 | -3,406 | -1,703 |
| Q3 | 315-535 | 1 | +7,995 | +7,995 |
| Q4 | 535-584 | 2 | +5,120 | +2,560 |

**Insight:** ATR medio-alto (Q3-Q4) teve melhor resultado. ATR baixo (Q1-Q2) foi negativo.

---

## 6. COMPARACAO F1 vs F2 vs F3

| Aspecto | F1 (IS) | F2 (IS) | F3 (OOS) |
|---------|---------|---------|----------|
| **Trades** | 827 | 7 | 14 |
| **PnL** | +745K | +6.6K | -8.8K |
| **WR** | 39.7% | 28.6% | 14.3% |
| **Guardrails** | Nenhum | Nenhum | Nenhum |
| **Dados** | 15 samples | OHLC | OHLC (proxy) |
| **Realista** | Nao | Sim | Sim |

### Diferenca F1 → F2
- F1 superestima **112x** o PnL (745K vs 6.6K)
- F1 tem **118x** mais trades (827 vs 7)
- F1 **nao reflete a realidade** — serve apenas como pre-filtro

### Diferenca F2 → F3
- WR caiu **50%** (28.6% → 14.3%)
- PnL virou de **positivo para negativo**
- Estrategia **nao generaliza** para novos dados

---

## 7. LIÇOES APRENDIDAS

### 7.1 Problemas desta Config
1. **TP=15.0 é muito alto** — trades ficam abertos por semanas
2. **WR muito baixo** — 28.6% IS, 14.3% OOS
3. **Overfitting ao Fev** — Abril teve comportamento diferente
4. **F1 superestima** — 112x mais PnL que o real

### 7.2 O que Buscar no F1
- **WR > 50%** no F1 (para ter margem quando cair no F2/F3)
- **TP entre 1.0-4.0** — mais realista, trades mais curtos
- **PnL F1 moderado** — configs com 50K-100K são mais realistas
- **Backtest F2 antes de confiar** — sempre validar com F2

### 7.3 Processo Recomendado
1. F1: Filtrar configs com WR > 50%, TP < 5.0, PnL 50K-100K
2. F2: Validar top 10 — descartar se WR < 40% ou PF < 1.2
3. F3: Validar top 3 em OOS — descartar se PnL < 0
4. Guardrails: Otimizar BE/Grace/CD apenas para configs que passam F3

---

## 8. PROXIMOS PASSOS

1. **Buscar configs mais conservadoras no F1**
   - TP entre 1.0-4.0
   - WR > 50% no F1
   - SL < 3.0

2. **Re-rodar F2 com configs conservadoras**
   - Verificar se WR > 40% no F2
   - Verificar se PF > 1.2

3. **Validar em OOS (Abril)**
   - Rodar F3 com as melhores configs F2
   - Confirmar que generalizam

4. **Otimizar guardrails**
   - BE/Grace/CD apenas para configs validadas
   - Melhorar ainda mais o desempenho

---

**Relatorio gerado:** 2026-05-04  
**Arquivos:**
- F1: `docs/WIN_docs/F1_V87_TEST_PA_SIGNAL_DIR.csv`
- F2: `docs/WIN_docs/E2E_REPORTS/E2E_PA_SIGNAL_DIR_s0_z4p0_r0p5_BUY.csv`
- F3: Script `scripts/f3_oos_validation.py`
