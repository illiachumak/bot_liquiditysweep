# 🤖 Trading Bots - Implementation

Автоматизовані боти для торгівлі на Binance Futures.

---

## 🤖 Available Bots

### 1. 🏆 SMC Optimized Bot (15m) - **BEST!** ⭐⭐⭐

Smart Money Concepts з multiple limit levels і partial exits.

| Метрика | Значення |
|---------|----------|
| Місячна прибутковість | **6.81%** 🏆 |
| Річна прибутковість | **140-160%** 🏆 |
| Win Rate | 46.34% |
| Max Drawdown | **-2.00%** 🏆 **(Найкращий!)** |
| Total Return (22mo) | +320.85% |
| Частота трейдів | ~2/місяць |

**Чому найкращий?** Найвищий return з найнижчим drawdown!  
**Location:** `smc_optimized_bot/`  
**Status:** ✅ Verified (100% match з backtest)

---

### 2. 🚀 Breakout Bot (15m)

High/Low breakout на 15m з NY session filter.

| Метрика | Значення |
|---------|----------|
| Місячна прибутковість (net) | 3-4% |
| Річна прибутковість | 40-50%+ |
| Win Rate | 39-40% |
| Max Drawdown | -30-35% |
| Sharpe Ratio | 1.04 |
| Частота трейдів | ~10/місяць |

**Location:** `breakout_15m_bot/`

---

### 3. 🌙 Liquidity Sweep Bot (4h)

Торгівля на основі session liquidity sweeps з reversals.

| Метрика | Значення |
|---------|----------|
| Місячна прибутковість | 2.71% |
| Річна прибутковість | 32.5% |
| Win Rate | 59.09% |
| Max Drawdown | -10.67% |
| Sharpe Ratio | 1.16 |
| Частота трейдів | ~2/місяць |

**Location:** `liquidity_sweep_bot.py`

---

## 🚀 Швидкий Старт

### Bot 1: SMC Optimized Bot (15m) 🏆 **(RECOMMENDED)**

**Option A: Docker (1-Command Deploy)** 🐳 **(EASIEST)**
```bash
cd smc_optimized_bot
./deploy.sh
# Все автоматично: Docker + Bot + Trade Logging!
```

**Option B: Manual**
```bash
# 1. Перейти до директорії
cd smc_optimized_bot

# 2. Встановити залежності
pip install -r requirements.txt

# 3. Налаштувати API ключі
cp env_example.txt .env
nano .env  # додати API ключі

# 4. Запустити симуляцію (перевірка - ОБОВ'ЯЗКОВО!)
python3 bot_simulator.py

# 5. Запустити бота (testnet)
python3 smc_optimized_bot.py
```

**Документація:** `smc_optimized_bot/README.md`  
**Docker Guide:** `smc_optimized_bot/DOCKER_DEPLOYMENT.md`  
**Симуляція:** `smc_optimized_bot/SIMULATION_REPORT.md`  
**Trade Logging:** ✅ Automatic JSON & CSV (`trades_history/`)

---

### Bot 2: Breakout Bot (15m) 🚀

```bash
# 1. Перейти до директорії
cd breakout_15m_bot

# 2. Встановити залежності
pip install -r requirements.txt

# 3. Налаштувати API ключі
export BINANCE_API_KEY="your_key"
export BINANCE_API_SECRET="your_secret"

# 4. Запустити симуляцію (перевірка)
python3 bot_simulator.py

# 5. Запустити бота (testnet)
python3 breakout_bot.py
```

**Документація:** `breakout_15m_bot/README.md`

---

### Bot 3: Liquidity Sweep Bot (4h) 🌙

```bash
# 1. Встановити залежності
pip install -r requirements_bot.txt
brew install ta-lib  # macOS

# 2. Налаштувати .env
cp env_example.txt .env
nano .env  # додати API ключі

# 3. Запустити
python liquidity_sweep_bot.py
```

**Документація:** `README.md` (цей файл), `IMPLEMENTATION_SUMMARY.md`

---

### Варіант 2: Docker на Ubuntu (Рекомендовано)

```bash
# На Ubuntu сервері
./deploy.sh
```

**Детально:** `DOCKER_QUICKSTART.md`

---

## 📁 Структура Файлів

### 🏆 Bot 1: SMC Optimized Bot (15m) - BEST!
| Файл | Опис |
|------|------|
| `smc_optimized_bot/smc_optimized_bot.py` | Головний бот |
| `smc_optimized_bot/bot_simulator.py` | Симулятор (100% match!) |
| `smc_optimized_bot/SIMULATION_REPORT.md` | Детальний звіт симуляції |
| `smc_optimized_bot/QUICK_SUMMARY.txt` | Швидке резюме |
| `smc_optimized_bot/README.md` | Документація |
| `smc_optimized_bot/requirements.txt` | Python залежності |
| `smc_optimized_bot/env_example.txt` | Шаблон .env |

### 🚀 Bot 2: Breakout Bot (15m)
| Файл | Опис |
|------|------|
| `breakout_15m_bot/breakout_bot.py` | Головний бот |
| `breakout_15m_bot/bot_simulator.py` | Симулятор для перевірки |
| `breakout_15m_bot/requirements.txt` | Python залежності |
| `breakout_15m_bot/README.md` | Повна документація |
| `breakout_15m_bot/SIMULATION_REPORT.md` | Детальний звіт симуляції |
| `breakout_15m_bot/QUICK_SUMMARY.txt` | Швидкий огляд |

### 🐳 Docker Files
| Файл | Опис |
|------|------|
| `Dockerfile` | Docker image definition |
| `docker-compose.yml` | Docker orchestration |
| `.dockerignore` | Excluded files |
| `deploy.sh` | Автоматичний deployment |

### 📚 Документація
| Файл | Опис |
|------|------|
| `README.md` | Цей файл |
| `ІНСТРУКЦІЯ.md` | Швидкий старт (українською) ⭐ |
| `README_BOT.md` | Повна документація (англійською) |
| `LIQUIDITY_SWEEP_BOT_SPEC.md` | Технічна специфікація |
| `IMPLEMENTATION_SUMMARY.md` | Підсумок імплементації |
| `DOCKER_DEPLOY_UBUNTU.md` | Docker deployment guide |
| `DOCKER_QUICKSTART.md` | Docker quick start |

### 🗑️ Legacy (можна ігнорувати)
| Файл | Опис |
|------|------|
| `bot.py` | Старий бот (інша стратегія) |
| `nice_funcs.py` | Старі helper функції |

---

## 🆚 Bot Comparison

| Характеристика | SMC Optimized 🏆 | Breakout 🚀 | Liquidity Sweep 🌙 |
|----------------|------------------|-------------|-------------------|
| **Timeframe** | 15m | 15m | 4h |
| **Monthly Return** | **6.81%** 🏆 | 3-4% | 2.71% |
| **Win Rate** | 46% | 40% | 59% |
| **Trades/Month** | ~2 | ~10 | ~2 |
| **Max DD** | **-2.00%** 🏆 | -30-35% | -10.67% |
| **Sharpe** | **~3-4** 🏆 | 1.04 | 1.16 |
| **Features** | 3 limits, partial exits | High/Low breakout | Session sweeps |
| **Trading Hours** | 24/7 (optional NY) | NY session | Any |
| **Monitoring** | 15m (use bot!) | 15m (use bot!) | 4h check |
| **Psychology** | Balanced | Harder (low WR) | Easy (high WR) |
| **Best For** | **Best overall!** ⭐ | Aggressive | Conservative |

### 💡 Which One to Choose?

**SMC Optimized (15m)** 🏆 **(RECOMMENDED)** if you want:
- ✅ **Best risk/reward** (6.81% monthly, -2% DD)
- ✅ **Lowest drawdown** (easiest psychology!)
- ✅ High-quality trades (~2/month)
- ✅ Advanced features (multiple limits, partial exits)
- ✅ **Proven** (100% match with backtest)

**Breakout (15m)** 🚀 if you want:
- ✅ Higher returns (3-4%/mo)
- ✅ More trades (10/month)
- ✅ Accept higher DD (-30-35%)
- ✅ Simple strategy

**Liquidity Sweep (4h)** 🌙 if you want:
- ✅ Higher win rate (59%)
- ✅ Less monitoring (4h candles)
- ✅ Original proven strategy
- ✅ Passive trading

**All Three?** Diversification!
- 50% SMC + 25% Breakout + 25% Liq Sweep
- Expected: ~5-6%/month, -10-15% DD
- Best balance! 🚀

---

## 🎯 Способи Запуску

### 1. Локально (Для Тестування)

**Переваги:**
- ✅ Швидко налаштувати
- ✅ Легко дебажити
- ✅ Бачити логи в терміналі

**Мінуси:**
- ❌ Треба тримати комп'ютер увімкнутим
- ❌ Немає автоматичного restart

**Запуск:**
```bash
python liquidity_sweep_bot.py
```

**Документація:** `ІНСТРУКЦІЯ.md`

---

### 2. Docker на Ubuntu (Production)

**Переваги:**
- ✅ Працює 24/7 на сервері
- ✅ Автоматичний restart
- ✅ Ізольоване середовище
- ✅ Легко оновлювати

**Мінуси:**
- ❌ Потрібен Ubuntu сервер
- ❌ Треба знати Docker

**Запуск:**
```bash
./deploy.sh
```

**Документація:** `DOCKER_QUICKSTART.md` → `DOCKER_DEPLOY_UBUNTU.md`

---

## 📖 Яку Документацію Читати?

### Для Швидкого Старту
👉 **`ІНСТРУКЦІЯ.md`** - Українською, 5 хвилин

### Для Локального Запуску
👉 **`README_BOT.md`** - Детальна документація

### Для Docker Deployment
👉 **`DOCKER_QUICKSTART.md`** - Швидкий старт  
👉 **`DOCKER_DEPLOY_UBUNTU.md`** - Повна інструкція

### Для Розуміння Стратегії
👉 **`LIQUIDITY_SWEEP_BOT_SPEC.md`** - Технічна специфікація  
👉 **`../backtest/optimized_strategies/LIQUIDITY_SWEEP_FINAL_REPORT.md`** - Результати бектесту

---

## ⚙️ Конфігурація

### API Ключі (.env)

```bash
# Створіть .env файл:
cp env_example.txt .env

# Додайте ваші ключі:
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
BINANCE_TESTNET=True  # або False для live
```

### Параметри Бота

В `liquidity_sweep_bot.py` (рядки 23-47):

```python
# Trading
SYMBOL = 'BTCUSDT'
RISK_PER_TRADE = 2.0  # 2% risk

# Strategy (оптимізовані 2022-2025)
SWING_LOOKBACK = 5
SWEEP_TOLERANCE = 0.001  # 0.1%
MIN_RR = 1.5
ATR_STOP_MULTIPLIER = 1.5

# Bot
TIMEFRAME = '4h'
CHECK_INTERVAL = 60  # seconds
```

---

## 🧪 Тестування

### Перед Запуском

```bash
# Перевірити налаштування
python test_bot.py

# Має бути:
# ✅ PASS - Imports
# ✅ PASS - Environment
# ✅ PASS - Binance Connection
# ✅ PASS - Strategy Logic
```

### Testnet (Рекомендовано)

1. Створіть акаунт: https://testnet.binancefuture.com
2. Отримайте API ключі
3. Встановіть `BINANCE_TESTNET=True` в .env
4. Запустіть бота
5. Тестуйте 2-4 тижні

---

## 📊 Моніторинг

### Логи

**Консоль:**
```bash
# Локально
python liquidity_sweep_bot.py

# Docker
docker-compose logs -f
```

**Файл:**
```bash
# Локально
tail -f logs/liquidity_sweep_bot.log

# Docker
tail -f ./logs/liquidity_sweep_bot.log
```

### Статистика

Бот автоматично логує:
- ✅ Нові свічки
- ✅ Сигнали на вхід
- ✅ Виконані ордери
- ✅ Закриття позицій
- ✅ Win rate і PnL

---

## 🔧 Основні Команди

### Локально

```bash
# Запустити
python liquidity_sweep_bot.py

# Або через скрипт
./start_bot.sh

# Зупинити
Ctrl+C
```

### Docker

```bash
# Запустити
docker-compose up -d

# Логи
docker-compose logs -f

# Статус
docker-compose ps

# Перезапустити
docker-compose restart

# Зупинити
docker-compose down

# Rebuild
docker-compose up -d --build
```

---

## ⚠️ Важливо

### Низька Частота Трейдів
- ~2 трейди на місяць - це **нормально**
- Можуть бути тижні без трейдів
- **НЕ змінюйте параметри**
- Стратегія про якість, не кількість

### Ризик-Менеджмент
- 2% ризику на трейд (автоматично)
- Тільки 1 позиція одночасно
- Завжди використовуються SL/TP
- Не втручайтесь в трейди вручну

### Реалістичні Очікування
- 2.71% місячних (не 5%+)
- 59% win rate (відмінно)
- -10.67% max DD (низький)
- Для більшого - комбінуйте з іншими стратегіями

---

## 🆘 Проблеми?

### "TA-Lib not found"
```bash
# macOS
brew install ta-lib
pip install TA-Lib

# Ubuntu
sudo apt-get install ta-lib
pip install TA-Lib

# Docker
docker-compose build --no-cache
```

### "Invalid API key"
- Перевірте .env файл
- Переконайтесь що Futures API увімкнено
- Для testnet використовуйте ключі з testnet.binancefuture.com

### "Insufficient balance"
- Testnet: отримайте кошти через faucet
- Live: поповніть Futures wallet

### Бот не знаходить сигналів
- Це нормально! ~2 трейди/місяць
- Дочекайтесь більше свічок
- Перевірте що session levels відслідковуються

---

## 📈 Очікувані Результати

### Короткостроково (1 місяць)
- 1-3 трейди
- ~2-3% прибуток
- Можливі тижні без трейдів

### Середньостроково (1 рік)
- ~23 трейди
- ~32.5% прибуток
- Win rate ~55-65%
- Max DD ~10-15%

### Довгостроково (3-5 років)
- Стабільне зростання
- Compound effect
- 3-5x збільшення капіталу

---

## 🎓 Рекомендації

### ✅ РОБІТЬ
- Починайте з testnet
- Тестуйте 2-4 тижні
- Малий капітал спочатку
- Ведіть журнал трейдів
- Будьте терплячі
- Моніторте щотижня

### ❌ НЕ РОБІТЬ
- Не змінюйте параметри
- Не втручайтесь в трейди
- Не очікуйте швидкого збагачення
- Не ризикуйте >2% на трейд
- Не запускайте на live без testnet

---

## 📚 Корисні Посилання

### Binance
- Testnet: https://testnet.binancefuture.com
- API Docs: https://binance-docs.github.io/apidocs/futures/en/

### Документація
- Python Binance: https://python-binance.readthedocs.io/
- TA-Lib: https://github.com/mrjbq7/ta-lib
- Docker: https://docs.docker.com/

---

## 🏗️ Архітектура Бота

```
LiquiditySweepBot (Main)
    │
    ├── BinanceManager
    │   ├── REST API integration
    │   ├── Order execution
    │   └── Position management
    │
    ├── LiquiditySweepStrategy
    │   ├── Session tracking
    │   ├── Liquidity sweep detection
    │   ├── Reversal pattern recognition
    │   └── Signal generation
    │
    ├── RiskManager
    │   ├── Position sizing (2% risk)
    │   └── Validation
    │
    └── Logging
        ├── File logs
        └── Console output
```

---

## 🎯 Статус

| Компонент | Статус |
|-----------|--------|
| Код бота | ✅ Complete |
| Документація | ✅ Complete |
| Docker setup | ✅ Complete |
| Тестування | ⚠️ Потрібно протестувати |
| Production ready | ⚠️ Після testnet |

---

## 📞 Підтримка

### Документи
- Технічні питання → `LIQUIDITY_SWEEP_BOT_SPEC.md`
- Deployment → `DOCKER_DEPLOY_UBUNTU.md`
- Швидкий старт → `ІНСТРУКЦІЯ.md`
- Backtest результати → `../backtest/optimized_strategies/LIQUIDITY_SWEEP_FINAL_REPORT.md`

### Логи
```bash
# Локально
tail -f logs/liquidity_sweep_bot.log

# Docker
docker-compose logs -f
```

---

## ✅ Готовність

- [x] Бот створено
- [x] Стратегія імплементована
- [x] Ризик-менеджмент (2%)
- [x] Docker containerization
- [x] Документація
- [ ] Testnet тестування (потрібно зробити)
- [ ] Production deployment (після testnet)

---

**Status:** ✅ **Ready for Testing**

**Next Step:** Прочитайте `ІНСТРУКЦІЯ.md` або `DOCKER_QUICKSTART.md` і запустіть бота!

---

**Built with ❤️ for disciplined trading**

**Disclaimer:** Trading carries risk. Use at your own risk. Test thoroughly before live trading.

