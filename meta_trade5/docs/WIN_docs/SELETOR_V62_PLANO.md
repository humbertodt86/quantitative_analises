# Seletor V6.2 — Diagnóstico e Rota de Correção

## Diagnóstico do V6.1 (O que falhou)

| Problema | Causa | Impacto |
|----------|-------|---------|
| **Threshold 0.5** | Otimizado para menor valor que já deu lucro no passado | Vira OR lógico, não ensemble |
| **666 trades/mês** | Sem filtro de convicção real | Overtrading, 30 pts de custo por trade |
| **Pesos fixos** | Treinado só em Janeiro | Não acompanha mudança de regime |
| **PnL -18K Fev / -11K Abr** | Ensemble fraco + candle-level sim | Perda consistente |
| **S/R, Tape Reading ausentes** | Desligados desde o início | Falta microestrutura que o V139 tinha |

---

## Meta
- **+1.000 pts/dia** líquido (já descontando COST=30)
- **90% dos dias positivos**
- **OU** 50 ciclos de otimização
- Validação em OOS cego (Abril)

---

## Plano de Ação V6.2

### Ciclo 0 — Baseline Regime Classifier
Antes de qualquer otimização, validar o **regime classifier**:

```
Para cada candle no OOS (Abril):
  regime_predito = classificar(REGIME_TREND, REGIME_VOL, CVD_SIGNAL, BOOK_IMB)
  regime_real = olhar para trás: o candle seguinte foi trend ou range?

Acurácia mínima exigida: 70%
Se < 70%: rever features do regime classifier
```

### Ciclo 1 — Guardrails + Risco Individual (separado do ensemble)
Em vez de otimizar tudo junto, **primeiro otimizar cada estratégia com seus guardrails**:

```
Para cada estratégia (PA_SIGNAL_DIR, PA_VCP, etc):
  Grid sobre:
    - BE_trigger: [100, 150, 200, 250]
    - BE_offset: [10, 15, 20, 25]
    - HP_candles: [1, 2, 3]
    - HP_th: [0.10, 0.15, 0.20]
    - cooldown: [1, 2, 3]
    - slope_decay: [0.3, 0.5, 0.7]
    - min_sl: [50, 100, 150]
    - max_sl: [300, 500, 800]
  
  Critério: MAX(drawdown < 20%, trades > 20, WR > 20%)

Resultado: cada estratégia tem seu próprio "perfil de risco"
```

### Ciclo 2 — Feature Engineering do Regime Classifier
Adicionar de volta o que o V139 tinha e foi desligado:

| Feature | Fonte | Por que importante |
|---------|-------|--------------------|
| **S/R buffers** | `dist_to_d1_high`, `dist_to_d1_low` | V139 usava 90%/110% para TP/SL |
| **Book Imbalance** | BOOK_IMB (já no parquet) | Pressão institucional real |
| **CVD divergência** | CVD_ACCUM + preço | Se preço sobe e CVD cai = bear trap |
| **Tape Reading** | tick_delta, whale_count | Microestrutura de curto prazo |
| **VOL_SPIKE** | volume > 3x média | Confirmação de rompimento |
| **REGIME_STRETCH** | ATR_STRETCH discretizado | Preço esticado = reversão iminente |

### Ciclo 3 — Ensemble com Pesos Móveis
Substituir pesos fixos por **janela deslizante**:

```
A cada 5 dias:
  1. Recalcular matriz de pesos nos últimos 20 dias
  2. Estratégias com Sharpe < 0.5 no período → peso ZERO
  3. Estratégias com drawdown > 30% → peso NEGATIVO (veto)
  4. Threshold adaptativo: CONVICCAO = 1.5 + (volatilidade_atual / volatilidade_media)
```

### Ciclo 4 — Ensemble com Hierarquia
Não usar todas as 21 estratégias. Selecionar **apenas as top 5 por regime**:

```
SE REGIME_TREND=1:
  Estratégias: PA_SIGNAL_DIR, PA_STRONG_TREND, PA_ADX_BREAK, PA_EFF_RATIO, PA_HMA_CROSS
  (5 estratégias de momentum)

SE REGIME_TREND=0 (range):
  Estratégias: PA_REV_RSI, PA_VCP, PA_CHOP, PA_LIQ_GRAB, PA_BB
  (5 estratégias de reversão/range)

SE REGIME_VOL=alta:
  Ativar guardrails mais apertados (BE mais cedo, cooldown maior)
  Diminuir TP (menos exposição)

SE REGIME_VOL=baixa:
  Aumentar SL (mais espaço para o trade respirar)
```

### Ciclo 5 — Global Risk Manager Reforçado

```
REGRAS:
1. Se 3 SLs consecutivos → cooldown de 60 min (não apenas bloquear o dia)
2. Se PnL do dia < -5.000 → desligar até próxima sessão
3. Se regime mudar durante trade aberto:
   - trend → chop: ativar H-Progress imediatamente
   - chop → trend: aumentar SL em 20% (deixar o trade respirar)
4. Se CVD divergir do preço por 3 candles consecutivos → fechar posição
5. Máximo 1 trade por hora (evitar overtrading)
```

### Ciclo 6 — Meta-Backtest Final

```
1. Treino: Jan (pesos) + Fev (teste threshold)
2. Validação: Março (calibração guardrails)
3. OOS cego: Abril (relatório final)
4. Métricas: PnL/dia, % dias positivos, Sharpe, max drawdown
5. Se PnL/dia < 1000 OU %dias_positivos < 90%:
   → Voltar ao Ciclo 1 com ajustes
```

---

## Timeline Estimada

| Ciclo | O que | Tempo |
|-------|-------|-------|
| **0** | Validar regime classifier (acurácia > 70%) | ~5min |
| **1** | Otimizar guardrails individuais (21 estratégias × 10 combos) | ~30min |
| **2** | Feature engineering + S/R, Tape Reading | ~15min |
| **3** | Pesos móveis + threshold adaptativo | ~10min |
| **4** | Hierarquia por regime | ~10min |
| **5** | Global Risk Manager | ~10min |
| **6** | Meta-backtest + relatório | ~15min |
| **Total** | | **~1,5h** |

---

## Arquivos

| Arquivo | Descrição |
|---------|-----------|
| `scripts/_v62_ciclo0.py` | Validação do regime classifier |
| `scripts/_v62_ciclo1.py` | Grid de guardrails individuais |
| `scripts/_v62_ciclo2_6.py` | Feature engineering + ensemble + risk + meta-backtest |
| `docs/WIN_docs/SELETOR_V62_PLANO.md` | Este arquivo |
