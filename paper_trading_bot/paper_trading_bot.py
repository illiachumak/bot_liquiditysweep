"""
Paper Trading Bot - Liquidity Reversal Strategy
================================================
Bot monitors Binance for real-time data and logs trade signals to JSON.
Does NOT execute real trades - only logs entry/exit signals for testing.

Usage:
    1. Install: pip install python-binance pandas
    2. Run: python paper_trading_bot.py
"""

import sys
import os
import json
import time
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from binance.client import Client
from binance.exceptions import BinanceAPIException

# Import strategy components from backtest
sys.path.append(os.path.dirname(__file__))
from liquidity_reversal_backtest import (
    LiquiditySweepDetector,
    FVGDetector,
    VolumeAnalyzer,
    ReversalDetector
)


class BinanceDataFeed:
    """Fetches real-time data from Binance"""

    def __init__(self, symbol: str = 'BTCUSDT'):
        """
        Initialize Binance client (public API, no keys needed for market data)

        Args:
            symbol: Trading pair (default: BTCUSDT)
        """
        self.symbol = symbol
        self.client = Client()  # Public API (no authentication needed)

    def get_klines(self, interval: str, limit: int = 500) -> pd.DataFrame:
        """
        Fetch historical klines (candlestick data)

        Args:
            interval: Timeframe (1m, 5m, 15m, 1h, 4h, 1d, etc.)
            limit: Number of candles to fetch (max 1000)

        Returns:
            DataFrame with OHLCV data
        """
        try:
            klines = self.client.get_klines(
                symbol=self.symbol,
                interval=interval,
                limit=limit
            )

            # Convert to DataFrame
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])

            # Convert types
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)

            # Keep only OHLCV
            df = df[['open', 'high', 'low', 'close', 'volume']]

            return df

        except BinanceAPIException as e:
            print(f"Binance API Error: {e}")
            return pd.DataFrame()

    def get_latest_price(self) -> float:
        """Get current price"""
        try:
            ticker = self.client.get_symbol_ticker(symbol=self.symbol)
            return float(ticker['price'])
        except BinanceAPIException as e:
            print(f"Error getting price: {e}")
            return 0.0


class PaperTrade:
    """Represents a paper trade with fill tracking"""

    def __init__(self, signal: Dict):
        """Initialize paper trade from signal"""
        self.signal_time = signal['timestamp']
        self.entry_time = signal['entry_time']
        self.direction = signal['direction']
        self.entry_price = signal['entry_price']
        self.stop_loss = signal['stop_loss']
        self.tp1 = signal['tp1']
        self.tp2 = signal['tp2']
        self.tp3 = signal['tp3']
        self.size = signal['size']
        self.risk_usd = signal['risk_usd']
        self.volume_ratio = signal['volume_ratio']
        self.sweep_type = signal['sweep_type']

        # Status tracking
        self.status = 'PENDING'  # PENDING -> FILLED -> CLOSED/CANCELLED
        self.fill_price = None
        self.fill_time = None
        self.exit_price = None
        self.exit_time = None
        self.exit_reason = None
        self.pnl = 0.0
        self.pnl_pct = 0.0

        # Partial exits tracking
        self.tp1_hit = False
        self.tp2_hit = False
        self.tp3_hit = False

    def check_fill(self, candle: pd.Series) -> bool:
        """Check if limit order would be filled on this candle"""
        if self.status != 'PENDING':
            return False

        high = candle['high']
        low = candle['low']

        # Check if price reached our limit order
        if self.direction == 'LONG':
            # For LONG, limit order at entry_price - fills if price drops to it
            if low <= self.entry_price:
                self.status = 'FILLED'
                self.fill_price = self.entry_price
                self.fill_time = candle.name
                return True
        else:  # SHORT
            # For SHORT, limit order at entry_price - fills if price rises to it
            if high >= self.entry_price:
                self.status = 'FILLED'
                self.fill_price = self.entry_price
                self.fill_time = candle.name
                return True

        return False

    def check_exit(self, candle: pd.Series) -> Optional[str]:
        """Check if position hit SL or TP"""
        if self.status != 'FILLED':
            return None

        high = candle['high']
        low = candle['low']

        if self.direction == 'LONG':
            # Check stop loss
            if low <= self.stop_loss:
                self.status = 'CLOSED'
                self.exit_price = self.stop_loss
                self.exit_time = candle.name
                self.exit_reason = 'STOP_LOSS'
                self.pnl = (self.stop_loss - self.fill_price) * self.size
                self.pnl_pct = ((self.stop_loss - self.fill_price) / self.fill_price) * 100
                return 'STOP_LOSS'

            # Check take profits
            if not self.tp1_hit and high >= self.tp1:
                self.tp1_hit = True
                return 'TP1'
            if not self.tp2_hit and high >= self.tp2:
                self.tp2_hit = True
                return 'TP2'
            if not self.tp3_hit and high >= self.tp3:
                self.tp3_hit = True
                self.status = 'CLOSED'
                self.exit_price = self.tp3
                self.exit_time = candle.name
                self.exit_reason = 'ALL_TPS'
                self.pnl = (self.tp3 - self.fill_price) * self.size
                self.pnl_pct = ((self.tp3 - self.fill_price) / self.fill_price) * 100
                return 'TP3'

        else:  # SHORT
            # Check stop loss
            if high >= self.stop_loss:
                self.status = 'CLOSED'
                self.exit_price = self.stop_loss
                self.exit_time = candle.name
                self.exit_reason = 'STOP_LOSS'
                self.pnl = (self.fill_price - self.stop_loss) * self.size
                self.pnl_pct = ((self.fill_price - self.stop_loss) / self.fill_price) * 100
                return 'STOP_LOSS'

            # Check take profits
            if not self.tp1_hit and low <= self.tp1:
                self.tp1_hit = True
                return 'TP1'
            if not self.tp2_hit and low <= self.tp2:
                self.tp2_hit = True
                return 'TP2'
            if not self.tp3_hit and low <= self.tp3:
                self.tp3_hit = True
                self.status = 'CLOSED'
                self.exit_price = self.tp3
                self.exit_time = candle.name
                self.exit_reason = 'ALL_TPS'
                self.pnl = (self.fill_price - self.tp3) * self.size
                self.pnl_pct = ((self.fill_price - self.tp3) / self.fill_price) * 100
                return 'TP3'

        return None

    def to_dict(self) -> Dict:
        """Convert to dictionary for logging"""
        return {
            'signal_time': self.signal_time,
            'entry_time': self.entry_time,
            'direction': self.direction,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'tp1': self.tp1,
            'tp2': self.tp2,
            'tp3': self.tp3,
            'size': self.size,
            'risk_usd': self.risk_usd,
            'volume_ratio': self.volume_ratio,
            'sweep_type': self.sweep_type,
            'status': self.status,
            'fill_price': self.fill_price,
            'fill_time': str(self.fill_time) if self.fill_time else None,
            'exit_price': self.exit_price,
            'exit_time': str(self.exit_time) if self.exit_time else None,
            'exit_reason': self.exit_reason,
            'tp1_hit': self.tp1_hit,
            'tp2_hit': self.tp2_hit,
            'tp3_hit': self.tp3_hit,
            'pnl': self.pnl,
            'pnl_pct': self.pnl_pct
        }


class PaperTradingBot:
    """
    Paper trading bot that monitors Binance and logs signals
    """

    def __init__(self,
                 symbol: str = 'BTCUSDT',
                 initial_balance: float = 10000,
                 risk_per_trade: float = 0.02,
                 volume_threshold: float = 1.2,
                 sweep_lookback: int = 20,
                 volume_lookback: int = 25,
                 min_stop_loss_pct: float = 0.003,
                 max_position_size: float = 10.0,
                 check_interval: int = 60):
        """
        Initialize paper trading bot

        Args:
            symbol: Trading pair
            initial_balance: Starting virtual balance in USDT
            risk_per_trade: Risk % per trade (0.02 = 2%)
            volume_threshold: Minimum volume ratio (1.2 = 20% above avg)
            sweep_lookback: Lookback for sweep detection
            volume_lookback: Lookback for volume calculation
            min_stop_loss_pct: Min stop loss % (0.003 = 0.3%)
            max_position_size: Max position in BTC
            check_interval: How often to check for signals (seconds)
        """
        self.symbol = symbol
        self.balance = initial_balance
        self.risk_per_trade = risk_per_trade
        self.volume_threshold = volume_threshold
        self.volume_lookback = volume_lookback
        self.min_stop_loss_pct = min_stop_loss_pct
        self.max_position_size = max_position_size
        self.check_interval = check_interval

        # Binance data feed
        self.data_feed = BinanceDataFeed(symbol)

        # Strategy components
        self.sweep_detector = LiquiditySweepDetector(lookback=sweep_lookback)
        self.fvg_detector = FVGDetector()
        self.volume_analyzer = VolumeAnalyzer()
        self.reversal_detector = ReversalDetector()

        # Track active sweeps and signals
        self.active_sweeps = []
        self.pending_trades = []  # Trades waiting to be filled
        self.active_trades = []   # Trades that are filled
        self.closed_trades = []   # Completed trades
        self.signals_log = []

        # Last checked candle times
        self.last_4h_time = None
        self.last_15m_time = None

        # Setup logging directory
        self.logs_dir = Path(__file__).parent / 'paper_trading_logs'
        self.logs_dir.mkdir(exist_ok=True)

        # Signal log file
        self.signal_log_file = self.logs_dir / f'signals_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'

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

        # Filter: Minimum stop loss
        min_risk = entry_price * self.min_stop_loss_pct
        if risk_per_unit < min_risk:
            return None

        size = risk_amount / risk_per_unit

        # Filter: Maximum position size
        if self.max_position_size and size > self.max_position_size:
            return None

        return size

    def check_4h_for_sweeps(self, df_4h: pd.DataFrame) -> None:
        """Check 4H timeframe for new liquidity sweeps"""

        if len(df_4h) < self.sweep_detector.lookback + 5:
            return

        # Check only the most recent completed candle
        current_idx = len(df_4h) - 1
        current_time = df_4h.index[current_idx]

        # Skip if already checked
        if self.last_4h_time and current_time <= self.last_4h_time:
            return

        self.last_4h_time = current_time

        # Detect sweep
        sweep = self.sweep_detector.detect_liquidity_sweep(df_4h, current_idx)

        if sweep:
            print(f"\n🎯 LIQUIDITY SWEEP DETECTED!")
            print(f"   Time: {sweep['sweep_time']}")
            print(f"   Type: {sweep['type']}")
            print(f"   Level: ${sweep['swept_level']:,.2f}")

            # Add to active sweeps
            self.active_sweeps.append(sweep)

            # Log sweep
            self.log_event({
                'type': 'SWEEP_DETECTED',
                'time': str(sweep['sweep_time']),
                'sweep_type': sweep['type'],
                'swept_level': float(sweep['swept_level']),
                'current_price': float(df_4h.iloc[current_idx]['close'])
            })

    def check_15m_for_entries(self, df_4h: pd.DataFrame, df_15m: pd.DataFrame) -> None:
        """Check 15M timeframe for entry signals"""

        if len(df_15m) < 25:
            return

        # Check only the most recent completed candle
        current_idx = len(df_15m) - 1
        current_time = df_15m.index[current_idx]

        # Skip if already checked
        if self.last_15m_time and current_time <= self.last_15m_time:
            return

        self.last_15m_time = current_time

        # Check each active sweep for entry conditions
        for sweep in self.active_sweeps[:]:
            # Skip if sweep is too old (>48 hours)
            time_since_sweep = (current_time - sweep['sweep_time']).total_seconds() / 3600
            if time_since_sweep > 48:
                self.active_sweeps.remove(sweep)
                continue

            # Skip if 15m candle is before sweep
            if current_time < sweep['sweep_time']:
                continue

            # Check entry conditions
            signal = self.check_entry_conditions(df_15m, current_idx, sweep)

            if signal:
                # Remove sweep from active list
                self.active_sweeps.remove(sweep)

                # Create trade parameters
                trade_params = self.create_trade_params(signal)

                if trade_params:
                    # Create PaperTrade object
                    paper_trade = PaperTrade(trade_params)
                    self.pending_trades.append(paper_trade)

                    # Log signal
                    print(f"\n📈 ENTRY SIGNAL DETECTED!")
                    print(f"   Time: {trade_params['entry_time']}")
                    print(f"   Direction: {trade_params['direction']}")
                    print(f"   Entry Price: ${trade_params['entry_price']:,.2f}")
                    print(f"   Stop Loss: ${trade_params['stop_loss']:,.2f}")
                    print(f"   TP1: ${trade_params['tp1']:,.2f} (1:2 RR)")
                    print(f"   TP2: ${trade_params['tp2']:,.2f} (1:3 RR)")
                    print(f"   TP3: ${trade_params['tp3']:,.2f} (1:5 RR)")
                    print(f"   Position Size: {trade_params['size']:.4f} BTC")
                    print(f"   Volume Ratio: {trade_params['volume_ratio']:.2f}x")
                    print(f"   Status: PENDING (waiting for fill)")

                    self.signals_log.append(trade_params)
                    self.save_signal(paper_trade.to_dict())

                break  # Only one entry per check

    def check_entry_conditions(self, df_15m: pd.DataFrame, idx: int,
                               sweep_info: Dict) -> Optional[Dict]:
        """
        Check if entry conditions are met on 15m candle

        Returns:
            Entry signal dict or None
        """
        candle = df_15m.iloc[idx]

        # 1. Check if near swept liquidity level
        liquidity_level = sweep_info['swept_level']
        tolerance = liquidity_level * 0.005  # 0.5% tolerance

        candle_near_level = (candle['low'] <= liquidity_level + tolerance and
                           candle['high'] >= liquidity_level - tolerance)

        if not candle_near_level:
            return None

        # 2. Check for reversal candle
        is_bullish_reversal = False
        is_bearish_reversal = False

        if sweep_info['type'] == 'LOW':
            is_bullish_reversal = self.reversal_detector.detect_bullish_reversal(
                df_15m, idx, min_body_pct=0.5
            )
        else:  # HIGH sweep
            is_bearish_reversal = self.reversal_detector.detect_bearish_reversal(
                df_15m, idx, min_body_pct=0.5
            )

        if not (is_bullish_reversal or is_bearish_reversal):
            return None

        # 3. Check volume
        volume_ratio = self.volume_analyzer.calculate_volume_ratio(
            df_15m, idx, lookback=self.volume_lookback
        )

        if volume_ratio < self.volume_threshold * 0.8:  # 80% of threshold
            return None

        # 4. Check for FVG (optional)
        fvg = self.fvg_detector.detect_fvg(df_15m, idx)

        # Check previous candles if no FVG
        if not fvg and idx >= 2:
            for check_idx in [idx - 1, idx - 2]:
                fvg = self.fvg_detector.detect_fvg(df_15m, check_idx)
                if fvg:
                    break

        # Calculate entry price (limit order at liquidity level)
        if sweep_info['type'] == 'LOW':
            entry_price = liquidity_level * 1.0005  # LONG: 0.05% above
        else:
            entry_price = liquidity_level * 0.9995  # SHORT: 0.05% below

        return {
            'direction': 'LONG' if sweep_info['type'] == 'LOW' else 'SHORT',
            'entry_price': entry_price,
            'entry_time': df_15m.index[idx],
            'volume_ratio': volume_ratio,
            'fvg': fvg,
            'sweep_info': sweep_info
        }

    def create_trade_params(self, signal: Dict) -> Optional[Dict]:
        """
        Create trade parameters from signal

        Returns:
            Trade parameters dict or None if filtered
        """
        direction = signal['direction']
        entry_price = signal['entry_price']

        # Calculate stop loss
        if direction == 'LONG':
            stop_loss = signal['sweep_info']['swept_level'] * 0.995  # 0.5% below
            risk = entry_price - stop_loss

            # Calculate take profits
            tp1 = entry_price + risk * 2  # 1:2 RR
            tp2 = entry_price + risk * 3  # 1:3 RR
            tp3 = entry_price + risk * 5  # 1:5 RR
        else:  # SHORT
            stop_loss = signal['sweep_info']['swept_level'] * 1.005  # 0.5% above
            risk = stop_loss - entry_price

            # Calculate take profits
            tp1 = entry_price - risk * 2
            tp2 = entry_price - risk * 3
            tp3 = entry_price - risk * 5

        # Calculate position size (with filters)
        size = self.calculate_position_size(entry_price, stop_loss)

        if size is None or size <= 0:
            print(f"   ⚠️  Signal filtered out (size constraints)")
            return None

        # Calculate risk in USD
        risk_usd = abs(entry_price - stop_loss) * size

        return {
            'timestamp': datetime.now().isoformat(),
            'entry_time': str(signal['entry_time']),
            'direction': direction,
            'entry_price': float(entry_price),
            'stop_loss': float(stop_loss),
            'tp1': float(tp1),
            'tp2': float(tp2),
            'tp3': float(tp3),
            'size': float(size),
            'risk_usd': float(risk_usd),
            'risk_pct': float(self.risk_per_trade * 100),
            'volume_ratio': float(signal['volume_ratio']),
            'sweep_type': signal['sweep_info']['type'],
            'swept_level': float(signal['sweep_info']['swept_level']),
            'fvg': {
                'type': signal['fvg']['type'],
                'top': float(signal['fvg']['top']),
                'bottom': float(signal['fvg']['bottom'])
            } if signal['fvg'] else None,
            'order_type': 'LIMIT',
            'status': 'SIGNAL_GENERATED'
        }

    def log_event(self, event: Dict) -> None:
        """Log event to console and file"""
        with open(self.signal_log_file, 'a') as f:
            f.write(json.dumps(event) + '\n')

    def save_signal(self, signal: Dict) -> None:
        """Save signal to JSON file"""
        self.log_event(signal)

    def track_trades(self, df_15m: pd.DataFrame) -> None:
        """Track pending and active trades for fills and exits"""

        if len(df_15m) < 1:
            return

        # Get current candle
        current_candle = df_15m.iloc[-1]

        # Check pending trades for fills
        for trade in self.pending_trades[:]:
            if trade.check_fill(current_candle):
                self.pending_trades.remove(trade)
                self.active_trades.append(trade)

                print(f"\n✅ ORDER FILLED!")
                print(f"   Direction: {trade.direction}")
                print(f"   Fill Price: ${trade.fill_price:,.2f}")
                print(f"   Fill Time: {trade.fill_time}")
                print(f"   Size: {trade.size:.4f} BTC")
                print(f"   Status: FILLED")

                # Update log
                self.save_signal(trade.to_dict())

        # Check active trades for exits
        for trade in self.active_trades[:]:
            exit_reason = trade.check_exit(current_candle)

            if exit_reason:
                if exit_reason in ['TP1', 'TP2']:
                    # Partial exit
                    print(f"\n🎯 {exit_reason} HIT!")
                    print(f"   Direction: {trade.direction}")
                    print(f"   Price: ${current_candle['close']:,.2f}")
                    print(f"   Time: {current_candle.name}")

                    # Update log
                    self.save_signal(trade.to_dict())

                elif exit_reason in ['STOP_LOSS', 'TP3', 'ALL_TPS']:
                    # Full exit
                    self.active_trades.remove(trade)
                    self.closed_trades.append(trade)

                    # Update balance
                    self.balance += trade.pnl

                    if exit_reason == 'STOP_LOSS':
                        print(f"\n🛑 STOP LOSS HIT!")
                    else:
                        print(f"\n🎉 ALL TPS HIT!")

                    print(f"   Direction: {trade.direction}")
                    print(f"   Entry: ${trade.fill_price:,.2f}")
                    print(f"   Exit: ${trade.exit_price:,.2f}")
                    print(f"   PnL: ${trade.pnl:+,.2f} ({trade.pnl_pct:+.2f}%)")
                    print(f"   New Balance: ${self.balance:,.2f}")
                    print(f"   Status: CLOSED")

                    # Update log
                    self.save_signal(trade.to_dict())

        # Cancel old pending orders (older than 24 hours)
        current_time = df_15m.index[-1]
        for trade in self.pending_trades[:]:
            signal_time = pd.to_datetime(trade.signal_time)
            time_elapsed = (current_time - signal_time).total_seconds() / 3600

            if time_elapsed > 24:  # 24 hours
                self.pending_trades.remove(trade)
                trade.status = 'CANCELLED'
                self.closed_trades.append(trade)

                print(f"\n⚠️  ORDER CANCELLED (timeout)")
                print(f"   Direction: {trade.direction}")
                print(f"   Entry Price: ${trade.entry_price:,.2f}")
                print(f"   Reason: No fill after 24 hours")

                # Update log
                self.save_signal(trade.to_dict())

    def run(self) -> None:
        """
        Main bot loop - continuously monitors Binance for signals
        """
        print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     PAPER TRADING BOT - STARTED                              ║
║                                                                              ║
║  Strategy: Liquidity Reversal (4H sweeps + 15M entries)                     ║
║  Mode: PAPER TRADING (No real trades executed)                              ║
║  All signals logged to JSON                                                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
        """)

        print(f"\n📊 Configuration:")
        print(f"   Symbol: {self.symbol}")
        print(f"   Virtual Balance: ${self.balance:,.2f}")
        print(f"   Risk per Trade: {self.risk_per_trade * 100}%")
        print(f"   Volume Threshold: {self.volume_threshold}x")
        print(f"   Min Stop Loss: {self.min_stop_loss_pct * 100}%")
        print(f"   Max Position Size: {self.max_position_size} BTC")
        print(f"   Check Interval: {self.check_interval}s")
        print(f"\n📁 Signals logged to: {self.signal_log_file}")
        print(f"\n🔄 Starting monitoring loop...")
        print("-" * 80)

        try:
            while True:
                try:
                    # Fetch fresh data
                    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking for signals...")

                    # Get 4H data (500 candles)
                    df_4h = self.data_feed.get_klines('4h', limit=500)

                    if df_4h.empty:
                        print("   ⚠️  Failed to fetch 4H data")
                        time.sleep(self.check_interval)
                        continue

                    # Get 15M data (500 candles)
                    df_15m = self.data_feed.get_klines('15m', limit=500)

                    if df_15m.empty:
                        print("   ⚠️  Failed to fetch 15M data")
                        time.sleep(self.check_interval)
                        continue

                    current_price = self.data_feed.get_latest_price()
                    print(f"   Current Price: ${current_price:,.2f}")
                    print(f"   4H Candles: {len(df_4h)}, Latest: {df_4h.index[-1]}")
                    print(f"   15M Candles: {len(df_15m)}, Latest: {df_15m.index[-1]}")
                    print(f"   Active Sweeps: {len(self.active_sweeps)}")
                    print(f"   Pending Orders: {len(self.pending_trades)}")
                    print(f"   Active Trades: {len(self.active_trades)}")
                    print(f"   Closed Trades: {len(self.closed_trades)}")
                    print(f"   Balance: ${self.balance:,.2f}")

                    # Track existing trades (fills and exits)
                    self.track_trades(df_15m)

                    # Check for sweeps on 4H
                    self.check_4h_for_sweeps(df_4h)

                    # Check for entries on 15M
                    self.check_15m_for_entries(df_4h, df_15m)

                    # Wait before next check
                    time.sleep(self.check_interval)

                except BinanceAPIException as e:
                    print(f"\n⚠️  Binance API Error: {e}")
                    print("   Retrying in 60 seconds...")
                    time.sleep(60)

                except Exception as e:
                    print(f"\n❌ Error: {e}")
                    import traceback
                    traceback.print_exc()
                    time.sleep(self.check_interval)

        except KeyboardInterrupt:
            print("\n\n⚠️  Bot stopped by user")
            self.print_summary()

    def print_summary(self) -> None:
        """Print session summary"""
        print("\n" + "=" * 80)
        print("📊 SESSION SUMMARY")
        print("=" * 80)

        # Trade statistics
        print(f"\n💼 Trade Statistics:")
        print(f"   Total Signals: {len(self.signals_log)}")
        print(f"   Pending Orders: {len(self.pending_trades)}")
        print(f"   Active Trades: {len(self.active_trades)}")
        print(f"   Closed Trades: {len(self.closed_trades)}")

        # Calculate PnL statistics
        if self.closed_trades:
            winning_trades = [t for t in self.closed_trades if t.pnl > 0]
            losing_trades = [t for t in self.closed_trades if t.pnl < 0]
            total_pnl = sum(t.pnl for t in self.closed_trades)

            print(f"\n💰 Performance:")
            print(f"   Initial Balance: ${10000:,.2f}")
            print(f"   Final Balance: ${self.balance:,.2f}")
            print(f"   Total PnL: ${total_pnl:+,.2f}")
            print(f"   Return: {((self.balance - 10000) / 10000 * 100):+.2f}%")

            print(f"\n📈 Win/Loss:")
            print(f"   Winning Trades: {len(winning_trades)}")
            print(f"   Losing Trades: {len(losing_trades)}")
            if len(self.closed_trades) > 0:
                print(f"   Win Rate: {len(winning_trades) / len(self.closed_trades) * 100:.1f}%")

            # Show latest closed trades
            if self.closed_trades:
                print(f"\n📋 Latest Closed Trades:")
                for i, trade in enumerate(self.closed_trades[-5:], 1):
                    pnl_sign = "+" if trade.pnl > 0 else ""
                    print(f"   {i}. {trade.direction} | Entry: ${trade.fill_price:,.2f} | Exit: ${trade.exit_price:,.2f} | PnL: {pnl_sign}${trade.pnl:,.2f} ({trade.exit_reason})")

        print(f"\n📁 Full log: {self.signal_log_file}")
        print("\n" + "=" * 80)


if __name__ == "__main__":
    # Configuration
    bot = PaperTradingBot(
        symbol='BTCUSDT',
        initial_balance=10000,
        risk_per_trade=0.02,  # 2%
        volume_threshold=1.2,  # 1.2x average
        sweep_lookback=20,
        volume_lookback=25,
        min_stop_loss_pct=0.003,  # 0.3%
        max_position_size=10.0,  # 10 BTC max
        check_interval=60  # Check every 60 seconds
    )

    try:
        bot.run()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
