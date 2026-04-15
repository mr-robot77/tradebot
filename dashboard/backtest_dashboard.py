"""
Interactive public backtest dashboard for tradebot.

Lets any visitor choose a trading strategy, ticker, exchange, date range,
timeframe, and initial balance, click "Run Backtest", and instantly see:
  - Equity curve (Plotly interactive chart with dark template)
  - Performance KPIs: total return, final value, Sharpe ratio, max drawdown, win rate, # trades
  - Monthly returns heatmap
  - Full annotated trades table

Data is fetched live from public CCXT exchange endpoints — no API key required.
Indicators are computed with pandas-ta (pure Python, no C extensions).

Usage:
    pip install -r requirements-dashboard.txt
    python backtest_dashboard.py          # http://127.0.0.1:8050
    PORT=7860 python backtest_dashboard.py
"""

import math
import os
import warnings
from datetime import datetime, timezone

import ccxt
import numpy as np
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go
import dash
from dash import Input, Output, State, dash_table, dcc, html

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────── strategy catalogue ──────── #

STRATEGIES = [
    "Golden Cross / Death Cross",
    "RSI Reversion",
    "MACD Signal Cross",
    "Bollinger Bands",
    "EMA Crossover",
    "Stochastic Oscillator",
    "CCI Reversion",
    "Williams %R",
]

# Per-strategy: human description + 3 configurable parameters (p3 may be None)
_S = {
    "Golden Cross / Death Cross": {
        "desc": "Buy: Fast SMA crosses above Slow SMA  ·  Sell: Fast SMA crosses below Slow SMA",
        "p1": ("Fast SMA Period", 9),
        "p2": ("Slow SMA Period", 50),
        "p3": None,
    },
    "RSI Reversion": {
        "desc": "Buy: RSI falls below Oversold threshold  ·  Sell: RSI rises above Overbought threshold",
        "p1": ("RSI Period",           14),
        "p2": ("Oversold Threshold",   30),
        "p3": ("Overbought Threshold", 70),
    },
    "MACD Signal Cross": {
        "desc": "Buy: MACD line crosses above Signal line  ·  Sell: MACD crosses below Signal line",
        "p1": ("Fast Period",   12),
        "p2": ("Slow Period",   26),
        "p3": ("Signal Period",  9),
    },
    "Bollinger Bands": {
        "desc": "Buy: Price touches lower band  ·  Sell: Price touches upper band",
        "p1": ("BB Period",          20),
        "p2": ("Std Dev Multiplier", 2.0),
        "p3": None,
    },
    "EMA Crossover": {
        "desc": "Buy: Fast EMA crosses above Slow EMA  ·  Sell: Fast EMA crosses below Slow EMA",
        "p1": ("Fast EMA Period", 9),
        "p2": ("Slow EMA Period", 21),
        "p3": None,
    },
    "Stochastic Oscillator": {
        "desc": "Buy: %K crosses above %D below Oversold  ·  Sell: %K crosses below %D above Overbought",
        "p1": ("%K Period",           14),
        "p2": ("Oversold Threshold",  20),
        "p3": ("Overbought Threshold", 80),
    },
    "CCI Reversion": {
        "desc": "Buy: CCI drops below -100 (oversold)  ·  Sell: CCI rises above +100 (overbought)",
        "p1": ("CCI Period",          20),
        "p2": ("Oversold Level",    -100),
        "p3": ("Overbought Level",   100),
    },
    "Williams %R": {
        "desc": "Buy: Williams %R drops below -80 (oversold)  ·  Sell: rises above -20 (overbought)",
        "p1": ("Period",             14),
        "p2": ("Oversold Level",    -80),
        "p3": ("Overbought Level",  -20),
    },
}

# ─────────────────────────────────────────────────── exchange catalogue ───── #

EXCHANGES = [
    {"label": "Binance",   "value": "binance"},
    {"label": "Kraken",    "value": "kraken"},
    {"label": "KuCoin",    "value": "kucoin"},
    {"label": "Bybit",     "value": "bybit"},
    {"label": "OKX",       "value": "okx"},
    {"label": "Bitvavo",   "value": "bitvavo"},
    {"label": "Bitfinex",  "value": "bitfinex"},
    {"label": "Gate.io",   "value": "gateio"},
]

TIMEFRAMES = [
    {"label": "15 Minutes", "value": "15m"},
    {"label": "1 Hour",     "value": "1h"},
    {"label": "4 Hours",    "value": "4h"},
    {"label": "1 Day",      "value": "1d"},
    {"label": "1 Week",     "value": "1w"},
]

# ─────────────────────────────────────────────────── popular tickers ──────── #
# Grouped by category for the searchable dropdown.
# Users can also type any custom pair directly.

TICKERS = [
    # ── Major ──────────────────────────────────────────────────────────────
    {"label": "BTC/USDT  — Bitcoin",         "value": "BTC/USDT"},
    {"label": "ETH/USDT  — Ethereum",        "value": "ETH/USDT"},
    {"label": "BNB/USDT  — BNB",             "value": "BNB/USDT"},
    {"label": "SOL/USDT  — Solana",          "value": "SOL/USDT"},
    {"label": "XRP/USDT  — XRP",             "value": "XRP/USDT"},
    {"label": "ADA/USDT  — Cardano",         "value": "ADA/USDT"},
    {"label": "AVAX/USDT — Avalanche",       "value": "AVAX/USDT"},
    {"label": "DOT/USDT  — Polkadot",        "value": "DOT/USDT"},
    {"label": "MATIC/USDT— Polygon",         "value": "MATIC/USDT"},
    {"label": "LINK/USDT — Chainlink",       "value": "LINK/USDT"},
    # ── Meme / Popular ─────────────────────────────────────────────────────
    {"label": "DOGE/USDT — Dogecoin",        "value": "DOGE/USDT"},
    {"label": "SHIB/USDT — Shiba Inu",       "value": "SHIB/USDT"},
    {"label": "PEPE/USDT — Pepe",            "value": "PEPE/USDT"},
    # ── DeFi ───────────────────────────────────────────────────────────────
    {"label": "UNI/USDT  — Uniswap",         "value": "UNI/USDT"},
    {"label": "AAVE/USDT — Aave",            "value": "AAVE/USDT"},
    {"label": "CRV/USDT  — Curve",           "value": "CRV/USDT"},
    {"label": "MKR/USDT  — Maker",           "value": "MKR/USDT"},
    {"label": "COMP/USDT — Compound",        "value": "COMP/USDT"},
    # ── Layer 1 / Layer 2 ──────────────────────────────────────────────────
    {"label": "ATOM/USDT — Cosmos",          "value": "ATOM/USDT"},
    {"label": "NEAR/USDT — NEAR Protocol",   "value": "NEAR/USDT"},
    {"label": "FTM/USDT  — Fantom",          "value": "FTM/USDT"},
    {"label": "ALGO/USDT — Algorand",        "value": "ALGO/USDT"},
    {"label": "TRX/USDT  — TRON",            "value": "TRX/USDT"},
    {"label": "LTC/USDT  — Litecoin",        "value": "LTC/USDT"},
    {"label": "BCH/USDT  — Bitcoin Cash",    "value": "BCH/USDT"},
    {"label": "XLM/USDT  — Stellar",         "value": "XLM/USDT"},
    {"label": "VET/USDT  — VeChain",         "value": "VET/USDT"},
    # ── EUR pairs (Bitvavo / Kraken) ────────────────────────────────────────
    {"label": "BTC/EUR   — Bitcoin (EUR)",   "value": "BTC/EUR"},
    {"label": "ETH/EUR   — Ethereum (EUR)",  "value": "ETH/EUR"},
    {"label": "SOL/EUR   — Solana (EUR)",    "value": "SOL/EUR"},
    # ── BTC pairs ──────────────────────────────────────────────────────────
    {"label": "ETH/BTC   — ETH vs BTC",      "value": "ETH/BTC"},
    {"label": "SOL/BTC   — SOL vs BTC",      "value": "SOL/BTC"},
    {"label": "BNB/BTC   — BNB vs BTC",      "value": "BNB/BTC"},
]

# ────────────────────────────────────────────────── colour palette ─────────── #

ACCENT = "#1f6fb2"
BG     = "#0d1117"
CARD   = "#161b22"
BORDER = "#30363d"
TEXT   = "#e6edf3"
GREEN  = "#3fb950"
RED    = "#f85149"
MUTED  = "#8b949e"

PLOTLY_TEMPLATE = "plotly_dark"

# ───────────────────────────────────────────────── OHLCV fetching ─────────── #

def fetch_ohlcv(exchange_id: str, symbol: str, timeframe: str,
                start_dt: datetime, end_dt: datetime) -> pd.DataFrame:
    """
    Download OHLCV candles from *exchange_id* for the given date range.
    Paginates automatically when the exchange caps a single request at 1 000 rows.

    Returns a DataFrame indexed by UTC timestamp with columns:
        open, high, low, close, volume (all float64).
    """
    exchange = getattr(ccxt, exchange_id)({"enableRateLimit": True})

    since_ms = int(start_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)
    until_ms = int(end_dt.replace(tzinfo=timezone.utc).timestamp() * 1000)

    rows, cursor = [], since_ms
    while cursor < until_ms:
        candles = exchange.fetch_ohlcv(
            symbol, timeframe=timeframe, since=cursor, limit=1_000
        )
        if not candles:
            break
        rows.extend(candles)
        new_cursor = candles[-1][0]
        if new_cursor >= until_ms or new_cursor == cursor:
            break
        cursor = new_cursor + 1

    if not rows:
        raise ValueError(
            f"No OHLCV data returned from {exchange_id} for '{symbol}' "
            f"in the requested date range. "
            "Check the symbol format (e.g. BTC/USDT) and date range."
        )

    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    df = df.set_index("ts").astype(float)
    df = df[
        (df.index >= pd.Timestamp(start_dt).tz_localize("UTC")) &
        (df.index <= pd.Timestamp(end_dt).tz_localize("UTC"))
    ]
    return df[~df.index.duplicated(keep="first")]


# ─────────────────────────────────────────────── signal generation ─────────── #

def _xover(fast: pd.Series, slow: pd.Series) -> pd.Series:
    """True on bars where fast just crossed above slow."""
    return (fast.shift(1) <= slow.shift(1)) & (fast > slow)


def _xunder(fast: pd.Series, slow: pd.Series) -> pd.Series:
    """True on bars where fast just crossed below slow."""
    return (fast.shift(1) >= slow.shift(1)) & (fast < slow)


def compute_signals(df: pd.DataFrame, strategy: str,
                    p1, p2, p3) -> pd.Series:
    """
    Generate a +1 / -1 / 0 signal Series for the chosen strategy.

    p1, p2, p3 are the three configurable parameters shown in the sidebar.
    p3 is ignored for strategies that only require two parameters.
    """
    close = df["close"]
    high  = df["high"]
    low   = df["low"]
    sig   = pd.Series(0, index=df.index, dtype=int)

    if strategy == "Golden Cross / Death Cross":
        fast = ta.sma(close, length=int(p1))
        slow = ta.sma(close, length=int(p2))
        sig[_xover(fast, slow)]  = 1
        sig[_xunder(fast, slow)] = -1

    elif strategy == "RSI Reversion":
        rsi = ta.rsi(close, length=int(p1))
        sig[rsi < float(p2)] = 1
        sig[rsi > float(p3)] = -1

    elif strategy == "MACD Signal Cross":
        mdf = ta.macd(close, fast=int(p1), slow=int(p2), signal=int(p3))
        macd_col   = mdf.iloc[:, 0]   # MACD line
        signal_col = mdf.iloc[:, 2]   # Signal line
        sig[_xover(macd_col,  signal_col)] = 1
        sig[_xunder(macd_col, signal_col)] = -1

    elif strategy == "Bollinger Bands":
        bdf   = ta.bbands(close, length=int(p1), std=float(p2))
        lower = bdf.iloc[:, 0]   # BBL
        upper = bdf.iloc[:, 2]   # BBU
        sig[close <= lower] = 1
        sig[close >= upper] = -1

    elif strategy == "EMA Crossover":
        fast = ta.ema(close, length=int(p1))
        slow = ta.ema(close, length=int(p2))
        sig[_xover(fast, slow)]  = 1
        sig[_xunder(fast, slow)] = -1

    elif strategy == "Stochastic Oscillator":
        stoch_df = ta.stoch(high, low, close, k=int(p1))
        if stoch_df is not None and not stoch_df.empty:
            pct_k = stoch_df.iloc[:, 0]
            pct_d = stoch_df.iloc[:, 1]
            bull = _xover(pct_k, pct_d) & (pct_k < float(p2))
            bear = _xunder(pct_k, pct_d) & (pct_k > float(p3))
            sig[bull] = 1
            sig[bear] = -1

    elif strategy == "CCI Reversion":
        cci = ta.cci(high, low, close, length=int(p1))
        sig[cci < float(p2)] = 1
        sig[cci > float(p3)] = -1

    elif strategy == "Williams %R":
        wr = ta.willr(high, low, close, length=int(p1))
        sig[wr < float(p2)] = 1
        sig[wr > float(p3)] = -1

    return sig


# ────────────────────────────────────────────────── backtest engine ─────────── #

def run_backtest(df: pd.DataFrame, strategy: str, initial_balance: float,
                 p1, p2, p3):
    """
    Simple vectorised-signal event-driven backtester.

    Returns
    -------
    trades : list[dict]   – one dict per completed or forced-close trade
    equity : pd.Series    – portfolio value at every bar
    """
    signals = compute_signals(df, strategy, p1, p2, p3)

    balance     = float(initial_balance)
    position    = 0.0         # units of base asset held
    entry_price = 0.0
    entry_time  = None
    trades, equity_vals = [], []

    for ts, row in df.iterrows():
        s     = signals[ts]
        price = row["close"]

        # ── open position ──────────────────────────────────────────────── #
        if s == 1 and position == 0.0 and balance > 0.0:
            position    = balance / price
            entry_price = price
            entry_time  = ts
            balance     = 0.0

        # ── close position ─────────────────────────────────────────────── #
        elif s == -1 and position > 0.0:
            exit_value = position * price
            trades.append({
                "Entry Time":  entry_time.strftime("%Y-%m-%d %H:%M"),
                "Exit Time":   ts.strftime("%Y-%m-%d %H:%M"),
                "Entry Price": round(entry_price, 4),
                "Exit Price":  round(price, 4),
                "P&L":         round(exit_value - position * entry_price, 2),
                "Return %":    round((price / entry_price - 1) * 100, 2),
                "Duration":    str(ts - entry_time).split(".")[0],
                "Status":      "Closed",
            })
            balance  = exit_value
            position = 0.0

        equity_vals.append(balance + position * price)

    # Force-close any open position at the last bar
    if position > 0.0:
        last_price = df["close"].iloc[-1]
        last_ts    = df.index[-1]
        exit_value = position * last_price
        trades.append({
            "Entry Time":  entry_time.strftime("%Y-%m-%d %H:%M"),
            "Exit Time":   last_ts.strftime("%Y-%m-%d %H:%M"),
            "Entry Price": round(entry_price, 4),
            "Exit Price":  round(last_price, 4),
            "P&L":         round(exit_value - position * entry_price, 2),
            "Return %":    round((last_price / entry_price - 1) * 100, 2),
            "Duration":    str(last_ts - entry_time).split(".")[0],
            "Status":      "Open (closed at end)",
        })

    equity = pd.Series(equity_vals, index=df.index)
    return trades, equity


# ───────────────────────────────────────────────── performance metrics ─────── #

def compute_metrics(trades: list, equity: pd.Series, initial_balance: float) -> dict:
    """Compute portfolio-level performance metrics from the equity curve."""
    if equity.empty:
        return {}

    final_val    = equity.iloc[-1]
    total_return = (final_val / float(initial_balance) - 1) * 100

    daily = equity.resample("D").last().pct_change().dropna()
    sharpe = (
        (daily.mean() / daily.std()) * math.sqrt(365)
        if daily.std() > 0 else 0.0
    )

    rolling_max  = equity.cummax()
    max_drawdown = ((equity - rolling_max) / rolling_max).min() * 100

    wins     = sum(1 for t in trades if t["P&L"] > 0)
    win_rate = (wins / len(trades) * 100) if trades else 0.0

    return {
        "total_return": round(total_return, 2),
        "final_value":  round(final_val,    2),
        "sharpe":       round(sharpe,        3),
        "max_drawdown": round(max_drawdown,  2),
        "win_rate":     round(win_rate,      1),
        "num_trades":   len(trades),
    }


def build_monthly_returns(equity: pd.Series) -> pd.DataFrame:
    """Pivot equity curve into a year × month return table (fractions)."""
    if equity.empty:
        return pd.DataFrame()

    monthly = equity.resample("ME").last().pct_change().dropna()
    df      = monthly.to_frame("ret")
    df["year"]  = df.index.year
    df["month"] = df.index.month
    pivot = df.pivot(index="year", columns="month", values="ret")
    month_names = ["Jan","Feb","Mar","Apr","May","Jun",
                   "Jul","Aug","Sep","Oct","Nov","Dec"]
    pivot.columns = [month_names[m - 1] for m in pivot.columns]
    return pivot


# ──────────────────────────────────────────────────── chart builders ─────────── #

def make_empty_fig(title: str = "") -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        paper_bgcolor=CARD, plot_bgcolor=CARD,
        font=dict(color=MUTED),
        title=dict(text=title, font=dict(color=MUTED, size=13)),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        margin=dict(l=20, r=20, t=40, b=20),
        annotations=[dict(text="Run a backtest to see results",
                          xref="paper", yref="paper", x=0.5, y=0.5,
                          showarrow=False, font=dict(color=MUTED, size=14))],
    )
    return fig


def make_equity_chart(equity: pd.Series, initial_balance: float,
                      strategy_name: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=equity.index, y=equity.values,
        mode="lines", name=strategy_name,
        line=dict(color=ACCENT, width=2),
        fill="tozeroy",
        fillcolor="rgba(31,111,178,0.10)",
        hovertemplate="%{x|%Y-%m-%d}<br>Portfolio: %{y:,.2f}<extra></extra>",
    ))
    fig.add_hline(
        y=initial_balance, line_dash="dot", line_color=MUTED,
        annotation_text=f"Initial: {initial_balance:,.0f}",
        annotation_font_color=MUTED,
    )
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        paper_bgcolor=CARD, plot_bgcolor=CARD,
        font=dict(color=TEXT, size=12),
        title=dict(text="Equity Curve", font=dict(size=14, color=TEXT)),
        xaxis=dict(gridcolor=BORDER, showgrid=True, zeroline=False),
        yaxis=dict(gridcolor=BORDER, showgrid=True, zeroline=False),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        hovermode="x unified",
        margin=dict(l=60, r=20, t=45, b=30),
    )
    return fig


def make_monthly_heatmap(monthly_table: pd.DataFrame) -> go.Figure:
    if monthly_table.empty:
        return make_empty_fig("Monthly Returns")

    z    = monthly_table.values * 100
    text = [
        [f"{v:.1f}%" if not np.isnan(v) else "" for v in row]
        for row in z
    ]
    fig = go.Figure(go.Heatmap(
        z=z,
        x=monthly_table.columns.tolist(),
        y=[str(yr) for yr in monthly_table.index],
        text=text,
        texttemplate="%{text}",
        colorscale=[[0, "#c0392b"], [0.5, "#555555"], [1, "#27ae60"]],
        zmid=0,
        showscale=True,
        colorbar=dict(ticksuffix="%", tickfont=dict(color=TEXT)),
        hovertemplate="%{y} %{x}: %{z:.2f}%<extra></extra>",
    ))
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        paper_bgcolor=CARD, plot_bgcolor=CARD,
        font=dict(color=TEXT, size=11),
        title=dict(text="Monthly Returns", font=dict(size=14, color=TEXT)),
        margin=dict(l=60, r=20, t=45, b=30),
    )
    return fig


# ──────────────────────────────────────────────────── Dash layout ─────────── #

_CARD = {
    "background":   CARD,
    "border":       f"1px solid {BORDER}",
    "borderRadius": "8px",
    "padding":      "16px",
    "marginBottom": "16px",
}
_LBL = {
    "color":         MUTED,
    "fontSize":      "11px",
    "fontWeight":    "600",
    "textTransform": "uppercase",
    "letterSpacing": "0.05em",
    "marginBottom":  "4px",
    "marginTop":     "0",
}
_INP = {
    "background":   "#21262d",
    "border":       f"1px solid {BORDER}",
    "borderRadius": "6px",
    "color":        TEXT,
    "width":        "100%",
    "padding":      "6px 10px",
    "fontSize":     "13px",
    "boxSizing":    "border-box",
}
_BTN = {
    "background":   ACCENT,
    "border":       "none",
    "borderRadius": "6px",
    "color":        "white",
    "cursor":       "pointer",
    "fontSize":     "14px",
    "fontWeight":   "600",
    "padding":      "10px 0",
    "width":        "100%",
    "marginTop":    "8px",
}
_DD = {
    "background":        "#21262d",
    "color":             TEXT,
    "border":            f"1px solid {BORDER}",
    "borderRadius":      "6px",
}


def _field(label: str, component) -> html.Div:
    return html.Div(
        [html.P(label, style=_LBL), component],
        style={"marginBottom": "12px"},
    )


def _kpi_card(title: str, elem_id: str) -> html.Div:
    return html.Div(
        [
            html.P(title, style={**_LBL, "marginBottom": "2px"}),
            html.Div(
                "–",
                id=elem_id,
                style={"color": TEXT, "fontSize": "20px", "fontWeight": "700"},
            ),
        ],
        style={**_CARD, "textAlign": "center", "flex": "1",
               "minWidth": "100px", "marginBottom": "0"},
    )


# ── sidebar ──────────────────────────────────────────────────────────────── #

_sidebar = html.Div(
    [
        html.H3(
            "⚙ Strategy Setup",
            style={"color": TEXT, "marginTop": "0",
                   "marginBottom": "16px", "fontSize": "16px"},
        ),

        _field("Strategy", dcc.Dropdown(
            id="dd-strategy",
            options=[{"label": s, "value": s} for s in STRATEGIES],
            value=STRATEGIES[0],
            clearable=False,
            searchable=True,
            style=_DD,
        )),

        html.P(
            id="strategy-desc",
            style={"color": MUTED, "fontSize": "11px",
                   "marginTop": "-8px", "marginBottom": "12px"},
        ),

        _field("Exchange", dcc.Dropdown(
            id="dd-exchange",
            options=EXCHANGES,
            value="binance",
            clearable=False,
            searchable=True,
            style=_DD,
        )),

        _field("Ticker", dcc.Dropdown(
            id="dd-symbol",
            options=TICKERS,
            value="BTC/USDT",
            clearable=False,
            searchable=True,
            placeholder="Search or type a symbol…",
            style=_DD,
        )),

        _field("Timeframe", dcc.Dropdown(
            id="dd-tf",
            options=TIMEFRAMES,
            value="1d",
            clearable=False,
            style=_DD,
        )),

        html.Div(
            [
                html.Div(
                    [
                        html.P("Start Date", style=_LBL),
                        dcc.DatePickerSingle(
                            id="dp-start", date="2023-01-01",
                            display_format="YYYY-MM-DD",
                            style={"width": "100%"},
                        ),
                    ],
                    style={"width": "48%"},
                ),
                html.Div(
                    [
                        html.P("End Date", style=_LBL),
                        dcc.DatePickerSingle(
                            id="dp-end", date="2024-01-01",
                            display_format="YYYY-MM-DD",
                            style={"width": "100%"},
                        ),
                    ],
                    style={"width": "48%"},
                ),
            ],
            style={
                "display": "flex", "justifyContent": "space-between",
                "marginBottom": "12px",
            },
        ),

        _field("Initial Balance", dcc.Input(
            id="inp-balance", type="number", value=1000, min=10, step=10,
            style=_INP,
        )),

        html.Hr(style={"borderColor": BORDER, "margin": "8px 0 12px 0"}),
        html.P("Strategy Parameters",
               style={**_LBL, "fontSize": "12px", "marginBottom": "10px"}),

        # Three dynamic parameter rows (labels and visibility updated by callback)
        html.Div(
            id="div-param1",
            children=[
                html.P("Fast SMA Period", id="lbl-param1", style=_LBL),
                dcc.Input(id="p-param1", type="number", value=9, style=_INP),
            ],
            style={"marginBottom": "10px"},
        ),
        html.Div(
            id="div-param2",
            children=[
                html.P("Slow SMA Period", id="lbl-param2", style=_LBL),
                dcc.Input(id="p-param2", type="number", value=50, style=_INP),
            ],
            style={"marginBottom": "10px"},
        ),
        html.Div(
            id="div-param3",
            children=[
                html.P("", id="lbl-param3", style=_LBL),
                dcc.Input(id="p-param3", type="number", value=9, style=_INP),
            ],
            style={"display": "none", "marginBottom": "10px"},
        ),

        dcc.Loading(
            html.Button("▶  Run Backtest", id="btn-run", n_clicks=0, style=_BTN),
            color=ACCENT,
            type="dot",
        ),
    ],
    style={**_CARD, "width": "300px", "minWidth": "300px", "flexShrink": "0"},
)

# ── results pane ─────────────────────────────────────────────────────────── #

_results = html.Div(
    [
        # Status / error banner
        html.Div(id="status-msg", style={"marginBottom": "12px"}),

        # KPI cards
        html.Div(
            [
                _kpi_card("Total Return",   "kpi-return"),
                _kpi_card("Final Value",    "kpi-final"),
                _kpi_card("Sharpe Ratio",   "kpi-sharpe"),
                _kpi_card("Max Drawdown",   "kpi-dd"),
                _kpi_card("Win Rate",       "kpi-wr"),
                _kpi_card("# Trades",       "kpi-trades"),
            ],
            style={
                "display": "flex", "gap": "12px",
                "marginBottom": "16px", "flexWrap": "wrap",
            },
        ),

        # Equity curve
        dcc.Loading(
            dcc.Graph(
                id="chart-equity",
                figure=make_empty_fig("Equity Curve"),
                style={"height": "340px"},
                config={"displaylogo": False},
            ),
            color=ACCENT,
        ),

        # Monthly heatmap
        dcc.Loading(
            dcc.Graph(
                id="chart-monthly",
                figure=make_empty_fig("Monthly Returns"),
                style={"height": "260px", "marginTop": "16px"},
                config={"displaylogo": False},
            ),
            color=ACCENT,
        ),

        # Trades log
        html.Div(
            [
                html.P(
                    "Trades Log",
                    style={**_LBL, "fontSize": "13px", "marginBottom": "8px"},
                ),
                dash_table.DataTable(
                    id="tbl-trades",
                    columns=[
                        {"name": c, "id": c}
                        for c in [
                            "Entry Time", "Exit Time", "Entry Price",
                            "Exit Price", "P&L", "Return %",
                            "Duration", "Status",
                        ]
                    ],
                    data=[],
                    page_size=10,
                    style_table={"overflowX": "auto"},
                    style_cell={
                        "backgroundColor": CARD,
                        "color": TEXT,
                        "border": f"1px solid {BORDER}",
                        "fontSize": "12px",
                        "padding": "6px 10px",
                        "whiteSpace": "nowrap",
                    },
                    style_header={
                        "backgroundColor": "#21262d",
                        "fontWeight": "600",
                        "color": TEXT,
                        "border": f"1px solid {BORDER}",
                    },
                    style_data_conditional=[
                        {"if": {"filter_query": "{P&L} > 0",      "column_id": "P&L"},      "color": GREEN},
                        {"if": {"filter_query": "{P&L} < 0",      "column_id": "P&L"},      "color": RED},
                        {"if": {"filter_query": "{Return %} > 0", "column_id": "Return %"}, "color": GREEN},
                        {"if": {"filter_query": "{Return %} < 0", "column_id": "Return %"}, "color": RED},
                    ],
                ),
            ],
            style={**_CARD, "marginTop": "16px"},
        ),
    ],
    style={"flex": "1", "minWidth": "0"},
)

# ── full app layout ──────────────────────────────────────────────────────── #

app = dash.Dash(
    __name__,
    title="tradebot · Backtest Dashboard",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
server = app.server  # expose Flask server for gunicorn / Render / HF Spaces

app.layout = html.Div(
    [
        # ── header bar ─────────────────────────────────────────────────── #
        html.Div(
            [
                html.Span("🤖", style={"fontSize": "22px", "marginRight": "8px"}),
                html.Span(
                    "tradebot",
                    style={"fontWeight": "700", "fontSize": "18px", "color": TEXT},
                ),
                html.Span(
                    " · Interactive Backtest Dashboard",
                    style={"color": MUTED, "fontSize": "14px", "marginLeft": "4px"},
                ),
            ],
            style={
                "background":   CARD,
                "padding":      "12px 24px",
                "display":      "flex",
                "alignItems":   "center",
                "borderBottom": f"1px solid {BORDER}",
            },
        ),

        # ── main body ───────────────────────────────────────────────────── #
        html.Div(
            [_sidebar, _results],
            style={
                "display":    "flex",
                "gap":        "20px",
                "padding":    "20px",
                "alignItems": "flex-start",
                "flexWrap":   "wrap",
            },
        ),
    ],
    style={
        "background": BG,
        "minHeight":  "100vh",
        "fontFamily": "'Inter', 'Segoe UI', 'Arial', sans-serif",
    },
)


# ────────────────────────────────────────────────────── callbacks ─────────── #

@app.callback(
    Output("strategy-desc", "children"),
    Output("lbl-param1",    "children"),
    Output("lbl-param2",    "children"),
    Output("lbl-param3",    "children"),
    Output("div-param3",    "style"),
    Output("p-param1",      "value"),
    Output("p-param2",      "value"),
    Output("p-param3",      "value"),
    Input("dd-strategy",    "value"),
)
def sync_params_ui(strategy: str):
    """Update parameter labels and default values when strategy changes."""
    info     = _S[strategy]
    has_p3   = info["p3"] is not None
    p3_style = {"marginBottom": "10px"} if has_p3 else {"display": "none"}
    p3_val   = info["p3"][1] if has_p3 else 0
    p3_lbl   = info["p3"][0] if has_p3 else ""

    return (
        info["desc"],
        info["p1"][0],
        info["p2"][0],
        p3_lbl,
        p3_style,
        info["p1"][1],
        info["p2"][1],
        p3_val,
    )


@app.callback(
    Output("chart-equity",  "figure"),
    Output("chart-monthly", "figure"),
    Output("tbl-trades",    "data"),
    Output("kpi-return",    "children"),
    Output("kpi-final",     "children"),
    Output("kpi-sharpe",    "children"),
    Output("kpi-dd",        "children"),
    Output("kpi-wr",        "children"),
    Output("kpi-trades",    "children"),
    Output("status-msg",    "children"),
    Input("btn-run",        "n_clicks"),
    State("dd-strategy",    "value"),
    State("dd-exchange",    "value"),
    State("dd-symbol",      "value"),
    State("dd-tf",          "value"),
    State("dp-start",       "date"),
    State("dp-end",         "date"),
    State("inp-balance",    "value"),
    State("p-param1",       "value"),
    State("p-param2",       "value"),
    State("p-param3",       "value"),
    prevent_initial_call=True,
)
def run_and_display(
    _n,
    strategy, exchange, symbol, timeframe,
    start_date, end_date, balance,
    p1, p2, p3,
):
    """Fetch data, run backtest, compute metrics, render charts and tables."""
    empty = make_empty_fig()

    def _err(msg: str):
        banner = html.Div(
            [
                html.Span("⚠ Error: ", style={"color": RED, "fontWeight": "600"}),
                html.Span(msg, style={"color": RED}),
            ]
        )
        return empty, empty, [], "–", "–", "–", "–", "–", "–", banner

    try:
        if not symbol or not symbol.strip():
            return _err("Symbol cannot be empty.")

        start_dt = datetime.strptime(start_date[:10], "%Y-%m-%d")
        end_dt   = datetime.strptime(end_date[:10],   "%Y-%m-%d")

        if end_dt <= start_dt:
            return _err("End date must be after start date.")

        df = fetch_ohlcv(exchange, symbol.strip().upper(), timeframe,
                         start_dt, end_dt)

        if len(df) < 10:
            return _err(
                f"Only {len(df)} candles found – not enough data to run a backtest. "
                "Try a longer date range."
            )

        trades, equity = run_backtest(df, strategy, balance, p1, p2, p3)
        metrics        = compute_metrics(trades, equity, balance)
        monthly        = build_monthly_returns(equity)

        eq_fig  = make_equity_chart(equity, float(balance), strategy)
        mth_fig = make_monthly_heatmap(monthly)

        ret       = metrics.get("total_return", 0.0)
        ret_color = GREEN if ret >= 0 else RED

        status = html.Div(
            [
                html.Span("✓ Backtest complete", style={"color": GREEN}),
                html.Span(
                    f"  ·  {symbol.upper()}  ·  {exchange}  ·  "
                    f"{len(df):,} candles  ·  "
                    f"{start_date[:10]} → {end_date[:10]}",
                    style={"color": MUTED, "fontSize": "12px", "marginLeft": "8px"},
                ),
            ]
        )

        final_val = metrics.get("final_value", 0.0)
        dd        = metrics.get("max_drawdown", 0.0)

        return (
            eq_fig, mth_fig, trades,
            html.Span(f"{ret:+.2f}%",    style={"color": ret_color}),
            html.Span(f"{final_val:,.2f}"),
            html.Span(str(metrics.get("sharpe", "–"))),
            html.Span(f"{dd:.2f}%",      style={"color": RED}),
            html.Span(f"{metrics.get('win_rate', 0):.1f}%"),
            html.Span(str(metrics.get("num_trades", 0))),
            status,
        )

    except Exception as exc:  # noqa: BLE001
        return _err(str(exc))


# ─────────────────────────────────────────────────── entry point ─────────── #

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run(debug=False, host="0.0.0.0", port=port)
