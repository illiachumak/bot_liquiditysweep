# 4H FVG Bot - Docker Setup

## Quick Start

### 1. Configure Environment

Create or update `.env` file with your Binance API credentials:

```bash
# Trading mode
DRY_RUN=true  # Set to 'false' for real trading

# Binance API credentials
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
```

### 2. Build and Run

```bash
# Build the Docker image
docker-compose build

# Run the bot
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the bot
docker-compose down
```

## Commands

### Build Image
```bash
docker-compose build
```

### Start Bot (detached)
```bash
docker-compose up -d
```

### Start Bot (foreground)
```bash
docker-compose up
```

### View Logs
```bash
# Follow logs in real-time
docker-compose logs -f

# View last 100 lines
docker-compose logs --tail=100
```

### Stop Bot
```bash
docker-compose down
```

### Restart Bot
```bash
docker-compose restart
```

### Check Bot Status
```bash
docker-compose ps
```

### Execute Commands Inside Container
```bash
# Open shell
docker-compose exec fvg-bot /bin/bash

# Run Python shell
docker-compose exec fvg-bot python

# View state file
docker-compose exec fvg-bot cat state.json
```

## Data Persistence

The following data is persisted via Docker volumes:

- **state.json** - Bot state (FVGs, pending setups, active trades)
- **logs/** - All log files

This means your bot state will persist even if you restart or rebuild the container.

## Resource Limits

Current limits (can be adjusted in docker-compose.yml):
- CPU: 1 core (limit), 0.5 core (reserved)
- Memory: 512MB (limit), 256MB (reserved)

## Monitoring

### Health Check
Docker will automatically check if the bot is healthy every 60 seconds.

```bash
# Check health status
docker inspect --format='{{.State.Health.Status}}' 4hfvg-bot
```

### View Live Stats
```bash
docker stats 4hfvg-bot
```

## Troubleshooting

### Bot crashes immediately
Check logs:
```bash
docker-compose logs
```

Common issues:
- Missing or invalid API credentials in .env
- Insufficient balance in testnet account
- Network connectivity issues

### Clear state and start fresh
```bash
# Stop bot
docker-compose down

# Remove state file
rm state.json

# Start bot
docker-compose up -d
```

### Rebuild image from scratch
```bash
# Remove old image and rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Production Deployment

### Security Checklist
- [ ] Set strong API key permissions (only spot trading, no withdrawals)
- [ ] Use API key IP whitelist if possible
- [ ] Never commit .env file to git
- [ ] Use Docker secrets in production
- [ ] Set up monitoring and alerts
- [ ] Configure automatic backups of state.json

### Running in Production
```bash
# Set production environment
export DRY_RUN=false

# Run with explicit .env file
docker-compose --env-file .env.production up -d

# Monitor logs
docker-compose logs -f --tail=100
```

## Advanced Configuration

### Custom Python Version
Edit Dockerfile, line 2:
```dockerfile
FROM python:3.12-slim  # or any other version
```

### Adjust Resource Limits
Edit docker-compose.yml under `deploy.resources`

### Add Environment Variables
Add to .env file or docker-compose.yml under `environment`

### Network Configuration
To connect to other containers:
```yaml
networks:
  - trading-network
```

## File Structure
```
4HFVG_BOT/
├── Dockerfile              # Docker image definition
├── docker-compose.yml      # Docker Compose configuration
├── .dockerignore          # Files to exclude from image
├── requirements.txt        # Python dependencies
├── .env                   # Environment variables (not in git)
├── .env.example           # Example environment file
├── failed_fvg_live_bot.py # Main bot script
├── state.json             # Bot state (auto-created)
└── logs/                  # Log files (auto-created)
```
