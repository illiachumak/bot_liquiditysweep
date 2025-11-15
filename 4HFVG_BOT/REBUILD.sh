#!/bin/bash

# Quick rebuild script after code changes

echo "======================================"
echo "Rebuilding 4H FVG Bot"
echo "======================================"
echo ""

echo "1. Stopping container..."
docker-compose down

echo ""
echo "2. Rebuilding image (no cache)..."
docker-compose build --no-cache

echo ""
echo "3. Starting bot..."
docker-compose up -d

echo ""
echo "4. Showing logs (Ctrl+C to exit)..."
sleep 2
docker-compose logs -f
