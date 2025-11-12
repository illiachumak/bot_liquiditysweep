"""
DEBUG: Детальний аналіз чому сигнали не підтвердились
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from binance.client import Client

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False

SWING_LOOKBACK = 5
SWEEP_TOLERANCE = 0.001
MIN_RR = 1.5
ATR_PERIOD = 14
ATR_STOP_MULTIPLIER = 1.5

ASIAN_SESSION = (0, 8)
LONDON_SESSION = (8, 13)
NY_SESSION = (13, 20)


def calculate_atr_pandas(high, low, close, period=14):
    high_low = high - low
    high_close = np.abs(high - close.shift())
    low_close = np.abs(low - close.shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.ewm(span=period, adjust=False).mean()
    return atr


def download_data():
    client = Client()
    start_time = datetime(2025, 11, 1)
    
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
    
    df = df.rename(columns={
        'open': 'Open', 'high': 'High', 'low': 'Low',
        'close': 'Close', 'volume': 'Volume'
    })
    
    return df[['Open', 'High', 'Low', 'Close', 'Volume']]


def analyze_signal(data, signal_time_str, signal_type):
    """Детальний аналіз чому сигнал виник"""
    
    signal_time = pd.to_datetime(signal_time_str)
    
    print(f"\n{'='*80}")
    print(f"🔍 ДЕТАЛЬНИЙ АНАЛІЗ: {signal_type} @ {signal_time_str}")
    print(f"{'='*80}")
    
    # Find exact candle
    candle_idx = data.index.get_indexer([signal_time], method='nearest')[0]
    candle_time = data.index[candle_idx]
    
    print(f"\n📍 Найближча свічка: {candle_time}")
    print(f"   Різниця в часі: {abs((candle_time - signal_time).total_seconds() / 60):.0f} хвилин")
    
    # Show candle details
    current = data.iloc[candle_idx]
    print(f"\n🕯️  Поточна свічка [{candle_idx}] {candle_time}:")
    print(f"   Open:  ${current['Open']:,.2f}")
    print(f"   High:  ${current['High']:,.2f}")
    print(f"   Low:   ${current['Low']:,.2f}")
    print(f"   Close: ${current['Close']:,.2f}")
    
    candle_type = "🟢 Bullish" if current['Close'] > current['Open'] else "🔴 Bearish"
    body_size = abs(current['Close'] - current['Open'])
    print(f"   Тип: {candle_type}")
    print(f"   Body: ${body_size:,.2f}")
    
    # Previous candles
    print(f"\n📊 Попередні 3 свічки:")
    for i in range(3, 0, -1):
        if candle_idx - i >= 0:
            prev = data.iloc[candle_idx - i]
            prev_time = data.index[candle_idx - i]
            prev_type = "🟢" if prev['Close'] > prev['Open'] else "🔴"
            print(f"   {prev_type} [{candle_idx-i}] {prev_time}")
            print(f"      O: ${prev['Open']:,.2f} H: ${prev['High']:,.2f} L: ${prev['Low']:,.2f} C: ${prev['Close']:,.2f}")
    
    # Calculate ATR
    if TALIB_AVAILABLE:
        atr_values = talib.ATR(
            data['High'].iloc[:candle_idx+1].values,
            data['Low'].iloc[:candle_idx+1].values,
            data['Close'].iloc[:candle_idx+1].values,
            ATR_PERIOD
        )
        atr = atr_values[-1]
    else:
        atr_series = calculate_atr_pandas(
            data['High'].iloc[:candle_idx+1],
            data['Low'].iloc[:candle_idx+1],
            data['Close'].iloc[:candle_idx+1],
            ATR_PERIOD
        )
        atr = atr_series.iloc[-1]
    
    print(f"\n📏 ATR(14): ${atr:,.2f}")
    
    # Recent high/low
    recent_3 = data.iloc[candle_idx-2:candle_idx+1]
    recent_high = recent_3['High'].max()
    recent_low = recent_3['Low'].min()
    
    print(f"\n📊 Recent 3 candles:")
    print(f"   High: ${recent_high:,.2f}")
    print(f"   Low:  ${recent_low:,.2f}")
    
    # Session levels for that day
    day_data = data[data.index.date == signal_time.date()]
    
    session_levels = {}
    for _, candle in day_data.iterrows():
        hour = candle.name.hour
        
        if ASIAN_SESSION[0] <= hour < ASIAN_SESSION[1]:
            if 'asian_high' not in session_levels:
                session_levels['asian_high'] = candle['High']
                session_levels['asian_low'] = candle['Low']
            else:
                session_levels['asian_high'] = max(session_levels['asian_high'], candle['High'])
                session_levels['asian_low'] = min(session_levels['asian_low'], candle['Low'])
        
        elif LONDON_SESSION[0] <= hour < LONDON_SESSION[1]:
            if 'london_high' not in session_levels:
                session_levels['london_high'] = candle['High']
                session_levels['london_low'] = candle['Low']
            else:
                session_levels['london_high'] = max(session_levels['london_high'], candle['High'])
                session_levels['london_low'] = min(session_levels['london_low'], candle['Low'])
        
        elif NY_SESSION[0] <= hour < NY_SESSION[1]:
            if 'ny_high' not in session_levels:
                session_levels['ny_high'] = candle['High']
                session_levels['ny_low'] = candle['Low']
            else:
                session_levels['ny_high'] = max(session_levels['ny_high'], candle['High'])
                session_levels['ny_low'] = min(session_levels['ny_low'], candle['Low'])
    
    print(f"\n🌍 Session Levels ({signal_time.date()}):")
    for key, value in sorted(session_levels.items()):
        if value is not None:
            print(f"   {key:15s}: ${value:,.2f}")
    
    # Get liquidity levels
    liq_highs = [v for k, v in session_levels.items() if 'high' in k and v is not None]
    liq_lows = [v for k, v in session_levels.items() if 'low' in k and v is not None]
    
    print(f"\n💧 Liquidity Zones:")
    print(f"   Highs: {[f'${h:,.2f}' for h in liq_highs]}")
    print(f"   Lows:  {[f'${l:,.2f}' for l in liq_lows]}")
    
    # Check sweep conditions
    print(f"\n🔍 Перевірка умов:")
    
    if signal_type == 'SHORT':
        print(f"\n   SHORT умови:")
        for liq_high in liq_highs:
            sweep_threshold = liq_high * (1 - SWEEP_TOLERANCE)
            is_sweep = recent_high >= sweep_threshold
            distance = ((recent_high - liq_high) / liq_high) * 100
            
            print(f"\n   Liquidity High: ${liq_high:,.2f}")
            print(f"   Sweep threshold: ${sweep_threshold:,.2f}")
            print(f"   Recent high: ${recent_high:,.2f}")
            print(f"   Distance: {distance:+.3f}%")
            print(f"   Sweep? {'✅ YES' if is_sweep else '❌ NO'}")
            
            if is_sweep:
                # Check bearish reversal
                curr_bearish = current['Close'] < current['Open']
                print(f"   Current bearish? {'✅ YES' if curr_bearish else '❌ NO'}")
                
                if candle_idx >= 1:
                    previous = data.iloc[candle_idx-1]
                    curr_body = abs(current['Close'] - current['Open'])
                    prev_body = abs(previous['Close'] - previous['Open'])
                    strong_body = curr_body > prev_body
                    print(f"   Current body: ${curr_body:,.2f}")
                    print(f"   Previous body: ${prev_body:,.2f}")
                    print(f"   Strong body? {'✅ YES' if strong_body else '❌ NO'}")
                
                recent_candle_high = recent_3['High'].max()
                back_below = current['Close'] < recent_candle_high
                print(f"   Recent high: ${recent_candle_high:,.2f}")
                print(f"   Close: ${current['Close']:,.2f}")
                print(f"   Back below? {'✅ YES' if back_below else '❌ NO'}")
    
    elif signal_type == 'LONG':
        print(f"\n   LONG умови:")
        for liq_low in liq_lows:
            sweep_threshold = liq_low * (1 + SWEEP_TOLERANCE)
            is_sweep = recent_low <= sweep_threshold
            distance = ((recent_low - liq_low) / liq_low) * 100
            
            print(f"\n   Liquidity Low: ${liq_low:,.2f}")
            print(f"   Sweep threshold: ${sweep_threshold:,.2f}")
            print(f"   Recent low: ${recent_low:,.2f}")
            print(f"   Distance: {distance:+.3f}%")
            print(f"   Sweep? {'✅ YES' if is_sweep else '❌ NO'}")
            
            if is_sweep:
                # Check bullish reversal
                curr_bullish = current['Close'] > current['Open']
                print(f"   Current bullish? {'✅ YES' if curr_bullish else '❌ NO'}")
                
                if candle_idx >= 1:
                    previous = data.iloc[candle_idx-1]
                    curr_body = abs(current['Close'] - current['Open'])
                    prev_body = abs(previous['Close'] - previous['Open'])
                    strong_body = curr_body > prev_body
                    print(f"   Current body: ${curr_body:,.2f}")
                    print(f"   Previous body: ${prev_body:,.2f}")
                    print(f"   Strong body? {'✅ YES' if strong_body else '❌ NO'}")
                
                recent_candle_low = recent_3['Low'].min()
                back_above = current['Close'] > recent_candle_low
                print(f"   Recent low: ${recent_candle_low:,.2f}")
                print(f"   Close: ${current['Close']:,.2f}")
                print(f"   Back above? {'✅ YES' if back_above else '❌ NO'}")
    
    # Show next candles to see what happened
    print(f"\n📈 Наступні свічки (що сталось далі):")
    for i in range(1, min(6, len(data) - candle_idx)):
        next_candle = data.iloc[candle_idx + i]
        next_time = data.index[candle_idx + i]
        next_type = "🟢" if next_candle['Close'] > next_candle['Open'] else "🔴"
        print(f"   {next_type} {next_time}")
        print(f"      O: ${next_candle['Open']:,.2f} H: ${next_candle['High']:,.2f} L: ${next_candle['Low']:,.2f} C: ${next_candle['Close']:,.2f}")


def main():
    print("\n" + "="*80)
    print("🔍 DEBUG: Чому сигнали не підтвердились?")
    print("="*80)
    
    data = download_data()
    
    # Analyze Signal #1
    analyze_signal(data, '2025-11-11 20:00', 'SHORT')
    
    # Analyze Signal #2
    analyze_signal(data, '2025-11-12 04:00', 'LONG')
    
    print("\n" + "="*80)
    print("💡 ВИСНОВОК")
    print("="*80)
    print("\nМожливі причини розбіжностей:")
    print("  1. Бот працює між свічками (20:02, 04:01) vs бектест на закритті (20:00, 04:00)")
    print("  2. Session levels можуть формуватись трохи інакше")
    print("  3. Різниця в визначенні reversal patterns")
    print("  4. Бектест використовує Close свічки, бот може бачити поточну ціну")
    print("\n" + "="*80)


if __name__ == "__main__":
    main()

