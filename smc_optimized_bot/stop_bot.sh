#!/bin/bash

# 🛑 Stop SMC Optimized Bot

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║              🛑 STOPPING SMC OPTIMIZED BOT                    ║"
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

# Stop the bot
echo -e "${CYAN}Stopping bot...${NC}"
if $COMPOSE_CMD stop; then
    echo -e "${GREEN}✅ Bot stopped successfully${NC}"
else
    echo -e "${YELLOW}⚠️  Bot might not be running${NC}"
fi

# Show status
echo -e "\n${CYAN}Current status:${NC}"
$COMPOSE_CMD ps

echo -e "\n${GREEN}Bot stopped!${NC}"
echo -e "${CYAN}To start again: ./start_bot.sh${NC}"



