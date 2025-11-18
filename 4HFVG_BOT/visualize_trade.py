"""
Візуалізація трейду з candlestick графіками
"""
import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf
from datetime import datetime, timedelta
import json
from binance.client import Client
import os
from dotenv import load_dotenv

load_dotenv()

# Binance API
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
client = Client(API_KEY, API_SECRET)

# Trade details (setup_197)
TRADE = {
    'direction': 'SHORT',
    'entry_time': '2024-12-19T16:45:00',
    'entry_price': 100360.0,
    'exit_time': '2024-12-20T12:00:00',
    'exit_price': 92422.87,
    'sl': 103005.71,
    'tp': 92422.87,
    'size': 3.386
}

def get_klines(symbol, interval, start_str, end_str):
    """Fetch klines from Binance"""
    klines = client.get_historical_klines(
        symbol, interval, start_str, end_str
    )

    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])

    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)

    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

    return df

def detect_fvg(df, idx):
    """Detect FVG at index"""
    if idx < 2:
        return None

    row = df.iloc[idx]
    row_i2 = df.iloc[idx-2]

    # Bullish FVG
    if row['low'] > row_i2['high']:
        return {
            'type': 'BULLISH',
            'top': row['low'],
            'bottom': row_i2['high'],
            'time': row.name
        }

    # Bearish FVG
    elif row['high'] < row_i2['low']:
        return {
            'type': 'BEARISH',
            'top': row_i2['low'],
            'bottom': row['high'],
            'time': row.name
        }

    return None

def plot_4h_rejection(df_4h, rejected_fvg):
    """Plot 4H chart with rejected FVG"""
    fig, ax = plt.subplots(figsize=(16, 9))

    # Plot candlesticks
    mpf.plot(df_4h, type='candle', style='charles', ax=ax, volume=False)

    # Draw FVG zone
    ax.axhspan(rejected_fvg['bottom'], rejected_fvg['top'],
               alpha=0.3, color='red' if rejected_fvg['type'] == 'BULLISH' else 'green',
               label=f"{rejected_fvg['type']} FVG (REJECTED)")

    # Annotations
    ax.set_title(f"Step 1: 4H {rejected_fvg['type']} FVG REJECTED → {'SHORT' if rejected_fvg['type'] == 'BULLISH' else 'LONG'} Signal",
                 fontsize=16, fontweight='bold')
    ax.set_ylabel('Price (USDT)', fontsize=12)
    ax.legend(loc='upper left', fontsize=12)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('4h_rejection.png', dpi=150, bbox_inches='tight')
    print("✅ Saved: 4h_rejection.png")
    plt.close()

def plot_15m_entry(df_15m, entry_time, entry_price, fvg_15m):
    """Plot 15M chart with entry setup"""
    fig, ax = plt.subplots(figsize=(16, 9))

    # Plot candlesticks
    mpf.plot(df_15m, type='candle', style='charles', ax=ax, volume=False)

    # Draw 15M FVG zone
    if fvg_15m:
        ax.axhspan(fvg_15m['bottom'], fvg_15m['top'],
                   alpha=0.3, color='green' if fvg_15m['type'] == 'BEARISH' else 'red',
                   label=f"15M {fvg_15m['type']} FVG")

    # Entry line
    ax.axhline(entry_price, color='blue', linestyle='--', linewidth=2, label=f'Entry: ${entry_price:,.0f}')

    # Entry marker
    entry_idx = df_15m.index.get_indexer([pd.Timestamp(entry_time)], method='nearest')[0]
    ax.scatter(entry_idx, entry_price, color='blue', s=200, marker='v', zorder=5, label='Entry Point')

    ax.set_title("Step 2: 15M Entry Setup - Limit Order Placed", fontsize=16, fontweight='bold')
    ax.set_ylabel('Price (USDT)', fontsize=12)
    ax.legend(loc='upper left', fontsize=12)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('15m_entry.png', dpi=150, bbox_inches='tight')
    print("✅ Saved: 15m_entry.png")
    plt.close()

def plot_trade_execution(df_15m, trade):
    """Plot trade execution with SL and TP"""
    fig, ax = plt.subplots(figsize=(16, 9))

    # Plot candlesticks
    mpf.plot(df_15m, type='candle', style='charles', ax=ax, volume=False)

    # Entry, SL, TP lines
    ax.axhline(trade['entry_price'], color='blue', linestyle='--', linewidth=2, label=f"Entry: ${trade['entry_price']:,.0f}")
    ax.axhline(trade['sl'], color='red', linestyle='--', linewidth=2, label=f"SL: ${trade['sl']:,.0f}")
    ax.axhline(trade['tp'], color='green', linestyle='--', linewidth=2, label=f"TP: ${trade['tp']:,.0f}")

    # Entry and exit markers
    entry_idx = df_15m.index.get_indexer([pd.Timestamp(trade['entry_time'])], method='nearest')[0]
    exit_idx = df_15m.index.get_indexer([pd.Timestamp(trade['exit_time'])], method='nearest')[0]

    ax.scatter(entry_idx, trade['entry_price'], color='blue', s=200, marker='v', zorder=5, label='Entry')
    ax.scatter(exit_idx, trade['exit_price'], color='green', s=200, marker='^', zorder=5, label='Exit (TP)')

    # Calculate PnL
    pnl = (trade['entry_price'] - trade['exit_price']) * trade['size']
    pnl_pct = ((trade['entry_price'] - trade['exit_price']) / trade['entry_price']) * 100

    ax.set_title(f"Step 3: Trade Execution - PnL: ${pnl:,.2f} (+{pnl_pct:.2f}%)",
                 fontsize=16, fontweight='bold', color='green')
    ax.set_ylabel('Price (USDT)', fontsize=12)
    ax.legend(loc='upper right', fontsize=12)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('trade_execution.png', dpi=150, bbox_inches='tight')
    print("✅ Saved: trade_execution.png")
    plt.close()

def main():
    print("\n" + "="*80)
    print("ВІЗУАЛІЗАЦІЯ ТРЕЙДУ setup_197 (SHORT)")
    print("="*80 + "\n")

    # Fetch 4H data
    print("📊 Завантаження 4H даних...")
    start_4h = (pd.Timestamp(TRADE['entry_time']) - timedelta(days=10)).strftime('%Y-%m-%d')
    end_4h = (pd.Timestamp(TRADE['entry_time']) + timedelta(days=2)).strftime('%Y-%m-%d')
    df_4h = get_klines('BTCUSDT', '4h', start_4h, end_4h)
    print(f"   Завантажено {len(df_4h)} 4H свічок")

    # Fetch 15M data
    print("📊 Завантаження 15M даних...")
    start_15m = (pd.Timestamp(TRADE['entry_time']) - timedelta(days=2)).strftime('%Y-%m-%d')
    end_15m = (pd.Timestamp(TRADE['exit_time']) + timedelta(hours=12)).strftime('%Y-%m-%d')
    df_15m = get_klines('BTCUSDT', '15m', start_15m, end_15m)
    print(f"   Завантажено {len(df_15m)} 15M свічок\n")

    # Find rejected 4H FVG (simulate detection)
    print("🔍 Шукаємо rejected 4H FVG...")
    rejected_fvg = None

    # Look backwards from entry time to find a rejected bullish FVG (for SHORT setup)
    entry_time = pd.Timestamp(TRADE['entry_time'])
    df_4h_before = df_4h[df_4h.index <= entry_time]

    for i in range(len(df_4h_before)-1, 2, -1):
        fvg = detect_fvg(df_4h_before, i)
        if fvg and fvg['type'] == 'BULLISH':
            # Check if rejected (price closed below)
            for j in range(i+1, len(df_4h_before)):
                if df_4h_before.iloc[j]['close'] < fvg['bottom']:
                    rejected_fvg = fvg
                    print(f"   ✅ Знайдено: {fvg['type']} FVG ${fvg['bottom']:.0f}-${fvg['top']:.0f}")
                    print(f"   🚫 REJECTED на {df_4h_before.index[j]}")
                    break
            if rejected_fvg:
                break

    if not rejected_fvg:
        print("   ⚠️  Використовую наближені значення для демонстрації")
        rejected_fvg = {
            'type': 'BULLISH',
            'top': 102000,
            'bottom': 100500,
            'time': entry_time - timedelta(days=1)
        }

    # Find 15M FVG near entry
    print("\n🔍 Шукаємо 15M FVG для входу...")
    fvg_15m = None
    df_15m_entry = df_15m[(df_15m.index >= entry_time - timedelta(hours=4)) &
                          (df_15m.index <= entry_time)]

    for i in range(len(df_15m_entry)-1, 2, -1):
        fvg = detect_fvg(df_15m_entry, i)
        if fvg and fvg['type'] == 'BEARISH':
            fvg_15m = fvg
            print(f"   ✅ Знайдено: {fvg['type']} FVG ${fvg['bottom']:.0f}-${fvg['top']:.0f}")
            break

    # Plot Step 1: 4H Rejection
    print("\n📈 Створення графіка Step 1: 4H Rejection...")
    df_4h_plot = df_4h[(df_4h.index >= entry_time - timedelta(days=7)) &
                       (df_4h.index <= entry_time + timedelta(days=1))]
    plot_4h_rejection(df_4h_plot, rejected_fvg)

    # Plot Step 2: 15M Entry
    print("📈 Створення графіка Step 2: 15M Entry...")
    df_15m_plot = df_15m[(df_15m.index >= entry_time - timedelta(hours=12)) &
                         (df_15m.index <= entry_time + timedelta(hours=4))]
    plot_15m_entry(df_15m_plot, TRADE['entry_time'], TRADE['entry_price'], fvg_15m)

    # Plot Step 3: Trade Execution
    print("📈 Створення графіка Step 3: Trade Execution...")
    df_15m_exec = df_15m[(df_15m.index >= entry_time - timedelta(hours=4)) &
                         (df_15m.index <= pd.Timestamp(TRADE['exit_time']) + timedelta(hours=4))]
    plot_trade_execution(df_15m_exec, TRADE)

    print("\n" + "="*80)
    print("✅ ВІЗУАЛІЗАЦІЯ ЗАВЕРШЕНА!")
    print("="*80)
    print("\nСтворені файли:")
    print("  1. 4h_rejection.png     - Step 1: 4H FVG Rejection")
    print("  2. 15m_entry.png        - Step 2: 15M Entry Setup")
    print("  3. trade_execution.png  - Step 3: Trade Execution")
    print()

if __name__ == '__main__':
    main()
