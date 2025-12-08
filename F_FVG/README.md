# FVG Strategy Backtest - No Look-Ahead Bias

Comprehensive backtesting framework for 4H Fair Value Gap (FVG) trading strategies with strict timing controls.

## Critical Fix: Look-Ahead Bias Elimination

### The Problem
The original 4H FVG strategy had a critical look-ahead bias:
- A 4H candle timestamped `12:00` means it **OPENED** at 12:00, not closed
- The candle closes at `16:00` (4 hours later)
- **Cannot trade on candle data until it has CLOSED**

### The Solution
This backtest implements strict timing controls:
1. **Candle timestamp = open time**, not close time
2. **FVG detection** only uses closed candles
3. **Trading decisions** can only use information available at decision time
4. **Rejection/Hold events** tracked with `action_available_time`
5. **Lookahead bias check** before every trade execution

Example:
```
4H Candle: timestamp=12:00 → opens at 12:00, closes at 16:00
Cannot trade based on this candle until 16:00!
```

## Strategy Variations

### 1. FAILED FVG (Rejection-based)
Price enters FVG zone then **rejects** (closes outside zone)

**Trading Logic:**
- BULLISH FVG rejection → Price closed **below** zone → **SHORT**
  - Entry: 15M FVG top or breakout
  - SL: Above highest high inside 4H FVG zone
  - Direction: SHORT (continuation down)

- BEARISH FVG rejection → Price closed **above** zone → **LONG**
  - Entry: 15M FVG bottom or breakout
  - SL: Below lowest low inside 4H FVG zone
  - Direction: LONG (continuation up)

### 2. HELD FVG (Continuation-based)
Price enters FVG zone and **holds** (closes inside zone)

**Trading Logic:**
- BULLISH FVG held → Price closed **inside** zone → **LONG**
  - Entry: Immediate or 15M FVG bottom
  - SL: Below lowest low inside 4H FVG zone
  - Direction: LONG (bullish continuation)

- BEARISH FVG held → Price closed **inside** zone → **SHORT**
  - Entry: Immediate or 15M FVG top
  - SL: Above highest high inside 4H FVG zone
  - Direction: SHORT (bearish continuation)

## Entry Methods

### A. Immediate (4H close)
- **Type:** Market order
- **Entry:** At 4H close price when rejection/hold confirmed
- **Pros:** Guaranteed fill, immediate execution
- **Cons:** Market order fees (0.045%)
- **Use case:** When certainty is more important than price

### B. 15M FVG
- **Type:** Limit order
- **Entry:** At 15M FVG zone boundary
- **Expiry:** 16 candles (4 hours)
- **Pros:** Better entry price, maker fees (0.018%)
- **Cons:** May not fill
- **Use case:** Patient entries with better risk/reward

### C. 15M Breakout
- **Type:** Limit order
- **Entry:** At breakout level from 4H hold/rejection candle
- **Expiry:** 16 candles (4 hours)
- **Pros:** Confirmation of momentum
- **Cons:** Later entry, may miss move
- **Use case:** Conservative entries

## TP Methods

### 1. Liquidity-based
- Finds nearest swing high/low (resistance/support)
- Min RR: 1.5
- Max RR: 10.0 (capped)
- Dynamic based on market structure

### 2. Fixed RR 2.0
- TP = Entry + (2 × Risk)
- Consistent 2:1 risk/reward
- Predictable outcomes

### 3. Fixed RR 3.0
- TP = Entry + (3 × Risk)
- Higher risk/reward
- Lower win rate expected

## Configuration Matrix

**Total combinations:** 2 strategies × 3 entry methods × 3 TP methods = **18 configurations**

| Strategy | Entry Methods | TP Methods | Total |
|----------|--------------|------------|-------|
| FAILED   | 4h_close, 15m_fvg, 15m_breakout | liquidity, rr_2.0, rr_3.0 | 9 |
| HELD     | 4h_close, 15m_fvg, 15m_breakout | liquidity, rr_2.0, rr_3.0 | 9 |

## Backtest Parameters

```python
initial_balance = 10000.0       # Starting capital
risk_per_trade = 0.02           # 2% risk per trade
min_rr = 2.0                    # Minimum risk/reward
min_sl_pct = 0.3                # Minimum 0.3% SL
max_sl_pct = 5.0                # Maximum 5% SL
enable_fees = True              # Include Binance fees
limit_expiry_candles = 16       # 4H expiry for limit orders
```

## Fee Structure (Binance)

- **Maker fee:** 0.018% (limit orders)
- **Taker fee:** 0.045% (market orders)

Entry fees:
- 4H close → Taker (0.045%)
- 15M FVG → Maker (0.018%)
- 15M breakout → Maker (0.018%)

Exit fees:
- TP → Maker (0.018%)
- SL → Taker (0.045%)

## Usage

### Run Full Backtest
```bash
cd F_FVG
python run_comprehensive_backtest.py
```

This will:
1. Test all 18 configurations
2. Across 3 periods (2023, 2024, 2025)
3. Generate detailed results
4. Save JSON output files
5. Print comparison tables

### Output Files
```
F_FVG/
├── backtest_results_2023_TIMESTAMP.json
├── backtest_results_2024_TIMESTAMP.json
└── backtest_results_2025_TIMESTAMP.json
```

## Results Interpretation

### Key Metrics
- **Total Trades:** Number of completed trades
- **Win Rate:** Percentage of profitable trades
- **Total PnL:** Net profit/loss after fees
- **PnL %:** Return on initial balance
- **Max Drawdown:** Largest peak-to-trough decline
- **Profit Factor:** Gross profit / Gross loss
- **Avg RR:** Average risk/reward ratio

### What to Look For
✅ **Profitable configs:** PnL > 0, Profit Factor > 1.5
✅ **Consistent winners:** Positive across multiple periods
✅ **Reasonable drawdown:** Max DD < 20%
✅ **Adequate sample size:** 20+ trades per year
✅ **Win rate alignment:**
   - RR 2.0 → expect ~50%+ win rate
   - RR 3.0 → expect ~40%+ win rate

⚠️ **Warning signs:**
- Very high win rate (>80%) → possible overfitting
- Very low trades (<10/year) → insufficient data
- Extreme drawdown (>30%) → risky
- Inconsistent across periods → not robust

## Validation Checks

The backtest includes automatic validation:

1. **Lookahead bias check:**
   ```python
   if entry_time < fvg.action_available_time:
       raise ValueError("LOOKAHEAD BIAS DETECTED!")
   ```

2. **Timing verification:**
   - FVG formed_time = candle close time
   - action_available_time = when rejection/hold confirmed
   - No trading before information is available

3. **Data integrity:**
   - Only closed candles used
   - Exclude last candle (may be unclosed)
   - Sequential processing

## Next Steps

After running backtests:

1. **Identify best configs:** Top 3-5 by total PnL
2. **Check consistency:** Profitable across all periods?
3. **Analyze drawdowns:** Acceptable risk levels?
4. **Review trade log:** Any patterns in wins/losses?
5. **Forward test:** Paper trade best config
6. **Optimize:** Fine-tune parameters if needed

## Notes

- Uses historical BTC/USDT data
- 4H and 15M timeframes required
- CSV data format expected (from Binance)
- All times in UTC
- No leverage (spot trading simulation)

## Disclaimer

This backtest is for educational purposes only. Past performance does not guarantee future results. Always test strategies thoroughly before risking real capital.
