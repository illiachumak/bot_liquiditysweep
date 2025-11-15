# Failed 4H FVG Bot - Docker Image
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

# Copy bot files
COPY failed_fvg_live_bot.py .
COPY failed_fvg_strategy.py .
COPY backtest_failed_fvg.py .
COPY test_failed_fvg.py .

# Create logs directory
RUN mkdir -p logs

# Create state file
RUN touch state.json

# Environment variables (will be overridden by docker-compose or .env)
ENV DRY_RUN=true
ENV BINANCE_API_KEY=""
ENV BINANCE_API_SECRET=""

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import os; exit(0 if os.path.exists('state.json') else 1)"

# Run the bot
CMD ["python", "-u", "failed_fvg_live_bot.py"]
