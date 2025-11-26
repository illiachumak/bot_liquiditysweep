# HELD FVG Live Bot

**Live trading bot з simulation mode для HELD 4H FVG strategy**

---

## 🎯 Стратегія

**Strategy:** 4h_close + rr_2.0

**Parameters:**
- Entry Method: Immediate on 4H close (when FVG held)
- TP Method: Fixed RR 2.0
- Risk per Trade: 2%
- Min SL: 0.3%
- Max SL: 5.0%

**Expected Performance (2024 backtest):**
- Trades: 126
- Win Rate: 63.5%
- Total PnL: +$1,766 (from $300)
- ROI: 589%
- Max Drawdown: 7.9%
- Profit Factor: 2.92

---

## 🏗️ Architecture

### Shared Core Logic

Bot використовує **спільну логіку** між backtest, simulation та live trading:

```
core/
├── fvg.py       - HeldFVG class (FVG detection & state)
└── strategy.py  - HeldFVGStrategy (shared logic)
```

**Benefits:**
- ✅ Simulation results = Backtest results (same logic!)
- ✅ Easy to test before going live
- ✅ Single source of truth

### Feature Flags

```python
# .env file
SIMULATION_MODE=True   # Safe testing with historical data
SIMULATION_MODE=False  # Real trading ($$$ at risk!)
```

---

## 🚀 Usage

### 1. Simulation Mode (Recommended First!)

```bash
# Install dependencies
pip install pandas python-binance python-dotenv

# Set environment (default is simulation)
echo "SIMULATION_MODE=True" > .env

# Run simulation
python held_fvg_live_bot.py
```

### 2. Live Trading Mode

```bash
# Configure API keys in .env
SIMULATION_MODE=False
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here
BINANCE_TESTNET=True  # Start with testnet!

# Run live bot
python held_fvg_live_bot.py
```

⚠️ **WARNING:** Live mode risks real money! Test simulation first!

---

## 📊 Simulation vs Backtest

Simulation mode дозволяє **перевірити** що логіка ідентична бектесту:

| Aspect | Backtest | Simulation | Live |
|--------|----------|------------|------|
| **Data Source** | Historical CSV | Historical CSV | Binance API |
| **Speed** | Fast (instant) | Real-time/Fast | Real-time |
| **Orders** | Simulated | Simulated | Real |
| **Purpose** | Strategy testing | Bot logic testing | Production |
| **Risk** | None | None | Real money |

**Simulation = dry-run з історичними даними**
- Використовує TU САМУ логіку що і live bot
- Але без реальних ордерів
- Результати мають бути ІДЕНТИЧНІ бектесту

---

## 🔍 Comparing Results

### Backtest Results (2024, 4h_close + rr_2.0):
```
Total Trades: 126
Win Rate: 63.5%
Total PnL: $1,766.70
Final Balance: $2,066.70
Max DD: 7.9%
```

### Simulation Results:
Run simulation and compare:
```bash
python held_fvg_live_bot.py
```

Should see similar stats at the end.

---

## 📁 File Structure

```
HELD_FVG_STRATEGY/
├── core/
│   ├── __init__.py
│   ├── fvg.py              # FVG class (shared)
│   └── strategy.py         # Strategy logic (shared)
│
├── held_fvg_live_bot.py    # Main bot (simulation + live)
├── config.py               # Configuration
├── .env.example            # Environment template
├── .env                    # Your settings (gitignored)
│
├── backtest_held_fvg.py    # Backtest engine
├── debug_held_fvg_logic.py # Debug tools
│
└── docs/
    ├── README.md
    ├── HELD_BACKTEST_RESULTS.md
    └── FVG_INVALIDATION_RULES.md
```

---

## ⚙️ Configuration

### config.py

Main configuration file with all parameters:

```python
# Feature flags
SIMULATION_MODE = True/False

# Trading parameters (same as backtest!)
INITIAL_BALANCE = 300.0
RISK_PER_TRADE = 0.02
MIN_SL_PCT = 0.3
MAX_SL_PCT = 5.0

# Strategy
ENTRY_METHOD = '4h_close'
TP_METHOD = 'rr_2.0'
FIXED_RR = 2.0

# Fees (same as backtest!)
MAKER_FEE = 0.00018
TAKER_FEE = 0.00045
```

### .env

Environment-specific settings:

```bash
SIMULATION_MODE=True
BINANCE_API_KEY=...
BINANCE_API_SECRET=...
BINANCE_TESTNET=True
LOG_LEVEL=INFO
```

---

## 🧪 Testing Workflow

**Recommended testing sequence:**

1. **Backtest** - Test strategy on historical data
   ```bash
   python backtest_held_fvg.py
   ```

2. **Simulation** - Test bot logic with same data
   ```bash
   SIMULATION_MODE=True python held_fvg_live_bot.py
   ```

3. **Compare Results** - Should be identical (within rounding)

4. **Testnet** - Test with Binance testnet
   ```bash
   SIMULATION_MODE=False BINANCE_TESTNET=True python held_fvg_live_bot.py
   ```

5. **Live** - Start with small balance
   ```bash
   SIMULATION_MODE=False BINANCE_TESTNET=False python held_fvg_live_bot.py
   ```

---

## 🐛 Debugging

If simulation results differ from backtest:

1. Check FVG detection logic
2. Check hold detection logic
3. Check trade execution logic
4. Check fee calculations
5. Use debug mode:
   ```python
   # In strategy.update_fvgs()
   debug=True
   ```

---

## 🔐 Security

**API Keys:**
- Never commit .env file to git
- Use read-only API keys for monitoring
- Enable IP whitelist on Binance
- Start with testnet!

**Risk Management:**
- Start with minimum balance
- Set max daily loss limit
- Monitor bot 24/7 initially
- Have kill switch ready

---

## 📈 Monitoring

Bot prints real-time updates:

```
⏰ 4H Candle: 2024-01-01 12:00:00
   OHLC: 42690 / 42847 / 42580 / 42783
   📍 New BULLISH FVG: $42500-$42580
   💚 BULLISH FVG HELD!

🔵 SIMULATION TRADE OPENED:
  Direction: LONG
  Entry: $42783.00
  SL: $42450.00
  TP: $43449.00
  Size: 0.018023

🟢 TRADE CLOSED:
  Exit: $43449.00
  Reason: TP
  PnL: $12.00 (+2.00%)
  Balance: $312.00
```

---

## 📊 Final Statistics

At end of simulation/live run:

```
================================================================================
📊 BOT STATISTICS
================================================================================

Total 4H FVGs: 409
Total Holds: 148
Hold Rate: 36.2%

Total Trades: 126
Wins: 80
Losses: 46
Win Rate: 63.5%

Total PnL: $1,766.70
Final Balance: $2,066.70
ROI: +589.0%

================================================================================
```

---

## 🚨 Important Notes

1. **Shared Logic** - core/ modules used by both backtest and live bot
2. **Same Parameters** - config.py matches backtest parameters exactly
3. **Same Fees** - maker/taker fees identical to backtest
4. **Simulation First** - Always test simulation before live!
5. **One Trade per FVG** - Logic enforced (has_filled_trade flag)
6. **FVG Invalidation** - Proper invalidation logic implemented

---

## 🎓 Next Steps

1. ✅ Run simulation - compare with backtest
2. ⬜ Test on Binance testnet
3. ⬜ Start live with small balance ($50-100)
4. ⬜ Monitor for 1 week
5. ⬜ Scale up if profitable

---

## 📞 Support

Questions or issues? Check:
- `FVG_INVALIDATION_RULES.md` - FVG logic
- `HELD_BACKTEST_RESULTS.md` - Expected performance
- `debug_held_fvg_logic.py` - Debug tools

---

**Remember:** Past performance (backtest) does not guarantee future results!
