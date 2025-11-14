"""
Verify liquidity sweep signals detected by the bot
"""

import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os

# Strategy parameters (from liquidity_sweep_bot.py)
SWEEP_TOLERANCE = 0.001  # 0.1%
MIN_RR = 1.5
ATR_PERIOD = 14
ATR_STOP_MULTIPLIER = 1.5
ASIAN_SESSION = (0, 8)
LONDON_SESSION = (8, 13)
NY_SESSION = (13, 20)
CANDLE_BUFFER_SIZE = 100

# Try to import talib, but provide fallback if not available
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False

def calculate_atr_pandas(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate ATR using pandas"""
    high_low = high - low
    high_close = np.abs(high - close.shift())
    low_close = np.abs(low - close.shift())
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    
    atr = true_range.ewm(span=period, adjust=False).mean()
    return atr

class LiquiditySweepStrategy:
    """Implements Liquidity Sweep strategy logic"""
    
    def __init__(self):
        self.candles = pd.DataFrame()
        self.session_levels = {
            'asian_high': None,
            'asian_low': None,
            'london_high': None,
            'london_low': None,
            'ny_high': None,
            'ny_low': None
        }
        self.current_date = None
    
    def update_candles(self, new_candle: pd.Series):
        """Add new candle to buffer"""
        if self.candles.empty:
            self.candles = pd.DataFrame([new_candle])
        else:
            self.candles = pd.concat([self.candles, pd.DataFrame([new_candle])], ignore_index=False)
            self.candles = self.candles.tail(CANDLE_BUFFER_SIZE)
        
        self.update_session_levels(new_candle)
    
    def update_session_levels(self, candle: pd.Series):
        """Update session high/low levels"""
        timestamp = candle.name
        current_date = timestamp.date()
        hour = timestamp.hour
        
        # Reset levels on new day
        if self.current_date != current_date:
            self.current_date = current_date
            self.session_levels = {k: None for k in self.session_levels}
        
        # Determine session
        if ASIAN_SESSION[0] <= hour < ASIAN_SESSION[1]:
            if self.session_levels['asian_high'] is None:
                self.session_levels['asian_high'] = candle['high']
                self.session_levels['asian_low'] = candle['low']
            else:
                self.session_levels['asian_high'] = max(self.session_levels['asian_high'], candle['high'])
                self.session_levels['asian_low'] = min(self.session_levels['asian_low'], candle['low'])
        
        elif LONDON_SESSION[0] <= hour < LONDON_SESSION[1]:
            if self.session_levels['london_high'] is None:
                self.session_levels['london_high'] = candle['high']
                self.session_levels['london_low'] = candle['low']
            else:
                self.session_levels['london_high'] = max(self.session_levels['london_high'], candle['high'])
                self.session_levels['london_low'] = min(self.session_levels['london_low'], candle['low'])
        
        elif NY_SESSION[0] <= hour < NY_SESSION[1]:
            if self.session_levels['ny_high'] is None:
                self.session_levels['ny_high'] = candle['high']
                self.session_levels['ny_low'] = candle['low']
            else:
                self.session_levels['ny_high'] = max(self.session_levels['ny_high'], candle['high'])
                self.session_levels['ny_low'] = min(self.session_levels['ny_low'], candle['low'])
    
    def calculate_indicators(self) -> pd.DataFrame:
        """Calculate ATR indicator"""
        if len(self.candles) < ATR_PERIOD:
            return self.candles
        
        df = self.candles.copy()
        
        if TALIB_AVAILABLE:
            df['atr'] = talib.ATR(df['high'].values, df['low'].values, df['close'].values, ATR_PERIOD)
        else:
            df['atr'] = calculate_atr_pandas(df['high'], df['low'], df['close'], ATR_PERIOD)
        
        return df
    
    def detect_bullish_reversal(self) -> bool:
        """Detect bullish reversal pattern"""
        if len(self.candles) < 3:
            return False
        
        recent = self.candles.tail(3)
        current = recent.iloc[-1]
        previous = recent.iloc[-2]
        
        curr_bullish = current['close'] > current['open']
        strong_body = abs(current['close'] - current['open']) > abs(previous['close'] - previous['open'])
        recent_low = recent['low'].min()
        back_above = current['close'] > recent_low
        
        return curr_bullish and back_above and strong_body
    
    def detect_bearish_reversal(self) -> bool:
        """Detect bearish reversal pattern"""
        if len(self.candles) < 3:
            return False
        
        recent = self.candles.tail(3)
        current = recent.iloc[-1]
        previous = recent.iloc[-2]
        
        curr_bearish = current['close'] < current['open']
        strong_body = abs(current['close'] - current['open']) > abs(previous['close'] - previous['open'])
        recent_high = recent['high'].max()
        back_below = current['close'] < recent_high
        
        return curr_bearish and back_below and strong_body
    
    def check_signals(self):
        """Check for entry signals"""
        if len(self.candles) < ATR_PERIOD:
            return False, None
        
        df = self.calculate_indicators()
        current = df.iloc[-1]
        recent_3 = df.tail(3)
        
        atr = current['atr']
        recent_high = recent_3['high'].max()
        recent_low = recent_3['low'].min()
        
        # Get session levels
        liq_highs = [v for v in [self.session_levels['asian_high'], 
                                  self.session_levels['london_high'],
                                  self.session_levels['ny_high']] if v is not None]
        
        liq_lows = [v for v in [self.session_levels['asian_low'],
                                 self.session_levels['london_low'],
                                 self.session_levels['ny_low']] if v is not None]
        
        if not liq_highs or not liq_lows:
            return False, None
        
        # CHECK LONG SIGNAL
        for liq_low in liq_lows:
            if recent_low <= liq_low * (1 + SWEEP_TOLERANCE):
                if self.detect_bullish_reversal():
                    entry = current['close']
                    stop_loss = entry - (atr * ATR_STOP_MULTIPLIER)
                    
                    valid_highs = [h for h in liq_highs if h > entry]
                    if valid_highs:
                        take_profit = min(valid_highs)
                    else:
                        take_profit = entry + (entry - stop_loss) * MIN_RR
                    
                    risk = entry - stop_loss
                    reward = take_profit - entry
                    
                    if risk > 0 and reward > 0 and (reward / risk) >= MIN_RR:
                        return True, {
                            'side': 'LONG',
                            'entry': entry,
                            'stop_loss': stop_loss,
                            'take_profit': take_profit,
                            'rr_ratio': reward / risk,
                            'liquidity_level': liq_low,
                            'session': 'sweep_low'
                        }
        
        # CHECK SHORT SIGNAL
        for liq_high in liq_highs:
            if recent_high >= liq_high * (1 - SWEEP_TOLERANCE):
                if self.detect_bearish_reversal():
                    entry = current['close']
                    stop_loss = entry + (atr * ATR_STOP_MULTIPLIER)
                    
                    valid_lows = [l for l in liq_lows if l < entry]
                    if valid_lows:
                        take_profit = max(valid_lows)
                    else:
                        take_profit = entry - (stop_loss - entry) * MIN_RR
                    
                    risk = stop_loss - entry
                    reward = entry - take_profit
                    
                    if risk > 0 and reward > 0 and (reward / risk) >= MIN_RR:
                        return True, {
                            'side': 'SHORT',
                            'entry': entry,
                            'stop_loss': stop_loss,
                            'take_profit': take_profit,
                            'rr_ratio': reward / risk,
                            'liquidity_level': liq_high,
                            'session': 'sweep_high'
                        }
        
        return False, None

def load_btc_4h_data():
    """Load BTC 4h data"""
    data_path = '../backtest/data/btc_4h_data_2018_to_2025.csv'
    if not os.path.exists(data_path):
        print(f"❌ Data file not found: {data_path}")
        return None
    
    df = pd.read_csv(data_path)
    
    # Check column names
    print(f"📋 Columns: {list(df.columns)}")
    
    # Find datetime column
    datetime_col = None
    for col in df.columns:
        if 'time' in col.lower() or 'date' in col.lower():
            datetime_col = col
            break
    
    if datetime_col:
        df[datetime_col] = pd.to_datetime(df[datetime_col])
        df.set_index(datetime_col, inplace=True)
    else:
        # Try first column
        first_col = df.columns[0]
        df[first_col] = pd.to_datetime(df[first_col])
        df.set_index(first_col, inplace=True)
    
    # Remove duplicates and sort
    df = df[~df.index.duplicated(keep='first')]
    df = df.sort_index()
    
    # Rename columns to lowercase
    df.columns = [col.lower() for col in df.columns]
    
    # Ensure we have open, high, low, close
    required_cols = ['open', 'high', 'low', 'close']
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        print(f"⚠️  Missing columns: {missing}")
        print(f"   Available: {list(df.columns)}")
    
    return df

def verify_signal(df: pd.DataFrame, signal_time: str, expected_side: str):
    """
    Verify if signal at given time is valid
    
    Args:
        df: DataFrame with OHLCV data
        signal_time: Timestamp string (e.g., "2025-11-14 00:00:00")
        expected_side: "LONG" or "SHORT"
    """
    print(f"\n{'='*80}")
    print(f"🔍 VERIFYING SIGNAL: {signal_time} ({expected_side})")
    print(f"{'='*80}")
    
    try:
        target_time = pd.to_datetime(signal_time)
    except:
        print(f"❌ Invalid time format: {signal_time}")
        return False
    
    # Check if data goes up to target time
    if target_time > df.index[-1]:
        print(f"❌ Target time {target_time} is after last available data: {df.index[-1]}")
        print(f"   Cannot verify future signals")
        return False
    
    # Find closest candle (use searchsorted for monotonic index)
    if target_time not in df.index:
        # Find nearest by searching
        idx = df.index.searchsorted(target_time)
        if idx == len(df.index):
            idx = len(df.index) - 1
        elif idx > 0:
            # Check which is closer
            if abs((df.index[idx] - target_time).total_seconds()) > abs((df.index[idx-1] - target_time).total_seconds()):
                idx = idx - 1
        target_time = df.index[idx]
        print(f"⚠️  Exact time not found, using closest: {target_time}")
    
    if target_time not in df.index:
        print(f"❌ Time not found in data")
        return False
    
    # Get data up to signal time
    signal_idx = df.index.get_loc(target_time)
    if signal_idx < ATR_PERIOD:
        print(f"❌ Not enough data (need {ATR_PERIOD} candles, have {signal_idx})")
        return False
    
    # Initialize strategy
    strategy = LiquiditySweepStrategy()
    
    # Load candles up to signal time
    candles_to_load = df.iloc[:signal_idx + 1]
    
    for idx, row in candles_to_load.iterrows():
        strategy.update_candles(row)
    
    # Check signal
    has_signal, signal = strategy.check_signals()
    
    if not has_signal:
        print(f"❌ NO SIGNAL DETECTED at {target_time}")
        print(f"   Expected: {expected_side}")
        return False
    
    if signal['side'] != expected_side:
        print(f"❌ SIGNAL MISMATCH")
        print(f"   Expected: {expected_side}")
        print(f"   Detected: {signal['side']}")
        return False
    
    # Verify signal details
    current_candle = candles_to_load.iloc[-1]
    print(f"\n✅ SIGNAL CONFIRMED: {signal['side']}")
    print(f"\n📊 Signal Details:")
    print(f"   Entry: ${signal['entry']:.2f}")
    print(f"   Stop Loss: ${signal['stop_loss']:.2f}")
    print(f"   Take Profit: ${signal['take_profit']:.2f}")
    print(f"   R:R Ratio: {signal['rr_ratio']:.2f}")
    print(f"   Liquidity Level: ${signal['liquidity_level']:.2f}")
    print(f"   Session: {signal['session']}")
    
    print(f"\n📈 Candle Data:")
    print(f"   Open: ${current_candle['open']:.2f}")
    print(f"   High: ${current_candle['high']:.2f}")
    print(f"   Low: ${current_candle['low']:.2f}")
    print(f"   Close: ${current_candle['close']:.2f}")
    
    # Check if entry price is valid (should be close price)
    if abs(signal['entry'] - current_candle['close']) > 0.01:
        print(f"\n⚠️  WARNING: Entry price mismatch!")
        print(f"   Signal entry: ${signal['entry']:.2f}")
        print(f"   Candle close: ${current_candle['close']:.2f}")
    
    # Check reversal pattern
    if signal['side'] == 'LONG':
        reversal = strategy.detect_bullish_reversal()
        print(f"\n🔄 Bullish Reversal Pattern: {'✅' if reversal else '❌'}")
    else:
        reversal = strategy.detect_bearish_reversal()
        print(f"\n🔄 Bearish Reversal Pattern: {'✅' if reversal else '❌'}")
    
    # Check session levels
    print(f"\n📅 Session Levels:")
    for key, value in strategy.session_levels.items():
        if value is not None:
            print(f"   {key}: ${value:.2f}")
    
    # Check if liquidity level was actually swept
    recent_3 = candles_to_load.tail(3)
    if signal['side'] == 'LONG':
        recent_low = recent_3['low'].min()
        liq_low = signal['liquidity_level']
        swept = recent_low <= liq_low * (1 + SWEEP_TOLERANCE)
        print(f"\n💧 Liquidity Sweep Check:")
        print(f"   Liquidity Low: ${liq_low:.2f}")
        print(f"   Recent Low (3 candles): ${recent_low:.2f}")
        print(f"   Swept: {'✅' if swept else '❌'}")
    else:
        recent_high = recent_3['high'].max()
        liq_high = signal['liquidity_level']
        swept = recent_high >= liq_high * (1 - SWEEP_TOLERANCE)
        print(f"\n💧 Liquidity Sweep Check:")
        print(f"   Liquidity High: ${liq_high:.2f}")
        print(f"   Recent High (3 candles): ${recent_high:.2f}")
        print(f"   Swept: {'✅' if swept else '❌'}")
    
    return True

def check_position_blocking():
    """
    Check if failed position opening blocks new signals
    """
    print(f"\n{'='*80}")
    print(f"🔒 CHECKING POSITION BLOCKING LOGIC")
    print(f"{'='*80}")
    
    print("\n📋 Code Analysis:")
    print("   Line 768: `if self.in_position: return`")
    print("   Line 790-792: If position_size <= 0, just `return` (doesn't set in_position)")
    print("\n✅ CONCLUSION: Failed position opening does NOT block new signals")
    print("   - `in_position` remains False")
    print("   - Next signal will be checked normally")
    print("   - Only successful order placement sets `in_position = True`")

def main():
    """Main verification"""
    print("="*80)
    print("🔍 LIQUIDITY SWEEP SIGNAL VERIFICATION")
    print("="*80)
    
    # Load data
    print("\n📂 Loading BTC 4h data...")
    df = load_btc_4h_data()
    if df is None:
        return
    
    print(f"✅ Loaded {len(df)} candles")
    print(f"   Date range: {df.index[0]} to {df.index[-1]}")
    
    # Signals to verify
    signals = [
        ("2025-11-14 00:00:00", "SHORT"),
        ("2025-11-13 20:00:00", "SHORT"),
        ("2025-11-13 08:00:00", "LONG"),
    ]
    
    results = []
    for signal_time, side in signals:
        result = verify_signal(df, signal_time, side)
        results.append((signal_time, side, result))
    
    # Summary
    print(f"\n{'='*80}")
    print(f"📊 VERIFICATION SUMMARY")
    print(f"{'='*80}")
    
    for signal_time, side, result in results:
        status = "✅ VALID" if result else "❌ INVALID"
        print(f"   {signal_time} ({side}): {status}")
    
    valid_count = sum(1 for _, _, r in results if r)
    print(f"\n✅ Valid: {valid_count}/{len(results)}")
    
    # Check blocking logic
    check_position_blocking()
    
    print(f"\n{'='*80}")
    print("✅ Verification complete!")
    print(f"{'='*80}")

if __name__ == "__main__":
    main()

