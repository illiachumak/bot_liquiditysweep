"""
Configuration for PRODUCTION_Q3_DynamicRR_VariableRisk Live Trading Bot
Strategy: Impulse Breakout + Dynamic RR + Variable Risk (Binance Futures)

CRITICAL: This strategy uses dynamic RR and variable risk based on quality score!
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =============================================================================
# BINANCE API CREDENTIALS
# =============================================================================

BINANCE_API_KEY = os.getenv('BINANCE_API_KEY', '')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET', '')

if not BINANCE_API_KEY or not BINANCE_API_SECRET:
    raise ValueError("BINANCE_API_KEY and BINANCE_API_SECRET must be set in .env file!")

# =============================================================================
# TRADING CONFIGURATION
# =============================================================================

# Symbol
SYMBOL = "BTCUSDT"

# Leverage (1x-125x)
LEVERAGE = 100

# Base risk per trade (% of balance) - will be adjusted by quality category
# This is the BASE risk, actual risk is determined by RISK_BY_CATEGORY
BASE_RISK_PER_TRADE = 0.015  # 1.5%

# Stop Loss limits
MIN_SL_PCT = 0.003  # 0.3% minimum SL distance
MAX_SL_PCT = 0.05   # 5.0% maximum SL distance

# =============================================================================
# STRATEGY CONFIGURATION - PRODUCTION_Q3
# =============================================================================

# Impulse Detection (ATR-Based)
IMPULSE_ATR_MULTIPLIER = 1.5
IMPULSE_BODY_RATIO = 0.70
IMPULSE_ATR_PERIOD = 14

# Entry Strategy (Breakout)
ENTRY_METHOD = "breakout"
CONSOLIDATION_MIN = 3
CONSOLIDATION_MAX = 20
STOP_BUFFER_PCT = 0.5  # 0.5% buffer for stop loss

# EMA Filter (for trend confirmation on 1H)
EMA_SHORT_PERIOD = 12
EMA_LONG_PERIOD = 21
EMA_LOOKBACK = 5  # Number of candles to check for respect

# Quality Scoring
MIN_QUALITY_SCORE = 3  # Minimum score to take trade (3-10)

# Dynamic RR Mapping (Quality Score -> RR Ratio)
# Format: (min_score, max_score): rr_ratio
RR_MAPPING = {
    (8, 10): 8.0,   # High quality: 8.0 RR
    (6, 7): 3.5,    # Good quality: 3.5 RR
    (4, 5): 3.0,    # Medium quality: 3.0 RR
    (3, 3): 2.5,    # Low quality: 2.5 RR
    (0, 2): None    # Filtered out
}

# Variable Risk by Quality Category (% of balance)
RISK_BY_CATEGORY = {
    '8-10': 2.0,   # High quality: 2.0% risk
    '6-7': 1.5,    # Good quality: 1.5% risk
    '4-5': 1.5,    # Medium quality: 1.5% risk
    '3': 2.0       # Low quality but acceptable: 2.0% risk
}

# =============================================================================
# SAFETY LIMITS
# =============================================================================

# Maximum position size (USDT)
MAX_POSITION_SIZE_USDT = 10000.0

# Minimum notional
MIN_NOTIONAL_USDT = 10.0

# Maximum number of concurrent positions
MAX_CONCURRENT_POSITIONS = 1

# Maximum trades per day (to prevent spam in case of bugs)
MAX_TRADES_PER_DAY = 5

# =============================================================================
# BOT BEHAVIOR
# =============================================================================

# Polling interval (seconds)
POLL_INTERVAL = 60  # Check every 60 seconds for 4H candle close

# HTF timeframe (4H for impulse detection)
HTF_INTERVAL = "4h"
HTF_INTERVAL_BINANCE = "4h"

# LTF timeframe (1H for entry)
LTF_INTERVAL = "1h"
LTF_INTERVAL_BINANCE = "1h"

# Historical candles to fetch
HISTORICAL_CANDLES_4H = 100  # Last 100 x 4H candles (~16 days)
HISTORICAL_CANDLES_1H = 200  # Last 200 x 1H candles (~8 days)

# =============================================================================
# LOGGING
# =============================================================================

LOG_LEVEL = "INFO"  # INFO, WARNING, ERROR

# Log format
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# =============================================================================
# PERSISTENCE
# =============================================================================

# State file for tracking trades (in case of restart)
STATE_FILE = "bot_state.json"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_rr_for_score(score: int) -> float:
    """Get RR ratio for given quality score"""
    for (min_s, max_s), rr in RR_MAPPING.items():
        if rr is not None and min_s <= score <= max_s:
            return rr
    return None

def get_risk_for_score(score: int) -> float:
    """Get risk % for given quality score"""
    if score >= 8:
        return RISK_BY_CATEGORY['8-10']
    elif score >= 6:
        return RISK_BY_CATEGORY['6-7']
    elif score >= 4:
        return RISK_BY_CATEGORY['4-5']
    elif score >= 3:
        return RISK_BY_CATEGORY['3']
    else:
        return None  # Filtered out

def print_config():
    """Print configuration (hide sensitive data)"""
    print("="*80)
    print("PRODUCTION_Q3_DynamicRR_VariableRisk LIVE BOT CONFIGURATION")
    print("="*80)
    print(f"Symbol: {SYMBOL}")
    print(f"Leverage: {LEVERAGE}x")
    print(f"Base Risk: {BASE_RISK_PER_TRADE*100}%")
    print(f"SL Range: {MIN_SL_PCT*100}% - {MAX_SL_PCT*100}%")
    print(f"")
    print(f"Strategy: Impulse Breakout + Dynamic RR + Variable Risk")
    print(f"HTF: {HTF_INTERVAL} | LTF: {LTF_INTERVAL}")
    print(f"Impulse: ATR {IMPULSE_ATR_MULTIPLIER}x, Body {IMPULSE_BODY_RATIO*100}%")
    print(f"Entry: {ENTRY_METHOD.upper()}")
    print(f"Min Quality Score: {MIN_QUALITY_SCORE}")
    print(f"")
    print(f"Dynamic RR Mapping:")
    for (min_s, max_s), rr in RR_MAPPING.items():
        if rr is not None:
            print(f"  Score {min_s}-{max_s}: {rr}x RR")
    print(f"")
    print(f"Variable Risk by Category:")
    for cat, risk in RISK_BY_CATEGORY.items():
        print(f"  {cat}: {risk}%")
    print(f"")
    print(f"Max Position Size: ${MAX_POSITION_SIZE_USDT}")
    print(f"Max Concurrent Positions: {MAX_CONCURRENT_POSITIONS}")
    print(f"Max Trades/Day: {MAX_TRADES_PER_DAY}")
    print(f"")
    print(f"Poll Interval: {POLL_INTERVAL}s")
    print(f"API Key: {'*' * 20}{BINANCE_API_KEY[-4:] if len(BINANCE_API_KEY) > 4 else '****'}")
    print("="*80)


if __name__ == "__main__":
    print_config()
