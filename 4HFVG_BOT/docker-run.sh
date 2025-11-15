#!/bin/bash

# Simple Docker launcher for 4H FVG Bot

set -e

cd "$(dirname "$0")"

echo "======================================"
echo "4H FVG Bot - Docker Launcher"
echo "======================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo ""
    echo "Please create .env file:"
    echo "  cp .env.example .env"
    echo "  nano .env  # Add your API keys"
    exit 1
fi

# Create required directories
echo "Creating directories..."
mkdir -p logs

echo "✅ Setup complete"
echo ""
echo "Starting bot with Docker Compose..."
docker-compose up -d

echo ""
echo "✅ Bot started!"
echo ""
echo "Useful commands:"
echo "  docker-compose logs -f       # View logs"
echo "  docker-compose ps            # Check status"
echo "  docker-compose down          # Stop bot"
echo "  docker-compose restart       # Restart bot"
echo ""
