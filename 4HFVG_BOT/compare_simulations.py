"""
Compare results from both simulation methods:
1. simulate_live_bot_2024.py (original)
2. failed_fvg_live_bot.py run_simulation() (new)

This verifies that the live bot produces identical results to the simulation.
"""

import sys
sys.path.append('/Users/illiachumak/trading/implement/4HFVG_BOT')

from simulate_live_bot_2024 import LiveBotSimulator
from failed_fvg_live_bot import run_simulation

def compare_trades(trades1, trades2):
    """Compare two lists of trades"""

    if len(trades1) != len(trades2):
        print(f"❌ TRADE COUNT MISMATCH: {len(trades1)} vs {len(trades2)}")
        return False

    print(f"✅ Trade count matches: {len(trades1)}")

    mismatches = []

    for i, (t1, t2) in enumerate(zip(trades1, trades2)):
        # Compare key fields
        fields_to_compare = ['entry_price', 'exit_price', 'exit_reason', 'direction', 'sl', 'tp']

        for field in fields_to_compare:
            val1 = t1.get(field)
            val2 = t2.get(field)

            # For float comparisons, allow small differences
            if isinstance(val1, float) and isinstance(val2, float):
                if abs(val1 - val2) > 0.01:  # Allow 1 cent difference
                    mismatches.append(f"Trade #{i+1}: {field} mismatch - {val1} vs {val2}")
            elif val1 != val2:
                mismatches.append(f"Trade #{i+1}: {field} mismatch - {val1} vs {val2}")

    if mismatches:
        print(f"\n❌ Found {len(mismatches)} mismatches:")
        for m in mismatches[:10]:  # Show first 10
            print(f"   {m}")
        if len(mismatches) > 10:
            print(f"   ... and {len(mismatches) - 10} more")
        return False
    else:
        print("✅ All trades match!")
        return True


def main():
    print("="*80)
    print("SIMULATION COMPARISON TEST")
    print("="*80)
    print("\nRunning both simulations for 2024...\n")

    # Run original simulation
    print("1️⃣  Running original simulation (simulate_live_bot_2024.py)...")
    print("-" * 80)

    sim1 = LiveBotSimulator(initial_balance=10000.0)
    sim1.run_simulation(start_date='2024-01-01', end_date='2024-12-31')

    results1 = {
        'total_trades': len(sim1.trades_history),
        'final_balance': sim1.balance,
        'total_pnl': sim1.balance - sim1.initial_balance,
        'trades': sim1.trades_history
    }

    print("\n" + "="*80)
    print("2️⃣  Running new simulation (failed_fvg_live_bot.py)...")
    print("-" * 80)

    # Run new simulation
    results2 = run_simulation('2024-01-01', '2024-12-31')

    # Compare results
    print("\n" + "="*80)
    print("COMPARISON RESULTS")
    print("="*80)

    print("\n📊 Summary:")
    print(f"Original Simulation:")
    print(f"  Trades: {results1['total_trades']}")
    print(f"  Final Balance: ${results1['final_balance']:,.2f}")
    print(f"  Total PnL: ${results1['total_pnl']:+,.2f}")

    print(f"\nLive Bot Simulation:")
    print(f"  Trades: {results2['total_trades']}")
    print(f"  Final Balance: ${results2['final_balance']:,.2f}")
    print(f"  Total PnL: ${results2['total_pnl']:+,.2f}")

    # Check if results match
    print("\n🔍 Detailed Comparison:")

    # Compare totals
    if results1['total_trades'] == results2['total_trades']:
        print(f"✅ Total trades match: {results1['total_trades']}")
    else:
        print(f"❌ Total trades differ: {results1['total_trades']} vs {results2['total_trades']}")

    if abs(results1['final_balance'] - results2['final_balance']) < 0.01:
        print(f"✅ Final balance matches: ${results1['final_balance']:,.2f}")
    else:
        print(f"❌ Final balance differs: ${results1['final_balance']:,.2f} vs ${results2['final_balance']:,.2f}")
        diff = abs(results1['final_balance'] - results2['final_balance'])
        print(f"   Difference: ${diff:.2f}")

    # Compare individual trades
    print("\n📋 Trade-by-Trade Comparison:")
    trades_match = compare_trades(results1['trades'], results2['trades'])

    # Final verdict
    print("\n" + "="*80)
    if trades_match and results1['total_trades'] == results2['total_trades']:
        print("✅ SUCCESS: Both simulations produce IDENTICAL results!")
        print("="*80)
        return 0
    else:
        print("❌ FAILURE: Simulations produce DIFFERENT results!")
        print("="*80)
        return 1


if __name__ == '__main__':
    exit(main())
