"""
BACKTEST: Liquidity Sweep Bot - November 2025
Завантажує актуальні дані з Binance і перевіряє які трейди мали виконатись
"""

import pandas as pd
import numpy as np
import sys
from datetime import datetime, timedelta
from binance.client import Client

# TA-Lib з fallback
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    print("⚠️  TA-Lib not available, using pandas-based ATR calculation")

# Strategy parameters (from liquidity_sweep_bot.py)
SWING_LOOKBACK = 5
SWEEP_TOLERANCE = 0.001  # 0.1%
MIN_RR = 1.5
ATR_PERIOD = 14
ATR_STOP_MULTIPLIER = 1.5

# Sessions (UTC)
ASIAN_SESSION = (0, 8)
LONDON_SESSION = (8, 13)
NY_SESSION = (13, 20)

TIMEFRAME = '4h'
SYMBOL = 'BTCUSDT'
RISK_PER_TRADE = 2.0  # %


def calculate_atr_pandas(high, low, close, period=14):
    """Calculate ATR using pandas (fallback)"""
    high_low = high - low
    high_close = np.abs(high - close.shift())
    low_close = np.abs(low - close.shift())
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    atr = true_range.ewm(span=period, adjust=False).mean()
    
    return atr


def download_binance_data(symbol='BTCUSDT', interval='4h', days_back=60):
    """Download recent data from Binance"""
    print(f"\n📥 Завантаження даних з Binance...")
    print(f"   Symbol: {symbol}")
    print(f"   Interval: {interval}")
    print(f"   Period: {days_back} днів")
    
    try:
        # Public client (no API keys needed for market data)
        client = Client()
        
        # Calculate start time
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days_back)
        
        # Download klines
        klines = client.futures_klines(
            symbol=symbol,
            interval=interval,
            startTime=int(start_time.timestamp() * 1000),
            limit=1000
        )
        
        # Convert to DataFrame
        df = pd.DataFrame(klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        df = df.set_index('open_time')
        
        # Convert to float
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        
        # Rename columns to match backtesting format
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
        print(f"❌ Помилка завантаження даних: {e}")
        return None


class LiquiditySweepBacktest:
    """Backtest logic matching liquidity_sweep_bot.py"""
    
    def __init__(self, data, initial_balance=10000):
        self.data = data
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.position = None
        self.trades = []
        
        # Session levels
        self.session_levels = {
            'asian_high': None,
            'asian_low': None,
            'london_high': None,
            'london_low': None,
            'ny_high': None,
            'ny_low': None
        }
        self.current_date = None
        
        # Calculate ATR
        print("\n📊 Розрахунок індикаторів...")
        if TALIB_AVAILABLE:
            self.data['atr'] = talib.ATR(
                self.data['High'].values,
                self.data['Low'].values,
                self.data['Close'].values,
                ATR_PERIOD
            )
        else:
            self.data['atr'] = calculate_atr_pandas(
                self.data['High'],
                self.data['Low'],
                self.data['Close'],
                ATR_PERIOD
            )
        
        print(f"✅ ATR розраховано")
    
    def get_session(self, hour):
        """Get current session"""
        if ASIAN_SESSION[0] <= hour < ASIAN_SESSION[1]:
            return 'ASIAN'
        elif LONDON_SESSION[0] <= hour < LONDON_SESSION[1]:
            return 'LONDON'
        elif NY_SESSION[0] <= hour < NY_SESSION[1]:
            return 'NY'
        return None
    
    def update_session_levels(self, candle, timestamp):
        """Update session high/low levels"""
        current_date = timestamp.date()
        hour = timestamp.hour
        
        # Reset on new day
        if self.current_date != current_date:
            self.current_date = current_date
            self.session_levels = {k: None for k in self.session_levels}
        
        session = self.get_session(hour)
        
        if session == 'ASIAN':
            if self.session_levels['asian_high'] is None:
                self.session_levels['asian_high'] = candle['High']
                self.session_levels['asian_low'] = candle['Low']
            else:
                self.session_levels['asian_high'] = max(self.session_levels['asian_high'], candle['High'])
                self.session_levels['asian_low'] = min(self.session_levels['asian_low'], candle['Low'])
        
        elif session == 'LONDON':
            if self.session_levels['london_high'] is None:
                self.session_levels['london_high'] = candle['High']
                self.session_levels['london_low'] = candle['Low']
            else:
                self.session_levels['london_high'] = max(self.session_levels['london_high'], candle['High'])
                self.session_levels['london_low'] = min(self.session_levels['london_low'], candle['Low'])
        
        elif session == 'NY':
            if self.session_levels['ny_high'] is None:
                self.session_levels['ny_high'] = candle['High']
                self.session_levels['ny_low'] = candle['Low']
            else:
                self.session_levels['ny_high'] = max(self.session_levels['ny_high'], candle['High'])
                self.session_levels['ny_low'] = min(self.session_levels['ny_low'], candle['Low'])
    
    def find_swing_high(self, idx, lookback=SWING_LOOKBACK):
        """Find swing high"""
        if idx < lookback:
            return None
        highs = self.data['High'].iloc[idx-lookback:idx].values
        return float(np.max(highs)) if len(highs) > 0 else None
    
    def find_swing_low(self, idx, lookback=SWING_LOOKBACK):
        """Find swing low"""
        if idx < lookback:
            return None
        lows = self.data['Low'].iloc[idx-lookback:idx].values
        return float(np.min(lows)) if len(lows) > 0 else None
    
    def detect_bullish_reversal(self, idx):
        """Detect bullish reversal"""
        if idx < 3:
            return False
        
        recent = self.data.iloc[idx-3:idx+1]
        current = recent.iloc[-1]
        previous = recent.iloc[-2]
        
        curr_bullish = current['Close'] > current['Open']
        strong_body = abs(current['Close'] - current['Open']) > abs(previous['Close'] - previous['Open'])
        recent_low = recent['Low'].min()
        back_above = current['Close'] > recent_low
        
        return curr_bullish and back_above and strong_body
    
    def detect_bearish_reversal(self, idx):
        """Detect bearish reversal"""
        if idx < 3:
            return False
        
        recent = self.data.iloc[idx-3:idx+1]
        current = recent.iloc[-1]
        previous = recent.iloc[-2]
        
        curr_bearish = current['Close'] < current['Open']
        strong_body = abs(current['Close'] - current['Open']) > abs(previous['Close'] - previous['Open'])
        recent_high = recent['High'].max()
        back_below = current['Close'] < recent_high
        
        return curr_bearish and back_below and strong_body
    
    def calculate_position_size(self, entry, stop_loss):
        """Calculate position size based on risk"""
        risk_amount = self.balance * (RISK_PER_TRADE / 100)
        risk_per_unit = abs(entry - stop_loss)
        
        if risk_per_unit == 0:
            return 0
        
        position_size = risk_amount / risk_per_unit
        return position_size
    
    def check_signals(self, idx):
        """Check for entry signals"""
        if idx < ATR_PERIOD:
            return None
        
        if self.position is not None:
            return None
        
        current = self.data.iloc[idx]
        recent_3 = self.data.iloc[idx-2:idx+1]
        
        atr = current['atr']
        if pd.isna(atr) or atr == 0:
            return None
        
        recent_high = recent_3['High'].max()
        recent_low = recent_3['Low'].min()
        
        # Get session levels
        liq_highs = [v for v in [self.session_levels['asian_high'], 
                                  self.session_levels['london_high'],
                                  self.session_levels['ny_high']] if v is not None]
        
        liq_lows = [v for v in [self.session_levels['asian_low'],
                                 self.session_levels['london_low'],
                                 self.session_levels['ny_low']] if v is not None]
        
        if not liq_highs or not liq_lows:
            return None
        
        # CHECK LONG SIGNAL
        for liq_low in liq_lows:
            if recent_low <= liq_low * (1 + SWEEP_TOLERANCE):
                if self.detect_bullish_reversal(idx):
                    entry = current['Close']
                    stop_loss = entry - (atr * ATR_STOP_MULTIPLIER)
                    
                    # Find nearest high for TP
                    valid_highs = [h for h in liq_highs if h > entry]
                    if valid_highs:
                        take_profit = min(valid_highs)
                    else:
                        take_profit = entry + (entry - stop_loss) * MIN_RR
                    
                    risk = entry - stop_loss
                    reward = take_profit - entry
                    
                    if risk > 0 and reward > 0 and (reward / risk) >= MIN_RR:
                        return {
                            'side': 'LONG',
                            'entry': entry,
                            'stop_loss': stop_loss,
                            'take_profit': take_profit,
                            'rr_ratio': reward / risk,
                            'liquidity_level': liq_low,
                            'session': 'sweep_low'
                        }
        
        # CHECK SHORT SIGNAL
        for liq_high in liq_highs:
            if recent_high >= liq_high * (1 - SWEEP_TOLERANCE):
                if self.detect_bearish_reversal(idx):
                    entry = current['Close']
                    stop_loss = entry + (atr * ATR_STOP_MULTIPLIER)
                    
                    # Find nearest low for TP
                    valid_lows = [l for l in liq_lows if l < entry]
                    if valid_lows:
                        take_profit = max(valid_lows)
                    else:
                        take_profit = entry - (stop_loss - entry) * MIN_RR
                    
                    risk = stop_loss - entry
                    reward = entry - take_profit
                    
                    if risk > 0 and reward > 0 and (reward / risk) >= MIN_RR:
                        return {
                            'side': 'SHORT',
                            'entry': entry,
                            'stop_loss': stop_loss,
                            'take_profit': take_profit,
                            'rr_ratio': reward / risk,
                            'liquidity_level': liq_high,
                            'session': 'sweep_high'
                        }
        
        return None
    
    def check_exit(self, idx):
        """Check if position should exit"""
        if self.position is None:
            return None
        
        current = self.data.iloc[idx]
        high = current['High']
        low = current['Low']
        close = current['Close']
        
        side = self.position['side']
        entry = self.position['entry']
        stop_loss = self.position['stop_loss']
        take_profit = self.position['take_profit']
        
        if side == 'LONG':
            # Check SL
            if low <= stop_loss:
                exit_price = stop_loss
                reason = 'STOP_LOSS'
            # Check TP
            elif high >= take_profit:
                exit_price = take_profit
                reason = 'TAKE_PROFIT'
            else:
                return None
            
            pnl_pct = ((exit_price - entry) / entry) * 100
        
        else:  # SHORT
            # Check SL
            if high >= stop_loss:
                exit_price = stop_loss
                reason = 'STOP_LOSS'
            # Check TP
            elif low <= take_profit:
                exit_price = take_profit
                reason = 'TAKE_PROFIT'
            else:
                return None
            
            pnl_pct = ((entry - exit_price) / entry) * 100
        
        # Calculate PnL
        position_size = self.position['size']
        pnl = position_size * (exit_price - entry) if side == 'LONG' else position_size * (entry - exit_price)
        
        return {
            'exit_price': exit_price,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'reason': reason
        }
    
    def run(self):
        """Run backtest"""
        print("\n" + "="*70)
        print("🚀 ЗАПУСК БЕКТЕСТУ")
        print("="*70)
        
        for idx in range(len(self.data)):
            timestamp = self.data.index[idx]
            candle = self.data.iloc[idx]
            
            # Update session levels
            self.update_session_levels(candle, timestamp)
            
            # Check exit if in position
            if self.position is not None:
                exit_result = self.check_exit(idx)
                
                if exit_result:
                    # Close position
                    trade = {
                        'entry_time': self.position['entry_time'],
                        'exit_time': timestamp,
                        'side': self.position['side'],
                        'entry_price': self.position['entry'],
                        'exit_price': exit_result['exit_price'],
                        'stop_loss': self.position['stop_loss'],
                        'take_profit': self.position['take_profit'],
                        'rr_ratio': self.position['rr_ratio'],
                        'pnl': exit_result['pnl'],
                        'pnl_pct': exit_result['pnl_pct'],
                        'exit_reason': exit_result['reason'],
                        'win': exit_result['pnl'] > 0,
                        'session': self.position.get('session', 'unknown'),
                        'liquidity_level': self.position.get('liquidity_level', 0)
                    }
                    
                    self.balance += exit_result['pnl']
                    self.trades.append(trade)
                    self.position = None
            
            # Check for new signals
            else:
                signal = self.check_signals(idx)
                
                if signal:
                    # Open position
                    position_size = self.calculate_position_size(signal['entry'], signal['stop_loss'])
                    
                    if position_size > 0:
                        self.position = {
                            'entry_time': timestamp,
                            'side': signal['side'],
                            'entry': signal['entry'],
                            'stop_loss': signal['stop_loss'],
                            'take_profit': signal['take_profit'],
                            'rr_ratio': signal['rr_ratio'],
                            'size': position_size,
                            'session': signal.get('session', 'unknown'),
                            'liquidity_level': signal.get('liquidity_level', 0)
                        }
        
        return self.analyze_results()
    
    def analyze_results(self):
        """Analyze backtest results"""
        print("\n" + "="*70)
        print("📊 РЕЗУЛЬТАТИ БЕКТЕСТУ")
        print("="*70)
        
        if len(self.trades) == 0:
            print("\n⚠️  Трейдів не знайдено!")
            print("\nМожливі причини:")
            print("  - Недостатньо даних для формування сигналів")
            print("  - Умови для входу не виконувались")
            print("  - Session levels не налаштувались")
            return None
        
        df_trades = pd.DataFrame(self.trades)
        
        # Filter November 2025 trades
        november_trades = df_trades[
            (df_trades['entry_time'].dt.year == 2025) &
            (df_trades['entry_time'].dt.month == 11)
        ]
        
        # Overall stats
        total_trades = len(df_trades)
        wins = df_trades[df_trades['win'] == True].shape[0]
        losses = df_trades[df_trades['win'] == False].shape[0]
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        total_pnl = df_trades['pnl'].sum()
        total_return = ((self.balance - self.initial_balance) / self.initial_balance) * 100
        
        print(f"\n📈 Загальна статистика:")
        print(f"   Період: {self.data.index[0]} - {self.data.index[-1]}")
        print(f"   Початковий баланс: ${self.initial_balance:,.2f}")
        print(f"   Кінцевий баланс: ${self.balance:,.2f}")
        print(f"   Прибуток: ${total_pnl:,.2f} ({total_return:.2f}%)")
        print(f"   Всього трейдів: {total_trades}")
        print(f"   Виграшних: {wins} ({win_rate:.1f}%)")
        print(f"   Програшних: {losses}")
        
        if len(november_trades) > 0:
            print(f"\n🗓️  Листопад 2025:")
            print(f"   Трейдів: {len(november_trades)}")
            print(f"   Виграшних: {november_trades[november_trades['win'] == True].shape[0]}")
            print(f"   PnL: ${november_trades['pnl'].sum():,.2f}")
        else:
            print(f"\n🗓️  Листопад 2025:")
            print(f"   ⚠️  Трейдів не виконано")
        
        print("\n" + "="*70)
        print("📋 ДЕТАЛЬНИЙ СПИСОК ТРЕЙДІВ")
        print("="*70)
        
        for idx, trade in df_trades.iterrows():
            duration = (trade['exit_time'] - trade['entry_time']).total_seconds() / 3600
            status = "✅ WIN" if trade['win'] else "❌ LOSS"
            
            print(f"\n{status} | Trade #{idx + 1}")
            print(f"   Вхід: {trade['entry_time'].strftime('%Y-%m-%d %H:%M')} | {trade['side']}")
            print(f"   Entry: ${trade['entry_price']:,.2f}")
            print(f"   SL: ${trade['stop_loss']:,.2f} | TP: ${trade['take_profit']:,.2f}")
            print(f"   Вихід: {trade['exit_time'].strftime('%Y-%m-%d %H:%M')} | {trade['exit_reason']}")
            print(f"   Exit: ${trade['exit_price']:,.2f}")
            print(f"   PnL: ${trade['pnl']:,.2f} ({trade['pnl_pct']:.2f}%)")
            print(f"   R:R: {trade['rr_ratio']:.2f} | Тривалість: {duration:.1f}h")
            print(f"   Session: {trade['session']} | Liq Level: ${trade['liquidity_level']:,.2f}")
        
        # November 2025 detailed
        if len(november_trades) > 0:
            print("\n" + "="*70)
            print("🗓️  ЛИСТОПАД 2025 - ДЕТАЛЬНО")
            print("="*70)
            
            for idx, trade in november_trades.iterrows():
                duration = (trade['exit_time'] - trade['entry_time']).total_seconds() / 3600
                status = "✅ WIN" if trade['win'] else "❌ LOSS"
                
                print(f"\n{status} | {trade['side']}")
                print(f"   Вхід: {trade['entry_time'].strftime('%Y-%m-%d %H:%M')} @ ${trade['entry_price']:,.2f}")
                print(f"   Вихід: {trade['exit_time'].strftime('%Y-%m-%d %H:%M')} @ ${trade['exit_price']:,.2f}")
                print(f"   PnL: ${trade['pnl']:,.2f} ({trade['pnl_pct']:.2f}%)")
                print(f"   R:R: {trade['rr_ratio']:.2f} | Тривалість: {duration:.1f}h")
        
        print("\n" + "="*70)
        
        return {
            'trades': df_trades,
            'november_trades': november_trades,
            'stats': {
                'total_trades': total_trades,
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'total_return': total_return,
                'final_balance': self.balance
            }
        }


def main():
    """Main function"""
    print("\n" + "="*70)
    print("🌙 LIQUIDITY SWEEP BOT - BACKTEST NOVEMBER 2025")
    print("="*70)
    print("\nПеревірка трейдів за листопад 2025")
    print("Завантаження актуальних даних з Binance...")
    print("="*70)
    
    # Download data
    data = download_binance_data(SYMBOL, TIMEFRAME, days_back=90)
    
    if data is None or len(data) == 0:
        print("\n❌ Не вдалось завантажити дані")
        return
    
    # Run backtest
    backtest = LiquiditySweepBacktest(data, initial_balance=10000)
    results = backtest.run()
    
    if results is None:
        print("\n⚠️  Бектест завершено без трейдів")
        return
    
    # Summary
    print("\n" + "="*70)
    print("✅ БЕКТЕСТ ЗАВЕРШЕНО")
    print("="*70)
    
    stats = results['stats']
    print(f"\n📊 Підсумок:")
    print(f"   Всього трейдів: {stats['total_trades']}")
    print(f"   Win Rate: {stats['win_rate']:.1f}%")
    print(f"   Total Return: {stats['total_return']:.2f}%")
    print(f"   Final Balance: ${stats['final_balance']:,.2f}")
    
    november_count = len(results['november_trades'])
    if november_count > 0:
        nov_pnl = results['november_trades']['pnl'].sum()
        print(f"\n🗓️  Листопад 2025:")
        print(f"   Трейдів: {november_count}")
        print(f"   PnL: ${nov_pnl:,.2f}")
    else:
        print(f"\n🗓️  Листопад 2025:")
        print(f"   ⚠️  Трейдів не було")
        print(f"\n💡 Це нормально! Стратегія має ~2 трейди/місяць")
        print(f"   Можливо умови для входу ще не виконались")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    main()

