#!/bin/bash

# 🔄 Restart SMC Optimized Bot

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║            🔄 RESTARTING SMC OPTIMIZED BOT                    ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if docker compose is available
if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    echo -e "${YELLOW}❌ Docker Compose not found${NC}"
    exit 1
fi

# Restart the bot
echo -e "${CYAN}Restarting bot...${NC}"
if $COMPOSE_CMD restart; then
    echo -e "${GREEN}✅ Bot restarted successfully${NC}"
else
    echo -e "${YELLOW}⚠️  Bot might not be running, trying to start...${NC}"
    $COMPOSE_CMD up -d
fi

# Wait a moment
sleep 2

# Show status
echo -e "\n${CYAN}Bot status:${NC}"
$COMPOSE_CMD ps

# Show logs (last 20 lines)
echo -e "\n${CYAN}Recent logs:${NC}"
$COMPOSE_CMD logs --tail=20

echo -e "\n${GREEN}Bot restarted!${NC}"

