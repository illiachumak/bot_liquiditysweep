#!/usr/bin/env python3
"""
Quick test for Binance Futures Testnet API connection
"""
import os
from dotenv import load_dotenv
from binance.client import Client
from binance.exceptions import BinanceAPIException

load_dotenv()

API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
TESTNET = os.getenv('BINANCE_TESTNET', 'True').lower() == 'true'

print("=" * 60)
print("🧪 Binance Futures API Test")
print("=" * 60)
print(f"Testnet mode: {TESTNET}")
print(f"API Key: {API_KEY[:10]}...{API_KEY[-5:]}" if API_KEY else "API Key: NOT SET")
print("=" * 60)

if not API_KEY or not API_SECRET:
    print("❌ Error: API keys not found in .env file!")
    exit(1)

# Create client
client = Client(API_KEY, API_SECRET, tld='com')

if TESTNET:
    print("\n📍 Configuring Testnet URLs...")
    client.FUTURES_URL = 'https://testnet.binancefuture.com'
    client.FUTURES_DATA_URL = 'https://testnet.binancefuture.com'
    client.FUTURES_COIN_URL = 'https://testnet.binancefuture.com'
    print(f"   Using: {client.FUTURES_URL}")

print("\n🔍 Testing connection...")

# Test 1: Get server time
try:
    print("\n1️⃣ Testing server time...")
    server_time = client.futures_time()
    print(f"   ✅ Server time: {server_time['serverTime']}")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    exit(1)

# Test 2: Get exchange info
try:
    print("\n2️⃣ Testing exchange info...")
    exchange_info = client.futures_exchange_info()
    symbols_count = len(exchange_info.get('symbols', []))
    print(f"   ✅ Exchange info: {symbols_count} symbols available")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    exit(1)

# Test 3: Get klines (doesn't require API key)
try:
    print("\n3️⃣ Testing market data (klines)...")
    klines = client.futures_klines(symbol='BTCUSDT', interval='1h', limit=5)
    print(f"   ✅ Fetched {len(klines)} candles for BTCUSDT")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    exit(1)

# Test 4: Get account info (requires valid API key with permissions)
try:
    print("\n4️⃣ Testing account access (requires valid API key)...")
    account = client.futures_account()
    
    # Find USDT balance
    usdt_balance = 0.0
    for asset in account.get('assets', []):
        if asset['asset'] == 'USDT':
            usdt_balance = float(asset['availableBalance'])
            break
    
    print(f"   ✅ Account access OK!")
    print(f"   💰 USDT Balance: ${usdt_balance:.2f}")
    
    # Show position mode
    position_mode = account.get('positionSide', 'Unknown')
    print(f"   📊 Position mode: {position_mode}")
    
except BinanceAPIException as e:
    print(f"   ❌ API Error: {e.code} - {e.message}")
    if e.code == -5000:
        print("\n⚠️  Error -5000 means:")
        print("   1. Wrong API endpoint (check if using testnet keys with testnet mode)")
        print("   2. API keys don't have Futures permission")
        print("   3. Using mainnet keys with testnet mode (or vice versa)")
        print("\n💡 Solution:")
        print("   - For TESTNET: Get keys from https://testnet.binancefuture.com/")
        print("   - For LIVE: Get keys from binance.com with 'Enable Futures' ON")
    exit(1)
except Exception as e:
    print(f"   ❌ Failed: {e}")
    exit(1)

# Test 5: Test position info
try:
    print("\n5️⃣ Testing position info...")
    positions = client.futures_position_information(symbol='BTCUSDT')
    print(f"   ✅ Position info: {len(positions)} positions")
except Exception as e:
    print(f"   ❌ Failed: {e}")

print("\n" + "=" * 60)
print("✅ All tests passed! Your API is working correctly!")
print("=" * 60)
print("\n🚀 You can now start the bot with confidence!")

