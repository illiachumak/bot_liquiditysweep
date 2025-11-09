# 📊 Де Зберігаються Дані Трейдів?

Повна інформація про збереження даних бота.

---

## 📁 Структура Файлів

```
/Users/illiachumak/trading/implement/
│
└── logs/
    ├── liquidity_sweep_bot.log    # Всі події бота (text)
    ├── trades.json                # Історія ВСІХ трейдів (JSON)
    └── performance.json           # Статистика продуктивності (JSON)
```

### Docker (Ubuntu)

```
/opt/trading/implement/
│
└── logs/
    ├── liquidity_sweep_bot.log
    ├── trades.json
    └── performance.json
```

---

## 📝 logs/liquidity_sweep_bot.log

**Формат:** Plain text  
**Кодування:** UTF-8  
**Оновлення:** В реальному часі

### Що Записується

- ✅ Запуск/зупинка бота
- ✅ Нові свічки
- ✅ Session levels
- ✅ Виявлені сигнали
- ✅ Виконані ордери
- ✅ Закриття позицій
- ✅ PnL кожного трейда
- ✅ Статистика
- ✅ Помилки

### Приклад

```
2025-11-09 10:00:00 | INFO | [TESTNET] Binance client initialized
2025-11-09 10:00:01 | INFO | Loaded 100 historical candles
2025-11-09 10:00:01 | INFO | Account balance: $10000.00 USDT
2025-11-09 10:00:01 | INFO | ✅ Bot initialized successfully
2025-11-09 14:00:00 | INFO | 🕯️ New candle: 2025-11-09 14:00:00
2025-11-09 14:00:05 | INFO | 🚨 SIGNAL DETECTED: LONG
2025-11-09 14:00:05 | INFO |    Entry: $50000.00
2025-11-09 14:00:05 | INFO |    Stop Loss: $49250.00
2025-11-09 14:00:05 | INFO |    Take Profit: $51125.00
2025-11-09 14:00:07 | INFO | ✅ Market order executed: LONG 0.267 BTC
2025-11-09 14:00:08 | INFO | 💾 Trade saved to logs/trades.json
2025-11-09 22:00:00 | INFO | ✅ Position closed - WIN | PnL: $300.00
2025-11-09 22:00:00 | INFO | 📊 Stats: 1 trades | 100.0% WR | $300.00 PnL
```

### Переглянути

```bash
# Tail (live)
tail -f logs/liquidity_sweep_bot.log

# Останні 50 рядків
tail -n 50 logs/liquidity_sweep_bot.log

# Шукати помилки
grep -i error logs/liquidity_sweep_bot.log

# Шукати трейди
grep "SIGNAL DETECTED" logs/liquidity_sweep_bot.log
```

---

## 💾 logs/trades.json

**Формат:** JSON Array  
**Кодування:** UTF-8  
**Оновлення:** Після кожного закритого трейда

### Структура

```json
[
  {
    "timestamp": "ISO 8601 timestamp",
    "symbol": "BTCUSDT",
    "side": "LONG or SHORT",
    "entry_price": 50000.0,
    "exit_price": 50750.0,
    "stop_loss": 49250.0,
    "take_profit": 51125.0,
    "rr_ratio": 1.5,
    "pnl": 300.0,
    "pnl_percent": 3.0,
    "win": true,
    "session": "sweep_low or sweep_high",
    "liquidity_level": 49800.0,
    "mode": "TESTNET or LIVE"
  }
]
```

### Повний Приклад

```json
[
  {
    "timestamp": "2025-11-09T14:35:22.123456",
    "symbol": "BTCUSDT",
    "side": "LONG",
    "entry_price": 50000.0,
    "exit_price": 50750.0,
    "stop_loss": 49250.0,
    "take_profit": 51125.0,
    "rr_ratio": 1.5,
    "pnl": 300.0,
    "pnl_percent": 3.0,
    "win": true,
    "session": "sweep_low",
    "liquidity_level": 49800.0,
    "mode": "TESTNET"
  },
  {
    "timestamp": "2025-11-10T08:15:44.987654",
    "symbol": "BTCUSDT",
    "side": "SHORT",
    "entry_price": 51000.0,
    "exit_price": 50250.0,
    "stop_loss": 51750.0,
    "take_profit": 49875.0,
    "rr_ratio": 1.5,
    "pnl": 200.0,
    "pnl_percent": 2.94,
    "win": true,
    "session": "sweep_high",
    "liquidity_level": 51200.0,
    "mode": "TESTNET"
  },
  {
    "timestamp": "2025-11-12T16:45:10.456789",
    "symbol": "BTCUSDT",
    "side": "LONG",
    "entry_price": 49500.0,
    "exit_price": 49000.0,
    "stop_loss": 48750.0,
    "take_profit": 50625.0,
    "rr_ratio": 1.5,
    "pnl": -100.0,
    "pnl_percent": -2.02,
    "win": false,
    "session": "sweep_low",
    "liquidity_level": 49300.0,
    "mode": "TESTNET"
  }
]
```

### Поля

| Поле | Тип | Опис |
|------|-----|------|
| `timestamp` | string | Час закриття трейда (ISO 8601) |
| `symbol` | string | Торгова пара (BTCUSDT) |
| `side` | string | LONG або SHORT |
| `entry_price` | float | Ціна входу |
| `exit_price` | float | Ціна виходу |
| `stop_loss` | float | Stop Loss |
| `take_profit` | float | Take Profit |
| `rr_ratio` | float | Risk:Reward співвідношення |
| `pnl` | float | Profit/Loss в USDT |
| `pnl_percent` | float | P/L у відсотках |
| `win` | boolean | true=прибутковий, false=збитковий |
| `session` | string | sweep_low або sweep_high |
| `liquidity_level` | float | Рівень ліквідності який був пробитий |
| `mode` | string | TESTNET або LIVE |

### Переглянути

```bash
# Pretty print
cat logs/trades.json | jq '.'

# Кількість трейдів
cat logs/trades.json | jq 'length'

# Тільки прибуткові
cat logs/trades.json | jq '.[] | select(.win == true)'

# Тільки збиткові
cat logs/trades.json | jq '.[] | select(.win == false)'

# Останній трейд
cat logs/trades.json | jq '.[-1]'

# Сума PnL
cat logs/trades.json | jq '[.[].pnl] | add'

# Середній PnL
cat logs/trades.json | jq '[.[].pnl] | add / length'
```

### Імпорт в Excel/Google Sheets

1. Відкрити Excel/Sheets
2. Import → JSON
3. Вибрати `logs/trades.json`
4. Дані з'являться в таблиці

### Імпорт в Python/Pandas

```python
import pandas as pd

# Завантажити трейди
df = pd.read_json('logs/trades.json')

# Аналіз
print(f"Total trades: {len(df)}")
print(f"Win rate: {df['win'].mean() * 100:.1f}%")
print(f"Total PnL: ${df['pnl'].sum():.2f}")
print(f"Avg PnL: ${df['pnl'].mean():.2f}")

# Прибуткові vs Збиткові
wins = df[df['win'] == True]
losses = df[df['win'] == False]
print(f"Wins: {len(wins)}, Avg: ${wins['pnl'].mean():.2f}")
print(f"Losses: {len(losses)}, Avg: ${losses['pnl'].mean():.2f}")
```

---

## 📈 logs/performance.json

**Формат:** JSON Object  
**Кодування:** UTF-8  
**Оновлення:** Після кожного закритого трейда

### Структура

```json
{
  "last_updated": "ISO 8601 timestamp",
  "stats": {
    "total_trades": 0,
    "wins": 0,
    "losses": 0,
    "total_pnl": 0.0
  },
  "win_rate": 0.0,
  "mode": "TESTNET or LIVE",
  "symbol": "BTCUSDT"
}
```

### Повний Приклад

```json
{
  "last_updated": "2025-11-12T16:45:10.789012",
  "stats": {
    "total_trades": 15,
    "wins": 9,
    "losses": 6,
    "total_pnl": 1250.50
  },
  "win_rate": 60.0,
  "mode": "TESTNET",
  "symbol": "BTCUSDT"
}
```

### Поля

| Поле | Тип | Опис |
|------|-----|------|
| `last_updated` | string | Останнє оновлення |
| `stats.total_trades` | int | Загальна кількість трейдів |
| `stats.wins` | int | Прибуткові трейди |
| `stats.losses` | int | Збиткові трейди |
| `stats.total_pnl` | float | Загальний P/L в USDT |
| `win_rate` | float | Win rate у відсотках |
| `mode` | string | TESTNET або LIVE |
| `symbol` | string | Торгова пара |

### Переглянути

```bash
# Pretty print
cat logs/performance.json | jq '.'

# Тільки win rate
cat logs/performance.json | jq '.win_rate'

# Тільки total PnL
cat logs/performance.json | jq '.stats.total_pnl'
```

---

## 🔄 Як Оновлюються Файли

### Цикл Життя Даних

```
1. БОТ СТАРТУЄ
   └─> logs/liquidity_sweep_bot.log створюється
   └─> Завантажує існуючі trades.json (якщо є)

2. НОВА СВІЧКА
   └─> Записується в .log

3. СИГНАЛ ВИЯВЛЕНО
   └─> Записується в .log
   └─> Відкривається позиція

4. ПОЗИЦІЯ ВІДКРИТА
   └─> Записується в .log
   └─> Ордери виконані

5. ПОЗИЦІЯ ЗАКРИТА
   └─> Записується в .log
   └─> ДОДАЄТЬСЯ в trades.json ✅
   └─> ОНОВЛЮЄТЬСЯ performance.json ✅
   └─> Показується в консолі

6. НАСТУПНИЙ ТРЕЙД
   └─> Повтор кроків 2-5
```

### Частота Оновлення

| Файл | Коли Оновлюється |
|------|------------------|
| `.log` | В реальному часі (кожна подія) |
| `trades.json` | Після закриття кожного трейда |
| `performance.json` | Після закриття кожного трейда |

---

## 📊 Аналіз Даних

### Швидка Статистика

```bash
# Кількість трейдів
echo "Total trades:" $(cat logs/trades.json | jq 'length')

# Win rate
echo "Win rate:" $(cat logs/performance.json | jq '.win_rate')"%"

# Total PnL
echo "Total PnL: $"$(cat logs/performance.json | jq '.stats.total_pnl')

# Прибуткові трейди
echo "Wins:" $(cat logs/performance.json | jq '.stats.wins')

# Збиткові трейди
echo "Losses:" $(cat logs/performance.json | jq '.stats.losses')
```

### Python Скрипт Аналізу

```python
#!/usr/bin/env python3
import json
import pandas as pd
from datetime import datetime

# Завантажити дані
with open('logs/trades.json') as f:
    trades = json.load(f)

with open('logs/performance.json') as f:
    perf = json.load(f)

df = pd.DataFrame(trades)

print("="*60)
print("📊 TRADING PERFORMANCE ANALYSIS")
print("="*60)
print(f"\nMode: {perf['mode']}")
print(f"Symbol: {perf['symbol']}")
print(f"Last Updated: {perf['last_updated']}")

print(f"\n📈 STATISTICS:")
print(f"  Total Trades: {perf['stats']['total_trades']}")
print(f"  Wins: {perf['stats']['wins']}")
print(f"  Losses: {perf['stats']['losses']}")
print(f"  Win Rate: {perf['win_rate']:.1f}%")
print(f"  Total PnL: ${perf['stats']['total_pnl']:.2f}")

if len(df) > 0:
    wins = df[df['win'] == True]
    losses = df[df['win'] == False]
    
    print(f"\n💰 PnL BREAKDOWN:")
    print(f"  Avg Win: ${wins['pnl'].mean():.2f}")
    print(f"  Avg Loss: ${losses['pnl'].mean():.2f}")
    print(f"  Largest Win: ${wins['pnl'].max():.2f}")
    print(f"  Largest Loss: ${losses['pnl'].min():.2f}")
    
    print(f"\n📊 R:R ANALYSIS:")
    print(f"  Avg R:R: {df['rr_ratio'].mean():.2f}")
    print(f"  Min R:R: {df['rr_ratio'].min():.2f}")
    print(f"  Max R:R: {df['rr_ratio'].max():.2f}")
    
    print(f"\n🔄 SIDE BREAKDOWN:")
    longs = len(df[df['side'] == 'LONG'])
    shorts = len(df[df['side'] == 'SHORT'])
    print(f"  LONG: {longs} ({longs/len(df)*100:.1f}%)")
    print(f"  SHORT: {shorts} ({shorts/len(df)*100:.1f}%)")

print("="*60)
```

### Зберегти скрипт

```bash
# Створити аналізатор
nano analyze_trades.py
# Вставити код вище

# Зробити виконуваним
chmod +x analyze_trades.py

# Запустити
python3 analyze_trades.py
```

---

## 💾 Backup Даних

### Ручний Backup

```bash
# Створити backup папку
mkdir -p backups

# Backup з timestamp
timestamp=$(date +%Y%m%d_%H%M%S)
tar -czf backups/trading_data_$timestamp.tar.gz logs/

# Перевірити
ls -lh backups/
```

### Автоматичний Backup (Cron)

```bash
# Відкрити crontab
crontab -e

# Додати (backup щодня о 00:00)
0 0 * * * cd /opt/trading/implement && tar -czf backups/trading_data_$(date +\%Y\%m\%d).tar.gz logs/
```

### Backup в Cloud (Опційно)

```bash
# Використовуючи rclone (Dropbox/Google Drive)
rclone copy logs/ dropbox:trading_bot_logs/

# Або AWS S3
aws s3 sync logs/ s3://your-bucket/trading-bot-logs/
```

---

## 🔍 Моніторинг в Real-Time

### Watch Command

```bash
# Моніторити performance.json
watch -n 5 'cat logs/performance.json | jq "."'

# Моніторити останній трейд
watch -n 5 'cat logs/trades.json | jq ".[-1]"'
```

### Dashboard (Advanced)

Створіть простий HTML dashboard:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Trading Bot Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <h1>Trading Bot Performance</h1>
    <div id="stats"></div>
    <canvas id="chart"></canvas>
    
    <script>
        // Завантажити дані
        fetch('logs/performance.json')
            .then(r => r.json())
            .then(data => {
                document.getElementById('stats').innerHTML = `
                    <p>Win Rate: ${data.win_rate}%</p>
                    <p>Total PnL: $${data.stats.total_pnl}</p>
                    <p>Trades: ${data.stats.total_trades}</p>
                `;
            });
    </script>
</body>
</html>
```

---

## ✅ Підсумок

### Три Головні Файли

| Файл | Що Містить | Для Чого |
|------|------------|----------|
| `liquidity_sweep_bot.log` | Всі події | Debugging, моніторинг |
| `trades.json` | Історія трейдів | Аналіз, статистика |
| `performance.json` | Загальна продуктивність | Швидкий огляд |

### Де Знайти

```bash
# Локально (Mac)
/Users/illiachumak/trading/implement/logs/

# Docker (Ubuntu)
/opt/trading/implement/logs/

# Або в контейнері
docker exec liquidity-sweep-bot ls -lh logs/
```

### Як Аналізувати

1. **В реальному часі:** `tail -f logs/liquidity_sweep_bot.log`
2. **Статистика:** `cat logs/performance.json | jq '.'`
3. **Історія:** `cat logs/trades.json | jq '.'`
4. **Python/Pandas:** Завантажити і аналізувати
5. **Excel:** Імпорт JSON

---

**Все готово!** Дані автоматично зберігаються після кожного трейда. 📊

