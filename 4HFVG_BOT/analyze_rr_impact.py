"""
Аналіз впливу RR на кількість трейдів
Перевіряє гіпотезу: чи більше трейдів закриваються по SL при більшому RR
"""

import json
import sys
from collections import defaultdict

def analyze_backtest_results(filename):
    """Аналізує результати бектесту"""
    with open(filename, 'r') as f:
        data = json.load(f)
    
    trades = data['trades']
    summary = data['summary']
    
    # Підрахунок за exit_reason
    exit_reasons = defaultdict(int)
    sl_trades = []
    tp_trades = []
    
    for trade in trades:
        reason = trade['exit_reason']
        exit_reasons[reason] += 1
        
        if reason == 'SL':
            sl_trades.append(trade)
        elif reason == 'TP':
            tp_trades.append(trade)
    
    # Середній час утримання трейдів
    def avg_holding_time(trade_list):
        if not trade_list:
            return 0
        from datetime import datetime
        times = []
        for t in trade_list:
            entry = datetime.fromisoformat(t['entry_time'].replace(' ', 'T'))
            exit = datetime.fromisoformat(t['exit_time'].replace(' ', 'T'))
            times.append((exit - entry).total_seconds() / 3600)  # в годинах
        return sum(times) / len(times) if times else 0
    
    avg_sl_time = avg_holding_time(sl_trades)
    avg_tp_time = avg_holding_time(tp_trades)
    
    return {
        'filename': filename,
        'total_trades': summary['total_trades'],
        'exit_reasons': dict(exit_reasons),
        'sl_count': exit_reasons['SL'],
        'tp_count': exit_reasons['TP'],
        'sl_percentage': (exit_reasons['SL'] / summary['total_trades'] * 100) if summary['total_trades'] > 0 else 0,
        'tp_percentage': (exit_reasons['TP'] / summary['total_trades'] * 100) if summary['total_trades'] > 0 else 0,
        'avg_rr': summary['avg_rr'],
        'avg_sl_holding_hours': avg_sl_time,
        'avg_tp_holding_hours': avg_tp_time,
        'win_rate': summary['win_rate']
    }

def main():
    # Файли для аналізу - порівнюємо різні RR
    files = [
        'backtest_2024_fixed.json',  # RR 1.5
        'backtest_failed_fvg_2024_4h_expiry.json',  # RR 3.0
    ]
    
    results = []
    for filename in files:
        try:
            result = analyze_backtest_results(filename)
            results.append(result)
        except Exception as e:
            print(f"Помилка при обробці {filename}: {e}")
    
    # Виведення результатів
    print("\n" + "="*80)
    print("АНАЛІЗ ВПЛИВУ RR НА КІЛЬКІСТЬ ТРЕЙДІВ")
    print("="*80)
    print(f"\n{'Файл':<40} {'RR':<6} {'Трейди':<8} {'SL':<6} {'TP':<6} {'SL%':<8} {'Win Rate':<10}")
    print("-"*80)
    
    for r in results:
        filename_short = r['filename'].replace('backtest_failed_fvg_2024_', '').replace('.json', '')
        print(f"{filename_short:<40} {r['avg_rr']:<6.1f} {r['total_trades']:<8} "
              f"{r['sl_count']:<6} {r['tp_count']:<6} {r['sl_percentage']:<8.1f}% {r['win_rate']:<10.1f}%")
    
    print("\n" + "="*80)
    print("СЕРЕДНІЙ ЧАС УТРИМАННЯ ТРЕЙДІВ")
    print("="*80)
    print(f"\n{'Файл':<40} {'RR':<6} {'SL (год)':<12} {'TP (год)':<12}")
    print("-"*80)
    
    for r in results:
        filename_short = r['filename'].replace('backtest_failed_fvg_2024_', '').replace('.json', '')
        print(f"{filename_short:<40} {r['avg_rr']:<6.1f} {r['avg_sl_holding_hours']:<12.1f} {r['avg_tp_holding_hours']:<12.1f}")
    
    # Висновки
    print("\n" + "="*80)
    print("ВИСНОВКИ")
    print("="*80)
    
    if len(results) >= 2:
        # Порівняння першого та останнього
        first = results[0]
        last = results[-1]
        
        print(f"\n1. Кількість трейдів:")
        print(f"   RR {first['avg_rr']:.1f}: {first['total_trades']} трейдів")
        print(f"   RR {last['avg_rr']:.1f}: {last['total_trades']} трейдів")
        print(f"   Різниця: {last['total_trades'] - first['total_trades']} трейдів")
        
        print(f"\n2. Відсоток трейдів, що закрилися по SL:")
        print(f"   RR {first['avg_rr']:.1f}: {first['sl_percentage']:.1f}%")
        print(f"   RR {last['avg_rr']:.1f}: {last['sl_percentage']:.1f}%")
        print(f"   Різниця: {last['sl_percentage'] - first['sl_percentage']:.1f}%")
        
        print(f"\n3. Середній час утримання трейдів, що закрилися по SL:")
        print(f"   RR {first['avg_rr']:.1f}: {first['avg_sl_holding_hours']:.1f} годин")
        print(f"   RR {last['avg_rr']:.1f}: {last['avg_sl_holding_hours']:.1f} годин")
        
        if last['avg_sl_holding_hours'] < first['avg_sl_holding_hours']:
            print(f"   ✅ Трейди закриваються по SL ШВИДШЕ при більшому RR!")
            print(f"   Це пояснює, чому більше трейдів: швидше закриття = більше можливостей для нових трейдів")
        else:
            print(f"   ⚠️ Трейди закриваються по SL ПОВІЛЬНІШЕ при більшому RR")
    
    print("\n" + "="*80)

if __name__ == "__main__":
    main()

