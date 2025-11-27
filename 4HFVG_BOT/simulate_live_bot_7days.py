"""
Live Bot Simulation on Last 7 Days
Uses EXACT same logic as failed_fvg_live_bot.py
Fetches data from REAL Binance (not testnet)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, field
import requests
import time
import json

# ============================================================================
# CONFIGURATION (same as live bot)
# ============================================================================

SYMBOL = 'BTCUSDT'
RISK_PER_TRADE = 0.02
MIN_SL_PCT = 0.3
MIN_RR = 2.0
FIXED_RR = 3.0
LIMIT_EXPIRY_CANDLES = 16  # 4H on 15M
COOLDOWN_CANDLES = 16

MAKER_FEE = 0.00018
TAKER_FEE = 0.00045

# ============================================================================
# DATA CLASSES (exact copy from live bot)
# ============================================================================

@dataclass
class LiveFVG:
    """Fair Value Gap (exact copy from live bot)"""
    id: str
    type: str
    top: float
    bottom: float
    formed_time: datetime
    timeframe: str

    rejected: bool = False
    invalidated: bool = False
    has_filled_trade: bool = False

    rejection_time: Optional[datetime] = None
    rejection_price: Optional[float] = None
    highs_inside: List[float] = field(default_factory=list)
    lows_inside: List[float] = field(default_factory=list)

    pending_setup_id: Optional[str] = None
    pending_expiry_time: Optional[datetime] = None

    def is_inside(self, price: float) -> bool:
        return self.bottom <= price <= self.top

    def is_fully_passed(self, high: float, low: float) -> bool:
        if self.type == 'BULLISH':
            return low < self.bottom
        else:
            return high > self.top

    def check_rejection(self, candle: pd.Series) -> bool:
        """Check if this candle rejects the FVG"""
        high = float(candle['high'])
        low = float(candle['low'])
        close = float(candle['close'])

        # Track highs/lows when price touches the zone
        touched = not (high < self.bottom or low > self.top)
        if touched:
            if high >= self.bottom:
                self.highs_inside.append(high)
            if low <= self.top:
                self.lows_inside.append(low)

        # Check rejection - close outside the zone
        if self.type == 'BULLISH':
            if close < self.bottom and not self.rejected:
                self.rejected = True
                self.rejection_time = candle.name
                self.rejection_price = close
                return True
        else:  # BEARISH
            if close > self.top and not self.rejected:
                self.rejected = True
                self.rejection_time = candle.name
                self.rejection_price = close
                return True

        return False

    def get_stop_loss(self) -> Optional[float]:
        """Get SL based on highs/lows inside zone"""
        if self.type == 'BULLISH':
            if self.highs_inside:
                return max(self.highs_inside) * 1.002
        else:
            if self.lows_inside:
                return min(self.lows_inside) * 0.998
        return None


@dataclass
class SimulatedTrade:
    """Simulated trade"""
    trade_id: int
    setup_id: str
    parent_4h_fvg_id: str

    direction: str
    entry_price: float
    entry_time: datetime
    sl: float
    tp: float
    size: float

    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    exit_reason: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            'trade_id': self.trade_id,
            'direction': self.direction,
            'entry_time': str(self.entry_time),
            'entry_price': self.entry_price,
            'exit_time': str(self.exit_time) if self.exit_time else None,
            'exit_price': self.exit_price,
            'sl': self.sl,
            'tp': self.tp,
            'size': self.size,
            'pnl': round(self.pnl, 2) if self.pnl else None,
            'pnl_pct': round(self.pnl_pct, 2) if self.pnl_pct else None,
            'exit_reason': self.exit_reason
        }


# ============================================================================
# FVG DETECTOR (exact copy from live bot)
# ============================================================================

class FVGDetector:
    """Detect FVGs from candle data"""

    @staticmethod
    def detect_fvgs(df: pd.DataFrame, timeframe: str) -> List[LiveFVG]:
        """Detect all FVGs in dataframe"""
        fvgs = []

        for i in range(2, len(df)):
            row = df.iloc[i]
            row_i2 = df.iloc[i-2]

            # Bullish FVG
            if row['low'] > row_i2['high']:
                fvg = LiveFVG(
                    id=f"{timeframe}_BULLISH_{row['low']:.2f}_{row_i2['high']:.2f}_{int(row.name.timestamp())}",
                    type='BULLISH',
                    top=row['low'],
                    bottom=row_i2['high'],
                    formed_time=row.name,
                    timeframe=timeframe
                )
                fvgs.append(fvg)

            # Bearish FVG
            elif row['high'] < row_i2['low']:
                fvg = LiveFVG(
                    id=f"{timeframe}_BEARISH_{row_i2['low']:.2f}_{row['high']:.2f}_{int(row.name.timestamp())}",
                    type='BEARISH',
                    top=row_i2['low'],
                    bottom=row['high'],
                    formed_time=row.name,
                    timeframe=timeframe
                )
                fvgs.append(fvg)

        return fvgs


# ============================================================================
# LIVE BOT SIMULATOR
# ============================================================================

class LiveBotSimulator:
    """Simulates live bot logic on historical data"""

    def __init__(self, initial_balance: float = 300.0):
        self.initial_balance = initial_balance
        self.balance = initial_balance

        self.detector = FVGDetector()

        self.active_4h_fvgs: List[LiveFVG] = []
        self.rejected_4h_fvgs: List[LiveFVG] = []

        self.trades: List[SimulatedTrade] = []
        self.trade_counter = 0

    def validate_setup(self, entry: float, sl: float, tp: float) -> bool:
        """Validate setup (same as live bot)"""
        sl_distance_pct = abs(entry - sl) / entry * 100
        if sl_distance_pct < MIN_SL_PCT:
            return False

        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr = reward / risk
        if rr < MIN_RR:
            return False

        return True

    def calculate_position_size(self, entry: float, sl: float) -> float:
        """Calculate position size (same as live bot)"""
        risk_amount = self.balance * RISK_PER_TRADE
        risk_per_unit = abs(entry - sl)
        size = risk_amount / risk_per_unit

        # Round to 3 decimals
        size = round(size, 3)

        # Check minimum notional
        notional = size * entry
        min_notional = 10.0
        if notional < min_notional:
            size = min_notional / entry
            size = round(size, 3)

        return size

    def create_setup_from_rejection(self, rejected_fvg: LiveFVG, fvg_15m: LiveFVG,
                                   current_time: datetime) -> Optional[Dict]:
        """Create setup (same as live bot)"""

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

        # Calculate expiry time
        expiry_time = current_time + timedelta(minutes=15 * LIMIT_EXPIRY_CANDLES)

        setup = {
            'setup_id': f"setup_{int(current_time.timestamp())}",
            'parent_4h_fvg_id': rejected_fvg.id,
            'fvg_15m_id': fvg_15m.id,
            'direction': direction,
            'entry_price': entry_price,
            'sl': sl,
            'tp': tp,
            'size': size,
            'created_time': current_time,
            'expiry_time': expiry_time
        }

        return setup

    def check_limit_fill(self, setup: Dict, df_15m: pd.DataFrame,
                        start_idx: int, end_idx: int) -> tuple:
        """Check if limit order gets filled"""
        entry_price = setup['entry_price']
        direction = setup['direction']

        for i in range(start_idx, min(end_idx, len(df_15m))):
            candle = df_15m.iloc[i]

            if direction == 'LONG':
                if candle['low'] <= entry_price:
                    return True, i
            else:  # SHORT
                if candle['high'] >= entry_price:
                    return True, i

        return False, None

    def simulate_trade(self, setup: Dict, df_15m: pd.DataFrame, entry_idx: int) -> SimulatedTrade:
        """Simulate trade execution"""

        self.trade_counter += 1

        trade = SimulatedTrade(
            trade_id=self.trade_counter,
            setup_id=setup['setup_id'],
            parent_4h_fvg_id=setup['parent_4h_fvg_id'],
            direction=setup['direction'],
            entry_price=setup['entry_price'],
            entry_time=df_15m.index[entry_idx],
            sl=setup['sl'],
            tp=setup['tp'],
            size=setup['size']
        )

        # Simulate execution
        max_candles = 200
        for i in range(entry_idx, min(entry_idx + max_candles, len(df_15m))):
            candle = df_15m.iloc[i]

            if trade.direction == 'LONG':
                # Check SL
                if candle['low'] <= trade.sl:
                    trade.exit_price = trade.sl
                    trade.exit_time = candle.name
                    trade.exit_reason = 'SL'
                    break

                # Check TP
                if candle['high'] >= trade.tp:
                    trade.exit_price = trade.tp
                    trade.exit_time = candle.name
                    trade.exit_reason = 'TP'
                    break

            else:  # SHORT
                # Check SL
                if candle['high'] >= trade.sl:
                    trade.exit_price = trade.sl
                    trade.exit_time = candle.name
                    trade.exit_reason = 'SL'
                    break

                # Check TP
                if candle['low'] <= trade.tp:
                    trade.exit_price = trade.tp
                    trade.exit_time = candle.name
                    trade.exit_reason = 'TP'
                    break

        # If still no exit, close at timeout
        if trade.exit_price is None:
            last_candle = df_15m.iloc[min(entry_idx + max_candles - 1, len(df_15m) - 1)]
            trade.exit_price = last_candle['close']
            trade.exit_time = last_candle.name
            trade.exit_reason = 'TIMEOUT'

        # Calculate PnL
        if trade.direction == 'LONG':
            pnl = (trade.exit_price - trade.entry_price) * trade.size
        else:
            pnl = (trade.entry_price - trade.exit_price) * trade.size

        # Apply fees
        entry_fee = trade.entry_price * trade.size * MAKER_FEE
        if trade.exit_reason == 'SL':
            exit_fee = trade.exit_price * trade.size * TAKER_FEE
        else:
            exit_fee = trade.exit_price * trade.size * MAKER_FEE

        pnl -= (entry_fee + exit_fee)

        trade.pnl = pnl
        trade.pnl_pct = (pnl / (trade.entry_price * trade.size)) * 100

        # Update balance
        self.balance += pnl

        return trade

    def run_simulation(self, df_4h: pd.DataFrame, df_15m: pd.DataFrame):
        """Run simulation using live bot logic"""

        print(f"\n{'='*80}")
        print(f"LIVE BOT SIMULATION - Last 7 Days")
        print(f"{'='*80}")
        print(f"Period: {df_4h.index[0]} to {df_4h.index[-1]}")
        print(f"Initial Balance: ${self.initial_balance:.2f}")
        print(f"{'='*80}\n")

        # Iterate through 4H candles (excluding last open candle)
        for i in range(len(df_4h) - 1):  # Exclude last open candle
            current_4h_candle = df_4h.iloc[i]
            current_4h_time = df_4h.index[i]

            # Detect FVGs from closed candles only
            if i >= 2:
                row = df_4h.iloc[i]
                row_i2 = df_4h.iloc[i-2]

                # Bullish FVG
                if row['low'] > row_i2['high']:
                    fvg = LiveFVG(
                        id=f"4h_BULLISH_{row['low']:.2f}_{row_i2['high']:.2f}_{int(row.name.timestamp())}",
                        type='BULLISH',
                        top=row['low'],
                        bottom=row_i2['high'],
                        formed_time=row.name,
                        timeframe='4h'
                    )
                    if not any(f.id == fvg.id for f in self.active_4h_fvgs):
                        self.active_4h_fvgs.append(fvg)

                # Bearish FVG
                elif row['high'] < row_i2['low']:
                    fvg = LiveFVG(
                        id=f"4h_BEARISH_{row_i2['low']:.2f}_{row['high']:.2f}_{int(row.name.timestamp())}",
                        type='BEARISH',
                        top=row_i2['low'],
                        bottom=row['high'],
                        formed_time=row.name,
                        timeframe='4h'
                    )
                    if not any(f.id == fvg.id for f in self.active_4h_fvgs):
                        self.active_4h_fvgs.append(fvg)

            # Check rejections
            for fvg in self.active_4h_fvgs[:]:
                if not fvg.rejected:
                    if fvg.check_rejection(current_4h_candle):
                        if fvg not in self.rejected_4h_fvgs:
                            self.rejected_4h_fvgs.append(fvg)
                            print(f"🚫 REJECTION: {fvg.type} FVG @ {current_4h_time}")

                # Check invalidation
                if fvg.is_fully_passed(current_4h_candle['high'], current_4h_candle['low']):
                    fvg.invalidated = True
                    self.active_4h_fvgs.remove(fvg)

            # Find corresponding 15M candles for this 4H period
            next_4h_time = df_4h.index[i+1] if i+1 < len(df_4h) else df_15m.index[-1]
            df_15m_period = df_15m[(df_15m.index >= current_4h_time) & (df_15m.index < next_4h_time)]

            # Process 15M candles
            for j in range(len(df_15m_period)):
                current_15m_time = df_15m_period.index[j]
                current_15m_idx = df_15m.index.get_loc(current_15m_time)

                # Check for setups from rejected FVGs
                for rejected_fvg in self.rejected_4h_fvgs[:]:
                    # Skip if already has filled trade
                    if rejected_fvg.has_filled_trade:
                        continue

                    # Skip if pending setup not expired
                    if rejected_fvg.pending_expiry_time:
                        if current_15m_time < rejected_fvg.pending_expiry_time:
                            continue

                    # Check if invalidated on 15M
                    current_15m_candle = df_15m_period.iloc[j]
                    if rejected_fvg.is_fully_passed(current_15m_candle['high'], current_15m_candle['low']):
                        rejected_fvg.invalidated = True
                        self.rejected_4h_fvgs.remove(rejected_fvg)
                        continue

                    # Look for 15M FVG (only use closed candles)
                    lookback_start = max(0, current_15m_idx - 10)
                    df_15m_lookback = df_15m.iloc[lookback_start:current_15m_idx]
                    fvgs_15m = self.detector.detect_fvgs(df_15m_lookback, '15m')

                    if fvgs_15m:
                        fvg_15m = fvgs_15m[-1]

                        # Create setup
                        setup = self.create_setup_from_rejection(rejected_fvg, fvg_15m, current_15m_time)

                        if setup:
                            print(f"📋 Setup created: {setup['direction']} @ ${setup['entry_price']:.2f}")

                            # Set expiry
                            rejected_fvg.pending_expiry_time = setup['expiry_time']

                            # Check if limit gets filled
                            expiry_idx = current_15m_idx + LIMIT_EXPIRY_CANDLES
                            filled, fill_idx = self.check_limit_fill(
                                setup, df_15m, current_15m_idx + 1, expiry_idx
                            )

                            if filled:
                                print(f"✅ Limit filled at {df_15m.index[fill_idx]}")

                                # Simulate trade
                                trade = self.simulate_trade(setup, df_15m, fill_idx)
                                self.trades.append(trade)

                                # Mark rejection as having filled trade
                                rejected_fvg.has_filled_trade = True
                                self.rejected_4h_fvgs.remove(rejected_fvg)

                                result_emoji = "✅" if trade.pnl > 0 else "❌"
                                print(f"{result_emoji} Trade #{trade.trade_id} | {trade.direction} | "
                                      f"Entry: ${trade.entry_price:.2f} | Exit: ${trade.exit_price:.2f} | "
                                      f"PnL: ${trade.pnl:+.2f} ({trade.pnl_pct:+.2f}%) | {trade.exit_reason}\n")

                                # Only one trade at a time
                                break
                            else:
                                print(f"⏰ Limit NOT filled, expired")
                                # Set cooldown
                                rejected_fvg.pending_expiry_time = current_15m_time + timedelta(minutes=15 * COOLDOWN_CANDLES)

        # Calculate metrics
        self.print_results()

    def print_results(self):
        """Print simulation results"""

        print(f"\n{'='*80}")
        print("SIMULATION RESULTS")
        print(f"{'='*80}")

        if not self.trades:
            print("\n⚠️  No trades executed")
            return

        wins = [t for t in self.trades if t.pnl > 0]
        losses = [t for t in self.trades if t.pnl <= 0]

        total_pnl = sum(t.pnl for t in self.trades)
        win_rate = len(wins) / len(self.trades) * 100

        avg_win = np.mean([t.pnl for t in wins]) if wins else 0
        avg_loss = np.mean([t.pnl for t in losses]) if losses else 0

        print(f"\n📊 TRADE STATISTICS")
        print(f"   Total Trades:      {len(self.trades)}")
        print(f"   Wins:              {len(wins)}")
        print(f"   Losses:            {len(losses)}")
        print(f"   Win Rate:          {win_rate:.2f}%")

        print(f"\n💰 PROFIT & LOSS")
        print(f"   Total PnL:         ${total_pnl:+.2f}")
        print(f"   Final Balance:     ${self.balance:.2f}")
        print(f"   Return:            {(total_pnl/self.initial_balance)*100:+.2f}%")
        print(f"   Avg Win:           ${avg_win:.2f}")
        print(f"   Avg Loss:          ${avg_loss:.2f}")
        if losses and sum(t.pnl for t in losses) != 0:
            profit_factor = sum(t.pnl for t in wins) / abs(sum(t.pnl for t in losses))
            print(f"   Profit Factor:     {profit_factor:.2f}")

        print(f"\n{'='*80}\n")


# ============================================================================
# DATA FETCHING
# ============================================================================

def fetch_binance_klines(symbol: str, interval: str, start_time: int, end_time: int) -> List[List]:
    """Fetch klines from Binance API"""

    base_url = "https://api.binance.com"
    endpoint = "/api/v3/klines"

    all_klines = []
    current_start = start_time

    while current_start < end_time:
        params = {
            'symbol': symbol,
            'interval': interval,
            'startTime': current_start,
            'endTime': end_time,
            'limit': 1000
        }

        try:
            response = requests.get(base_url + endpoint, params=params)
            response.raise_for_status()
            klines = response.json()

            if not klines:
                break

            all_klines.extend(klines)
            current_start = klines[-1][6] + 1

            time.sleep(0.1)
            print(f"  Fetched {len(klines)} candles (Total: {len(all_klines)})")

        except Exception as e:
            print(f"❌ Error fetching data: {e}")
            break

    return all_klines


def load_data_from_binance(days: int = 7):
    """Load data from Binance for last N days"""

    print(f"\n📊 Loading data from Binance for last {days} days...")

    end_time = int(datetime.utcnow().timestamp() * 1000)
    start_time = int((datetime.utcnow() - timedelta(days=days)).timestamp() * 1000)

    print(f"Start: {datetime.fromtimestamp(start_time/1000)}")
    print(f"End: {datetime.fromtimestamp(end_time/1000)}\n")

    # Fetch 4H
    print("Fetching 4H data...")
    klines_4h = fetch_binance_klines('BTCUSDT', '4h', start_time, end_time)

    # Fetch 15M
    print("\nFetching 15M data...")
    klines_15m = fetch_binance_klines('BTCUSDT', '15m', start_time, end_time)

    # Convert to DataFrame
    columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume',
               'close_time', 'quote_volume', 'trades', 'taker_buy_base',
               'taker_buy_quote', 'ignore']

    df_4h = pd.DataFrame(klines_4h, columns=columns)
    df_4h['timestamp'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
    df_4h.set_index('timestamp', inplace=True)
    df_4h = df_4h[['open', 'high', 'low', 'close', 'volume']].astype(float)

    df_15m = pd.DataFrame(klines_15m, columns=columns)
    df_15m['timestamp'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
    df_15m.set_index('timestamp', inplace=True)
    df_15m = df_15m[['open', 'high', 'low', 'close', 'volume']].astype(float)

    print(f"\n✅ Loaded {len(df_4h)} 4H candles")
    print(f"✅ Loaded {len(df_15m)} 15M candles")

    return df_4h, df_15m


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":

    # Load data from Binance
    df_4h, df_15m = load_data_from_binance(days=7)

    # Run simulation
    simulator = LiveBotSimulator(initial_balance=300.0)
    simulator.run_simulation(df_4h, df_15m)

    # Save results
    if simulator.trades:
        results = {
            'period': f"{df_4h.index[0]} to {df_4h.index[-1]}",
            'trades': [t.to_dict() for t in simulator.trades],
            'summary': {
                'total_trades': len(simulator.trades),
                'wins': len([t for t in simulator.trades if t.pnl > 0]),
                'losses': len([t for t in simulator.trades if t.pnl <= 0]),
                'total_pnl': round(sum(t.pnl for t in simulator.trades), 2),
                'final_balance': round(simulator.balance, 2)
            }
        }

        filename = f"live_bot_simulation_7days_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"💾 Results saved to {filename}")
