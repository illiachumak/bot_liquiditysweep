"""
Quick test script - тестує кілька найпопулярніших конфігурацій
"""
import sys
from pathlib import Path
from datetime import datetime
import json

from impulse_backtest import run_single_backtest
from impulse_detectors import ATRBasedDetector, VolumeBasedDetector, EngulfingDetector
from entry_strategies import PullbackEntry, BreakoutEntry
from ema_filter import EMAFilter


def run_quick_test():
    """Run quick test with popular configurations"""
    print("\n" + "="*80)
    print("QUICK TEST - Popular Impulse Candles Configurations")
    print("="*80 + "\n")

    results = []

    # Test configurations
    configs = [
        # ATR-Based + Pullback
        {
            'detector': ATRBasedDetector(atr_multiplier=2.0, body_ratio_threshold=0.75),
            'strategy': PullbackEntry(fib_level=0.618, rr_ratio=2.0),
            'lookback': 10
        },
        # Volume-Based + Pullback
        {
            'detector': VolumeBasedDetector(volume_multiplier=1.5),
            'strategy': PullbackEntry(fib_level=0.5, rr_ratio=2.0),
            'lookback': 10
        },
        # Engulfing + Breakout
        {
            'detector': EngulfingDetector(require_volume_confirmation=True, volume_multiplier=1.5),
            'strategy': BreakoutEntry(rr_ratio=2.0),
            'lookback': 10
        },
        # ATR-Based + Breakout
        {
            'detector': ATRBasedDetector(atr_multiplier=1.5, body_ratio_threshold=0.70),
            'strategy': BreakoutEntry(rr_ratio=3.0),
            'lookback': 5
        },
    ]

    assets = ['btc', 'eth']
    htf = '4h'
    ltf = '1h'

    counter = 0
    total = len(configs) * len(assets)

    for asset in assets:
        for config in configs:
            counter += 1

            detector = config['detector']
            strategy = config['strategy']
            lookback = config['lookback']

            ema_filter = EMAFilter(short_period=12, long_period=21, lookback=lookback)

            print(f"\n[{counter}/{total}] Testing:")
            print(f"  Asset: {asset.upper()}")
            print(f"  Detector: {detector.name}")
            print(f"  Strategy: {strategy.name}")
            print(f"  Lookback: {lookback}")

            try:
                result = run_single_backtest(asset, htf, ltf, detector, strategy, ema_filter)
                results.append(result)

                print(f"  ✓ Trades: {result['total_trades']}, "
                      f"Win Rate: {result['win_rate']}%, "
                      f"PnL: {result['total_pnl_pct']}%")

            except Exception as e:
                print(f"  ✗ ERROR: {e}")
                import traceback
                traceback.print_exc()

    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = Path(__file__).parent / f'quick_test_results_{timestamp}.json'

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n{'='*80}")
    print(f"Quick test completed!")
    print(f"Results saved to: {output_file}")
    print(f"{'='*80}\n")

    # Print summary
    print("SUMMARY:\n")
    sorted_results = sorted(results, key=lambda x: x['total_pnl_pct'], reverse=True)

    for i, result in enumerate(sorted_results, 1):
        print(f"{i}. {result['asset'].upper()} - {result['impulse_detector']} + {result['entry_strategy']}")
        print(f"   Trades: {result['total_trades']}, Win Rate: {result['win_rate']}%")
        print(f"   PnL: {result['total_pnl_pct']}%, Max DD: {result['max_drawdown_pct']}%")
        print(f"   Profit Factor: {result['profit_factor']}\n")

    return results


if __name__ == "__main__":
    results = run_quick_test()
