"""
Backtest Failed 4H FVG Strategy on Historical Data
2024-2025 Period

No external backtesting library - pure simulation
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import json


class BacktestFVG:
    """FVG class for backtesting"""
    def __init__(self, fvg_type: str, top: float, bottom: float,
                 formed_time: pd.Timestamp, timeframe: str, index: int):
        self.type = fvg_type
        self.top = top
        self.bottom = bottom
        self.formed_time = formed_time
        self.timeframe = timeframe
        self.index = index

        self.entered = False
        self.rejected = False
        self.invalidated = False

        self.rejection_time = None
        self.rejection_price = None

        self.highs_inside = []
        self.lows_inside = []

        # Track if we already had a filled trade from this rejection
        self.has_filled_trade = False
        self.pending_setup_expiry_time = None  # Track when current pending setup expires

        self.id = f"{timeframe}_{fvg_type}_{top:.2f}_{bottom:.2f}_{int(formed_time.timestamp())}"

    def is_inside(self, price: float) -> bool:
        return self.bottom <= price <= self.top

    def is_fully_passed(self, candle_high: float, candle_low: float) -> bool:
        if self.type == 'BULLISH':
            return candle_low < self.bottom
        else:
            return candle_high > self.top

    def check_rejection(self, candle: pd.Series, debug: bool = False) -> bool:
        candle_high = candle['High']
        candle_low = candle['Low']
        candle_close = candle['Close']

        touched = not (candle_high < self.bottom or candle_low > self.top)

        if not touched:
            return False

        if not self.entered:
            self.entered = True
            if debug:
                print(f"  ✅ {self.timeframe} {self.type} FVG entered: ${self.bottom:.2f}-${self.top:.2f}, Close: ${candle_close:.2f}")

        # Always track highs/lows when candle touches FVG (not just inside)
        # This ensures we have SL levels
        if candle_high >= self.bottom:  # Any high that reached FVG zone
            self.highs_inside.append(candle_high)
        if candle_low <= self.top:  # Any low that reached FVG zone
            self.lows_inside.append(candle_low)

        if self.type == 'BULLISH':
            # Bullish FVG rejection = close BELOW bottom
            if self.entered and candle_close < self.bottom:
                if not self.rejected:
                    self.rejected = True
                    self.rejection_time = candle.name
                    self.rejection_price = candle_close
                    if debug:
                        print(f"  🚫 BULLISH FVG rejected! Close ${candle_close:.2f} < Bottom ${self.bottom:.2f}")
                    return True
            elif self.entered and debug:
                print(f"  ⏳ BULLISH FVG not rejected: Close ${candle_close:.2f} >= Bottom ${self.bottom:.2f}")
        else:  # BEARISH
            # Bearish FVG rejection = close ABOVE top
            if self.entered and candle_close > self.top:
                if not self.rejected:
                    self.rejected = True
                    self.rejection_time = candle.name
                    self.rejection_price = candle_close
                    if debug:
                        print(f"  🚫 BEARISH FVG rejected! Close ${candle_close:.2f} > Top ${self.top:.2f}")
                    return True
            elif self.entered and debug:
                print(f"  ⏳ BEARISH FVG not rejected: Close ${candle_close:.2f} <= Top ${self.top:.2f}")

        return False

    def get_stop_loss(self) -> Optional[float]:
        if self.type == 'BULLISH':
            if self.highs_inside:
                return max(self.highs_inside) * 1.002
        else:
            if self.lows_inside:
                return min(self.lows_inside) * 0.998
        return None


class BacktestTrade:
    """Represents a backtested trade"""
    def __init__(self, trade_id: int, order_type: str, entry_price: float,
                 sl: float, tp: float, size: float, entry_time: pd.Timestamp):
        self.trade_id = trade_id
        self.type = order_type
        self.entry_price = entry_price
        self.sl = sl
        self.tp = tp
        self.size = size
        self.entry_time = entry_time

        self.exit_price = None
        self.exit_time = None
        self.pnl = 0.0
        self.pnl_pct = 0.0
        self.result = None  # 'WIN' or 'LOSS'
        self.exit_reason = None  # 'TP', 'SL', 'TIMEOUT'

        risk = abs(entry_price - sl)
        reward = abs(tp - entry_price)
        self.rr = reward / risk if risk > 0 else 0
        self.sl_pct = abs(entry_price - sl) / entry_price * 100

        self.active = True

    def close(self, exit_price: float, exit_time: pd.Timestamp, reason: str,
             enable_fees: bool = False, maker_fee: float = 0.0018, taker_fee: float = 0.0045):
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.exit_reason = reason
        self.active = False

        if self.type == 'LONG':
            self.pnl = (exit_price - self.entry_price) * self.size
        else:
            self.pnl = (self.entry_price - exit_price) * self.size

        # Apply fees if enabled
        if enable_fees:
            entry_fee = self.entry_price * self.size * maker_fee  # Entry is limit order
            if reason == 'SL':
                exit_fee = exit_price * self.size * taker_fee  # SL is market order
            else:  # TP or TIMEOUT
                exit_fee = exit_price * self.size * maker_fee  # TP is limit order

            total_fees = entry_fee + exit_fee
            self.pnl -= total_fees

        self.pnl_pct = (self.pnl / (self.entry_price * self.size)) * 100
        self.result = 'WIN' if self.pnl > 0 else 'LOSS'

    def to_dict(self) -> Dict:
        return {
            'trade_id': self.trade_id,
            'type': self.type,
            'entry_time': str(self.entry_time),
            'entry_price': self.entry_price,
            'exit_time': str(self.exit_time) if self.exit_time else None,
            'exit_price': self.exit_price,
            'sl': self.sl,
            'tp': self.tp,
            'size': self.size,
            'pnl': round(self.pnl, 2),
            'pnl_pct': round(self.pnl_pct, 2),
            'rr': round(self.rr, 2),
            'sl_pct': round(self.sl_pct, 2),
            'result': self.result,
            'exit_reason': self.exit_reason
        }


class FailedFVGBacktest:
    """Backtesting engine for Failed 4H FVG strategy"""

    def __init__(self, initial_balance: float = 10000.0, risk_per_trade: float = 0.02,
                 min_rr: float = 2.0, min_sl_pct: float = 0.3,
                 use_fixed_rr: bool = False, fixed_rr: float = 2.0,
                 enable_fees: bool = False,
                 limit_order_expiry_candles: int = 16):  # 4H on 15M timeframe
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.risk_per_trade = risk_per_trade
        self.min_rr = min_rr
        self.min_sl_pct = min_sl_pct
        self.use_fixed_rr = use_fixed_rr
        self.fixed_rr = fixed_rr
        self.enable_fees = enable_fees
        self.limit_order_expiry_candles = limit_order_expiry_candles

        # Fee structure
        self.maker_fee = 0.00018  # 0.0180% for entry and TP (limit orders)
        self.taker_fee = 0.00045  # 0.0450% for SL (market order)

        self.active_4h_fvgs: List[BacktestFVG] = []
        self.rejected_4h_fvgs: List[BacktestFVG] = []

        self.trades: List[BacktestTrade] = []
        self.active_trade: Optional[BacktestTrade] = None

        self.trade_counter = 0

        self.liquidity_lookback = 50
        self.max_active_fvgs = 100  # Increased to not lose rejected FVGs

    def detect_fvg(self, df: pd.DataFrame, start_idx: int, end_idx: int, timeframe: str) -> List[BacktestFVG]:
        """Detect FVGs in a range"""
        fvgs = []

        for i in range(start_idx + 2, end_idx):
            if i >= len(df):
                break

            # Bullish FVG
            if df.iloc[i]['Low'] > df.iloc[i-2]['High']:
                top = df.iloc[i]['Low']
                bottom = df.iloc[i-2]['High']

                fvg = BacktestFVG(
                    fvg_type='BULLISH',
                    top=top,
                    bottom=bottom,
                    formed_time=df.index[i],
                    timeframe=timeframe,
                    index=i
                )
                fvgs.append(fvg)

            # Bearish FVG
            elif df.iloc[i]['High'] < df.iloc[i-2]['Low']:
                top = df.iloc[i-2]['Low']
                bottom = df.iloc[i]['High']

                fvg = BacktestFVG(
                    fvg_type='BEARISH',
                    top=top,
                    bottom=bottom,
                    formed_time=df.index[i],
                    timeframe=timeframe,
                    index=i
                )
                fvgs.append(fvg)

        return fvgs

    def update_4h_fvgs(self, df_4h: pd.DataFrame, current_4h_idx: int):
        """Update 4H FVGs and check rejection on 4H candles"""
        # Detect new FVGs in recent candles
        lookback = min(10, current_4h_idx)
        start_idx = max(0, current_4h_idx - lookback)

        new_fvgs = self.detect_fvg(df_4h, start_idx, current_4h_idx + 1, timeframe='4h')

        # Add unique FVGs
        newly_added = 0
        for fvg in new_fvgs:
            if not any(existing.id == fvg.id for existing in self.active_4h_fvgs):
                self.active_4h_fvgs.append(fvg)
                newly_added += 1

        # Check rejection on CURRENT 4H candle (not 15M)
        current_candle = df_4h.iloc[current_4h_idx]

        debug_enabled = False  # Disable debug

        newly_rejected_count = 0

        for fvg in self.active_4h_fvgs[:]:
            # Check rejection (updates fvg.rejected internally)
            if not fvg.rejected:
                was_rejected = fvg.check_rejection(current_candle, debug=debug_enabled)
                if was_rejected:
                    if debug_enabled:
                        print(f"   🔥 REJECTION DETECTED at idx {current_4h_idx}!")
                    # Add to rejected list immediately (before invalidation check)
                    if fvg not in self.rejected_4h_fvgs:
                        self.rejected_4h_fvgs.append(fvg)
                        newly_rejected_count += 1
                        # Don't print every rejection (too noisy)
                        # if newly_rejected_count <= 5:  # Show first 5
                        #     expected_dir = "SHORT" if fvg.type == "BULLISH" else "LONG"
                        #     print(f"🔥 REJECTION! 4H {fvg.type} FVG -> {expected_dir}, Total rejected: {len(self.rejected_4h_fvgs)}")

            # Check invalidation
            if fvg.is_fully_passed(current_candle['High'], current_candle['Low']):
                fvg.invalidated = True
                self.active_4h_fvgs.remove(fvg)
                # DON'T remove from rejected_4h_fvgs - we still want to look for 15M FVG
                # Rejected FVG will be removed after trade is created or after timeout

        # Limit active FVGs (memory)
        if len(self.active_4h_fvgs) > self.max_active_fvgs:
            self.active_4h_fvgs = self.active_4h_fvgs[-self.max_active_fvgs:]

        return newly_added, newly_rejected_count

    def check_4h_rejections(self, df_15m: pd.DataFrame, current_15m_idx: int) -> List[BacktestFVG]:
        """Check for 4H FVG rejections using 15M data"""
        newly_rejected = []

        current_candle = df_15m.iloc[current_15m_idx]

        for fvg in self.active_4h_fvgs:
            if fvg.rejected:
                continue

            if fvg.check_rejection(current_candle):
                self.rejected_4h_fvgs.append(fvg)
                newly_rejected.append(fvg)

        return newly_rejected

    def find_liquidity(self, df_15m: pd.DataFrame, current_idx: int, direction: str) -> Optional[float]:
        """Find nearest liquidity for TP"""
        start_idx = max(0, current_idx - self.liquidity_lookback)
        lookback_df = df_15m.iloc[start_idx:current_idx+1]

        current_price = df_15m.iloc[current_idx]['Close']

        if direction == 'LONG':
            # Find highs above current price
            highs = lookback_df[lookback_df['High'] > current_price]['High'].values
            if len(highs) > 0:
                # Return the highest (most recent significant high)
                return max(highs)
            else:
                # Fallback: use recent high + buffer
                recent_high = lookback_df['High'].max()
                if recent_high > current_price:
                    return recent_high
                else:
                    return current_price * 1.015  # +1.5%

        else:  # SHORT
            # Find lows below current price
            lows = lookback_df[lookback_df['Low'] < current_price]['Low'].values
            if len(lows) > 0:
                # Return the lowest (most recent significant low)
                return min(lows)
            else:
                # Fallback: use recent low - buffer
                recent_low = lookback_df['Low'].min()
                if recent_low < current_price:
                    return recent_low
                else:
                    return current_price * 0.985  # -1.5%

    def create_trade(self, parent_4h_fvg: BacktestFVG, fvg_15m: BacktestFVG,
                    df_15m: pd.DataFrame, current_idx: int) -> Optional[BacktestTrade]:
        """Create trade from setup"""

        if parent_4h_fvg.type == 'BULLISH':
            order_type = 'SHORT'

            if fvg_15m.type != 'BEARISH':
                return None

            limit_price = fvg_15m.top
            sl = parent_4h_fvg.get_stop_loss()
            if not sl:
                return None

            # Calculate TP
            risk = abs(limit_price - sl)
            if self.use_fixed_rr:
                tp = limit_price - (self.fixed_rr * risk)
            else:
                tp = self.find_liquidity(df_15m, current_idx, direction='SHORT')
                if not tp:
                    return None

        else:
            order_type = 'LONG'

            if fvg_15m.type != 'BULLISH':
                return None

            limit_price = fvg_15m.bottom
            sl = parent_4h_fvg.get_stop_loss()
            if not sl:
                return None

            # Calculate TP
            risk = abs(limit_price - sl)
            if self.use_fixed_rr:
                tp = limit_price + (self.fixed_rr * risk)
            else:
                tp = self.find_liquidity(df_15m, current_idx, direction='LONG')
                if not tp:
                    return None

        # Calculate RR and SL%
        reward = abs(tp - limit_price)
        rr = reward / risk if risk > 0 else 0
        sl_pct = risk / limit_price * 100

        # Validate
        if rr < self.min_rr:
            return None

        if sl_pct < self.min_sl_pct:
            return None

        # Calculate size
        risk_amount = self.balance * self.risk_per_trade
        size = risk_amount / risk
        
        # Round size to reasonable precision (simulate lot size rounding)
        # For BTC, typical lot size is 0.001 BTC
        size = round(size, 3)
        
        # Check minimum notional (simulate Binance minimum)
        min_notional = 10.0  # $10 minimum
        notional = size * limit_price
        if notional < min_notional:
            # Increase size to meet minimum
            size = min_notional / limit_price
            size = round(size, 3)

        # Create trade
        self.trade_counter += 1

        trade = BacktestTrade(
            trade_id=self.trade_counter,
            order_type=order_type,
            entry_price=limit_price,
            sl=sl,
            tp=tp,
            size=size,
            entry_time=df_15m.index[current_idx]
        )

        return trade

    def check_trade_fill(self, trade: BacktestTrade, df_15m: pd.DataFrame,
                        start_idx: int, end_idx: int) -> Tuple[bool, Optional[int]]:
        """Check if limit order gets filled"""
        for i in range(start_idx, end_idx):
            if i >= len(df_15m):
                break

            candle = df_15m.iloc[i]

            if trade.type == 'LONG':
                if candle['Low'] <= trade.entry_price:
                    return True, i
            else:
                if candle['High'] >= trade.entry_price:
                    return True, i

        return False, None

    def simulate_trade(self, trade: BacktestTrade, df_15m: pd.DataFrame,
                      entry_idx: int, max_candles: int = 200) -> BacktestTrade:
        """Simulate trade execution"""

        for i in range(entry_idx, min(entry_idx + max_candles, len(df_15m))):
            candle = df_15m.iloc[i]

            if trade.type == 'LONG':
                # Check SL
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
                # Check SL
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

        # If still active after max_candles, close at current price
        if trade.active:
            last_candle = df_15m.iloc[min(entry_idx + max_candles - 1, len(df_15m) - 1)]
            trade.close(last_candle['Close'], last_candle.name, 'TIMEOUT',
                       enable_fees=self.enable_fees,
                       maker_fee=self.maker_fee,
                       taker_fee=self.taker_fee)

        return trade

    def run_backtest(self, df_4h: pd.DataFrame, df_15m: pd.DataFrame,
                    start_date: str, end_date: str) -> Dict:
        """Run full backtest"""

        print(f"\n{'='*80}")
        print(f"FAILED 4H FVG BACKTEST")
        print(f"{'='*80}")
        print(f"Period: {start_date} to {end_date}")
        print(f"Initial Balance: ${self.initial_balance:,.2f}")
        print(f"Risk per Trade: {self.risk_per_trade*100}%")
        print(f"Min RR: {self.min_rr}")
        print(f"Min SL: {self.min_sl_pct}%")
        print(f"{'='*80}\n")

        # Filter data by date
        df_4h = df_4h.loc[start_date:end_date].copy()
        df_15m = df_15m.loc[start_date:end_date].copy()

        print(f"4H Candles: {len(df_4h)}")
        print(f"15M Candles: {len(df_15m)}")
        print(f"\nRunning backtest...\n")

        current_15m_idx = 0

        # Debug counters
        total_4h_fvgs = 0
        total_rejections = 0
        total_15m_fvgs_found = 0
        failed_rr_check = 0
        failed_sl_check = 0
        no_sl_available = 0
        no_tp_available = 0
        fvg_type_mismatch = 0
        debug_logs_shown = 0  # Track debug logs

        # Fill tracking
        total_setups_created = 0
        total_fills = 0
        total_no_fills = 0
        setups_per_rejection = {}  # Track how many setups created per rejection

        # Iterate through 4H candles
        for i in range(len(df_4h)):
            current_4h_time = df_4h.index[i]

            # Update 4H FVGs (including rejection detection)
            newly_added, newly_rejected = self.update_4h_fvgs(df_4h, i)
            total_4h_fvgs += newly_added
            total_rejections += newly_rejected

            # Log newly rejected FVGs (disabled for clean output)
            # if newly_rejected > 0:
            #     for fvg in self.rejected_4h_fvgs[-newly_rejected:]:
            #         expected_direction = "SHORT" if fvg.type == "BULLISH" else "LONG"
            #         expected_15m_type = "BEARISH" if fvg.type == "BULLISH" else "BULLISH"
            #         print(f"🚫 REJECTION #{total_rejections}! 4H {fvg.type} FVG ${fvg.bottom:.2f}-${fvg.top:.2f}")
            #         print(f"   Rejected @ ${fvg.rejection_price:.2f}")
            #         print(f"   Expected: {expected_direction} trade with 15M {expected_15m_type} FVG")

            # Find corresponding 15M candles for this 4H period
            next_4h_time = df_4h.index[i+1] if i+1 < len(df_4h) else df_15m.index[-1]

            # Process all 15M candles in this 4H period
            while current_15m_idx < len(df_15m) and df_15m.index[current_15m_idx] < next_4h_time:

                # Check for setups (only if no active trade)
                # NOTE: self.active_trade is never set, so this check always passes.
                # This means new trades can be created even while a trade is being simulated.
                # When RR increases, more trades close by SL, and the code jumps forward
                # in time (line 677), creating more opportunities for new trades.
                if not self.active_trade:

                    current_time = df_15m.index[current_15m_idx]

                    for rej_idx, rejected_fvg in enumerate(self.rejected_4h_fvgs[:]):

                        # CRITICAL: Skip if already had a filled trade from this rejection
                        if rejected_fvg.has_filled_trade:
                            continue

                        # Check if 4H FVG is invalidated on current 15M candle
                        current_candle_15m = df_15m.iloc[current_15m_idx]
                        if rejected_fvg.is_fully_passed(current_candle_15m['High'], current_candle_15m['Low']):
                            rejected_fvg.invalidated = True
                            self.rejected_4h_fvgs.remove(rejected_fvg)
                            continue

                        # Skip if there's a pending setup that hasn't expired yet
                        if rejected_fvg.pending_setup_expiry_time is not None:
                            if current_time < rejected_fvg.pending_setup_expiry_time:
                                continue  # Setup still pending, wait for expiry

                        # Look for 15M FVG
                        lookback_start = max(0, current_15m_idx - 10)
                        fvgs_15m = self.detect_fvg(df_15m, lookback_start, current_15m_idx + 1, timeframe='15m')

                        if fvgs_15m:
                            fvg_15m = fvgs_15m[-1]
                            total_15m_fvgs_found += 1

                            # Check type match
                            if rejected_fvg.type == 'BULLISH' and fvg_15m.type != 'BEARISH':
                                fvg_type_mismatch += 1
                                continue
                            if rejected_fvg.type == 'BEARISH' and fvg_15m.type != 'BULLISH':
                                fvg_type_mismatch += 1
                                continue

                            sl_val = rejected_fvg.get_stop_loss()
                            if not sl_val:
                                no_sl_available += 1
                                continue

                            direction = 'SHORT' if rejected_fvg.type == 'BULLISH' else 'LONG'
                            tp_val = self.find_liquidity(df_15m, current_15m_idx, direction)
                            if not tp_val:
                                no_tp_available += 1
                                continue

                            # Create trade
                            potential_trade = self.create_trade(rejected_fvg, fvg_15m, df_15m, current_15m_idx)

                            if not potential_trade:
                                # Check why
                                limit_price = fvg_15m.top if direction == 'SHORT' else fvg_15m.bottom
                                risk = abs(limit_price - sl_val)
                                reward = abs(tp_val - limit_price)
                                rr = reward / risk if risk > 0 else 0
                                sl_pct = risk / limit_price * 100

                                if rr < self.min_rr:
                                    failed_rr_check += 1
                                if sl_pct < self.min_sl_pct:
                                    failed_sl_check += 1
                                continue

                            if potential_trade:
                                total_setups_created += 1

                                # Track setups per rejection
                                rej_id = id(rejected_fvg)
                                setups_per_rejection[rej_id] = setups_per_rejection.get(rej_id, 0) + 1

                                # Mark setup as pending with expiry time
                                expiry_idx = min(current_15m_idx + self.limit_order_expiry_candles, len(df_15m) - 1)
                                rejected_fvg.pending_setup_expiry_time = df_15m.index[expiry_idx]

                                # Check if limit gets filled in next N candles (expiry window)
                                filled, fill_idx = self.check_trade_fill(
                                    potential_trade, df_15m,
                                    current_15m_idx + 1,
                                    min(current_15m_idx + self.limit_order_expiry_candles, len(df_15m))
                                )

                                if filled:
                                    total_fills += 1
                                    # Set active trade BEFORE simulating (prevents multiple trades)
                                    self.active_trade = potential_trade
                                    
                                    # Simulate trade
                                    trade = self.simulate_trade(potential_trade, df_15m, fill_idx)

                                    self.trades.append(trade)
                                    self.balance += trade.pnl

                                    result_emoji = "✅" if trade.result == 'WIN' else "❌"
                                    print(f"{result_emoji} Trade #{trade.trade_id} | {trade.type} | "
                                          f"Entry: ${trade.entry_price:.2f} | Exit: ${trade.exit_price:.2f} | "
                                          f"PnL: ${trade.pnl:+.2f} ({trade.pnl_pct:+.2f}%) | "
                                          f"Exit: {trade.exit_reason}")

                                    # CRITICAL: Mark this rejection as having a filled trade
                                    rejected_fvg.has_filled_trade = True

                                    # Remove from active rejected FVGs (no more setups from this rejection)
                                    if rejected_fvg in self.rejected_4h_fvgs:
                                        self.rejected_4h_fvgs.remove(rejected_fvg)

                                    # Clear active trade after close
                                    self.active_trade = None

                                    # Continue processing from next candle (don't jump forward)
                                    # This ensures we don't miss opportunities between entry and exit
                                    current_15m_idx = fill_idx + 1

                                    # Break from rejected_fvg loop (only 1 trade at a time)
                                    break
                                else:
                                    # Setup expired without fill
                                    total_no_fills += 1
                                    # Set cooldown before next setup attempt (wait same duration as expiry)
                                    # This prevents creating 100+ setups from same rejection
                                    cooldown_idx = min(expiry_idx + self.limit_order_expiry_candles, len(df_15m) - 1)
                                    rejected_fvg.pending_setup_expiry_time = df_15m.index[cooldown_idx]

                current_15m_idx += 1

        # Print debug stats
        print(f"\n{'='*80}")
        print("DEBUG STATISTICS")
        print(f"{'='*80}")
        print(f"Total 4H FVGs detected:        {total_4h_fvgs}")
        print(f"Total rejections:              {total_rejections}")
        print(f"Total 15M FVGs found:          {total_15m_fvgs_found}")
        print(f"\nFILL STATISTICS:")
        print(f"  Total setups created:        {total_setups_created}")
        print(f"  Filled:                      {total_fills} ({total_fills/total_setups_created*100:.1f}%)" if total_setups_created > 0 else "  Filled:                      0 (0.0%)")
        print(f"  Not filled:                  {total_no_fills} ({total_no_fills/total_setups_created*100:.1f}%)" if total_setups_created > 0 else "  Not filled:                  0 (0.0%)")

        # Setups per rejection stats
        if setups_per_rejection:
            avg_setups = sum(setups_per_rejection.values()) / len(setups_per_rejection)
            max_setups = max(setups_per_rejection.values())
            min_setups = min(setups_per_rejection.values())
            print(f"\nSETUPS PER REJECTION:")
            print(f"  Average:                     {avg_setups:.1f}")
            print(f"  Max:                         {max_setups}")
            print(f"  Min:                         {min_setups}")
            print(f"  Unique rejections:           {len(setups_per_rejection)}")

        print(f"\nFAILURE REASONS:")
        print(f"  FVG type mismatch:           {fvg_type_mismatch}")
        print(f"  No SL available:             {no_sl_available}")
        print(f"  No TP available:             {no_tp_available}")
        print(f"  Failed RR check (< {self.min_rr}):     {failed_rr_check}")
        print(f"  Failed SL check (< {self.min_sl_pct}%):    {failed_sl_check}")
        print(f"{'='*80}\n")

        # Calculate metrics
        results = self.calculate_metrics()

        return results

    def calculate_metrics(self) -> Dict:
        """Calculate performance metrics"""

        if not self.trades:
            return {
                'total_trades': 0,
                'error': 'No trades executed'
            }

        wins = [t for t in self.trades if t.result == 'WIN']
        losses = [t for t in self.trades if t.result == 'LOSS']

        total_pnl = sum(t.pnl for t in self.trades)
        total_pnl_pct = (total_pnl / self.initial_balance) * 100

        win_rate = len(wins) / len(self.trades) * 100 if self.trades else 0

        avg_win = np.mean([t.pnl for t in wins]) if wins else 0
        avg_loss = np.mean([t.pnl for t in losses]) if losses else 0

        avg_rr = np.mean([t.rr for t in self.trades])

        # Drawdown
        cumulative = [self.initial_balance]
        for trade in self.trades:
            cumulative.append(cumulative[-1] + trade.pnl)

        peak = cumulative[0]
        max_dd = 0
        for val in cumulative:
            if val > peak:
                peak = val
            dd = (peak - val) / peak * 100
            if dd > max_dd:
                max_dd = dd

        # Monthly return (approximate)
        if self.trades:
            days = (self.trades[-1].exit_time - self.trades[0].entry_time).days
            months = days / 30 if days > 0 else 1
            monthly_return = (total_pnl_pct / months) if months > 0 else 0
        else:
            monthly_return = 0

        return {
            'total_trades': len(self.trades),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': round(win_rate, 2),
            'total_pnl': round(total_pnl, 2),
            'total_pnl_pct': round(total_pnl_pct, 2),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'avg_rr': round(avg_rr, 2),
            'max_drawdown': round(max_dd, 2),
            'final_balance': round(self.balance, 2),
            'monthly_return': round(monthly_return, 2),
            'profit_factor': round(sum(t.pnl for t in wins) / abs(sum(t.pnl for t in losses)), 2) if losses and sum(t.pnl for t in losses) != 0 else float('inf')
        }

    def save_results(self, results: Dict, filename: str = 'backtest_results.json'):
        """Save results to JSON"""

        output = {
            'summary': results,
            'trades': [t.to_dict() for t in self.trades],
            'parameters': {
                'initial_balance': self.initial_balance,
                'risk_per_trade': self.risk_per_trade,
                'min_rr': self.min_rr,
                'min_sl_pct': self.min_sl_pct
            }
        }

        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)

        print(f"\n💾 Results saved to {filename}")


def load_data(data_dir: str = '/Users/illiachumak/trading/backtest/data'):
    """Load historical data"""

    print("📊 Loading historical data...")

    # Load 4H data
    df_4h = pd.read_csv(f"{data_dir}/btc_4h_data_2018_to_2025.csv")
    df_4h['Open time'] = pd.to_datetime(df_4h['Open time'])
    df_4h.set_index('Open time', inplace=True)
    df_4h = df_4h[['Open', 'High', 'Low', 'Close', 'Volume']]

    # Load 15M data
    df_15m = pd.read_csv(f"{data_dir}/btc_15m_data_2018_to_2025.csv")
    df_15m['Open time'] = pd.to_datetime(df_15m['Open time'])
    df_15m.set_index('Open time', inplace=True)
    df_15m = df_15m[['Open', 'High', 'Low', 'Close', 'Volume']]

    print(f"✅ Loaded {len(df_4h)} 4H candles")
    print(f"✅ Loaded {len(df_15m)} 15M candles")

    return df_4h, df_15m


def print_results(results: Dict):
    """Print results in formatted table"""

    print(f"\n{'='*80}")
    print("BACKTEST RESULTS")
    print(f"{'='*80}")

    if 'error' in results:
        print(f"\n⚠️  {results['error']}")
        print(f"\n{'='*80}\n")
        return

    print(f"\n📊 TRADE STATISTICS")
    print(f"   Total Trades:      {results['total_trades']}")
    print(f"   Wins:              {results['wins']}")
    print(f"   Losses:            {results['losses']}")
    print(f"   Win Rate:          {results['win_rate']}%")

    print(f"\n💰 PROFIT & LOSS")
    print(f"   Total PnL:         ${results['total_pnl']:+,.2f} ({results['total_pnl_pct']:+.2f}%)")
    print(f"   Final Balance:     ${results['final_balance']:,.2f}")
    print(f"   Avg Win:           ${results['avg_win']:,.2f}")
    print(f"   Avg Loss:          ${results['avg_loss']:,.2f}")
    print(f"   Profit Factor:     {results['profit_factor']}")

    print(f"\n📈 RISK METRICS")
    print(f"   Avg R:R:           {results['avg_rr']:.2f}")
    print(f"   Max Drawdown:      {results['max_drawdown']:.2f}%")
    print(f"   Monthly Return:    {results['monthly_return']:.2f}%")

    print(f"\n{'='*80}\n")


if __name__ == "__main__":

    # Load data
    df_4h, df_15m = load_data()

    # Test configurations - Testing different expiry windows
    test_configs = [
        {
            'name': 'Test 1: Fixed RR 3.0, Min RR 2.0, 4H Expiry (16 candles)',
            'params': {
                'initial_balance': 10000.0,
                'risk_per_trade': 0.02,
                'min_rr': 2.0,  # Same as live bot MIN_RR
                'min_sl_pct': 0.3,
                'use_fixed_rr': True,
                'fixed_rr': 3.0,  # Same as live bot FIXED_RR
                'enable_fees': True,
                'limit_order_expiry_candles': 16  # 4H
            },
            'suffix': '4h_expiry_fixed_rr_3'
        },
        {
            'name': 'Test 2: Fixed RR 1.5, 8H Expiry (32 candles)',
            'params': {
                'initial_balance': 10000.0,
                'risk_per_trade': 0.02,
                'min_rr': 0.0,
                'min_sl_pct': 0.3,
                'use_fixed_rr': True,
                'fixed_rr': 3,
                'enable_fees': True,
                'limit_order_expiry_candles': 32  # 8H
            },
            'suffix': '8h_expiry'
        },
        {
            'name': 'Test 3: Fixed RR 1.5, 12H Expiry (48 candles)',
            'params': {
                'initial_balance': 10000.0,
                'risk_per_trade': 0.02,
                'min_rr': 0.0,
                'min_sl_pct': 0.3,
                'use_fixed_rr': True,
                'fixed_rr': 3,
                'enable_fees': True,
                'limit_order_expiry_candles': 48  # 12H
            },
            'suffix': '12h_expiry'
        }
    ]

    # Test periods - testing only 2024 for quick comparison
    test_periods = [
        ('2024-01-01', '2024-12-31'),
    ]

    # Run all tests
    for config in test_configs:
        print(f"\n{'#'*80}")
        print(f"# {config['name']}")
        print(f"{'#'*80}\n")

        config_results = {}

        for start_date, end_date in test_periods:
            year = start_date[:4]

            # Create filename using config suffix
            filename = f"backtest_failed_fvg_{year}_{config['suffix']}.json"

            print(f"\n{'='*80}")
            print(f"TESTING PERIOD: {year}")
            print(f"{'='*80}\n")

            # Reset backtest state
            backtest = FailedFVGBacktest(**config['params'])

            # Run backtest
            results = backtest.run_backtest(
                df_4h=df_4h,
                df_15m=df_15m,
                start_date=start_date,
                end_date=end_date
            )

            # Print results
            print_results(results)

            # Save results
            backtest.save_results(results, filename=filename)

            config_results[year] = results

        # Print comparison for this config
        print(f"\n{'='*80}")
        print(f"COMPARISON - {config['name']}")
        print(f"{'='*80}\n")
        print(f"{'Year':<10} {'Trades':<10} {'Win Rate':<12} {'Return':<15} {'Profit Factor':<15} {'Max DD':<10}")
        print("-" * 80)

        for year in sorted(config_results.keys()):
            s = config_results[year]
            total_return = (s['final_balance'] - 10000) / 10000 * 100
            print(f"{year:<10} {s['total_trades']:<10} {s['win_rate']:<12.2f}% {total_return:<15.2f}% {s['profit_factor']:<15.2f} {s['max_drawdown']:<10.2f}%")

    print("\n✅ All backtests complete!")
