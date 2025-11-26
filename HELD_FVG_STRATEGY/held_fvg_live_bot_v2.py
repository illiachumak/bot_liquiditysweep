"""
HELD FVG Live Bot V2 - Uses BACKTEST logic directly
Guarantees 1-to-1 match with backtest results
"""

import pandas as pd
import time
from datetime import datetime
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backtest_held_fvg import HeldFVGBacktester
import config


class HeldFVGBot:
    """Live bot that uses exact backtest logic"""

    def __init__(self):
        self.config = config

        # Use backtest class directly!
        self.backtester = HeldFVGBacktester(
            min_sl_pct=config.MIN_SL_PCT,
            max_sl_pct=config.MAX_SL_PCT,
            risk_per_trade=config.RISK_PER_TRADE,
            initial_balance=config.INITIAL_BALANCE,
            enable_fees=True
        )

        self.balance = config.INITIAL_BALANCE
        self.stats = {}

        # Load simulation data
        if config.SIMULATION_MODE:
            self.load_simulation_data()

        print(f"✅ Bot initialized (using BACKTEST logic)")
        print(f"Mode: {'SIMULATION' if config.SIMULATION_MODE else 'LIVE'}")
        print(f"Balance: ${self.balance:,.2f}\n")

    def load_simulation_data(self):
        """Load historical data for simulation"""
        print("📊 Loading simulation data...")

        # Load 4H data
        df_4h = pd.read_csv(config.DATA_PATH_4H)
        df_4h['Open time'] = pd.to_datetime(df_4h['Open time'])
        df_4h.set_index('Open time', inplace=True)
        df_4h = df_4h.loc[config.SIMULATION_START_DATE:config.SIMULATION_END_DATE]

        # Load 15M data
        df_15m = pd.read_csv(config.DATA_PATH_15M)
        df_15m['Open time'] = pd.to_datetime(df_15m['Open time'])
        df_15m.set_index('Open time', inplace=True)
        df_15m = df_15m.loc[config.SIMULATION_START_DATE:config.SIMULATION_END_DATE]

        self.sim_df_4h = df_4h
        self.sim_df_15m = df_15m

        print(f"✅ Loaded {len(df_4h)} 4H candles, {len(df_15m)} 15M candles\n")

    def run_simulation(self):
        """Run simulation - simply calls backtest logic"""
        print(f"{'='*80}")
        print(f"🎮 SIMULATION MODE - Using BACKTEST logic")
        print(f"Period: {config.SIMULATION_START_DATE} to {config.SIMULATION_END_DATE}")
        print(f"Strategy: 4h_close + rr_2.0")
        print(f"{'='*80}\n")

        # Run backtest!
        results = self.backtester.run_single_combination(
            df_4h=self.sim_df_4h,
            df_15m=self.sim_df_15m,
            entry_method='4h_close',
            tp_method='rr_2.0',
            start_date=config.SIMULATION_START_DATE,
            end_date=config.SIMULATION_END_DATE
        )

        # Store results
        self.stats = results
        self.balance = results['final_balance']

        # Print stats
        self.print_stats()

    def print_stats(self):
        """Print bot statistics"""
        if not self.stats:
            return

        win_rate = self.stats['win_rate']

        print(f"\n{'='*80}")
        print(f"📊 BOT STATISTICS")
        print(f"{'='*80}")
        print(f"")
        print(f"Total 4H FVGs: {self.stats['stats']['total_4h_fvgs']}")
        print(f"Total Holds: {self.stats['stats']['total_holds']}")
        print(f"Hold Rate: {(self.stats['stats']['total_holds']/self.stats['stats']['total_4h_fvgs']*100) if self.stats['stats']['total_4h_fvgs'] > 0 else 0:.1f}%")
        print(f"")
        print(f"Total Trades: {self.stats['total_trades']}")
        print(f"Wins: {self.stats['winning_trades']}")
        print(f"Losses: {self.stats['losing_trades']}")
        print(f"Win Rate: {win_rate:.1f}%")
        print(f"")
        print(f"Total PnL: ${self.stats['total_pnl']:.2f}")
        print(f"Final Balance: ${self.balance:.2f}")
        print(f"ROI: {((self.balance - config.INITIAL_BALANCE) / config.INITIAL_BALANCE * 100):+.1f}%")
        print(f"")
        print(f"{'='*80}\n")


def main():
    """Main entry point"""
    # Print configuration
    config.print_config()

    # Create bot
    bot = HeldFVGBot()

    # Run in appropriate mode
    if config.SIMULATION_MODE:
        bot.run_simulation()
    else:
        print("⚠️  LIVE mode not implemented yet!")
        print("Use SIMULATION_MODE=True for now")


if __name__ == "__main__":
    main()
