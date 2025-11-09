"""
Простий тест для перевірки що всі модулі працюють
"""

import sys

def test_imports():
    """Тест імпорту всіх необхідних модулів"""
    print("🧪 Testing imports...")
    
    try:
        import pandas as pd
        print("  ✅ pandas")
    except ImportError:
        print("  ❌ pandas - run: pip install pandas")
        return False
    
    try:
        import numpy as np
        print("  ✅ numpy")
    except ImportError:
        print("  ❌ numpy - run: pip install numpy")
        return False
    
    try:
        import talib
        print("  ✅ TA-Lib")
    except ImportError:
        print("  ❌ TA-Lib - run: pip install TA-Lib")
        print("     Note: TA-Lib requires C dependencies")
        print("     macOS: brew install ta-lib")
        print("     Ubuntu: apt-get install ta-lib")
        return False
    
    try:
        from binance.client import Client
        print("  ✅ python-binance")
    except ImportError:
        print("  ❌ python-binance - run: pip install python-binance")
        return False
    
    try:
        from dotenv import load_dotenv
        print("  ✅ python-dotenv")
    except ImportError:
        print("  ❌ python-dotenv - run: pip install python-dotenv")
        return False
    
    try:
        from termcolor import colored
        print("  ✅ termcolor")
    except ImportError:
        print("  ❌ termcolor - run: pip install termcolor")
        return False
    
    return True

def test_env_file():
    """Тест наявності .env файлу"""
    print("\n🧪 Testing .env file...")
    
    import os
    from dotenv import load_dotenv
    
    if not os.path.exists('.env'):
        print("  ❌ .env file not found")
        print("     Create .env from env_example.txt")
        return False
    
    print("  ✅ .env file exists")
    
    load_dotenv()
    
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')
    
    if not api_key or api_key == 'your_api_key_here':
        print("  ⚠️  BINANCE_API_KEY not configured")
        print("     Add your API key to .env file")
        return False
    
    if not api_secret or api_secret == 'your_api_secret_here':
        print("  ⚠️  BINANCE_API_SECRET not configured")
        print("     Add your API secret to .env file")
        return False
    
    print("  ✅ API credentials configured")
    return True

def test_binance_connection():
    """Тест підключення до Binance"""
    print("\n🧪 Testing Binance connection...")
    
    import os
    from dotenv import load_dotenv
    from binance.client import Client
    
    load_dotenv()
    
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')
    testnet = os.getenv('BINANCE_TESTNET', 'True').lower() == 'true'
    
    if not api_key or not api_secret:
        print("  ⏭️  Skipping (credentials not configured)")
        return True
    
    try:
        client = Client(api_key, api_secret, testnet=testnet)
        
        # Try to get server time
        server_time = client.get_server_time()
        print(f"  ✅ Connected to Binance {'Testnet' if testnet else 'Live'}")
        
        # Try to get account balance
        account = client.futures_account()
        print("  ✅ Account access OK")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Connection failed: {e}")
        print("     Check your API keys and network connection")
        return False

def test_strategy_logic():
    """Тест логіки стратегії"""
    print("\n🧪 Testing strategy logic...")
    
    try:
        import pandas as pd
        import numpy as np
        
        # Create sample data
        dates = pd.date_range('2025-01-01', periods=20, freq='4h')
        data = pd.DataFrame({
            'open': np.random.uniform(48000, 52000, 20),
            'high': np.random.uniform(50000, 53000, 20),
            'low': np.random.uniform(47000, 50000, 20),
            'close': np.random.uniform(48000, 52000, 20),
            'volume': np.random.uniform(100, 1000, 20)
        }, index=dates)
        
        print("  ✅ Sample data created")
        
        # Test indicators
        import talib
        atr = talib.ATR(data['high'].values, data['low'].values, data['close'].values, 14)
        
        if len(atr) > 0 and not np.isnan(atr[-1]):
            print("  ✅ ATR calculation works")
        else:
            print("  ⚠️  ATR returned NaN (expected for small dataset)")
        
        # Test swing calculations
        swing_high = data['high'].tail(5).max()
        swing_low = data['low'].tail(5).min()
        
        print(f"  ✅ Swing high/low calculated: {swing_high:.2f} / {swing_low:.2f}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Strategy test failed: {e}")
        return False

def main():
    """Запуск всіх тестів"""
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║         🧪 BOT DIAGNOSTICS & CONFIGURATION TEST 🔧           ║")
    print("╚═══════════════════════════════════════════════════════════════╝\n")
    
    results = []
    
    # Run tests
    results.append(("Imports", test_imports()))
    results.append(("Environment", test_env_file()))
    results.append(("Binance Connection", test_binance_connection()))
    results.append(("Strategy Logic", test_strategy_logic()))
    
    # Summary
    print("\n" + "="*65)
    print("📊 TEST SUMMARY")
    print("="*65)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status:10} - {name}")
    
    print("="*65)
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n✅ All tests passed! Bot is ready to run.")
        print("   Start bot with: python liquidity_sweep_bot.py")
        print("   Or use: ./start_bot.sh")
    else:
        print("\n⚠️  Some tests failed. Fix the issues above before running the bot.")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())

