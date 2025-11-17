#!/usr/bin/env python3
"""
Check Active 4H FVGs and their status
Shows all 4H FVGs, whether they're rejected, and if there are 15M FVGs after rejection
"""

from failed_fvg_live_bot import FVGDetector, BinanceClientWrapper, LiveFVG
import pandas as pd
from datetime import datetime, timedelta

client = BinanceClientWrapper()
detector = FVGDetector()

# Load data
print("📊 Loading data from Binance...")
df_4h = client.get_klines('BTCUSDT', '4h', limit=200)
df_15m = client.get_klines('BTCUSDT', '15m', limit=1000)

# Filter to last 30 days for context
end_time = datetime.now()
start_time = end_time - timedelta(days=30)
df_4h_recent = df_4h[df_4h.index >= start_time]
df_15m_recent = df_15m[df_15m.index >= start_time]

print(f"✅ Loaded {len(df_4h_recent)} 4H candles, {len(df_15m_recent)} 15M candles")
print(f"Period: {df_4h_recent.index[0]} to {df_4h_recent.index[-1]}\n")

# Detect all 4H FVGs
fvgs_4h = detector.detect_fvgs(df_4h_recent, '4h')

print('='*80)
print(f'4H FVG ЗНАЙДЕНО: {len(fvgs_4h)}')
print('='*80)

if len(fvgs_4h) == 0:
    print("❌ Не знайдено жодного 4H FVG за останні 30 днів")
    print("\n💡 FVG формується коли:")
    print("   - Bullish FVG: Low[i] > High[i-2] (gap up)")
    print("   - Bearish FVG: High[i] < Low[i-2] (gap down)")
    print("\n   Потрібен значний рух ціни між свічками!")
else:
    # Check status of each FVG
    for i, fvg in enumerate(fvgs_4h, 1):
        print(f"\n📊 FVG #{i}: {fvg.type}")
        print(f"   Zone: ${fvg.bottom:.2f} - ${fvg.top:.2f}")
        print(f"   Formed: {fvg.formed_time}")
        gap = abs(fvg.top - fvg.bottom)
        print(f"   Gap Size: ${gap:.2f}")
        
        # Check if FVG is still active (not invalidated)
        # Find candles after FVG formation
        fvg_time = fvg.formed_time
        candles_after = df_4h_recent[df_4h_recent.index > fvg_time]
        
        invalidated = False
        rejected = False
        rejection_time = None
        rejection_price = None
        
        # Check for rejection and invalidation
        for idx, candle in candles_after.iterrows():
            # Check if price entered FVG
            if not fvg.entered:
                if not (candle['high'] < fvg.bottom or candle['low'] > fvg.top):
                    fvg.entered = True
                    print(f"   ✅ Price entered FVG at {idx}")
            
            # Check rejection
            if fvg.entered and not rejected:
                if fvg.type == 'BULLISH':
                    if candle['close'] < fvg.bottom:
                        rejected = True
                        rejection_time = idx
                        rejection_price = candle['close']
                        print(f"   🚫 REJECTED at {rejection_time} @ ${rejection_price:.2f}")
                else:  # BEARISH
                    if candle['close'] > fvg.top:
                        rejected = True
                        rejection_time = idx
                        rejection_price = candle['close']
                        print(f"   🚫 REJECTED at {rejection_time} @ ${rejection_price:.2f}")
            
            # Check invalidation
            if fvg.type == 'BULLISH':
                if candle['low'] < fvg.bottom:
                    invalidated = True
                    print(f"   ❌ INVALIDATED at {idx} (price closed below FVG)")
                    break
            else:  # BEARISH
                if candle['high'] > fvg.top:
                    invalidated = True
                    print(f"   ❌ INVALIDATED at {idx} (price closed above FVG)")
                    break
        
        if not invalidated and not rejected:
            print(f"   ⏳ Still active (waiting for rejection or invalidation)")
        elif rejected and not invalidated:
            print(f"   ✅ Rejected but not invalidated - looking for 15M FVG...")
            
            # Check for 15M FVG after rejection
            if rejection_time:
                # Look for 15M FVG after rejection time
                fvgs_15m_after = detector.detect_fvgs(
                    df_15m_recent[df_15m_recent.index > rejection_time], 
                    '15m'
                )
                
                # Filter by opposite type
                opposite_type = 'BULLISH' if fvg.type == 'BEARISH' else 'BEARISH'
                matching_15m = [f for f in fvgs_15m_after if f.type == opposite_type]
                
                if matching_15m:
                    print(f"   ✅ Found {len(matching_15m)} {opposite_type} 15M FVG(s) after rejection:")
                    for f15m in matching_15m[:3]:  # Show first 3
                        print(f"      - ${f15m.bottom:.2f} - ${f15m.top:.2f} (formed: {f15m.formed_time})")
                else:
                    print(f"   ⏳ No {opposite_type} 15M FVG found after rejection yet")

print('\n' + '='*80)
print('ПІДСУМОК')
print('='*80)
print(f"Всього 4H FVG: {len(fvgs_4h)}")
active = sum(1 for f in fvgs_4h if not f.invalidated)
rejected = sum(1 for f in fvgs_4h if f.rejected and not f.invalidated)
print(f"Активних: {active}")
print(f"Відхилених (очікують 15M FVG): {rejected}")
print(f"Інвалідованих: {len(fvgs_4h) - active}")

print('\n💡 Стратегія потребує:')
print('   1. 4H FVG (bullish або bearish)')
print('   2. Відхилення 4H FVG (rejection)')
print('   3. 15M FVG протилежного типу після відхилення')
print('   4. Валідація setup (RR >= 2.0, SL >= 0.3%)')

