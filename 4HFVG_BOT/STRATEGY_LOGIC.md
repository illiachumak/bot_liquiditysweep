# Failed 4H FVG Strategy - Повна Логіка

## Концепція

Стратегія базується на ідеї, що коли 4H FVG **rejected** (ціна увійшла в зону але не заповнила її), це сигнал для трейду в протилежному напрямку.

---

## 1. Виявлення 4H FVG

### Bullish FVG
- Формується коли `candle[i].low > candle[i-2].high`
- **Top**: `candle[i].low`
- **Bottom**: `candle[i-2].high`
- Зона: `$bottom - $top`

### Bearish FVG
- Формується коли `candle[i].high < candle[i-2].low`
- **Top**: `candle[i-2].low`
- **Bottom**: `candle[i].high`
- Зона: `$bottom - $top`

---

## 2. Tracking FVG

### Entered (зона торкнута)
FVG вважається **entered** коли ціна ТОРКАЄТЬСЯ зони:
- Свічка має `high >= bottom` АБО `low <= top`
- Тобто свічка НЕ повністю вище/нижче зони

### Highs/Lows Inside
Коли FVG entered, треба відстежувати:
- **Bullish FVG**: записуємо всі `high` що >= bottom
- **Bearish FVG**: записуємо всі `low` що <= top

Це потрібно для розрахунку SL пізніше.

---

## 3. Rejection (Ключовий Момент!)

**Rejection** = коли 4H свічка **ЗАКРИВАЄТЬСЯ** за межами FVG після того як entered.

### Bullish FVG Rejection (SHORT сигнал)
```
1. FVG entered = True (ціна торкнулася зони)
2. 4H свічка закривається НИЖЧЕ bottom (close < bottom)
3. → REJECTION! Очікуємо SHORT трейд
```

### Bearish FVG Rejection (LONG сигнал)
```
1. FVG entered = True (ціна торкнулася зони)
2. 4H свічка закривається ВИЩЕ top (close > top)
3. → REJECTION! Очікуємо LONG трейд
```

**ВАЖЛИВО:**
- Перевірка rejection відбувається на КОЖНІЙ 4H свічці
- Треба спочатку entered = True, інакше rejection не спрацює

---

## 4. Invalidation

FVG вважається **invalidated** коли ціна ПОВНІСТЮ пройшла крізь зону:

### Bullish FVG Invalidated
- Коли `low < bottom` (ціна пройшла ПІД зоною)
- FVG видаляється з active list

### Bearish FVG Invalidated
- Коли `high > top` (ціна пройшла НАД зоною)
- FVG видаляється з active list

**Перевірка:**
- На кожній 4H свічці для active FVG
- На кожній 15M свічці для rejected FVG (перед пошуком setup)

---

## 5. Пошук 15M Entry після Rejection

Коли 4H FVG rejected, шукаємо 15M FVG для точного входу:

### Для SHORT (після Bullish FVG rejection)
1. Шукаємо **BEARISH 15M FVG** в останніх 10 свічках
2. Беремо найсвіжіший (останній)
3. **Entry** = top 15M FVG

### Для LONG (після Bearish FVG rejection)
1. Шукаємо **BULLISH 15M FVG** в останніх 10 свічках
2. Беремо найсвіжіший (останній)
3. **Entry** = bottom 15M FVG

---

## 6. Розрахунок SL

SL береться з **highs/lows inside** 4H FVG:

### SHORT Setup (Bullish FVG rejected)
```
SL = max(highs_inside) * 1.002  // +0.2% буфер
```

### LONG Setup (Bearish FVG rejected)
```
SL = min(lows_inside) * 0.998   // -0.2% буфер
```

**Якщо немає highs/lows inside** → setup відхиляється

---

## 7. Розрахунок TP

Використовуємо **фіксований RR = 3.0**:

```
Risk = |Entry - SL|
Reward = Risk * 3.0

SHORT:
TP = Entry - Reward

LONG:
TP = Entry + Reward
```

---

## 8. Валідація Setup

Перед розміщенням ордеру, перевіряємо:

### 1. SL Distance
```
sl_distance_pct = |Entry - SL| / Entry * 100
Мінімум: 0.3%
```

### 2. Risk/Reward Ratio
```
RR = |TP - Entry| / |Entry - SL|
Мінімум: 2.0
```

### 3. Entry Price Sanity
```
distance_from_current = |Entry - CurrentPrice| / CurrentPrice * 100
Максимум: 5.0%
```

**Якщо хоч одна перевірка fails** → setup відхиляється

---

## 9. Розрахунок Position Size

```
Risk Amount = Balance * 2%  // RISK_PER_TRADE = 0.02
Risk Per Unit = |Entry - SL|
Size = Risk Amount / Risk Per Unit

// Округлюємо до lot size біржі
```

**Мінімальний notional:** $10

---

## 10. Limit Order та Expiry

### Розміщення
- **SELL limit** для SHORT @ Entry price
- **BUY limit** для LONG @ Entry price
- Ордер type: **LIMIT GTC**

### Expiry
- Limit діє **16 свічок по 15M = 4 години**
- Якщо НЕ filled за цей час → ордер скасовується
- Рахуємо з моменту створення setup

---

## 11. Cooldown після Expiry

Якщо limit НЕ filled та expired:

```
Cooldown = 16 свічок * 15M = 4 години
```

Протягом cooldown **НЕ можна** створювати новий setup з того самого 4H FVG.

Після закінчення cooldown можна спробувати знову (якщо з'явиться новий 15M FVG).

---

## 12. Trade Management

### Fill
Коли limit filled:
1. Розмістити **TP order** (LIMIT @ TP price)
2. Розмістити **SL order** (STOP MARKET @ SL price)
3. Для Futures: використовуємо TAKE_PROFIT_MARKET + STOP_MARKET з closePosition=true
4. Для Spot: використовуємо OCO order

### Exit
- **TP hit** → фіксуємо прибуток (MAKER fee)
- **SL hit** → фіксуємо збиток (TAKER fee)

### After Trade Closed
- 4H FVG отримує `has_filled_trade = True`
- Більше НЕ можна створювати setup з цього FVG
- Видаляємо з rejected list

---

## 13. Одночасні Трейди

**ТІЛЬКИ 1 АКТИВНИЙ ТРЕЙД ОДНОЧАСНО**

- Якщо є active trade → НЕ шукаємо нові setup
- Якщо є pending limit → НЕ шукаємо нові setup
- Тільки після закриття → шукаємо наступний

---

## 14. Fees

### Binance Futures
- **Maker**: 0.018% (0.00018)
- **Taker**: 0.045% (0.00045)

### Застосування
- Entry (limit filled) → MAKER
- TP hit → MAKER
- SL hit → TAKER

```
Entry Fee = Entry Price * Size * 0.00018
TP Fee = TP Price * Size * 0.00018
SL Fee = SL Price * Size * 0.00045

Net PnL = Gross PnL - Entry Fee - Exit Fee
```

---

## 15. Приклад Повного Циклу

### День 1, 08:00 UTC
- Утворюється **Bullish 4H FVG** $91567-$92532
- Додається до active list

### День 1, 12:00 UTC
- 4H свічка торкається зони → `entered = True`
- Записуємо `highs_inside = [92100, 92300]`

### День 2, 08:00 UTC
- 4H свічка закривається @ $91400 (< $91567 bottom)
- **REJECTION!** → SHORT сигнал
- Додається до rejected list

### День 2, 08:15 UTC
- Шукаємо BEARISH 15M FVG
- Знаходимо: $92108-$92276
- Entry = $92276 (top)
- SL = max(92100, 92300) * 1.002 = $92446
- Risk = $92446 - $92276 = $170
- TP = $92276 - ($170 * 3) = $91766
- Size = ($300 * 0.02) / $170 = 0.0353 BTC

### Валідація
- SL distance: 0.18% ✅ (>= 0.3% ❌ - реально може бути відхилено)
- Якщо пройшло → розміщуємо SELL LIMIT @ $92276

### День 2, 14:30 UTC
- Ціна торкнулася $92276 → limit filled
- Розміщуємо TP @ $91766 та SL @ $92446

### День 2, 18:00 UTC
- Ціна досягла TP $91766
- Gross PnL = ($92276 - $91766) * 0.0353 = $18.00
- Entry Fee = $92276 * 0.0353 * 0.00018 = $0.59
- TP Fee = $91766 * 0.0353 * 0.00018 = $0.58
- **Net PnL = $18.00 - $0.59 - $0.58 = $16.83**

### After
- 4H FVG отримує `has_filled_trade = True`
- Більше НЕ створюємо setup з цього FVG

---

## 16. Edge Cases

### FVG Invalidated перед Setup
- Якщо rejected 4H FVG invalidated на 15M → пропускаємо
- Перевіряємо перед створенням setup

### Немає 15M FVG
- Якщо після rejection немає відповідного 15M FVG → чекаємо
- Перевіряємо кожні 15M протягом 4H

### Multiple Rejections
- Той самий FVG може мати кілька rejection
- Але тільки 1 filled trade дозволено

### FVG з однаковими границями
- Якщо утворюється новий FVG з тими самими границями
- Перевіряємо по `id` (містить timestamp)
- Дублікати НЕ додаються

---

## 17. Для Ручного Бектесту

### Що треба відстежувати:

**4H Chart:**
1. Виявляємо всі FVG (записуємо top/bottom/timestamp)
2. Для кожного FVG відстежуємо entered (чи торкалася ціна)
3. Записуємо всі highs/lows INSIDE зони
4. Перевіряємо rejection (close < bottom для bullish)
5. Перевіряємо invalidation (low < bottom для bullish)

**15M Chart (після rejection):**
1. Шукаємо відповідний 15M FVG в останніх 10 свічках
2. Розраховуємо Entry, SL, TP
3. Перевіряємо валідацію
4. Перевіряємо чи limit filled протягом 16 свічок (4H)
5. Симулюємо trade до TP/SL

**Spreadsheet Columns:**
- 4H FVG ID
- Type (BULLISH/BEARISH)
- Top/Bottom
- Formed Time
- Entered Time
- Highs/Lows Inside
- Rejected Time
- Direction (LONG/SHORT)
- 15M FVG Top/Bottom
- Entry Price
- SL Price
- TP Price
- Size
- Limit Filled Time (or EXPIRED)
- Exit Time
- Exit Price
- Exit Reason (TP/SL)
- Gross PnL
- Fees
- Net PnL

---

## Параметри Стратегії

```python
RISK_PER_TRADE = 0.02          # 2% баланса на трейд
MIN_SL_PCT = 0.3               # Мінімальна відстань SL 0.3%
MIN_RR = 2.0                   # Мінімальний RR для валідації
FIXED_RR = 3.0                 # Фіксований RR для TP
LIMIT_EXPIRY_CANDLES = 16      # 4H = 16 * 15M
COOLDOWN_CANDLES = 16          # 4H cooldown після expiry
MAKER_FEE = 0.00018            # 0.018%
TAKER_FEE = 0.00045            # 0.045%
```

---

## Важливі Нюанси

1. **Rejection перевіряється на КОЖНІЙ 4H свічці**, не тільки при утворенні FVG
2. **Invalidation перевіряється на 4H для active FVG, на 15M для rejected FVG**
3. **Один FVG = максимум один filled trade**
4. **Cooldown працює тільки після expiry, не після TP/SL**
5. **Highs/lows inside записуємо з УСІХ свічок що торкалися зони, не тільки rejection candle**
6. **Entry завжди на краю 15M FVG (top для SHORT, bottom для LONG)**
7. **Fees враховуються ПІСЛЯ розрахунку gross PnL**
