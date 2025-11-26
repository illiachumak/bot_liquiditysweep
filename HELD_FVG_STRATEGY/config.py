"""
Configuration for HELD FVG Live Bot
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =============================================================================
# FEATURE FLAGS
# =============================================================================

# SIMULATION MODE: True = use historical data, False = live trading
SIMULATION_MODE = os.getenv('SIMULATION_MODE', 'True').lower() == 'true'

# =============================================================================
# BINANCE API
# =============================================================================

API_KEY = os.getenv('BINANCE_API_KEY', '')
API_SECRET = os.getenv('BINANCE_API_SECRET', '')
TESTNET = os.getenv('BINANCE_TESTNET', 'False').lower() == 'true'

# =============================================================================
# STRATEGY PARAMETERS (Same as backtest!)
# =============================================================================

# Trading pair
SYMBOL = 'BTCUSDT'

# Timeframes
TIMEFRAME_4H = '4h'
TIMEFRAME_15M = '15m'

# Risk management
INITIAL_BALANCE = 300.0  # Starting balance
RISK_PER_TRADE = 0.02    # 2% risk per trade
MIN_SL_PCT = 0.3         # Min SL distance (%)
MAX_SL_PCT = 5.0         # Max SL distance (%)

# Strategy settings
ENTRY_METHOD = '4h_close'  # Immediate entry on 4H close
TP_METHOD = 'rr_2.0'       # Fixed RR 2.0
FIXED_RR = 2.0

# Fees (Binance futures maker/taker)
MAKER_FEE = 0.00018  # 0.018%
TAKER_FEE = 0.00045  # 0.045%

# =============================================================================
# BOT SETTINGS
# =============================================================================

# Update intervals
CHECK_INTERVAL_4H = 60  # Check 4H candles every 60 seconds
CHECK_INTERVAL_15M = 15  # Check trades every 15 seconds

# Logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = 'logs/held_fvg_bot.log'

# Database (for trade history)
DB_FILE = 'data/held_fvg_trades.db'

# =============================================================================
# SIMULATION MODE SETTINGS
# =============================================================================

# Historical data for simulation
SIMULATION_START_DATE = '2024-01-01'
SIMULATION_END_DATE = '2024-12-31'
SIMULATION_SPEED = 1  # 1 = real-time, >1 = faster

# Data source for simulation
DATA_PATH_4H = '/Users/illiachumak/trading/backtest/data/btc_4h_data_2018_to_2025.csv'
DATA_PATH_15M = '/Users/illiachumak/trading/backtest/data/btc_15m_data_2018_to_2025.csv'

# =============================================================================
# VALIDATION
# =============================================================================

def validate_config():
    """Validate configuration"""
    errors = []

    if not SIMULATION_MODE:
        if not API_KEY or not API_SECRET:
            errors.append("API_KEY and API_SECRET required for live trading")

    if RISK_PER_TRADE <= 0 or RISK_PER_TRADE > 0.1:
        errors.append("RISK_PER_TRADE should be between 0 and 0.1 (10%)")

    if FIXED_RR < 1.0:
        errors.append("FIXED_RR should be >= 1.0")

    if errors:
        raise ValueError(f"Configuration errors:\\n" + "\\n".join(errors))

    return True


# Validate on import
validate_config()


# =============================================================================
# CONFIG SUMMARY
# =============================================================================

def print_config():
    """Print configuration summary"""
    print("=" * 80)
    print("HELD FVG BOT - CONFIGURATION")
    print("=" * 80)
    print(f"")
    print(f"🎯 MODE: {'SIMULATION' if SIMULATION_MODE else 'LIVE TRADING'}")
    print(f"")
    print(f"Symbol: {SYMBOL}")
    print(f"Initial Balance: ${INITIAL_BALANCE:,.2f}")
    print(f"Risk per Trade: {RISK_PER_TRADE * 100}%")
    print(f"")
    print(f"Strategy: {ENTRY_METHOD} + {TP_METHOD}")
    print(f"Fixed RR: {FIXED_RR}")
    print(f"SL Range: {MIN_SL_PCT}% - {MAX_SL_PCT}%")
    print(f"")

    if SIMULATION_MODE:
        print(f"📊 Simulation Settings:")
        print(f"  Period: {SIMULATION_START_DATE} to {SIMULATION_END_DATE}")
        print(f"  Speed: {SIMULATION_SPEED}x")
        print(f"  Data: Local CSV files")
    else:
        print(f"🔴 LIVE TRADING:")
        print(f"  Testnet: {TESTNET}")
        print(f"  ⚠️  REAL MONEY AT RISK!")

    print("=" * 80)
    print()
