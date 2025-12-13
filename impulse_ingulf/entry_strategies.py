"""
Entry Strategy для Live Bot - Breakout Entry
Адаптовано для live trading без lookahead bias
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class BreakoutEntry:
    """
    Breakout Entry після Impulse Candle

    CRITICAL для live bot:
    - Використовуємо тільки ЗАКРИТІ свічки
    - Entry може відбутися тільки ПІСЛЯ закриття імпульсної свічки
    - Немає lookahead bias
    """

    def __init__(self, consolidation_min=3, consolidation_max=20,
                 rr_ratio=2.0, stop_buffer_pct=0.5):
        self.consolidation_min = consolidation_min
        self.consolidation_max = consolidation_max
        self.rr_ratio = rr_ratio  # Base RR (will be overridden by dynamic RR)
        self.stop_buffer_pct = stop_buffer_pct / 100.0

    def find_entry(self, htf_df, ltf_df, impulse_idx, impulse_direction, ema_filter=None):
        """
        Find breakout entry on LTF after HTF impulse candle

        CRITICAL: This method ensures NO lookahead bias:
        - Uses only CLOSED candles from ltf_df
        - Entry can only happen AFTER impulse candle close

        Args:
            htf_df: Higher timeframe dataframe (4H)
            ltf_df: Lower timeframe dataframe (1H)
            impulse_idx: Index of impulse candle in HTF
            impulse_direction: 1 for bullish, -1 for bearish
            ema_filter: EMA filter for trend confirmation

        Returns:
            dict with entry info or None
        """
        # Get impulse candle
        impulse_candle = htf_df.iloc[impulse_idx]
        impulse_close_time = pd.to_datetime(impulse_candle['Close time'])

        # Get LTF candles AFTER impulse closed (no lookahead!)
        ltf_after = ltf_df[pd.to_datetime(ltf_df['Open time']) >= impulse_close_time].copy()

        if len(ltf_after) < self.consolidation_min + 2:
            return None

        impulse_high = impulse_candle['High']
        impulse_low = impulse_candle['Low']

        # Look for consolidation period + breakout
        for start_idx in range(0, min(10, len(ltf_after) - self.consolidation_min)):
            for consol_len in range(self.consolidation_min,
                                   min(self.consolidation_max, len(ltf_after) - start_idx)):
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

                            # Base TP (will be recalculated with dynamic RR)
                            take_profit = entry_price + (risk * self.rr_ratio)

                            return {
                                'entry_idx': ltf_after.index[breakout_idx],
                                'entry_price': entry_price,
                                'stop_loss': stop_loss,
                                'take_profit': take_profit,
                                'entry_time': breakout_candle['Open time'],
                                'side': 'long',
                                'rr': self.rr_ratio  # Base RR
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

                            # Base TP (will be recalculated with dynamic RR)
                            take_profit = entry_price - (risk * self.rr_ratio)

                            return {
                                'entry_idx': ltf_after.index[breakout_idx],
                                'entry_price': entry_price,
                                'stop_loss': stop_loss,
                                'take_profit': take_profit,
                                'entry_time': breakout_candle['Open time'],
                                'side': 'short',
                                'rr': self.rr_ratio  # Base RR
                            }

        return None
