#!/bin/bash

# 🐳 Liquidity Sweep Bot - Docker Deployment Script
# For Ubuntu/Linux systems

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║         🐳 LIQUIDITY SWEEP BOT - DOCKER DEPLOY 🚀           ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo -e "${YELLOW}⚠️  Warning: This script is designed for Linux/Ubuntu${NC}"
    echo -e "${YELLOW}   It may work on other systems but not tested${NC}"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Step 1: Check Docker installation
echo -e "${CYAN}[1/7] Checking Docker installation...${NC}"
if command_exists docker; then
    echo -e "${GREEN}✅ Docker is installed: $(docker --version)${NC}"
else
    echo -e "${RED}❌ Docker is not installed${NC}"
    echo -e "${YELLOW}Installing Docker...${NC}"
    
    # Install Docker on Ubuntu
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    
    echo -e "${GREEN}✅ Docker installed successfully${NC}"
    echo -e "${YELLOW}⚠️  You may need to log out and log back in for Docker permissions${NC}"
fi

# Step 2: Check Docker Compose installation
echo -e "\n${CYAN}[2/7] Checking Docker Compose installation...${NC}"
if command_exists docker-compose || docker compose version >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Docker Compose is installed${NC}"
else
    echo -e "${RED}❌ Docker Compose is not installed${NC}"
    echo -e "${YELLOW}Installing Docker Compose...${NC}"
    
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    
    echo -e "${GREEN}✅ Docker Compose installed successfully${NC}"
fi

# Step 3: Check .env file
echo -e "\n${CYAN}[3/7] Checking .env file...${NC}"
if [ -f .env ]; then
    echo -e "${GREEN}✅ .env file exists${NC}"
    
    # Check if API keys are configured
    if grep -q "your_api_key_here" .env || grep -q "your_api_secret_here" .env; then
        echo -e "${RED}❌ API keys not configured in .env${NC}"
        echo -e "${YELLOW}Please edit .env and add your Binance API keys${NC}"
        echo -e "${YELLOW}Run: nano .env${NC}"
        exit 1
    fi
    echo -e "${GREEN}✅ API keys appear to be configured${NC}"
else
    echo -e "${RED}❌ .env file not found${NC}"
    
    if [ -f env_example.txt ]; then
        echo -e "${YELLOW}Creating .env from template...${NC}"
        cp env_example.txt .env
        echo -e "${GREEN}✅ .env file created${NC}"
        echo -e "${YELLOW}⚠️  Please edit .env and add your Binance API keys${NC}"
        echo -e "${YELLOW}Run: nano .env${NC}"
        exit 1
    else
        echo -e "${RED}❌ env_example.txt not found${NC}"
        exit 1
    fi
fi

# Step 4: Create logs directory
echo -e "\n${CYAN}[4/7] Creating directories...${NC}"
mkdir -p logs
mkdir -p trades_history
echo -e "${GREEN}✅ Directories created${NC}"

# Step 5: Build Docker image
echo -e "\n${CYAN}[5/7] Building Docker image...${NC}"
echo -e "${YELLOW}This may take 5-10 minutes (installing TA-Lib)...${NC}"

if docker-compose build; then
    echo -e "${GREEN}✅ Docker image built successfully${NC}"
else
    echo -e "${RED}❌ Failed to build Docker image${NC}"
    exit 1
fi

# Step 6: Ask user about deployment mode
echo -e "\n${CYAN}[6/7] Deployment options${NC}"
echo "1) Start bot in background (daemon mode)"
echo "2) Start bot in foreground (see logs)"
echo "3) Build only (don't start)"
read -p "Choose option (1-3): " -n 1 -r
echo

case $REPLY in
    1)
        echo -e "\n${CYAN}[7/7] Starting bot in background...${NC}"
        docker-compose up -d
        echo -e "${GREEN}✅ Bot is running in background${NC}"
        echo -e "${CYAN}View logs: docker-compose logs -f${NC}"
        echo -e "${CYAN}Stop bot: docker-compose down${NC}"
        echo -e "${CYAN}Restart bot: docker-compose restart${NC}"
        ;;
    2)
        echo -e "\n${CYAN}[7/7] Starting bot in foreground...${NC}"
        echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
        docker-compose up
        ;;
    3)
        echo -e "\n${GREEN}✅ Build complete${NC}"
        echo -e "${CYAN}Start bot with: docker-compose up -d${NC}"
        ;;
    *)
        echo -e "${RED}Invalid option${NC}"
        exit 1
        ;;
esac

echo -e "\n${GREEN}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║               ✅ DEPLOYMENT COMPLETE ✅                       ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "${CYAN}Useful commands:${NC}"
echo -e "  ${YELLOW}docker-compose ps${NC}              - Check bot status"
echo -e "  ${YELLOW}docker-compose logs -f${NC}         - View live logs"
echo -e "  ${YELLOW}docker-compose restart${NC}         - Restart bot"
echo -e "  ${YELLOW}docker-compose stop${NC}            - Stop bot"
echo -e "  ${YELLOW}docker-compose down${NC}            - Stop and remove container"
echo -e "  ${YELLOW}docker-compose up -d --build${NC}   - Rebuild and restart"

echo -e "\n${CYAN}Log files location:${NC}"
echo -e "  ${YELLOW}./logs/liquidity_sweep_bot.log${NC}"

echo -e "\n${GREEN}Happy Trading! 🚀${NC}"

