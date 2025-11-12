"""
VERIFICATION: Перевірка сигналів які знайшов бот в реальному часі
Завантажує дані з Binance та валідує сигнали через логіку бектесту
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from binance.client import Client

# TA-Lib з fallback
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    print("⚠️  TA-Lib not available, using pandas-based ATR calculation")

# Strategy parameters
SWING_LOOKBACK = 5
SWEEP_TOLERANCE = 0.001
MIN_RR = 1.5
ATR_PERIOD = 14
ATR_STOP_MULTIPLIER = 1.5

ASIAN_SESSION = (0, 8)
LONDON_SESSION = (8, 13)
NY_SESSION = (13, 20)

# Detected signals from bot logs
DETECTED_SIGNALS = [
    {
        'time': '2025-11-11 20:02',
        'side': 'SHORT',
        'entry': 103004.10,
        'stop_loss': 104410.24,
        'take_profit': 100894.89,
        'rr_ratio': 1.50,
        'liquidity_level': 105260.00
    },
    {
        'time': '2025-11-12 04:01',
        'side': 'LONG',
        'entry': 103299.00,
        'stop_loss': 102185.25,
        'take_profit': 104969.63,
        'rr_ratio': 1.50,
        'liquidity_level': 103009.60
    }
]


def calculate_atr_pandas(high, low, close, period=14):
    """Calculate ATR using pandas"""
    high_low = high - low
    high_close = np.abs(high - close.shift())
    low_close = np.abs(low - close.shift())
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.ewm(span=period, adjust=False).mean()
    
    return atr


def download_data(symbol='BTCUSDT', interval='4h', start_date='2025-11-01'):
    """Download data from Binance"""
    print(f"\n📥 Завантаження даних з Binance...")
    print(f"   Symbol: {symbol}")
    print(f"   Interval: {interval}")
    print(f"   Start: {start_date}")
    
    try:
        client = Client()
        
        start_time = datetime.strptime(start_date, '%Y-%m-%d')
        
        klines = client.futures_klines(
            symbol=symbol,
            interval=interval,
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
            'open': 'Open',
            'high': 'High',
            'low': 'Low',
            'close': 'Close',
            'volume': 'Volume'
        })
        
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        
        print(f"✅ Завантажено {len(df)} свічок")
        print(f"   Період: {df.index[0]} - {df.index[-1]}")
        
        return df
        
    except Exception as e:
        print(f"❌ Помилка завантаження: {e}")
        return None


def get_session(hour):
    """Get current session"""
    if ASIAN_SESSION[0] <= hour < ASIAN_SESSION[1]:
        return 'ASIAN'
    elif LONDON_SESSION[0] <= hour < LONDON_SESSION[1]:
        return 'LONDON'
    elif NY_SESSION[0] <= hour < NY_SESSION[1]:
        return 'NY'
    return None


def calculate_session_levels(data, target_date):
    """Calculate session levels for a specific date"""
    day_data = data[data.index.date == target_date.date()]
    
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
    
    return session_levels


def check_signal_at_time(data, signal_time, session_levels):
    """Check if signal should be detected at specific time"""
    signal_dt = pd.to_datetime(signal_time)
    
    # Find candle at signal time
    candle_idx = data.index.get_indexer([signal_dt], method='nearest')[0]
    
    if candle_idx < 3 or candle_idx < ATR_PERIOD:
        return None, "Недостатньо даних"
    
    current = data.iloc[candle_idx]
    recent_3 = data.iloc[candle_idx-2:candle_idx+1]
    
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
    
    if pd.isna(atr) or atr == 0:
        return None, "ATR не розраховано"
    
    recent_high = recent_3['High'].max()
    recent_low = recent_3['Low'].min()
    
    # Get liquidity levels
    liq_highs = [v for k, v in session_levels.items() if 'high' in k]
    liq_lows = [v for k, v in session_levels.items() if 'low' in k]
    
    if not liq_highs or not liq_lows:
        return None, "Session levels не сформовані"
    
    signals = []
    
    # Check LONG signals
    for liq_low in liq_lows:
        if recent_low <= liq_low * (1 + SWEEP_TOLERANCE):
            # Check bullish reversal
            curr_bullish = current['Close'] > current['Open']
            if candle_idx >= 2:
                previous = data.iloc[candle_idx-1]
                strong_body = abs(current['Close'] - current['Open']) > abs(previous['Close'] - previous['Open'])
            else:
                strong_body = True
            
            recent_candle_low = recent_3['Low'].min()
            back_above = current['Close'] > recent_candle_low
            
            if curr_bullish and back_above and strong_body:
                entry = current['Close']
                stop_loss = entry - (atr * ATR_STOP_MULTIPLIER)
                
                valid_highs = [h for h in liq_highs if h > entry]
                if valid_highs:
                    take_profit = min(valid_highs)
                else:
                    take_profit = entry + (entry - stop_loss) * MIN_RR
                
                risk = entry - stop_loss
                reward = take_profit - entry
                
                if risk > 0 and reward > 0 and (reward / risk) >= MIN_RR:
                    signals.append({
                        'side': 'LONG',
                        'entry': entry,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'rr_ratio': reward / risk,
                        'liquidity_level': liq_low,
                        'atr': atr
                    })
    
    # Check SHORT signals
    for liq_high in liq_highs:
        if recent_high >= liq_high * (1 - SWEEP_TOLERANCE):
            # Check bearish reversal
            curr_bearish = current['Close'] < current['Open']
            if candle_idx >= 2:
                previous = data.iloc[candle_idx-1]
                strong_body = abs(current['Close'] - current['Open']) > abs(previous['Close'] - previous['Open'])
            else:
                strong_body = True
            
            recent_candle_high = recent_3['High'].max()
            back_below = current['Close'] < recent_candle_high
            
            if curr_bearish and back_below and strong_body:
                entry = current['Close']
                stop_loss = entry + (atr * ATR_STOP_MULTIPLIER)
                
                valid_lows = [l for l in liq_lows if l < entry]
                if valid_lows:
                    take_profit = max(valid_lows)
                else:
                    take_profit = entry - (stop_loss - entry) * MIN_RR
                
                risk = stop_loss - entry
                reward = entry - take_profit
                
                if risk > 0 and reward > 0 and (reward / risk) >= MIN_RR:
                    signals.append({
                        'side': 'SHORT',
                        'entry': entry,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'rr_ratio': reward / risk,
                        'liquidity_level': liq_high,
                        'atr': atr
                    })
    
    return signals, "OK"


def check_trade_outcome(data, signal, signal_time):
    """Check what happened after signal"""
    signal_dt = pd.to_datetime(signal_time)
    future_data = data[data.index > signal_dt].head(20)  # Check next 20 candles
    
    if len(future_data) == 0:
        return None, "Немає даних для перевірки"
    
    entry = signal['entry']
    stop_loss = signal['stop_loss']
    take_profit = signal['take_profit']
    side = signal['side']
    
    for idx, candle in future_data.iterrows():
        if side == 'LONG':
            # Check SL
            if candle['Low'] <= stop_loss:
                return {
                    'exit_time': idx,
                    'exit_price': stop_loss,
                    'exit_reason': 'STOP_LOSS',
                    'pnl_pct': ((stop_loss - entry) / entry) * 100,
                    'duration_hours': (idx - signal_dt).total_seconds() / 3600,
                    'win': False
                }, "Спрацював Stop Loss"
            
            # Check TP
            if candle['High'] >= take_profit:
                return {
                    'exit_time': idx,
                    'exit_price': take_profit,
                    'exit_reason': 'TAKE_PROFIT',
                    'pnl_pct': ((take_profit - entry) / entry) * 100,
                    'duration_hours': (idx - signal_dt).total_seconds() / 3600,
                    'win': True
                }, "Спрацював Take Profit"
        
        else:  # SHORT
            # Check SL
            if candle['High'] >= stop_loss:
                return {
                    'exit_time': idx,
                    'exit_price': stop_loss,
                    'exit_reason': 'STOP_LOSS',
                    'pnl_pct': ((entry - stop_loss) / entry) * 100,
                    'duration_hours': (idx - signal_dt).total_seconds() / 3600,
                    'win': False
                }, "Спрацював Stop Loss"
            
            # Check TP
            if candle['Low'] <= take_profit:
                return {
                    'exit_time': idx,
                    'exit_price': take_profit,
                    'exit_reason': 'TAKE_PROFIT',
                    'pnl_pct': ((entry - take_profit) / entry) * 100,
                    'duration_hours': (idx - signal_dt).total_seconds() / 3600,
                    'win': True
                }, "Спрацював Take Profit"
    
    # Still open
    last_candle = future_data.iloc[-1]
    current_price = last_candle['Close']
    
    if side == 'LONG':
        pnl_pct = ((current_price - entry) / entry) * 100
    else:
        pnl_pct = ((entry - current_price) / entry) * 100
    
    return {
        'exit_time': last_candle.name,
        'exit_price': current_price,
        'exit_reason': 'STILL_OPEN',
        'pnl_pct': pnl_pct,
        'duration_hours': (last_candle.name - signal_dt).total_seconds() / 3600,
        'win': pnl_pct > 0
    }, "Позиція ще відкрита"


def main():
    """Main verification function"""
    print("\n" + "="*80)
    print("🔍 VERIFICATION: Перевірка Сигналів з Логів Бота")
    print("="*80)
    
    # Download data
    data = download_data('BTCUSDT', '4h', '2025-11-01')
    
    if data is None or len(data) == 0:
        print("\n❌ Не вдалось завантажити дані")
        return
    
    print("\n" + "="*80)
    print("📊 ПЕРЕВІРКА СИГНАЛІВ")
    print("="*80)
    
    for i, detected in enumerate(DETECTED_SIGNALS, 1):
        print(f"\n{'='*80}")
        print(f"🚨 SIGNAL #{i}: {detected['side']} @ {detected['time']}")
        print(f"{'='*80}")
        
        print(f"\n📝 З логів бота:")
        print(f"   Entry: ${detected['entry']:,.2f}")
        print(f"   Stop Loss: ${detected['stop_loss']:,.2f}")
        print(f"   Take Profit: ${detected['take_profit']:,.2f}")
        print(f"   R:R: {detected['rr_ratio']:.2f}")
        print(f"   Liquidity Level: ${detected['liquidity_level']:,.2f}")
        
        # Calculate session levels for that day
        signal_time = pd.to_datetime(detected['time'])
        
        # Get session levels from previous day too
        prev_day = signal_time - timedelta(days=1)
        session_levels_prev = calculate_session_levels(data, prev_day)
        session_levels_curr = calculate_session_levels(data, signal_time)
        
        # Merge session levels
        session_levels = {**session_levels_prev, **session_levels_curr}
        
        print(f"\n🌍 Session Levels на {signal_time.date()}:")
        for key, value in session_levels.items():
            if value is not None:
                print(f"   {key}: ${value:,.2f}")
        
        # Verify signal
        print(f"\n🔍 Перевірка через логіку бектесту...")
        signals, status = check_signal_at_time(data, detected['time'], session_levels)
        
        if signals is None:
            print(f"   ❌ Сигнал НЕ підтверджено: {status}")
        elif len(signals) == 0:
            print(f"   ❌ Сигнал НЕ знайдено логікою бектесту")
            print(f"   Статус: {status}")
        else:
            # Find matching signal
            matching = None
            for sig in signals:
                if sig['side'] == detected['side']:
                    matching = sig
                    break
            
            if matching:
                print(f"   ✅ СИГНАЛ ПІДТВЕРДЖЕНО!")
                print(f"\n   Розрахунок бектесту:")
                print(f"   Entry: ${matching['entry']:,.2f}")
                print(f"   Stop Loss: ${matching['stop_loss']:,.2f}")
                print(f"   Take Profit: ${matching['take_profit']:,.2f}")
                print(f"   R:R: {matching['rr_ratio']:.2f}")
                print(f"   ATR: ${matching['atr']:,.2f}")
                
                # Compare
                entry_diff = abs(matching['entry'] - detected['entry'])
                sl_diff = abs(matching['stop_loss'] - detected['stop_loss'])
                tp_diff = abs(matching['take_profit'] - detected['take_profit'])
                
                print(f"\n   📊 Різниця (бектест vs бот):")
                print(f"   Entry: ${entry_diff:.2f}")
                print(f"   SL: ${sl_diff:.2f}")
                print(f"   TP: ${tp_diff:.2f}")
                
                if entry_diff < 10 and sl_diff < 50 and tp_diff < 50:
                    print(f"   ✅ Параметри співпадають!")
                else:
                    print(f"   ⚠️  Є відмінності в параметрах")
                
                # Check outcome
                print(f"\n   📈 ЩО СТАЛОСЬ ДАЛІ:")
                outcome, outcome_status = check_trade_outcome(data, matching, detected['time'])
                
                if outcome:
                    if outcome['exit_reason'] == 'STILL_OPEN':
                        status_emoji = "⏳"
                        status_text = "ВІДКРИТА"
                    elif outcome['win']:
                        status_emoji = "✅"
                        status_text = "WIN"
                    else:
                        status_emoji = "❌"
                        status_text = "LOSS"
                    
                    print(f"   {status_emoji} {status_text} | {outcome['exit_reason']}")
                    print(f"   Exit Time: {outcome['exit_time'].strftime('%Y-%m-%d %H:%M')}")
                    print(f"   Exit Price: ${outcome['exit_price']:,.2f}")
                    print(f"   PnL: {outcome['pnl_pct']:+.2f}%")
                    print(f"   Duration: {outcome['duration_hours']:.1f} hours")
                else:
                    print(f"   ⚠️  {outcome_status}")
            else:
                print(f"   ⚠️  Знайдено інші сигнали, але не {detected['side']}")
                for sig in signals:
                    print(f"   - {sig['side']} @ ${sig['entry']:,.2f}")
    
    # Summary
    print("\n" + "="*80)
    print("✅ ПІДСУМОК ВЕРИФІКАЦІЇ")
    print("="*80)
    
    print(f"\nВсього сигналів з логів: {len(DETECTED_SIGNALS)}")
    print(f"\n💡 Висновок:")
    print(f"   Якщо сигнали підтверджені - бот працює правильно")
    print(f"   Якщо є розбіжності - потрібно перевірити логіку")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()

