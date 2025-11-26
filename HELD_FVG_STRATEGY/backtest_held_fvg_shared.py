"""
Backtest HELD FVG Strategy - Using SHARED logic from core/
Same logic as held_fvg_live_bot.py
"""

import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
import json
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.fvg import HeldFVG
from core.strategy import HeldFVGStrategy
import config


class BacktestTrade:
    """Trade object for backtest"""
    def __init__(self, direction: str, entry: float, sl: float, tp: float,
                 size: float, entry_time: pd.Timestamp):
        self.direction = direction
        self.entry = entry
        self.sl = sl
        self.tp = tp
        self.size = size
        self.entry_time = entry_time

        self.exit_time = None
        self.exit_price = None
        self.exit_reason = None
        self.pnl = 0.0
        self.active = True

    def check_exit(self, candle_high: float, candle_low: float, candle_time: pd.Timestamp,
                   maker_fee: float, taker_fee: float) -> bool:
        """
        Check if trade should exit on this candle
        Returns True if exited
        """
        if not self.active:
            return False

        exit_price = None
        exit_reason = None

        if self.direction == 'LONG':
            # Check SL first
            if candle_low <= self.sl:
                exit_price = self.sl
                exit_reason = 'SL'
            # Check TP
            elif candle_high >= self.tp:
                exit_price = self.tp
                exit_reason = 'TP'
        else:  # SHORT
            # Check SL first
            if candle_high >= self.sl:
                exit_price = self.sl
                exit_reason = 'SL'
            # Check TP
            elif candle_low <= self.tp:
                exit_price = self.tp
                exit_reason = 'TP'

        if exit_price:
            self.close(exit_price, candle_time, exit_reason, maker_fee, taker_fee)
            return True

        return False

    def close(self, exit_price: float, exit_time: pd.Timestamp, reason: str,
              maker_fee: float, taker_fee: float):
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

        # Calculate fees (same as live bot!)
        entry_fee = self.entry * self.size * taker_fee  # Market order
        if reason == 'TP':
            exit_fee = exit_price * self.size * maker_fee
        else:
            exit_fee = exit_price * self.size * taker_fee

        self.pnl = gross_pnl - entry_fee - exit_fee


class HeldFVGBacktest:
    """Backtest engine using SHARED core logic"""

    def __init__(self):
        self.config = config
        self.strategy = HeldFVGStrategy(
            min_sl_pct=config.MIN_SL_PCT,
            max_sl_pct=config.MAX_SL_PCT
        )

        self.balance = config.INITIAL_BALANCE
        self.active_trade: Optional[BacktestTrade] = None

        # Historical data for FVG detection (last 20 candles)
        self.candle_history_4h: List[Dict] = []

        # Stats
        self.stats = {
            'total_fvgs': 0,
            'total_holds': 0,
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'total_pnl': 0.0
        }

        self.trades: List[BacktestTrade] = []

    def detect_new_fvg(self) -> Optional[HeldFVG]:
        """Detect new FVG from last 3 candles"""
        if len(self.candle_history_4h) < 3:
            return None

        # Get last 3 candles
        candle_1 = self.candle_history_4h[-3]
        candle_2 = self.candle_history_4h[-2]
        candle_3 = self.candle_history_4h[-1]

        # Detect FVG using shared strategy
        fvg = self.strategy.detect_fvg_from_candles(
            candle_1, candle_2, candle_3,
            candle_3['time']
        )

        if fvg:
            self.stats['total_fvgs'] += 1

        return fvg

    def check_for_setup(self, current_price: float) -> Optional[Dict]:
        """Check if any held FVG can create a trade setup"""
        for held_fvg in self.strategy.held_4h_fvgs[:]:
            # Skip if already had filled trade
            if held_fvg.has_filled_trade:
                continue

            # Create setup using shared strategy
            setup = self.strategy.create_setup(held_fvg, current_price, fixed_rr=config.FIXED_RR)

            if setup:
                # Calculate position size
                size = self.strategy.calculate_position_size(
                    self.balance,
                    config.RISK_PER_TRADE,
                    setup['entry'],
                    setup['sl']
                )

                # Check minimum notional
                notional = setup['entry'] * size
                if notional < 10.0:
                    continue

                setup['size'] = size
                setup['fvg'] = held_fvg

                return setup

        return None

    def execute_trade(self, setup: Dict, entry_time: pd.Timestamp):
        """Execute trade"""
        trade = BacktestTrade(
            direction=setup['direction'],
            entry=setup['entry'],
            sl=setup['sl'],
            tp=setup['tp'],
            size=setup['size'],
            entry_time=entry_time
        )

        self.active_trade = trade
        self.stats['total_trades'] += 1

        # Mark FVG as used
        setup['fvg'].has_filled_trade = True

    def run_backtest(self, df_4h: pd.DataFrame, df_15m: pd.DataFrame,
                     start_date: str, end_date: str):
        """Run backtest for 4h_close + rr_2.0 strategy"""

        print(f"\n{'='*80}")
        print(f"HELD FVG BACKTEST - Using Shared Core Logic")
        print(f"{'='*80}")
        print(f"Period: {start_date} to {end_date}")
        print(f"Strategy: 4h_close + rr_2.0")
        print(f"Initial Balance: ${self.balance:,.2f}")
        print(f"Risk per Trade: {config.RISK_PER_TRADE*100}%")
        print(f"{'='*80}\n")

        # Filter data
        df_4h_filtered = df_4h.loc[start_date:end_date].copy()
        df_15m_filtered = df_15m.loc[start_date:end_date].copy()

        current_15m_idx = 0

        # Iterate through 4H candles
        for i in range(len(df_4h_filtered)):
            current_4h_candle = df_4h_filtered.iloc[i]
            current_4h_time = current_4h_candle.name

            candle_dict = {
                'time': current_4h_time,
                'open': float(current_4h_candle['Open']),
                'high': float(current_4h_candle['High']),
                'low': float(current_4h_candle['Low']),
                'close': float(current_4h_candle['Close']),
                'volume': float(current_4h_candle['Volume'])
            }

            # Add to history
            self.candle_history_4h.append(candle_dict)
            if len(self.candle_history_4h) > 20:
                self.candle_history_4h.pop(0)

            # Detect new FVG
            new_fvg = self.detect_new_fvg()
            if new_fvg:
                self.strategy.active_4h_fvgs.append(new_fvg)

            # Update FVG states using shared strategy
            newly_held, invalidated = self.strategy.update_fvgs(candle_dict, current_4h_time)

            if newly_held:
                for fvg in newly_held:
                    self.stats['total_holds'] += 1

            # Check if held FVG can create setup (only if no active trade)
            if not self.active_trade:
                setup = self.check_for_setup(candle_dict['close'])
                if setup:
                    self.execute_trade(setup, current_4h_time)

            # Find next 4H candle time
            next_4h_time = df_4h_filtered.index[i+1] if i+1 < len(df_4h_filtered) else df_15m_filtered.index[-1]

            # Process ALL 15M candles between current and next 4H candle
            # (Check trade exit every 15 minutes - same as live bot!)
            while current_15m_idx < len(df_15m_filtered):
                candle_15m_time = df_15m_filtered.index[current_15m_idx]

                # Stop when we reach next 4H candle
                if candle_15m_time >= next_4h_time:
                    break

                # Only process 15M candles AFTER current 4H candle
                if candle_15m_time > current_4h_time:
                    candle_15m = df_15m_filtered.iloc[current_15m_idx]

                    # Check active trade exit on each 15M candle
                    if self.active_trade:
                        exited = self.active_trade.check_exit(
                            float(candle_15m['High']),
                            float(candle_15m['Low']),
                            candle_15m.name,
                            config.MAKER_FEE,
                            config.TAKER_FEE
                        )

                        if exited:
                            # Trade closed - update stats
                            self.balance += self.active_trade.pnl
                            self.stats['total_pnl'] += self.active_trade.pnl

                            if self.active_trade.pnl > 0:
                                self.stats['wins'] += 1
                            else:
                                self.stats['losses'] += 1

                            self.trades.append(self.active_trade)
                            self.active_trade = None

                current_15m_idx += 1

        # Print results
        self.print_results()

    def print_results(self):
        """Print backtest results"""
        win_rate = (self.stats['wins'] / self.stats['total_trades'] * 100) if self.stats['total_trades'] > 0 else 0
        hold_rate = (self.stats['total_holds'] / self.stats['total_fvgs'] * 100) if self.stats['total_fvgs'] > 0 else 0

        print(f"\n{'='*80}")
        print(f"📊 BACKTEST RESULTS")
        print(f"{'='*80}")
        print(f"")
        print(f"Total 4H FVGs: {self.stats['total_fvgs']}")
        print(f"Total Holds: {self.stats['total_holds']}")
        print(f"Hold Rate: {hold_rate:.1f}%")
        print(f"")
        print(f"Total Trades: {self.stats['total_trades']}")
        print(f"Wins: {self.stats['wins']}")
        print(f"Losses: {self.stats['losses']}")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"")
        print(f"Total PnL: ${self.stats['total_pnl']:.2f}")
        print(f"Final Balance: ${self.balance:.2f}")
        print(f"ROI: {((self.balance - config.INITIAL_BALANCE) / config.INITIAL_BALANCE * 100):+.1f}%")
        print(f"")
        print(f"{'='*80}\n")


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
    backtester = HeldFVGBacktest()
    backtester.run_backtest(df_4h, df_15m, start_date, end_date)

    # Save results
    output = {
        'stats': backtester.stats,
        'final_balance': backtester.balance,
        'roi': ((backtester.balance - config.INITIAL_BALANCE) / config.INITIAL_BALANCE * 100)
    }

    output_file = f"backtest_shared_logic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)

    print(f"✅ Results saved to: {output_file}")
