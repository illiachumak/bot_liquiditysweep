# Покращення логування в Live Bot

## ✅ Додані логи

### 1. 🚫 Rejection Detection (LiveFVG.check_rejection)
```python
# Bullish FVG rejection:
🚫 REJECTION! Bullish FVG $91567.00-$92532.00 → SHORT setup
   Rejected @ $91450.25 (closed below bottom $91567.00)
   Expected: SHORT trade with 15M BEARISH FVG

# Bearish FVG rejection:
🚫 REJECTION! Bearish FVG $90842.10-$91250.00 → LONG setup
   Rejected @ $91350.75 (closed above top $91250.00)
   Expected: LONG trade with 15M BULLISH FVG
```

### 2. ✅ FVG Entry
```python
✅ FVG entered: 4h BULLISH $91567.00-$92532.00
```

### 3. 📋 Setup Search (look_for_setups)
```python
Looking for setups from 3 rejected FVG(s)...
  Checking rejected BULLISH FVG $91567.00-$92532.00
    Found 15M BEARISH FVG $91200.00-$91450.00
    Validating SHORT setup: Entry=$91450.00, SL=$92738.64, TP=$87612.08
    ✅ Setup validation passed: Entry=$91450.00, SL=$92738.64, TP=$87612.08, RR=3.00
📋 Setup created: SHORT @ $91450.00, SL=$92738.64, TP=$87612.08, Size=0.005
Setup search complete: checked 3, created 1
```

### 4. ❌ Setup Validation Failures
```python
# RR too low:
    ❌ Setup validation failed: RR too low 1.5 < 2.0

# SL too tight:
    ❌ Setup validation failed: SL too tight 0.25% < 0.3%

# Entry too far:
    ❌ Setup validation failed: Entry too far from current 6.5% > 5.0%

# FVG type mismatch:
    ❌ FVG type mismatch: need BEARISH for SHORT, got BULLISH

# No SL available:
    ❌ No SL available (no highs/lows inside FVG)

# No 15M FVG:
    No 15M FVG found in last 10 candles
```

### 5. ❌ Invalidation
```python
❌ 4H FVG BULLISH $91567.00-$92532.00 invalidated (price fully passed)
4H FVG update: 0 new rejections, 1 invalidations
```

### 6. 📦 Pending Setups
```python
Checking 2 pending setup(s)...
🎯 Setup filled! OrderID: 123456789
   Direction: SHORT
   Entry: $91450.00
   Size: 0.005 BTC
   Fill time: 2025-11-18 22:30:00
✅ SL/TP orders placed: SL=123456790, TP=123456791
🚀 Trade activated: SHORT @ $91450.00

# Або:
⏰ Setup expired: setup_1731965400
   OrderID: 123456789 cancelled
   Cooldown set until 2025-11-19 02:30:00 (4H)
```

### 7. 💰 Trade Closed
```python
# Win:
✅ Trade closed: TP | PnL: $+19.45 (+4.25%) | Balance: $319.45
   Entry: $91450.00 @ 2025-11-18 22:30:00
   Exit:  $87612.08 @ 2025-11-18 23:45:00
   Duration: 1.2h | Direction: SHORT

# Loss:
❌ Trade closed: SL | PnL: $-6.48 (-1.41%) | Balance: $293.52
   Entry: $91450.00 @ 2025-11-18 22:30:00
   Exit:  $92738.64 @ 2025-11-18 23:15:00
   Duration: 45m | Direction: SHORT
```

### 8. 📊 Periodic Statistics (після кожної 4H свічки)
```python
================================================================================
📊 BOT STATISTICS
================================================================================
💰 Balance: $315.45 (Start: $300.00, +5.15%)
📋 Active 4H FVGs: 12
🚫 Rejected 4H FVGs: 2
📦 Pending setups: 1
🔄 Active trades: 0
📈 Total trades: 5 (Win rate: 80.0%)
Recent rejected FVGs:
  - BULLISH $91567.00-$92532.00 (cooldown 45m)
  - BEARISH $90842.10-$91250.00 [FILLED]
================================================================================
```

### 9. 🔄 Cooldown Info
```python
Looking for setups from 2 rejected FVG(s)...
  Rejected FVG BULLISH in cooldown (45m left)
  Rejected FVG BEARISH already has filled trade
Setup search complete: checked 2, created 0
```

### 10. 🕯️ 4H Candle Processing
```python
🕯️  New 4H candle detected!
   Previous: 2025-11-18 16:00:00
   Current:  2025-11-18 20:00:00
🔍 Checking for FVG: closed candle 2025-11-18 16:00:00, prev-2: 2025-11-18 08:00:00
✅ New 4H FVG detected: BEARISH $90842.10-$91250.00 (from closed candle at 2025-11-18 16:00:00)
✅ 4H candle processed
```

## 🎯 Що тепер видно в логах:

### ✅ ЗАВЖДИ видно:
1. **Чи є rejected FVG** - скільки їх активних
2. **Чому setup не створюється** - детальна причина (RR, SL, type mismatch, etc.)
3. **Які 15M FVG знайдено** - якщо знайдено
4. **Коли rejection відбувається** - з повною інформацією
5. **Коли FVG invalidується** - і чому
6. **Детальна інформація про trade** - entry/exit з часом та тривалістю
7. **Статистика бота** - після кожної 4H свічки
8. **Cooldown status** - скільки часу залишилось
9. **Validation failures** - точна причина чому setup не пройшов

### 📊 Періодичність логів:
- **Кожні 15M**: Нова свічка, перевірка setups
- **Кожні 4H**: Нова 4H свічка, детекція FVG, статистика
- **При події**: Rejection, setup creation, trade fill, trade close

## 🔍 Приклад повного циклу в логах:

```
2025-11-18 20:00:12 | 🕯️  New 4H candle detected!
2025-11-18 20:00:12 | ✅ New 4H FVG detected: BULLISH $91567.00-$92532.00
2025-11-18 20:00:12 | ✅ 4H candle processed
2025-11-18 20:00:12 | ================================================================================
2025-11-18 20:00:12 | 📊 BOT STATISTICS
2025-11-18 20:00:12 | ================================================================================
2025-11-18 20:00:12 | 💰 Balance: $300.00 (Start: $300.00, +0.00%)
2025-11-18 20:00:12 | 📋 Active 4H FVGs: 15
2025-11-18 20:00:12 | 🚫 Rejected 4H FVGs: 0
2025-11-18 20:00:12 | ================================================================================
2025-11-18 22:15:15 | 🕯️  New 15M candle detected: 2025-11-18 22:15:00
2025-11-18 22:15:15 | Checking 15M logic...
2025-11-18 22:15:16 | 🚫 REJECTION! Bullish FVG $91567.00-$92532.00 → SHORT setup
2025-11-18 22:15:16 |    Rejected @ $91450.25 (closed below bottom $91567.00)
2025-11-18 22:15:16 |    Expected: SHORT trade with 15M BEARISH FVG
2025-11-18 22:15:16 | 4H FVG update: 1 new rejections, 0 invalidations
2025-11-18 22:15:17 | Looking for setups from 1 rejected FVG(s)...
2025-11-18 22:15:17 |   Checking rejected BULLISH FVG $91567.00-$92532.00
2025-11-18 22:15:17 |     Found 15M BEARISH FVG $91200.00-$91450.00
2025-11-18 22:15:17 |     Validating SHORT setup: Entry=$91450.00, SL=$92738.64, TP=$87612.08
2025-11-18 22:15:17 |     ✅ Setup validation passed: Entry=$91450.00, SL=$92738.64, TP=$87612.08, RR=3.00
2025-11-18 22:15:17 | 📋 Setup created: SHORT @ $91450.00, SL=$92738.64, TP=$87612.08, Size=0.005
2025-11-18 22:15:18 | ✅ Limit order placed: SELL 0.005 @ $91450.00, OrderID: 123456789
2025-11-18 22:15:18 | Setup search complete: checked 1, created 1
2025-11-18 22:30:45 | 🕯️  New 15M candle detected: 2025-11-18 22:30:00
2025-11-18 22:30:45 | Checking 15M logic...
2025-11-18 22:30:45 | Checking 1 pending setup(s)...
2025-11-18 22:30:46 | 🎯 Setup filled! OrderID: 123456789
2025-11-18 22:30:46 |    Direction: SHORT
2025-11-18 22:30:46 |    Entry: $91450.00
2025-11-18 22:30:46 |    Size: 0.005 BTC
2025-11-18 22:30:46 |    Fill time: 2025-11-18 22:30:00
2025-11-18 22:30:47 | ✅ SL/TP orders placed: SL=123456790, TP=123456791
2025-11-18 22:30:47 | 🚀 Trade activated: SHORT @ $91450.00
2025-11-18 23:45:12 | ✅ Trade closed: TP | PnL: $+19.45 (+4.25%) | Balance: $319.45
2025-11-18 23:45:12 |    Entry: $91450.00 @ 2025-11-18 22:30:00
2025-11-18 23:45:12 |    Exit:  $87612.08 @ 2025-11-18 23:45:00
2025-11-18 23:45:12 |    Duration: 1.2h | Direction: SHORT
```

## 🎉 Результат

Тепер live bot **повністю прозорий**! Ти бачиш:
- ✅ Кожен rejection
- ✅ Кожен setup (створений чи ні, і чому)
- ✅ Валідацію (пройшла чи ні, і чому)
- ✅ Статистику (баланс, FVG, трейди)
- ✅ Повну інформацію про трейди
- ✅ Cooldowns та invalidations

**Більше ніяких питань "що робить бот?"** 🎯
