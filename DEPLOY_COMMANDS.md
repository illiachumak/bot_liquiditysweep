# 🚀 Команди для Deploy на Ubuntu

Копіюйте і вставляйте послідовно.

---

## 📦 Варіант 1: Автоматичний Deploy (Рекомендовано)

### На вашому Ubuntu сервері:

```bash
# 1. Перейти в папку (або створити)
cd /opt
mkdir -p trading
cd trading

# 2. Завантажити файли (один з варіантів):

# Варіант А: Git
git clone YOUR_REPO_URL
cd implement

# Варіант Б: З локального Mac через SCP
# (запустіть це на Mac, не на сервері)
# scp -r /Users/illiachumak/trading/implement user@server-ip:/opt/trading/

# 3. Створити .env файл
cp env_example.txt .env
nano .env
# Вставте ваші Binance API ключі
# BINANCE_API_KEY=ваш_ключ
# BINANCE_API_SECRET=ваш_секрет
# BINANCE_TESTNET=True
# Зберегти: Ctrl+O, Enter, Ctrl+X

# 4. Запустити автоматичний deploy
chmod +x deploy.sh
./deploy.sh

# 5. Вибрати опцію 1 (start in background)
```

**Готово!** Бот працює.

---

## ⚙️ Варіант 2: Ручний Deploy

Якщо хочете зробити все вручну:

```bash
# 1. Встановити Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# ВАЖЛИВО: Вийти і зайти знову для застосування прав
exit
# SSH знову
ssh user@server-ip

# 2. Встановити Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
docker-compose --version

# 3. Перейти в папку з ботом
cd /opt/trading/implement

# 4. Створити .env
cp env_example.txt .env
nano .env
# Додати API ключі

# 5. Створити папки
mkdir -p logs
mkdir -p trades_history

# 6. Build image
docker-compose build

# 7. Запустити бота
docker-compose up -d

# 8. Перевірити що працює
docker-compose ps
docker-compose logs -f
```

---

## 📊 Команди Управління

### Перевірка Статусу

```bash
# Статус контейнера
docker-compose ps

# Live логи
docker-compose logs -f

# Останні 50 рядків
docker-compose logs --tail=50

# Використання ресурсів
docker stats liquidity-sweep-bot
```

### Керування Ботом

```bash
# Запустити
docker-compose up -d

# Зупинити
docker-compose stop

# Перезапустити
docker-compose restart

# Зупинити і видалити
docker-compose down

# Rebuild і restart
docker-compose up -d --build
```

### Перегляд Логів

```bash
# Live логи Docker
docker-compose logs -f

# Логи з файлу
tail -f logs/liquidity_sweep_bot.log

# Останні 100 рядків
tail -n 100 logs/liquidity_sweep_bot.log

# Шукати помилки
grep -i error logs/liquidity_sweep_bot.log
```

---

## 🔧 Troubleshooting Команди

### Якщо бот не запускається

```bash
# 1. Перевірити логи
docker-compose logs

# 2. Перевірити .env
cat .env

# 3. Rebuild з нуля
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# 4. Перевірити статус
docker-compose ps
```

### Якщо помилка TA-Lib

```bash
# Rebuild без кешу
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Якщо помилка API

```bash
# Перевірити інтернет
ping binance.com

# Перевірити .env
cat .env | grep BINANCE

# Перевірити що API ключі правильні
```

### Перевірка Docker

```bash
# Docker version
docker --version

# Docker Compose version
docker-compose --version

# Список всіх контейнерів
docker ps -a

# Використання диску
docker system df

# Очистити все (ОБЕРЕЖНО!)
docker system prune -a
```

---

## 📁 Завантаження Файлів на Сервер

### З Mac на Ubuntu (SCP)

```bash
# На вашому Mac (не на сервері!)
cd /Users/illiachumak/trading

# Завантажити всю папку
scp -r implement user@your-server-ip:/opt/trading/

# Або тільки потрібні файли
scp implement/liquidity_sweep_bot.py user@server-ip:/opt/trading/implement/
scp implement/Dockerfile user@server-ip:/opt/trading/implement/
scp implement/docker-compose.yml user@server-ip:/opt/trading/implement/
scp implement/requirements_bot.txt user@server-ip:/opt/trading/implement/
```

### З Mac на Ubuntu (rsync)

```bash
# На вашому Mac
rsync -avz --progress implement/ user@server-ip:/opt/trading/implement/
```

### Через Git

```bash
# На сервері
cd /opt
git clone https://github.com/your-username/your-repo.git trading
cd trading/implement
```

---

## 🔐 Безпека

### Захист .env

```bash
# Обмежити доступ до .env
chmod 600 .env

# Перевірити
ls -l .env
# Має бути: -rw------- (тільки власник)
```

### Налаштування Firewall

```bash
# Встановити UFW
sudo apt install ufw

# Дозволити SSH
sudo ufw allow ssh

# Увімкнути
sudo ufw enable

# Перевірити
sudo ufw status
```

---

## 📊 Моніторинг

### Системні Ресурси

```bash
# CPU і RAM
htop

# Або
top

# Disk space
df -h

# Docker stats
docker stats
```

### Автоматичний Restart

```bash
# Перевірити налаштування restart
docker inspect liquidity-sweep-bot | grep -i restart

# Має бути: "RestartPolicy": {"Name": "unless-stopped"}

# Тест: перезавантажити сервер
sudo reboot

# Після перезавантаження:
docker-compose ps
# Контейнер має автоматично запуститись
```

---

## 🎯 Перевірка Роботи

### Після Deploy

```bash
# 1. Контейнер працює?
docker-compose ps
# STATUS = Up

# 2. Логи виглядають нормально?
docker-compose logs --tail=50
# Має бути:
# ✅ Bot initialized successfully
# 🔍 Starting main loop...

# 3. Файл логів створено?
ls -lh logs/
cat logs/liquidity_sweep_bot.log

# 4. Ресурси в нормі?
docker stats liquidity-sweep-bot
# CPU < 50%, Memory < 300MB
```

### Тестування на Testnet

```bash
# Перевірити що BINANCE_TESTNET=True
cat .env | grep TESTNET

# Має бути: BINANCE_TESTNET=True

# Переглянути логи для підтвердження
docker-compose logs | grep -i testnet
```

---

## 🔄 Оновлення Бота

### Через Git

```bash
# Зупинити бота
docker-compose down

# Оновити код
git pull origin main

# Rebuild і restart
docker-compose up -d --build

# Перевірити
docker-compose logs -f
```

### Ручне Оновлення

```bash
# На Mac: завантажити новий файл
scp liquidity_sweep_bot.py user@server:/opt/trading/implement/

# На сервері: restart
docker-compose down
docker-compose up -d --build
```

---

## 📈 Production Checklist

Перед запуском на real money:

```bash
# 1. Протестовано на testnet 2+ тижні?
cat .env | grep TESTNET
# Має бути True для testnet

# 2. .env захищено?
ls -l .env
# Має бути -rw-------

# 3. Контейнер працює стабільно?
docker-compose ps
uptime
# Перевірити uptime контейнера

# 4. Логи без помилок?
docker-compose logs | grep -i error
# Не має бути critical errors

# 5. Автоматичний restart працює?
sudo systemctl status docker
# Має бути active

# 6. Готові до live?
nano .env
# Змінити: BINANCE_TESTNET=False
# ⚠️ ТІЛЬКИ після успішного testnet!

# 7. Restart для live
docker-compose down
docker-compose up -d

# 8. Підтвердити live mode
docker-compose logs | head -20
# Має бути: Mode: [LIVE]
```

---

## 🆘 Швидка Допомога

### Бот не стартує
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
docker-compose logs -f
```

### Помилка підключення
```bash
ping binance.com
cat .env
docker-compose restart
```

### Високе використання ресурсів
```bash
docker stats
docker-compose restart
```

### Видалити все і почати з початку
```bash
docker-compose down -v
docker system prune -a
docker-compose build --no-cache
docker-compose up -d
```

---

## 📞 Корисні Посилання

- Binance Testnet: https://testnet.binancefuture.com
- Docker Docs: https://docs.docker.com
- Ubuntu Guide: https://ubuntu.com/server/docs

---

**Готово!** Копіюйте команди і вставляйте в термінал Ubuntu. 🚀

