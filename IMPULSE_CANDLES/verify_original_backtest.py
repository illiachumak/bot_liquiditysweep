"""
Verify original backtest engine results
"""
import pandas as pd
from pathlib import Path
import json
from datetime import datetime

from impulse_backtest import ImpulseBacktest
from impulse_detectors import ATRBasedDetector
from ema_filter import EMAFilter
from entry_strategies import BreakoutEntry


def load_data(asset='btc'):
    """Load data"""
    data_dir = Path('/Users/illiachumak/trading/backtest/data')

    if asset == 'btc':
        htf_file = data_dir / 'btc_4h_data_2018_to_2025.csv'
        ltf_file = data_dir / 'btc_1h_data_2018_to_2025.csv'
    else:
        htf_file = data_dir / 'eth_4h_data_2017_to_2025.csv'
        ltf_file = data_dir / 'eth_1h_data_2017_to_2025.csv'

    htf_df = pd.read_csv(htf_file)
    ltf_df = pd.read_csv(ltf_file)

    return htf_df, ltf_df


def run_verification():
    """Run verification test"""

    print("\n" + "="*80)
    print("VERIFICATION: Original Backtest Engine")
    print("Testing same config that gave 89 trades during optimization")
    print("="*80 + "\n")

    # Same config as during optimization
    detector = ATRBasedDetector(atr_multiplier=1.5, body_ratio_threshold=0.70)
    strategy = BreakoutEntry(rr_ratio=3.0)
    ema_filter = EMAFilter(short_period=12, long_period=21, lookback=5)

    results = {}

    for asset in ['btc', 'eth']:
        print(f"\n{'='*80}")
        print(f"ASSET: {asset.upper()}")
        print(f"{'='*80}\n")

        htf_df, ltf_df = load_data(asset)

        backtest = ImpulseBacktest(
            htf_df=htf_df,
            ltf_df=ltf_df,
            impulse_detector=detector,
            entry_strategy=strategy,
            ema_filter=ema_filter,
            start_date='2024-01-01',
            end_date='2025-12-31',
            initial_capital=10000,
            risk_per_trade_pct=1.0
        )

        stats = backtest.run()
        stats['asset'] = asset

        results[asset] = stats

        print(f"\n{'='*80}")
        print(f"RESULTS - {asset.upper()}")
        print(f"{'='*80}\n")

        print(f"Impulses Found: {len(backtest.impulse_candles_found)}")
        print(f"Trades Executed: {stats['total_trades']}")
        print(f"Win Rate: {stats['win_rate']}%")
        print(f"EV per R: {stats.get('ev_per_r', 'N/A')}")
        print(f"Total PnL: {stats.get('total_pnl_pct', 0)}%")
        print(f"Max DD: {stats.get('max_drawdown_pct', 0)}%\n")

    # Save
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = Path(__file__).parent / f'VERIFICATION_RESULTS_{timestamp}.json'

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n{'='*80}")
    print(f"Results saved to: {output_file}")
    print(f"{'='*80}\n")

    # Compare
    print("\n" + "="*80)
    print("COMPARISON WITH OPTIMIZATION RESULTS:")
    print("="*80 + "\n")

    print("Expected (from optimization):")
    print("  BTC: 89 trades, WR ~40%, EV ~1.17, PnL ~165%")
    print("  ETH: 80 trades, WR ~39%, EV ~0.90, PnL ~96%\n")

    print("Actual (this run):")
    print(f"  BTC: {results['btc']['total_trades']} trades, "
          f"WR {results['btc']['win_rate']}%, "
          f"EV {results['btc'].get('ev_per_r', 'N/A')}, "
          f"PnL {results['btc'].get('total_pnl_pct', 0)}%")
    print(f"  ETH: {results['eth']['total_trades']} trades, "
          f"WR {results['eth']['win_rate']}%, "
          f"EV {results['eth'].get('ev_per_r', 'N/A')}, "
          f"PnL {results['eth'].get('total_pnl_pct', 0)}%\n")

    # Check if match
    btc_match = abs(results['btc']['total_trades'] - 89) <= 5

    if btc_match:
        print("✅ RESULTS MATCH! Original backtest is consistent.")
    else:
        print("⚠️ MISMATCH! Something changed between optimization and now.")
        print("   This could indicate:")
        print("   - Data file updated")
        print("   - Code changed")
        print("   - Different filtering logic")

    return results


if __name__ == "__main__":
    results = run_verification()
