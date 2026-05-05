# V139 — Guia de Operação e Problemas Conhecidos

## Como confirmar que o código correto foi carregado

A primeira linha do log após o startup mostra a versão:

```
V139 started | version=v139.1 | symbol=WINM26 | magic=202702 | init_latency=...
```

- `version=v139.1` → código correto carregado
- `magic=202702` → magic atualizado

Se aparecer `magic=202701` ou sem `version=`, o bot está rodando código antigo.

---

## Procedimento correto de reinicialização

### Sem posição aberta (situação normal)
1. No Command Center, clique no botão do V139 para parar o processo
2. Edite o arquivo se necessário e salve
3. Clique novamente para iniciar
4. Verifique no log: `version=v139.1 | magic=202702`

### Com posição aberta (CRÍTICO)
**Nunca reinicie o bot com posição aberta.**

Ao reiniciar com posição aberta:
- O bot detecta o ticket pelo magic number via `positions_get`
- Recria o `entry_state` zerado: `{"ticket": ..., "be_active": False, "mode": mode}`
- Perde `tp_pts`, `entry_slope`, `tp30_mode` — a lógica de defesa da posição fica comprometida

**Procedimento com posição aberta:**
1. Aguarde a posição fechar (TP, SL ou panic close às 17:55)
2. Só então pare e reinicie o bot

### Após fazer edições no arquivo
O Python lê o `.py` do disco apenas na inicialização — mudanças no arquivo **não afetam** o processo já em execução. Sempre reinicie após editar.

---

## Bugs corrigidos / Atenção

### Bug 1 — `order_send` com argumento nomeado (crítico)
**Sintoma no log:**
```
last_error_code: -2, last_error_msg: 'Unnamed arguments not allowed'
result_is_none: True, send_style: 'named'
```
**Causa:** `mt5.order_send(request=req)` — a versão atual do pacote MetaTrader5 não aceita argumento nomeado. Retorna `None` com erro -2 **sem lançar TypeError**, portanto o fallback posicional nunca era acionado.

**Correção em `timed_mt5_order_send` (bot_mt5_v139.py):**
```python
# ERRADO — não fazer assim:
result = mt5.order_send(request=req)   # retorna None silenciosamente

# CORRETO:
result = mt5.order_send(req)           # posicional, padrão da API MT5
```

### Bug 2 — Campo `comment` excede 31 caracteres (crítico)
**Sintoma no log:**
```
last_error_code: -2, last_error_msg: 'Invalid "comment" argument'
result_is_none: True
```
**Causa:** O MT5 rejeita ordens com `comment` acima de 31 caracteres.

**Correção (linha ~892):**
```python
# ERRADO:
"comment": f"V139 {mode} {risk_tag} d={abs(dist):.0f}",

# CORRETO:
"comment": f"V139 {mode} {risk_tag} d={abs(dist):.0f}"[:31],
```

**Atenção:** este é o bug que retorna com mais frequência após edições. Ao fazer qualquer ajuste nas linhas próximas ao bloco `req = {...}`, verifique se o `[:31]` continua presente.

---

## V139 Novidades (vs V100)

### v139.2 - Fix ADX Warmup
- Carrega 600 candles no startup para warmup do ADX
- Appenda novo candle a cada iteração (rolling window)
- Mantém ADX calculado corretamente, evitando NaN

### v139.1 - S/R Buffer Logic
V139 implementa a lógica de S/R buffers validada na V138:
- **SNIPER** (09:45-11:00): tp_sr_pct=0.3, tp_buffer=90%, sl_buffer=110%
- **HUNTER** (11:00-14:00): tp_sr_pct=0.0 (puro ATR)
- **SCALPER** (14:00-17:30): tp_sr_pct=0.4, tp_buffer=90%, sl_buffer=110%

### Book Imbalance como soft preference
V139 loga e exibe no status o `edge_type`:
- `FAVORABLE`: LONG quando concentração abaixo, SHORT quando acima
- `UNFAVORABLE`: LONG quando concentração acima, SHORT quando abaixo
- `NEUTRAL`: sem sinal claro

**Não bloqueia entries** — é apenas uma preferência e warning.

### Whale como risk warning
V139 loga quando `tape_whale=True` + `edge_type=UNFAVORABLE`:
- Warning: `RISK_HIGH_UNFAVORABLE_WHALE`
- Não bloqueia, mas aumenta atenção

### Telemetria V138
V139 loga em JSONL todos os indicadores V138:
- `book_imbalance`, `tape_whale`, `tape_score`, `tape_net_delta`
- `conc_at_price`, `conc_below`, `conc_above`
- `edge_type` para cada signal

---

## Comportamentos normais (não são bugs)

### BLOCK_TIME
O bot bloqueia entradas antes das 09:30 e após as 17:30. Normal.

### BLOCK_VOLATILITY
O bot bloqueia quando `ATR < 200` ou `ATR > 800`. Se o mercado estiver em baixa volatilidade, o bot fica em BLOCK_VOLATILITY por horas. Normal — é um filtro de qualidade.

### entry_filter_reject com adx_delta negativo
Em modo STRONG, o bot exige ADX crescente (`adx_delta > 0.5`). Se o ADX estiver caindo, rejeita o sinal mesmo que a direção esteja correta. Normal.

### no_signal_gate
Preço não atingiu a distância mínima do gatilho (160/220/260 pts conforme o regime). Normal.

---

## Checklist de deploy

Antes de reiniciar o bot, verifique:

- [ ] `MAGIC = 202702` em `bot_mt5_v139.py`
- [ ] `VERSION = "v139.2"` presente
- [ ] `mt5.order_send(req)` posicional no `try` de `timed_mt5_order_send`
- [ ] `"comment": f"..."[:31]` no bloco de entrada (~linha 892)
- [ ] Nenhuma posição aberta com magic 202702 antes de reiniciar
- [ ] Após iniciar, confirmar no log: `version=v139.1 | magic=202702`

---

## Arquivos

- `bot_mt5_v139.py` — Bot principal
- `bot_status_v139.json` — Status file (lido pelo Command Center)
- `logs/v139_YYYYMMDD.log` — Log de texto
- `logs/v139_telemetry_YYYYMMDD.jsonl` — Telemetria JSONL