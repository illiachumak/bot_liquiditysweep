"""
🌙 Liquidity Sweep Trading Bot for Binance Futures

Strategy: Session Liquidity Sweeps (Optimized 2022-2025)
Expected: 2.71% monthly | 59% win rate | -10.67% max DD
Risk: 2% per trade | Max 1 position

Built with ❤️ for disciplined trading
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
# Try to import talib, but provide fallback if not available
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    print("⚠️  TA-Lib not available, using pandas-based ATR calculation")
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv
from termcolor import colored

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def calculate_atr_pandas(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate ATR (Average True Range) using pandas
    Fallback when TA-Lib is not available
    """
    # Calculate True Range
    high_low = high - low
    high_close = np.abs(high - close.shift())
    low_close = np.abs(low - close.shift())
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    
    # Calculate ATR as exponential moving average of True Range
    atr = true_range.ewm(span=period, adjust=False).mean()
    
    return atr

# ============================================================================
# CONFIGURATION
# ============================================================================

load_dotenv()

# Binance credentials
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')
USE_TESTNET = os.getenv('BINANCE_TESTNET', 'True').lower() == 'true'

# Trading parameters
SYMBOL = 'BTCUSDT'
TIMEFRAME = '4h'
RISK_PER_TRADE = 2.0  # 2% risk per trade

# Strategy parameters (optimized 2022-2025)
SWING_LOOKBACK = 5
SWEEP_TOLERANCE = 0.001  # 0.1%
MIN_RR = 1.5
ATR_PERIOD = 14
ATR_STOP_MULTIPLIER = 1.5

# Sessions (UTC)
ASIAN_SESSION = (0, 8)
LONDON_SESSION = (8, 13)
NY_SESSION = (13, 20)

# Bot settings
CANDLE_BUFFER_SIZE = 100
CHECK_INTERVAL = 60  # Check every 60 seconds for new candles
LOG_LEVEL = logging.INFO

# Trade logging
TRADES_LOG_FILE = 'logs/trades.json'
PERFORMANCE_LOG_FILE = 'logs/performance.json'

# ============================================================================
# LOGGING SETUP
# ============================================================================

# Create logs directory
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('logs/liquidity_sweep_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# BINANCE CLIENT
# ============================================================================

class BinanceManager:
    """Manages Binance API interactions"""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.testnet = testnet
        
        # Configure Futures Testnet URLs if needed
        if testnet:
            self.client = Client(api_key, api_secret, tld='com')
            # Set correct Testnet Futures API URLs
            self.client.FUTURES_URL = 'https://testnet.binancefuture.com/fapi'
            logger.info("[TESTNET] Binance Futures Testnet initialized")
            logger.info(f"[TESTNET] Using URL: {self.client.FUTURES_URL}")
        else:
            self.client = Client(api_key, api_secret)
            logger.info("[LIVE] Binance Futures Live initialized")
    
    def get_account_balance(self) -> float:
        """Get USDT balance"""
        try:
            account = self.client.futures_account()
            for asset in account['assets']:
                if asset['asset'] == 'USDT':
                    return float(asset['availableBalance'])
            return 0.0
        except BinanceAPIException as e:
            if e.code == -5000:
                logger.error(f"⚠️  API Error -5000: Invalid endpoint or API keys don't have Futures access")
                logger.error(f"    Please check:")
                logger.error(f"    1. API keys have 'Enable Futures' permission")
                logger.error(f"    2. Using correct Testnet keys if BINANCE_TESTNET=True")
                logger.error(f"    3. Testnet keys from: https://testnet.binancefuture.com/")
            else:
                logger.error(f"Error fetching balance: {e}")
            return 0.0
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
            return 0.0
    
    def get_historical_klines(self, symbol: str, interval: str, limit: int = 100) -> pd.DataFrame:
        """Fetch historical klines"""
        try:
            klines = self.client.futures_klines(symbol=symbol, interval=interval, limit=limit)
            
            df = pd.DataFrame(klines, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
            df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
            
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            
            df.set_index('open_time', inplace=True)
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            logger.info(f"Fetched {len(df)} historical candles for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"Error fetching klines: {e}")
            return pd.DataFrame()
    
    def get_current_position(self, symbol: str) -> Dict:
        """Get current position for symbol"""
        try:
            positions = self.client.futures_position_information(symbol=symbol)
            for pos in positions:
                if pos['symbol'] == symbol:
                    return {
                        'size': float(pos['positionAmt']),
                        'entry_price': float(pos['entryPrice']),
                        'unrealized_pnl': float(pos['unRealizedProfit']),
                        'leverage': int(pos['leverage'])
                    }
            return {'size': 0, 'entry_price': 0, 'unrealized_pnl': 0, 'leverage': 1}
        except Exception as e:
            logger.error(f"Error fetching position: {e}")
            return {'size': 0, 'entry_price': 0, 'unrealized_pnl': 0, 'leverage': 1}
    
    def place_market_order(self, symbol: str, side: str, quantity: float) -> Optional[Dict]:
        """Place market order"""
        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type=ORDER_TYPE_MARKET,
                quantity=quantity
            )
            logger.info(f"Market order placed: {side} {quantity} {symbol}")
            return order
        except BinanceAPIException as e:
            logger.error(f"Binance API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return None
    
    def place_stop_loss(self, symbol: str, side: str, quantity: float, stop_price: float) -> Optional[Dict]:
        """Place stop loss order"""
        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type=FUTURE_ORDER_TYPE_STOP_MARKET,
                quantity=quantity,
                stopPrice=stop_price
            )
            logger.info(f"Stop loss placed: {stop_price}")
            return order
        except Exception as e:
            logger.error(f"Error placing stop loss: {e}")
            return None
    
    def place_take_profit(self, symbol: str, side: str, quantity: float, price: float) -> Optional[Dict]:
        """Place take profit order"""
        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type=FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET,
                quantity=quantity,
                stopPrice=price
            )
            logger.info(f"Take profit placed: {price}")
            return order
        except Exception as e:
            logger.error(f"Error placing take profit: {e}")
            return None
    
    def cancel_all_orders(self, symbol: str):
        """Cancel all open orders for symbol"""
        try:
            self.client.futures_cancel_all_open_orders(symbol=symbol)
            logger.info(f"All orders cancelled for {symbol}")
        except Exception as e:
            logger.error(f"Error cancelling orders: {e}")
    
    def set_leverage(self, symbol: str, leverage: int):
        """Set leverage for symbol"""
        try:
            self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
            logger.info(f"Leverage set to {leverage}x for {symbol}")
        except Exception as e:
            logger.error(f"Error setting leverage: {e}")

# ============================================================================
# STRATEGY LOGIC
# ============================================================================

class LiquiditySweepStrategy:
    """Implements Liquidity Sweep strategy logic"""
    
    def __init__(self):
        self.candles = pd.DataFrame()
        self.session_levels = {
            'asian_high': None,
            'asian_low': None,
            'london_high': None,
            'london_low': None,
            'ny_high': None,
            'ny_low': None
        }
        self.current_date = None
        logger.info("Liquidity Sweep Strategy initialized")
    
    def update_candles(self, new_candle: pd.Series):
        """Add new candle to buffer"""
        if self.candles.empty:
            self.candles = pd.DataFrame([new_candle])
        else:
            self.candles = pd.concat([self.candles, pd.DataFrame([new_candle])], ignore_index=False)
            self.candles = self.candles.tail(CANDLE_BUFFER_SIZE)
        
        self.update_session_levels(new_candle)
    
    def update_session_levels(self, candle: pd.Series):
        """Update session high/low levels"""
        timestamp = candle.name
        current_date = timestamp.date()
        hour = timestamp.hour
        
        # Reset levels on new day
        if self.current_date != current_date:
            self.current_date = current_date
            self.session_levels = {k: None for k in self.session_levels}
        
        # Determine session
        if ASIAN_SESSION[0] <= hour < ASIAN_SESSION[1]:
            if self.session_levels['asian_high'] is None:
                self.session_levels['asian_high'] = candle['high']
                self.session_levels['asian_low'] = candle['low']
            else:
                self.session_levels['asian_high'] = max(self.session_levels['asian_high'], candle['high'])
                self.session_levels['asian_low'] = min(self.session_levels['asian_low'], candle['low'])
        
        elif LONDON_SESSION[0] <= hour < LONDON_SESSION[1]:
            if self.session_levels['london_high'] is None:
                self.session_levels['london_high'] = candle['high']
                self.session_levels['london_low'] = candle['low']
            else:
                self.session_levels['london_high'] = max(self.session_levels['london_high'], candle['high'])
                self.session_levels['london_low'] = min(self.session_levels['london_low'], candle['low'])
        
        elif NY_SESSION[0] <= hour < NY_SESSION[1]:
            if self.session_levels['ny_high'] is None:
                self.session_levels['ny_high'] = candle['high']
                self.session_levels['ny_low'] = candle['low']
            else:
                self.session_levels['ny_high'] = max(self.session_levels['ny_high'], candle['high'])
                self.session_levels['ny_low'] = min(self.session_levels['ny_low'], candle['low'])
    
    def calculate_indicators(self) -> pd.DataFrame:
        """Calculate ATR indicator"""
        if len(self.candles) < ATR_PERIOD:
            return self.candles
        
        df = self.candles.copy()
        
        # Use TA-Lib if available, otherwise use pandas-based calculation
        if TALIB_AVAILABLE:
            df['atr'] = talib.ATR(df['high'].values, df['low'].values, df['close'].values, ATR_PERIOD)
        else:
            df['atr'] = calculate_atr_pandas(df['high'], df['low'], df['close'], ATR_PERIOD)
        
        return df
    
    def find_swing_high(self, lookback: int = SWING_LOOKBACK) -> Optional[float]:
        """Find swing high"""
        if len(self.candles) < lookback:
            return None
        highs = self.candles['high'].tail(lookback).values
        return float(np.max(highs))
    
    def find_swing_low(self, lookback: int = SWING_LOOKBACK) -> Optional[float]:
        """Find swing low"""
        if len(self.candles) < lookback:
            return None
        lows = self.candles['low'].tail(lookback).values
        return float(np.min(lows))
    
    def detect_bullish_reversal(self) -> bool:
        """Detect bullish reversal pattern"""
        if len(self.candles) < 3:
            return False
        
        recent = self.candles.tail(3)
        current = recent.iloc[-1]
        previous = recent.iloc[-2]
        
        curr_bullish = current['close'] > current['open']
        strong_body = abs(current['close'] - current['open']) > abs(previous['close'] - previous['open'])
        recent_low = recent['low'].min()
        back_above = current['close'] > recent_low
        
        return curr_bullish and back_above and strong_body
    
    def detect_bearish_reversal(self) -> bool:
        """Detect bearish reversal pattern"""
        if len(self.candles) < 3:
            return False
        
        recent = self.candles.tail(3)
        current = recent.iloc[-1]
        previous = recent.iloc[-2]
        
        curr_bearish = current['close'] < current['open']
        strong_body = abs(current['close'] - current['open']) > abs(previous['close'] - previous['open'])
        recent_high = recent['high'].max()
        back_below = current['close'] < recent_high
        
        return curr_bearish and back_below and strong_body
    
    def check_signals(self) -> Tuple[bool, Optional[Dict]]:
        """
        Check for entry signals
        Returns: (has_signal, signal_dict)
        """
        if len(self.candles) < ATR_PERIOD:
            return False, None
        
        df = self.calculate_indicators()
        current = df.iloc[-1]
        recent_3 = df.tail(3)
        
        atr = current['atr']
        recent_high = recent_3['high'].max()
        recent_low = recent_3['low'].min()
        
        # Get session levels
        liq_highs = [v for v in [self.session_levels['asian_high'], 
                                  self.session_levels['london_high'],
                                  self.session_levels['ny_high']] if v is not None]
        
        liq_lows = [v for v in [self.session_levels['asian_low'],
                                 self.session_levels['london_low'],
                                 self.session_levels['ny_low']] if v is not None]
        
        if not liq_highs or not liq_lows:
            return False, None
        
        # CHECK LONG SIGNAL
        for liq_low in liq_lows:
            if recent_low <= liq_low * (1 + SWEEP_TOLERANCE):
                if self.detect_bullish_reversal():
                    entry = current['close']
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
                        return True, {
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
                if self.detect_bearish_reversal():
                    entry = current['close']
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
                        return True, {
                            'side': 'SHORT',
                            'entry': entry,
                            'stop_loss': stop_loss,
                            'take_profit': take_profit,
                            'rr_ratio': reward / risk,
                            'liquidity_level': liq_high,
                            'session': 'sweep_high'
                        }
        
        return False, None

# ============================================================================
# RISK MANAGER
# ============================================================================

class RiskManager:
    """Manages position sizing and risk"""
    
    @staticmethod
    def calculate_position_size(balance: float, entry: float, stop_loss: float, 
                                risk_percent: float = RISK_PER_TRADE) -> float:
        """
        Calculate position size based on risk
        Returns quantity to trade
        """
        risk_amount = balance * (risk_percent / 100)
        risk_per_unit = abs(entry - stop_loss)
        
        if risk_per_unit == 0:
            return 0
        
        position_size = risk_amount / risk_per_unit
        
        # Round to 3 decimal places for BTC
        position_size = round(position_size, 3)
        
        logger.info(f"Position size calculated: {position_size} BTC (Risk: ${risk_amount:.2f})")
        return position_size

# ============================================================================
# MAIN TRADING BOT
# ============================================================================

class LiquiditySweepBot:
    """Main trading bot orchestrator"""
    
    def __init__(self):
        self.binance = BinanceManager(BINANCE_API_KEY, BINANCE_API_SECRET, USE_TESTNET)
        self.strategy = LiquiditySweepStrategy()
        self.risk_manager = RiskManager()
        self.in_position = False
        self.current_trade = None
        self.last_candle_time = None
        
        # Statistics
        self.stats = {
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'total_pnl': 0.0
        }
        
        # Load existing trades if any
        self.trades_history = self.load_trades_history()
        
        logger.info("🚀 Liquidity Sweep Bot initialized")
    
    def load_trades_history(self) -> List[Dict]:
        """Load trades history from JSON file"""
        try:
            if os.path.exists(TRADES_LOG_FILE):
                with open(TRADES_LOG_FILE, 'r') as f:
                    return json.load(f)
            return []
        except Exception as e:
            logger.error(f"Error loading trades history: {e}")
            return []
    
    def save_trade(self, trade: Dict):
        """Save trade to JSON file"""
        try:
            self.trades_history.append(trade)
            with open(TRADES_LOG_FILE, 'w') as f:
                json.dump(self.trades_history, f, indent=2, default=str)
            logger.info(f"💾 Trade saved to {TRADES_LOG_FILE}")
        except Exception as e:
            logger.error(f"Error saving trade: {e}")
    
    def save_performance(self):
        """Save performance stats to JSON file"""
        try:
            performance = {
                'last_updated': datetime.now().isoformat(),
                'stats': self.stats,
                'win_rate': (self.stats['wins'] / self.stats['total_trades'] * 100) if self.stats['total_trades'] > 0 else 0,
                'mode': 'TESTNET' if USE_TESTNET else 'LIVE',
                'symbol': SYMBOL
            }
            with open(PERFORMANCE_LOG_FILE, 'w') as f:
                json.dump(performance, f, indent=2)
            logger.info(f"📊 Performance saved to {PERFORMANCE_LOG_FILE}")
        except Exception as e:
            logger.error(f"Error saving performance: {e}")
    
    def print_banner(self):
        """Print startup banner"""
        banner = """
╔═══════════════════════════════════════════════════════════════╗
║           🌙 LIQUIDITY SWEEP TRADING BOT 🚀                  ║
╠═══════════════════════════════════════════════════════════════╣
║  Strategy: Session Liquidity Sweeps (2022-2025 Optimized)    ║
║  Expected: 2.71% monthly | 59% WR | -10.67% max DD          ║
║  Risk: 2% per trade | Frequency: ~2 trades/month            ║
╠═══════════════════════════════════════════════════════════════╣
║  Symbol: BTCUSDT | Timeframe: 4h                            ║
║  Mode: {} 
╚═══════════════════════════════════════════════════════════════╝
        """.format('[TESTNET]' if USE_TESTNET else '[LIVE]     ')
        print(colored(banner, 'cyan'))
    
    async def initialize(self):
        """Initialize bot with historical data"""
        logger.info("Initializing bot...")
        
        # Fetch historical data
        df = self.binance.get_historical_klines(SYMBOL, TIMEFRAME, CANDLE_BUFFER_SIZE)
        if df.empty:
            logger.error("Failed to fetch historical data")
            return False
        
        # Load into strategy
        self.strategy.candles = df
        for idx, row in df.iterrows():
            self.strategy.update_session_levels(row)
        
        self.last_candle_time = df.index[-1]
        
        logger.info(f"Loaded {len(df)} historical candles")
        logger.info(f"Last candle time: {self.last_candle_time}")
        logger.info(f"Session levels: {self.strategy.session_levels}")
        
        # Check account balance
        balance = self.binance.get_account_balance()
        logger.info(f"Account balance: ${balance:.2f} USDT")
        
        return True
    
    async def check_new_candle(self):
        """Check for new candles and update strategy"""
        try:
            df = self.binance.get_historical_klines(SYMBOL, TIMEFRAME, limit=1)
            if df.empty:
                return False
            
            latest_time = df.index[-1]
            
            # New candle detected
            if self.last_candle_time is None or latest_time > self.last_candle_time:
                logger.info(f"🕯️  New candle: {latest_time}")
                
                new_candle = df.iloc[-1]
                self.strategy.update_candles(new_candle)
                self.last_candle_time = latest_time
                
                logger.info(f"Close: ${new_candle['close']:.2f} | High: ${new_candle['high']:.2f} | Low: ${new_candle['low']:.2f}")
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking new candle: {e}")
            return False
    
    async def monitor_position(self):
        """Monitor current position and handle exits"""
        if not self.in_position or not self.current_trade:
            return
        
        try:
            position = self.binance.get_current_position(SYMBOL)
            
            # Position closed (hit SL or TP)
            if position['size'] == 0:
                pnl = position['unrealized_pnl']
                
                # Prepare trade record
                trade_record = {
                    'timestamp': datetime.now().isoformat(),
                    'symbol': SYMBOL,
                    'side': self.current_trade['side'],
                    'entry_price': self.current_trade['entry'],
                    'exit_price': position.get('exit_price', 0),  # May not be available
                    'stop_loss': self.current_trade['stop_loss'],
                    'take_profit': self.current_trade['take_profit'],
                    'rr_ratio': self.current_trade['rr_ratio'],
                    'pnl': pnl,
                    'pnl_percent': (pnl / (self.current_trade['entry'] * position.get('size', 0)) * 100) if position.get('size', 0) > 0 else 0,
                    'win': pnl > 0,
                    'session': self.current_trade.get('session', 'unknown'),
                    'liquidity_level': self.current_trade.get('liquidity_level', 0),
                    'mode': 'TESTNET' if USE_TESTNET else 'LIVE'
                }
                
                # Save trade
                self.save_trade(trade_record)
                
                # Update stats
                self.stats['total_trades'] += 1
                self.stats['total_pnl'] += pnl
                
                if pnl > 0:
                    self.stats['wins'] += 1
                    logger.info(f"✅ Position closed - WIN | PnL: ${pnl:.2f}")
                else:
                    self.stats['losses'] += 1
                    logger.info(f"❌ Position closed - LOSS | PnL: ${pnl:.2f}")
                
                # Save performance
                self.save_performance()
                
                # Reset state
                self.in_position = False
                self.current_trade = None
                
                # Log stats
                win_rate = (self.stats['wins'] / self.stats['total_trades'] * 100) if self.stats['total_trades'] > 0 else 0
                logger.info(f"📊 Stats: {self.stats['total_trades']} trades | {win_rate:.1f}% WR | ${self.stats['total_pnl']:.2f} PnL")
            
            else:
                # Position still open
                logger.debug(f"Position open: {position['size']} BTC @ ${position['entry_price']:.2f} | PnL: ${position['unrealized_pnl']:.2f}")
        
        except Exception as e:
            logger.error(f"Error monitoring position: {e}")
    
    async def check_signals_and_trade(self):
        """Check for signals and execute trades"""
        if self.in_position:
            return
        
        try:
            has_signal, signal = self.strategy.check_signals()
            
            if has_signal and signal:
                logger.info(f"🚨 SIGNAL DETECTED: {signal['side']}")
                logger.info(f"   Entry: ${signal['entry']:.2f}")
                logger.info(f"   Stop Loss: ${signal['stop_loss']:.2f}")
                logger.info(f"   Take Profit: ${signal['take_profit']:.2f}")
                logger.info(f"   R:R Ratio: {signal['rr_ratio']:.2f}")
                logger.info(f"   Liquidity Level: ${signal['liquidity_level']:.2f}")
                
                # Get balance
                balance = self.binance.get_account_balance()
                
                # Calculate position size
                position_size = self.risk_manager.calculate_position_size(
                    balance, signal['entry'], signal['stop_loss']
                )
                
                if position_size <= 0:
                    logger.warning("Position size too small, skipping trade")
                    return
                
                # Place market order
                side = SIDE_BUY if signal['side'] == 'LONG' else SIDE_SELL
                order = self.binance.place_market_order(SYMBOL, side, position_size)
                
                if order:
                    logger.info(f"✅ Market order executed: {signal['side']} {position_size} BTC")
                    
                    # Place stop loss
                    sl_side = SIDE_SELL if signal['side'] == 'LONG' else SIDE_BUY
                    self.binance.place_stop_loss(SYMBOL, sl_side, position_size, signal['stop_loss'])
                    
                    # Place take profit
                    self.binance.place_take_profit(SYMBOL, sl_side, position_size, signal['take_profit'])
                    
                    # Update state
                    self.in_position = True
                    self.current_trade = signal
                    
                    logger.info("🎯 Trade opened successfully!")
                else:
                    logger.error("Failed to place order")
        
        except Exception as e:
            logger.error(f"Error checking signals: {e}")
    
    async def run(self):
        """Main bot loop"""
        self.print_banner()
        
        # Initialize
        success = await self.initialize()
        if not success:
            logger.error("Initialization failed, exiting")
            return
        
        logger.info("✅ Bot initialized successfully")
        logger.info("🔍 Starting main loop...")
        
        while True:
            try:
                # Monitor existing position
                await self.monitor_position()
                
                # Check for new candle
                new_candle = await self.check_new_candle()
                
                # If new candle, check for signals
                if new_candle:
                    await self.check_signals_and_trade()
                
                # Sleep before next check
                await asyncio.sleep(CHECK_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("🛑 Bot stopped by user")
                break
            
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(10)

# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    # Create logs directory
    os.makedirs('logs', exist_ok=True)
    
    # Check credentials
    if not BINANCE_API_KEY or not BINANCE_API_SECRET:
        logger.error("Binance API credentials not found in .env file")
        logger.error("Please create .env file with BINANCE_API_KEY and BINANCE_API_SECRET")
        return
    
    # Run bot
    bot = LiquiditySweepBot()
    asyncio.run(bot.run())

if __name__ == "__main__":
    main()

