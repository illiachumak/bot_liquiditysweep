#!/bin/bash
# Alternative way to run bot - passing env vars directly (without .env file)

echo "============================================================"
echo "🚀 Starting Liquidity Sweep Bot (Manual Env Vars)"
echo "============================================================"

# Load from .env if exists
if [ -f .env ]; then
    source .env
    echo "✅ Loaded variables from .env"
else
    echo "⚠️  No .env file found, please set variables manually"
fi

# Check if variables are set
if [ -z "$BINANCE_API_KEY" ] || [ -z "$BINANCE_API_SECRET" ]; then
    echo "❌ ERROR: Required variables not set!"
    echo ""
    echo "Please set them:"
    echo "export BINANCE_API_KEY='your_key'"
    echo "export BINANCE_API_SECRET='your_secret'"
    echo "export BINANCE_TESTNET='True'"
    exit 1
fi

echo ""
echo "📋 Configuration:"
echo "  API Key: ${BINANCE_API_KEY:0:10}...${BINANCE_API_KEY: -5}"
echo "  Testnet: ${BINANCE_TESTNET:-True}"
echo ""

# Stop old container if exists
echo "🛑 Stopping old container..."
docker stop liquidity-sweep-bot 2>/dev/null
docker rm liquidity-sweep-bot 2>/dev/null

echo "🚀 Starting bot..."

# Run with environment variables passed directly
docker run -d --name liquidity-sweep-bot \
  -e BINANCE_API_KEY="$BINANCE_API_KEY" \
  -e BINANCE_API_SECRET="$BINANCE_API_SECRET" \
  -e BINANCE_TESTNET="${BINANCE_TESTNET:-True}" \
  -e SYMBOL="${SYMBOL:-BTCUSDT}" \
  -e TIMEFRAME="${TIMEFRAME:-4h}" \
  -e RISK_PER_TRADE="${RISK_PER_TRADE:-2.0}" \
  -e LOG_LEVEL="${LOG_LEVEL:-INFO}" \
  -v $(pwd)/logs:/app/logs \
  liquidity-sweep-bot

if [ $? -eq 0 ]; then
    echo ""
    echo "============================================================"
    echo "✅ Bot started successfully!"
    echo "============================================================"
    echo ""
    echo "View logs:"
    echo "  docker logs -f liquidity-sweep-bot"
    echo ""
    echo "Stop bot:"
    echo "  docker stop liquidity-sweep-bot"
    echo ""
else
    echo "❌ Failed to start bot!"
    exit 1
fi

