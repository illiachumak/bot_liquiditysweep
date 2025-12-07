# HELD FVG Live Trading Bot

**⚠️ WARNING: This bot trades with REAL MONEY on Binance Futures!**

Live trading bot for the HELD 4H FVG strategy (4h_close + rr_3.0_liq).

## 🎯 Strategy

- **Entry:** Immediate market order when 4H FVG is held
- **TP:** Liquidity zones (2.5-5.0 RR)
- **SL:** Below/above FVG zone with 0.2% buffer
- **Risk:** 2% per trade
- **Leverage:** 5x
- **Max Positions:** 1 concurrent

## 📊 Expected Performance (from backtest 2023-2025)

- Win Rate: ~70%
- Profit Factor: ~5.66
- Trades: ~34 per year
- Max Drawdown: ~9%
- ROI: ~+878% per year

**Note:** Live results will be ~5-15% worse due to slippage and execution delays.

## 🚀 Quick Start

### 1. Get Binance API Keys

1. Go to https://www.binance.com/en/my/settings/api-management
2. Create new API key
3. Enable "Futures" permission
4. **Important:** Set IP whitelist for security
5. Save API Key and Secret

### 2. Setup Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your API keys
nano .env
```

**.env file:**
```bash
BINANCE_API_KEY=your_actual_key_here
BINANCE_API_SECRET=your_actual_secret_here
```

### 3. Run with Docker

```bash
# Build and start
docker-compose -f docker-compose.live.yml up -d

# View logs
docker logs -f held-fvg-bot-live

# Stop bot
docker-compose -f docker-compose.live.yml down
```

## 📋 Logging

Bot logs only important events:

```
INFO  - Bot started
INFO  - 4H candle closed at 2025-12-08 16:00:00
INFO  - New FVG detected: BULLISH at $95000-$96000
INFO  - FVG HELD: BULLISH at $95500
INFO  - OPENING TRADE: LONG entry=$95500 sl=$94800 tp=$100000
INFO  - Trade opened successfully!
ERROR - Failed to execute trade: <error details>
```

### View logs:

```bash
# Real-time logs
docker logs -f held-fvg-bot-live

# Last 100 lines
docker logs --tail 100 held-fvg-bot-live

# Today's logs
docker logs --since $(date +%Y-%m-%d) held-fvg-bot-live
```

## 🔧 Configuration

Edit `config.py` to adjust settings:

**Trading:**
- `SYMBOL` - Trading pair (default: BTCUSDT)
- `LEVERAGE` - Leverage (default: 5x)
- `RISK_PER_TRADE` - Risk per trade (default: 2%)
- `MIN_SL_PCT` / `MAX_SL_PCT` - SL limits (0.3% - 5.0%)

**Liquidity:**
- `LIQUIDITY_MIN_RR` - Min R:R (default: 2.5)
- `LIQUIDITY_MAX_RR` - Max R:R (default: 5.0)
- `LIQUIDITY_LOOKBACK` - Candles to scan (default: 50)

**Safety:**
- `MAX_POSITION_SIZE_USDT` - Max position (default: $1000)
- `MAX_CONCURRENT_POSITIONS` - Max open positions (default: 1)
- `MAX_TRADES_PER_DAY` - Daily limit (default: 5)

**After changing config:**
```bash
docker-compose -f docker-compose.live.yml restart
```

## 🛡️ Safety Features

### Automatic Risk Management

- ✅ SL and TP orders attached immediately on entry
- ✅ Position size calculated from balance
- ✅ Maximum position size enforced
- ✅ Daily trade limit prevents spam

### Error Handling

- API errors → logged, bot continues
- Connection lost → automatic reconnection
- Invalid setup → trade skipped

### Graceful Shutdown

```bash
# Stop bot (waits for current operation)
docker-compose -f docker-compose.live.yml stop

# Force stop
docker-compose -f docker-compose.live.yml kill
```

**Note:** Open positions remain active after shutdown. Manual intervention required to close them.

## 📊 Monitoring

### Check Current Position

```bash
# View bot logs
docker logs held-fvg-bot-live | grep "Trade opened"
```

### Check on Binance

1. Go to https://www.binance.com/en/futures/BTCUSDT
2. Check "Positions" tab
3. Check "Open Orders" for SL/TP

### Balance Check

Bot logs current balance on startup:
```
INFO - Current balance: $1234.56 USDT
```

## ⚠️ Important Notes

### Before Starting

1. **Test API Keys:** Verify futures permission is enabled
2. **Check Balance:** Ensure sufficient USDT in Futures wallet
3. **Understand Risk:** 2% risk means possible 2% loss per trade
4. **Monitor Daily:** Check logs at least once per day

### During Operation

1. **Don't Interfere:** Let bot manage positions automatically
2. **Don't Close SL/TP Orders:** They protect your position
3. **Don't Open Manual Trades:** Bot expects max 1 position
4. **Watch for Errors:** Check logs if no trades for 7+ days

### Emergency Stop

If you need to stop immediately:

```bash
# 1. Stop bot
docker-compose -f docker-compose.live.yml down

# 2. Manually close position on Binance
# Go to Futures → Positions → Close

# 3. Cancel all orders
# Go to Futures → Open Orders → Cancel All
```

## 🐛 Troubleshooting

### Bot not starting

```bash
# Check logs
docker logs held-fvg-bot-live

# Common issues:
# - Invalid API keys → check .env file
# - No futures permission → enable in Binance
# - Insufficient balance → deposit USDT
```

### No trades executing

Possible reasons:
- No FVGs forming (wait for setup)
- No holds detected (normal, ~74% filtered)
- No liquidity in 2.5-5.0 RR range (skip)
- Max daily trades reached (resets at midnight UTC)
- Already have open position (wait for close)

### Orders failing

```bash
# Check logs for error
docker logs held-fvg-bot-live | grep ERROR

# Common issues:
# - Insufficient balance
# - Position size too small (< $10)
# - API rate limit (wait 1 minute)
```

## 📁 Files

- **live_bot.py** - Main bot code
- **config.py** - Configuration
- **.env** - API credentials (create from .env.example)
- **Dockerfile** - Docker image definition
- **docker-compose.live.yml** - Docker Compose config
- **requirements.txt** - Python dependencies

## 🔐 Security Checklist

- [ ] API keys stored in .env (not in code)
- [ ] .env file in .gitignore (never commit)
- [ ] IP whitelist enabled on Binance
- [ ] Futures permission only (no spot/withdrawal)
- [ ] Position size limit configured
- [ ] Daily trade limit configured
- [ ] Logs monitored regularly

## 📞 Support

If you encounter issues:

1. Check logs: `docker logs held-fvg-bot-live`
2. Check Binance API status: https://www.binance.com/en/support/announcement
3. Verify API keys and permissions
4. Check bot balance: sufficient USDT?

## ⚖️ Disclaimer

**Use at your own risk!**

- This bot trades with real money
- Past performance ≠ future results
- Cryptocurrency trading is highly risky
- You can lose all your capital
- Always start with small amounts
- Monitor the bot regularly

**The authors are not responsible for any losses incurred using this software.**

---

**Version:** 1.0
**Last Updated:** 2025-12-08
**Strategy:** 4h_close + rr_3.0_liq (verified, no lookahead bias)
