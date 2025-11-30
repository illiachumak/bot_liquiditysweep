#!/bin/bash

# Copy .env from 4HFVG_BOT to HELD_FVG_STRATEGY

echo "======================================"
echo "Copying .env file"
echo "======================================"
echo ""

SOURCE="../4HFVG_BOT/.env"
DEST=".env"

# Check if source exists
if [ ! -f "$SOURCE" ]; then
    echo "❌ Error: Source file not found: $SOURCE"
    exit 1
fi

# Backup existing .env if it exists
if [ -f "$DEST" ]; then
    echo "⚠️  Backing up existing .env to .env.backup"
    cp "$DEST" "$DEST.backup"
fi

# Copy file
echo "📋 Copying $SOURCE to $DEST"
cp "$SOURCE" "$DEST"

# Verify
if [ $? -eq 0 ]; then
    echo "✅ .env copied successfully!"
    echo ""
    echo "Contents:"
    echo "---"
    cat "$DEST"
else
    echo "❌ Error: Failed to copy .env"
    exit 1
fi

echo ""
echo "======================================"
echo "Done!"
echo "======================================"
