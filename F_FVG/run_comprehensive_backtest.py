"""
Comprehensive FVG Strategy Backtest Runner
==========================================

Tests all combinations of:
- Strategies: FAILED vs HELD
- Entry methods: 4H close, 15M FVG, 15M breakout
- TP methods: Liquidity, RR 2.0, RR 3.0

Periods tested:
- 2023: Full year
- 2024: Full year
- 2025: YTD

Output: Detailed comparison with JSON results
"""

import pandas as pd
import json
from datetime import datetime
from fvg_backtest_engine import FVGBacktester


def load_data_from_csv() -> tuple:
    """Load 4H and 15M data from CSV files"""
    print("Loading data from CSV files...")

    # Update these paths to your actual CSV locations
    csv_4h = '/Users/illiachumak/trading/backtest/data/btc_4h_data_2018_to_2025.csv'
    csv_15m = '/Users/illiachumak/trading/backtest/data/btc_15m_data_2018_to_2025.csv'

    # Load 4H
    df_4h = pd.read_csv(csv_4h)
    df_4h['Open time'] = pd.to_datetime(df_4h['Open time'])
    df_4h.set_index('Open time', inplace=True)
    df_4h = df_4h[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)

    # Load 15M
    df_15m = pd.read_csv(csv_15m)
    df_15m['Open time'] = pd.to_datetime(df_15m['Open time'])
    df_15m.set_index('Open time', inplace=True)
    df_15m = df_15m[['Open', 'High', 'Low', 'Close', 'Volume']].astype(float)

    print(f"✅ Loaded {len(df_4h):,} 4H candles")
    print(f"✅ Loaded {len(df_15m):,} 15M candles")
    print(f"4H range: {df_4h.index[0]} to {df_4h.index[-1]}")
    print(f"15M range: {df_15m.index[0]} to {df_15m.index[-1]}\n")

    return df_4h, df_15m


def print_results_table(results: list):
    """Print formatted results table"""
    print(f"\n{'='*120}")
    print("BACKTEST RESULTS COMPARISON")
    print(f"{'='*120}\n")

    # Table header
    header = f"{'Strategy':<10} {'Entry':<15} {'TP':<12} {'Trades':<8} {'Win%':<8} " \
             f"{'PnL':<12} {'PnL%':<10} {'Final':<12} {'MaxDD%':<10} {'PF':<8} {'AvgRR':<8}"
    print(header)
    print("-" * 120)

    # Sort by total PnL
    results_sorted = sorted(results, key=lambda x: x['total_pnl'], reverse=True)

    for r in results_sorted:
        strategy = r['strategy']
        entry = r['entry_method']
        tp = r['tp_method']
        trades = r['total_trades']
        win_rate = r['win_rate']
        pnl = r['total_pnl']
        pnl_pct = r['total_pnl_pct']
        final = r['final_balance']
        max_dd = r['max_drawdown']
        pf = r['profit_factor']
        avg_rr = r['avg_rr']

        pf_str = f"{pf:.2f}" if pf != float('inf') else "∞"

        # Color code (best = green checkmark)
        emoji = "🟢" if pnl > 0 else "🔴"

        print(f"{strategy:<10} {entry:<15} {tp:<12} {trades:<8} {win_rate:<8.1f} "
              f"${pnl:<11.2f} {pnl_pct:<10.1f} ${final:<11.2f} {max_dd:<10.1f} "
              f"{pf_str:<8} {avg_rr:<8.2f} {emoji}")

    print("\n" + "="*120)


def print_summary_stats(results: list, period: str):
    """Print summary statistics"""
    print(f"\n📊 SUMMARY - {period}")
    print("=" * 60)

    profitable = [r for r in results if r['total_pnl'] > 0]
    unprofitable = [r for r in results if r['total_pnl'] <= 0]

    print(f"Total configurations tested: {len(results)}")
    print(f"Profitable: {len(profitable)} ({len(profitable)/len(results)*100:.1f}%)")
    print(f"Unprofitable: {len(unprofitable)} ({len(unprofitable)/len(results)*100:.1f}%)")

    if profitable:
        best = max(profitable, key=lambda x: x['total_pnl'])
        print(f"\n🏆 BEST CONFIGURATION:")
        print(f"   Strategy: {best['strategy']}")
        print(f"   Entry: {best['entry_method']}")
        print(f"   TP: {best['tp_method']}")
        print(f"   Trades: {best['total_trades']}")
        print(f"   Win Rate: {best['win_rate']:.1f}%")
        print(f"   Total PnL: ${best['total_pnl']:.2f} ({best['total_pnl_pct']:.1f}%)")
        print(f"   Profit Factor: {best['profit_factor']:.2f}")
        print(f"   Max Drawdown: {best['max_drawdown']:.1f}%")
        print(f"   Avg RR: {best['avg_rr']:.2f}")

        # Print top 3
        print(f"\n📈 TOP 3 CONFIGURATIONS:")
        top3 = sorted(profitable, key=lambda x: x['total_pnl'], reverse=True)[:3]
        for i, r in enumerate(top3, 1):
            print(f"   #{i}: {r['strategy']} | {r['entry_method']} | {r['tp_method']} | "
                  f"PnL: ${r['total_pnl']:.2f} ({r['total_pnl_pct']:.1f}%)")

    print("=" * 60)


def run_comprehensive_test():
    """Run comprehensive backtest across all variations"""

    print(f"\n{'#'*80}")
    print("# FVG STRATEGY COMPREHENSIVE BACKTEST")
    print(f"{'#'*80}\n")
    print(f"Test started at: {datetime.now()}\n")

    # Load data
    df_4h, df_15m = load_data_from_csv()

    # Test configurations
    strategies = ['failed', 'held']
    entry_methods = ['4h_close', '15m_fvg', '15m_breakout']
    tp_methods = ['liquidity', 'rr_2.0', 'rr_3.0']

    # Test periods
    periods = [
        ('2023-01-01', '2023-12-31', '2023'),
        ('2024-01-01', '2024-12-31', '2024'),
        ('2025-01-01', '2025-12-31', '2025'),
    ]

    # Store all results
    all_results = {}

    # Run tests
    total_configs = len(strategies) * len(entry_methods) * len(tp_methods)

    for start_date, end_date, period_name in periods:
        print(f"\n{'='*80}")
        print(f"TESTING PERIOD: {period_name}")
        print(f"{'='*80}")
        print(f"Date range: {start_date} to {end_date}")
        print(f"Total configurations: {total_configs}\n")

        period_results = []
        config_count = 0

        for strategy in strategies:
            for entry_method in entry_methods:
                for tp_method in tp_methods:
                    config_count += 1

                    print(f"[{config_count}/{total_configs}] Testing: "
                          f"{strategy.upper()} | {entry_method} | {tp_method}...", end=' ')

                    # Initialize backtester
                    backtester = FVGBacktester(
                        initial_balance=10000.0,
                        risk_per_trade=0.02,
                        min_rr=2.0,
                        min_sl_pct=0.3,
                        max_sl_pct=5.0,
                        enable_fees=True,
                        limit_expiry_candles=16
                    )

                    # Run backtest
                    try:
                        result = backtester.run_backtest(
                            df_4h=df_4h,
                            df_15m=df_15m,
                            start_date=start_date,
                            end_date=end_date,
                            entry_method=entry_method,
                            tp_method=tp_method,
                            strategy=strategy
                        )

                        period_results.append(result)

                        # Quick summary
                        trades = result['total_trades']
                        pnl = result['total_pnl']
                        win_rate = result['win_rate']

                        status = "✅" if pnl > 0 else "❌"
                        print(f"{status} {trades} trades, ${pnl:+.2f}, WR: {win_rate:.1f}%")

                    except Exception as e:
                        print(f"❌ ERROR: {e}")
                        continue

        # Store results for this period
        all_results[period_name] = period_results

        # Print results table for this period
        print_results_table(period_results)

        # Print summary stats
        print_summary_stats(period_results, period_name)

        # Save period results
        output_file = f"F_FVG/backtest_results_{period_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(output_file, 'w') as f:
            json.dump({
                'period': period_name,
                'start_date': start_date,
                'end_date': end_date,
                'results': period_results
            }, f, indent=2)

        print(f"\n💾 Results saved to: {output_file}")

    # Final comparison across all periods
    print(f"\n\n{'#'*80}")
    print("# FINAL COMPARISON - ALL PERIODS")
    print(f"{'#'*80}\n")

    # Compare best configs across periods
    for strategy in strategies:
        for entry_method in entry_methods:
            for tp_method in tp_methods:
                print(f"\n{strategy.upper()} | {entry_method} | {tp_method}")
                print("-" * 60)

                for period_name in ['2023', '2024', '2025']:
                    if period_name in all_results:
                        matching = [r for r in all_results[period_name]
                                   if r['strategy'] == strategy and
                                   r['entry_method'] == entry_method and
                                   r['tp_method'] == tp_method]

                        if matching:
                            r = matching[0]
                            emoji = "🟢" if r['total_pnl'] > 0 else "🔴"
                            print(f"  {period_name}: {r['total_trades']:3} trades | "
                                  f"${r['total_pnl']:+8.2f} ({r['total_pnl_pct']:+6.1f}%) | "
                                  f"WR: {r['win_rate']:5.1f}% | PF: {r['profit_factor']:5.2f} {emoji}")

    # Find overall best
    print(f"\n{'='*80}")
    print("🏆 OVERALL BEST CONFIGURATIONS (by total PnL across all periods)")
    print(f"{'='*80}\n")

    # Aggregate by config
    config_totals = {}

    for strategy in strategies:
        for entry_method in entry_methods:
            for tp_method in tp_methods:
                key = f"{strategy}|{entry_method}|{tp_method}"
                total_pnl = 0
                total_trades = 0

                for period_name in ['2023', '2024', '2025']:
                    if period_name in all_results:
                        matching = [r for r in all_results[period_name]
                                   if r['strategy'] == strategy and
                                   r['entry_method'] == entry_method and
                                   r['tp_method'] == tp_method]

                        if matching:
                            total_pnl += matching[0]['total_pnl']
                            total_trades += matching[0]['total_trades']

                config_totals[key] = {
                    'strategy': strategy,
                    'entry_method': entry_method,
                    'tp_method': tp_method,
                    'total_pnl': total_pnl,
                    'total_trades': total_trades
                }

    # Sort and print top 5
    sorted_configs = sorted(config_totals.values(),
                           key=lambda x: x['total_pnl'], reverse=True)

    for i, config in enumerate(sorted_configs[:5], 1):
        emoji = "🟢" if config['total_pnl'] > 0 else "🔴"
        print(f"#{i}: {config['strategy'].upper():<8} | {config['entry_method']:<15} | "
              f"{config['tp_method']:<12} | {config['total_trades']:4} trades | "
              f"${config['total_pnl']:+10.2f} {emoji}")

    print(f"\n{'='*80}")
    print(f"Test completed at: {datetime.now()}")
    print(f"{'='*80}\n")

    print("✅ All backtests complete!")


if __name__ == "__main__":
    run_comprehensive_test()
