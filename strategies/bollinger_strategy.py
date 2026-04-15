"""
Bollinger Bands mean-reversion strategy.

Buy signal  : Close price touches or falls below the lower Bollinger Band
Sell signal : Close price touches or rises above the upper Bollinger Band

Default parameters: period=20, std_dev multiplier=2.0 (industry standard).

The strategy runs on 2-hour BTC/EUR candles from Bitvavo and allocates
25 % of the available portfolio balance on each buy signal.
"""

from investing_algorithm_framework import TradingStrategy, TimeUnit, \
    OrderSide, DataSource, DataType
import tulipy as tp


class BollingerBandsTradingStrategy(TradingStrategy):
    """Bollinger Bands(20, 2.0) mean-reversion strategy on BTC/EUR 2-hour candles."""

    time_unit = TimeUnit.HOUR
    interval = 2
    # BB(20) needs at least 20 bars; keep generous buffer (80 ≈ 7 days)
    data_sources = [
        DataSource(
            identifier="BTC/EUR-ohlcv",
            data_type=DataType.OHLCV,
            symbol="BTC/EUR",
            time_frame="2h",
            warmup_window=80,
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

    # Bollinger Bands parameters
    bb_period = 20
    bb_stddev = 2.0

    def run_strategy(self, context, data):
        for symbol in self.symbols:
            target_symbol = symbol.split("/")[0]

            if context.has_open_orders(target_symbol):
                continue

            ohlcv_data = data["BTC/EUR-ohlcv"]
            df = ohlcv_data.to_pandas() if hasattr(ohlcv_data, "to_pandas") else ohlcv_data

            close = df["Close"].to_numpy(dtype=float)
            upper, _middle, lower = tp.bbands(
                close,
                period=self.bb_period,
                stddev=self.bb_stddev,
            )
            price = data["BTC/EUR-ticker"]["bid"]
            last_close = close[-1]

            if context.has_position(target_symbol) and last_close >= upper[-1]:
                context.close_position(target_symbol)
            elif not context.has_position(target_symbol) and last_close <= lower[-1]:
                context.create_limit_order(
                    target_symbol=target_symbol,
                    order_side=OrderSide.BUY,
                    price=price,
                    percentage_of_portfolio=25,
                    precision=4,
                )
