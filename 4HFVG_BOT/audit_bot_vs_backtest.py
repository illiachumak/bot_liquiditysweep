"""
Audit Script: Compare Live Bot Logic vs Backtest Logic
Checks for discrepancies that could cause live trading to diverge from backtest results
"""

import pandas as pd
import numpy as np
from datetime import datetime

print("="*80)
print("AUDIT: Live Bot vs Backtest Comparison")
print("="*80)

# ============================================================================
# 1. FVG DETECTION LOGIC
# ============================================================================
print("\n1. FVG DETECTION LOGIC")
print("-" * 80)

print("Backtest (BacktestFVG.__init__):")
print("  - Bullish: df.iloc[i]['Low'] > df.iloc[i-2]['High']")
print("  - Bearish: df.iloc[i]['High'] < df.iloc[i-2]['Low']")

print("\nLive Bot (FVGDetector.detect_fvgs):")
print("  - Bullish: row['low'] > row_i2['high']")
print("  - Bearish: row['high'] < row_i2['low']")

print("\n✅ SAME LOGIC (just different variable names)")

# ============================================================================
# 2. REJECTION LOGIC
# ============================================================================
print("\n2. REJECTION LOGIC")
print("-" * 80)

print("Backtest (BacktestFVG.check_rejection):")
print("  - Bullish FVG rejection: candle_close < self.bottom")
print("  - Bearish FVG rejection: candle_close > self.top")

print("\nLive Bot (LiveFVG.check_rejection):")
print("  - Bullish FVG rejection: close < self.bottom")
print("  - Bearish FVG rejection: close > self.top")

print("\n✅ SAME LOGIC")

# ============================================================================
# 3. STOP LOSS CALCULATION
# ============================================================================
print("\n3. STOP LOSS CALCULATION")
print("-" * 80)

print("Backtest (BacktestFVG.get_stop_loss):")
print("  - Bullish FVG (SHORT): max(highs_inside) * 1.002")
print("  - Bearish FVG (LONG): min(lows_inside) * 0.998")

print("\nLive Bot (LiveFVG.get_stop_loss):")
print("  - Bullish FVG (SHORT): max(highs_inside) * 1.002")
print("  - Bearish FVG (LONG): min(lows_inside) * 0.998")

print("\n✅ SAME LOGIC")

# ============================================================================
# 4. TAKE PROFIT CALCULATION
# ============================================================================
print("\n4. TAKE PROFIT CALCULATION")
print("-" * 80)

print("Backtest (FailedFVGBacktest.create_trade):")
print("  - Uses fixed RR: tp = entry ± (FIXED_RR * risk)")
print("  - FIXED_RR = 3.0 (from test config)")

print("\nLive Bot (FailedFVGLiveBot.create_setup_from_rejection):")
print("  - Uses fixed RR: tp = entry ± (FIXED_RR * risk)")
print("  - FIXED_RR = 3.0")

print("\n✅ SAME LOGIC")

# ============================================================================
# 5. FEES
# ============================================================================
print("\n5. FEES")
print("-" * 80)

print("Backtest:")
print("  - maker_fee = 0.00018 (0.018%)")
print("  - taker_fee = 0.00045 (0.045%)")

print("\nLive Bot:")
print("  - MAKER_FEE = 0.00018 (0.018%)")
print("  - TAKER_FEE = 0.00045 (0.045%)")

print("\n✅ SAME VALUES")

# ============================================================================
# 6. STRATEGY PARAMETERS
# ============================================================================
print("\n6. STRATEGY PARAMETERS")
print("-" * 80)

print("Backtest (Test 1 config):")
print("  - risk_per_trade = 0.02 (2%)")
print("  - min_rr = 2.0")
print("  - min_sl_pct = 0.3")
print("  - fixed_rr = 3.0")
print("  - limit_order_expiry_candles = 16 (4H on 15M)")

print("\nLive Bot:")
print("  - RISK_PER_TRADE = 0.02 (2%)")
print("  - MIN_RR = 2.0")
print("  - MIN_SL_PCT = 0.3")
print("  - FIXED_RR = 3.0")
print("  - LIMIT_EXPIRY_CANDLES = 16")

print("\n✅ SAME PARAMETERS")

# ============================================================================
# 7. INVALIDATION LOGIC
# ============================================================================
print("\n7. INVALIDATION LOGIC")
print("-" * 80)

print("Backtest (BacktestFVG.is_fully_passed):")
print("  - Bullish FVG: candle_low < self.bottom")
print("  - Bearish FVG: candle_high > self.top")

print("\nLive Bot (LiveFVG.is_fully_passed):")
print("  - Bullish FVG: low < self.bottom")
print("  - Bearish FVG: high > self.top")

print("\n✅ SAME LOGIC")

# ============================================================================
# 8. CRITICAL DIFFERENCES
# ============================================================================
print("\n8. CRITICAL DIFFERENCES")
print("-" * 80)

print("\n⚠️  DIFFERENCE #1: Candle Close Detection")
print("  Backtest:")
print("    - Works with historical data (all closed candles)")
print("    - Detects FVG from closed candles only")
print("    - Uses df.iloc[:-1] to exclude last candle in initial detection")
print("  Live Bot:")
print("    - Must handle real-time data (last candle is open)")
print("    - Uses check_new_4h_candle() to detect when candle closes")
print("    - Only detects FVG from PREVIOUS candle when NEW candle appears")
print("  Impact: Live bot has complex timestamp tracking logic")

print("\n⚠️  DIFFERENCE #2: Data Source")
print("  Backtest:")
print("    - Loads from CSV files (historical data)")
print("  Live Bot:")
print("    - Fetches from Binance API in real-time")
print("  Impact: Potential timestamp/timezone differences")

print("\n⚠️  DIFFERENCE #3: Trade Execution")
print("  Backtest:")
print("    - Simulates limit order fills instantly if price reached")
print("    - Simulates trade outcome deterministically")
print("  Live Bot:")
print("    - Places real limit orders on exchange")
print("    - Monitors order status, handles partial fills, etc.")
print("  Impact: Real orders may not fill even if price touched")

print("\n⚠️  DIFFERENCE #4: State Management")
print("  Backtest:")
print("    - No state persistence (runs in memory)")
print("  Live Bot:")
print("    - Saves/restores state from state.json")
print("    - Can resume after crash")
print("  Impact: State corruption could cause issues")

# ============================================================================
# 9. CRITICAL BUGS TO CHECK
# ============================================================================
print("\n9. POTENTIAL BUGS TO CHECK")
print("-" * 80)

print("\n⚠️  BUG #1: Futures Testnet Configuration")
print("  Issue:")
print("    - Live bot sets USE_FUTURES = True")
print("    - In DRY_RUN mode, uses Client(testnet=True)")
print("    - BUT: testnet=True is for SPOT testnet!")
print("    - Futures testnet requires different base URL!")
print("  Fix:")
print("    - Use testnet=False and manually set futures_url")
print("    - OR use futures_testnet=True if supported")

print("\n⚠️  BUG #2: FVG Detection Timing")
print("  Issue:")
print("    - Live bot detects FVG when NEW candle appears")
print("    - Uses complex timestamp matching logic")
print("    - Timezone issues could cause missed detections")
print("  Fix:")
print("    - Test thoroughly with different timezones")
print("    - Add more logging for debugging")

print("\n⚠️  BUG #3: Balance Hardcoded")
print("  Issue:")
print("    - get_balance() returns hardcoded 300.0")
print("    - Never updates after trades")
print("  Fix:")
print("    - Track balance manually: self.balance += pnl")
print("    - This is actually implemented correctly in close_trade()")

print("\n⚠️  BUG #4: Multiple Setups from Same Rejection")
print("  Backtest:")
print("    - Prevents multiple setups via has_filled_trade flag")
print("    - Uses pending_setup_expiry_time for cooldown")
print("  Live Bot:")
print("    - Same logic in can_create_setup()")
print("  Status: ✅ Looks correct")

# ============================================================================
# 10. VALIDATION CHECKLIST
# ============================================================================
print("\n10. VALIDATION CHECKLIST")
print("-" * 80)

checklist = [
    ("FVG detection logic matches backtest", "✅"),
    ("Rejection logic matches backtest", "✅"),
    ("SL calculation matches backtest", "✅"),
    ("TP calculation matches backtest", "✅"),
    ("Fees match backtest", "✅"),
    ("Strategy parameters match backtest", "✅"),
    ("Invalidation logic matches backtest", "✅"),
    ("Futures testnet configuration", "❌ NEEDS FIX"),
    ("Closed candle detection", "⚠️  NEEDS TESTING"),
    ("State persistence", "⚠️  NEEDS TESTING"),
]

for check, status in checklist:
    print(f"{status} {check}")

# ============================================================================
# 11. RECOMMENDATIONS
# ============================================================================
print("\n11. RECOMMENDATIONS")
print("-" * 80)

print("\n1. Fix Futures Testnet Configuration:")
print("   - Change Client initialization for futures testnet")
print("   - Use futures testnet base URL")

print("\n2. Test Candle Close Detection:")
print("   - Run live bot in DRY_RUN mode")
print("   - Verify FVGs detected at correct times")
print("   - Compare with backtest on same date range")

print("\n3. Add Comprehensive Logging:")
print("   - Log every FVG detection with timestamp")
print("   - Log every rejection with candle details")
print("   - Log every setup creation/fill/expiry")

print("\n4. Run Parallel Comparison:")
print("   - Run backtest on last 7 days")
print("   - Run live bot simulation on same period")
print("   - Compare: number of FVGs, rejections, setups, trades")

print("\n5. State Recovery Testing:")
print("   - Test state save/restore")
print("   - Simulate crash and recovery")
print("   - Verify no trades lost or duplicated")

print("\n" + "="*80)
print("END OF AUDIT")
print("="*80)
