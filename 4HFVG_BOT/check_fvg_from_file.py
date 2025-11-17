#!/usr/bin/env python3
"""
Check FVG from historical data file (not from API)
This uses real data, not testnet data
"""

import pandas as pd
from failed_fvg_live_bot import FVGDetector
from datetime import datetime, timedelta

# Load from historical data file
data_dir = '/Users/illiachumak/trading/backtest/data'
df_4h = pd.read_csv(f'{data_dir}/btc_4h_data_2018_to_2025.csv')
df_15m = pd.read_csv(f'{data_dir}/btc_15m_data_2018_to_2025.csv')

df_4h['Open time'] = pd.to_datetime(df_4h['Open time'])
df_4h.set_index('Open time', inplace=True)
df_4h = df_4h[['Open', 'High', 'Low', 'Close', 'Volume']]
df_4h.columns = ['open', 'high', 'low', 'close', 'volume']

df_15m['Open time'] = pd.to_datetime(df_15m['Open time'])
df_15m.set_index('Open time', inplace=True)
df_15m = df_15m[['Open', 'High', 'Low', 'Close', 'Volume']]
df_15m.columns = ['open', 'high', 'low', 'close', 'volume']

detector = FVGDetector()

# Get last 2 days from the data
if len(df_4h) > 0:
    end_date = df_4h.index[-1]
    start_date = end_date - timedelta(days=2)
    
    df_4h_recent = df_4h[(df_4h.index >= start_date) & (df_4h.index <= end_date)]
    df_15m_recent = df_15m[(df_15m.index >= start_date) & (df_15m.index <= end_date)]
else:
    df_4h_recent = pd.DataFrame()
    df_15m_recent = pd.DataFrame()
    start_date = None
    end_date = None

print('='*80)
print('ПЕРЕВІРКА FVG З ІСТОРИЧНИХ ДАНИХ (РЕАЛЬНІ ДАНІ)')
print('='*80)
print(f'\nПеріод: {start_date.date()} до {end_date.date()}')
print(f'4H свічки: {len(df_4h_recent)}')
print(f'15M свічки: {len(df_15m_recent)}')

# Detect 4H FVGs
fvgs_4h = detector.detect_fvgs(df_4h_recent, '4h')

print(f'\n\n4H FVG знайдено: {len(fvgs_4h)}')
for fvg in fvgs_4h:
    gap = abs(fvg.top - fvg.bottom)
    print(f'   {fvg.type}: \${fvg.bottom:.2f} - \${fvg.top:.2f} (gap: \${gap:.2f}, formed: {fvg.formed_time})')

# Detect 15M FVGs
fvgs_15m = detector.detect_fvgs(df_15m_recent, '15m')

print(f'\n15M FVG знайдено: {len(fvgs_15m)}')
for fvg in fvgs_15m[:10]:  # Show first 10
    gap = abs(fvg.top - fvg.bottom)
    print(f'   {fvg.type}: \${fvg.bottom:.2f} - \${fvg.top:.2f} (gap: \${gap:.2f}, formed: {fvg.formed_time})')
if len(fvgs_15m) > 10:
    print(f'   ... і ще {len(fvgs_15m) - 10} FVG')

print('='*80)
print('💡 Використовуються РЕАЛЬНІ історичні дані з файлів, не testnet API!')
print('='*80)

