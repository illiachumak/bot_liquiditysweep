"""
Failed 4H FVG Live Trading Bot
Trades rejected 4H FVGs with precise 15M entries

CRITICAL: Only use in DRY_RUN mode first!
"""

import os
import sys
import json
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict
from decimal import Decimal

import pandas as pd
import numpy as np
from dotenv import load_dotenv

# Binance
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException

# Futures support
USE_FUTURES = True  # Set to True for futures trading

# ============================================================================
# CONFIGURATION
# ============================================================================

load_dotenv()

API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
DRY_RUN = os.getenv('DRY_RUN', 'true').lower() == 'true'

SYMBOL = 'BTCUSDT'
TIMEFRAME_4H = '4h'
TIMEFRAME_15M = '15m'

# Strategy parameters
RISK_PER_TRADE = 0.02          # 2%
MIN_SL_PCT = 0.3               # 0.3%
MIN_RR = 2.0                   # Minimum RR for validation (same as backtest)
FIXED_RR = 3.0                 # 3.0 RR for TP calculation (optimized from backtest: 82% win rate, 1621% return, 9.43 profit factor)
LIMIT_EXPIRY_CANDLES = 16      # 4H (optimized from backtest)
COOLDOWN_CANDLES = 16          # 4H

# Fees
MAKER_FEE = 0.00018             # 0.0180% (0.0180 / 100 = 0.00018)
TAKER_FEE = 0.00045             # 0.0450% (0.0450 / 100 = 0.00045)

# Risk limits
MAX_DRAWDOWN_PCT = 15.0
MAX_DAILY_LOSS = 500.0
MAX_CONSECUTIVE_LOSSES = 5

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('live_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class LiveFVG:
    """Fair Value Gap for live trading"""
    id: str
    type: str  # 'BULLISH' or 'BEARISH'
    top: float
    bottom: float
    formed_time: datetime
    timeframe: str

    entered: bool = False
    rejected: bool = False
    invalidated: bool = False
    has_filled_trade: bool = False

    rejection_time: Optional[datetime] = None
    rejection_price: Optional[float] = None
    highs_inside: List[float] = field(default_factory=list)
    lows_inside: List[float] = field(default_factory=list)

    pending_setup_id: Optional[str] = None
    pending_expiry_time: Optional[datetime] = None

    def is_inside(self, price: float) -> bool:
        return self.bottom <= price <= self.top

    def is_fully_passed(self, high: float, low: float) -> bool:
        if self.type == 'BULLISH':
            return low < self.bottom
        else:
            return high > self.top

    def check_rejection(self, candle: Dict) -> bool:
        """Check if this candle rejects the FVG"""
        high = float(candle['high'])
        low = float(candle['low'])
        close = float(candle['close'])

        # Check if touched
        touched = not (high < self.bottom or low > self.top)
        if not touched:
            return False

        if not self.entered:
            self.entered = True
            logger.info(f"FVG entered: {self.timeframe} {self.type} ${self.bottom:.2f}-${self.top:.2f}")

        # Track highs/lows inside
        if high >= self.bottom:
            self.highs_inside.append(high)
        if low <= self.top:
            self.lows_inside.append(low)

        # Check rejection
        if self.type == 'BULLISH':
            if self.entered and close < self.bottom:
                if not self.rejected:
                    self.rejected = True
                    self.rejection_time = datetime.fromtimestamp(candle['close_time'] / 1000)
                    self.rejection_price = close
                    logger.info(f"🚫 REJECTION! Bullish FVG ${self.bottom:.2f}-${self.top:.2f} → SHORT setup")
                    return True
        else:  # BEARISH
            if self.entered and close > self.top:
                if not self.rejected:
                    self.rejected = True
                    self.rejection_time = datetime.fromtimestamp(candle['close_time'] / 1000)
                    self.rejection_price = close
                    logger.info(f"🚫 REJECTION! Bearish FVG ${self.bottom:.2f}-${self.top:.2f} → LONG setup")
                    return True

        return False

    def get_stop_loss(self) -> Optional[float]:
        """Get SL based on highs/lows inside zone"""
        if self.type == 'BULLISH':
            if self.highs_inside:
                return max(self.highs_inside) * 1.002
        else:
            if self.lows_inside:
                return min(self.lows_inside) * 0.998
        return None

    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'type': self.type,
            'top': self.top,
            'bottom': self.bottom,
            'formed_time': self.formed_time.isoformat(),
            'timeframe': self.timeframe,
            'entered': self.entered,
            'rejected': self.rejected,
            'invalidated': self.invalidated,
            'has_filled_trade': self.has_filled_trade,
            'rejection_time': self.rejection_time.isoformat() if self.rejection_time else None,
            'rejection_price': self.rejection_price,
            'highs_inside': self.highs_inside,
            'lows_inside': self.lows_inside,
            'pending_setup_id': self.pending_setup_id,
            'pending_expiry_time': self.pending_expiry_time.isoformat() if self.pending_expiry_time else None
        }

    @classmethod
    def from_dict(cls, data: Dict):
        data['formed_time'] = datetime.fromisoformat(data['formed_time'])
        if data['rejection_time']:
            data['rejection_time'] = datetime.fromisoformat(data['rejection_time'])
        if data['pending_expiry_time']:
            data['pending_expiry_time'] = datetime.fromisoformat(data['pending_expiry_time'])
        return cls(**data)


@dataclass
class PendingSetup:
    """Pending setup waiting for fill"""
    setup_id: str
    parent_4h_fvg_id: str
    fvg_15m_id: str

    order_id: Optional[int] = None
    direction: str = ''  # 'LONG' or 'SHORT'
    entry_price: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    size: float = 0.0

    created_time: Optional[datetime] = None
    expiry_time: Optional[datetime] = None

    status: str = 'PENDING'  # PENDING, FILLED, EXPIRED, CANCELLED
    fill_time: Optional[datetime] = None
    fill_price: Optional[float] = None

    def to_dict(self) -> Dict:
        return {
            'setup_id': self.setup_id,
            'parent_4h_fvg_id': self.parent_4h_fvg_id,
            'fvg_15m_id': self.fvg_15m_id,
            'order_id': self.order_id,
            'direction': self.direction,
            'entry_price': self.entry_price,
            'sl': self.sl,
            'tp': self.tp,
            'size': self.size,
            'created_time': self.created_time.isoformat() if self.created_time else None,
            'expiry_time': self.expiry_time.isoformat() if self.expiry_time else None,
            'status': self.status,
            'fill_time': self.fill_time.isoformat() if self.fill_time else None,
            'fill_price': self.fill_price
        }

    @classmethod
    def from_dict(cls, data: Dict):
        if data['created_time']:
            data['created_time'] = datetime.fromisoformat(data['created_time'])
        if data['expiry_time']:
            data['expiry_time'] = datetime.fromisoformat(data['expiry_time'])
        if data['fill_time']:
            data['fill_time'] = datetime.fromisoformat(data['fill_time'])
        return cls(**data)


@dataclass
class ActiveTrade:
    """Active trade being monitored"""
    trade_id: str
    setup_id: str

    entry_order_id: int = 0
    sl_order_id: int = 0
    tp_order_id: int = 0

    direction: str = ''
    entry_price: float = 0.0
    entry_time: Optional[datetime] = None
    sl: float = 0.0
    tp: float = 0.0
    size: float = 0.0

    current_pnl: float = 0.0
    max_pnl: float = 0.0
    max_dd: float = 0.0

    status: str = 'ACTIVE'
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: Optional[float] = None
    exit_reason: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            'trade_id': self.trade_id,
            'setup_id': self.setup_id,
            'entry_order_id': self.entry_order_id,
            'sl_order_id': self.sl_order_id,
            'tp_order_id': self.tp_order_id,
            'direction': self.direction,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time.isoformat() if self.entry_time else None,
            'sl': self.sl,
            'tp': self.tp,
            'size': self.size,
            'current_pnl': self.current_pnl,
            'status': self.status,
            'exit_price': self.exit_price,
            'exit_time': self.exit_time.isoformat() if self.exit_time else None,
            'pnl': self.pnl,
            'exit_reason': self.exit_reason
        }

    @classmethod
    def from_dict(cls, data: Dict):
        if data['entry_time']:
            data['entry_time'] = datetime.fromisoformat(data['entry_time'])
        if data['exit_time']:
            data['exit_time'] = datetime.fromisoformat(data['exit_time'])
        return cls(**data)


# ============================================================================
# FVG DETECTOR
# ============================================================================

class FVGDetector:
    """Detect FVGs from candle data"""

    @staticmethod
    def detect_fvgs(df: pd.DataFrame, timeframe: str) -> List[LiveFVG]:
        """Detect all FVGs in dataframe"""
        fvgs = []

        for i in range(2, len(df)):
            row = df.iloc[i]
            row_i2 = df.iloc[i-2]

            # Bullish FVG
            if row['low'] > row_i2['high']:
                fvg = LiveFVG(
                    id=f"{timeframe}_BULLISH_{row['low']:.2f}_{row_i2['high']:.2f}_{int(row.name.timestamp())}",
                    type='BULLISH',
                    top=row['low'],
                    bottom=row_i2['high'],
                    formed_time=row.name,
                    timeframe=timeframe
                )
                fvgs.append(fvg)

            # Bearish FVG
            elif row['high'] < row_i2['low']:
                fvg = LiveFVG(
                    id=f"{timeframe}_BEARISH_{row_i2['low']:.2f}_{row['high']:.2f}_{int(row.name.timestamp())}",
                    type='BEARISH',
                    top=row_i2['low'],
                    bottom=row['high'],
                    formed_time=row.name,
                    timeframe=timeframe
                )
                fvgs.append(fvg)

        return fvgs


# ============================================================================
# BINANCE CLIENT WRAPPER
# ============================================================================

class BinanceClientWrapper:
    """Wrapper for Binance client with error handling"""

    def __init__(self):
        if DRY_RUN:
            logger.info("🧪 DRY RUN MODE - Using Binance Testnet")
            self.client = Client(API_KEY, API_SECRET, testnet=True)
        else:
            logger.info("💰 LIVE TRADING MODE")
            self.client = Client(API_KEY, API_SECRET)

        # Futures support
        if USE_FUTURES:
            logger.info("📊 Using FUTURES API")
        else:
            logger.info("📊 Using SPOT API")

        # Get symbol info
        if USE_FUTURES:
            exchange_info = self.client.futures_exchange_info()
            self.symbol_info = None
            for s in exchange_info['symbols']:
                if s['symbol'] == SYMBOL:
                    self.symbol_info = s
                    break
        else:
            self.symbol_info = self.client.get_symbol_info(SYMBOL)

        self.lot_size_filter = None
        self.min_notional_filter = None

        if self.symbol_info:
            for f in self.symbol_info['filters']:
                if f['filterType'] == 'LOT_SIZE':
                    self.lot_size_filter = f
                elif f['filterType'] == 'NOTIONAL' or f['filterType'] == 'MIN_NOTIONAL':
                    self.min_notional_filter = f

        logger.info(f"Symbol info loaded: {SYMBOL}")

    def get_klines(self, symbol: str, interval: str, limit: int = 500) -> pd.DataFrame:
        """Fetch historical klines"""
        try:
            if USE_FUTURES:
                klines = self.client.futures_klines(symbol=symbol, interval=interval, limit=limit)
            else:
                klines = self.client.get_klines(symbol=symbol, interval=interval, limit=limit)

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

        except BinanceAPIException as e:
            logger.error(f"Error fetching klines: {e}")
            raise

    def get_current_price(self, symbol: str) -> float:
        """Get current price"""
        try:
            if USE_FUTURES:
                ticker = self.client.futures_symbol_ticker(symbol=symbol)
            else:
                ticker = self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except BinanceAPIException as e:
            logger.error(f"Error fetching price: {e}")
            raise

    def get_balance(self, asset: str = 'USDT') -> float:
        """Get balance - HARDCODED for futures account"""
        # HARDCODED: Using futures account with fixed balance
        logger.info("Using hardcoded balance: $300.00 (Futures account)")
        return 300.0

    def round_to_lot_size(self, quantity: float) -> float:
        """Round quantity to valid lot size"""
        step_size = float(self.lot_size_filter['stepSize'])
        precision = int(round(-np.log10(step_size), 0))
        return round(quantity, precision)

    def place_limit_order(self, symbol: str, side: str, quantity: float, price: float) -> Dict:
        """Place limit order"""
        try:
            quantity = self.round_to_lot_size(quantity)

            if USE_FUTURES:
                # Determine position side based on order direction (for Hedge Mode)
                position_side = "SHORT" if side == "SELL" else "LONG"

                order = self.client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type='LIMIT',
                    timeInForce='GTC',
                    quantity=quantity,
                    price=str(price),
                    positionSide=position_side
                )
            else:
                order = self.client.create_order(
                    symbol=symbol,
                    side=side,
                    type=ORDER_TYPE_LIMIT,
                    timeInForce=TIME_IN_FORCE_GTC,
                    quantity=quantity,
                    price=str(price)
                )

            logger.info(f"✅ Limit order placed: {side} {quantity} @ ${price:.2f}, OrderID: {order['orderId']}")
            return order

        except BinanceAPIException as e:
            logger.error(f"Error placing limit order: {e}")
            raise

    def cancel_order(self, symbol: str, order_id: int):
        """Cancel order"""
        try:
            if USE_FUTURES:
                result = self.client.futures_cancel_order(symbol=symbol, orderId=order_id)
            else:
                result = self.client.cancel_order(symbol=symbol, orderId=order_id)
            logger.info(f"❌ Order cancelled: {order_id}")
            return result
        except BinanceAPIException as e:
            logger.error(f"Error cancelling order {order_id}: {e}")
            raise

    def get_order(self, symbol: str, order_id: int) -> Dict:
        """Get order status"""
        try:
            if USE_FUTURES:
                return self.client.futures_get_order(symbol=symbol, orderId=order_id)
            else:
                return self.client.get_order(symbol=symbol, orderId=order_id)
        except BinanceAPIException as e:
            logger.error(f"Error fetching order {order_id}: {e}")
            raise

    def place_oco_order(self, symbol: str, side: str, quantity: float, price: float,
                       stop_price: float, stop_limit_price: float) -> Dict:
        """Place OCO order (TP + SL) - For futures: separate TP/SL orders"""
        try:
            quantity = self.round_to_lot_size(quantity)

            if USE_FUTURES:
                # Futures doesn't support OCO, use separate TP and SL orders
                # Determine position side: SELL closes LONG, BUY closes SHORT
                position_side = "LONG" if side == "SELL" else "SHORT"

                # Place TP order (TAKE_PROFIT_MARKET)
                tp_order = self.client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type='TAKE_PROFIT_MARKET',
                    stopPrice=str(price),
                    closePosition='true',
                    positionSide=position_side
                )

                # Place SL order (STOP_MARKET)
                sl_order = self.client.futures_create_order(
                    symbol=symbol,
                    side=side,
                    type='STOP_MARKET',
                    stopPrice=str(stop_limit_price),
                    closePosition='true',
                    positionSide=position_side
                )

                logger.info(f"✅ Futures TP/SL orders placed: {side} {quantity}, TP=${price:.2f}, SL=${stop_limit_price:.2f}")

                # Return combined response
                return {
                    'orders': [
                        {'orderId': tp_order['orderId'], 'type': 'TAKE_PROFIT_MARKET'},
                        {'orderId': sl_order['orderId'], 'type': 'STOP_MARKET'}
                    ]
                }
            else:
                # Spot OCO order
                order = self.client.create_oco_order(
                    symbol=symbol,
                    side=side,
                    quantity=quantity,
                    price=str(price),  # TP price
                    stopPrice=str(stop_price),
                    stopLimitPrice=str(stop_limit_price),
                    stopLimitTimeInForce=TIME_IN_FORCE_GTC
                )

                logger.info(f"✅ OCO order placed: {side} {quantity}, TP=${price:.2f}, SL=${stop_limit_price:.2f}")
                return order

        except BinanceAPIException as e:
            logger.error(f"Error placing OCO/TP-SL order: {e}")
            raise


# ============================================================================
# FAILED FVG LIVE BOT
# ============================================================================

class FailedFVGLiveBot:
    """Main live trading bot"""

    def __init__(self):
        self.client = BinanceClientWrapper()
        self.detector = FVGDetector()

        # State
        self.active_4h_fvgs: List[LiveFVG] = []
        self.rejected_4h_fvgs: List[LiveFVG] = []
        self.pending_setups: List[PendingSetup] = []
        self.active_trade: Optional[ActiveTrade] = None

        # Data
        self.df_4h: Optional[pd.DataFrame] = None
        self.df_15m: Optional[pd.DataFrame] = None

        # Candle timestamps tracking
        self.last_4h_candle_time: Optional[pd.Timestamp] = None
        self.last_15m_candle_time: Optional[pd.Timestamp] = None

        # Stats
        self.balance = 0.0
        self.initial_balance = 0.0
        self.trades_history: List[Dict] = []
        self.consecutive_losses = 0

        self.running = False

    def initialize(self):
        """Initialize bot - fetch data, restore state"""
        logger.info("="*80)
        logger.info("FAILED 4H FVG LIVE BOT - INITIALIZATION")
        logger.info("="*80)

        # Pre-flight check
        if not self.pre_flight_check():
            logger.critical("❌ Pre-flight check failed!")
            sys.exit(1)

        # Fetch initial data
        logger.info("Fetching historical data...")
        self.df_4h = self.client.get_klines(SYMBOL, TIMEFRAME_4H, limit=200)
        self.df_15m = self.client.get_klines(SYMBOL, TIMEFRAME_15M, limit=1000)
        logger.info(f"Loaded {len(self.df_4h)} 4H candles, {len(self.df_15m)} 15M candles")

        # Store last candle timestamps
        self.last_4h_candle_time = self.df_4h.index[-1]
        self.last_15m_candle_time = self.df_15m.index[-1]
        logger.info(f"Last 4H candle: {self.last_4h_candle_time}")
        logger.info(f"Last 15M candle: {self.last_15m_candle_time}")

        # Detect initial FVGs
        logger.info("Detecting initial FVGs...")
        self.active_4h_fvgs = self.detector.detect_fvgs(self.df_4h, '4h')
        logger.info(f"Found {len(self.active_4h_fvgs)} 4H FVGs")

        # Get balance
        self.balance = self.client.get_balance('USDT')
        self.initial_balance = self.balance
        logger.info(f"Balance: ${self.balance:.2f} USDT")

        # Try to restore state
        self.restore_state()

        logger.info("✅ Initialization complete")
        logger.info("="*80)

    def pre_flight_check(self) -> bool:
        """Run pre-flight checks"""
        logger.info("Running pre-flight checks...")

        checks = []

        # API connection
        try:
            self.client.client.get_account()
            checks.append(('API Connection', True))
        except Exception as e:
            checks.append(('API Connection', False))
            logger.error(f"API connection failed: {e}")

        # Balance
        try:
            balance = self.client.get_balance('USDT')
            if balance >= 10:  # Min $10
                checks.append(('Balance', True))
            else:
                checks.append(('Balance', False))
                logger.error(f"Insufficient balance: ${balance:.2f}")
        except Exception as e:
            checks.append(('Balance', False))
            logger.error(f"Balance check failed: {e}")

        # Symbol info
        if self.client.symbol_info:
            checks.append(('Symbol Info', True))
        else:
            checks.append(('Symbol Info', False))

        # State file writable
        try:
            with open('state.json', 'w') as f:
                json.dump({}, f)
            checks.append(('State File', True))
        except Exception as e:
            checks.append(('State File', False))
            logger.error(f"State file check failed: {e}")

        # Print results
        for check, passed in checks:
            status = '✅' if passed else '❌'
            logger.info(f"{status} {check}")

        return all(passed for _, passed in checks)

    def restore_state(self):
        """Restore state from disk"""
        try:
            with open('state.json', 'r') as f:
                state = json.load(f)

            if state:
                logger.info("Restoring state from disk...")

                # Restore FVGs
                if 'active_4h_fvgs' in state:
                    self.active_4h_fvgs = [LiveFVG.from_dict(d) for d in state['active_4h_fvgs']]
                if 'rejected_4h_fvgs' in state:
                    self.rejected_4h_fvgs = [LiveFVG.from_dict(d) for d in state['rejected_4h_fvgs']]

                # Restore setups
                if 'pending_setups' in state:
                    self.pending_setups = [PendingSetup.from_dict(d) for d in state['pending_setups']]

                # Restore active trade
                if state.get('active_trade'):
                    self.active_trade = ActiveTrade.from_dict(state['active_trade'])

                # Restore candle timestamps
                if 'last_4h_candle_time' in state and state['last_4h_candle_time']:
                    self.last_4h_candle_time = pd.Timestamp(state['last_4h_candle_time'])
                if 'last_15m_candle_time' in state and state['last_15m_candle_time']:
                    self.last_15m_candle_time = pd.Timestamp(state['last_15m_candle_time'])

                logger.info(f"Restored: {len(self.active_4h_fvgs)} active FVGs, "
                          f"{len(self.rejected_4h_fvgs)} rejected FVGs, "
                          f"{len(self.pending_setups)} pending setups")
                if self.last_4h_candle_time:
                    logger.info(f"Last 4H candle: {self.last_4h_candle_time}")
                if self.last_15m_candle_time:
                    logger.info(f"Last 15M candle: {self.last_15m_candle_time}")

        except FileNotFoundError:
            logger.info("No state file found, starting fresh")
        except Exception as e:
            logger.error(f"Error restoring state: {e}")

    def save_state(self):
        """Save state to disk"""
        try:
            state = {
                'active_4h_fvgs': [fvg.to_dict() for fvg in self.active_4h_fvgs],
                'rejected_4h_fvgs': [fvg.to_dict() for fvg in self.rejected_4h_fvgs],
                'pending_setups': [setup.to_dict() for setup in self.pending_setups],
                'active_trade': self.active_trade.to_dict() if self.active_trade else None,
                'balance': self.balance,
                'last_4h_candle_time': self.last_4h_candle_time.isoformat() if self.last_4h_candle_time else None,
                'last_15m_candle_time': self.last_15m_candle_time.isoformat() if self.last_15m_candle_time else None,
                'last_updated': datetime.now().isoformat()
            }

            with open('state.json', 'w') as f:
                json.dump(state, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving state: {e}")

    def can_create_setup(self, rejected_fvg: LiveFVG) -> bool:
        """Check if we can create setup from this rejection"""

        # Already had filled trade
        if rejected_fvg.has_filled_trade:
            return False

        # Check cooldown
        if rejected_fvg.pending_expiry_time:
            if datetime.now() < rejected_fvg.pending_expiry_time:
                return False

        # Check if already has pending setup
        if rejected_fvg.pending_setup_id:
            for setup in self.pending_setups:
                if setup.setup_id == rejected_fvg.pending_setup_id and setup.status == 'PENDING':
                    return False

        return True

    def calculate_position_size(self, entry: float, sl: float) -> float:
        """Calculate position size based on risk"""
        risk_amount = self.balance * RISK_PER_TRADE
        risk_per_unit = abs(entry - sl)
        size = risk_amount / risk_per_unit

        # Round to lot size
        size = self.client.round_to_lot_size(size)

        # Check minimum notional
        notional = size * entry
        min_notional = 10.0  # Binance minimum
        if notional < min_notional:
            logger.warning(f"Notional ${notional:.2f} < ${min_notional:.2f}, increasing size")
            size = min_notional / entry
            size = self.client.round_to_lot_size(size)

        return size

    def validate_setup(self, entry: float, sl: float, tp: float) -> bool:
        """Validate setup parameters"""

        # SL distance
        sl_distance_pct = abs(entry - sl) / entry * 100
        if sl_distance_pct < MIN_SL_PCT:
            logger.warning(f"SL too tight: {sl_distance_pct:.3f}% < {MIN_SL_PCT}%")
            return False

        # RR ratio
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr = reward / risk
        if rr < MIN_RR:
            logger.warning(f"RR too low: {rr:.2f} < {MIN_RR}")
            return False

        # Price sanity
        current_price = self.client.get_current_price(SYMBOL)
        max_distance_pct = 5.0
        distance_pct = abs(entry - current_price) / current_price * 100
        if distance_pct > max_distance_pct:
            logger.warning(f"Entry too far from current: {distance_pct:.2f}% > {max_distance_pct}%")
            return False

        return True

    def create_setup_from_rejection(self, rejected_fvg: LiveFVG, fvg_15m: LiveFVG) -> Optional[PendingSetup]:
        """Create setup from rejected 4H FVG and 15M FVG"""

        # Determine direction
        if rejected_fvg.type == 'BULLISH':
            direction = 'SHORT'
            if fvg_15m.type != 'BEARISH':
                return None
            entry_price = fvg_15m.top
        else:
            direction = 'LONG'
            if fvg_15m.type != 'BULLISH':
                return None
            entry_price = fvg_15m.bottom

        # Get SL
        sl = rejected_fvg.get_stop_loss()
        if not sl:
            logger.warning("No SL available")
            return None

        # Calculate TP
        risk = abs(entry_price - sl)
        if direction == 'SHORT':
            tp = entry_price - (FIXED_RR * risk)
        else:
            tp = entry_price + (FIXED_RR * risk)

        # Validate
        if not self.validate_setup(entry_price, sl, tp):
            return None

        # Calculate size
        size = self.calculate_position_size(entry_price, sl)

        # Calculate expiry time based on 15M candles (16 candles = 4H)
        # Use last 15M candle time + 16 * 15 minutes for accuracy
        if self.df_15m is not None and len(self.df_15m) > 0:
            last_candle_time = self.df_15m.index[-1]
            expiry_time = last_candle_time + timedelta(minutes=15 * LIMIT_EXPIRY_CANDLES)
        else:
            # Fallback to current time + 4 hours if no data
            expiry_time = datetime.now() + timedelta(hours=4)
        
        # Create setup
        setup = PendingSetup(
            setup_id=f"setup_{int(datetime.now().timestamp())}",
            parent_4h_fvg_id=rejected_fvg.id,
            fvg_15m_id=fvg_15m.id,
            direction=direction,
            entry_price=entry_price,
            sl=sl,
            tp=tp,
            size=size,
            created_time=datetime.now(),
            expiry_time=expiry_time
        )

        logger.info(f"📋 Setup created: {direction} @ ${entry_price:.2f}, SL=${sl:.2f}, TP=${tp:.2f}, Size={size}")

        return setup

    def place_setup_order(self, setup: PendingSetup):
        """Place limit order for setup"""
        try:
            side = 'SELL' if setup.direction == 'SHORT' else 'BUY'

            order = self.client.place_limit_order(
                symbol=SYMBOL,
                side=side,
                quantity=setup.size,
                price=setup.entry_price
            )

            setup.order_id = order['orderId']
            setup.status = 'PENDING'

            self.pending_setups.append(setup)
            self.save_state()

            logger.info(f"✅ Limit order placed: OrderID {order['orderId']}")

        except Exception as e:
            logger.error(f"Failed to place setup order: {e}")

    def check_pending_setups(self):
        """Check status of pending setups"""
        for setup in self.pending_setups[:]:
            try:
                # Check if expired
                if datetime.now() >= setup.expiry_time:
                    self.handle_setup_expiry(setup)
                    continue

                # Check if filled
                order = self.client.get_order(SYMBOL, setup.order_id)

                if order['status'] == 'FILLED':
                    self.handle_setup_filled(setup, order)
                elif order['status'] in ['EXPIRED', 'CANCELED']:
                    self.handle_setup_expiry(setup)

            except Exception as e:
                logger.error(f"Error checking setup {setup.setup_id}: {e}")

    def handle_setup_filled(self, setup: PendingSetup, order: Dict):
        """Handle filled setup"""
        logger.info(f"🎯 Setup filled! OrderID: {order['orderId']}")

        setup.status = 'FILLED'
        setup.fill_time = datetime.now()
        setup.fill_price = float(order['price'])

        # Remove from pending
        self.pending_setups.remove(setup)

        # Mark parent FVG as has_filled_trade
        for fvg in self.rejected_4h_fvgs:
            if fvg.id == setup.parent_4h_fvg_id:
                fvg.has_filled_trade = True
                self.rejected_4h_fvgs.remove(fvg)
                break

        # Create active trade
        self.create_active_trade(setup)

        self.save_state()

    def handle_setup_expiry(self, setup: PendingSetup):
        """Handle expired setup"""
        logger.info(f"⏰ Setup expired: {setup.setup_id}")

        # Cancel order on Binance
        try:
            self.client.cancel_order(SYMBOL, setup.order_id)
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")

        setup.status = 'EXPIRED'
        self.pending_setups.remove(setup)

        # Set cooldown on parent FVG (16 candles = 4H)
        # Use last 15M candle time for accuracy
        if self.df_15m is not None and len(self.df_15m) > 0:
            last_candle_time = self.df_15m.index[-1]
            cooldown_time = last_candle_time + timedelta(minutes=15 * COOLDOWN_CANDLES)
        else:
            # Fallback to current time + 4 hours if no data
            cooldown_time = datetime.now() + timedelta(hours=4)
        
        for fvg in self.rejected_4h_fvgs:
            if fvg.id == setup.parent_4h_fvg_id:
                fvg.pending_expiry_time = cooldown_time
                logger.info(f"Cooldown set until {fvg.pending_expiry_time}")
                break

        self.save_state()

    def create_active_trade(self, setup: PendingSetup):
        """Create active trade and place SL/TP"""
        trade = ActiveTrade(
            trade_id=f"trade_{int(datetime.now().timestamp())}",
            setup_id=setup.setup_id,
            entry_order_id=setup.order_id,
            direction=setup.direction,
            entry_price=setup.entry_price,
            entry_time=setup.fill_time,
            sl=setup.sl,
            tp=setup.tp,
            size=setup.size
        )

        # Place SL/TP orders (OCO)
        try:
            side = 'SELL' if trade.direction == 'LONG' else 'BUY'

            # Calculate stop price (trigger price for stop-limit)
            if trade.direction == 'LONG':
                stop_price = trade.sl * 0.999  # Slightly below SL
            else:
                stop_price = trade.sl * 1.001  # Slightly above SL

            oco_order = self.client.place_oco_order(
                symbol=SYMBOL,
                side=side,
                quantity=trade.size,
                price=trade.tp,
                stop_price=stop_price,
                stop_limit_price=trade.sl
            )

            # Extract order IDs
            for order in oco_order['orders']:
                order_type = order['type']

                # Spot types
                if order_type == 'LIMIT_MAKER':
                    trade.tp_order_id = order['orderId']
                elif order_type == 'STOP_LOSS_LIMIT':
                    trade.sl_order_id = order['orderId']

                # Futures types
                elif order_type == 'TAKE_PROFIT_MARKET':
                    trade.tp_order_id = order['orderId']
                elif order_type == 'STOP_MARKET':
                    trade.sl_order_id = order['orderId']

            logger.info(f"✅ SL/TP orders placed: SL={trade.sl_order_id}, TP={trade.tp_order_id}")

        except Exception as e:
            logger.error(f"❌ Failed to place SL/TP: {e}")
            # CRITICAL: Emergency close position
            logger.critical("EMERGENCY: Closing position at market")
            # TODO: Implement emergency close

        self.active_trade = trade
        self.save_state()

        logger.info(f"🚀 Trade activated: {trade.direction} @ ${trade.entry_price:.2f}")

    def monitor_active_trade(self):
        """Monitor active trade"""
        if not self.active_trade:
            return

        try:
            # Check SL order
            sl_order = self.client.get_order(SYMBOL, self.active_trade.sl_order_id)
            if sl_order['status'] == 'FILLED':
                self.close_trade('SL', float(sl_order['price']))
                return

            # Check TP order
            tp_order = self.client.get_order(SYMBOL, self.active_trade.tp_order_id)
            if tp_order['status'] == 'FILLED':
                self.close_trade('TP', float(tp_order['price']))
                return

            # Update current PnL
            current_price = self.client.get_current_price(SYMBOL)
            if self.active_trade.direction == 'LONG':
                self.active_trade.current_pnl = (current_price - self.active_trade.entry_price) * self.active_trade.size
            else:
                self.active_trade.current_pnl = (self.active_trade.entry_price - current_price) * self.active_trade.size

        except Exception as e:
            logger.error(f"Error monitoring trade: {e}")

    def close_trade(self, reason: str, exit_price: float):
        """Close active trade"""
        if not self.active_trade:
            return

        self.active_trade.status = f'CLOSED_{reason}'
        self.active_trade.exit_time = datetime.now()
        self.active_trade.exit_price = exit_price
        self.active_trade.exit_reason = reason

        # Calculate PnL
        if self.active_trade.direction == 'LONG':
            pnl = (exit_price - self.active_trade.entry_price) * self.active_trade.size
        else:
            pnl = (self.active_trade.entry_price - exit_price) * self.active_trade.size

        # Apply fees
        entry_fee = self.active_trade.entry_price * self.active_trade.size * MAKER_FEE
        if reason == 'SL':
            exit_fee = exit_price * self.active_trade.size * TAKER_FEE
        else:
            exit_fee = exit_price * self.active_trade.size * MAKER_FEE

        pnl -= (entry_fee + exit_fee)
        self.active_trade.pnl = pnl

        # Update balance
        self.balance += pnl

        # Update stats
        if pnl > 0:
            self.consecutive_losses = 0
            emoji = "✅"
        else:
            self.consecutive_losses += 1
            emoji = "❌"

        pnl_pct = (pnl / (self.active_trade.entry_price * self.active_trade.size)) * 100

        logger.info(f"{emoji} Trade closed: {reason} | PnL: ${pnl:+.2f} ({pnl_pct:+.2f}%) | Balance: ${self.balance:.2f}")

        # Save to history
        self.trades_history.append(self.active_trade.to_dict())

        # Clear active trade
        self.active_trade = None

        self.save_state()

    def update_4h_fvgs(self, candle: Dict):
        """Update 4H FVGs with new candle"""
        # Check rejections
        for fvg in self.active_4h_fvgs[:]:
            if not fvg.rejected:
                fvg.check_rejection(candle)

                # If rejected, add to rejected list
                if fvg.rejected:
                    self.rejected_4h_fvgs.append(fvg)

            # Check invalidation
            high = float(candle['high'])
            low = float(candle['low'])
            if fvg.is_fully_passed(high, low):
                fvg.invalidated = True
                self.active_4h_fvgs.remove(fvg)
                # DON'T remove from rejected_4h_fvgs yet - will be checked on 15M data

        # Detect new FVGs from already updated df_4h (no re-fetch needed)
        new_fvgs = self.detector.detect_fvgs(self.df_4h.tail(10), '4h')

        for fvg in new_fvgs:
            if not any(existing.id == fvg.id for existing in self.active_4h_fvgs):
                self.active_4h_fvgs.append(fvg)
                logger.info(f"New 4H FVG detected: {fvg.type} ${fvg.bottom:.2f}-${fvg.top:.2f}")

    def look_for_setups(self):
        """Look for setup opportunities"""
        if self.active_trade:
            return

        if not self.rejected_4h_fvgs:
            return

        # Use already updated 15M data (no re-fetch needed)
        current_candle_15m = self.df_15m.iloc[-1]

        for rejected_fvg in self.rejected_4h_fvgs[:]:
            # Check if 4H FVG is invalidated on current 15M candle
            if rejected_fvg.is_fully_passed(float(current_candle_15m['high']), float(current_candle_15m['low'])):
                logger.info(f"4H FVG {rejected_fvg.id} invalidated, removing from rejected list")
                rejected_fvg.invalidated = True
                self.rejected_4h_fvgs.remove(rejected_fvg)
                continue

            if not self.can_create_setup(rejected_fvg):
                continue

            # Look for 15M FVG
            fvgs_15m = self.detector.detect_fvgs(self.df_15m.tail(10), '15m')

            if fvgs_15m:
                fvg_15m = fvgs_15m[-1]  # Most recent

                # Try to create setup
                setup = self.create_setup_from_rejection(rejected_fvg, fvg_15m)

                if setup:
                    # Place order
                    self.place_setup_order(setup)

                    # Mark FVG as having pending setup
                    rejected_fvg.pending_setup_id = setup.setup_id

                    # Only one setup at a time
                    break

    def check_emergency_stop(self) -> bool:
        """Check if we should stop trading"""

        # Max drawdown
        if self.initial_balance > 0:
            dd = (self.initial_balance - self.balance) / self.initial_balance * 100
            if dd > MAX_DRAWDOWN_PCT:
                logger.critical(f"🚨 MAX DRAWDOWN EXCEEDED: {dd:.2f}% > {MAX_DRAWDOWN_PCT}%")
                return True

        # Consecutive losses
        if self.consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
            logger.critical(f"🚨 MAX CONSECUTIVE LOSSES: {self.consecutive_losses} >= {MAX_CONSECUTIVE_LOSSES}")
            return True

        return False

    def check_new_4h_candle(self) -> bool:
        """Check if new 4H candle appeared (by timestamp)"""
        try:
            # Fetch latest 4H data
            df_new = self.client.get_klines(SYMBOL, TIMEFRAME_4H, limit=50)

            if df_new.empty:
                return False

            latest_candle_time = df_new.index[-1]

            # Check if new candle appeared
            if self.last_4h_candle_time is None or latest_candle_time > self.last_4h_candle_time:
                logger.info(f"🕯️  New 4H candle detected!")
                logger.info(f"   Previous: {self.last_4h_candle_time}")
                logger.info(f"   Current:  {latest_candle_time}")

                # Update data
                self.df_4h = df_new
                last_candle = self.df_4h.iloc[-1].to_dict()

                # Add close_time to candle dict for check_rejection
                last_candle['close_time'] = int(latest_candle_time.timestamp() * 1000)

                # Update FVGs with the NEW candle
                self.update_4h_fvgs(last_candle)

                # Update timestamp
                self.last_4h_candle_time = latest_candle_time

                return True

            return False

        except Exception as e:
            logger.error(f"Error checking new 4H candle: {e}")
            return False

    def check_new_15m_candle(self) -> bool:
        """Check if new 15M candle appeared (by timestamp)"""
        try:
            # Fetch latest 15M data
            df_new = self.client.get_klines(SYMBOL, TIMEFRAME_15M, limit=50)

            if df_new.empty:
                return False

            latest_candle_time = df_new.index[-1]

            # Check if new candle appeared
            if self.last_15m_candle_time is None or latest_candle_time > self.last_15m_candle_time:
                logger.info(f"🕯️  New 15M candle detected: {latest_candle_time}")

                # Update data
                self.df_15m = df_new

                # Update timestamp
                self.last_15m_candle_time = latest_candle_time

                return True

            return False

        except Exception as e:
            logger.error(f"Error checking new 15M candle: {e}")
            return False

    def run(self):
        """Main loop"""
        self.running = True

        logger.info("🚀 Bot started! Entering main loop...")
        logger.info("Press Ctrl+C to stop")

        last_state_save = datetime.now()

        try:
            while self.running:
                now = datetime.now()

                # Check emergency stop
                if self.check_emergency_stop():
                    logger.critical("Emergency stop triggered!")
                    break

                # Check for new 4H candle (by timestamp comparison)
                new_4h = self.check_new_4h_candle()
                if new_4h:
                    logger.info("✅ 4H candle processed")

                # Check for new 15M candle (by timestamp comparison)
                new_15m = self.check_new_15m_candle()
                if new_15m:
                    logger.info("Checking 15M logic...")

                    # Check pending setups
                    self.check_pending_setups()

                    # Look for new setups
                    if not self.active_trade and not self.pending_setups:
                        self.look_for_setups()

                    # Monitor active trade
                    self.monitor_active_trade()

                # Save state every 5 minutes
                if (now - last_state_save).total_seconds() >= 300:
                    self.save_state()
                    last_state_save = now

                # Sleep - check every 30 seconds for new candles
                time.sleep(30)

        except KeyboardInterrupt:
            logger.info("\n⚠️  Keyboard interrupt received")

        finally:
            self.shutdown()

    def shutdown(self):
        """Shutdown bot gracefully"""
        logger.info("="*80)
        logger.info("SHUTTING DOWN")
        logger.info("="*80)

        # Cancel all pending orders
        logger.info("Cancelling all pending orders...")
        for setup in self.pending_setups:
            try:
                self.client.cancel_order(SYMBOL, setup.order_id)
            except Exception as e:
                logger.error(f"Error cancelling order {setup.order_id}: {e}")

        # Save final state
        logger.info("Saving state...")
        self.save_state()

        # Print summary
        logger.info(f"Final balance: ${self.balance:.2f}")
        logger.info(f"Total trades: {len(self.trades_history)}")
        if self.trades_history:
            wins = sum(1 for t in self.trades_history if t.get('pnl', 0) > 0)
            logger.info(f"Win rate: {wins/len(self.trades_history)*100:.1f}%")

        logger.info("✅ Shutdown complete")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point"""

    # Print warning
    if not DRY_RUN:
        logger.warning("="*80)
        logger.warning("⚠️  WARNING: LIVE TRADING MODE - REAL MONEY")
        logger.warning("="*80)
        logger.warning("This bot will trade with REAL MONEY on Binance.")
        logger.warning("Ensure you understand the risks before running.")
        logger.warning("Set DRY_RUN=true in .env for testnet mode.")
        logger.warning("="*80)
    else:
        logger.info("🧪 DRY RUN MODE - Using Binance Testnet")

    # Create and run bot
    bot = FailedFVGLiveBot()
    bot.initialize()
    bot.run()


if __name__ == '__main__':
    main()
