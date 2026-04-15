from investing_algorithm_framework import TradingStrategy, TimeUnit, \
    OrderSide, DataSource, DataType
import tulipy as tp
import pandas as pd


def is_crossover(fast_series, slow_series):
    """
    Expect df to have columns: Date, ma_<period_one>, ma_<period_two>.
    With the given date time it will check if the ma_<period_one> is a
    crossover with the ma_<period_two>
    """
    return fast_series[-2] <= slow_series[-2] \
        and fast_series[-1] > slow_series[-1]


def is_crossunder(fast_series, slow_series):
    """
    Expect df to have columns: Date, ma_<period_one>, ma_<period_two>.
    With the given date time it will check if the ma_<period_one> is a
    crossunder with the ma_<period_two>
    """
    return fast_series[-2] >= slow_series[-2] \
        and fast_series[-1] < slow_series[-1]


class GoldenCrossDeathCrossTradingStrategy(TradingStrategy):
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
            target_symbol = symbol.split('/')[0]

            # Don't open a new order when we already have an open order
            if context.has_open_orders(target_symbol):
                continue

            ohlcv_data = data["BTC/EUR-ohlcv"]

            # Convert to pandas DataFrame if Polars
            if hasattr(ohlcv_data, 'to_pandas'):
                df = ohlcv_data.to_pandas()
            else:
                df = ohlcv_data

            fast = tp.sma(df["Close"].to_numpy(dtype=float), period=9)
            slow = tp.sma(df["Close"].to_numpy(dtype=float), period=50)
            price = data["BTC/EUR-ticker"]["bid"]

            if context.has_position(target_symbol) \
                    and is_crossunder(fast, slow):
                context.close_position(target_symbol)
            elif not context.has_position(target_symbol) \
                    and is_crossover(fast, slow):
                context.create_limit_order(
                    target_symbol=target_symbol,
                    order_side=OrderSide.BUY,
                    price=price,
                    percentage_of_portfolio=25,
                    precision=4
                )
