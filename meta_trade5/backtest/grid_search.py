"""
Parallel Grid Search for V134.

Uses multiprocessing to run multiple engine simulations in parallel.
"""
import sys
sys.path.insert(0, '.')

import json
import time
import itertools
from dataclasses import dataclass
from typing import List, Dict, Any
from multiprocessing import Pool, cpu_count
from pathlib import Path

from backtest.engine_v2 import BacktestEngine, load_default_config, ModeConfig, BacktestConfig


@dataclass
class GridResult:
    """Result of a single grid search iteration."""
    params: dict
    metrics: dict
    mode_results: dict


def run_single_simulation(args: tuple) -> dict:
    """Run a single simulation with given params.

    This function is designed to be called in a separate process.

    Args:
        args: Tuple of (param_dict, config_dict, indicators_path, ticks_path)

    Returns:
        Dict with params, metrics, and mode_results
    """
    param_dict, config_dict, indicators_path, ticks_path = args

    try:
        # Create engine and load data
        engine = BacktestEngine(indicators_path)
        engine.load_indicators()
        engine.load_ticks_for_simulation(ticks_path)

        # Merge config with params
        merged_config = merge_params_to_config(config_dict, param_dict)
        engine.load_config_dict(merged_config)

        # Run simulation
        results = engine.simulate()
        metrics = engine.calculate_metrics(results)

        # Get per-mode results
        mode_results = {}
        for mode in ['SNIPER', 'HUNTER', 'SCALPER']:
            mode_results[mode] = engine.calculate_metrics([r for r in results if r['mode'] == mode])

        return {
            'params': param_dict,
            'metrics': metrics,
            'mode_results': mode_results,
            'error': None
        }
    except Exception as e:
        return {
            'params': param_dict,
            'metrics': None,
            'mode_results': None,
            'error': str(e)
        }


def merge_params_to_config(base_config: dict, params: dict) -> dict:
    """Merge parameter overrides into base config.

    Args:
        base_config: Base configuration dict
        params: Parameter overrides, e.g. {"SNIPER": {"be_trigger": 500}}

    Returns:
        Merged configuration dict
    """
    config = json.loads(json.dumps(base_config))  # Deep copy

    for mode_name, mode_params in params.items():
        if mode_name in config.get('modes', {}):
            if 'behp' not in config['modes'][mode_name]:
                config['modes'][mode_name]['behp'] = {}
            config['modes'][mode_name]['behp'].update(mode_params)

    return config


class GridSearch:
    """Parallel grid search manager."""

    def __init__(self, config: dict, indicators_path: str, ticks_path: str):
        """Initialize grid search.

        Args:
            config: Base configuration dict
            indicators_path: Path to pre-calculated indicators
            ticks_path: Path to raw ticks for simulation
        """
        self.base_config = config
        self.indicators_path = indicators_path
        self.ticks_path = ticks_path
        self.results = []
        self.best_result = None

    def generate_param_combinations(self, param_grid: dict) -> List[dict]:
        """Generate all combinations of parameters.

        Args:
            param_grid: Dict mapping mode names to param dicts
            e.g. {"SNIPER": {"be_trigger": [500, 600], "hp_th": [30, 40]}}

        Returns:
            List of param dicts, each containing a specific combination
        """
        combinations = []

        # For each mode, create list of param dicts
        mode_param_lists = {}
        for mode_name, mode_params in param_grid.items():
            param_list = []
            keys = list(mode_params.keys())
            values = [mode_params[k] for k in keys]

            for combo in itertools.product(*values):
                param_dict = dict(zip(keys, combo))
                param_list.append(param_dict)

            mode_param_lists[mode_name] = param_list

        # Generate all combinations across modes
        mode_names = list(mode_param_lists.keys())
        mode_combos = [mode_param_lists[name] for name in mode_names]

        for full_combo in itertools.product(*mode_combos):
            result = dict(zip(mode_names, full_combo))
            combinations.append(result)

        return combinations

    def run(self, param_grid: dict, n_workers: int = None, progress_callback=None) -> List[GridResult]:
        """Run grid search in parallel.

        Args:
            param_grid: Parameter grid to search
            n_workers: Number of worker processes (default: cpu_count - 1)
            progress_callback: Optional callback(completed, total) for progress

        Returns:
            List of GridResult objects
        """
        if n_workers is None:
            n_workers = max(1, cpu_count() - 1)

        # Generate all combinations
        combinations = self.generate_param_combinations(param_grid)
        total = len(combinations)
        print(f"  Grid search: {total} combinations with {n_workers} workers")

        # Prepare args for each process
        args_list = [
            (combo, self.base_config, self.indicators_path, self.ticks_path)
            for combo in combinations
        ]

        # Run in parallel
        t_start = time.time()
        results = []

        if n_workers == 1:
            # Single process mode
            for i, args in enumerate(args_list):
                result = run_single_simulation(args)
                results.append(result)
                if progress_callback:
                    progress_callback(i + 1, total)
        else:
            # Multi-process mode
            with Pool(processes=n_workers) as pool:
                for i, result in enumerate(pool.imap_unordered(run_single_simulation, args_list)):
                    results.append(result)
                    if progress_callback:
                        progress_callback(i + 1, total)

        elapsed = time.time() - t_start
        print(f"  Grid search completed in {elapsed:.1f}s ({elapsed/total*1000:.1f}ms/combo)")

        # Find best result
        self.results = [r for r in results if r['error'] is None and r['metrics'] is not None]

        if self.results:
            self.best_result = max(self.results, key=lambda x: x['metrics']['pnl'])

        return results

    def get_top_n(self, n: int = 10, sort_by: str = 'pnl') -> List[GridResult]:
        """Get top N results sorted by metric.

        Args:
            n: Number of results to return
            sort_by: Metric to sort by ('pnl', 'exp', 'pf', 'max_dd')

        Returns:
            List of top N GridResult objects
        """
        if not self.results:
            return []

        if sort_by == 'pnl':
            return sorted(self.results, key=lambda x: x['metrics']['pnl'], reverse=True)[:n]
        elif sort_by == 'exp':
            return sorted(self.results, key=lambda x: x['metrics']['exp'], reverse=True)[:n]
        elif sort_by == 'pf' or sort_by == 'profit_factor':
            return sorted(self.results, key=lambda x: x['metrics']['profit_factor'], reverse=True)[:n]
        elif sort_by == 'max_dd':
            return sorted(self.results, key=lambda x: x['metrics']['max_dd'])[:n]
        else:
            return sorted(self.results, key=lambda x: x['metrics']['pnl'], reverse=True)[:n]


def run_quick_grid(config_path: str, indicators_path: str, ticks_path: str,
                   param_grid: dict, n_workers: int = None) -> dict:
    """Run a quick grid search and return best result.

    Args:
        config_path: Path to JSON config
        indicators_path: Path to pre-calculated indicators
        ticks_path: Path to raw ticks
        param_grid: Parameter grid to search
        n_workers: Number of workers

    Returns:
        Dict with best params and metrics
    """
    # Load config
    with open(config_path, 'r') as f:
        config = json.load(f)

    # Create grid search
    gs = GridSearch(config, indicators_path, ticks_path)

    # Run
    def progress(completed, total):
        if completed % 10 == 0 or completed == total:
            print(f"    Progress: {completed}/{total}")

    gs.run(param_grid, n_workers=n_workers, progress_callback=progress)

    # Return best
    if gs.best_result:
        return {
            'best_params': gs.best_result['params'],
            'best_metrics': gs.best_result['metrics'],
            'top5': gs.get_top_n(5)
        }
    else:
        return {'error': 'No valid results'}


if __name__ == "__main__":
    # Example usage
    import argparse

    parser = argparse.ArgumentParser(description='Run parallel grid search')
    parser.add_argument('--config', default='configs/v134_default.json', help='Config path')
    parser.add_argument('--indicators', default='data/indicators/indicators_jan2026.parquet',
                        help='Indicators parquet path')
    parser.add_argument('--ticks', default='data/raw/ticks/WIN_merged_all_partitioned/',
                        help='Ticks path (partitioned)')
    parser.add_argument('--output', default='docs/artifacts/grid_results.json',
                        help='Output path for results')

    args = parser.parse_args()

    # Example param grid
    param_grid = {
        "SNIPER": {
            "be_trigger": [400, 500, 600],
            "hp_th": [3, 5, 7],
        },
        "HUNTER": {
            "be_trigger": [100, 150, 200],
            "hp_th": [30, 40, 50],
        }
    }

    print("Example grid search - not run in standalone mode")
    print(f"Config: {args.config}")
    print(f"Indicators: {args.indicators}")
    print(f"Param grid: {param_grid}")
