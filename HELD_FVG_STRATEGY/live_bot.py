"""
HELD FVG Live Trading Bot
Strategy: 4h_close + rr_3.0_liq
Exchange: Binance Futures

IMPORTANT: This bot trades with REAL MONEY on Binance Futures!
"""

import logging
import time
import signal
import sys
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import pandas as pd
import numpy as np
from binance.client import Client
from binance.exceptions import BinanceAPIException

import config

# =============================================================================
# LOGGING SETUP
# =============================================================================

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT,
    datefmt=config.LOG_DATE_FORMAT
)
logger = logging.getLogger(__name__)


# =============================================================================
# FVG CLASS (REUSED FROM BACKTEST)
# =============================================================================

class HeldFVG:
    """FVG tracker for HELD strategy (live trading)"""

    def __init__(self, fvg_type: str, top: float, bottom: float,
                 formed_time: datetime):
        self.type = fvg_type  # 'BULLISH' or 'BEARISH'
        self.top = top
        self.bottom = bottom
        self.formed_time = formed_time

        self.entered = False
        self.held = False
        self.invalidated = False

        self.hold_time = None
        self.hold_price = None
        self.hold_available_time = None

        self.highs_inside = []
        self.lows_inside = []

        self.has_filled_trade = False

        self.id = f"{fvg_type}_{top:.2f}_{bottom:.2f}_{int(formed_time.timestamp())}"

    def is_inside(self, price: float) -> bool:
        """Check if price is inside FVG zone"""
        return self.bottom <= price <= self.top

    def is_fully_passed(self, candle_high: float, candle_low: float) -> bool:
        """Check if FVG is invalidated"""
        if self.type == 'BULLISH':
            return candle_low < self.bottom
        else:
            return candle_high > self.top

    def check_hold(self, candle: Dict, candle_close_time: datetime) -> bool:
        """
        Check if FVG is HELD
        Returns True if hold detected on this candle
        """
        candle_high = candle['high']
        candle_low = candle['low']
        candle_close = candle['close']

        # Check if touched
        touched = not (candle_high < self.bottom or candle_low > self.top)

        if not touched:
            return False

        if not self.entered:
            self.entered = True

        # Track highs/lows for SL calculation
        if candle_high >= self.bottom:
            self.highs_inside.append(candle_high)
        if candle_low <= self.top:
            self.lows_inside.append(candle_low)

        # Check hold condition
        if self.type == 'BULLISH':
            if self.entered and self.bottom <= candle_close <= self.top:
                if not self.held:
                    self.held = True
                    self.hold_time = datetime.fromtimestamp(candle['close_time'] / 1000)
                    self.hold_price = candle_close
                    self.hold_available_time = candle_close_time
                    return True
        else:  # BEARISH
            if self.entered and self.bottom <= candle_close <= self.top:
                if not self.held:
                    self.held = True
                    self.hold_time = datetime.fromtimestamp(candle['close_time'] / 1000)
                    self.hold_price = candle_close
                    self.hold_available_time = candle_close_time
                    return True

        return False

    def get_stop_loss(self) -> Optional[float]:
        """Get SL price based on highs/lows inside zone"""
        if self.type == 'BULLISH':
            # LONG: SL below zone
            if self.lows_inside:
                return min(self.lows_inside) * 0.998
            else:
                return self.bottom * 0.998
        else:
            # SHORT: SL above zone
            if self.highs_inside:
                return max(self.highs_inside) * 1.002
            else:
                return self.top * 1.002


# =============================================================================
# BINANCE FUTURES CLIENT
# =============================================================================

class BinanceFuturesClient:
    """Wrapper for Binance Futures API"""

    def __init__(self):
        self.client = Client(config.BINANCE_API_KEY, config.BINANCE_API_SECRET)

        # Set leverage
        try:
            self.client.futures_change_leverage(
                symbol=config.SYMBOL,
                leverage=config.LEVERAGE
            )
            logger.info(f"Leverage set to {config.LEVERAGE}x for {config.SYMBOL}")
        except BinanceAPIException as e:
            logger.error(f"Failed to set leverage: {e}")
            raise

    def get_4h_candles(self, limit: int = 100) -> pd.DataFrame:
        """Fetch 4H candles"""
        try:
            klines = self.client.futures_klines(
                symbol=config.SYMBOL,
                interval=Client.KLINE_INTERVAL_4HOUR,
                limit=limit
            )

            df = pd.DataFrame(klines, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])

            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
            df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')

            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)

            return df

        except BinanceAPIException as e:
            logger.error(f"Failed to fetch 4H candles: {e}")
            raise

    def get_15m_candles(self, limit: int = 200) -> pd.DataFrame:
        """Fetch 15M candles for liquidity detection"""
        try:
            klines = self.client.futures_klines(
                symbol=config.SYMBOL,
                interval=Client.KLINE_INTERVAL_15MINUTE,
                limit=limit
            )

            df = pd.DataFrame(klines, columns=[
                'open_time', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])

            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
            df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')

            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)

            return df

        except BinanceAPIException as e:
            logger.error(f"Failed to fetch 15M candles: {e}")
            raise

    def get_balance(self) -> float:
        """Get USDT balance"""
        try:
            account = self.client.futures_account()
            for asset in account['assets']:
                if asset['asset'] == 'USDT':
                    return float(asset['availableBalance'])
            return 0.0
        except BinanceAPIException as e:
            logger.error(f"Failed to get balance: {e}")
            raise

    def get_position(self) -> Optional[Dict]:
        """Get current position for symbol"""
        try:
            positions = self.client.futures_position_information(symbol=config.SYMBOL)
            for pos in positions:
                if float(pos['positionAmt']) != 0:
                    return {
                        'side': 'LONG' if float(pos['positionAmt']) > 0 else 'SHORT',
                        'size': abs(float(pos['positionAmt'])),
                        'entry_price': float(pos['entryPrice']),
                        'unrealized_pnl': float(pos['unRealizedProfit'])
                    }
            return None
        except BinanceAPIException as e:
            logger.error(f"Failed to get position: {e}")
            raise

    def open_position_with_sl_tp(self, direction: str, quantity: float,
                                  sl_price: float, tp_price: float) -> Dict:
        """
        Open position with automatic SL and TP orders

        Returns: dict with entry_order, sl_order, tp_order
        """
        try:
            # 1. Open market position
            side = 'BUY' if direction == 'LONG' else 'SELL'

            logger.info(f"Opening {direction} position: {quantity} {config.SYMBOL} at market")

            entry_order = self.client.futures_create_order(
                symbol=config.SYMBOL,
                side=side,
                type='MARKET',
                quantity=quantity
            )

            logger.info(f"Entry order filled: {entry_order['orderId']}")

            # Get fill price
            time.sleep(0.5)  # Wait for order to be processed
            fills = self.client.futures_get_order(
                symbol=config.SYMBOL,
                orderId=entry_order['orderId']
            )
            entry_price = float(fills['avgPrice'])

            # 2. Create STOP_MARKET order for SL
            sl_side = 'SELL' if direction == 'LONG' else 'BUY'

            logger.info(f"Creating SL order at {sl_price:.2f}")

            sl_order = self.client.futures_create_order(
                symbol=config.SYMBOL,
                side=sl_side,
                type='STOP_MARKET',
                stopPrice=round(sl_price, 2),
                closePosition=True
            )

            logger.info(f"SL order created: {sl_order['orderId']}")

            # 3. Create TAKE_PROFIT_MARKET order for TP
            logger.info(f"Creating TP order at {tp_price:.2f}")

            tp_order = self.client.futures_create_order(
                symbol=config.SYMBOL,
                side=sl_side,  # Same side as SL (closes position)
                type='TAKE_PROFIT_MARKET',
                stopPrice=round(tp_price, 2),
                closePosition=True
            )

            logger.info(f"TP order created: {tp_order['orderId']}")

            return {
                'entry_order': entry_order,
                'entry_price': entry_price,
                'sl_order': sl_order,
                'tp_order': tp_order
            }

        except BinanceAPIException as e:
            logger.error(f"Failed to open position: {e}")
            raise

    def cancel_all_orders(self):
        """Cancel all open orders"""
        try:
            result = self.client.futures_cancel_all_open_orders(symbol=config.SYMBOL)
            logger.info(f"Cancelled all orders: {result}")
        except BinanceAPIException as e:
            logger.error(f"Failed to cancel orders: {e}")


# =============================================================================
# LIQUIDITY DETECTOR (REUSED FROM BACKTEST - BACKWARD-LOOKING ONLY!)
# =============================================================================

class LiquidityDetector:
    """Detect liquidity zones (swing highs/lows) for TP"""

    @staticmethod
    def find_liquidity(df: pd.DataFrame, current_idx: int, direction: str,
                       lookback: int = 50) -> Optional[float]:
        """
        Find liquidity zone (backward-looking only!)

        CRITICAL: This uses the FIXED version from backtest (i+1, not i+3)
        """
        start_idx = max(0, current_idx - lookback)

        if direction == 'LONG':
            # Look for swing high
            for i in range(current_idx - 1, start_idx, -1):
                if i < 2 or i >= len(df) - 2:
                    continue

                candle = df.iloc[i]
                is_swing_high = True

                # FIXED: Only look backward (i+1 instead of i+3)
                for j in range(max(0, i-2), min(len(df), i+1)):
                    if j != i and df.iloc[j]['high'] > candle['high']:
                        is_swing_high = False
                        break

                if is_swing_high:
                    return candle['high'] * 0.999  # -0.1% buffer

        else:  # SHORT
            # Look for swing low
            for i in range(current_idx - 1, start_idx, -1):
                if i < 2 or i >= len(df) - 2:
                    continue

                candle = df.iloc[i]
                is_swing_low = True

                # FIXED: Only look backward (i+1 instead of i+3)
                for j in range(max(0, i-2), min(len(df), i+1)):
                    if j != i and df.iloc[j]['low'] < candle['low']:
                        is_swing_low = False
                        break

                if is_swing_low:
                    return candle['low'] * 1.001  # +0.1% buffer

        return None


# =============================================================================
# FVG TRACKER
# =============================================================================

class FVGTracker:
    """Track and manage 4H FVGs"""

    def __init__(self):
        self.active_fvgs: List[HeldFVG] = []
        self.held_fvgs: List[HeldFVG] = []

    def detect_fvg(self, df: pd.DataFrame) -> List[HeldFVG]:
        """Detect FVGs in recent CLOSED candles only"""
        fvgs = []

        if len(df) < 4:
            return fvgs

        # IMPORTANT: Use iloc[-2] as last CLOSED candle
        # iloc[-1] is the current (potentially unclosed) candle from Binance API
        i = len(df) - 2

        candle = df.iloc[i]
        candle_prev2 = df.iloc[i-2]

        # Bullish FVG
        if candle['low'] > candle_prev2['high']:
            fvg = HeldFVG(
                fvg_type='BULLISH',
                top=candle['low'],
                bottom=candle_prev2['high'],
                formed_time=candle['open_time']
            )
            fvgs.append(fvg)

        # Bearish FVG
        elif candle['high'] < candle_prev2['low']:
            fvg = HeldFVG(
                fvg_type='BEARISH',
                top=candle_prev2['low'],
                bottom=candle['high'],
                formed_time=candle['open_time']
            )
            fvgs.append(fvg)

        return fvgs

    def update_fvgs(self, df: pd.DataFrame) -> List[HeldFVG]:
        """
        Update FVGs with new candle data
        Returns list of newly held FVGs
        """
        newly_held = []

        if len(df) < 4:
            return newly_held

        # Detect new FVGs
        new_fvgs = self.detect_fvg(df)
        newly_added_ids = set()
        for fvg in new_fvgs:
            if not any(existing.id == fvg.id for existing in self.active_fvgs):
                self.active_fvgs.append(fvg)
                newly_added_ids.add(fvg.id)
                logger.info(f"New FVG detected: {fvg.type} at ${fvg.bottom:.2f}-${fvg.top:.2f}")

        # Check active FVGs for holds/invalidations
        # IMPORTANT: Use iloc[-2] as last CLOSED candle (iloc[-1] may be unclosed)
        # Skip FVGs that were just detected on this candle to avoid look-ahead bias
        last_closed_candle = df.iloc[-2]
        candle_dict = {
            'high': last_closed_candle['high'],
            'low': last_closed_candle['low'],
            'close': last_closed_candle['close'],
            'close_time': int(last_closed_candle['close_time'].timestamp() * 1000)
        }
        candle_close_time = last_closed_candle['close_time']

        for fvg in self.active_fvgs[:]:
            # Skip newly added FVGs - they should only be checked starting from next candle
            if fvg.id in newly_added_ids:
                continue

            # Check hold
            if fvg.check_hold(candle_dict, candle_close_time):
                self.held_fvgs.append(fvg)
                self.active_fvgs.remove(fvg)
                newly_held.append(fvg)
                logger.info(f"FVG HELD: {fvg.type} at ${fvg.hold_price:.2f}")

            # Check invalidation
            elif fvg.is_fully_passed(last_closed_candle['high'], last_closed_candle['low']):
                fvg.invalidated = True
                self.active_fvgs.remove(fvg)

        return newly_held


# =============================================================================
# TRADE MANAGER
# =============================================================================

class TradeManager:
    """Manage trade creation and execution"""

    def __init__(self, client: BinanceFuturesClient):
        self.client = client

    def create_setup(self, held_fvg: HeldFVG, df_15m: pd.DataFrame,
                     current_price: float) -> Optional[Dict]:
        """
        Create trade setup for held FVG

        Returns: dict with entry, sl, tp, direction, size if valid, else None
        """
        # Direction
        direction = 'LONG' if held_fvg.type == 'BULLISH' else 'SHORT'

        # Entry (4h_close method)
        entry = held_fvg.hold_price

        # SL
        sl = held_fvg.get_stop_loss()
        if sl is None:
            return None

        # Validate SL distance
        sl_distance_pct = abs(entry - sl) / entry * 100
        if sl_distance_pct < config.MIN_SL_PCT * 100 or sl_distance_pct > config.MAX_SL_PCT * 100:
            logger.warning(f"SL distance {sl_distance_pct:.2f}% out of range [{config.MIN_SL_PCT*100}%-{config.MAX_SL_PCT*100}%]")
            return None

        # Find liquidity for TP (rr_3.0_liq method)
        # IMPORTANT: Use len-2 to point to last CLOSED candle
        # len-1 would be the current unclosed candle from Binance API
        current_idx = len(df_15m) - 2
        liquidity = LiquidityDetector.find_liquidity(
            df_15m, current_idx, direction,
            lookback=config.LIQUIDITY_LOOKBACK
        )

        if liquidity is None:
            logger.warning("No liquidity zone found")
            return None

        # Validate liquidity RR
        risk = abs(entry - sl)
        liquidity_rr = abs(liquidity - entry) / risk

        if direction == 'LONG':
            if liquidity < entry + risk * config.LIQUIDITY_MIN_RR:
                logger.warning(f"Liquidity RR {liquidity_rr:.2f} < {config.LIQUIDITY_MIN_RR}")
                return None
            if liquidity > entry + risk * config.LIQUIDITY_MAX_RR:
                liquidity = entry + risk * config.LIQUIDITY_MAX_RR
        else:  # SHORT
            if liquidity > entry - risk * config.LIQUIDITY_MIN_RR:
                logger.warning(f"Liquidity RR {liquidity_rr:.2f} < {config.LIQUIDITY_MIN_RR}")
                return None
            if liquidity < entry - risk * config.LIQUIDITY_MAX_RR:
                liquidity = entry - risk * config.LIQUIDITY_MAX_RR

        tp = liquidity

        # Calculate position size
        balance = self.client.get_balance()
        risk_amount = balance * config.RISK_PER_TRADE
        risk_per_unit = abs(entry - sl)
        size = risk_amount / risk_per_unit

        # Validate notional
        notional = entry * size
        if notional < config.MIN_NOTIONAL_USDT:
            logger.warning(f"Notional ${notional:.2f} < ${config.MIN_NOTIONAL_USDT}")
            return None

        if notional > config.MAX_POSITION_SIZE_USDT:
            size = config.MAX_POSITION_SIZE_USDT / entry
            logger.warning(f"Position size capped at ${config.MAX_POSITION_SIZE_USDT}")

        # Round size to appropriate precision (BTC usually 3 decimals)
        size = round(size, 3)

        return {
            'direction': direction,
            'entry': entry,
            'sl': sl,
            'tp': tp,
            'size': size,
            'balance': balance,
            'risk_amount': risk_amount,
            'rr': abs(tp - entry) / abs(entry - sl)
        }

    def execute_trade(self, setup: Dict) -> bool:
        """Execute trade with SL and TP"""
        try:
            logger.info(f"="*60)
            logger.info(f"OPENING TRADE:")
            logger.info(f"  Direction: {setup['direction']}")
            logger.info(f"  Entry: ${setup['entry']:.2f}")
            logger.info(f"  SL: ${setup['sl']:.2f}")
            logger.info(f"  TP: ${setup['tp']:.2f}")
            logger.info(f"  Size: {setup['size']} BTC")
            logger.info(f"  Notional: ${setup['entry'] * setup['size']:.2f}")
            logger.info(f"  Risk: ${setup['risk_amount']:.2f} ({config.RISK_PER_TRADE*100}%)")
            logger.info(f"  R:R: {setup['rr']:.2f}")
            logger.info(f"="*60)

            result = self.client.open_position_with_sl_tp(
                direction=setup['direction'],
                quantity=setup['size'],
                sl_price=setup['sl'],
                tp_price=setup['tp']
            )

            logger.info(f"✅ Trade opened successfully!")
            logger.info(f"  Entry Price: ${result['entry_price']:.2f}")
            logger.info(f"  Entry Order ID: {result['entry_order']['orderId']}")
            logger.info(f"  SL Order ID: {result['sl_order']['orderId']}")
            logger.info(f"  TP Order ID: {result['tp_order']['orderId']}")

            return True

        except Exception as e:
            logger.error(f"❌ Failed to execute trade: {e}")
            return False


# =============================================================================
# MAIN BOT
# =============================================================================

class HeldFVGBot:
    """Main live trading bot"""

    def __init__(self):
        self.client = BinanceFuturesClient()
        self.fvg_tracker = FVGTracker()
        self.trade_manager = TradeManager(self.client)

        self.running = True
        self.last_4h_candle_time = None
        self.trades_today = 0
        self.last_reset_date = datetime.now().date()

        # Setup signal handlers
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

    def shutdown(self, signum, frame):
        """Graceful shutdown"""
        logger.info("Shutdown signal received. Closing bot...")
        self.running = False
        sys.exit(0)

    def check_daily_limit(self):
        """Reset daily trade counter"""
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.trades_today = 0
            self.last_reset_date = today
            logger.info(f"Daily trade counter reset: {today}")

    def run(self):
        """Main bot loop"""
        logger.info("="*80)
        logger.info("HELD FVG LIVE BOT STARTED")
        logger.info("="*80)
        config.print_config()
        logger.info("="*80)

        # Initial balance check
        balance = self.client.get_balance()
        logger.info(f"Current balance: ${balance:.2f} USDT")

        while self.running:
            try:
                # Check daily limit
                self.check_daily_limit()

                # Check if max trades reached today
                if self.trades_today >= config.MAX_TRADES_PER_DAY:
                    logger.warning(f"Max trades per day reached ({config.MAX_TRADES_PER_DAY}). Waiting until tomorrow...")
                    time.sleep(config.POLL_INTERVAL)
                    continue

                # Check for existing position
                position = self.client.get_position()
                if position:
                    # Already have a position - just monitor
                    time.sleep(config.POLL_INTERVAL)
                    continue

                # Fetch 4H candles
                df_4h = self.client.get_4h_candles(limit=config.HISTORICAL_CANDLES_4H)

                # Check if new 4H candle closed
                # IMPORTANT: Use iloc[-2] for last CLOSED candle
                # iloc[-1] is the current UNCLOSED candle from Binance API
                latest_closed_candle_time = df_4h.iloc[-2]['close_time']

                if self.last_4h_candle_time is None:
                    self.last_4h_candle_time = latest_closed_candle_time
                    logger.info(f"Initial 4H candle time set: {latest_closed_candle_time}")

                if latest_closed_candle_time > self.last_4h_candle_time:
                    # New 4H candle closed!
                    logger.info(f"4H candle closed at {latest_closed_candle_time}")
                    self.last_4h_candle_time = latest_closed_candle_time

                    # Update FVGs
                    newly_held = self.fvg_tracker.update_fvgs(df_4h)

                    # Check for trade setups
                    for held_fvg in newly_held:
                        if held_fvg.has_filled_trade:
                            continue

                        # CRITICAL: Verify hold_available_time is set and current time >= hold_available_time
                        if not held_fvg.hold_available_time:
                            logger.warning(f"FVG {held_fvg.id} has no hold_available_time, skipping")
                            continue

                        current_time = datetime.now()
                        if current_time < held_fvg.hold_available_time:
                            logger.warning(
                                f"LOOKAHEAD BIAS PREVENTION: Current time {current_time} < "
                                f"hold_available_time {held_fvg.hold_available_time}, skipping trade"
                            )
                            continue

                        # Fetch 15M candles for liquidity detection
                        df_15m = self.client.get_15m_candles(limit=config.HISTORICAL_CANDLES_15M)

                        # Use last CLOSED candle for current price
                        current_price = df_15m.iloc[-2]['close']

                        # Create setup
                        setup = self.trade_manager.create_setup(held_fvg, df_15m, current_price)

                        if setup:
                            # Execute trade
                            success = self.trade_manager.execute_trade(setup)

                            if success:
                                held_fvg.has_filled_trade = True
                                self.trades_today += 1
                                break  # Only one trade at a time

                # Sleep until next check
                time.sleep(config.POLL_INTERVAL)

            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(config.POLL_INTERVAL)


# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    bot = HeldFVGBot()
    bot.run()
