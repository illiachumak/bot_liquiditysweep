#!/usr/bin/env python3
"""
Check specific gaps mentioned by user
Shows all possible gap definitions
"""

from failed_fvg_live_bot import BinanceClientWrapper
import pandas as pd

client = BinanceClientWrapper()
df_4h = client.get_klines('BTCUSDT', '4h', limit=200)

print('='*80)
print('ПЕРЕВІРКА КОНКРЕТНИХ GAP')
print('='*80)

# Get specific candles
candle_16_16 = df_4h[df_4h.index == pd.Timestamp('2025-11-16 16:00:00')]
candle_17_00 = df_4h[df_4h.index == pd.Timestamp('2025-11-17 00:00:00')]
candle_17_08 = df_4h[df_4h.index == pd.Timestamp('2025-11-17 08:00:00')]
candle_17_16 = df_4h[df_4h.index == pd.Timestamp('2025-11-17 16:00:00')]

print(f'\n1. GAP між 16 nov 16:00 та 17 nov 00:00:')
if not candle_16_16.empty and not candle_17_00.empty:
    c16 = candle_16_16.iloc[0]
    c17 = candle_17_00.iloc[0]
    
    open_16 = c16['open']
    high_16 = c16['high']
    low_16 = c16['low']
    close_16 = c16['close']
    open_17 = c17['open']
    high_17 = c17['high']
    low_17 = c17['low']
    close_17 = c17['close']
    
    print(f'   16 nov 16:00: O=${open_16:.2f}, H=${high_16:.2f}, L=${low_16:.2f}, C=${close_16:.2f}')
    print(f'   17 nov 00:00: O=${open_17:.2f}, H=${high_17:.2f}, L=${low_17:.2f}, C=${close_17:.2f}')
    
    # Standard FVG: Low[i] > High[i-2] or High[i] < Low[i-2]
    print(f'\n   Стандартна FVG логіка (i vs i-2):')
    if low_17 > high_16:
        gap = low_17 - high_16
        print(f'      ✅ BULLISH FVG: Low[17 nov 00:00]=${low_17:.2f} > High[16 nov 16:00]=${high_16:.2f}')
        print(f'      Gap: ${gap:.2f}')
        print(f'      FVG Zone: ${high_16:.2f} - ${low_17:.2f}')
    elif high_17 < low_16:
        gap = low_16 - high_17
        print(f'      ✅ BEARISH FVG: High[17 nov 00:00]=${high_17:.2f} < Low[16 nov 16:00]=${low_16:.2f}')
        print(f'      Gap: ${gap:.2f}')
        print(f'      FVG Zone: ${high_17:.2f} - ${low_16:.2f}')
    else:
        print(f'      ❌ No FVG (є overlap)')
        print(f'      Low[17 nov 00:00]=${low_17:.2f} <= High[16 nov 16:00]=${high_16:.2f}')
        print(f'      High[17 nov 00:00]=${high_17:.2f} >= Low[16 nov 16:00]=${low_16:.2f}')
    
    # Alternative: gap between close and open
    print(f'\n   Альтернативна перевірка (Close vs Open):')
    if open_17 > close_16:
        gap = open_17 - close_16
        print(f'      ✅ Gap up: Open[17 nov 00:00]=${open_17:.2f} > Close[16 nov 16:00]=${close_16:.2f}')
        print(f'      Gap: ${gap:.2f}')
    elif open_17 < close_16:
        gap = close_16 - open_17
        print(f'      ✅ Gap down: Open[17 nov 00:00]=${open_17:.2f} < Close[16 nov 16:00]=${close_16:.2f}')
        print(f'      Gap: ${gap:.2f}')
    else:
        print(f'      ❌ No gap')

print(f'\n2. GAP між 17 nov 08:00 та 17 nov 16:00:')
if not candle_17_08.empty and not candle_17_16.empty:
    c08 = candle_17_08.iloc[0]
    c16 = candle_17_16.iloc[0]
    
    open_08 = c08['open']
    high_08 = c08['high']
    low_08 = c08['low']
    close_08 = c08['close']
    open_16_2 = c16['open']
    high_16_2 = c16['high']
    low_16_2 = c16['low']
    close_16_2 = c16['close']
    
    print(f'   17 nov 08:00: O=${open_08:.2f}, H=${high_08:.2f}, L=${low_08:.2f}, C=${close_08:.2f}')
    print(f'   17 nov 16:00: O=${open_16_2:.2f}, H=${high_16_2:.2f}, L=${low_16_2:.2f}, C=${close_16_2:.2f}')
    
    # Standard FVG
    print(f'\n   Стандартна FVG логіка (i vs i-2):')
    if low_16_2 > high_08:
        gap = low_16_2 - high_08
        print(f'      ✅ BULLISH FVG: Low[17 nov 16:00]=${low_16_2:.2f} > High[17 nov 08:00]=${high_08:.2f}')
        print(f'      Gap: ${gap:.2f}')
        print(f'      FVG Zone: ${high_08:.2f} - ${low_16_2:.2f}')
    elif high_16_2 < low_08:
        gap = low_08 - high_16_2
        print(f'      ✅ BEARISH FVG: High[17 nov 16:00]=${high_16_2:.2f} < Low[17 nov 08:00]=${low_08:.2f}')
        print(f'      Gap: ${gap:.2f}')
        print(f'      FVG Zone: ${high_16_2:.2f} - ${low_08:.2f}')
    else:
        print(f'      ❌ No FVG (є overlap)')
        print(f'      Low[17 nov 16:00]=${low_16_2:.2f} <= High[17 nov 08:00]=${high_08:.2f}')
        print(f'      High[17 nov 16:00]=${high_16_2:.2f} >= Low[17 nov 08:00]=${low_08:.2f}')
    
    # Alternative: gap between close and open
    print(f'\n   Альтернативна перевірка (Close vs Open):')
    if open_16_2 > close_08:
        gap = open_16_2 - close_08
        print(f'      ✅ Gap up: Open[17 nov 16:00]=${open_16_2:.2f} > Close[17 nov 08:00]=${close_08:.2f}')
        print(f'      Gap: ${gap:.2f}')
    elif open_16_2 < close_08:
        gap = close_08 - open_16_2
        print(f'      ✅ Gap down: Open[17 nov 16:00]=${open_16_2:.2f} < Close[17 nov 08:00]=${close_08:.2f}')
        print(f'      Gap: ${gap:.2f}')
    else:
        print(f'      ❌ No gap')

# Check all candles in range
print(f'\n\n📊 ВСІ 4H СВІЧКИ ЗА 16-17 ЛИСТОПАДА:')
df_nov = df_4h[(df_4h.index >= '2025-11-16') & (df_4h.index <= '2025-11-17 23:59:59')]
for i in range(len(df_nov)):
    candle = df_nov.iloc[i]
    idx_time = df_nov.index[i]
    o = candle['open']
    h = candle['high']
    l = candle['low']
    c = candle['close']
    print(f'   {i:2d}. {idx_time}: O=${o:>10.2f}, H=${h:>10.2f}, L=${l:>10.2f}, C=${c:>10.2f}')

print('='*80)
print('💡 Примітка: Стандартна FVG логіка вимагає gap між свічками i та i-2')
print('   (Bullish: Low[i] > High[i-2], Bearish: High[i] < Low[i-2])')
print('='*80)

