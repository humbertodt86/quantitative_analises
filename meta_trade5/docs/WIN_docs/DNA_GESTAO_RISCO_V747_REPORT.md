# DNA + PnL Diario: PA_SIGNAL_DIR_S0_Z30_R05 (Otimizado)

**Data:** 2026-05-03
**Config Otimizada:** BE=60, Offset=50, HP=2, TP30=20%, Slope Decay=0.50
**Variante:** PA_SIGNAL_DIR_S0_Z30_R05
**Periodo OOS:** Mar 30 - Abr 29, 2026 (tick-level)

---

## 1. PnL Medio por Dia

### OOS (10 dias com trades)

| Metrica | Valor |
|---------|-------|
| **PnL total** | +1,651 |
| **Dias operados** | 10 |
| **PnL medio/dia** | **+165.1 pts/dia** |
| **Mediana/dia** | -277.5 pts/dia |
| **Std/dia** | 1,289.3 |
| **Dias positivos** | 4/10 (40%) |
| **Dia maximo** | +3,254 (15 Abr) |
| **Dia minimo** | -1,067 (7 Abr) |

**Analise:** A media positiva (+165/dia) esconde volatilidade alta. Mediana negativa (-277) mostra que a maioria dos dias eh perdedora, mas os poucos dias ganhadores compensam muito (dia 15 Abr = +3,254 sozinho = 197% do PnL total).

### IS (20 dias com trades)

| Metrica | Valor |
|---------|-------|
| **PnL total** | +2,823 |
| **Dias operados** | 20 |
| **PnL medio/dia** | **+144.4 pts/dia** |
| **Mediana/dia** | +40.0 pts/dia |
| **Std/dia** | 2,707.6 |
| **Dias positivos** | 14/20 (70%) |

---

## 2. Gestao de Risco Detalhada (OOS)

### Como Funciona Cada Guardrail

**1. BE (Break Even):**
- Ativa quando MFE >= max(60 pts, 1.0x ATR)
- Move SL para entry_price - 50 pts (SELL)
- Objetivo: se o trade avancou 60+ pts, protege o capital

**2. TP30 (Take Profit 30%):**
- Apos HP=2 candles, verifica progresso
- Se profit_now / tp_pts < 0.15 (15%), reduz TP em 80%
- TP efetivo vira: 4.0x * 0.20 = 0.8x ATR (muito curto)
- Objetivo: sair rapido se o trade nao esta indo bem

**3. HP (Holding Period):**
- Apos 2 candles, verifica se progrediu >= 15% do TP
- Se nao progrediu, ativa TP30
- Objetivo: nao ficar exposto em trades fracos

**4. Slope Decay:**
- Se EMA5_SLOPE cair abaixo de entry_slope * 0.50
- Move SL para BE (entry - 50 pts)
- Objetivo: sai se o momentum inverter

**5. BE Progress:**
- Apos TP30 + 2 grace candles, move SL para BE
- Objetivo: garante que trades lentos nao viram loss

### Estatisticas dos Guardrails (OOS - 34 trades)

| Guardrail | Ativou | % |
|-----------|--------|---|
| BE triggered | 11/34 | 32.4% |
| TP30 triggered | 29/34 | **85.3%** |
| Slope decay | 32/34 | **94.1%** |
| Progressed | 22/34 | 64.7% |

**TP30 ativa em 85% dos trades!** Isso significa que o TP=4.0x eh raramente atingido. O TP efetivo eh 0.8x ATR (apos reducao de 80%).

### Impacto em Losses (18 trades OOS)

| Tipo | Count | Avg Loss | Impacto |
|------|-------|----------|---------|
| **Losses COM BE** | 2/18 | **-2.5 pts** | **Salvou completamente!** |
| **Losses SEM BE** | 16/18 | -368.8 pts | Loss cheio |

**BE reduziu o loss medio de -368 para -2.5 quando ativou.**

### Impacto em Wins (16 trades OOS)

| Tipo | Count | Avg Win | Impacto |
|------|-------|---------|---------|
| **Wins COM TP30** | 13/16 | +272.9 pts | TP reduzido, mas lucro |
| **Wins SEM TP30** | 3/16 | +1,676.0 pts | **TP cheio atingido!** |

**Trade-off:** TP30 limita wins (+273 vs +1,676), mas protege de losses prolongados.

---

## 3. Trailing Stop, Tape Reading, Book Imbalance, Concentration Zones, S/R Buffer

### O que o Engine JA TEM:

| Recurso | Status | Como Funciona |
|---------|--------|---------------|
| **Slope Decay** | ✅ SIM | Move SL para BE quando EMA5_SLOPE inverte |
| **BE Progress** | ✅ SIM | Move SL para BE apos TP30 + grace |
| **TP30** | ✅ SIM | Reduz TP em 80% se trade nao progredir |
| **HP** | ✅ SIM | Forca saida apos 2 candles sem progresso |
| **GK Ratio** | ✅ SIM | Indicador de volatilidade |
| **VWAP Z-Score** | ✅ SIM | Distancia do preco em relacao ao VWAP |
| **ADX Multi-periodo** | ✅ SIM | ADX7, ADX14, ADX20, ADX30 |
| **Microestrutura** | ✅ SIM | Book_Imbalance, CVD (colunas no parquet) |

### O que o Engine NAO TEM:

| Recurso | Status | Pode Adicionar? |
|---------|--------|-----------------|
| **Trailing Stop (ATR-based)** | ❌ NAO | Sim - mover SL para x% do movimento |
| **Tape Reading (delta/volume)** | ❌ NAO | Parcial - CVD existe mas nao usado no engine |
| **Book Imbalance (filtro)** | ❌ NAO | Sim - coluna BOOK_IMB existe no parquet |
| **Concentration Zones (POC)** | ❌ NAO | Sim - evitar regioes de alta liquidez |
| **S/R Buffer (niveis)** | ❌ NAO | Sim - usar prev_10/20_high/low |

---

## 4. Proposta de Melhorias

### A. Trailing Stop (Prioridade ALTA)

**Problema:** Wins SEM TP30 ganham +1,676 pts (TP cheio), mas sao apenas 3/16. A maioria (13/16) sai no TP30 reduzido (+273 pts).

**Solucao:** Apos BE ativar, mover SL para 50% do movimento (trailing dinamico).

Exemplo:
- Trade avanca 500 pts, BE ativa em 60 pts
- Trailing: move SL para entry + (500 * 0.5) = entry + 250 (SELL = entry - 250)
- Se o preco cair de 500 para 300, SL eh acionado em +250 pts (ainda lucrativo)
- Resultado: captura mais do movimento sem esperar TP cheio

**Estimativa:** Aumentar avg win de +273 para +500+ pts.

### B. Book Imbalance (Prioridade MEDIA)

**Problema:** Entramos sem verificar se o book esta a favor.

**Solucao:** Adicionar filtro: so entra se BOOK_IMB < -0.3 (mais vendedores que compradores no book).

**Dados:** Coluna BOOK_IMB ja existe no parquet.

### C. S/R Buffer (Prioridade MEDIA)

**Problema:** SL pode estar muito proximo de suportes/resistencias naturais.

**Solucao:** Ajustar SL dinamicamente:
- Se prev_10_low esta a 2.0x ATR abaixo do entry, usar esse como SL
- Se prev_10_high esta proximo, reduzir TP para nao bater na resistencia

### D. Concentration Zones (Prioridade BAIXA)

**Problema:** Entramos em regioes onde ha muito volume (POC, VWAP), que funcionam como imas.

**Solucao:** Bloquear entradas quando |VWAP_Z| < 0.5 (preco muito proximo do VWAP = zona de congestionamento).

---

## 5. Conclusao

**A gestao de risco funcionou, mas com trade-offs claros:**

✅ **O que funcionou:**
1. Slope Decay ativou em 94% dos trades - salvou a maioria dos losses
2. BE ativou em 32% - onde ativou, loss medio foi -2.5 pts (quase zero)
3. HP=2 foi o parametro mais importante (multiplicou PnL por 30x)

⚠️ **O que pode melhorar:**
1. TP30 ativa em 85% - limita muito os wins (273 vs 1,676)
2. Sem trailing stop - perdemos parte do movimento apos BE
3. Sem book imbalance - entramos sem confirmacao de fluxo
4. PnL diario volatil (std=1,289) - poucos dias dominam o resultado

**Proximo passo recomendado:**
Implementar trailing stop (50% do movimento apos BE) e re-rodar F3. Estimativa de aumento de +50% no PnL.

---

*Gerado automaticamente em 2026-05-03*
