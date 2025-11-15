# 🎯 Failed 4H FVG Live Trading - Technical Specification

## 📋 Table of Contents
1. [Strategy Overview](#strategy-overview)
2. [Architecture](#architecture)
3. [Data Flow](#data-flow)
4. [State Management](#state-management)
5. [Order Execution Logic](#order-execution-logic)
6. [Risk Management](#risk-management)
7. [Edge Cases & Error Handling](#edge-cases--error-handling)
8. [Binance API Integration](#binance-api-integration)
9. [Testing Plan](#testing-plan)
10. [Live Trading Safeguards](#live-trading-safeguards)

---

## Strategy Overview

### Core Concept
**Failed 4H FVG Strategy**: Trade rejections of Fair Value Gaps on 4H timeframe with precise entries on 15M timeframe.

### Trading Logic Flow
```
1. Detect 4H FVG (Bullish or Bearish)
   ↓
2. Wait for price to ENTER FVG zone
   ↓
3. Check for REJECTION (close outside zone)
   ↓
4. Look for 15M FVG in direction of rejection
   ↓
5. Place LIMIT ORDER at 15M FVG boundary
   ↓
6. Wait for FILL (max 4H = 16 candles)
   ↓
7. If filled: Execute trade with SL/TP
   If not filled: Cooldown period, then retry
```

### Key Parameters
```python
TIMEFRAME_4H = '4h'
TIMEFRAME_15M = '15m'
SYMBOL = 'BTCUSDT'

RISK_PER_TRADE = 0.02          # 2% of balance
MIN_SL_PCT = 0.3               # Minimum 0.3% stop loss
FIXED_RR = 1.5                 # 1:1.5 risk-reward ratio
LIMIT_EXPIRY_CANDLES = 16      # 4H expiry (16x 15M candles)
COOLDOWN_CANDLES = 16          # Same as expiry

MAKER_FEE = 0.0018             # 0.18% for limit orders
TAKER_FEE = 0.0045             # 0.45% for market orders
```

---

## Architecture

### Components
```
┌─────────────────────────────────────────────────────┐
│              FailedFVGLiveBot                       │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────┐    ┌──────────────┐             │
│  │ DataManager  │◄───│BinanceClient │             │
│  └──────────────┘    └──────────────┘             │
│         │                                           │
│         ▼                                           │
│  ┌──────────────┐                                  │
│  │ FVGDetector  │                                  │
│  └──────────────┘                                  │
│         │                                           │
│         ▼                                           │
│  ┌──────────────┐    ┌──────────────┐             │
│  │StateManager  │───►│OrderManager  │             │
│  └──────────────┘    └──────────────┘             │
│         │                    │                      │
│         ▼                    ▼                      │
│  ┌──────────────┐    ┌──────────────┐             │
│  │TradeLogger   │    │RiskManager   │             │
│  └──────────────┘    └──────────────┘             │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Class Responsibilities

#### 1. **BinanceClient**
- Connect to Binance API
- Fetch historical klines (4H, 15M)
- Fetch current price
- Fetch account balance
- Place/cancel/modify orders
- Stream real-time klines via WebSocket

#### 2. **DataManager**
- Maintain rolling windows of 4H and 15M candles
- Convert raw Binance data to pandas DataFrame
- Handle candle close events
- Sync 4H and 15M timeframes

#### 3. **FVGDetector**
- Detect FVGs on 4H and 15M timeframes
- Track FVG states (active, entered, rejected, invalidated)
- Calculate SL from highs/lows inside zone

#### 4. **StateManager**
- Track all active 4H FVGs
- Track all rejected 4H FVGs
- Track pending setups (limit orders waiting to fill)
- Manage cooldown periods
- Persist state to disk (survive restarts)

#### 5. **OrderManager**
- Place limit orders
- Monitor order status (filled, expired, cancelled)
- Place SL and TP orders after fill
- Handle partial fills
- Handle order errors

#### 6. **RiskManager**
- Calculate position size based on risk
- Validate SL distance (min 0.3%)
- Validate RR ratio (min 1.5)
- Check max drawdown limits
- Emergency stop on max DD

#### 7. **TradeLogger**
- Log all trades to database
- Log all state changes
- Log all errors
- Generate daily reports

---

## Data Flow

### 1. Initialization
```python
# Load historical data
4h_candles = fetch_klines('BTCUSDT', '4h', limit=200)
15m_candles = fetch_klines('BTCUSDT', '15m', limit=1000)

# Detect existing FVGs
active_4h_fvgs = detect_fvgs(4h_candles)

# Restore state from disk (if restart)
state = load_state_from_disk()
```

### 2. Real-Time Loop
```python
while True:
    # Stream candles via WebSocket
    on_candle_close(timeframe, candle):

        if timeframe == '4h':
            # Update 4H FVGs
            update_4h_fvgs(candle)

            # Check rejections
            check_rejections(candle)

        elif timeframe == '15m':
            # Update pending orders
            check_pending_orders()

            # Look for setup opportunities
            if no_active_trade and has_rejected_fvgs:
                look_for_15m_fvg()

                if found_15m_fvg:
                    create_setup()
                    place_limit_order()

            # Monitor active trade
            if active_trade:
                monitor_trade()

    # Save state every N minutes
    save_state_to_disk()
```

### 3. Order Execution Flow
```
REJECTED 4H FVG DETECTED
    ↓
LOOK FOR 15M FVG (check last 10 candles)
    ↓
CALCULATE ENTRY, SL, TP
    ↓
VALIDATE RR & SL distance
    ↓
CALCULATE POSITION SIZE
    ↓
PLACE LIMIT ORDER on Binance
    ↓
SET EXPIRY TIME (current_time + 4H)
    ↓
    ┌────────────────────────────┐
    │ Wait for fill or expiry... │
    └────────────────────────────┘
    ↓                           ↓
ORDER FILLED               ORDER EXPIRED
    ↓                           ↓
PLACE SL ORDER          SET COOLDOWN (4H)
PLACE TP ORDER               ↓
    ↓                      RETRY LATER
MONITOR EXECUTION           (if still valid)
    ↓
EXIT (SL/TP/TIMEOUT)
    ↓
MARK REJECTION as has_filled_trade = True
REMOVE from rejected_fvgs
```

---

## State Management

### FVG State
```python
class LiveFVG:
    # Identity
    id: str
    type: str  # 'BULLISH' or 'BEARISH'
    top: float
    bottom: float
    formed_time: datetime
    timeframe: str  # '4h' or '15m'

    # State flags
    entered: bool = False
    rejected: bool = False
    invalidated: bool = False
    has_filled_trade: bool = False

    # Tracking
    rejection_time: Optional[datetime] = None
    rejection_price: Optional[float] = None
    highs_inside: List[float] = []
    lows_inside: List[float] = []

    # Pending setup tracking
    pending_setup_id: Optional[str] = None
    pending_expiry_time: Optional[datetime] = None
```

### Setup State
```python
class PendingSetup:
    # Identity
    setup_id: str
    parent_4h_fvg_id: str
    fvg_15m_id: str

    # Order details
    order_id: Optional[int] = None  # Binance order ID
    direction: str  # 'LONG' or 'SHORT'
    entry_price: float
    sl: float
    tp: float
    size: float

    # Timing
    created_time: datetime
    expiry_time: datetime

    # Status
    status: str  # 'PENDING', 'FILLED', 'EXPIRED', 'CANCELLED'
    fill_time: Optional[datetime] = None
    fill_price: Optional[float] = None
```

### Trade State
```python
class ActiveTrade:
    # Identity
    trade_id: str
    setup_id: str

    # Order IDs
    entry_order_id: int
    sl_order_id: int
    tp_order_id: int

    # Details
    direction: str
    entry_price: float
    entry_time: datetime
    sl: float
    tp: float
    size: float

    # P&L tracking
    current_pnl: float
    max_pnl: float
    max_dd: float

    # Status
    status: str  # 'ACTIVE', 'CLOSED_TP', 'CLOSED_SL', 'CLOSED_TIMEOUT'
    exit_price: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: Optional[float] = None
```

### State Persistence
```python
# Save state to disk every 5 minutes
state = {
    'active_4h_fvgs': [fvg.to_dict() for fvg in active_4h_fvgs],
    'rejected_4h_fvgs': [fvg.to_dict() for fvg in rejected_4h_fvgs],
    'pending_setups': [setup.to_dict() for setup in pending_setups],
    'active_trade': active_trade.to_dict() if active_trade else None,
    'last_updated': datetime.now().isoformat()
}

with open('state.json', 'w') as f:
    json.dump(state, f, indent=2)
```

---

## Order Execution Logic

### Critical Rules

#### 1. **Limit Order Fill Detection**
```python
# CRITICAL: Must wait for candle CLOSE before checking fill
# Do NOT use current candle - only check COMPLETED candles

def check_order_fill(order_id):
    """Query Binance API for order status"""
    order = client.get_order(symbol='BTCUSDT', orderId=order_id)

    if order['status'] == 'FILLED':
        return True, float(order['executedQty'])
    elif order['status'] == 'EXPIRED' or order['status'] == 'CANCELED':
        return False, 0
    else:
        return None, 0  # Still pending
```

#### 2. **Limit Order Expiry**
```python
def check_setup_expiry(setup: PendingSetup):
    """Check if setup has expired"""
    now = datetime.now()

    if now >= setup.expiry_time:
        # Cancel order on Binance
        try:
            client.cancel_order(symbol='BTCUSDT', orderId=setup.order_id)
        except Exception as e:
            logger.error(f"Failed to cancel order: {e}")

        # Set cooldown
        cooldown_time = now + timedelta(hours=4)
        parent_fvg.pending_expiry_time = cooldown_time

        # Update status
        setup.status = 'EXPIRED'

        # Remove from pending setups
        pending_setups.remove(setup)

        logger.info(f"Setup {setup.setup_id} expired. Cooldown until {cooldown_time}")
```

#### 3. **SL/TP Placement After Fill**
```python
def place_sl_tp_orders(trade: ActiveTrade):
    """Place SL and TP orders after limit order fills"""

    # CRITICAL: Use OCO (One-Cancels-Other) order
    # If one executes, the other is cancelled

    try:
        response = client.create_oco_order(
            symbol='BTCUSDT',
            side='SELL' if trade.direction == 'LONG' else 'BUY',
            quantity=trade.size,
            price=str(trade.tp),  # TP as limit order
            stopPrice=str(trade.sl * 1.001 if trade.direction == 'LONG' else trade.sl * 0.999),
            stopLimitPrice=str(trade.sl),
            stopLimitTimeInForce='GTC'
        )

        trade.sl_order_id = response['orders'][0]['orderId']
        trade.tp_order_id = response['orders'][1]['orderId']

        logger.info(f"SL/TP orders placed: SL={trade.sl_order_id}, TP={trade.tp_order_id}")

    except Exception as e:
        logger.error(f"Failed to place SL/TP: {e}")
        # EMERGENCY: Close position at market
        emergency_close_position(trade)
```

#### 4. **Only One Setup Per Rejection**
```python
def can_create_setup(rejected_fvg: LiveFVG) -> bool:
    """Check if we can create a setup from this rejection"""

    # Rule 1: Never create setup if already had filled trade
    if rejected_fvg.has_filled_trade:
        return False

    # Rule 2: Check cooldown period
    if rejected_fvg.pending_expiry_time:
        if datetime.now() < rejected_fvg.pending_expiry_time:
            return False

    # Rule 3: Check if already has pending setup
    if rejected_fvg.pending_setup_id:
        pending_setup = get_setup_by_id(rejected_fvg.pending_setup_id)
        if pending_setup and pending_setup.status == 'PENDING':
            return False

    return True
```

---

## Risk Management

### Position Sizing
```python
def calculate_position_size(entry: float, sl: float, balance: float) -> float:
    """Calculate position size based on risk"""

    risk_amount = balance * RISK_PER_TRADE  # 2% of balance
    risk_per_unit = abs(entry - sl)

    size = risk_amount / risk_per_unit

    # Apply lot size filter (Binance)
    size = round_to_lot_size(size, 'BTCUSDT')

    # Check minimum notional (Binance requires min $10)
    notional = size * entry
    if notional < 10:
        logger.warning(f"Notional {notional} < 10, increasing size")
        size = 10 / entry
        size = round_to_lot_size(size, 'BTCUSDT')

    return size
```

### Validation
```python
def validate_setup(entry: float, sl: float, tp: float) -> bool:
    """Validate setup before placing order"""

    # 1. Check SL distance
    sl_distance_pct = abs(entry - sl) / entry * 100
    if sl_distance_pct < MIN_SL_PCT:
        logger.warning(f"SL too tight: {sl_distance_pct:.2f}% < {MIN_SL_PCT}%")
        return False

    # 2. Check RR ratio
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    rr = reward / risk
    if rr < FIXED_RR:
        logger.warning(f"RR too low: {rr:.2f} < {FIXED_RR}")
        return False

    # 3. Check price sanity (not too far from current)
    current_price = get_current_price()
    max_distance_pct = 5  # Max 5% from current price
    distance_pct = abs(entry - current_price) / current_price * 100
    if distance_pct > max_distance_pct:
        logger.warning(f"Entry too far from current: {distance_pct:.2f}% > {max_distance_pct}%")
        return False

    return True
```

### Emergency Stop
```python
def check_emergency_stop() -> bool:
    """Check if we should stop trading"""

    # 1. Max drawdown exceeded
    current_dd = calculate_current_drawdown()
    if current_dd > MAX_DRAWDOWN_PCT:
        logger.critical(f"Max DD exceeded: {current_dd:.2f}% > {MAX_DRAWDOWN_PCT}%")
        return True

    # 2. Daily loss limit
    daily_pnl = calculate_daily_pnl()
    if daily_pnl < -MAX_DAILY_LOSS:
        logger.critical(f"Daily loss limit hit: ${daily_pnl:.2f}")
        return True

    # 3. Connection issues
    if not is_connected_to_binance():
        logger.critical("Lost connection to Binance")
        return True

    return False
```

---

## Edge Cases & Error Handling

### 1. **Binance API Errors**
```python
def handle_api_error(error: Exception, operation: str):
    """Handle Binance API errors"""

    if 'insufficient balance' in str(error).lower():
        logger.critical("Insufficient balance!")
        pause_trading()

    elif 'rate limit' in str(error).lower():
        logger.warning("Rate limit hit, sleeping 60s")
        time.sleep(60)

    elif 'invalid symbol' in str(error).lower():
        logger.critical(f"Invalid symbol in {operation}")
        stop_trading()

    else:
        logger.error(f"API error in {operation}: {error}")
        # Retry with exponential backoff
        retry_with_backoff(operation)
```

### 2. **WebSocket Disconnection**
```python
def on_websocket_error(error):
    """Handle WebSocket errors"""
    logger.error(f"WebSocket error: {error}")

    # Close all pending orders (safety)
    cancel_all_pending_orders()

    # Reconnect
    reconnect_websocket()
```

### 3. **Partial Fills**
```python
def handle_partial_fill(order):
    """Handle partially filled orders"""

    filled_qty = float(order['executedQty'])
    total_qty = float(order['origQty'])

    if filled_qty < total_qty:
        logger.warning(f"Partial fill: {filled_qty}/{total_qty}")

        # Cancel remaining
        client.cancel_order(symbol='BTCUSDT', orderId=order['orderId'])

        # Adjust SL/TP for filled quantity only
        adjust_sl_tp_for_partial(filled_qty)
```

### 4. **Price Slippage on SL**
```python
def monitor_sl_execution():
    """Monitor SL execution for slippage"""

    # SL is market order, can have slippage
    # Log actual fill price vs expected

    if trade.exit_price:
        expected_sl = trade.sl
        actual_exit = trade.exit_price

        slippage_pct = abs(actual_exit - expected_sl) / expected_sl * 100

        if slippage_pct > 0.5:  # More than 0.5% slippage
            logger.warning(f"SL slippage: {slippage_pct:.2f}%")
```

### 5. **System Restart Recovery**
```python
def recover_from_restart():
    """Recover state after system restart"""

    # 1. Load state from disk
    state = load_state_from_disk()

    # 2. Query Binance for open orders
    open_orders = client.get_open_orders(symbol='BTCUSDT')

    # 3. Reconcile state with Binance
    for order in open_orders:
        if order['orderId'] not in state['pending_setups']:
            # Found unknown order - cancel it
            logger.warning(f"Unknown order {order['orderId']}, cancelling")
            client.cancel_order(symbol='BTCUSDT', orderId=order['orderId'])

    # 4. Check if we have active trade
    if state['active_trade']:
        # Verify positions on Binance
        positions = client.get_position_risk(symbol='BTCUSDT')
        # Reconcile...

    logger.info("Recovery complete")
```

---

## Binance API Integration

### Authentication
```python
from binance.client import Client
from binance.enums import *
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
DRY_RUN = os.getenv('DRY_RUN', 'true').lower() == 'true'

if DRY_RUN:
    # Use testnet
    client = Client(API_KEY, API_SECRET, testnet=True)
else:
    # Use mainnet
    client = Client(API_KEY, API_SECRET)
```

### Key API Calls

#### 1. **Fetch Klines**
```python
def fetch_klines(symbol: str, interval: str, limit: int = 500):
    """Fetch historical candles"""
    klines = client.get_klines(
        symbol=symbol,
        interval=interval,
        limit=limit
    )

    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])

    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)

    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)

    return df
```

#### 2. **Place Limit Order**
```python
def place_limit_order(symbol: str, side: str, quantity: float, price: float):
    """Place limit order"""
    try:
        order = client.create_order(
            symbol=symbol,
            side=side,  # 'BUY' or 'SELL'
            type=ORDER_TYPE_LIMIT,
            timeInForce=TIME_IN_FORCE_GTC,
            quantity=quantity,
            price=str(price)
        )

        logger.info(f"Limit order placed: {order['orderId']}")
        return order

    except Exception as e:
        logger.error(f"Failed to place limit order: {e}")
        raise
```

#### 3. **WebSocket Stream**
```python
from binance.streams import ThreadedWebsocketManager

def start_websocket():
    """Start WebSocket for real-time candles"""

    twm = ThreadedWebsocketManager(api_key=API_KEY, api_secret=API_SECRET)
    twm.start()

    # Stream 4H candles
    twm.start_kline_socket(
        callback=on_4h_candle,
        symbol='BTCUSDT',
        interval='4h'
    )

    # Stream 15M candles
    twm.start_kline_socket(
        callback=on_15m_candle,
        symbol='BTCUSDT',
        interval='15m'
    )

    return twm
```

---

## Testing Plan

### 1. **Mock Order Testing**
```python
# Test with limit orders FAR from current price (won't fill)

current_price = 95000

# Test SHORT setup
mock_entry = current_price * 1.10  # +10% above current (won't fill)
mock_sl = mock_entry * 1.005
mock_tp = mock_entry - (abs(mock_entry - mock_sl) * 1.5)

place_limit_order('BTCUSDT', 'SELL', 0.001, mock_entry)

# Verify:
# 1. Order placed successfully
# 2. Order ID stored in state
# 3. Expiry timer started
# 4. After 4H, order cancelled
# 5. Cooldown period set
```

### 2. **State Persistence Test**
```python
# 1. Start bot
# 2. Create some FVGs and setups
# 3. Kill bot (Ctrl+C)
# 4. Restart bot
# 5. Verify state restored correctly
```

### 3. **Emergency Stop Test**
```python
# 1. Manually set high drawdown
# 2. Verify bot stops trading
# 3. Verify all orders cancelled
# 4. Verify notification sent
```

---

## Live Trading Safeguards

### 1. **Pre-Flight Checklist**
```python
def pre_flight_check() -> bool:
    """Run before starting live trading"""

    checks = []

    # 1. API credentials valid
    try:
        client.get_account()
        checks.append(('API Connection', True))
    except:
        checks.append(('API Connection', False))

    # 2. Sufficient balance
    balance = get_usdt_balance()
    if balance >= 100:
        checks.append(('Balance', True))
    else:
        checks.append(('Balance', False))

    # 3. Symbol info correct
    info = client.get_symbol_info('BTCUSDT')
    if info:
        checks.append(('Symbol Info', True))
    else:
        checks.append(('Symbol Info', False))

    # 4. State file writable
    try:
        with open('state.json', 'w') as f:
            json.dump({}, f)
        checks.append(('State File', True))
    except:
        checks.append(('State File', False))

    # Print results
    for check, passed in checks:
        status = '✅' if passed else '❌'
        print(f"{status} {check}")

    return all(passed for _, passed in checks)
```

### 2. **Dry Run Mode**
```python
# Always test with DRY_RUN=true first!
# Uses Binance testnet with fake money

if DRY_RUN:
    print("🧪 DRY RUN MODE - Using testnet")
    print("No real money at risk")
else:
    print("💰 LIVE TRADING MODE")
    confirmation = input("Type 'I UNDERSTAND THE RISKS' to continue: ")
    if confirmation != 'I UNDERSTAND THE RISKS':
        sys.exit("Aborted")
```

### 3. **Max Loss Limits**
```python
MAX_DRAWDOWN_PCT = 15.0        # Stop if DD > 15%
MAX_DAILY_LOSS = 500.0         # Stop if daily loss > $500
MAX_CONSECUTIVE_LOSSES = 5     # Stop if 5 losses in a row
```

### 4. **Monitoring & Alerts**
```python
def send_alert(message: str, level: str = 'INFO'):
    """Send alert via Telegram/Discord/Email"""

    if level == 'CRITICAL':
        # Send to all channels
        send_telegram(message)
        send_email(message)
    elif level == 'WARNING':
        send_telegram(message)
    else:
        logger.info(message)
```

---

## Performance Expectations

Based on backtest (2024):
- **Trades/year:** ~320
- **Win rate:** ~70%
- **Annual return:** ~600%
- **Max DD:** ~12%
- **Monthly return:** ~50%

**Note:** Live results will differ from backtest due to:
- Slippage
- Order fill rates
- Real-time latency
- Market conditions

**Conservative estimates for live:**
- **Win rate:** 60-65% (5-10% lower)
- **Annual return:** 300-400% (50% of backtest)
- **Max DD:** 15-20% (higher than backtest)

---

## Conclusion

This spec provides complete technical details for live implementation.

**Critical success factors:**
1. ✅ Strict adherence to order execution logic (no lookahead)
2. ✅ Robust state management (survive crashes)
3. ✅ Proper risk management (position sizing, stops)
4. ✅ Comprehensive error handling
5. ✅ Thorough testing before live deployment

**Ready to implement!** 🚀
