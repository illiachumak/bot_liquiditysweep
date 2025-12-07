"""
Verify Lookahead Bias in HELD FVG Backtest - CORRECTED VERSION

Правильна логіка перевірки:
- Hold виявляється коли 4H свічка ЗАКРИВАЄТЬСЯ
- Якщо свічка 12:00-16:00, hold стає доступним о 16:00
- Трейди можуть відкриватися >= 16:00
- Якщо entry в 16:00, це OK! (hold доступний о 16:00)
- Якщо entry в 15:45, це BIAS! (hold ще не доступний)
"""

import json
import pandas as pd
from datetime import datetime, timedelta

def load_backtest_results(filepath: str) -> dict:
    """Load backtest results from JSON"""
    with open(filepath, 'r') as f:
        return json.load(f)

def get_4h_candle_times(entry_time: pd.Timestamp) -> tuple:
    """
    Get the 4H candle BEFORE entry time (where hold was detected)

    Logic:
    - 4H candles align to: 00:00, 04:00, 08:00, 12:00, 16:00, 20:00
    - If entry is at 16:15, the PREVIOUS 4H candle was 12:00-16:00
    - Hold becomes available at 16:00 (when that candle closed)
    - Entry at 16:15 >= 16:00 = NO BIAS
    """
    # Find which 4H slot the entry falls into
    hour = entry_time.hour
    minute = entry_time.minute

    # Calculate the 4H open time that entry falls into or after
    current_4h_slot = (hour // 4) * 4

    # If entry is exactly at slot boundary (e.g., 16:00:00)
    # The hold was from PREVIOUS 4H candle (12:00-16:00)
    if minute == 0 and entry_time.second == 0:
        # Entry at exact 4H boundary - hold from previous candle
        prev_4h_slot = current_4h_slot - 4
        if prev_4h_slot < 0:
            prev_4h_slot = 20
            hold_candle_open = entry_time.replace(hour=prev_4h_slot, minute=0, second=0) - timedelta(days=1)
        else:
            hold_candle_open = entry_time.replace(hour=prev_4h_slot, minute=0, second=0)
        hold_candle_close = entry_time  # This is when hold becomes available
    else:
        # Entry is AFTER 4H boundary
        # The current 4H candle started at current_4h_slot
        # But hold was from PREVIOUS candle
        prev_4h_slot = current_4h_slot - 4
        if prev_4h_slot < 0:
            prev_4h_slot = 20
            hold_candle_open = entry_time.replace(hour=prev_4h_slot, minute=0, second=0) - timedelta(days=1)
        else:
            hold_candle_open = entry_time.replace(hour=prev_4h_slot, minute=0, second=0)

        # Hold candle closes at current slot
        hold_candle_close = entry_time.replace(hour=current_4h_slot, minute=0, second=0, microsecond=0)

    return hold_candle_open, hold_candle_close

def verify_lookahead_bias(results: dict):
    """
    Перевіряє чи є lookahead bias в результатах - CORRECTED VERSION
    """
    print("="*80)
    print("ПЕРЕВІРКА LOOKAHEAD BIAS (CORRECTED)")
    print("="*80)

    all_results = results.get('all_results', [])

    total_bias_cases = 0

    for result in all_results:
        entry_method = result['entry_method']
        tp_method = result['tp_method']
        trades = result.get('trades', [])

        print(f"\n📊 {entry_method} + {tp_method}")
        print(f"   Total trades: {len(trades)}")

        bias_count = 0
        suspicious_trades = []

        for trade in trades:
            entry_time_str = trade['entry_time']
            entry_time = pd.to_datetime(entry_time_str)

            # Get the 4H candle where hold was detected
            hold_candle_open, hold_available_time = get_4h_candle_times(entry_time)

            # CRITICAL CHECK:
            # Entry can happen ONLY >= hold_available_time
            # If entry_time < hold_available_time, that's lookahead bias
            if entry_time < hold_available_time:
                bias_count += 1
                time_diff = (hold_available_time - entry_time).total_seconds() / 3600  # hours

                suspicious_trades.append({
                    'entry_time': entry_time_str,
                    'hold_candle_open': str(hold_candle_open),
                    'hold_available_time': str(hold_available_time),
                    'hours_before_available': time_diff,
                    'direction': trade['direction'],
                    'entry': trade['entry'],
                    'pnl': trade['pnl']
                })

        if bias_count > 0:
            print(f"   🔴 LOOKAHEAD BIAS DETECTED: {bias_count}/{len(trades)} trades ({bias_count/len(trades)*100:.1f}%)")

            # Показати перші 3 приклади
            print(f"\n   Приклади:")
            for i, st in enumerate(suspicious_trades[:3], 1):
                print(f"      {i}. Entry: {st['entry_time']}")
                print(f"         Hold candle: {st['hold_candle_open']} - {st['hold_available_time']}")
                print(f"         ⚠️  Трейд відкрито на {st['hours_before_available']:.2f}h РАНІШЕ!")
                print(f"         Direction: {st['direction']}, PnL: ${st['pnl']:.2f}")
                print()

            total_bias_cases += bias_count
        else:
            print(f"   ✅ No lookahead bias detected")

    print("\n" + "="*80)
    print(f"РЕЗЮМЕ:")
    print(f"  Total trades with lookahead bias: {total_bias_cases}")
    if total_bias_cases > 0:
        print(f"  ❌ БЕКТЕСТ МАЄ LOOKAHEAD BIAS!")
        print(f"  Результати не можуть бути досягнуті в live trading!")
    else:
        print(f"  ✅ Lookahead bias не виявлено - results are valid! 🎉")
    print("="*80)

def main():
    import sys

    if len(sys.argv) < 2:
        # Use most recent file
        filepath = "backtest_held_fvg_all_combinations_20251207_235112.json"
        print(f"Using file: {filepath}\n")
    else:
        filepath = sys.argv[1]

    try:
        results = load_backtest_results(filepath)
        verify_lookahead_bias(results)
    except FileNotFoundError:
        print(f"❌ File not found: {filepath}")
        print("\nUsage: python verify_lookahead_bias_v2.py [backtest_results.json]")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
