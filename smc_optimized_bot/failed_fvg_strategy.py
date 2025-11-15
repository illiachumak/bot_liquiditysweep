"""
Failed 4H FVG Strategy
15-minute execution timeframe with 4H FVG analysis

Strategy Rules:
1. Detect 4H FVG zones
2. Wait for price to enter 4H FVG zone
3. Wait for rejection (close outside FVG zone)
4. After rejection, look for 15M FVG formation
5. Entry: Limit order at near boundary of 15M FVG
6. Stop Loss: Behind highs/lows formed INSIDE the 4H FVG zone
7. Take Profit: Nearest liquidity (wicks)
8. Skip trade if RR < 2 or SL < 0.3%
9. FVG invalidation: Price fully passes through FVG

Performance Target:
- Win Rate: ~45-50%
- Risk/Reward: 2.0+ average
- Precision entries at FVG boundaries
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


# Setup logging
def setup_logging(verbose: bool = True):
    """Setup logging with rotation"""
    os.makedirs('logs', exist_ok=True)

    logger = logging.getLogger('FailedFVGBot')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)

    file_handler = RotatingFileHandler(
        'logs/failed_fvg_bot.log',
        maxBytes=10*1024*1024,
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

logger = setup_logging(verbose=True)


class FVG:
    """Represents a Fair Value Gap"""
    def __init__(self, fvg_type: str, top: float, bottom: float,
                 formed_time: datetime, timeframe: str, index: int):
        self.type = fvg_type  # 'BULLISH' or 'BEARISH'
        self.top = top
        self.bottom = bottom
        self.formed_time = formed_time
        self.timeframe = timeframe  # '4h' or '15m'
        self.index = index

        self.entered = False  # Price entered this FVG
        self.rejected = False  # Price rejected from this FVG
        self.invalidated = False  # FVG fully passed through

        self.rejection_time = None
        self.rejection_price = None

        # Track price action inside FVG
        self.highs_inside = []  # Highs formed inside FVG
        self.lows_inside = []   # Lows formed inside FVG

        self.id = f"{timeframe}_{fvg_type}_{top:.2f}_{bottom:.2f}_{int(formed_time.timestamp())}"

    def is_inside(self, price: float) -> bool:
        """Check if price is inside FVG zone"""
        return self.bottom <= price <= self.top

    def is_fully_passed(self, candle_high: float, candle_low: float) -> bool:
        """Check if candle fully passed through FVG (invalidation)"""
        if self.type == 'BULLISH':
            # For bullish FVG, invalidation = close below bottom
            return candle_low < self.bottom
        else:  # BEARISH
            # For bearish FVG, invalidation = close above top
            return candle_high > self.top

    def check_rejection(self, candle: pd.Series) -> bool:
        """
        Check if candle rejected from FVG
        Rejection = entered FVG but closed outside
        """
        candle_high = candle['High']
        candle_low = candle['Low']
        candle_close = candle['Close']

        # Check if candle touched FVG
        touched = not (candle_high < self.bottom or candle_low > self.top)

        if not touched:
            return False

        # Mark as entered
        if not self.entered:
            self.entered = True
            logger.info(f"   ✅ Price entered {self.timeframe} {self.type} FVG ${self.bottom:.2f}-${self.top:.2f}")

        # Track highs/lows inside FVG
        if self.is_inside(candle_high):
            self.highs_inside.append(candle_high)
        if self.is_inside(candle_low):
            self.lows_inside.append(candle_low)

        # Check rejection
        if self.type == 'BULLISH':
            # Bullish FVG rejection = close below FVG after entering
            if self.entered and candle_close < self.bottom:
                if not self.rejected:
                    self.rejected = True
                    self.rejection_time = candle['timestamp']
                    self.rejection_price = candle_close
                    logger.info(f"   🚫 REJECTION! {self.timeframe} BULLISH FVG rejected at ${candle_close:.2f}")
                    return True
        else:  # BEARISH
            # Bearish FVG rejection = close above FVG after entering
            if self.entered and candle_close > self.top:
                if not self.rejected:
                    self.rejected = True
                    self.rejection_time = candle['timestamp']
                    self.rejection_price = candle_close
                    logger.info(f"   🚫 REJECTION! {self.timeframe} BEARISH FVG rejected at ${candle_close:.2f}")
                    return True

        return False

    def get_stop_loss(self) -> Optional[float]:
        """
        Get stop loss based on highs/lows inside FVG
        SL should be behind the extreme formed inside FVG
        """
        if self.type == 'BULLISH':
            # For bullish rejection (going SHORT), SL above highest high inside
            if self.highs_inside:
                sl = max(self.highs_inside) * 1.002  # +0.2% buffer
                logger.debug(f"   📍 SL for BULLISH FVG rejection: ${sl:.2f} (highest inside: ${max(self.highs_inside):.2f})")
                return sl
        else:  # BEARISH
            # For bearish rejection (going LONG), SL below lowest low inside
            if self.lows_inside:
                sl = min(self.lows_inside) * 0.998  # -0.2% buffer
                logger.debug(f"   📍 SL for BEARISH FVG rejection: ${sl:.2f} (lowest inside: ${min(self.lows_inside):.2f})")
                return sl

        return None


class LimitOrder:
    """Represents a limit order"""
    def __init__(self, order_type: str, limit_price: float, sl: float, tp: float,
                 placed_time: datetime, expiry_hours: int, parent_fvg_id: str):
        self.order_type = order_type  # 'LONG' or 'SHORT'
        self.limit_price = limit_price
        self.sl = sl
        self.tp = tp
        self.placed_time = placed_time
        self.expiry_time = placed_time + timedelta(hours=expiry_hours)
        self.parent_fvg_id = parent_fvg_id

        self.binance_order_id = None
        self.filled = False
        self.filled_time = None
        self.filled_price = None

        # Calculate RR
        risk = abs(limit_price - sl)
        reward = abs(tp - limit_price)
        self.rr = reward / risk if risk > 0 else 0

        # Calculate SL percentage
        self.sl_pct = abs(limit_price - sl) / limit_price * 100

    def is_expired(self, current_time: datetime) -> bool:
        return current_time >= self.expiry_time


class Position:
    """Represents an active position"""
    def __init__(self, order: LimitOrder, size: float, entry_time: datetime):
        self.type = order.order_type
        self.entry = order.filled_price
        self.size = size
        self.sl = order.sl
        self.tp = order.tp
        self.entry_time = entry_time
        self.parent_fvg_id = order.parent_fvg_id
        self.rr = order.rr


class FailedFVGStrategy:
    """Failed 4H FVG Strategy Logic"""

    def __init__(self):
        self.active_4h_fvgs: List[FVG] = []
        self.rejected_4h_fvgs: List[FVG] = []  # FVGs that rejected, waiting for 15m FVG

        self.limit_expiry_hours = 24
        self.min_rr = 2.0
        self.min_sl_pct = 0.3

        # Lookback for liquidity detection
        self.liquidity_lookback = 50  # candles

    def detect_fvg(self, df: pd.DataFrame, timeframe: str) -> List[FVG]:
        """
        Detect Fair Value Gaps

        Bullish FVG: low[i] > high[i-2] (gap up)
        Bearish FVG: high[i] < low[i-2] (gap down)
        """
        fvgs = []

        for i in range(2, len(df)):
            # Bullish FVG
            if df.iloc[i]['Low'] > df.iloc[i-2]['High']:
                top = df.iloc[i]['Low']
                bottom = df.iloc[i-2]['High']

                fvg = FVG(
                    fvg_type='BULLISH',
                    top=top,
                    bottom=bottom,
                    formed_time=df.iloc[i]['timestamp'],
                    timeframe=timeframe,
                    index=i
                )
                fvgs.append(fvg)
                logger.debug(f"   📊 Detected BULLISH FVG at idx {i}: ${bottom:.2f}-${top:.2f}")

            # Bearish FVG
            elif df.iloc[i]['High'] < df.iloc[i-2]['Low']:
                top = df.iloc[i-2]['Low']
                bottom = df.iloc[i]['High']

                fvg = FVG(
                    fvg_type='BEARISH',
                    top=top,
                    bottom=bottom,
                    formed_time=df.iloc[i]['timestamp'],
                    timeframe=timeframe,
                    index=i
                )
                fvgs.append(fvg)
                logger.debug(f"   📊 Detected BEARISH FVG at idx {i}: ${bottom:.2f}-${top:.2f}")

        return fvgs

    def update_4h_fvgs(self, df_4h: pd.DataFrame):
        """Update 4H FVGs - detect new ones and check invalidation"""
        logger.debug("🔍 Updating 4H FVGs...")

        # Detect new FVGs in recent candles (last 10)
        if len(df_4h) >= 10:
            recent_fvgs = self.detect_fvg(df_4h.tail(10).reset_index(drop=True), timeframe='4h')

            # Add new FVGs that are not already tracked
            for fvg in recent_fvgs:
                if not any(existing.id == fvg.id for existing in self.active_4h_fvgs):
                    self.active_4h_fvgs.append(fvg)
                    logger.info(f"✅ New 4H {fvg.type} FVG: ${fvg.bottom:.2f}-${fvg.top:.2f}")

        # Check invalidation of active FVGs
        current_candle = df_4h.iloc[-1]
        invalidated = []

        for fvg in self.active_4h_fvgs:
            if fvg.is_fully_passed(current_candle['High'], current_candle['Low']):
                fvg.invalidated = True
                invalidated.append(fvg)
                logger.info(f"❌ 4H FVG invalidated: {fvg.type} ${fvg.bottom:.2f}-${fvg.top:.2f}")

        # Remove invalidated FVGs
        self.active_4h_fvgs = [fvg for fvg in self.active_4h_fvgs if not fvg.invalidated]

        # Also clean from rejected list
        self.rejected_4h_fvgs = [fvg for fvg in self.rejected_4h_fvgs if not fvg.invalidated]

        logger.debug(f"   Active 4H FVGs: {len(self.active_4h_fvgs)}, Rejected (waiting): {len(self.rejected_4h_fvgs)}")

    def check_4h_rejections(self, df_15m: pd.DataFrame) -> List[FVG]:
        """
        Check if any 4H FVG got rejected
        Uses 15m data to detect rejection
        Returns list of newly rejected FVGs
        """
        newly_rejected = []

        if len(df_15m) < 2:
            return newly_rejected

        current_candle = df_15m.iloc[-1]

        for fvg in self.active_4h_fvgs:
            if fvg.rejected:
                continue  # Already rejected

            if fvg.check_rejection(current_candle):
                # Rejected!
                self.rejected_4h_fvgs.append(fvg)
                newly_rejected.append(fvg)

        return newly_rejected

    def find_liquidity(self, df_15m: pd.DataFrame, direction: str) -> Optional[float]:
        """
        Find nearest liquidity (wicks) for take profit

        For LONG: Look for resistance (high wicks above)
        For SHORT: Look for support (low wicks below)
        """
        if len(df_15m) < self.liquidity_lookback:
            lookback_df = df_15m
        else:
            lookback_df = df_15m.tail(self.liquidity_lookback)

        current_price = df_15m.iloc[-1]['Close']

        if direction == 'LONG':
            # Find resistance wicks above current price
            highs = lookback_df[lookback_df['High'] > current_price]['High'].values
            if len(highs) > 0:
                # Group nearby highs (within 0.5%)
                highs_sorted = sorted(highs, reverse=True)

                # Find first significant cluster
                for high in highs_sorted:
                    if high > current_price * 1.005:  # At least 0.5% above
                        logger.debug(f"   🎯 Found LONG TP liquidity at ${high:.2f}")
                        return high

        else:  # SHORT
            # Find support wicks below current price
            lows = lookback_df[lookback_df['Low'] < current_price]['Low'].values
            if len(lows) > 0:
                # Group nearby lows
                lows_sorted = sorted(lows)

                # Find first significant cluster
                for low in lows_sorted:
                    if low < current_price * 0.995:  # At least 0.5% below
                        logger.debug(f"   🎯 Found SHORT TP liquidity at ${low:.2f}")
                        return low

        return None

    def create_order_from_15m_fvg(self, parent_4h_fvg: FVG, fvg_15m: FVG,
                                   df_15m: pd.DataFrame, current_time: datetime) -> Optional[LimitOrder]:
        """
        Create limit order from 15m FVG after 4h rejection

        Logic:
        - Entry: Near boundary of 15m FVG
        - SL: Behind highs/lows inside 4h FVG
        - TP: Nearest liquidity
        """
        logger.info(f"🔨 Creating order from 15M FVG after 4H rejection...")

        # Determine direction
        # If 4H bullish FVG rejected (price went down) -> expect SHORT
        # If 4H bearish FVG rejected (price went up) -> expect LONG

        if parent_4h_fvg.type == 'BULLISH':
            # 4H bullish rejected = price went down = SHORT setup
            order_type = 'SHORT'

            # Entry: Top of 15M FVG (near boundary for SHORT)
            # For SHORT after bearish move, we want 15M bearish FVG
            if fvg_15m.type != 'BEARISH':
                logger.warning(f"   ⚠️ FVG mismatch: Expected BEARISH 15M FVG for SHORT, got {fvg_15m.type}")
                return None

            limit_price = fvg_15m.top  # Enter at top

            # SL: Above highs inside 4H FVG
            sl = parent_4h_fvg.get_stop_loss()
            if not sl:
                logger.warning(f"   ⚠️ No valid SL (no highs inside 4H FVG)")
                return None

            # TP: Nearest liquidity below
            tp = self.find_liquidity(df_15m, direction='SHORT')
            if not tp:
                logger.warning(f"   ⚠️ No liquidity found for SHORT TP")
                return None

        else:  # parent_4h_fvg.type == 'BEARISH'
            # 4H bearish rejected = price went up = LONG setup
            order_type = 'LONG'

            # Entry: Bottom of 15M FVG (near boundary for LONG)
            # For LONG after bullish move, we want 15M bullish FVG
            if fvg_15m.type != 'BULLISH':
                logger.warning(f"   ⚠️ FVG mismatch: Expected BULLISH 15M FVG for LONG, got {fvg_15m.type}")
                return None

            limit_price = fvg_15m.bottom  # Enter at bottom

            # SL: Below lows inside 4H FVG
            sl = parent_4h_fvg.get_stop_loss()
            if not sl:
                logger.warning(f"   ⚠️ No valid SL (no lows inside 4H FVG)")
                return None

            # TP: Nearest liquidity above
            tp = self.find_liquidity(df_15m, direction='LONG')
            if not tp:
                logger.warning(f"   ⚠️ No liquidity found for LONG TP")
                return None

        # Create order
        order = LimitOrder(
            order_type=order_type,
            limit_price=limit_price,
            sl=sl,
            tp=tp,
            placed_time=current_time,
            expiry_hours=self.limit_expiry_hours,
            parent_fvg_id=parent_4h_fvg.id
        )

        logger.info(f"   📋 Order created: {order_type}")
        logger.info(f"      Entry: ${limit_price:.2f}")
        logger.info(f"      SL: ${sl:.2f} ({order.sl_pct:.2f}%)")
        logger.info(f"      TP: ${tp:.2f}")
        logger.info(f"      RR: {order.rr:.2f}")

        # Validate RR
        if order.rr < self.min_rr:
            logger.warning(f"   ❌ RR too low: {order.rr:.2f} < {self.min_rr}")
            return None

        # Validate SL percentage
        if order.sl_pct < self.min_sl_pct:
            logger.warning(f"   ❌ SL too tight: {order.sl_pct:.2f}% < {self.min_sl_pct}%")
            return None

        logger.info(f"   ✅ Order passed validation!")
        return order

    def check_for_setup(self, df_4h: pd.DataFrame, df_15m: pd.DataFrame,
                       current_time: datetime) -> List[LimitOrder]:
        """
        Main strategy logic - check for failed FVG setups

        Returns list of limit orders to place
        """
        orders = []

        # 1. Update 4H FVGs
        self.update_4h_fvgs(df_4h)

        # 2. Check for 4H rejections
        newly_rejected = self.check_4h_rejections(df_15m)

        # 3. For each rejected 4H FVG, look for 15M FVG
        for rejected_fvg in self.rejected_4h_fvgs:
            logger.info(f"🔍 Checking for 15M FVG after 4H {rejected_fvg.type} rejection...")

            # Detect 15M FVGs in recent candles (after rejection)
            # Look at last 10 candles
            if len(df_15m) >= 10:
                recent_15m_fvgs = self.detect_fvg(df_15m.tail(10).reset_index(drop=True), timeframe='15m')

                if recent_15m_fvgs:
                    # Take the most recent 15M FVG
                    fvg_15m = recent_15m_fvgs[-1]

                    logger.info(f"   ✅ Found 15M {fvg_15m.type} FVG: ${fvg_15m.bottom:.2f}-${fvg_15m.top:.2f}")

                    # Create order
                    order = self.create_order_from_15m_fvg(rejected_fvg, fvg_15m, df_15m, current_time)

                    if order:
                        orders.append(order)

                        # Remove from rejected list (order created)
                        self.rejected_4h_fvgs.remove(rejected_fvg)

                        logger.info(f"   ✅ SETUP COMPLETE! {order.order_type} order created")
                else:
                    logger.debug(f"   ⏳ No 15M FVG yet after rejection, waiting...")

        return orders


class BinanceClient:
    """Binance API wrapper"""

    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        if testnet:
            self.client = Client(api_key, api_secret, testnet=True)
            self.client.API_URL = 'https://testnet.binance.vision/api'
        else:
            self.client = Client(api_key, api_secret)

        self.symbol = 'BTCUSDT'
        logger.info(f"📡 Binance Client initialized (Testnet: {testnet})")

    def get_klines(self, interval: str, limit: int = 200) -> pd.DataFrame:
        """Fetch klines"""
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
            logger.debug(f"📈 Fetched {len(result)} {interval} candles")
            return result

        except Exception as e:
            logger.error(f"❌ Error fetching klines: {e}")
            raise

    def get_current_price(self) -> float:
        """Get current price"""
        try:
            ticker = self.client.get_symbol_ticker(symbol=self.symbol)
            return float(ticker['price'])
        except Exception as e:
            logger.error(f"❌ Error fetching price: {e}")
            raise

    def get_balance(self) -> float:
        """Get USDT balance"""
        try:
            balance = self.client.get_asset_balance(asset='USDT')
            return float(balance['free'])
        except Exception as e:
            logger.error(f"❌ Error fetching balance: {e}")
            raise


class FailedFVGBot:
    """Main bot class"""

    def __init__(self, api_key: str, api_secret: str,
                 risk_per_trade: float = 0.02,
                 testnet: bool = True,
                 dry_run: bool = True):

        self.binance = BinanceClient(api_key, api_secret, testnet)
        self.strategy = FailedFVGStrategy()
        self.risk_per_trade = risk_per_trade
        self.dry_run = dry_run

        self.pending_orders: List[LimitOrder] = []
        self.position: Optional[Position] = None

        logger.info("✅ Failed FVG Bot initialized")
        logger.info(f"   Risk per trade: {risk_per_trade*100}%")
        logger.info(f"   Testnet: {testnet}")
        logger.info(f"   Dry run: {dry_run}")

    def calculate_position_size(self, order: LimitOrder) -> float:
        """Calculate position size based on risk"""
        if self.dry_run:
            balance = 10000.0
        else:
            balance = self.binance.get_balance()

        risk_amount = balance * self.risk_per_trade
        risk_per_unit = abs(order.limit_price - order.sl)
        size = risk_amount / risk_per_unit

        return round(size, 3)

    def check_limit_orders(self, current_price: float, current_time: datetime):
        """Check if any limit orders filled (simulated in dry_run)"""
        if not self.pending_orders:
            return

        filled_order = None
        expired_orders = []

        for order in self.pending_orders:
            # Check expiry
            if order.is_expired(current_time):
                logger.info(f"⌛ Order expired: {order.order_type} @ ${order.limit_price:.2f}")
                expired_orders.append(order)
                continue

            # Check fill (simulated)
            if order.order_type == 'LONG':
                if current_price <= order.limit_price:
                    logger.info(f"🎯 LONG LIMIT HIT @ ${current_price:.2f}")
                    order.filled = True
                    order.filled_price = order.limit_price
                    order.filled_time = current_time
                    filled_order = order
                    break
            else:  # SHORT
                if current_price >= order.limit_price:
                    logger.info(f"🎯 SHORT LIMIT HIT @ ${current_price:.2f}")
                    order.filled = True
                    order.filled_price = order.limit_price
                    order.filled_time = current_time
                    filled_order = order
                    break

        # Process filled order
        if filled_order:
            self.pending_orders.remove(filled_order)
            size = self.calculate_position_size(filled_order)
            self.position = Position(filled_order, size, current_time)

            print(f"\n✅ POSITION OPENED")
            print(f"   Type: {filled_order.order_type}")
            print(f"   Entry: ${filled_order.filled_price:.2f}")
            print(f"   Size: {size:.4f} BTC")
            print(f"   SL: ${self.position.sl:.2f}")
            print(f"   TP: ${self.position.tp:.2f}")
            print(f"   RR: {self.position.rr:.2f}")

        # Remove expired
        for order in expired_orders:
            if order in self.pending_orders:
                self.pending_orders.remove(order)

    def check_exits(self, current_price: float, current_time: datetime):
        """Check for position exits"""
        if not self.position:
            return

        # Check SL
        if self.position.type == 'LONG':
            if current_price <= self.position.sl:
                pnl = (current_price - self.position.entry) * self.position.size
                print(f"\n🛑 STOP LOSS HIT")
                print(f"   Exit: ${current_price:.2f}")
                print(f"   PnL: ${pnl:+.2f}")
                self.position = None
                return
        else:  # SHORT
            if current_price >= self.position.sl:
                pnl = (self.position.entry - current_price) * self.position.size
                print(f"\n🛑 STOP LOSS HIT")
                print(f"   Exit: ${current_price:.2f}")
                print(f"   PnL: ${pnl:+.2f}")
                self.position = None
                return

        # Check TP
        if self.position.type == 'LONG':
            if current_price >= self.position.tp:
                pnl = (current_price - self.position.entry) * self.position.size
                print(f"\n🎯 TAKE PROFIT HIT")
                print(f"   Exit: ${current_price:.2f}")
                print(f"   PnL: ${pnl:+.2f}")
                self.position = None
                return
        else:  # SHORT
            if current_price <= self.position.tp:
                pnl = (self.position.entry - current_price) * self.position.size
                print(f"\n🎯 TAKE PROFIT HIT")
                print(f"   Exit: ${current_price:.2f}")
                print(f"   PnL: ${pnl:+.2f}")
                self.position = None
                return

    def run(self, check_interval: int = 60):
        """Main bot loop"""
        logger.info("="*80)
        logger.info("🚀 FAILED FVG BOT STARTED")
        logger.info("="*80)

        print(f"\n🚀 Failed 4H FVG Bot started")
        print(f"   Strategy: Failed 4H FVG with 15M execution")
        print(f"   Check interval: {check_interval}s")
        print(f"   Waiting for setups...\n")

        iteration = 0

        while True:
            try:
                iteration += 1
                current_time = datetime.utcnow()

                logger.info(f"\n{'='*60}")
                logger.info(f"Iteration #{iteration} | {current_time}")
                logger.info(f"{'='*60}")

                # Fetch data
                df_4h = self.binance.get_klines(interval='4h', limit=100)
                df_15m = self.binance.get_klines(interval='15m', limit=200)
                current_price = self.binance.get_current_price()

                logger.info(f"💵 BTC Price: ${current_price:,.2f}")

                # Status
                if self.position:
                    logger.info(f"📈 Position: {self.position.type} | Entry: ${self.position.entry:.2f}")
                elif self.pending_orders:
                    logger.info(f"⏳ Pending: {len(self.pending_orders)} orders")
                else:
                    logger.info("💤 No position, no orders")

                # Check pending orders
                if self.pending_orders and not self.position:
                    self.check_limit_orders(current_price, current_time)

                # Check exits
                if self.position:
                    self.check_exits(current_price, current_time)

                # Check for new setups (only if no position and < 3 orders)
                if not self.position and len(self.pending_orders) < 3:
                    logger.info("🔎 Checking for failed FVG setups...")
                    new_orders = self.strategy.check_for_setup(df_4h, df_15m, current_time)

                    if new_orders:
                        self.pending_orders.extend(new_orders)

                        print(f"\n📋 {len(new_orders)} NEW LIMIT ORDER(S)")
                        for order in new_orders:
                            print(f"   {order.order_type} @ ${order.limit_price:.2f}")
                            print(f"   SL: ${order.sl:.2f} | TP: ${order.tp:.2f}")
                            print(f"   RR: {order.rr:.2f} | SL: {order.sl_pct:.2f}%")

                # Sleep
                time.sleep(check_interval)

            except KeyboardInterrupt:
                logger.info("\n⚠️ Bot stopped by user")
                print("\n⚠️ Bot stopped")
                break
            except Exception as e:
                logger.error(f"❌ Error: {e}", exc_info=True)
                time.sleep(check_interval)


if __name__ == "__main__":
    # Load credentials
    API_KEY = os.getenv('BINANCE_API_KEY', '')
    API_SECRET = os.getenv('BINANCE_API_SECRET', '')
    DRY_RUN = os.getenv('DRY_RUN', 'true').lower() == 'true'

    if not DRY_RUN and (not API_KEY or not API_SECRET):
        print("❌ Set BINANCE_API_KEY and BINANCE_API_SECRET or use DRY_RUN=true")
        exit(1)

    # Initialize bot
    bot = FailedFVGBot(
        api_key=API_KEY or 'dummy',
        api_secret=API_SECRET or 'dummy',
        risk_per_trade=0.02,
        testnet=True,
        dry_run=DRY_RUN
    )

    # Run
    bot.run(check_interval=60)
