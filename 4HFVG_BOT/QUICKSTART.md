# 4H FVG Bot - Quick Start with Docker

## Prerequisites
- Docker installed ([Get Docker](https://docs.docker.com/get-docker/))
- Docker Compose installed (usually comes with Docker)
- Binance account with API keys

## Setup in 3 Steps

### Step 1: Configure API Keys
```bash
cd 4HFVG_BOT

# Copy example and edit
cp .env.example .env
nano .env  # or use your favorite editor
```

Set your credentials in `.env`:
```bash
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here
DRY_RUN=true  # Keep true for testnet
```

### Step 2: Build and Run
```bash
# Easy way - use the launcher script
./docker-start.sh

# Or manually
docker-compose up -d
```

### Step 3: Monitor
```bash
# View logs
docker-compose logs -f

# Check status
docker-compose ps
```

That's it! The bot is now running.

## Common Commands

| Action | Command |
|--------|---------|
| Start bot | `docker-compose up -d` |
| Stop bot | `docker-compose down` |
| View logs | `docker-compose logs -f` |
| Restart | `docker-compose restart` |
| Status | `docker-compose ps` |
| Shell access | `docker-compose exec fvg-bot /bin/bash` |

## Using the Launcher Script

The `docker-start.sh` script provides an interactive menu:

```bash
./docker-start.sh
```

Options:
1. Build and start bot
2. Start bot (already built)
3. View logs
4. Stop bot
5. Restart bot
6. View bot status
7. Clear state and restart
8. Open shell in container
9. Exit

## File Structure

```
4HFVG_BOT/
├── docker-start.sh         ← Interactive launcher
├── docker-compose.yml      ← Docker configuration
├── Dockerfile              ← Image definition
├── .env                    ← Your API keys (create this)
├── .env.example            ← Template
├── DOCKER_README.md        ← Full documentation
└── QUICKSTART.md          ← This file
```

## Troubleshooting

### Bot crashes on start
```bash
# Check logs
docker-compose logs

# Common issues:
# - Missing/invalid API keys
# - No testnet balance
# - Network issues
```

### Start fresh
```bash
docker-compose down
rm state.json
docker-compose up -d
```

### Rebuild image
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Next Steps

- Read [DOCKER_README.md](DOCKER_README.md) for advanced features
- Read [LIVE_TRADING_SPEC.md](LIVE_TRADING_SPEC.md) for strategy details
- Check [TESTING_GUIDE.md](TESTING_GUIDE.md) for testing instructions

## Important Notes

⚠️ **Always test in DRY_RUN mode first!**

⚠️ **Never commit .env file to git**

⚠️ **Set up API key IP whitelist for security**

⚠️ **Only enable spot trading permissions**
