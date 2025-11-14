"""
Quick test script for liquidity reversal backtest
Tests individual components and runs a small backtest
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from liquidity_reversal_backtest import (
    LiquiditySweepDetector,
    FVGDetector,
    VolumeAnalyzer,
    ReversalDetector,
    LiquidityReversalBacktest
)


def generate_test_data(n_candles: int = 500, timeframe: str = '15m') -> pd.DataFrame:
    """
    Generate synthetic test data for testing

    Args:
        n_candles: Number of candles to generate
        timeframe: Timeframe string ('15m', '4h')

    Returns:
        DataFrame with OHLCV data
    """
    print(f"\n🔧 Generating {n_candles} {timeframe} test candles...")

    # Generate timestamps
    if timeframe == '15m':
        freq = '15min'
    elif timeframe == '4h':
        freq = '4H'
    else:
        freq = timeframe

    start = datetime(2023, 1, 1)
    timestamps = pd.date_range(start=start, periods=n_candles, freq=freq)

    # Generate price data with trend and volatility
    base_price = 25000
    trend = np.linspace(0, 3000, n_candles)  # Uptrend
    noise = np.random.normal(0, 200, n_candles)  # Volatility
    prices = base_price + trend + noise

    # Generate OHLCV
    data = {
        'open': [],
        'high': [],
        'low': [],
        'close': [],
        'volume': []
    }

    for i in range(n_candles):
        o = prices[i]
        c = o + np.random.normal(0, 100)

        # Ensure high is highest, low is lowest
        h = max(o, c) + abs(np.random.normal(0, 50))
        l = min(o, c) - abs(np.random.normal(0, 50))

        # Generate volume
        v = np.random.uniform(10, 100)

        data['open'].append(o)
        data['high'].append(h)
        data['low'].append(l)
        data['close'].append(c)
        data['volume'].append(v)

    df = pd.DataFrame(data, index=timestamps)

    print(f"   ✅ Generated data from {df.index[0]} to {df.index[-1]}")
    print(f"   Price range: ${df['low'].min():.2f} - ${df['high'].max():.2f}")

    return df


def test_liquidity_sweep_detector():
    """Test liquidity sweep detection"""
    print("\n" + "="*80)
    print("TEST 1: Liquidity Sweep Detector")
    print("="*80)

    df_4h = generate_test_data(n_candles=200, timeframe='4h')
    detector = LiquiditySweepDetector(lookback=20, sweep_threshold=0.001)

    sweeps_found = 0

    for idx in range(30, len(df_4h)):
        sweep = detector.detect_liquidity_sweep(df_4h, idx)

        if sweep:
            sweeps_found += 1
            print(f"\n✅ Sweep #{sweeps_found} detected:")
            print(f"   Time: {sweep['sweep_time']}")
            print(f"   Type: {sweep['type']}")
            print(f"   Level: ${sweep['swept_level']:,.2f}")

            if sweeps_found >= 3:  # Show only first 3
                break

    print(f"\n📊 Total sweeps found: {sweeps_found}")


def test_fvg_detector():
    """Test FVG detection"""
    print("\n" + "="*80)
    print("TEST 2: FVG Detector")
    print("="*80)

    df_15m = generate_test_data(n_candles=100, timeframe='15m')

    fvgs_found = 0

    for idx in range(2, len(df_15m)):
        fvg = FVGDetector.detect_fvg(df_15m, idx)

        if fvg:
            fvgs_found += 1
            print(f"\n✅ FVG #{fvgs_found} detected:")
            print(f"   Type: {fvg['type']}")
            print(f"   Top: ${fvg['top']:,.2f}")
            print(f"   Bottom: ${fvg['bottom']:,.2f}")
            print(f"   Size: ${fvg['size']:.2f}")

            if fvgs_found >= 3:  # Show only first 3
                break

    print(f"\n📊 Total FVGs found: {fvgs_found}")


def test_volume_analyzer():
    """Test volume analysis"""
    print("\n" + "="*80)
    print("TEST 3: Volume Analyzer")
    print("="*80)

    df_15m = generate_test_data(n_candles=50, timeframe='15m')

    # Manually create high volume candle
    df_15m.loc[df_15m.index[30], 'volume'] = 200  # 2x normal

    print(f"\n📊 Testing volume at index 30:")
    print(f"   Volume: {df_15m.iloc[30]['volume']:.2f}")

    ratio = VolumeAnalyzer.calculate_volume_ratio(df_15m, 30, lookback=20)
    is_high = VolumeAnalyzer.is_high_volume(df_15m, 30, threshold=1.5, lookback=20)

    print(f"   Ratio vs avg: {ratio:.2f}x")
    print(f"   Is high volume (>1.5x): {is_high}")

    if is_high:
        print("   ✅ Correctly identified high volume!")
    else:
        print("   ⚠️  Not detected as high volume")


def test_reversal_detector():
    """Test reversal candle detection"""
    print("\n" + "="*80)
    print("TEST 4: Reversal Detector")
    print("="*80)

    df_15m = generate_test_data(n_candles=50, timeframe='15m')

    # Create strong bullish reversal candle manually
    idx = 30
    low_price = 25000
    high_price = 25500
    df_15m.loc[df_15m.index[idx], 'open'] = low_price + 50
    df_15m.loc[df_15m.index[idx], 'low'] = low_price
    df_15m.loc[df_15m.index[idx], 'high'] = high_price
    df_15m.loc[df_15m.index[idx], 'close'] = high_price - 50  # Close near high

    print(f"\n📊 Testing reversal at index {idx}:")
    print(f"   OHLC: {df_15m.iloc[idx]['open']:.2f} / {df_15m.iloc[idx]['high']:.2f} / "
          f"{df_15m.iloc[idx]['low']:.2f} / {df_15m.iloc[idx]['close']:.2f}")

    is_bull_rev = ReversalDetector.detect_bullish_reversal(df_15m, idx)
    is_bear_rev = ReversalDetector.detect_bearish_reversal(df_15m, idx)

    print(f"   Is bullish reversal: {is_bull_rev}")
    print(f"   Is bearish reversal: {is_bear_rev}")

    if is_bull_rev:
        print("   ✅ Correctly identified bullish reversal!")


def test_full_backtest():
    """Test full backtest with synthetic data"""
    print("\n" + "="*80)
    print("TEST 5: Full Backtest with Synthetic Data")
    print("="*80)

    # Generate data
    df_4h = generate_test_data(n_candles=200, timeframe='4h')
    df_15m = generate_test_data(n_candles=3200, timeframe='15m')  # 16x more candles

    # Ensure 15m data covers same period as 4h
    df_15m.index = pd.date_range(
        start=df_4h.index[0],
        end=df_4h.index[-1],
        periods=len(df_15m)
    )

    print("\n📊 Data prepared:")
    print(f"   4H: {len(df_4h)} candles")
    print(f"   15M: {len(df_15m)} candles")

    # Create backtest
    backtest = LiquidityReversalBacktest(
        initial_balance=10000,
        risk_per_trade=0.02,
        volume_threshold=1.3,  # Lower threshold for test data
        sweep_lookback=15       # Shorter lookback for test
    )

    # Run backtest
    print("\n🚀 Running backtest...")
    try:
        results = backtest.run_backtest(df_4h, df_15m)

        print("\n" + "="*80)
        print("✅ BACKTEST COMPLETED SUCCESSFULLY")
        print("="*80)

        return results

    except Exception as e:
        print(f"\n❌ Error during backtest: {e}")
        import traceback
        traceback.print_exc()
        return None


def run_all_tests():
    """Run all tests"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                   LIQUIDITY REVERSAL BACKTEST - TESTS                        ║
║                                                                              ║
║  Testing individual components and full backtest                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)

    # Run tests
    test_liquidity_sweep_detector()
    test_fvg_detector()
    test_volume_analyzer()
    test_reversal_detector()
    test_full_backtest()

    print("\n" + "="*80)
    print("✅ ALL TESTS COMPLETED")
    print("="*80)
    print("\n📝 Next steps:")
    print("   1. Run with real data: python run_liquidity_backtest.py")
    print("   2. Check README: LIQUIDITY_REVERSAL_README.md")
    print("   3. Optimize parameters for your trading style")
    print("\n")


if __name__ == "__main__":
    run_all_tests()
