# 🧪 Testing Guide - Failed 4H FVG Live Bot

## Pre-requisites

### 1. Install Dependencies
```bash
pip install python-binance pandas numpy python-dotenv
```

### 2. Get Binance Testnet API Keys

**IMPORTANT:** Start with testnet (fake money)!

1. Go to https://testnet.binance.vision/
2. Click "Generate HMAC_SHA256 Key"
3. Save API Key and Secret Key

### 3. Setup Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your testnet keys
nano .env
```

Example `.env`:
```bash
BINANCE_API_KEY=your_testnet_api_key
BINANCE_API_SECRET=your_testnet_secret
DRY_RUN=true
```

---

## Test 1: Mock Order Test (Won't Fill)

**Purpose:** Test order placement without fills (entry far from price)

### Setup

```python
# Modify failed_fvg_live_bot.py temporarily
# Add this to validate_setup() to allow far prices:

def validate_setup(self, entry: float, sl: float, tp: float) -> bool:
    # ... existing checks ...

    # Comment out this check for mock testing:
    # if distance_pct > max_distance_pct:
    #     logger.warning(f"Entry too far from current: {distance_pct:.2f}% > {max_distance_pct}%")
    #     return False

    return True
```

### Manual Mock Order Creation

Create a test script `test_mock_order.py`:

```python
from failed_fvg_live_bot import FailedFVGLiveBot
import logging

logging.basicConfig(level=logging.INFO)

bot = FailedFVGLiveBot()
bot.initialize()

# Get current price
current_price = bot.client.get_current_price('BTCUSDT')
print(f"Current BTC price: ${current_price:.2f}")

# Create mock setup (won't fill)
# SHORT example: entry 10% above current
mock_entry = current_price * 1.10
mock_sl = mock_entry * 1.005  # 0.5% SL
mock_tp = mock_entry - (abs(mock_entry - mock_sl) * 1.5)

print(f"\nMock SHORT setup:")
print(f"Entry: ${mock_entry:.2f} (+10% from current - won't fill)")
print(f"SL:    ${mock_sl:.2f}")
print(f"TP:    ${mock_tp:.2f}")

# Calculate size
size = bot.calculate_position_size(mock_entry, mock_sl)
print(f"Size:  {size}")

# Place order
try:
    order = bot.client.place_limit_order(
        symbol='BTCUSDT',
        side='SELL',
        quantity=size,
        price=mock_entry
    )

    print(f"\n✅ Mock order placed!")
    print(f"Order ID: {order['orderId']}")
    print(f"Status: {order['status']}")

    # Wait 5 minutes, then check status
    import time
    print("\nWaiting 60 seconds...")
    time.sleep(60)

    # Check order
    order_status = bot.client.get_order('BTCUSDT', order['orderId'])
    print(f"\nOrder status after 60s: {order_status['status']}")

    # Cancel order
    bot.client.cancel_order('BTCUSDT', order['orderId'])
    print("✅ Order cancelled")

except Exception as e:
    print(f"❌ Error: {e}")
```

Run:
```bash
python test_mock_order.py
```

### Expected Results:
✅ Order placed successfully
✅ Order ID returned
✅ Status = 'NEW'
✅ After 60s, status still 'NEW' (not filled)
✅ Order cancelled successfully

---

## Test 2: State Persistence Test

**Purpose:** Verify bot state survives restart

### Steps:

1. **Start bot normally:**
```bash
python failed_fvg_live_bot.py
```

2. **Wait for bot to detect some FVGs** (check logs):
```
Found 15 4H FVGs
New 4H FVG detected: BULLISH $94000.00-$94500.00
```

3. **Kill bot (Ctrl+C)**

4. **Check state file created:**
```bash
cat state.json
```

Should see:
```json
{
  "active_4h_fvgs": [...],
  "rejected_4h_fvgs": [...],
  "pending_setups": [],
  "active_trade": null,
  "balance": 10000.0,
  "last_updated": "2025-11-15T..."
}
```

5. **Restart bot:**
```bash
python failed_fvg_live_bot.py
```

6. **Check logs for state restoration:**
```
Restoring state from disk...
Restored: 15 active FVGs, 0 rejected FVGs, 0 pending setups
```

### Expected Results:
✅ State file created
✅ FVGs saved correctly
✅ On restart, state restored
✅ Bot continues from where it left off

---

## Test 3: FVG Detection Test

**Purpose:** Verify FVG detection works correctly

Create test script `test_fvg_detection.py`:

```python
from failed_fvg_live_bot import FailedFVGLiveBot, FVGDetector
import pandas as pd

bot = FailedFVGLiveBot()
bot.initialize()

# Fetch recent candles
df_4h = bot.client.get_klines('BTCUSDT', '4h', limit=200)

print(f"Loaded {len(df_4h)} 4H candles")
print(f"Date range: {df_4h.index[0]} to {df_4h.index[-1]}")

# Detect FVGs
detector = FVGDetector()
fvgs = detector.detect_fvgs(df_4h, '4h')

print(f"\n✅ Detected {len(fvgs)} FVGs")

# Print first 5
for i, fvg in enumerate(fvgs[:5]):
    print(f"\n{i+1}. {fvg.type} FVG")
    print(f"   Range: ${fvg.bottom:.2f} - ${fvg.top:.2f}")
    print(f"   Formed: {fvg.formed_time}")
    print(f"   Size: ${fvg.top - fvg.bottom:.2f}")
```

Run:
```bash
python test_fvg_detection.py
```

### Expected Results:
✅ 10-30 FVGs detected on 200 candles
✅ FVGs have valid price ranges
✅ Types are 'BULLISH' or 'BEARISH'
✅ Formed times match candle times

---

## Test 4: Rejection Detection Test

**Purpose:** Verify rejection logic works

Create test script `test_rejection.py`:

```python
from failed_fvg_live_bot import FailedFVGLiveBot, LiveFVG
from datetime import datetime

bot = FailedFVGLiveBot()
bot.initialize()

# Create test FVG (Bullish)
test_fvg = LiveFVG(
    id='test_bullish_fvg',
    type='BULLISH',
    top=95000.0,
    bottom=94500.0,
    formed_time=datetime.now(),
    timeframe='4h'
)

print(f"Test FVG: BULLISH ${test_fvg.bottom:.2f}-${test_fvg.top:.2f}")

# Simulate candles
test_candles = [
    # Candle enters zone
    {'high': 94800.0, 'low': 94600.0, 'close': 94700.0, 'close_time': int(datetime.now().timestamp() * 1000)},
    # Candle rejects (closes below)
    {'high': 94600.0, 'low': 94300.0, 'close': 94400.0, 'close_time': int(datetime.now().timestamp() * 1000)},
]

for i, candle in enumerate(test_candles):
    print(f"\nCandle {i+1}: High=${candle['high']:.2f}, Low=${candle['low']:.2f}, Close=${candle['close']:.2f}")

    rejected = test_fvg.check_rejection(candle)

    print(f"Entered: {test_fvg.entered}")
    print(f"Rejected: {test_fvg.rejected}")

    if rejected:
        print(f"🚫 REJECTION DETECTED at ${test_fvg.rejection_price:.2f}")
        break

# Check SL calculation
sl = test_fvg.get_stop_loss()
print(f"\nSL calculated: ${sl:.2f}")
print(f"Highs inside: {test_fvg.highs_inside}")
```

Run:
```bash
python test_rejection.py
```

### Expected Results:
✅ First candle: entered = True, rejected = False
✅ Second candle: rejected = True
✅ Rejection price = close price
✅ SL calculated from highs_inside
✅ Highs inside list contains [94800.0, 94600.0]

---

## Test 5: Pre-Flight Check Test

**Purpose:** Verify all systems ready before trading

```bash
python -c "
from failed_fvg_live_bot import FailedFVGLiveBot
bot = FailedFVGLiveBot()
bot.pre_flight_check()
"
```

### Expected Output:
```
Running pre-flight checks...
✅ API Connection
✅ Balance
✅ Symbol Info
✅ State File
```

If any ❌, fix before proceeding!

---

## Test 6: Full Integration Test

**Purpose:** Run bot for 1 hour and verify all components work

### Steps:

1. **Clear previous state:**
```bash
rm state.json
rm *.log
```

2. **Start bot:**
```bash
python failed_fvg_live_bot.py
```

3. **Monitor logs for 1 hour:**
```bash
tail -f live_bot.log
```

Look for:
- ✅ Initialization complete
- ✅ FVGs detected
- ✅ Checking 4H candles every 4H
- ✅ Checking 15M candles every 15M
- ✅ State saved every 5 min

4. **If rejection detected:**
- ✅ Setup created
- ✅ Limit order placed
- ✅ Order ID logged
- ✅ Expiry time set

5. **Stop bot (Ctrl+C)**

6. **Verify state saved:**
```bash
cat state.json | jq .
```

### Expected Results:
✅ No errors in logs
✅ FVGs detected correctly
✅ State saved periodically
✅ On shutdown, orders cancelled
✅ Final state saved

---

## Test 7: Emergency Stop Test

**Purpose:** Test safety mechanisms

Create test script `test_emergency_stop.py`:

```python
from failed_fvg_live_bot import FailedFVGLiveBot

bot = FailedFVGLiveBot()
bot.initialize()

# Simulate high drawdown
bot.initial_balance = 10000
bot.balance = 8000  # 20% loss

print(f"Initial: ${bot.initial_balance:.2f}")
print(f"Current: ${bot.balance:.2f}")
print(f"DD: {(bot.initial_balance - bot.balance) / bot.initial_balance * 100:.2f}%")

# Check emergency stop
should_stop = bot.check_emergency_stop()
print(f"\nEmergency stop triggered: {should_stop}")

# Test consecutive losses
bot.balance = 9500  # Reset
bot.consecutive_losses = 5

should_stop = bot.check_emergency_stop()
print(f"\nEmergency stop (5 losses): {should_stop}")
```

Run:
```bash
python test_emergency_stop.py
```

### Expected Results:
✅ 20% DD triggers emergency stop
✅ 5 consecutive losses trigger emergency stop
✅ Logs show critical alert

---

## Common Issues & Solutions

### Issue: "Insufficient balance"
**Solution:** Get testnet funds from https://testnet.binance.vision/ faucet

### Issue: "Invalid API key"
**Solution:**
- Regenerate testnet keys
- Check .env file format (no quotes, no spaces)
- Ensure DRY_RUN=true

### Issue: "Order rejected: MIN_NOTIONAL"
**Solution:** Position size too small, bot auto-adjusts to $10 minimum

### Issue: "No FVGs detected"
**Solution:** Normal, wait for market to form FVGs (can take hours)

### Issue: Bot keeps creating setups from same rejection
**Solution:** Check cooldown logic in code, should be 4H cooldown after expiry

---

## Live Trading Checklist (After Testing)

**Only proceed if ALL tests passed!**

- [ ] Mock order test passed
- [ ] State persistence test passed
- [ ] FVG detection test passed
- [ ] Rejection detection test passed
- [ ] Pre-flight check passed
- [ ] 1 hour integration test passed
- [ ] Emergency stop test passed
- [ ] Understand all risks
- [ ] Have stop-loss plan
- [ ] Ready to monitor 24/7

**To go live:**

1. Get real Binance API keys
2. Update .env with real keys
3. Set `DRY_RUN=false`
4. Start with small balance ($100-$500)
5. Monitor closely for first week

---

## Monitoring & Logs

### View live logs:
```bash
tail -f live_bot.log
```

### View state:
```bash
cat state.json | jq .
```

### View last 100 log lines:
```bash
tail -100 live_bot.log
```

### Search for errors:
```bash
grep ERROR live_bot.log
grep CRITICAL live_bot.log
```

---

## Support & Resources

- **Binance API Docs:** https://binance-docs.github.io/apidocs/
- **Python-Binance:** https://python-binance.readthedocs.io/
- **Testnet:** https://testnet.binance.vision/

**Good luck! Test thoroughly before going live! 🚀**
