from investing_algorithm_framework import TradingStrategy, TimeUnit, \
    Algorithm, OrderSide
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
    market_data_sources = [
        "BTC/EUR-ohlcv",
        "BTC/EUR-ticker",
    ]
    symbols = ["BTC/EUR"]

    def apply_strategy(self, algorithm: Algorithm, market_data: dict):

        for symbol in self.symbols:
            target_symbol = symbol.split('/')[0]

            # Don't open a new order when we already have an open order
            if algorithm.has_open_orders(target_symbol):
                continue

            ohlcv_data = market_data[f"{symbol}-ohlcv"]
            df = pd.DataFrame(
                ohlcv_data,
                columns=['Datetime', 'Open', 'High', 'Low', 'Close', 'Volume']
            )
            fast = tp.sma(df["Close"].to_numpy(), period=9)
            slow = tp.sma(df["Close"].to_numpy(), period=50)
            price = market_data[f"{symbol}-ticker"]["bid"]

            if algorithm.has_position(target_symbol) and is_crossunder(fast, slow):
                algorithm.close_position(target_symbol)
            elif not algorithm.has_position(target_symbol) and is_crossover(fast, slow):
                algorithm.create_limit_order(
                    target_symbol=target_symbol,
                    order_side=OrderSide.BUY,
                    price=price,
                    percentage_of_portfolio=25,
                    precision=4
                )
