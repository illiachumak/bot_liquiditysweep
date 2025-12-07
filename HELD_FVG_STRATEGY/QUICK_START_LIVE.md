# Quick Start Guide - HELD FVG Live Bot

## ⚡ 5-Minute Setup

### Step 1: Get API Keys (2 min)

1. Go to https://www.binance.com/en/my/settings/api-management
2. Create new API key
3. ✅ Enable "Futures" permission
4. ✅ Set IP whitelist (your server IP)
5. Copy Key & Secret

### Step 2: Configure Bot (1 min)

```bash
# Create .env file
cat > .env << 'EOF'
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here
EOF
```

### Step 3: Start Bot (2 min)

```bash
# Build and run
docker-compose -f docker-compose.live.yml up -d

# Check logs
docker logs -f held-fvg-bot-live
```

**You should see:**
```
[INFO] HELD FVG LIVE BOT STARTED
[INFO] Leverage set to 5x for BTCUSDT
[INFO] Current balance: $XXX.XX USDT
[INFO] Initial 4H candle time set: ...
```

## ✅ Verification Checklist

- [ ] API keys valid (no errors in logs)
- [ ] Futures permission enabled
- [ ] Bot shows balance correctly
- [ ] Leverage set to 5x
- [ ] Bot polling every 60 seconds

## 📊 What to Expect

### First Hours
- Bot polls 4H candles every 60 seconds
- Logs: "4H candle closed" every 4 hours
- May not see trades immediately (normal!)

### First Trade
```
[INFO] New FVG detected: BULLISH at $95000-$96000
[INFO] FVG HELD: BULLISH at $95500
[INFO] OPENING TRADE:
[INFO]   Direction: LONG
[INFO]   Entry: $95500
[INFO]   SL: $94800
[INFO]   TP: $100000
[INFO]   Size: 0.123 BTC
[INFO] ✅ Trade opened successfully!
```

### When Trade Executes
- Entry order: MARKET (filled immediately)
- SL order: STOP_MARKET (activated if price hits SL)
- TP order: TAKE_PROFIT_MARKET (activated if price hits TP)

## 🛑 How to Stop

### Normal Stop
```bash
docker-compose -f docker-compose.live.yml stop
```

### Emergency Stop
```bash
# 1. Stop bot
docker-compose -f docker-compose.live.yml down

# 2. Go to Binance Futures
# 3. Close position manually
# 4. Cancel all orders
```

## 📱 Monitoring Commands

```bash
# View real-time logs
docker logs -f held-fvg-bot-live

# View last 50 lines
docker logs --tail 50 held-fvg-bot-live

# Search for trades
docker logs held-fvg-bot-live | grep "Trade opened"

# Search for errors
docker logs held-fvg-bot-live | grep ERROR

# Check if bot is running
docker ps | grep held-fvg-bot-live

# Restart bot
docker-compose -f docker-compose.live.yml restart
```

## 🔍 Troubleshooting Quick Fixes

### "API key not valid"
```bash
# Check .env file
cat .env

# Verify keys on Binance
# Make sure Futures permission is enabled
```

### "Insufficient balance"
```bash
# Transfer USDT to Futures wallet on Binance
# Minimum: ~$50 for smallest trades
# Recommended: $300+ (same as backtest)
```

### "No trades after 24 hours"
**This is normal!** The strategy is selective:
- ~34 trades per year
- ~3 trades per month
- May go 7-14 days without trades

Check logs for:
- "New FVG detected" (FVGs forming)
- "FVG HELD" (holds happening)
- "No liquidity zone found" (setups filtered)

## 📈 Expected Timeline

**Day 1:**
- Bot starts, monitors candles
- May see FVG detections
- Unlikely to have trade (need specific conditions)

**Week 1:**
- Should see 0-2 trades
- Monitor logs daily
- Verify bot is running

**Month 1:**
- Expect ~3 trades (based on backtest)
- Should see first profits/losses
- Confirm strategy working as expected

**Year 1:**
- Expect ~34 trades
- Target: ~+878% ROI (before slippage)
- Realistic: ~+700-800% ROI

## ⚠️ Safety Reminders

1. **Start Small:** Use $100-300 to test
2. **Monitor Daily:** Check logs once per day minimum
3. **Don't Interfere:** Let bot manage positions
4. **Keep SL/TP:** Don't cancel protective orders
5. **Watch Balance:** Ensure sufficient USDT

## 🎯 Success Indicators

After 1 month, you should see:
- ✅ Bot running 24/7 without crashes
- ✅ 2-4 trades executed
- ✅ Win rate around 60-75%
- ✅ No API errors
- ✅ Positions closed at SL or TP

## 🚨 When to Stop Bot

Stop immediately if:
- ❌ Multiple API errors
- ❌ Trades executing incorrectly
- ❌ SL/TP orders not being placed
- ❌ Balance draining rapidly
- ❌ You don't understand what's happening

## 📞 Need Help?

1. Check logs first
2. Read README_LIVE.md
3. Verify Binance API status
4. Check bot configuration
5. Review backtest results (FINAL_RESULTS_2023-2025.md)

---

**Ready to start? Run:**

```bash
docker-compose -f docker-compose.live.yml up -d && docker logs -f held-fvg-bot-live
```

Good luck! 🚀
