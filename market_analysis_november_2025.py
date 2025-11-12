"""
MARKET ANALYSIS - November 2025
Поточний стан ринку та потенційні setup-и
"""

import pandas as pd
import numpy as np
from datetime import datetime
from binance.client import Client

# TA-Lib з fallback
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False

# Strategy parameters
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


def download_recent_data(symbol='BTCUSDT', interval='4h', limit=100):
    """Download recent market data"""
    try:
        client = Client()
        klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
        
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
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
        })
        
        return df[['Open', 'High', 'Low', 'Close', 'Volume']]
    
    except Exception as e:
        print(f"Error: {e}")
        return None


def analyze_market():
    """Analyze current market condition"""
    print("\n" + "="*70)
    print("📊 АНАЛІЗ РИНКУ - ЛИСТОПАД 2025")
    print("="*70)
    
    # Download data
    print("\n📥 Завантаження даних...")
    data = download_recent_data('BTCUSDT', '4h', 100)
    
    if data is None or len(data) == 0:
        print("❌ Не вдалось завантажити дані")
        return
    
    print(f"✅ Завантажено {len(data)} свічок")
    print(f"   Період: {data.index[0]} до {data.index[-1]}")
    
    # Calculate ATR
    if TALIB_AVAILABLE:
        data['atr'] = talib.ATR(data['High'].values, data['Low'].values, 
                                data['Close'].values, ATR_PERIOD)
    else:
        data['atr'] = calculate_atr_pandas(data['High'], data['Low'], 
                                           data['Close'], ATR_PERIOD)
    
    # Current state
    current = data.iloc[-1]
    current_time = data.index[-1]
    
    print("\n" + "="*70)
    print("📈 ПОТОЧНИЙ СТАН")
    print("="*70)
    print(f"\n🕐 Час: {current_time.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"💰 Ціна: ${current['Close']:,.2f}")
    print(f"📊 High: ${current['High']:,.2f} | Low: ${current['Low']:,.2f}")
    print(f"📏 ATR(14): ${current['atr']:,.2f}")
    
    # Calculate session levels
    session_levels = {}
    current_date = current_time.date()
    
    # Get today's data
    today_data = data[data.index.date == current_date]
    
    if len(today_data) > 0:
        for _, candle in today_data.iterrows():
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
    
    # Print session levels
    print("\n" + "="*70)
    print("🌍 SESSION LEVELS (Сьогодні)")
    print("="*70)
    
    if 'asian_high' in session_levels:
        print(f"\n🌏 ASIAN SESSION (00:00-08:00 UTC):")
        print(f"   High: ${session_levels['asian_high']:,.2f}")
        print(f"   Low:  ${session_levels['asian_low']:,.2f}")
    else:
        print(f"\n🌏 ASIAN SESSION: Не сформовано")
    
    if 'london_high' in session_levels:
        print(f"\n🇬🇧 LONDON SESSION (08:00-13:00 UTC):")
        print(f"   High: ${session_levels['london_high']:,.2f}")
        print(f"   Low:  ${session_levels['london_low']:,.2f}")
    else:
        print(f"\n🇬🇧 LONDON SESSION: Не сформовано")
    
    if 'ny_high' in session_levels:
        print(f"\n🇺🇸 NY SESSION (13:00-20:00 UTC):")
        print(f"   High: ${session_levels['ny_high']:,.2f}")
        print(f"   Low:  ${session_levels['ny_low']:,.2f}")
    else:
        print(f"\n🇺🇸 NY SESSION: Не сформовано")
    
    # Recent swing levels
    recent_5 = data.tail(5)
    swing_high = recent_5['High'].max()
    swing_low = recent_5['Low'].min()
    
    print("\n" + "="*70)
    print("📊 SWING LEVELS (Останні 5 свічок)")
    print("="*70)
    print(f"\n   Swing High: ${swing_high:,.2f}")
    print(f"   Swing Low:  ${swing_low:,.2f}")
    
    # Check for potential setups
    print("\n" + "="*70)
    print("🎯 ПОТЕНЦІЙНІ SETUP-И")
    print("="*70)
    
    recent_3 = data.tail(3)
    recent_high = recent_3['High'].max()
    recent_low = recent_3['Low'].min()
    
    liq_highs = [v for k, v in session_levels.items() if 'high' in k]
    liq_lows = [v for k, v in session_levels.items() if 'low' in k]
    
    found_setup = False
    
    # Check for sweep setups
    if liq_lows:
        for liq_low in liq_lows:
            distance = ((recent_low - liq_low) / liq_low) * 100
            if abs(distance) <= 0.5:  # Within 0.5%
                print(f"\n🟢 POTENTIAL LONG SETUP:")
                print(f"   Ціна наближається до Liquidity Low: ${liq_low:,.2f}")
                print(f"   Відстань: {distance:.2f}%")
                print(f"   Очікуємо:")
                print(f"     1. Sweep нижче ${liq_low:,.2f}")
                print(f"     2. Бичачий реверс (bullish candle)")
                print(f"     3. Entry на закритті свічки")
                found_setup = True
    
    if liq_highs:
        for liq_high in liq_highs:
            distance = ((recent_high - liq_high) / liq_high) * 100
            if abs(distance) <= 0.5:  # Within 0.5%
                print(f"\n🔴 POTENTIAL SHORT SETUP:")
                print(f"   Ціна наближається до Liquidity High: ${liq_high:,.2f}")
                print(f"   Відстань: {distance:.2f}%")
                print(f"   Очікуємо:")
                print(f"     1. Sweep вище ${liq_high:,.2f}")
                print(f"     2. Ведмежий реверс (bearish candle)")
                print(f"     3. Entry на закритті свічки")
                found_setup = True
    
    if not found_setup:
        print("\n⚠️  Наразі немає активних setup-ів")
        print("\n💡 Що робити:")
        print("   1. Чекати наступних свічок")
        print("   2. Моніторити формування session levels")
        print("   3. Шукати sweep liquidity zones")
        print("\n   Бот автоматично знайде сигнал коли умови виконаються!")
    
    # Recent price action
    print("\n" + "="*70)
    print("📜 ОСТАННЯ PRICE ACTION (5 свічок)")
    print("="*70)
    
    for idx, (timestamp, candle) in enumerate(data.tail(5).iterrows()):
        candle_type = "🟢" if candle['Close'] > candle['Open'] else "🔴"
        body_size = abs(candle['Close'] - candle['Open'])
        
        print(f"\n{candle_type} {timestamp.strftime('%Y-%m-%d %H:%M')}")
        print(f"   Open: ${candle['Open']:,.2f} | Close: ${candle['Close']:,.2f}")
        print(f"   High: ${candle['High']:,.2f} | Low: ${candle['Low']:,.2f}")
        print(f"   Body: ${body_size:,.2f}")
    
    # Summary
    print("\n" + "="*70)
    print("📝 ВИСНОВОК")
    print("="*70)
    print(f"\n1. Поточна ціна: ${current['Close']:,.2f}")
    print(f"2. Session levels сформовано: {len(session_levels) // 2}")
    print(f"3. ATR(14): ${current['atr']:,.2f}")
    print(f"4. Активні setup-и: {'Є потенційні' if found_setup else 'Немає'}")
    print("\n💡 Бот автоматично відловить сигнал коли:")
    print("   - Ціна зробить sweep liquidity level")
    print("   - Сформується reversal pattern")
    print("   - R:R буде >= 1.5")
    
    print("\n🤖 Рекомендація: Запустіть бота і дайте йому працювати")
    print("   Стратегія має низьку частоту трейдів - це нормально!")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    analyze_market()

