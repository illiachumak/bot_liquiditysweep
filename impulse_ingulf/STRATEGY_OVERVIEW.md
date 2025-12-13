# PRODUCTION_Q3 Strategy Overview

## Strategy Components

### 1. Impulse Detection (HTF: 4H)

**ATR-Based Detector** detects strong price movements:

```
Criteria:
- Body > 1.5 × ATR(14)
- Body Ratio > 70% of total candle range
- Direction: BULLISH (close > open) or BEARISH (close < open)
```

**Example:**
```
4H Candle:
- Open: $40,000
- High: $42,500
- Low: $40,000
- Close: $42,400

Body = $42,400 - $40,000 = $2,400
Total Range = $42,500 - $40,000 = $2,500
Body Ratio = $2,400 / $2,500 = 96%

ATR(14) = $1,400
Body / ATR = $2,400 / $1,400 = 1.71x

✅ IMPULSE: Body (1.71x) > 1.5x ATR AND Body Ratio (96%) > 70%
Direction: BULLISH
```

---

### 2. Entry Strategy (LTF: 1H)

**Breakout Entry** waits for consolidation + breakout:

```
Steps:
1. Wait for consolidation (3-20 candles on 1H)
2. Consolidation must be BELOW impulse high (bullish) or ABOVE impulse low (bearish)
3. Breakout candle CLOSES above impulse high (bullish) or below impulse low (bearish)
4. EMA filter confirms trend (EMA12 > EMA21 for longs, EMA12 < EMA21 for shorts)
```

**Example (Bullish):**
```
Impulse: High = $42,500

1H Candles after impulse:
- Candle 1-5: Consolidating between $41,800 - $42,400
- Candle 6: BREAKS above $42,500 and CLOSES at $42,700

Entry: $42,500 (impulse high)
Stop Loss: $41,800 × 0.995 = $41,591 (0.5% buffer below consolidation low)
Risk: $42,500 - $41,591 = $909

Take Profit: Determined by Dynamic RR (see below)
```

---

### 3. Quality Scoring (0-10 Points)

**5 Criteria** evaluate setup quality:

#### A. Impulse Strength (0-2 points)
```
Body Ratio > 85%: +2 points
Body Ratio > 75%: +1 point
Body Ratio < 75%: 0 points
```

#### B. Volume Confirmation (0-2 points)
```
Volume > 2.0 × Avg(20): +2 points
Volume > 1.5 × Avg(20): +1 point
Volume < 1.5 × Avg(20): 0 points
```

#### C. Trend Alignment (0-2 points)
```
Bullish impulse + Price > MA(50) × 1.02: +2 points
Bullish impulse + Price > MA(50): +1 point
Bearish impulse + Price < MA(50) × 0.98: +2 points
Bearish impulse + Price < MA(50): +1 point
Otherwise: 0 points
```

#### D. Entry Timing (0-2 points)
```
Entry within 4 hours of impulse: +2 points
Entry within 12 hours of impulse: +1 point
Entry > 12 hours after impulse: 0 points
```

#### E. Consolidation Quality (0-2 points)
```
Consolidation range < 30% of impulse range: +2 points
Consolidation range < 50% of impulse range: +1 point
Consolidation range > 50% of impulse range: 0 points
```

**Example:**
```
Setup:
- Body Ratio: 96% → +2 points (A)
- Volume: 1.8 × Avg → +1 point (B)
- Price: $42,400 > MA50($40,000) × 1.02 = $40,800 → +2 points (C)
- Entry Timing: 3 hours after impulse → +2 points (D)
- Consolidation: $600 range / $2,500 impulse = 24% → +2 points (E)

Total Quality Score: 9/10 ✅ EXCELLENT
```

---

### 4. Dynamic RR Mapping

**Quality Score determines RR:**

| Quality Score | RR Ratio | Example (Risk $909) |
|--------------|----------|---------------------|
| **8-10** | 8.0x | TP @ Entry + $7,272 |
| **6-7** | 3.5x | TP @ Entry + $3,181 |
| **4-5** | 3.0x | TP @ Entry + $2,727 |
| **3** | 2.5x | TP @ Entry + $2,272 |
| **0-2** | Filtered | No trade |

**Example (Score 9):**
```
Entry: $42,500
Risk: $909
RR: 8.0x (score 8-10)

Take Profit: $42,500 + ($909 × 8.0) = $42,500 + $7,272 = $49,772
```

---

### 5. Variable Risk by Category

**Quality Score determines Risk %:**

| Quality Score | Risk % | Reasoning |
|--------------|--------|-----------|
| **8-10** | 2.0% | High conviction, large RR |
| **6-7** | 1.5% | Good setup, moderate RR |
| **4-5** | 1.5% | Medium quality, moderate RR |
| **3** | 2.0% | Acceptable but lower RR, compensate with higher risk |

**Example (Balance: $10,000):**
```
Quality Score: 9
Risk %: 2.0%
Risk Amount: $10,000 × 0.02 = $200

Entry: $42,500
Stop Loss: $41,591
Risk per unit: $909

Position Size: $200 / $909 = 0.220 BTC
Notional: 0.220 × $42,500 = $9,350
```

---

## Complete Trade Example

### Setup
```
Balance: $10,000
Symbol: BTCUSDT
Leverage: 100x
```

### Step 1: Impulse Detected (4H)
```
4H Candle closes at 12:00 UTC:
- Open: $40,000
- High: $42,500
- Low: $40,000
- Close: $42,400
- Volume: 18,000 BTC (Avg: 10,000 BTC)

ATR(14): $1,400
Body: $2,400 (1.71 × ATR) ✅
Body Ratio: 96% ✅
Direction: BULLISH ✅

🔥 IMPULSE DETECTED!
```

### Step 2: Consolidation (1H)
```
1H Candles after impulse (12:00-17:00):
- 13:00: $42,200 (high) - $41,800 (low)
- 14:00: $42,100 - $41,900
- 15:00: $42,300 - $42,000
- 16:00: $42,400 - $42,100
- 17:00: $42,350 - $42,000

Consolidation: 5 candles
Range: $41,800 - $42,400 ($600 range)
```

### Step 3: Breakout (1H)
```
18:00 Candle:
- Open: $42,300
- High: $42,900
- Low: $42,200
- Close: $42,700 (ABOVE $42,500 impulse high ✅)

EMA12: $42,100
EMA21: $41,500
EMA12 > EMA21 ✅

🎯 BREAKOUT CONFIRMED!
```

### Step 4: Quality Scoring
```
A. Impulse Strength (Body 96%): +2
B. Volume (18k vs 10k avg): +2
C. Trend Alignment (strong uptrend): +2
D. Entry Timing (6 hours): +1
E. Consolidation Quality (24%): +2

Total Score: 9/10 ✅
```

### Step 5: Position Sizing
```
Quality Score: 9 → RR: 8.0x, Risk: 2.0%

Risk Amount: $10,000 × 0.02 = $200

Entry: $42,500
Stop Loss: $41,800 × 0.995 = $41,591
Risk per unit: $909

Position Size: $200 / $909 = 0.220 BTC
Notional: 0.220 × $42,500 = $9,350
```

### Step 6: Trade Execution
```
✅ TRADE OPENED:
Direction: LONG
Entry: $42,500
Stop Loss: $41,591
Take Profit: $49,772 (8.0 RR)
Size: 0.220 BTC
Notional: $9,350
Risk: $200 (2.0%)
Potential Reward: $1,600 (16.0% of balance!)
```

---

## Key Differences: Backtest vs Live Bot

### Backtest (IMPULSE_CANDLES/final_production_backtest_v2.py)
```python
# Uses full dataset with known close times
impulse_candle = htf_df.iloc[idx]
impulse_close_time = impulse_candle['Close time']

# Entry can be found immediately
entry = entry_strategy.find_entry(...)
```

### Live Bot (PRODUCTION_Q3_LIVE/live_bot.py)
```python
# CRITICAL: Uses iloc[-2] for last CLOSED candle
# iloc[-1] is CURRENT (unclosed) candle from Binance API
last_closed_idx = len(df_4h) - 2
impulse_candle = df_4h.iloc[last_closed_idx]

# Validates entry time > impulse close time
if entry_time < impulse_close_time:
    logger.warning("LOOKAHEAD BIAS DETECTED!")
    return None
```

**Key Points:**
1. ✅ Live bot ALWAYS uses `iloc[-2]` for last closed candle
2. ✅ Live bot VALIDATES entry time to prevent lookahead
3. ✅ Live bot WAITS for consolidation + breakout on fresh data
4. ✅ Live bot NEVER peeks at future candles

---

## Performance Expectations

Based on backtest results (2024-2025):

### BTC
- **Impulses Found**: ~50-100 per year
- **Trades Executed**: ~15-30 per year (after quality filter)
- **Win Rate**: ~45%
- **Average RR**: 4.5x (dynamic)
- **EV per Trade**: ~0.5 R

### Trade Frequency
- **Impulse Frequency**: 1-2 per week
- **Entry Frequency**: 1-2 per month (strict quality filter)
- **Expected Drawdown**: 15-25%
- **Expected Annual Return**: 30-60% (depends on execution)

---

## Risk Management

### Position Limits
```
Max Position: $10,000
Min Notional: $10
Max Concurrent: 1 position
Max Trades/Day: 5
```

### Stop Loss Validation
```
Min SL Distance: 0.3% (prevents too tight)
Max SL Distance: 5.0% (prevents too wide)
```

### Leverage
```
Default: 100x (HIGH RISK!)
Recommended: 10-20x for testing
Note: Higher leverage = smaller position size for same risk %
```

---

## Strategy Edge

1. **Quality Filter**: Eliminates 70-80% of impulses, keeps only best setups
2. **Dynamic RR**: Exceptional setups (8-10) get 8.0 RR, not just 3.0
3. **Variable Risk**: Optimizes capital allocation based on quality
4. **Trend Confirmation**: EMA filter ensures directional bias
5. **NO Lookahead**: Realistic live trading, no future peeking

---

**Strategy designed for low-frequency, high-quality trades with asymmetric risk-reward.**
