"""
Grid Optimization Advisor — Decide quando parar ou continuar buscando
=====================================================================

Implementa a lógica de decisão:
1. Teste da Fronteira (borda do grid)
2. Teste do Planalto (robustez dos vizinhos)
3. Teste de Spinning (diminuição de retornos)
4. Geração automática de novos grids (zoom/expand)

Uso:
    from scripts.grid_advisor import GridAdvisor
    advisor = GridAdvisor()
    
    # Após F2
    decision = advisor.analyze_f2_results(f2_results, current_grid)
    if decision['action'] == 'ZOOM':
        new_grid = decision['new_grid']
        # Re-executar F1/F2 com novo grid
    elif decision['action'] == 'EXPAND':
        new_grid = decision['new_grid']
        # Expandir grid na direção da borda
    elif decision['action'] == 'STOP':
        # Prosseguir para F3
"""
import numpy as np
from typing import List, Dict, Any, Tuple

class GridAdvisor:
    """Analisa resultados de grid search e decide proximo passo."""
    
    def __init__(self, 
                 zoom_cv_threshold=20.0,      # CV% para considerar zoom
                 plateau_drop_threshold=15.0,  # Drop% para vizinhos serem considerados instaveis
                 spinning_threshold=500,       # Delta minimo entre ciclos
                 max_zoom_levels=3,            # Maximo de niveis de zoom
                 max_subcycles=3,              # Maximo de sub-ciclos por sinal
                 sl_floor=0.5):                # Floor minimo para SL (x ATR)
        self.zoom_cv_threshold = zoom_cv_threshold
        self.plateau_drop_threshold = plateau_drop_threshold
        self.spinning_threshold = spinning_threshold
        self.max_zoom_levels = max_zoom_levels
        self.max_subcycles = max_subcycles
        self.sl_floor = sl_floor
        
        self.subcycle_history = []  # Historico de resultados por sinal
        self.zoom_level = 0         # Nivel atual de zoom
        self._expanded_dims = set() # Track dimensions already expanded to avoid loops
    
    def analyze_f1_results(self, f1_results: List[Dict], 
                          tp_grid: List[float], 
                          sl_grid: List[float],
                          atr_min_grid: List[float],
                          atr_max_grid: List[float]) -> Dict[str, Any]:
        """
        Analisa resultados F1.
        
        NOTA: F1 geralmente tem CV=0% porque ATR nao afeta f1_eval.
        Por isso, F1 so detecta fronteiras (TP/SL na borda).
        A variancia real so aparece no F2/F3.
        """
        if len(f1_results) < 3:
            return {'action': 'STOP', 'reason': 'insufficient_f1_results'}
        
        top3 = f1_results[:3]
        nets = [r['f1_net'] for r in top3]
        tps = [r['tp'] for r in top3]
        sls = [r['sl'] for r in top3]
        
        best = top3[0]
        
        # Check 1: Fronteira
        if best['tp'] in [min(tp_grid), max(tp_grid)]:
            return {
                'action': 'EXPAND',
                'reason': f"TP na borda ({best['tp']})",
                'dimension': 'tp',
                'direction': 'up' if best['tp'] == max(tp_grid) else 'down',
                'new_grid': self._expand_grid(tp_grid, best['tp'], 'tp')
            }
        
        if best['sl'] in [min(sl_grid), max(sl_grid)]:
            return {
                'action': 'EXPAND',
                'reason': f"SL na borda ({best['sl']})",
                'dimension': 'sl',
                'direction': 'up' if best['sl'] == max(sl_grid) else 'down',
                'new_grid': self._expand_grid(sl_grid, best['sl'], 'sl')
            }
        
        # Check 2: Variancia (rara no F1, mas possivel)
        cv = self._calc_cv(nets)
        if cv > self.zoom_cv_threshold:
            return {
                'action': 'ZOOM',
                'reason': f'F1 CV={cv:.1f}% > {self.zoom_cv_threshold}%',
                'new_grid': self._zoom_grid(tp_grid, sl_grid, best['tp'], best['sl'])
            }
        
        # F1 OK — prosseguir para F2
        return {
            'action': 'CONTINUE',
            'reason': f'F1 CV={cv:.1f}%, nao na borda',
            'best_config': best
        }
    
    def _score_config(self, r: Dict) -> float:
        """Score Sharpe-based: penaliza volatilidade e stops curtos."""
        net = r.get('f2_net', r.get('f1_net', 0))
        sharpe = r.get('f2_sharpe', 0.0)
        sl = r.get('sl', 1.0)
        # Penalidade para SL abaixo do floor
        sl_penalty = 0.5 if sl < self.sl_floor else 1.0
        if net <= 0:
            return net * sl_penalty
        return net * max(0, sharpe) * sl_penalty
    
    def analyze_f2_results(self, f2_results: List[Dict],
                          f1_best: Dict,
                          tp_grid: List[float],
                          sl_grid: List[float],
                          atr_min_grid: List[float],
                          atr_max_grid: List[float]) -> Dict[str, Any]:
        """
        Analisa resultados F2 (onde ATR importa e variancia aparece).
        Usa Sharpe Ratio como peso principal no desempate.
        
        Args:
            f2_results: Lista de dicts com keys: tp, sl, atr_min, atr_max, f2_net, f2_n
            f1_best: Melhor resultado do F1 (para comparar)
        """
        if len(f2_results) < 3:
            return {'action': 'STOP', 'reason': 'insufficient_f2_results'}
        
        # Re-rank por score Sharpe (não por net puro)
        scored = [(self._score_config(r), r) for r in f2_results]
        scored.sort(key=lambda x: -x[0])
        top3 = [s[1] for s in scored[:3]]
        nets = [r['f2_net'] for r in top3]
        best = top3[0]
        
        # Sanity Check: SL floor
        if best['sl'] < self.sl_floor:
            if self.zoom_level < self.max_zoom_levels:
                return {
                    'action': 'ZOOM',
                    'reason': f"SL={best['sl']} < floor={self.sl_floor} → zoom para achar config viavel",
                    'new_grid': self._zoom_grid(tp_grid, sl_grid, best['tp'], max(best['sl'], self.sl_floor),
                                               atr_min_grid, atr_max_grid, best['atr_min'], best['atr_max'])
                }
            else:
                return {
                    'action': 'STOP',
                    'reason': f"SL={best['sl']} < floor={self.sl_floor} e max zoom atingido"
                }
        
        # Check 1: Fronteira de TP/SL — com proteção contra loop
        if best['tp'] in [min(tp_grid), max(tp_grid)]:
            dim_key = f"tp_{best['tp']}"
            if dim_key not in self._expanded_dims:
                new_grid = self._expand_grid(tp_grid, best['tp'], 'tp')
                if new_grid and len(new_grid) > len(tp_grid):
                    self._expanded_dims.add(dim_key)
                    return {
                        'action': 'EXPAND',
                        'reason': f"F2 TP na borda ({best['tp']})",
                        'dimension': 'tp',
                        'new_grid': new_grid
                    }
            # Já expandiu essa borda antes → zoom
            if self.zoom_level < self.max_zoom_levels:
                return {
                    'action': 'ZOOM',
                    'reason': f"TP na borda ({best['tp']}) mas ja expandido → zoom",
                    'new_grid': self._zoom_grid(tp_grid, sl_grid, best['tp'], best['sl'])
                }
        
        if best['sl'] in [min(sl_grid), max(sl_grid)]:
            dim_key = f"sl_{best['sl']}"
            if dim_key not in self._expanded_dims:
                new_grid = self._expand_grid(sl_grid, best['sl'], 'sl')
                if new_grid and len(new_grid) > len(sl_grid):
                    self._expanded_dims.add(dim_key)
                    return {
                        'action': 'EXPAND',
                        'reason': f"F2 SL na borda ({best['sl']})",
                        'dimension': 'sl',
                        'new_grid': new_grid
                    }
            # Já expandiu essa borda antes → zoom
            if self.zoom_level < self.max_zoom_levels:
                return {
                    'action': 'ZOOM',
                    'reason': f"SL na borda ({best['sl']}) mas ja expandido → zoom",
                    'new_grid': self._zoom_grid(tp_grid, sl_grid, best['tp'], best['sl'])
                }
        
        # Check 2: Fronteira de ATR — com proteção contra loop
        if best['atr_min'] in [min(atr_min_grid), max(atr_min_grid)]:
            dim_key = f"atrmin_{best['atr_min']}"
            if dim_key not in self._expanded_dims:
                new_grid = self._expand_grid(atr_min_grid, best['atr_min'], 'atr_min')
                if new_grid and len(new_grid) > len(atr_min_grid):
                    self._expanded_dims.add(dim_key)
                    return {
                        'action': 'EXPAND',
                        'reason': f"ATR_MIN na borda ({best['atr_min']})",
                        'dimension': 'atr_min',
                        'new_grid': new_grid
                    }
        
        if best['atr_max'] in [min(atr_max_grid), max(atr_max_grid)]:
            dim_key = f"atrmax_{best['atr_max']}"
            if dim_key not in self._expanded_dims:
                new_grid = self._expand_grid(atr_max_grid, best['atr_max'], 'atr_max')
                if new_grid and len(new_grid) > len(atr_max_grid):
                    self._expanded_dims.add(dim_key)
                    return {
                        'action': 'EXPAND',
                        'reason': f"ATR_MAX na borda ({best['atr_max']})",
                        'dimension': 'atr_max',
                        'new_grid': new_grid
                    }
        
        # Check 3: Variancia (CV)
        cv = self._calc_cv(nets)
        if cv > self.zoom_cv_threshold and self.zoom_level < self.max_zoom_levels:
            return {
                'action': 'ZOOM',
                'reason': f'F2 CV={cv:.1f}% > {self.zoom_cv_threshold}% (zoom_level={self.zoom_level})',
                'new_grid': self._zoom_grid(tp_grid, sl_grid, best['tp'], best['sl'],
                                           atr_min_grid, atr_max_grid, best['atr_min'], best['atr_max'])
            }
        
        # Check 4: Planalto (robustez dos vizinhos)
        stability = self._check_plateau(top3)
        if stability['is_peak']:
            # Pico instavel — precisa de zoom
            if self.zoom_level < self.max_zoom_levels:
                return {
                    'action': 'ZOOM',
                    'reason': f'Pico instavel: drop={stability["max_drop"]:.1f}% > {self.plateau_drop_threshold}%',
                    'new_grid': self._zoom_grid(tp_grid, sl_grid, best['tp'], best['sl'])
                }
        
        # Check 5: Spinning (historico de subciclos)
        if len(self.subcycle_history) >= 2:
            last_net = self.subcycle_history[-1]['oos_net']
            prev_net = self.subcycle_history[-2]['oos_net']
            delta = abs(last_net - prev_net)
            if delta < self.spinning_threshold:
                return {
                    'action': 'STOP',
                    'reason': f'Spinning: delta={delta:.0f} < {self.spinning_threshold} (ultimos 2 ciclos)'
                }
        
        # Tudo OK — prosseguir
        return {
            'action': 'CONTINUE',
            'reason': f'F2 CV={cv:.1f}%, stable={not stability["is_peak"]}, nivel={self.zoom_level}',
            'best_config': best,
            'stability': stability
        }
    
    def record_subcycle(self, result: Dict):
        """Registra resultado de um sub-ciclo para detectar spinning."""
        self.subcycle_history.append({
            'oos_net': result.get('oos_net', 0),
            'oos_wr': result.get('oos_wr', 0),
            'zoom_level': self.zoom_level
        })
    
    def _calc_cv(self, values: List[float]) -> float:
        """Calcula coeficiente de variacao (%)."""
        arr = np.array(values, dtype=np.float64)
        if len(arr) < 2 or np.mean(arr) == 0:
            return 0.0
        return np.std(arr, ddof=1) / abs(np.mean(arr)) * 100
    
    def _check_plateau(self, top_results: List[Dict]) -> Dict:
        """
        Verifica se o top 1 e um pico instavel ou parte de um planalto.
        
        Retorna:
            is_peak: True se o vizinho mais proximo cai > threshold%
            max_drop: maior queda percentual para vizinhos
        """
        if len(top_results) < 2:
            return {'is_peak': False, 'max_drop': 0.0}
        
        best_net = top_results[0].get('f2_net', top_results[0].get('f1_net', 0))
        drops = []
        
        for r in top_results[1:]:
            net = r.get('f2_net', r.get('f1_net', 0))
            if best_net != 0:
                drop = abs(best_net - net) / abs(best_net) * 100
                drops.append(drop)
        
        max_drop = max(drops) if drops else 0.0
        return {
            'is_peak': max_drop > self.plateau_drop_threshold,
            'max_drop': max_drop
        }
    
    def _expand_grid(self, grid: List[float], best_value: float, dimension: str) -> List[float]:
        """
        Expande o grid na direção da borda.
        
        Se best esta na borda inferior: adiciona valores menores
        Se best esta na borda superior: adiciona valores maiores
        Retorna None se não puder expandir (ex: SL=0.05, não pode ir < 0).
        """
        sorted_grid = sorted(grid)
        step = self._get_typical_step(sorted_grid)
        
        if best_value == sorted_grid[0]:
            # Borda inferior — expandir para baixo
            new_values = [best_value - step * i for i in range(1, 4)]
            new_values = [v for v in new_values if v > 0]
            if not new_values:
                return None  # Não pode expandir mais
            return sorted(new_values + sorted_grid)
        else:
            # Borda superior — expandir para cima
            new_values = [best_value + step * i for i in range(1, 4)]
            if not new_values or all(v in sorted_grid for v in new_values):
                return None  # Não pode expandir mais
            return sorted(sorted_grid + new_values)
    
    def _zoom_grid(self, tp_grid: List[float], sl_grid: List[float],
                   best_tp: float, best_sl: float,
                   atr_min_grid: List[float] = None,
                   atr_max_grid: List[float] = None,
                   best_atr_min: float = None,
                   best_atr_max: float = None) -> Dict[str, List[float]]:
        """
        Cria novo grid com zoom ao redor do melhor resultado.
        
        Janela deslizante com contração:
            NovoRange = [Best - Step_prev/2, Best + Step_prev/2]
            NovoStep = Step_prev / N
        """
        new_tp = self._zoom_single_dimension(tp_grid, best_tp)
        new_sl = self._zoom_single_dimension(sl_grid, best_sl)
        
        result = {
            'tp': new_tp,
            'sl': new_sl
        }
        
        if atr_min_grid and best_atr_min is not None:
            result['atr_min'] = self._zoom_single_dimension(atr_min_grid, best_atr_min)
        if atr_max_grid and best_atr_max is not None:
            result['atr_max'] = self._zoom_single_dimension(atr_max_grid, best_atr_max)
        
        self.zoom_level += 1
        return result
    
    def _zoom_single_dimension(self, grid: List[float], best_value: float) -> List[float]:
        """Zoom em uma unica dimensao."""
        sorted_grid = sorted(grid)
        step = self._get_typical_step(sorted_grid)
        
        # Nova janela centrada no best
        half_window = step  # Janela de +/- 1 step
        new_min = max(sorted_grid[0], best_value - half_window)
        new_max = min(sorted_grid[-1], best_value + half_window)
        
        # Novo step = step anterior / 2
        new_step = step / 2
        
        # Gerar valores
        values = []
        current = new_min
        while current <= new_max + 1e-9:
            values.append(round(current, 6))
            current += new_step
        
        # Garantir que best_value esta incluido
        if best_value not in values:
            values.append(best_value)
        
        return sorted(set(values))
    
    def _get_typical_step(self, grid: List[float]) -> float:
        """Calcula o step tipico de um grid."""
        if len(grid) < 2:
            return grid[0] if grid else 1.0
        
        diffs = [grid[i+1] - grid[i] for i in range(len(grid)-1)]
        # Usar a moda (valor mais comum) dos diffs
        from collections import Counter
        counter = Counter(round(d, 4) for d in diffs)
        most_common = counter.most_common(1)[0][0]
        return most_common


# ===== FUNÇÃO DE UTILIDADE =====
def analyze_strategy_for_report(strategy_name: str, f1_results: List[Dict], 
                                f2_results: List[Dict] = None) -> Dict:
    """
    Analisa uma estrategia e retorna recomendacao formatada para relatorio.
    """
    advisor = GridAdvisor()
    
    tp_grid = [1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 15.0, 18.0, 20.0, 25.0, 30.0]
    sl_grid = [0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0, 5.0]
    atr_min_grid = [50, 100, 150, 200, 300]
    atr_max_grid = [400, 600, 800, 1000, 9999, 15000]
    
    f1_decision = advisor.analyze_f1_results(f1_results, tp_grid, sl_grid, atr_min_grid, atr_max_grid)
    
    result = {
        'strategy': strategy_name,
        'f1_action': f1_decision['action'],
        'f1_reason': f1_decision.get('reason', ''),
    }
    
    if f2_results:
        f1_best = f1_results[0] if f1_results else {}
        f2_decision = advisor.analyze_f2_results(f2_results, f1_best, tp_grid, sl_grid, atr_min_grid, atr_max_grid)
        result['f2_action'] = f2_decision['action']
        result['f2_reason'] = f2_decision.get('reason', '')
        result['stability'] = f2_decision.get('stability', {})
    
    return result


if __name__ == '__main__':
    # Teste com dados reais
    import polars as pl
    import glob, os
    
    print("="*80)
    print("GRID ADVISOR — Analise de Estrategias Reais")
    print("="*80)
    print()
    
    files = glob.glob('meta_trade5/docs/WIN_docs/f2_rank_c1_*.csv')
    
    print(f"{'Estrategia':<40} {'F1_Action':<12} {'F2_Action':<12} {'F2_CV':<8} {'Stability':<15} {'Recomendacao':<30}")
    print("-"*120)
    
    for fpath in sorted(files)[:15]:
        fname = os.path.basename(fpath).replace('f2_rank_c1_', '').replace('.csv', '')
        
        # Carrega F1 e F2
        f1_path = fpath.replace('f2_rank', 'f1_rank')
        f1_df = pl.read_csv(f1_path) if os.path.exists(f1_path) else None
        f2_df = pl.read_csv(fpath)
        
        if f1_df is None or len(f1_df) < 3 or len(f2_df) < 3:
            continue
        
        f1_results = f1_df.head(10).to_dicts()
        f2_results = f2_df.head(10).to_dicts()
        
        analysis = analyze_strategy_for_report(fname, f1_results, f2_results)
        
        stab = analysis.get('stability', {})
        stab_str = f"drop={stab.get('max_drop', 0):.1f}%"
        
        # Calcula CV do F2
        f2_nets = [r['f2_net'] for r in f2_results[:3]]
        cv = np.std(f2_nets) / abs(np.mean(f2_nets)) * 100 if np.mean(f2_nets) != 0 else 0
        
        print(f"{fname:<40} {analysis['f1_action']:<12} {analysis.get('f2_action', 'N/A'):<12} {cv:>6.1f}% {stab_str:<15} {analysis.get('f2_reason', '')[:28]:<30}")
    
    print()
    print("Legenda:")
    print("  EXPAND  = Melhor resultado na borda do grid → expandir")
    print("  ZOOM    = Alta variancia → aumentar granularidade")
    print("  CONTINUE = Planalto detectado → prosseguir para F3")
    print("  STOP    = Spinning ou sem resultados → parar")
