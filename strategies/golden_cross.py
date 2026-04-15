"""
Golden Cross / Death Cross strategy.

Buy signal  : Fast SMA(9) crosses above Slow SMA(50)  → Golden Cross
Sell signal : Fast SMA(9) crosses below Slow SMA(50)  → Death Cross

The strategy runs on 2-hour BTC/EUR candles from Bitvavo and allocates
25 % of the available portfolio balance on each buy signal.
"""

from investing_algorithm_framework import TradingStrategy, TimeUnit, \
    OrderSide, DataSource, DataType
import tulipy as tp


def _is_crossover(fast, slow):
    """Return True when fast crossed above slow on the last completed bar."""
    return fast[-2] <= slow[-2] and fast[-1] > slow[-1]


def _is_crossunder(fast, slow):
    """Return True when fast crossed below slow on the last completed bar."""
    return fast[-2] >= slow[-2] and fast[-1] < slow[-1]


class GoldenCrossDeathCrossTradingStrategy(TradingStrategy):
    """SMA(9) / SMA(50) crossover strategy on BTC/EUR 2-hour candles."""

    time_unit = TimeUnit.HOUR
    interval = 2
    data_sources = [
        DataSource(
            identifier="BTC/EUR-ohlcv",
            data_type=DataType.OHLCV,
            symbol="BTC/EUR",
            time_frame="2h",
            warmup_window=204,
            market="BITVAVO",
        ),
        DataSource(
            identifier="BTC/EUR-ticker",
            data_type=DataType.TICKER,
            symbol="BTC/EUR",
            market="BITVAVO",
        ),
    ]
    symbols = ["BTC/EUR"]

    def run_strategy(self, context, data):
        for symbol in self.symbols:
            target_symbol = symbol.split("/")[0]

            if context.has_open_orders(target_symbol):
                continue

            ohlcv_data = data["BTC/EUR-ohlcv"]
            df = ohlcv_data.to_pandas() if hasattr(ohlcv_data, "to_pandas") else ohlcv_data

            fast = tp.sma(df["Close"].to_numpy(dtype=float), period=9)
            slow = tp.sma(df["Close"].to_numpy(dtype=float), period=50)
            price = data["BTC/EUR-ticker"]["bid"]

            if context.has_position(target_symbol) and _is_crossunder(fast, slow):
                context.close_position(target_symbol)
            elif not context.has_position(target_symbol) and _is_crossover(fast, slow):
                context.create_limit_order(
                    target_symbol=target_symbol,
                    order_side=OrderSide.BUY,
                    price=price,
                    percentage_of_portfolio=25,
                    precision=4,
                )
