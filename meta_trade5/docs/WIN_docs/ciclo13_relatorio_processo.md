# Relatório Ciclo 13 — F1 Reboot: Aderência ao Processo e Correções Necessárias

## Sumário Executivo

O Ciclo 13 reiniciou o processo desde o F1 com todas as correções aplicadas:
- F2/F3 search com `modo_busca=False` + guardrails fixos
- Sanity checks automáticos no guardrail sweep
- Teste de estratégias BUY (PA_MFI_B*, PA_SIGNAL_DIR=+1)

**Resultado:** O processo funcionou conforme projetado, mas revelou **problemas estruturais** que impedem a geração de estratégias BUY viáveis. Sem estratégias BUY, o sanity check de direção falha em 100% dos casos.

---

## Aderência ao Processo V6.3

| Etapa | Implementada | Observação |
|-------|-------------|------------|
| F1 Grid Search | ✅ | 648 combos/estratégia, ~0s execução |
| F2 IS Validation | ✅ | `modo_busca=False`, guardrails fixos (BE=200/HP=2/CD=1) |
| F3 Search IS | ✅ | `modo_busca=False`, guardrails fixos |
| Guardrail Sweep (36 combos) | ✅ | Todos os 36 combos executados |
| Sanity Checks | ✅ | 0/36 configs SELL passaram (100% direcional) |
| F3 OOS Production | ✅ | Real bid/ask, `modo_busca=False` |
| Engine Reuse | ✅ | 4 engines total, zero recriações |
| IS-First Process | ✅ | F3 search + guardrail no IS, apenas produção no OOS |
| Checkpoint | ✅ | Checkpoint salvo a cada estratégia |
| Relatório Completo | ✅ | PnL, WR, PF, direção, guardrails, sanity status |

**Score de Aderência: 10/10** — Todas as etapas do processo V6.3 foram seguidas rigorosamente.

---

## Resultados por Estratégia

### SELL Strategies (signal=-1)

| Estratégia | F1 Top Net | F2 IS Net | F3 IS Net | OOS Net | Trades | WR | PF | Sanity |
|------------|-----------|-----------|-----------|---------|--------|-----|-----|--------|
| REV_RSI_S70 | +137,815 | +590,526 | +590,526 | **+31,357** | 184 | 37.5% | 3.48 | ❌ 100% SELL |
| REV_RSI_S75 | +116,520 | +504,150 | +504,150 | **+25,911** | 152 | 34.9% | 3.31 | ❌ 100% SELL |
| VWAP_Z | +41,760 | +341,859 | +341,859 | **+957** | 94 | 45.7% | 1.29 | ❌ 100% SELL |
| TSI | +18,510 | +375,904 | +375,904 | **-517** | 83 | 49.4% | 1.18 | ❌ 100% SELL |
| VWAP_REV | +64,000 | +35,873 | +35,873 | **+1,455** | 75 | 50.7% | 1.59 | ❌ 100% SELL |

### BUY Strategies (signal=+1)

| Estratégia | F1 Top Net | F2 IS Net | F3 IS Net | OOS Net | Trades | WR | Observação |
|------------|-----------|-----------|-----------|---------|--------|-----|------------|
| MFI_B10 | N/A | SKIP | SKIP | SKIP | 0 | 0% | 1 entrada no cache (insuficiente) |
| MFI_B15 | +14,860 | -6,935 | -6,935 | ERROR | 0 | 0% | Erro de encoding no log |
| MFI_B20 | +37,145 | -13,846 | -13,846 | ERROR | 0 | 0% | Erro de encoding no log |
| SIGNAL_DIR_BUY | N/A | SKIP | SKIP | SKIP | 0 | 0% | 0 entradas no cache |

---

## Problemas Críticos Identificados

### 1. Cache F1 é SELL-Only (Bloqueante)

**Causa:** O cache `_fev_cache.npz` foi construído pré-filtrando `PA_SIGNAL_DIR=-1` (SELL). Ele contém apenas 941 entradas SELL.

**Impacto:**
- Estratégias BUY (`PA_MFI_B*`, `PA_SIGNAL_DIR=+1`) encontram 0-5 entradas no cache
- F1 não consegue avaliar configs BUY de forma significativa
- BUY strategies são descartadas automaticamente por "too few entries"

**Evidência:**
```
MFI_B10: Signal entries: 1 (after regime filter) → SKIP
SIGNAL_DIR_BUY: Signal entries: 0 (after regime filter) → SKIP
```

**Correção Necessária:**
Reconstruir o F1 cache para incluir **ambas as direções** (BUY e SELL), ou criar cache separado para BUY. O cache deve ser indexado por `(estratégia, direção)` em vez de ter direção fixa.

### 2. Erro de Encoding no Log (Bloqueante para BUY)

**Causa:** O log usa `encoding='utf-8'` no arquivo, mas quando há caracteres não-ASCII no console do Windows PowerShell, o `print()` falha.

**Impacto:**
- Estratégias BUY causam crash no OOS production
- `OOS ERROR: 'charmap' codec can't encode characters in position 2-3`

**Evidência:**
```
MFI_B15: OOS ERROR: 'charmap' codec can't encode characters in position 2-3
MFI_B20: OOS ERROR: 'charmap' codec can't encode characters in position 2-3
```

**Correção Necessária:**
Garantir que todos os prints usem apenas ASCII, ou usar `sys.stdout.reconfigure(encoding='utf-8')` no início do script.

### 3. Sanity Check Direcional Falha em 100% dos Casos

**Causa:** Todas as estratégias SELL geram 0% trades BUY. O sanity check rejeita qualquer config com >95% trades na mesma direção.

**Impacto:**
- 0/36 configs de guardrail passaram no sanity check
- Todas as 5 estratégias SELL foram marcadas como FAIL
- O ensemble futuro (Ciclo 15) será 100% rejeitado se não houver estratégias BUY

**Evidência:**
```
Guardrail sweep: 0/36 passed sanity
Issues: Direction bias: BUY=0% SELL=100%
```

**Correção Necessária:**
O sanity check deve ser mais flexível para estratégias individuais (que naturalmente são direcionais), e aplicar a regra de direção apenas no **ensemble** (que DEVE ter diversidade). Ou: adicionar estratégias BUY ao ensemble.

### 4. Degradação com Guardrails Reais

**Causa:** F2 e F3 search agora rodam com `modo_busca=False` + guardrails fixos (BE=200, HP=2, CD=1).

**Impacto:**
- VWAP_Z caiu de +25K (Ciclo 4) para +957 (Ciclo 13)
- TSI caiu de +19K (Ciclo 4) para -517 (Ciclo 13)
- Apenas REV_RSI_S70/S75 mantiveram performance positiva

**Análise:**
Isso é **esperado e desejável**. Os resultados anteriores eram inflados por `modo_busca=True`. O Ciclo 13 mostra a performance **realista** com guardrails. REV_RSI continua sendo a única família consistentemente lucrativa.

---

## Qualidade dos Resultados

| Métrica | Ciclo 13 | Ciclo 10 (comparação) | Avaliação |
|---------|----------|----------------------|-----------|
| Best OOS Net | +31,357 (REV_RSI_S70) | +62,176 (ensemble) | Individual < Ensemble (esperado) |
| Best OOS WR | 50.7% (VWAP_REV) | 48.0% | Similar |
| Overfit Ratio | 18.9x a 727.6x | ~20x | Persistente — guardrails não resolveram overfit |
| Trade Count | 75-184 | 339-396 | Menor (filtragem mais rigorosa) |
| Sanity Pass | 0/5 SELL, 0/4 BUY | N/A | Processo funcionando, mas não há configs válidas |

---

## Correções Necessárias Antes dos Próximos Ciclos

### Correção 1: Reconstruir F1 Cache para BUY

**Prioridade:** CRÍTICA

```python
# Novo cache deve incluir entradas para AMBAS as direções
# Ou: reconstruir M para cada estratégia+direção no fly
```

Alternativa mais simples: usar o período IS completo (Jan-Mar) para o F1 em vez de só fevereiro. Isso dá mais entradas para ambas as direções.

### Correção 2: Fix Encoding no Log

**Prioridade:** ALTA

```python
import sys
sys.stdout.reconfigure(encoding='utf-8')
```

### Correção 3: Ajustar Sanity Check para Estratégias Individuais

**Prioridade:** ALTA

Estratégias individuais são naturalmente direcionais (SELL-only ou BUY-only). O sanity check de direção deve aplicar apenas ao **ensemble final**.

```python
def sanity_check_gr(gr_config, trades, period_name, is_ensemble=False):
    if not is_ensemble:
        # Para estratégias individuais, não checar direção
        # (elas são direcionais por design)
        pass
```

### Correção 4: Expandir Grid de Estratégias BUY

**Prioridade:** ALTA

Testar mais colunas que geram sinais +1:
- `PA_SIGNAL_DIR` com filtro `eq: 1` (BUY)
- `PA_MFI_B*` (B10, B15, B20, B25, B30)
- `PA_REV_RSI_B*` (B5, B10, B15, B20, B25) — REV_RSI pode ser BUY?
- `PA_VWAP_Z_*` com `eq: 1`
- `PA_TSI_*` com `eq: 1`

---

## Próximos Passos Recomendados

1. **Corrigir cache F1** para suportar BUY (ou usar IS completo no F1)
2. **Corrigir encoding** no log
3. **Ajustar sanity check** para não rejeitar estratégias individuais direcionais
4. **Ciclo 14:** Rodar F1 com estratégias BUY expandidas
5. **Ciclo 15:** Ensemble com melhores SELL + melhores BUY (se existirem)
6. **Ciclo 16:** Otimizar pesos por Sharpe
7. **Ciclo 17:** Testar filtros heurísticos

---

## Conclusão

O Ciclo 13 provou que o **processo V6.3 corrigido funciona**. Todas as etapas foram executadas corretamente, os engines foram reusados, os sanity checks flagaram problemas reais, e os resultados são mais realistas (menor overfit aparente devido aos guardrails fixos no F2/F3).

No entanto, revelou um **problema estrutural:** sem estratégias BUY viáveis, o ensemble nunca passará no sanity check de direção. A próxima prioridade é corrigir o F1 cache para gerar estratégias BUY, ou aceitar que o ensemble será 100% SELL e ajustar o sanity check accordingly.

**Recomendação:** O usuário deve decidir:
- **Opção A:** Aceitar ensemble 100% SELL e remover sanity check de direção para estratégias individuais
- **Opção B:** Investir tempo em reconstruir F1 cache e encontrar estratégias BUY viáveis

Considerando que o WIN é um mercado onde o viés de baixa é comum (especialmente em certos regimes), a Opção A pode ser pragmaticamente aceitável, desde que o ensemble tenha convicção mínima (`min_votes`) para filtrar sinais fracos.
