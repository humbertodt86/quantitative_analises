# Arquitetura do Bot — Modelo de 4 Camadas (V139+)

## Visão Geral

O bot opera em 4 camadas independentes, cada uma com responsabilidades específicas. Dados fluem de cima para baixo (enriquecimento → seleção → execução → proteção), e decisões de risco fluem de baixo para cima (proteção pode vetar qualquer nível).

```
┌──────────────────────────────────────────────────┐
│            CAMADA 1: INTELIGÊNCIA LOCAL           │
│     Enriquecimento + Cálculo de Sinais           │
│  (ER, CVD, Book, S/R, ATR, ADX, PA_*)          │
├──────────────────────────────────────────────────┤
│            CAMADA 2: SELEÇÃO E CONVICÇÃO          │
│     Ensemble Selector + Pesos por Regime         │
│  (Votação ponderada, veto, threshold)           │
├──────────────────────────────────────────────────┤
│            CAMADA 3: GUARDRAILS TÁTICOS           │
│     Filtros Temporais + BE/HP + Cooldown         │
│  (Hora, dia, lunch, break-even, H-Progress)     │
├──────────────────────────────────────────────────┤
│            CAMADA 4: RISCO GLOBAL                 │
│     Circuit Breaker + Daily Stop + Regime Shift  │
│  (Proteção patrimonial, fechamento forçado)     │
└──────────────────────────────────────────────────┘
```

---

## Camada 1 — Inteligência Local (Enriquecimento + Sinal)

### O que faz

Transforma o tick/candle bruto em um "contexto rico" que as estratégias consomem. As estratégias **não calculam indicadores** — elas leem colunas pré-computadas.

### Fluxo

```
Tick/Candle bruto
    ↓
[Pré-Processador] → Calcula: ER, ADX7, ATR, CVD_RAW, CVD_ACCUM,
                    BOOK_IMB, EMA5_SLOPE, GK_RATIO, CHOP_INDEX,
                    S/R zones, VWAP, RSI2, RSI14, BB, Keltner, ...
    ↓
[Gerador de Sinais] → 119 variantes PA_* (PA_REV_RSI, PA_SIGNAL_DIR,
                      PA_STRONG_TREND, PA_VWAP_Z, ...)
    ↓
Linha enriquecida pronta (super_win_continuous.parquet — 185 colunas)
```

### Status Atual

| Componente | Implementado? | Onde |
|-----------|:-------------:|------|
| ER (Efficiency Ratio) | ✅ | `engines/check_dist.py` — `calc_efficiency_ratio()` |
| ADX7, ATR | ✅ | `super_win_continuous.parquet` |
| CVD_RAW, CVD_ACCUM | ✅ | `super_win_continuous.parquet` |
| BOOK_IMB | ✅ | `super_win_continuous.parquet` |
| 119 variantes PA_* | ✅ | `super_win_continuous.parquet` |
| S/R zones intraday | ⚠️ Parcial | `gaps_is.parquet` (não no super) |
| Regime labels (ER+ADX) | ✅ | `engines/check_dist.py` |
| Pré-processador em runtime | ❌ | Só existe no `build_continuous_indicators.py` |

### Ajuste Necessário

O pré-processador existe apenas no script de build (`build_continuous_indicators.py`), que gera o parquet estaticamente. Para produção ao vivo, seria necessário um **módulo de enriquecimento em tempo real** que:

1. Recebe o candle fechado
2. Calcula ER, ADX, CVD, Book a partir do tick data
3. Adiciona ao DataFrame em memória
4. Engine lê do DataFrame (já funciona)

Para backtest, o parquet estático já contém tudo — **nenhuma modificação necessária.**

---

## Camada 2 — Seleção e Convicção (Ensemble Selector)

### O que faz

Decide **qual estratégia comanda** com base no regime de mercado. Não é uma média simples — é uma votação ponderada com poder de veto.

### Fluxo

```
Linha enriquecida
    ↓
[Regime Classifier] → Range / Trend / Mixed
    ↓
[Seletor] → Para cada estratégia:
              - Verifica peso no regime atual
              - Coleta voto (comprar/vender/neutro)
              - Aplica threshold de convicção
              - Se convicção < threshold → VETO (não opera)
    ↓
Decisão final (entrar com tamanho X, ou não entrar)
```

### Status Atual

| Componente | Implementado? | Onde |
|-----------|:-------------:|------|
| Regime classifier (ER+ADX7) | ✅ | `engines/check_dist.py` |
| Pesos por regime | ⚠️ Parcial | `ciclo7_ensemble.py` (pós-processo, não em runtime) |
| Votação ponderada | ❌ | Não implementada no engine_v2 |
| Threshold de convicção | ❌ | Não implementado |
| Veto por regime | ❌ | Não implementado |

### Ajuste Necessário

O engine_v2 atualmente suporta **múltiplos modes** em um único `simulate()`, onde cada mode é uma estratégia independente. Mas ele NÃO suporta:

- **Votação ponderada**: todos os modes ativos entram se o sinal disparar. Não há soma de votos com peso.
- **Veto**: se um mode dispara e outro também, ambos entram. Não há "um veta o outro".
- **Threshold de convicção**: não há verificação de "concordância mínima entre estratégias".

**Para implementar:** Seria necessário modificar o `engine_v2.py` para:

```python
# NOVO: Lógica de ensemble no simulate()
votos = []
for mode_name, mode_cfg in self.config['modes'].items():
    if signal_fired(mode_cfg, candle):
        votos.append({
            'direcao': mode_cfg.get('direction', 0),
            'peso': mode_cfg.get('weight', 1.0),
            'conviccao': mode_cfg.get('conviction', 1.0),
        })

# Soma ponderada dos votos
soma = sum(v['direcao'] * v['peso'] * v['conviccao'] for v in votos)
if abs(soma) < CONVICCAO_THRESHOLD:
    next  # VETO — nenhuma entrada

direcao = 1 if soma > 0 else -1
```

**Alternativa (sem modificar o engine):** Orquestrar a votação externamente, criando um script que:
1. Para cada candle, calcula regime
2. Para cada estratégia, verifica se o sinal disparou
3. Acumula votos ponderados
4. Se passar do threshold, cria um sinal composto
5. Engine executa o sinal composto

---

## Camada 3 — Guardrails Heurísticos e Táticos

### O que faz

Regras de "sobrevivência" que protegem o robô de entrar em horários/dias ruins e gerenciam a posição após a entrada.

### Fluxo

```
Antes da entrada (hard blocks):
  ├─ Horário válido? (10:00-17:00) → Não → PULA
  ├─ Sexta-feira após 15:00? → Sim → PULA
  ├─ Lunch time (12:00-14:00)? → Sim → PULA (se liquidez baixa)
  └─ Passou → Pode entrar

Após a entrada (gestão ativa):
  ├─ Break-even: se lucro > BE_trigger, move SL para entrada
  ├─ H-Progress: se após N candles lucro < threshold, reduz TP para 30%
  ├─ Cooldown: após SL, espera N candles antes de reentrar
  └─ Slope Decay: reduz TP se a inclinação da EMA5 diminui
```

### Status Atual

| Guardrail | Implementado? | Onde |
|-----------|:-------------:|------|
| Horário mínimo/máximo | ✅ | `hour_min` / `hour_max` no config |
| Lunch filter | ✅ | `modo_busca` desliga; produção ativa |
| Sexta-feira filter | ❌ | Não existe no engine_v2 |
| Break-even (BE) | ✅ | `be_trigger` / `be_offset` no config |
| H-Progress (TP30) | ✅ | `hp_candles` / `hp_th` / `tp30_pct` no config |
| Cooldown | ✅ | `cooldown_candles` no config |
| Slope Decay | ✅ | `slope_decay` no config |
| Grace Period | ✅ | `grace_candles` no config |

### Ajuste Necessário

**Filtro de Sexta-feira** precisaria ser adicionado ao engine_v2:

```python
# NOVO: No config dict
'filters': {
    'day_of_week': {'exclude': [5]},  # exclui sexta
}
```

O `day_of_week` já existe no `super_win_continuous.parquet` (coluna 57), então o engine só precisa suportar o filtro. Isso já funciona — o engine_v2 aceita qualquer coluna no `filters` dict.

**Conclusão:** A Camada 3 é a MAIS completa. Quase todos os guardrails estão implementados. Faltam apenas filtros de dia da semana, que são triviais de adicionar (já que o engine suporta filtros por coluna arbitrária).

---

## Camada 4 — Risco Global (Global Risk Manager)

### O que faz

Proteção patrimonial que opera acima das estratégias individuais. Pode fechar posições, reduzir tamanho ou parar o robô completamente.

### Fluxo

```
Durante a operação (monitoramento contínuo):
  ├─ Perda diária > Daily Stop? → Fecha tudo, para o robô até amanhã
  ├─ 3 SLs consecutivos? → Cooldown de 60 min
  ├─ Regime mudou com posição aberta? → Reduz alvo ou fecha
  └─ Tudo ok → Continua normal
```

### Status Atual

| Componente | Implementado? | Onde |
|-----------|:-------------:|------|
| Circuit Breaker (N SLs consecutivos) | ✅ | `engine_v2.py` (5 SLs, hardcoded) |
| Daily Stop | ❌ | Não existe |
| Regime Shift Protection | ❌ | Não existe |
| Cooldown progressivo | ❌ | Não existe |

### Ajuste Necessário

O engine_v2 precisaria de modificações para suportar:

```python
# NOVO: No config dict (Camada 4)
'risk_manager': {
    'daily_stop': -5000,           # perda máxima diária
    'consecutive_sl_limit': 3,     # SLs consecutivos antes de cooldown
    'consecutive_sl_cooldown': 60, # minutos de pausa após N SLs
    'regime_shift_action': 'close',  # o que fazer se regime mudar
}
```

**Atualmente**, o Circuit Breaker existe mas é fixo em 5 SLs consecutivos (hardcoded). Idealmente, seria configurável via dict.

---

## Mapa de Implementação vs Engine_v2 Atual

| Camada | Componente | Engine suporta? | Ação necessária |
|--------|-----------|:---------------:|-----------------|
| **1** | Enriquecimento prévio | ✅ (parquet estático) | Nada (para backtest). Para produção ao vivo, criar módulo de enriquecimento runtime |
| **1** | S/R zones no super | ❌ | Adicionar ao `build_continuous_indicators.py` |
| **2** | Múltiplos modes | ✅ | Já funciona (`modes` dict) |
| **2** | **Votação ponderada** | **✅** | **Implementado V6.3** — `mode.weight` + `ensemble_threshold` no config |
| **2** | **Threshold de convicção** | **✅** | **Implementado V6.3** — `ensemble_threshold` (default 0.5) |
| **2** | **Veto entre estratégias** | **✅** | **Implementado V6.3** — votos abaixo do threshold não geram entrada |
| **3** | BE/HP/Cooldown/Grace/Slope | ✅ | Já funciona (`behp` dict) |
| **3** | **Filtro de dia da semana** | **✅** | **Documentado V6.3** — `day_of_week: {"exclude": [5]}` via filters |
| **3** | Lunch filter | ✅ | Já funciona (modo produção) |
| **4** | **Circuit Breaker** | **✅** | **Implementado V6.3** — `consecutive_sl_limit` configurável (não mais hardcoded 5) |
| **4** | **Daily Stop** | **✅** | **Implementado V6.3** — `risk_manager.daily_stop` |
| **4** | **Regime Shift Protection** | ❌ | Não implementado — requer monitoramento de regime durante posição aberta |
| **4** | **Cooldown progressivo** | **✅** | **Implementado V6.3** — `consecutive_sl_cooldown` após N SLs consecutivos |

---

## Recomendações

### ✅ Concluído (V6.3)

1. **Votação ponderada (Layer 2)**: Engine_v2 agora suporta `weight` por modo e `ensemble_threshold` — votos coletados de todos os modos, soma ponderada deve exceder threshold
2. **Daily Stop (Layer 4)**: `risk_manager.daily_stop` no config — para o robô quando a perda diária atinge o limite
3. **Circuit Breaker configurável (Layer 4)**: `consecutive_sl_limit` substitui o hardcoded 5
4. **Cooldown progressivo (Layer 4)**: `consecutive_sl_cooldown` após N SLs consecutivos
5. **day_of_week filter (Layer 3)**: Documentado — já funciona via filters dict

### Médio Prazo

1. **Regime Shift Protection**: Monitorar regime durante posição aberta e ajustar alvo
2. **S/R zones no super parquet**: Adicionar ao build de indicadores

### Longo Prazo

1. **Módulo de enriquecimento runtime**: Para produção ao vivo

---

## Referências

| Documento | Conteúdo |
|-----------|----------|
| `engines/README.md` | Arquitetura dos motores F1, F2, F3 |
| `engines/check_dist.py` | Detector de regime (ER + ADX7) |
| `backtest/engine_v2.py` | Engine principal de simulação |
| `docs/WIN_docs/GUIA_CICLOS.md` | Guia de execução de ciclos |
| `data/super_win_continuous.parquet` | Tabela mestra com 185 colunas enriquecidas |

---

*Documentação de arquitetura — V6.3*
*Baseada no modelo de 4 camadas do V139 (refatorado)*
