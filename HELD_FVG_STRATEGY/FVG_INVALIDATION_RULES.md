# FVG Invalidation Rules - Documentation

## Загальна концепція

**Fair Value Gap (FVG)** - це ціновий розрив між свічками, який створює зону дисбалансу.

**Invalidation (інвалідація)** - це момент коли FVG втрачає силу і більше не може використовуватися для трейдингу.

---

## Правила інвалідації

### Bullish FVG (бичачий розрив)
```
Структура:
   Candle 3: Low (верх зони)
   ----- GAP -----
   Candle 1: High (низ зони)
```

**Інвалідується коли:**
- Ціна пробиває і ЗАКРИВАЄТЬСЯ НИЖЧЕ дна зони (below bottom)
- `candle_low < fvg.bottom`

**Логіка:** Якщо ціна повернулась нижче бичачого розриву - bullish сила втрачена

---

### Bearish FVG (ведмежий розрив)
```
Структура:
   Candle 1: Low (верх зони)
   ----- GAP -----
   Candle 3: High (низ зони)
```

**Інвалідується коли:**
- Ціна пробиває і ЗАКРИВАЄТЬСЯ ВИЩЕ верху зони (above top)
- `candle_high > fvg.top`

**Логіка:** Якщо ціна повернулась вище ведмежого розриву - bearish сила втрачена

---

## Імплементація в HELD стратегії

### Code Implementation

```python
def is_fully_passed(self, candle_high: float, candle_low: float) -> bool:
    """Invalidation для held strategy"""
    if self.type == 'BULLISH':
        # Bullish FVG invalidated якщо ціна пройшла НИЖЧЕ
        return candle_low < self.bottom
    else:
        # Bearish FVG invalidated якщо ціна пройшла ВИЩЕ
        return candle_high > self.top
```

### Де перевіряється invalidation

1. **Active FVGs (line 312-314):**
   ```python
   elif fvg.is_fully_passed(candle['High'], candle['Low']):
       fvg.invalidated = True
       self.active_4h_fvgs.remove(fvg)
   ```

2. **Held FVGs (line 655-658):**
   ```python
   if held_fvg.is_fully_passed(current_candle['High'], current_candle['Low']):
       held_fvg.invalidated = True
       self.held_4h_fvgs.remove(held_fvg)
       continue
   ```

---

## One Trade Per FVG Rule

### Механізм

Кожен FVG може створити **тільки ОДИН** filled trade:

```python
# Skip if already had filled trade
if held_fvg.has_filled_trade:
    continue
```

### Коли встановлюється has_filled_trade

```python
# Line 681-684
if trade.exit_reason != 'EXPIRED':
    stats['fills'] += 1
    held_fvg.has_filled_trade = True  # ✅ Mark as used
    self.trades.append(trade)
```

**Important:** Якщо order EXPIRED (не filled) - FVG НЕ маркується як used і може створити новий setup

---

## Lifecycle of FVG in HELD Strategy

```
1. FVG Detected (active_4h_fvgs)
   ↓
2. Price enters & HOLDS (moved to held_4h_fvgs)
   ↓
3. Setup created
   ↓
4a. Order FILLED → Trade executed → has_filled_trade = True → FVG no longer used
4b. Order EXPIRED → FVG can try again (if not invalidated)
4c. FVG INVALIDATED → Removed from held_4h_fvgs
```

---

## Debug Checklist

- [ ] FVG інвалідується коли ціна йде в протилежний бік
- [ ] Після filled trade FVG більше не створює setups
- [ ] Expired orders НЕ маркують FVG як used
- [ ] Invalidated FVGs видаляються зі списку
- [ ] Не більше 1 filled trade на FVG

---

## Відмінності: HELD vs FAILED

### FAILED FVG Strategy
- **Trade Direction:** Протилежний до FVG
- **Bullish FVG rejected → SHORT**
- **Bearish FVG rejected → LONG**
- **Invalidation:** Ціна йде В НАПРЯМКУ FVG (failed to reject)

### HELD FVG Strategy
- **Trade Direction:** В напрямку FVG
- **Bullish FVG held → LONG**
- **Bearish FVG held → SHORT**
- **Invalidation:** Ціна йде ПРОТИ напрямку FVG (failed to hold)
