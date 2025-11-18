# Live Bot Logging Examples

## 📊 Ініціалізація

```
================================================================================
FAILED 4H FVG LIVE BOT - INITIALIZATION
================================================================================
Running pre-flight checks...
✅ API Connection
✅ Balance
✅ Symbol Info
✅ State File
Fetching historical data...
Loaded 200 4H candles, 1000 15M candles
Last 4H candle: 2025-11-18 20:00:00 (still OPEN - will detect FVG when it closes)
Last 15M candle: 2025-11-18 22:45:00
Detecting initial FVGs...
Found 15 4H FVGs (from closed candles only)
Balance: $300.00 USDT
✅ Initialization complete
================================================================================
```

## 🕯️ Детекція нових свічок

### 4H свічка (коли закривається):
```
🕯️  New 4H candle detected!
   Previous: 2025-11-18 16:00:00
   Current:  2025-11-18 20:00:00
🔍 Checking for FVG: closed candle 2025-11-18 16:00:00, prev-2: 2025-11-18 08:00:00
✅ New 4H FVG detected: BEARISH $90842.10-$91250.00 (from closed candle at 2025-11-18 16:00:00)
✅ New 4H FVG detected: BULLISH $91567.00-$92532.00 (from closed candle at 2025-11-18 16:00:00)
Total active 4H FVGs: 17
✅ 4H candle processed
```

### 15M свічка:
```
🕯️  New 15M candle detected: 2025-11-18 22:15:00
Checking 15M logic...
```

## 🚫 Rejection Detection

```
🚫 REJECTION! Bullish FVG $91567.00-$92532.00 → SHORT setup
   Rejected @ $91450.25 (closed below bottom $91567.00)
   Time: 2025-11-18 22:15:00
   Expected: SHORT trade with 15M BEARISH FVG
   Total rejected FVGs: 3
```

## 📋 Пошук setups

### Коли є rejected FVG:
```
Looking for setups from 3 rejected FVG(s)...
  Checking rejected BULLISH FVG $91567.00-$92532.00
    Found 15M BEARISH FVG $91200.00-$91450.00
    Validating setup...
    Entry: $91450.00, SL: $92738.64, TP: $87612.08
    RR: 3.0, SL%: 1.41%
📋 Setup created: SHORT @ $91450.00, SL=$92738.64, TP=$87612.08, Size=0.005
✅ Limit order placed: SELL 0.005 @ $91450.00, OrderID: 123456789
Setup search complete: checked 3, created 1
```

### Коли FVG типи не співпадають:
```
Looking for setups from 2 rejected FVG(s)...
  Checking rejected BULLISH FVG $91567.00-$92532.00
    Found 15M BULLISH FVG $91800.00-$92100.00
    ❌ FVG type mismatch: need BEARISH for SHORT, got BULLISH
  Checking rejected BEARISH FVG $90842.10-$91250.00
    No 15M FVG found in last 10 candles
Setup search complete: checked 2, created 0
```

### Коли RR занадто низький:
```
Looking for setups from 1 rejected FVG(s)...
  Checking rejected BEARISH FVG $90842.10-$91250.00
    Found 15M BULLISH FVG $90900.00-$91100.00
    Validating setup...
    Entry: $90900.00, SL: $90633.68, TP: $91698.96
    RR: 1.5 < MIN_RR 2.0
    ❌ Setup validation failed: RR too low
Setup search complete: checked 1, created 0
```

### Коли FVG в cooldown:
```
Looking for setups from 2 rejected FVG(s)...
  Rejected FVG BULLISH in cooldown (45m left)
  Rejected FVG BEARISH already has filled trade
Setup search complete: checked 2, created 0
```

## 📦 Pending setups

### Коли limit order заповнюється:
```
🎯 Setup filled! OrderID: 123456789
   Direction: SHORT
   Entry: $91450.00
   Size: 0.005 BTC
   Fill time: 2025-11-18 22:30:00
✅ SL/TP orders placed: SL=123456790, TP=123456791
🚀 Trade activated: SHORT @ $91450.00
```

### Коли limit order експірується:
```
⏰ Setup expired: setup_1731965400
   OrderID: 123456789 cancelled
   Cooldown set until 2025-11-19 02:30:00 (4H)
```

## 📊 Active Trade Monitoring

### Нормальний моніторинг:
```
Monitoring active trade #1...
   Current price: $91200.00
   Current PnL: +$1.25 (+0.27%)
   Entry: $91450.00, SL: $92738.64, TP: $87612.08
```

### Trade закривається по TP:
```
✅ Trade closed: TP | PnL: $+19.45 (+4.25%) | Balance: $319.45
   Entry: $91450.00 @ 2025-11-18 22:30:00
   Exit:  $87612.08 @ 2025-11-18 23:45:00
   Duration: 1h 15m
   Trade #1 | SHORT
```

### Trade закривається по SL:
```
❌ Trade closed: SL | PnL: $-6.48 (-1.41%) | Balance: $293.52
   Entry: $91450.00 @ 2025-11-18 22:30:00
   Exit:  $92738.64 @ 2025-11-18 23:15:00
   Duration: 45m
   Trade #1 | SHORT
```

## 🚨 Помилки та попередження

### Недостатній баланс:
```
⚠️  WARNING: Insufficient balance for trade
   Required: $10.00
   Available: $8.50
   Skipping setup creation
```

### API помилка:
```
❌ Error placing limit order: BinanceAPIException
   Code: -1013
   Message: Filter failure: MIN_NOTIONAL
   Retrying with adjusted size...
```

### Invalidation:
```
❌ 4H FVG BULLISH $91567.00-$92532.00 invalidated
   Reason: Price fully passed below $91567.00
   Current price: $91400.00
   Removed from active FVGs
```

## 📈 Статистика (кожні 4H або після трейду)

```
================================================================================
BOT STATISTICS
================================================================================
⏱️  Running time: 2 days 5h 30m
💰 Balance: $315.45 (Start: $300.00, +5.15%)

📊 Trades:
   Total: 5
   Wins: 4 (80%)
   Losses: 1 (20%)

💵 P&L:
   Total: +$15.45
   Avg Win: +$6.25
   Avg Loss: -$6.48
   Profit Factor: 3.86

📋 Current Status:
   Active 4H FVGs: 12
   Rejected 4H FVGs: 2
   Pending setups: 1
   Active trades: 0

🔍 Recent Activity:
   Last 4H candle: 2025-11-19 00:00:00
   Last rejection: 2025-11-18 22:15:00
   Last trade: #5 (WIN, +$8.25)
================================================================================
```

## 🔄 State Management

```
💾 Saving state...
   Active 4H FVGs: 12
   Rejected 4H FVGs: 2
   Pending setups: 1
   Active trade: None
   Balance: $315.45
✅ State saved to state.json
```

## 🛑 Shutdown

```
================================================================================
SHUTTING DOWN
================================================================================
Cancelling all pending orders...
   Cancelled OrderID: 123456789
Saving state...
✅ State saved
Final balance: $315.45
Total trades: 5
Win rate: 80.0%
✅ Shutdown complete
================================================================================
```

## 🎯 Приклад повного циклу трейду:

```
2025-11-18 20:00:12 | 🕯️  New 4H candle detected!
2025-11-18 20:00:12 | ✅ New 4H FVG detected: BULLISH $91567.00-$92532.00
2025-11-18 22:15:15 | 🚫 REJECTION! Bullish FVG $91567.00-$92532.00 → SHORT setup
2025-11-18 22:15:20 | Looking for setups from 1 rejected FVG(s)...
2025-11-18 22:15:20 |   Found 15M BEARISH FVG $91200.00-$91450.00
2025-11-18 22:15:20 | 📋 Setup created: SHORT @ $91450.00
2025-11-18 22:15:21 | ✅ Limit order placed: OrderID: 123456789
2025-11-18 22:30:45 | 🎯 Setup filled! OrderID: 123456789
2025-11-18 22:30:46 | ✅ SL/TP orders placed: SL=123456790, TP=123456791
2025-11-18 22:30:46 | 🚀 Trade activated: SHORT @ $91450.00
2025-11-18 23:45:12 | ✅ Trade closed: TP | PnL: $+19.45 (+4.25%) | Balance: $319.45
```

## Рівні логування:

- **INFO** - основні події (FVG detection, rejections, setups, trades)
- **DEBUG** - детальна інформація (cooldowns, validation failures)
- **WARNING** - попередження (low balance, API issues)
- **ERROR** - помилки (API failures, order placement failures)
- **CRITICAL** - критичні події (emergency stop, max drawdown)
