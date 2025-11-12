"""
MOCK BOT TEST: Standalone версія з виправленою логікою
Симуляція роботи бота з 9 листопада 2025
"""

import pandas as pd
import numpy as np
from datetime import datetime
from binance.client import Client

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False

# Strategy parameters (from bot)
SWING_LOOKBACK = 5
SWEEP_TOLERANCE = 0.001
MIN_RR = 1.5
ATR_PERIOD = 14
ATR_STOP_MULTIPLIER = 1.5

ASIAN_SESSION = (0, 8)
LONDON_SESSION = (8, 13)
NY_SESSION = (13, 20)


def calculate_atr_pandas(high, low, close, period=14):
    """Calculate ATR using pandas"""
    high_low = high - low
    high_close = np.abs(high - close.shift())
    low_close = np.abs(low - close.shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.ewm(span=period, adjust=False).mean()
    return atr


class MockStrategy:
    """Mock strategy with FIXED logic"""
    
    def __init__(self):
        self.candles = pd.DataFrame()
        self.session_levels = {
            'asian_high': None, 'asian_low': None,
            'london_high': None, 'london_low': None,
            'ny_high': None, 'ny_low': None
        }
        self.current_date = None
    
    def update_session_levels(self, candle):
        """Update session levels"""
        timestamp = candle.name
        current_date = timestamp.date()
        hour = timestamp.hour
        
        if self.current_date != current_date:
            self.current_date = current_date
            self.session_levels = {k: None for k in self.session_levels}
        
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
    
    def detect_bullish_reversal(self):
        """FIXED: Detect bullish reversal - strict checks"""
        if len(self.candles) < 3:
            return False
        
        recent = self.candles.tail(3)
        current = recent.iloc[-1]
        previous = recent.iloc[-2]
        
        # CRITICAL: Must be bullish candle first!
        curr_bullish = current['close'] > current['open']
        if not curr_bullish:
            return False
        
        # Must have stronger body than previous
        curr_body = abs(current['close'] - current['open'])
        prev_body = abs(previous['close'] - previous['open'])
        strong_body = curr_body > prev_body
        if not strong_body:
            return False
        
        # Must close back above recent low
        recent_low = recent['low'].min()
        back_above = current['close'] > recent_low
        
        return back_above
    
    def detect_bearish_reversal(self):
        """FIXED: Detect bearish reversal - strict checks"""
        if len(self.candles) < 3:
            return False
        
        recent = self.candles.tail(3)
        current = recent.iloc[-1]
        previous = recent.iloc[-2]
        
        # CRITICAL: Must be bearish candle first!
        curr_bearish = current['close'] < current['open']
        if not curr_bearish:
            return False
        
        # Must have stronger body than previous
        curr_body = abs(current['close'] - current['open'])
        prev_body = abs(previous['close'] - previous['open'])
        strong_body = curr_body > prev_body
        if not strong_body:
            return False
        
        # Must close back below recent high
        recent_high = recent['high'].max()
        back_below = current['close'] < recent_high
        
        return back_below
    
    def check_signals(self):
        """Check for signals"""
        if len(self.candles) < ATR_PERIOD:
            return False, None
        
        current = self.candles.iloc[-1]
        recent_3 = self.candles.tail(3)
        
        # Calculate ATR
        if TALIB_AVAILABLE:
            atr = talib.ATR(self.candles['high'].values, self.candles['low'].values,
                           self.candles['close'].values, ATR_PERIOD)[-1]
        else:
            atr_series = calculate_atr_pandas(self.candles['high'], self.candles['low'],
                                             self.candles['close'], ATR_PERIOD)
            atr = atr_series.iloc[-1]
        
        if pd.isna(atr) or atr == 0:
            return False, None
        
        recent_high = recent_3['high'].max()
        recent_low = recent_3['low'].min()
        
        liq_highs = [v for v in [self.session_levels['asian_high'],
                                  self.session_levels['london_high'],
                                  self.session_levels['ny_high']] if v is not None]
        
        liq_lows = [v for v in [self.session_levels['asian_low'],
                                 self.session_levels['london_low'],
                                 self.session_levels['ny_low']] if v is not None]
        
        if not liq_highs or not liq_lows:
            return False, None
        
        # CHECK LONG
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
                            'liquidity_level': liq_low
                        }
        
        # CHECK SHORT
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
                            'liquidity_level': liq_high
                        }
        
        return False, None


def download_data():
    """Download data from Binance"""
    print(f"\n📥 Завантаження даних з 9 листопада...")
    
    try:
        client = Client()
        start_time = datetime(2025, 11, 9)
        
        klines = client.futures_klines(
            symbol='BTCUSDT',
            interval='4h',
            startTime=int(start_time.timestamp() * 1000),
            limit=1000
        )
        
        df = pd.DataFrame(klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df = df.set_index('open_time')
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        
        print(f"✅ Завантажено {len(df)} свічок")
        print(f"   Період: {df.index[0]} - {df.index[-1]}")
        
        return df
        
    except Exception as e:
        print(f"❌ Помилка: {e}")
        return None


def simulate_bot(data):
    """Simulate bot with fixed logic"""
    
    print("\n" + "="*80)
    print("🤖 СИМУЛЯЦІЯ БОТА (ВИПРАВЛЕНА ЛОГІКА)")
    print("="*80)
    
    strategy = MockStrategy()
    signals = []
    
    # Initialize with first 10 candles
    strategy.candles = data.iloc[:10].copy()
    for idx, row in strategy.candles.iterrows():
        strategy.update_session_levels(row)
    
    print(f"\n✅ Ініціалізовано: {len(strategy.candles)} свічок")
    
    # Process remaining candles
    for i in range(10, len(data)):
        candle_time = data.index[i]
        candle = data.iloc[i]
        
        # Add candle
        strategy.candles = pd.concat([strategy.candles, pd.DataFrame([candle], index=[candle_time])])
        strategy.candles = strategy.candles.tail(100)
        strategy.update_session_levels(candle)
        
        # Check signals
        has_signal, signal = strategy.check_signals()
        
        candle_type = "🟢" if candle['close'] > candle['open'] else "🔴"
        body = abs(candle['close'] - candle['open'])
        
        print(f"\n{candle_type} {candle_time.strftime('%m-%d %H:%M')} | Body: ${body:.2f}")
        
        if has_signal and signal:
            print(f"\n   🚨 SIGNAL: {signal['side']}")
            print(f"      Entry: ${signal['entry']:,.2f}")
            print(f"      SL: ${signal['stop_loss']:,.2f} | TP: ${signal['take_profit']:,.2f}")
            print(f"      R:R: {signal['rr_ratio']:.2f}")
            
            signals.append({
                'time': candle_time,
                **signal
            })
    
    return signals


def main():
    """Main function"""
    
    print("\n" + "="*80)
    print("🧪 MOCK BOT TEST - ВИПРАВЛЕНА ЛОГІКА")
    print("="*80)
    print("\nМета: Перевірити чи після фіксу false signals відфільтровані")
    print("="*80)
    
    # Download data
    data = download_data()
    if data is None:
        return
    
    # Simulate
    signals = simulate_bot(data)
    
    # Results
    print("\n" + "="*80)
    print("📊 РЕЗУЛЬТАТИ")
    print("="*80)
    
    print(f"\n🔴 Старий бот (з багом): 2 сигнали")
    print(f"   1. SHORT @ 2025-11-11 20:02 | Entry: $103,004")
    print(f"   2. LONG @ 2025-11-12 04:01 | Entry: $103,299")
    
    print(f"\n🟢 Новий бот (після фіксу): {len(signals)} сигналів")
    
    if signals:
        for sig in signals:
            print(f"   {sig['side']} @ {sig['time'].strftime('%Y-%m-%d %H:%M')} | Entry: ${sig['entry']:,.2f}")
    else:
        print(f"   (Не знайдено жодного)")
    
    print("\n" + "="*80)
    print("✅ ВИСНОВОК")
    print("="*80)
    
    if len(signals) == 0:
        print("\n🎉 ВИПРАВЛЕННЯ ПРАЦЮЄ!")
        print("   ✅ False signals відфільтровані")
        print("   ✅ Логіка тепер коректна")
        print("   ✅ Бот готовий до тестування на Testnet")
    elif len(signals) < 2:
        print("\n⚠️  Частково виправлено")
        print(f"   {2 - len(signals)} з 2 false signals відфільтровано")
    else:
        print("\n⚠️  Потрібна додаткова перевірка")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()

