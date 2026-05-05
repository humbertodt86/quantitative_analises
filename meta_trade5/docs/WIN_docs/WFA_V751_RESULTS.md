# WFA - Walk-Forward Analysis V7.5.1

**Data:** 2026-01-02 a 2026-03-31
**Folds:** 3 mensais (Jan, Fev, Mar)
**Criterio:** 2+ folds positivos + PnL/dia medio > 0
**Custo:** 30 pts/trade

## Configs Testadas

| Config | Descricao |
|--------|-----------|
| BASE | Sem filtros microestrutura |
| VWAP_M03 | Filtro VWAP_Z <= -0.3 |

## Resultados por Fold

| Config | Jan Net | Jan N | Fev Net | Fev N | Mar Net | Mar N | Total | +/3 | PnL/dia | Passou |
|--------|---------|-------|---------|-------|---------|-------|-------|-----|---------|--------|
| WFA_BASE_TP3060 | +5019 | 3 | +15719 | 11 | +4208 | 60 | +24946 | 3/3 | +2239.9 | SIM |
| WFA_VWAP_M03_TP3060 | +5019 | 3 | +15719 | 11 | +5328 | 57 | +26066 | 3/3 | +2273.3 | SIM |

## Conclusao

**WFA_VWAP_M03_TP3060 PASSOU WFA.** Robustez temporal confirmada em 3/3 folds. PnL total: +26066 pts | PnL/dia: +2273.3.