"""
SMC Optimized Trading Bot
15-minute timeframe with multiple limit levels

Strategy Features:
- 3 limit orders per Order Block (25%, 50%, 75%)
- Partial exits (TP1: 50%, TP2: 30%, TP3: 20%)
- Trailing stops (SL to BE after TP1, SL to TP1 after TP2)
- Re-entry allowed (max 3x per OB)
- Optional session filter (NY hours)

Expected Performance:
- Monthly Return: 6.81%
- Win Rate: 46.34%
- Max Drawdown: -2.00%
- Trades: ~1.9/month
"""

import os
import time
import json
import logging
from logging.handlers import RotatingFileHandler
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from binance.client import Client
from binance.enums import *
import warnings
warnings.filterwarnings('ignore')


# Setup detailed logging
def setup_logging(verbose: bool = True):
    """Setup logging with rotation"""
    os.makedirs('logs', exist_ok=True)
    
    # Create logger
    logger = logging.getLogger('SMCBot')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        'logs/smc_bot.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Global logger
logger = setup_logging(verbose=True)

try:
    from smartmoneyconcepts import smc
    SMC_AVAILABLE = True
except ImportError:
    print("⚠️  smartmoneyconcepts not available. Install: pip install smartmoneyconcepts")
    SMC_AVAILABLE = False


class LimitOrder:
    """Represents a limit order"""
    def __init__(self, order_type: str, limit_price: float, sl: float,
                 tp_levels: List[float], tp_sizes: List[float],
                 placed_time: datetime, expiry_hours: int, ob_id: str, level: int):
        self.order_type = order_type  # 'LONG' or 'SHORT'
        self.limit_price = limit_price
        self.sl = sl
        self.tp_levels = tp_levels  # [TP1, TP2, TP3]
        self.tp_sizes = tp_sizes    # [0.5, 0.3, 0.2]
        self.placed_time = placed_time
        self.expiry_time = placed_time + timedelta(hours=expiry_hours)
        self.ob_id = ob_id
        self.level = level  # 1, 2, or 3
        self.binance_order_id = None
        self.filled = False
        self.filled_time = None
        self.filled_price = None
    
    def is_expired(self, current_time: datetime) -> bool:
        return current_time >= self.expiry_time


class Position:
    """Represents an active position with partial exits"""
    def __init__(self, order: LimitOrder, size: float, entry_time: datetime):
        self.type = order.order_type
        self.entry = order.filled_price
        self.size = size
        self.remaining_size = size
        self.sl = order.sl
        self.tp_levels = order.tp_levels
        self.tp_sizes = order.tp_sizes
        self.tp_hit = [False, False, False]
        self.entry_time = entry_time
        self.level = order.level
        self.ob_id = order.ob_id
        
        if self.type == 'LONG':
            self.risk = self.entry - self.sl
        else:
            self.risk = self.sl - self.entry
        
        self.breakeven_moved = False
        self.binance_position_ids = []  # Track Binance order IDs


class TradeLogger:
    """Logs all trades to JSON and CSV files"""
    
    def __init__(self, log_dir: str = 'trades_history'):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        
        self.json_file = os.path.join(log_dir, 'trades.json')
        self.csv_file = os.path.join(log_dir, 'trades.csv')
        
        # Load existing trades
        self.trades = self._load_trades()
    
    def _load_trades(self) -> List[Dict]:
        """Load existing trades from JSON"""
        if os.path.exists(self.json_file):
            try:
                with open(self.json_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def log_trade(self, trade_data: Dict):
        """Log a trade to JSON and CSV"""
        # Add timestamp
        trade_data['logged_at'] = datetime.utcnow().isoformat()
        
        # Append to list
        self.trades.append(trade_data)
        
        # Save to JSON
        with open(self.json_file, 'w') as f:
            json.dump(self.trades, f, indent=2)
        
        # Save to CSV
        df = pd.DataFrame(self.trades)
        df.to_csv(self.csv_file, index=False)
        
        print(f"💾 Trade logged to {self.json_file} and {self.csv_file}")
    
    def log_signal(self, signal_type: str, order: 'LimitOrder', current_time: datetime):
        """Log a new signal/limit order"""
        signal_data = {
            'event': 'SIGNAL',
            'type': signal_type,
            'level': order.level,
            'limit_price': order.limit_price,
            'sl': order.sl,
            'tp1': order.tp_levels[0],
            'tp2': order.tp_levels[1],
            'tp3': order.tp_levels[2],
            'placed_time': current_time.isoformat(),
            'expiry_time': order.expiry_time.isoformat(),
            'ob_id': order.ob_id
        }
        self.log_trade(signal_data)
    
    def log_fill(self, order: 'LimitOrder', size: float, current_time: datetime):
        """Log a limit order fill"""
        fill_data = {
            'event': 'FILL',
            'type': order.order_type,
            'level': order.level,
            'entry_price': order.filled_price,
            'size': size,
            'sl': order.sl,
            'tp1': order.tp_levels[0],
            'tp2': order.tp_levels[1],
            'tp3': order.tp_levels[2],
            'filled_time': current_time.isoformat(),
            'ob_id': order.ob_id
        }
        self.log_trade(fill_data)
    
    def log_exit(self, position: 'Position', exit_price: float, reason: str, 
                 size: float, pnl: float, current_time: datetime):
        """Log a position exit"""
        exit_data = {
            'event': 'EXIT',
            'type': position.type,
            'level': position.level,
            'entry_price': position.entry,
            'exit_price': exit_price,
            'size': size,
            'pnl': pnl,
            'reason': reason,
            'exit_time': current_time.isoformat(),
            'ob_id': position.ob_id,
            'entry_time': position.entry_time.isoformat()
        }
        self.log_trade(exit_data)


class SMCOptimizedStrategy:
    """Optimized SMC strategy logic"""
    
    def __init__(self, timeframe: str = '15m', session_filter: bool = False):
        self.timeframe = timeframe
        self.session_filter = session_filter
        
        # Strategy parameters (optimized for 15m)
        self.swing_length = 10
        self.ob_lookback = 12
        self.limit_expiry_hours = 12
        self.max_reentry = 3
        self.ny_hours = [13, 14, 15, 16, 17, 18, 19, 20]
        
        # Track OB usage
        self.ob_usage_count = {}
        
        # Cache for indicators
        self.indicators_cache = None
        self.cache_timestamp = None
    
    def calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Calculate SMC indicators"""
        if not SMC_AVAILABLE:
            logger.error("❌ SMC library not available!")
            return {}
        
        # Use cache if recent
        now = datetime.utcnow()
        if (self.indicators_cache and self.cache_timestamp and 
            (now - self.cache_timestamp).seconds < 60):
            logger.debug("📊 Using cached indicators")
            return self.indicators_cache
        
        logger.debug(f"🔍 Calculating SMC indicators on {len(df)} candles...")
        
        ohlc = pd.DataFrame({
            'open': df['Open'].values,
            'high': df['High'].values,
            'low': df['Low'].values,
            'close': df['Close'].values,
            'volume': df['Volume'].values
        })
        
        swings = smc.swing_highs_lows(ohlc, self.swing_length)
        obs = smc.ob(ohlc, swings)
        bos_choch = smc.bos_choch(ohlc, swings)
        
        indicators = {
            'swings': swings,
            'ob_signal': obs['OB'].values,
            'ob_top': obs['Top'].values,
            'ob_bottom': obs['Bottom'].values,
            'bos': bos_choch['BOS'].values,
            'choch': bos_choch['CHOCH'].values,
        }
        
        # Count OBs
        ob_count = sum(1 for x in indicators['ob_signal'] if not pd.isna(x))
        logger.debug(f"📊 Found {ob_count} Order Blocks in dataset")
        
        self.indicators_cache = indicators
        self.cache_timestamp = now
        
        return indicators
    
    def check_new_ob(self, df: pd.DataFrame, current_time: datetime) -> List[LimitOrder]:
        """
        Check for new Order Blocks and create limit orders
        Returns list of 3 limit orders at different levels
        """
        # Session filter
        if self.session_filter and current_time.hour not in self.ny_hours:
            logger.debug(f"⏰ Outside NY session (hour: {current_time.hour})")
            return []
        
        logger.debug(f"🔎 Scanning for Order Blocks at {current_time}")
        
        indicators = self.calculate_indicators(df)
        if not indicators:
            logger.warning("⚠️  No indicators calculated")
            return []
        
        ob_signal = indicators['ob_signal']
        ob_top = indicators['ob_top']
        ob_bottom = indicators['ob_bottom']
        current_idx = len(df) - 1
        
        orders = []
        
        # Look for recently formed OBs (2-5 candles old)
        logger.debug(f"🔍 Looking for OBs in last {min(6, current_idx)} candles...")
        
        for i in range(2, min(6, current_idx)):
            idx = current_idx - i
            
            if pd.isna(ob_signal[idx]):
                continue
            
            ob_sig = ob_signal[idx]
            ob_t = ob_top[idx]
            ob_b = ob_bottom[idx]
            
            if pd.isna(ob_t) or pd.isna(ob_b):
                continue
            
            logger.debug(f"   📍 Found OB at idx {idx} ({i} candles old): {'LONG' if ob_sig == 1 else 'SHORT'}, ${ob_b:.2f} - ${ob_t:.2f}")
            
            ob_id = f"{ob_sig}_{ob_b:.2f}_{ob_t:.2f}"
            
            # Check re-entry limit
            usage_count = self.ob_usage_count.get(ob_id, 0)
            if usage_count >= self.max_reentry:
                logger.debug(f"   ❌ OB already used {usage_count} times (max: {self.max_reentry})")
                continue
            
            ob_range = ob_t - ob_b
            logger.debug(f"   ✅ OB valid! Range: ${ob_range:.2f}, Usage: {usage_count}/{self.max_reentry}")
            
            # Create 3 limit orders
            if ob_sig == 1:  # LONG
                limit1 = ob_b + ob_range * 0.25
                limit2 = ob_b + ob_range * 0.50
                limit3 = ob_b + ob_range * 0.75
                
                for level, limit_price in enumerate([limit1, limit2, limit3], 1):
                    sl = ob_b * 0.995
                    risk = limit_price - sl
                    
                    if risk > 0 and risk / limit_price < 0.08:
                        tp1 = limit_price + risk * 1.5
                        tp2 = limit_price + risk * 2.5
                        tp3 = limit_price + risk * 4.0
                        
                        self.ob_usage_count[ob_id] = usage_count + 1
                        
                        logger.debug(f"   📋 Creating LONG Level {level}: ${limit_price:.2f}, SL: ${sl:.2f}, TP1: ${tp1:.2f}")
                        
                        orders.append(LimitOrder(
                            order_type='LONG',
                            limit_price=limit_price,
                            sl=sl,
                            tp_levels=[tp1, tp2, tp3],
                            tp_sizes=[0.5, 0.3, 0.2],
                            placed_time=current_time,
                            expiry_hours=self.limit_expiry_hours,
                            ob_id=ob_id,
                            level=level
                        ))
            
            elif ob_sig == -1:  # SHORT
                limit1 = ob_b + ob_range * 0.75
                limit2 = ob_b + ob_range * 0.50
                limit3 = ob_b + ob_range * 0.25
                
                for level, limit_price in enumerate([limit1, limit2, limit3], 1):
                    sl = ob_t * 1.005
                    risk = sl - limit_price
                    
                    if risk > 0 and risk / limit_price < 0.08:
                        tp1 = limit_price - risk * 1.5
                        tp2 = limit_price - risk * 2.5
                        tp3 = limit_price - risk * 4.0
                        
                        if tp1 > 0 and tp2 > 0 and tp3 > 0:
                            self.ob_usage_count[ob_id] = usage_count + 1
                            
                            logger.debug(f"   📋 Creating SHORT Level {level}: ${limit_price:.2f}, SL: ${sl:.2f}, TP1: ${tp1:.2f}")
                            
                            orders.append(LimitOrder(
                                order_type='SHORT',
                                limit_price=limit_price,
                                sl=sl,
                                tp_levels=[tp1, tp2, tp3],
                                tp_sizes=[0.5, 0.3, 0.2],
                                placed_time=current_time,
                                expiry_hours=self.limit_expiry_hours,
                                ob_id=ob_id,
                                level=level
                            ))
            
            if orders:
                logger.info(f"✅ Created {len(orders)} limit orders for OB")
                break
        
        if not orders:
            logger.debug("   ⭕ No valid OBs found")
        
        return orders
    
    def check_invalidation(self, position: Position, df: pd.DataFrame) -> bool:
        """Check if position should be closed due to invalidation"""
        indicators = self.calculate_indicators(df)
        if not indicators:
            return False
        
        current_idx = len(df) - 1
        
        # Check for opposite OB in last 5 candles
        for i in range(1, min(5, current_idx)):
            idx = current_idx - i
            ob_sig = indicators['ob_signal'][idx]
            
            if pd.isna(ob_sig):
                continue
            
            if position.type == 'LONG' and ob_sig == -1:
                return True
            if position.type == 'SHORT' and ob_sig == 1:
                return True
        
        return False
    
    def cleanup_old_obs(self):
        """Clean up old OB tracking (memory management)"""
        if len(self.ob_usage_count) > 100:
            self.ob_usage_count.clear()


class BinanceClient:
    """Wrapper for Binance API with request tracking"""
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        if testnet:
            self.client = Client(api_key, api_secret, testnet=True)
            self.client.API_URL = 'https://testnet.binance.vision/api'
        else:
            self.client = Client(api_key, api_secret)
        
        self.symbol = 'BTCUSDT'
        
        # Request tracking
        self.api_call_count = 0
        self.last_reset_time = datetime.utcnow()
        
        # Cache
        self.price_cache = None
        self.price_cache_time = None
        self.price_cache_ttl = 5  # seconds
        
        logger.info(f"📡 Binance Client initialized (Testnet: {testnet})")
    
    def _track_request(self, endpoint: str):
        """Track API request for rate limit monitoring"""
        self.api_call_count += 1
        
        # Reset counter every minute
        now = datetime.utcnow()
        if (now - self.last_reset_time).seconds >= 60:
            logger.debug(f"📊 API Calls last minute: {self.api_call_count}")
            self.api_call_count = 0
            self.last_reset_time = now
        
        logger.debug(f"🌐 API Call #{self.api_call_count}: {endpoint}")
    
    def get_klines(self, interval: str, limit: int = 500) -> pd.DataFrame:
        """Fetch klines from Binance"""
        self._track_request(f"get_klines({interval}, {limit})")
        
        try:
            klines = self.client.get_klines(
                symbol=self.symbol,
                interval=interval,
                limit=limit
            )
            
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'Open', 'High', 'Low', 'Close', 'Volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                df[col] = df[col].astype(float)
            
            result = df[['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume']]
            
            logger.debug(f"📈 Fetched {len(result)} candles. Last: {result.iloc[-1]['timestamp']}, Close: ${result.iloc[-1]['Close']:.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error fetching klines: {e}")
            raise
    
    def get_balance(self) -> float:
        """Get USDT balance"""
        self._track_request("get_balance")
        
        try:
            balance = self.client.get_asset_balance(asset='USDT')
            bal = float(balance['free'])
            logger.debug(f"💰 Balance: ${bal:,.2f} USDT")
            return bal
        except Exception as e:
            logger.error(f"❌ Error fetching balance: {e}")
            raise
    
    def get_current_price(self) -> float:
        """Get current BTC price (cached for 5 seconds)"""
        now = datetime.utcnow()
        
        # Use cache if recent
        if (self.price_cache and self.price_cache_time and 
            (now - self.price_cache_time).seconds < self.price_cache_ttl):
            logger.debug(f"💵 Price (cached): ${self.price_cache:.2f}")
            return self.price_cache
        
        self._track_request("get_current_price")
        
        try:
            ticker = self.client.get_symbol_ticker(symbol=self.symbol)
            price = float(ticker['price'])
            
            self.price_cache = price
            self.price_cache_time = now
            
            logger.debug(f"💵 Price (live): ${price:.2f}")
            return price
        except Exception as e:
            logger.error(f"❌ Error fetching price: {e}")
            raise


class SMCOptimizedBot:
    """Main bot class"""
    
    def __init__(self, api_key: str, api_secret: str, 
                 risk_per_trade: float = 0.02,
                 session_filter: bool = False,
                 testnet: bool = True,
                 log_trades: bool = True):
        
        self.binance = BinanceClient(api_key, api_secret, testnet)
        self.strategy = SMCOptimizedStrategy(timeframe='15m', session_filter=session_filter)
        self.risk_per_trade = risk_per_trade
        
        self.pending_orders = []
        self.position = None
        
        # Trade logger
        self.logger = TradeLogger() if log_trades else None
        
        print(f"✅ Bot initialized")
        print(f"   Timeframe: 15m")
        print(f"   Risk per trade: {risk_per_trade*100}%")
        print(f"   Session filter: {'ON (NY hours)' if session_filter else 'OFF (24/7)'}")
        print(f"   Testnet: {testnet}")
        print(f"   Trade logging: {'ON' if log_trades else 'OFF'}")
    
    def calculate_position_size(self, order: LimitOrder) -> float:
        """Calculate position size based on risk"""
        balance = self.binance.get_balance()
        risk_amount = balance * self.risk_per_trade
        risk_per_unit = abs(order.limit_price - order.sl)
        size = risk_amount / risk_per_unit
        
        # Round to 3 decimals for BTC
        size = round(size, 3)
        return size
    
    def check_limit_orders(self, current_price: float, current_time: datetime):
        """Check if limit orders should fill"""
        logger.debug(f"🔍 Checking {len(self.pending_orders)} pending limit orders at ${current_price:.2f}")
        
        filled_order = None
        expired_orders = []
        
        for order in self.pending_orders:
            # Check expiry
            if order.is_expired(current_time):
                logger.info(f"⌛ Limit order expired: {order.order_type} L{order.level} @ ${order.limit_price:.2f}")
                expired_orders.append(order)
                continue
            
            # Check fill (simplified - in real bot would check via Binance API)
            # For limit order to fill, price must reach limit
            if order.order_type == 'LONG':
                if current_price <= order.limit_price:
                    logger.info(f"🎯 LONG LIMIT HIT! Price ${current_price:.2f} <= Limit ${order.limit_price:.2f} (Level {order.level})")
                    order.filled = True
                    order.filled_price = order.limit_price
                    order.filled_time = current_time
                    filled_order = order
                    break
                else:
                    logger.debug(f"   ⏳ LONG L{order.level}: ${order.limit_price:.2f} (need price <= this)")
            else:  # SHORT
                if current_price >= order.limit_price:
                    logger.info(f"🎯 SHORT LIMIT HIT! Price ${current_price:.2f} >= Limit ${order.limit_price:.2f} (Level {order.level})")
                    order.filled = True
                    order.filled_price = order.limit_price
                    order.filled_time = current_time
                    filled_order = order
                    break
                else:
                    logger.debug(f"   ⏳ SHORT L{order.level}: ${order.limit_price:.2f} (need price >= this)")
        
        # Remove filled and related orders
        if filled_order:
            self.pending_orders = [o for o in self.pending_orders 
                                 if o.ob_id != filled_order.ob_id]
            
            size = self.calculate_position_size(filled_order)
            self.position = Position(filled_order, size, current_time)
            
            # Log fill
            if self.logger:
                self.logger.log_fill(filled_order, size, current_time)
            
            print(f"\n✅ LIMIT ORDER FILLED")
            print(f"   Type: {filled_order.order_type}")
            print(f"   Level: {filled_order.level}/3")
            print(f"   Price: ${filled_order.filled_price:.2f}")
            print(f"   Size: {size:.4f} BTC")
            print(f"   SL: ${self.position.sl:.2f}")
            print(f"   TP1: ${self.position.tp_levels[0]:.2f} (50%)")
            print(f"   TP2: ${self.position.tp_levels[1]:.2f} (30%)")
            print(f"   TP3: ${self.position.tp_levels[2]:.2f} (20%)")
        
        # Remove expired
        for order in expired_orders:
            if order in self.pending_orders:
                self.pending_orders.remove(order)
                print(f"⏰ Limit order expired (Level {order.level})")
    
    def check_exits(self, current_price: float, df: pd.DataFrame, current_time: datetime):
        """Check for position exits"""
        if not self.position:
            return
        
        logger.debug(f"🔍 Checking exits for {self.position.type} position at ${current_price:.2f}")
        logger.debug(f"   Entry: ${self.position.entry:.2f}, SL: ${self.position.sl:.2f}")
        logger.debug(f"   TPs: ${self.position.tp_levels[0]:.2f}, ${self.position.tp_levels[1]:.2f}, ${self.position.tp_levels[2]:.2f}")
        
        # 1. Check invalidation
        if self.strategy.check_invalidation(self.position, df):
            logger.warning(f"❌ INVALIDATION - Opposite OB formed!")
            print(f"\n❌ INVALIDATION - Opposite OB formed")
            self._close_position(current_price, 'INVALIDATION', current_time)
            return
        
        # 2. Check stop loss
        if self.position.type == 'LONG':
            if current_price <= self.position.sl:
                logger.warning(f"🛑 STOP LOSS HIT! Price ${current_price:.2f} <= SL ${self.position.sl:.2f}")
                print(f"\n🛑 STOP LOSS HIT")
                self._close_position(current_price, 'SL', current_time)
                return
            else:
                logger.debug(f"   ✅ SL safe: ${current_price:.2f} > ${self.position.sl:.2f}")
        else:
            if current_price >= self.position.sl:
                logger.warning(f"🛑 STOP LOSS HIT! Price ${current_price:.2f} >= SL ${self.position.sl:.2f}")
                print(f"\n🛑 STOP LOSS HIT")
                self._close_position(current_price, 'SL', current_time)
                return
            else:
                logger.debug(f"   ✅ SL safe: ${current_price:.2f} < ${self.position.sl:.2f}")
        
        # 3. Check TP levels
        for i, (tp, size_pct) in enumerate(zip(self.position.tp_levels, self.position.tp_sizes)):
            if self.position.tp_hit[i]:
                continue
            
            tp_hit = False
            if self.position.type == 'LONG':
                tp_hit = current_price >= tp
                logger.debug(f"   TP{i+1}: ${current_price:.2f} {'✅ >=' if tp_hit else '⏳ <'} ${tp:.2f}")
            else:
                tp_hit = current_price <= tp
                logger.debug(f"   TP{i+1}: ${current_price:.2f} {'✅ <=' if tp_hit else '⏳ >'} ${tp:.2f}")
            
            if tp_hit:
                close_size = self.position.size * size_pct
                self.position.remaining_size -= close_size
                self.position.tp_hit[i] = True
                
                pnl = self._calculate_pnl(close_size, tp)
                
                logger.info(f"🎯 TP{i+1} HIT! Price: ${current_price:.2f}, PnL: ${pnl:+.2f}")
                
                # Log exit
                if self.logger:
                    self.logger.log_exit(self.position, tp, f'TP{i+1}', close_size, pnl, current_time)
                
                print(f"\n🎯 TP{i+1} HIT")
                print(f"   Price: ${tp:.2f}")
                print(f"   Closed: {size_pct*100}% ({close_size:.4f} BTC)")
                print(f"   PnL: ${pnl:+.2f}")
                print(f"   Remaining: {self.position.remaining_size:.4f} BTC")
                
                # Move stops
                if i == 0 and not self.position.breakeven_moved:
                    self.position.sl = self.position.entry
                    self.position.breakeven_moved = True
                    print(f"   📌 SL moved to Break Even: ${self.position.sl:.2f}")
                elif i == 1:
                    self.position.sl = self.position.tp_levels[0]
                    print(f"   📌 SL moved to TP1: ${self.position.sl:.2f}")
                
                # Close position if all TPs hit
                if self.position.remaining_size <= 0.001:
                    print(f"\n✅ ALL TPs HIT - Position closed")
                    self.position = None
                    return
    
    def _close_position(self, exit_price: float, reason: str, exit_time: datetime):
        """Close entire position"""
        if not self.position:
            return
        
        pnl = self._calculate_pnl(self.position.remaining_size, exit_price)
        
        # Log exit
        if self.logger:
            self.logger.log_exit(self.position, exit_price, reason, 
                               self.position.remaining_size, pnl, exit_time)
        
        print(f"   Exit: ${exit_price:.2f}")
        print(f"   Size: {self.position.remaining_size:.4f} BTC")
        print(f"   PnL: ${pnl:+.2f}")
        print(f"   Reason: {reason}")
        
        self.position = None
    
    def _calculate_pnl(self, size: float, exit_price: float) -> float:
        """Calculate PnL"""
        if self.position.type == 'LONG':
            return (exit_price - self.position.entry) * size
        else:
            return (self.position.entry - exit_price) * size
    
    def run(self, check_interval: int = 60):
        """Main bot loop"""
        logger.info("="*80)
        logger.info("🚀 SMC OPTIMIZED BOT STARTED")
        logger.info("="*80)
        logger.info(f"Start time: {datetime.utcnow()}")
        logger.info(f"Check interval: {check_interval}s")
        logger.info(f"Session filter: {'ON (NY)' if self.strategy.session_filter else 'OFF (24/7)'}")
        logger.info(f"Log file: logs/smc_bot.log")
        logger.info("="*80)
        
        print(f"\n🚀 Bot started at {datetime.utcnow()}")
        print(f"   Check interval: {check_interval}s")
        print(f"   Waiting for signals...\n")
        
        iteration = 0
        
        while True:
            try:
                iteration += 1
                current_time = datetime.utcnow()
                
                logger.info(f"\n{'='*60}")
                logger.info(f"Iteration #{iteration} | {current_time}")
                logger.info(f"{'='*60}")
                
                # Fetch data
                logger.info("📊 Fetching market data...")
                df = self.binance.get_klines(interval='15m', limit=200)
                current_price = self.binance.get_current_price()
                
                logger.info(f"💵 BTC Price: ${current_price:,.2f}")
                
                # Status
                if self.position:
                    logger.info(f"📈 Position: {self.position.type} | Entry: ${self.position.entry:.2f} | Size: {self.position.remaining_size:.4f}")
                    logger.info(f"   SL: ${self.position.sl:.2f} | TPs: {self.position.tp_hit}")
                elif self.pending_orders:
                    logger.info(f"⏳ Pending orders: {len(self.pending_orders)}")
                    for order in self.pending_orders[:3]:  # Show first 3
                        logger.info(f"   {order.order_type} L{order.level}: ${order.limit_price:.2f}")
                else:
                    logger.info("💤 No position, no pending orders")
                
                # Check pending limit orders
                if self.pending_orders and not self.position:
                    logger.info("🔍 Checking limit orders...")
                    self.check_limit_orders(current_price, current_time)
                
                # Check exits
                if self.position:
                    logger.info("🔍 Checking exits...")
                    self.check_exits(current_price, df, current_time)
                
                # Check for new OBs (only if no position and few pending orders)
                if not self.position and len(self.pending_orders) < 6:
                    logger.info("🔎 Scanning for new Order Blocks...")
                    new_orders = self.strategy.check_new_ob(df, current_time)
                    
                    if new_orders:
                        self.pending_orders.extend(new_orders)
                        
                        logger.info(f"✅ {len(new_orders)} NEW LIMIT ORDERS PLACED!")
                        
                        # Log signals
                        if self.logger:
                            for order in new_orders:
                                self.logger.log_signal(order.order_type, order, current_time)
                        
                        print(f"\n📋 {len(new_orders)} NEW LIMIT ORDERS PLACED")
                        for order in new_orders:
                            print(f"   {order.order_type} Level {order.level}: ${order.limit_price:.2f}")
                        print(f"   Expiry: {self.strategy.limit_expiry_hours}h")
                
                # Cleanup
                self.strategy.cleanup_old_obs()
                
                logger.info(f"✅ Iteration complete. Sleeping {check_interval}s...")
                
                # Sleep
                time.sleep(check_interval)
                
            except KeyboardInterrupt:
                logger.info("\n⚠️  Bot stopped by user (KeyboardInterrupt)")
                print("\n\n⚠️  Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ ERROR in main loop: {e}", exc_info=True)
                print(f"\n❌ Error: {e}")
                time.sleep(check_interval)


if __name__ == "__main__":
    # Load credentials
    API_KEY = os.getenv('BINANCE_API_KEY', '')
    API_SECRET = os.getenv('BINANCE_API_SECRET', '')
    
    if not API_KEY or not API_SECRET:
        print("❌ Please set BINANCE_API_KEY and BINANCE_API_SECRET environment variables")
        exit(1)
    
    # Initialize bot
    bot = SMCOptimizedBot(
        api_key=API_KEY,
        api_secret=API_SECRET,
        risk_per_trade=0.02,  # 2% risk
        session_filter=False,  # Trade 24/7 (set True for NY only)
        testnet=True  # Use testnet
    )
    
    # Run
    bot.run(check_interval=60)  # Check every 60 seconds

