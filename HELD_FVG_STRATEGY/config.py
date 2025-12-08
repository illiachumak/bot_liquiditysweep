"""
Configuration for HELD FVG Live Trading Bot
Strategy: 4h_close + rr_3.0_liq (Binance Futures)
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

# Risk per trade (% of balance)
RISK_PER_TRADE = 0.02  # 2%

# Stop Loss limits
MIN_SL_PCT = 0.003  # 0.3% minimum SL distance
MAX_SL_PCT = 0.05   # 5.0% maximum SL distance

# =============================================================================
# STRATEGY CONFIGURATION
# =============================================================================

# Entry method (fixed for this bot)
ENTRY_METHOD = "4h_close"

# TP method (fixed for this bot)
TP_METHOD = "rr_3.0_liq"

# Liquidity detection parameters
LIQUIDITY_LOOKBACK = 50  # Number of candles to look back for liquidity
LIQUIDITY_MIN_RR = 2.5   # Minimum risk-reward ratio
LIQUIDITY_MAX_RR = 5.0   # Maximum risk-reward ratio (cap)

# Minimum notional
MIN_NOTIONAL_USDT = 10.0

# =============================================================================
# SAFETY LIMITS
# =============================================================================

# Maximum position size (USDT)
MAX_POSITION_SIZE_USDT = 1000.0

# Maximum number of concurrent positions
MAX_CONCURRENT_POSITIONS = 1

# Maximum trades per day (to prevent spam in case of bugs)
MAX_TRADES_PER_DAY = 5

# =============================================================================
# BOT BEHAVIOR
# =============================================================================

# Polling interval (seconds)
POLL_INTERVAL = 60  # Check every 60 seconds for 4H candle close

# Candle interval
CANDLE_INTERVAL = "4h"

# Historical candles to fetch for FVG detection
HISTORICAL_CANDLES_4H = 100  # Last 100 x 4H candles (~16 days)

# Historical 15M candles for liquidity detection
HISTORICAL_CANDLES_15M = 200  # Last 200 x 15M candles (~50 hours)

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

def print_config():
    """Print configuration (hide sensitive data)"""
    print("="*80)
    print("HELD FVG LIVE BOT CONFIGURATION")
    print("="*80)
    print(f"Symbol: {SYMBOL}")
    print(f"Leverage: {LEVERAGE}x")
    print(f"Risk per Trade: {RISK_PER_TRADE*100}%")
    print(f"SL Range: {MIN_SL_PCT*100}% - {MAX_SL_PCT*100}%")
    print(f"")
    print(f"Strategy: {ENTRY_METHOD} + {TP_METHOD}")
    print(f"Liquidity RR Range: {LIQUIDITY_MIN_RR} - {LIQUIDITY_MAX_RR}")
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
