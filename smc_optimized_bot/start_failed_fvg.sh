#!/bin/bash

# Failed 4H FVG Bot Startup Script

echo "======================================"
echo "Failed 4H FVG Bot - Starting..."
echo "======================================"

# Check if running in dry run or real mode
DRY_RUN="${DRY_RUN:-true}"

if [ "$DRY_RUN" = "true" ]; then
    echo "Mode: DRY RUN (Simulation)"
    echo "No real orders will be placed."
else
    echo "Mode: REAL MODE"

    # Check for API keys
    if [ -z "$BINANCE_API_KEY" ] || [ -z "$BINANCE_API_SECRET" ]; then
        echo "ERROR: BINANCE_API_KEY and BINANCE_API_SECRET must be set for real mode"
        echo "Usage:"
        echo "  export BINANCE_API_KEY='your_key'"
        echo "  export BINANCE_API_SECRET='your_secret'"
        echo "  export DRY_RUN=false"
        echo "  ./start_failed_fvg.sh"
        exit 1
    fi

    echo "WARNING: Real orders will be placed on Binance testnet!"
    echo "Press CTRL+C in 5 seconds to cancel..."
    sleep 5
fi

echo ""
echo "Strategy: Failed 4H FVG"
echo "Timeframes: 4H analysis, 15M execution"
echo "Min RR: 2.0"
echo "Min SL: 0.3%"
echo ""

# Create logs directory
mkdir -p logs

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Run the bot
echo "Starting bot..."
python3 failed_fvg_strategy.py

echo ""
echo "Bot stopped."
