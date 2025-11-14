#!/bin/bash

# 🚀 Start SMC Optimized Bot

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║              🚀 STARTING SMC OPTIMIZED BOT                    ║"
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

# Check .env file
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
    if [ -f env_example.txt ]; then
        echo -e "${CYAN}Creating .env from template...${NC}"
        cp env_example.txt .env
        echo -e "${YELLOW}⚠️  Please edit .env and add your API keys${NC}"
        exit 1
    else
        echo -e "${YELLOW}❌ env_example.txt not found${NC}"
        exit 1
    fi
fi

# Start the bot
echo -e "${CYAN}Starting bot in background...${NC}"
if $COMPOSE_CMD up -d; then
    echo -e "${GREEN}✅ Bot started successfully${NC}"
else
    echo -e "${YELLOW}❌ Failed to start bot${NC}"
    exit 1
fi

# Wait a moment
sleep 2

# Show status
echo -e "\n${CYAN}Bot status:${NC}"
$COMPOSE_CMD ps

# Show logs (last 20 lines)
echo -e "\n${CYAN}Recent logs:${NC}"
$COMPOSE_CMD logs --tail=20

echo -e "\n${GREEN}Bot is running!${NC}"
echo -e "${CYAN}Useful commands:${NC}"
echo -e "  ${YELLOW}./stop_bot.sh${NC}              - Stop bot"
echo -e "  ${YELLOW}./restart_bot.sh${NC}           - Restart bot"
echo -e "  ${YELLOW}docker compose logs -f${NC}     - View live logs"
echo -e "  ${YELLOW}docker compose ps${NC}          - Check status"
echo -e "  ${YELLOW}cat trades_history/trades.json${NC} - View trades"


