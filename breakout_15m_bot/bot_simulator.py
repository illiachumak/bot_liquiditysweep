"""
Bot Simulator - Verify bot logic matches backtest
Runs bot simulation on historical data and compares with backtest results
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import List, Dict, Optional
import sys
sys.path.append('../../backtest')

# Try to import talib
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False


def calculate_atr_pandas(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate ATR using pandas"""
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr


class BotSimulator:
    """Simulates bot behavior on historical data"""
    
    def __init__(self, data: pd.DataFrame, initial_balance: float = 10000.0):
        """
        Initialize simulator
        
        Args:
            data: Historical OHLCV data
            initial_balance: Starting balance
        """
        self.data = data.copy()
        self.initial_balance = initial_balance
        self.balance = initial_balance
        
        # Bot parameters (matching backtest)
        self.lookback = 24  # 6 hours on 15m
        self.min_rr = 2.0
        self.atr_period = 14
        self.ny_hours = [13, 14, 15, 16, 17, 18, 19, 20]
        self.risk_per_trade = 0.02
        
        # State
        self.position = None
        self.trades = []
        
        print("🤖 Bot Simulator initialized")
        print(f"   Data: {len(data)} candles from {data.index[0]} to {data.index[-1]}")
        print(f"   Initial balance: ${initial_balance:,.0f}")
    
    def calculate_atr(self, candles: pd.DataFrame) -> Optional[float]:
        """Calculate ATR"""
        if len(candles) < self.atr_period:
            return None
        
        if TALIB_AVAILABLE:
            atr = talib.ATR(candles['high'].values, candles['low'].values,
                           candles['close'].values, self.atr_period)
            return atr[-1] if len(atr) > 0 and not np.isnan(atr[-1]) else None
        else:
            atr = calculate_atr_pandas(candles['high'], candles['low'],
                                      candles['close'], self.atr_period)
            return atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else None
    
    def is_ny_session(self, timestamp) -> bool:
        """Check if in NY session"""
        hour = timestamp.hour
        return hour in self.ny_hours
    
    def find_swing_levels(self, idx: int) -> tuple:
        """Find swing high/low"""
        if idx < self.lookback:
            return None, None
        
        lookback_data = self.data.iloc[idx-self.lookback:idx]
        swing_high = lookback_data['high'].max()
        swing_low = lookback_data['low'].min()
        
        return swing_high, swing_low
    
    def check_signal(self, idx: int) -> Optional[Dict]:
        """Check for signal at given index"""
        timestamp = self.data.index[idx]
        
        # Time filter
        if not self.is_ny_session(timestamp):
            return None
        
        # Need enough history
        if idx < self.lookback + self.atr_period:
            return None
        
        current_price = self.data['close'].iloc[idx]
        
        # Find swing levels
        swing_high, swing_low = self.find_swing_levels(idx)
        if swing_high is None:
            return None
        
        # Calculate ATR
        atr = self.calculate_atr(self.data.iloc[:idx+1].tail(50))
        if atr is None:
            return None
        
        # LONG breakout
        if current_price > swing_high:
            entry = current_price
            sl = swing_low
            risk = entry - sl
            tp = entry + (risk * self.min_rr)
            
            if risk > 0 and risk / entry < 0.1:
                return {
                    'side': 'LONG',
                    'entry': entry,
                    'sl': sl,
                    'tp': tp,
                    'timestamp': timestamp,
                    'risk': risk,
                    'reward': tp - entry
                }
        
        # SHORT breakout
        elif current_price < swing_low:
            entry = current_price
            sl = swing_high
            risk = sl - entry
            tp = entry - (risk * self.min_rr)
            
            if risk > 0 and tp > 0 and risk / entry < 0.1:
                return {
                    'side': 'SHORT',
                    'entry': entry,
                    'sl': sl,
                    'tp': tp,
                    'timestamp': timestamp,
                    'risk': risk,
                    'reward': entry - tp
                }
        
        return None
    
    def calculate_position_size(self, entry: float, sl: float) -> float:
        """Calculate position size"""
        risk_amount = self.balance * self.risk_per_trade
        risk_per_unit = abs(entry - sl)
        
        if risk_per_unit > 0:
            return risk_amount / risk_per_unit
        return 0.0
    
    def check_exit(self, idx: int) -> bool:
        """Check if position should exit"""
        if not self.position:
            return False
        
        current_price = self.data['close'].iloc[idx]
        side = self.position['side']
        sl = self.position['sl']
        tp = self.position['tp']
        
        if side == 'LONG':
            return current_price <= sl or current_price >= tp
        else:
            return current_price >= sl or current_price <= tp
    
    def close_position(self, idx: int):
        """Close position"""
        if not self.position:
            return
        
        exit_price = self.data['close'].iloc[idx]
        exit_time = self.data.index[idx]
        
        side = self.position['side']
        entry = self.position['entry']
        size = self.position['size']
        
        if side == 'LONG':
            pnl = (exit_price - entry) * size
            hit_tp = exit_price >= self.position['tp']
        else:
            pnl = (entry - exit_price) * size
            hit_tp = exit_price <= self.position['tp']
        
        self.balance += pnl
        
        trade = {
            'side': side,
            'entry_time': self.position['entry_time'],
            'exit_time': exit_time,
            'entry': entry,
            'exit': exit_price,
            'sl': self.position['sl'],
            'tp': self.position['tp'],
            'size': size,
            'pnl': pnl,
            'hit_tp': hit_tp,
            'balance': self.balance
        }
        
        self.trades.append(trade)
        self.position = None
    
    def open_position(self, signal: Dict):
        """Open position"""
        size = self.calculate_position_size(signal['entry'], signal['sl'])
        
        if size > 0:
            self.position = {
                'side': signal['side'],
                'entry': signal['entry'],
                'sl': signal['sl'],
                'tp': signal['tp'],
                'size': size,
                'entry_time': signal['timestamp']
            }
    
    def run(self):
        """Run simulation"""
        print("\n🚀 Running simulation...")
        
        # Track equity curve for DD calculation
        equity_curve = [self.initial_balance]
        peak = self.initial_balance
        max_dd = 0
        max_dd_pct = 0
        
        for idx in range(len(self.data)):
            # Check exit first
            if self.position:
                if self.check_exit(idx):
                    self.close_position(idx)
                    equity_curve.append(self.balance)
                    
                    # Update drawdown
                    if self.balance > peak:
                        peak = self.balance
                    dd = peak - self.balance
                    dd_pct = (dd / peak) * 100 if peak > 0 else 0
                    if dd_pct > max_dd_pct:
                        max_dd_pct = dd_pct
                        max_dd = dd
            
            # Check for new signal
            if not self.position:
                signal = self.check_signal(idx)
                if signal:
                    self.open_position(signal)
        
        # Close any open position at end
        if self.position:
            self.close_position(len(self.data) - 1)
            equity_curve.append(self.balance)
        
        # Store for analysis
        self.equity_curve = equity_curve
        self.max_dd = max_dd
        self.max_dd_pct = max_dd_pct
        
        print("✅ Simulation complete")
        print(f"\n📊 Results:")
        print(f"   Total trades: {len(self.trades)}")
        print(f"   Final balance: ${self.balance:,.2f}")
        print(f"   Total PnL: ${self.balance - self.initial_balance:,.2f}")
        print(f"   Max Drawdown: ${max_dd:,.2f} ({max_dd_pct:.2f}%)")
        
        if len(self.trades) > 0:
            wins = sum(1 for t in self.trades if t['pnl'] > 0)
            wr = wins / len(self.trades) * 100
            print(f"   Win rate: {wr:.2f}%")
            print(f"   Wins: {wins}, Losses: {len(self.trades) - wins}")
    
    def get_trades_df(self) -> pd.DataFrame:
        """Get trades as DataFrame"""
        if not self.trades:
            return pd.DataFrame()
        
        return pd.DataFrame(self.trades)


def load_backtest_data(start_year: int = 2024):
    """Load data for backtesting"""
    data_path = '../../backtest/data/btc_15m_data_2018_to_2025.csv'
    
    data = pd.read_csv(data_path)
    data = data[data['Open time'].notna()]
    data['datetime'] = pd.to_datetime(data['Open time'], errors='coerce')
    data = data[data['datetime'].notna()]
    data.set_index('datetime', inplace=True)
    data = data[['Open', 'High', 'Low', 'Close', 'Volume']]
    data.columns = ['open', 'high', 'low', 'close', 'volume']
    
    for col in ['open', 'high', 'low', 'close', 'volume']:
        data[col] = data[col].astype(float)
    
    data = data.dropna().sort_index()
    data = data[data.index >= f'{start_year}-01-01']
    
    return data


def compare_with_backtest():
    """Compare bot simulation with backtest results"""
    print("\n" + "="*80)
    print("🔍 COMPARING BOT SIMULATION WITH BACKTEST")
    print("="*80)
    
    # Load data
    print("\n📥 Loading data...")
    data = load_backtest_data(2024)
    
    print(f"   Loaded {len(data)} candles")
    print(f"   From: {data.index[0]}")
    print(f"   To: {data.index[-1]}")
    
    # Run bot simulation
    simulator = BotSimulator(data, initial_balance=100000)
    simulator.run()
    
    # Get trades
    bot_trades = simulator.get_trades_df()
    
    if bot_trades.empty:
        print("\n❌ No trades executed by bot")
        return
    
    # Analyze
    print("\n" + "="*80)
    print("📊 BOT SIMULATION RESULTS")
    print("="*80)
    
    total_days = (data.index[-1] - data.index[0]).days
    total_months = total_days / 30.44
    
    total_pnl = simulator.balance - simulator.initial_balance
    total_pnl_pct = (total_pnl / simulator.initial_balance) * 100
    monthly_pnl_pct = total_pnl_pct / total_months
    
    wins = bot_trades[bot_trades['pnl'] > 0]
    losses = bot_trades[bot_trades['pnl'] <= 0]
    
    print(f"\n💰 Performance:")
    print(f"   Total PnL: ${total_pnl:,.2f} ({total_pnl_pct:+.2f}%)")
    print(f"   Monthly: {monthly_pnl_pct:+.2f}%")
    print(f"   Trades: {len(bot_trades)}")
    print(f"   Trades/month: {len(bot_trades) / total_months:.1f}")
    print(f"   Win Rate: {len(wins) / len(bot_trades) * 100:.2f}%")
    print(f"   Wins: {len(wins)}, Losses: {len(losses)}")
    
    if len(wins) > 0:
        print(f"   Avg Win: ${wins['pnl'].mean():,.2f}")
    if len(losses) > 0:
        print(f"   Avg Loss: ${losses['pnl'].mean():,.2f}")
    
    # Expected from backtest
    print("\n📊 Expected (from backtest - NY Session):")
    print(f"   Monthly: +6.70% (net after commission)")
    print(f"   Gross Monthly: +7.99%")
    print(f"   Win Rate: 40.25%")
    print(f"   Trades/month: 10.7")
    
    # Compare
    print("\n🔍 Comparison:")
    expected_monthly = 7.99  # Gross (before commission)
    diff = monthly_pnl_pct - expected_monthly
    diff_pct = (diff / expected_monthly) * 100 if expected_monthly != 0 else 0
    
    print(f"   Monthly: {monthly_pnl_pct:.2f}% vs {expected_monthly:.2f}% = {diff:+.2f}% ({diff_pct:+.1f}%)")
    
    expected_trades_per_month = 10.7
    actual_trades_per_month = len(bot_trades) / total_months
    trades_diff = actual_trades_per_month - expected_trades_per_month
    
    print(f"   Trades/month: {actual_trades_per_month:.1f} vs {expected_trades_per_month:.1f} = {trades_diff:+.1f}")
    
    expected_wr = 40.25
    actual_wr = len(wins) / len(bot_trades) * 100
    wr_diff = actual_wr - expected_wr
    
    print(f"   Win Rate: {actual_wr:.2f}% vs {expected_wr:.2f}% = {wr_diff:+.2f}%")
    
    # Verdict
    print("\n" + "="*80)
    print("✅ VERDICT")
    print("="*80)
    
    if abs(diff_pct) < 10:
        print("✅ MATCH! Bot simulation closely matches backtest results (<10% difference)")
    elif abs(diff_pct) < 20:
        print("⚠️  CLOSE. Bot simulation reasonably matches backtest (10-20% difference)")
    else:
        print("❌ MISMATCH. Bot simulation differs significantly from backtest (>20%)")
    
    print(f"\n💡 Difference: {diff_pct:+.1f}%")
    
    if diff_pct > 0:
        print("   Bot performed BETTER than backtest (possible reasons: different entry timing)")
    else:
        print("   Bot performed WORSE than backtest (possible reasons: execution differences)")
    
    # Sample trades
    print("\n" + "="*80)
    print("📋 SAMPLE TRADES (first 10)")
    print("="*80)
    
    sample = bot_trades.head(10)[['side', 'entry_time', 'entry', 'exit', 'pnl', 'hit_tp']]
    print(sample.to_string(index=False))
    
    return simulator, bot_trades


if __name__ == "__main__":
    simulator, trades = compare_with_backtest()

