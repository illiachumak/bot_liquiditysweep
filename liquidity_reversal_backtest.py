"""
Liquidity Sweep Reversal Backtest
==================================
Strategy: Reversal after liquidity sweep with volume and weak (FVG)

Timeframes:
- 4H: Detect liquidity sweeps
- 15M: Entry on sharp reversal with volume + weak/FVG

Entry Conditions:
1. 4H liquidity sweep detected (sweep of recent high/low)
2. 15M sharp reversal candle back to liquidity level
3. High volume on reversal candle (> 1.5x average)
4. Fair Value Gap (FVG/weak) present at reversal level

Exit:
- Stop Loss: Beyond swept liquidity level
- Take Profit: Risk:Reward 1:2, 1:3, 1:5 levels
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
from pathlib import Path

try:
    from smartmoneyconcepts import smc
    SMC_AVAILABLE = True
except ImportError:
    print("⚠️  smartmoneyconcepts library not available. Install: pip install smartmoneyconcepts")
    SMC_AVAILABLE = False


class LiquiditySweepDetector:
    """Detects liquidity sweeps on 4H timeframe"""

    def __init__(self, lookback: int = 20, sweep_threshold: float = 0.001):
        """
        Args:
            lookback: How many candles to look back for swing highs/lows
            sweep_threshold: Minimum % move beyond level to confirm sweep (0.1%)
        """
        self.lookback = lookback
        self.sweep_threshold = sweep_threshold
        self.liquidity_levels = []  # Track identified liquidity levels

    def find_swing_points(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """Find swing highs and lows"""
        swing_highs = pd.Series(index=df.index, dtype=float)
        swing_lows = pd.Series(index=df.index, dtype=float)

        for i in range(self.lookback, len(df) - self.lookback):
            # Check if current candle is swing high
            is_swing_high = True
            is_swing_low = True

            for j in range(1, self.lookback + 1):
                if df['high'].iloc[i] <= df['high'].iloc[i - j] or \
                   df['high'].iloc[i] <= df['high'].iloc[i + j]:
                    is_swing_high = False

                if df['low'].iloc[i] >= df['low'].iloc[i - j] or \
                   df['low'].iloc[i] >= df['low'].iloc[i + j]:
                    is_swing_low = False

            if is_swing_high:
                swing_highs.iloc[i] = df['high'].iloc[i]
            if is_swing_low:
                swing_lows.iloc[i] = df['low'].iloc[i]

        return swing_highs, swing_lows

    def detect_liquidity_sweep(self, df_4h: pd.DataFrame, current_idx: int) -> Optional[Dict]:
        """
        Detect if liquidity sweep occurred at current 4H candle

        Returns:
            Dict with sweep info or None
            {
                'type': 'HIGH' or 'LOW',
                'swept_level': price,
                'sweep_candle_idx': idx,
                'sweep_time': timestamp
            }
        """
        if current_idx < self.lookback + 5:
            return None

        swing_highs, swing_lows = self.find_swing_points(df_4h.iloc[:current_idx + 1])

        current_candle = df_4h.iloc[current_idx]

        # Check for liquidity sweep HIGH
        # Look for recent swing high that got swept
        recent_swing_highs = swing_highs.iloc[max(0, current_idx - 20):current_idx].dropna()

        if len(recent_swing_highs) > 0:
            last_swing_high = recent_swing_highs.iloc[-1]
            last_swing_high_idx = recent_swing_highs.index[-1]

            # Check if current candle swept above this high
            sweep_threshold_price = last_swing_high * (1 + self.sweep_threshold)

            if current_candle['high'] > sweep_threshold_price:
                # Check if price reversed (closed below swept level)
                if current_candle['close'] < last_swing_high:
                    return {
                        'type': 'HIGH',
                        'swept_level': last_swing_high,
                        'sweep_candle_idx': current_idx,
                        'sweep_time': df_4h.index[current_idx],
                        'reversal_confirmed': True,
                        'swept_level_idx': last_swing_high_idx
                    }

        # Check for liquidity sweep LOW
        recent_swing_lows = swing_lows.iloc[max(0, current_idx - 20):current_idx].dropna()

        if len(recent_swing_lows) > 0:
            last_swing_low = recent_swing_lows.iloc[-1]
            last_swing_low_idx = recent_swing_lows.index[-1]

            # Check if current candle swept below this low
            sweep_threshold_price = last_swing_low * (1 - self.sweep_threshold)

            if current_candle['low'] < sweep_threshold_price:
                # Check if price reversed (closed above swept level)
                if current_candle['close'] > last_swing_low:
                    return {
                        'type': 'LOW',
                        'swept_level': last_swing_low,
                        'sweep_candle_idx': current_idx,
                        'sweep_time': df_4h.index[current_idx],
                        'reversal_confirmed': True,
                        'swept_level_idx': last_swing_low_idx
                    }

        return None


class FVGDetector:
    """Detects Fair Value Gaps (imbalances/weak areas)"""

    @staticmethod
    def detect_fvg(df: pd.DataFrame, idx: int) -> Optional[Dict]:
        """
        Detect FVG at given index

        FVG occurs when:
        - Bullish FVG: candle[i-2].high < candle[i].low (gap between them)
        - Bearish FVG: candle[i-2].low > candle[i].high (gap between them)

        Returns:
            Dict with FVG info or None
        """
        if idx < 2:
            return None

        current = df.iloc[idx]
        two_back = df.iloc[idx - 2]

        # Bullish FVG
        if two_back['high'] < current['low']:
            gap_size = current['low'] - two_back['high']
            if gap_size > 0:
                return {
                    'type': 'BULLISH',
                    'top': current['low'],
                    'bottom': two_back['high'],
                    'size': gap_size,
                    'idx': idx
                }

        # Bearish FVG
        if two_back['low'] > current['high']:
            gap_size = two_back['low'] - current['high']
            if gap_size > 0:
                return {
                    'type': 'BEARISH',
                    'top': two_back['low'],
                    'bottom': current['high'],
                    'size': gap_size,
                    'idx': idx
                }

        return None


class VolumeAnalyzer:
    """Analyzes volume for entry confirmation"""

    @staticmethod
    def calculate_volume_ratio(df: pd.DataFrame, idx: int, lookback: int = 20) -> float:
        """
        Calculate volume ratio: current volume / average volume

        Args:
            df: DataFrame with 'volume' column
            idx: Current index
            lookback: How many candles to use for average

        Returns:
            Volume ratio (e.g., 1.5 means 50% higher than average)
        """
        if idx < lookback:
            return 1.0

        current_volume = df['volume'].iloc[idx]
        avg_volume = df['volume'].iloc[idx - lookback:idx].mean()

        if avg_volume == 0:
            return 1.0

        return current_volume / avg_volume

    @staticmethod
    def is_high_volume(df: pd.DataFrame, idx: int, threshold: float = 1.5, lookback: int = 20) -> bool:
        """Check if current candle has high volume"""
        ratio = VolumeAnalyzer.calculate_volume_ratio(df, idx, lookback)
        return ratio >= threshold


class ReversalDetector:
    """Detects sharp reversal candles on 15m timeframe"""

    @staticmethod
    def detect_bullish_reversal(df: pd.DataFrame, idx: int, min_body_pct: float = 0.6) -> bool:
        """
        Detect bullish reversal candle

        Criteria:
        - Green candle (close > open)
        - Large body (body > 60% of total range)
        - Close near high
        """
        if idx < 1:
            return False

        candle = df.iloc[idx]
        open_price = candle['open']
        close = candle['close']
        high = candle['high']
        low = candle['low']

        # Must be green
        if close <= open_price:
            return False

        total_range = high - low
        if total_range == 0:
            return False

        body = close - open_price
        body_pct = body / total_range

        # Body must be significant
        if body_pct < min_body_pct:
            return False

        # Close should be in upper part of candle
        upper_wick = high - close
        if upper_wick / total_range > 0.3:  # Upper wick < 30%
            return False

        return True

    @staticmethod
    def detect_bearish_reversal(df: pd.DataFrame, idx: int, min_body_pct: float = 0.6) -> bool:
        """
        Detect bearish reversal candle

        Criteria:
        - Red candle (close < open)
        - Large body (body > 60% of total range)
        - Close near low
        """
        if idx < 1:
            return False

        candle = df.iloc[idx]
        open_price = candle['open']
        close = candle['close']
        high = candle['high']
        low = candle['low']

        # Must be red
        if close >= open_price:
            return False

        total_range = high - low
        if total_range == 0:
            return False

        body = open_price - close
        body_pct = body / total_range

        # Body must be significant
        if body_pct < min_body_pct:
            return False

        # Close should be in lower part of candle
        lower_wick = close - low
        if lower_wick / total_range > 0.3:  # Lower wick < 30%
            return False

        return True


class Trade:
    """Represents a single trade"""

    def __init__(self, entry_time, entry_price, stop_loss, take_profits,
                 direction, size, sweep_info):
        self.entry_time = entry_time
        self.entry_price = entry_price
        self.stop_loss = stop_loss
        self.take_profits = take_profits  # List of TP levels
        self.tp_percentages = [0.5, 0.3, 0.2]  # 50%, 30%, 20% of position
        self.direction = direction  # 'LONG' or 'SHORT'
        self.size = size
        self.sweep_info = sweep_info

        self.exit_time = None
        self.exit_price = None
        self.exit_reason = None
        self.pnl = 0
        self.pnl_pct = 0
        self.remaining_size = size
        self.partial_exits = []  # List of partial exits
        self.status = 'OPEN'  # OPEN, CLOSED

        # Move SL to breakeven after TP1
        self.breakeven_moved = False

    def check_exit(self, candle: pd.Series) -> Optional[str]:
        """
        Check if trade should exit on this candle

        Returns:
            Exit reason if should exit, None otherwise
        """
        high = candle['high']
        low = candle['low']

        if self.direction == 'LONG':
            # Check stop loss
            if low <= self.stop_loss:
                return 'SL'

            # Check take profits
            for i, tp in enumerate(self.take_profits):
                if high >= tp and i >= len(self.partial_exits):
                    return f'TP{i+1}'

        else:  # SHORT
            # Check stop loss
            if high >= self.stop_loss:
                return 'SL'

            # Check take profits
            for i, tp in enumerate(self.take_profits):
                if low <= tp and i >= len(self.partial_exits):
                    return f'TP{i+1}'

        return None

    def close_partial(self, exit_time, exit_price, tp_level: int):
        """Close partial position at TP level"""
        exit_size = self.size * self.tp_percentages[tp_level]
        self.remaining_size -= exit_size

        if self.direction == 'LONG':
            partial_pnl = (exit_price - self.entry_price) * exit_size
        else:
            partial_pnl = (self.entry_price - exit_price) * exit_size

        self.partial_exits.append({
            'time': exit_time,
            'price': exit_price,
            'size': exit_size,
            'pnl': partial_pnl,
            'reason': f'TP{tp_level + 1}'
        })

        self.pnl += partial_pnl

        # Move SL to breakeven after TP1
        if tp_level == 0 and not self.breakeven_moved:
            self.stop_loss = self.entry_price
            self.breakeven_moved = True

        # If all TPs hit, close trade
        if len(self.partial_exits) == len(self.take_profits):
            self.status = 'CLOSED'
            self.exit_time = exit_time
            self.exit_price = exit_price
            self.exit_reason = 'ALL_TPS'

    def close_full(self, exit_time, exit_price, reason: str):
        """Close full remaining position"""
        if self.direction == 'LONG':
            remaining_pnl = (exit_price - self.entry_price) * self.remaining_size
        else:
            remaining_pnl = (self.entry_price - exit_price) * self.remaining_size

        self.pnl += remaining_pnl
        self.pnl_pct = (self.pnl / (self.entry_price * self.size)) * 100

        self.exit_time = exit_time
        self.exit_price = exit_price
        self.exit_reason = reason
        self.status = 'CLOSED'
        self.remaining_size = 0

    def to_dict(self) -> Dict:
        """Convert trade to dictionary for logging"""
        return {
            'entry_time': str(self.entry_time),
            'entry_price': float(self.entry_price),
            'exit_time': str(self.exit_time) if self.exit_time else None,
            'exit_price': float(self.exit_price) if self.exit_price else None,
            'direction': self.direction,
            'size': float(self.size),
            'stop_loss': float(self.stop_loss),
            'take_profits': [float(tp) for tp in self.take_profits],
            'pnl': float(self.pnl),
            'pnl_pct': float(self.pnl_pct),
            'exit_reason': self.exit_reason,
            'partial_exits': self.partial_exits,
            'breakeven_moved': self.breakeven_moved,
            'sweep_type': self.sweep_info['type'] if self.sweep_info else None
        }


class LiquidityReversalBacktest:
    """Main backtest engine"""

    def __init__(self,
                 initial_balance: float = 10000,
                 risk_per_trade: float = 0.02,
                 volume_threshold: float = 1.5,
                 sweep_lookback: int = 20):
        """
        Args:
            initial_balance: Starting capital in USDT
            risk_per_trade: Risk per trade as % of balance (0.02 = 2%)
            volume_threshold: Minimum volume ratio for entry (1.5 = 50% above avg)
            sweep_lookback: Lookback period for liquidity sweep detection
        """
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.risk_per_trade = risk_per_trade
        self.volume_threshold = volume_threshold

        # Components
        self.sweep_detector = LiquiditySweepDetector(lookback=sweep_lookback)
        self.fvg_detector = FVGDetector()
        self.volume_analyzer = VolumeAnalyzer()
        self.reversal_detector = ReversalDetector()

        # Trade tracking
        self.trades = []
        self.active_trade = None
        self.active_sweeps = []  # Track recent sweeps waiting for entry

        # Statistics
        self.stats = {
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'total_pnl': 0,
            'max_balance': initial_balance,
            'min_balance': initial_balance,
            'max_drawdown': 0
        }

    def load_data(self, symbol: str = 'BTCUSDT',
                  start_date: str = '2023-01-01',
                  end_date: str = '2024-12-31') -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Load historical data for both timeframes

        In production, this would fetch from Binance API
        For now, using simulated data structure

        Returns:
            df_4h, df_15m - DataFrames with OHLCV data
        """
        print(f"\n📊 Loading data for {symbol}")
        print(f"   Period: {start_date} to {end_date}")
        print(f"   Timeframes: 4H, 15M")

        # TODO: Implement actual data loading from Binance or CSV
        # For now, return empty DataFrames with correct structure
        # User will need to provide their own data

        raise NotImplementedError(
            "Data loading not implemented. Please load your own data with columns:\n"
            "- 'open', 'high', 'low', 'close', 'volume'\n"
            "- Index: DatetimeIndex\n\n"
            "Example:\n"
            "  df_4h = pd.read_csv('btcusdt_4h.csv', parse_dates=['timestamp'], index_col='timestamp')\n"
            "  df_15m = pd.read_csv('btcusdt_15m.csv', parse_dates=['timestamp'], index_col='timestamp')\n"
            "  backtest.run_backtest(df_4h, df_15m)"
        )

    def check_entry_conditions(self, df_15m: pd.DataFrame, idx_15m: int,
                               sweep_info: Dict) -> Optional[Dict]:
        """
        Check if entry conditions are met on 15m timeframe

        Args:
            df_15m: 15-minute DataFrame
            idx_15m: Current 15m candle index
            sweep_info: Liquidity sweep information from 4H

        Returns:
            Entry signal dict or None
        """
        if idx_15m < 25:  # Need history for volume calculation
            return None

        candle = df_15m.iloc[idx_15m]

        # 1. Check if we're near the swept liquidity level
        liquidity_level = sweep_info['swept_level']
        tolerance = liquidity_level * 0.002  # 0.2% tolerance

        candle_near_level = (candle['low'] <= liquidity_level + tolerance and
                            candle['high'] >= liquidity_level - tolerance)

        if not candle_near_level:
            return None

        # 2. Check for sharp reversal candle
        is_bullish_reversal = False
        is_bearish_reversal = False

        if sweep_info['type'] == 'LOW':
            # After low sweep, look for bullish reversal
            is_bullish_reversal = self.reversal_detector.detect_bullish_reversal(df_15m, idx_15m)
        else:  # HIGH sweep
            # After high sweep, look for bearish reversal
            is_bearish_reversal = self.reversal_detector.detect_bearish_reversal(df_15m, idx_15m)

        if not (is_bullish_reversal or is_bearish_reversal):
            return None

        # 3. Check volume
        if not self.volume_analyzer.is_high_volume(df_15m, idx_15m,
                                                   threshold=self.volume_threshold):
            return None

        volume_ratio = self.volume_analyzer.calculate_volume_ratio(df_15m, idx_15m)

        # 4. Check for FVG (imbalance/weak)
        fvg = self.fvg_detector.detect_fvg(df_15m, idx_15m)

        if not fvg:
            return None

        # Check FVG type matches sweep type
        if sweep_info['type'] == 'LOW' and fvg['type'] != 'BULLISH':
            return None
        if sweep_info['type'] == 'HIGH' and fvg['type'] != 'BEARISH':
            return None

        # All conditions met!
        return {
            'direction': 'LONG' if sweep_info['type'] == 'LOW' else 'SHORT',
            'entry_price': candle['close'],
            'entry_time': df_15m.index[idx_15m],
            'volume_ratio': volume_ratio,
            'fvg': fvg,
            'sweep_info': sweep_info
        }

    def calculate_position_size(self, entry_price: float, stop_loss: float) -> float:
        """Calculate position size based on risk"""
        risk_amount = self.balance * self.risk_per_trade
        risk_per_unit = abs(entry_price - stop_loss)

        if risk_per_unit == 0:
            return 0

        size = risk_amount / risk_per_unit
        return size

    def create_trade(self, signal: Dict) -> Trade:
        """Create trade from entry signal"""
        direction = signal['direction']
        entry_price = signal['entry_price']

        # Calculate stop loss (beyond swept level)
        if direction == 'LONG':
            stop_loss = signal['sweep_info']['swept_level'] * 0.995  # 0.5% below
            risk = entry_price - stop_loss

            # Calculate take profits
            tp1 = entry_price + risk * 2  # 1:2 RR
            tp2 = entry_price + risk * 3  # 1:3 RR
            tp3 = entry_price + risk * 5  # 1:5 RR
            take_profits = [tp1, tp2, tp3]
        else:  # SHORT
            stop_loss = signal['sweep_info']['swept_level'] * 1.005  # 0.5% above
            risk = stop_loss - entry_price

            # Calculate take profits
            tp1 = entry_price - risk * 2  # 1:2 RR
            tp2 = entry_price - risk * 3  # 1:3 RR
            tp3 = entry_price - risk * 5  # 1:5 RR
            take_profits = [tp1, tp2, tp3]

        # Calculate position size
        size = self.calculate_position_size(entry_price, stop_loss)

        trade = Trade(
            entry_time=signal['entry_time'],
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profits=take_profits,
            direction=direction,
            size=size,
            sweep_info=signal['sweep_info']
        )

        return trade

    def run_backtest(self, df_4h: pd.DataFrame, df_15m: pd.DataFrame,
                     start_date: Optional[str] = None,
                     end_date: Optional[str] = None) -> Dict:
        """
        Run backtest on historical data

        Args:
            df_4h: 4-hour DataFrame with OHLCV data
            df_15m: 15-minute DataFrame with OHLCV data
            start_date: Optional start date for backtest
            end_date: Optional end date for backtest

        Returns:
            Dictionary with backtest results
        """
        print("\n" + "="*80)
        print("🚀 STARTING LIQUIDITY REVERSAL BACKTEST")
        print("="*80)

        # Filter data by date if specified
        if start_date:
            df_4h = df_4h[df_4h.index >= start_date]
            df_15m = df_15m[df_15m.index >= start_date]
        if end_date:
            df_4h = df_4h[df_4h.index <= end_date]
            df_15m = df_15m[df_15m.index <= end_date]

        print(f"\n📊 Data Summary:")
        print(f"   4H candles: {len(df_4h)}")
        print(f"   15M candles: {len(df_15m)}")
        print(f"   Period: {df_4h.index[0]} to {df_4h.index[-1]}")
        print(f"\n💰 Starting Balance: ${self.initial_balance:,.2f}")
        print(f"   Risk per trade: {self.risk_per_trade*100}%")
        print(f"   Volume threshold: {self.volume_threshold}x")

        print("\n" + "-"*80)
        print("Running backtest...")
        print("-"*80 + "\n")

        # Convert 15m index to lookup for faster access
        idx_15m = 0

        # Iterate through 4H candles
        for idx_4h in range(self.sweep_detector.lookback + 5, len(df_4h)):
            current_time_4h = df_4h.index[idx_4h]

            # 1. Check for liquidity sweep on 4H
            sweep = self.sweep_detector.detect_liquidity_sweep(df_4h, idx_4h)

            if sweep:
                print(f"\n🎯 LIQUIDITY SWEEP DETECTED!")
                print(f"   Time: {sweep['sweep_time']}")
                print(f"   Type: {sweep['type']}")
                print(f"   Level: ${sweep['swept_level']:,.2f}")

                # Add to active sweeps
                self.active_sweeps.append(sweep)

            # 2. Check 15M candles for entry (process all 15m candles up to current 4h time)
            while idx_15m < len(df_15m) and df_15m.index[idx_15m] <= current_time_4h:

                # Check if we have active trade
                if self.active_trade:
                    # Check for exit
                    candle_15m = df_15m.iloc[idx_15m]
                    exit_reason = self.active_trade.check_exit(candle_15m)

                    if exit_reason:
                        if 'TP' in exit_reason:
                            # Partial exit
                            tp_level = int(exit_reason[2]) - 1
                            self.active_trade.close_partial(
                                df_15m.index[idx_15m],
                                self.active_trade.take_profits[tp_level],
                                tp_level
                            )

                            print(f"\n✅ {exit_reason} HIT!")
                            print(f"   Time: {df_15m.index[idx_15m]}")
                            print(f"   Price: ${self.active_trade.take_profits[tp_level]:,.2f}")
                            print(f"   Partial PnL: ${self.active_trade.partial_exits[-1]['pnl']:,.2f}")

                            if self.active_trade.status == 'CLOSED':
                                print(f"\n🎉 ALL TPs HIT - TRADE CLOSED")
                                print(f"   Total PnL: ${self.active_trade.pnl:,.2f}")

                                self.balance += self.active_trade.pnl
                                self.trades.append(self.active_trade)
                                self.update_stats(self.active_trade)
                                self.active_trade = None

                        else:  # SL
                            self.active_trade.close_full(
                                df_15m.index[idx_15m],
                                self.active_trade.stop_loss,
                                exit_reason
                            )

                            print(f"\n🛑 STOP LOSS HIT")
                            print(f"   Time: {df_15m.index[idx_15m]}")
                            print(f"   Price: ${self.active_trade.stop_loss:,.2f}")
                            print(f"   PnL: ${self.active_trade.pnl:,.2f}")

                            self.balance += self.active_trade.pnl
                            self.trades.append(self.active_trade)
                            self.update_stats(self.active_trade)
                            self.active_trade = None

                # Check for entry if no active trade
                elif len(self.active_sweeps) > 0:
                    # Check entry conditions for each active sweep
                    for sweep in self.active_sweeps[:]:  # Copy list to modify during iteration
                        signal = self.check_entry_conditions(df_15m, idx_15m, sweep)

                        if signal:
                            # Create trade
                            self.active_trade = self.create_trade(signal)
                            self.active_sweeps.remove(sweep)

                            print(f"\n📈 TRADE OPENED!")
                            print(f"   Time: {signal['entry_time']}")
                            print(f"   Direction: {signal['direction']}")
                            print(f"   Entry: ${signal['entry_price']:,.2f}")
                            print(f"   Stop Loss: ${self.active_trade.stop_loss:,.2f}")
                            print(f"   TP1: ${self.active_trade.take_profits[0]:,.2f} (1:2)")
                            print(f"   TP2: ${self.active_trade.take_profits[1]:,.2f} (1:3)")
                            print(f"   TP3: ${self.active_trade.take_profits[2]:,.2f} (1:5)")
                            print(f"   Size: {self.active_trade.size:.4f} BTC")
                            print(f"   Volume Ratio: {signal['volume_ratio']:.2f}x")
                            print(f"   FVG: {signal['fvg']['type']}, Size: ${signal['fvg']['size']:.2f}")

                            break

                idx_15m += 1

            # Clean up old sweeps (older than 48 hours)
            self.active_sweeps = [s for s in self.active_sweeps
                                 if (current_time_4h - s['sweep_time']).total_seconds() < 48*3600]

        # Close any remaining open trade
        if self.active_trade:
            last_candle = df_15m.iloc[-1]
            self.active_trade.close_full(
                df_15m.index[-1],
                last_candle['close'],
                'END_OF_BACKTEST'
            )
            self.balance += self.active_trade.pnl
            self.trades.append(self.active_trade)
            self.update_stats(self.active_trade)

        # Calculate final stats
        results = self.calculate_results()

        return results

    def update_stats(self, trade: Trade):
        """Update statistics after trade closes"""
        self.stats['total_trades'] += 1

        if trade.pnl > 0:
            self.stats['winning_trades'] += 1
        else:
            self.stats['losing_trades'] += 1

        self.stats['total_pnl'] += trade.pnl

        # Update max/min balance
        if self.balance > self.stats['max_balance']:
            self.stats['max_balance'] = self.balance
        if self.balance < self.stats['min_balance']:
            self.stats['min_balance'] = self.balance

        # Update max drawdown
        drawdown = (self.stats['max_balance'] - self.balance) / self.stats['max_balance']
        if drawdown > self.stats['max_drawdown']:
            self.stats['max_drawdown'] = drawdown

    def calculate_results(self) -> Dict:
        """Calculate final backtest results"""
        print("\n" + "="*80)
        print("📊 BACKTEST RESULTS")
        print("="*80)

        total_trades = self.stats['total_trades']
        winning_trades = self.stats['winning_trades']
        losing_trades = self.stats['losing_trades']

        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        final_balance = self.balance
        total_return = ((final_balance - self.initial_balance) / self.initial_balance) * 100

        # Calculate average win/loss
        winning_pnls = [t.pnl for t in self.trades if t.pnl > 0]
        losing_pnls = [t.pnl for t in self.trades if t.pnl < 0]

        avg_win = sum(winning_pnls) / len(winning_pnls) if winning_pnls else 0
        avg_loss = sum(losing_pnls) / len(losing_pnls) if losing_pnls else 0

        profit_factor = abs(sum(winning_pnls) / sum(losing_pnls)) if losing_pnls and sum(losing_pnls) != 0 else 0

        results = {
            'initial_balance': self.initial_balance,
            'final_balance': final_balance,
            'total_return': total_return,
            'total_pnl': self.stats['total_pnl'],
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_drawdown': self.stats['max_drawdown'] * 100,
            'trades': [t.to_dict() for t in self.trades]
        }

        # Print results
        print(f"\n💰 Financial Results:")
        print(f"   Initial Balance: ${self.initial_balance:,.2f}")
        print(f"   Final Balance: ${final_balance:,.2f}")
        print(f"   Total PnL: ${self.stats['total_pnl']:+,.2f}")
        print(f"   Total Return: {total_return:+.2f}%")

        print(f"\n📈 Trade Statistics:")
        print(f"   Total Trades: {total_trades}")
        print(f"   Winning Trades: {winning_trades}")
        print(f"   Losing Trades: {losing_trades}")
        print(f"   Win Rate: {win_rate:.2f}%")

        print(f"\n💵 Performance Metrics:")
        print(f"   Average Win: ${avg_win:,.2f}")
        print(f"   Average Loss: ${avg_loss:,.2f}")
        print(f"   Profit Factor: {profit_factor:.2f}")
        print(f"   Max Drawdown: {self.stats['max_drawdown']*100:.2f}%")

        print("\n" + "="*80)

        return results

    def save_results(self, results: Dict, filename: str = 'backtest_results.json'):
        """Save results to JSON file"""
        output_dir = Path('backtest_results')
        output_dir.mkdir(exist_ok=True)

        filepath = output_dir / filename

        with open(filepath, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        print(f"\n💾 Results saved to: {filepath}")

    def save_trades_csv(self, filename: str = 'trades.csv'):
        """Save trades to CSV file"""
        output_dir = Path('backtest_results')
        output_dir.mkdir(exist_ok=True)

        filepath = output_dir / filename

        trades_data = []
        for trade in self.trades:
            trades_data.append({
                'entry_time': trade.entry_time,
                'exit_time': trade.exit_time,
                'direction': trade.direction,
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'size': trade.size,
                'pnl': trade.pnl,
                'pnl_pct': trade.pnl_pct,
                'exit_reason': trade.exit_reason,
                'sweep_type': trade.sweep_info['type'] if trade.sweep_info else None
            })

        df = pd.DataFrame(trades_data)
        df.to_csv(filepath, index=False)

        print(f"💾 Trades saved to: {filepath}")


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                  LIQUIDITY SWEEP REVERSAL BACKTEST                           ║
║                                                                              ║
║  Strategy: Reversal after 4H liquidity sweep with 15M volume + FVG entry    ║
╚══════════════════════════════════════════════════════════════════════════════╝
""")

    # Initialize backtest
    backtest = LiquidityReversalBacktest(
        initial_balance=10000,
        risk_per_trade=0.02,  # 2% risk
        volume_threshold=1.5,  # 1.5x average volume
        sweep_lookback=20
    )

    print("\n⚠️  TO RUN BACKTEST:")
    print("\n1. Load your historical data:")
    print("   df_4h = pd.read_csv('btcusdt_4h.csv', parse_dates=['timestamp'], index_col='timestamp')")
    print("   df_15m = pd.read_csv('btcusdt_15m.csv', parse_dates=['timestamp'], index_col='timestamp')")
    print("\n2. Run backtest:")
    print("   results = backtest.run_backtest(df_4h, df_15m)")
    print("\n3. Save results:")
    print("   backtest.save_results(results)")
    print("   backtest.save_trades_csv()")
    print("\n" + "="*80)

    # Example with dummy data (won't work without real data)
    try:
        backtest.load_data()
    except NotImplementedError as e:
        print(f"\n{e}")
