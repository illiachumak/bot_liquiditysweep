#!/bin/bash
# Stop Paper Trading Bot

cd "$(dirname "$0")"

echo "🛑 Stopping Paper Trading Bot..."
docker-compose down

echo "✅ Bot stopped!"
