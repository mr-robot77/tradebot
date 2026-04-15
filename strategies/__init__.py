"""
Trading strategies package.

Available strategies (all compatible with investing-algorithm-framework):
  - GoldenCrossDeathCrossTradingStrategy  (SMA 9 / 50 crossover)
  - RSIReversionTradingStrategy           (RSI-14 oversold/overbought)
  - MACDSignalCrossTradingStrategy        (MACD line × signal line)
  - BollingerBandsTradingStrategy         (price touches lower/upper band)
  - EMACrossTradingStrategy               (EMA 9 / 21 crossover)
  - StochasticTradingStrategy             (Stochastic %K/%D crossover)
  - CCITradingStrategy                    (CCI oversold/overbought)
  - WilliamsRTradingStrategy              (Williams %R oversold/overbought)
"""

from strategies.golden_cross import GoldenCrossDeathCrossTradingStrategy
from strategies.rsi_strategy import RSIReversionTradingStrategy
from strategies.macd_strategy import MACDSignalCrossTradingStrategy
from strategies.bollinger_strategy import BollingerBandsTradingStrategy
from strategies.ema_cross import EMACrossTradingStrategy
from strategies.stochastic_strategy import StochasticTradingStrategy
from strategies.cci_strategy import CCITradingStrategy
from strategies.williams_r_strategy import WilliamsRTradingStrategy

__all__ = [
    "GoldenCrossDeathCrossTradingStrategy",
    "RSIReversionTradingStrategy",
    "MACDSignalCrossTradingStrategy",
    "BollingerBandsTradingStrategy",
    "EMACrossTradingStrategy",
    "StochasticTradingStrategy",
    "CCITradingStrategy",
    "WilliamsRTradingStrategy",
]
