"""
CCI (Commodity Channel Index) mean-reversion strategy.

Buy signal  : CCI drops below -100 (oversold)
Sell signal : CCI rises above +100 (overbought)

Default parameters: period=20, overbought=100, oversold=-100.

The strategy runs on 2-hour BTC/EUR candles from Bitvavo and allocates
25 % of the available portfolio balance on each buy signal.
"""

from investing_algorithm_framework import TradingStrategy, TimeUnit, \
    OrderSide, DataSource, DataType
import tulipy as tp


class CCITradingStrategy(TradingStrategy):
    """CCI(20) mean-reversion strategy on BTC/EUR 2-hour candles."""

    time_unit = TimeUnit.HOUR
    interval = 2
    # CCI(20) needs at least 20 bars; keep generous buffer (80 ≈ 7 days)
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

    # CCI parameters
    cci_period = 20
    overbought = 100
    oversold = -100

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

            cci = tp.cci(high, low, close, period=self.cci_period)

            if context.has_position(target_symbol) and cci[-1] > self.overbought:
                context.close_position(target_symbol)
            elif not context.has_position(target_symbol) and cci[-1] < self.oversold:
                context.create_limit_order(
                    target_symbol=target_symbol,
                    order_side=OrderSide.BUY,
                    price=price,
                    percentage_of_portfolio=25,
                    precision=4,
                )
