"""
MACD Signal Cross strategy.

Buy signal  : MACD line crosses above the signal line (bullish crossover)
Sell signal : MACD line crosses below the signal line (bearish crossover)

Default parameters: fast=12, slow=26, signal=9 (industry standard).

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


class MACDSignalCrossTradingStrategy(TradingStrategy):
    """MACD(12, 26, 9) signal-line crossover strategy on BTC/EUR 2-hour candles."""

    time_unit = TimeUnit.HOUR
    interval = 2
    # MACD(12,26,9) needs ~26+9=35 bars minimum; keep generous buffer (120 ≈ 10 days)
    data_sources = [
        DataSource(
            identifier="BTC/EUR-ohlcv",
            data_type=DataType.OHLCV,
            symbol="BTC/EUR",
            time_frame="2h",
            warmup_window=120,
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

    # MACD parameters
    fast_period = 12
    slow_period = 26
    signal_period = 9

    def run_strategy(self, context, data):
        for symbol in self.symbols:
            target_symbol = symbol.split("/")[0]

            if context.has_open_orders(target_symbol):
                continue

            ohlcv_data = data["BTC/EUR-ohlcv"]
            df = ohlcv_data.to_pandas() if hasattr(ohlcv_data, "to_pandas") else ohlcv_data

            close = df["Close"].to_numpy(dtype=float)
            macd_line, signal_line, _histogram = tp.macd(
                close,
                short_period=self.fast_period,
                long_period=self.slow_period,
                signal_period=self.signal_period,
            )
            price = data["BTC/EUR-ticker"]["bid"]

            if context.has_position(target_symbol) \
                    and _is_crossunder(macd_line, signal_line):
                context.close_position(target_symbol)
            elif not context.has_position(target_symbol) \
                    and _is_crossover(macd_line, signal_line):
                context.create_limit_order(
                    target_symbol=target_symbol,
                    order_side=OrderSide.BUY,
                    price=price,
                    percentage_of_portfolio=25,
                    precision=4,
                )
