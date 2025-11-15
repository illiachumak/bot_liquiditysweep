#!/bin/bash

# 4H FVG Bot - Docker Quick Start Script

set -e

echo "======================================"
echo "4H FVG Bot - Docker Launcher"
echo "======================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  Warning: .env file not found!"
    echo ""
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo ""
    echo "✅ .env created. Please edit it with your API credentials:"
    echo "   nano .env"
    echo ""
    read -p "Press Enter after you've configured .env, or Ctrl+C to exit..."
fi

# Source .env to check DRY_RUN
source .env

echo "Configuration:"
echo "  DRY_RUN: $DRY_RUN"
if [ "$DRY_RUN" = "false" ]; then
    echo "  Mode: 🔴 LIVE TRADING (REAL MONEY)"
    echo ""
    echo "⚠️  WARNING: You are about to start LIVE trading!"
    echo ""
    read -p "Type 'I UNDERSTAND THE RISKS' to continue: " confirmation
    if [ "$confirmation" != "I UNDERSTAND THE RISKS" ]; then
        echo "Aborted."
        exit 0
    fi
else
    echo "  Mode: 🟢 DRY RUN (Testnet/Simulation)"
fi

echo ""
echo "What would you like to do?"
echo ""
echo "1) Build and start bot"
echo "2) Start bot (already built)"
echo "3) View logs"
echo "4) Stop bot"
echo "5) Restart bot"
echo "6) View bot status"
echo "7) Clear state and restart"
echo "8) Open shell in container"
echo "9) Exit"
echo ""
read -p "Choose option [1-9]: " option

case $option in
    1)
        echo ""
        echo "Building Docker image..."
        docker-compose build
        echo ""
        echo "Starting bot..."
        docker-compose up -d
        echo ""
        echo "✅ Bot started!"
        echo "View logs: docker-compose logs -f"
        ;;
    2)
        echo ""
        echo "Starting bot..."
        docker-compose up -d
        echo ""
        echo "✅ Bot started!"
        echo "View logs: docker-compose logs -f"
        ;;
    3)
        echo ""
        echo "Showing logs (Ctrl+C to exit)..."
        docker-compose logs -f
        ;;
    4)
        echo ""
        echo "Stopping bot..."
        docker-compose down
        echo "✅ Bot stopped!"
        ;;
    5)
        echo ""
        echo "Restarting bot..."
        docker-compose restart
        echo "✅ Bot restarted!"
        ;;
    6)
        echo ""
        docker-compose ps
        echo ""
        echo "Health status:"
        docker inspect --format='{{.State.Health.Status}}' 4hfvg-bot 2>/dev/null || echo "Container not running"
        ;;
    7)
        echo ""
        echo "⚠️  This will clear all bot state (pending orders, FVGs, etc.)"
        read -p "Are you sure? [y/N]: " confirm
        if [[ $confirm == [yY] ]]; then
            echo "Stopping bot..."
            docker-compose down
            echo "Clearing state..."
            rm -f state.json
            rm -f logs/*.log
            echo "Starting bot..."
            docker-compose up -d
            echo "✅ Bot restarted with fresh state!"
        else
            echo "Cancelled."
        fi
        ;;
    8)
        echo ""
        echo "Opening shell in container..."
        docker-compose exec fvg-bot /bin/bash
        ;;
    9)
        echo "Goodbye!"
        exit 0
        ;;
    *)
        echo "Invalid option"
        exit 1
        ;;
esac
