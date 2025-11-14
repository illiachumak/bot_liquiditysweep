"""
Script to run liquidity reversal backtest on real data from backtest/data
"""

import pandas as pd
import sys
import os
from datetime import datetime
from pathlib import Path

# Add parent directory to path to import liquidity_reversal_backtest
sys.path.append(os.path.dirname(__file__))
from liquidity_reversal_backtest import LiquidityReversalBacktest


def load_data_from_backtest_data(timeframe: str = '4h', 
                                 start_date: str = None,
                                 end_date: str = None) -> pd.DataFrame:
    """
    Load BTC data from backtest/data directory
    
    Args:
        timeframe: '15m', '4h', '1h', '1d'
        start_date: Start date filter (YYYY-MM-DD) or None
        end_date: End date filter (YYYY-MM-DD) or None
    
    Returns:
        DataFrame with OHLCV data, lowercase column names, datetime index
    """
    data_files = {
        '15m': 'backtest/data/btc_15m_data_2018_to_2025.csv',
        '1h': 'backtest/data/btc_1h_data_2018_to_2025.csv',
        '4h': 'backtest/data/btc_4h_data_2018_to_2025.csv',
        '1d': 'backtest/data/btc_1d_data_2018_to_2025.csv',
    }
    
    if timeframe not in data_files:
        raise ValueError(f"Timeframe {timeframe} not supported. Use: 15m, 1h, 4h, 1d")
    
    filepath = data_files[timeframe]
    
    # Get absolute path
    script_dir = Path(__file__).parent.parent
    full_path = script_dir / filepath
    
    if not full_path.exists():
        raise FileNotFoundError(f"Data file not found: {full_path}")
    
    print(f"\n📊 Loading {timeframe} data from {filepath}...")
    
    # Load CSV
    data = pd.read_csv(full_path)
    
    # Filter out rows with missing Open time
    data = data[data['Open time'].notna()]
    
    # Convert Open time to datetime
    data['datetime'] = pd.to_datetime(data['Open time'], errors='coerce')
    data = data[data['datetime'].notna()]
    
    # Set datetime as index
    data.set_index('datetime', inplace=True)
    
    # Select and rename columns to lowercase
    data = data[['Open', 'High', 'Low', 'Close', 'Volume']]
    data.columns = ['open', 'high', 'low', 'close', 'volume']
    
    # Convert to float
    for col in data.columns:
        data[col] = pd.to_numeric(data[col], errors='coerce')
    
    # Remove NaN rows and sort
    data = data.dropna().sort_index()
    
    # Filter by date if specified
    if start_date:
        data = data[data.index >= start_date]
    if end_date:
        data = data[data.index <= end_date]
    
    print(f"   ✅ Loaded {len(data)} candles")
    print(f"   Period: {data.index[0]} to {data.index[-1]}")
    print(f"   Price range: ${data['low'].min():,.2f} - ${data['high'].max():,.2f}")
    
    return data


def run_backtest_real_data(start_date: str = '2023-01-01',
                           end_date: str = '2024-12-31',
                           initial_balance: float = 10000,
                           risk_per_trade: float = 0.02,
                           volume_threshold: float = 1.5,
                           sweep_lookback: int = 20):
    """
    Run liquidity reversal backtest on real data
    
    Args:
        start_date: Start date for backtest (YYYY-MM-DD)
        end_date: End date for backtest (YYYY-MM-DD)
        initial_balance: Starting capital
        risk_per_trade: Risk per trade as fraction (0.02 = 2%)
        volume_threshold: Minimum volume ratio for entry
        sweep_lookback: Lookback period for liquidity sweep detection
    """
    
    import sys
    sys.stdout.flush()
    
    print("\n" + "="*80)
    print("🚀 LIQUIDITY REVERSAL BACKTEST - REAL DATA")
    print("="*80)
    sys.stdout.flush()
    
    print(f"\n⚙️  Configuration:")
    print(f"   Period: {start_date} to {end_date}")
    print(f"   Initial Balance: ${initial_balance:,.2f}")
    print(f"   Risk per Trade: {risk_per_trade*100}%")
    print(f"   Volume Threshold: {volume_threshold}x")
    print(f"   Sweep Lookback: {sweep_lookback} candles")
    sys.stdout.flush()
    
    # Load 4H data
    print("\n" + "-"*80)
    sys.stdout.flush()
    df_4h = load_data_from_backtest_data('4h', start_date, end_date)
    sys.stdout.flush()
    
    # Load 15M data
    print("\n" + "-"*80)
    sys.stdout.flush()
    df_15m = load_data_from_backtest_data('15m', start_date, end_date)
    sys.stdout.flush()
    
    # Verify data overlap
    if df_4h.index[0] > df_15m.index[-1] or df_4h.index[-1] < df_15m.index[0]:
        raise ValueError("4H and 15M data periods don't overlap!")
    
    # Initialize backtest
    print("\n" + "-"*80)
    print("🔧 Initializing backtest engine...")
    backtest = LiquidityReversalBacktest(
        initial_balance=initial_balance,
        risk_per_trade=risk_per_trade,
        volume_threshold=volume_threshold,
        sweep_lookback=sweep_lookback,
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
    
    # Create results directory
    results_dir = Path(__file__).parent / 'backtest_results'
    results_dir.mkdir(exist_ok=True)
    
    backtest.save_results(results, f'liquidity_reversal_real_{timestamp}.json')
    backtest.save_trades_csv(f'liquidity_reversal_trades_real_{timestamp}.csv')
    
    print("\n" + "="*80)
    print("✅ BACKTEST COMPLETED!")
    print("="*80)
    print(f"\n📁 Results saved to: {results_dir}")
    print(f"   - JSON: liquidity_reversal_real_{timestamp}.json")
    print(f"   - CSV: liquidity_reversal_trades_real_{timestamp}.csv")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Run liquidity reversal backtest on real data')
    parser.add_argument('--start-date', type=str, default='2023-01-01',
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default='2024-12-31',
                       help='End date (YYYY-MM-DD)')
    parser.add_argument('--balance', type=float, default=10000,
                       help='Initial balance (default: 10000)')
    parser.add_argument('--risk', type=float, default=0.02,
                       help='Risk per trade as fraction (default: 0.02 = 2%%)')
    parser.add_argument('--volume-threshold', type=float, default=1.5,
                       help='Volume threshold multiplier (default: 1.5)')
    parser.add_argument('--sweep-lookback', type=int, default=20,
                       help='Sweep lookback period (default: 20)')
    
    args = parser.parse_args()
    
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║          LIQUIDITY SWEEP REVERSAL BACKTEST - REAL DATA                        ║
║                                                                              ║
║  Strategy: Reversal after 4H liquidity sweep with 15M volume + FVG entry     ║
║  Data: Real BTC data from backtest/data/                                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        results = run_backtest_real_data(
            start_date=args.start_date,
            end_date=args.end_date,
            initial_balance=args.balance,
            risk_per_trade=args.risk,
            volume_threshold=args.volume_threshold,
            sweep_lookback=args.sweep_lookback
        )
        
        print("\n🎉 Success!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
