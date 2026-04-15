"""
RSI Reversion strategy.

Buy signal  : RSI(14) drops below the oversold threshold (default 30)
Sell signal : RSI(14) rises above the overbought threshold (default 70)

The strategy runs on 2-hour BTC/EUR candles from Bitvavo and allocates
25 % of the available portfolio balance on each buy signal.
"""

from investing_algorithm_framework import TradingStrategy, TimeUnit, \
    OrderSide, DataSource, DataType
import tulipy as tp


class RSIReversionTradingStrategy(TradingStrategy):
    """RSI(14) mean-reversion strategy on BTC/EUR 2-hour candles."""

    time_unit = TimeUnit.HOUR
    interval = 2
    # RSI(14) needs at least 14 bars; keep a generous buffer (60 × 2h ≈ 5 days)
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

    # Configurable thresholds
    rsi_period = 14
    oversold = 30
    overbought = 70

    def run_strategy(self, context, data):
        for symbol in self.symbols:
            target_symbol = symbol.split("/")[0]

            if context.has_open_orders(target_symbol):
                continue

            ohlcv_data = data["BTC/EUR-ohlcv"]
            df = ohlcv_data.to_pandas() if hasattr(ohlcv_data, "to_pandas") else ohlcv_data

            close = df["Close"].to_numpy(dtype=float)
            rsi = tp.rsi(close, period=self.rsi_period)
            price = data["BTC/EUR-ticker"]["bid"]

            if context.has_position(target_symbol) and rsi[-1] > self.overbought:
                context.close_position(target_symbol)
            elif not context.has_position(target_symbol) and rsi[-1] < self.oversold:
                context.create_limit_order(
                    target_symbol=target_symbol,
                    order_side=OrderSide.BUY,
                    price=price,
                    percentage_of_portfolio=25,
                    precision=4,
                )
