# Relatório Consolidado — Ciclos 10 a 19

## Ciclo 10 ✅ — MIXED Ensemble (3 estratégias)
| Métrica | Valor |
|---------|-------|
| Abordagem | 3 modos no mesmo engine, sem filtro de regime |
| OOS Net | **+62.176** |
| WR | 48.0% |
| PF | 3.30 |
| Trades | 344 |
| Multi-voto | 64% (+45.467) |
| Guardrails | BE=999999 HP=2 CD=0 |
| Engines | 3/3 ✅ |
| Tempo | 2.7min |

## Ciclo 11 ✅ — 5 Estratégias
| Métrica | Valor |
|---------|-------|
| Abordagem | 5 modos (adicionados RANGE_REV_S80, CHOP_RANGE) |
| OOS Net | **+63.047** |
| WR | 45.5% |
| PF | 2.67 |
| Trades | 396 |
| Multi-voto | 42% (+30.255) |
| Modo dominante | CHOP_RANGE (174 trades) |
| Engines | 3/3 ✅ |
| Tempo | 2.6min |

## Ciclo 12 ❌ — Falha na criação do script
Falha devido a erro de sintaxe na substituição de string do MODES dict. Necessário reescrever manualmente.

## Ciclo 13 ❌ — Não executado (dependente do 12)

## Ciclo 14 ❌ — Não executado

## Ciclo 15 ❌ — Não executado

## Ciclo 16 ❌ — Não executado

## Ciclo 17 ❌ — Não executado

## Ciclo 18 ❌ — Não executado

## Ciclo 19 ❌ — Não executado

---

## Problemas Identificados no Processo

| Problema | Causa | Solução |
|----------|-------|---------|
| Scripts C12-19 falharam | Substituição de string no MODES dict quebrou sintaxe | Usar `write` para criar cada script individualmente, não manipular strings |
| Template genérico não funcionou | `__file__` + problemas de path no script genérico | Cada ciclo precisa de seu próprio script isolado |
| Batch automático complexo demais | F-strings aninhadas + JSON + subprocess | Criar scripts individuais com `write`, executar com `bash` |

## Próximos Passos

Para executar C12-19 corretamente, cada script precisa ser:
1. Criado com `write` (0% de chance de erro de sintaxe)
2. Executado com `python -u script.py` 
3. Cerca de 3min cada → ~24min para os 8 restantes

Recomendação: criar scripts individuais com base no `ciclo10_ensemble.py` que funcionou, alterando apenas MODES e CYCLE.
