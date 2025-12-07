"""
Тестовий приклад для демонстрації проблеми з timing свічок
"""

import pandas as pd
from datetime import datetime, timedelta

# Створимо тестові дані
timestamps = []
current_time = datetime(2024, 1, 1, 0, 0, 0)

# Створимо 5 свічок 4H
for i in range(5):
    timestamps.append(current_time)
    current_time += timedelta(hours=4)

# Додамо ще одну "поточну" свічку (яка ще не закрита)
current_moment = current_time  # 20:00
timestamps.append(current_moment)  # Ця свічка відкрилась в 20:00, але ще не закрита

df_4h = pd.DataFrame({
    'open': [100, 102, 104, 106, 108, 110],
    'high': [101, 103, 105, 107, 109, 111],
    'low': [99, 101, 103, 105, 107, 109],
    'close': [100.5, 102.5, 104.5, 106.5, 108.5, 110.5]
}, index=timestamps)

print("=" * 80)
print("ТЕСТОВІ ДАНІ 4H")
print("=" * 80)
print(f"\nПоточний момент часу: {current_moment} (20:00)")
print(f"Кількість свічок в DataFrame: {len(df_4h)}")
print("\nСвічки:")
for i, (idx, row) in enumerate(df_4h.iterrows()):
    status = "ЗАКРИТА" if i < len(df_4h) - 1 else "🔴 НЕ ЗАКРИТА (формується зараз)"
    next_time = idx + timedelta(hours=4)
    print(f"  Свічка {i}: {idx} - {next_time} | {status}")

print("\n" + "=" * 80)
print("АНАЛІЗ ПОТОЧНОГО КОДУ")
print("=" * 80)

# Поточний код
end_idx = len(df_4h) - 1  # = 5
print(f"\nend_idx = len(df_4h) - 1 = {end_idx}")
print(f"range(0, end_idx + 1) = range(0, {end_idx + 1})")
print(f"Обробляються індекси: {list(range(0, end_idx + 1))}")

print("\n⚠️  ПРОБЛЕМА:")
for i in range(0, end_idx + 1):
    idx = df_4h.index[i]
    status = "ЗАКРИТА" if i < len(df_4h) - 1 else "🔴 НЕ ЗАКРИТА"
    print(f"  Індекс {i}: Свічка {idx} - {status}")
    if i == len(df_4h) - 1:
        print(f"       ❌ Ця свічка ще формується! Її close може змінитися!")

print("\n" + "=" * 80)
print("ВИПРАВЛЕНИЙ КОД")
print("=" * 80)

# Виправлений код
end_idx_fixed = len(df_4h) - 2  # Виключаємо останню свічку
print(f"\nend_idx = len(df_4h) - 2 = {end_idx_fixed}")
print(f"range(0, end_idx + 1) = range(0, {end_idx_fixed + 1})")
print(f"Обробляються індекси: {list(range(0, end_idx_fixed + 1))}")

print("\n✅ ПРАВИЛЬНО:")
for i in range(0, end_idx_fixed + 1):
    idx = df_4h.index[i]
    print(f"  Індекс {i}: Свічка {idx} - ЗАКРИТА")

print(f"\n  Індекс {len(df_4h) - 1}: Свічка {df_4h.index[-1]} - НЕ ЗАКРИТА (пропущена)")

print("\n" + "=" * 80)
