#!/bin/bash

# 🌙 Liquidity Sweep Bot Launcher

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║           🌙 LIQUIDITY SWEEP TRADING BOT 🚀                  ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found!"
    echo "📝 Creating .env from template..."
    
    if [ -f env_example.txt ]; then
        cp env_example.txt .env
        echo "✅ .env file created"
        echo ""
        echo "⚠️  IMPORTANT: Edit .env and add your Binance API keys!"
        echo "   nano .env"
        echo ""
        exit 1
    else
        echo "❌ env_example.txt not found!"
        exit 1
    fi
fi

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.8+"
    exit 1
fi

echo "✅ Python found: $(python3 --version)"
echo ""

# Check if requirements are installed
echo "🔍 Checking dependencies..."
pip3 show python-binance &> /dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  Dependencies not installed"
    echo "📦 Installing requirements..."
    pip3 install -r requirements_bot.txt
    echo ""
fi

echo "✅ Dependencies OK"
echo ""

# Create logs directory
mkdir -p logs

echo "🚀 Starting Liquidity Sweep Bot..."
echo "   (Press Ctrl+C to stop)"
echo ""

# Run bot
python3 liquidity_sweep_bot.py

