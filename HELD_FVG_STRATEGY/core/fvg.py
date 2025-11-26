"""
FVG Class for HELD Strategy
Shared logic between backtest and live bot
"""

from datetime import datetime
from typing import List, Optional


class HeldFVG:
    """Fair Value Gap for HELD strategy"""

    def __init__(self, fvg_type: str, top: float, bottom: float,
                 formed_time: datetime, timeframe: str = '4h'):
        self.type = fvg_type  # 'BULLISH' or 'BEARISH'
        self.top = top
        self.bottom = bottom
        self.formed_time = formed_time
        self.timeframe = timeframe

        # State tracking
        self.entered = False
        self.held = False
        self.invalidated = False

        self.hold_time: Optional[datetime] = None
        self.hold_price: Optional[float] = None

        # Track highs/lows inside for SL calculation
        self.highs_inside: List[float] = []
        self.lows_inside: List[float] = []

        # Trade tracking
        self.has_filled_trade = False
        self.pending_setup_expiry_time: Optional[datetime] = None

        # Unique ID
        self.id = f"{timeframe}_{fvg_type}_{top:.2f}_{bottom:.2f}_{int(formed_time.timestamp())}"

    def is_inside(self, price: float) -> bool:
        """Check if price is inside FVG zone"""
        return self.bottom <= price <= self.top

    def is_fully_passed(self, candle_high: float, candle_low: float) -> bool:
        """
        Check if FVG is invalidated (price went opposite direction)

        Bullish FVG invalidated: price went BELOW bottom
        Bearish FVG invalidated: price went ABOVE top
        """
        if self.type == 'BULLISH':
            return candle_low < self.bottom
        else:  # BEARISH
            return candle_high > self.top

    def check_hold(self, candle_high: float, candle_low: float,
                   candle_close: float, candle_time: datetime,
                   debug: bool = False) -> bool:
        """
        Check if FVG is HELD

        HELD = price entered zone and closed INSIDE zone
        (zone held price, didn't let it break through)

        Returns True if newly held on this candle
        """
        # Check if touched
        touched = not (candle_high < self.bottom or candle_low > self.top)

        if not touched:
            return False

        # Mark as entered
        if not self.entered:
            self.entered = True
            if debug:
                print(f"  ✅ {self.timeframe} {self.type} FVG entered: "
                      f"${self.bottom:.2f}-${self.top:.2f}, Close: ${candle_close:.2f}")

        # Track highs/lows inside for SL calculation
        if candle_high >= self.bottom:
            self.highs_inside.append(candle_high)
        if candle_low <= self.top:
            self.lows_inside.append(candle_low)

        # Check if HELD (close inside zone)
        if self.entered and self.bottom <= candle_close <= self.top:
            if not self.held:
                self.held = True
                self.hold_time = candle_time
                self.hold_price = candle_close
                if debug:
                    print(f"  💚 {self.type} FVG HELD! Close ${candle_close:.2f} "
                          f"inside zone ${self.bottom:.2f}-${self.top:.2f}")
                return True

        return False

    def get_stop_loss(self) -> Optional[float]:
        """
        Get stop loss for HELD strategy

        BULLISH FVG held → LONG → SL below zone
        BEARISH FVG held → SHORT → SL above zone
        """
        if self.type == 'BULLISH':
            # LONG setup: SL = lowest low inside zone
            if self.lows_inside:
                return min(self.lows_inside) * 0.998  # -0.2% buffer
            else:
                return self.bottom * 0.998
        else:  # BEARISH
            # SHORT setup: SL = highest high inside zone
            if self.highs_inside:
                return max(self.highs_inside) * 1.002  # +0.2% buffer
            else:
                return self.top * 1.002

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/storage"""
        return {
            'id': self.id,
            'type': self.type,
            'top': self.top,
            'bottom': self.bottom,
            'formed_time': str(self.formed_time),
            'entered': self.entered,
            'held': self.held,
            'invalidated': self.invalidated,
            'hold_time': str(self.hold_time) if self.hold_time else None,
            'hold_price': self.hold_price,
            'has_filled_trade': self.has_filled_trade
        }
