#!/bin/bash
# Quick check for .env file configuration

echo "============================================================"
echo "🔍 Checking .env file configuration"
echo "============================================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ ERROR: .env file not found!"
    echo ""
    echo "Please create .env file with:"
    echo "BINANCE_TESTNET=True"
    echo "BINANCE_API_KEY=your_key_here"
    echo "BINANCE_API_SECRET=your_secret_here"
    exit 1
fi

echo "✅ .env file exists"
echo ""

# Check if .env is readable
if [ ! -r .env ]; then
    echo "❌ ERROR: .env file is not readable!"
    echo "Fix with: chmod 644 .env"
    exit 1
fi

echo "✅ .env file is readable"
echo ""

# Check required variables
echo "📋 Checking environment variables:"
echo ""

source .env

if [ -z "$BINANCE_API_KEY" ]; then
    echo "❌ BINANCE_API_KEY: NOT SET"
else
    KEY_LENGTH=${#BINANCE_API_KEY}
    echo "✅ BINANCE_API_KEY: SET (length: $KEY_LENGTH chars)"
    echo "   Preview: ${BINANCE_API_KEY:0:10}...${BINANCE_API_KEY: -5}"
fi

if [ -z "$BINANCE_API_SECRET" ]; then
    echo "❌ BINANCE_API_SECRET: NOT SET"
else
    SECRET_LENGTH=${#BINANCE_API_SECRET}
    echo "✅ BINANCE_API_SECRET: SET (length: $SECRET_LENGTH chars)"
    echo "   Preview: ${BINANCE_API_SECRET:0:10}...${BINANCE_API_SECRET: -5}"
fi

if [ -z "$BINANCE_TESTNET" ]; then
    echo "⚠️  BINANCE_TESTNET: NOT SET (will default to True)"
else
    echo "✅ BINANCE_TESTNET: $BINANCE_TESTNET"
fi

echo ""
echo "============================================================"

if [ -n "$BINANCE_API_KEY" ] && [ -n "$BINANCE_API_SECRET" ]; then
    echo "✅ All required variables are set!"
    echo ""
    echo "You can start the bot with:"
    echo "docker run -d --name liquidity-sweep-bot \\"
    echo "  --env-file .env \\"
    echo "  -v \$(pwd)/logs:/app/logs \\"
    echo "  liquidity-sweep-bot"
else
    echo "❌ Some required variables are missing!"
    echo ""
    echo "Please edit .env file and add missing variables"
fi

echo "============================================================"

