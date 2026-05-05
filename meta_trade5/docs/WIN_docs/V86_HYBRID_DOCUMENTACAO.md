# V8.6 HYBRID — DOCUMENTAÇÃO TÉCNICA

**Data**: 2026-05-04
**Status**: ✅ Estratégia implementada | ❌ Scripts F1/F2/F3 ausentes | ❌ Documentação não atualizada
**Versão Anterior**: V8.5 (Abril 2026)
**Próxima Versão**: V8.7 Otimizado (em implementação)

---

## 1. VISÃO GERAL

V8.6 é uma estratégia **HYBRID** que opera em TODOS os regimes (sem filtro de regime), com melhorias sobre V8.5:

| Melhoria | V8.5 | V8.6 | Impacto |
|----------|------|------|---------|
| `gatilho_min_range` | 150 pts | **200 pts** | PF RANGE: 2.95→11.08 |
| `progress_m1_candles` | 4 candles | **2 candles** | Detecção precoce (2min vs 4min) |
| `be_offset` | 10 pts | **50 pts** | BE rende R$8 líquido (era R$-2) |
| `max_sl_consec` | ativo | **99 (desativado)** | Avaliação completa |

---

## 2. ARQUIVOS EXISTENTES

### Estratégia (Implementada)
```
meta_trade5/backtest/strategies/v86.py  ✅
```

**Script F1/F2/F3**: ❌ **NÃO EXISTE** — usar `f1_full_scan_v85.py` como base

### Scripts Relacionados
```
meta_trade5/scripts/f1_full_scan_v86.py          ✅ (existe, mas não na pasta engines/)
meta_trade5/scripts/compare_buy_sell_v86.py      ✅
meta_trade5/scripts/show_v86_top10.py            ✅
```

---

## 3. PARÂMETROS V8.6

### ADX7 — Detecção de Regime
```python
adx_period: int      = 14
adx_threshold: float = 25.0
use_adx7: bool       = True  # ADX7 detecta regime mais cedo
```

### Gatilhos Separados por Modo
```python
gatilho_min_range: int   = 200   # RANGE: dist mínima 200pts
gatilho_min_trend: int   = 150   # TREND: dist mínima 150pts
gatilho_max: int         = 700   # fixo, aplicado em RANGE only
gatilho_max_atr_mult: float = 0.0  # off — usa gatilho_max fixo
```

### Filtros (SEM V87)
```python
adx_max: float       = 9999.0    # sem limite ADX superior
cooldown_candles: int = 0         # sem cooldown
```

### TP/SL
```python
tp_range_mult: float = 1.4
sl_range_mult: float = 0.8
tp_trend_mult: float = 1.5
sl_trend_mult: float = 0.8
ema_slope_max: float = 80.0
```

### H-Progress M1 (2 candles, TP30%)
```python
use_m1_progress: bool    = True
progress_m1_candles: int = 2      # 2 candles M1 (~2min)
progress_threshold: float = 0.15
progress_mode: str       = "TP30"
progress_tp_pct: float   = 0.30
grace_candles: int       = 6
be_offset: int           = 50     # BE+50pts = R$8 líquido
```

### H-Slope
```python
slope_decay_factor: float = 0.65
```

### Circuit Breaker
```python
max_sl_consec: int = 99  # desativado
```

---

## 4. DIFERENÇAS V8.6 vs V8.7

| Característica | V8.6 | V8.7 |
|----------------|------|------|
| **ADX_MAX** | ❌ Sem limite (aceita ADX > 50) | ✅ Filtra ADX > 50 |
| **GATILHO_MAX** | ✅ Fixo em 700 (RANGE only) | ✅ Dinâmico por ATR |
| **GATILHO_MIN_TREND** | 150 pts | **300 pts** |
| **COOLDOWN** | ❌ Sem cooldown | ✅ Cooldown pós-SL |
| **Grid Search** | ❌ Não otimizado | ✅ Poda por correlação |

---

## 5. RESULTADOS (BACKTEST TICK WINJ26)

**Período**: Mar29–Abr07/2026 (6 sessões)
**Ativo**: WINJ26 (ticks reais)

| Métrica | Valor |
|---------|-------|
| **N** | 137 trades |
| **WR_tp** | 42.3% |
| **PF** | 11.08 |
| **SL_real** | 4 (2.9%) |
| **PnL Diário** | +1840 pts/dia |

---

## 6. COMO EXECUTAR V8.6

### F1 Screening (Pre-filtro)
```bash
# Script não existe na pasta engines/ — usar V8.5 como base
python scripts/f1_full_scan_v85.py \
    --strategy v86 \
    --signal PA_SIGNAL_DIR \
    --mode HYBRID \
    --tp-mult 1.0 1.5 2.0 2.5 3.0 \
    --sl-mult 2.0 3.0 4.0 5.0 \
    --atr-min 200 400 600 \
    --atr-max 400 600 800
```

### F2 Validation (Top 10)
```bash
# Script não existe — criar baseado em f1_full_scan_v85.py
python scripts/f1_full_scan_v85.py \
    --strategy v86 \
    --signal PA_SIGNAL_DIR \
    --mode HYBRID \
    --top-10 \
    --validation
```

### F3 Guardrails (Top 3)
```bash
# Script não existe — criar baseado em f1_full_scan_v85.py
python scripts/f1_full_scan_v85.py \
    --strategy v86 \
    --signal PA_SIGNAL_DIR \
    --mode HYBRID \
    --top-3 \
    --guardrails
```

---

## 7. PRÓXIMOS PASSOS

### Imediato (V8.7)
1. ✅ **Documentação criada**: `docs/WIN_docs/GRID_SEARCH_OTIMIZADO_V87.md`
2. ⏳ **Implementar V8.7** em `build_win_signals_v81.py`:
   - Unificar PA_REV_RSI_B10/S90
   - Renomear PA_HMA_CROSS → PA_SMA_CROSS
   - Aplicar grids otimizados (3,150 variantes)
3. ⏳ **Gerar parquets V8.7**: 23 arquivos × 3,150 variantes
4. ⏳ **Executar F1 V8.7**: 7.26M combos @ 50k/s = 2.4 minutos

### Médio Prazo
5. ⏳ **Criar script `f1_full_scan_v87.py`** na pasta `engines/`
6. ⏳ **Atualizar AGENTS.md** com pipeline V8.7
7. ⏳ **OOS Validation** em Abril 2026

---

## 8. LIÇÕES V8.6

### O Que Funcionou
- ✅ **gatilho_min_range=200**: PF RANGE 2.95→11.08 (3.7x)
- ✅ **progress_m1_candles=2**: Detecção 2min vs 4min
- ✅ **be_offset=50**: BE rende R$8 líquido (era R$-2)

### O Que Não Funcionou
- ❌ **max_sl_consec=99**: Sem filtro de perdas consecutivas
- ❌ **adx_max=9999**: Aceita ADX > 50 (overbought extremo)
- ❌ **gatilho_max fixo**: Não adapta à volatilidade do dia

### O Que V8.7 Corrige
- ✅ **Poda por correlação**: 18B → 7.26M combos (2,479x)
- ✅ **Escalonamento geométrico**: Passos que mudam comportamento
- ✅ **Binning ATR**: 3 regimes (Low/Normal/High)
- ✅ **Piso de Viabilidade**: Anti-HFT (SL >= 150pts, TP >= 100pts)

---

## 9. ESTRUTURA DE ARQUIVOS (ATUALIZAR)

### Estrutura Atual (INCORRETA)
```
meta_trade5/
├── backtest/strategies/
│   ├── v86.py              ✅
│   └── v87.py              ✅
├── scripts/
│   ├── f1_full_scan_v86.py ✅ (fora de engines/)
│   └── f1_full_scan_v85.py ✅
└── docs/WIN_docs/
    ├── GRID_SEARCH_OTIMIZADO_V87.md ✅
    └── V86_HYBRID_DOCUMENTACAO.md   ⏳ (ESTE ARQUIVO)
```

### Estrutura Ideal (V8.7)
```
meta_trade5/
├── backtest/strategies/
│   ├── v86.py              ✅
│   └── v87.py              ⏳
├── engines/
│   ├── f1_full_scan_v87.py ⏳ (CRIAR)
│   ├── f2_validation_v87.py ⏳ (CRIAR)
│   └── f3_guardrails_v87.py ⏳ (CRIAR)
└── docs/WIN_docs/
    ├── GRID_SEARCH_OTIMIZADO_V87.md ✅
    └── V86_HYBRID_DOCUMENTACAO.md   ✅
```

---

## 10. COMANDOS ÚTEIS

### Ver Top 10 V8.6
```bash
python scripts/show_v86_top10.py
```

### Comparar BUY vs SELL V8.6
```bash
python scripts/compare_buy_sell_v86.py
```

### Gerar Grid V8.7
```bash
python scripts/build_win_signals_v81_variants.py --version v87
```

### Executar F1 V8.7
```bash
python engines/f1_full_scan_v87.py \
    --all-signals \
    --optimized-grid
```

---

## 11. REFERÊNCIAS

- **Estratégia V8.6**: `backtest/strategies/v86.py`
- **Grid Otimizado V8.7**: `docs/WIN_docs/GRID_SEARCH_OTIMIZADO_V87.md`
- **Inconsistências V8.0/V8.1**: `docs/WIN_docs/V80_V81_INCONSISTENCIAS.md`
- **Validação V8.4**: `docs/WIN_docs/V84_VALIDACAO.md`

---

**Última Atualização**: 2026-05-04
**Autor**: WIN Lead Quant Scientist
**Status**: Documento criado para preencher lacuna de documentação V8.6
