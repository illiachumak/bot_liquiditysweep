"""
Quality Scoring для фільтрації слабких setup
Мета: фільтрувати low-quality trades для підвищення EV
"""
import pandas as pd
import numpy as np


class QualityScorer:
    """Оцінює якість setup перед входом"""

    def __init__(self, name, min_score=5):
        self.name = name
        self.min_score = min_score

    def score_setup(self, htf_df, ltf_df, impulse_idx, impulse_direction, entry):
        """
        Оцінити якість setup

        Returns:
            int: score (0-10), вищий = краще
        """
        score = 0

        # 1. Impulse strength (0-2 points)
        impulse_candle = htf_df.iloc[impulse_idx]
        body = abs(impulse_candle['Close'] - impulse_candle['Open'])
        total_range = impulse_candle['High'] - impulse_candle['Low']

        if total_range > 0:
            body_ratio = body / total_range
            if body_ratio > 0.85:
                score += 2
            elif body_ratio > 0.75:
                score += 1

        # 2. Volume confirmation (0-2 points)
        if impulse_idx >= 20:
            avg_volume = htf_df['Volume'].iloc[impulse_idx-20:impulse_idx].mean()
            if impulse_candle['Volume'] > avg_volume * 2.0:
                score += 2
            elif impulse_candle['Volume'] > avg_volume * 1.5:
                score += 1

        # 3. Trend alignment (0-2 points)
        # Check if impulse is in direction of higher TF trend
        if impulse_idx >= 50:
            # Simple MA based trend
            ma50 = htf_df['Close'].iloc[impulse_idx-50:impulse_idx].mean()
            current_close = impulse_candle['Close']

            if impulse_direction == 1 and current_close > ma50 * 1.02:  # Uptrend + bullish impulse
                score += 2
            elif impulse_direction == -1 and current_close < ma50 * 0.98:  # Downtrend + bearish impulse
                score += 2
            elif impulse_direction == 1 and current_close > ma50:
                score += 1
            elif impulse_direction == -1 and current_close < ma50:
                score += 1

        # 4. Entry timing (0-2 points)
        # Чим швидше вхід після impulse = краще
        entry_time = pd.to_datetime(entry['entry_time'])
        impulse_close_time = pd.to_datetime(impulse_candle['Close time'])

        time_diff_hours = (entry_time - impulse_close_time).total_seconds() / 3600

        if time_diff_hours <= 4:  # Within 4 hours
            score += 2
        elif time_diff_hours <= 12:
            score += 1

        # 5. Clean breakout (0-2 points) - for breakout strategy
        # Check if consolidation is tight
        if 'consolidation' in entry:
            consol_range = entry['consolidation']['range']
            impulse_range = total_range

            if impulse_range > 0:
                consol_ratio = consol_range / impulse_range
                if consol_ratio < 0.3:  # Tight consolidation
                    score += 2
                elif consol_ratio < 0.5:
                    score += 1

        return score

    def filter_setup(self, htf_df, ltf_df, impulse_idx, impulse_direction, entry):
        """
        Return True if setup passes quality filter

        Args:
            htf_df, ltf_df: dataframes
            impulse_idx: index of impulse
            impulse_direction: 1/-1
            entry: entry dict

        Returns:
            bool: True if quality is sufficient
        """
        score = self.score_setup(htf_df, ltf_df, impulse_idx, impulse_direction, entry)
        return score >= self.min_score


class TrailingStopOptimizer:
    """
    Trailing Stop для максимізації profits

    Після досягнення певного профіту, переключаємось на trailing stop
    """

    def __init__(self, activation_r=1.5, trail_distance_r=0.5):
        """
        Args:
            activation_r: Після скількох R активувати trailing (1.5 = after 1.5R profit)
            trail_distance_r: На якій відстані тримати trailing stop (0.5 = 0.5R від highest)
        """
        self.name = f"Trailing_act{activation_r}R_trail{trail_distance_r}R"
        self.activation_r = activation_r
        self.trail_distance_r = trail_distance_r

    def optimize_exit(self, ltf_df, entry, side, entry_idx):
        """Trailing stop logic"""
        entry_price = entry['entry_price']
        stop_loss = entry['stop_loss']
        take_profit = entry['take_profit']
        entry_time = pd.to_datetime(entry['entry_time'])

        ltf_after = ltf_df[pd.to_datetime(ltf_df['Open time']) > entry_time].copy()

        if len(ltf_after) == 0:
            return None

        risk = abs(entry_price - stop_loss)
        trailing_active = False
        trailing_stop = stop_loss
        highest_profit = 0  # In R

        for i in range(len(ltf_after)):
            candle = ltf_after.iloc[i]

            if side == 'long':
                # Update highest profit
                current_profit_r = (candle['High'] - entry_price) / risk
                if current_profit_r > highest_profit:
                    highest_profit = current_profit_r

                # Activate trailing if profit >= activation_r
                if not trailing_active and highest_profit >= self.activation_r:
                    trailing_active = True

                # Update trailing stop
                if trailing_active:
                    new_trailing_stop = entry_price + (risk * (highest_profit - self.trail_distance_r))
                    trailing_stop = max(trailing_stop, new_trailing_stop)

                # Check stop
                current_stop = trailing_stop if trailing_active else stop_loss
                if candle['Low'] <= current_stop:
                    exit_reason = 'trailing_stop' if trailing_active else 'stop_loss'
                    pnl_mult = (current_stop - entry_price) / risk
                    return {
                        'exit_price': current_stop,
                        'exit_time': candle['Open time'],
                        'exit_reason': exit_reason,
                        'pnl_multiplier': pnl_mult
                    }

                # Check TP
                if candle['High'] >= take_profit:
                    return {
                        'exit_price': take_profit,
                        'exit_time': candle['Open time'],
                        'exit_reason': 'take_profit',
                        'pnl_multiplier': (take_profit - entry_price) / risk
                    }

            else:  # short
                # Update highest profit
                current_profit_r = (entry_price - candle['Low']) / risk
                if current_profit_r > highest_profit:
                    highest_profit = current_profit_r

                # Activate trailing
                if not trailing_active and highest_profit >= self.activation_r:
                    trailing_active = True

                # Update trailing stop
                if trailing_active:
                    new_trailing_stop = entry_price - (risk * (highest_profit - self.trail_distance_r))
                    trailing_stop = min(trailing_stop, new_trailing_stop)

                # Check stop
                current_stop = trailing_stop if trailing_active else stop_loss
                if candle['High'] >= current_stop:
                    exit_reason = 'trailing_stop' if trailing_active else 'stop_loss'
                    pnl_mult = (entry_price - current_stop) / risk
                    return {
                        'exit_price': current_stop,
                        'exit_time': candle['Open time'],
                        'exit_reason': exit_reason,
                        'pnl_multiplier': pnl_mult
                    }

                # Check TP
                if candle['Low'] <= take_profit:
                    return {
                        'exit_price': take_profit,
                        'exit_time': candle['Open time'],
                        'exit_reason': 'take_profit',
                        'pnl_multiplier': (entry_price - take_profit) / risk
                    }

        return None


def get_quality_filters():
    """Get quality filter variations"""
    filters = []

    # Different minimum score thresholds
    for min_score in [4, 5, 6, 7]:
        filters.append(QualityScorer(f"QualityMin{min_score}", min_score=min_score))

    return filters


def get_trailing_optimizers():
    """Get trailing stop variations"""
    optimizers = []

    # Different activation and trail distances
    for activation_r in [1.0, 1.5, 2.0]:
        for trail_r in [0.3, 0.5, 0.7]:
            optimizers.append(TrailingStopOptimizer(activation_r, trail_r))

    return optimizers
