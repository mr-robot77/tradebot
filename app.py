from datetime import datetime, timedelta

from investing_algorithm_framework import CCXTOHLCVMarketDataSource, \
    CCXTTickerMarketDataSource

# OHLCV data for BTC/EUR with 2-hour candles, going back 17 days
bitvavo_btc_eur_ohlcv_2h = CCXTOHLCVMarketDataSource(
    identifier="BTC/EUR-ohlcv",
    market="BITVAVO",
    symbol="BTC/EUR",
    timeframe="2h",
    # We want to retrieve data from the last 17 days (17 days * 24 hours / 2h)
    start_date_func=lambda: datetime.utcnow() - timedelta(days=17)
)

# Ticker data to track orders, trades and positions we make with symbol BTC/EUR
bitvavo_btc_eur_ticker = CCXTTickerMarketDataSource(
    identifier="BTC/EUR-ticker",
    market="BITVAVO",
    symbol="BTC/EUR",
)
