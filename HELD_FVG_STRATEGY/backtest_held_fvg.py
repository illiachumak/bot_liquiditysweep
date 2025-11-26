"""
Backtest HELD 4H FVG Strategy - Протилежна до Failed FVG
Tests all combinations of entry and TP methods

Entry Methods:
  A. Immediate 4H Close
  B. 15M FVG
  C. 15M Breakout

TP Methods:
  1. Liquidity-based
  2. Fixed RR 2.0
  3. Fixed RR 3.0

Total: 9 combinations to compare
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import json
import requests
import time


class HeldBacktestFVG:
    """FVG class for backtesting HELD strategy"""
    def __init__(self, fvg_type: str, top: float, bottom: float,
                 formed_time: pd.Timestamp, timeframe: str, index: int):
        self.type = fvg_type
        self.top = top
        self.bottom = bottom
        self.formed_time = formed_time
        self.timeframe = timeframe
        self.index = index

        self.entered = False
        self.held = False  # Changed from rejected
        self.invalidated = False

        self.hold_time = None  # Changed from rejection_time
        self.hold_price = None  # Changed from rejection_price

        self.highs_inside = []
        self.lows_inside = []

        # Track if we already had a filled trade from this hold
        self.has_filled_trade = False
        self.pending_setup_expiry_time = None

        self.id = f"{timeframe}_{fvg_type}_{top:.2f}_{bottom:.2f}_{int(formed_time.timestamp())}"

    def is_inside(self, price: float) -> bool:
        return self.bottom <= price <= self.top

    def is_fully_passed(self, candle_high: float, candle_low: float) -> bool:
        """Invalidation для held strategy - протилежна до failed"""
        if self.type == 'BULLISH':
            # Bullish FVG invalidated якщо ціна пройшла НИЖЧЕ
            return candle_low < self.bottom
        else:
            # Bearish FVG invalidated якщо ціна пройшла ВИЩЕ
            return candle_high > self.top

    def check_hold(self, candle: pd.Series, debug: bool = False) -> bool:
        """
        Check if FVG is HELD (opposite of rejection)

        Bullish FVG held: price entered and closed INSIDE or ABOVE
        Bearish FVG held: price entered and closed INSIDE or BELOW
        """
        candle_high = candle['High']
        candle_low = candle['Low']
        candle_close = candle['Close']

        # Check if touched
        touched = not (candle_high < self.bottom or candle_low > self.top)

        if not touched:
            return False

        if not self.entered:
            self.entered = True
            if debug:
                print(f"  ✅ {self.timeframe} {self.type} FVG entered: ${self.bottom:.2f}-${self.top:.2f}, Close: ${candle_close:.2f}")

        # Track highs/lows inside for SL calculation
        if candle_high >= self.bottom:
            self.highs_inside.append(candle_high)
        if candle_low <= self.top:
            self.lows_inside.append(candle_low)

        if self.type == 'BULLISH':
            # Bullish FVG HOLD = close INSIDE zone (zone held price, didn't break through)
            if self.entered and self.bottom <= candle_close <= self.top:
                if not self.held:
                    self.held = True
                    self.hold_time = candle.name
                    self.hold_price = candle_close
                    if debug:
                        print(f"  💚 BULLISH FVG HELD! Close ${candle_close:.2f} inside zone ${self.bottom:.2f}-${self.top:.2f}")
                    return True
            elif self.entered and debug:
                if candle_close < self.bottom:
                    print(f"  ❌ BULLISH FVG rejected: Close ${candle_close:.2f} < Bottom ${self.bottom:.2f}")
                elif candle_close > self.top:
                    print(f"  ⚡ BULLISH FVG broken through: Close ${candle_close:.2f} > Top ${self.top:.2f}")
        else:  # BEARISH
            # Bearish FVG HOLD = close INSIDE zone (zone held price, didn't break through)
            if self.entered and self.bottom <= candle_close <= self.top:
                if not self.held:
                    self.held = True
                    self.hold_time = candle.name
                    self.hold_price = candle_close
                    if debug:
                        print(f"  💚 BEARISH FVG HELD! Close ${candle_close:.2f} inside zone ${self.bottom:.2f}-${self.top:.2f}")
                    return True
            elif self.entered and debug:
                if candle_close > self.top:
                    print(f"  ❌ BEARISH FVG rejected: Close ${candle_close:.2f} > Top ${self.top:.2f}")
                elif candle_close < self.bottom:
                    print(f"  ⚡ BEARISH FVG broken through: Close ${candle_close:.2f} < Bottom ${self.bottom:.2f}")

        return False

    def get_stop_loss_for_held(self) -> Optional[float]:
        """
        Get SL for HELD strategy (opposite side from failed)

        BULLISH FVG held → LONG → SL below zone
        BEARISH FVG held → SHORT → SL above zone
        """
        if self.type == 'BULLISH':
            # LONG setup: SL = lowest low inside zone
            if self.lows_inside:
                return min(self.lows_inside) * 0.998  # -0.2% buffer
            else:
                return self.bottom * 0.998
        else:
            # SHORT setup: SL = highest high inside zone
            if self.highs_inside:
                return max(self.highs_inside) * 1.002  # +0.2% buffer
            else:
                return self.top * 1.002


class BacktestTrade:
    """Trade object for simulation"""
    def __init__(self, direction: str, entry: float, sl: float, tp: float,
                 size: float, entry_time: pd.Timestamp,
                 entry_method: str, tp_method: str):
        self.direction = direction
        self.entry = entry
        self.sl = sl
        self.tp = tp
        self.size = size
        self.entry_time = entry_time
        self.entry_method = entry_method
        self.tp_method = tp_method

        self.exit_time = None
        self.exit_price = None
        self.exit_reason = None
        self.pnl = 0.0
        self.pnl_pct = 0.0
        self.active = True

    def close(self, exit_price: float, exit_time: pd.Timestamp, reason: str,
              enable_fees: bool = True, maker_fee: float = 0.00018, taker_fee: float = 0.00045):
        """Close trade and calculate PnL"""
        self.active = False
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.exit_reason = reason

        # Calculate gross PnL
        if self.direction == 'LONG':
            gross_pnl = (exit_price - self.entry) * self.size
        else:  # SHORT
            gross_pnl = (self.entry - exit_price) * self.size

        # Calculate fees
        if enable_fees:
            # Entry fee depends on entry method
            if self.entry_method == '4h_close':
                entry_fee = self.entry * self.size * taker_fee  # Market order
            else:
                entry_fee = self.entry * self.size * maker_fee  # Limit order

            # Exit fee
            if reason == 'TP':
                exit_fee = exit_price * self.size * maker_fee
            else:  # SL or TIMEOUT
                exit_fee = exit_price * self.size * taker_fee

            net_pnl = gross_pnl - entry_fee - exit_fee
        else:
            net_pnl = gross_pnl

        self.pnl = net_pnl
        self.pnl_pct = (net_pnl / (self.entry * self.size)) * 100 if self.entry * self.size != 0 else 0

    def to_dict(self) -> Dict:
        return {
            'direction': self.direction,
            'entry_method': self.entry_method,
            'tp_method': self.tp_method,
            'entry': self.entry,
            'sl': self.sl,
            'tp': self.tp,
            'size': self.size,
            'entry_time': str(self.entry_time),
            'exit_time': str(self.exit_time) if self.exit_time else None,
            'exit_price': self.exit_price,
            'exit_reason': self.exit_reason,
            'pnl': self.pnl,
            'pnl_pct': self.pnl_pct,
        }


class HeldFVGBacktester:
    """Backtest engine for HELD FVG strategy with multiple entry/TP methods"""

    def __init__(self, initial_balance: float = 300.0, risk_per_trade: float = 0.02,
                 min_sl_pct: float = 0.3, max_sl_pct: float = 5.0,
                 enable_fees: bool = True):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.risk_per_trade = risk_per_trade
        self.min_sl_pct = min_sl_pct
        self.max_sl_pct = max_sl_pct
        self.enable_fees = enable_fees

        self.maker_fee = 0.00018  # 0.018%
        self.taker_fee = 0.00045  # 0.045%

        # FVG tracking
        self.active_4h_fvgs: List[HeldBacktestFVG] = []
        self.held_4h_fvgs: List[HeldBacktestFVG] = []  # Changed from rejected

        # Trade tracking
        self.trades: List[BacktestTrade] = []
        self.active_trade = None

    def detect_fvg(self, df: pd.DataFrame, start_idx: int, end_idx: int,
                   timeframe: str = '4h') -> List[HeldBacktestFVG]:
        """Detect FVGs in candle data"""
        fvgs = []

        for i in range(start_idx + 2, end_idx):
            if i < 2:
                continue

            candle = df.iloc[i]
            candle_prev = df.iloc[i-1]
            candle_prev2 = df.iloc[i-2]

            # Bullish FVG
            if candle['Low'] > candle_prev2['High']:
                fvg = HeldBacktestFVG(
                    fvg_type='BULLISH',
                    top=candle['Low'],
                    bottom=candle_prev2['High'],
                    formed_time=candle.name,
                    timeframe=timeframe,
                    index=i
                )
                fvgs.append(fvg)

            # Bearish FVG
            elif candle['High'] < candle_prev2['Low']:
                fvg = HeldBacktestFVG(
                    fvg_type='BEARISH',
                    top=candle_prev2['Low'],
                    bottom=candle['High'],
                    formed_time=candle.name,
                    timeframe=timeframe,
                    index=i
                )
                fvgs.append(fvg)

        return fvgs

    def update_4h_fvgs(self, df_4h: pd.DataFrame, current_idx: int, debug: bool = False) -> Tuple[int, int]:
        """Update 4H FVGs - detect new ones and check for holds"""
        newly_added = 0
        newly_held = 0

        # Detect new FVGs at current index
        # Need to look back from start to current_idx to detect FVG at current_idx
        start_idx = max(0, current_idx - 10)  # Look back a bit
        new_fvgs = self.detect_fvg(df_4h, start_idx, current_idx + 1, timeframe='4h')

        if debug and current_idx < 20:
            print(f"  Index {current_idx}: detected {len(new_fvgs)} FVGs")

        for fvg in new_fvgs:
            # Only add FVGs formed at current index
            if fvg.index == current_idx:
                if not any(existing.id == fvg.id for existing in self.active_4h_fvgs):
                    self.active_4h_fvgs.append(fvg)
                    newly_added += 1
                    if debug and current_idx < 20:
                        print(f"    Added {fvg.type} FVG: ${fvg.bottom:.0f}-${fvg.top:.0f}")

        # Check active FVGs for hold/invalidation
        for fvg in self.active_4h_fvgs[:]:
            candle = df_4h.iloc[current_idx]

            # Check hold
            if fvg.check_hold(candle):
                self.held_4h_fvgs.append(fvg)
                self.active_4h_fvgs.remove(fvg)
                newly_held += 1

            # Check invalidation
            elif fvg.is_fully_passed(candle['High'], candle['Low']):
                fvg.invalidated = True
                self.active_4h_fvgs.remove(fvg)

        return newly_added, newly_held

    def find_liquidity(self, df: pd.DataFrame, current_idx: int, direction: str,
                      lookback: int = 30) -> Optional[float]:
        """Find liquidity zones (swing highs/lows) for TP"""
        start_idx = max(0, current_idx - lookback)

        if direction == 'LONG':
            # Look for swing high
            for i in range(current_idx - 1, start_idx, -1):
                if i < 2 or i >= len(df) - 2:
                    continue

                candle = df.iloc[i]
                is_swing_high = True

                # Check if this high is higher than surrounding candles
                for j in range(max(0, i-2), min(len(df), i+3)):
                    if j != i and df.iloc[j]['High'] > candle['High']:
                        is_swing_high = False
                        break

                if is_swing_high:
                    return candle['High'] * 0.999  # -0.1% buffer

        else:  # SHORT
            # Look for swing low
            for i in range(current_idx - 1, start_idx, -1):
                if i < 2 or i >= len(df) - 2:
                    continue

                candle = df.iloc[i]
                is_swing_low = True

                # Check if this low is lower than surrounding candles
                for j in range(max(0, i-2), min(len(df), i+3)):
                    if j != i and df.iloc[j]['Low'] < candle['Low']:
                        is_swing_low = False
                        break

                if is_swing_low:
                    return candle['Low'] * 1.001  # +0.1% buffer

        return None

    def calculate_tp(self, entry: float, sl: float, direction: str, tp_method: str,
                    df_15m: pd.DataFrame, current_idx: int) -> Optional[float]:
        """Calculate TP based on method"""
        risk = abs(entry - sl)

        if tp_method == 'liquidity':
            # Find liquidity zone
            tp = self.find_liquidity(df_15m, current_idx, direction, lookback=30)

            # Validate RR
            if tp:
                rr = abs(tp - entry) / risk
                if rr < 1.5:  # Min RR for liquidity
                    return None
                if rr > 10.0:  # Max RR (cap it)
                    if direction == 'LONG':
                        tp = entry + risk * 10.0
                    else:
                        tp = entry - risk * 10.0

            return tp

        elif tp_method == 'rr_2.0':
            # Fixed RR = 2.0
            if direction == 'LONG':
                return entry + risk * 2.0
            else:
                return entry - risk * 2.0

        elif tp_method == 'rr_3.0':
            # Fixed RR = 3.0
            if direction == 'LONG':
                return entry + risk * 3.0
            else:
                return entry - risk * 3.0

        return None

    def create_setup(self, held_fvg: HeldBacktestFVG, df_15m: pd.DataFrame,
                    current_15m_idx: int, entry_method: str, tp_method: str,
                    current_price: float) -> Optional[Dict]:
        """
        Create setup for a held FVG based on entry and TP method

        Returns dict with entry, sl, tp, direction if valid, else None
        """
        # Determine direction (opposite of failed FVG!)
        # BULLISH FVG held → LONG (price continued up)
        # BEARISH FVG held → SHORT (price continued down)
        direction = 'LONG' if held_fvg.type == 'BULLISH' else 'SHORT'

        entry = None
        sl = None

        # Calculate entry based on method
        if entry_method == '4h_close':
            # Immediate entry at hold price (4H close)
            entry = held_fvg.hold_price
            sl = held_fvg.get_stop_loss_for_held()

        elif entry_method == '15m_fvg':
            # Look for 15M FVG in direction of trade
            lookback_start = max(0, current_15m_idx - 10)
            fvgs_15m = self.detect_fvg(df_15m, lookback_start, current_15m_idx + 1, timeframe='15m')

            if not fvgs_15m:
                return None

            # Find FVG of matching type (SAME as 4H for held strategy!)
            matching_fvgs = [f for f in fvgs_15m if f.type == held_fvg.type]
            if not matching_fvgs:
                return None

            fvg_15m = matching_fvgs[-1]  # Latest

            # Entry at edge of 15M FVG
            if direction == 'LONG':
                entry = fvg_15m.bottom  # Enter at bottom for LONG
                sl = fvg_15m.bottom * 0.998  # SL below
            else:  # SHORT
                entry = fvg_15m.top  # Enter at top for SHORT
                sl = fvg_15m.top * 1.002  # SL above

        elif entry_method == '15m_breakout':
            # Entry at breakout of 4H candle that held
            # Need to find the 4H candle high/low
            # For simplicity, use hold_price with buffer
            if direction == 'LONG':
                entry = held_fvg.hold_price * 1.001  # +0.1% above
            else:
                entry = held_fvg.hold_price * 0.999  # -0.1% below

            sl = held_fvg.get_stop_loss_for_held()

        if entry is None or sl is None:
            return None

        # Validate SL distance
        sl_distance_pct = abs(entry - sl) / entry * 100
        if sl_distance_pct < self.min_sl_pct or sl_distance_pct > self.max_sl_pct:
            return None

        # Calculate TP
        tp = self.calculate_tp(entry, sl, direction, tp_method, df_15m, current_15m_idx)
        if tp is None:
            return None

        # Validate RR
        rr = abs(tp - entry) / abs(entry - sl)
        min_rr = 1.5 if tp_method == 'liquidity' else 2.0
        if rr < min_rr:
            return None

        # Validate entry price sanity
        entry_distance_pct = abs(entry - current_price) / current_price * 100
        if entry_distance_pct > 5.0:
            return None

        # Calculate position size
        risk_amount = self.balance * self.risk_per_trade
        risk_per_unit = abs(entry - sl)
        size = risk_amount / risk_per_unit

        # Check minimum notional
        notional = entry * size
        if notional < 10.0:
            return None

        return {
            'direction': direction,
            'entry': entry,
            'sl': sl,
            'tp': tp,
            'size': size,
            'entry_method': entry_method,
            'tp_method': tp_method
        }

    def simulate_trade(self, setup: Dict, df_15m: pd.DataFrame, entry_idx: int,
                      entry_method: str) -> BacktestTrade:
        """Simulate trade execution"""

        trade = BacktestTrade(
            direction=setup['direction'],
            entry=setup['entry'],
            sl=setup['sl'],
            tp=setup['tp'],
            size=setup['size'],
            entry_time=df_15m.index[entry_idx],
            entry_method=entry_method,
            tp_method=setup['tp_method']
        )

        # For immediate entry (4h_close), fill immediately
        if entry_method == '4h_close':
            trade.entry_time = df_15m.index[entry_idx]
            start_idx = entry_idx

        # For limit orders (15m_fvg, 15m_breakout), check if filled within 16 candles
        else:
            filled = False
            fill_idx = entry_idx

            for i in range(entry_idx, min(entry_idx + 16, len(df_15m))):
                candle = df_15m.iloc[i]

                # Check if price hit entry level
                if setup['direction'] == 'LONG':
                    if candle['Low'] <= setup['entry']:
                        filled = True
                        fill_idx = i
                        trade.entry_time = candle.name
                        break
                else:  # SHORT
                    if candle['High'] >= setup['entry']:
                        filled = True
                        fill_idx = i
                        trade.entry_time = candle.name
                        break

            # If not filled, close as expired
            if not filled:
                trade.close(setup['entry'], df_15m.index[min(entry_idx + 15, len(df_15m) - 1)],
                           'EXPIRED', enable_fees=False)
                return trade

            start_idx = fill_idx + 1

        # Simulate trade until TP/SL/timeout
        max_candles = 500  # Max 500 * 15m = ~5 days

        for i in range(start_idx, min(start_idx + max_candles, len(df_15m))):
            candle = df_15m.iloc[i]

            if trade.direction == 'LONG':
                # Check SL first
                if candle['Low'] <= trade.sl:
                    trade.close(trade.sl, candle.name, 'SL',
                               enable_fees=self.enable_fees,
                               maker_fee=self.maker_fee,
                               taker_fee=self.taker_fee)
                    break

                # Check TP
                if candle['High'] >= trade.tp:
                    trade.close(trade.tp, candle.name, 'TP',
                               enable_fees=self.enable_fees,
                               maker_fee=self.maker_fee,
                               taker_fee=self.taker_fee)
                    break

            else:  # SHORT
                # Check SL first
                if candle['High'] >= trade.sl:
                    trade.close(trade.sl, candle.name, 'SL',
                               enable_fees=self.enable_fees,
                               maker_fee=self.maker_fee,
                               taker_fee=self.taker_fee)
                    break

                # Check TP
                if candle['Low'] <= trade.tp:
                    trade.close(trade.tp, candle.name, 'TP',
                               enable_fees=self.enable_fees,
                               maker_fee=self.maker_fee,
                               taker_fee=self.taker_fee)
                    break

        # If still active, close at timeout
        if trade.active:
            last_candle = df_15m.iloc[min(start_idx + max_candles - 1, len(df_15m) - 1)]
            trade.close(last_candle['Close'], last_candle.name, 'TIMEOUT',
                       enable_fees=self.enable_fees,
                       maker_fee=self.maker_fee,
                       taker_fee=self.taker_fee)

        return trade

    def run_single_combination(self, df_4h: pd.DataFrame, df_15m: pd.DataFrame,
                              start_date: str, end_date: str,
                              entry_method: str, tp_method: str) -> Dict:
        """Run backtest for a single entry/TP combination"""

        # Reset state
        self.balance = self.initial_balance
        self.active_4h_fvgs = []
        self.held_4h_fvgs = []
        self.trades = []
        self.active_trade = None

        # Filter data
        df_4h_filtered = df_4h.loc[start_date:end_date].copy()
        df_15m_filtered = df_15m.loc[start_date:end_date].copy()

        current_15m_idx = 0

        stats = {
            'total_4h_fvgs': 0,
            'total_holds': 0,
            'setups_created': 0,
            'fills': 0,
            'no_fills': 0,
        }

        # Iterate through 4H candles
        debug_mode = (entry_method == '4h_close' and tp_method == 'liquidity')  # Only debug first combo

        for i in range(len(df_4h_filtered)):
            current_4h_time = df_4h_filtered.index[i]

            # Update 4H FVGs
            newly_added, newly_held = self.update_4h_fvgs(df_4h_filtered, i, debug=debug_mode)
            stats['total_4h_fvgs'] += newly_added
            stats['total_holds'] += newly_held

            # Find corresponding 15M candles
            next_4h_time = df_4h_filtered.index[i+1] if i+1 < len(df_4h_filtered) else df_15m_filtered.index[-1]

            # Process 15M candles in this 4H period
            while current_15m_idx < len(df_15m_filtered) and df_15m_filtered.index[current_15m_idx] < next_4h_time:

                # Check for setups (only if no active trade)
                if not self.active_trade:
                    current_time = df_15m_filtered.index[current_15m_idx]
                    current_candle = df_15m_filtered.iloc[current_15m_idx]
                    current_price = current_candle['Close']

                    for held_fvg in self.held_4h_fvgs[:]:

                        # Skip if already had filled trade
                        if held_fvg.has_filled_trade:
                            continue

                        # Check invalidation
                        if held_fvg.is_fully_passed(current_candle['High'], current_candle['Low']):
                            held_fvg.invalidated = True
                            self.held_4h_fvgs.remove(held_fvg)
                            continue

                        # Skip if pending setup not expired
                        if held_fvg.pending_setup_expiry_time:
                            if current_time < held_fvg.pending_setup_expiry_time:
                                continue

                        # Create setup
                        setup = self.create_setup(held_fvg, df_15m_filtered, current_15m_idx,
                                                 entry_method, tp_method, current_price)

                        if setup:
                            stats['setups_created'] += 1

                            # Set expiry time for limit orders
                            if entry_method != '4h_close':
                                expiry_idx = min(current_15m_idx + 16, len(df_15m_filtered) - 1)
                                held_fvg.pending_setup_expiry_time = df_15m_filtered.index[expiry_idx]

                            # Simulate trade
                            trade = self.simulate_trade(setup, df_15m_filtered, current_15m_idx, entry_method)

                            # Track trade
                            if trade.exit_reason != 'EXPIRED':
                                stats['fills'] += 1
                                held_fvg.has_filled_trade = True
                                self.trades.append(trade)
                                self.balance += trade.pnl

                                # Jump forward in time to after trade closes
                                close_idx = df_15m_filtered.index.get_loc(trade.exit_time)
                                current_15m_idx = close_idx
                                break
                            else:
                                stats['no_fills'] += 1

                current_15m_idx += 1

        # Calculate results
        results = self.calculate_results(entry_method, tp_method, stats)

        # Debug output
        print(f"  Debug: 4H FVGs={stats['total_4h_fvgs']}, Holds={stats['total_holds']}, "
              f"Setups={stats['setups_created']}, Fills={stats['fills']}, NoFills={stats['no_fills']}")

        return results

    def calculate_results(self, entry_method: str, tp_method: str, stats: Dict) -> Dict:
        """Calculate backtest results"""

        total_trades = len(self.trades)

        if total_trades == 0:
            return {
                'entry_method': entry_method,
                'tp_method': tp_method,
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0.0,
                'avg_win': 0.0,
                'avg_loss': 0.0,
                'total_pnl': 0.0,
                'final_balance': self.initial_balance,
                'max_drawdown': 0.0,
                'profit_factor': 0.0,
                'stats': stats,
                'trades': []
            }

        winning_trades = [t for t in self.trades if t.pnl > 0]
        losing_trades = [t for t in self.trades if t.pnl <= 0]

        win_rate = len(winning_trades) / total_trades * 100
        avg_win = sum(t.pnl for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t.pnl for t in losing_trades) / len(losing_trades) if losing_trades else 0

        total_pnl = sum(t.pnl for t in self.trades)

        # Calculate max drawdown
        balance_curve = [self.initial_balance]
        for trade in self.trades:
            balance_curve.append(balance_curve[-1] + trade.pnl)

        peak = balance_curve[0]
        max_dd = 0
        for balance in balance_curve:
            if balance > peak:
                peak = balance
            dd = (peak - balance) / peak * 100 if peak > 0 else 0
            max_dd = max(max_dd, dd)

        # Profit factor
        total_wins = sum(t.pnl for t in winning_trades)
        total_losses = abs(sum(t.pnl for t in losing_trades))
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')

        return {
            'entry_method': entry_method,
            'tp_method': tp_method,
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'total_pnl': total_pnl,
            'final_balance': self.initial_balance + total_pnl,
            'max_drawdown': max_dd,
            'profit_factor': profit_factor,
            'stats': stats,
            'trades': [t.to_dict() for t in self.trades]
        }

    def run_all_combinations(self, df_4h: pd.DataFrame, df_15m: pd.DataFrame,
                            start_date: str, end_date: str) -> Dict:
        """Run all 9 combinations and compare"""

        print(f"\n{'='*80}")
        print(f"HELD 4H FVG BACKTEST - ALL COMBINATIONS")
        print(f"{'='*80}")
        print(f"Period: {start_date} to {end_date}")
        print(f"Initial Balance: ${self.initial_balance:,.2f}")
        print(f"Risk per Trade: {self.risk_per_trade*100}%")
        print(f"{'='*80}\n")

        entry_methods = ['4h_close', '15m_fvg', '15m_breakout']
        tp_methods = ['liquidity', 'rr_2.0', 'rr_3.0']

        all_results = []

        for entry_method in entry_methods:
            for tp_method in tp_methods:
                print(f"\n▶ Testing: Entry={entry_method}, TP={tp_method}")

                result = self.run_single_combination(df_4h, df_15m, start_date, end_date,
                                                     entry_method, tp_method)
                all_results.append(result)

                print(f"  Trades: {result['total_trades']}, "
                      f"Win Rate: {result['win_rate']:.1f}%, "
                      f"Total PnL: ${result['total_pnl']:.2f}")

        # Print comparison table
        print(f"\n{'='*80}")
        print("COMPARISON TABLE")
        print(f"{'='*80}\n")

        print(f"{'ID':<4} {'Entry':<15} {'TP':<12} {'Trades':<8} {'Win%':<8} "
              f"{'PnL':<10} {'Final':<10} {'MaxDD%':<8} {'PF':<6}")
        print("-" * 100)

        for i, result in enumerate(all_results, 1):
            entry = result['entry_method']
            tp = result['tp_method']
            trades = result['total_trades']
            win_rate = result['win_rate']
            pnl = result['total_pnl']
            final = result['final_balance']
            max_dd = result['max_drawdown']
            pf = result['profit_factor']

            pf_str = f"{pf:.2f}" if pf != float('inf') else "∞"

            print(f"{i:<4} {entry:<15} {tp:<12} {trades:<8} {win_rate:<8.1f} "
                  f"${pnl:<9.2f} ${final:<9.2f} {max_dd:<8.1f} {pf_str:<6}")

        print("\n" + "="*80)

        # Find best combination
        profitable_results = [r for r in all_results if r['total_pnl'] > 0]
        if profitable_results:
            best = max(profitable_results, key=lambda x: x['total_pnl'])
            print(f"\n🏆 BEST COMBINATION:")
            print(f"   Entry: {best['entry_method']}")
            print(f"   TP: {best['tp_method']}")
            print(f"   Total PnL: ${best['total_pnl']:.2f}")
            print(f"   Win Rate: {best['win_rate']:.1f}%")
            print(f"   Profit Factor: {best['profit_factor']:.2f}")

        return {
            'all_results': all_results,
            'best': best if profitable_results else None
        }


def load_data_from_csv(interval: str) -> pd.DataFrame:
    """Load historical data from local CSV files"""
    if interval == '4h':
        csv_path = '/Users/illiachumak/trading/backtest/data/btc_4h_data_2018_to_2025.csv'
    elif interval == '15m':
        csv_path = '/Users/illiachumak/trading/backtest/data/btc_15m_data_2018_to_2025.csv'
    else:
        raise ValueError(f"Unsupported interval: {interval}")

    print(f"Loading {interval} data from {csv_path}...")
    df = pd.read_csv(csv_path)

    # Convert Open time to datetime and set as index
    df['Open time'] = pd.to_datetime(df['Open time'])
    df.set_index('Open time', inplace=True)

    # Convert price columns to float
    for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
        df[col] = df[col].astype(float)

    return df[['Open', 'High', 'Low', 'Close', 'Volume']]


if __name__ == "__main__":
    print("Loading data from local CSV files...")

    # Load data from CSV
    df_4h = load_data_from_csv("4h")
    print(f"4H candles: {len(df_4h)}")

    df_15m = load_data_from_csv("15m")
    print(f"15M candles: {len(df_15m)}")

    # Test 2024 data
    start_date = "2024-01-01"
    end_date = "2024-12-31"

    # Run backtest
    backtester = HeldFVGBacktester(
        initial_balance=300.0,
        risk_per_trade=0.02,
        enable_fees=True
    )

    results = backtester.run_all_combinations(df_4h, df_15m, start_date, end_date)

    # Save results
    output_file = f"backtest_held_fvg_all_combinations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n✅ Results saved to: {output_file}")
