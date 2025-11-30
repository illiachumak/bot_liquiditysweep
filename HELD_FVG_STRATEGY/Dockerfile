# HELD FVG Bot - Docker Image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy core logic files
COPY core/ ./core/

# Copy bot files
COPY held_fvg_live_bot.py .
COPY backtest_held_fvg.py .
COPY config.py .
COPY .env .

# Create necessary directories
RUN mkdir -p logs data

# Environment variables (will be overridden by docker-compose or .env)
ENV SIMULATION_MODE=True
ENV BINANCE_API_KEY=""
ENV BINANCE_API_SECRET=""
ENV LOG_LEVEL=INFO

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import os; exit(0)"

# Run the bot
CMD ["python", "-u", "held_fvg_live_bot.py"]
