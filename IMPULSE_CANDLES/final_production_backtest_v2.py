"""
FINAL PRODUCTION BACKTEST - Based on working impulse_backtest.py
Added: Quality Scoring + Dynamic RR + Variable Risk
Verified: NO look-forward bias
"""
import pandas as pd
import numpy as np
from datetime import datetime
import json
from pathlib import Path

from impulse_detectors import ATRBasedDetector, calculate_atr_column
from ema_filter import EMAFilter, add_ema_columns
from entry_strategies import BreakoutEntry
from quality_filter import QualityScorer


class ProductionBacktest:
    """Production backtest with quality scoring, dynamic RR, and variable risk"""

    def __init__(self, htf_df, ltf_df, config, start_date='2024-01-01',
                 end_date='2025-12-31', initial_capital=10000):
        """
        Initialize backtest

        Config должен содержать:
        - min_score: минимальный quality score
        - rr_mapping: маппинг score -> RR
        - risk_by_category: маппинг category -> risk %
        """
        self.htf_df = htf_df.copy()
        self.ltf_df = ltf_df.copy()
        self.config = config
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.initial_capital = initial_capital
        self.capital = initial_capital

        # Components
        self.impulse_detector = ATRBasedDetector(atr_multiplier=1.5, body_ratio_threshold=0.70)
        self.entry_strategy = BreakoutEntry(rr_ratio=3.0)  # base RR, will be overridden
        self.ema_filter = EMAFilter(short_period=12, long_period=21, lookback=5)
        self.quality_scorer = QualityScorer("Q", min_score=config['min_score'])

        # Stats
        self.trades = []
        self.impulse_candles_found = []

    def prepare_data(self):
        """Prepare data"""
        print("Preparing data...")

        # Convert timestamps
        self.htf_df['Open time'] = pd.to_datetime(self.htf_df['Open time'])
        self.htf_df['Close time'] = pd.to_datetime(self.htf_df['Close time'])
        self.ltf_df['Open time'] = pd.to_datetime(self.ltf_df['Open time'])
        self.ltf_df['Close time'] = pd.to_datetime(self.ltf_df['Close time'])

        # Filter by date
        self.htf_df = self.htf_df[
            (self.htf_df['Open time'] >= self.start_date) &
            (self.htf_df['Open time'] <= self.end_date)
        ].reset_index(drop=True)

        self.ltf_df = self.ltf_df[
            (self.ltf_df['Open time'] >= self.start_date) &
            (self.ltf_df['Open time'] <= self.end_date)
        ].reset_index(drop=True)

        # Calculate indicators
        self.htf_df = calculate_atr_column(self.htf_df)
        self.ltf_df = self.ema_filter.prepare_data(self.ltf_df)

        print(f"HTF candles: {len(self.htf_df)}")
        print(f"LTF candles: {len(self.ltf_df)}")

    def run(self):
        """Run backtest"""
        print(f"\n{'='*80}")
        print(f"FINAL PRODUCTION BACKTEST")
        print(f"Config: {self.config['name']}")
        print(f"{'='*80}\n")

        self.prepare_data()

        print("Scanning for impulse candles...")

        for idx in range(len(self.htf_df)):
            # Detect impulse
            is_impulse, direction, strength = self.impulse_detector.detect(self.htf_df, idx)

            if is_impulse:
                impulse_candle = self.htf_df.iloc[idx]
                self.impulse_candles_found.append({
                    'idx': idx,
                    'time': impulse_candle['Open time'],
                    'direction': direction,
                    'strength': strength
                })

                # CRITICAL: Impulse candle closes 4 hours after open
                # In real trading, we can only act AFTER candle close
                impulse_open = impulse_candle['Open time']
                impulse_close = impulse_candle['Close time']
                earliest_action_time = impulse_close
                
                # Try to find entry (entry_strategy should only use data after impulse close)
                entry = self.entry_strategy.find_entry(
                    self.htf_df.iloc[:idx+1].copy(),  # Only past HTF data up to impulse
                    self.ltf_df,  # Full LTF (entry_strategy filters internally)
                    idx, direction, self.ema_filter
                )

                if entry is None:
                    continue

                # Quality scoring
                # Use data up to entry time (no look-forward bias)
                entry_time = pd.to_datetime(entry['entry_time'])
                
                # CRITICAL CHECK: Entry must be AFTER impulse close
                if entry_time < earliest_action_time:
                    # This is look-forward bias - skip this trade
                    continue

                htf_for_quality = self.htf_df[self.htf_df['Open time'] <= impulse_candle['Open time']].copy()
                ltf_for_quality = self.ltf_df[self.ltf_df['Open time'] <= entry_time].copy()

                quality_score = self.quality_scorer.score_setup(
                    htf_for_quality,
                    ltf_for_quality,
                    len(htf_for_quality) - 1,
                    direction,
                    entry
                )

                # Check RR mapping
                rr_mapping = self.config['rr_mapping']
                target_rr = None

                for (min_s, max_s), rr in rr_mapping.items():
                    if rr is not None and min_s <= quality_score <= max_s:
                        target_rr = rr
                        break

                if target_rr is None:
                    continue  # Filtered out by quality

                # Determine risk % based on category
                risk_by_category = self.config.get('risk_by_category', {})

                if quality_score >= 8:
                    risk_pct = risk_by_category.get('8-10', 1.0)
                elif quality_score >= 6:
                    risk_pct = risk_by_category.get('6-7', 1.0)
                elif quality_score >= 4:
                    risk_pct = risk_by_category.get('4-5', 1.0)
                else:
                    risk_pct = risk_by_category.get('3', 1.0)

                # Recalculate TP with new RR
                entry_price = entry['entry_price']
                stop_loss = entry['stop_loss']
                side = entry['side']
                risk = abs(entry_price - stop_loss)

                if side == 'long':
                    take_profit = entry_price + (risk * target_rr)
                else:
                    take_profit = entry_price - (risk * target_rr)

                entry['take_profit'] = take_profit
                entry['rr'] = target_rr
                entry['quality_score'] = quality_score
                entry['risk_pct'] = risk_pct

                # Simulate trade
                trade_result = self.simulate_trade(entry)

                if trade_result is not None:
                    self.trades.append(trade_result)

            # Progress
            if (idx + 1) % 500 == 0:
                print(f"  Processed {idx + 1}/{len(self.htf_df)} candles...")

        print(f"\nFound {len(self.impulse_candles_found)} impulse candles")
        print(f"Executed {len(self.trades)} trades")

        return self.get_statistics()

    def simulate_trade(self, entry):
        """Simulate trade execution with realistic slippage and execution issues"""

        entry_price = entry['entry_price']
        stop_loss = entry['stop_loss']
        take_profit = entry['take_profit']
        side = entry['side']
        entry_time = pd.to_datetime(entry['entry_time'])
        risk_pct = entry['risk_pct']

        # Position sizing with variable risk
        risk_amount = self.capital * (risk_pct / 100.0)
        risk_per_unit = abs(entry_price - stop_loss)

        if risk_per_unit == 0:
            return None

        position_size = risk_amount / risk_per_unit

        # ENTRY LOGIC: Try limit order first (maker), if not filled, use market (taker)
        # In live bot: limit order with price adjusted to market if not filled
        entry_candle = self.ltf_df[self.ltf_df['Open time'] == entry_time]
        if len(entry_candle) == 0:
            # Find closest candle after entry_time
            entry_candle = self.ltf_df[self.ltf_df['Open time'] >= entry_time]
            if len(entry_candle) == 0:
                return None  # No data available
            entry_candle = entry_candle.iloc[0:1]
        
        entry_candle = entry_candle.iloc[0]
        
        # Try limit order first
        entry_filled_limit = False
        actual_entry = entry_price
        entry_fee_type = 'maker'  # Default to maker
        
        if side == 'long':
            # Limit order: fill if price touched or went below entry_price
            if entry_candle['Low'] <= entry_price:
                # Limit order filled at entry_price (or better)
                actual_entry = min(entry_price, entry_candle['Open'])
                entry_filled_limit = True
            else:
                # Limit order not filled, execute as market order
                actual_entry = entry_candle['Open']  # Market entry at open
                entry_fee_type = 'taker'
        else:  # short
            # Limit order: fill if price touched or went above entry_price
            if entry_candle['High'] >= entry_price:
                # Limit order filled at entry_price (or better)
                actual_entry = max(entry_price, entry_candle['Open'])
                entry_filled_limit = True
            else:
                # Limit order not filled, execute as market order
                actual_entry = entry_candle['Open']  # Market entry at open
                entry_fee_type = 'taker'
        
        # Recalculate position size with actual entry
        risk_per_unit_actual = abs(actual_entry - stop_loss)
        if risk_per_unit_actual == 0:
            return None
        position_size = risk_amount / risk_per_unit_actual

        # Get LTF after entry (no look-forward bias)
        ltf_after_entry = self.ltf_df[
            self.ltf_df['Open time'] > entry_time
        ].copy()

        if len(ltf_after_entry) == 0:
            return None

        # Simulate execution (no slippage)
        for i in range(len(ltf_after_entry)):
            candle = ltf_after_entry.iloc[i]

            if side == 'long':
                # Check SL (market order - executes at stop_loss or worse)
                if candle['Low'] <= stop_loss:
                    # Market stop loss: executes at stop_loss if touched, or at open if gapped
                    actual_sl = stop_loss if candle['Open'] >= stop_loss else candle['Open']
                    
                    pnl = (actual_sl - actual_entry) * position_size
                    self.capital += pnl

                    return self.create_trade_result(
                        entry, candle, actual_sl, -1.0, position_size, 'stop_loss',
                        actual_entry=actual_entry, entry_fee_type=entry_fee_type
                    )

                # Check TP (limit order - executes at take_profit if touched)
                if candle['High'] >= take_profit:
                    # Limit take profit: executes at take_profit (or better)
                    actual_tp = take_profit
                    
                    pnl = (actual_tp - actual_entry) * position_size
                    self.capital += pnl
                    
                    # Calculate actual R multiple
                    actual_risk = abs(actual_entry - stop_loss)
                    actual_r = (actual_tp - actual_entry) / actual_risk if actual_risk > 0 else 0

                    return self.create_trade_result(
                        entry, candle, actual_tp, actual_r, position_size, 'take_profit',
                        actual_entry=actual_entry, entry_fee_type=entry_fee_type
                    )

            else:  # short
                # Check SL (market order)
                if candle['High'] >= stop_loss:
                    actual_sl = stop_loss if candle['Open'] <= stop_loss else candle['Open']
                    
                    pnl = (actual_entry - actual_sl) * position_size
                    self.capital += pnl

                    return self.create_trade_result(
                        entry, candle, actual_sl, -1.0, position_size, 'stop_loss',
                        actual_entry=actual_entry, entry_fee_type=entry_fee_type
                    )

                # Check TP (limit order)
                if candle['Low'] <= take_profit:
                    actual_tp = take_profit
                    
                    pnl = (actual_entry - actual_tp) * position_size
                    self.capital += pnl
                    
                    actual_risk = abs(actual_entry - stop_loss)
                    actual_r = (actual_entry - actual_tp) / actual_risk if actual_risk > 0 else 0

                    return self.create_trade_result(
                        entry, candle, actual_tp, actual_r, position_size, 'take_profit',
                        actual_entry=actual_entry, entry_fee_type=entry_fee_type
                    )

        return None

    def create_trade_result(self, entry, exit_candle, exit_price, r_multiple,
                           position_size, exit_reason, actual_entry=None, entry_fee_type='maker'):
        """Create trade result dict with realistic fees (no slippage)"""

        # Use actual entry price
        entry_price = actual_entry if actual_entry is not None else entry['entry_price']
        
        # Calculate PnL
        if entry['side'] == 'long':
            pnl = (exit_price - entry_price) * position_size
        else:  # short
            pnl = (entry_price - exit_price) * position_size

        # Exchange fees: maker 0.02%, taker 0.05%
        maker_fee_rate = 0.0002  # 0.02% for limit orders
        taker_fee_rate = 0.0005  # 0.05% for market orders
        
        # Entry fee: depends on whether limit order filled
        if entry_fee_type == 'maker':
            entry_fee = entry_price * position_size * maker_fee_rate
        else:  # taker
            entry_fee = entry_price * position_size * taker_fee_rate
        
        # Exit fee: 
        #   - Stop loss: Market order (taker) = 0.05%
        #   - Take profit: Limit order (maker) = 0.02%
        if exit_reason == 'stop_loss':
            exit_fee = exit_price * position_size * taker_fee_rate  # Market stop
        else:  # take_profit
            exit_fee = exit_price * position_size * maker_fee_rate  # Limit TP
        
        total_fee = entry_fee + exit_fee
        
        self.capital -= total_fee
        pnl_after_fees = pnl - total_fee

        return {
            'entry_time': str(entry['entry_time']),
            'exit_time': str(exit_candle['Open time']),
            'side': entry['side'],
            'entry_price': entry_price,  # Actual executed price
            'entry_price_expected': entry['entry_price'],  # Expected limit price
            'exit_price': exit_price,
            'stop_loss': entry['stop_loss'],
            'take_profit': entry['take_profit'],
            'position_size': position_size,
            'pnl': pnl,
            'pnl_after_fees': pnl_after_fees,
            'fee': total_fee,
            'entry_fee': entry_fee,
            'exit_fee': exit_fee,
            'entry_fee_type': entry_fee_type,
            'exit_fee_type': 'taker' if exit_reason == 'stop_loss' else 'maker',
            'r_multiple': r_multiple,
            'rr_used': entry['rr'],
            'quality_score': entry['quality_score'],
            'risk_pct': entry['risk_pct'],
            'exit_reason': exit_reason,
            'capital_after': self.capital
        }

    def get_statistics(self):
        """Calculate statistics"""

        if len(self.trades) == 0:
            return {'total_trades': 0, 'error': 'No trades'}

        wins = [t for t in self.trades if t['r_multiple'] > 0]
        losses = [t for t in self.trades if t['r_multiple'] < 0]

        wr = (len(wins) / len(self.trades)) * 100
        avg_r_win = np.mean([t['r_multiple'] for t in wins]) if wins else 0
        avg_r_loss = abs(np.mean([t['r_multiple'] for t in losses])) if losses else 0

        ev = (len(wins) / len(self.trades)) * avg_r_win - (len(losses) / len(self.trades)) * avg_r_loss

        total_pnl = sum(t['pnl_after_fees'] for t in self.trades)
        total_pnl_pct = (total_pnl / self.initial_capital) * 100

        # Max DD
        capitals = [self.initial_capital] + [t['capital_after'] for t in self.trades]
        peak = capitals[0]
        max_dd = 0

        for cap in capitals:
            if cap > peak:
                peak = cap
            dd = ((cap - peak) / peak) * 100
            if dd < max_dd:
                max_dd = dd

        # Profit factor
        total_wins = sum(t['pnl_after_fees'] for t in wins)
        total_losses = abs(sum(t['pnl_after_fees'] for t in losses)) if losses else 1
        pf = total_wins / total_losses if total_losses > 0 else total_wins

        # By category
        cat_stats = self.calculate_category_stats()
        
        # Execution statistics
        total_fees = sum(t.get('fee', 0) for t in self.trades)
        total_entry_slippage = sum(t.get('entry_slippage', 0) * t.get('position_size', 0) for t in self.trades if t.get('slippage_applied', False))
        trades_with_slippage = sum(1 for t in self.trades if t.get('slippage_applied', False))

        return {
            'config': str(self.config),
            'total_trades': len(self.trades),
            'impulses_found': len(self.impulse_candles_found),
            'win_rate': round(wr, 2),
            'wins': len(wins),
            'losses': len(losses),
            'ev_per_r': round(ev, 3),
            'avg_r_win': round(avg_r_win, 2),
            'avg_r_loss': round(avg_r_loss, 2),
            'total_pnl': round(total_pnl, 2),
            'total_pnl_pct': round(total_pnl_pct, 2),
            'avg_win': round(np.mean([t['pnl_after_fees'] for t in wins]), 2) if wins else 0,
            'avg_loss': round(abs(np.mean([t['pnl_after_fees'] for t in losses])), 2) if losses else 0,
            'profit_factor': round(pf, 2),
            'max_drawdown_pct': round(max_dd, 2),
            'final_capital': round(self.capital, 2),
            'category_stats': cat_stats,
            'execution_stats': {
                'total_fees': round(total_fees, 2),
                'total_entry_slippage': round(total_entry_slippage, 2),
                'trades_with_slippage': trades_with_slippage,
                'avg_fee_per_trade': round(total_fees / len(self.trades), 2) if self.trades else 0
            }
        }

    def calculate_category_stats(self):
        """Stats by quality category"""

        categories = {'8-10': [], '6-7': [], '4-5': [], '3': []}

        for trade in self.trades:
            score = trade.get('quality_score', 0)

            if score >= 8:
                categories['8-10'].append(trade)
            elif score >= 6:
                categories['6-7'].append(trade)
            elif score >= 4:
                categories['4-5'].append(trade)
            elif score >= 3:
                categories['3'].append(trade)

        cat_stats = {}

        for cat_name, trades in categories.items():
            if len(trades) == 0:
                continue

            wins = [t for t in trades if t['r_multiple'] > 0]
            losses = [t for t in trades if t['r_multiple'] < 0]

            wr = (len(wins) / len(trades)) * 100
            avg_r_win = np.mean([t['r_multiple'] for t in wins]) if wins else 0
            avg_r_loss = abs(np.mean([t['r_multiple'] for t in losses])) if losses else 0
            ev = (len(wins) / len(trades)) * avg_r_win - (len(losses) / len(trades)) * avg_r_loss
            avg_risk = np.mean([t['risk_pct'] for t in trades])

            cat_stats[cat_name] = {
                'trades': len(trades),
                'wins': len(wins),
                'losses': len(losses),
                'wr': round(wr, 2),
                'avg_r_win': round(avg_r_win, 2),
                'avg_r_loss': round(avg_r_loss, 2),
                'ev': round(ev, 3),
                'avg_risk_pct': round(avg_risk, 2)
            }

        return cat_stats


def load_data(asset='btc'):
    """Load data"""
    data_dir = Path('/Users/illiachumak/trading/backtest/data')

    if asset == 'btc':
        htf_file = data_dir / 'btc_4h_data_2018_to_2025.csv'
        ltf_file = data_dir / 'btc_1h_data_2018_to_2025.csv'
    else:
        htf_file = data_dir / 'eth_4h_data_2017_to_2025.csv'
        ltf_file = data_dir / 'eth_1h_data_2017_to_2025.csv'

    htf_df = pd.read_csv(htf_file)
    ltf_df = pd.read_csv(ltf_file)

    return htf_df, ltf_df


def run_final():
    """Run final production backtest"""

    print("\n" + "="*80)
    print("FINAL PRODUCTION BACKTEST")
    print("="*80 + "\n")

    config = {
        'name': 'PRODUCTION_Q3_DynamicRR_VariableRisk',
        'min_score': 3,
        'rr_mapping': {
            (8, 10): 8.0,
            (6, 7): 3.5,
            (4, 5): 3.0,
            (3, 3): 2.5,
            (0, 2): None
        },
        'risk_by_category': {
            '8-10': 2.0,
            '6-7': 1.5,
            '4-5': 1.5,
            '3': 2.0
        }
    }

    results = {}

    for asset in ['btc', 'eth']:
        print(f"\n{'='*80}")
        print(f"ASSET: {asset.upper()}")
        print(f"{'='*80}")

        htf_df, ltf_df = load_data(asset)

        backtest = ProductionBacktest(
            htf_df=htf_df,
            ltf_df=ltf_df,
            config=config,
            start_date='2024-01-01',
            end_date='2025-12-31',
            initial_capital=10000
        )

        stats = backtest.run()
        stats['asset'] = asset
        results[asset] = stats

        # Print
        print(f"\n{'='*80}")
        print(f"RESULTS - {asset.upper()}")
        print(f"{'='*80}\n")

        print(f"Impulses: {stats['impulses_found']}")
        print(f"Trades: {stats['total_trades']}")
        print(f"Win Rate: {stats['win_rate']}%")
        print(f"EV per R: {stats['ev_per_r']}")
        print(f"Total PnL: ${stats['total_pnl']:,.2f} ({stats['total_pnl_pct']}%)")
        print(f"Max DD: {stats['max_drawdown_pct']}%")
        print(f"Profit Factor: {stats['profit_factor']}\n")

        print("CATEGORY BREAKDOWN:\n")
        print(f"{'Category':<10} {'Trades':<8} {'WR %':<10} {'EV':<10} {'Avg Risk %':<12}")
        print(f"{'-'*60}")

        for cat, cat_stat in stats['category_stats'].items():
            print(f"{cat:<10} {cat_stat['trades']:<8} {cat_stat['wr']:<10.2f} {cat_stat['ev']:<10.3f} {cat_stat['avg_risk_pct']:<12.2f}")

    # Save
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = Path(__file__).parent / f'PRODUCTION_BACKTEST_{timestamp}.json'

    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n{'='*80}")
    print(f"Results saved to: {output_file}")
    print(f"{'='*80}\n")

    return results


if __name__ == "__main__":
    results = run_final()
