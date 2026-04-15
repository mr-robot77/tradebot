"""
Live trading dashboard for the tradebot.

Provides a real-time web interface that displays portfolio performance,
open positions, and recent trades. The dashboard polls the app's state
every 30 seconds and updates all panels automatically.

Usage:
    python dashboard.py          # starts at http://127.0.0.1:8050

The dashboard reads live state from the investing-algorithm-framework
SQLite database.  When no live data is present it shows a demo view
so you can verify the UI before going live.
"""

import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import dash
from dash import dcc, html, Input, Output, dash_table
import plotly.graph_objects as go

# ──────────────────────────────────────────────────── configuration ──────── #

# Path where investing-algorithm-framework writes its SQLite database.
# Override with the DATABASE_PATH env variable if you store it elsewhere.
_DEFAULT_DB = Path(__file__).parent / "bot_state.db"
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", _DEFAULT_DB))

# How often (ms) the browser polls for new data
POLL_INTERVAL_MS = 30_000

ACCENT = "#1f6fb2"
BG     = "#0d1117"
CARD   = "#161b22"
BORDER = "#30363d"
TEXT   = "#e6edf3"
GREEN  = "#3fb950"
RED    = "#f85149"

# ─────────────────────────────────────────── database helpers ────────────── #

def _db_available():
    return DATABASE_PATH.exists()


def _query(sql, params=()):
    """Run *sql* against the state database and return rows as dicts."""
    try:
        with sqlite3.connect(DATABASE_PATH) as con:
            con.row_factory = sqlite3.Row
            return [dict(r) for r in con.execute(sql, params).fetchall()]
    except Exception:
        return []


def _portfolio_snapshots():
    """Return portfolio_snapshots ordered by created_at."""
    return _query(
        "SELECT created_at, total_value FROM portfolio_snapshot "
        "ORDER BY created_at ASC"
    )


def _latest_portfolio():
    rows = _query(
        "SELECT total_value, unallocated FROM portfolio "
        "ORDER BY updated_at DESC LIMIT 1"
    )
    return rows[0] if rows else None


def _positions():
    return _query(
        "SELECT symbol, amount, cost, value "
        "FROM position WHERE amount > 0 "
        "ORDER BY symbol ASC"
    )


def _trades(limit=50):
    return _query(
        "SELECT symbol, opened_at, closed_at, "
        "       net_gain, net_gain_percentage, status "
        "FROM trade "
        "ORDER BY opened_at DESC "
        f"LIMIT {limit}"
    )


# ─────────────────────────────────────────── demo / fallback data ────────── #

def _demo_equity():
    """Return synthetic equity data when no live DB is present."""
    import math
    import random
    random.seed(42)
    start = datetime.utcnow() - timedelta(days=90)
    dates, values = [], []
    v = 400.0
    for i in range(90 * 24):
        v *= 1 + random.gauss(0.00005, 0.005)
        dates.append(start + timedelta(hours=i))
        values.append(round(v, 2))
    return dates, values


# ─────────────────────────────────────────── layout helpers ──────────────── #

def _kpi_card(title, value, sub="", color=TEXT):
    return html.Div(
        [
            html.P(title, style={"margin": "0", "fontSize": "0.75rem",
                                 "color": "#8b949e", "textTransform": "uppercase",
                                 "letterSpacing": "0.05em"}),
            html.P(value, style={"margin": "4px 0 2px", "fontSize": "1.6rem",
                                 "fontWeight": "700", "color": color}),
            html.P(sub,   style={"margin": "0", "fontSize": "0.75rem",
                                 "color": "#8b949e"}),
        ],
        style={
            "background": CARD,
            "border": f"1px solid {BORDER}",
            "borderRadius": "8px",
            "padding": "16px 20px",
            "flex": "1",
            "minWidth": "140px",
        },
    )


def _section_header(title):
    return html.H3(
        title,
        style={"color": TEXT, "fontSize": "0.9rem", "fontWeight": "600",
               "borderBottom": f"1px solid {BORDER}",
               "paddingBottom": "8px", "marginBottom": "12px",
               "marginTop": "0"},
    )


# ─────────────────────────────────────────────────────────── app ──────────── #

app = dash.Dash(
    __name__,
    title="tradebot · live dashboard",
    update_title=None,
    suppress_callback_exceptions=True,
)

app.layout = html.Div(
    style={"background": BG, "minHeight": "100vh",
           "fontFamily": "'Segoe UI', system-ui, sans-serif",
           "color": TEXT, "padding": "20px"},
    children=[
        # ── top bar ─────────────────────────────────────────────────────── #
        html.Div(
            style={"display": "flex", "alignItems": "center",
                   "marginBottom": "20px"},
            children=[
                html.Span("●", style={"color": ACCENT,
                                      "fontSize": "1.6rem", "marginRight": "10px"}),
                html.Div([
                    html.H1("tradebot",
                            style={"margin": "0", "fontSize": "1.2rem",
                                   "fontWeight": "700", "color": TEXT}),
                    html.P("Golden Cross / Death Cross  ·  BTC/EUR  ·  BITVAVO",
                           style={"margin": "0", "fontSize": "0.75rem",
                                  "color": "#8b949e"}),
                ]),
                html.Div(id="live-badge",
                         style={"marginLeft": "auto", "fontSize": "0.75rem",
                                "color": "#8b949e"}),
            ],
        ),

        # ── KPI row ─────────────────────────────────────────────────────── #
        html.Div(id="kpi-row",
                 style={"display": "flex", "gap": "12px",
                        "flexWrap": "wrap", "marginBottom": "20px"}),

        # ── equity chart ────────────────────────────────────────────────── #
        html.Div(
            style={"background": CARD, "border": f"1px solid {BORDER}",
                   "borderRadius": "8px", "padding": "16px",
                   "marginBottom": "16px"},
            children=[
                _section_header("Portfolio Equity Curve"),
                dcc.Graph(id="equity-chart",
                          config={"displayModeBar": False},
                          style={"height": "320px"}),
            ],
        ),

        # ── positions + trades ──────────────────────────────────────────── #
        html.Div(
            style={"display": "grid",
                   "gridTemplateColumns": "1fr 2fr",
                   "gap": "16px"},
            children=[
                # positions
                html.Div(
                    style={"background": CARD, "border": f"1px solid {BORDER}",
                           "borderRadius": "8px", "padding": "16px"},
                    children=[
                        _section_header("Open Positions"),
                        html.Div(id="positions-table"),
                    ],
                ),
                # recent trades
                html.Div(
                    style={"background": CARD, "border": f"1px solid {BORDER}",
                           "borderRadius": "8px", "padding": "16px"},
                    children=[
                        _section_header("Recent Trades"),
                        html.Div(id="trades-table"),
                    ],
                ),
            ],
        ),

        # ── hidden interval for live refresh ─────────────────────────────── #
        dcc.Interval(id="interval", interval=POLL_INTERVAL_MS, n_intervals=0),
    ],
)


# ─────────────────────────────────────────────────── callbacks ────────────── #

@app.callback(
    Output("live-badge", "children"),
    Output("kpi-row", "children"),
    Output("equity-chart", "figure"),
    Output("positions-table", "children"),
    Output("trades-table", "children"),
    Input("interval", "n_intervals"),
)
def refresh(_n):
    now = datetime.utcnow().strftime("%H:%M:%S UTC")
    badge = f"Last updated: {now}"

    # ── equity curve ──────────────────────────────────────────────────────── #
    if _db_available():
        snaps = _portfolio_snapshots()
        dates  = [s["created_at"] for s in snaps]
        values = [s["total_value"] for s in snaps]
    else:
        dates, values = _demo_equity()
        badge = f"⚠ Demo mode · {now}"

    initial = values[0] if values else 400.0
    total_return = (values[-1] / initial - 1) * 100 if values else 0.0
    current_val  = values[-1] if values else initial

    # ── KPI cards ─────────────────────────────────────────────────────────── #
    ret_color = GREEN if total_return >= 0 else RED
    kpis = [
        _kpi_card("Portfolio Value",
                  f"€{current_val:,.2f}",
                  f"Initial: €{initial:,.2f}"),
        _kpi_card("Total Return",
                  f"{total_return:+.2f}%",
                  f"€{current_val - initial:+,.2f}",
                  color=ret_color),
    ]

    if _db_available():
        port = _latest_portfolio()
        if port:
            kpis.append(_kpi_card("Unallocated",
                                  f"€{port['unallocated']:,.2f}",
                                  "Available cash"))
        trades = _trades()
        if trades:
            closed = [t for t in trades if t.get("status") == "closed"]
            wins   = [t for t in closed if (t.get("net_gain") or 0) > 0]
            wr = len(wins) / len(closed) * 100 if closed else 0.0
            kpis.append(_kpi_card("Win Rate", f"{wr:.1f}%",
                                  f"{len(closed)} closed trades",
                                  color=GREEN if wr >= 50 else RED))
    else:
        kpis.append(_kpi_card("Status", "Demo", "No live DB found"))

    # ── equity figure ─────────────────────────────────────────────────────── #
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=values,
        mode="lines",
        line=dict(color=ACCENT, width=1.5),
        fill="tozeroy",
        fillcolor="rgba(31,111,178,0.08)",
        name="Portfolio Value",
        hovertemplate="<b>%{x}</b><br>€%{y:,.2f}<extra></extra>",
    ))
    fig.add_hline(y=initial, line=dict(color="#8b949e", dash="dot", width=1))
    fig.update_layout(
        paper_bgcolor=CARD,
        plot_bgcolor=CARD,
        font=dict(color=TEXT, size=11),
        margin=dict(l=0, r=0, t=4, b=0),
        xaxis=dict(showgrid=False, color="#8b949e",
                   tickfont=dict(size=10)),
        yaxis=dict(gridcolor=BORDER, color="#8b949e",
                   tickformat="€,.0f", tickfont=dict(size=10)),
        showlegend=False,
        hovermode="x unified",
    )

    # ── positions ─────────────────────────────────────────────────────────── #
    if _db_available():
        pos_rows = _positions()
    else:
        pos_rows = [{"symbol": "BTC", "amount": 0.00423,
                     "cost": 100.0, "value": 112.5}]

    if pos_rows:
        pos_table = dash_table.DataTable(
            data=pos_rows,
            columns=[
                {"name": "Symbol", "id": "symbol"},
                {"name": "Amount", "id": "amount",
                 "type": "numeric", "format": {"specifier": ".6f"}},
                {"name": "Cost (€)",  "id": "cost",
                 "type": "numeric", "format": {"specifier": ",.2f"}},
                {"name": "Value (€)", "id": "value",
                 "type": "numeric", "format": {"specifier": ",.2f"}},
            ],
            style_table={"overflowX": "auto"},
            style_header={"background": BG, "color": "#8b949e",
                           "border": "none", "fontSize": "0.75rem",
                           "fontWeight": "600"},
            style_cell={"background": CARD, "color": TEXT,
                        "border": f"1px solid {BORDER}",
                        "padding": "8px 12px", "fontSize": "0.8rem"},
            style_data_conditional=[
                {"if": {"row_index": "odd"},
                 "backgroundColor": "#1c2128"},
            ],
        )
    else:
        pos_table = html.P("No open positions.",
                           style={"color": "#8b949e", "fontSize": "0.8rem"})

    # ── recent trades ─────────────────────────────────────────────────────── #
    if _db_available():
        trade_rows = _trades(20)
    else:
        trade_rows = [
            {"symbol": "BTC", "opened_at": "2024-01-15 08:00",
             "closed_at": "2024-01-22 14:00",
             "net_gain": 12.40, "net_gain_percentage": 12.4,
             "status": "closed"},
            {"symbol": "BTC", "opened_at": "2024-02-03 10:00",
             "closed_at": "2024-02-09 16:00",
             "net_gain": -5.20, "net_gain_percentage": -5.2,
             "status": "closed"},
        ]

    if trade_rows:
        trades_table = dash_table.DataTable(
            data=trade_rows,
            columns=[
                {"name": "Symbol",   "id": "symbol"},
                {"name": "Opened",   "id": "opened_at"},
                {"name": "Closed",   "id": "closed_at"},
                {"name": "Net Gain (€)", "id": "net_gain",
                 "type": "numeric", "format": {"specifier": "+,.2f"}},
                {"name": "Return %", "id": "net_gain_percentage",
                 "type": "numeric", "format": {"specifier": "+.2f"}},
                {"name": "Status",   "id": "status"},
            ],
            style_table={"overflowX": "auto"},
            style_header={"background": BG, "color": "#8b949e",
                           "border": "none", "fontSize": "0.75rem",
                           "fontWeight": "600"},
            style_cell={"background": CARD, "color": TEXT,
                        "border": f"1px solid {BORDER}",
                        "padding": "8px 12px", "fontSize": "0.8rem"},
            style_data_conditional=[
                {"if": {"row_index": "odd"},
                 "backgroundColor": "#1c2128"},
                {"if": {"filter_query": "{net_gain} > 0",
                        "column_id": "net_gain"},
                 "color": GREEN},
                {"if": {"filter_query": "{net_gain} < 0",
                        "column_id": "net_gain"},
                 "color": RED},
                {"if": {"filter_query": "{net_gain_percentage} > 0",
                        "column_id": "net_gain_percentage"},
                 "color": GREEN},
                {"if": {"filter_query": "{net_gain_percentage} < 0",
                        "column_id": "net_gain_percentage"},
                 "color": RED},
            ],
            page_size=10,
        )
    else:
        trades_table = html.P("No trades recorded yet.",
                              style={"color": "#8b949e", "fontSize": "0.8rem"})

    return badge, kpis, fig, pos_table, trades_table


# ──────────────────────────────────────────────────────────── main ────────── #

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    print(f"\n  tradebot live dashboard  ->  http://127.0.0.1:{port}\n")
    app.run(debug=False, host="0.0.0.0", port=port)
