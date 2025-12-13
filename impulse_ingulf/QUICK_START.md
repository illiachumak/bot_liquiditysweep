# PRODUCTION_Q3 Live Bot - Quick Start Guide

## Step-by-Step Setup (5 minutes)

### 1. Prerequisites ✅

- [ ] Binance Futures account created
- [ ] API keys generated with Futures trading permissions
- [ ] Docker installed on your machine
- [ ] Basic understanding of trading risks

### 2. Configuration ⚙️

**Copy environment file:**
```bash
cd PRODUCTION_Q3_LIVE
cp .env.example .env
```

**Edit .env file:**
```bash
nano .env  # or use any text editor
```

Add your credentials:
```
BINANCE_API_KEY=your_actual_api_key_here
BINANCE_API_SECRET=your_actual_api_secret_here
```

### 3. Review Settings 📋

Open `config.py` and check these critical settings:

```python
# Symbol (default: BTCUSDT)
SYMBOL = "BTCUSDT"

# Leverage (default: 100x) ⚠️ HIGH RISK
LEVERAGE = 100

# Risk per trade (default: 1.5%-2.0% depending on quality)
# Adjust RISK_BY_CATEGORY if needed

# Max position size (default: $10,000)
MAX_POSITION_SIZE_USDT = 10000.0

# Max trades per day (default: 5)
MAX_TRADES_PER_DAY = 5
```

**⚠️ IMPORTANT:** Start with lower leverage (10-20x) if you're testing!

### 4. Launch Bot 🚀

**Using Docker Compose (Recommended):**
```bash
# Build and start in background
docker-compose up -d

# View live logs
docker-compose logs -f

# To stop
docker-compose down
```

**Alternative - Direct Docker:**
```bash
# Build
docker build -t production-q3-bot .

# Run
docker run -d --name production-q3-bot --env-file .env production-q3-bot

# Logs
docker logs -f production-q3-bot
```

### 5. Monitor Bot 👀

Watch for these log messages:

```
✅ Leverage set to 100x for BTCUSDT
Current balance: $XXXX.XX USDT
Initial 4H candle time set: ...
```

**When impulse detected:**
```
✅ 4H candle closed at 2025-XX-XX XX:XX:XX
🔥 IMPULSE DETECTED: BULLISH (strength: 2.34)
```

**When trade opens:**
```
OPENING TRADE:
  Direction: LONG
  Entry: $XXXXX
  SL: $XXXXX
  TP: $XXXXX
  Quality Score: 7
  R:R: 3.5
```

### 6. Safety Checklist ✅

Before going live:

- [ ] Tested configuration on Binance Testnet (if available)
- [ ] Verified API permissions (Futures trading enabled)
- [ ] Confirmed balance is correct
- [ ] Reviewed all safety limits in config.py
- [ ] Understand the strategy logic
- [ ] Prepared to monitor regularly
- [ ] Set alerts for notifications (optional)

## Common Commands

```bash
# Start bot
docker-compose up -d

# View logs (live)
docker-compose logs -f

# Stop bot
docker-compose down

# Restart bot
docker-compose restart

# Check bot status
docker-compose ps

# Remove everything (including volumes)
docker-compose down -v
```

## What Happens Next?

### Normal Operation Flow

1. **Bot starts** → Fetches 4H candles → Sets initial reference time
2. **Every 60 seconds** → Checks for new 4H candle close
3. **New 4H candle closes** → Detects impulse (if criteria met)
4. **Impulse detected** → Waits for consolidation + breakout on 1H
5. **Entry found** → Calculates quality score
6. **Quality passes** → Determines dynamic RR and variable risk
7. **Trade executed** → Opens position with SL and TP orders
8. **Position open** → Bot monitors until SL/TP hit
9. **Position closed** → Bot ready for next impulse

### Expected Behavior

- **Trade Frequency**: Low (impulses are rare, quality filter is strict)
- **Typical Wait**: Several hours to days between trades
- **4H Candle Frequency**: Every 4 hours
- **Max Trades/Day**: 5 (configurable)

## Strategy Summary

| Component | Setting | Purpose |
|-----------|---------|---------|
| HTF | 4H | Impulse detection |
| LTF | 1H | Entry confirmation |
| Impulse | ATR 1.5x, Body 70% | Strong moves only |
| Entry | Breakout | Confirmation required |
| Quality | 3-10 score | Filter weak setups |
| RR | 2.5x - 8.0x | Dynamic based on quality |
| Risk | 1.5% - 2.0% | Variable based on category |

## Quality Score → RR/Risk Mapping

| Quality Score | RR Ratio | Risk % | Description |
|--------------|----------|--------|-------------|
| 8-10 | 8.0x | 2.0% | Exceptional setup |
| 6-7 | 3.5x | 1.5% | Good setup |
| 4-5 | 3.0x | 1.5% | Medium setup |
| 3 | 2.5x | 2.0% | Acceptable setup |
| 0-2 | - | - | Filtered out |

## Emergency Stop

**To immediately stop the bot:**

```bash
# Docker Compose
docker-compose down

# Direct Docker
docker stop production-q3-bot

# Cancel all open orders manually (if needed)
# Log into Binance and cancel via UI
```

## Troubleshooting Quick Fixes

### Bot starts but no activity
- **Cause**: Waiting for next 4H candle close
- **Fix**: Be patient, next candle in max 4 hours

### API Authentication Error
- **Cause**: Wrong API credentials
- **Fix**: Double-check .env file, ensure no spaces/quotes

### Insufficient Balance
- **Cause**: Balance too low for position
- **Fix**: Increase balance or reduce MAX_POSITION_SIZE_USDT

### No trades executing
- **Cause**: Quality filter too strict
- **Fix**: Lower MIN_QUALITY_SCORE (but increases risk)

## Next Steps

1. ✅ Monitor first 24 hours closely
2. ✅ Keep logs for analysis
3. ✅ Track trade outcomes
4. ✅ Adjust settings based on performance
5. ✅ Consider risk management tweaks

## Support

Need help? Check:
1. Full README.md for detailed docs
2. Log files for error messages
3. Binance API status page
4. Strategy backtest results in IMPULSE_CANDLES/

---

**Good luck and trade safe! 📈**
