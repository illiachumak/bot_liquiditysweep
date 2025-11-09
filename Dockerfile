# Liquidity Sweep Trading Bot - Docker Image
# Base: Python 3.13 slim
FROM python:3.9.6

# Metadata
LABEL maintainer="trading-bot"
LABEL description="Liquidity Sweep Trading Bot for Binance Futures"
LABEL version="1.0"

# Set working directory
WORKDIR /app

# Install system dependencies for compiling TA-Lib
RUN apt-get update && apt-get install -y \
    wget \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install TA-Lib C library from source (version 0.4.0)
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    ldconfig && \
    cd .. && \
    rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# Copy requirements first (for better caching)
COPY requirements_bot.txt .

# Install Python dependencies
# Install numpy first (required for building TA-Lib), then install everything else
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "numpy<2.0.0" "Cython<3.0.0" && \
    pip install --no-cache-dir TA-Lib==0.4.19 && \
    grep -v "TA-Lib" requirements_bot.txt | grep -v "^#" | grep -v "^$" | xargs -r pip install --no-cache-dir

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

