#!/usr/bin/env python3
"""
Check FVG using REAL Binance API (not testnet)
For 2025 year data
"""

from binance.client import Client
import pandas as pd
from failed_fvg_live_bot import FVGDetector
import os
from dotenv import load_dotenv

load_dotenv()

# Use REAL API (not testnet)
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')

# Create client WITHOUT testnet
client = Client(API_KEY, API_SECRET, testnet=False)  # REAL API!

detector = FVGDetector()

print('='*80)
print('ПЕРЕВІРКА FVG З РЕАЛЬНОГО BINANCE API (2025 РІК)')
print('='*80)

# Fetch 4H data for 2025
print('\n📊 Завантаження 4H даних...')
klines = client.futures_klines(symbol='BTCUSDT', interval='4h', limit=1000)

df_4h = pd.DataFrame(klines, columns=[
    'timestamp', 'open', 'high', 'low', 'close', 'volume',
    'close_time', 'quote_volume', 'trades', 'taker_buy_base',
    'taker_buy_quote', 'ignore'
])

df_4h['timestamp'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
df_4h.set_index('timestamp', inplace=True)

for col in ['open', 'high', 'low', 'close', 'volume']:
    df_4h[col] = df_4h[col].astype(float)

# Filter to Nov 16-17 2025
df_4h_nov = df_4h[(df_4h.index >= '2025-11-16') & (df_4h.index <= '2025-11-17 23:59:59')]

print(f'✅ Завантажено {len(df_4h_nov)} 4H свічок за 16-17 листопада 2025')

print(f'\nВсі 4H свічки:')
for i in range(len(df_4h_nov)):
    candle = df_4h_nov.iloc[i]
    idx_time = df_4h_nov.index[i]
    o = candle['open']
    h = candle['high']
    l = candle['low']
    c = candle['close']
    print(f'   {i:2d}. {idx_time}: O=${o:>10.2f}, H=${h:>10.2f}, L=${l:>10.2f}, C=${c:>10.2f}')

# Detect FVGs
fvgs = detector.detect_fvgs(df_4h_nov, '4h')

print(f'\n\n4H FVG знайдено: {len(fvgs)}')
for fvg in fvgs:
    gap = abs(fvg.top - fvg.bottom)
    print(f'   {fvg.type}: ${fvg.bottom:.2f} - ${fvg.top:.2f} (gap: ${gap:.2f}, formed: {fvg.formed_time})')

# Check specific periods
print(f'\n\n🔍 ПЕРЕВІРКА КОНКРЕТНИХ ПЕРІОДІВ:')
print(f'\n1. 16 nov 16:00 - 17 nov 00:00 (свічки #4 та #6)')
if len(df_4h_nov) > 6:
    candle_4 = df_4h_nov.iloc[4]  # 16:00
    candle_6 = df_4h_nov.iloc[6]  # 17 nov 00:00
    time_4 = df_4h_nov.index[4]
    time_6 = df_4h_nov.index[6]
    
    h4 = candle_4['high']
    l4 = candle_4['low']
    h6 = candle_6['high']
    l6 = candle_6['low']
    
    print(f'   Свічка #4 ({time_4}): H=${h4:.2f}, L=${l4:.2f}')
    print(f'   Свічка #6 ({time_6}): H=${h6:.2f}, L=${l6:.2f}')
    
    # FVG: i=6, i-2=4
    if l6 > h4:
        gap = l6 - h4
        print(f'   ✅ BULLISH FVG! Gap: ${gap:.2f}')
        print(f'   FVG Zone: ${h4:.2f} - ${l6:.2f}')
    elif h6 < l4:
        gap = l4 - h6
        print(f'   ✅ BEARISH FVG! Gap: ${gap:.2f}')
        print(f'   FVG Zone: ${h6:.2f} - ${l4:.2f}')
    else:
        print(f'   ❌ No FVG (є overlap)')
        print(f'   Low[6]=${l6:.2f} <= High[4]=${h4:.2f}')
        print(f'   High[6]=${h6:.2f} >= Low[4]=${l4:.2f}')

print(f'\n2. 17 nov 08:00 - 17 nov 16:00 (свічки #8 та #10)')
if len(df_4h_nov) > 10:
    candle_8 = df_4h_nov.iloc[8]  # 08:00
    candle_10 = df_4h_nov.iloc[10]  # 16:00
    time_8 = df_4h_nov.index[8]
    time_10 = df_4h_nov.index[10]
    
    h8 = candle_8['high']
    l8 = candle_8['low']
    h10 = candle_10['high']
    l10 = candle_10['low']
    
    print(f'   Свічка #8 ({time_8}): H=${h8:.2f}, L=${l8:.2f}')
    print(f'   Свічка #10 ({time_10}): H=${h10:.2f}, L=${l10:.2f}')
    
    # FVG: i=10, i-2=8
    if l10 > h8:
        gap = l10 - h8
        print(f'   ✅ BULLISH FVG! Gap: ${gap:.2f}')
        print(f'   FVG Zone: ${h8:.2f} - ${l10:.2f}')
    elif h10 < l8:
        gap = l8 - h10
        print(f'   ✅ BEARISH FVG! Gap: ${gap:.2f}')
        print(f'   FVG Zone: ${h10:.2f} - ${l8:.2f}')
    else:
        print(f'   ❌ No FVG (є overlap)')
        print(f'   Low[10]=${l10:.2f} <= High[8]=${h8:.2f}')
        print(f'   High[10]=${h10:.2f} >= Low[8]=${l8:.2f}')

print('='*80)

