"""
Failed 4H FVG Strategy - Backtesting Script

Test the strategy on historical data to validate logic
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from failed_fvg_strategy import FVG, FailedFVGStrategy, LimitOrder
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('TestFailedFVG')


def generate_sample_data():
    """Generate sample OHLC data for testing"""

    # Generate 200 4H candles
    dates_4h = pd.date_range(start='2024-01-01', periods=200, freq='4H')

    # BTC price simulation
    np.random.seed(42)
    base_price = 95000

    data_4h = []
    price = base_price

    for date in dates_4h:
        # Random walk
        change = np.random.randn() * 500
        price += change

        open_price = price
        high_price = price + abs(np.random.randn() * 300)
        low_price = price - abs(np.random.randn() * 300)
        close_price = price + np.random.randn() * 200

        data_4h.append({
            'timestamp': date,
            'Open': open_price,
            'High': high_price,
            'Low': low_price,
            'Close': close_price,
            'Volume': np.random.randint(100, 1000)
        })

    df_4h = pd.DataFrame(data_4h)

    # Generate 15M data (more granular)
    dates_15m = pd.date_range(start='2024-01-01', periods=1000, freq='15min')

    data_15m = []
    price = base_price

    for date in dates_15m:
        change = np.random.randn() * 150
        price += change

        open_price = price
        high_price = price + abs(np.random.randn() * 100)
        low_price = price - abs(np.random.randn() * 100)
        close_price = price + np.random.randn() * 80

        data_15m.append({
            'timestamp': date,
            'Open': open_price,
            'High': high_price,
            'Low': low_price,
            'Close': close_price,
            'Volume': np.random.randint(10, 100)
        })

    df_15m = pd.DataFrame(data_15m)

    return df_4h, df_15m


def test_fvg_detection():
    """Test FVG detection logic"""
    logger.info("="*60)
    logger.info("TEST 1: FVG Detection")
    logger.info("="*60)

    # Create sample data with known FVG
    data = [
        {'timestamp': datetime(2024, 1, 1, 0, 0), 'Open': 95000, 'High': 95100, 'Low': 94900, 'Close': 95000, 'Volume': 100},
        {'timestamp': datetime(2024, 1, 1, 4, 0), 'Open': 95000, 'High': 95200, 'Low': 94800, 'Close': 95100, 'Volume': 100},
        # Bullish FVG: Low[2] > High[0]
        {'timestamp': datetime(2024, 1, 1, 8, 0), 'Open': 95500, 'High': 95800, 'Low': 95400, 'Close': 95700, 'Volume': 100},  # Low=95400 > High[0]=95100 -> FVG!
    ]

    df = pd.DataFrame(data)

    strategy = FailedFVGStrategy()
    fvgs = strategy.detect_fvg(df, timeframe='4h')

    logger.info(f"Detected {len(fvgs)} FVG(s)")

    for fvg in fvgs:
        logger.info(f"  {fvg.type} FVG: ${fvg.bottom:.2f} - ${fvg.top:.2f}")

    assert len(fvgs) == 1, "Should detect 1 FVG"
    assert fvgs[0].type == 'BULLISH', "Should be BULLISH FVG"
    assert fvgs[0].bottom == 95100, f"Bottom should be 95100, got {fvgs[0].bottom}"
    assert fvgs[0].top == 95400, f"Top should be 95400, got {fvgs[0].top}"

    logger.info("✅ TEST 1 PASSED\n")


def test_rejection_detection():
    """Test rejection detection"""
    logger.info("="*60)
    logger.info("TEST 2: Rejection Detection")
    logger.info("="*60)

    # Create Bullish FVG
    fvg = FVG(
        fvg_type='BULLISH',
        top=95400,
        bottom=95100,
        formed_time=datetime(2024, 1, 1, 8, 0),
        timeframe='4h',
        index=2
    )

    logger.info(f"Testing rejection for BULLISH FVG: ${fvg.bottom:.2f} - ${fvg.top:.2f}")

    # Candle that enters FVG
    candle1 = pd.Series({
        'timestamp': datetime(2024, 1, 1, 12, 0),
        'Open': 95000,
        'High': 95300,  # Touches FVG
        'Low': 95000,
        'Close': 95200  # Closes inside FVG
    })

    rejected = fvg.check_rejection(candle1)
    assert not rejected, "Should not reject yet (closed inside)"
    assert fvg.entered, "Should mark as entered"
    logger.info(f"  Candle 1: Entered FVG, no rejection (closed inside)")

    # Candle that rejects
    candle2 = pd.Series({
        'timestamp': datetime(2024, 1, 1, 16, 0),
        'Open': 95200,
        'High': 95350,
        'Low': 95000,
        'Close': 95050  # Closes BELOW FVG bottom (95100)
    })

    rejected = fvg.check_rejection(candle2)
    assert rejected, "Should reject (closed below FVG)"
    assert fvg.rejected, "FVG should be marked as rejected"
    logger.info(f"  Candle 2: REJECTED! Closed @ ${candle2['Close']:.2f} (below ${fvg.bottom:.2f})")

    # Check SL
    sl = fvg.get_stop_loss()
    logger.info(f"  Stop Loss: ${sl:.2f}")
    assert sl is not None, "Should have valid SL"
    assert sl > max(fvg.highs_inside), "SL should be above highest high inside"

    logger.info("✅ TEST 2 PASSED\n")


def test_full_strategy():
    """Test full strategy flow"""
    logger.info("="*60)
    logger.info("TEST 3: Full Strategy Flow")
    logger.info("="*60)

    df_4h, df_15m = generate_sample_data()

    strategy = FailedFVGStrategy()

    logger.info(f"Testing with {len(df_4h)} 4H candles and {len(df_15m)} 15M candles")

    # Run strategy
    current_time = datetime.utcnow()

    orders = strategy.check_for_setup(df_4h, df_15m, current_time)

    logger.info(f"Strategy generated {len(orders)} order(s)")

    for i, order in enumerate(orders):
        logger.info(f"\nOrder #{i+1}:")
        logger.info(f"  Type: {order.order_type}")
        logger.info(f"  Entry: ${order.limit_price:.2f}")
        logger.info(f"  SL: ${order.sl:.2f} ({order.sl_pct:.2f}%)")
        logger.info(f"  TP: ${order.tp:.2f}")
        logger.info(f"  RR: {order.rr:.2f}")

        assert order.rr >= strategy.min_rr, f"RR {order.rr} should be >= {strategy.min_rr}"
        assert order.sl_pct >= strategy.min_sl_pct, f"SL% {order.sl_pct} should be >= {strategy.min_sl_pct}"

    logger.info(f"\n✅ TEST 3 PASSED")


def test_invalidation():
    """Test FVG invalidation"""
    logger.info("="*60)
    logger.info("TEST 4: FVG Invalidation")
    logger.info("="*60)

    # Bullish FVG
    fvg = FVG(
        fvg_type='BULLISH',
        top=95400,
        bottom=95100,
        formed_time=datetime(2024, 1, 1, 8, 0),
        timeframe='4h',
        index=2
    )

    logger.info(f"Testing invalidation for BULLISH FVG: ${fvg.bottom:.2f} - ${fvg.top:.2f}")

    # Candle that invalidates (closes below bottom)
    candle = pd.Series({
        'timestamp': datetime(2024, 1, 1, 12, 0),
        'Open': 95200,
        'High': 95300,
        'Low': 95000,  # Went below bottom
        'Close': 95050
    })

    invalidated = fvg.is_fully_passed(candle['High'], candle['Low'])
    logger.info(f"  Candle closed @ ${candle['Close']:.2f}, Low: ${candle['Low']:.2f}")
    logger.info(f"  Invalidated: {invalidated}")

    assert invalidated, "Should be invalidated (low < bottom)"

    logger.info("✅ TEST 4 PASSED\n")


if __name__ == "__main__":
    logger.info("\n" + "="*60)
    logger.info("FAILED 4H FVG STRATEGY - TEST SUITE")
    logger.info("="*60 + "\n")

    try:
        test_fvg_detection()
        test_rejection_detection()
        test_invalidation()
        test_full_strategy()

        logger.info("\n" + "="*60)
        logger.info("ALL TESTS PASSED!")
        logger.info("="*60 + "\n")

    except AssertionError as e:
        logger.error(f"\n❌ TEST FAILED: {e}\n")
        raise
    except Exception as e:
        logger.error(f"\n❌ ERROR: {e}\n", exc_info=True)
        raise
