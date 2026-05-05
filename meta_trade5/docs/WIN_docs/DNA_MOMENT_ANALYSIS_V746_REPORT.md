# DNA Moment Analysis V7.4.6
**Pergunta:** Estamos entrando no momento certo do movimento?

**Data:** 2026-05-03 18:13

## Resumo Comparativo

| Cenario | Candles | Trades | WR% | Slope Entrada | Slope Nao-Entrada | ADX Entrada | ADX Nao-Entrada | GK Entrada | GK Nao-Entrada |
|---------|---------|--------|-----|---------------|-------------------|-------------|-----------------|------------|----------------|
| IS - Hipotese Usuario | 6517 | 92 | 63.0% | -103.84 | 3.98 | 50.1 | 35.6 | 0.0014 | 0.0009 |
| OOS - Hipotese Usuario | 2156 | 33 | 51.5% | -79.14 | 3.14 | 41.0 | 34.0 | 0.0013 | 0.0009 |
| IS - Config Atual | 6517 | 159 | 72.3% | -82.41 | 4.58 | 49.0 | 35.5 | 0.0012 | 0.0009 |
| OOS - Config Atual | 2156 | 67 | 71.6% | -60.64 | 3.89 | 42.2 | 33.9 | 0.0012 | 0.0009 |

## Conclusoes

### Momento da Entrada

- **IS (Hipotese):** Slope medio na entrada = -103.84 (nao-entrada = 3.98)
- **OOS (Hipotese):** Slope medio na entrada = -79.14 (nao-entrada = 3.14)
- **Continuidade:** Em 21.2% das entradas OOS, o slope acelerou no proximo candle.
- **Reversao:** Em 21.2% das entradas OOS, o slope reverteu imediatamente.

**ALERTA:** Menos da metade das entradas OOS tem continuidade de momentum. Isso sugere que estamos entrando TARDE — o movimento ja esta desacelerando quando entramos.

### Recomendacoes

1. **Filtro de aceleracao:** Verificar se slope esta acelerando (derivada do slope > 0 para SELL = slope ficando mais negativo).
2. **Confirmacao de volume:** Verificar se volume esta aumentando no candle de entrada.
3. **Candle range:** Entradas em candles com range maior que a media (range_ratio > 1) podem ter melhor follow-through.

---
*Gerado automaticamente por DNA_Moment_Analysis_V746*
