# 📊 Аналіз Expiry Window

## Що таке Fill Rate?

**Fill Rate** = відсоток limit orders що заповнились (ціна повернулась до entry point)

### Приклад:
- **Setup створено:** Стратегія знайшла 15M FVG після 4H rejection і виставила limit order
- **Filled:** Ціна повернулась до entry і ордер виконався
- **Not Filled:** Ціна продовжила рухатись без pullback, ордер expired

## 🎯 Результати Тестів (2024)

### Test 1: 4H Expiry ✅ BEST
```
Expiry Window: 16 candles (4 години на 15M)
Total Setups:  16,869
Filled:        317 (1.9%)
Not Filled:    16,552 (98.1%)

Performance:
├─ Trades:         317
├─ Win Rate:       68.77%
├─ Return:         +628.98%
├─ Profit Factor:  3.78
└─ Max DD:         9.28%
```

### Test 2: 8H Expiry
```
Expiry Window: 32 candles (8 годин)
Total Setups:  13,992
Filled:        278 (2.0%)
Not Filled:    13,714 (98.0%)

Performance:
├─ Trades:         278
├─ Win Rate:       65.11%
├─ Return:         +356.27%
├─ Profit Factor:  3.41
└─ Max DD:         15.51%
```

### Test 3: 12H Expiry
```
Expiry Window: 48 candles (12 годин)
Total Setups:  11,679
Filled:        288 (2.5%)
Not Filled:    11,391 (97.5%)

Performance:
├─ Trades:         288
├─ Win Rate:       68.06%
├─ Return:         +371.55%
├─ Profit Factor:  3.24
└─ Max DD:         9.88%
```

## 📈 Висновки

### 1. Більше Setups = Більше Трейдів
- **4H:** 16,869 setups → 317 fills
- **8H:** 13,992 setups → 278 fills
- **12H:** 11,679 setups → 288 fills

**Чому?** Короткий expiry дозволяє швидше створювати нові setup після expiration.

### 2. Якість > Кількість
Навіть при низькому fill rate (1.9-2.5%), стратегія прибуткова:
- Win rate: 65-69%
- Profit factor: 3.2-3.8
- Return: +356-629%

### 3. Оптимальний Expiry = 4H

**Переваги:**
✅ Найбільше трейдів (317)
✅ Найвищий return (+629%)
✅ Найкращий profit factor (3.78)
✅ Низький drawdown (9.28%)

**Логіка:**
Якщо setup не fill за 4H (1 свічка 4H таймфрейму), можливо:
- Momentum змінився
- Setup став неактуальним
- Краще шукати новий opportunity

## 🔍 Чому Низький Fill Rate?

### Причини:
1. **Limit Order на границі 15M FVG**
   - Чекає pullback до точного рівня
   - Якщо strong momentum → no pullback → no fill

2. **Fixed RR 1.5**
   - Створює багато aggressive setups
   - Entry далеко від поточної ціни
   - Потребує значний pullback

3. **Expiry Filter**
   - Відкидає setups де ціна не повертається швидко
   - Фокус на якісних entries

### Чому це добре?

**Якість > Кількість:**
- З 16,869 setups → fill тільки 317
- Але 317 filled trades дали +629% return!
- Win rate 68.77%, Profit Factor 3.78

**Ті setup що fill = найкращі:**
- Ціна показала pullback (підтвердження)
- Entry точний (limit на FVG boundary)
- High probability setup

## 💡 Trade Flow Example

### SHORT Setup:
```
1. 4H Bullish FVG formed
   └─ Zone: $95,000 - $95,500

2. Price enters zone
   └─ High inside: $95,400
   └─ Low inside: $95,100

3. REJECTION ✅
   └─ Candle closes @ $94,800 (below $95,000)

4. 15M Bearish FVG found
   └─ Zone: $94,600 - $94,900

5. LIMIT ORDER created
   ├─ Entry: $94,900 (top of 15M FVG)
   ├─ SL: $95,450 (above high inside 4H FVG)
   └─ TP: $94,267.50 (risk × 1.5)

6. EXPIRY CHECK (4H = 16 candles)
   ├─ Candle 1-16: Check if price hits $94,900
   ├─ If YES → FILL → Execute trade
   └─ If NO → EXPIRE → Look for new setup

7. In this case: FILLED at candle 5
   └─ Price pulled back to $94,900
   └─ Trade executed
   └─ Result: Hit TP → +1.5R profit ✅
```

### NOT FILLED Example:
```
1-4. Same as above...

5. LIMIT ORDER created @ $94,900

6. Price action:
   ├─ Candle 1: $94,700 (missed entry by $200)
   ├─ Candle 2: $94,500
   ├─ Candle 3-16: Continues down, no pullback
   └─ After 16 candles (4H): ORDER EXPIRES ❌

7. Result: Not filled
   └─ Move on to next setup
```

## 🎲 Statistics

### 2024 Data (4H Expiry):
- **Total 4H FVGs:** 1,339
- **Rejections:** 425 (31.8%)
- **15M FVGs found:** 16,869
- **Setups created:** 16,869
- **Filled:** 317 (1.9%)
- **Win:** 218 (68.77% of filled)
- **Loss:** 99 (31.23% of filled)

### Pipeline Funnel:
```
1,339 4H FVGs
    ↓ (31.8% rejected)
425 Rejections
    ↓ (found 15M FVG)
16,869 Setups
    ↓ (1.9% filled in 4H)
317 Trades
    ↓ (68.77% win rate)
218 Wins → +$72,887
99 Losses → -$17,820
    ↓
Net: +$55,067 (+628.98%)
```

## 📊 Recommendation

**Optimal Configuration:**
```python
limit_order_expiry_candles = 16  # 4H expiry
min_sl_pct = 0.3
use_fixed_rr = True
fixed_rr = 1.5
enable_fees = True
```

**Expected Performance:**
- ~317 trades/year
- ~69% win rate
- ~+600% annual return
- <10% max drawdown
- Profit factor >3.5
