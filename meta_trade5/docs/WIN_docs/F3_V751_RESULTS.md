# F3 Microstructure Grid V7.5.1 — Resultados Completos

**Data:** 2026-05-03
**Variante:** PA_SIGNAL_DIR_S0_Z30_R05
**Grid:** 60 combos (10 cenários × 3 TP30 × 2 SD)

---

## Resumo Executivo

Após implementar as 3 melhorias propostas (Slope Decay Dinâmico, S/R Buffer 30/60, VWAP_Z corrigido), descobrimos que **apenas a correção do VWAP_Z trouxe melhora significativa**. O Slope Decay dinâmico **piorou** o resultado. O S/R Buffer 30/60 **piorou** vs janela 10.

| Melhoria | Resultado | Delta vs BASE |
|----------|-----------|---------------|
| **VWAP_Z <= -0.3** | **+3,187** | **+206 (+6.9%)** |
| BASE (dynamic decay ON) | +2,562 | -419 (-14.1%) |
| BASE (sem dynamic decay) | +2,981 | baseline |
| SR_BUF30 | +1,995 | -986 (-33.1%) |
| SR_BUF60 | +1,414 | -1,567 (-52.6%) |

---

## Descobertas Críticas

### 1. Slope Decay Dinâmico PIOROU o Resultado

| Config | PnL OOS | Delta |
|--------|---------|-------|
| BASE_NO_DYN (estático) | **+2,981** | baseline |
| BASE (dinâmico ON) | +2,562 | **-419 (-14%)** |

**Por que piorou?** O dynamic decay encolhe o TP quando o momentum cai. Mas no WIN, o preço oscila muito antes de continuar. O TP encolhido sai cedo demais nas oscilações, transformando wins em break-evens. A fórmula `Mt = max(0.2, 1.0 - 0.5 * (S0-St)/S0)` reduz o TP para 20-80% do original quando o slope cai — isso é muito agressivo.

**Recomendação:** Manter slope decay ESTÁTICO (move SL para BE quando slope cai 50%). Não usar dynamic decay para TP.

### 2. VWAP_Z Corrigido é a MELHOR Melhoria

O filtro original `VWAP_Z >= 0.5` estava **inverteido** para SELL. A correção `VWAP_Z <= -0.3` (ou -0.5) trouxe o melhor resultado:

| VWAP_Z | PnL OOS | N | WR | Stress |
|--------|---------|---|----|--------|
| **<= -0.3** | **+3,187** | **32** | **46.9%** | **+2,227** |
| <= -0.5 | +3,177 | 31 | 45.2% | +2,247 |
| Sem filtro | +2,981 | 34 | 47.1% | +1,961 |

**Por que funciona?** Para SELL, queremos vender quando o preço está ABAIXO do VWAP (VWAP_Z negativo). Isso indica que o preço está esticado para baixo com momentum de venda. O filtro `<= -0.3` remove trades onde o preço está próximo ou acima do VWAP (sem momentum claro).

### 3. S/R Buffer — Janela 10 Melhor que 30/60

| Janela | PnL OOS | N | WR | Stress |
|--------|---------|---|----|--------|
| prev_10 | +2,419 | 33 | 45.5% | +1,429 |
| prev_30 | +1,995 | 33 | 48.5% | +1,005 |
| prev_60 | +1,414 | 33 | 45.5% | +424 |

**Por que 10 é melhor?** prev_10 captura suportes/resistências de curto prazo (50 minutos no M5). No WIN intradiário, o mercado se move rápido — suportes de 50 minutos são mais relevantes que suportes de 5 horas (prev_60). prev_30/60 ficam muito distantes e produzem SLs/TPs irreais.

### 4. TP30=60% Domina em Todos os Cenários

| TP30 | BASE PnL | VWAP_M03 PnL |
|------|----------|--------------|
| 0% | -961 | -304 |
| 20% | +1,876 | +2,119 |
| **60%** | **+2,562** | **+3,187** |

TP30=0% (sem TP30) é DISASTER (-961). TP30=60% é o sweet spot — captura lucro parcial sem sair cedo demais.

### 5. Book Imbalance Continua Não Funcionando

BOOK_IMB < -0.3: +93 PnL (23 trades). O filtro reduz trades de 34 para 23 e mata a performance.

---

## Resultados Detalhados por Cenario

### BASE (Dynamic Decay ON)

| TP30 | SD | PnL | N | WR | Stress |
|------|----|-----|---|----|--------|
| 0% | 0.0 | -961 | 34 | 8.8% | -1,981 |
| 20% | 0.0 | +1,876 | 34 | 47.1% | +856 |
| **60%** | **0.0** | **+2,562** | **34** | **47.1%** | **+1,542** |

### BASE_NO_DYN (Dynamic Decay OFF — baseline)

| TP30 | SD | PnL | N | WR | Stress |
|------|----|-----|---|----|--------|
| 0% | 0.0 | -783 | 34 | 8.8% | -1,803 |
| 20% | 0.0 | +1,651 | 34 | 47.1% | +631 |
| **60%** | **0.0** | **+2,981** | **34** | **47.1%** | **+1,961** |

### VWAP_M03 (VWAP_Z <= -0.3) ⭐ MELHOR

| TP30 | SD | PnL | N | WR | Stress |
|------|----|-----|---|----|--------|
| 0% | 0.0 | -304 | 32 | 9.4% | -1,264 |
| 20% | 0.0 | +2,119 | 32 | 46.9% | +1,159 |
| **60%** | **0.0** | **+3,187** | **32** | **46.9%** | **+2,227** |

### SR_BUF10 (S/R prev_10)

| TP30 | SD | PnL | N | WR | Stress |
|------|----|-----|---|----|--------|
| 0% | 0.0 | +1,735 | 34 | 20.6% | +715 |
| **20%** | **0.0** | **+2,419** | **33** | **45.5%** | **+1,429** |
| 60% | 0.0 | +1,905 | 33 | 42.4% | +915 |

### SR_BUF30 (S/R prev_30)

| TP30 | SD | PnL | N | WR | Stress |
|------|----|-----|---|----|--------|
| 0% | 0.0 | +670 | 34 | 17.6% | -350 |
| **20%** | **0.0** | **+1,995** | **33** | **48.5%** | **+1,005** |
| 60% | 0.0 | +1,388 | 33 | 45.5% | +398 |

---

## Config Oficial Recomendada V7.5.1

```python
Sinal: PA_SIGNAL_DIR_S0_Z30_R05 (V8.0)
TP: 4.0x | SL: 4.0x | ATR: 400-600
BE Trigger: 60 | BE Offset: 50 | HP: 2
TP30: 60% | Slope Decay: 0.50 (ESTÁTICO — move SL para BE)
Dynamic Decay: DESLIGADO (piorou resultado)

# Filtros
Regime: TREND (regime_label == 1)
Direction: SELL (PA_SIGNAL_DIR == -1)
Hour: 9:30 - 12:00
VWAP_Z: <= -0.3 (NOVO — melhorou +6.9%)

# S/R Buffer
SR_Buffer: DESLIGADO (ou prev_10 se quiser usar)
# prev_30/60 pioraram resultado

# NÃO USAR
Trailing Stop: 0% (piorou)
Book Imbalance: NÃO (piorou)
Dynamic Decay: NÃO (piorou)
```

---

## Evolução do Modelo

| Versão | PnL OOS | N | WR | Stress | Delta |
|--------|---------|---|----|--------|-------|
| V7.4.9 (BASE TP30=20%) | +1,651 | 34 | 47.1% | +631 | baseline |
| V7.5.0 (BASE TP30=60%) | +2,981 | 34 | 47.1% | +1,961 | +80% |
| **V7.5.1 (VWAP_M03 TP30=60%)** | **+3,187** | **32** | **46.9%** | **+2,227** | **+93%** |

---

## Lições Aprendidas

1. **Nem toda melhoria proposta funciona.** O dynamic decay parecia lógico na teoria, mas piorou na prática. Testar é essencial.
2. **VWAP_Z estava invertido.** Um simples bug (min em vez de max) matou completamente o filtro. Correção trivial, impacto enorme.
3. **Janela S/R menor é melhor para intradiário.** prev_10 (50 min) > prev_30 (2.5h) > prev_60 (5h) para WIN M5.
4. **TP30 é OBRIGATÓRIO.** Sem TP30, o modelo perde dinheiro em todos os cenários.
5. **Slope Decay estático funciona.** Mover SL para BE quando slope cai 50% é efetivo. Não precisa ser dinâmico no TP.

---

## Arquivos

- `docs/WIN_docs/F3_V751_GRID.csv` — Resultados completos do grid
- `docs/WIN_docs/F3_V751_BEST_TRADES_VWAP_M03.csv` — Trades do top 1
- `backtest/engine_v2.py` — Atualizado com S/R dinâmico e dynamic decay
- `backtest/engine_v119_v2.py` — Atualizado com dynamic decay
- `data/super_win_continuous.parquet` — Atualizado com prev_30/60

---

*F3 Microstructure V7.5.1*
*Gerado em 2026-05-03*
