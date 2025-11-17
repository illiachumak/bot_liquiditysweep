#!/usr/bin/env python3
"""
Run simulation for last 2 months with detailed trade logging
"""

from datetime import datetime, timedelta
from simulate_live_bot_2024 import LiveBotSimulator

# Calculate last 2 months (approximately 60 days)
end_date = datetime(2024, 12, 31)  # Use end of 2024 as reference
start_date = end_date - timedelta(days=60)

start_str = start_date.strftime('%Y-%m-%d')
end_str = end_date.strftime('%Y-%m-%d')

print(f"Running simulation for last 2 months of 2024:")
print(f"Period: {start_str} to {end_str}")
print()

sim = LiveBotSimulator(initial_balance=10000.0)
sim.run_simulation(start_date=start_str, end_date=end_str, log_trades=True)

print("\n✅ Simulation complete!")
print(f"Results saved to: simulation_last_2months_results.json")

