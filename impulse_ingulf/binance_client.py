"""
Binance Futures Client
Wrapper for Binance Futures API with proper candle handling
"""

import logging
import time
import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException

import config

logger = logging.getLogger(__name__)


class BinanceFuturesClient:
    """Wrapper for Binance Futures API"""

    def __init__(self):
        self.client = Client(config.BINANCE_API_KEY, config.BINANCE_API_SECRET)

        # Set leverage
        try:
            self.client.futures_change_leverage(
                symbol=config.SYMBOL,
                leverage=config.LEVERAGE
            )
            logger.info(f"Leverage set to {config.LEVERAGE}x for {config.SYMBOL}")
        except BinanceAPIException as e:
            logger.error(f"Failed to set leverage: {e}")
            raise

    def get_4h_candles(self, limit: int = 100) -> pd.DataFrame:
        """
        Fetch 4H candles

        CRITICAL: Returns candles where:
        - iloc[-1] is the CURRENT (potentially unclosed) candle
        - iloc[-2] is the LAST CLOSED candle

        For live bot logic, ALWAYS use iloc[-2] for the last closed candle!
        """
        try:
            klines = self.client.futures_klines(
                symbol=config.SYMBOL,
                interval=Client.KLINE_INTERVAL_4HOUR,
                limit=limit
            )

            df = pd.DataFrame(klines, columns=[
                'open_time', 'Open', 'High', 'Low', 'Close', 'Volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])

            df['Open time'] = pd.to_datetime(df['open_time'], unit='ms')
            df['Close time'] = pd.to_datetime(df['close_time'], unit='ms')

            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                df[col] = df[col].astype(float)

            return df

        except BinanceAPIException as e:
            logger.error(f"Failed to fetch 4H candles: {e}")
            raise

    def get_1h_candles(self, limit: int = 200) -> pd.DataFrame:
        """
        Fetch 1H candles

        CRITICAL: Returns candles where:
        - iloc[-1] is the CURRENT (potentially unclosed) candle
        - iloc[-2] is the LAST CLOSED candle

        For live bot logic, ALWAYS use iloc[-2] for the last closed candle!
        """
        try:
            klines = self.client.futures_klines(
                symbol=config.SYMBOL,
                interval=Client.KLINE_INTERVAL_1HOUR,
                limit=limit
            )

            df = pd.DataFrame(klines, columns=[
                'open_time', 'Open', 'High', 'Low', 'Close', 'Volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_base',
                'taker_buy_quote', 'ignore'
            ])

            df['Open time'] = pd.to_datetime(df['open_time'], unit='ms')
            df['Close time'] = pd.to_datetime(df['close_time'], unit='ms')

            for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
                df[col] = df[col].astype(float)

            return df

        except BinanceAPIException as e:
            logger.error(f"Failed to fetch 1H candles: {e}")
            raise

    def get_balance(self) -> float:
        """Get USDT balance"""
        try:
            account = self.client.futures_account()
            for asset in account['assets']:
                if asset['asset'] == 'USDT':
                    return float(asset['availableBalance'])
            return 0.0
        except BinanceAPIException as e:
            logger.error(f"Failed to get balance: {e}")
            raise

    def get_position(self) -> dict:
        """Get current position for symbol"""
        try:
            positions = self.client.futures_position_information(symbol=config.SYMBOL)
            for pos in positions:
                if float(pos['positionAmt']) != 0:
                    return {
                        'side': 'LONG' if float(pos['positionAmt']) > 0 else 'SHORT',
                        'size': abs(float(pos['positionAmt'])),
                        'entry_price': float(pos['entryPrice']),
                        'unrealized_pnl': float(pos['unRealizedProfit'])
                    }
            return None
        except BinanceAPIException as e:
            logger.error(f"Failed to get position: {e}")
            raise

    def open_position_with_sl_tp(self, direction: str, quantity: float,
                                  sl_price: float, tp_price: float) -> dict:
        """
        Open position with automatic SL and TP orders

        Args:
            direction: 'LONG' or 'SHORT'
            quantity: Position size in BTC
            sl_price: Stop loss price
            tp_price: Take profit price

        Returns:
            dict with entry_order, sl_order, tp_order, entry_price
        """
        try:
            # 1. Open market position
            side = 'BUY' if direction == 'LONG' else 'SELL'

            logger.info(f"Opening {direction} position: {quantity} {config.SYMBOL} at market")

            entry_order = self.client.futures_create_order(
                symbol=config.SYMBOL,
                side=side,
                type='MARKET',
                quantity=quantity
            )

            logger.info(f"Entry order filled: {entry_order['orderId']}")

            # Get fill price
            time.sleep(0.5)  # Wait for order to be processed
            fills = self.client.futures_get_order(
                symbol=config.SYMBOL,
                orderId=entry_order['orderId']
            )
            entry_price = float(fills['avgPrice'])

            # 2. Create STOP_MARKET order for SL
            sl_side = 'SELL' if direction == 'LONG' else 'BUY'

            logger.info(f"Creating SL order at {sl_price:.2f}")

            sl_order = self.client.futures_create_order(
                symbol=config.SYMBOL,
                side=sl_side,
                type='STOP_MARKET',
                stopPrice=round(sl_price, 2),
                closePosition=True
            )

            logger.info(f"SL order created: {sl_order['orderId']}")

            # 3. Create TAKE_PROFIT_MARKET order for TP
            logger.info(f"Creating TP order at {tp_price:.2f}")

            tp_order = self.client.futures_create_order(
                symbol=config.SYMBOL,
                side=sl_side,  # Same side as SL (closes position)
                type='TAKE_PROFIT_MARKET',
                stopPrice=round(tp_price, 2),
                closePosition=True
            )

            logger.info(f"TP order created: {tp_order['orderId']}")

            return {
                'entry_order': entry_order,
                'entry_price': entry_price,
                'sl_order': sl_order,
                'tp_order': tp_order
            }

        except BinanceAPIException as e:
            logger.error(f"Failed to open position: {e}")
            raise

    def cancel_all_orders(self):
        """Cancel all open orders"""
        try:
            result = self.client.futures_cancel_all_open_orders(symbol=config.SYMBOL)
            logger.info(f"Cancelled all orders: {result}")
        except BinanceAPIException as e:
            logger.error(f"Failed to cancel orders: {e}")
