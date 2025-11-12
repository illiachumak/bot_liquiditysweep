"""
SMC Optimized Bot Simulator
Simulates bot behavior with historical data to verify backtest results
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from smartmoneyconcepts import smc
    SMC_AVAILABLE = True
except ImportError:
    print("⚠️  smartmoneyconcepts not available")
    SMC_AVAILABLE = False


class LimitOrder:
    """Limit order"""
    def __init__(self, order_type: str, limit_price: float, sl: float,
                 tp_levels: List[float], tp_sizes: List[float],
                 placed_time: datetime, expiry_hours: int, ob_id: str, level: int):
        self.order_type = order_type
        self.limit_price = limit_price
        self.sl = sl
        self.tp_levels = tp_levels
        self.tp_sizes = tp_sizes
        self.placed_time = placed_time
        self.expiry_time = placed_time + timedelta(hours=expiry_hours)
        self.ob_id = ob_id
        self.level = level
        self.filled = False
        self.filled_time = None
        self.filled_price = None
    
    def check_fill(self, candle: pd.Series) -> bool:
        """Check if limit filled in this candle"""
        high = candle['High']
        low = candle['Low']
        
        if self.order_type == 'LONG':
            if low <= self.limit_price <= high:
                self.filled = True
                self.filled_price = self.limit_price
                return True
        else:
            if low <= self.limit_price <= high:
                self.filled = True
                self.filled_price = self.limit_price
                return True
        return False
    
    def is_expired(self, current_time: datetime) -> bool:
        return current_time >= self.expiry_time


class Position:
    """Active position"""
    def __init__(self, order: LimitOrder, size: float, entry_time: datetime):
        self.type = order.order_type
        self.entry = order.filled_price
        self.size = size
        self.remaining_size = size
        self.sl = order.sl
        self.tp_levels = order.tp_levels
        self.tp_sizes = order.tp_sizes
        self.tp_hit = [False, False, False]
        self.entry_time = entry_time
        self.level = order.level
        self.ob_id = order.ob_id
        
        if self.type == 'LONG':
            self.risk = self.entry - self.sl
        else:
            self.risk = self.sl - self.entry
        
        self.breakeven_moved = False
    
    def check_exit(self, candle: pd.Series, indicators: Dict, current_idx: int) -> List[Dict]:
        """Check for exits"""
        closes = []
        high = candle['High']
        low = candle['Low']
        close = candle['Close']
        
        # 1. Invalidation
        if self._check_invalidation(indicators, current_idx):
            pnl = self._calculate_pnl(self.remaining_size, close)
            closes.append({
                'size': self.remaining_size,
                'exit_price': close,
                'reason': 'INVALIDATION',
                'pnl': pnl
            })
            self.remaining_size = 0
            return closes
        
        # 2. Stop Loss
        if self.type == 'LONG':
            if low <= self.sl:
                pnl = self._calculate_pnl(self.remaining_size, self.sl)
                closes.append({
                    'size': self.remaining_size,
                    'exit_price': self.sl,
                    'reason': 'SL',
                    'pnl': pnl
                })
                self.remaining_size = 0
                return closes
        else:
            if high >= self.sl:
                pnl = self._calculate_pnl(self.remaining_size, self.sl)
                closes.append({
                    'size': self.remaining_size,
                    'exit_price': self.sl,
                    'reason': 'SL',
                    'pnl': pnl
                })
                self.remaining_size = 0
                return closes
        
        # 3. TP Levels
        for i, (tp, size_pct) in enumerate(zip(self.tp_levels, self.tp_sizes)):
            if self.tp_hit[i]:
                continue
            
            tp_hit = False
            if self.type == 'LONG':
                tp_hit = high >= tp
            else:
                tp_hit = low <= tp
            
            if tp_hit:
                close_size = self.size * size_pct
                pnl = self._calculate_pnl(close_size, tp)
                
                closes.append({
                    'size': close_size,
                    'exit_price': tp,
                    'reason': f'TP{i+1}',
                    'pnl': pnl
                })
                
                self.remaining_size -= close_size
                self.tp_hit[i] = True
                
                # Move stops
                if i == 0 and not self.breakeven_moved:
                    self.sl = self.entry
                    self.breakeven_moved = True
                elif i == 1:
                    self.sl = self.tp_levels[0]
        
        return closes
    
    def _check_invalidation(self, indicators: Dict, current_idx: int) -> bool:
        """Check for opposite OB"""
        for i in range(1, min(5, current_idx)):
            idx = current_idx - i
            ob_sig = indicators['ob_signal'][idx]
            
            if pd.isna(ob_sig):
                continue
            
            if self.type == 'LONG' and ob_sig == -1:
                return True
            if self.type == 'SHORT' and ob_sig == 1:
                return True
        return False
    
    def _calculate_pnl(self, size: float, exit_price: float) -> float:
        if self.type == 'LONG':
            return (exit_price - self.entry) * size
        else:
            return (self.entry - exit_price) * size


class SMCOptimizedStrategy:
    """Strategy logic"""
    def __init__(self):
        self.swing_length = 10
        self.ob_lookback = 12
        self.limit_expiry_hours = 12
        self.max_reentry = 3
        self.ob_usage_count = {}
    
    def calculate_indicators(self, df: pd.DataFrame) -> Dict:
        """Calculate SMC indicators"""
        if not SMC_AVAILABLE:
            return {}
        
        ohlc = pd.DataFrame({
            'open': df['Open'].values,
            'high': df['High'].values,
            'low': df['Low'].values,
            'close': df['Close'].values,
            'volume': df['Volume'].values
        })
        
        swings = smc.swing_highs_lows(ohlc, self.swing_length)
        obs = smc.ob(ohlc, swings)
        bos_choch = smc.bos_choch(ohlc, swings)
        
        return {
            'swings': swings,
            'ob_signal': obs['OB'].values,
            'ob_top': obs['Top'].values,
            'ob_bottom': obs['Bottom'].values,
            'bos': bos_choch['BOS'].values,
            'choch': bos_choch['CHOCH'].values,
        }
    
    def check_new_ob(self, df: pd.DataFrame, current_idx: int, indicators: Dict) -> List[LimitOrder]:
        """Check for new OBs"""
        current_time = df.index[current_idx]
        
        ob_signal = indicators['ob_signal']
        ob_top = indicators['ob_top']
        ob_bottom = indicators['ob_bottom']
        
        orders = []
        
        for i in range(2, min(6, current_idx)):
            idx = current_idx - i
            
            if pd.isna(ob_signal[idx]):
                continue
            
            ob_sig = ob_signal[idx]
            ob_t = ob_top[idx]
            ob_b = ob_bottom[idx]
            
            if pd.isna(ob_t) or pd.isna(ob_b):
                continue
            
            ob_id = f"{ob_sig}_{ob_b:.2f}_{ob_t:.2f}"
            
            usage_count = self.ob_usage_count.get(ob_id, 0)
            if usage_count >= self.max_reentry:
                continue
            
            ob_range = ob_t - ob_b
            
            if ob_sig == 1:  # LONG
                limit1 = ob_b + ob_range * 0.25
                limit2 = ob_b + ob_range * 0.50
                limit3 = ob_b + ob_range * 0.75
                
                for level, limit_price in enumerate([limit1, limit2, limit3], 1):
                    sl = ob_b * 0.995
                    risk = limit_price - sl
                    
                    if risk > 0 and risk / limit_price < 0.08:
                        tp1 = limit_price + risk * 1.5
                        tp2 = limit_price + risk * 2.5
                        tp3 = limit_price + risk * 4.0
                        
                        self.ob_usage_count[ob_id] = usage_count + 1
                        
                        orders.append(LimitOrder(
                            order_type='LONG',
                            limit_price=limit_price,
                            sl=sl,
                            tp_levels=[tp1, tp2, tp3],
                            tp_sizes=[0.5, 0.3, 0.2],
                            placed_time=current_time,
                            expiry_hours=self.limit_expiry_hours,
                            ob_id=ob_id,
                            level=level
                        ))
            
            elif ob_sig == -1:  # SHORT
                limit1 = ob_b + ob_range * 0.75
                limit2 = ob_b + ob_range * 0.50
                limit3 = ob_b + ob_range * 0.25
                
                for level, limit_price in enumerate([limit1, limit2, limit3], 1):
                    sl = ob_t * 1.005
                    risk = sl - limit_price
                    
                    if risk > 0 and risk / limit_price < 0.08:
                        tp1 = limit_price - risk * 1.5
                        tp2 = limit_price - risk * 2.5
                        tp3 = limit_price - risk * 4.0
                        
                        if tp1 > 0 and tp2 > 0 and tp3 > 0:
                            self.ob_usage_count[ob_id] = usage_count + 1
                            
                            orders.append(LimitOrder(
                                order_type='SHORT',
                                limit_price=limit_price,
                                sl=sl,
                                tp_levels=[tp1, tp2, tp3],
                                tp_sizes=[0.5, 0.3, 0.2],
                                placed_time=current_time,
                                expiry_hours=self.limit_expiry_hours,
                                ob_id=ob_id,
                                level=level
                            ))
            
            if orders:
                break
        
        return orders


class BotSimulator:
    """Simulator"""
    def __init__(self, initial_capital: float = 10000, risk_per_trade: float = 0.02):
        self.strategy = SMCOptimizedStrategy()
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.risk_per_trade = risk_per_trade
        
        self.pending_orders = []
        self.position = None
        self.completed_trades = []
        
        self.peak_capital = initial_capital
        self.max_dd = 0.0
    
    def calculate_position_size(self, order: LimitOrder) -> float:
        """Calculate size"""
        risk_amount = self.capital * self.risk_per_trade
        risk_per_unit = abs(order.limit_price - order.sl)
        size = risk_amount / risk_per_unit
        return size
    
    def run(self, data: pd.DataFrame, start_date: str = '2024-01-01'):
        """Run simulation"""
        print(f"\n{'='*80}")
        print(f"🎮 SIMULATION: SMC Optimized Bot (15m)")
        print(f"{'='*80}")
        print(f"Period: {start_date} → {data.index[-1].strftime('%Y-%m-%d')}")
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"Risk per Trade: {self.risk_per_trade*100}%")
        print(f"\nCalculating indicators...")
        
        # Filter data
        data = data[data.index >= start_date].copy()
        
        # Calculate indicators
        indicators = self.strategy.calculate_indicators(data)
        if not indicators:
            print("❌ Failed to calculate indicators")
            return
        
        print(f"✅ Ready\n")
        print("Processing candles...")
        
        lookback = 200
        for i in range(lookback, len(data)):
            current_time = data.index[i]
            current_candle = data.iloc[i]
            
            # Check pending orders
            filled_order = None
            expired_orders = []
            
            for order in self.pending_orders:
                if order.check_fill(current_candle):
                    size = self.calculate_position_size(order)
                    self.position = Position(order, size, current_time)
                    filled_order = order
                    break
                elif order.is_expired(current_time):
                    expired_orders.append(order)
            
            # Remove filled and related
            if filled_order:
                self.pending_orders = [o for o in self.pending_orders 
                                     if o.ob_id != filled_order.ob_id]
            
            # Remove expired
            for order in expired_orders:
                if order in self.pending_orders:
                    self.pending_orders.remove(order)
            
            # Check exits
            if self.position:
                closes = self.position.check_exit(current_candle, indicators, i)
                
                for close in closes:
                    self.capital += close['pnl']
                    
                    if self.capital > self.peak_capital:
                        self.peak_capital = self.capital
                    dd = (self.peak_capital - self.capital) / self.peak_capital * 100
                    if dd > self.max_dd:
                        self.max_dd = dd
                    
                    # Track completed trades
                    if close['reason'] in ['SL', 'INVALIDATION'] or close['reason'] == 'TP3':
                        total_pnl = sum(c['pnl'] for c in closes)
                        self.completed_trades.append({
                            'entry_time': self.position.entry_time,
                            'exit_time': current_time,
                            'type': self.position.type,
                            'entry': self.position.entry,
                            'level': self.position.level,
                            'pnl': total_pnl,
                            'reason': close['reason']
                        })
                
                if self.position.remaining_size <= 0.001:
                    self.position = None
            
            # Check for new OBs
            if not self.position and len(self.pending_orders) < 6:
                new_orders = self.strategy.check_new_ob(data, i, indicators)
                self.pending_orders.extend(new_orders)
        
        self._print_results(data)
    
    def _print_results(self, data: pd.DataFrame):
        """Print results"""
        print(f"\n{'='*80}")
        print(f"📊 SIMULATION RESULTS")
        print(f"{'='*80}\n")
        
        if len(self.completed_trades) == 0:
            print("❌ No trades completed")
            return
        
        wins = [t for t in self.completed_trades if t['reason'] in ['TP1', 'TP2', 'TP3']]
        losses = [t for t in self.completed_trades if t['reason'] in ['SL', 'INVALIDATION']]
        
        first = self.completed_trades[0]['entry_time']
        last = self.completed_trades[-1]['exit_time']
        days = (last - first).days
        months = days / 30.44
        
        total_pnl = sum(t['pnl'] for t in self.completed_trades)
        monthly_return = ((self.capital / self.initial_capital) ** (1/months) - 1) * 100 if months > 0 else 0
        
        print(f"Period:           {first.strftime('%Y-%m-%d')} → {last.strftime('%Y-%m-%d')}")
        print(f"Duration:         {days} days ({months:.1f} months)")
        print(f"\nTotal Trades:     {len(self.completed_trades)}")
        print(f"Wins:             {len(wins)}")
        print(f"Losses:           {len(losses)}")
        print(f"Win Rate:         {len(wins)/len(self.completed_trades)*100:.2f}%")
        print(f"\nInitial Capital:  ${self.initial_capital:,.2f}")
        print(f"Final Capital:    ${self.capital:,.2f}")
        print(f"Total PnL:        ${total_pnl:+,.2f}")
        print(f"Total Return:     {(self.capital/self.initial_capital-1)*100:+.2f}%")
        print(f"Monthly Return:   {monthly_return:.2f}%")
        print(f"Trades/Month:     {len(self.completed_trades)/months:.1f}")
        print(f"Max Drawdown:     {self.max_dd:.2f}%")
        
        # Level distribution
        print(f"\n📊 Fill Distribution by Level:")
        for level in [1, 2, 3]:
            count = len([t for t in self.completed_trades if t['level'] == level])
            pct = count / len(self.completed_trades) * 100 if len(self.completed_trades) > 0 else 0
            print(f"   Level {level}: {count} trades ({pct:.1f}%)")
        
        # Comparison with backtest
        print(f"\n{'='*80}")
        print(f"📊 COMPARISON: Simulation vs Backtest")
        print(f"{'='*80}")
        print(f"\n{'Metric':<20} {'Simulation':<15} {'Backtest':<15} {'Diff':<10}")
        print("-" * 60)
        
        backtest_monthly = 6.81
        backtest_wr = 46.34
        backtest_trades = 41
        backtest_dd = 2.00
        
        monthly_diff = (monthly_return / backtest_monthly - 1) * 100
        wr_diff = (len(wins)/len(self.completed_trades)*100 / backtest_wr - 1) * 100
        trades_diff = (len(self.completed_trades) / backtest_trades - 1) * 100
        dd_diff = (self.max_dd / backtest_dd - 1) * 100
        
        print(f"{'Monthly Return':<20} {monthly_return:<15.2f} {backtest_monthly:<15.2f} {monthly_diff:+.1f}%")
        print(f"{'Win Rate':<20} {len(wins)/len(self.completed_trades)*100:<15.2f} {backtest_wr:<15.2f} {wr_diff:+.1f}%")
        print(f"{'Total Trades':<20} {len(self.completed_trades):<15} {backtest_trades:<15} {trades_diff:+.1f}%")
        print(f"{'Max DD':<20} {self.max_dd:<15.2f} {backtest_dd:<15.2f} {dd_diff:+.1f}%")
        
        print(f"\n{'='*80}\n")


def load_historical_data() -> pd.DataFrame:
    """Load historical data"""
    data_path = '../../backtest/data/btc_15m_data_2018_to_2025.csv'
    
    print(f"📊 Loading data from {data_path}...")
    df = pd.read_csv(data_path)
    df['datetime'] = pd.to_datetime(df['Open time'], errors='coerce')
    
    # Remove rows with NaT
    df = df[df['datetime'].notna()]
    
    df.set_index('datetime', inplace=True)
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
    
    for col in df.columns:
        df[col] = df[col].astype(float)
    
    df = df.dropna()
    df = df.sort_index()
    
    print(f"✅ Loaded {len(df)} candles")
    return df


if __name__ == "__main__":
    if not SMC_AVAILABLE:
        print("❌ smartmoneyconcepts library required")
        print("   Install: pip install smartmoneyconcepts")
        exit(1)
    
    # Load data
    data = load_historical_data()
    
    # Run simulation
    simulator = BotSimulator(initial_capital=10000, risk_per_trade=0.02)
    simulator.run(data, start_date='2024-01-01')

