"""
Script to download data from Binance and run liquidity reversal backtest
"""

import pandas as pd
from binance.client import Client
from datetime import datetime, timedelta
from liquidity_reversal_backtest import LiquidityReversalBacktest
import os


def download_binance_data(symbol: str, interval: str, start_date: str, end_date: str = None) -> pd.DataFrame:
    """
    Download historical data from Binance

    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        interval: Timeframe ('15m', '4h', '1d', etc.)
        start_date: Start date in format 'YYYY-MM-DD'
        end_date: End date in format 'YYYY-MM-DD' (default: today)

    Returns:
        DataFrame with OHLCV data
    """
    print(f"\n📥 Downloading {symbol} {interval} data from Binance...")
    print(f"   Period: {start_date} to {end_date or 'now'}")

    # Initialize Binance client (no API key needed for public data)
    client = Client()

    # Convert dates to timestamps
    start_ts = int(datetime.strptime(start_date, '%Y-%m-%d').timestamp() * 1000)

    if end_date:
        end_ts = int(datetime.strptime(end_date, '%Y-%m-%d').timestamp() * 1000)
    else:
        end_ts = int(datetime.now().timestamp() * 1000)

    # Download data in chunks (Binance has 1000 candle limit per request)
    all_klines = []
    current_ts = start_ts

    while current_ts < end_ts:
        print(f"   Fetching data from {datetime.fromtimestamp(current_ts/1000)}...")

        klines = client.get_klines(
            symbol=symbol,
            interval=interval,
            startTime=current_ts,
            endTime=end_ts,
            limit=1000
        )

        if not klines:
            break

        all_klines.extend(klines)
        current_ts = klines[-1][0] + 1  # Move to next timestamp

    print(f"   ✅ Downloaded {len(all_klines)} candles")

    # Convert to DataFrame
    df = pd.DataFrame(all_klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])

    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)

    # Convert to float
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

    # Keep only OHLCV columns
    df = df[['open', 'high', 'low', 'close', 'volume']]

    return df


def save_data(df: pd.DataFrame, filename: str):
    """Save DataFrame to CSV"""
    os.makedirs('data', exist_ok=True)
    filepath = f'data/{filename}'
    df.to_csv(filepath)
    print(f"   💾 Saved to {filepath}")


def load_data(filename: str) -> pd.DataFrame:
    """Load DataFrame from CSV"""
    filepath = f'data/{filename}'
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    df = pd.read_csv(filepath, parse_dates=['timestamp'], index_col='timestamp')
    return df


def run_backtest_with_download(symbol: str = 'BTCUSDT',
                               start_date: str = '2023-01-01',
                               end_date: str = None,
                               download_fresh: bool = True):
    """
    Main function to download data and run backtest

    Args:
        symbol: Trading pair
        start_date: Start date for backtest
        end_date: End date for backtest (default: today)
        download_fresh: If True, download fresh data. If False, try to use cached data.
    """

    print("\n" + "="*80)
    print("🚀 LIQUIDITY REVERSAL BACKTEST - DATA PREPARATION")
    print("="*80)

    # File names for cached data
    file_4h = f'{symbol}_4h_{start_date}_to_{end_date or "now"}.csv'.replace(':', '_')
    file_15m = f'{symbol}_15m_{start_date}_to_{end_date or "now"}.csv'.replace(':', '_')

    # Try to load cached data or download fresh
    if not download_fresh:
        try:
            print("\n📂 Trying to load cached data...")
            df_4h = load_data(file_4h)
            df_15m = load_data(file_15m)
            print("✅ Loaded cached data successfully")
        except FileNotFoundError:
            print("⚠️  Cached data not found, downloading fresh data...")
            download_fresh = True

    if download_fresh:
        # Download 4H data
        df_4h = download_binance_data(symbol, '4h', start_date, end_date)
        save_data(df_4h, file_4h)

        # Download 15M data
        df_15m = download_binance_data(symbol, '15m', start_date, end_date)
        save_data(df_15m, file_15m)

    # Verify data
    print(f"\n📊 Data Summary:")
    print(f"   4H candles: {len(df_4h)} (from {df_4h.index[0]} to {df_4h.index[-1]})")
    print(f"   15M candles: {len(df_15m)} (from {df_15m.index[0]} to {df_15m.index[-1]})")

    # Initialize backtest
    backtest = LiquidityReversalBacktest(
        initial_balance=10000,  # $10k starting capital
        risk_per_trade=0.02,    # 2% risk per trade
        volume_threshold=1.5,   # 1.5x average volume for entry
        sweep_lookback=20       # Look 20 candles back for swing points
    )

    # Run backtest
    results = backtest.run_backtest(df_4h, df_15m, start_date, end_date)

    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backtest.save_results(results, f'liquidity_reversal_{symbol}_{timestamp}.json')
    backtest.save_trades_csv(f'liquidity_reversal_trades_{symbol}_{timestamp}.csv')

    return results


if __name__ == "__main__":
    import sys

    # Parse command line arguments
    symbol = sys.argv[1] if len(sys.argv) > 1 else 'BTCUSDT'
    start_date = sys.argv[2] if len(sys.argv) > 2 else '2023-01-01'
    end_date = sys.argv[3] if len(sys.argv) > 3 else None

    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║               LIQUIDITY SWEEP REVERSAL - AUTOMATED BACKTEST                  ║
║                                                                              ║
║  This script will:                                                           ║
║  1. Download historical data from Binance (4H and 15M)                       ║
║  2. Run liquidity sweep reversal backtest                                    ║
║  3. Save results and trades to files                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)

    print(f"\n⚙️  Configuration:")
    print(f"   Symbol: {symbol}")
    print(f"   Start Date: {start_date}")
    print(f"   End Date: {end_date or 'now'}")

    try:
        results = run_backtest_with_download(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            download_fresh=True
        )

        print("\n✅ Backtest completed successfully!")
        print("\n📁 Check backtest_results/ folder for detailed results")

    except Exception as e:
        print(f"\n❌ Error running backtest: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
