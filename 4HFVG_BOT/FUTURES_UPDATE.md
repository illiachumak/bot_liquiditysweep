# ✅ FUTURES API - Оновлення

## Зміни

Бот оновлено для роботи з **Binance Futures API**.

### Що змінено:

1. ✅ **Баланс захардкоджено**: $300 USDT
2. ✅ **Futures API**: Використовується futures замість spot
3. ✅ **Ордера**: Адаптовано під futures
4. ✅ **TP/SL**: Замість OCO використовуються окремі TAKE_PROFIT_MARKET та STOP_MARKET ордера

---

## Детальні зміни

### 1. Баланс
```python
# Було: Фетчив з spot аккаунта
balance = self.client.get_asset_balance(asset='USDT')

# Стало: Захардкоджено
return 300.0  # Futures account balance
```

### 2. API Methods

| Операція | Spot API | Futures API |
|----------|----------|-------------|
| Klines | `get_klines()` | `futures_klines()` |
| Price | `get_symbol_ticker()` | `futures_symbol_ticker()` |
| Symbol Info | `get_symbol_info()` | `futures_exchange_info()` |
| Create Order | `create_order()` | `futures_create_order()` |
| Cancel Order | `cancel_order()` | `futures_cancel_order()` |
| Get Order | `get_order()` | `futures_get_order()` |

### 3. OCO Orders → TP/SL Orders

**Spot** використовує OCO (One-Cancels-Other):
```python
create_oco_order(
    price=tp_price,           # TP
    stopLimitPrice=sl_price   # SL
)
```

**Futures** використовує окремі ордера:
```python
# TP order
futures_create_order(type='TAKE_PROFIT_MARKET', stopPrice=tp)

# SL order
futures_create_order(type='STOP_MARKET', stopPrice=sl)
```

---

## Конфігурація

### В коді (`failed_fvg_live_bot.py`):

```python
# Line ~28
USE_FUTURES = True  # Set to True for futures trading
```

**Для перемикання між Spot/Futures:**
- `USE_FUTURES = True` - Futures (поточна конфігурація)
- `USE_FUTURES = False` - Spot

### Баланс:

```python
# Line ~398
def get_balance(self, asset: str = 'USDT') -> float:
    logger.info("Using hardcoded balance: $300.00 (Futures account)")
    return 300.0
```

Для зміни балансу відредагуйте `300.0` на потрібну суму.

---

## Тестування

### Перевірка що використовується Futures:

Після запуску в логах ви побачите:
```
📊 Using FUTURES API
Using hardcoded balance: $300.00 (Futures account)
```

### Перевірка ордерів:

При розміщенні TP/SL ви побачите:
```
✅ Futures TP/SL orders placed: SELL 0.003, TP=$95000.00, SL=$93000.00
```

---

## Важливо

### Binance Testnet для Futures

⚠️ **Futures Testnet відрізняється від Spot Testnet!**

**Futures Testnet:**
- URL: https://testnet.binancefuture.com/
- API Keys: https://testnet.binancefuture.com/en/futures/BTCUSDT

**НЕ плутати з:**
- Spot Testnet: https://testnet.binance.vision/

### API Permissions

Для Futures потрібні дозволи:
- ✅ Enable Futures
- ✅ Enable Reading
- ⚠️ Enable Spot & Margin Trading (якщо потрібен fallback на spot)

### Обмеження Futures

1. **Немає OCO ордерів** - використовуються окремі TP/SL
2. **Leverage** - за замовчуванням 1x (можна налаштувати)
3. **Margin mode** - ISOLATED або CROSS
4. **Position mode** - One-way або Hedge

---

## Перезапуск

Після змін виконайте:

```bash
cd 4HFVG_BOT
./REBUILD.sh
```

Або вручную:
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
docker-compose logs -f
```

---

## Troubleshooting

### Помилка: "Invalid symbol"
- Перевірте що символ існує на Futures (BTCUSDT)
- Перевірте що використовується правильний testnet URL

### Помилка: "Insufficient balance"
- Додайте тестові монети на Futures testnet аккаунт
- Або змініте захардкоджений баланс в коді

### Помилка: "Order would immediately trigger"
- TP/SL ціни занадто близько до поточної
- Збільште MIN_SL_PCT або перевірте FIXED_RR

### Помилка: "APIError(code=-4131): Invalid quantity"
- Перевірте lot_size_filter для futures
- Futures мають інші вимоги до quantity ніж spot

---

## Наступні кроки

1. ✅ Протестуйте на Futures Testnet
2. ✅ Переконайтесь що баланс $300 достатній
3. ✅ Перевірте розміщення ордерів
4. ✅ Перевірте що TP/SL працюють
5. ⚠️ Налаштуйте leverage якщо потрібно

---

## Додаткові налаштування (опційно)

### Leverage

Для налаштування кредитного плеча додайте в `BinanceClientWrapper.__init__()`:

```python
if USE_FUTURES:
    # Set leverage to 5x
    self.client.futures_change_leverage(symbol=SYMBOL, leverage=5)
```

### Margin Mode

```python
if USE_FUTURES:
    # Set ISOLATED margin
    self.client.futures_change_margin_type(symbol=SYMBOL, marginType='ISOLATED')
```

---

## Changelog

- **2024-11-15**: Додано підтримку Futures API
- **2024-11-15**: Захардкоджено баланс $300
- **2024-11-15**: Замінено OCO на окремі TP/SL ордера
- **2024-11-15**: Додано перемикач USE_FUTURES

---

Готово! Бот тепер працює з Futures API 🚀
