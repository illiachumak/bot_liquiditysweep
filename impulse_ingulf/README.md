# PRODUCTION_Q3_DynamicRR_VariableRisk Live Trading Bot

**Impulse Breakout Strategy with Dynamic Risk-Reward and Variable Position Sizing**

🚨 **WARNING: This bot trades with REAL MONEY on Binance Futures! Use at your own risk.**

## Strategy Overview

This live trading bot implements the PRODUCTION_Q3 strategy with:
- **Impulse Detection**: ATR-based detection on 4H timeframe
- **Entry Strategy**: Breakout confirmation on 1H timeframe
- **Quality Scoring**: 0-10 point system to filter low-quality setups
- **Dynamic RR**: Adjusts risk-reward ratio (2.5x - 8.0x) based on quality score
- **Variable Risk**: Adjusts position size (1.5% - 2.0%) based on quality category

### Key Features

✅ **NO Lookahead Bias**
- Uses ONLY closed candles (iloc[-2])
- Entry can only happen AFTER impulse candle close
- All indicators calculated on historical data only

✅ **Smart Risk Management**
- Quality score determines both RR and risk %
- Higher quality = larger RR, not necessarily larger risk
- Position sizing respects balance limits

✅ **Production-Ready**
- Docker containerized
- Graceful shutdown handling
- Daily trade limits
- Comprehensive logging

## Strategy Logic

### 1. Impulse Detection (4H Timeframe)

Detects strong price movements using ATR-based criteria:
- Body > 1.5x ATR
- Body ratio > 70% of total candle range
- Direction: Bullish (close > open) or Bearish (close < open)

### 2. Entry Strategy (1H Timeframe)

Waits for breakout confirmation:
- Consolidation period (3-20 candles)
- Breakout above/below impulse high/low
- EMA trend confirmation (12/21 EMAs)

### 3. Quality Scoring (0-10 Points)

Filters weak setups using multiple criteria:
- **Impulse Strength** (0-2 pts): Body ratio quality
- **Volume Confirmation** (0-2 pts): Volume vs average
- **Trend Alignment** (0-2 pts): MA50 trend direction
- **Entry Timing** (0-2 pts): Speed of entry after impulse
- **Consolidation Quality** (0-2 pts): Tightness of consolidation

### 4. Dynamic RR Mapping

Quality Score → RR Ratio:
- **8-10**: 8.0x RR (exceptional setups)
- **6-7**: 3.5x RR (good setups)
- **4-5**: 3.0x RR (medium setups)
- **3**: 2.5x RR (acceptable setups)
- **0-2**: Filtered out

### 5. Variable Risk by Category

Quality Score → Risk %:
- **8-10**: 2.0% (high conviction)
- **6-7**: 1.5% (moderate conviction)
- **4-5**: 1.5% (moderate conviction)
- **3**: 2.0% (acceptable but lower RR)

## Installation

### Prerequisites

- Docker and Docker Compose
- Binance Futures account with API access
- API keys with Futures trading permissions

### Setup

1. **Clone repository**
```bash
cd PRODUCTION_Q3_LIVE
```

2. **Create .env file**
```bash
cp .env.example .env
```

3. **Edit .env with your API credentials**
```bash
# Binance Futures API Credentials
BINANCE_API_KEY=your_api_key_here
BINANCE_API_SECRET=your_api_secret_here
```

4. **Review config.py**
```bash
# Edit config.py to adjust:
# - LEVERAGE (default: 100x)
# - Risk settings
# - Safety limits
# - Logging level
```

## Running the Bot

### Using Docker Compose (Recommended)

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Manual Docker

```bash
# Build image
docker build -t production-q3-bot .

# Run container
docker run -d \
  --name production-q3-bot \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  production-q3-bot

# View logs
docker logs -f production-q3-bot

# Stop
docker stop production-q3-bot
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run bot
python live_bot.py
```

## Configuration

### Key Settings in config.py

```python
# Symbol
SYMBOL = "BTCUSDT"

# Leverage
LEVERAGE = 100

# Impulse Detection
IMPULSE_ATR_MULTIPLIER = 1.5
IMPULSE_BODY_RATIO = 0.70

# Entry Strategy
CONSOLIDATION_MIN = 3
CONSOLIDATION_MAX = 20

# Quality Scoring
MIN_QUALITY_SCORE = 3  # Minimum score to trade

# Safety Limits
MAX_POSITION_SIZE_USDT = 10000.0
MAX_TRADES_PER_DAY = 5
MAX_CONCURRENT_POSITIONS = 1

# Polling
POLL_INTERVAL = 60  # seconds
```

### Dynamic RR and Variable Risk

Edit `RR_MAPPING` and `RISK_BY_CATEGORY` in config.py:

```python
RR_MAPPING = {
    (8, 10): 8.0,   # High quality
    (6, 7): 3.5,    # Good quality
    (4, 5): 3.0,    # Medium quality
    (3, 3): 2.5,    # Low quality
    (0, 2): None    # Filtered out
}

RISK_BY_CATEGORY = {
    '8-10': 2.0,   # 2% risk
    '6-7': 1.5,    # 1.5% risk
    '4-5': 1.5,    # 1.5% risk
    '3': 2.0       # 2% risk
}
```

## Architecture

```
PRODUCTION_Q3_LIVE/
├── config.py                 # Configuration
├── live_bot.py              # Main bot logic
├── binance_client.py        # Binance API wrapper
├── impulse_detectors.py     # Impulse detection
├── entry_strategies.py      # Breakout entry
├── quality_filter.py        # Quality scoring
├── ema_filter.py            # EMA trend filter
├── requirements.txt         # Python dependencies
├── Dockerfile               # Docker image
├── docker-compose.yml       # Docker Compose config
├── .env.example            # Environment template
└── README.md               # This file
```

## Safety Features

### 1. Lookahead Bias Prevention
- Always uses `iloc[-2]` for last closed candle
- Never uses `iloc[-1]` (current unclosed candle) for decision making
- Entry validation ensures entry time > impulse close time

### 2. Position Limits
- Max position size: $10,000 USDT (configurable)
- Max concurrent positions: 1
- Min notional: $10 USDT

### 3. Daily Limits
- Max trades per day: 5 (configurable)
- Counter resets at midnight

### 4. Stop Loss Validation
- Min SL distance: 0.3%
- Max SL distance: 5.0%
- Prevents too tight or too wide stops

### 5. Graceful Shutdown
- SIGINT/SIGTERM handlers
- Proper cleanup on exit

## Monitoring

### Log Levels

```python
# In config.py
LOG_LEVEL = "INFO"  # OPTIONS: DEBUG, INFO, WARNING, ERROR
```

### Important Log Messages

```
✅ 4H candle closed at ...           # New 4H candle
🔥 IMPULSE DETECTED: BULLISH         # Impulse found
OPENING TRADE: ...                    # Trade execution
✅ Trade opened successfully!         # Trade confirmed
```

### Health Checks

Monitor these in logs:
- Balance updates
- Position status
- Impulse detection
- Entry attempts
- Quality scores
- Trade executions

## Backtest Results

Strategy tested on BTC/ETH (2024-2025):

**BTC:**
- Win Rate: ~45%
- Expected Value: ~0.5 R
- Quality filtering improves EV significantly

**ETH:**
- Similar performance profile
- Dynamic RR increases profit potential
- Variable risk optimizes capital allocation

## Risk Disclaimer

⚠️ **IMPORTANT:**

- This bot trades with REAL MONEY
- Cryptocurrency trading involves substantial risk
- Past performance does not guarantee future results
- You can lose all your capital
- Test thoroughly on testnet first
- Start with small position sizes
- Never invest more than you can afford to lose

## Troubleshooting

### Bot not detecting impulses

Check:
- 4H candles are being fetched correctly
- ATR calculation is working
- Impulse criteria not too strict

### Bot not entering trades

Check:
- Quality score threshold (MIN_QUALITY_SCORE)
- RR mapping allows trades
- EMA filter not too restrictive
- Consolidation parameters

### API Errors

Check:
- API keys are correct
- Futures trading enabled
- API permissions sufficient
- Rate limits not exceeded

### Position size too small/large

Check:
- Balance calculation
- Risk percentage settings
- Min/max notional limits
- Leverage setting

## Support

For issues, bugs, or questions:
1. Check logs for errors
2. Review configuration
3. Test on Binance Testnet first
4. Start with paper trading

## License

This bot is for educational purposes. Use at your own risk.

---

**Built with ❤️ for systematic trading**
