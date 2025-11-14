# Liquidity Sweep Reversal Backtest

Якісний бектест з підтримкою multitimeframe для стратегії **reversal after liquidity sweep**.

## 📋 Стратегія

### Концепція
Стратегія базується на ідеї, що після liquidity sweep (зачіпки ліквідності) ціна часто різко розвертається. Ми входимо в позицію на розвороті з підтвердженням через об'єм та FVG (Fair Value Gap).

### Умови входу

#### 1. Liquidity Sweep на 4H таймфреймі
- Визначаються swing high/low за останні 20 свічок
- Ціна має пробити (sweep) цей рівень на 0.1%+
- Після пробиття свічка має закритись назад за рівень (підтвердження розвороту)

#### 2. Вхід на 15M таймфреймі
Після детекції sweep на 4H, шукаємо вхід на 15M з трьома умовами:

**a) Різке повернення до рівня ліквідності:**
- Сильна свічка розвороту (тіло >60% від range)
- Закриття біля хаю (для лонгів) або лоу (для шортів)
- Мінімальний фітіль проти тренду

**b) Високий об'єм:**
- Об'єм свічки має бути >1.5x від середнього за 20 свічок
- Підтверджує інтерес великих гравців

**c) FVG (Fair Value Gap / imbalance / weak):**
- Наявність gap між свічками
- Bullish FVG для лонгів (candle[i-2].high < candle[i].low)
- Bearish FVG для шортів (candle[i-2].low > candle[i].high)

#### 3. Вихід
- **Stop Loss:** За swept рівнем (0.5% запас)
- **Take Profit:**
  - TP1: 1:2 RR (50% позиції)
  - TP2: 1:3 RR (30% позиції)
  - TP3: 1:5 RR (20% позиції)
- **Трейлінг:** SL переміщується до breakeven після TP1

---

## 🚀 Швидкий старт

### 1. Встановлення залежностей

```bash
pip install pandas numpy python-binance
```

### 2. Запуск бектесту

#### Простий запуск (автоматичне завантаження даних):
```bash
python run_liquidity_backtest.py
```

#### З параметрами:
```bash
python run_liquidity_backtest.py BTCUSDT 2023-01-01 2024-12-31
```

### 3. Результати

Результати зберігаються в папці `backtest_results/`:
- `liquidity_reversal_BTCUSDT_*.json` - детальні результати
- `liquidity_reversal_trades_BTCUSDT_*.csv` - список всіх трейдів

---

## 📊 Структура бектесту

### Основні класи

#### `LiquiditySweepDetector`
Визначає liquidity sweeps на 4H таймфреймі:
```python
detector = LiquiditySweepDetector(lookback=20, sweep_threshold=0.001)
sweep = detector.detect_liquidity_sweep(df_4h, current_idx)
```

#### `FVGDetector`
Знаходить Fair Value Gaps (imbalances):
```python
fvg = FVGDetector.detect_fvg(df_15m, idx)
# Returns: {'type': 'BULLISH', 'top': ..., 'bottom': ..., 'size': ...}
```

#### `VolumeAnalyzer`
Аналізує об'єм для підтвердження входу:
```python
is_high_vol = VolumeAnalyzer.is_high_volume(df_15m, idx, threshold=1.5)
volume_ratio = VolumeAnalyzer.calculate_volume_ratio(df_15m, idx)
```

#### `ReversalDetector`
Визначає сильні свічки розвороту:
```python
is_reversal = ReversalDetector.detect_bullish_reversal(df_15m, idx)
```

#### `LiquidityReversalBacktest`
Головний клас бектесту з multitimeframe логікою:
```python
backtest = LiquidityReversalBacktest(
    initial_balance=10000,
    risk_per_trade=0.02,
    volume_threshold=1.5
)

results = backtest.run_backtest(df_4h, df_15m)
```

---

## 🔧 Налаштування

### Основні параметри

```python
backtest = LiquidityReversalBacktest(
    initial_balance=10000,      # Початковий капітал ($)
    risk_per_trade=0.02,        # Ризик на трейд (2%)
    volume_threshold=1.5,       # Мінімальний об'єм (1.5x від середнього)
    sweep_lookback=20           # Період для визначення swing points
)
```

### Тюнінг параметрів

#### Liquidity Sweep Detection
```python
detector = LiquiditySweepDetector(
    lookback=20,              # Більше = більш значущі рівні, менше сигналів
    sweep_threshold=0.001     # 0.1% - мінімальний пробій для підтвердження
)
```

#### Reversal Detection
```python
ReversalDetector.detect_bullish_reversal(
    df, idx,
    min_body_pct=0.6         # Мінімальний розмір тіла свічки (60%)
)
```

#### Volume Analysis
```python
VolumeAnalyzer.is_high_volume(
    df, idx,
    threshold=1.5,           # 1.5x від середнього об'єму
    lookback=20              # Період для розрахунку середнього
)
```

---

## 📈 Приклад використання

### З власними даними

```python
import pandas as pd
from liquidity_reversal_backtest import LiquidityReversalBacktest

# Завантажити дані
df_4h = pd.read_csv('btcusdt_4h.csv', parse_dates=['timestamp'], index_col='timestamp')
df_15m = pd.read_csv('btcusdt_15m.csv', parse_dates=['timestamp'], index_col='timestamp')

# Дані мають містити колонки: open, high, low, close, volume

# Створити бектест
backtest = LiquidityReversalBacktest(
    initial_balance=10000,
    risk_per_trade=0.02,
    volume_threshold=1.5
)

# Запустити
results = backtest.run_backtest(df_4h, df_15m)

# Зберегти результати
backtest.save_results(results, 'my_backtest.json')
backtest.save_trades_csv('my_trades.csv')
```

### З завантаженням з Binance

```python
from run_liquidity_backtest import run_backtest_with_download

results = run_backtest_with_download(
    symbol='ETHUSDT',
    start_date='2023-01-01',
    end_date='2024-12-31',
    download_fresh=True
)
```

---

## 📊 Інтерпретація результатів

### Виведення консолі

Під час роботи бектест виводить:

```
🎯 LIQUIDITY SWEEP DETECTED!
   Time: 2023-06-15 08:00:00
   Type: LOW
   Level: $25,234.50

📈 TRADE OPENED!
   Time: 2023-06-15 09:45:00
   Direction: LONG
   Entry: $25,250.00
   Stop Loss: $25,115.00
   TP1: $25,520.00 (1:2)
   TP2: $25,655.00 (1:3)
   TP3: $25,925.00 (1:5)
   Size: 0.1481 BTC
   Volume Ratio: 1.87x
   FVG: BULLISH, Size: $45.20

✅ TP1 HIT!
   Time: 2023-06-15 11:15:00
   Price: $25,520.00
   Partial PnL: $199.85

...
```

### Фінальна статистика

```
📊 BACKTEST RESULTS
================================================================================

💰 Financial Results:
   Initial Balance: $10,000.00
   Final Balance: $12,845.30
   Total PnL: +$2,845.30
   Total Return: +28.45%

📈 Trade Statistics:
   Total Trades: 34
   Winning Trades: 22
   Losing Trades: 12
   Win Rate: 64.71%

💵 Performance Metrics:
   Average Win: $189.45
   Average Loss: -$85.23
   Profit Factor: 2.22
   Max Drawdown: 8.34%
```

### Metrics пояснення

- **Win Rate:** Відсоток прибуткових трейдів
- **Profit Factor:** Відношення загального прибутку до загального збитку (>1.5 добре)
- **Max Drawdown:** Максимальне падіння балансу від піку (чим менше, тим краще)
- **Avg Win/Loss:** Середній профіт/збиток на трейд

---

## 🎯 Оптимізація

### Що тестувати

1. **Volume Threshold:** 1.2x, 1.5x, 2.0x
2. **Sweep Lookback:** 15, 20, 25, 30 свічок
3. **Risk per Trade:** 1%, 2%, 3%
4. **TP Ratios:** Різні комбінації RR

### Приклад grid search

```python
# Test різні volume thresholds
results_grid = []

for vol_thresh in [1.2, 1.5, 2.0]:
    for sweep_back in [15, 20, 25]:
        backtest = LiquidityReversalBacktest(
            initial_balance=10000,
            risk_per_trade=0.02,
            volume_threshold=vol_thresh,
            sweep_lookback=sweep_back
        )

        results = backtest.run_backtest(df_4h, df_15m)

        results_grid.append({
            'vol_threshold': vol_thresh,
            'sweep_lookback': sweep_back,
            'total_return': results['total_return'],
            'win_rate': results['win_rate'],
            'profit_factor': results['profit_factor'],
            'max_drawdown': results['max_drawdown']
        })

# Проаналізувати найкращі параметри
df_results = pd.DataFrame(results_grid)
df_results.sort_values('total_return', ascending=False, inplace=True)
print(df_results.head(10))
```

---

## 🔍 Troubleshooting

### Помилка: "smartmoneyconcepts not available"
Бектест НЕ використовує smartmoneyconcepts - це просто warning. Всі індикатори реалізовані вручну.

### Помилка: "Empty DataFrame"
Переконайтесь що дані містять колонки: `open`, `high`, `low`, `close`, `volume` і індекс `timestamp`.

### Мало сигналів
- Зменшіть `volume_threshold` (наприклад, з 1.5 до 1.3)
- Збільште `sweep_lookback` для більш частих sweep детекцій
- Перевірте чи є достатньо історичних даних (мінімум 3-6 місяців)

### Багато false signals
- Збільште `volume_threshold` для більш строгого фільтру
- Додайте додаткові умови в `check_entry_conditions`

---

## 📝 Формат даних

Дані мають бути у форматі:

```
timestamp (index)   open      high      low       close     volume
2023-01-01 00:00   16547.23  16589.45  16523.12  16567.89  1245.67
2023-01-01 00:15   16567.89  16601.34  16555.78  16588.23  987.45
...
```

### Завантаження з Binance вручну

```python
from binance.client import Client
import pandas as pd

client = Client()  # Public API, no keys needed

klines = client.get_klines(
    symbol='BTCUSDT',
    interval='15m',
    startTime='1 Jan, 2023',
    endTime='31 Dec, 2023'
)

df = pd.DataFrame(klines, columns=[
    'timestamp', 'open', 'high', 'low', 'close', 'volume',
    'close_time', 'quote_volume', 'trades', 'taker_buy_base',
    'taker_buy_quote', 'ignore'
])

df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
df.set_index('timestamp', inplace=True)
df = df[['open', 'high', 'low', 'close', 'volume']].astype(float)

df.to_csv('btcusdt_15m.csv')
```

---

## 🤝 Contribution

Якщо знайдете баги або маєте ідеї для покращення:
1. Протестуйте зміни на historical data
2. Задокументуйте результати
3. Створіть pull request

---

## ⚠️ Disclaimer

Цей бектест призначений для **освітніх та дослідницьких цілей**.

- Минулі результати не гарантують майбутніх
- Завжди тестуйте на paper trading перед live
- Використовуйте розумний ризик-менеджмент
- Ніколи не ризикуйте більше ніж можете втратити

---

## 📚 Додаткові ресурси

### Liquidity Concepts
- [Smart Money Concepts](https://www.investopedia.com/terms/s/smart-money.asp)
- [Order Flow & Liquidity](https://www.tradingview.com/ideas/orderflow/)

### Fair Value Gaps
- [What is FVG](https://www.tradingview.com/script/Yc7Cjp7u-Fair-Value-Gaps-FVG/)
- [Imbalance Trading](https://www.youtube.com/results?search_query=fair+value+gap+trading)

### Risk Management
- [Position Sizing](https://www.investopedia.com/articles/trading/09/determine-position-size.asp)
- [Money Management](https://www.babypips.com/learn/forex/money-management)

---

**Успішного трейдингу! 🚀📈**
