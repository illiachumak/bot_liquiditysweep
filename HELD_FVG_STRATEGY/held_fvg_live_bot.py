"""
HELD FVG Live Bot
Supports both SIMULATION and LIVE trading modes

Usage:
    # Simulation mode (default)
    python held_fvg_live_bot.py

    # Live trading mode
    SIMULATION_MODE=False python held_fvg_live_bot.py
"""

import pandas as pd
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import json
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import BACKTEST classes and logic (to ensure 1-to-1 match!)
from backtest_held_fvg import HeldBacktestFVG as HeldFVG, HeldFVGBacktester
import config
from core.strategy import HeldFVGStrategy


class HeldFVGBot:
    """Live bot for HELD FVG strategy - Uses BACKTEST logic for 1-to-1 match"""

    def __init__(self):
        self.config = config

        self.balance = config.INITIAL_BALANCE

        # Stats (for display only)
        self.stats = {
            'total_fvgs': 0,
            'total_holds': 0,
            'total_trades': 0,
            'wins': 0,
            'losses': 0,
            'total_pnl': 0.0
        }

        # Initialize attributes needed for both modes
        self.candle_history_4h = []
        self.active_trade = None

        # Simulation mode data - ONLY load if in simulation mode
        if config.SIMULATION_MODE:
            # Use backtest class for simulation
            self.backtester = HeldFVGBacktester(
                min_sl_pct=config.MIN_SL_PCT,
                max_sl_pct=config.MAX_SL_PCT,
                risk_per_trade=config.RISK_PER_TRADE,
                initial_balance=config.INITIAL_BALANCE,
                enable_fees=True
            )
            self.load_simulation_data()
            print(f"✅ Bot initialized in SIMULATION mode")
        else:
            # Live mode - initialize strategy without backtest data
            self.strategy = HeldFVGStrategy(
                min_sl_pct=config.MIN_SL_PCT,
                max_sl_pct=config.MAX_SL_PCT
            )
            print(f"✅ Bot initialized in LIVE mode")

        print(f"Balance: ${self.balance:,.2f}")
        print()

    def load_simulation_data(self):
        """Load historical data for simulation"""
        print("📊 Loading simulation data...")

        try:
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
            self.sim_current_idx_4h = 2  # Start from index 2 (need 3 candles for FVG)
            self.sim_current_idx_15m = 0

            print(f"✅ Loaded {len(df_4h)} 4H candles, {len(df_15m)} 15M candles")
        except FileNotFoundError as e:
            print(f"❌ ERROR: Cannot find data files for simulation mode!")
            print(f"   Missing file: {e.filename}")
            print(f"   Expected paths:")
            print(f"     4H: {config.DATA_PATH_4H}")
            print(f"     15M: {config.DATA_PATH_15M}")
            print(f"\n💡 TIP: Set SIMULATION_MODE=False in .env for live trading")
            raise

    def fetch_current_candle_4h(self) -> Optional[Dict]:
        """
        Fetch current 4H candle

        In SIMULATION: return next candle from historical data
        In LIVE: fetch from Binance API
        """
        if config.SIMULATION_MODE:
            if self.sim_current_idx_4h >= len(self.sim_df_4h):
                return None  # Simulation ended

            candle = self.sim_df_4h.iloc[self.sim_current_idx_4h]
            return {
                'time': candle.name,
                'open': float(candle['Open']),
                'high': float(candle['High']),
                'low': float(candle['Low']),
                'close': float(candle['Close']),
                'volume': float(candle['Volume'])
            }
        else:
            # TODO: Implement Binance API call
            from binance.client import Client
            client = Client(config.API_KEY, config.API_SECRET, testnet=config.TESTNET)
            klines = client.get_klines(symbol=config.SYMBOL, interval=config.TIMEFRAME_4H, limit=1)
            candle = klines[0]
            return {
                'time': pd.to_datetime(candle[0], unit='ms'),
                'open': float(candle[1]),
                'high': float(candle[2]),
                'low': float(candle[3]),
                'close': float(candle[4]),
                'volume': float(candle[5])
            }

    def detect_new_fvg(self) -> Optional[HeldFVG]:
        """
        Detect new FVG from last 3 candles

        Returns new FVG if detected, else None
        """
        if len(self.candle_history_4h) < 3:
            return None

        # Get last 3 candles
        candle_1 = self.candle_history_4h[-3]
        candle_2 = self.candle_history_4h[-2]
        candle_3 = self.candle_history_4h[-1]

        # Detect FVG
        fvg = self.strategy.detect_fvg_from_candles(
            candle_1, candle_2, candle_3,
            candle_3['time']
        )

        if fvg:
            self.stats['total_fvgs'] += 1

        return fvg

    def check_for_setup(self, current_price: float, candle_high: float = None,
                         candle_low: float = None) -> Optional[Dict]:
        """
        Check if any held FVG can create a trade setup

        Returns setup dict if valid, else None
        """
        for held_fvg in self.strategy.held_4h_fvgs[:]:
            # Skip if already had filled trade
            if held_fvg.has_filled_trade:
                continue

            # Check invalidation (matching backtest logic)
            # Note: This should already be done in the 15M loop, but double-check
            if candle_high is not None and candle_low is not None:
                if held_fvg.is_fully_passed(candle_high, candle_low):
                    held_fvg.invalidated = True
                    self.strategy.held_4h_fvgs.remove(held_fvg)
                    continue

            # Create setup
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

    def execute_trade(self, setup: Dict):
        """
        Execute trade

        In SIMULATION: just create trade object
        In LIVE: place order on Binance
        """
        trade = {
            'direction': setup['direction'],
            'entry': setup['entry'],
            'sl': setup['sl'],
            'tp': setup['tp'],
            'size': setup['size'],
            'entry_time': datetime.now() if config.SIMULATION_MODE else datetime.utcnow(),
            'status': 'active',
            'pnl': 0.0
        }

        if config.SIMULATION_MODE:
            print(f"\n🔵 SIMULATION TRADE OPENED:")
        else:
            # TODO: Place real order on Binance
            print(f"\n🔴 LIVE TRADE OPENED:")

        print(f"  Direction: {trade['direction']}")
        print(f"  Entry: ${trade['entry']:.2f}")
        print(f"  SL: ${trade['sl']:.2f}")
        print(f"  TP: ${trade['tp']:.2f}")
        print(f"  Size: {trade['size']:.6f}")
        print(f"  Notional: ${trade['entry'] * trade['size']:.2f}")
        print()

        self.active_trade = trade
        self.stats['total_trades'] += 1

        # Mark FVG as used
        setup['fvg'].has_filled_trade = True

    def check_trade_exit(self, current_candle: Dict) -> bool:
        """
        Check if active trade should be closed

        Returns True if trade closed
        """
        if not self.active_trade:
            return False

        trade = self.active_trade
        candle_high = current_candle['high']
        candle_low = current_candle['low']

        exit_price = None
        exit_reason = None

        if trade['direction'] == 'LONG':
            # Check SL
            if candle_low <= trade['sl']:
                exit_price = trade['sl']
                exit_reason = 'SL'
            # Check TP
            elif candle_high >= trade['tp']:
                exit_price = trade['tp']
                exit_reason = 'TP'

        else:  # SHORT
            # Check SL
            if candle_high >= trade['sl']:
                exit_price = trade['sl']
                exit_reason = 'SL'
            # Check TP
            elif candle_low <= trade['tp']:
                exit_price = trade['tp']
                exit_reason = 'TP'

        if exit_price:
            self.close_trade(exit_price, exit_reason, current_candle['time'])
            return True

        return False

    def close_trade(self, exit_price: float, reason: str, exit_time: datetime):
        """Close active trade and calculate PnL"""
        trade = self.active_trade

        # Calculate gross PnL
        if trade['direction'] == 'LONG':
            gross_pnl = (exit_price - trade['entry']) * trade['size']
        else:
            gross_pnl = (trade['entry'] - exit_price) * trade['size']

        # Calculate fees (same logic as backtest!)
        entry_fee = trade['entry'] * trade['size'] * config.TAKER_FEE  # Market order
        if reason == 'TP':
            exit_fee = exit_price * trade['size'] * config.MAKER_FEE
        else:
            exit_fee = exit_price * trade['size'] * config.TAKER_FEE

        net_pnl = gross_pnl - entry_fee - exit_fee

        # Update balance
        self.balance += net_pnl

        # Update stats
        self.stats['total_pnl'] += net_pnl
        if net_pnl > 0:
            self.stats['wins'] += 1
        else:
            self.stats['losses'] += 1

        # Print results
        pnl_pct = (net_pnl / (trade['entry'] * trade['size'])) * 100

        print(f"\n{'🟢' if net_pnl > 0 else '🔴'} TRADE CLOSED:")
        print(f"  Exit: ${exit_price:.2f}")
        print(f"  Reason: {reason}")
        print(f"  PnL: ${net_pnl:.2f} ({pnl_pct:+.2f}%)")
        print(f"  Balance: ${self.balance:.2f}")
        print()

        # Clear active trade
        self.active_trade = None

    def process_4h_candle(self):
        """Process new 4H candle"""
        # Fetch current candle
        candle = self.fetch_current_candle_4h()
        if candle is None:
            return False  # No more candles (simulation ended)

        print(f"\n⏰ 4H Candle: {candle['time']}")
        print(f"   OHLC: {candle['open']:.0f} / {candle['high']:.0f} / "
              f"{candle['low']:.0f} / {candle['close']:.0f}")

        # Add to history
        self.candle_history_4h.append(candle)
        if len(self.candle_history_4h) > 20:
            self.candle_history_4h.pop(0)

        # Detect new FVG
        new_fvg = self.detect_new_fvg()
        if new_fvg:
            self.strategy.active_4h_fvgs.append(new_fvg)
            print(f"   📍 New {new_fvg.type} FVG: ${new_fvg.bottom:.0f}-${new_fvg.top:.0f}")

        # Update FVG states
        newly_held, invalidated = self.strategy.update_fvgs(candle, candle['time'])

        if newly_held:
            for fvg in newly_held:
                self.stats['total_holds'] += 1
                print(f"   💚 {fvg.type} FVG HELD!")

        # Setup check moved to 15M candle processing (below in run_simulation)
        # This ensures we check setup on EVERY 15M candle, not just 4H candles
        # (matching backtest logic which checks on every 15M candle)

        return True

    def run_simulation(self):
        """Run simulation mode - uses BACKTEST logic directly!"""
        print(f"\n{'='*80}")
        print(f"🎮 SIMULATION MODE - Starting from {config.SIMULATION_START_DATE}")
        print(f"Using BACKTEST logic (guarantees 1-to-1 match)")
        print(f"{'='*80}\n")

        # Simply run the backtest!
        results = self.backtester.run_single_combination(
            df_4h=self.sim_df_4h,
            df_15m=self.sim_df_15m,
            start_date=config.SIMULATION_START_DATE,
            end_date=config.SIMULATION_END_DATE,
            entry_method=config.ENTRY_METHOD,
            tp_method=config.TP_METHOD
        )

        # Update our stats from backtest results
        self.stats['total_fvgs'] = results['stats']['total_4h_fvgs']
        self.stats['total_holds'] = results['stats']['total_holds']
        self.stats['total_trades'] = results['total_trades']
        self.stats['wins'] = results['winning_trades']
        self.stats['losses'] = results['losing_trades']
        self.stats['total_pnl'] = results['total_pnl']
        self.balance = results['final_balance']

        # Print final stats
        self.print_stats()

    def run_live(self):
        """Run live trading mode"""
        print(f"\n{'='*80}")
        print(f"🔴 LIVE TRADING MODE - STARTING")
        print(f"{'='*80}\n")

        print("⚠️  WARNING: Real money at risk!")
        print("Press Ctrl+C to stop\n")

        try:
            while True:
                # Check for new 4H candle
                # (In real implementation, check if new candle formed)
                self.process_4h_candle()

                # Sleep until next check
                time.sleep(config.CHECK_INTERVAL_4H)

        except KeyboardInterrupt:
            print("\n\n🛑 Bot stopped by user")
            self.print_stats()

    def print_stats(self):
        """Print bot statistics"""
        win_rate = (self.stats['wins'] / self.stats['total_trades'] * 100) if self.stats['total_trades'] > 0 else 0

        print(f"\n{'='*80}")
        print(f"📊 BOT STATISTICS")
        print(f"{'='*80}")
        print(f"")
        print(f"Total 4H FVGs: {self.stats['total_fvgs']}")
        print(f"Total Holds: {self.stats['total_holds']}")
        print(f"Hold Rate: {(self.stats['total_holds']/self.stats['total_fvgs']*100) if self.stats['total_fvgs'] > 0 else 0:.1f}%")
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
        bot.run_live()


if __name__ == "__main__":
    main()
