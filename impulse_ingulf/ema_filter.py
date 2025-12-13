"""
EMA Trend Filter для LTF (Lower Timeframe)
"""
import pandas as pd
import numpy as np


def calculate_ema(df, period, column='Close'):
    """Calculate EMA for given period"""
    return df[column].ewm(span=period, adjust=False).mean()


def add_ema_columns(df, short_period=12, long_period=21):
    """Add EMA columns to dataframe"""
    df = df.copy()
    df['ema_short'] = calculate_ema(df, short_period)
    df['ema_long'] = calculate_ema(df, long_period)
    return df


def is_uptrend_with_respect(df, idx, lookback=10):
    """
    Check if market is in uptrend with EMA respect

    Uptrend conditions:
    - EMA12 > EMA21
    - No close below EMA21 in last N candles (respect)

    Args:
        df: DataFrame with ema_short and ema_long columns
        idx: Current candle index
        lookback: Number of candles to check for respect

    Returns:
        bool: True if uptrend with respect, False otherwise
    """
    if idx < lookback:
        return False

    # Check if EMA12 > EMA21
    ema_short = df['ema_short'].iloc[idx]
    ema_long = df['ema_long'].iloc[idx]

    if ema_short <= ema_long:
        return False

    # Check respect: no close below EMA21 in last N candles
    start_idx = max(0, idx - lookback + 1)
    last_n_closes = df['Close'].iloc[start_idx:idx + 1]
    last_n_ema_long = df['ema_long'].iloc[start_idx:idx + 1]

    # All closes should be >= EMA21
    respect = (last_n_closes >= last_n_ema_long).all()

    return respect


def is_downtrend_with_respect(df, idx, lookback=10):
    """
    Check if market is in downtrend with EMA respect

    Downtrend conditions:
    - EMA12 < EMA21
    - No close above EMA21 in last N candles (respect)

    Args:
        df: DataFrame with ema_short and ema_long columns
        idx: Current candle index
        lookback: Number of candles to check for respect

    Returns:
        bool: True if downtrend with respect, False otherwise
    """
    if idx < lookback:
        return False

    # Check if EMA12 < EMA21
    ema_short = df['ema_short'].iloc[idx]
    ema_long = df['ema_long'].iloc[idx]

    if ema_short >= ema_long:
        return False

    # Check respect: no close above EMA21 in last N candles
    start_idx = max(0, idx - lookback + 1)
    last_n_closes = df['Close'].iloc[start_idx:idx + 1]
    last_n_ema_long = df['ema_long'].iloc[start_idx:idx + 1]

    # All closes should be <= EMA21
    respect = (last_n_closes <= last_n_ema_long).all()

    return respect


def get_trend_direction(df, idx, lookback=10):
    """
    Get trend direction at given index

    Returns:
        1: Uptrend with respect
        -1: Downtrend with respect
        0: No clear trend or no respect
    """
    if is_uptrend_with_respect(df, idx, lookback):
        return 1
    elif is_downtrend_with_respect(df, idx, lookback):
        return -1
    else:
        return 0


def trend_matches_impulse(df, idx, impulse_direction, lookback=10):
    """
    Check if trend direction matches impulse direction

    Args:
        df: DataFrame with EMA columns
        idx: Current candle index
        impulse_direction: 1 for bullish, -1 for bearish
        lookback: Lookback period for respect check

    Returns:
        bool: True if trend matches impulse direction
    """
    trend_dir = get_trend_direction(df, idx, lookback)
    return trend_dir == impulse_direction


class EMAFilter:
    """EMA Trend Filter class"""

    def __init__(self, short_period=12, long_period=21, lookback=10):
        self.short_period = short_period
        self.long_period = long_period
        self.lookback = lookback
        self.name = f"EMA{short_period}_{long_period}_lookback{lookback}"

    def prepare_data(self, df):
        """Add EMA columns to dataframe"""
        return add_ema_columns(df, self.short_period, self.long_period)

    def check_trend(self, df, idx, required_direction):
        """
        Check if trend at idx matches required direction

        Args:
            df: DataFrame with EMA columns
            idx: Current index
            required_direction: 1 for uptrend, -1 for downtrend

        Returns:
            bool: True if trend matches required direction
        """
        if required_direction == 1:
            return is_uptrend_with_respect(df, idx, self.lookback)
        elif required_direction == -1:
            return is_downtrend_with_respect(df, idx, self.lookback)
        else:
            return False

    def get_trend(self, df, idx):
        """Get current trend direction"""
        return get_trend_direction(df, idx, self.lookback)


def get_all_ema_filters():
    """Get all EMA filter configurations for testing"""
    filters = []

    # Different lookback periods: 5, 7, 10, 12, 15
    for lookback in [5, 7, 10, 12, 15]:
        filters.append(EMAFilter(short_period=12, long_period=21, lookback=lookback))

    return filters
