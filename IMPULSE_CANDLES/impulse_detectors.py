"""
Impulse Candle Detection - 7 різних концепцій
"""
import pandas as pd
import numpy as np


class ImpulseDetector:
    """Base class for impulse candle detection"""

    def __init__(self, name):
        self.name = name

    def detect(self, df, idx):
        """
        Detect if candle at index is impulse candle
        Returns: (is_impulse, direction, strength)
        direction: 1 for bullish, -1 for bearish, 0 for none
        strength: float value indicating impulse strength
        """
        raise NotImplementedError


class ATRBasedDetector(ImpulseDetector):
    """Концепція 1: ATR-Based Detection"""

    def __init__(self, atr_multiplier=2.0, body_ratio_threshold=0.75, atr_period=14):
        super().__init__(f"ATR_{atr_multiplier}x_body{int(body_ratio_threshold*100)}%")
        self.atr_multiplier = atr_multiplier
        self.body_ratio_threshold = body_ratio_threshold
        self.atr_period = atr_period

    def detect(self, df, idx):
        if idx < self.atr_period:
            return False, 0, 0.0

        candle = df.iloc[idx]

        # Calculate body and ratios
        body = abs(candle['Close'] - candle['Open'])
        total_range = candle['High'] - candle['Low']

        if total_range == 0:
            return False, 0, 0.0

        body_ratio = body / total_range

        # Calculate ATR
        atr = df['atr'].iloc[idx] if 'atr' in df.columns else self._calculate_atr(df, idx)

        # Check conditions
        is_impulse = (body > self.atr_multiplier * atr) and (body_ratio > self.body_ratio_threshold)

        if not is_impulse:
            return False, 0, 0.0

        # Determine direction
        direction = 1 if candle['Close'] > candle['Open'] else -1
        strength = body / atr  # How many ATRs is the body

        return True, direction, strength

    def _calculate_atr(self, df, idx):
        """Calculate ATR for given index"""
        if idx < self.atr_period:
            return 0

        high = df['High'].iloc[idx - self.atr_period + 1:idx + 1]
        low = df['Low'].iloc[idx - self.atr_period + 1:idx + 1]
        close = df['Close'].iloc[idx - self.atr_period:idx]

        tr1 = high - low
        tr2 = abs(high - close.values)
        tr3 = abs(low - close.values)

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.mean()

        return atr


class VolumeBasedDetector(ImpulseDetector):
    """Концепція 2: Volume-Based Detection"""

    def __init__(self, volume_multiplier=1.5, avg_period=20):
        super().__init__(f"Volume_{volume_multiplier}x_avg{avg_period}")
        self.volume_multiplier = volume_multiplier
        self.avg_period = avg_period

    def detect(self, df, idx):
        if idx < self.avg_period:
            return False, 0, 0.0

        candle = df.iloc[idx]

        # Calculate average volume
        avg_volume = df['Volume'].iloc[idx - self.avg_period:idx].mean()

        if avg_volume == 0:
            return False, 0, 0.0

        volume_ratio = candle['Volume'] / avg_volume

        # Check if volume is above threshold
        is_impulse = volume_ratio > self.volume_multiplier

        if not is_impulse:
            return False, 0, 0.0

        # Determine direction based on candle color
        direction = 1 if candle['Close'] > candle['Open'] else -1
        strength = volume_ratio

        return True, direction, strength


class EngulfingDetector(ImpulseDetector):
    """Концепція 3: Engulfing Pattern Detection"""

    def __init__(self, require_volume_confirmation=False, volume_multiplier=1.5):
        name = "Engulfing"
        if require_volume_confirmation:
            name += f"_Vol{volume_multiplier}x"
        super().__init__(name)
        self.require_volume_confirmation = require_volume_confirmation
        self.volume_multiplier = volume_multiplier

    def detect(self, df, idx):
        if idx < 1:
            return False, 0, 0.0

        curr = df.iloc[idx]
        prev = df.iloc[idx - 1]

        # Bullish engulfing
        bullish_engulfing = (
            (curr['Close'] > prev['High']) and
            (curr['Open'] <= prev['Low'])
        )

        # Bearish engulfing
        bearish_engulfing = (
            (curr['Close'] < prev['Low']) and
            (curr['Open'] >= prev['High'])
        )

        is_impulse = bullish_engulfing or bearish_engulfing

        # Volume confirmation if required
        if is_impulse and self.require_volume_confirmation:
            if idx < 20:
                return False, 0, 0.0
            avg_volume = df['Volume'].iloc[idx - 20:idx].mean()
            if avg_volume > 0:
                volume_ratio = curr['Volume'] / avg_volume
                if volume_ratio < self.volume_multiplier:
                    return False, 0, 0.0
            else:
                return False, 0, 0.0

        if not is_impulse:
            return False, 0, 0.0

        direction = 1 if bullish_engulfing else -1
        body = abs(curr['Close'] - curr['Open'])
        prev_range = prev['High'] - prev['Low']
        strength = body / prev_range if prev_range > 0 else 1.0

        return True, direction, strength


class RangeExpansionDetector(ImpulseDetector):
    """Концепція 4: Range Expansion Detection"""

    def __init__(self, range_multiplier=2.0, avg_period=20):
        super().__init__(f"RangeExp_{range_multiplier}x_avg{avg_period}")
        self.range_multiplier = range_multiplier
        self.avg_period = avg_period

    def detect(self, df, idx):
        if idx < self.avg_period:
            return False, 0, 0.0

        candle = df.iloc[idx]

        # Calculate candle range
        candle_range = candle['High'] - candle['Low']

        # Calculate average range
        avg_range = (df['High'].iloc[idx - self.avg_period:idx] -
                     df['Low'].iloc[idx - self.avg_period:idx]).mean()

        if avg_range == 0:
            return False, 0, 0.0

        range_ratio = candle_range / avg_range

        # Check if range expansion occurred
        is_impulse = range_ratio > self.range_multiplier

        if not is_impulse:
            return False, 0, 0.0

        # Determine direction
        direction = 1 if candle['Close'] > candle['Open'] else -1
        strength = range_ratio

        return True, direction, strength


class PercentageMoveDetector(ImpulseDetector):
    """Концепція 5: Percentage Move Detection"""

    def __init__(self, body_pct_threshold=3.0):
        super().__init__(f"PctMove_{body_pct_threshold}%")
        self.body_pct_threshold = body_pct_threshold

    def detect(self, df, idx):
        candle = df.iloc[idx]

        if candle['Open'] == 0:
            return False, 0, 0.0

        # Calculate body percentage
        body = abs(candle['Close'] - candle['Open'])
        body_pct = (body / candle['Open']) * 100

        # Check if percentage move is above threshold
        is_impulse = body_pct > self.body_pct_threshold

        if not is_impulse:
            return False, 0, 0.0

        # Determine direction
        direction = 1 if candle['Close'] > candle['Open'] else -1
        strength = body_pct

        return True, direction, strength


class CombinedDetector(ImpulseDetector):
    """Концепція 6: Combined Multi-Criteria Detection"""

    def __init__(self, criteria_type="atr_volume"):
        """
        criteria_type options:
        - "atr_volume": (Body > 1.5x ATR) AND (Volume > 1.5x avg_vol)
        - "atr_body": (Body > 2.0x ATR) AND (Body ratio > 75%)
        - "volume_range": (Volume > 2.0x avg_vol) AND (Range > 1.5x avg_range)
        - "engulfing_volume": (Engulfing) AND (Volume > 1.5x avg_vol)
        """
        super().__init__(f"Combined_{criteria_type}")
        self.criteria_type = criteria_type

        # Initialize sub-detectors based on criteria type
        if criteria_type == "atr_volume":
            self.detector1 = ATRBasedDetector(atr_multiplier=1.5, body_ratio_threshold=0.7)
            self.detector2 = VolumeBasedDetector(volume_multiplier=1.5)
        elif criteria_type == "atr_body":
            self.detector1 = ATRBasedDetector(atr_multiplier=2.0, body_ratio_threshold=0.75)
            self.detector2 = None
        elif criteria_type == "volume_range":
            self.detector1 = VolumeBasedDetector(volume_multiplier=2.0)
            self.detector2 = RangeExpansionDetector(range_multiplier=1.5)
        elif criteria_type == "engulfing_volume":
            self.detector1 = EngulfingDetector(require_volume_confirmation=True, volume_multiplier=1.5)
            self.detector2 = None

    def detect(self, df, idx):
        if self.criteria_type == "atr_volume":
            is_imp1, dir1, str1 = self.detector1.detect(df, idx)
            is_imp2, dir2, str2 = self.detector2.detect(df, idx)
            is_impulse = is_imp1 and is_imp2 and (dir1 == dir2)
            direction = dir1 if is_impulse else 0
            strength = (str1 + str2) / 2

        elif self.criteria_type == "atr_body":
            is_impulse, direction, strength = self.detector1.detect(df, idx)

        elif self.criteria_type == "volume_range":
            is_imp1, dir1, str1 = self.detector1.detect(df, idx)
            is_imp2, dir2, str2 = self.detector2.detect(df, idx)
            is_impulse = is_imp1 and is_imp2 and (dir1 == dir2)
            direction = dir1 if is_impulse else 0
            strength = (str1 + str2) / 2

        elif self.criteria_type == "engulfing_volume":
            is_impulse, direction, strength = self.detector1.detect(df, idx)
        else:
            return False, 0, 0.0

        return is_impulse, direction, strength


class MomentumBasedDetector(ImpulseDetector):
    """Концепція 7: Momentum-Based Detection"""

    def __init__(self, momentum_threshold=0.8, wick_threshold=0.2):
        super().__init__(f"Momentum_{int(momentum_threshold*100)}%_wick{int(wick_threshold*100)}%")
        self.momentum_threshold = momentum_threshold
        self.wick_threshold = wick_threshold

    def detect(self, df, idx):
        candle = df.iloc[idx]

        total_range = candle['High'] - candle['Low']

        if total_range == 0:
            return False, 0, 0.0

        # Check for bullish momentum
        bullish_body = candle['Close'] - candle['Open']
        bullish_momentum = bullish_body > self.momentum_threshold * total_range
        small_upper_wick = (candle['High'] - candle['Close']) < self.wick_threshold * total_range

        is_bullish = bullish_momentum and small_upper_wick and (bullish_body > 0)

        # Check for bearish momentum
        bearish_body = candle['Open'] - candle['Close']
        bearish_momentum = bearish_body > self.momentum_threshold * total_range
        small_lower_wick = (candle['Close'] - candle['Low']) < self.wick_threshold * total_range

        is_bearish = bearish_momentum and small_lower_wick and (bearish_body > 0)

        is_impulse = is_bullish or is_bearish

        if not is_impulse:
            return False, 0, 0.0

        direction = 1 if is_bullish else -1
        body = abs(candle['Close'] - candle['Open'])
        strength = body / total_range

        return True, direction, strength


def get_all_detectors():
    """Get all detector configurations for testing"""
    detectors = []

    # 1. ATR-Based variations
    for atr_mult in [1.5, 2.0, 2.5]:
        for body_ratio in [0.70, 0.75, 0.80]:
            detectors.append(ATRBasedDetector(atr_mult, body_ratio))

    # 2. Volume-Based variations
    for vol_mult in [1.3, 1.5, 2.0, 2.5]:
        detectors.append(VolumeBasedDetector(vol_mult))

    # 3. Engulfing variations
    detectors.append(EngulfingDetector(require_volume_confirmation=False))
    detectors.append(EngulfingDetector(require_volume_confirmation=True, volume_multiplier=1.5))

    # 4. Range Expansion variations
    for range_mult in [1.5, 2.0, 2.5]:
        detectors.append(RangeExpansionDetector(range_mult))

    # 5. Percentage Move variations
    for pct in [2.0, 3.0, 4.0, 5.0]:
        detectors.append(PercentageMoveDetector(pct))

    # 6. Combined variations
    for criteria in ["atr_volume", "atr_body", "volume_range", "engulfing_volume"]:
        detectors.append(CombinedDetector(criteria))

    # 7. Momentum-Based variations
    for momentum in [0.75, 0.80, 0.85]:
        for wick in [0.15, 0.20, 0.25]:
            detectors.append(MomentumBasedDetector(momentum, wick))

    return detectors


def calculate_atr_column(df, period=14):
    """Calculate ATR and add to dataframe"""
    df = df.copy()

    high = df['High']
    low = df['Low']
    close = df['Close'].shift(1)

    tr1 = high - low
    tr2 = abs(high - close)
    tr3 = abs(low - close)

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df['atr'] = tr.rolling(window=period).mean()

    return df
