"""
Stochastic Oscillator mean-reversion strategy.

Buy signal  : %K line crosses above %D line while both are below 20 (oversold)
Sell signal : %K line crosses below %D line while both are above 80 (overbought)

Default parameters: k_period=14, d_period=3, overbought=80, oversold=20.

The strategy runs on 2-hour BTC/EUR candles from Bitvavo and allocates
25 % of the available portfolio balance on each buy signal.
"""

from investing_algorithm_framework import TradingStrategy, TimeUnit, \
    OrderSide, DataSource, DataType
import tulipy as tp


class StochasticTradingStrategy(TradingStrategy):
    """Stochastic Oscillator mean-reversion strategy on BTC/EUR 2-hour candles."""

    time_unit = TimeUnit.HOUR
    interval = 2
    # Stochastic(14,3) needs at least 17 bars; keep generous buffer (80 ≈ 7 days)
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

    # Stochastic parameters
    k_period = 14
    d_period = 3
    oversold = 20
    overbought = 80

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

            pct_k, pct_d = tp.stoch(high, low, close,
                                     k_period=self.k_period,
                                     k_slow_period=1,
                                     d_period=self.d_period)

            bullish_cross = (pct_k[-2] <= pct_d[-2] and pct_k[-1] > pct_d[-1]
                             and pct_k[-1] < self.oversold)
            bearish_cross = (pct_k[-2] >= pct_d[-2] and pct_k[-1] < pct_d[-1]
                             and pct_k[-1] > self.overbought)

            if context.has_position(target_symbol) and bearish_cross:
                context.close_position(target_symbol)
            elif not context.has_position(target_symbol) and bullish_cross:
                context.create_limit_order(
                    target_symbol=target_symbol,
                    order_side=OrderSide.BUY,
                    price=price,
                    percentage_of_portfolio=25,
                    precision=4,
                )
