#!/usr/bin/env python3
"""
Comparison script for backtests
Compares the 2-month recent backtest with the full 2024 backtest
"""

import json
from datetime import datetime

def load_backtest_results(filename):
    """Load backtest results from JSON file"""
    with open(filename, 'r') as f:
        return json.load(f)

def calculate_monthly_metrics(trades, start_date, end_date):
    """Calculate monthly breakdown metrics"""
    from collections import defaultdict

    monthly_pnl = defaultdict(float)
    monthly_trades = defaultdict(int)
    monthly_wins = defaultdict(int)

    for trade in trades:
        entry_time = datetime.strptime(trade['entry_time'], '%Y-%m-%d %H:%M:%S')
        month_key = entry_time.strftime('%Y-%m')

        monthly_pnl[month_key] += trade['pnl']
        monthly_trades[month_key] += 1
        if trade['result'] == 'WIN':
            monthly_wins[month_key] += 1

    return monthly_pnl, monthly_trades, monthly_wins

def print_comparison(backtest1_file, backtest2_file, name1, name2):
    """Print detailed comparison between two backtests"""

    # Load data
    bt1 = load_backtest_results(backtest1_file)
    bt2 = load_backtest_results(backtest2_file)

    s1 = bt1['summary']
    s2 = bt2['summary']

    print("\n" + "="*100)
    print(f"BACKTEST COMPARISON: {name1} vs {name2}")
    print("="*100 + "\n")

    # Overall Summary
    print("OVERALL PERFORMANCE METRICS")
    print("-"*100)
    print(f"{'Metric':<30} {name1:<30} {name2:<30} {'Change':<15}")
    print("-"*100)

    # Calculate changes
    def calc_change(val1, val2):
        if val1 == 0:
            return "N/A"
        change = ((val2 - val1) / val1) * 100
        sign = "+" if change > 0 else ""
        return f"{sign}{change:.2f}%"

    metrics = [
        ('Total Trades', s1['total_trades'], s2['total_trades']),
        ('Wins', s1['wins'], s2['wins']),
        ('Losses', s1['losses'], s2['losses']),
        ('Win Rate (%)', f"{s1['win_rate']:.2f}", f"{s2['win_rate']:.2f}"),
        ('Total PnL (USDT)', f"{s1['total_pnl']:.2f}", f"{s2['total_pnl']:.2f}"),
        ('Total Return (%)', f"{s1['total_pnl_pct']:.2f}", f"{s2['total_pnl_pct']:.2f}"),
        ('Average Win (USDT)', f"{s1['avg_win']:.2f}", f"{s2['avg_win']:.2f}"),
        ('Average Loss (USDT)', f"{s1['avg_loss']:.2f}", f"{s2['avg_loss']:.2f}"),
        ('Average RR', f"{s1['avg_rr']:.2f}", f"{s2['avg_rr']:.2f}"),
        ('Max Drawdown (%)', f"{s1['max_drawdown']:.2f}", f"{s2['max_drawdown']:.2f}"),
        ('Final Balance (USDT)', f"{s1['final_balance']:.2f}", f"{s2['final_balance']:.2f}"),
        ('Monthly Return (%)', f"{s1['monthly_return']:.2f}", f"{s2['monthly_return']:.2f}"),
        ('Profit Factor', f"{s1['profit_factor']:.2f}", f"{s2['profit_factor']:.2f}"),
    ]

    for metric_name, val1, val2 in metrics:
        try:
            change = calc_change(float(str(val1).replace(',','')), float(str(val2).replace(',','')))
        except (ValueError, ZeroDivisionError):
            change = "N/A"

        print(f"{metric_name:<30} {str(val1):<30} {str(val2):<30} {change:<15}")

    print("\n" + "-"*100 + "\n")

    # Detailed Analysis
    print("\nDETAILED ANALYSIS")
    print("-"*100)

    # Win/Loss distribution
    print(f"\n📊 Win/Loss Distribution:")
    print(f"{name1}: {s1['wins']} wins / {s1['losses']} losses ({s1['win_rate']:.2f}% win rate)")
    print(f"{name2}: {s2['wins']} wins / {s2['losses']} losses ({s2['win_rate']:.2f}% win rate)")

    # Risk-Reward Analysis
    print(f"\n💰 Risk-Reward Analysis:")
    expectancy1 = (s1['win_rate']/100 * s1['avg_win']) + ((100-s1['win_rate'])/100 * s1['avg_loss'])
    expectancy2 = (s2['win_rate']/100 * s2['avg_win']) + ((100-s2['win_rate'])/100 * s2['avg_loss'])
    print(f"{name1} Expectancy: ${expectancy1:.2f} per trade")
    print(f"{name2} Expectancy: ${expectancy2:.2f} per trade")

    # Trading Frequency
    print(f"\n📈 Trading Frequency:")
    trades1 = bt1['trades']
    trades2 = bt2['trades']

    if trades1:
        date1_start = datetime.strptime(trades1[0]['entry_time'], '%Y-%m-%d %H:%M:%S')
        date1_end = datetime.strptime(trades1[-1]['entry_time'], '%Y-%m-%d %H:%M:%S')
        days1 = (date1_end - date1_start).days + 1
        print(f"{name1}: {s1['total_trades']} trades over {days1} days ({s1['total_trades']/days1:.2f} trades/day)")

    if trades2:
        date2_start = datetime.strptime(trades2[0]['entry_time'], '%Y-%m-%d %H:%M:%S')
        date2_end = datetime.strptime(trades2[-1]['entry_time'], '%Y-%m-%d %H:%M:%S')
        days2 = (date2_end - date2_start).days + 1
        print(f"{name2}: {s2['total_trades']} trades over {days2} days ({s2['total_trades']/days2:.2f} trades/day)")

    # Monthly Breakdown for 2-month backtest
    if trades2:
        print(f"\n📅 Monthly Breakdown ({name2}):")
        print("-"*100)
        monthly_pnl, monthly_trades, monthly_wins = calculate_monthly_metrics(trades2, date2_start, date2_end)

        print(f"{'Month':<15} {'Trades':<10} {'Wins':<10} {'Win Rate':<12} {'PnL (USDT)':<15}")
        print("-"*100)
        for month in sorted(monthly_pnl.keys()):
            win_rate = (monthly_wins[month] / monthly_trades[month] * 100) if monthly_trades[month] > 0 else 0
            print(f"{month:<15} {monthly_trades[month]:<10} {monthly_wins[month]:<10} {win_rate:<12.2f}% {monthly_pnl[month]:<15.2f}")

    # Best and Worst Trades
    print(f"\n🏆 Top 5 Best Trades ({name2}):")
    print("-"*100)
    sorted_trades = sorted(trades2, key=lambda x: x['pnl'], reverse=True)[:5]
    print(f"{'Date':<20} {'Type':<10} {'Entry':<12} {'Exit':<12} {'PnL':<12} {'PnL %':<10}")
    print("-"*100)
    for trade in sorted_trades:
        print(f"{trade['entry_time']:<20} {trade['type']:<10} {trade['entry_price']:<12.2f} {trade['exit_price']:<12.2f} {trade['pnl']:<12.2f} {trade['pnl_pct']:<10.2f}%")

    print(f"\n📉 Top 5 Worst Trades ({name2}):")
    print("-"*100)
    sorted_trades = sorted(trades2, key=lambda x: x['pnl'])[:5]
    print(f"{'Date':<20} {'Type':<10} {'Entry':<12} {'Exit':<12} {'PnL':<12} {'PnL %':<10}")
    print("-"*100)
    for trade in sorted_trades:
        print(f"{trade['entry_time']:<20} {trade['type']:<10} {trade['entry_price']:<12.2f} {trade['exit_price']:<12.2f} {trade['pnl']:<12.2f} {trade['pnl_pct']:<10.2f}%")

    # Key Insights
    print("\n\n" + "="*100)
    print("KEY INSIGHTS")
    print("="*100 + "\n")

    insights = []

    # Win rate comparison
    if s2['win_rate'] > s1['win_rate']:
        insights.append(f"✅ Win rate IMPROVED by {s2['win_rate'] - s1['win_rate']:.2f}% ({s1['win_rate']:.2f}% → {s2['win_rate']:.2f}%)")
    else:
        insights.append(f"⚠️  Win rate DECREASED by {s1['win_rate'] - s2['win_rate']:.2f}% ({s1['win_rate']:.2f}% → {s2['win_rate']:.2f}%)")

    # Profit factor comparison
    if s2['profit_factor'] > s1['profit_factor']:
        insights.append(f"✅ Profit factor IMPROVED by {((s2['profit_factor'] - s1['profit_factor'])/s1['profit_factor']*100):.2f}% ({s1['profit_factor']:.2f} → {s2['profit_factor']:.2f})")
    else:
        insights.append(f"⚠️  Profit factor DECREASED by {((s1['profit_factor'] - s2['profit_factor'])/s1['profit_factor']*100):.2f}% ({s1['profit_factor']:.2f} → {s2['profit_factor']:.2f})")

    # Monthly return comparison
    if s2['monthly_return'] > s1['monthly_return']:
        insights.append(f"✅ Monthly return IMPROVED from {s1['monthly_return']:.2f}% to {s2['monthly_return']:.2f}%")
    else:
        insights.append(f"⚠️  Monthly return DECREASED from {s1['monthly_return']:.2f}% to {s2['monthly_return']:.2f}%")

    # Max drawdown comparison
    if s2['max_drawdown'] < s1['max_drawdown']:
        insights.append(f"✅ Max drawdown IMPROVED (reduced) from {s1['max_drawdown']:.2f}% to {s2['max_drawdown']:.2f}%")
    else:
        insights.append(f"⚠️  Max drawdown INCREASED from {s1['max_drawdown']:.2f}% to {s2['max_drawdown']:.2f}%")

    # Expectancy comparison
    if expectancy2 > expectancy1:
        insights.append(f"✅ Trade expectancy IMPROVED from ${expectancy1:.2f} to ${expectancy2:.2f} per trade")
    else:
        insights.append(f"⚠️  Trade expectancy DECREASED from ${expectancy1:.2f} to ${expectancy2:.2f} per trade")

    for insight in insights:
        print(f"  {insight}")

    print("\n" + "="*100 + "\n")

if __name__ == "__main__":
    # Compare 2024 full year vs last 2 months
    print_comparison(
        backtest1_file="backtest_2024_fixed.json",
        backtest2_file="backtest_2months_20251117_165856.json",
        name1="2024 Full Year",
        name2="Last 2 Months (Sep-Nov 2025)"
    )
