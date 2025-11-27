# Як переглянути реджекшени в логах лайв бота

## ⚡ Швидкий старт (Docker)

Якщо бот запущений через Docker, використовуйте ці команди:

```bash
# 1. Перевірте чи контейнер запущений
docker ps | grep 4hfvg-bot

# 2. Останні 50 реджекшенів
docker exec 4hfvg-bot grep "🚫 REJECTION" /app/logs/live_bot.log | tail -50

# 3. Моніторинг в реальному часі
docker exec 4hfvg-bot tail -f /app/logs/live_bot.log | grep --line-buffered "🚫 REJECTION"

# 4. Підрахунок реджекшенів
docker exec 4hfvg-bot grep -c "🚫 REJECTION" /app/logs/live_bot.log
```

**Або якщо volume працює, перейдіть в директорію з docker-compose.yml:**
```bash
cd ~/bot/4HFVG_BOT  # або ваш шлях
grep "🚫 REJECTION" logs/live_bot.log | tail -50
```

---

## 📍 Розташування логів

### 🐳 Docker (рекомендовано)

Якщо бот запущений через Docker, логи монтуються з контейнера на хост.

**Контейнер:** `4hfvg-bot`  
**Шлях в контейнері:** `/app/logs/live_bot.log`  
**Шлях на хості:** `./logs/live_bot.log` (в директорії де знаходиться docker-compose.yml)

#### Спосіб 1: Через docker exec (всередині контейнера)
```bash
# Перевірте чи контейнер запущений
docker ps | grep 4hfvg-bot

# Виконайте команду всередині контейнера
docker exec 4hfvg-bot grep "🚫 REJECTION" /app/logs/live_bot.log | tail -50
```

#### Спосіб 2: Безпосередньо на хості (якщо volume працює)
```bash
# Перейдіть в директорію з docker-compose.yml
cd ~/bot/4HFVG_BOT  # або ваш шлях

# Перевірте чи є логи
ls -la logs/live_bot.log

# Використовуйте звичайні команди
grep "🚫 REJECTION" logs/live_bot.log | tail -50
```

#### Спосіб 3: Копіювання з контейнера
```bash
# Скопіювати лог файл з контейнера
docker cp 4hfvg-bot:/app/logs/live_bot.log ./live_bot.log

# Потім використовуйте звичайні команди
grep "🚫 REJECTION" ./live_bot.log | tail -50
```

### 💻 Локально (без Docker):
Логи зберігаються в: `4HFVG_BOT/logs/live_bot.log`

### 🖥️ На сервері (без Docker):
Спочатку знайдіть правильний шлях:
```bash
# Варіант 1: Якщо ви в директорії бота
find . -name "live_bot.log" 2>/dev/null

# Варіант 2: Пошук з кореня
find /root -name "live_bot.log" 2>/dev/null

# Варіант 3: Перевірте поточну директорію
pwd
ls -la logs/ 2>/dev/null || ls -la */logs/ 2>/dev/null
```

## 🔍 Команди для пошуку реджекшенів

### 🐳 Docker команди (найпростіші)

#### 1. Всі реджекшени (останні 50) - через docker exec
```bash
docker exec 4hfvg-bot grep "🚫 REJECTION" /app/logs/live_bot.log | tail -50
```

#### 2. Всі реджекшени (останні 50) - на хості (якщо volume працює)
```bash
# Перейдіть в директорію з docker-compose.yml
cd ~/bot/4HFVG_BOT  # або ваш шлях
grep "🚫 REJECTION" logs/live_bot.log | tail -50
```

#### 3. Моніторинг в реальному часі - через docker exec
```bash
docker exec 4hfvg-bot tail -f /app/logs/live_bot.log | grep --line-buffered "🚫 REJECTION"
```

#### 4. Моніторинг в реальному часі - на хості
```bash
tail -f logs/live_bot.log | grep --line-buffered "🚫 REJECTION"
```

#### 5. Підрахунок реджекшенів
```bash
# Через docker exec
docker exec 4hfvg-bot grep -c "🚫 REJECTION" /app/logs/live_bot.log

# На хості
grep -c "🚫 REJECTION" logs/live_bot.log
```

### 💻 Локально / На сервері (без Docker)

> **⚠️ ВАЖЛИВО:** Замініть шлях на правильний до вашого лог файлу!

#### 1. Всі реджекшени (останні 50)
```bash
# Локально
grep "🚫 REJECTION" 4HFVG_BOT/logs/live_bot.log | tail -50

# На сервері (якщо ви в директорії бота)
grep "🚫 REJECTION" logs/live_bot.log | tail -50

# На сервері (з повним шляхом)
grep "🚫 REJECTION" ~/bot/4HFVG_BOT/logs/live_bot.log | tail -50
```

### 2. Всі реджекшени з контекстом (рядок до і після)
```bash
# Локально
grep -A 2 -B 1 "🚫 REJECTION" 4HFVG_BOT/logs/live_bot.log | tail -100

# На сервері (замініть на правильний шлях)
grep -A 2 -B 1 "🚫 REJECTION" logs/live_bot.log | tail -100
```

### 3. Тільки SHORT реджекшени (Bullish FVG → SHORT)
```bash
# Замініть на правильний шлях
grep "🚫 REJECTION.*SHORT setup" logs/live_bot.log
```

### 4. Тільки LONG реджекшени (Bearish FVG → LONG)
```bash
# Замініть на правильний шлях
grep "🚫 REJECTION.*LONG setup" logs/live_bot.log
```

### 5. Реджекшени за конкретну дату
```bash
# Замініть на правильний шлях та дату
grep "2025-11-21.*🚫 REJECTION" logs/live_bot.log
```

### 6. Реджекшени з детальною інформацією (з наступними рядками)
```bash
grep -A 3 "🚫 REJECTION" 4HFVG_BOT/logs/live_bot.log | tail -100
```

### 7. Підрахунок реджекшенів
```bash
grep -c "🚫 REJECTION" 4HFVG_BOT/logs/live_bot.log
```

### 8. Останні 20 реджекшенів з часом
```bash
grep "🚫 REJECTION" 4HFVG_BOT/logs/live_bot.log | tail -20
```

### 9. Реджекшени з конкретним FVG (наприклад, ціна $91567)
```bash
grep "🚫 REJECTION.*91567" 4HFVG_BOT/logs/live_bot.log
```

### 10. Реджекшени + що сталося далі (setup creation)
```bash
grep -A 5 "🚫 REJECTION" 4HFVG_BOT/logs/live_bot.log | grep -E "(REJECTION|Setup created|Looking for setups)" | tail -50
```

## 📊 Формат логу реджекшену

```
2025-11-19 15:12:00,181 | INFO | 🚫 REJECTION! Bullish FVG $91567.00-$92532.00 → SHORT setup
   Rejected @ $91450.25 (closed below bottom $91567.00)
   Time: 2025-11-18 22:15:00
   Expected: SHORT trade with 15M BEARISH FVG
   Total rejected FVGs: 3
```

## 🔎 Швидкий пошук в реальному часі

### 🐳 Docker

#### Відстеження нових реджекшенів
```bash
docker exec 4hfvg-bot tail -f /app/logs/live_bot.log | grep --line-buffered "🚫 REJECTION"
```

#### Відстеження реджекшенів + setup creation
```bash
docker exec 4hfvg-bot tail -f /app/logs/live_bot.log | grep --line-buffered -E "(🚫 REJECTION|📋 Setup created|Looking for setups)"
```

### 💻 Локально / На сервері

#### Відстеження нових реджекшенів
```bash
tail -f logs/live_bot.log | grep --line-buffered "🚫 REJECTION"
```

#### Відстеження реджекшенів + setup creation
```bash
tail -f logs/live_bot.log | grep --line-buffered -E "(🚫 REJECTION|📋 Setup created|Looking for setups)"
```

## 📈 Статистика реджекшенів

### Підрахунок по типах
```bash
# SHORT реджекшени
grep -c "SHORT setup" 4HFVG_BOT/logs/live_bot.log

# LONG реджекшени
grep -c "LONG setup" 4HFVG_BOT/logs/live_bot.log
```

### Реджекшени за датами
```bash
grep "🚫 REJECTION" 4HFVG_BOT/logs/live_bot.log | cut -d' ' -f1 | sort | uniq -c
```

## 💡 Корисні комбінації

### Останні реджекшени + що з ними сталося
```bash
grep -A 10 "🚫 REJECTION" 4HFVG_BOT/logs/live_bot.log | tail -50
```

### Реджекшени які призвели до setup creation
```bash
grep -B 1 -A 8 "📋 Setup created" 4HFVG_BOT/logs/live_bot.log | grep -B 1 "🚫 REJECTION"
```

### Реджекшени які НЕ призвели до setup (тільки rejection, без setup)
```bash
# Складніше - потрібно аналізувати лог вручну
grep -A 15 "🚫 REJECTION" 4HFVG_BOT/logs/live_bot.log | grep -v "Setup created" | head -100
```

## 🎯 Найкорисніші команди (швидкий доступ)

### 🐳 Docker (рекомендовано)

```bash
# 1. Останні 30 реджекшенів
docker exec 4hfvg-bot grep "🚫 REJECTION" /app/logs/live_bot.log | tail -30

# 2. Всі реджекшени сьогодні
docker exec 4hfvg-bot grep "$(date +%Y-%m-%d).*🚫 REJECTION" /app/logs/live_bot.log

# 3. Моніторинг в реальному часі
docker exec 4hfvg-bot tail -f /app/logs/live_bot.log | grep --line-buffered "🚫 REJECTION"

# 4. Реджекшени з деталями (3 рядки після)
docker exec 4hfvg-bot grep -A 3 "🚫 REJECTION" /app/logs/live_bot.log | tail -40
```

### 💻 Локально / На сервері (без Docker)

```bash
# 1. Останні 30 реджекшенів
grep "🚫 REJECTION" logs/live_bot.log | tail -30

# 2. Всі реджекшени сьогодні
grep "$(date +%Y-%m-%d).*🚫 REJECTION" logs/live_bot.log

# 3. Моніторинг в реальному часі
tail -f logs/live_bot.log | grep --line-buffered "🚫 REJECTION"
```

## 📝 Приклад виводу

```
2025-11-19 15:12:00,181 | INFO | 🚫 REJECTION! Bearish FVG $43771.10-$43812.50 → LONG setup
2025-11-19 15:12:00,181 | INFO | 🚫 REJECTION! Bearish FVG $43716.00-$44940.93 → LONG setup
2025-11-19 15:12:00,184 | INFO | 🚫 REJECTION! Bullish FVG $44184.10-$45121.96 → SHORT setup
2025-11-19 15:12:00,185 | INFO | 🚫 REJECTION! Bullish FVG $43550.00-$44148.34 → SHORT setup
```

