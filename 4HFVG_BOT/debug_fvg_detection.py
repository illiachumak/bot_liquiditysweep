#!/usr/bin/env python3
"""
Debug FVG Detection Logic
Simulates live bot logic with real Binance data from last 2 days
"""

import os
import sys
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Import bot classes
from failed_fvg_live_bot import LiveFVG, FVGDetector
from binance.client import Client

load_dotenv()

SYMBOL = 'BTCUSDT'
TIMEFRAME_4H = '4h'
TIMEFRAME_15M = '15m'

# Use REAL API (not testnet) for debugging
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
USE_FUTURES = True  # Same as live bot

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_header(text: str):
    """Print colored header"""
    print(f"\n{BLUE}{'='*80}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'='*80}{RESET}\n")


def print_section(text: str):
    """Print colored section"""
    print(f"\n{YELLOW}{'-'*80}{RESET}")
    print(f"{YELLOW}{text}{RESET}")
    print(f"{YELLOW}{'-'*80}{RESET}\n")


def print_fvg(fvg: LiveFVG, prefix: str = "", detailed: bool = False):
    """Print FVG info"""
    color = GREEN if fvg.type == 'BULLISH' else RED
    print(f"{prefix}{color}  {fvg.type:8} FVG: ${fvg.bottom:>10.2f} - ${fvg.top:>10.2f}  (formed: {fvg.formed_time}){RESET}")
    if detailed:
        # Gap is always positive (top - bottom)
        gap = abs(fvg.top - fvg.bottom)
        print(f"{prefix}      ID: {fvg.id}")
        print(f"{prefix}      Gap Size: ${gap:.2f}")
        print(f"{prefix}      Entered: {fvg.entered}, Rejected: {fvg.rejected}, Invalidated: {fvg.invalidated}")
        if fvg.rejected:
            print(f"{prefix}      Rejection: ${fvg.rejection_price:.2f} at {fvg.rejection_time}")


def print_candle(candle: pd.Series, idx: int, is_closed: bool = True):
    """Print candle info"""
    status = "CLOSED" if is_closed else "OPEN"
    color = GREEN if is_closed else YELLOW
    print(f"{color}[{status:6}] Candle #{idx:2} | Time: {candle.name} | "
          f"O: ${candle['open']:>10.2f} | H: ${candle['high']:>10.2f} | "
          f"L: ${candle['low']:>10.2f} | C: ${candle['close']:>10.2f}{RESET}")


class FVGDetectionDebugger:
    """Debug FVG detection logic"""
    
    def __init__(self):
        # Use REAL API (not testnet)
        self.client = Client(API_KEY, API_SECRET, testnet=False)
        self.detector = FVGDetector()
        self.active_4h_fvgs: List[LiveFVG] = []
        self.last_4h_candle_time: Optional[pd.Timestamp] = None
        
    def load_data(self, days: int = 2):
        """Load last N days of data"""
        print_header(f"Loading last {days} days of data from Binance")
        
        # Calculate time range
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        print(f"Time range: {start_time} to {end_time}")
        
        # Load 4H data (need more to have enough for FVG detection)
        # Use futures API if enabled
        if USE_FUTURES:
            klines_4h = self.client.futures_klines(symbol=SYMBOL, interval=TIMEFRAME_4H, limit=100)
            klines_15m = self.client.futures_klines(symbol=SYMBOL, interval=TIMEFRAME_15M, limit=500)
        else:
            klines_4h = self.client.get_klines(symbol=SYMBOL, interval=TIMEFRAME_4H, limit=100)
            klines_15m = self.client.get_klines(symbol=SYMBOL, interval=TIMEFRAME_15M, limit=500)
        
        # Convert to DataFrame
        df_4h = pd.DataFrame(klines_4h, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        df_4h['timestamp'] = pd.to_datetime(df_4h['timestamp'], unit='ms')
        df_4h.set_index('timestamp', inplace=True)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df_4h[col] = df_4h[col].astype(float)
        
        df_15m = pd.DataFrame(klines_15m, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base',
            'taker_buy_quote', 'ignore'
        ])
        df_15m['timestamp'] = pd.to_datetime(df_15m['timestamp'], unit='ms')
        df_15m.set_index('timestamp', inplace=True)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df_15m[col] = df_15m[col].astype(float)
        
        # Filter to last N days
        df_4h = df_4h[df_4h.index >= start_time]
        df_15m = df_15m[df_15m.index >= start_time]
        
        print(f"✅ Loaded {len(df_4h)} 4H candles")
        print(f"✅ Loaded {len(df_15m)} 15M candles")
        
        if len(df_4h) < 3:
            print(f"{RED}⚠️  Not enough 4H candles for FVG detection (need at least 3){RESET}")
            return None, None
        
        return df_4h, df_15m
    
    def detect_fvg_from_candle(self, closed_candle: pd.Series, prev_candle_2: pd.Series, 
                                closed_idx: int) -> Optional[LiveFVG]:
        """Detect FVG from closed candle"""
        # Bullish FVG: low[i] > high[i-2]
        if closed_candle['low'] > prev_candle_2['high']:
            fvg = LiveFVG(
                id=f"4h_BULLISH_{closed_candle['low']:.2f}_{prev_candle_2['high']:.2f}_{int(closed_candle.name.timestamp())}",
                type='BULLISH',
                top=closed_candle['low'],
                bottom=prev_candle_2['high'],
                formed_time=closed_candle.name,
                timeframe='4h'
            )
            return fvg
        
        # Bearish FVG: high[i] < low[i-2]
        elif closed_candle['high'] < prev_candle_2['low']:
            fvg = LiveFVG(
                id=f"4h_BEARISH_{prev_candle_2['low']:.2f}_{closed_candle['high']:.2f}_{int(closed_candle.name.timestamp())}",
                type='BEARISH',
                top=prev_candle_2['low'],
                bottom=closed_candle['high'],
                formed_time=closed_candle.name,
                timeframe='4h'
            )
            return fvg
        
        return None
    
    def simulate_candle_processing(self, df_4h: pd.DataFrame):
        """Simulate live bot candle processing"""
        print_header("Simulating Live Bot Logic")
        
        # Initialize with first candle
        if len(df_4h) == 0:
            print(f"{RED}No candles to process{RESET}")
            return
        
        # Start from index 2 (need at least 3 candles for FVG detection)
        # IMPORTANT: Don't process the last candle (it's still open/forming)
        total_candles = len(df_4h)
        last_closed_idx = total_candles - 2  # Last closed candle is second to last
        
        print(f"Starting simulation from candle index 2 (need at least 3 candles for FVG detection)")
        print(f"Total candles: {total_candles} (last one at index {total_candles-1} is still OPEN)")
        print(f"Will process up to index {last_closed_idx} (last closed candle)\n")
        
        # Process each new candle (but skip the last one - it's still open)
        for i in range(2, total_candles):
            current_candle = df_4h.iloc[i]
            current_time = df_4h.index[i]
            
            # Check if this is the last candle (still open)
            is_last_candle = (i == total_candles - 1)
            
            print_section(f"Processing Candle #{i} at {current_time}")
            
            # Check if this is a "new" candle (simulating check_new_4h_candle)
            if self.last_4h_candle_time is None or current_time > self.last_4h_candle_time:
                if is_last_candle:
                    print(f"{YELLOW}⚠️  This is the LAST candle (still OPEN/forming) - skipping FVG detection{RESET}")
                    print_candle(current_candle, i, is_closed=False)
                    
                    # BUT: Process the PREVIOUS candle (i-1) as closed if we haven't yet
                    if self.last_4h_candle_time is not None:
                        closed_candle_idx = i - 1
                        if closed_candle_idx >= 0 and closed_candle_idx < total_candles:
                            closed_candle = df_4h.iloc[closed_candle_idx]
                            actual_closed_time = df_4h.index[closed_candle_idx]
                            
                            # Only process if we haven't processed this candle yet
                            if actual_closed_time == self.last_4h_candle_time:
                                print(f"\n{YELLOW}📊 Processing PREVIOUS CLOSED candle (index {closed_candle_idx}) before skipping last{RESET}")
                                print_candle(closed_candle, closed_candle_idx, is_closed=True)
                                
                                # Check if we can detect FVG from closed candle
                                if closed_candle_idx >= 2:
                                    prev_candle_2 = df_4h.iloc[closed_candle_idx - 2]
                                    
                                    print(f"\n   Previous candles:")
                                    print_candle(prev_candle_2, closed_candle_idx - 2, is_closed=True)
                                    
                                    # Detect FVG
                                    fvg = self.detect_fvg_from_candle(closed_candle, prev_candle_2, closed_candle_idx)
                                    
                                    if fvg:
                                        exists = any(existing.id == fvg.id for existing in self.active_4h_fvgs)
                                        
                                        if not exists:
                                            self.active_4h_fvgs.append(fvg)
                                            print(f"\n{GREEN}✅ NEW FVG DETECTED:{RESET}")
                                            print_fvg(fvg, "", detailed=True)
                    
                    print(f"\n   📋 Active FVGs: {len(self.active_4h_fvgs)}")
                    if self.active_4h_fvgs:
                        for idx, fvg in enumerate(self.active_4h_fvgs, 1):
                            print(f"\n      FVG #{idx}:")
                            print_fvg(fvg, "         ", detailed=True)
                    else:
                        print(f"      (none)")
                    # Update timestamp but don't process FVG detection for the open candle
                    self.last_4h_candle_time = current_time
                    continue
                
                print(f"{GREEN}🕯️  New 4H candle detected!{RESET}")
                print(f"   Previous: {self.last_4h_candle_time}")
                print(f"   Current:  {current_time}")
                
                # Show current candle (still forming)
                print_candle(current_candle, i, is_closed=False)
                
                # CRITICAL: When new candle appears, the PREVIOUS candle is now closed
                if self.last_4h_candle_time is not None:
                    # Find the closed candle (the one that just finished)
                    # It should be at index i-1 (previous to current)
                    closed_candle_idx = i - 1
                    
                    # Verify it matches last_4h_candle_time
                    if closed_candle_idx >= 0 and closed_candle_idx < len(df_4h):
                        actual_closed_time = df_4h.index[closed_candle_idx]
                        if actual_closed_time != self.last_4h_candle_time:
                            print(f"{YELLOW}⚠️  Warning: Closed candle time mismatch!{RESET}")
                            print(f"   Expected: {self.last_4h_candle_time}")
                            print(f"   Actual:   {actual_closed_time}")
                            print(f"   Using index {closed_candle_idx} anyway")
                    
                    print(f"\n{YELLOW}📊 Processing CLOSED candle (index {closed_candle_idx}){RESET}")
                    closed_candle = df_4h.iloc[closed_candle_idx]
                    print_candle(closed_candle, closed_candle_idx, is_closed=True)
                    
                    # Check if we can detect FVG from closed candle
                    if closed_candle_idx >= 2:
                        prev_candle_2 = df_4h.iloc[closed_candle_idx - 2]
                        prev_candle_1 = df_4h.iloc[closed_candle_idx - 1] if closed_candle_idx >= 1 else None
                        
                        print(f"\n   Previous candles:")
                        if prev_candle_1 is not None:
                            print_candle(prev_candle_1, closed_candle_idx - 1, is_closed=True)
                        print_candle(prev_candle_2, closed_candle_idx - 2, is_closed=True)
                        
                        # Show FVG detection conditions
                        print(f"\n   FVG Detection Conditions:")
                        print(f"   Bullish FVG: Low[{closed_candle_idx}] > High[{closed_candle_idx-2}]")
                        print(f"      {closed_candle['low']:.2f} > {prev_candle_2['high']:.2f} ? {closed_candle['low'] > prev_candle_2['high']}")
                        print(f"   Bearish FVG: High[{closed_candle_idx}] < Low[{closed_candle_idx-2}]")
                        print(f"      {closed_candle['high']:.2f} < {prev_candle_2['low']:.2f} ? {closed_candle['high'] < prev_candle_2['low']}")
                        
                        # Detect FVG
                        fvg = self.detect_fvg_from_candle(closed_candle, prev_candle_2, closed_candle_idx)
                        
                        if fvg:
                            # Check if already exists
                            exists = any(existing.id == fvg.id for existing in self.active_4h_fvgs)
                            
                            if not exists:
                                self.active_4h_fvgs.append(fvg)
                                print(f"\n{GREEN}{'='*80}{RESET}")
                                print(f"{GREEN}✅ NEW FVG DETECTED:{RESET}")
                                print(f"{GREEN}{'='*80}{RESET}")
                                print_fvg(fvg, "", detailed=True)
                                print(f"\n   📊 Formation Details:")
                                print(f"   Closed candle: {closed_candle.name} (index {closed_candle_idx})")
                                print(f"   Prev-2 candle: {prev_candle_2.name} (index {closed_candle_idx-2})")
                                
                                # Show gap calculation
                                if fvg.type == 'BULLISH':
                                    gap = closed_candle['low'] - prev_candle_2['high']
                                    print(f"\n   🔍 Bullish FVG Calculation:")
                                    print(f"   Low[{closed_candle_idx}]:  ${closed_candle['low']:.2f}")
                                    print(f"   High[{closed_candle_idx-2}]: ${prev_candle_2['high']:.2f}")
                                    print(f"   Gap: ${gap:.2f} ({GREEN}✓ Low > High{RESET})")
                                    print(f"   FVG Zone: ${fvg.bottom:.2f} - ${fvg.top:.2f}")
                                else:
                                    gap = prev_candle_2['low'] - closed_candle['high']
                                    print(f"\n   🔍 Bearish FVG Calculation:")
                                    print(f"   High[{closed_candle_idx}]: ${closed_candle['high']:.2f}")
                                    print(f"   Low[{closed_candle_idx-2}]:  ${prev_candle_2['low']:.2f}")
                                    print(f"   Gap: ${gap:.2f} ({RED}✓ High < Low{RESET})")
                                    print(f"   FVG Zone: ${fvg.bottom:.2f} - ${fvg.top:.2f}")
                                print(f"{GREEN}{'='*80}{RESET}\n")
                            else:
                                print(f"\n{YELLOW}⚠️  FVG already exists (skipped){RESET}")
                                print_fvg(fvg, "   ")
                        else:
                            print(f"\n   No FVG detected from this closed candle")
                    else:
                        print(f"\n{YELLOW}⚠️  Not enough candles for FVG detection (need closed_idx >= 2, got {closed_candle_idx}){RESET}")
                
                # Update timestamp
                self.last_4h_candle_time = current_time
                
                print(f"\n   📋 Active FVGs: {len(self.active_4h_fvgs)}")
                if self.active_4h_fvgs:
                    for idx, fvg in enumerate(self.active_4h_fvgs, 1):
                        print(f"\n      FVG #{idx}:")
                        print_fvg(fvg, "         ", detailed=True)
                else:
                    print(f"      (none)")
            else:
                print(f"{GRAY}   No new candle (current time <= last candle time){RESET}")
    
    def compare_with_batch_detection(self, df_4h: pd.DataFrame):
        """Compare with batch detection (all at once)"""
        print_header("Comparing with Batch Detection (All FVGs at once)")
        
        # IMPORTANT: Exclude last candle (still open) from batch detection
        # Only process closed candles
        df_4h_closed = df_4h.iloc[:-1] if len(df_4h) > 0 else df_4h
        
        print(f"Batch detection: processing {len(df_4h_closed)} closed candles (excluding last open candle)")
        
        # Detect all FVGs using batch method (only from closed candles)
        all_fvgs = self.detector.detect_fvgs(df_4h_closed, '4h')
        
        print(f"Batch detection found {len(all_fvgs)} FVGs:")
        for idx, fvg in enumerate(all_fvgs, 1):
            print(f"\n   FVG #{idx}:")
            print_fvg(fvg, "      ", detailed=True)
        
        print(f"\nSimulated detection found {len(self.active_4h_fvgs)} FVGs:")
        for idx, fvg in enumerate(self.active_4h_fvgs, 1):
            print(f"\n   FVG #{idx}:")
            print_fvg(fvg, "      ", detailed=True)
        
        # Compare
        batch_ids = {fvg.id for fvg in all_fvgs}
        sim_ids = {fvg.id for fvg in self.active_4h_fvgs}
        
        missing = batch_ids - sim_ids
        extra = sim_ids - batch_ids
        
        print(f"\n{GREEN}✅ Matching FVGs: {len(batch_ids & sim_ids)}{RESET}")
        
        if missing:
            print(f"\n{RED}❌ Missing in simulation ({len(missing)}):{RESET}")
            for fvg_id in missing:
                fvg = next(f for f in all_fvgs if f.id == fvg_id)
                print_fvg(fvg, "   ")
        
        if extra:
            print(f"\n{YELLOW}⚠️  Extra in simulation ({len(extra)}):{RESET}")
            for fvg_id in extra:
                fvg = next(f for f in self.active_4h_fvgs if f.id == fvg_id)
                print_fvg(fvg, "   ")
        
        if not missing and not extra:
            print(f"\n{GREEN}✅ Perfect match! All FVGs detected correctly.{RESET}")
        else:
            print(f"\n{RED}❌ Mismatch detected! Need to fix logic.{RESET}")
    
    def run_debug(self, days: int = 2):
        """Run full debug"""
        print_header("FVG DETECTION DEBUGGER")
        print(f"Symbol: {SYMBOL}")
        print(f"Timeframe: {TIMEFRAME_4H}")
        print(f"Period: Last {days} days")
        print(f"Time: {datetime.now()}\n")
        
        # Load data
        df_4h, df_15m = self.load_data(days)
        
        if df_4h is None or len(df_4h) < 3:
            print(f"{RED}❌ Not enough data to debug{RESET}")
            return
        
        # Show all candles first
        print_header("All 4H Candles (for reference)")
        for i in range(len(df_4h)):
            candle = df_4h.iloc[i]
            is_closed = i < len(df_4h) - 1  # Last candle is still open
            print_candle(candle, i, is_closed)
        
        # Simulate live bot logic
        self.simulate_candle_processing(df_4h)
        
        # Compare with batch detection
        self.compare_with_batch_detection(df_4h)
        
        print_header("Debug Complete")


if __name__ == "__main__":
    import sys
    
    days = 2
    if len(sys.argv) > 1:
        try:
            days = int(sys.argv[1])
        except ValueError:
            print(f"Invalid days argument: {sys.argv[1]}, using default: 2")
    
    debugger = FVGDetectionDebugger()
    debugger.run_debug(days=days)

