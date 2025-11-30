#!/bin/bash

echo "======================================"
echo "Hot fix - rebuilding bot"
echo "======================================"
echo ""

echo "1. Stopping container..."
docker compose -f docker-compose.live.yml down

echo ""
echo "2. Rebuilding image (no cache)..."
docker compose -f docker-compose.live.yml build --no-cache

echo ""
echo "3. Starting bot..."
docker compose -f docker-compose.live.yml up -d

echo ""
echo "4. Showing logs (Ctrl+C to exit)..."
sleep 2
docker compose -f docker-compose.live.yml logs -f
