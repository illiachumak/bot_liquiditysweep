#!/bin/bash

# Quick rebuild script after code changes

echo "======================================"
echo "Rebuilding Impulse Ingulf Bot"
echo "======================================"
echo ""

echo "1. Stopping container..."
docker compose down

echo ""
echo "2. Removing logs (optional - keeping for history)..."
# rm -rf logs/*
echo "   ✅ Logs preserved"

echo ""
echo "3. Rebuilding image (no cache)..."
docker compose build --no-cache

echo ""
echo "4. Starting bot..."
docker compose up -d

echo ""
echo "5. Showing logs (Ctrl+C to exit)..."
sleep 2
docker compose logs -f

