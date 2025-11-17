"""
Simulate Live Bot with Historical Data
Uses the same loop logic as live bot but with historical data from /backtest/data
Results should match backtest_2024_fixed.json
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, field

# Import bot classes
import sys
sys.path.append('/Users/illiachumak/trading/implement/4HFVG_BOT')
from failed_fvg_live_bot import LiveFVG, PendingSetup, ActiveTrade, FVGDetector

# Strategy parameters (same as live bot)
RISK_PER_TRADE = 0.02
MIN_SL_PCT = 0.3
MIN_RR = 2.0  # Minimum RR for validation (same as live bot)
FIXED_RR = 3.0  # Fixed RR for TP calculation (same as live bot)
LIMIT_EXPIRY_CANDLES = 16  # 4H in 15M candles
COOLDOWN_CANDLES = 16
MAKER_FEE = 0.00018  # 0.0180% (0.0180 / 100 = 0.00018)
TAKER_FEE = 0.00045  # 0.0450% (0.0450 / 100 = 0.00045)


class LiveBotSimulator:
    """Simulates live bot with historical data"""

    def __init__(self, initial_balance: float = 10000.0):
        self.detector = FVGDetector()

        # State (same as live bot)
        self.active_4h_fvgs: List[LiveFVG] = []
        self.rejected_4h_fvgs: List[LiveFVG] = []
        self.pending_setups: List[PendingSetup] = []
        self.active_trade: Optional[ActiveTrade] = None

        # Data
        self.df_4h: Optional[pd.DataFrame] = None
        self.df_15m: Optional[pd.DataFrame] = None

        # Stats
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.trades_history: List[Dict] = []
        self.trade_counter = 0

        # Simulation tracking
        self.current_4h_idx = 0
        self.current_15m_idx = 0

    def load_data(self, data_dir: str = '/Users/illiachumak/trading/backtest/data'):
        """Load historical data"""
        print("📊 Loading historical data...")

        # Load 4H data
        df_4h = pd.read_csv(f"{data_dir}/btc_4h_data_2018_to_2025.csv")
        df_4h['Open time'] = pd.to_datetime(df_4h['Open time'])
        df_4h.set_index('Open time', inplace=True)
        df_4h = df_4h[['Open', 'High', 'Low', 'Close', 'Volume']]
        df_4h.columns = ['open', 'high', 'low', 'close', 'volume']

        # Load 15M data
        df_15m = pd.read_csv(f"{data_dir}/btc_15m_data_2018_to_2025.csv")
        df_15m['Open time'] = pd.to_datetime(df_15m['Open time'])
        df_15m.set_index('Open time', inplace=True)
        df_15m = df_15m[['Open', 'High', 'Low', 'Close', 'Volume']]
        df_15m.columns = ['open', 'high', 'low', 'close', 'volume']

        print(f"✅ Loaded {len(df_4h)} 4H candles, {len(df_15m)} 15M candles")

        return df_4h, df_15m

    def can_create_setup(self, rejected_fvg: LiveFVG, current_time: pd.Timestamp) -> bool:
        """Check if we can create setup (same as live bot)"""
        if rejected_fvg.has_filled_trade:
            return False

        if rejected_fvg.pending_expiry_time:
            # Convert to pd.Timestamp if needed
            if isinstance(rejected_fvg.pending_expiry_time, datetime):
                expiry_ts = pd.Timestamp(rejected_fvg.pending_expiry_time)
            else:
                expiry_ts = rejected_fvg.pending_expiry_time
            
            if current_time < expiry_ts:
                return False

        if rejected_fvg.pending_setup_id:
            for setup in self.pending_setups:
                if setup.setup_id == rejected_fvg.pending_setup_id and setup.status == 'PENDING':
                    return False

        return True

    def calculate_position_size(self, entry: float, sl: float) -> float:
        """Calculate position size based on risk"""
        risk_amount = self.balance * RISK_PER_TRADE
        risk_per_unit = abs(entry - sl)
        size = risk_amount / risk_per_unit

        # Simple rounding (no lot size from API)
        return round(size, 8)

    def validate_setup(self, entry: float, sl: float, tp: float) -> bool:
        """Validate setup parameters"""
        # SL distance
        sl_distance_pct = abs(entry - sl) / entry * 100
        if sl_distance_pct < MIN_SL_PCT:
            return False

        # RR ratio
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr = reward / risk
        if rr < MIN_RR:  # Use MIN_RR for validation, not FIXED_RR
            return False

        return True

    def create_setup_from_rejection(self, rejected_fvg: LiveFVG, fvg_15m: LiveFVG,
                                   current_time: pd.Timestamp) -> Optional[PendingSetup]:
        """Create setup from rejected 4H FVG and 15M FVG"""

        # Determine direction
        if rejected_fvg.type == 'BULLISH':
            direction = 'SHORT'
            if fvg_15m.type != 'BEARISH':
                return None
            entry_price = fvg_15m.top
        else:
            direction = 'LONG'
            if fvg_15m.type != 'BULLISH':
                return None
            entry_price = fvg_15m.bottom

        # Get SL
        sl = rejected_fvg.get_stop_loss()
        if not sl:
            return None

        # Calculate TP
        risk = abs(entry_price - sl)
        if direction == 'SHORT':
            tp = entry_price - (FIXED_RR * risk)
        else:
            tp = entry_price + (FIXED_RR * risk)

        # Validate
        if not self.validate_setup(entry_price, sl, tp):
            return None

        # Calculate size
        size = self.calculate_position_size(entry_price, sl)

        # Create setup
        self.trade_counter += 1
        setup = PendingSetup(
            setup_id=f"setup_{self.trade_counter}",
            parent_4h_fvg_id=rejected_fvg.id,
            fvg_15m_id=fvg_15m.id,
            order_id=self.trade_counter,  # Fake order ID
            direction=direction,
            entry_price=entry_price,
            sl=sl,
            tp=tp,
            size=size,
            created_time=current_time,
            expiry_time=current_time + timedelta(hours=4)
        )

        return setup

    def check_setup_fill(self, setup: PendingSetup, df_15m: pd.DataFrame,
                        start_idx: int, end_idx: int) -> tuple:
        """Check if setup gets filled in window"""
        for i in range(start_idx, end_idx):
            if i >= len(df_15m):
                break

            candle = df_15m.iloc[i]

            # Check if limit price hit
            if setup.direction == 'LONG':
                if candle['low'] <= setup.entry_price:
                    return True, i
            else:
                if candle['high'] >= setup.entry_price:
                    return True, i

        return False, None

    def simulate_trade(self, setup: PendingSetup, df_15m: pd.DataFrame,
                      entry_idx: int) -> Dict:
        """Simulate trade execution"""

        trade = {
            'trade_id': setup.setup_id,
            'direction': setup.direction,
            'entry_price': setup.entry_price,
            'entry_time': df_15m.index[entry_idx],
            'sl': setup.sl,
            'tp': setup.tp,
            'size': setup.size,
            'status': 'ACTIVE'
        }

        # Simulate until TP or SL hit
        for i in range(entry_idx, min(entry_idx + 200, len(df_15m))):
            candle = df_15m.iloc[i]

            if setup.direction == 'LONG':
                # Check SL first
                if candle['low'] <= setup.sl:
                    trade['exit_price'] = setup.sl
                    trade['exit_time'] = df_15m.index[i]
                    trade['exit_reason'] = 'SL'
                    break

                # Check TP
                if candle['high'] >= setup.tp:
                    trade['exit_price'] = setup.tp
                    trade['exit_time'] = df_15m.index[i]
                    trade['exit_reason'] = 'TP'
                    break

            else:  # SHORT
                # Check SL first
                if candle['high'] >= setup.sl:
                    trade['exit_price'] = setup.sl
                    trade['exit_time'] = df_15m.index[i]
                    trade['exit_reason'] = 'SL'
                    break

                # Check TP
                if candle['low'] <= setup.tp:
                    trade['exit_price'] = setup.tp
                    trade['exit_time'] = df_15m.index[i]
                    trade['exit_reason'] = 'TP'
                    break

        # If still active, close at timeout
        if 'exit_price' not in trade:
            last_idx = min(entry_idx + 199, len(df_15m) - 1)
            trade['exit_price'] = df_15m.iloc[last_idx]['close']
            trade['exit_time'] = df_15m.index[last_idx]
            trade['exit_reason'] = 'TIMEOUT'

        # Calculate PnL
        if setup.direction == 'LONG':
            pnl = (trade['exit_price'] - setup.entry_price) * setup.size
        else:
            pnl = (setup.entry_price - trade['exit_price']) * setup.size

        # Apply fees
        entry_fee = setup.entry_price * setup.size * MAKER_FEE
        if trade['exit_reason'] == 'SL':
            exit_fee = trade['exit_price'] * setup.size * TAKER_FEE
        else:
            exit_fee = trade['exit_price'] * setup.size * MAKER_FEE

        pnl -= (entry_fee + exit_fee)
        trade['pnl'] = pnl
        trade['pnl_pct'] = (pnl / (setup.entry_price * setup.size)) * 100
        trade['result'] = 'WIN' if pnl > 0 else 'LOSS'

        return trade

    def update_4h_fvgs(self, candle: pd.Series, candle_time: pd.Timestamp):
        """Update 4H FVGs (same logic as live bot)"""
        candle_dict = {
            'high': candle['high'],
            'low': candle['low'],
            'close': candle['close'],
            'close_time': int(candle_time.timestamp() * 1000)
        }

        # Check rejections
        for fvg in self.active_4h_fvgs[:]:
            if not fvg.rejected:
                fvg.check_rejection(candle_dict)

                if fvg.rejected:
                    self.rejected_4h_fvgs.append(fvg)

            # Check invalidation
            if fvg.is_fully_passed(candle['high'], candle['low']):
                fvg.invalidated = True
                self.active_4h_fvgs.remove(fvg)

        # Detect new FVGs
        lookback_start = max(0, self.current_4h_idx - 10)
        df_window = self.df_4h.iloc[lookback_start:self.current_4h_idx + 1]
        new_fvgs = self.detector.detect_fvgs(df_window, '4h')

        for fvg in new_fvgs:
            if not any(existing.id == fvg.id for existing in self.active_4h_fvgs):
                self.active_4h_fvgs.append(fvg)

    def look_for_setups(self, current_15m_idx: int) -> Optional[PendingSetup]:
        """Look for setups (same logic as live bot)"""
        if self.active_trade:
            return None

        if not self.rejected_4h_fvgs:
            return None

        current_candle_15m = self.df_15m.iloc[current_15m_idx]

        for rejected_fvg in self.rejected_4h_fvgs[:]:
            # Check if 4H FVG is invalidated on current 15M candle
            if rejected_fvg.is_fully_passed(current_candle_15m['high'], current_candle_15m['low']):
                rejected_fvg.invalidated = True
                self.rejected_4h_fvgs.remove(rejected_fvg)
                continue

            if not self.can_create_setup(rejected_fvg, self.df_15m.index[current_15m_idx]):
                continue

            # Look for 15M FVG
            lookback_start = max(0, current_15m_idx - 10)
            df_window = self.df_15m.iloc[lookback_start:current_15m_idx + 1]
            fvgs_15m = self.detector.detect_fvgs(df_window, '15m')

            if fvgs_15m:
                fvg_15m = fvgs_15m[-1]

                # Try to create setup
                setup = self.create_setup_from_rejection(
                    rejected_fvg, fvg_15m, self.df_15m.index[current_15m_idx]
                )

                if setup:
                    # Mark FVG as having pending setup
                    rejected_fvg.pending_setup_id = setup.setup_id
                    rejected_fvg.pending_expiry_time = setup.expiry_time

                    return setup

        return None

    def run_simulation(self, start_date: str = '2024-01-01', end_date: str = '2024-12-31'):
        """Run simulation"""

        print(f"\n{'='*80}")
        print(f"LIVE BOT SIMULATION - 2024")
        print(f"{'='*80}\n")

        # Load data
        self.df_4h, self.df_15m = self.load_data()

        # Filter to date range
        self.df_4h = self.df_4h.loc[start_date:end_date]
        self.df_15m = self.df_15m.loc[start_date:end_date]

        print(f"Period: {self.df_4h.index[0]} to {self.df_4h.index[-1]}")
        print(f"4H candles: {len(self.df_4h)}")
        print(f"15M candles: {len(self.df_15m)}")
        print(f"Initial balance: ${self.balance:,.2f}\n")

        print("Running simulation...\n")

        # Initialize with first 50 candles
        initial_4h = self.detector.detect_fvgs(self.df_4h.head(50), '4h')
        self.active_4h_fvgs = initial_4h
        self.current_4h_idx = 50

        # Map 15M index to 4H index
        current_15m_idx = 0

        # Main loop - iterate through 4H candles
        for i in range(50, len(self.df_4h)):
            self.current_4h_idx = i
            current_4h_time = self.df_4h.index[i]
            current_4h_candle = self.df_4h.iloc[i]

            # Update 4H FVGs
            self.update_4h_fvgs(current_4h_candle, current_4h_time)

            # Find next 4H time
            next_4h_time = self.df_4h.index[i+1] if i+1 < len(self.df_4h) else self.df_15m.index[-1]

            # Process 15M candles in this 4H period
            while current_15m_idx < len(self.df_15m) and self.df_15m.index[current_15m_idx] < next_4h_time:

                # Look for setups (only if no active trade and no pending setups)
                if not self.active_trade and not self.pending_setups:
                    setup = self.look_for_setups(current_15m_idx)

                    if setup:
                        # Check if gets filled in expiry window
                        expiry_idx = min(current_15m_idx + LIMIT_EXPIRY_CANDLES, len(self.df_15m))
                        filled, fill_idx = self.check_setup_fill(
                            setup, self.df_15m, current_15m_idx + 1, expiry_idx
                        )

                        if filled:
                            # Set active trade BEFORE simulating (prevents multiple trades)
                            # Create temporary active trade object
                            self.active_trade = ActiveTrade(
                                trade_id=setup.setup_id,
                                setup_id=setup.setup_id,
                                direction=setup.direction,
                                entry_price=setup.entry_price,
                                entry_time=datetime.fromtimestamp(self.df_15m.index[fill_idx].timestamp()),
                                sl=setup.sl,
                                tp=setup.tp,
                                size=setup.size
                            )
                            
                            # Simulate trade
                            trade = self.simulate_trade(setup, self.df_15m, fill_idx)

                            self.trades_history.append(trade)
                            self.balance += trade['pnl']

                            # Mark parent FVG
                            for fvg in self.rejected_4h_fvgs:
                                if fvg.id == setup.parent_4h_fvg_id:
                                    fvg.has_filled_trade = True
                                    self.rejected_4h_fvgs.remove(fvg)
                                    break

                            # Clear active trade after close
                            self.active_trade = None

                            emoji = "✅" if trade['result'] == 'WIN' else "❌"
                            print(f"{emoji} Trade #{len(self.trades_history)} | {trade['direction']} | "
                                  f"Entry: ${trade['entry_price']:.2f} | Exit: ${trade['exit_price']:.2f} | "
                                  f"PnL: ${trade['pnl']:+.2f} ({trade['pnl_pct']:+.2f}%) | "
                                  f"Exit: {trade['exit_reason']}")

                            # Continue from next candle (don't jump forward)
                            current_15m_idx = fill_idx + 1
                            continue
                        else:
                            # Setup expired
                            # Set cooldown
                            for fvg in self.rejected_4h_fvgs:
                                if fvg.id == setup.parent_4h_fvg_id:
                                    fvg.pending_expiry_time = setup.expiry_time + timedelta(hours=4)
                                    break

                current_15m_idx += 1

        # Print results
        self.print_results()

        # Save results
        self.save_results()

    def print_results(self):
        """Print simulation results"""

        print(f"\n{'='*80}")
        print("SIMULATION RESULTS")
        print(f"{'='*80}\n")

        if not self.trades_history:
            print("No trades executed")
            return

        wins = [t for t in self.trades_history if t['result'] == 'WIN']
        losses = [t for t in self.trades_history if t['result'] == 'LOSS']

        total_pnl = sum(t['pnl'] for t in self.trades_history)
        total_pnl_pct = (total_pnl / self.initial_balance) * 100
        win_rate = len(wins) / len(self.trades_history) * 100

        avg_win = np.mean([t['pnl'] for t in wins]) if wins else 0
        avg_loss = np.mean([t['pnl'] for t in losses]) if losses else 0

        profit_factor = sum(t['pnl'] for t in wins) / abs(sum(t['pnl'] for t in losses)) if losses and sum(t['pnl'] for t in losses) != 0 else float('inf')

        print(f"📊 TRADE STATISTICS")
        print(f"   Total Trades:      {len(self.trades_history)}")
        print(f"   Wins:              {len(wins)}")
        print(f"   Losses:            {len(losses)}")
        print(f"   Win Rate:          {win_rate:.2f}%")

        print(f"\n💰 PROFIT & LOSS")
        print(f"   Total PnL:         ${total_pnl:+,.2f} ({total_pnl_pct:+.2f}%)")
        print(f"   Final Balance:     ${self.balance:,.2f}")
        print(f"   Avg Win:           ${avg_win:,.2f}")
        print(f"   Avg Loss:          ${avg_loss:,.2f}")
        print(f"   Profit Factor:     {profit_factor:.2f}")

        print()

    def save_results(self):
        """Save results to JSON"""

        wins = [t for t in self.trades_history if t['result'] == 'WIN']
        losses = [t for t in self.trades_history if t['result'] == 'LOSS']

        total_pnl = sum(t['pnl'] for t in self.trades_history)
        total_pnl_pct = (total_pnl / self.initial_balance) * 100
        win_rate = len(wins) / len(self.trades_history) * 100 if self.trades_history else 0

        avg_win = np.mean([t['pnl'] for t in wins]) if wins else 0
        avg_loss = np.mean([t['pnl'] for t in losses]) if losses else 0

        profit_factor = sum(t['pnl'] for t in wins) / abs(sum(t['pnl'] for t in losses)) if losses and sum(t['pnl'] for t in losses) != 0 else float('inf')

        results = {
            'summary': {
                'total_trades': len(self.trades_history),
                'wins': len(wins),
                'losses': len(losses),
                'win_rate': round(win_rate, 2),
                'total_pnl': round(total_pnl, 2),
                'total_pnl_pct': round(total_pnl_pct, 2),
                'avg_win': round(avg_win, 2),
                'avg_loss': round(avg_loss, 2),
                'profit_factor': round(profit_factor, 2),
                'final_balance': round(self.balance, 2)
            },
            'trades': []
        }

        # Convert trades to serializable format
        for trade in self.trades_history:
            trade_dict = {
                'trade_id': trade['trade_id'],
                'direction': trade['direction'],
                'entry_time': trade['entry_time'].isoformat(),
                'entry_price': trade['entry_price'],
                'exit_time': trade['exit_time'].isoformat(),
                'exit_price': trade['exit_price'],
                'sl': trade['sl'],
                'tp': trade['tp'],
                'size': trade['size'],
                'pnl': round(trade['pnl'], 2),
                'pnl_pct': round(trade['pnl_pct'], 2),
                'result': trade['result'],
                'exit_reason': trade['exit_reason']
            }
            results['trades'].append(trade_dict)

        filename = 'simulation_2024_results.json'
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"💾 Results saved to {filename}")


if __name__ == "__main__":
    sim = LiveBotSimulator(initial_balance=10000.0)
    sim.run_simulation(start_date='2024-01-01', end_date='2024-12-31')
    print("\n✅ Simulation complete!")
