# HELD FVG Bot - Docker Setup

Docker configuration for running HELD FVG trading bot in containerized environment.

## Quick Start

### For SIMULATION Mode (with historical data)

1. Uncomment volume mounts in `docker-compose.yml`
2. Set `SIMULATION_MODE=True` in `.env`
3. Run: `docker compose up -d`

### For LIVE Trading (on server)

1. Copy .env from 4HFVG_BOT:
   ```bash
   cp ../4HFVG_BOT/.env .env
   ```

2. Edit `.env` - ensure:
   ```bash
   SIMULATION_MODE=False
   BINANCE_API_KEY=your_real_key
   BINANCE_API_SECRET=your_real_secret
   ```

3. Use live compose file:
   ```bash
   # Start
   docker compose -f docker-compose.live.yml up -d

   # View logs
   docker compose -f docker-compose.live.yml logs -f

   # Stop
   docker compose -f docker-compose.live.yml down
   ```

### 3. Quick Rebuild (after code changes)

```bash
./rebuild.sh
```

## Configuration

### Strategy Settings

Current configuration in `config.py`:
- **Entry Method**: `4h_close` (immediate entry on 4H close)
- **TP Method**: `rr_3.0_liq` (3RR with liquidity check)
- **Risk per Trade**: 2%
- **Initial Balance**: $300

### Volume Mounts

The container mounts:
1. `./logs` → Persistent logs
2. `/Users/illiachumak/trading/backtest/data` → Historical data (read-only)

### Resource Limits

Default limits:
- **CPU**: 1.0 core max, 0.5 reserved
- **Memory**: 1024MB max, 512MB reserved

Adjust in `docker-compose.yml` if needed.

## Modes

### Simulation Mode (Default)

Runs bot with historical data to validate logic:

```bash
# Already set in .env
SIMULATION_MODE=True
```

Results should match backtest exactly:
- **75 trades**
- **60.0% win rate**
- **+$3,290.73 PnL**

### Live Trading Mode

⚠️ **WARNING: Real money at risk!**

1. Update `.env`:
   ```bash
   SIMULATION_MODE=False
   BINANCE_API_KEY=your_real_key
   BINANCE_API_SECRET=your_real_secret
   ```

2. Rebuild and start:
   ```bash
   ./rebuild.sh
   ```

## Monitoring

### View Logs

```bash
# Follow logs in real-time
docker compose logs -f

# View last 100 lines
docker compose logs --tail=100

# View logs from specific time
docker compose logs --since=1h
```

### Check Container Status

```bash
# Container status
docker compose ps

# Container stats (CPU, memory)
docker stats held-fvg-bot
```

### Health Check

The container has a built-in health check that runs every 60 seconds.

```bash
# Check health status
docker inspect held-fvg-bot | grep -A 5 Health
```

## Troubleshooting

### Container Exits Immediately

Check logs:
```bash
docker compose logs
```

Common issues:
- Missing `.env` file
- Invalid API credentials (if in live mode)
- Missing data files (if in simulation mode)

### Data Files Not Found

Ensure data path is correct in `docker-compose.yml`:
```yaml
volumes:
  - /Users/illiachumak/trading/backtest/data:/app/backtest_data:ro
```

### High Memory Usage

Reduce resource limits in `docker-compose.yml`:
```yaml
limits:
  memory: 512M
reservations:
  memory: 256M
```

## Maintenance

### Clean Up

```bash
# Stop and remove container
docker compose down

# Remove image
docker rmi held-fvg-bot

# Clean up logs
rm -rf logs/*
```

### Update Code

```bash
# After making code changes
./rebuild.sh
```

This will:
1. Stop container
2. Rebuild image (no cache)
3. Start container
4. Show logs

## Files

### Required Files
- `Dockerfile` - Container image definition
- `docker-compose.yml` - Service configuration
- `requirements.txt` - Python dependencies
- `.env` - Environment variables
- `rebuild.sh` - Quick rebuild script

### Bot Files (copied to container)
- `held_fvg_live_bot.py` - Main bot
- `backtest_held_fvg.py` - Shared logic
- `config.py` - Configuration
- `core/` - Core strategy modules

## Validation

Before deploying to live:

1. ✅ Run simulation mode - verify results match backtest
2. ✅ Check logs - ensure no errors
3. ⬜ Test on Binance testnet
4. ⬜ Start live with small balance

---

**Current Status**: Ready for Docker deployment with rr_3.0_liq optimization! 🚀
