# Relatorio de Revisao Conceitual — Sinais PA_* WIN
**Versao:** V7.5.2-RC1 (Revisao de Codigo de Sinais)
**Data:** 2026-05-03
**Autor:** Sisyphus (Auditoria Quant)

---

## Resumo Executivo

### Veredito: SIM, e necessario refatorar o codigo de geracao de sinais.

O sistema possui **21 familias de sinais** e **241 variantes pre-computadas** no parquet. A arquitetura conceitual e solida (bar-close entry, proximo candle open), a implementacao do PA_SIGNAL_DIR V8.0 esta **correta**, mas existem **bugs em scripts auxiliares**, **nomes enganosos**, **fragmentacao do codigo** e **superficie de overfitting excessiva**.

A refatoracao e **obrigatoria** antes de qualquer deploy em producao. Os bugs nos scripts de update/mmerge corrompem colunas auxiliares, e a fragmentacao do codigo em multiplos arquivos cria risco de inconsistencia.

---

## 1. Onde os Sinais Sao Gerados

### Problema de Arquitetura: Codigo FRAGMENTADO

O codigo de geracao de sinais esta **espalhado em 5+ arquivos diferentes**, criando risco de inconsistencia:

| Arquivo | Funcao | Risco |
|---------|--------|-------|
| `build_continuous_indicators.py` | Gera TODOS os sinais do zero (rebuild completo) | Bug de ordenacao no V8.0 (range_ratio definido depois de ser usado). NAO afeta parquet atual, mas quebraria rebuild do zero. |
| `update_signal_dir_v8.py` | Atualiza PA_SIGNAL_DIR para V8.0 em parquet existente | Correto. Verifica se `range_ratio` existe antes de usar. |
| `update_v8_optimized.py` | Atualiza PA_SIGNAL_DIR com parametros otimos do F1 | Correto. Mesmo padrao do update_signal_dir_v8. |
| `build_signal_dir_variants.py` | Gera 120+ variantes de PA_SIGNAL_DIR | Duplicacao de logica. Se V8.0 mudar, este script tambem precisa mudar. |
| `add_signal_dir_v2.py` | Adiciona PA_SIGNAL_DIR_V2 | Script separado para uma unica coluna. |

**Recomendacao:** Consolidar TUDO em `build_continuous_indicators.py` (unico ponto de verdade) e remover os scripts de update dispersos. O fluxo correto deve ser: **rebuild completo do parquet a partir do zero**, nao updates incrementais.

### Implementacao V8.0 (Validada — CORRETA)

A implementacao atual do PA_SIGNAL_DIR V8.0 esta **conceitualmente correta**:

```python
# 1. Parametros de Momentum e Distancia
di['ema_slope'] = di['EMA20'].diff()
di['std_dev'] = di['close'].rolling(20).std()
di['z_score'] = (di['close'] - di['EMA20']) / di['std_dev']

# 2. Definicao da Direcao V8.0 (Inercia + Exaustao)
di['PA_SIGNAL_DIR'] = np.where(
    (di['close'] > di['EMA20']) & (di['ema_slope'] > 0) & (di['z_score'] < 2.0), 1,  # BUY
    np.where(
        (di['close'] < di['EMA20']) & (di['ema_slope'] < 0) & (di['z_score'] > -2.0), -1, # SELL
        0 # NEUTRO: Filtra lateralidade e exaustao
    )
).astype('int64')
```

**Validacao:**
- `ema_slope = EMA20.diff()` — Correta. Captura inclinacao da media movel.
- `std_dev = close.rolling(20).std()` — Aceitavel. O std inclui o candle atual, o que inflige ligeiramente o desvio (conservador), mas nao e look-ahead para estrategias bar-close.
- `z_score = (close - EMA20) / std_dev` — Correta. Mede distancia do preco a media em unidades de desvio.
- **BUY:** close > EMA20 (preco acima da media) AND slope > 0 (media subindo) AND z_score < 2.0 (nao esticado) — Logica valida.
- **SELL:** close < EMA20 AND slope < 0 AND z_score > -2.0 — Simetrica, valida.
- **NEUTRO (0):** Filtra candles sem direcao clara ou com preco esticado demais. Reduz ruido.

**Ressalva:** O `rolling(20).std()` no z-score inclui o `close` atual no calculo do desvio, o que torna o z-score ligeiramente mais conservador (|z| um pouco menor do que seria se o std excluisse o candle atual). Isso faz com que o filtro `|z| < 2.0` seja levemente mais permissivo. Impacto pratico: minimo.

---

## 2. Bugs Criticos Encontrados

### 🚨 BUG 1: ADX7_DELTA E Corrompido no Merge
**Severidade: ALTA. Impacto: 99.8% dos valores estao errados.**

No `build_continuous_indicators.py`, linhas 386-390:
```python
for p in [7]:
    col = f'ADX{p}'; delta = f'ADX{p}_DELTA'
    continuous = continuous.with_columns(
        (pl.col(col) - pl.col(col).shift(1)).alias(delta)  # shift(1) — ERRADO!
    )
```

A computacao correta (dentro de cada contrato) usa `shift(3)`:
```python
adx_delta = di['ADX7'] - di['ADX7'].shift(3)  # shift(3) — CORRETO
```

O pos-merge sobrescreve com `shift(1)`, criando:
1. Valores completamente diferentes (99.8% das linhas divergem)
2. Pico falso na fronteira de contrato (J26 → M26 em 14/Abr)

**PA_ADX_BREAK e PA_EXHAUST nao sao afetados** porque usam a variavel local `adx_delta` (correta). Mas **qualquer codigo que le a coluna ADX7_DELTA do parquet** recebe valores errados.

**Acao urgente:** Mudar `shift(1)` para `shift(3)` na linha 389 ou remover o bloco de sobrescritura (ja esta computado corretamente dentro de cada contrato).

---

### 🚨 BUG 2: PA_TUESDAY Desatualizado
**Severidade: MEDIA. Impacto: 10.7% de discrepancia.**

PA_TUESDAY foi computado com PA_SIGNAL_DIR **DEPRECATED** (close vs EMA20), nao com V8.0 (momentum + z-score + noise). Apos a atualizacao V8.0, PA_TUESDAY nunca foi recalculado.

```python
# build_continuous_indicators.py, linha 234
di['PA_TUESDAY'] = np.where(di['day_of_week'] == 1, di['PA_SIGNAL_DIR'], 0)
```

O problema: `PA_SIGNAL_DIR` nesta linha e o DEPRECATED (linha 125-128), nao o V8.0 (linhas 158-161). Além disso, `update_signal_dir_v8.py` atualiza PA_SIGNAL_DIR mas NAO recalcula PA_TUESDAY.

**Acao:** Consolidar tudo em um unico script de rebuild para garantir que PA_TUESDAY (e outros sinais dependentes) sempre usem a versao mais recente de PA_SIGNAL_DIR.

---

## 3. Nomes Enganosos (Misleading Column Names)

### ⚠️ PA_BB_* — NAO sao Bollinger Bands
```python
# build_continuous_indicators.py, linhas 251-255
buy = di['close'] < di['EMA20'] - di['ATR'] * mult
sell = di['close'] > di['EMA20'] + di['ATR'] * mult
```

Usa **ATR** como medida de volatilidade, nao desvio padrao. Sao **Keltner Channels**, nao Bollinger Bands. O arquivo computa BB_UPPER/BB_LOWER corretamente (usando std) em `add_indicators()`, mas **nao usa**.

**Recomendacao:** Renomear para `PA_KELT_ATR_M*` ou usar BB_UPPER/BB_LOWER reais.

---

### ⚠️ PA_HMA_CROSS_* — NAO usam Hull Moving Average
```python
# build_continuous_indicators.py, linhas 302-306
hma_fast = di['close'].rolling(fast).mean()   # SMA simples!
hma_slow = di['close'].rolling(slow).mean()   # SMA simples!
```

O comentario diz "using MA proxy", mas o nome da coluna diz HMA. A HMA real e computada nas linhas 50-57 mas **ignorada**.

**Recomendacao:** Usar HMA_FAST/HMA_SLOW reais ou renomear para `PA_MA_CROSS_*`.

---

### ⚠️ PA_POC_REV — NAO e Point of Control
```python
# build_continuous_indicators.py, linhas 236-239
buy = (di['close'] - di['VWAP']) / di['ATR'] < -2.0
sell = (di['close'] - di['VWAP']) / di['ATR'] > 2.0
```

E a distancia do preco ao VWAP normalizada por ATR. Nao ha volume profile, nao ha POC. **Renomear** para `PA_VWAP_STRETCH`.

---

### ⚠️ PA_VWAP_Z — Denominador Incorreto
```python
# build_continuous_indicators.py, linhas 184-186
vwap_std = di.groupby('date')['dist'].transform(lambda x: x.rolling(20,min_periods=1).std())
di['VWAP_Z'] = (di['close'] - di['VWAP']) / vwap_std
```

O denominador e `std(dist)` = `std(close - EMA20)`, nao `std(close - VWAP)`. Mistura estatisticas de EMA20 e VWAP.

**Recomendacao:** Corrigir para usar `std(close - VWAP)` por dia.

---

## 4. Qualidade dos Sinais por Familia

### 4.1 Sinais Robustos (baixa frequencia, logica concreta)

| # | Sinal | % Ativo | Qualidade | Logica |
|---|-------|---------|-----------|--------|
| 1 | **PA_LIQ_GRAB** | 11-22% | ⭐⭐⭐⭐⭐ | Quebra de high/low previo + fechamento revertido. Microestrutura real. |
| 2 | **PA_VCP** | 3-25% | ⭐⭐⭐⭐⭐ | Contracao de volatilidade + expansao. Pattern classico. |
| 3 | **PA_ADX_BREAK** | 35-46% | ⭐⭐⭐⭐ | ADX acelerando + filtro de regime. Momentum confirmado. |
| 4 | **PA_EXHAUST** | 8-15% | ⭐⭐⭐⭐ | ADX desacelerando em tendencia. Captura exaustao. |
| 5 | **PA_REV_RSI** | 25-51% | ⭐⭐⭐ | RSI2 mean reversion. Logica valida, mas muitas variantes redundantes. |
| 6 | **PA_VWAP_Z** | 41-75% | ⭐⭐⭐ | Z-score de VWAP. Logica valida, mas denominador incorreto. |

### 4.2 Sinais Ruidosos (alta frequencia, baixa conviccao)

| # | Sinal | % Ativo | Problema |
|---|-------|---------|----------|
| 1 | **PA_SIGNAL_DIR** | **90.1%** | Ativo quase sempre. 26.4% dos candles invertem direcao. Media de streak: 11.9 candles (~1h). |
| 2 | **PA_SIGNAL_DIR_DEPRECATED** | **100%** | Sempre 1 ou -1. Zero conteudo informativo. |
| 3 | **PA_STRONG_TREND** | 38-74% | Depende de PA_SIGNAL_DIR (bugado). |
| 4 | **PA_EFF_RATIO** | 38-56% | E um classificador de regime, nao um sinal independente. |
| 5 | **PA_CHOP** | 43-61% | Idem — so aplica PA_SIGNAL_DIR quando CHOP < threshold. |

### 4.3 Sinais Suspeitos (data mining ou raros demais)

| # | Sinal | % Ativo | Problema |
|---|-------|---------|----------|
| 1 | **PA_TUESDAY** | 14-18% | Efeito calendario sem fundamento economico. Data mining puro. |
| 2 | **PA_GK_BREAK_G0_005** | **0.1%** | Apenas 11 valores nao-zero. Estatisticamente insignificante. |
| 3 | **PA_STRONG_TREND_A35_S30** | **0.4%** | Filtra demais. Overfit provavel. |

---

## 5. Look-Ahead Bias — Veredicto: NAO HA

O engine consome sinais corretamente:
- **Sinal avaliado no candle i** (close): `s_dir = row['PA_SIGNAL_DIR']`
- **Entrada no candle i+1** (open): `ep = records[i+1]['open']`

Isso e **backtesting correto** para estrategias bar-close. Nenhum `.shift(-1)` ou acesso a dados futuros foi encontrado.

**Caveat:** Todos os indicadores (EMA20, ATR, ADX, etc.) usam dados do candle atual em suas computacoes. Isso e correto para decisao no fechamento do candle, mas significa que os sinais nao podem ser usados para entrada no **mesmo** candle (only bar-close strategies).

---

## 6. Resultados Historicos (Resumido)

### Sinais Completamente Validados (F1→F2→F3→OOS)

| # | Sinal | OOS PnL | WR | Trades | WFA |
|---|-------|---------|-----|--------|-----|
| 1 | **PA_SIGNAL_DIR_S0_Z30_R05** | +1,651 → **+3,187** (VWAP fix) | 47% | 32 | 3/3 |
| 2 | **PA_EXHAUST_TREND_SELL** | +4,364 | 42% | 19 | 3/3 |
| 3 | **PA_REV_RSI_B15_HYBRID_SELL** | +13,111 | 52% | 147 | — |
| 4 | **PA_VCP_HYBRID_SELL** | +12,149 | 58% | 43 | — |
| 5 | **PA_TSI_T25_HYBRID_SELL** | +9,532 | 54% | 87 | — |

### Sinais que Falharam OOS

| Familia | Motivo |
|---------|--------|
| PA_SIGNAL_REV | Nunca testado individualmente |
| PA_STRONG_TREND | OOS negativo em todos os regimes |
| PA_SLOPE_TREND | OOS negativo em todos os regimes |
| PA_HMA_CROSS | OOS negativo em todos os regimes |
| PA_EFF_RATIO | OOS negativo em todos os regimes |
| PA_CHOP | OOS negativo em todos os regimes |
| PA_GK_BREAK | OOS negativo em todos os regimes |
| PA_LIQ_GRAB | OOS positivo em TREND, mas falhou em RANGE/HYBRID |
| PA_MFI | OOS positivo em TREND, mas falhou em RANGE/HYBRID |
| PA_BB/KELT | So TREND_SELL funcionou (compliant) |
| **TODOS os sinais BUY** | **0/29 sinais BUY tiveram OOS positivo** |

### Observacao Critica
Os resultados historicos estao **validos para PA_SIGNAL_DIR** (o V8.0 foi aplicado corretamente via `update_signal_dir_v8.py`), mas **colunas auxiliares como ADX7_DELTA estao corrompidas** no parquet. Sinais dependentes de PA_SIGNAL_DIR (VCP, TUESDAY, EFF_RATIO, CHOP) podem estar desatualizados se foram computados antes do update V8.0.

---

## 7. Superficie de Overfitting

### Problema: 241 sinais e excessivo

| Familia | Variantws | Correlacao Interna | Problema |
|---------|-----------|-------------------|----------|
| PA_SIGNAL_DIR | 150+ | r > 0.95 | Grid fino de thresholds (S/Z/R). Superficie enorme. |
| PA_REV_RSI | 10 | r > 0.90 | Thresholds muito proximos. Variantes quase identicas. |
| PA_STRONG_TREND | 16 | r > 0.85 | Combinacoes de ADMin x SlopeMin redundantes. |
| PA_SLOPE_TREND | 15 | r > 0.80 | Idem. |
| PA_VWAP_Z | 5 | r > 0.75 | Thresholds Z=1.0 a 3.0. Diferenciacao baixa. |

**Recomendacao:** Reduzir para ~30-40 variantes nao-redundantes. Manter no maximo 2-3 por familia.

---

## 8. Recomendacoes de Refatoracao

### Prioridade 0 — Consolidacao do Codigo (FAZER PRIMEIRO)

0. **Consolidar todos os scripts de geracao em um unico arquivo:**
   - Mover logica de `update_signal_dir_v8.py`, `update_v8_optimized.py`, `build_signal_dir_variants.py`, `add_signal_dir_v2.py` para dentro de `build_continuous_indicators.py`
   - O fluxo deve ser: **rebuild completo do zero** (unico ponto de verdade)
   - Remover updates incrementais — eles criam inconsistencia (ex: PA_TUESDAY desatualizado)
   - Criar funcao `build_all_signals(df)` que retorna o dataframe completo com TODOS os sinais

### Prioridade 1 — Bugs (FAZER AGORA)

1. **Corrigir BUG 1 (ADX7_DELTA):** Remover o bloco de sobrescritura de ADX7_DELTA (linhas 386-390) ou mudar `shift(1)` para `shift(3)`.
2. **Corrigir BUG 2 (PA_TUESDAY):** Garantir que PA_TUESDAY seja computado APOS PA_SIGNAL_DIR V8.0 (nao o DEPRECATED). No script consolidado, a ordem de computacao sera explicita.
3. **Corrigir `build_continuous_indicators.py`:** A ordenacao do V8.0 (linha 140 usando `range_ratio` antes da linha 196 definir) precisa ser corrigida para rebuilds do zero funcionarem. Mover bloco V6.0 (range_ratio) para antes do V8.0.
4. **Regerar o parquet** `super_win_continuous.parquet` a partir do script consolidado.
5. **Revalidar PA_SIGNAL_DIR** e todos os sinais dependentes com o parquet novo.

### Prioridade 2 — Nomes e Logica

6. **Renomear PA_BB_* → PA_KELT_ATR_*** (ou usar BB_UPPER/BB_LOWER reais).
7. **Renomear PA_HMA_CROSS_* → PA_MA_CROSS_*** (ou usar HMA reais).
8. **Renomear PA_POC_REV → PA_VWAP_STRETCH**.
9. **Corrigir VWAP_Z:** Usar `std(close - VWAP)` ao inves de `std(close - EMA20)`.

### Prioridade 3 — Reducao de Overfitting

10. **Prune PA_SIGNAL_DIR:** De 150 para ~12 variantes (3 valores de S x 2 de Z x 2 de R).
11. **Prune PA_REV_RSI:** De 10 para 3 (S70, B10, e um intermediario).
12. **Remover sinais raros:** PA_GK_BREAK_G0_005 (11 sinais), PA_STRONG_TREND_A35_S30 (0.4%).
13. **Remover PA_TUESDAY:** Data mining sem fundamento.
14. **Remover PA_SIGNAL_DIR_DEPRECATED:** Sempre ativo, sem valor informativo.
15. **Remover PA_EFF_RATIO e PA_CHOP:** Nao sao sinais independentes (so aplicam direcao de PA_SIGNAL_DIR quando regime coincide).

### Prioridade 4 — Testes e Validacao

16. **Adicionar CI:** Script de validacao que verifica:
   - PA_SIGNAL_DIR != PA_SIGNAL_DIR_DEPRECATED apos atualizacao
   - ADX7_DELTA = ADX7 - ADX7.shift(3)
   - Nenhuma coluna PA_* tem 100% de valores nao-zero (exceto DEPRECATED)
   - Correlacao entre variantes da mesma familia < 0.90
17. **Testes unitarios:** Para cada familia de sinais, verificar logica em casos edge (crossover exato, RSI=50, close=VWAP, etc.).

---

## 9. Plano de Acao Proposto

### Fase 1: Consolidacao (1 dia)
- [ ] Criar `build_signals_unified.py` — script unico de rebuild completo
- [ ] Migrar logica de: `update_signal_dir_v8.py`, `update_v8_optimized.py`, `build_signal_dir_variants.py`, `add_signal_dir_v2.py`
- [ ] Corrigir ordenacao em `build_continuous_indicators.py` (range_ratio antes de V8.0)
- [ ] Corrigir ADX7_DELTA (shift(1) → shift(3))
- [ ] Garantir que PA_TUESDAY use PA_SIGNAL_DIR V8.0 (nao DEPRECATED)

### Fase 2: Rebuild e Validacao (1 dia)
- [ ] Executar rebuild completo do parquet via script consolidado
- [ ] Validar que PA_SIGNAL_DIR == PA_SIGNAL_DIR gerado pelo update_v8_optimized.py (mesmos valores)
- [ ] Revalidar PA_SIGNAL_DIR com F1 rapido (10 min)
- [ ] Verificar ADX7_DELTA = ADX7 - ADX7.shift(3)

### Fase 3: Refatoracao de Nomes (1 dia)
- [ ] Renomear PA_BB, PA_HMA, PA_POC_REV
- [ ] Corrigir VWAP_Z denominador
- [ ] Atualizar todos os scripts/bots que referenciam nomes antigos

### Fase 4: Prune e Revalidacao (2-3 dias)
- [ ] Reduzir PA_SIGNAL_DIR para 12 variantes
- [ ] Reduzir PA_REV_RSI para 3 variantes
- [ ] Remover sinais raros/deprecated
- [ ] Reexecutar F1 completo com sinais pruningados
- [ ] Reexecutar F2/F3/OOS para sinais que mostrarem promessa

### Fase 5: CI e Monitoramento (1 dia)
- [ ] Criar script de validacao de integridade do parquet
- [ ] Adicionar checks de correlacao entre variantes
- [ ] Documentar pipeline de geracao de sinais
- [ ] Remover scripts obsoletos (`update_signal_dir_v8.py`, `update_v8_optimized.py`, etc.)

---

## 10. Conclusao

**A arquitetura do sistema e solida:** bar-close entry, proximo candle open, sem look-ahead. A implementacao do PA_SIGNAL_DIR V8.0 esta **conceitualmente correta** (inercia + exaustao + filtro de ruido). Os indicadores base (EMA, ATR, ADX, RSI, VWAP) estao corretamente implementados e alinhados com MT5.

**Mas a implementacao tem problemas serious:**
- **Codigo fragmentado** em 5+ arquivos, criando inconsistencia (PA_TUESDAY desatualizado, ADX7_DELTA corrompido no merge)
- **Bug no rebuild do zero:** `build_continuous_indicators.py` tem ordenacao errada (range_ratio usado antes de definido)
- **Nomes enganosos** que induzem a erro (PA_BB usa ATR, PA_HMA usa SMA)
- **Superficie de overfitting** com 241 variantes
- **Sinais dependentes** (EFF_RATIO, CHOP, TUESDAY) que nao agregam valor independente

**O parquet atual esta funcional** (PA_SIGNAL_DIR V8.0 aplicado corretamente via scripts de update), mas **nao e reproduzivel** a partir do `build_continuous_indicators.py` sozinho. Qualquer rebuild do zero falharia.

**Recomendacao final:** Executar Fase 1 (consolidacao do codigo em um unico script de rebuild). So entao prosseguir com validacao de outros sinais ou deploy.

---

**Arquivos Referenciados:**
- `meta_trade5/scripts/build_continuous_indicators.py` — Codigo de geracao (com bug de ordenacao no rebuild do zero)
- `meta_trade5/scripts/update_signal_dir_v8.py` — Update V8.0 (correto, usado no ciclo anterior)
- `meta_trade5/scripts/update_v8_optimized.py` — Update com parametros otimos (correto)
- `meta_trade5/scripts/build_signal_dir_variants.py` — Geracao de variantes (duplicacao de logica)
- `meta_trade5/backtest/engine_v2.py` — Engine (correto, sem look-ahead)
- `meta_trade5/docs/WIN_docs/V68_FULL_RESCAN_REPORT.md` — Resultados historicos
- `meta_trade5/docs/WIN_docs/V72_ENSEMBLE_FINAL_REPORT.md` — Ensemble
- `meta_trade5/data/super_win_continuous.parquet` — Parquet (funcional, mas nao reproduzivel do zero)
