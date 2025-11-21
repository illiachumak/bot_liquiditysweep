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
import os

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('logs/live_bot.log'),
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
            logger.info(f"✅ FVG entered: {self.timeframe} {self.type} ${self.bottom:.2f}-${self.top:.2f}")

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
                    expected_direction = "SHORT"
                    expected_15m = "BEARISH"
                    logger.info(f"🚫 REJECTION! Bullish FVG ${self.bottom:.2f}-${self.top:.2f} → {expected_direction} setup")
                    logger.info(f"   Rejected @ ${close:.2f} (closed below bottom ${self.bottom:.2f})")
                    logger.info(f"   Expected: {expected_direction} trade with 15M {expected_15m} FVG")
                    return True
        else:  # BEARISH
            if self.entered and close > self.top:
                if not self.rejected:
                    self.rejected = True
                    self.rejection_time = datetime.fromtimestamp(candle['close_time'] / 1000)
                    self.rejection_price = close
                    expected_direction = "LONG"
                    expected_15m = "BULLISH"
                    logger.info(f"🚫 REJECTION! Bearish FVG ${self.bottom:.2f}-${self.top:.2f} → {expected_direction} setup")
                    logger.info(f"   Rejected @ ${close:.2f} (closed above top ${self.top:.2f})")
                    logger.info(f"   Expected: {expected_direction} trade with 15M {expected_15m} FVG")
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

class MockBinanceClient:
    """Mock client for simulation mode"""

    def __init__(self, df_4h: pd.DataFrame, df_15m: pd.DataFrame):
        self.df_4h = df_4h
        self.df_15m = df_15m
        self.current_4h_idx = 0
        self.current_15m_idx = 0
        self.symbol_info = {'filters': []}

    def get_klines(self, symbol: str, interval: str, limit: int = 100) -> pd.DataFrame:
        """Return historical data up to current simulation point"""
        if interval == TIMEFRAME_4H:
            end_idx = min(self.current_4h_idx + 1, len(self.df_4h))
            start_idx = max(0, end_idx - limit)
            return self.df_4h.iloc[start_idx:end_idx].copy()
        else:  # 15M
            end_idx = min(self.current_15m_idx + 1, len(self.df_15m))
            start_idx = max(0, end_idx - limit)
            return self.df_15m.iloc[start_idx:end_idx].copy()

    def get_current_price(self, symbol: str) -> float:
        """Return current price in simulation"""
        if self.current_15m_idx < len(self.df_15m):
            return float(self.df_15m.iloc[self.current_15m_idx]['close'])
        return float(self.df_15m.iloc[-1]['close'])

    def round_to_lot_size(self, size: float) -> float:
        """Simple rounding for simulation"""
        return round(size, 8)

    def get_balance(self, asset: str) -> float:
        """Mock balance - not used in simulation"""
        return 10000.0

    def create_order(self, **kwargs):
        """Mock order creation"""
        return {'orderId': 1, 'status': 'NEW'}

    def cancel_order(self, symbol: str, orderId: int):
        """Mock order cancellation"""
        return {'orderId': orderId, 'status': 'CANCELED'}

    def get_order(self, symbol: str, orderId: int):
        """Mock get order"""
        return {'orderId': orderId, 'status': 'NEW', 'price': 0}

    def place_oco_order(self, **kwargs):
        """Mock OCO order"""
        return {'orders': [
            {'orderId': 1, 'type': 'LIMIT_MAKER'},
            {'orderId': 2, 'type': 'STOP_LOSS_LIMIT'}
        ]}

    def futures_create_order(self, **kwargs):
        """Mock futures order"""
        return {'orderId': 1, 'status': 'NEW'}

    def futures_cancel_order(self, **kwargs):
        """Mock futures cancel"""
        return {'orderId': 1, 'status': 'CANCELED'}

    def futures_get_order(self, **kwargs):
        """Mock futures get order"""
        return {'orderId': 1, 'status': 'NEW', 'price': 0}


class BinanceClientWrapper:
    """Wrapper for Binance client with error handling"""

    def __init__(self):
        if DRY_RUN:
            logger.info("🧪 DRY RUN MODE - Using Binance Testnet")
            if USE_FUTURES:
                # Futures testnet requires different configuration
                logger.info("📊 Using FUTURES TESTNET")
                self.client = Client(API_KEY, API_SECRET, testnet=False)
                self.client.FUTURES_URL = 'https://testnet.binancefuture.com'
            else:
                # Spot testnet
                logger.info("📊 Using SPOT TESTNET")
                self.client = Client(API_KEY, API_SECRET, testnet=True)
        else:
            logger.info("💰 LIVE TRADING MODE")
            self.client = Client(API_KEY, API_SECRET)
            if USE_FUTURES:
                logger.info("📊 Using FUTURES API (REAL MONEY)")
            else:
                logger.info("📊 Using SPOT API (REAL MONEY)")

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

    def __init__(self, client=None, simulation_mode=False):
        self.simulation_mode = simulation_mode
        if client is not None:
            self.client = client
        else:
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

    def check_historical_rejections(self):
        """Check historical data to determine if FVGs were already rejected"""
        if self.df_4h is None or len(self.df_4h) == 0:
            return

        df_4h_closed = self.df_4h.iloc[:-1]  # Exclude last open candle

        # Check each active FVG against historical candles
        for fvg in self.active_4h_fvgs[:]:
            # Find the index where this FVG was formed
            try:
                fvg_idx = df_4h_closed.index.get_loc(fvg.formed_time)
            except (KeyError, TypeError):
                # Try to find closest candle
                time_diffs = [(i, abs((df_4h_closed.index[i] - fvg.formed_time).total_seconds()))
                             for i in range(len(df_4h_closed))]
                if time_diffs:
                    closest_idx, min_diff = min(time_diffs, key=lambda x: x[1])
                    if min_diff <= 7200:  # Within 2 hours tolerance
                        fvg_idx = closest_idx
                    else:
                        continue
                else:
                    continue

            # Check all candles after FVG formation
            for i in range(fvg_idx + 1, len(df_4h_closed)):
                candle_row = df_4h_closed.iloc[i]
                candle_time = df_4h_closed.index[i]
                candle_close_time = candle_time + timedelta(hours=4)

                candle_dict = {
                    'open': float(candle_row['open']),
                    'high': float(candle_row['high']),
                    'low': float(candle_row['low']),
                    'close': float(candle_row['close']),
                    'close_time': int(candle_close_time.timestamp() * 1000)
                }

                # Check rejection
                if not fvg.rejected:
                    was_rejected = fvg.check_rejection(candle_dict)
                    if fvg.rejected:
                        # Move to rejected list
                        self.rejected_4h_fvgs.append(fvg)
                        self.active_4h_fvgs.remove(fvg)
                        logger.info(f"  ✅ Historical rejection found: {fvg.type} FVG ${fvg.bottom:.2f}-${fvg.top:.2f} @ {candle_time}")
                        break

                # Check invalidation
                high = float(candle_dict['high'])
                low = float(candle_dict['low'])
                if fvg.is_fully_passed(high, low):
                    fvg.invalidated = True
                    self.active_4h_fvgs.remove(fvg)
                    logger.info(f"  ❌ Historical invalidation: {fvg.type} FVG ${fvg.bottom:.2f}-${fvg.top:.2f} @ {candle_time}")
                    break

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
        # IMPORTANT: Last candle is still OPEN, so we store it but won't detect FVG from it
        # When a new candle appears, the previous one (which was last) will be closed
        self.last_4h_candle_time = self.df_4h.index[-1]
        self.last_15m_candle_time = self.df_15m.index[-1]
        logger.info(f"Last 4H candle: {self.last_4h_candle_time} (still OPEN - will detect FVG when it closes)")
        logger.info(f"Last 15M candle: {self.last_15m_candle_time}")

        # Detect initial FVGs
        # IMPORTANT: Exclude last candle (still open) from initial detection
        logger.info("Detecting initial FVGs...")
        df_4h_closed = self.df_4h.iloc[:-1] if len(self.df_4h) > 0 else self.df_4h
        self.active_4h_fvgs = self.detector.detect_fvgs(df_4h_closed, '4h')
        logger.info(f"Found {len(self.active_4h_fvgs)} 4H FVGs (from closed candles only)")

        # Check historical rejections
        logger.info("Checking historical rejections for detected FVGs...")
        self.check_historical_rejections()
        logger.info(f"After rejection check: {len(self.active_4h_fvgs)} active, {len(self.rejected_4h_fvgs)} rejected")

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

        # Simple rounding to match simulation (no lot size or notional checks)
        return round(size, 8)

    def validate_setup(self, entry: float, sl: float, tp: float) -> bool:
        """Validate setup parameters"""

        # SL distance
        sl_distance_pct = abs(entry - sl) / entry * 100
        if sl_distance_pct < MIN_SL_PCT:
            logger.warning(f"    ❌ Setup validation failed: SL too tight {sl_distance_pct:.3f}% < {MIN_SL_PCT}%")
            return False

        # RR ratio
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr = reward / risk
        if rr < MIN_RR:
            logger.warning(f"    ❌ Setup validation failed: RR too low {rr:.2f} < {MIN_RR}")
            return False

        # REMOVED: Price sanity check (not in simulation)
        # This check was rejecting valid setups that simulation would accept

        logger.info(f"    ✅ Setup validation passed: Entry=${entry:.2f}, SL=${sl:.2f}, TP=${tp:.2f}, RR={rr:.2f}")
        return True

    def create_setup_from_rejection(self, rejected_fvg: LiveFVG, fvg_15m: LiveFVG) -> Optional[PendingSetup]:
        """Create setup from rejected 4H FVG and 15M FVG"""

        # Determine direction
        if rejected_fvg.type == 'BULLISH':
            direction = 'SHORT'
            if fvg_15m.type != 'BEARISH':
                logger.warning(f"    ❌ FVG type mismatch: need BEARISH for SHORT, got {fvg_15m.type}")
                return None
            entry_price = fvg_15m.top
        else:
            direction = 'LONG'
            if fvg_15m.type != 'BULLISH':
                logger.warning(f"    ❌ FVG type mismatch: need BULLISH for LONG, got {fvg_15m.type}")
                return None
            entry_price = fvg_15m.bottom

        # Get SL
        sl = rejected_fvg.get_stop_loss()
        if not sl:
            logger.warning("    ❌ No SL available (no highs/lows inside FVG)")
            return None

        # Calculate TP
        risk = abs(entry_price - sl)
        if direction == 'SHORT':
            tp = entry_price - (FIXED_RR * risk)
        else:
            tp = entry_price + (FIXED_RR * risk)

        logger.info(f"    Validating {direction} setup: Entry=${entry_price:.2f}, SL=${sl:.2f}, TP=${tp:.2f}")

        # Validate
        if not self.validate_setup(entry_price, sl, tp):
            return None

        # Calculate size
        size = self.calculate_position_size(entry_price, sl)

        # Calculate created_time and expiry_time (matches simulation)
        # Use last 15M candle time as current_time
        if self.df_15m is not None and len(self.df_15m) > 0:
            current_time = self.df_15m.index[-1]
        else:
            current_time = datetime.now()

        expiry_time = current_time + timedelta(hours=4)

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
            created_time=current_time,
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
        if not self.pending_setups:
            return

        logger.info(f"Checking {len(self.pending_setups)} pending setup(s)...")

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

        # Set cooldown on parent FVG (matches simulation)
        cooldown_time = setup.expiry_time + timedelta(hours=4)

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

            # Log monitoring info (every 15M)
            pnl_pct = (self.active_trade.current_pnl / (self.active_trade.entry_price * self.active_trade.size)) * 100
            logger.debug(f"Monitoring trade #{self.active_trade.trade_id}: Current PnL ${self.active_trade.current_pnl:+.2f} ({pnl_pct:+.2f}%)")

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

        # Calculate duration
        duration = (self.active_trade.exit_time - self.active_trade.entry_time).total_seconds()
        duration_hours = duration / 3600
        duration_str = f"{duration_hours:.1f}h" if duration_hours >= 1 else f"{duration/60:.0f}m"

        logger.info(f"{emoji} Trade closed: {reason} | PnL: ${pnl:+.2f} ({pnl_pct:+.2f}%) | Balance: ${self.balance:.2f}")
        logger.info(f"   Entry: ${self.active_trade.entry_price:.2f} @ {self.active_trade.entry_time}")
        logger.info(f"   Exit:  ${exit_price:.2f} @ {self.active_trade.exit_time}")
        logger.info(f"   Duration: {duration_str} | Direction: {self.active_trade.direction}")

        # Save to history
        self.trades_history.append(self.active_trade.to_dict())

        # Clear active trade
        self.active_trade = None

        self.save_state()

    def update_4h_fvgs(self, candle: Dict):
        """Update 4H FVGs with new candle - NOTE: FVG detection moved to check_new_4h_candle()"""
        # This method is now only used for checking rejections and invalidations
        # FVG detection happens in check_new_4h_candle() when a candle closes

        rejections_count = 0
        invalidations_count = 0

        # Check rejections
        for fvg in self.active_4h_fvgs[:]:
            if not fvg.rejected:
                was_rejected = fvg.check_rejection(candle)

                # If rejected, add to rejected list
                if was_rejected and fvg.rejected:
                    self.rejected_4h_fvgs.append(fvg)
                    rejections_count += 1

            # Check invalidation
            high = float(candle['high'])
            low = float(candle['low'])
            if fvg.is_fully_passed(high, low):
                logger.info(f"❌ 4H FVG {fvg.type} ${fvg.bottom:.2f}-${fvg.top:.2f} invalidated (price fully passed)")
                fvg.invalidated = True
                self.active_4h_fvgs.remove(fvg)
                invalidations_count += 1
                # DON'T remove from rejected_4h_fvgs yet - will be checked on 15M data

        if rejections_count > 0 or invalidations_count > 0:
            logger.info(f"4H FVG update: {rejections_count} new rejections, {invalidations_count} invalidations")

    def look_for_setups(self):
        """Look for setup opportunities"""
        if self.active_trade:
            logger.debug(f"Active trade exists, skipping setup search")
            return

        if not self.rejected_4h_fvgs:
            logger.debug(f"No rejected 4H FVGs to check")
            return

        logger.info(f"Looking for setups from {len(self.rejected_4h_fvgs)} rejected FVG(s)...")

        # Use already updated 15M data (no re-fetch needed)
        current_candle_15m = self.df_15m.iloc[-1]

        setups_checked = 0
        setups_created = 0

        for rejected_fvg in self.rejected_4h_fvgs[:]:
            setups_checked += 1

            # Check if 4H FVG is invalidated on current 15M candle
            if rejected_fvg.is_fully_passed(float(current_candle_15m['high']), float(current_candle_15m['low'])):
                logger.info(f"❌ 4H FVG {rejected_fvg.type} ${rejected_fvg.bottom:.2f}-${rejected_fvg.top:.2f} invalidated")
                rejected_fvg.invalidated = True
                self.rejected_4h_fvgs.remove(rejected_fvg)
                continue

            if not self.can_create_setup(rejected_fvg):
                # Log why we can't create setup
                if rejected_fvg.has_filled_trade:
                    logger.debug(f"  Rejected FVG {rejected_fvg.type} already has filled trade")
                elif rejected_fvg.pending_expiry_time:
                    time_left = (rejected_fvg.pending_expiry_time - datetime.now()).total_seconds() / 60
                    logger.debug(f"  Rejected FVG {rejected_fvg.type} in cooldown ({time_left:.0f}m left)")
                continue

            logger.info(f"  Checking rejected {rejected_fvg.type} FVG ${rejected_fvg.bottom:.2f}-${rejected_fvg.top:.2f}")

            # Look for 15M FVG
            fvgs_15m = self.detector.detect_fvgs(self.df_15m.tail(10), '15m')

            if fvgs_15m:
                fvg_15m = fvgs_15m[-1]  # Most recent
                logger.info(f"    Found 15M {fvg_15m.type} FVG ${fvg_15m.bottom:.2f}-${fvg_15m.top:.2f}")

                # Try to create setup
                setup = self.create_setup_from_rejection(rejected_fvg, fvg_15m)

                if setup:
                    setups_created += 1
                    # Place order
                    self.place_setup_order(setup)

                    # Mark FVG as having pending setup (matches simulation)
                    rejected_fvg.pending_setup_id = setup.setup_id
                    rejected_fvg.pending_expiry_time = setup.expiry_time

                    # Only one setup at a time
                    break
                else:
                    logger.debug(f"    Setup validation failed")
            else:
                logger.debug(f"    No 15M FVG found in last 10 candles")

        if setups_checked > 0:
            logger.info(f"Setup search complete: checked {setups_checked}, created {setups_created}")

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

    def log_statistics(self):
        """Log current bot statistics"""
        logger.info("=" * 80)
        logger.info("📊 BOT STATISTICS")
        logger.info("=" * 80)

        # Balance info
        pnl = self.balance - self.initial_balance
        pnl_pct = (pnl / self.initial_balance * 100) if self.initial_balance > 0 else 0
        logger.info(f"💰 Balance: ${self.balance:.2f} (Start: ${self.initial_balance:.2f}, {pnl_pct:+.2f}%)")

        # FVG info
        logger.info(f"📋 Active 4H FVGs: {len(self.active_4h_fvgs)}")
        logger.info(f"🚫 Rejected 4H FVGs: {len(self.rejected_4h_fvgs)}")

        # Setup/Trade info
        logger.info(f"📦 Pending setups: {len(self.pending_setups)}")
        logger.info(f"🔄 Active trades: {1 if self.active_trade else 0}")

        # Trade history
        if self.trades_history:
            wins = sum(1 for t in self.trades_history if t.get('pnl', 0) > 0)
            win_rate = wins / len(self.trades_history) * 100
            logger.info(f"📈 Total trades: {len(self.trades_history)} (Win rate: {win_rate:.1f}%)")
        else:
            logger.info(f"📈 Total trades: 0")

        # Recent rejected FVGs details
        if self.rejected_4h_fvgs:
            logger.info(f"Recent rejected FVGs:")
            for fvg in self.rejected_4h_fvgs[-3:]:  # Last 3
                cooldown_info = ""
                if fvg.pending_expiry_time:
                    time_left = (fvg.pending_expiry_time - datetime.now()).total_seconds() / 60
                    if time_left > 0:
                        cooldown_info = f" (cooldown {time_left:.0f}m)"
                trade_info = " [FILLED]" if fvg.has_filled_trade else ""
                logger.info(f"  - {fvg.type} ${fvg.bottom:.2f}-${fvg.top:.2f}{cooldown_info}{trade_info}")

        logger.info("=" * 80)

    def check_new_4h_candle(self) -> bool:
        """Check if new 4H candle appeared (by timestamp)"""
        try:
            # Fetch latest 4H data
            df_new = self.client.get_klines(SYMBOL, TIMEFRAME_4H, limit=50)

            if df_new.empty:
                return False

            latest_candle_time = df_new.index[-1]

            # Check if new candle appeared (new candle means previous one closed)
            if self.last_4h_candle_time is None or latest_candle_time > self.last_4h_candle_time:
                logger.info(f"🕯️  New 4H candle detected!")
                logger.info(f"   Previous: {self.last_4h_candle_time}")
                logger.info(f"   Current:  {latest_candle_time}")

                # CRITICAL: Exclude the last (open/forming) candle from FVG detection
                # When Binance returns klines, the last candle (index -1) is still forming
                # We should only detect FVGs from CLOSED candles
                df_closed = df_new.iloc[:-1] if len(df_new) > 0 else df_new
                
                # Update data (keep full df for rejection checking, but use closed for FVG detection)
                self.df_4h = df_new
                
                # CRITICAL: When new candle appears, the PREVIOUS candle is now closed
                # We need to detect FVG from the CLOSED candle, not the new one that just started
                if self.last_4h_candle_time is not None and len(df_closed) >= 3:
                    # Find the closed candle that matches last_4h_candle_time
                    try:
                        closed_candle_idx = df_closed.index.get_loc(self.last_4h_candle_time)
                        logger.debug(f"Found exact match for closed candle at index {closed_candle_idx}")
                    except (KeyError, TypeError):
                        # If not found by exact match, find the closest candle by timestamp
                        # This can happen due to timezone issues or timestamp precision
                        time_diffs = [(i, abs((df_closed.index[i] - self.last_4h_candle_time).total_seconds()))
                                     for i in range(len(df_closed))]
                        closest_idx, min_diff = min(time_diffs, key=lambda x: x[1])

                        # Use closest if within reasonable range (10 minutes tolerance)
                        if min_diff <= 600:  # 10 minutes in seconds
                            closed_candle_idx = closest_idx
                            actual_closed_time = df_closed.index[closed_candle_idx]
                            logger.info(f"Using closest candle: {actual_closed_time} (diff: {min_diff:.0f}s from {self.last_4h_candle_time})")
                        else:
                            # Use the last closed candle as fallback
                            closed_candle_idx = len(df_closed) - 1
                            actual_closed_time = df_closed.index[closed_candle_idx]
                            logger.warning(f"⚠️  Could not find close match for {self.last_4h_candle_time}, using last closed candle: {actual_closed_time} (diff: {min_diff:.0f}s)")
                    
                    # FVG DETECTION - Use 10-candle lookback window (matches simulation)
                    if len(df_closed) >= 3:  # Need at least 3 candles for FVG detection
                        lookback_start = max(0, len(df_closed) - 10)
                        df_window = df_closed.iloc[lookback_start:]

                        logger.info(f"🔍 Detecting FVGs in window: {len(df_window)} candles (from index {lookback_start} to {len(df_closed)-1})")
                        new_fvgs = self.detector.detect_fvgs(df_window, '4h')

                        # Add new FVGs
                        for fvg in new_fvgs:
                            if not any(existing.id == fvg.id for existing in self.active_4h_fvgs):
                                self.active_4h_fvgs.append(fvg)
                                logger.info(f"✅ New 4H FVG detected: {fvg.type} ${fvg.bottom:.2f}-${fvg.top:.2f}")

                        # Log if no FVG found
                        if not new_fvgs:
                            logger.debug(f"No FVG detected in lookback window")
                    else:
                        logger.info(f"⚠️  Skipping FVG detection: only {len(df_closed)} closed candles (need >= 3)")

                    # REJECTION/INVALIDATION CHECK - Check ALL candles between last check and now
                    # This ensures we don't miss rejections if bot missed a candle detection
                    try:
                        # Get all closed candles starting from last_4h_candle_time (inclusive)
                        # When new candle appears, last_4h_candle_time is the candle that JUST CLOSED
                        # If bot missed some candles, we check all missed ones too
                        candles_to_check = df_closed[df_closed.index >= self.last_4h_candle_time]

                        if len(candles_to_check) == 0:
                            logger.warning("⚠️  No candles to check for rejection/invalidation")
                        else:
                            logger.info(f"Checking {len(self.active_4h_fvgs)} active FVGs on {len(candles_to_check)} closed candle(s)")
                            logger.info(f"   Time range: {self.last_4h_candle_time} → {latest_candle_time}")

                        for candle_row in candles_to_check.itertuples():
                            candle_open_time = candle_row.Index
                            candle_close_time = candle_open_time + timedelta(hours=4)

                            closed_candle_dict = {
                                'open': candle_row.open,
                                'high': candle_row.high,
                                'low': candle_row.low,
                                'close': candle_row.close,
                                'close_time': int(candle_close_time.timestamp() * 1000)
                            }

                            logger.info(f"📊 Checking candle {candle_open_time} → {candle_close_time}")
                            logger.info(f"   OHLC: O={candle_row.open:.2f} H={candle_row.high:.2f} L={candle_row.low:.2f} C={candle_row.close:.2f}")

                            for fvg in self.active_4h_fvgs[:]:
                                # Check rejection on closed candle
                                if not fvg.rejected:
                                    rejection_result = fvg.check_rejection(closed_candle_dict)
                                    if fvg.rejected:
                                        self.rejected_4h_fvgs.append(fvg)
                                        logger.info(f"   ✅ Rejection detected: {fvg.type} FVG ${fvg.bottom:.2f}-${fvg.top:.2f}")

                                # Check invalidation
                                high = float(closed_candle_dict['high'])
                                low = float(closed_candle_dict['low'])
                                if fvg.is_fully_passed(high, low):
                                    fvg.invalidated = True
                                    self.active_4h_fvgs.remove(fvg)
                                    logger.info(f"   ❌ FVG {fvg.id} invalidated")

                    except Exception as e:
                        logger.error(f"Error checking rejection/invalidation: {e}")
                elif self.last_4h_candle_time is None:
                    # First run - detect FVGs from all closed candles (excluding last open one)
                    logger.info("First run: Detecting FVGs from all closed candles...")
                    # This is handled in __init__, so we skip here

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
        last_stats_log = datetime.now()

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
                    # Log statistics after 4H candle
                    self.log_statistics()
                    last_stats_log = now

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

                # Log statistics every 4 hours
                if (now - last_stats_log).total_seconds() >= 14400:  # 4 hours
                    self.log_statistics()
                    last_stats_log = now

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


def run_simulation(start_date: str = '2024-01-01', end_date: str = '2024-12-31'):
    """Run simulation using live bot logic with historical data"""

    print("="*80)
    print("LIVE BOT SIMULATION MODE")
    print("="*80)
    print(f"Testing period: {start_date} to {end_date}")
    print("="*80)

    # Load historical data
    data_dir = '/Users/illiachumak/trading/backtest/data'

    print("\n📊 Loading historical data...")

    # Load 4H data
    df_4h = pd.read_csv(f"{data_dir}/btc_4h_data_2018_to_2025.csv")
    df_4h['Open time'] = pd.to_datetime(df_4h['Open time'])
    df_4h.set_index('Open time', inplace=True)
    df_4h = df_4h[['Open', 'High', 'Low', 'Close', 'Volume']]
    df_4h.columns = ['open', 'high', 'low', 'close', 'volume']

    # Load 15M data
    df_15m = pd.read_csv(f"{data_dir}/btc_15m_data_2018_to_2025.csv")
    df_15m['Open time'] = pd.to_datetime(df_15m['Open time'])
    df_15m.set_index('Open time', inplace=True)
    df_15m = df_15m[['Open', 'High', 'Low', 'Close', 'Volume']]
    df_15m.columns = ['open', 'high', 'low', 'close', 'volume']

    # Filter by date range
    df_4h = df_4h[(df_4h.index >= start_date) & (df_4h.index <= end_date)]
    df_15m = df_15m[(df_15m.index >= start_date) & (df_15m.index <= end_date)]

    print(f"✅ Loaded {len(df_4h)} 4H candles, {len(df_15m)} 15M candles")
    print(f"Period: {df_4h.index[0]} to {df_4h.index[-1]}")

    # Create mock client
    mock_client = MockBinanceClient(df_4h, df_15m)

    # Create bot with mock client
    bot = FailedFVGLiveBot(client=mock_client, simulation_mode=True)
    bot.balance = 10000.0
    bot.initial_balance = 10000.0

    # Simulation state
    trade_counter = 0
    trades_history = []

    print("\n🔄 Running simulation...\n")

    # Start from index 2 (minimum for FVG detection)
    start_idx = 2

    # Initialize with FVGs from first candles
    init_lookback = min(50, len(df_4h))
    df_4h_init = df_4h.head(init_lookback)
    bot.active_4h_fvgs = bot.detector.detect_fvgs(df_4h_init, '4h')

    # Apply same filtering as live bot - check for already rejected FVGs
    bot.df_4h = df_4h_init  # Needed for check_historical_rejections
    bot.check_historical_rejections()

    print(f"After filtering: {len(bot.active_4h_fvgs)} active FVGs, {len(bot.rejected_4h_fvgs)} rejected FVGs")

    # Map 15M index to current position
    current_15m_idx = 0

    # Main simulation loop - iterate through 4H candles
    for i in range(start_idx, len(df_4h)):
        mock_client.current_4h_idx = i
        current_4h_time = df_4h.index[i]
        current_4h_candle = df_4h.iloc[i]

        # Convert to dict for compatibility
        candle_dict = {
            'open': current_4h_candle['open'],
            'high': current_4h_candle['high'],
            'low': current_4h_candle['low'],
            'close': current_4h_candle['close'],
            'volume': current_4h_candle['volume'],
            'close_time': int(current_4h_time.timestamp() * 1000)  # milliseconds
        }

        # Update 4H FVGs (rejection & invalidation checks)
        bot.update_4h_fvgs(candle_dict)

        # Detect new 4H FVGs from lookback window (matches fixed live bot)
        if len(df_4h) >= 3:
            lookback_start = max(0, i - 10)
            df_window = df_4h.iloc[lookback_start:i+1]
            new_fvgs = bot.detector.detect_fvgs(df_window, '4h')

            for fvg in new_fvgs:
                if not any(existing.id == fvg.id for existing in bot.active_4h_fvgs):
                    bot.active_4h_fvgs.append(fvg)

        # Find next 4H time
        next_4h_time = df_4h.index[i+1] if i+1 < len(df_4h) else df_15m.index[-1]

        # Process 15M candles in this 4H period
        while current_15m_idx < len(df_15m) and df_15m.index[current_15m_idx] < next_4h_time:
            mock_client.current_15m_idx = current_15m_idx

            # Update 15M data (for look_for_setups)
            bot.df_15m = mock_client.get_klines(SYMBOL, TIMEFRAME_15M, limit=1000)
            bot.df_4h = mock_client.get_klines(SYMBOL, TIMEFRAME_4H, limit=200)

            # Look for setups (only if no active trade and no pending setups)
            if not bot.active_trade and not bot.pending_setups:
                # Check all rejected FVGs for setup opportunities
                for rejected_fvg in bot.rejected_4h_fvgs[:]:
                    # Check if invalidated
                    current_candle_15m = df_15m.iloc[current_15m_idx]
                    if rejected_fvg.is_fully_passed(current_candle_15m['high'], current_candle_15m['low']):
                        rejected_fvg.invalidated = True
                        bot.rejected_4h_fvgs.remove(rejected_fvg)
                        continue

                    # Check if can create setup
                    current_time = df_15m.index[current_15m_idx]
                    if rejected_fvg.has_filled_trade:
                        continue
                    if rejected_fvg.pending_expiry_time:
                        if isinstance(rejected_fvg.pending_expiry_time, datetime):
                            expiry_ts = pd.Timestamp(rejected_fvg.pending_expiry_time)
                        else:
                            expiry_ts = rejected_fvg.pending_expiry_time
                        if current_time < expiry_ts:
                            continue

                    # Look for 15M FVG
                    lookback_start = max(0, current_15m_idx - 10)
                    df_window_15m = df_15m.iloc[lookback_start:current_15m_idx + 1]
                    fvgs_15m = bot.detector.detect_fvgs(df_window_15m, '15m')

                    if fvgs_15m:
                        fvg_15m = fvgs_15m[-1]

                        # Check type match
                        if rejected_fvg.type == 'BULLISH' and fvg_15m.type != 'BEARISH':
                            continue
                        if rejected_fvg.type == 'BEARISH' and fvg_15m.type != 'BULLISH':
                            continue

                        # Create setup (using bot's method)
                        setup = bot.create_setup_from_rejection(rejected_fvg, fvg_15m)

                        if setup:
                            # Mark FVG
                            rejected_fvg.pending_setup_id = setup.setup_id
                            rejected_fvg.pending_expiry_time = setup.expiry_time

                            # Check if gets filled in expiry window
                            expiry_idx = min(current_15m_idx + LIMIT_EXPIRY_CANDLES, len(df_15m))
                            filled = False
                            fill_idx = None

                            for j in range(current_15m_idx + 1, expiry_idx):
                                candle = df_15m.iloc[j]
                                if setup.direction == 'LONG':
                                    if candle['low'] <= setup.entry_price:
                                        filled = True
                                        fill_idx = j
                                        break
                                else:  # SHORT
                                    if candle['high'] >= setup.entry_price:
                                        filled = True
                                        fill_idx = j
                                        break

                            if filled:
                                # Set active trade
                                bot.active_trade = ActiveTrade(
                                    trade_id=f"trade_{trade_counter}",
                                    setup_id=setup.setup_id,
                                    direction=setup.direction,
                                    entry_price=setup.entry_price,
                                    entry_time=df_15m.index[fill_idx],
                                    sl=setup.sl,
                                    tp=setup.tp,
                                    size=setup.size
                                )

                                # Simulate trade execution
                                entry_idx = fill_idx
                                exit_price = None
                                exit_reason = None
                                exit_idx = None

                                # Check for TP/SL hit (max 200 candles = 50h ~2 days)
                                for k in range(entry_idx, min(entry_idx + 200, len(df_15m))):
                                    candle = df_15m.iloc[k]

                                    if setup.direction == 'LONG':
                                        # Check SL first
                                        if candle['low'] <= setup.sl:
                                            exit_price = setup.sl
                                            exit_reason = 'SL'
                                            exit_idx = k
                                            break
                                        # Check TP
                                        if candle['high'] >= setup.tp:
                                            exit_price = setup.tp
                                            exit_reason = 'TP'
                                            exit_idx = k
                                            break
                                    else:  # SHORT
                                        # Check SL first
                                        if candle['high'] >= setup.sl:
                                            exit_price = setup.sl
                                            exit_reason = 'SL'
                                            exit_idx = k
                                            break
                                        # Check TP
                                        if candle['low'] <= setup.tp:
                                            exit_price = setup.tp
                                            exit_reason = 'TP'
                                            exit_idx = k
                                            break

                                # If still no exit, close at timeout
                                if exit_price is None:
                                    last_idx = min(entry_idx + 199, len(df_15m) - 1)
                                    exit_price = df_15m.iloc[last_idx]['close']
                                    exit_reason = 'TIMEOUT'
                                    exit_idx = last_idx

                                # Calculate PnL
                                if setup.direction == 'LONG':
                                    pnl = (exit_price - setup.entry_price) * setup.size
                                else:
                                    pnl = (setup.entry_price - exit_price) * setup.size

                                # Apply fees
                                entry_fee = setup.entry_price * setup.size * MAKER_FEE
                                if exit_reason == 'SL':
                                    exit_fee = exit_price * setup.size * TAKER_FEE
                                else:
                                    exit_fee = exit_price * setup.size * MAKER_FEE

                                pnl -= (entry_fee + exit_fee)

                                # Record trade
                                trade = {
                                    'trade_id': trade_counter,
                                    'entry_time': df_15m.index[fill_idx],
                                    'entry_price': setup.entry_price,
                                    'exit_time': df_15m.index[exit_idx],
                                    'exit_price': exit_price,
                                    'exit_reason': exit_reason,
                                    'direction': setup.direction,
                                    'size': setup.size,
                                    'sl': setup.sl,
                                    'tp': setup.tp,
                                    'pnl': pnl,
                                    'pnl_pct': (pnl / (setup.entry_price * setup.size)) * 100,
                                    'result': 'WIN' if pnl > 0 else 'LOSS'
                                }

                                trades_history.append(trade)
                                bot.balance += pnl
                                trade_counter += 1

                                # Mark parent FVG
                                rejected_fvg.has_filled_trade = True
                                bot.rejected_4h_fvgs.remove(rejected_fvg)

                                # Clear active trade
                                bot.active_trade = None

                                # Print trade
                                emoji = "✅" if trade['result'] == 'WIN' else "❌"
                                print(f"\n{'='*80}")
                                print(f"{emoji} TRADE #{trade_counter} - {trade['direction']}")
                                print(f"{'='*80}")
                                print(f"Entry:  {trade['entry_time']} @ ${trade['entry_price']:.2f}")
                                print(f"Exit:   {trade['exit_time']} @ ${trade['exit_price']:.2f}")
                                print(f"Reason: {trade['exit_reason']}")
                                print(f"PnL:    ${trade['pnl']:+.2f} ({trade['pnl_pct']:+.2f}%)")
                                print(f"Balance: ${bot.balance:.2f}")
                                print(f"{'='*80}\n")

                                # Continue from next candle
                                current_15m_idx = fill_idx + 1
                                break  # Only one trade at a time
                            else:
                                # Setup expired - set cooldown
                                rejected_fvg.pending_expiry_time = setup.expiry_time + timedelta(hours=4)

                            break  # Only one setup at a time

            current_15m_idx += 1

    # Print results
    print("\n" + "="*80)
    print("SIMULATION RESULTS")
    print("="*80)
    print(f"Period: {start_date} to {end_date}")
    print(f"Initial Balance: ${bot.initial_balance:,.2f}")
    print(f"Final Balance:   ${bot.balance:,.2f}")
    print(f"Total PnL:       ${bot.balance - bot.initial_balance:+,.2f}")
    print(f"Return:          {((bot.balance - bot.initial_balance) / bot.initial_balance * 100):+.2f}%")
    print(f"\nTotal Trades:    {len(trades_history)}")

    if trades_history:
        wins = sum(1 for t in trades_history if t['pnl'] > 0)
        losses = len(trades_history) - wins
        win_rate = wins / len(trades_history) * 100

        avg_win = np.mean([t['pnl'] for t in trades_history if t['pnl'] > 0]) if wins > 0 else 0
        avg_loss = np.mean([t['pnl'] for t in trades_history if t['pnl'] < 0]) if losses > 0 else 0

        print(f"Wins:            {wins}")
        print(f"Losses:          {losses}")
        print(f"Win Rate:        {win_rate:.2f}%")
        print(f"Avg Win:         ${avg_win:.2f}")
        print(f"Avg Loss:        ${avg_loss:.2f}")

        if avg_loss != 0:
            profit_factor = abs(avg_win * wins / (avg_loss * losses))
            print(f"Profit Factor:   {profit_factor:.2f}")

    print("="*80)

    # Save results
    results = {
        'period': f"{start_date} to {end_date}",
        'initial_balance': bot.initial_balance,
        'final_balance': bot.balance,
        'total_pnl': bot.balance - bot.initial_balance,
        'return_pct': ((bot.balance - bot.initial_balance) / bot.initial_balance * 100),
        'total_trades': len(trades_history),
        'trades': trades_history
    }

    output_file = f'4HFVG_BOT/live_bot_simulation_{start_date}_to_{end_date}.json'
    with open(output_file, 'w') as f:
        # Convert datetime objects to strings
        def serialize(obj):
            if isinstance(obj, (datetime, pd.Timestamp)):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        json.dump(results, f, indent=2, default=serialize)

    print(f"\n✅ Results saved to {output_file}")

    return results


if __name__ == '__main__':
    main()
