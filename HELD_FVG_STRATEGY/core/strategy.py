"""
HELD FVG Strategy Logic
Shared between backtest, simulation, and live trading
"""

from typing import List, Optional, Tuple
from datetime import datetime
import pandas as pd
from .fvg import HeldFVG


class HeldFVGStrategy:
    """Core strategy logic for HELD FVG"""

    def __init__(self, min_sl_pct: float = 0.3, max_sl_pct: float = 5.0):
        self.min_sl_pct = min_sl_pct
        self.max_sl_pct = max_sl_pct

        # FVG tracking
        self.active_4h_fvgs: List[HeldFVG] = []
        self.held_4h_fvgs: List[HeldFVG] = []

    def detect_fvg_from_candles(self, candle_1: dict, candle_2: dict,
                                 candle_3: dict, candle_3_time: datetime) -> Optional[HeldFVG]:
        """
        Detect FVG from 3 candles

        FVG = gap between candle 1 and candle 3 (candle 2 in middle)
        """
        # Bullish FVG: candle_3 Low > candle_1 High
        if candle_3['low'] > candle_1['high']:
            return HeldFVG(
                fvg_type='BULLISH',
                top=candle_3['low'],
                bottom=candle_1['high'],
                formed_time=candle_3_time,
                timeframe='4h'
            )

        # Bearish FVG: candle_3 High < candle_1 Low
        elif candle_3['high'] < candle_1['low']:
            return HeldFVG(
                fvg_type='BEARISH',
                top=candle_1['low'],
                bottom=candle_3['high'],
                formed_time=candle_3_time,
                timeframe='4h'
            )

        return None

    def update_fvgs(self, current_candle: dict, candle_time: datetime,
                    debug: bool = False) -> Tuple[List[HeldFVG], List[HeldFVG]]:
        """
        Update FVG states based on current candle

        Returns: (newly_held_fvgs, invalidated_fvgs)
        """
        newly_held = []
        invalidated = []

        candle_high = current_candle['high']
        candle_low = current_candle['low']
        candle_close = current_candle['close']

        # Check active FVGs
        for fvg in self.active_4h_fvgs[:]:
            # Check if held
            if fvg.check_hold(candle_high, candle_low, candle_close, candle_time, debug=debug):
                self.held_4h_fvgs.append(fvg)
                self.active_4h_fvgs.remove(fvg)
                newly_held.append(fvg)

            # Check invalidation
            elif fvg.is_fully_passed(candle_high, candle_low):
                fvg.invalidated = True
                self.active_4h_fvgs.remove(fvg)
                invalidated.append(fvg)

        # Check held FVGs for invalidation
        for fvg in self.held_4h_fvgs[:]:
            if fvg.is_fully_passed(candle_high, candle_low):
                fvg.invalidated = True
                self.held_4h_fvgs.remove(fvg)
                invalidated.append(fvg)

        return newly_held, invalidated

    def create_setup(self, held_fvg: HeldFVG, current_price: float,
                     fixed_rr: float = 2.0) -> Optional[dict]:
        """
        Create trade setup from held FVG

        Strategy: 4h_close + rr_2.0
        - Entry: immediate at hold_price (4H close)
        - SL: from FVG
        - TP: fixed RR 2.0
        """
        # Determine direction
        direction = 'LONG' if held_fvg.type == 'BULLISH' else 'SHORT'

        # Entry price = hold price (4H close where it held)
        entry = held_fvg.hold_price

        # Stop loss
        sl = held_fvg.get_stop_loss()
        if sl is None:
            return None

        # Validate SL distance
        sl_distance_pct = abs(entry - sl) / entry * 100
        if sl_distance_pct < self.min_sl_pct or sl_distance_pct > self.max_sl_pct:
            return None

        # Calculate TP with fixed RR
        risk = abs(entry - sl)
        if direction == 'LONG':
            tp = entry + risk * fixed_rr
        else:  # SHORT
            tp = entry - risk * fixed_rr

        # Validate entry price distance from current price
        entry_distance_pct = abs(entry - current_price) / current_price * 100
        if entry_distance_pct > 5.0:
            return None

        return {
            'direction': direction,
            'entry': entry,
            'sl': sl,
            'tp': tp,
            'fvg_id': held_fvg.id
        }

    def calculate_position_size(self, balance: float, risk_per_trade: float,
                                entry: float, sl: float) -> float:
        """Calculate position size based on risk"""
        risk_amount = balance * risk_per_trade
        risk_per_unit = abs(entry - sl)
        size = risk_amount / risk_per_unit
        return size

    def reset(self):
        """Reset strategy state"""
        self.active_4h_fvgs.clear()
        self.held_4h_fvgs.clear()
