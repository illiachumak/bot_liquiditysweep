"""
Quick test of HELD FVG logic on last 7 days
"""

import pandas as pd
import requests
import time
from datetime import datetime, timedelta

# Copy detect_fvg logic
def detect_fvg(df, start_idx, end_idx):
    """Simple FVG detection"""
    fvgs = []

    for i in range(start_idx + 2, end_idx):
        if i < 2:
            continue

        candle = df.iloc[i]
        candle_prev2 = df.iloc[i-2]

        # Bullish FVG
        if candle['Low'] > candle_prev2['High']:
            fvgs.append({
                'type': 'BULLISH',
                'top': candle['Low'],
                'bottom': candle_prev2['High'],
                'index': i,
                'time': candle.name
            })

        # Bearish FVG
        elif candle['High'] < candle_prev2['Low']:
            fvgs.append({
                'type': 'BEARISH',
                'top': candle_prev2['Low'],
                'bottom': candle['High'],
                'index': i,
                'time': candle.name
            })

    return fvgs


def fetch_binance_data(symbol, interval, start_time, end_time):
    """Fetch data from Binance"""
    url = "https://api.binance.com/api/v3/klines"
    all_candles = []
    current_start = start_time

    while current_start < end_time:
        params = {
            'symbol': symbol,
            'interval': interval,
            'startTime': current_start,
            'endTime': end_time,
            'limit': 1000
        }

        response = requests.get(url, params=params)
        data = response.json()

        if not data:
            break

        all_candles.extend(data)
        current_start = data[-1][6] + 1

        time.sleep(0.5)

    df = pd.DataFrame(all_candles, columns=[
        'Open time', 'Open', 'High', 'Low', 'Close', 'Volume',
        'Close time', 'Quote asset volume', 'Number of trades',
        'Taker buy base asset volume', 'Taker buy quote asset volume', 'Ignore'
    ])

    df['Open time'] = pd.to_datetime(df['Open time'], unit='ms')
    df.set_index('Open time', inplace=True)

    for col in ['Open', 'High', 'Low', 'Close']:
        df[col] = df[col].astype(float)

    return df[['Open', 'High', 'Low', 'Close']]


if __name__ == "__main__":
    print("Testing HELD FVG logic on last 7 days...")

    # Last 7 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)

    start_ts = int(start_date.timestamp() * 1000)
    end_ts = int(end_date.timestamp() * 1000)

    print(f"Fetching 4H data from {start_date.date()} to {end_date.date()}...")
    df_4h = fetch_binance_data("BTCUSDT", "4h", start_ts, end_ts)

    print(f"Got {len(df_4h)} 4H candles")

    # Detect FVGs
    print("\nDetecting 4H FVGs...")
    fvgs = detect_fvg(df_4h, 0, len(df_4h))

    print(f"\nFound {len(fvgs)} 4H FVGs\n")

    # Show first 10
    for i, fvg in enumerate(fvgs[:10], 1):
        print(f"{i}. {fvg['type']} FVG @ {fvg['time']}: ${fvg['bottom']:.0f} - ${fvg['top']:.0f}")

    # Now test HOLD logic
    print(f"\n{'='*60}")
    print("Testing HOLD detection...")
    print(f"{'='*60}\n")

    held_count = 0
    rejected_count = 0

    for fvg in fvgs:
        fvg_idx = fvg['index']
        entered = False
        held = False

        # Check subsequent candles
        for i in range(fvg_idx + 1, min(fvg_idx + 20, len(df_4h))):
            candle = df_4h.iloc[i]

            # Check if touched
            touched = not (candle['High'] < fvg['bottom'] or candle['Low'] > fvg['top'])

            if not touched:
                continue

            if not entered:
                entered = True
                print(f"\n{fvg['type']} FVG @ {fvg['time']} ENTERED on {candle.name}")
                print(f"  FVG zone: ${fvg['bottom']:.0f} - ${fvg['top']:.0f}")
                print(f"  Candle: H=${candle['High']:.0f}, L=${candle['Low']:.0f}, C=${candle['Close']:.0f}")

            # Check HOLD (opposite of rejection)
            if fvg['type'] == 'BULLISH':
                # Bullish HOLD = close >= bottom
                if candle['Close'] >= fvg['bottom']:
                    if not held:
                        held = True
                        held_count += 1
                        print(f"  ✅ HELD! Close ${candle['Close']:.0f} >= Bottom ${fvg['bottom']:.0f}")
                        print(f"  → LONG signal (price continued up)")
                        break
                else:
                    # Rejected
                    rejected_count += 1
                    print(f"  ❌ REJECTED! Close ${candle['Close']:.0f} < Bottom ${fvg['bottom']:.0f}")
                    break

            else:  # BEARISH
                # Bearish HOLD = close <= top
                if candle['Close'] <= fvg['top']:
                    if not held:
                        held = True
                        held_count += 1
                        print(f"  ✅ HELD! Close ${candle['Close']:.0f} <= Top ${fvg['top']:.0f}")
                        print(f"  → SHORT signal (price continued down)")
                        break
                else:
                    # Rejected
                    rejected_count += 1
                    print(f"  ❌ REJECTED! Close ${candle['Close']:.0f} > Top ${fvg['top']:.0f}")
                    break

    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"Total FVGs: {len(fvgs)}")
    print(f"Held: {held_count}")
    print(f"Rejected: {rejected_count}")
    print(f"Neither (not touched or still active): {len(fvgs) - held_count - rejected_count}")
    print(f"{'='*60}")
