# 🎯 Failed 4H FVG Strategy Bot

Торгова стратегія базована на failed (rejected) Fair Value Gaps на 4-годинному таймфреймі з точним входом на 15-хвилинному.

## 📊 Результати Бектестів (2024)

### Оптимальна Конфігурація: ✅

| Parameter | Value |
|-----------|-------|
| **Min SL** | 0.3% |
| **RR** | Fixed 1.5 |
| **Expiry** | 4H (16 candles) |
| **Fees** | Enabled (0.18% maker, 0.45% taker) |

### Performance:
- **Trades:** 317
- **Win Rate:** 68.77%
- **Return:** +628.98%
- **Profit Factor:** 3.78
- **Max Drawdown:** 9.28%

## 🔍 Expiry Comparison

| Expiry | Trades | Win Rate | Return | Profit Factor | Max DD |
|--------|--------|----------|--------|---------------|--------|
| **4H** ✅ | 317 | 68.77% | +628.98% | 3.78 | 9.28% |
| 8H | 278 | 65.11% | +356.27% | 3.41 | 15.51% |
| 12H | 288 | 68.06% | +371.55% | 3.24 | 9.88% |

**Висновок:** Коротший expiry (4H) = кращі результати!

## 📖 Логіка Стратегії

### 1. Виявлення 4H FVG
```
Bullish FVG: Low[i] > High[i-2]
Bearish FVG: High[i] < Low[i-2]
```

### 2. Rejection
- Ціна заходить в 4H FVG зону
- Ціна закривається ЗА МЕЖАМИ зони = rejection
- **Bullish FVG rejected → SHORT setup**
- **Bearish FVG rejected → LONG setup**

### 3. Entry Trigger
- Після rejection шукаємо 15M FVG в напрямку rejection
- **Entry:** Limit order на границі 15M FVG
- **Fill window:** 4H (16 свічок 15M)

### 4. Risk Management
- **SL:** За highs/lows що сформувались ВСЕРЕДИНІ 4H FVG зони
- **TP:** Fixed RR 1.5 (risk × 1.5)
- **Min SL:** 0.3% (фільтр занадто тайтових стопів)

### 5. Fees
- **Entry/TP:** 0.18% (limit orders)
- **SL:** 0.45% (market order)

## 🎲 Fill Statistics

З створених setups тільки ~2% заповнюються (ціна повертається до entry):
- **Total setups:** 16,869
- **Filled:** 317 (1.9%)
- **Not filled:** 16,552 (98.1%)

**Чому низький fill rate?**
- Limit order чекає pullback до 15M FVG boundary
- Якщо strong momentum → ордер не fill
- Але ті що fill → дуже прибуткові (PF 3.78, WR 68%)

## 📁 Файли

### Backtesting
- `backtest_failed_fvg.py` - Backtesting engine
- `backtest_failed_fvg_2024_4h_expiry.json` - Результати бектесту
- `EXPIRY_ANALYSIS.md` - Аналіз expiry window

### Live Trading
- `failed_fvg_live_bot.py` - **Live trading bot з Binance API**
- `LIVE_TRADING_SPEC.md` - **Детальна технічна специфікація**
- `TESTING_GUIDE.md` - **Гайд по тестуванню**
- `test_mock_order.py` - Тест на mock orders
- `.env.example` - Template для API keys
- `.gitignore` - Не коммітити секрети

### Documentation
- `FAILED_FVG_STRATEGY.md` - Детальна документація стратегії

## 🚀 Запуск

### 1. Backtest
```bash
python3 backtest_failed_fvg.py
```

### 2. Live Bot - ТЕСТУВАННЯ (обов'язково спочатку!)

#### Setup:
```bash
# 1. Встановити залежності
pip install python-binance pandas numpy python-dotenv

# 2. Отримати Testnet API keys
# Перейти на https://testnet.binance.vision/
# Згенерувати HMAC_SHA256 ключі

# 3. Налаштувати .env
cp .env.example .env
nano .env  # Додати testnet keys
```

#### Тестування Mock Order:
```bash
# Цей тест створить ордер далеко від ціни (не заповниться)
python3 test_mock_order.py
```

Очікуваний результат:
```
✅ Order placed successfully
✅ Order remained PENDING (not filled)
✅ Order cancelled successfully
```

#### Запуск бота (Testnet):
```bash
# DRY_RUN=true використовує testnet (фейкові гроші)
python3 failed_fvg_live_bot.py
```

### 3. Live Bot - PRODUCTION (тільки після ретельного тестування!)

⚠️ **ПОПЕРЕДЖЕННЯ:** Це реальні гроші! Тільки після повного тестування!

```bash
# 1. Отримати REAL Binance API keys
# 2. Оновити .env з реальними ключами
# 3. Встановити DRY_RUN=false в .env
# 4. Запустити
python3 failed_fvg_live_bot.py
```

**Детальні інструкції:** Дивись `TESTING_GUIDE.md`

## ⚙️ Параметри

```python
initial_balance = 10000
risk_per_trade = 0.02  # 2%
min_sl_pct = 0.3  # 0.3%
use_fixed_rr = True
fixed_rr = 1.5
enable_fees = True
limit_order_expiry_candles = 16  # 4H
```

## 💡 Ключові Інсайти

1. **Короткий expiry краще** - 4H оптимально
2. **Fixed RR 1.5 > Liquidity TP** - більш консистентний
3. **Min SL 0.3% критичний** - фільтрує noise
4. **Fill rate 2%** - нормально, якість > кількість
5. **Fees impact ~40%** - але стратегія прибуткова

## 📈 Подальші Покращення

- [ ] Multiple timeframe confirmation
- [ ] Session filter (London/NY)
- [ ] Volume confirmation
- [ ] Trailing stop після 1R
- [ ] Partial exits (50% @ 1R, 50% @ 1.5R)
