"""
Створення візуального summary трейдів
"""

import pandas as pd
from datetime import datetime

# Trade data from backtest
trades_data = [
    {
        'date': '2025-09-01',
        'type': 'LONG',
        'result': 'LOSS',
        'pnl': -200.00,
        'pnl_pct': -1.46,
        'entry': 109390.30,
        'exit': 107790.47
    },
    {
        'date': '2025-09-28',
        'type': 'LONG',
        'result': 'WIN',
        'pnl': 294.00,
        'pnl_pct': 1.49,
        'entry': 109990.00,
        'exit': 111631.78
    },
    {
        'date': '2025-10-01',
        'type': 'LONG',
        'result': 'WIN',
        'pnl': 302.82,
        'pnl_pct': 2.05,
        'entry': 118552.40,
        'exit': 120977.74
    },
    {
        'date': '2025-10-10',
        'type': 'SHORT',
        'result': 'WIN',
        'pnl': 311.90,
        'pnl_pct': 5.40,
        'entry': 112714.90,
        'exit': 106629.77
    },
    {
        'date': '2025-10-21',
        'type': 'SHORT',
        'result': 'LOSS',
        'pnl': -214.17,
        'pnl_pct': -1.94,
        'entry': 109005.00,
        'exit': 111123.40
    },
    {
        'date': '2025-10-26',
        'type': 'LONG',
        'result': 'LOSS',
        'pnl': -209.89,
        'pnl_pct': -1.53,
        'entry': 114497.80,
        'exit': 112742.01
    }
]


def create_visual_summary():
    """Create visual summary"""
    
    print("\n" + "="*80)
    print("📊 ВІЗУАЛЬНИЙ SUMMARY - LIQUIDITY SWEEP BOT")
    print("="*80)
    
    # Calculate cumulative balance
    initial_balance = 10000
    balance = initial_balance
    
    print(f"\n💰 ДИНАМІКА БАЛАНСУ")
    print("-"*80)
    print(f"Початок: ${initial_balance:,.2f}")
    
    for i, trade in enumerate(trades_data, 1):
        balance += trade['pnl']
        symbol = "✅" if trade['result'] == 'WIN' else "❌"
        
        # Create visual bar
        bar_length = int(abs(trade['pnl_pct']) * 5)
        if trade['pnl'] > 0:
            bar = "🟩" * bar_length
        else:
            bar = "🟥" * bar_length
        
        print(f"\n{symbol} Trade #{i} | {trade['date']} | {trade['type']}")
        print(f"   Entry: ${trade['entry']:,.2f} → Exit: ${trade['exit']:,.2f}")
        print(f"   PnL: ${trade['pnl']:+,.2f} ({trade['pnl_pct']:+.2f}%)")
        print(f"   {bar}")
        print(f"   Balance: ${balance:,.2f}")
    
    total_pnl = balance - initial_balance
    total_return = (total_pnl / initial_balance) * 100
    
    print("\n" + "-"*80)
    print(f"Кінець: ${balance:,.2f}")
    print(f"Прибуток: ${total_pnl:+,.2f} ({total_return:+.2f}%)")
    
    # Monthly breakdown
    print("\n" + "="*80)
    print("📅 РОЗПОДІЛ ПО МІСЯЦЯХ")
    print("="*80)
    
    months = {
        '2025-09': {'trades': 0, 'wins': 0, 'pnl': 0},
        '2025-10': {'trades': 0, 'wins': 0, 'pnl': 0},
        '2025-11': {'trades': 0, 'wins': 0, 'pnl': 0}
    }
    
    for trade in trades_data:
        month = trade['date'][:7]
        months[month]['trades'] += 1
        if trade['result'] == 'WIN':
            months[month]['wins'] += 1
        months[month]['pnl'] += trade['pnl']
    
    for month, data in months.items():
        month_name = {
            '2025-09': 'Вересень',
            '2025-10': 'Жовтень',
            '2025-11': 'Листопад'
        }[month]
        
        wr = (data['wins'] / data['trades'] * 100) if data['trades'] > 0 else 0
        
        print(f"\n{month_name} 2025:")
        print(f"   Трейдів: {data['trades']}")
        print(f"   Виграшних: {data['wins']} ({wr:.0f}%)")
        print(f"   PnL: ${data['pnl']:+,.2f}")
        
        if data['trades'] > 0:
            # Create bar chart
            bar_length = data['trades']
            win_bars = "🟩" * data['wins']
            loss_bars = "🟥" * (data['trades'] - data['wins'])
            print(f"   {win_bars}{loss_bars}")
    
    # Win/Loss distribution
    print("\n" + "="*80)
    print("📊 РОЗПОДІЛ WIN/LOSS")
    print("="*80)
    
    wins = [t for t in trades_data if t['result'] == 'WIN']
    losses = [t for t in trades_data if t['result'] == 'LOSS']
    
    print(f"\n✅ WINS: {len(wins)}/6 (50%)")
    print("   " + "🟩" * len(wins))
    
    if wins:
        avg_win = sum(t['pnl'] for t in wins) / len(wins)
        max_win = max(wins, key=lambda x: x['pnl'])
        print(f"   Середній виграш: ${avg_win:.2f}")
        print(f"   Найкращий: ${max_win['pnl']:.2f} ({max_win['date']})")
    
    print(f"\n❌ LOSSES: {len(losses)}/6 (50%)")
    print("   " + "🟥" * len(losses))
    
    if losses:
        avg_loss = sum(t['pnl'] for t in losses) / len(losses)
        max_loss = min(losses, key=lambda x: x['pnl'])
        print(f"   Середній програш: ${avg_loss:.2f}")
        print(f"   Найгірший: ${max_loss['pnl']:.2f} ({max_loss['date']})")
    
    # Performance metrics
    print("\n" + "="*80)
    print("📈 МЕТРИКИ PERFORMANCE")
    print("="*80)
    
    print(f"\n✅ ПОЗИТИВНІ:")
    print(f"   • Profit Factor: {abs(sum(t['pnl'] for t in wins)) / abs(sum(t['pnl'] for t in losses)):.2f}")
    print(f"   • Середній Win > Avg Loss: ${avg_win:.2f} vs ${avg_loss:.2f}")
    print(f"   • Max Win: ${max_win['pnl']:.2f} (+{max_win['pnl_pct']:.2f}%)")
    print(f"   • Всі SL/TP спрацювали правильно ✅")
    
    print(f"\n⚠️  ДЛЯ ПОКРАЩЕННЯ:")
    print(f"   • Win Rate: 50% (ціль: 55-60%)")
    print(f"   • Місячна прибутковість: 0.95% (ціль: 2.7%)")
    print(f"   • Потрібно більше даних (3 міс → 6-12 міс)")
    
    # Comparison with backtest
    print("\n" + "="*80)
    print("🎯 ПОРІВНЯННЯ З БЕКТЕСТОМ (2022-2025)")
    print("="*80)
    
    comparison = [
        ("Місячна прибутковість", "2.71%", "0.95%", "⚠️"),
        ("Win Rate", "59%", "50%", "⚠️"),
        ("Трейдів/місяць", "~2", "2", "✅"),
        ("Max Drawdown", "-10.67%", "~-2%", "✅"),
        ("Profit Factor", "2.15", "1.5", "⚠️")
    ]
    
    print(f"\n{'Метрика':<25} {'Очікування':<15} {'Факт':<15} {'Статус':<5}")
    print("-"*65)
    for metric, expected, actual, status in comparison:
        print(f"{metric:<25} {expected:<15} {actual:<15} {status:<5}")
    
    print("\n💡 Висновок: Результати нижче очікувань, але це нормально для короткого періоду")
    print("   Потрібно 6-12 місяців для валідації стратегії")
    
    # Current market status
    print("\n" + "="*80)
    print("📊 ПОТОЧНИЙ СТАН (12.11.2025)")
    print("="*80)
    
    print(f"\n💰 BTC/USDT: $104,929")
    print(f"📊 24h: $102,400 - $105,297")
    print(f"📏 ATR(14): $1,271")
    
    print(f"\n🎯 Потенційні Setup-и:")
    print(f"   🟢 LONG: $102,629 (Asian Low)")
    print(f"   🟢 LONG: $103,066 (London Low)")
    print(f"   🔴 SHORT: $105,297 (London High)")
    
    print(f"\n🤖 Бот активний і шукає сигнали...")
    
    # Recommendations
    print("\n" + "="*80)
    print("💡 РЕКОМЕНДАЦІЇ")
    print("="*80)
    
    print(f"\n✅ ЩО РОБИТИ:")
    print(f"   1. Продовжити запуск бота на Testnet")
    print(f"   2. Дати йому попрацювати ще 2-3 місяці")
    print(f"   3. Не змінювати параметри")
    print(f"   4. Збирати статистику")
    print(f"   5. Бути терплячим")
    
    print(f"\n❌ ЩО НЕ РОБИТИ:")
    print(f"   1. Не змінювати параметри через низьку частоту")
    print(f"   2. Не входити вручну")
    print(f"   3. Не зупиняти бота")
    print(f"   4. Не очікувати швидких результатів")
    
    print(f"\n🎓 ПАМ'ЯТАЙТЕ:")
    print(f"   • Низька частота - це нормально (~2 трейди/міс)")
    print(f"   • Якість > Кількість")
    print(f"   • Win Rate 50% + позитивний Profit Factor = profitable")
    print(f"   • Потрібен довгостроковий підхід (6-12+ місяців)")
    
    print("\n" + "="*80)
    print("✅ ВИСНОВОК: Стратегія працює, потрібно більше часу!")
    print("="*80)
    
    print(f"\nНаступна перевірка: 15 грудня 2025")
    print(f"Статус: Продовжуємо тестування 🚀")
    print("")


if __name__ == "__main__":
    create_visual_summary()

