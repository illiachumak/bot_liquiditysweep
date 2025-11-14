# Paper Trading Bot

## Опис

Paper Trading Bot для стратегії Liquidity Reversal. Бот моніторить Binance в реальному часі, виявляє сигнали та логує їх у JSON файл **БЕЗ ВИКОНАННЯ РЕАЛЬНИХ ТРЕЙДІВ**.

## Стратегія

1. **Детекція на 4H**: Liquidity sweep (свіп high/low рівнів)
2. **Підтвердження на 15M**:
   - Різкий reversal candle
   - Високий volume (>1.2x середнього)
   - Fair Value Gap (FVG) - опціонально
3. **Entry**: Limit order на рівні ліквідності
4. **Exit**:
   - Stop Loss: 0.5% за swept level
   - TP1: 1:2 RR (50% позиції)
   - TP2: 1:3 RR (30% позиції)
   - TP3: 1:5 RR (20% позиції)

## Встановлення та Запуск

### Варіант 1: Docker (Рекомендовано)

#### Швидкий запуск:

```bash
cd paper_trading_bot
./deploy.sh
```

Скрипт `deploy.sh` автоматично:
- Перевірить наявність Docker
- Зібере Docker image
- Запустить контейнер
- Покаже логи

#### Ручний Docker запуск:

```bash
# Збірка image
docker-compose build

# Запуск бота
docker-compose up -d

# Перегляд логів
docker-compose logs -f

# Зупинка бота
docker-compose down
```

#### Команди управління:

```bash
./start_bot.sh    # Запустити бота
./stop_bot.sh     # Зупинити бота
./restart_bot.sh  # Перезапустити бота
```

#### Перегляд логів:

```bash
# Реальний час
docker-compose logs -f

# Останні 100 рядків
docker-compose logs --tail=100

# З певного часу
docker-compose logs --since 1h
```

### Варіант 2: Прямий запуск (без Docker)

#### Встановіть залежності:

```bash
pip install -r requirements.txt
```

#### Запустіть бота:

```bash
python paper_trading_bot.py
```

## Налаштування

Параметри бота в `paper_trading_bot.py` (рядок 415):

```python
bot = PaperTradingBot(
    symbol='BTCUSDT',           # Торгова пара
    initial_balance=10000,      # Віртуальний баланс (USDT)
    risk_per_trade=0.02,        # 2% ризику на трейд
    volume_threshold=1.2,       # 1.2x середній volume
    sweep_lookback=20,          # Lookback для sweep detection
    volume_lookback=25,         # Lookback для volume
    min_stop_loss_pct=0.003,    # Мін. стоп лос 0.3%
    max_position_size=10.0,     # Макс. 10 BTC
    check_interval=60           # Перевірка кожні 60 сек
)
```

## Трекінг Трейдів

Бот автоматично відстежує **fills** та **exits**:

### Статуси ордерів:

1. **PENDING** - Limit ордер розміщено, чекаємо fill
2. **FILLED** - Ордер виконано, позиція відкрита
3. **CLOSED** - Позиція закрита (SL або всі TP хіт)
4. **CANCELLED** - Ордер скасовано (не filled за 24 години)

### Що відстежується:

✅ **Entry Fill** - Чи ціна досягла limit order
✅ **Stop Loss** - Автоматичний exit при хіті SL
✅ **Take Profits** - Відстеження TP1, TP2, TP3
✅ **PnL Calculation** - Розрахунок прибутку/збитку
✅ **Balance Updates** - Оновлення балансу після кожного трейда

### Приклад виводу:

```
📈 ENTRY SIGNAL DETECTED!
   Direction: LONG
   Entry Price: $96,500.50
   Status: PENDING (waiting for fill)

✅ ORDER FILLED!
   Fill Price: $96,500.50
   Status: FILLED

🎯 TP1 HIT!
   Price: $97,301.00

🎉 ALL TPS HIT!
   Entry: $96,500.50
   Exit: $98,502.50
   PnL: +$265.15 (+2.07%)
   Status: CLOSED
```

## Формат логів

Всі трейди логуються в `paper_trading_logs/signals_*.json` з повною інформацією про fills та exits:

```json
{
  "signal_time": "2025-11-14T10:30:00",
  "entry_time": "2025-11-14 10:15:00",
  "direction": "LONG",
  "entry_price": 96500.50,
  "stop_loss": 96100.00,
  "tp1": 97301.00,
  "tp2": 97701.50,
  "tp3": 98502.50,
  "size": 0.1325,
  "risk_usd": 200.00,
  "volume_ratio": 1.45,
  "sweep_type": "LOW",
  "status": "CLOSED",
  "fill_price": 96500.50,
  "fill_time": "2025-11-14 10:30:00",
  "exit_price": 98502.50,
  "exit_time": "2025-11-14 12:45:00",
  "exit_reason": "ALL_TPS",
  "tp1_hit": true,
  "tp2_hit": true,
  "tp3_hit": true,
  "pnl": 265.15,
  "pnl_pct": 2.07
}
```

### Нові поля в JSON:

- **status** - Статус ордера (PENDING/FILLED/CLOSED/CANCELLED)
- **fill_price** - Ціна виконання entry ордера
- **fill_time** - Час виконання ордера
- **exit_price** - Ціна закриття позиції
- **exit_time** - Час закриття позиції
- **exit_reason** - Причина закриття (STOP_LOSS/ALL_TPS/CANCELLED)
- **tp1_hit, tp2_hit, tp3_hit** - Які TP були досягнуті
- **pnl** - Прибуток/збиток в USD
- **pnl_pct** - Прибуток/збиток у %

## Моніторинг

### Docker logs:

```bash
# Перевірка статусу контейнера
docker-compose ps

# Перегляд ресурсів
docker stats paper-trading-bot

# Перевірка health check
docker inspect paper-trading-bot | grep -A 10 Health
```

### Консольний вивід:

```
[2025-11-14 10:30:15] Checking for signals...
   Current Price: $96,500.50
   4H Candles: 500, Latest: 2025-11-14 08:00:00
   15M Candles: 500, Latest: 2025-11-14 10:15:00
   Active Sweeps: 1
   Pending Orders: 0
   Active Trades: 0
   Closed Trades: 2
   Balance: $10,450.00

🎯 LIQUIDITY SWEEP DETECTED!
   Time: 2025-11-14 08:00:00
   Type: LOW
   Level: $96,150.00

📈 ENTRY SIGNAL DETECTED!
   Direction: LONG
   Entry Price: $96,500.50
   Stop Loss: $96,100.00
   TP1: $97,301.00 (1:2 RR)
   TP2: $97,701.50 (1:3 RR)
   TP3: $98,502.50 (1:5 RR)
   Size: 0.1325 BTC
   Status: PENDING (waiting for fill)

✅ ORDER FILLED!
   Direction: LONG
   Fill Price: $96,500.50
   Status: FILLED

🎯 TP1 HIT!
   Price: $97,301.00

🎉 ALL TPS HIT!
   Entry: $96,500.50
   Exit: $98,502.50
   PnL: +$265.15 (+2.07%)
   New Balance: $10,265.15
   Status: CLOSED
```

## Docker Configuration

### Resource Limits:

```yaml
resources:
  limits:
    cpus: '0.5'      # Макс 0.5 CPU
    memory: 256M     # Макс 256MB RAM
```

### Volumes:

- `./paper_trading_logs:/app/paper_trading_logs` - Логи сигналів

### Health Check:

Контейнер автоматично перезапускається при збоях.

## Важливо!

- ✅ Бот НЕ виконує реальні трейди (paper trading)
- ✅ Відстежує fills та exits автоматично
- ✅ Розраховує PnL для кожного трейда
- ✅ Оновлює віртуальний баланс
- ✅ Використовує публічний Binance API (ключі не потрібні)
- ✅ Всі трейди логуються в JSON з повною історією
- ✅ Працює 24/7 в Docker контейнері
- ⚠️  Pending orders скасовуються через 24 години якщо не filled
- ⚠️  Binance має ліміти запитів (1200 req/min)

## Структура файлів

```
paper_trading_bot/
├── Dockerfile                      # Docker образ
├── docker-compose.yml              # Docker Compose конфігурація
├── requirements.txt                # Python залежності
├── .dockerignore                   # Виключення для Docker
├── paper_trading_bot.py            # Головний бот
├── liquidity_reversal_backtest.py  # Компоненти стратегії
├── README.md                       # Ця інструкція
├── deploy.sh                       # Скрипт деплою
├── start_bot.sh                    # Запуск бота
├── stop_bot.sh                     # Зупинка бота
├── restart_bot.sh                  # Перезапуск бота
└── paper_trading_logs/             # Логи сигналів (створюється автоматично)
```

## Troubleshooting

### Docker не знайдено

```bash
# macOS
brew install docker docker-compose

# Ubuntu
sudo apt-get install docker.io docker-compose
```

### Контейнер не стартує

```bash
# Перевірте логи
docker-compose logs

# Перезапустіть з нуля
docker-compose down
docker-compose up --build
```

### BinanceAPIException

Перевірте інтернет з'єднання або спробуйте збільшити `check_interval`.

## Наступні кроки

1. Запустіть бота: `./deploy.sh`
2. Моніторте сигнали: `docker-compose logs -f`
3. Аналізуйте результати: `paper_trading_logs/signals_*.json`
4. Налаштуйте параметри за потреби
5. Після успішного paper trading → переходьте до real trading

## Контакти

Для питань та пропозицій створіть issue в репозиторії.
