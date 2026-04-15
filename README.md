# tradebot
Crypto trading bot implementing a Golden Cross / Death Cross strategy on BTC/EUR
using the [investing-algorithm-framework](https://github.com/coding-kitties/investing-algorithm-framework).

## Strategy

The bot uses two Simple Moving Averages (SMA) on 2-hour BTC/EUR candles:

- **Buy signal**: fast SMA (9) crosses above slow SMA (50) — *Golden Cross*
- **Sell signal**: fast SMA (9) crosses below slow SMA (50) — *Death Cross*

Each buy order allocates 25 % of the available portfolio balance.

## Project structure

| File | Description |
|------|-------------|
| `app.py` | Creates the app and registers data providers and the strategy |
| `strategy.py` | Golden Cross / Death Cross trading strategy |
| `backtest.py` | Step 3 – Run a historical backtest and print results |
| `plot.py` | Step 4 – Visualise backtest results (performance charts) |
| `azure_function.py` | Step 5 – Deploy the bot as an Azure Functions timer trigger |

## Step 3 – Backtest the strategy

Run a backtest over a custom date range:

```bash
python backtest.py 2023-01-01 2023-12-30
```

Example output:

```
* Start date: 2023-01-01 00:00:00
* End date:   2023-12-30 00:00:00
* Number of days: 363
* Initial balance: 400.0000 EUR
* Final balance:   468.1028 EUR
* Growth rate:     17.0257 %
```

## Step 4 – Analyse the backtest results

Generate a visual performance report (saved as `backtest_report.png`):

```bash
python plot.py 2023-01-01 2023-12-30
```

The report includes:
- Strategy performance (normalised equity curve)
- Monthly returns heatmap
- Yearly returns bar chart
- Distribution of monthly returns
- Normal distribution Q-Q plot
- Rolling 6-month return and volatility

## Step 5 – Deploy the trading bot

The bot can be deployed to **Azure Functions** with a timer trigger
that runs every 2 hours.

1. Copy `azure_function.py` into your Azure Functions project.
2. Set the Bitvavo API keys as application settings (environment variables):

   | Variable | Description |
   |----------|-------------|
   | `BITVAVO_API_KEY` | Your Bitvavo API key |
   | `BITVAVO_SECRET_KEY` | Your Bitvavo secret key |

3. Set the required environment variables before deploying:

```bash
BITVAVO_API_KEY=your_api_key
BITVAVO_SECRET_KEY=your_secret_key
```
