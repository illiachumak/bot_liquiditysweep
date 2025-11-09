# Liquidity Sweep Trading Bot - Docker Image
# Base: Python 3.11 slim
FROM python:3.11-slim

# Metadata
LABEL maintainer="trading-bot"
LABEL description="Liquidity Sweep Trading Bot for Binance Futures"
LABEL version="1.0"

# Set working directory
WORKDIR /app

# Install minimal system dependencies
# Note: Using TA-Lib-binary (pre-compiled), so no compilation needed
RUN apt-get update && apt-get install -y \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements_bot.txt .

# Install Python dependencies
# Using TA-Lib-binary (pre-compiled wheel), much faster than compilation!
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements_bot.txt

# Copy bot files
COPY liquidity_sweep_bot.py .
COPY test_bot.py .

# Create logs directory
RUN mkdir -p /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TZ=UTC

# Health check (optional - checks if bot process is running)
HEALTHCHECK --interval=5m --timeout=10s --start-period=30s --retries=3 \
    CMD ps aux | grep -q '[p]ython.*liquidity_sweep_bot' || exit 1

# Run the bot
CMD ["python", "-u", "liquidity_sweep_bot.py"]

