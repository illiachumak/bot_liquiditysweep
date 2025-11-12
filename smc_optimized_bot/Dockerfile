# SMC Optimized Trading Bot - Docker Image
# Base: Python 3.10 (required for smartmoneyconcepts 1.2.1+)
FROM python:3.10-slim

# Metadata
LABEL maintainer="trading-bot"
LABEL description="SMC Optimized Trading Bot for Binance"
LABEL version="1.0"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy bot files
COPY smc_optimized_bot.py .

# Create directories
RUN mkdir -p /app/logs /app/trades_history

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TZ=UTC

# Health check
HEALTHCHECK --interval=5m --timeout=10s --start-period=30s --retries=3 \
    CMD ps aux | grep -q '[p]ython.*smc_optimized_bot' || exit 1

# Run the bot
CMD ["python", "-u", "smc_optimized_bot.py"]

