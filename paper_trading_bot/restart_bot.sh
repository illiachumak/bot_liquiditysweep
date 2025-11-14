#!/bin/bash
# Restart Paper Trading Bot

cd "$(dirname "$0")"

echo "🔄 Restarting Paper Trading Bot..."
docker-compose restart

echo "✅ Bot restarted!"
echo ""
echo "View logs: docker-compose logs -f"
docker-compose ps
