"""
Williams %R mean-reversion strategy.

Buy signal  : Williams %R drops below -80 (oversold)
Sell signal : Williams %R rises above -20 (overbought)

Williams %R oscillates between 0 and -100:
  -100 to -80 → oversold zone (potential buy)
    0 to -20  → overbought zone (potential sell)

Default parameters: period=14.

The strategy runs on 2-hour BTC/EUR candles from Bitvavo and allocates
25 % of the available portfolio balance on each buy signal.
"""

from investing_algorithm_framework import TradingStrategy, TimeUnit, \
    OrderSide, DataSource, DataType
import tulipy as tp


class WilliamsRTradingStrategy(TradingStrategy):
    """Williams %R(14) mean-reversion strategy on BTC/EUR 2-hour candles."""

    time_unit = TimeUnit.HOUR
    interval = 2
    # Williams %R(14) needs at least 14 bars; keep generous buffer (60 ≈ 5 days)
    data_sources = [
        DataSource(
            identifier="BTC/EUR-ohlcv",
            data_type=DataType.OHLCV,
            symbol="BTC/EUR",
            time_frame="2h",
            warmup_window=60,
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

    # Williams %R parameters
    wr_period = 14
    oversold = -80
    overbought = -20

    def run_strategy(self, context, data):
        for symbol in self.symbols:
            target_symbol = symbol.split("/")[0]

            if context.has_open_orders(target_symbol):
                continue

            ohlcv_data = data["BTC/EUR-ohlcv"]
            df = ohlcv_data.to_pandas() if hasattr(ohlcv_data, "to_pandas") else ohlcv_data

            high  = df["High"].to_numpy(dtype=float)
            low   = df["Low"].to_numpy(dtype=float)
            close = df["Close"].to_numpy(dtype=float)
            price = data["BTC/EUR-ticker"]["bid"]

            wr = tp.willr(high, low, close, period=self.wr_period)

            if context.has_position(target_symbol) and wr[-1] > self.overbought:
                context.close_position(target_symbol)
            elif not context.has_position(target_symbol) and wr[-1] < self.oversold:
                context.create_limit_order(
                    target_symbol=target_symbol,
                    order_side=OrderSide.BUY,
                    price=price,
                    percentage_of_portfolio=25,
                    precision=4,
                )
