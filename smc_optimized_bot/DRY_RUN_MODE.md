# 📝 Dry Run Mode - Testing Without Real Orders

## ✅ Що Зроблено

Додано **DRY RUN режим** - бот логує всі orders які БУЛИ Б надіслані на Binance, але **НЕ створює реальні orders**.

---

## 🎯 Мета

Перевірити роботу бота та порівняти з бектестом **БЕЗ ризику** реальних трейдів.

---

## 🔧 Як Працює

### Dry Run Mode (DRY_RUN=true):
- ✅ **Логує** всі orders в `trades_history/trades.json` та `.csv`
- ✅ **Симулює** fill через порівняння ціни з limit
- ✅ **НЕ створює** реальні orders на Binance
- ✅ **НЕ викликає** Binance API для orders
- ✅ Використовує фіксований баланс ($10,000) для розрахунків

### Real Mode (DRY_RUN=false):
- ✅ Створює **реальні** orders на Binance
- ✅ Перевіряє статус через Binance API
- ✅ Використовує реальний баланс

---

## 📊 Що Логується

### BINANCE_ORDER Event:

```json
{
  "event": "BINANCE_ORDER",
  "dry_run": true,
  "side": "BUY",
  "quantity": 0.200,
  "price": 50000.00,
  "type": "LONG",
  "level": 1,
  "sl": 49500.00,
  "tp1": 50750.00,
  "tp2": 51250.00,
  "tp3": 52000.00,
  "placed_time": "2025-11-12T20:30:00",
  "expiry_time": "2025-11-13T08:30:00",
  "ob_id": "1_49450.00_49550.00",
  "binance_order_id": null
}
```

**Поля:**
- `event`: "BINANCE_ORDER"
- `dry_run`: `true` (dry run) або `false` (real)
- `side`: "BUY" або "SELL"
- `quantity`: Кількість BTC
- `price`: Limit price
- `type`: "LONG" або "SHORT"
- `level`: 1, 2, або 3
- `sl`, `tp1`, `tp2`, `tp3`: Stop loss та take profit levels
- `placed_time`: Коли order був би створений
- `expiry_time`: Коли order експайриться
- `ob_id`: Order Block ID
- `binance_order_id`: `null` в dry_run, реальний ID в real mode

---

## 🚀 Як Використовувати

### 1. Запуск в Dry Run Mode (за замовчуванням):

```bash
# Dry run ON (default)
python3 smc_optimized_bot.py

# Або явно
DRY_RUN=true python3 smc_optimized_bot.py
```

### 2. Запуск в Real Mode:

```bash
# Встанови DRY_RUN=false
DRY_RUN=false python3 smc_optimized_bot.py

# Або в .env файлі
echo "DRY_RUN=false" >> .env
```

### 3. Docker:

```bash
# Dry run (default)
docker compose up -d

# Real mode
DRY_RUN=false docker compose up -d
```

---

## 📁 Де Знайти Логи

### JSON:
```bash
cat trades_history/trades.json | jq '.[] | select(.event == "BINANCE_ORDER")'
```

### CSV:
```bash
cat trades_history/trades.csv | grep BINANCE_ORDER
```

### Тільки Dry Run Orders:
```bash
cat trades_history/trades.json | jq '.[] | select(.event == "BINANCE_ORDER" and .dry_run == true)'
```

---

## 🔍 Порівняння з Бектестом

### 1. Експортуй Orders з Dry Run:

```python
import json
import pandas as pd

# Load dry run orders
with open('trades_history/trades.json', 'r') as f:
    trades = json.load(f)

# Filter BINANCE_ORDER events
orders = [t for t in trades if t['event'] == 'BINANCE_ORDER']

# Convert to DataFrame
df = pd.DataFrame(orders)

# Save for comparison
df.to_csv('dry_run_orders.csv', index=False)
```

### 2. Порівняй з Бектестом:

```python
# Load backtest results
backtest_orders = pd.read_csv('backtest_orders.csv')

# Load dry run orders
dry_run_orders = pd.read_csv('dry_run_orders.csv')

# Compare
# - Кількість orders
# - Ціни (limit_price)
# - Час створення
# - SL/TP levels
```

---

## 📊 Приклад Логів

### Console Output (Dry Run):

```
📝 DRY RUN: Would place 3 limit orders on Binance...
📝 DRY RUN: Would create BUY limit order: 0.200 BTC @ $50000.00
📝 DRY RUN: Would create BUY limit order: 0.200 BTC @ $49650.00
📝 DRY RUN: Would create BUY limit order: 0.200 BTC @ $49725.00
✅ 3 NEW LIMIT ORDERS PLACED ON BINANCE
   LONG Level 1: $50000.00 (Order ID: DRY_1734038400000)
   LONG Level 2: $49650.00 (Order ID: DRY_1734038401000)
   LONG Level 3: $49725.00 (Order ID: DRY_1734038402000)
```

### Log File:

```
2025-11-12 20:30:00 | INFO | 📝 DRY RUN: Would place 3 limit orders on Binance...
2025-11-12 20:30:00 | INFO | 📝 DRY RUN: Would create BUY limit order: 0.200 BTC @ $50000.00
2025-11-12 20:30:00 | INFO | 💾 Trade logged to trades_history/trades.json and trades_history/trades.csv
```

---

## ⚙️ Налаштування

### Змінні Оточення:

```bash
# .env файл
DRY_RUN=true          # Dry run mode (default: true)
BINANCE_API_KEY=...   # Не потрібен в dry_run
BINANCE_API_SECRET=... # Не потрібен в dry_run
```

### В Коді:

```python
bot = SMCOptimizedBot(
    api_key=API_KEY,
    api_secret=API_SECRET,
    dry_run=True,  # Enable dry run
    risk_per_trade=0.02
)
```

---

## 🎯 Переваги

✅ **Безпечно**
- Немає ризику реальних трейдів
- Можна тестувати скільки завгодно

✅ **Повне Логування**
- Всі orders логуються в JSON/CSV
- Легко порівняти з бектестом

✅ **Швидко**
- Не треба чекати на Binance API
- Не треба API ключі (в dry_run)

✅ **Точність**
- Та сама логіка що і в real mode
- Тільки без реальних orders

---

## ⚠️ Важливо

### 1. Balance в Dry Run:

Використовується фіксований баланс **$10,000** для розрахунків.

Якщо хочеш інший баланс, зміни в коді:
```python
# В calculate_position_size()
if self.dry_run:
    balance = 20000.0  # Твій баланс
```

### 2. Fill Simulation:

В dry_run fills симулюються через порівняння `current_price` з `limit_price`:
- LONG: `current_price <= limit_price`
- SHORT: `current_price >= limit_price`

Це **не точно** як Binance (може бути slippage), але достатньо для тестування логіки.

### 3. Order IDs:

В dry_run використовуються симульовані IDs: `DRY_<timestamp>`

---

## 📋 Checklist для Тестування

- [ ] Запустити в dry_run режимі
- [ ] Перевірити що orders логуються в `trades_history/`
- [ ] Порівняти з бектестом:
  - [ ] Кількість orders
  - [ ] Ціни (limit_price)
  - [ ] Час створення
  - [ ] SL/TP levels
- [ ] Перевірити fills (симульовані)
- [ ] Перевірити exits (TP/SL)

---

## 🚀 Next Steps

1. **Запусти dry_run** на історичних даних
2. **Порівняй** з бектестом
3. **Якщо збігається** → переходи на real mode
4. **Якщо не збігається** → debug та виправ

---

**Status:** ✅ READY FOR TESTING

**Default:** `DRY_RUN=true` (безпечно!)

**Usage:** Просто запусти `python3 smc_optimized_bot.py` і всі orders будуть залоговані!
