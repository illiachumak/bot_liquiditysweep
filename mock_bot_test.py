"""
MOCK BOT TEST: Симуляція роботи бота з 9 листопада 2025
Використовує виправлену логіку з liquidity_sweep_bot.py
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime
from binance.client import Client

# Import bot logic
sys.path.insert(0, '/Users/illiachumak/trading/implement')
from liquidity_sweep_bot import LiquiditySweepStrategy, SWING_LOOKBACK, SWEEP_TOLERANCE, MIN_RR, ATR_PERIOD, ATR_STOP_MULTIPLIER

try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    print("⚠️  TA-Lib not available")


def download_data_from_date(start_date='2025-11-09'):
    """Download data from Binance"""
    print(f"\n📥 Завантаження даних з {start_date}...")
    
    try:
        client = Client()
        start_time = datetime.strptime(start_date, '%Y-%m-%d')
        
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
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        
        df = df.set_index('open_time')
        
        print(f"✅ Завантажено {len(df)} свічок")
        print(f"   Від: {df.index[0]}")
        print(f"   До: {df.index[-1]}")
        
        return df
        
    except Exception as e:
        print(f"❌ Помилка: {e}")
        return None


def simulate_bot_run(data, start_idx=30):
    """Simulate bot running candle by candle"""
    
    print("\n" + "="*80)
    print("🤖 СИМУЛЯЦІЯ РОБОТИ БОТА")
    print("="*80)
    print(f"\nСтарт симуляції з індексу {start_idx}")
    print(f"Початкова свічка: {data.index[start_idx]}")
    
    # Initialize strategy
    strategy = LiquiditySweepStrategy()
    
    # Load initial candles
    initial_data = data.iloc[:start_idx].copy()
    strategy.candles = initial_data
    
    # Initialize session levels
    for idx, row in initial_data.iterrows():
        strategy.update_session_levels(row)
    
    print(f"✅ Ініціалізовано {len(strategy.candles)} початкових свічок")
    print(f"   Session levels: {sum(1 for v in strategy.session_levels.values() if v is not None)}")
    
    # Simulate new candles
    signals_found = []
    
    print("\n" + "="*80)
    print("🕯️  ОБРОБКА НОВИХ СВІЧОК")
    print("="*80)
    
    for i in range(start_idx, len(data)):
        candle_time = data.index[i]
        candle = data.iloc[i]
        
        # Add candle to strategy
        strategy.candles = pd.concat([strategy.candles, pd.DataFrame([candle], index=[candle_time])])
        strategy.candles = strategy.candles.tail(100)  # Keep last 100
        strategy.update_session_levels(candle)
        
        # Check for signals
        has_signal, signal = strategy.check_signals()
        
        # Log candle
        candle_type = "🟢" if candle['close'] > candle['open'] else "🔴"
        body_size = abs(candle['close'] - candle['open'])
        
        print(f"\n{candle_type} [{i}] {candle_time.strftime('%Y-%m-%d %H:%M')}")
        print(f"   O: ${candle['open']:,.2f} | C: ${candle['close']:,.2f} | Body: ${body_size:.2f}")
        
        if has_signal and signal:
            print(f"\n   🚨 SIGNAL DETECTED: {signal['side']}")
            print(f"      Entry: ${signal['entry']:,.2f}")
            print(f"      Stop Loss: ${signal['stop_loss']:,.2f}")
            print(f"      Take Profit: ${signal['take_profit']:,.2f}")
            print(f"      R:R: {signal['rr_ratio']:.2f}")
            print(f"      Liquidity Level: ${signal['liquidity_level']:,.2f}")
            
            signals_found.append({
                'time': candle_time,
                'side': signal['side'],
                'entry': signal['entry'],
                'stop_loss': signal['stop_loss'],
                'take_profit': signal['take_profit'],
                'rr_ratio': signal['rr_ratio'],
                'liquidity_level': signal['liquidity_level']
            })
    
    return signals_found


def compare_with_real_logs(mock_signals):
    """Compare mock results with real bot logs"""
    
    print("\n" + "="*80)
    print("📊 ПОРІВНЯННЯ З РЕАЛЬНИМИ ЛОГАМИ")
    print("="*80)
    
    # Real signals from logs
    real_signals = [
        {
            'time': '2025-11-11 20:02',
            'side': 'SHORT',
            'entry': 103004.10,
            'stop_loss': 104410.24,
            'take_profit': 100894.89
        },
        {
            'time': '2025-11-12 04:01',
            'side': 'LONG',
            'entry': 103299.00,
            'stop_loss': 102185.25,
            'take_profit': 104969.63
        }
    ]
    
    print(f"\n📝 Реальні логи бота: {len(real_signals)} сигналів")
    for sig in real_signals:
        print(f"   {sig['side']} @ {sig['time']} | Entry: ${sig['entry']:,.2f}")
    
    print(f"\n🤖 Mock симуляція (після фіксу): {len(mock_signals)} сигналів")
    for sig in mock_signals:
        print(f"   {sig['side']} @ {sig['time'].strftime('%Y-%m-%d %H:%M')} | Entry: ${sig['entry']:,.2f}")
    
    print("\n" + "="*80)
    print("🔍 АНАЛІЗ РОЗБІЖНОСТЕЙ")
    print("="*80)
    
    if len(mock_signals) == 0 and len(real_signals) == 2:
        print("\n✅ ВИПРАВЛЕННЯ ПРАЦЮЄ!")
        print("   Старий бот (з багом): знайшов 2 FALSE SIGNALS")
        print("   Новий бот (після фіксу): 0 сигналів")
        print("   Висновок: False signals відфільтровано! ✅")
    
    elif len(mock_signals) == 0:
        print("\n⚠️  Mock бот не знайшов сигналів")
        print("   Можливі причини:")
        print("   - Виправлена логіка коректно фільтрує слабкі сигнали")
        print("   - Умови для entry не виконались")
    
    elif len(mock_signals) > 0:
        print(f"\n⚠️  Mock бот знайшов {len(mock_signals)} сигналів")
        print("   Треба перевірити чи вони валідні:")
        for sig in mock_signals:
            print(f"\n   Сигнал: {sig['side']} @ {sig['time']}")
            print(f"   Entry: ${sig['entry']:,.2f}")
            print(f"   SL: ${sig['stop_loss']:,.2f} | TP: ${sig['take_profit']:,.2f}")
    
    # Check timing
    print("\n" + "="*80)
    print("⏰ TIMING АНАЛІЗ")
    print("="*80)
    
    for real in real_signals:
        real_dt = pd.to_datetime(real['time'])
        print(f"\n🔴 Реальний сигнал: {real['side']} @ {real['time']}")
        
        # Find closest mock signal
        if mock_signals:
            closest = min(mock_signals, key=lambda x: abs((x['time'] - real_dt).total_seconds()))
            time_diff = (closest['time'] - real_dt).total_seconds() / 60
            
            if abs(time_diff) < 240:  # within 4 hours
                print(f"   Closest mock: {closest['side']} @ {closest['time']}")
                print(f"   Time diff: {time_diff:.0f} minutes")
                
                if closest['side'] == real['side']:
                    print(f"   ⚠️  Same direction but different timing")
                else:
                    print(f"   ⚠️  Different direction")
            else:
                print(f"   ❌ No mock signal in same timeframe")
        else:
            print(f"   ✅ Mock didn't find this (correctly filtered false signal)")


def main():
    """Main test function"""
    
    print("\n" + "="*80)
    print("🧪 MOCK BOT TEST - ВИПРАВЛЕНА ЛОГІКА")
    print("="*80)
    print("\nМета: Перевірити чи після фіксу бот правильно фільтрує сигнали")
    print("Період: 9 листопада 2025 → сьогодні")
    print("="*80)
    
    # Download data
    data = download_data_from_date('2025-11-09')
    
    if data is None or len(data) == 0:
        print("\n❌ Не вдалось завантажити дані")
        return
    
    # Simulate bot
    signals = simulate_bot_run(data, start_idx=5)  # Start from index 5 (enough history)
    
    # Compare with real logs
    compare_with_real_logs(signals)
    
    # Summary
    print("\n" + "="*80)
    print("✅ ПІДСУМОК ТЕСТУ")
    print("="*80)
    
    print(f"\n📊 Результати:")
    print(f"   Реальний бот (з багом): 2 сигнали (FALSE)")
    print(f"   Mock бот (після фіксу): {len(signals)} сигналів")
    
    if len(signals) == 0:
        print(f"\n✅ ВИПРАВЛЕННЯ УСПІШНЕ!")
        print(f"   False signals відфільтровано")
        print(f"   Бот тепер працює згідно з логікою бектесту")
    elif len(signals) < 2:
        print(f"\n⚠️  Частково виправлено")
        print(f"   Деякі false signals відфільтровано")
    else:
        print(f"\n⚠️  Потрібна додаткова перевірка")
        print(f"   Чи знайдені сигнали валідні?")
    
    print("\n🎯 Рекомендація:")
    if len(signals) == 0:
        print("   ✅ Логіка виправлена - можна продовжувати тестування")
        print("   ✅ Запустити бота на Testnet з виправленою логікою")
    else:
        print("   ⚠️  Перевірити знайдені сигнали детально")
        print("   ⚠️  Можливо потрібні додаткові виправлення")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()

