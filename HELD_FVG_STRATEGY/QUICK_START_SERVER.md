# 🚀 Швидкий старт на сервері (LIVE режим)

## 0️⃣ Стягни останні зміни (якщо треба)

```bash
cd /path/to/trading/implement
git pull
```

## 1️⃣ Скопіюй .env

```bash
cd HELD_FVG_STRATEGY
cp ../4HFVG_BOT/.env .env
```

## 2️⃣ Перевір .env

```bash
cat .env
```

Має бути:
```
SIMULATION_MODE=False  ← ОБОВ'ЯЗКОВО!
BINANCE_API_KEY=твій_ключ
BINANCE_API_SECRET=твій_секрет
```

## 3️⃣ Запусти бота

```bash
docker compose -f docker-compose.live.yml up -d
```

## 4️⃣ Дивись логи

```bash
docker compose -f docker-compose.live.yml logs -f
```

## ✅ Перевірка

Має показати:
```
🎯 MODE: LIVE TRADING
✅ Bot initialized in LIVE mode
```

Якщо бачиш "SIMULATION" - СТОП! Виправ .env

---

## 🛑 Зупинка

```bash
docker compose -f docker-compose.live.yml down
```

---

## 🔧 Якщо щось пішло не так

### Помилка: "no attribute 'candle_history_4h'"

Застосуй hotfix:
```bash
git pull
./hotfix.sh
```

### Інші помилки

Подивись логи:
```bash
docker compose -f docker-compose.live.yml logs
```

---

**Це все!** Бот готовий до live trading 🚀
