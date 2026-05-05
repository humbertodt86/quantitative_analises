"""
DNA ANALYSIS V8.7 FINAL — COM PROJEÇÃO DE GUARDRAILS
======================================================
Evolução do dna_analysis_v87.py com projeção de PnL e sugestão de guardrails.

Input: Top 1 config do F3 (validado tick-by-tick)
Output:
  - TRADES_{sinal}.csv (log candle-a-candle)
  - DNA_ANALYSIS_FINAL_{sinal}.md (relatório completo)
  - GUARDRAILS_SUGGESTED_{sinal}.json (guardrails sugeridos)
"""
import sys, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandas as pd
import numpy as np
from datetime import datetime
import json
import argparse


def load_trade_log(signal: str, variant: str, direction: str):
    """Carrega trade log do F3."""
    path = os.path.join(ROOT, 'docs', 'WIN_docs', f'TRADES_{signal}_{variant}_{direction}.csv')
    return pd.read_csv(path)


def analyze_by_hour(trades_df: pd.DataFrame) -> pd.DataFrame:
    """Analise por hora do dia."""
    trades_df['entry_hour'] = pd.to_datetime(trades_df['entry_dt']).dt.hour
    
    hourly = trades_df.groupby('entry_hour').agg({
        'trade_id': 'count',
        'pnl_liquid': ['sum', 'mean'],
    }).reset_index()
    hourly.columns = ['hour', 'trades', 'total_pnl', 'avg_pnl']
    hourly['win_rate'] = trades_df.groupby('entry_hour').apply(
        lambda x: (x['pnl_liquid'] > 0).mean() * 100
    ).values
    
    return hourly


def analyze_by_day_of_week(trades_df: pd.DataFrame) -> pd.DataFrame:
    """Analise por dia da semana."""
    trades_df['day_of_week'] = pd.to_datetime(trades_df['entry_dt']).dt.day_name()
    
    daily = trades_df.groupby('day_of_week').agg({
        'trade_id': 'count',
        'pnl_liquid': ['sum', 'mean'],
    }).reset_index()
    daily.columns = ['day', 'trades', 'total_pnl', 'avg_pnl']
    daily['win_rate'] = trades_df.groupby('day_of_week').apply(
        lambda x: (x['pnl_liquid'] > 0).mean() * 100
    ).values
    
    # Order by day of week
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    daily['day_order'] = daily['day'].apply(lambda x: day_order.index(x) if x in day_order else 5)
    daily = daily.sort_values('day_order').drop('day_order', axis=1)
    
    return daily


def analyze_by_atr(trades_df: pd.DataFrame) -> pd.DataFrame:
    """Analise por ATR no entry."""
    # Bins de ATR
    trades_df['atr_bin'] = pd.cut(
        trades_df['entry_atr'],
        bins=[0, 250, 500, 800, 9999],
        labels=['ATR<250', '250-500', '500-800', 'ATR>800']
    )
    
    atr_analysis = trades_df.groupby('atr_bin').agg({
        'trade_id': 'count',
        'pnl_liquid': ['sum', 'mean'],
    }).reset_index()
    atr_analysis.columns = ['atr_range', 'trades', 'total_pnl', 'avg_pnl']
    atr_analysis['win_rate'] = trades_df.groupby('atr_bin').apply(
        lambda x: (x['pnl_liquid'] > 0).mean() * 100
    ).values
    
    return atr_analysis


def suggest_guardrails(hourly: pd.DataFrame, daily: pd.DataFrame, atr_analysis: pd.DataFrame) -> Dict:
    """
    Sugere guardrails heurísticos baseados na análise.
    
    Critérios:
    - Hour: bloquear se PnL < 0 e trades >= 5
    - Day: bloquear se PnL < 0 e trades >= 5
    - ATR: bloquear faixa com PnL < 0 e trades >= 5
    """
    guardrails = {
        'hour_filter': [],
        'day_filter': [],
        'atr_min_filter': None,
        'book_imbalance_filter': None,
        'cumulative_delta_filter': None,
    }
    
    # Hour filter
    for _, row in hourly.iterrows():
        if row['total_pnl'] < 0 and row['trades'] >= 5:
            guardrails['hour_filter'].append(int(row['hour']))
    
    # Day filter
    for _, row in daily.iterrows():
        if row['total_pnl'] < 0 and row['trades'] >= 5:
            day_map = {'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3, 'Friday': 4}
            guardrails['day_filter'].append(day_map.get(row['day'], -1))
    
    # ATR filter
    for _, row in atr_analysis.iterrows():
        if row['atr_range'] == 'ATR<250' and row['total_pnl'] < 0 and row['trades'] >= 5:
            guardrails['atr_min_filter'] = 250
    
    return guardrails


def calculate_pnl_projection(
    base_pnl: float,
    base_trades: int,
    base_wr: float,
    guardrails: Dict,
    hourly: pd.DataFrame,
    daily: pd.DataFrame,
    atr_analysis: pd.DataFrame
) -> Dict:
    """
    Calcula projeção de PnL com guardrails aplicados.
    """
    projection = {
        'base_pnl': base_pnl,
        'base_trades': base_trades,
        'base_wr': base_wr,
        'adjustments': [],
        'projected_pnl': base_pnl,
        'projected_trades': base_trades,
    }
    
    # Hour filter projection
    for hour in guardrails['hour_filter']:
        hour_data = hourly[hourly['hour'] == hour]
        if len(hour_data) > 0:
            pnl_saved = -hour_data['total_pnl'].values[0]
            trades_removed = hour_data['trades'].values[0]
            projection['adjustments'].append({
                'type': 'hour_filter',
                'value': hour,
                'pnl_impact': pnl_saved,
                'trades_impact': -trades_removed,
            })
            projection['projected_pnl'] += pnl_saved
            projection['projected_trades'] += -trades_removed
    
    # Day filter projection
    for day in guardrails['day_filter']:
        day_map = {0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday', 4: 'Friday'}
        day_name = day_map.get(day, 'Unknown')
        day_data = daily[daily['day'] == day_name]
        if len(day_data) > 0:
            pnl_saved = -day_data['total_pnl'].values[0]
            trades_removed = day_data['trades'].values[0]
            projection['adjustments'].append({
                'type': 'day_filter',
                'value': day_name,
                'pnl_impact': pnl_saved,
                'trades_impact': -trades_removed,
            })
            projection['projected_pnl'] += pnl_saved
            projection['projected_trades'] += -trades_removed
    
    # ATR filter projection
    if guardrails['atr_min_filter']:
        atr_data = atr_analysis[atr_analysis['atr_range'] == 'ATR<250']
        if len(atr_data) > 0:
            pnl_saved = -atr_data['total_pnl'].values[0]
            trades_removed = atr_data['trades'].values[0]
            projection['adjustments'].append({
                'type': 'atr_min_filter',
                'value': guardrails['atr_min_filter'],
                'pnl_impact': pnl_saved,
                'trades_impact': -trades_removed,
            })
            projection['projected_pnl'] += pnl_saved
            projection['projected_trades'] += -trades_removed
    
    # Estimated WR improvement
    if projection['projected_trades'] > 0:
        projection['projected_wr'] = min(90, base_wr + (len(projection['adjustments']) * 2))
    else:
        projection['projected_wr'] = base_wr
    
    return projection


def generate_dna_report(signal: str, variant: str, direction: str):
    """Gera relatório completo de DNA com projeção de guardrails."""
    print("="*80)
    print(f"DNA ANALYSIS V8.7 FINAL — {signal} {variant} {'BUY' if direction==1 else 'SELL'}")
    print("="*80)
    
    # Load trade log
    print("\nLoading trade log...")
    trades_df = load_trade_log(signal, variant, direction)
    print(f"  Loaded: {len(trades_df)} trades")
    
    # =========================================================================
    # 1. PARAMETROS DO MODELO
    # =========================================================================
    print("\n" + "="*80)
    print("1. PARAMETROS DO MODELO (DNA)")
    print("="*80)
    
    # Extrair do nome da variante
    parts = variant.split('_')
    s_min = int(parts[0].replace('s', ''))
    z_max = float(parts[1].replace('z', '').replace('p', '.'))
    r_min = float(parts[2].replace('r', '').replace('p', '.'))
    
    print(f"\n  Signal:         {signal}")
    print(f"  Variant:        {variant}")
    print(f"  Direction:      {'BUY' if direction==1 else 'SELL'}")
    print(f"\n  V8 Parameters:")
    print(f"    S_MIN:        {s_min} (slope minimo)")
    print(f"    Z_MAX:        {z_max} (z-score max)")
    print(f"    R_MIN:        {r_min} (range ratio min)")
    
    # =========================================================================
    # 2. PERFORMANCE GERAL
    # =========================================================================
    print("\n" + "="*80)
    print("2. PERFORMANCE GERAL")
    print("="*80)
    
    total_pnl = trades_df['pnl_liquid'].sum()
    avg_pnl = trades_df['pnl_liquid'].mean()
    win_rate = (trades_df['pnl_liquid'] > 0).mean() * 100
    total_trades = len(trades_df)
    
    print(f"\n  Total Trades:   {total_trades}")
    print(f"  Net PnL:        R$ {total_pnl:,.2f}")
    print(f"  Avg PnL/Trade:  R$ {avg_pnl:,.2f}")
    print(f"  Win Rate:       {win_rate:.1f}%")
    
    # =========================================================================
    # 3. ANALISE POR HORA
    # =========================================================================
    print("\n" + "="*80)
    print("3. ANALISE POR HORA DO DIA")
    print("="*80)
    
    hourly = analyze_by_hour(trades_df.copy())
    
    print(f"\n  {'Hour':<6} {'Trades':<8} {'Total PnL':<14} {'Avg PnL':<12} {'Win Rate':<10}")
    print(f"  {'-'*50}")
    for _, row in hourly.iterrows():
        print(f"  {int(row['hour']):02d}:00   {int(row['trades']):<8} {row['total_pnl']:<14,.0f} {row['avg_pnl']:<12,.0f} {row['win_rate']:<10.1f}%")
    
    # =========================================================================
    # 4. ANALISE POR DIA DA SEMANA
    # =========================================================================
    print("\n" + "="*80)
    print("4. ANALISE POR DIA DA SEMANA")
    print("="*80)
    
    daily = analyze_by_day_of_week(trades_df.copy())
    
    print(f"\n  {'Day':<12} {'Trades':<8} {'Total PnL':<14} {'Avg PnL':<12} {'Win Rate':<10}")
    print(f"  {'-'*56}")
    for _, row in daily.iterrows():
        print(f"  {row['day']:<12} {int(row['trades']):<8} {row['total_pnl']:<14,.0f} {row['avg_pnl']:<12,.0f} {row['win_rate']:<10.1f}%")
    
    # =========================================================================
    # 5. ANALISE POR ATR
    # =========================================================================
    print("\n" + "="*80)
    print("5. ANALISE POR ATR")
    print("="*80)
    
    atr_analysis = analyze_by_atr(trades_df.copy())
    
    print(f"\n  {'ATR Range':<12} {'Trades':<8} {'Total PnL':<14} {'Avg PnL':<12} {'Win Rate':<10}")
    print(f"  {'-'*56}")
    for _, row in atr_analysis.iterrows():
        print(f"  {str(row['atr_range']):<12} {int(row['trades']):<8} {row['total_pnl']:<14,.0f} {row['avg_pnl']:<12,.0f} {row['win_rate']:<10.1f}%")
    
    # =========================================================================
    # 6. SUGESTÃO DE GUARDRAILS
    # =========================================================================
    print("\n" + "="*80)
    print("6. SUGESTÃO DE GUARDRAILS (HEURÍSTICOS)")
    print("="*80)
    
    guardrails = suggest_guardrails(hourly, daily, atr_analysis)
    
    print(f"\n  Guardrails Sugeridos:")
    print(f"    HOUR_FILTER:    Bloquear horas {guardrails['hour_filter'] if guardrails['hour_filter'] else 'Nenhuma'}")
    print(f"    DAY_FILTER:     Bloquear dias {guardrails['day_filter'] if guardrails['day_filter'] else 'Nenhum'}")
    print(f"    ATR_MIN_FILTER: {guardrails['atr_min_filter'] if guardrails['atr_min_filter'] else 'Nenhum'}")
    
    # =========================================================================
    # 7. PROJEÇÃO DE PnL
    # =========================================================================
    print("\n" + "="*80)
    print("7. PROJEÇÃO DE PnL COM GUARDRAILS")
    print("="*80)
    
    projection = calculate_pnl_projection(
        total_pnl, total_trades, win_rate,
        guardrails, hourly, daily, atr_analysis
    )
    
    print(f"\n  PnL Base (sem guardrails):     R$ {projection['base_pnl']:,.2f} ({projection['base_trades']} trades, {projection['base_wr']:.1f}% WR)")
    
    for adj in projection['adjustments']:
        print(f"  {adj['type']:<20} ({adj['value']}): {'+' if adj['pnl_impact'] > 0 else ''}R$ {adj['pnl_impact']:,.2f} ({adj['trades_impact']:+.0f} trades)")
    
    print(f"  " + "-"*60)
    print(f"  PnL Projetado (com guardrails): R$ {projection['projected_pnl']:,.2f} ({projection['projected_trades']} trades, ~{projection['projected_wr']:.1f}% WR)")
    print(f"  ")
    print(f"  Trade-off:")
    print(f"    - PnL: {((projection['projected_pnl'] / projection['base_pnl']) - 1) * 100:+.1f}%")
    print(f"    - Trades: {((projection['projected_trades'] / projection['base_trades']) - 1) * 100:+.1f}%")
    print(f"    - WR: {projection['projected_wr'] - projection['base_wr']:+.1f}% pts")
    
    # =========================================================================
    # 8. SALVAR RELATÓRIO
    # =========================================================================
    
    # Salvar JSON
    report = {
        'signal': signal,
        'variant': variant,
        'direction': 'BUY' if direction==1 else 'SELL',
        'v8_params': {
            's_min': s_min,
            'z_max': z_max,
            'r_min': r_min,
        },
        'performance_base': {
            'pnl': float(total_pnl),
            'trades': int(total_trades),
            'wr': float(win_rate),
        },
        'guardrails_suggested': guardrails,
        'pnl_projection': projection,
        'generated_at': datetime.now().isoformat(),
    }
    
    output_json = os.path.join(ROOT, 'docs', 'WIN_docs', f'DNA_ANALYSIS_FINAL_{signal}_{variant}_{direction}.json')
    with open(output_json, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\n\nSaved: {output_json}")
    
    # Salvar Markdown
    output_md = os.path.join(ROOT, 'docs', 'WIN_docs', f'DNA_ANALYSIS_FINAL_{signal}_{variant}_{direction}.md')
    with open(output_md, 'w', encoding='utf-8') as f:
        f.write(f"# DNA ANALYSIS FINAL — {signal} {variant} {'BUY' if direction==1 else 'SELL'}\n\n")
        f.write(f"**Generated**: {datetime.now().isoformat()}\n\n")
        f.write(f"## Parametros\n\n")
        f.write(f"- S_MIN: {s_min}\n")
        f.write(f"- Z_MAX: {z_max}\n")
        f.write(f"- R_MIN: {r_min}\n\n")
        f.write(f"## Performance Base\n\n")
        f.write(f"- PnL: R$ {total_pnl:,.2f}\n")
        f.write(f"- Trades: {total_trades}\n")
        f.write(f"- WR: {win_rate:.1f}%\n\n")
        f.write(f"## Guardrails Sugeridos\n\n")
        f.write(f"- Hour Filter: Bloquear {guardrails['hour_filter']}\n")
        f.write(f"- Day Filter: Bloquear {guardrails['day_filter']}\n")
        f.write(f"- ATR Min Filter: {guardrails['atr_min_filter']}\n\n")
        f.write(f"## Projeção de PnL\n\n")
        f.write(f"- Base: R$ {projection['base_pnl']:,.2f} ({projection['base_trades']} trades)\n")
        f.write(f"- Projetado: R$ {projection['projected_pnl']:,.2f} ({projection['projected_trades']} trades)\n")
        f.write(f"- Trade-off: {((projection['projected_pnl'] / projection['base_pnl']) - 1) * 100:+.1f}% PnL, {((projection['projected_trades'] / projection['base_trades']) - 1) * 100:+.1f}% trades\n")
    
    print(f"Saved: {output_md}")
    
    print("\n" + "="*80)
    print("DNA ANALYSIS COMPLETE.")
    print("="*80)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='DNA Analysis V8.7 Final')
    parser.add_argument('--signal', type=str, default='PA_SIGNAL_DIR', help='Signal name')
    parser.add_argument('--variant', type=str, default='s10_z4p0_r0p5', help='Variant name')
    parser.add_argument('--direction', type=str, default='BUY', help='BUY or SELL')
    args = parser.parse_args()
    
    generate_dna_report(args.signal, args.variant, args.direction)
