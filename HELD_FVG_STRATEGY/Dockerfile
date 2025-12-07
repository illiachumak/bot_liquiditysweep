# Dockerfile for HELD FVG Live Trading Bot
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY config.py .
COPY live_bot.py .

# Create logs directory
RUN mkdir -p /app/logs

# Run bot
CMD ["python", "-u", "live_bot.py"]
