"""
Verify Lookahead Bias in HELD FVG Backtest

Цей скрипт перевіряє чи є lookahead bias в результатах бектесту.

Lookahead bias виявляється якщо:
- Трейд відкрито на 15M свічці з timestamp T
- Але інформація для рішення (hold на 4H) доступна тільки після T + 4h

Приклад:
- 4H свічка: 2024-01-01 16:00 (відкриття) - закриється в 20:00
- Hold виявлено по Close price (20:00)
- Трейд відкрито на 15M свічці 2024-01-01 16:15
- ❌ Це lookahead bias! Не могли знати про hold до 20:00
"""

import json
import pandas as pd
from datetime import datetime, timedelta

def load_backtest_results(filepath: str) -> dict:
    """Load backtest results from JSON"""
    with open(filepath, 'r') as f:
        return json.load(f)

def verify_lookahead_bias(results: dict):
    """
    Перевіряє чи є lookahead bias в результатах

    Логіка:
    - Якщо свічка 4H закривається в T
    - То трейди на цій основі можуть відкриватися тільки >= T
    - Якщо трейд відкрито раніше - це lookahead bias
    """
    print("="*80)
    print("ПЕРЕВІРКА LOOKAHEAD BIAS")
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

            # Parse entry time
            entry_time = pd.to_datetime(entry_time_str)

            # Визначаємо час відкриття попередньої 4H свічки
            # Якщо entry в 16:15, то попередня 4H свічка відкрилась в 16:00, закриється в 20:00

            # Normalize to 4H grid (00:00, 04:00, 08:00, 12:00, 16:00, 20:00)
            hour = entry_time.hour
            candle_4h_open_hour = (hour // 4) * 4

            # Час відкриття 4H свічки
            candle_4h_open = entry_time.replace(hour=candle_4h_open_hour, minute=0, second=0, microsecond=0)

            # Час ЗАКРИТТЯ 4H свічки (коли ми дізнаємось про hold!)
            candle_4h_close = candle_4h_open + timedelta(hours=4)

            # КРИТИЧНА ПЕРЕВІРКА:
            # Якщо entry_time < candle_4h_close, то це lookahead bias!
            # Бо ми не могли знати про hold до candle_4h_close

            if entry_time < candle_4h_close:
                bias_count += 1
                time_diff = (candle_4h_close - entry_time).total_seconds() / 3600  # hours

                suspicious_trades.append({
                    'entry_time': entry_time_str,
                    'candle_4h_open': str(candle_4h_open),
                    'candle_4h_close': str(candle_4h_close),
                    'hours_before_close': time_diff,
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
                print(f"         4H свічка: {st['candle_4h_open']} - {st['candle_4h_close']}")
                print(f"         ⚠️  Трейд відкрито на {st['hours_before_close']:.2f}h РАНІШЕ закриття 4H свічки!")
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
        print(f"  ✅ Lookahead bias не виявлено")
    print("="*80)

def main():
    import sys

    if len(sys.argv) < 2:
        # Use most recent file
        filepath = "backtest_held_fvg_all_combinations_20251201_122446.json"
        print(f"Using default file: {filepath}\n")
    else:
        filepath = sys.argv[1]

    try:
        results = load_backtest_results(filepath)
        verify_lookahead_bias(results)
    except FileNotFoundError:
        print(f"❌ File not found: {filepath}")
        print("\nUsage: python verify_lookahead_bias.py [backtest_results.json]")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
