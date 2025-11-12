# 📋 SMC Bot - Complete Logging Guide

## 🎯 Purpose

This bot logs **EVERYTHING** to help you verify triggers, debug issues, and track API usage.

---

## 📁 Log Files

```
logs/
├── smc_bot.log           # Main log (detailed)
└── smc_bot.log.1         # Backup (rotates at 10MB)

trades_history/
├── trades.json           # All trades (JSON)
└── trades.csv            # All trades (CSV)
```

---

## 📊 What's Logged

### 1. API Requests (Rate Limit Tracking)

```
🌐 API Call #1: get_klines(15m, 200)
📈 Fetched 200 candles. Last: 2025-11-12 20:30:00, Close: $50000.00
📊 API Calls last minute: 15
```

**Why:** Binance has rate limits (1200 requests/minute). Track usage to avoid bans.

**Cache:** Price cached for 5 seconds to reduce API calls.

---

### 2. Order Block Detection

```
🔎 Scanning for Order Blocks at 2025-11-12 20:30:00
🔍 Looking for OBs in last 6 candles...
   📍 Found OB at idx 498 (3 candles old): LONG, $49500.00 - $49800.00
   ✅ OB valid! Range: $300.00, Usage: 0/3
   📋 Creating LONG Level 1: $49575.00, SL: $49450.00, TP1: $50025.00
   📋 Creating LONG Level 2: $49650.00, SL: $49450.00, TP1: $50100.00
   📋 Creating LONG Level 3: $49725.00, SL: $49450.00, TP1: $50175.00
✅ Created 3 limit orders for OB
```

**Why:** See which OBs are found and why limits are placed.

---

### 3. Limit Order Fills

```
🔍 Checking 3 pending limit orders at $49650.00
   ⏳ LONG L1: $49575.00 (need price <= this)
   🎯 LONG LIMIT HIT! Price $49650.00 <= Limit $49650.00 (Level 2)
```

**Why:** Verify fills happen correctly when price touches limit.

---

### 4. Exit Checks (TP/SL)

```
🔍 Checking exits for LONG position at $50100.00
   Entry: $49650.00, SL: $49450.00
   TPs: $50100.00, $50650.00, $51550.00
   ✅ SL safe: $50100.00 > $49450.00
   TP1: $50100.00 ✅ >= $50100.00
   TP2: $50100.00 ⏳ < $50650.00
   TP3: $50100.00 ⏳ < $51550.00
🎯 TP1 HIT! Price: $50100.00, PnL: $225.00
```

**Why:** Track exactly when and why TPs/SL are hit.

---

### 5. Position Status (Every Iteration)

```
============================================================
Iteration #42 | 2025-11-12 20:35:00
============================================================
📊 Fetching market data...
💵 BTC Price: $50,100.00
📈 Position: LONG | Entry: $49650.00 | Size: 0.1000
   SL: $49650.00 | TPs: [True, False, False]
🔍 Checking exits...
✅ Iteration complete. Sleeping 60s...
```

**Why:** See bot status on every cycle (price, position, actions).

---

## 🔍 Viewing Logs

### 1. Tail (Real-time)

```bash
# Follow log in real-time
tail -f logs/smc_bot.log

# Only important events (INFO level)
tail -f logs/smc_bot.log | grep INFO

# Only errors/warnings
tail -f logs/smc_bot.log | grep -E "ERROR|WARNING"
```

### 2. Search for Specific Events

```bash
# All OB detections
grep "Found OB" logs/smc_bot.log

# All limit fills
grep "LIMIT HIT" logs/smc_bot.log

# All TP hits
grep "TP.*HIT" logs/smc_bot.log

# All SL hits
grep "STOP LOSS" logs/smc_bot.log

# API call count
grep "API Calls last minute" logs/smc_bot.log
```

### 3. Filter by Time

```bash
# Today only
grep "2025-11-12" logs/smc_bot.log

# Specific hour
grep "2025-11-12 20:" logs/smc_bot.log

# Last 100 lines
tail -100 logs/smc_bot.log
```

### 4. Count Events

```bash
# How many OBs found
grep -c "Found OB" logs/smc_bot.log

# How many fills
grep -c "LIMIT HIT" logs/smc_bot.log

# How many TP hits
grep -c "TP.*HIT" logs/smc_bot.log

# How many errors
grep -c "ERROR" logs/smc_bot.log
```

---

## 🚨 Troubleshooting

### Problem: No OBs found

```bash
# Check if scanning is happening
grep "Scanning for Order Blocks" logs/smc_bot.log

# Check session filter
grep "Outside NY session" logs/smc_bot.log

# Check if OBs are being rejected
grep "already used" logs/smc_bot.log
```

### Problem: Limit orders not filling

```bash
# Check pending orders
grep "pending limit orders" logs/smc_bot.log

# Check price vs limit
grep "⏳" logs/smc_bot.log | tail -20

# Check expiry
grep "expired" logs/smc_bot.log
```

### Problem: TPs not hitting

```bash
# Check TP levels
grep "Checking exits" logs/smc_bot.log | tail -50

# Check price vs TP
grep "TP1:" logs/smc_bot.log | tail -20
```

### Problem: Too many API calls

```bash
# Check API usage
grep "API Calls last minute" logs/smc_bot.log | tail -10

# Should be ~4-6 per iteration (klines + price)
# If >20, there might be caching issues
```

---

## 📈 API Request Optimization

The bot is optimized to minimize API calls:

### Per Iteration (60s):
1. `get_klines(15m, 200)` - 1 call
2. `get_current_price()` - 1 call (cached for 5s)
3. `get_balance()` - only when filling order

**Total:** ~2-3 calls per minute

### Rate Limits:
- Binance: **1200 requests/minute** (weight-based)
- Bot uses: **~2-3 requests/minute**
- **Safe margin:** 400x below limit! ✅

### Cache Strategy:
- **Price:** 5 seconds TTL
- **Indicators:** 60 seconds TTL
- **Balance:** Only fetched on fills

---

## 📊 Log Levels

| Level | Usage | Example |
|-------|-------|---------|
| **DEBUG** | Detailed info | `📊 Using cached indicators` |
| **INFO** | Normal events | `✅ Created 3 limit orders` |
| **WARNING** | Important alerts | `🛑 STOP LOSS HIT!` |
| **ERROR** | Errors | `❌ ERROR in main loop` |

### Change Log Level

Edit `setup_logging()` in `smc_optimized_bot.py`:

```python
# More verbose (DEBUG)
logger.setLevel(logging.DEBUG)

# Less verbose (INFO)
logger.setLevel(logging.INFO)

# Only warnings/errors
logger.setLevel(logging.WARNING)
```

---

## 🔄 Log Rotation

Logs automatically rotate:
- **Max size:** 10MB per file
- **Backups:** 5 files kept
- **Total:** ~50MB max disk usage

Old logs:
```
smc_bot.log       # Current
smc_bot.log.1     # Previous
smc_bot.log.2     # Older
...
smc_bot.log.5     # Oldest (deleted when new backup created)
```

---

## 📁 Trade Logs vs Bot Logs

### Bot Logs (`logs/smc_bot.log`)
- **What:** All bot activity (scanning, checking, API calls)
- **Format:** Plain text with timestamps
- **Use:** Debugging, verification, monitoring

### Trade Logs (`trades_history/trades.json`)
- **What:** Only actual trades (SIGNAL, FILL, EXIT)
- **Format:** Structured JSON/CSV
- **Use:** Analysis, tax reporting, performance tracking

---

## 💡 Pro Tips

### 1. Monitor in Real-time

```bash
# Open 3 terminals:

# Terminal 1: Bot output
python3 smc_optimized_bot.py

# Terminal 2: Detailed log
tail -f logs/smc_bot.log | grep INFO

# Terminal 3: Trade log
tail -f trades_history/trades.json
```

### 2. Daily Report

```bash
# Today's activity
TODAY=$(date +%Y-%m-%d)
grep "$TODAY" logs/smc_bot.log > daily_report.txt

# Count events
echo "OBs found: $(grep -c 'Found OB' daily_report.txt)"
echo "Fills: $(grep -c 'LIMIT HIT' daily_report.txt)"
echo "TP hits: $(grep -c 'TP.*HIT' daily_report.txt)"
```

### 3. Error Alert

```bash
# Check for errors every 5 minutes
watch -n 300 "tail -100 logs/smc_bot.log | grep ERROR"
```

### 4. API Usage Monitor

```bash
# Watch API calls
watch -n 60 "tail -50 logs/smc_bot.log | grep 'API Calls last minute'"
```

---

## 🎯 Verification Checklist

Use logs to verify bot is working correctly:

✅ **API Calls:** ~2-3 per minute  
✅ **OB Detection:** Logs show OBs found with price ranges  
✅ **Limit Orders:** 3 levels created per OB  
✅ **Fills:** Only when price touches limit  
✅ **TP/SL:** Checked every iteration with clear conditions  
✅ **No Errors:** No ERROR lines in last 1000 lines  

```bash
# Quick verification
echo "API calls/min: $(grep 'API Calls last minute' logs/smc_bot.log | tail -1)"
echo "OBs today: $(grep -c 'Found OB' logs/smc_bot.log)"
echo "Fills today: $(grep -c 'LIMIT HIT' logs/smc_bot.log)"
echo "Errors: $(grep -c 'ERROR' logs/smc_bot.log)"
```

---

## 📞 Support

If bot is not working as expected:

1. Check logs for errors: `grep ERROR logs/smc_bot.log`
2. Verify API calls are working: `grep "Fetched.*candles" logs/smc_bot.log`
3. Check if OBs are found: `grep "Found OB" logs/smc_bot.log`
4. Verify limit logic: `grep "LIMIT HIT" logs/smc_bot.log`

---

**Logging = Confidence!** 🚀

With detailed logs, you can verify every trigger and ensure the bot works exactly as expected.
