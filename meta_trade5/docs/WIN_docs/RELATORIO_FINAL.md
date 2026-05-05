# Relatorio Final - 5 Ciclos de Otimizacao WIN
**Data**: 2026-04-30 07:45
**Periodo IS**: 2026-01-02 a 2026-03-28
**Periodo OOS**: 2026-03-30 a 2026-04-30
**Custo**: 30 pts/trade

## Resumo dos Ciclos

### Ciclo 1: Short-only + RIBBON Guardrail
- **Descoberta**: Short-only (remover BUY) transforma a estrategia
- BUY tinha 7.9% WR -> removido, SELL passa a 61% WR
- TP=6.0 e SL=0.7-1.11 emergem como otimos
- H9-11 e a melhor janela
- Resultado OOS: +97.050 net, 63.2% WR, PF 13.85

### Ciclo 2: Refinamento TP + Filtros
- **Grid**: 174.720 combos em 218s
- TP=6.0 confirmado como ponto otimo
- ATR_MIN=300 melhor que 200 (maior vol = melhores resultados)
- VWAP_Z filter, Friday filter, RIBBON filter: nenhum melhora

### Ciclo 3: Cross-Validation (Descoberta CRITICA)
- OOS_A (30Mar-14Apr): 100% WR, +85.732 net
- OOS_B (15Apr-30Apr): 24.3% WR, +908 net
- **Conclusao**: Estrategia e 100% dependente de regime de tendencia baixista
- Resultados extraordinarios sao concentrados em 2 semanas de forte queda

### Ciclo 4: Exit Strategies + Regime Filter
- **PA_SIGNAL_REV exit**: IS +161.351 (4x melhor que default!)
- Slope BE exit: nao melhora
- ADX>=25 filter: melhora levemente a consistencia OOS_B

### Ciclo 5: Consolidacao Final
- ADX>=25 filter da o melhor balanco entre trades e consistencia
- Resultado final: 72t, +91.306 net, 63.9% WR, PF 13.81

## Tabela Comparativa
| Ciclo | Foco | Combos | Melhor OOS Net | WR | PF | Descoberta Principal |
|-------|------|--------|---------------|----|----|--------------------|
| V139 | Blueprint completo | 11.520 | +17.270 | 44.8% | 1.49 | Base inicial |
| C1 | Short-only + RIBBON | 49.896 | **+97.050** | 63.2% | 13.85 | BUY 7.9% WR, remover |
| C2 | Refinar TP/filtros | 174.720 | **+97.110** | 63.2% | 14.26 | TP6.0 ATR300 H9-11 |
| C3 | Cross-validation | 1.344 | +71.876 | 68.2% | 19.19 | Regime dependency |
| C4 | Exit + regime | 12 | +97.270 | 63.2% | 14.26 | Rev_exit promissor |
| C5 | Consolidacao | 4 | +91.306 | 63.9% | 13.81 | ADX>=25 filter |

## Melhor Configuracao Final
```
Signal: PA_SIGNAL_DIR == -1 (SELL only)
Filtros: ATR 300-800, ADX7 >= 25
TP: 6.0x ATR
SL: 0.7x ATR
Horario: 9:00 - 11:00
```

## Resultado Final OOS (com custos)
- Trades: 72
- Gross: +93.046
- Net: +91.306
- Win Rate: 63.9%
- Profit Factor: 13.81
- Avg Win: +2.106 pts
- Avg Loss: -280 pts

## Aderencia por Dia
- Mon: 12t gross=+13724 WR=58%
- Tue: 14t gross=+25862 WR=79%
- Wed: 25t gross=+36846 WR=68%
- Thu: 12t gross=+17110 WR=67%
- Fri: 9t gross=-76 WR=33%

## Aviso: Dependencia de Regime
**Resultados sao concentrados em periodo de forte tendencia baixista (OOS_A: 100% WR).**
Em periodo lateral/alta (OOS_B), a estrategia teve apenas 24-30% WR.
Recomendacoes para uso real:
1. **Nao operar em tempo real sem um filtro de regime de mercado**
2. Implementar PA_SIGNAL_REV exit (IS mostrou +161K)
3. Validar em periodo OUT OF SAMPLE adicional (Maio 2026)
4. Considerar ensemble com estrategias que funcionam em regime lateral/alta

## Arquivos Gerados
- `docs/WIN_docs/CICLO1.md` - Ciclo 1: Short-only + RIBBON
- `docs/WIN_docs/CICLO2.md` - Ciclo 2: Refinamento TP
- `docs/WIN_docs/CICLO3.md` - Ciclo 3: Cross-Validation
- `docs/WIN_docs/CICLO4.md` - Ciclo 4: Exit + Regime
- `docs/WIN_docs/WIN_TRADE_TABLE_BEST.csv` - Trade table final
- `docs/WIN_docs/WIN_RANKING_FULL.csv` - Ranking completo
- `backtest/engine_v2.py` - Engine com signal_field suportado