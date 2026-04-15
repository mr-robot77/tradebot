from investing_algorithm_framework import create_app, CCXTOHLCVDataProvider, \
    CCXTTickerDataProvider

from strategy import GoldenCrossDeathCrossTradingStrategy

app = create_app()

# OHLCV data provider for BTC/EUR with 2-hour candles
# We need at least 50 candles for the slow SMA + buffer (17 days * 24h / 2h = 204)
app.add_data_provider(CCXTOHLCVDataProvider(
    symbol="BTC/EUR",
    market="BITVAVO",
    time_frame="2h",
    window_size=204,
))

# Ticker data provider for live price and order tracking
app.add_data_provider(CCXTTickerDataProvider(
    symbol="BTC/EUR",
    market="BITVAVO",
))

app.add_strategy(GoldenCrossDeathCrossTradingStrategy)
