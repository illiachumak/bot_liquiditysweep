#!/bin/bash
# Start Paper Trading Bot

cd "$(dirname "$0")"

echo "🚀 Starting Paper Trading Bot..."
docker-compose up -d

echo "✅ Bot started!"
echo ""
echo "View logs: docker-compose logs -f"
docker-compose ps
