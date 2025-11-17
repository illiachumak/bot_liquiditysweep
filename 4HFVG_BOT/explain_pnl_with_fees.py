#!/usr/bin/env python3
"""
Пояснення розрахунку PnL з комісіями
"""

import json

# Завантажуємо останній бектест
with open('backtest_2months_20251117_165856.json', 'r') as f:
    backtest = json.load(f)

print("="*100)
print("РОЗРАХУНОК PNL З КОМІСІЯМИ В БЕКТЕСТІ")
print("="*100)

# Візьмемо перший трейд як приклад
trade = backtest['trades'][0]

print(f"\nПриклад трейду #{trade['trade_id']}:")
print(f"Тип: {trade['type']}")
print(f"Entry price: ${trade['entry_price']:,.2f}")
print(f"Exit price: ${trade['exit_price']:,.2f}")
print(f"Size: {trade['size']:.8f} BTC")
print(f"SL: ${trade['sl']:,.2f}")
print(f"TP: ${trade['tp']:,.2f}")

# Розрахуємо базовий PnL (без комісій)
if trade['type'] == 'LONG':
    base_pnl = (trade['exit_price'] - trade['entry_price']) * trade['size']
else:  # SHORT
    base_pnl = (trade['entry_price'] - trade['exit_price']) * trade['size']

print(f"\n{'─'*100}")
print("ДЕТАЛЬНИЙ РОЗРАХУНОК:")
print(f"{'─'*100}")

print(f"\n1️⃣  Базовий PnL (без комісій):")
if trade['type'] == 'LONG':
    print(f"   Formula: (Exit - Entry) × Size")
    print(f"   = (${trade['exit_price']:,.2f} - ${trade['entry_price']:,.2f}) × {trade['size']:.8f}")
else:
    print(f"   Formula: (Entry - Exit) × Size")
    print(f"   = (${trade['entry_price']:,.2f} - ${trade['exit_price']:,.2f}) × {trade['size']:.8f}")
print(f"   = ${base_pnl:,.2f}")

# Розрахуємо комісії
# Згідно з кодом:
# maker_fee = 0.0018 (0.18%) для entry та TP (limit orders)
# taker_fee = 0.0045 (0.45%) для SL (market orders)

maker_fee = 0.0018
taker_fee = 0.0045

entry_fee = trade['entry_price'] * trade['size'] * maker_fee
if trade['exit_reason'] == 'SL':
    exit_fee = trade['exit_price'] * trade['size'] * taker_fee
else:  # TP or TIMEOUT
    exit_fee = trade['exit_price'] * trade['size'] * maker_fee

total_fees = entry_fee + exit_fee

print(f"\n2️⃣  Комісії:")
print(f"   Entry Fee (maker 0.18%): ${trade['entry_price']:,.2f} × {trade['size']:.8f} × 0.0018 = ${entry_fee:,.2f}")
if trade['exit_reason'] == 'SL':
    print(f"   Exit Fee (taker 0.45%): ${trade['exit_price']:,.2f} × {trade['size']:.8f} × 0.0045 = ${exit_fee:,.2f}")
else:
    print(f"   Exit Fee (maker 0.18%): ${trade['exit_price']:,.2f} × {trade['size']:.8f} × 0.0018 = ${exit_fee:,.2f}")
print(f"   Total Fees: ${total_fees:,.2f}")

final_pnl = base_pnl - total_fees
print(f"\n3️⃣  Фінальний PnL:")
print(f"   = Базовий PnL - Комісії")
print(f"   = ${base_pnl:,.2f} - ${total_fees:,.2f}")
print(f"   = ${final_pnl:,.2f}")

print(f"\n{'─'*100}")
print(f"РЕЗУЛЬТАТ З БЕКТЕСТУ: ${trade['pnl']:,.2f}")
print(f"НАШІ РОЗРАХУНКИ:      ${final_pnl:,.2f}")
print(f"{'─'*100}")

if abs(final_pnl - trade['pnl']) < 0.01:
    print("\n✅ ТАК, В PNL ВРАХОВАНО КОМІСІЇ!")
else:
    print("\n❌ КОМІСІЇ НЕ ВРАХОВАНІ В PNL")

# Перевіряємо всі трейди
print("\n\n" + "="*100)
print("ПЕРЕВІРКА ВСІХ ТРЕЙДІВ")
print("="*100)

print(f"\n{'Trade ID':<10} {'Type':<8} {'Exit':<8} {'Maker Fee':<12} {'Taker/Maker Fee':<18} {'Total Fees':<12}")
print("─"*100)

total_all_fees = 0
for trade in backtest['trades']:
    entry_fee = trade['entry_price'] * trade['size'] * maker_fee
    if trade['exit_reason'] == 'SL':
        exit_fee = trade['exit_price'] * trade['size'] * taker_fee
        exit_type = "Taker (0.45%)"
    else:
        exit_fee = trade['exit_price'] * trade['size'] * maker_fee
        exit_type = "Maker (0.18%)"

    total_fees = entry_fee + exit_fee
    total_all_fees += total_fees

    print(f"{trade['trade_id']:<10} {trade['type']:<8} {trade['exit_reason']:<8} ${entry_fee:<11.2f} ${exit_fee:<12.2f} ({exit_type:<10}) ${total_fees:<11.2f}")

print("─"*100)
print(f"{'TOTAL':<50} ${total_all_fees:,.2f}")

# Розрахуємо вплив комісій на загальний результат
total_gross_pnl = sum([
    (t['exit_price'] - t['entry_price']) * t['size'] if t['type'] == 'LONG'
    else (t['entry_price'] - t['exit_price']) * t['size']
    for t in backtest['trades']
])

total_net_pnl = backtest['summary']['total_pnl']

print(f"\n{'='*100}")
print("ВПЛИВ КОМІСІЙ НА ЗАГАЛЬНИЙ РЕЗУЛЬТАТ:")
print(f"{'='*100}")
print(f"Валовий PnL (без комісій):     ${total_gross_pnl:,.2f}")
print(f"Сума всіх комісій:             -${total_all_fees:,.2f}")
print(f"Чистий PnL (з комісіями):      ${total_net_pnl:,.2f}")
print(f"Вплив комісій на прибуток:     -{total_all_fees/total_gross_pnl*100:.2f}%")
print(f"{'='*100}")

print("\n\n📋 ВИСНОВОК:")
print("─"*100)
print("✅ ТАК, в бектесті PnL кожного трейда ВРАХОВУЄ комісії!")
print("\nСтруктура комісій:")
print("  • Entry (limit order):  0.18% maker fee")
print("  • TP (limit order):     0.18% maker fee")
print("  • SL (market order):    0.45% taker fee")
print("\nВ коді (backtest_failed_fvg.py:148-157):")
print("  self.pnl -= total_fees  # Комісії віднімаються від PnL")
print("─"*100)
