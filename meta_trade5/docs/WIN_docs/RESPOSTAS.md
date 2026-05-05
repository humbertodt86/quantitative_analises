# Respostas Diretas — Perguntas do Usuario

## 1. O que e min_votes?

`min_votes` = quantos dos N sinais validados precisam dar o mesmo sinal (BUY) para o ensemble gerar um trade.

| min_votes | Sinais que precisam concordar | Trades gerados |
|-----------|------------------------------|----------------|
| 1 | Qualquer 1 sinal | Muitos |
| 2 | Pelo menos 2 sinais | Moderado |
| 3 | Pelo menos 3 sinais | Poucos |
| 4 | Todos os 4 sinais | Muito raros |

No ensemble atual, o sweep testou [1, 2, 3] e escolheu 3 como melhor no IS. Mas com 4 sinais correlacionados (todos TREND), isso gerou apenas 5 trades em OOS.

---

## 2. Ensemble como SELECTOR (nao consensus filter)

**Voce esta absolutamente correto.** O ensemble deve ser um SELETOR, nao um filtro de consenso.

### Visao correta:
- Se apenas 1 estrategia tem sinal → ela DEVE entrar sozinha
- Se multiplas querem entrar → o ensemble escolhe a MELHOR (por PnL, expectativa, confianca)
- `min_votes` deve ser sempre 1 (ou removido)

### Problema atual:
O engine faz **media ponderada** dos votos e bloqueia se o consenso for fraco:
```python
vote_sum = sum(signal_dir * weight)
vote_norm = vote_sum / total_weight
if abs(vote_norm) < threshold:  # bloqueia!
    continue
if len(voting_modes) < min_votes:  # bloqueia!
    continue
```

Isso e errado. Deveria ser:
```python
if len(voting_modes) == 1:
    # Entra com a unica estrategia disponivel
    mode = voting_modes[0]
elif len(voting_modes) > 1:
    # Escolhe a melhor por score (PnL, peso, confianca)
    mode = max(voting_modes, key=lambda m: m.score)
```

### Ajuste necessario:
Modificar `engine_v2.py` para modo SELECTOR em vez de CONSENSUS.

---

## 3. Sinais ja tem BUY e SELL? Precisa recalcular parquet?

**NAO.** Os sinais PA_* JA contem direcionalidade (-1/0/+1).

### Evidencia:
```python
# build_win_super_table.py
PA_SIGNAL_DIR = np.where(close > EMA20, 1,
                         np.where(close < EMA20, -1, 0))
PA_SIGNAL_REV = -PA_SIGNAL_DIR  # sinal invertido!
```

| Valor | Significado |
|-------|-------------|
| +1 | BUY (close > EMA20) |
| -1 | SELL (close < EMA20) |
| 0 | Sem sinal |

**Nao precisa recalcular o parquet.** Basta usar `--signal=-1` no orquestrador para testar SELL.

Alem disso, documentos anteriores (`RELATORIO_FINAL.md`) mostram que **SELL-only foi o melhor resultado historico** (+91K OOS, 63.9% WR).

---

## 4. Quantas estrategias? Por que 63 e nao 120+?

### Lista completa: 63 estrategias
21 familias de sinais × 3 regimes = **63 estrategias**

O arquivo se chama `strategy_queue_60.json` mas contem 63. O "60" e um nome antigo.

### Por que nao 120+?
Se testassemos BUY e SELL para cada uma, seriam **126 estrategias** (63 × 2).

Atualmente TODAS usam `signal=1` (BUY). Nao testamos SELL ainda.

---

## 5. Quantos combos por estrategia?

### F1: 5,400 combos
- TP: 15 valores
- SL: 12 valores  
- ATR min: 5 valores
- ATR max: 6 valores
- **Total: 15 × 12 × 5 × 6 = 5,400**

### F2: 10 combos (top 10 do F1)
**Por estrategia.** Cada uma das 63 estrategias avanca seus proprios top 10.

### F3: 3 combos (top 3 do F2)
**Por estrategia.** Cada estrategia avanca seus top 3.

### Guardrail: 45 combos
- BE: 5 valores × HP: 3 × CD: 3 = 45

### OOS: 1 combo
Melhor guardrail + melhor F3

---

## 6. Quantas avancaram para F2 no total?

**62 estrategias × 10 combos = 620 configs testadas no F2**

(62 porque PA_VWAP_REV_D1_0_TREND deu entries=0 e foi abortada no F1)

---

## 7. F3 com gestao de risco — foi feita analise para guardrail?

**SIM.** Cada estrategia que chegou ao F3 passou por:
1. F3 IS com o top 3 configs
2. Guardrail sweep: 45 combos de BE/HP/CD
3. Scoring: Sharpe Ratio × Net PnL
4. OOS com a melhor combinacao

---

## 8. Temos PnL projetado?

**SIM.** O OOS (Out-of-Sample) E o PnL projetado.
- Periodo: Abril 2026
- Dados nunca vistos pelo modelo
- Ticks reais (bid/ask)
- Custo real de 30 pts

---

## 9. Estrategias com mesma configuracao — como foi possivel?

**Bug HYBRID = RANGE.** 

O codigo tinha:
```python
regime_filter = {'eq': 1} if regime == 'trend' else {'eq': 0}
```

Isso faz RANGE e HYBRID usarem o MESMO filtro (`regime_label == 0`). Por isso:
```
PA_BB_M2_0_RANGE  → filtra regime_label == 0
PA_BB_M2_0_HYBRID → filtra regime_label == 0  (MESMO!)
```

**Resultado identico porque processam os MESMOS dados.**

### Correcao ja aplicada:
```python
if regime == 'trend':
    regime_filter = {'eq': 1}
elif regime == 'range':
    regime_filter = {'eq': 0}
else:  # hybrid
    regime_filter = None  # sem filtro!
```

---

## 10. Separacao por regime no F1

O F1 JA recalcula o regime em tempo real:
```python
er_thresh = s.get('regime_er_threshold', 0.4)
adx_thresh = s.get('regime_adx_threshold', 25)
regime_dynamic = ((er_vals > er_thresh) & (adx_vals > adx_thresh))
```

Mas o bug fazia HYBRID usar o filtro de RANGE em vez de nenhum filtro.

---

## 11. Resultado do ensemble foi terrivel — por que?

1. **4 sinais, todos TREND** → alta correlacao
2. **min_votes=3** com 4 sinais → so entra quando 75% concordam → 5 trades
3. **Custo destruiu lucro:** 5 trades × 30 pts = 150 pts de custo vs ~99 pts gross

---

## 12. Proximos passos

### Ajustes pendentes:
1. ✅ Corrigir bug HYBRID (FEITO)
2. 🔄 Re-executar 63 estrategias com correcao
3. 🔄 Gerar relatorio completo em .md
4. 🔄 Modificar ensemble para modo SELECTOR
5. 🔄 Testar SELL (--signal=-1)

### Voce quer que eu:
- [ ] Re-execute as 63 estrategias agora (30-40 min)?
- [ ] Ou apenas as 21 HYBRID (10-15 min)?
- [ ] Modifique o ensemble para SELECTOR primeiro?
