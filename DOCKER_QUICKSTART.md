# 🚀 Docker Quick Start - 5 Хвилин

## Швидкий Deploy на Ubuntu

### 1️⃣ Завантажте на сервер
```bash
# SSH на ваш Ubuntu сервер
ssh user@your-server-ip

# Завантажте файли (git або scp)
cd /opt
# git clone <repo> або scp файли
```

### 2️⃣ Налаштуйте .env
```bash
cd trading/implement
cp env_example.txt .env
nano .env
# Додайте BINANCE_API_KEY та BINANCE_API_SECRET
```

### 3️⃣ Запустіть deploy
```bash
chmod +x deploy.sh
./deploy.sh
```

Скрипт автоматично:
- ✅ Встановить Docker (якщо потрібно)
- ✅ Збудує image
- ✅ Запустить бота

---

## ⚡ Основні Команди

```bash
# Запустити
docker-compose up -d

# Логи (live)
docker-compose logs -f

# Статус
docker-compose ps

# Зупинити
docker-compose stop

# Перезапустити
docker-compose restart

# Зупинити і видалити
docker-compose down

# Rebuild і restart
docker-compose up -d --build
```

---

## 📁 Структура

```
/opt/trading/implement/
├── Dockerfile              ✅ Docker image definition
├── docker-compose.yml      ✅ Orchestration config
├── .dockerignore          ✅ Excluded files
├── deploy.sh              ✅ Auto-deployment script
├── .env                   ⚠️  YOUR API KEYS (create this!)
├── liquidity_sweep_bot.py ✅ Main bot
├── requirements_bot.txt   ✅ Dependencies
└── logs/                  📁 Bot logs (auto-created)
```

---

## 🔍 Перевірка Роботи

```bash
# 1. Перевірити що контейнер працює
docker-compose ps
# STATUS має бути "Up"

# 2. Переглянути логи
docker-compose logs -f
# Має бути:
# ✅ Bot initialized successfully
# 🔍 Starting main loop...

# 3. Перевірити файл логів
tail -f logs/liquidity_sweep_bot.log
```

---

## ⚠️ Важливо

### Перед Production
- ✅ Тестуйте на testnet 2+ тижні
- ✅ Перевірте що .env захищено: `chmod 600 .env`
- ✅ Малий капітал спочатку

### Коли Щось Не Так
```bash
# Подивитись логи помилок
docker-compose logs | grep -i error

# Rebuild з нуля
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Перевірити .env
cat .env
```

---

## 📊 Моніторинг

```bash
# Використання ресурсів
docker stats liquidity-sweep-bot

# Детальна інформація
docker inspect liquidity-sweep-bot

# Останні 50 рядків логів
docker-compose logs --tail=50
```

---

## 🎯 Автостарт після Reboot

```bash
# Docker Compose автоматично restart контейнер
# Налаштування в docker-compose.yml:
restart: unless-stopped

# Перевірити після reboot:
sudo reboot
# Після reboot:
docker-compose ps  # Має бути "Up"
```

---

## 🆘 Troubleshooting

### Container не стартує
```bash
docker-compose logs
# Перевірте помилки

docker-compose down
docker-compose up -d --build
```

### TA-Lib помилка
```bash
docker-compose build --no-cache
```

### Cannot connect to Binance
```bash
# Перевірте інтернет
ping binance.com

# Перевірте .env
cat .env
```

---

## 📚 Детальна Документація

Дивіться: **DOCKER_DEPLOY_UBUNTU.md**

---

**Готово! Бот працює в Docker на Ubuntu** 🚀

