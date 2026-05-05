"""
F2 — TICK_LAST (engine_v2 com last prices, sem bid/ask)
========================================================
Uso: Validacao intermediaria no periodo IS (Jan-Mar) onde so existem last ticks.

Correlacao com F3: 0.988 (spread de 5 pts do WIN e irrelevante).

Diferenca vs F3:
  - Usa last prices (bid = ask = last) → sem spread
  - Mesmos guardrails, TP30, BE, etc. (engine completo)

Uso:
    from engines.f2_tick_last import F2
    f2 = F2(df, ticks_last)
    net, trades, wr, pf = f2.eval(signal, tp, sl, ...)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engines.f3_tick_ba import F3

class F2(F3):
    """F2 = F3 com last prices (bid=ask=last). Herda toda a logica."""
    pass
