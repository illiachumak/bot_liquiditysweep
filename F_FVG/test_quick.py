"""
Quick test to validate backtest engine
Tests one configuration on limited data to ensure everything works
"""

import pandas as pd
from fvg_backtest_engine import FVGBacktester


def load_sample_data():
    """Load small sample of data for testing"""
    print("Loading sample data...")

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
    print(f"✅ Loaded {len(df_15m):,} 15M candles\n")

    return df_4h, df_15m


def test_single_config():
    """Test single configuration"""
    print("="*80)
    print("QUICK TEST - Single Configuration")
    print("="*80)
    print()

    # Load data
    df_4h, df_15m = load_sample_data()

    # Test parameters
    strategy = 'held'
    entry_method = '4h_close'
    tp_method = 'rr_3.0'
    start_date = '2024-01-01'
    end_date = '2024-12-31'  # Full year 2024

    print(f"Testing: {strategy.upper()} | {entry_method} | {tp_method}")
    print(f"Period: {start_date} to {end_date}")
    print()

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
    print("Running backtest...")
    result = backtester.run_backtest(
        df_4h=df_4h,
        df_15m=df_15m,
        start_date=start_date,
        end_date=end_date,
        entry_method=entry_method,
        tp_method=tp_method,
        strategy=strategy
    )

    # Print results
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    print()

    print(f"Strategy: {result['strategy'].upper()}")
    print(f"Entry Method: {result['entry_method']}")
    print(f"TP Method: {result['tp_method']}")
    print()

    print(f"📊 Trade Statistics:")
    print(f"   Total Trades: {result['total_trades']}")

    if result['total_trades'] > 0:
        print(f"   Winning: {result['winning_trades']}")
        print(f"   Losing: {result['losing_trades']}")
        print(f"   Win Rate: {result['win_rate']:.1f}%")
        print()

        print(f"💰 Performance:")
        print(f"   Total PnL: ${result['total_pnl']:,.2f}")
        print(f"   Total PnL %: {result['total_pnl_pct']:.2f}%")
        print(f"   Final Balance: ${result['final_balance']:,.2f}")
        print(f"   Avg Win: ${result['avg_win']:.2f}")
        print(f"   Avg Loss: ${result['avg_loss']:.2f}")
        print()

        print(f"📈 Risk Metrics:")
        print(f"   Max Drawdown: {result['max_drawdown']:.2f}%")
        print(f"   Profit Factor: {result['profit_factor']:.2f}")
        print(f"   Avg RR: {result['avg_rr']:.2f}")
        print()
    else:
        print("   ⚠️  No trades executed")
        print()

    print(f"🔍 Debug Stats:")
    print(f"   4H FVGs detected: {result['stats']['total_4h_fvgs']}")
    print(f"   Actionable FVGs: {result['stats']['total_actionable']}")
    print(f"   Setups created: {result['stats']['setups_created']}")
    print(f"   Fills: {result['stats']['fills']}")
    print(f"   No fills: {result['stats']['no_fills']}")
    print()

    # Show first 5 trades
    if result['trades']:
        print("📋 First 5 Trades:")
        print("-" * 80)
        for trade in result['trades'][:5]:
            emoji = "✅" if trade['pnl'] > 0 else "❌"
            print(f"{emoji} #{trade['trade_id']}: {trade['direction']} @ ${trade['entry']:.2f} | "
                  f"SL: ${trade['sl']:.2f} | TP: ${trade['tp']:.2f} | "
                  f"Exit: ${trade['exit_price']:.2f} ({trade['exit_reason']}) | "
                  f"PnL: ${trade['pnl']:+.2f}")

    print("\n" + "="*80)
    print("✅ Test complete!")
    print("="*80)

    # Validation checks
    print("\n🔍 Validation Checks:")

    if result['total_trades'] > 0:
        print("✅ Generated trades")
    else:
        print("⚠️  No trades generated - check if data period has FVG setups")

    if result['stats']['total_4h_fvgs'] > 0:
        print("✅ Detected 4H FVGs")
    else:
        print("⚠️  No 4H FVGs detected")

    if result['stats']['total_actionable'] > 0:
        print("✅ Found actionable FVGs (rejected/held)")
    else:
        print("⚠️  No actionable FVGs found")

    print("\n💡 If you see warnings above, try:")
    print("   - Increase date range (test Q1-Q4)")
    print("   - Try different strategy ('held' vs 'failed')")
    print("   - Check data is loading correctly")


if __name__ == "__main__":
    test_single_config()
