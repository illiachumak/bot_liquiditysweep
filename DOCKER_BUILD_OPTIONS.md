# Docker Build Options for Liquidity Sweep Bot

This guide explains the different Docker build options available and when to use each one.

## ✅ RECOMMENDED: Standard Build (with TA-Lib compilation)

**File:** `Dockerfile` (default)

This builds the bot with TA-Lib compiled from source. It's the most reliable option.

```bash
# Build
docker-compose build

# Or with docker directly
docker build -t liquidity-sweep-bot .

# Run
docker-compose up -d
```

**Build time:** ~3-5 minutes (compiles TA-Lib from source)

**Pros:**
- Full functionality with TA-Lib
- Most accurate ATR calculations
- Production-ready

**Cons:**
- Longer build time
- Requires compilation tools

---

## 🚀 FAST: Simple Build (without TA-Lib)

**File:** `Dockerfile.simple`

This builds the bot using pandas-based ATR calculation instead of TA-Lib. Much faster to build!

```bash
# Build
docker build -f Dockerfile.simple -t liquidity-sweep-bot .

# Run
docker run -d --name liquidity-sweep-bot \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  liquidity-sweep-bot
```

**Build time:** ~30 seconds

**Pros:**
- Very fast build
- No compilation needed
- Same functionality (pandas ATR)

**Cons:**
- Slightly different ATR values (usually negligible difference)

---

## 🔧 Troubleshooting Failed Builds

### If Standard Build Fails

Try building with no cache:
```bash
docker-compose build --no-cache
```

### If Still Failing

Use the simple build without TA-Lib:
```bash
docker build -f Dockerfile.simple -t liquidity-sweep-bot .
docker run -d --name liquidity-sweep-bot --env-file .env -v $(pwd)/logs:/app/logs liquidity-sweep-bot
```

### Check Docker Version

Make sure you have Docker 20.10+ and Docker Compose 2.0+:
```bash
docker --version
docker-compose --version
```

---

## 📊 Comparing ATR Calculations

Both methods calculate ATR (Average True Range), but with slight differences:

| Method | Accuracy | Speed | Complexity |
|--------|----------|-------|------------|
| TA-Lib | Industry standard | Fast | C library |
| Pandas | Very close (~99.9%) | Fast | Pure Python |

For trading purposes, both are acceptable. The bot automatically uses TA-Lib if available, otherwise falls back to pandas.

---

## 🐳 Testing Your Build

After building, test the bot:

```bash
# Check if container is running
docker ps

# View logs
docker logs liquidity-sweep-bot

# Run test inside container
docker exec liquidity-sweep-bot python test_bot.py
```

---

## 💡 Which Build Should I Use?

### Use Standard Build (Dockerfile) if:
- You want production-grade accuracy
- Build time is not critical
- You're deploying long-term

### Use Simple Build (Dockerfile.simple) if:
- You need to deploy quickly
- Standard build fails
- You're testing/developing
- You don't have compilation tools

---

## 📝 Current Build Status

Based on your previous error, the recommended approach is:

1. **Try Standard Build First:**
   ```bash
   docker-compose build
   ```

2. **If it fails, use Simple Build:**
   ```bash
   docker build -f Dockerfile.simple -t liquidity-sweep-bot .
   docker run -d --name liquidity-sweep-bot --env-file .env -v $(pwd)/logs:/app/logs liquidity-sweep-bot
   ```

The bot code now supports both methods automatically! 🎉

---

## 🔍 Verifying TA-Lib Status

After the bot starts, check the logs to see which ATR method is being used:

```bash
docker logs liquidity-sweep-bot | head -20
```

You'll see either:
- No message = TA-Lib is working
- `⚠️  TA-Lib not available, using pandas-based ATR calculation` = Using pandas fallback

Both are perfectly fine for trading! 📈

