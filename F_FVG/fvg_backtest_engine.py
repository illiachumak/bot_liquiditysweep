"""
FVG Backtest Engine - No Look-Ahead Bias
==========================================

Critical timing rules:
- A candle timestamp represents when it OPENED, not when it CLOSED
- 4H candle at 12:00 means: open=12:00, close=16:00
- Cannot trade on candle data until the candle has CLOSED
- All trading decisions must use only information available at decision time

Strategy variations:
1. FAILED FVG - Rejection-based (price enters FVG then rejects)
2. HELD FVG - Continuation-based (price enters FVG and holds)

Entry methods:
A. Immediate (4H close) - Market order at confirmation
B. 15M FVG - Limit order at 15M FVG zone
C. 15M Breakout - Limit order at breakout level

TP methods:
1. Liquidity-based - Nearest swing high/low
2. Fixed RR 2.0
3. Fixed RR 3.0
4. Fixed RR 3.0 with liquidity validation
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import json
from dataclasses import dataclass, field
from enum import Enum


class FVGType(Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"


class Direction(Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class ExitReason(Enum):
    TP = "TP"
    SL = "SL"
    TIMEOUT = "TIMEOUT"
    EXPIRED = "EXPIRED"


@dataclass
class FVG:
    """Fair Value Gap data structure"""
    type: FVGType
    top: float
    bottom: float
    formed_time: pd.Timestamp  # When FVG formed (candle close time)
    timeframe: str

    # State tracking
    entered: bool = False
    rejected: bool = False  # For FAILED strategy
    held: bool = False  # For HELD strategy
    invalidated: bool = False

    # Rejection/Hold tracking
    action_time: Optional[pd.Timestamp] = None  # When rejected/held
    action_price: Optional[float] = None
    action_available_time: Optional[pd.Timestamp] = None  # When this info becomes available

    # Price action inside FVG
    highs_inside: List[float] = field(default_factory=list)
    lows_inside: List[float] = field(default_factory=list)

    # Trade tracking
    has_filled_trade: bool = False
    pending_setup_expiry_time: Optional[pd.Timestamp] = None

    def is_inside(self, price: float) -> bool:
        """Check if price is inside FVG zone"""
        return self.bottom <= price <= self.top

    def is_fully_passed(self, high: float, low: float) -> bool:
        """Check if FVG is invalidated (price passed through completely)"""
        if self.type == FVGType.BULLISH:
            return low < self.bottom  # Broke below
        else:
            return high > self.top  # Broke above

    def check_failed_fvg_rejection(self, candle: pd.Series,
                                   candle_close_time: pd.Timestamp) -> bool:
        """
        Check for FAILED FVG (rejection)

        BULLISH FVG rejection: price entered, then closed BELOW zone
        BEARISH FVG rejection: price entered, then closed ABOVE zone
        """
        high, low, close = candle['High'], candle['Low'], candle['Close']

        # Check if touched
        if high < self.bottom or low > self.top:
            return False

        # Mark as entered
        if not self.entered:
            self.entered = True

        # Track highs/lows for SL calculation
        if high >= self.bottom:
            self.highs_inside.append(high)
        if low <= self.top:
            self.lows_inside.append(low)

        # Check rejection
        if self.type == FVGType.BULLISH:
            # Rejection = close below zone
            if self.entered and close < self.bottom and not self.rejected:
                self.rejected = True
                self.action_time = candle.name
                self.action_price = close
                self.action_available_time = candle_close_time
                return True
        else:
            # Rejection = close above zone
            if self.entered and close > self.top and not self.rejected:
                self.rejected = True
                self.action_time = candle.name
                self.action_price = close
                self.action_available_time = candle_close_time
                return True

        return False

    def check_held_fvg(self, candle: pd.Series,
                      candle_close_time: pd.Timestamp) -> bool:
        """
        Check for HELD FVG (continuation)

        BULLISH FVG held: price entered and closed INSIDE zone (held support)
        BEARISH FVG held: price entered and closed INSIDE zone (held resistance)
        """
        high, low, close = candle['High'], candle['Low'], candle['Close']

        # Check if touched
        if high < self.bottom or low > self.top:
            return False

        # Mark as entered
        if not self.entered:
            self.entered = True

        # Track highs/lows for SL calculation
        if high >= self.bottom:
            self.highs_inside.append(high)
        if low <= self.top:
            self.lows_inside.append(low)

        # Check hold (close inside zone)
        if self.entered and self.is_inside(close) and not self.held:
            self.held = True
            self.action_time = candle.name
            self.action_price = close
            self.action_available_time = candle_close_time
            return True

        return False

    def get_stop_loss_failed(self) -> Optional[float]:
        """
        Get SL for FAILED FVG strategy

        BULLISH rejection → SHORT → SL above highest high inside
        BEARISH rejection → LONG → SL below lowest low inside
        """
        if self.type == FVGType.BULLISH:
            if self.highs_inside:
                return max(self.highs_inside) * 1.002
            return self.top * 1.002
        else:
            if self.lows_inside:
                return min(self.lows_inside) * 0.998
            return self.bottom * 0.998

    def get_stop_loss_held(self) -> Optional[float]:
        """
        Get SL for HELD FVG strategy

        BULLISH hold → LONG → SL below lowest low inside
        BEARISH hold → SHORT → SL above highest high inside
        """
        if self.type == FVGType.BULLISH:
            if self.lows_inside:
                return min(self.lows_inside) * 0.998
            return self.bottom * 0.998
        else:
            if self.highs_inside:
                return max(self.highs_inside) * 1.002
            return self.top * 1.002


@dataclass
class Trade:
    """Trade data structure"""
    trade_id: int
    direction: Direction
    entry: float
    sl: float
    tp: float
    size: float
    entry_time: pd.Timestamp
    entry_method: str
    tp_method: str
    strategy: str  # 'failed' or 'held'

    exit_price: Optional[float] = None
    exit_time: Optional[pd.Timestamp] = None
    exit_reason: Optional[ExitReason] = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    fees: float = 0.0
    active: bool = True

    def calculate_rr(self) -> float:
        """Calculate risk/reward ratio"""
        risk = abs(self.entry - self.sl)
        reward = abs(self.tp - self.entry)
        return reward / risk if risk > 0 else 0

    def calculate_sl_pct(self) -> float:
        """Calculate SL distance as percentage"""
        return abs(self.entry - self.sl) / self.entry * 100

    def close_trade(self, exit_price: float, exit_time: pd.Timestamp,
                   reason: ExitReason, enable_fees: bool = True,
                   maker_fee: float = 0.00018, taker_fee: float = 0.00045,
                   entry_method: str = 'limit'):
        """Close trade and calculate PnL"""
        self.active = False
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.exit_reason = reason

        # Calculate gross PnL
        if self.direction == Direction.LONG:
            gross_pnl = (exit_price - self.entry) * self.size
        else:
            gross_pnl = (self.entry - exit_price) * self.size

        # Calculate fees
        if enable_fees:
            # Entry fee
            if entry_method == '4h_close':
                entry_fee = self.entry * self.size * taker_fee  # Market order
            else:
                entry_fee = self.entry * self.size * maker_fee  # Limit order

            # Exit fee
            if reason == ExitReason.TP:
                exit_fee = exit_price * self.size * maker_fee
            else:
                exit_fee = exit_price * self.size * taker_fee

            self.fees = entry_fee + exit_fee
            net_pnl = gross_pnl - self.fees
        else:
            net_pnl = gross_pnl

        self.pnl = net_pnl
        self.pnl_pct = (net_pnl / (self.entry * self.size)) * 100

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'trade_id': self.trade_id,
            'strategy': self.strategy,
            'direction': self.direction.value,
            'entry_method': self.entry_method,
            'tp_method': self.tp_method,
            'entry': round(self.entry, 2),
            'sl': round(self.sl, 2),
            'tp': round(self.tp, 2),
            'size': round(self.size, 6),
            'rr': round(self.calculate_rr(), 2),
            'sl_pct': round(self.calculate_sl_pct(), 2),
            'entry_time': str(self.entry_time),
            'exit_time': str(self.exit_time) if self.exit_time else None,
            'exit_price': round(self.exit_price, 2) if self.exit_price else None,
            'exit_reason': self.exit_reason.value if self.exit_reason else None,
            'pnl': round(self.pnl, 2),
            'pnl_pct': round(self.pnl_pct, 2),
            'fees': round(self.fees, 2)
        }


class FVGBacktester:
    """
    Main backtesting engine with strict timing controls
    """

    def __init__(self,
                 initial_balance: float = 10000.0,
                 risk_per_trade: float = 0.02,
                 min_rr: float = 2.0,
                 min_sl_pct: float = 0.3,
                 max_sl_pct: float = 5.0,
                 enable_fees: bool = True,
                 limit_expiry_candles: int = 16):

        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.risk_per_trade = risk_per_trade
        self.min_rr = min_rr
        self.min_sl_pct = min_sl_pct
        self.max_sl_pct = max_sl_pct
        self.enable_fees = enable_fees
        self.limit_expiry_candles = limit_expiry_candles

        # Fee structure (Binance fees)
        self.maker_fee = 0.00018  # 0.018%
        self.taker_fee = 0.00045  # 0.045%

        # FVG tracking
        self.active_4h_fvgs: List[FVG] = []
        self.actionable_4h_fvgs: List[FVG] = []  # Rejected or held

        # Trade tracking
        self.trades: List[Trade] = []
        self.trade_counter = 0
        self.active_trade: Optional[Trade] = None

    def detect_fvg(self, df: pd.DataFrame, start_idx: int, end_idx: int,
                   timeframe: str) -> List[FVG]:
        """
        Detect Fair Value Gaps

        CRITICAL: Only detect FVGs from CLOSED candles
        - Candle at index i has close_time = df.index[i+1] (next candle open)
        """
        fvgs = []

        for i in range(start_idx + 2, end_idx):
            if i >= len(df):
                break

            candle = df.iloc[i]
            candle_prev2 = df.iloc[i-2]

            # Calculate when this FVG information becomes available
            # FVG forms at candle i, available when candle i closes
            # Candle i close time = candle i+1 open time (if exists)
            if i + 1 < len(df):
                formed_time = df.index[i + 1]
            else:
                # Last candle - use current time + timeframe duration
                if timeframe == '4h':
                    formed_time = df.index[i] + timedelta(hours=4)
                else:
                    formed_time = df.index[i] + timedelta(minutes=15)

            # Bullish FVG
            if candle['Low'] > candle_prev2['High']:
                fvg = FVG(
                    type=FVGType.BULLISH,
                    top=candle['Low'],
                    bottom=candle_prev2['High'],
                    formed_time=formed_time,
                    timeframe=timeframe
                )
                fvgs.append(fvg)

            # Bearish FVG
            elif candle['High'] < candle_prev2['Low']:
                fvg = FVG(
                    type=FVGType.BEARISH,
                    top=candle_prev2['Low'],
                    bottom=candle['High'],
                    formed_time=formed_time,
                    timeframe=timeframe
                )
                fvgs.append(fvg)

        return fvgs

    def update_4h_fvgs(self, df_4h: pd.DataFrame, current_idx: int,
                      strategy: str = 'failed') -> Tuple[int, int]:
        """
        Update 4H FVGs - detect new ones and check for rejection/hold

        Args:
            df_4h: 4H dataframe
            current_idx: Current 4H candle index (this candle is CLOSED)
            strategy: 'failed' or 'held'

        Returns:
            (newly_added, newly_actionable)
        """
        newly_added = 0
        newly_actionable = 0

        # Detect new FVGs
        lookback = min(10, current_idx)
        start_idx = max(0, current_idx - lookback)
        new_fvgs = self.detect_fvg(df_4h, start_idx, current_idx + 1, '4h')

        # Add unique FVGs
        for fvg in new_fvgs:
            # Only add if not already tracked
            if not any(existing.formed_time == fvg.formed_time and
                      existing.type == fvg.type and
                      abs(existing.top - fvg.top) < 0.01
                      for existing in self.active_4h_fvgs):
                self.active_4h_fvgs.append(fvg)
                newly_added += 1

        # Check active FVGs for rejection/hold
        current_candle = df_4h.iloc[current_idx]

        # Calculate when current candle closes
        if current_idx + 1 < len(df_4h):
            candle_close_time = df_4h.index[current_idx + 1]
        else:
            candle_close_time = df_4h.index[current_idx] + timedelta(hours=4)

        for fvg in self.active_4h_fvgs[:]:
            # Check rejection/hold based on strategy
            if strategy == 'failed':
                if fvg.check_failed_fvg_rejection(current_candle, candle_close_time):
                    self.actionable_4h_fvgs.append(fvg)
                    newly_actionable += 1
            else:  # held
                if fvg.check_held_fvg(current_candle, candle_close_time):
                    self.actionable_4h_fvgs.append(fvg)
                    newly_actionable += 1

            # Check invalidation
            if fvg.is_fully_passed(current_candle['High'], current_candle['Low']):
                fvg.invalidated = True
                self.active_4h_fvgs.remove(fvg)

        # Clean up actionable FVGs (remove invalidated)
        self.actionable_4h_fvgs = [
            fvg for fvg in self.actionable_4h_fvgs
            if not fvg.invalidated
        ]

        return newly_added, newly_actionable

    def find_liquidity(self, df: pd.DataFrame, current_idx: int,
                      direction: Direction, lookback: int = 50) -> Optional[float]:
        """Find liquidity zones (swing highs/lows) for TP"""
        start_idx = max(0, current_idx - lookback)

        if direction == Direction.LONG:
            # Find swing high (resistance)
            for i in range(current_idx - 1, start_idx, -1):
                if i < 2:
                    continue

                candle = df.iloc[i]
                is_swing = True

                # Check surrounding candles (only look backward!)
                for j in range(max(0, i-2), min(len(df), i+1)):
                    if j != i and df.iloc[j]['High'] > candle['High']:
                        is_swing = False
                        break

                if is_swing:
                    return candle['High']

        else:  # SHORT
            # Find swing low (support)
            for i in range(current_idx - 1, start_idx, -1):
                if i < 2:
                    continue

                candle = df.iloc[i]
                is_swing = True

                # Check surrounding candles (only look backward!)
                for j in range(max(0, i-2), min(len(df), i+1)):
                    if j != i and df.iloc[j]['Low'] < candle['Low']:
                        is_swing = False
                        break

                if is_swing:
                    return candle['Low']

        return None

    def calculate_tp(self, entry: float, sl: float, direction: Direction,
                    tp_method: str, df_15m: pd.DataFrame, current_idx: int) -> Optional[float]:
        """Calculate TP based on method"""
        risk = abs(entry - sl)

        if tp_method == 'liquidity':
            tp = self.find_liquidity(df_15m, current_idx, direction, lookback=50)

            if tp:
                # Validate RR
                rr = abs(tp - entry) / risk
                if rr < 1.5:
                    return None
                if rr > 10.0:
                    # Cap at 10RR
                    if direction == Direction.LONG:
                        tp = entry + risk * 10.0
                    else:
                        tp = entry - risk * 10.0

            return tp

        elif tp_method == 'rr_2.0':
            if direction == Direction.LONG:
                return entry + risk * 2.0
            else:
                return entry - risk * 2.0

        elif tp_method == 'rr_3.0':
            if direction == Direction.LONG:
                return entry + risk * 3.0
            else:
                return entry - risk * 3.0

        return None

    def create_setup(self, fvg: FVG, df_15m: pd.DataFrame, current_idx: int,
                    entry_method: str, tp_method: str, strategy: str,
                    current_price: float) -> Optional[Dict]:
        """
        Create trading setup

        Args:
            fvg: Actionable 4H FVG
            df_15m: 15M dataframe
            current_idx: Current 15M candle index
            entry_method: Entry method
            tp_method: TP method
            strategy: 'failed' or 'held'
            current_price: Current price

        Returns:
            Setup dict or None if invalid
        """
        # Determine direction
        if strategy == 'failed':
            # FAILED: Bullish rejection → SHORT, Bearish rejection → LONG
            direction = Direction.SHORT if fvg.type == FVGType.BULLISH else Direction.LONG
            sl = fvg.get_stop_loss_failed()
        else:
            # HELD: Bullish hold → LONG, Bearish hold → SHORT
            direction = Direction.LONG if fvg.type == FVGType.BULLISH else Direction.SHORT
            sl = fvg.get_stop_loss_held()

        if not sl:
            return None

        # Calculate entry based on method
        if entry_method == '4h_close':
            entry = fvg.action_price

        elif entry_method == '15m_fvg':
            # Look for 15M FVG
            lookback_start = max(0, current_idx - 10)
            fvgs_15m = self.detect_fvg(df_15m, lookback_start, current_idx + 1, '15m')

            if not fvgs_15m:
                return None

            # Find matching FVG type
            if strategy == 'failed':
                # FAILED: opposite FVG type
                expected_type = FVGType.BEARISH if fvg.type == FVGType.BULLISH else FVGType.BULLISH
            else:
                # HELD: same FVG type
                expected_type = fvg.type

            matching = [f for f in fvgs_15m if f.type == expected_type]
            if not matching:
                return None

            fvg_15m = matching[-1]

            # Entry at FVG edge
            if direction == Direction.LONG:
                entry = fvg_15m.bottom
            else:
                entry = fvg_15m.top

        elif entry_method == '15m_breakout':
            # Entry at breakout level
            if direction == Direction.LONG:
                entry = fvg.action_price * 1.001
            else:
                entry = fvg.action_price * 0.999

        else:
            return None

        # Validate SL distance
        sl_pct = abs(entry - sl) / entry * 100
        if sl_pct < self.min_sl_pct or sl_pct > self.max_sl_pct:
            return None

        # Calculate TP
        tp = self.calculate_tp(entry, sl, direction, tp_method, df_15m, current_idx)
        if not tp:
            return None

        # Validate RR
        rr = abs(tp - entry) / abs(entry - sl)
        if rr < self.min_rr:
            return None

        # Calculate position size
        risk_amount = self.balance * self.risk_per_trade
        size = risk_amount / abs(entry - sl)
        size = round(size, 3)

        # Validate notional
        if entry * size < 10.0:
            return None

        return {
            'direction': direction,
            'entry': entry,
            'sl': sl,
            'tp': tp,
            'size': size,
            'entry_method': entry_method,
            'tp_method': tp_method,
            'strategy': strategy
        }

    def simulate_trade(self, setup: Dict, df_15m: pd.DataFrame,
                      entry_idx: int, fvg: FVG) -> Trade:
        """
        Simulate trade execution

        CRITICAL: Verify no lookahead bias!
        """
        entry_time = df_15m.index[entry_idx]

        # CRITICAL CHECK: Cannot trade before action info is available!
        if fvg.action_available_time and entry_time < fvg.action_available_time:
            raise ValueError(
                f"LOOKAHEAD BIAS DETECTED!\n"
                f"Trying to trade at {entry_time}\n"
                f"But info only available at {fvg.action_available_time}"
            )

        self.trade_counter += 1

        trade = Trade(
            trade_id=self.trade_counter,
            direction=setup['direction'],
            entry=setup['entry'],
            sl=setup['sl'],
            tp=setup['tp'],
            size=setup['size'],
            entry_time=entry_time,
            entry_method=setup['entry_method'],
            tp_method=setup['tp_method'],
            strategy=setup['strategy']
        )

        # Handle entry fill
        if setup['entry_method'] == '4h_close':
            # Immediate market entry
            start_idx = entry_idx
        else:
            # Limit order - check if filled
            filled = False
            fill_idx = entry_idx

            for i in range(entry_idx, min(entry_idx + self.limit_expiry_candles, len(df_15m))):
                candle = df_15m.iloc[i]

                if setup['direction'] == Direction.LONG:
                    if candle['Low'] <= setup['entry']:
                        filled = True
                        fill_idx = i
                        trade.entry_time = candle.name
                        break
                else:
                    if candle['High'] >= setup['entry']:
                        filled = True
                        fill_idx = i
                        trade.entry_time = candle.name
                        break

            if not filled:
                trade.close_trade(
                    setup['entry'],
                    df_15m.index[min(entry_idx + self.limit_expiry_candles - 1, len(df_15m) - 1)],
                    ExitReason.EXPIRED,
                    enable_fees=False
                )
                return trade

            start_idx = fill_idx + 1

        # Simulate until TP/SL/timeout
        max_candles = 500

        for i in range(start_idx, min(start_idx + max_candles, len(df_15m))):
            candle = df_15m.iloc[i]

            if trade.direction == Direction.LONG:
                if candle['Low'] <= trade.sl:
                    trade.close_trade(trade.sl, candle.name, ExitReason.SL,
                                    self.enable_fees, self.maker_fee, self.taker_fee,
                                    setup['entry_method'])
                    break
                if candle['High'] >= trade.tp:
                    trade.close_trade(trade.tp, candle.name, ExitReason.TP,
                                    self.enable_fees, self.maker_fee, self.taker_fee,
                                    setup['entry_method'])
                    break
            else:
                if candle['High'] >= trade.sl:
                    trade.close_trade(trade.sl, candle.name, ExitReason.SL,
                                    self.enable_fees, self.maker_fee, self.taker_fee,
                                    setup['entry_method'])
                    break
                if candle['Low'] <= trade.tp:
                    trade.close_trade(trade.tp, candle.name, ExitReason.TP,
                                    self.enable_fees, self.maker_fee, self.taker_fee,
                                    setup['entry_method'])
                    break

        # Timeout
        if trade.active:
            last_idx = min(start_idx + max_candles - 1, len(df_15m) - 1)
            last_candle = df_15m.iloc[last_idx]
            trade.close_trade(last_candle['Close'], last_candle.name,
                            ExitReason.TIMEOUT, self.enable_fees,
                            self.maker_fee, self.taker_fee, setup['entry_method'])

        return trade

    def run_backtest(self, df_4h: pd.DataFrame, df_15m: pd.DataFrame,
                    start_date: str, end_date: str,
                    entry_method: str, tp_method: str, strategy: str) -> Dict:
        """
        Run single backtest configuration

        Args:
            df_4h: 4H data
            df_15m: 15M data
            start_date: Start date
            end_date: End date
            entry_method: Entry method
            tp_method: TP method
            strategy: 'failed' or 'held'
        """
        # Reset state
        self.balance = self.initial_balance
        self.active_4h_fvgs = []
        self.actionable_4h_fvgs = []
        self.trades = []
        self.trade_counter = 0
        self.active_trade = None

        # Filter data
        df_4h_filt = df_4h.loc[start_date:end_date].copy()
        df_15m_filt = df_15m.loc[start_date:end_date].copy()

        # Statistics
        stats = {
            'total_4h_fvgs': 0,
            'total_actionable': 0,
            'setups_created': 0,
            'fills': 0,
            'no_fills': 0
        }

        current_15m_idx = 0

        # Iterate through 4H candles (exclude last - may be unclosed)
        for i in range(len(df_4h_filt) - 1):
            # Update 4H FVGs
            newly_added, newly_actionable = self.update_4h_fvgs(df_4h_filt, i, strategy)
            stats['total_4h_fvgs'] += newly_added
            stats['total_actionable'] += newly_actionable

            # Find next 4H candle time
            next_4h_time = df_4h_filt.index[i + 1]

            # Process 15M candles in this 4H period
            while current_15m_idx < len(df_15m_filt) and df_15m_filt.index[current_15m_idx] < next_4h_time:

                if not self.active_trade:
                    current_time = df_15m_filt.index[current_15m_idx]
                    current_candle = df_15m_filt.iloc[current_15m_idx]
                    current_price = current_candle['Close']

                    for fvg in self.actionable_4h_fvgs[:]:
                        # Skip if already traded
                        if fvg.has_filled_trade:
                            continue

                        # CRITICAL: Skip if action info not yet available!
                        if fvg.action_available_time and current_time < fvg.action_available_time:
                            continue

                        # Check invalidation
                        if fvg.is_fully_passed(current_candle['High'], current_candle['Low']):
                            fvg.invalidated = True
                            self.actionable_4h_fvgs.remove(fvg)
                            continue

                        # Check setup expiry cooldown
                        if fvg.pending_setup_expiry_time:
                            if current_time < fvg.pending_setup_expiry_time:
                                continue

                        # Create setup
                        setup = self.create_setup(fvg, df_15m_filt, current_15m_idx,
                                                 entry_method, tp_method, strategy,
                                                 current_price)

                        if setup:
                            stats['setups_created'] += 1

                            # Set expiry cooldown
                            expiry_idx = min(current_15m_idx + self.limit_expiry_candles,
                                           len(df_15m_filt) - 1)
                            fvg.pending_setup_expiry_time = df_15m_filt.index[expiry_idx]

                            # Simulate trade
                            trade = self.simulate_trade(setup, df_15m_filt, current_15m_idx, fvg)

                            if trade.exit_reason != ExitReason.EXPIRED:
                                stats['fills'] += 1
                                fvg.has_filled_trade = True
                                self.trades.append(trade)
                                self.balance += trade.pnl

                                # Jump to after trade closes
                                try:
                                    close_idx = df_15m_filt.index.get_loc(trade.exit_time)
                                    current_15m_idx = close_idx
                                except KeyError:
                                    pass

                                break
                            else:
                                stats['no_fills'] += 1

                current_15m_idx += 1

        # Calculate results
        results = self.calculate_results(entry_method, tp_method, strategy, stats)
        return results

    def calculate_results(self, entry_method: str, tp_method: str,
                         strategy: str, stats: Dict) -> Dict:
        """Calculate backtest metrics"""

        if not self.trades:
            return {
                'strategy': strategy,
                'entry_method': entry_method,
                'tp_method': tp_method,
                'total_trades': 0,
                'stats': stats,
                'trades': []
            }

        winning = [t for t in self.trades if t.pnl > 0]
        losing = [t for t in self.trades if t.pnl <= 0]

        total_pnl = sum(t.pnl for t in self.trades)

        # Balance curve for drawdown
        curve = [self.initial_balance]
        for t in self.trades:
            curve.append(curve[-1] + t.pnl)

        peak = curve[0]
        max_dd = 0
        for val in curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak * 100 if peak > 0 else 0
            max_dd = max(max_dd, dd)

        # Profit factor
        total_wins = sum(t.pnl for t in winning)
        total_losses = abs(sum(t.pnl for t in losing))
        pf = total_wins / total_losses if total_losses > 0 else float('inf')

        return {
            'strategy': strategy,
            'entry_method': entry_method,
            'tp_method': tp_method,
            'total_trades': len(self.trades),
            'winning_trades': len(winning),
            'losing_trades': len(losing),
            'win_rate': len(winning) / len(self.trades) * 100,
            'total_pnl': round(total_pnl, 2),
            'total_pnl_pct': round(total_pnl / self.initial_balance * 100, 2),
            'final_balance': round(self.initial_balance + total_pnl, 2),
            'avg_win': round(sum(t.pnl for t in winning) / len(winning), 2) if winning else 0,
            'avg_loss': round(sum(t.pnl for t in losing) / len(losing), 2) if losing else 0,
            'max_drawdown': round(max_dd, 2),
            'profit_factor': round(pf, 2) if pf != float('inf') else pf,
            'avg_rr': round(np.mean([t.calculate_rr() for t in self.trades]), 2),
            'stats': stats,
            'trades': [t.to_dict() for t in self.trades]
        }
