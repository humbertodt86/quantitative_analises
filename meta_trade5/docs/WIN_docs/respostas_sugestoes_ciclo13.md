# Respostas as Sugestoes do Ciclo 13

## 1. Spread Simulado no F2

**Concordancia:** Nao eh prioridade. O custo de 30 pts/trade no F1/F2 eh uma aproximacao grosseira mas funcional. O overfit eh causado principalmente por:
- Diferenca de regime IS→OOS (nao por dados)
- Guardrails desligados no F2/F3 (corrigido)
- BE=999999 selecionado como vencedor (corrigido)

**Decisao:** Manter COST=30. Nao implementar spread sintetico no F2 por enquanto.

---

## 2. Indicadores com Correlacao Positiva

Nao sao so EMA5_SLOPE e PA_REV. A analise completa revelou:

**REV_RSI_S70:**
- EMA5_SLOPE: -0.631 (FORTE)
- PA_REV_RSI_B15: +0.538 (BUY signals!)
- PA_REV_RSI_S85: +0.538 (SELL extremo)
- PA_REV_RSI_B5/B10: +0.534 (BUY leve)

**VWAP_REV:**
- EMA5_SLOPE: -0.706 (FORTE)
- dist: -0.607 (proximidade VWAP)
- PA_REV_RSI_B25: +0.552
- PA_KELT_M1_0: +0.524 (Keltner squeeze)

**Insight:** PA_REV_RSI_B* (BUY signals) correlacionam positivamente com PnL mesmo no modelo SELL-only. Isso sugere que a familia REV_RSI tem alpha em ambas as direcoes, mas Abril/2026 favoreceu SELL.

---

## 3. Combos F1 por Estrategia

```
TP: 9 valores × SL: 8 valores × ATRmin: 3 × ATRmax: 3 = 648 combos
Tempo: ~0.5s por estrategia (vetorizado numpy)
```

---

## 4. Relatorio Salvo

`docs/WIN_docs/ciclo13_descobertas_dna.md`

---

## 5. Documentacao Criada

**GUIA_ANALISE_DNA.md** — Guia completo de como fazer a analise post-ciclo:
- Etapa 1: Documentar processo
- Etapa 2: Correlacao indicador × PnL
- Etapa 3: Segmentacao temporal (dia, hora, tipo de saida)
- Etapa 4: DNA dos trades (medias TP vs SL, Cohen's d)
- Etapa 5: Sintese e hipoteses

**Referencia no GUIA_CICLOS.md:** Nova secao "Análise Pós-Ciclo: DNA dos Trades"

---

## 6. Sobre o "Dia Magico" (Terca)

Voce mencionou um video de um trader que compra terca 10h e vende 15h. A analise do Ciclo 13 encontrou algo similar:

| Modelo | Dia | WR | Net |
|--------|-----|-----|-----|
| REV_RSI_S70 | Ter | 55.3% | +3,421 |
| VWAP_REV | Ter | 77.8% | +6,283 |

**Mas** o mesmo trader provavelmente perde dinheiro nas outras direcoes/dias:
- Segunda: WR 36-41%, Net negativo
- Quinta: WR 23-36%, Net negativo

**Interpretacao:** Terca eh um dia com alta liquidez/rotatividade no WIN. O "dia magico" eh real, mas localizado.

---

## 7. Alpha Alem do PnL

Concordo 100%. Usar apenas PnL para selecionar estrategias eh um filtro grosseiro que mata alpha real. Adicionei no GUIA_CICLOS.md:

**Metricas adicionais para identificar alpha:**
1. **Hit Rate por Regime** — Funciona em range mas nao em trend? Isso eh alpha direcional
2. **Skew da Distribuicao de PnL** — Skew positivo (poucos ganhos grandes, muitas perdas pequenas) pode ser lucrativo com sizing adequado
3. **Serial Correlation** — Ganha em clusters (2-3 dias seguidos)? Ha timing alpha
4. **PnL Simulado com Heuristicas** — Aplicar filtros de dia/hora descobertos na analise DNA e recalcular:

```python
filtered = trades[
    (trades['dow'].isin([2, 3])) &           # Ter, Qua
    (~trades['hour'].isin([12, 13])) &       # Sem almoco
    (abs(trades['EMA5_SLOPE']) < 50)         # Flat market
]
simulated_pnl = filtered['pnl'].sum() - len(filtered) * COST
```

Se simulated_pnl >> raw_pnl, a estrategia tem alpha latente que os guardrails/heuristicas podem extrair.

---

## 8. PnL Simulado com Guardrails de Dia/Hora

Implementado no GUIA_CICLOS.md como metodo oficial de identificacao de alpha:

> "Aplicar filtros de dia/hora descobertos na analise DNA e recalcular PnL. Se o PnL simulado com heuristicas for significativamente melhor que o PnL bruto, a estrategia tem alpha latente."

Exemplo concreto para Ciclo 14:
```python
# REV_RSI_S70 sem filtros: +511 pts (194 trades, WR 41.8%)
# REV_RSI_S70 com filtros:
#   - Excluir Seg, Qui, Sex
#   - Excluir 12h-13h
#   - Excluir |EMA5_SLOPE| > 50
# Resultado estimado: ~120 trades, WR ~55%, Net ~+3,500 pts
```

---

## 9. DNA dos Vencedores/Perdedores para Planejar Grid

A analise do Ciclo 13 revelou regras para o proximo grid search:

**Filtros Heuristicos (nao otimizaveis, aplicados post-F1):**
- |EMA5_SLOPE| < 50 (efeito muito grande, d=-1.08)
- dist < 150 para VWAP_REV (efeito medio-grande, d=-0.83)
- dow IN [2, 3] (Ter, Qua) ou dow NOT IN [4, 5] (Qui, Sex)
- hour NOT IN [12, 13] (almoco)

**Parametros do Grid (otimizaveis via F1):**
- TP mult: testar mais valores > 8.0 (REV_RSI lucra com TP longo)
- SL mult: manter 0.10-0.30 (range strategies precisam de SL apertado)
- BE trigger: testar 50, 100, 150, 200 (atual seleciona 100-300)

---

## 10. Fase de Validacao de Sinais (Um Ciclo por Estrategia)

Concordo. A arquitetura foi atualizada no GUIA_CICLOS.md:

**Fase 1 — Validacao de Sinais (ciclos individuais):**
```
Para cada estrategia candidata:
  Ciclo: F1→F2→F3→Guardrail→OOS
  Analise DNA
  Ajustar params/guardrails/heuristicas
  Repetir ate estabilizar
  
Critério de aceite: WR OOS > 40%, Net OOS > 0, overfit < 10x
```

**Fase 2 — Assembly/Ensemble (depois da validacao):**
```
Combinar estratégias validadas individualmente
Testar min_votes, pesos, correlacao de erros
Validar diversidade de direcao (BUY+SELL)
```

**Regra:** Nunca montar ensemble com estrategias nao validadas.

---

## 11. Assembly/Ensemble: Estrategias Complementares vs Concorrentes

**Estrategias Complementares (operam em momentos diferentes):**
- REV_RSI_S70 (range, flat market) + VWAP_REV (proximidade VWAP)
- Overlap de datas: apenas 9% (18/194 trades)
- Sao complementares — lucram em regimes diferentes

**Estrategias Concorrentes (operam nos mesmos candles):**
- REV_RSI_S70 + REV_RSI_S75 (ambas range, RSI-based)
- Provavelmente alta correlacao de erros
- No ensemble, uma pode vetar a outra

**Sobre aproveitar sinais da mesma estratégia:**
Sim, eh possivel. A familia REV_RSI tem variantes (S70, S75, S80, B5, B10, B15) que capturam graus diferentes de reversao. No entanto:
- Correlacao de erros provavelmente > 0.7 (mesmo sinal subjacente)
- Matriz de veto recomenda remover uma se correlacao > 0.8
- Estrategia: manter a de melhor Sharpe OOS, descartar as redundantes

**Proposta de Assembly Ciclo 15:**
```python
MODES = {
    'REV_RSI_S70': {  # Validada, +511 OOS, 194 trades
        'signal_field': 'PA_REV_RSI_S70',
        'weight': 2.0,
        'filters': {
            'ATR': {'min': 100, 'max': 9999},
            'PA_REV_RSI_S70': {'eq': -1},
            'EMA5_SLOPE': {'max': 50, 'min': -50},  # NOVO: flat market
            'day_of_week': {'exclude': [4, 5]},      # NOVO: exclui Qui, Sex
        }
    },
    'VWAP_REV': {  # Validada, +1,739 OOS, 75 trades
        'signal_field': 'PA_VWAP_REV_D0_3',
        'weight': 1.5,
        'filters': {
            'ATR': {'min': 100, 'max': 600},
            'PA_VWAP_REV_D0_3': {'eq': -1},
            'dist': {'max': 150},                     # NOVO: perto do VWAP
        }
    },
}
# min_votes=1 (qualquer uma dispara) ou min_votes=2 (ambas concordam)
```

---

## Resumo das Acoes Tomadas

| # | Sugestao | Acao | Status |
|---|----------|------|--------|
| 1 | Spread simulado no F2 | Mantido COST=30, nao priorizar spread sintetico | ✅ Documentado |
| 2 | Correlacao de indicadores | Analisado 10+ indicadores, EMA5_SLOPE e dist sao os fortes | ✅ Relatorio salvo |
| 3 | Combos F1 | 648 combos/est, 0.5s cada | ✅ Documentado |
| 4 | Relatorio | `ciclo13_descobertas_dna.md` | ✅ Salvo |
| 5 | Guia de analise | `GUIA_ANALISE_DNA.md` + referencia no `GUIA_CICLOS.md` | ✅ Criado |
| 6 | "Dia magico" | Ter confirmado como dia de alta performance | ✅ Analisado |
| 7 | Alpha alem de PnL | 4 metricas adicionadas ao processo | ✅ No GUIA_CICLOS |
| 8 | PnL simulado com heuristicas | Metodo oficial de identificacao de alpha | ✅ No GUIA_CICLOS |
| 9 | DNA para planejar grid | Filtros heuristicos identificados para Ciclo 14 | ✅ Documentado |
| 10 | Fase de validacao de sinais | Fase 1 (individual) e Fase 2 (ensemble) definidas | ✅ No GUIA_CICLOS |
| 11 | Assembly/ensemble | Proposta de modos com filtros de DNA | ✅ Documentado |

**Proximo passo:** Quer que eu execute o Ciclo 14 com os filtros heuristicos identificados (EMA5_SLOPE < 50, excluir almoco, boost em terca)?
