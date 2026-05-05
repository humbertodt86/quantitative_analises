"""
F3 = TICK_BA — engine_v2 com bid/ask real (referencia ouro).

DOIS MODOS DE USO:
  1. com_guardrails=True  (MODO PRODUCAO): BE, Grace, Circuit Breaker, cooldown ATIVOS
     Usar para: validacao final de parametros otimizados, OOS report
  2. com_guardrails=False (MODO BUSCA): IGUAL ao F1 (sem guardrails, so TP30)
     Usar para: comparacao justa com F1, selecao de estrategias
     Neste modo, F3 e F1 devem dar resultados QUASE IDENTICOS

Uso:
    from engines.f3_tick_ba import F3
    f3 = F3(df, ticks_ba)
    # Modo busca (compara com F1)
    net, n, wr, pf = f3.eval(sinal, tp, sl, com_guardrails=False, apenas_sell=True)
    # Modo producao (report final OOS)
    net, n, wr, pf = f3.eval(sinal, tp, sl, com_guardrails=True)

Diferenca entre os modos:
  com_guardrails=True:  BE(200), Grace(2), Cooldown(2), Circuit Breaker(5), Slope Decay(0.5)
                        lunch filter(12-14h), 9:00-9:30 restriction ATIVOS
  com_guardrails=False: BE(off), Grace(off), Cooldown(0), Circuit Breaker(off), Slope Decay(0)
                        lunch filter, 9:00-9:30, cooldown DESLIGADOS (modo_busca)
  Ambos: TP30 ativo (hp_candles=2, hp_th=0.15, tp30_pct=0.30)

FIX: Exit tick-a-tick (engine_v119_v2.py):
  - Antes: usava max(ask_bar)/min(bid_bar) da candle inteira -> PnL superestimado
  - Agora: itera tick por tick, sai no PRIMEIRO que cruza SL/TP
  - Correlacao F2 vs F3 apos fix: >0.99
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backtest.engine_v2 import BacktestEngine

class F3:
    def __init__(self, df, ticks):
        self.eng = BacktestEngine(None)
        self.eng.df = df
        self.eng.load_ticks_for_simulation(ticks)
    
    def eval(self, signal, tp, sl, hm=9, hx=12, atr_min=200, atr_max=800, dist=0, 
             com_guardrails=True, cost=30, apenas_sell=False, min_sl=50, max_sl=500):
        filters = {'ATR': {'min': atr_min, 'max': atr_max}}
        if apenas_sell:
            filters[signal] = {'eq': -1}  # SELL only (comparacao com F1)
        else:
            filters[signal] = {'neq': 0}  # ambos sentidos
        if dist > 0:
            filters['DIST_ABS'] = {'min': dist}
        
        if com_guardrails:
            behp = {'be_trigger': 200, 'be_offset': 25, 'hp_candles': 2, 'hp_th': 0.15,
                    'tp30_pct': 0.30, 'grace_candles': 2, 'hard_stop': 500,
                    'cooldown_candles': 2, 'slope_decay': 0.50}
        else:
            behp = {'be_trigger': 999999, 'be_offset': 999, 'hp_candles': 2, 'hp_th': 0.15,
                    'tp30_pct': 0.30, 'grace_candles': 999, 'hard_stop': 500,
                    'cooldown_candles': 0, 'slope_decay': 0.0}
        
        cfg = {
            'name': 'F3', 'hour_min': float(hm), 'hour_max': float(hx),
            'modo_busca': not com_guardrails,
            'modes': {
                'M': {
                    'enabled': True, 'priority': 1, 'signal_field': signal,
                    'tp_mult': tp, 'sl_mult': sl, 'min_sl': min_sl, 'max_sl': max_sl,
                    'filters': filters, 'behp': behp
                }
            }
        }
        self.eng.load_config_dict(cfg)
        res = self.eng.simulate()
        m = self.eng.calculate_metrics(res)
        net = int(m['pnl'] - len(res) * cost)
        return net, len(res), m['wr'], m['profit_factor']
