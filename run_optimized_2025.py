"""
Run optimized backtest for 2025 year
Using best parameters from optimization:
- Volume Lookback: 25
- Min Stop Loss: 0.3%
- Max Position Size: 10 BTC
"""

import sys
import os
from pathlib import Path
from datetime import datetime

sys.path.append(os.path.dirname(__file__))
from run_liquidity_backtest_real_data import load_data_from_backtest_data
from liquidity_reversal_backtest import LiquidityReversalBacktest


def run_2025_backtest():
    """Run optimized backtest for 2025 year"""
    
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║          OPTIMIZED BACKTEST - 2025 YEAR                                      ║
║                                                                              ║
║  Optimized Parameters:                                                       ║
║    - Volume Lookback: 25                                                     ║
║    - Min Stop Loss: 0.3%                                                    ║
║    - Max Position Size: 10 BTC                                               ║
║    - Commission: 0.06% per side (0.12% round-trip)                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # 2025 year
    start_date = '2025-01-01'
    end_date = '2025-12-31'
    
    print(f"\n📅 Period: {start_date} to {end_date}")
    
    # Load data
    print("\n" + "-"*80)
    df_4h = load_data_from_backtest_data('4h', start_date, end_date)
    df_15m = load_data_from_backtest_data('15m', start_date, end_date)
    
    # Create optimized backtest
    print("\n" + "-"*80)
    print("🔧 Initializing OPTIMIZED backtest engine...")
    print("   Volume Lookback: 25")
    print("   Min Stop Loss: 0.3%")
    print("   Max Position Size: 10 BTC")
    print("   Commission: Market 0.0450%, Limit 0.0180%")
    
    backtest = LiquidityReversalBacktest(
        initial_balance=10000,
        risk_per_trade=0.02,  # 2% risk per trade
        volume_threshold=1.2,  # 1.2x average volume
        sweep_lookback=20,
        volume_lookback=25,  # Optimized: 25
        min_stop_loss_pct=0.003,  # Optimized: 0.3% minimum SL
        max_position_size=10.0,  # Optimized: max 10 BTC
        market_commission=0.00045,  # 0.0450% for market orders
        limit_commission=0.00018,  # 0.0180% for limit orders
        use_limit_entry=True  # Use limit order at liquidity level (cheaper)
    )
    
    # Run backtest
    print("\n" + "="*80)
    results = backtest.run_backtest(df_4h, df_15m, start_date, end_date)
    
    # Save results
    print("\n" + "-"*80)
    print("💾 Saving results...")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    results_dir = Path(__file__).parent / 'backtest_results'
    results_dir.mkdir(exist_ok=True)
    
    backtest.save_results(results, f'liquidity_reversal_optimized_2025_{timestamp}.json')
    backtest.save_trades_csv(f'liquidity_reversal_optimized_2025_{timestamp}.csv')
    
    # Print summary
    print("\n" + "="*80)
    print("📊 OPTIMIZED 2025 BACKTEST SUMMARY")
    print("="*80)
    
    print(f"\n💰 Financial Results:")
    print(f"   Initial Balance: ${results['initial_balance']:,.2f}")
    print(f"   Final Balance: ${results['final_balance']:,.2f}")
    print(f"   Total PnL: ${results['total_pnl']:+,.2f}")
    print(f"   Total Return: {results['total_return']:+.2f}%")
    print(f"   Total Commission: ${results['total_commission']:,.2f}")
    
    print(f"\n📈 Trade Statistics:")
    print(f"   Total Trades: {results['total_trades']}")
    print(f"   Winning Trades: {results['winning_trades']}")
    print(f"   Losing Trades: {results['losing_trades']}")
    print(f"   Win Rate: {results['win_rate']:.2f}%")
    
    print(f"\n💵 Performance Metrics:")
    print(f"   Average Win: ${results['avg_win']:,.2f}")
    print(f"   Average Loss: ${results['avg_loss']:,.2f}")
    print(f"   Profit Factor: {results['profit_factor']:.2f}")
    print(f"   Max Drawdown: {results['max_drawdown']:.2f}%")
    
    print(f"\n📊 Additional Metrics:")
    print(f"   Avg Commission per Trade: ${results['avg_commission_per_trade']:.2f} ({results['avg_commission_pct']:.3f}% of deposit)")
    print(f"   Avg Trades per Month: {results['trades_per_month']:.2f}")
    print(f"   Avg Winning R: {results['avg_winning_r']:.2f}")
    print(f"   Avg Losing R: {results['avg_losing_r']:.2f}")
    print(f"   Expected Value (EV): {results['expected_value']:.3f} R")
    
    print(f"\n🔍 Filter Effectiveness:")
    diag = results['diagnostics']
    print(f"   Sweeps Detected: {diag['sweeps_detected']}")
    print(f"   Successful Entries: {diag['successful_entries']}")
    print(f"   Filtered by Min SL: {diag.get('failed_min_sl', 0)}")
    print(f"   Filtered by Max Size: {diag.get('failed_max_size', 0)}")
    total_filtered = diag.get('failed_min_sl', 0) + diag.get('failed_max_size', 0)
    if total_filtered > 0:
        print(f"   Total Filtered: {total_filtered} trades")
        reduction = (total_filtered / (results['total_trades'] + total_filtered) * 100) if (results['total_trades'] + total_filtered) > 0 else 0
        print(f"   Trade Reduction: {reduction:.1f}%")
    
    print("\n" + "="*80)
    print("✅ OPTIMIZED BACKTEST COMPLETED!")
    print("="*80)
    print(f"\n📁 Results saved to: {results_dir}")
    print(f"   - JSON: liquidity_reversal_optimized_2025_{timestamp}.json")
    print(f"   - CSV: liquidity_reversal_optimized_2025_{timestamp}.csv")
    
    return results


if __name__ == "__main__":
    try:
        results = run_2025_backtest()
        print("\n🎉 Success!")
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

