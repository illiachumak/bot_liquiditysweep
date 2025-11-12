"""
15-Minute Breakout Bot - NY Session
Strategy: High/Low Breakout with 2:1 R:R during NY trading hours (13-20 UTC)

Based on backtest results:
- Net Monthly Return: 6.70%
- Win Rate: 40.25%
- Sharpe: 1.04
- Max DD: -28.80%
"""

import os
import time
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List
import pandas as pd
import numpy as np
from binance.client import Client
from binance.exceptions import BinanceAPIException

# Try to import talib, fallback to pandas if not available
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    print("⚠️  TA-Lib not available, using pandas fallback")


# ============================================================================
# CONFIGURATION
# ============================================================================

class BotConfig:
    """Bot configuration"""
    
    # Trading Parameters
    SYMBOL = 'BTCUSDT'
    TIMEFRAME = '15m'
    LOOKBACK_CANDLES = 24  # 6 hours
    MIN_RR = 2.0
    ATR_PERIOD = 14
    ATR_SL_MULT = 1.5
    
    # NY Session Filter (UTC)
    NY_SESSION_HOURS = [13, 14, 15, 16, 17, 18, 19, 20]
    
    # Risk Management
    RISK_PER_TRADE = 0.02  # 2% risk per trade
    
    # API Configuration
    USE_TESTNET = True  # Set to False for live trading
    
    # Logging
    LOG_LEVEL = logging.INFO


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_atr_pandas(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate ATR using pandas (fallback)"""
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr


# ============================================================================
# MAIN BOT CLASS
# ============================================================================

class BreakoutBot:
    """15m High/Low Breakout Bot with NY Session Filter"""
    
    def __init__(self, testnet: bool = True):
        """Initialize bot"""
        self.config = BotConfig()
        self.testnet = testnet
        
        # Setup logging
        self.setup_logging()
        
        # Initialize Binance client
        self.client = self.init_binance_client()
        
        # Trading state
        self.candles = pd.DataFrame()
        self.position = None  # {'side': 'LONG'/'SHORT', 'entry': price, 'sl': price, 'tp': price, 'size': amount}
        self.balance = 0.0
        self.last_check_time = None
        
        self.logger.info("🚀 Breakout Bot initialized")
        self.logger.info(f"   Symbol: {self.config.SYMBOL}")
        self.logger.info(f"   Timeframe: {self.config.TIMEFRAME}")
        self.logger.info(f"   NY Session: {self.config.NY_SESSION_HOURS[0]}:00-{self.config.NY_SESSION_HOURS[-1]}:00 UTC")
        self.logger.info(f"   Testnet: {testnet}")
    
    def setup_logging(self):
        """Setup logging"""
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        logging.basicConfig(
            level=self.config.LOG_LEVEL,
            format=log_format,
            handlers=[
                logging.FileHandler('breakout_bot.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def init_binance_client(self) -> Client:
        """Initialize Binance client"""
        api_key = os.getenv('BINANCE_API_KEY')
        api_secret = os.getenv('BINANCE_API_SECRET')
        
        if not api_key or not api_secret:
            self.logger.error("❌ Binance API keys not found in environment variables")
            raise ValueError("Missing API keys")
        
        if self.testnet:
            self.logger.info("📝 Using Binance TESTNET")
            client = Client(api_key, api_secret, testnet=True)
            client.API_URL = 'https://testnet.binancefuture.com'
        else:
            self.logger.warning("⚠️  Using Binance LIVE")
            client = Client(api_key, api_secret)
        
        # Test connection
        try:
            client.ping()
            self.logger.info("✅ Connected to Binance")
        except Exception as e:
            self.logger.error(f"❌ Connection failed: {e}")
            raise
        
        return client
    
    def fetch_candles(self, limit: int = 100) -> pd.DataFrame:
        """Fetch latest candles from Binance"""
        try:
            klines = self.client.get_klines(
                symbol=self.config.SYMBOL,
                interval=self.config.TIMEFRAME,
                limit=limit
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
            
            return df[['open', 'high', 'low', 'close', 'volume']]
            
        except BinanceAPIException as e:
            self.logger.error(f"❌ Error fetching candles: {e}")
            return pd.DataFrame()
    
    def calculate_atr(self, candles: pd.DataFrame) -> float:
        """Calculate ATR"""
        if TALIB_AVAILABLE:
            atr = talib.ATR(candles['high'].values, candles['low'].values,
                           candles['close'].values, self.config.ATR_PERIOD)
            return atr[-1] if len(atr) > 0 and not np.isnan(atr[-1]) else None
        else:
            atr = calculate_atr_pandas(candles['high'], candles['low'],
                                      candles['close'], self.config.ATR_PERIOD)
            return atr.iloc[-1] if len(atr) > 0 and not pd.isna(atr.iloc[-1]) else None
    
    def is_ny_session(self) -> bool:
        """Check if current hour is in NY session"""
        current_hour = datetime.now(timezone.utc).hour
        return current_hour in self.config.NY_SESSION_HOURS
    
    def find_swing_levels(self, candles: pd.DataFrame) -> tuple:
        """Find swing high/low from lookback period"""
        if len(candles) < self.config.LOOKBACK_CANDLES:
            return None, None
        
        lookback = candles.iloc[-self.config.LOOKBACK_CANDLES-1:-1]
        swing_high = lookback['high'].max()
        swing_low = lookback['low'].min()
        
        return swing_high, swing_low
    
    def check_signal(self, candles: pd.DataFrame) -> Optional[Dict]:
        """Check for breakout signal"""
        # Time filter
        if not self.is_ny_session():
            return None
        
        # Get current price
        current_price = candles['close'].iloc[-1]
        
        # Find swing levels
        swing_high, swing_low = self.find_swing_levels(candles)
        if swing_high is None or swing_low is None:
            return None
        
        # Calculate ATR
        atr = self.calculate_atr(candles)
        if atr is None:
            return None
        
        # Check for LONG breakout
        if current_price > swing_high:
            entry = current_price
            sl = swing_low
            risk = entry - sl
            tp = entry + (risk * self.config.MIN_RR)
            
            if risk > 0 and risk / entry < 0.1:  # Max 10% risk
                return {
                    'side': 'LONG',
                    'entry': entry,
                    'sl': sl,
                    'tp': tp,
                    'risk': risk,
                    'reward': tp - entry,
                    'rr': (tp - entry) / risk
                }
        
        # Check for SHORT breakout
        elif current_price < swing_low:
            entry = current_price
            sl = swing_high
            risk = sl - entry
            tp = entry - (risk * self.config.MIN_RR)
            
            if risk > 0 and tp > 0 and risk / entry < 0.1:
                return {
                    'side': 'SHORT',
                    'entry': entry,
                    'sl': sl,
                    'tp': tp,
                    'risk': risk,
                    'reward': entry - tp,
                    'rr': (entry - tp) / risk
                }
        
        return None
    
    def calculate_position_size(self, entry: float, stop_loss: float) -> float:
        """Calculate position size based on risk"""
        risk_amount = self.balance * self.config.RISK_PER_TRADE
        risk_per_unit = abs(entry - stop_loss)
        
        if risk_per_unit > 0:
            position_size = risk_amount / risk_per_unit
            return position_size
        
        return 0.0
    
    def check_exit(self, current_price: float) -> bool:
        """Check if should exit position"""
        if not self.position:
            return False
        
        side = self.position['side']
        sl = self.position['sl']
        tp = self.position['tp']
        
        if side == 'LONG':
            if current_price <= sl:
                self.logger.info(f"🛑 LONG Stop Loss hit at ${current_price:,.2f}")
                return True
            elif current_price >= tp:
                self.logger.info(f"🎯 LONG Take Profit hit at ${current_price:,.2f}")
                return True
        
        elif side == 'SHORT':
            if current_price >= sl:
                self.logger.info(f"🛑 SHORT Stop Loss hit at ${current_price:,.2f}")
                return True
            elif current_price <= tp:
                self.logger.info(f"🎯 SHORT Take Profit hit at ${current_price:,.2f}")
                return True
        
        return False
    
    def close_position(self, exit_price: float) -> Dict:
        """Close current position"""
        if not self.position:
            return None
        
        side = self.position['side']
        entry = self.position['entry']
        size = self.position['size']
        
        if side == 'LONG':
            pnl = (exit_price - entry) * size
        else:
            pnl = (entry - exit_price) * size
        
        pnl_pct = (pnl / (entry * size)) * 100
        
        self.balance += pnl
        
        trade = {
            'side': side,
            'entry': entry,
            'exit': exit_price,
            'size': size,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'exit_time': datetime.now(timezone.utc)
        }
        
        self.logger.info(f"💰 Closed {side}: PnL = ${pnl:,.2f} ({pnl_pct:+.2f}%)")
        self.logger.info(f"   Balance: ${self.balance:,.2f}")
        
        self.position = None
        
        return trade
    
    def open_position(self, signal: Dict):
        """Open new position"""
        size = self.calculate_position_size(signal['entry'], signal['sl'])
        
        if size <= 0:
            self.logger.warning("⚠️  Position size too small, skipping")
            return
        
        self.position = {
            'side': signal['side'],
            'entry': signal['entry'],
            'sl': signal['sl'],
            'tp': signal['tp'],
            'size': size,
            'entry_time': datetime.now(timezone.utc)
        }
        
        self.logger.info(f"📈 Opened {signal['side']} at ${signal['entry']:,.2f}")
        self.logger.info(f"   Size: {size:.6f}")
        self.logger.info(f"   SL: ${signal['sl']:,.2f}")
        self.logger.info(f"   TP: ${signal['tp']:,.2f}")
        self.logger.info(f"   R:R: {signal['rr']:.2f}:1")
    
    def run_once(self) -> Optional[Dict]:
        """Run one iteration of bot logic"""
        # Fetch candles
        candles = self.fetch_candles(limit=self.config.LOOKBACK_CANDLES + 20)
        if candles.empty:
            return None
        
        self.candles = candles
        current_price = candles['close'].iloc[-1]
        
        # Check if should exit
        if self.position:
            if self.check_exit(current_price):
                trade = self.close_position(current_price)
                return trade
        
        # Check for new signal (only if no position)
        if not self.position:
            signal = self.check_signal(candles)
            if signal:
                self.logger.info(f"🔔 {signal['side']} Signal detected!")
                self.open_position(signal)
        
        return None
    
    def get_balance(self) -> float:
        """Get current account balance"""
        try:
            if self.testnet:
                # Testnet - use mock balance
                return 10000.0
            else:
                account = self.client.get_account()
                for asset in account['balances']:
                    if asset['asset'] == 'USDT':
                        return float(asset['free'])
            return 0.0
        except Exception as e:
            self.logger.error(f"❌ Error getting balance: {e}")
            return 0.0
    
    def run(self, duration_minutes: Optional[int] = None):
        """Run bot continuously"""
        self.logger.info("🚀 Starting bot...")
        
        # Get initial balance
        self.balance = self.get_balance()
        self.logger.info(f"💰 Initial balance: ${self.balance:,.2f}")
        
        start_time = datetime.now()
        iterations = 0
        
        try:
            while True:
                self.run_once()
                iterations += 1
                
                # Check duration
                if duration_minutes:
                    elapsed = (datetime.now() - start_time).total_seconds() / 60
                    if elapsed >= duration_minutes:
                        self.logger.info(f"⏱️  Duration reached ({duration_minutes} min)")
                        break
                
                # Sleep until next candle
                time.sleep(60)  # Check every minute
                
        except KeyboardInterrupt:
            self.logger.info("🛑 Bot stopped by user")
        except Exception as e:
            self.logger.error(f"❌ Error in main loop: {e}")
        finally:
            self.logger.info(f"✅ Bot stopped after {iterations} iterations")
            self.logger.info(f"💰 Final balance: ${self.balance:,.2f}")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    bot = BreakoutBot(testnet=True)
    bot.run()

