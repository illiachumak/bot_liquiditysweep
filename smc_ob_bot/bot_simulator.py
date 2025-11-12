"""
Bot Simulator for SMC Order Block Strategy

Simulates bot behavior on historical data to verify:
- Signal detection matches backtest
- Entry/exit logic works correctly
- Performance is realistic
"""

import pandas as pd
import numpy as np
from datetime import datetime
from smc_ob_bot import SMCOrderBlockBot, Config, load_binance_data
from typing import List, Dict


def load_historical_data(start_year: int = 2024) -> pd.DataFrame:
    """Load historical data for simulation"""
    data_path = '../../backtest/data/btc_15m_data_2018_to_2025.csv'
    
    print(f"📊 Loading historical data from {data_path}...")
    
    data = pd.read_csv(data_path)
    data = data[data['Open time'].notna()]
    data['datetime'] = pd.to_datetime(data['Open time'], errors='coerce')
    data = data[data['datetime'].notna()]
    data.set_index('datetime', inplace=True)
    data = data[['Open', 'High', 'Low', 'Close', 'Volume']]
    
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        data[col] = data[col].astype(float)
    
    data = data.dropna().sort_index()
    data = data[data.index >= f'{start_year}-01-01']
    
    print(f"✅ Loaded {len(data)} candles")
    print(f"   Period: {data.index[0]} to {data.index[-1]}")
    
    return data


def simulate_bot(data: pd.DataFrame, initial_capital: float = 10000, 
                risk_per_trade: float = 0.03, verbose: bool = True) -> Dict:
    """
    Simulate bot on historical data
    
    Args:
        data: Historical OHLCV data
        initial_capital: Starting capital
        risk_per_trade: Risk percentage per trade
        verbose: Print trade details
    
    Returns:
        Dict with simulation results
    """
    
    print("\n" + "="*80)
    print("🎮 STARTING BOT SIMULATION")
    print("="*80)
    print(f"\nPeriod: {data.index[0]} to {data.index[-1]}")
    print(f"Candles: {len(data)}")
    print(f"Initial Capital: ${initial_capital:,.2f}")
    print(f"Risk per Trade: {risk_per_trade*100}%")
    print("\nStrategy: Pure Order Block (97.56% WR version)")
    print("  - swing_length: 10")
    print("  - min_rr: 2.0")
    print("  - ob_lookback: 15")
    print("  - ob_proximity: 1%")
    print("  - NY session only (13-20 UTC)")
    
    # Update config
    config = Config()
    config.INITIAL_CAPITAL = initial_capital
    config.RISK_PER_TRADE = risk_per_trade
    
    # Initialize bot
    bot = SMCOrderBlockBot(config, paper_trading=True)
    
    # Simulation loop
    lookback = config.LOOKBACK_CANDLES
    
    print(f"\n{'='*80}")
    print("🔄 SIMULATING...")
    print(f"{'='*80}\n")
    
    for i in range(lookback, len(data)):
        # Get current window
        window = data.iloc[i-lookback:i+1]
        current_time = data.index[i]
        current_candle = data.iloc[i]
        
        # Periodically cleanup old OBs (every 100 candles)
        if i % 100 == 0:
            bot.strategy.cleanup_old_obs()
        
        # Check for exit first
        if bot.position:
            # Check if hit TP or SL during this candle
            high = current_candle['High']
            low = current_candle['Low']
            close = current_candle['Close']
            
            if bot.position.type == 'LONG':
                if high >= bot.position.tp:
                    bot.close_position(bot.position.tp, current_time)
                elif low <= bot.position.sl:
                    bot.close_position(bot.position.sl, current_time)
            else:  # SHORT
                if low <= bot.position.tp:
                    bot.close_position(bot.position.tp, current_time)
                elif high >= bot.position.sl:
                    bot.close_position(bot.position.sl, current_time)
        
        # Check for new signal
        if not bot.position:
            signal = bot.strategy.check_signal(window, current_time)
            
            if signal:
                if verbose:
                    bot.open_position(signal, current_time)
                else:
                    # Silent mode
                    size = bot.calculate_position_size(signal)
                    from smc_ob_bot import Position
                    bot.position = Position(signal, size, current_time)
    
    # Close any remaining position
    if bot.position:
        final_price = data['Close'].iloc[-1]
        final_time = data.index[-1]
        bot.position.close(final_price, final_time, 'CLOSE')
        bot.capital += bot.position.pnl
        bot.trades.append(bot.position)
        
        if verbose:
            print(f"\n⚠️  FORCE CLOSE at end of simulation")
            print(f"   Exit: ${final_price:.2f}")
            print(f"   PnL: ${bot.position.pnl:.2f}")
    
    # Calculate statistics
    stats = bot.get_statistics()
    
    return {
        'bot': bot,
        'stats': stats,
        'trades': bot.trades
    }


def print_results(results: Dict):
    """Print simulation results"""
    
    stats = results['stats']
    trades = results['trades']
    
    print("\n" + "="*80)
    print("📊 SIMULATION RESULTS")
    print("="*80)
    
    if not stats:
        print("\n❌ No trades executed")
        return
    
    print(f"\n{'='*80}")
    print("PERFORMANCE SUMMARY")
    print(f"{'='*80}")
    
    print(f"\nTotal Trades:     {stats['total_trades']}")
    print(f"Wins:             {stats['wins']}")
    print(f"Losses:           {stats['losses']}")
    print(f"Win Rate:         {stats['win_rate']:.2f}%")
    
    print(f"\nInitial Capital:  ${stats['final_capital'] / (1 + stats['total_return']/100):,.2f}")
    print(f"Final Capital:    ${stats['final_capital']:,.2f}")
    print(f"Total PnL:        ${stats['total_pnl']:,.2f}")
    print(f"Total Return:     {stats['total_return']:+.2f}%")
    
    print(f"\nAverage Win:      ${stats['avg_win']:,.2f}")
    print(f"Average Loss:     ${stats['avg_loss']:,.2f}")
    print(f"Profit Factor:    {stats['profit_factor']:.2f}")
    print(f"Max Drawdown:     {stats['max_drawdown']:.2f}%")
    
    # Calculate additional metrics
    if len(trades) > 0:
        first_trade = trades[0].entry_time
        last_trade = trades[-1].exit_time if trades[-1].exit_time else trades[-1].entry_time
        days = (last_trade - first_trade).days
        months = days / 30.44
        
        monthly_return = stats['total_return'] / months if months > 0 else 0
        trades_per_month = len(trades) / months if months > 0 else 0
        
        print(f"\nTrading Period:   {days} days ({months:.1f} months)")
        print(f"Monthly Return:   {monthly_return:.2f}%")
        print(f"Trades/Month:     {trades_per_month:.1f}")
    
    # Trade breakdown
    print(f"\n{'='*80}")
    print("TRADE BREAKDOWN")
    print(f"{'='*80}\n")
    
    for i, trade in enumerate(trades[:10], 1):  # Show first 10
        result_emoji = "✅" if trade.result == 'TP' else "❌"
        print(f"{result_emoji} Trade #{i} - {trade.type}")
        print(f"   Entry: {trade.entry_time} @ ${trade.entry:.2f}")
        print(f"   Exit:  {trade.exit_time} @ ${trade.exit_price:.2f}")
        print(f"   PnL:   ${trade.pnl:,.2f} ({trade.pnl_pct:+.2f}%)")
        print()
    
    if len(trades) > 10:
        print(f"... and {len(trades)-10} more trades")


def compare_with_backtest():
    """Compare simulation with backtest results"""
    
    print("\n" + "="*80)
    print("📊 COMPARISON: Simulation vs Backtest")
    print("="*80)
    
    # Backtest results (from smc_strategies_backtest.py)
    backtest = {
        'monthly_return': 2.91,
        'win_rate': 97.56,
        'trades_per_month': 1.8,
        'max_dd': -2.51,
        'sharpe': 3.39,
        'total_trades': 41
    }
    
    # Run simulation
    data = load_historical_data(2024)
    results = simulate_bot(data, initial_capital=10000, risk_per_trade=0.03, verbose=False)
    
    if not results['stats']:
        print("\n❌ No simulation data")
        return
    
    stats = results['stats']
    
    # Calculate simulation metrics
    first_trade = results['trades'][0].entry_time
    last_trade = results['trades'][-1].exit_time if results['trades'][-1].exit_time else results['trades'][-1].entry_time
    months = (last_trade - first_trade).days / 30.44
    
    sim_monthly = stats['total_return'] / months if months > 0 else 0
    sim_trades_per_month = stats['total_trades'] / months if months > 0 else 0
    
    print(f"\n{'Metric':<25} {'Backtest':<15} {'Simulation':<15} {'Diff'}")
    print("-" * 70)
    print(f"{'Monthly Return %':<25} {backtest['monthly_return']:<15.2f} {sim_monthly:<15.2f} {sim_monthly - backtest['monthly_return']:+.2f}")
    print(f"{'Win Rate %':<25} {backtest['win_rate']:<15.2f} {stats['win_rate']:<15.2f} {stats['win_rate'] - backtest['win_rate']:+.2f}")
    print(f"{'Trades/Month':<25} {backtest['trades_per_month']:<15.1f} {sim_trades_per_month:<15.1f} {sim_trades_per_month - backtest['trades_per_month']:+.1f}")
    print(f"{'Max DD %':<25} {backtest['max_dd']:<15.2f} {stats['max_drawdown']:<15.2f} {stats['max_drawdown'] - backtest['max_dd']:+.2f}")
    
    # Analysis
    print(f"\n{'='*80}")
    print("ANALYSIS")
    print(f"{'='*80}\n")
    
    monthly_diff_pct = ((sim_monthly / backtest['monthly_return']) - 1) * 100
    
    if abs(monthly_diff_pct) < 20:
        print(f"✅ EXCELLENT: Simulation matches backtest within 20%")
        print(f"   Monthly return difference: {monthly_diff_pct:+.1f}%")
    elif abs(monthly_diff_pct) < 40:
        print(f"⚠️  ACCEPTABLE: Simulation differs by {monthly_diff_pct:+.1f}%")
        print(f"   Expected due to position sizing and execution")
    else:
        print(f"❌ WARNING: Large difference ({monthly_diff_pct:+.1f}%)")
        print(f"   Check implementation vs backtest logic")
    
    if abs(stats['win_rate'] - backtest['win_rate']) < 5:
        print(f"✅ Win Rate matches closely ({stats['win_rate']:.1f}% vs {backtest['win_rate']:.1f}%)")
    else:
        print(f"⚠️  Win Rate differs: {stats['win_rate']:.1f}% vs {backtest['win_rate']:.1f}%")
    
    print(f"\n{'='*80}\n")


def main():
    """Main simulation"""
    
    print("\n" + "="*80)
    print("🎮 SMC ORDER BLOCK BOT - SIMULATION")
    print("="*80)
    
    # Load data
    data = load_historical_data(2024)
    
    # Run simulation
    results = simulate_bot(data, initial_capital=10000, risk_per_trade=0.03, verbose=True)
    
    # Print results
    print_results(results)
    
    # Compare with backtest
    print("\n\n")
    compare_with_backtest()


if __name__ == "__main__":
    main()

