#!/usr/bin/env python3
"""
Compare Backtest and Simulation Results for 2024
"""

import json

def load_results(filename):
    """Load results from JSON file"""
    with open(filename, 'r') as f:
        return json.load(f)

def print_comparison():
    """Print comparison of backtest and simulation results"""
    
    print("="*80)
    print("COMPARISON: BACKTEST vs SIMULATION - 2024")
    print("="*80)
    print()
    
    # Load backtest results
    try:
        backtest_data = load_results('backtest_failed_fvg_2024_4h_expiry_fixed_rr_3.json')
        backtest_summary = backtest_data['summary']
    except FileNotFoundError:
        print("❌ Backtest results file not found!")
        return
    
    # Load simulation results
    try:
        sim_data = load_results('simulation_2024_results.json')
        sim_summary = sim_data['summary']
    except FileNotFoundError:
        print("❌ Simulation results file not found!")
        return
    
    # Print backtest results
    print("📊 BACKTEST RESULTS:")
    print(f"   Total Trades:      {backtest_summary['total_trades']}")
    print(f"   Wins:              {backtest_summary['wins']}")
    print(f"   Losses:            {backtest_summary['losses']}")
    print(f"   Win Rate:          {backtest_summary['win_rate']}%")
    print(f"   Total PnL:         ${backtest_summary['total_pnl']:+,.2f} ({backtest_summary['total_pnl_pct']:+.2f}%)")
    print(f"   Final Balance:     ${backtest_summary['final_balance']:,.2f}")
    print(f"   Avg Win:           ${backtest_summary['avg_win']:,.2f}")
    print(f"   Avg Loss:          ${backtest_summary['avg_loss']:,.2f}")
    print(f"   Profit Factor:     {backtest_summary['profit_factor']}")
    print(f"   Max Drawdown:      {backtest_summary['max_drawdown']}%")
    print(f"   Avg R:R:           {backtest_summary['avg_rr']:.2f}")
    print()
    
    # Print simulation results
    print("🤖 SIMULATION RESULTS:")
    print(f"   Total Trades:      {sim_summary['total_trades']}")
    print(f"   Wins:              {sim_summary['wins']}")
    print(f"   Losses:            {sim_summary['losses']}")
    print(f"   Win Rate:          {sim_summary['win_rate']}%")
    print(f"   Total PnL:         ${sim_summary['total_pnl']:+,.2f} ({sim_summary['total_pnl_pct']:+.2f}%)")
    print(f"   Final Balance:     ${sim_summary['final_balance']:,.2f}")
    print(f"   Avg Win:           ${sim_summary['avg_win']:,.2f}")
    print(f"   Avg Loss:          ${sim_summary['avg_loss']:,.2f}")
    print(f"   Profit Factor:     {sim_summary['profit_factor']}")
    print()
    
    # Calculate differences
    print("📈 DIFFERENCES:")
    trades_diff = sim_summary['total_trades'] - backtest_summary['total_trades']
    win_rate_diff = sim_summary['win_rate'] - backtest_summary['win_rate']
    pnl_diff = sim_summary['total_pnl'] - backtest_summary['total_pnl']
    pnl_pct_diff = sim_summary['total_pnl_pct'] - backtest_summary['total_pnl_pct']
    pf_diff = sim_summary['profit_factor'] - backtest_summary['profit_factor']
    
    print(f"   Trades Difference:     {trades_diff:+d}")
    print(f"   Win Rate Difference:    {win_rate_diff:+.2f}%")
    print(f"   PnL Difference:         ${pnl_diff:+,.2f} ({pnl_pct_diff:+.2f}%)")
    print(f"   Profit Factor Diff:     {pf_diff:+.2f}")
    print()
    
    # Calculate match percentage
    if backtest_summary['total_trades'] > 0:
        trades_match = (1 - abs(trades_diff) / backtest_summary['total_trades']) * 100
        print(f"   Trades Match:           {trades_match:.1f}%")
    
    if backtest_summary['total_pnl'] != 0:
        pnl_match = (1 - abs(pnl_diff) / abs(backtest_summary['total_pnl'])) * 100
        print(f"   PnL Match:              {pnl_match:.1f}%")
    
    print()
    print("="*80)
    
    # Check if results are similar
    if abs(trades_diff) <= 5 and abs(win_rate_diff) <= 5 and abs(pnl_pct_diff) <= 10:
        print("✅ Results are SIMILAR - Backtest and Simulation match well!")
    else:
        print("⚠️  Results are DIFFERENT - Need to investigate why")
    
    print("="*80)

if __name__ == "__main__":
    print_comparison()

