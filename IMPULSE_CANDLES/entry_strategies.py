"""
Entry Strategies для Impulse Candles
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class EntryStrategy:
    """Base class for entry strategies"""

    def __init__(self, name):
        self.name = name

    def find_entry(self, htf_df, ltf_df, impulse_idx, impulse_direction, ema_filter=None):
        """
        Find entry on LTF after HTF impulse candle

        Args:
            htf_df: Higher timeframe dataframe
            ltf_df: Lower timeframe dataframe
            impulse_idx: Index of impulse candle in HTF
            impulse_direction: 1 for bullish, -1 for bearish
            ema_filter: Optional EMA filter for trend confirmation

        Returns:
            dict with entry info or None:
            {
                'entry_idx': idx in ltf_df,
                'entry_price': price,
                'stop_loss': stop loss price,
                'take_profit': take profit price,
                'entry_time': timestamp,
                'side': 'long' or 'short'
            }
        """
        raise NotImplementedError


class PullbackEntry(EntryStrategy):
    """
    Варіант 1: Engulfing + Pullback Entry

    Чекаємо pullback до Fibonacci рівнів (50% або 61.8%) імпульсної свічки
    """

    def __init__(self, fib_level=0.618, rr_ratio=2.0, max_candles_wait=50, stop_buffer_pct=0.5):
        super().__init__(f"Pullback_Fib{int(fib_level*100)}_RR{rr_ratio}")
        self.fib_level = fib_level
        self.rr_ratio = rr_ratio
        self.max_candles_wait = max_candles_wait
        self.stop_buffer_pct = stop_buffer_pct / 100.0

    def find_entry(self, htf_df, ltf_df, impulse_idx, impulse_direction, ema_filter=None):
        # Get impulse candle
        impulse_candle = htf_df.iloc[impulse_idx]
        impulse_close_time = pd.to_datetime(impulse_candle['Close time'])

        # Get LTF candles after impulse closed
        ltf_after = ltf_df[pd.to_datetime(ltf_df['Open time']) >= impulse_close_time].copy()

        if len(ltf_after) < 5:
            return None

        # Calculate Fibonacci level
        impulse_high = impulse_candle['High']
        impulse_low = impulse_candle['Low']
        impulse_range = impulse_high - impulse_low

        if impulse_direction == 1:  # Bullish
            # Pullback target
            fib_target = impulse_high - (impulse_range * self.fib_level)
            stop_loss = impulse_low * (1 - self.stop_buffer_pct)

            # Look for pullback to fib level
            for i in range(min(self.max_candles_wait, len(ltf_after))):
                candle = ltf_after.iloc[i]

                # Check if price touched fib level
                if candle['Low'] <= fib_target <= candle['High']:
                    # Check EMA filter if provided
                    if ema_filter is not None:
                        ltf_idx = ltf_df.index.get_loc(ltf_after.index[i])
                        if not ema_filter.check_trend(ltf_df, ltf_idx, impulse_direction):
                            continue

                    # Entry at fib level
                    entry_price = fib_target
                    risk = entry_price - stop_loss
                    take_profit = entry_price + (risk * self.rr_ratio)

                    return {
                        'entry_idx': ltf_after.index[i],
                        'entry_price': entry_price,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'entry_time': candle['Open time'],
                        'side': 'long'
                    }

        else:  # Bearish
            # Pullback target
            fib_target = impulse_low + (impulse_range * self.fib_level)
            stop_loss = impulse_high * (1 + self.stop_buffer_pct)

            # Look for pullback to fib level
            for i in range(min(self.max_candles_wait, len(ltf_after))):
                candle = ltf_after.iloc[i]

                # Check if price touched fib level
                if candle['Low'] <= fib_target <= candle['High']:
                    # Check EMA filter if provided
                    if ema_filter is not None:
                        ltf_idx = ltf_df.index.get_loc(ltf_after.index[i])
                        if not ema_filter.check_trend(ltf_df, ltf_idx, impulse_direction):
                            continue

                    # Entry at fib level
                    entry_price = fib_target
                    risk = stop_loss - entry_price
                    take_profit = entry_price - (risk * self.rr_ratio)

                    return {
                        'entry_idx': ltf_after.index[i],
                        'entry_price': entry_price,
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'entry_time': candle['Open time'],
                        'side': 'short'
                    }

        return None


class BreakoutEntry(EntryStrategy):
    """
    Варіант 2: Breakout після Impulse

    Чекаємо consolidation і breakout high/low імпульсної свічки
    """

    def __init__(self, consolidation_min=3, consolidation_max=20, rr_ratio=2.0, stop_buffer_pct=0.5):
        super().__init__(f"Breakout_consol{consolidation_min}-{consolidation_max}_RR{rr_ratio}")
        self.consolidation_min = consolidation_min
        self.consolidation_max = consolidation_max
        self.rr_ratio = rr_ratio
        self.stop_buffer_pct = stop_buffer_pct / 100.0

    def find_entry(self, htf_df, ltf_df, impulse_idx, impulse_direction, ema_filter=None):
        # Get impulse candle
        impulse_candle = htf_df.iloc[impulse_idx]
        impulse_close_time = pd.to_datetime(impulse_candle['Close time'])

        # Get LTF candles after impulse closed
        ltf_after = ltf_df[pd.to_datetime(ltf_df['Open time']) >= impulse_close_time].copy()

        if len(ltf_after) < self.consolidation_min + 2:
            return None

        impulse_high = impulse_candle['High']
        impulse_low = impulse_candle['Low']

        # Look for consolidation period
        for start_idx in range(0, min(10, len(ltf_after) - self.consolidation_min)):
            for consol_len in range(self.consolidation_min, min(self.consolidation_max, len(ltf_after) - start_idx)):
                consol_candles = ltf_after.iloc[start_idx:start_idx + consol_len]

                # Check if consolidation (price not breaking impulse levels significantly)
                consol_high = consol_candles['High'].max()
                consol_low = consol_candles['Low'].min()

                if impulse_direction == 1:  # Bullish
                    # Consolidation should be below impulse high
                    if consol_high > impulse_high * 1.01:
                        continue

                    # Check for breakout
                    if start_idx + consol_len < len(ltf_after):
                        breakout_idx = start_idx + consol_len
                        breakout_candle = ltf_after.iloc[breakout_idx]

                        if breakout_candle['Close'] > impulse_high:
                            # Check EMA filter
                            if ema_filter is not None:
                                ltf_idx = ltf_df.index.get_loc(ltf_after.index[breakout_idx])
                                if not ema_filter.check_trend(ltf_df, ltf_idx, impulse_direction):
                                    continue

                            entry_price = impulse_high
                            stop_loss = consol_low * (1 - self.stop_buffer_pct)
                            risk = entry_price - stop_loss
                            take_profit = entry_price + (risk * self.rr_ratio)

                            return {
                                'entry_idx': ltf_after.index[breakout_idx],
                                'entry_price': entry_price,
                                'stop_loss': stop_loss,
                                'take_profit': take_profit,
                                'entry_time': breakout_candle['Open time'],
                                'side': 'long'
                            }

                else:  # Bearish
                    # Consolidation should be above impulse low
                    if consol_low < impulse_low * 0.99:
                        continue

                    # Check for breakout
                    if start_idx + consol_len < len(ltf_after):
                        breakout_idx = start_idx + consol_len
                        breakout_candle = ltf_after.iloc[breakout_idx]

                        if breakout_candle['Close'] < impulse_low:
                            # Check EMA filter
                            if ema_filter is not None:
                                ltf_idx = ltf_df.index.get_loc(ltf_after.index[breakout_idx])
                                if not ema_filter.check_trend(ltf_df, ltf_idx, impulse_direction):
                                    continue

                            entry_price = impulse_low
                            stop_loss = consol_high * (1 + self.stop_buffer_pct)
                            risk = stop_loss - entry_price
                            take_profit = entry_price - (risk * self.rr_ratio)

                            return {
                                'entry_idx': ltf_after.index[breakout_idx],
                                'entry_price': entry_price,
                                'stop_loss': stop_loss,
                                'take_profit': take_profit,
                                'entry_time': breakout_candle['Open time'],
                                'side': 'short'
                            }

        return None


class FVGEntry(EntryStrategy):
    """
    Варіант 3: FVG Entry після Impulse

    Чекаємо повернення до Fair Value Gap
    """

    def __init__(self, min_fvg_size_pct=0.3, rr_ratio=2.0, max_candles_wait=50, stop_buffer_pct=0.5):
        super().__init__(f"FVG_min{min_fvg_size_pct}%_RR{rr_ratio}")
        self.min_fvg_size_pct = min_fvg_size_pct / 100.0
        self.rr_ratio = rr_ratio
        self.max_candles_wait = max_candles_wait
        self.stop_buffer_pct = stop_buffer_pct / 100.0

    def find_entry(self, htf_df, ltf_df, impulse_idx, impulse_direction, ema_filter=None):
        if impulse_idx < 1:
            return None

        # Get impulse candle and check for FVG
        impulse_candle = htf_df.iloc[impulse_idx]
        prev_candle = htf_df.iloc[impulse_idx - 1]

        impulse_close_time = pd.to_datetime(impulse_candle['Close time'])

        # Detect FVG
        fvg_high = None
        fvg_low = None

        if impulse_direction == 1:  # Bullish FVG
            # Gap between prev candle high and impulse low
            if impulse_candle['Low'] > prev_candle['High']:
                fvg_low = prev_candle['High']
                fvg_high = impulse_candle['Low']
        else:  # Bearish FVG
            # Gap between impulse high and prev candle low
            if impulse_candle['High'] < prev_candle['Low']:
                fvg_high = prev_candle['Low']
                fvg_low = impulse_candle['High']

        # Check if FVG exists and is large enough
        if fvg_high is None or fvg_low is None:
            return None

        fvg_size = fvg_high - fvg_low
        avg_price = (fvg_high + fvg_low) / 2

        if fvg_size / avg_price < self.min_fvg_size_pct:
            return None

        # Get LTF candles after impulse closed
        ltf_after = ltf_df[pd.to_datetime(ltf_df['Open time']) >= impulse_close_time].copy()

        if len(ltf_after) < 3:
            return None

        # Look for price returning to FVG
        for i in range(min(self.max_candles_wait, len(ltf_after))):
            candle = ltf_after.iloc[i]

            # Check if price touched FVG zone
            if candle['Low'] <= fvg_high and candle['High'] >= fvg_low:
                # Check EMA filter if provided
                if ema_filter is not None:
                    ltf_idx = ltf_df.index.get_loc(ltf_after.index[i])
                    if not ema_filter.check_trend(ltf_df, ltf_idx, impulse_direction):
                        continue

                # Entry at mid FVG
                entry_price = (fvg_high + fvg_low) / 2

                if impulse_direction == 1:  # Long
                    stop_loss = fvg_low * (1 - self.stop_buffer_pct)
                    risk = entry_price - stop_loss
                    take_profit = entry_price + (risk * self.rr_ratio)
                    side = 'long'
                else:  # Short
                    stop_loss = fvg_high * (1 + self.stop_buffer_pct)
                    risk = stop_loss - entry_price
                    take_profit = entry_price - (risk * self.rr_ratio)
                    side = 'short'

                return {
                    'entry_idx': ltf_after.index[i],
                    'entry_price': entry_price,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'entry_time': candle['Open time'],
                    'side': side
                }

        return None


class MomentumContinuation(EntryStrategy):
    """
    Варіант 4: Momentum Continuation

    Вхід на pullback до EMA21 на LTF
    """

    def __init__(self, rr_ratio=2.0, max_candles_wait=30, stop_buffer_pct=1.0):
        super().__init__(f"MomentumCont_RR{rr_ratio}")
        self.rr_ratio = rr_ratio
        self.max_candles_wait = max_candles_wait
        self.stop_buffer_pct = stop_buffer_pct / 100.0

    def find_entry(self, htf_df, ltf_df, impulse_idx, impulse_direction, ema_filter=None):
        if ema_filter is None:
            return None  # This strategy requires EMA filter

        # Get impulse candle
        impulse_candle = htf_df.iloc[impulse_idx]
        impulse_close_time = pd.to_datetime(impulse_candle['Close time'])

        # Get LTF candles after impulse closed
        ltf_after = ltf_df[pd.to_datetime(ltf_df['Open time']) >= impulse_close_time].copy()

        if len(ltf_after) < 5:
            return None

        # Look for pullback to EMA21
        for i in range(1, min(self.max_candles_wait, len(ltf_after))):
            candle = ltf_after.iloc[i]
            ltf_idx = ltf_df.index.get_loc(ltf_after.index[i])

            # Check if price touched EMA21
            if 'ema_long' not in ltf_df.columns:
                continue

            ema21 = ltf_df['ema_long'].iloc[ltf_idx]

            if impulse_direction == 1:  # Long
                # Check if price pulled back to EMA21
                if candle['Low'] <= ema21 * 1.005:  # 0.5% tolerance
                    # Check trend
                    if not ema_filter.check_trend(ltf_df, ltf_idx, impulse_direction):
                        continue

                    # Check for rejection (close above EMA21)
                    if candle['Close'] > ema21:
                        entry_price = ema21
                        stop_loss = ema21 * (1 - self.stop_buffer_pct)
                        risk = entry_price - stop_loss
                        take_profit = entry_price + (risk * self.rr_ratio)

                        return {
                            'entry_idx': ltf_after.index[i],
                            'entry_price': entry_price,
                            'stop_loss': stop_loss,
                            'take_profit': take_profit,
                            'entry_time': candle['Open time'],
                            'side': 'long'
                        }

            else:  # Short
                # Check if price pulled back to EMA21
                if candle['High'] >= ema21 * 0.995:  # 0.5% tolerance
                    # Check trend
                    if not ema_filter.check_trend(ltf_df, ltf_idx, impulse_direction):
                        continue

                    # Check for rejection (close below EMA21)
                    if candle['Close'] < ema21:
                        entry_price = ema21
                        stop_loss = ema21 * (1 + self.stop_buffer_pct)
                        risk = stop_loss - entry_price
                        take_profit = entry_price - (risk * self.rr_ratio)

                        return {
                            'entry_idx': ltf_after.index[i],
                            'entry_price': entry_price,
                            'stop_loss': stop_loss,
                            'take_profit': take_profit,
                            'entry_time': candle['Open time'],
                            'side': 'short'
                        }

        return None


def get_all_entry_strategies():
    """Get all entry strategy configurations for testing"""
    strategies = []

    # 1. Pullback Entry variations
    for fib in [0.5, 0.618]:
        for rr in [2.0, 3.0]:
            strategies.append(PullbackEntry(fib_level=fib, rr_ratio=rr))

    # 2. Breakout Entry
    for rr in [2.0, 3.0]:
        strategies.append(BreakoutEntry(rr_ratio=rr))

    # 3. FVG Entry
    for rr in [2.0, 3.0]:
        strategies.append(FVGEntry(rr_ratio=rr))

    # 4. Momentum Continuation
    for rr in [2.0, 3.0]:
        strategies.append(MomentumContinuation(rr_ratio=rr))

    return strategies
