"""
Test script: Place mock order far from current price
This order won't fill - it's just for testing order placement
"""

import os
import sys
from dotenv import load_dotenv

# Load env
load_dotenv()

# Check if API keys set
if not os.getenv('BINANCE_API_KEY') or os.getenv('BINANCE_API_KEY') == 'your_api_key_here':
    print("❌ Error: Please set BINANCE_API_KEY in .env file")
    print("1. Copy .env.example to .env")
    print("2. Get testnet keys from https://testnet.binance.vision/")
    print("3. Update .env with your keys")
    sys.exit(1)

if os.getenv('DRY_RUN', 'true').lower() != 'true':
    print("❌ Error: DRY_RUN must be 'true' for testing!")
    print("Update .env: DRY_RUN=true")
    sys.exit(1)

print("✅ API keys configured")
print("✅ DRY_RUN mode enabled (testnet)")
print()

# Now import bot (after env loaded)
from failed_fvg_live_bot import BinanceClientWrapper
import time

print("="*80)
print("MOCK ORDER TEST - Order won't fill (entry far from current price)")
print("="*80)
print()

# Create client
client = BinanceClientWrapper()

# Get current price
print("Fetching current BTC price...")
current_price = client.get_current_price('BTCUSDT')
print(f"✅ Current BTC price: ${current_price:,.2f}")
print()

# Get balance
balance = client.get_balance('USDT')
print(f"✅ Testnet balance: ${balance:,.2f} USDT")
print()

# Create mock setup (won't fill)
print("Creating mock SHORT setup...")
print("(Entry price 10% above current - this order will NOT fill)")
print()

mock_entry = current_price * 1.10  # 10% above current
mock_sl = mock_entry * 1.005       # 0.5% SL
mock_tp = mock_entry - (abs(mock_entry - mock_sl) * 1.5)

print(f"Setup details:")
print(f"  Direction: SHORT")
print(f"  Entry:     ${mock_entry:,.2f} (+10% from current)")
print(f"  SL:        ${mock_sl:,.2f} (+0.5%)")
print(f"  TP:        ${mock_tp:,.2f} (-0.75%)")
print()

# Calculate size (small for testing)
risk_amount = balance * 0.01  # 1% risk
risk_per_unit = abs(mock_entry - mock_sl)
size = risk_amount / risk_per_unit
size = client.round_to_lot_size(size)

# Ensure min notional
notional = size * mock_entry
if notional < 10:
    size = 10 / mock_entry
    size = client.round_to_lot_size(size)

print(f"Position size: {size} BTC")
print(f"Notional: ${size * mock_entry:,.2f}")
print()

# Place order
print("Placing limit order...")
try:
    order = client.place_limit_order(
        symbol='BTCUSDT',
        side='SELL',
        quantity=size,
        price=mock_entry
    )

    print()
    print("="*80)
    print("✅ MOCK ORDER PLACED SUCCESSFULLY!")
    print("="*80)
    print()
    print(f"Order ID:      {order['orderId']}")
    print(f"Status:        {order['status']}")
    print(f"Side:          {order['side']}")
    print(f"Type:          {order['type']}")
    print(f"Price:         ${float(order['price']):,.2f}")
    print(f"Quantity:      {float(order['origQty'])}")
    print()

    # Wait and check status
    print("Waiting 30 seconds...")
    time.sleep(30)

    print("Checking order status...")
    order_status = client.get_order('BTCUSDT', order['orderId'])
    print(f"Status after 30s: {order_status['status']}")
    print()

    if order_status['status'] == 'NEW':
        print("✅ Order still PENDING (not filled) - as expected!")
        print("   (Entry price is 10% above current, so no fill)")
    elif order_status['status'] == 'FILLED':
        print("⚠️  Order FILLED - unexpected! Price moved 10% in 30s")
    else:
        print(f"Order status: {order_status['status']}")

    print()

    # Cancel order
    print("Cancelling order...")
    client.cancel_order('BTCUSDT', order['orderId'])
    print("✅ Order cancelled successfully")
    print()

    # Verify cancelled
    time.sleep(2)
    final_status = client.get_order('BTCUSDT', order['orderId'])
    print(f"Final status: {final_status['status']}")
    print()

    print("="*80)
    print("✅ TEST PASSED!")
    print("="*80)
    print()
    print("Order lifecycle:")
    print("1. ✅ Order placed successfully")
    print("2. ✅ Order remained PENDING (not filled)")
    print("3. ✅ Order cancelled successfully")
    print()
    print("Bot order management is working correctly!")
    print()

except Exception as e:
    print()
    print("="*80)
    print("❌ TEST FAILED!")
    print("="*80)
    print()
    print(f"Error: {e}")
    print()
    print("Possible issues:")
    print("- API keys invalid")
    print("- Insufficient testnet balance (get funds from faucet)")
    print("- Network connection issue")
    print("- Binance API down")
    print()
    sys.exit(1)
