"""
PRODUCTION_Q3_DynamicRR_VariableRisk Live Trading Bot
Strategy: Impulse Breakout + Dynamic RR + Variable Risk
Exchange: Binance Futures

CRITICAL: This bot trades with REAL MONEY on Binance Futures!
- Uses ONLY closed candles (iloc[-2])
- NO lookahead bias
- Dynamic RR based on quality score (2.5x - 8.0x)
- Variable risk based on quality category (1.5% - 2.0%)
"""

import logging
import time
import signal
import sys
from datetime import datetime
from typing import Optional, Dict
import pandas as pd
import numpy as np

import config
from binance_client import BinanceFuturesClient
from impulse_detectors import ATRBasedDetector, calculate_atr_column
from entry_strategies import BreakoutEntry
from ema_filter import EMAFilter
from quality_filter import QualityScorer

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
# IMPULSE TRACKER
# =============================================================================

class ImpulseTracker:
    """Track detected impulse candles"""

    def __init__(self):
        self.detected_impulses = []  # List of detected impulse candles
        self.processed_impulses = set()  # Set of processed impulse IDs

    def add_impulse(self, impulse_idx: int, impulse_time: datetime,
                    direction: int, strength: float):
        """Add detected impulse"""
        impulse_id = f"{impulse_time.isoformat()}_{direction}"

        if impulse_id not in self.processed_impulses:
            self.detected_impulses.append({
                'idx': impulse_idx,
                'time': impulse_time,
                'direction': direction,
                'strength': strength,
                'id': impulse_id,
                'processed': False
            })
            logger.info(f"New impulse detected: {impulse_id} (strength: {strength:.2f})")

    def mark_processed(self, impulse_id: str):
        """Mark impulse as processed"""
        self.processed_impulses.add(impulse_id)
        for imp in self.detected_impulses:
            if imp['id'] == impulse_id:
                imp['processed'] = True

    def get_unprocessed(self):
        """Get unprocessed impulses"""
        return [imp for imp in self.detected_impulses if not imp['processed']]

# =============================================================================
# TRADE MANAGER
# =============================================================================

class TradeManager:
    """Manage trade creation and execution"""

    def __init__(self, client: BinanceFuturesClient):
        self.client = client

        # Strategy components
        self.impulse_detector = ATRBasedDetector(
            atr_multiplier=config.IMPULSE_ATR_MULTIPLIER,
            body_ratio_threshold=config.IMPULSE_BODY_RATIO,
            atr_period=config.IMPULSE_ATR_PERIOD
        )
        self.entry_strategy = BreakoutEntry(
            consolidation_min=config.CONSOLIDATION_MIN,
            consolidation_max=config.CONSOLIDATION_MAX,
            rr_ratio=3.0,  # Base RR, will be overridden
            stop_buffer_pct=config.STOP_BUFFER_PCT
        )
        self.ema_filter = EMAFilter(
            short_period=config.EMA_SHORT_PERIOD,
            long_period=config.EMA_LONG_PERIOD,
            lookback=config.EMA_LOOKBACK
        )
        self.quality_scorer = QualityScorer(
            "Q3",
            min_score=config.MIN_QUALITY_SCORE
        )

    def detect_impulse(self, df_4h: pd.DataFrame) -> Optional[Dict]:
        """
        Detect impulse on last CLOSED 4H candle

        CRITICAL: Uses iloc[-2] for last closed candle!

        Returns:
            dict with impulse info or None
        """
        if len(df_4h) < 20:
            return None

        # CRITICAL: Use iloc[-2] as last CLOSED candle
        # iloc[-1] is the current UNCLOSED candle from Binance API
        last_closed_idx = len(df_4h) - 2

        is_impulse, direction, strength = self.impulse_detector.detect(df_4h, last_closed_idx)

        if is_impulse:
            impulse_candle = df_4h.iloc[last_closed_idx]
            return {
                'idx': last_closed_idx,
                'time': impulse_candle['Open time'],
                'close_time': impulse_candle['Close time'],
                'direction': direction,
                'strength': strength,
                'high': impulse_candle['High'],
                'low': impulse_candle['Low']
            }

        return None

    def find_entry(self, df_4h: pd.DataFrame, df_1h: pd.DataFrame,
                   impulse_idx: int, impulse_direction: int) -> Optional[Dict]:
        """
        Find entry setup

        CRITICAL: All data passed here is already verified to be closed candles only
        """
        # Find entry using breakout strategy
        entry = self.entry_strategy.find_entry(
            df_4h.copy(),
            df_1h.copy(),
            impulse_idx,
            impulse_direction,
            self.ema_filter
        )

        if entry is None:
            return None

        # Validate entry time (must be after impulse close)
        impulse_close_time = pd.to_datetime(df_4h.iloc[impulse_idx]['Close time'])
        entry_time = pd.to_datetime(entry['entry_time'])

        if entry_time < impulse_close_time:
            logger.warning("LOOKAHEAD BIAS DETECTED! Entry before impulse close - skipping")
            return None

        # Calculate quality score
        # Use data up to entry time (no look-forward bias)
        htf_for_quality = df_4h[df_4h['Open time'] <= df_4h.iloc[impulse_idx]['Open time']].copy()
        ltf_for_quality = df_1h[df_1h['Open time'] <= entry_time].copy()

        quality_score = self.quality_scorer.score_setup(
            htf_for_quality,
            ltf_for_quality,
            len(htf_for_quality) - 1,
            impulse_direction,
            entry
        )

        entry['quality_score'] = quality_score

        # Check if score passes minimum
        if quality_score < config.MIN_QUALITY_SCORE:
            logger.info(f"Quality score {quality_score} < {config.MIN_QUALITY_SCORE} - filtered")
            return None

        # Get dynamic RR for this quality score
        target_rr = config.get_rr_for_score(quality_score)
        if target_rr is None:
            logger.info(f"No RR mapping for score {quality_score} - filtered")
            return None

        # Get variable risk for this quality score
        risk_pct = config.get_risk_for_score(quality_score)
        if risk_pct is None:
            logger.info(f"No risk mapping for score {quality_score} - filtered")
            return None

        # Recalculate TP with dynamic RR
        entry_price = entry['entry_price']
        stop_loss = entry['stop_loss']
        side = entry['side']
        risk = abs(entry_price - stop_loss)

        if side == 'long':
            take_profit = entry_price + (risk * target_rr)
        else:
            take_profit = entry_price - (risk * target_rr)

        entry['take_profit'] = take_profit
        entry['rr'] = target_rr
        entry['risk_pct'] = risk_pct

        # Validate SL distance
        sl_distance_pct = abs(entry_price - stop_loss) / entry_price
        if sl_distance_pct < config.MIN_SL_PCT or sl_distance_pct > config.MAX_SL_PCT:
            logger.warning(f"SL distance {sl_distance_pct*100:.2f}% out of range")
            return None

        return entry

    def calculate_position_size(self, entry: Dict, balance: float) -> Optional[float]:
        """Calculate position size with variable risk"""
        entry_price = entry['entry_price']
        stop_loss = entry['stop_loss']
        risk_pct = entry['risk_pct']

        # Calculate position size
        risk_amount = balance * (risk_pct / 100.0)
        risk_per_unit = abs(entry_price - stop_loss)

        if risk_per_unit == 0:
            return None

        position_size = risk_amount / risk_per_unit

        # Validate notional
        notional = entry_price * position_size
        if notional < config.MIN_NOTIONAL_USDT:
            logger.warning(f"Notional ${notional:.2f} < ${config.MIN_NOTIONAL_USDT}")
            return None

        if notional > config.MAX_POSITION_SIZE_USDT:
            position_size = config.MAX_POSITION_SIZE_USDT / entry_price
            logger.warning(f"Position size capped at ${config.MAX_POSITION_SIZE_USDT}")

        # Round to 3 decimals (BTC precision)
        position_size = round(position_size, 3)

        return position_size

    def execute_trade(self, entry: Dict, position_size: float, balance: float) -> bool:
        """Execute trade with SL and TP"""
        try:
            logger.info("="*80)
            logger.info("OPENING TRADE:")
            logger.info(f"  Direction: {entry['side'].upper()}")
            logger.info(f"  Entry: ${entry['entry_price']:.2f}")
            logger.info(f"  SL: ${entry['stop_loss']:.2f}")
            logger.info(f"  TP: ${entry['take_profit']:.2f}")
            logger.info(f"  Size: {position_size} BTC")
            logger.info(f"  Notional: ${entry['entry_price'] * position_size:.2f}")
            logger.info(f"  Risk: ${balance * (entry['risk_pct']/100.0):.2f} ({entry['risk_pct']}%)")
            logger.info(f"  R:R: {entry['rr']:.1f}")
            logger.info(f"  Quality Score: {entry['quality_score']}")
            logger.info("="*80)

            direction = 'LONG' if entry['side'] == 'long' else 'SHORT'

            result = self.client.open_position_with_sl_tp(
                direction=direction,
                quantity=position_size,
                sl_price=entry['stop_loss'],
                tp_price=entry['take_profit']
            )

            logger.info("✅ Trade opened successfully!")
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

class ProductionQ3Bot:
    """Main live trading bot"""

    def __init__(self):
        self.client = BinanceFuturesClient()
        self.trade_manager = TradeManager(self.client)
        self.impulse_tracker = ImpulseTracker()

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
        logger.info("PRODUCTION_Q3_DynamicRR_VariableRisk LIVE BOT STARTED")
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
                    logger.warning(f"Max trades per day reached ({config.MAX_TRADES_PER_DAY}). Waiting...")
                    time.sleep(config.POLL_INTERVAL)
                    continue

                # Check for existing position
                position = self.client.get_position()
                if position:
                    # Already have a position - just monitor
                    logger.debug(f"Position open: {position['side']} {position['size']} BTC")
                    time.sleep(config.POLL_INTERVAL)
                    continue

                # Fetch 4H candles
                df_4h = self.client.get_4h_candles(limit=config.HISTORICAL_CANDLES_4H)

                # Prepare data (calculate ATR)
                df_4h = calculate_atr_column(df_4h, period=config.IMPULSE_ATR_PERIOD)

                # Check if new 4H candle closed
                # CRITICAL: Use iloc[-2] for last CLOSED candle
                latest_closed_candle_time = df_4h.iloc[-2]['Close time']

                if self.last_4h_candle_time is None:
                    self.last_4h_candle_time = latest_closed_candle_time
                    logger.info(f"Initial 4H candle time set: {latest_closed_candle_time}")

                if latest_closed_candle_time > self.last_4h_candle_time:
                    # New 4H candle closed!
                    logger.info(f"✅ 4H candle closed at {latest_closed_candle_time}")
                    self.last_4h_candle_time = latest_closed_candle_time

                    # Detect impulse
                    impulse = self.trade_manager.detect_impulse(df_4h)

                    if impulse:
                        direction_str = "BULLISH" if impulse['direction'] == 1 else "BEARISH"
                        logger.info(f"🔥 IMPULSE DETECTED: {direction_str} (strength: {impulse['strength']:.2f})")
                        self.impulse_tracker.add_impulse(
                            impulse['idx'],
                            impulse['time'],
                            impulse['direction'],
                            impulse['strength']
                        )

                # Process unprocessed impulses
                unprocessed = self.impulse_tracker.get_unprocessed()

                for impulse_data in unprocessed:
                    # Fetch fresh 1H candles
                    df_1h = self.client.get_1h_candles(limit=config.HISTORICAL_CANDLES_1H)

                    # Prepare data (calculate EMA)
                    df_1h = self.trade_manager.ema_filter.prepare_data(df_1h)

                    # Try to find entry
                    entry = self.trade_manager.find_entry(
                        df_4h,
                        df_1h,
                        impulse_data['idx'],
                        impulse_data['direction']
                    )

                    if entry:
                        # Calculate position size
                        balance = self.client.get_balance()
                        position_size = self.trade_manager.calculate_position_size(entry, balance)

                        if position_size:
                            # Execute trade
                            success = self.trade_manager.execute_trade(entry, position_size, balance)

                            if success:
                                self.impulse_tracker.mark_processed(impulse_data['id'])
                                self.trades_today += 1
                                break  # Only one trade at a time

                    # If no entry found yet, leave impulse unprocessed for next iteration

                # Sleep until next check
                time.sleep(config.POLL_INTERVAL)

            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(config.POLL_INTERVAL)

# =============================================================================
# ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    bot = ProductionQ3Bot()
    bot.run()
