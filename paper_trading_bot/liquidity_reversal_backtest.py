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
        """
        Find swing highs and lows using a more realistic approach
        
        Swing high: high is highest among left and right neighbors (smaller lookback)
        Swing low: low is lowest among left and right neighbors
        """
        swing_highs = pd.Series(index=df.index, dtype=float)
        swing_lows = pd.Series(index=df.index, dtype=float)

        # Use smaller lookback for swing detection (5 candles each side)
        swing_lookback = min(5, self.lookback // 2)
        
        for i in range(swing_lookback, len(df) - swing_lookback):
            current_high = df['high'].iloc[i]
            current_low = df['low'].iloc[i]
            
            # Check if current is swing high
            # Must be highest among left neighbors
            left_highs = [df['high'].iloc[i - j] for j in range(1, swing_lookback + 1)]
            right_highs = [df['high'].iloc[i + j] for j in range(1, swing_lookback + 1)]
            
            if current_high > max(left_highs) and current_high > max(right_highs):
                swing_highs.iloc[i] = current_high
            
            # Check if current is swing low
            # Must be lowest among left and right neighbors
            left_lows = [df['low'].iloc[i - j] for j in range(1, swing_lookback + 1)]
            right_lows = [df['low'].iloc[i + j] for j in range(1, swing_lookback + 1)]
            
            if current_low < min(left_lows) and current_low < min(right_lows):
                swing_lows.iloc[i] = current_low

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
                 sweep_lookback: int = 20,
                 volume_lookback: int = 20,
                 min_stop_loss_pct: float = 0.003,
                 max_position_size: float = None,
                 market_commission: float = 0.00045,
                 limit_commission: float = 0.00018,
                 use_limit_entry: bool = True):
        """
        Args:
            initial_balance: Starting capital in USDT
            risk_per_trade: Risk per trade as % of balance (0.02 = 2%)
            volume_threshold: Minimum volume ratio for entry (1.5 = 50% above avg)
            sweep_lookback: Lookback period for liquidity sweep detection
            volume_lookback: Lookback period for volume calculation (default: 20)
            min_stop_loss_pct: Minimum stop loss as % of entry price (0.003 = 0.3%) - filters out trades with very small SL
            max_position_size: Maximum position size in BTC (None = no limit)
            market_commission: Commission rate for market orders (0.00045 = 0.0450%)
            limit_commission: Commission rate for limit orders (0.00018 = 0.0180%)
            use_limit_entry: If True, use limit order at liquidity level for entry (cheaper). If False, use market order at candle close.
        """
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.risk_per_trade = risk_per_trade
        self.volume_threshold = volume_threshold
        self.volume_lookback = volume_lookback
        self.min_stop_loss_pct = min_stop_loss_pct
        self.max_position_size = max_position_size
        self.market_commission = market_commission
        self.limit_commission = limit_commission
        self.use_limit_entry = use_limit_entry

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
            'total_commission': 0,
            'max_balance': initial_balance,
            'min_balance': initial_balance,
            'max_drawdown': 0,
            'start_date': None,
            'end_date': None
        }
        
        # Diagnostics
        self.diagnostics = {
            'sweeps_detected': 0,
            'sweeps_checked_for_entry': 0,
            'failed_near_level': 0,
            'failed_reversal': 0,
            'failed_volume': 0,
            'failed_fvg': 0,
            'failed_fvg_type': 0,
            'failed_min_sl': 0,
            'failed_max_size': 0,
            'successful_entries': 0
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

        self.diagnostics['sweeps_checked_for_entry'] += 1

        candle = df_15m.iloc[idx_15m]

        # 1. Check if we're near the swept liquidity level
        liquidity_level = sweep_info['swept_level']
        tolerance = liquidity_level * 0.005  # Increased to 0.5% tolerance (was 0.2%)

        candle_near_level = (candle['low'] <= liquidity_level + tolerance and
                            candle['high'] >= liquidity_level - tolerance)

        if not candle_near_level:
            self.diagnostics['failed_near_level'] += 1
            return None

        # 2. Check for sharp reversal candle (relaxed requirements)
        is_bullish_reversal = False
        is_bearish_reversal = False

        if sweep_info['type'] == 'LOW':
            # After low sweep, look for bullish reversal
            is_bullish_reversal = self.reversal_detector.detect_bullish_reversal(df_15m, idx_15m, min_body_pct=0.5)  # Reduced from 0.6
        else:  # HIGH sweep
            # After high sweep, look for bearish reversal
            is_bearish_reversal = self.reversal_detector.detect_bearish_reversal(df_15m, idx_15m, min_body_pct=0.5)  # Reduced from 0.6

        if not (is_bullish_reversal or is_bearish_reversal):
            self.diagnostics['failed_reversal'] += 1
            return None

        # 3. Check volume (relaxed threshold)
        volume_ratio = self.volume_analyzer.calculate_volume_ratio(df_15m, idx_15m, lookback=self.volume_lookback)
        volume_threshold_relaxed = self.volume_threshold * 0.8  # 80% of original threshold
        
        if volume_ratio < volume_threshold_relaxed:
            self.diagnostics['failed_volume'] += 1
            return None

        # 4. Check for FVG (imbalance/weak) - make it optional or check nearby candles
        fvg = self.fvg_detector.detect_fvg(df_15m, idx_15m)
        
        # If no FVG at current candle, check previous 2 candles
        if not fvg and idx_15m >= 2:
            for check_idx in [idx_15m - 1, idx_15m - 2]:
                fvg = self.fvg_detector.detect_fvg(df_15m, check_idx)
                if fvg:
                    break

        if not fvg:
            self.diagnostics['failed_fvg'] += 1
            # Make FVG optional - continue without it if other conditions are strong
            # return None  # Commented out to make FVG optional

        # Check FVG type matches sweep type (only if FVG exists)
        if fvg:
            if sweep_info['type'] == 'LOW' and fvg['type'] != 'BULLISH':
                self.diagnostics['failed_fvg_type'] += 1
                # Make FVG type matching optional too
                # return None
            if sweep_info['type'] == 'HIGH' and fvg['type'] != 'BEARISH':
                self.diagnostics['failed_fvg_type'] += 1
                # return None

        # All conditions met!
        self.diagnostics['successful_entries'] += 1
        
        # Determine entry price based on order type
        if self.use_limit_entry:
            # Use limit order at liquidity level (cheaper commission)
            # For LONG: limit at or slightly above swept level
            # For SHORT: limit at or slightly below swept level
            liquidity_level = sweep_info['swept_level']
            if sweep_info['type'] == 'LOW':
                # LONG: limit at swept level (or slightly above for better fill)
                entry_price = liquidity_level * 1.0005  # 0.05% above for better fill
            else:  # HIGH
                # SHORT: limit at swept level (or slightly below for better fill)
                entry_price = liquidity_level * 0.9995  # 0.05% below for better fill
        else:
            # Use market order at candle close (current behavior)
            entry_price = candle['close']
        
        return {
            'direction': 'LONG' if sweep_info['type'] == 'LOW' else 'SHORT',
            'entry_price': entry_price,
            'entry_time': df_15m.index[idx_15m],
            'volume_ratio': volume_ratio,
            'fvg': fvg,
            'sweep_info': sweep_info,
            'entry_order_type': 'LIMIT' if self.use_limit_entry else 'MARKET'
        }

    def calculate_position_size(self, entry_price: float, stop_loss: float) -> Optional[float]:
        """
        Calculate position size based on risk
        
        Returns:
            Position size in BTC, or None if filters fail
        """
        risk_amount = self.balance * self.risk_per_trade
        risk_per_unit = abs(entry_price - stop_loss)

        if risk_per_unit == 0:
            return None

        # Filter: Minimum stop loss must be at least min_stop_loss_pct of entry price
        min_risk = entry_price * self.min_stop_loss_pct
        if risk_per_unit < min_risk:
            self.diagnostics['failed_min_sl'] = self.diagnostics.get('failed_min_sl', 0) + 1
            return None

        size = risk_amount / risk_per_unit
        
        # Filter: Maximum position size
        if self.max_position_size and size > self.max_position_size:
            self.diagnostics['failed_max_size'] = self.diagnostics.get('failed_max_size', 0) + 1
            return None
        
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

        # Calculate position size (with filters)
        size = self.calculate_position_size(entry_price, stop_loss)
        
        if size is None or size <= 0:
            # Trade filtered out due to size constraints
            return None

        trade = Trade(
            entry_time=signal['entry_time'],
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profits=take_profits,
            direction=direction,
            size=size,
            sweep_info=signal['sweep_info']
        )
        
        # Store entry order type for commission calculation
        trade.entry_order_type = signal.get('entry_order_type', 'MARKET')

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
        
        # Store dates for calculations
        self.stats['start_date'] = df_4h.index[0]
        self.stats['end_date'] = df_4h.index[-1]

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
                self.diagnostics['sweeps_detected'] += 1
                print(f"\n🎯 LIQUIDITY SWEEP DETECTED!")
                print(f"   Time: {sweep['sweep_time']}")
                print(f"   Type: {sweep['type']}")
                print(f"   Level: ${sweep['swept_level']:,.2f}")

                # Add to active sweeps
                self.active_sweeps.append(sweep)

            # 2. Process 15M candles up to current 4h time
            # This includes checking for exits and entries
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

                                # PnL already includes commission deduction in update_stats
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

                            # PnL already includes commission deduction in update_stats
                            self.trades.append(self.active_trade)
                            self.update_stats(self.active_trade)
                            self.active_trade = None

                # Check for entry if no active trade
                elif len(self.active_sweeps) > 0:
                    # Check entry conditions for each active sweep
                    # IMPORTANT: Only check entries AFTER the sweep time
                    current_15m_time = df_15m.index[idx_15m]
                    
                    for sweep in self.active_sweeps[:]:  # Copy list to modify during iteration
                        # Only check for entry if 15M candle is AFTER the sweep time
                        if current_15m_time < sweep['sweep_time']:
                            continue
                            
                        # Also check if sweep is not too old (within 48 hours)
                        time_since_sweep = (current_15m_time - sweep['sweep_time']).total_seconds() / 3600
                        if time_since_sweep > 48:
                            continue
                        
                        signal = self.check_entry_conditions(df_15m, idx_15m, sweep)

                        if signal:
                            # Create trade (may return None if filtered by size)
                            trade = self.create_trade(signal)
                            
                            if trade is None:
                                # Trade filtered out (too small SL or too large size)
                                continue
                            
                            self.active_trade = trade
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
                            if signal['fvg']:
                                print(f"   FVG: {signal['fvg']['type']}, Size: ${signal['fvg']['size']:.2f}")
                            else:
                                print(f"   FVG: None (optional)")

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
            # PnL already includes commission deduction in update_stats
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

        # Calculate commission (round-trip: entry + exit)
        # Entry: Check if limit or market order was used
        # Get entry order type from trade metadata (if available) or use default
        entry_order_type = getattr(trade, 'entry_order_type', 'MARKET' if not self.use_limit_entry else 'LIMIT')
        
        if entry_order_type == 'LIMIT':
            # Entry: Limit order (0.0180%)
            entry_commission = trade.entry_price * trade.size * self.limit_commission
        else:
            # Entry: Market order (0.0450%)
            entry_commission = trade.entry_price * trade.size * self.market_commission
        
        # Exit commission - calculate based on how trade was closed
        total_exit_commission = 0
        if trade.partial_exits:
            # Trade closed via partial exits (TPs are limit orders, 0.25%)
            for partial in trade.partial_exits:
                total_exit_commission += partial['price'] * partial['size'] * self.limit_commission
        elif trade.exit_price:
            # Trade closed fully
            if trade.exit_reason == 'SL':
                # Stop loss: Market order (0.55%)
                total_exit_commission = trade.exit_price * trade.size * self.market_commission
            else:
                # TP or other: Limit order (0.25%)
                total_exit_commission = trade.exit_price * trade.size * self.limit_commission
        
        total_commission = entry_commission + total_exit_commission
        self.stats['total_commission'] = self.stats.get('total_commission', 0) + total_commission
        
        # Net PnL (after commission)
        net_pnl = trade.pnl - total_commission
        self.stats['total_pnl'] += net_pnl
        self.balance += net_pnl
        
        # Store commission in trade for later analysis
        trade.total_commission = total_commission

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
        
        # Calculate R multiples (risk-reward ratios)
        # R = PnL / Risk Amount (where Risk = entry_price - stop_loss for LONG, stop_loss - entry_price for SHORT)
        winning_rs = []
        losing_rs = []
        for trade in self.trades:
            # Calculate actual risk for this trade
            if trade.direction == 'LONG':
                risk_amount = abs(trade.entry_price - trade.stop_loss) * trade.size
            else:  # SHORT
                risk_amount = abs(trade.stop_loss - trade.entry_price) * trade.size
            
            # R multiple = PnL / Risk
            r_multiple = trade.pnl / risk_amount if risk_amount > 0 else 0
            if trade.pnl > 0:
                winning_rs.append(r_multiple)
            else:
                losing_rs.append(abs(r_multiple))
        
        avg_winning_r = sum(winning_rs) / len(winning_rs) if winning_rs else 0
        avg_losing_r = sum(losing_rs) / len(losing_rs) if losing_rs else 0
        
        # Expected Value (EV) = (avg winning R * winrate) - (avg losing R * lossrate)
        winrate_decimal = winning_trades / total_trades if total_trades > 0 else 0
        lossrate_decimal = losing_trades / total_trades if total_trades > 0 else 0
        expected_value = (avg_winning_r * winrate_decimal) - (avg_losing_r * lossrate_decimal)
        
        # Calculate commission metrics
        total_commission = self.stats.get('total_commission', 0)
        avg_commission_per_trade = total_commission / total_trades if total_trades > 0 else 0
        avg_commission_pct = (avg_commission_per_trade / self.initial_balance) * 100 if total_trades > 0 else 0
        
        # Calculate trades per month
        if self.stats.get('start_date') and self.stats.get('end_date'):
            start_date = self.stats['start_date']
            end_date = self.stats['end_date']
            days = (end_date - start_date).days
            months = days / 30.44  # Average days per month
            trades_per_month = total_trades / months if months > 0 else 0
        else:
            trades_per_month = 0

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
            'avg_commission_per_trade': avg_commission_per_trade,
            'avg_commission_pct': avg_commission_pct,
            'total_commission': total_commission,
            'trades_per_month': trades_per_month,
            'avg_winning_r': avg_winning_r,
            'avg_losing_r': avg_losing_r,
            'expected_value': expected_value,
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
        
        print(f"\n📊 Additional Metrics:")
        print(f"   Avg Commission per Trade: ${avg_commission_per_trade:.2f} ({avg_commission_pct:.3f}% of deposit)")
        print(f"   Total Commission: ${total_commission:,.2f}")
        print(f"   Avg Trades per Month: {trades_per_month:.2f}")
        print(f"   Avg Winning R: {avg_winning_r:.2f}")
        print(f"   Avg Losing R: {avg_losing_r:.2f}")
        print(f"   Expected Value (EV): {expected_value:.3f} R")

        print(f"\n🔍 Diagnostics:")
        print(f"   Sweeps Detected: {self.diagnostics['sweeps_detected']}")
        print(f"   Sweeps Checked for Entry: {self.diagnostics['sweeps_checked_for_entry']}")
        if self.diagnostics['sweeps_checked_for_entry'] > 0:
            print(f"   Entry Check Rate: {self.diagnostics['sweeps_checked_for_entry'] / max(1, self.diagnostics['sweeps_detected']) * 100:.1f}%")
        print(f"   Failed - Not Near Level: {self.diagnostics['failed_near_level']}")
        print(f"   Failed - No Reversal: {self.diagnostics['failed_reversal']}")
        print(f"   Failed - Low Volume: {self.diagnostics['failed_volume']}")
        print(f"   Failed - No FVG: {self.diagnostics['failed_fvg']}")
        print(f"   Failed - FVG Type Mismatch: {self.diagnostics['failed_fvg_type']}")
        print(f"   Failed - Min SL Filter: {self.diagnostics.get('failed_min_sl', 0)}")
        print(f"   Failed - Max Size Filter: {self.diagnostics.get('failed_max_size', 0)}")
        print(f"   Successful Entries: {self.diagnostics['successful_entries']}")
        
        if self.diagnostics['sweeps_detected'] > 0 and self.diagnostics['successful_entries'] == 0:
            print(f"\n⚠️  WARNING: Found {self.diagnostics['sweeps_detected']} sweeps but 0 entries!")
            print(f"   Most common failure: ", end="")
            failures = {
                'Not Near Level': self.diagnostics['failed_near_level'],
                'No Reversal': self.diagnostics['failed_reversal'],
                'Low Volume': self.diagnostics['failed_volume'],
                'No FVG': self.diagnostics['failed_fvg'],
                'FVG Type Mismatch': self.diagnostics['failed_fvg_type'],
                'Min SL Filter': self.diagnostics.get('failed_min_sl', 0),
                'Max Size Filter': self.diagnostics.get('failed_max_size', 0)
            }
            max_failure = max(failures.items(), key=lambda x: x[1])
            print(f"{max_failure[0]} ({max_failure[1]} times)")

        print("\n" + "="*80)

        # Add diagnostics to results
        results['diagnostics'] = self.diagnostics

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
