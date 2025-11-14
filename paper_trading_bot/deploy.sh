#!/bin/bash
# Paper Trading Bot - Docker Deployment Script

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║      PAPER TRADING BOT - DOCKER DEPLOYMENT                  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Navigate to script directory
cd "$(dirname "$0")"

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if docker-compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: docker-compose is not installed"
    echo "Please install docker-compose: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "🔍 Checking Docker installation..."
echo "   Docker version: $(docker --version)"
echo "   Docker Compose version: $(docker-compose --version)"
echo ""

# Stop existing container if running
echo "🛑 Stopping existing container (if any)..."
docker-compose down 2>/dev/null || true
echo ""

# Remove old image
echo "🗑️  Removing old image (if any)..."
docker rmi paper-trading-bot_paper-trading-bot 2>/dev/null || true
echo ""

# Build new image
echo "🔨 Building new Docker image..."
docker-compose build --no-cache
echo ""

# Start container
echo "🚀 Starting Paper Trading Bot..."
docker-compose up -d
echo ""

# Wait for container to start
echo "⏳ Waiting for container to start..."
sleep 5
echo ""

# Check container status
echo "📊 Container status:"
docker-compose ps
echo ""

# Show logs
echo "📋 Recent logs:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker-compose logs --tail=20
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "✅ Deployment complete!"
echo ""
echo "📁 Signals will be logged to: ./paper_trading_logs/"
echo ""
echo "Commands:"
echo "  View logs:    docker-compose logs -f"
echo "  Stop bot:     docker-compose down"
echo "  Restart bot:  docker-compose restart"
echo "  Check status: docker-compose ps"
echo ""
