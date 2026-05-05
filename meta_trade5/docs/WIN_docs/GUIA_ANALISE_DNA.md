# Guia de Analise Post-Ciclo — DNA dos Trades

## Objetivo

Apos cada ciclo completo (F1→F2→F3→Guardrail→OOS), executar esta analise para extrair o "DNA" dos trades vencedores e planejar o proximo ciclo com base em dados, nao intuicao.

## Quando Executar

**OBRIGATORIO** apos todo ciclo completo que gere trades OOS. Nao executar = ciclo incompleto.

```
Ciclo N → Analise DNA → Hipotese N+1 → Ciclo N+1 → Analise DNA → ...
```

## Ferramentas

- `scripts/analise_ciclo_N.py` — Template de analise (adaptar por ciclo)
- `docs/WIN_docs/trades_ciclo{N}_*.parquet` — Trades OOS com metadados
- `data/super_win_continuous.parquet` — Indicadores no momento da entrada

---

## Etapas da Analise

### Etapa 1: Documentar o Processo

Verificar se o ciculo seguiu o processo V6.3:
- [ ] F1 com grid completo (648 combos)
- [ ] F2 com modo_busca=False + guardrails fixos
- [ ] F3 search com modo_busca=False + guardrails fixos
- [ ] Guardrail sweep com 36 combos + sanity checks
- [ ] OOS production com real bid/ask
- [ ] Engine reuse (max 4 engines)

**Artefato:** Secao "Aderencia ao Processo" no relatorio.

---

### Etapa 2: Correlacao dos Indicadores com PnL

Para cada estrategia lucrativa no OOS:
1. Carregar trades OOS (`trades_ciclo{N}_*.parquet`)
2. Join com indicadores (`super_win_continuous.parquet`) no `entry_dt`
3. Calcular correlacao de Pearson entre cada indicador e `pnl`
4. Ordenar por |correlacao| decrescente

**Artefato:** Tabela "Top 10 Correlacoes com PnL"

```python
for col in indicator_cols:
    corr = np.corrcoef(trades[col], trades['pnl'])[0, 1]
```

**Interpretacao:**
- |corr| > 0.5 → FORTE — candidato a filtro heurístico
- |corr| 0.3-0.5 → MODERADO — investigar mais
- |corr| < 0.3 → FRACO — ignorar por enquanto

---

### Etapa 3: Segmentacao Temporal

**3.1 Dia da Semana**
```python
trades['dow'] = trades['entry_dt'].dt.weekday()
```
Agrupar por dia (Seg=1, Ter=2, ..., Sex=5). Calcular:
- Numero de trades
- Win Rate (%)
- Net PnL

**Classificacao:**
- WR > 55% → "Dia Magico" — considerar boost de exposicao
- WR 45-55% → Neutro — manter
- WR < 40% → "Dia Ruim" — considerar filtro de exclusao

**3.2 Horario de Entrada**
```python
trades['hour'] = trades['entry_dt'].dt.hour()
```
Agrupar por hora (9h-17h). Mesma metrica.

**Classificacao:**
- WR > 50% → Horario favoravel
- WR < 30% → "Horario Mortal" — considerar filtro de exclusao

**3.3 Tipo de Saida**
Contar:
- TP (Take Profit)
- SL (Stop Loss)
- BE (Break Even)
- HP (H-Progress / TP30)
- HSTAG (outros)

**Interpretacao:**
- BE=0 em todos os trades → Investigar se BE esta configurado corretamente
- HP=0 → Investigar se H-Progress esta ativado
- TP/SL ratio < 0.5 → Estrategia perde mais do que ganha (depende de R:R)

**Artefato:** Tabelas de segmentacao + classificacao de dias/horarios.

---

### Etapa 4: DNA dos Trades (Indicadores no Momento da Entrada)

**4.1 Split por Resultado**
```python
tp_trades = trades[trades['hit_type'] == 'TP']
sl_trades = trades[trades['hit_type'] == 'SL']
be_trades = trades[trades['hit_type'] == 'BE']
hp_trades = trades[trades['hit_type'] == 'TP30']
```

**4.2 Calcular Medias por Grupo**
Para cada indicador (ATR, ADX7, EMA5_SLOPE, dist, etc.):
- Media no grupo TP
- Media no grupo SL
- Delta (TP - SL)
- Cohen's d (tamanho do efeito)

```python
cohens_d = (tp_mean - sl_mean) / pooled_std
```

**Interpretacao de Cohen's d:**
- |d| > 0.8 → EFEITO GRANDE — candidato a filtro heurístico
- |d| 0.5-0.8 → EFEITO MEDIO — investigar
- |d| < 0.5 → EFEITO PEQUENO — ignorar

**Artefato:** Tabela "DNA dos Trades" + analise estatistica.

---

### Etapa 5: Sintese e Hipoteses

Consolidar descobertas em hipoteses testaveis para o proximo ciclo:

**Exemplo (Ciclo 13 → 14):**

| # | Descoberta | Hipotese para Ciclo 14 | Tipo |
|---|-----------|----------------------|------|
| 1 | EMA5_SLOPE: TP=1.86, SL=69.56 (d=-1.08) | Adicionar filtro `|EMA5_SLOPE| < 50` | Guardrail heurístico |
| 2 | dist: TP=37.80, SL=199.52 (d=-0.57) | Adicionar filtro `dist < 150` | Guardrail heurístico |
| 3 | Terça: WR=55-78% | Boost de peso em Terça | Peso dinâmico |
| 4 | 12h-13h: WR=0-14% | Excluir 12:00-13:30 | Filtro de horário |
| 5 | BE/HP=0 em todos os trades | Investigar configuração de BE no engine | Bug/Config |

**Regra:** Cada hipotese deve ser testavel em UM ciclo completo.

---

## Arquivos Gerados

| Arquivo | Conteudo |
|---------|----------|
| `docs/WIN_docs/ciclo{N}_relatorio.txt` | Resultados brutos do ciclo |
| `docs/WIN_docs/ciclo{N}_relatorio_processo.md` | Aderência ao processo |
| `docs/WIN_docs/ciclo{N}_descobertas_dna.md` | Descobertas da analise |
| `docs/WIN_docs/ciclo{N}_analise_completa.txt` | Tabelas de segmentacao e DNA |

---

## Checklist de Analise

```
[ ] Carregar trades OOS e indicadores
[ ] Calcular correlacoes indicador x PnL
[ ] Segmentar por dia da semana
[ ] Segmentar por horario
[ ] Contar TP/SL/BE/HP
[ ] Calcular DNA (medias TP vs SL)
[ ] Calcular Cohen's d para cada indicador
[ ] Identificar "Dias Magicos" e "Horarios Mortais"
[ ] Formular hipoteses para proximo ciclo
[ ] Salvar relatorio e descobertas
[ ] Atualizar GUIA_CICLOS.md se necessario
```

---

## Exemplo de Ciclo Baseado em DNA

**Ciclo 13:** REV_RSI_S70 sem filtros → OOS +511 (WR 41.8%)

**Analise DNA revelou:**
- Terça: WR 55.3% (+3,421)
- Quinta: WR 36.2% (-1,297)
- |EMA5_SLOPE| < 20 nos trades TP
- |EMA5_SLOPE| > 60 nos trades SL

**Hipotese Ciclo 14:**
> "Aplicar filtro |EMA5_SLOPE| < 50 e boost em Terça vai aumentar WR de 41.8% para >50%"

**Ciclo 14:** REV_RSI_S70 + filtros → Testar hipotese

---

## Referencia

Este guia esta referenciado em `docs/WIN_docs/GUIA_CICLOS.md` na secao "Anti-Overfit: Sanity Checks Automáticos".

Atualizado: 2026-05-02
Versao: 1.0
