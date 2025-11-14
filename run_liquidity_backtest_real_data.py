"""
Script to run liquidity reversal backtest using real data from backtest/data
"""

import pandas as pd
import sys
import os
from pathlib import Path
from datetime import datetime
from liquidity_reversal_backtest import LiquidityReversalBacktest

# Add parent directory to path to access backtest/data
project_root = Path(__file__).parent.parent
backtest_data_dir = project_root / 'backtest' / 'data'


def load_csv_data(filename: str) -> pd.DataFrame:
    """
    Load CSV data from backtest/data directory
    
    Args:
        filename: Name of CSV file (e.g., 'btc_4h_data_2018_to_2025.csv')
    
    Returns:
        DataFrame with OHLCV data
    """
    filepath = backtest_data_dir / filename
    
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    
    print(f"\n📂 Loading data from: {filepath}")
    
    # Read CSV - handle different formats
    df = pd.read_csv(filepath)
    
    # Check column names and normalize
    # Files might have 'Open time' or 'timestamp' as first column
    if 'Open time' in df.columns:
        time_col = 'Open time'
        # Rename columns to lowercase
        df = df.rename(columns={
            'Open time': 'timestamp',
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        })
    elif 'timestamp' in df.columns:
        time_col = 'timestamp'
    else:
        # Try first column as timestamp
        time_col = df.columns[0]
        df = df.rename(columns={time_col: 'timestamp'})
    
    # Parse timestamp
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df.set_index('timestamp', inplace=True)
    
    # Ensure we have OHLCV columns (case insensitive)
    required_cols = ['open', 'high', 'low', 'close', 'volume']
    df.columns = df.columns.str.lower()
    
    # Select only OHLCV columns
    df = df[required_cols].copy()
    
    # Convert to float
    for col in required_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Remove any rows with NaN
    df = df.dropna()
    
    # Sort by timestamp
    df = df.sort_index()
    
    print(f"   ✅ Loaded {len(df)} candles")
    print(f"   📅 Period: {df.index[0]} to {df.index[-1]}")
    print(f"   💰 Price range: ${df['low'].min():.2f} - ${df['high'].max():.2f}")
    
    return df


def filter_data_by_date(df: pd.DataFrame, start_date: str = None, end_date: str = None) -> pd.DataFrame:
    """
    Filter DataFrame by date range
    
    Args:
        df: DataFrame with datetime index
        start_date: Start date in format 'YYYY-MM-DD' (optional)
        end_date: End date in format 'YYYY-MM-DD' (optional)
    
    Returns:
        Filtered DataFrame
    """
    if start_date:
        start_dt = pd.to_datetime(start_date)
        df = df[df.index >= start_dt]
        print(f"   📅 Filtered from: {start_dt}")
    
    if end_date:
        end_dt = pd.to_datetime(end_date)
        df = df[df.index <= end_dt]
        print(f"   📅 Filtered to: {end_dt}")
    
    return df


def run_backtest_with_real_data(
    start_date: str = '2023-01-01',
    end_date: str = None,
    initial_balance: float = 10000,
    risk_per_trade: float = 0.02,
    volume_threshold: float = 1.5,
    sweep_lookback: int = 20
):
    """
    Run liquidity reversal backtest with real data from backtest/data
    
    Args:
        start_date: Start date for backtest (YYYY-MM-DD)
        end_date: End date for backtest (YYYY-MM-DD, optional)
        initial_balance: Starting capital
        risk_per_trade: Risk per trade as fraction (0.02 = 2%)
        volume_threshold: Volume threshold multiplier (1.5 = 1.5x average)
        sweep_lookback: Lookback period for liquidity sweeps
    """
    
    print("\n" + "="*80)
    print("🚀 LIQUIDITY REVERSAL BACKTEST - REAL DATA")
    print("="*80)
    
    # Load 4H data
    print("\n📊 Loading 4H data...")
    df_4h = load_csv_data('btc_4h_data_2018_to_2025.csv')
    df_4h = filter_data_by_date(df_4h, start_date, end_date)
    
    # Load 15M data
    print("\n📊 Loading 15M data...")
    df_15m = load_csv_data('btc_15m_data_2018_to_2025.csv')
    df_15m = filter_data_by_date(df_15m, start_date, end_date)
    
    # Verify data overlap
    print("\n📊 Data Summary:")
    print(f"   4H candles: {len(df_4h)} (from {df_4h.index[0]} to {df_4h.index[-1]})")
    print(f"   15M candles: {len(df_15m)} (from {df_15m.index[0]} to {df_15m.index[-1]})")
    
    # Check if we have enough data
    if len(df_4h) < 50:
        print("⚠️  Warning: Not enough 4H data (need at least 50 candles)")
        return None
    
    if len(df_15m) < 100:
        print("⚠️  Warning: Not enough 15M data (need at least 100 candles)")
        return None
    
    # Initialize backtest
    print("\n⚙️  Initializing backtest...")
    backtest = LiquidityReversalBacktest(
        initial_balance=initial_balance,
        risk_per_trade=risk_per_trade,
        volume_threshold=volume_threshold,
        sweep_lookback=sweep_lookback
    )
    
    # Run backtest
    print("\n🚀 Running backtest...")
    try:
        results = backtest.run_backtest(df_4h, df_15m, start_date, end_date)
        
        # Save results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        results_dir = Path(__file__).parent / 'backtest_results'
        results_dir.mkdir(exist_ok=True)
        
        results_file = results_dir / f'liquidity_reversal_real_{timestamp}.json'
        trades_file = results_dir / f'liquidity_reversal_trades_real_{timestamp}.csv'
        
        backtest.save_results(results, str(results_file))
        backtest.save_trades_csv(str(trades_file))
        
        print(f"\n💾 Results saved:")
        print(f"   📄 {results_file}")
        print(f"   📊 {trades_file}")
        
        return results
        
    except Exception as e:
        print(f"\n❌ Error during backtest: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║         LIQUIDITY SWEEP REVERSAL - BACKTEST WITH REAL DATA                   ║
║                                                                              ║
║  This script uses data from backtest/data/ directory                        ║
║  Files: btc_4h_data_2018_to_2025.csv, btc_15m_data_2018_to_2025.csv         ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Parse command line arguments
    start_date = sys.argv[1] if len(sys.argv) > 1 else '2023-01-01'
    end_date = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(f"\n⚙️  Configuration:")
    print(f"   Start Date: {start_date}")
    print(f"   End Date: {end_date or 'end of data'}")
    print(f"   Initial Balance: $10,000")
    print(f"   Risk per Trade: 2.0%")
    print(f"   Volume Threshold: 1.5x")
    
    try:
        results = run_backtest_with_real_data(
            start_date=start_date,
            end_date=end_date,
            initial_balance=10000,
            risk_per_trade=0.02,
            volume_threshold=1.5,
            sweep_lookback=20
        )
        
        if results:
            print("\n✅ Backtest completed successfully!")
            print("\n📁 Check backtest_results/ folder for detailed results")
        else:
            print("\n⚠️  Backtest completed with warnings or errors")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Error running backtest: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

