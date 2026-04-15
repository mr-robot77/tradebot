"""
Visualization module for backtest results.

Generates a multi-panel performance report matching the QF-Lib style,
including:
  - Header block with strategy metadata
  - Strategy performance (normalized equity curve)
  - Monthly returns heatmap with color-coded cells
  - Yearly returns horizontal bar chart
  - Distribution of monthly returns histogram
  - Normal distribution Q-Q plot
  - Rolling statistics (6-month rolling return and volatility)
  - Page footer

Usage:
    python plot.py <start_date> <end_date>
    python plot.py 2023-01-01 2023-12-30

Or import and call directly after running a backtest:
    from plot import plot_backtest
    plot_backtest(backtest, output_path="backtest_report.png")
"""

import math
from datetime import datetime

import matplotlib.gridspec as gridspec
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter
from scipy import stats

# Number of trading days used for the 6-month rolling window (~126 = 252 / 2)
ROLLING_WINDOW_TRADING_DAYS = 126

# Approximate number of trading days in a year used to annualise volatility
TRADING_DAYS_PER_YEAR = 252

# Divisor applied to the number of monthly return data points when
# calculating histogram bin count (keeps bins readable for small datasets)
HISTOGRAM_BIN_DIVISOR = 3

# Report style constants
REPORT_BG = "white"
HEADER_BG = "#f5f5f5"
ACCENT_BLUE = "#1f6fb2"
ACCENT_DARK = "#333333"
GRID_ALPHA = 0.35

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ────────────────────────────────────────────────────────── helpers ──────── #

def _pct(x, _=None):
    return f"{x * 100:.0f}%"


def _pct1(x, _=None):
    return f"{x * 100:.1f}%"


def _build_equity_series(equity_curve):
    """Convert list of (value, datetime) to a sorted pandas Series."""
    values = [v for v, _ in equity_curve]
    dates = [d for _, d in equity_curve]
    s = pd.Series(values, index=pd.DatetimeIndex(dates))
    s.sort_index(inplace=True)
    return s


def _build_monthly_table(monthly_returns):
    """Return DataFrame[years × 12 months] of return fractions."""
    rows = {}
    for ret, dt in monthly_returns:
        year = dt.year
        month = dt.month
        rows.setdefault(year, {})[month] = ret
    df = pd.DataFrame(rows).T.reindex(columns=range(1, 13))
    df.index.name = "Year"
    return df


def _build_yearly_series(yearly_returns):
    """Return pandas Series indexed by integer year."""
    if not yearly_returns:
        return pd.Series(dtype=float)
    values = [v for v, _ in yearly_returns]
    years = [d.year for _, d in yearly_returns]
    return pd.Series(values, index=years)


def _draw_header(fig, strategy_name, start_date, end_date,
                 metrics, report_date=None):
    """
    Draw a QF-Lib-style header block at the very top of the figure.
    Draws directly into figure coordinates so it is independent of the
    axes grid.
    """
    if report_date is None:
        report_date = datetime.utcnow()

    # Shaded header rectangle
    fig.add_artist(
        mpatches.FancyBboxPatch(
            (0, 0.955), 1, 0.045,
            boxstyle="square,pad=0",
            transform=fig.transFigure,
            facecolor=HEADER_BG,
            edgecolor="#cccccc",
            linewidth=0.5,
            zorder=0,
            clip_on=False,
        )
    )

    # Left column – logo placeholder + generated-by text
    fig.text(0.01, 0.982, "●", fontsize=18, color=ACCENT_BLUE,
             transform=fig.transFigure, va="top", fontweight="bold")
    fig.text(0.04, 0.982, "tradebot", fontsize=10, color=ACCENT_DARK,
             transform=fig.transFigure, va="top", fontweight="bold")
    fig.text(0.04, 0.969, strategy_name, fontsize=8.5, color="#555555",
             transform=fig.transFigure, va="top")
    fig.text(0.04, 0.958,
             report_date.strftime("%d %B %Y").lstrip("0"),
             fontsize=8, color="#888888",
             transform=fig.transFigure, va="top")

    # Right column – key metrics summary
    if metrics is not None:
        growth = float(metrics.total_net_gain_percentage)
        try:
            sharpe = float(metrics.sharpe_ratio)
        except Exception:
            sharpe = float("nan")
        try:
            max_dd = float(metrics.max_drawdown)
        except Exception:
            max_dd = float("nan")

        summary = (
            f"Total Return: {growth:.2f}%   "
            f"Sharpe: {sharpe:.2f}   "
            f"Max Drawdown: {max_dd * 100:.2f}%   "
            f"Period: {start_date} → {end_date}"
        )
        fig.text(0.55, 0.970, summary, fontsize=8, color=ACCENT_DARK,
                 transform=fig.transFigure, va="top")

    # Horizontal divider below header
    fig.add_artist(
        plt.Line2D(
            [0, 1], [0.954, 0.954],
            transform=fig.transFigure,
            color="#aaaaaa", linewidth=0.8,
        )
    )


def _draw_footer(fig):
    """Draw page footer."""
    fig.text(0.99, 0.012, "Page 1 of 1",
             ha="right", va="bottom", fontsize=7.5, color="#888888",
             transform=fig.transFigure)
    fig.add_artist(
        plt.Line2D(
            [0.01, 0.99], [0.023, 0.023],
            transform=fig.transFigure,
            color="#cccccc", linewidth=0.6,
        )
    )


# ─────────────────────────────────────────────────── main public API ──────── #

def plot_backtest(
    backtest,
    output_path="backtest_report.png",
    strategy_name="Golden Cross / Death Cross Strategy",
    dpi=150,
):
    """
    Generate a QF-Lib-style multi-panel backtest performance report.

    Args:
        backtest: Backtest object returned by ``app.run_backtest()``.
        output_path (str): File path to write the PNG report to.
        strategy_name (str): Strategy label shown in the report header.
        dpi (int): Resolution of the saved image.

    Returns:
        str: The resolved ``output_path``.
    """
    if not backtest.backtest_runs:
        raise ValueError("Backtest contains no runs.")

    run = backtest.backtest_runs[0]
    metrics = run.backtest_metrics

    if metrics is None:
        raise ValueError("Backtest run contains no metrics.")

    equity_curve = metrics.equity_curve
    if not equity_curve:
        raise ValueError("Equity curve is empty.")

    monthly_returns = metrics.monthly_returns
    yearly_returns = metrics.yearly_returns

    start_str = run.backtest_start_date.strftime("%Y-%m-%d")
    end_str = run.backtest_end_date.strftime("%Y-%m-%d")

    # ── build data structures ─────────────────────────────────────────────── #
    equity_series = _build_equity_series(equity_curve)
    equity_norm = equity_series / equity_series.iloc[0]
    monthly_table = _build_monthly_table(monthly_returns)
    yearly_series = _build_yearly_series(yearly_returns)
    daily_returns = equity_series.pct_change().dropna()

    rolling_return = daily_returns.rolling(ROLLING_WINDOW_TRADING_DAYS).apply(
        lambda x: (1 + x).prod() - 1
    )
    rolling_vol = (
        daily_returns.rolling(ROLLING_WINDOW_TRADING_DAYS).std()
        * math.sqrt(TRADING_DAYS_PER_YEAR)
    )
    monthly_ret_values = [r for r, _ in monthly_returns]

    # ── figure & layout ───────────────────────────────────────────────────── #
    fig = plt.figure(figsize=(11.69, 16.54))   # A4 portrait at 1x
    fig.patch.set_facecolor(REPORT_BG)

    # 5 row grid: performance / (monthly + yearly) / (hist + qq) / rolling
    outer = gridspec.GridSpec(
        4, 1, figure=fig,
        hspace=0.55,
        top=0.945,
        bottom=0.04,
        left=0.07,
        right=0.97,
        height_ratios=[1.8, 1.5, 1.5, 1.8],
    )

    ax_equity = fig.add_subplot(outer[0])

    inner1 = gridspec.GridSpecFromSubplotSpec(
        1, 2, subplot_spec=outer[1], wspace=0.35
    )
    ax_monthly = fig.add_subplot(inner1[0])
    ax_yearly = fig.add_subplot(inner1[1])

    inner2 = gridspec.GridSpecFromSubplotSpec(
        1, 2, subplot_spec=outer[2], wspace=0.35
    )
    ax_dist = fig.add_subplot(inner2[0])
    ax_qq = fig.add_subplot(inner2[1])

    ax_rolling = fig.add_subplot(outer[3])

    # ── header & footer ───────────────────────────────────────────────────── #
    _draw_header(fig, strategy_name, start_str, end_str, metrics)
    _draw_footer(fig)

    # ── panel 1 – Strategy Performance ───────────────────────────────────── #
    ax_equity.plot(
        equity_norm.index, equity_norm.values,
        color=ACCENT_BLUE, linewidth=1.2, label=strategy_name,
    )
    ax_equity.axhline(1.0, color="grey", linewidth=0.7, linestyle="--")
    ax_equity.set_title("Strategy Performance", fontweight="bold", fontsize=10)
    ax_equity.set_ylabel("Normalized Value", fontsize=8)
    ax_equity.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.1f}"))
    ax_equity.legend(loc="upper left", fontsize=8)
    ax_equity.grid(True, linestyle="--", alpha=GRID_ALPHA)
    ax_equity.set_xlim(equity_norm.index[0], equity_norm.index[-1])
    ax_equity.tick_params(labelsize=8)

    # ── panel 2 – Monthly Returns heatmap ────────────────────────────────── #
    if not monthly_table.empty:
        heat_data = monthly_table.values.astype(float)
        abs_max = max(np.nanpercentile(np.abs(heat_data[~np.isnan(heat_data)]), 95), 0.01)
        cmap = mcolors.LinearSegmentedColormap.from_list(
            "rg", ["#c0392b", "#ffffff", "#27ae60"], N=256
        )
        ax_monthly.imshow(
            heat_data, cmap=cmap,
            vmin=-abs_max, vmax=abs_max, aspect="auto",
        )
        ax_monthly.set_xticks(range(12))
        ax_monthly.set_xticklabels(MONTH_NAMES, fontsize=7)
        ax_monthly.set_xlabel("Month", fontsize=8)
        ax_monthly.set_yticks(range(len(monthly_table.index)))
        ax_monthly.set_yticklabels(monthly_table.index, fontsize=7)
        ax_monthly.set_ylabel("Year", fontsize=8)
        ax_monthly.set_title("Monthly Returns", fontweight="bold", fontsize=10)

        for i in range(heat_data.shape[0]):
            for j in range(heat_data.shape[1]):
                val = heat_data[i, j]
                if not np.isnan(val):
                    ax_monthly.text(
                        j, i, f"{val * 100:.1f}",
                        ha="center", va="center", fontsize=5,
                        color="black",
                    )
    else:
        ax_monthly.set_title("Monthly Returns", fontweight="bold", fontsize=10)
        ax_monthly.text(0.5, 0.5, "No data",
                        ha="center", va="center",
                        transform=ax_monthly.transAxes, fontsize=9)

    # ── panel 3 – Yearly Returns ──────────────────────────────────────────── #
    if not yearly_series.empty:
        bar_colors = [
            "#27ae60" if v >= 0 else "#c0392b" for v in yearly_series.values
        ]
        y_labels = [str(y) for y in yearly_series.index]
        ax_yearly.barh(
            y_labels, yearly_series.values,
            color=bar_colors, edgecolor="white", height=0.6,
        )
        mean_val = yearly_series.mean()
        ax_yearly.axvline(
            mean_val, color="grey", linestyle="--", linewidth=1,
            label=f"Mean: {mean_val * 100:.1f}%",
        )
        ax_yearly.xaxis.set_major_formatter(FuncFormatter(_pct))
        ax_yearly.set_title("Yearly Returns", fontweight="bold", fontsize=10)
        ax_yearly.set_xlabel("Returns", fontsize=8)
        ax_yearly.legend(fontsize=7.5)
        ax_yearly.grid(axis="x", linestyle="--", alpha=GRID_ALPHA)
        ax_yearly.tick_params(labelsize=8)

        for i, (year, val) in enumerate(yearly_series.items()):
            offset = 0.003 if val >= 0 else -0.003
            ha = "left" if val >= 0 else "right"
            ax_yearly.text(
                val + offset, i, f"{val * 100:.1f}%",
                va="center", ha=ha, fontsize=7,
            )
    else:
        ax_yearly.set_title("Yearly Returns", fontweight="bold", fontsize=10)
        ax_yearly.text(0.5, 0.5, "No data",
                       ha="center", va="center",
                       transform=ax_yearly.transAxes, fontsize=9)

    # ── panel 4 – Distribution of Monthly Returns ────────────────────────── #
    if monthly_ret_values:
        n_bins = max(8, len(monthly_ret_values) // HISTOGRAM_BIN_DIVISOR)
        ax_dist.hist(
            monthly_ret_values, bins=n_bins,
            color=ACCENT_BLUE, edgecolor="white", alpha=0.85,
        )
        mean_m = np.mean(monthly_ret_values)
        ax_dist.axvline(
            mean_m, color="grey", linestyle="--", linewidth=1.2,
            label=f"Mean: {mean_m * 100:.2f}%",
        )
        ax_dist.xaxis.set_major_formatter(FuncFormatter(_pct1))
        ax_dist.set_title("Distribution of Monthly Returns",
                           fontweight="bold", fontsize=10)
        ax_dist.set_xlabel("Returns", fontsize=8)
        ax_dist.set_ylabel("Occurrences", fontsize=8)
        ax_dist.legend(fontsize=8)
        ax_dist.tick_params(labelsize=8)
    else:
        ax_dist.set_title("Distribution of Monthly Returns",
                           fontweight="bold", fontsize=10)
        ax_dist.text(0.5, 0.5, "No data",
                     ha="center", va="center",
                     transform=ax_dist.transAxes, fontsize=9)

    # ── panel 5 – Normal Distribution Q-Q ─────────────────────────────────── #
    if len(monthly_ret_values) >= 4:
        (osm, osr), (slope, intercept, _) = stats.probplot(
            monthly_ret_values, dist="norm"
        )
        ax_qq.scatter(osm, osr, color=ACCENT_BLUE,
                      s=16, alpha=0.8, zorder=3)
        line_x = np.array([osm[0], osm[-1]])
        ax_qq.plot(line_x, slope * line_x + intercept,
                   color=ACCENT_DARK, linewidth=1.2)
        ax_qq.axhline(0, color="lightgrey", linewidth=0.6)
        ax_qq.axvline(0, color="lightgrey", linewidth=0.6)
        ax_qq.set_title("Normal Distribution Q-Q",
                         fontweight="bold", fontsize=10)
        ax_qq.set_xlabel("Normal Distribution Quantile", fontsize=8)
        ax_qq.set_ylabel("Observed Quantile", fontsize=8)
        ax_qq.grid(linestyle="--", alpha=GRID_ALPHA)
        ax_qq.tick_params(labelsize=8)
    else:
        ax_qq.set_title("Normal Distribution Q-Q",
                         fontweight="bold", fontsize=10)
        ax_qq.text(0.5, 0.5, "Insufficient data",
                   ha="center", va="center",
                   transform=ax_qq.transAxes, fontsize=9)

    # ── panel 6 – Rolling Statistics [6 Months] ──────────────────────────── #
    ax_rolling.plot(
        rolling_return.index, rolling_return.values,
        color=ACCENT_BLUE, linewidth=1, label="Rolling Return",
    )
    ax_twin = ax_rolling.twinx()
    ax_twin.plot(
        rolling_vol.index, rolling_vol.values,
        color=ACCENT_DARK, linewidth=1, linestyle="-",
        alpha=0.7, label="Rolling Volatility",
    )
    ax_rolling.axhline(0, color="grey", linewidth=0.7, linestyle="--")
    ax_rolling.set_title("Rolling Statistics [6 Months]",
                          fontweight="bold", fontsize=10)
    ax_rolling.set_ylabel("Rolling Return", fontsize=8)
    ax_twin.set_ylabel("Rolling Volatility (ann.)", fontsize=8)
    ax_rolling.yaxis.set_major_formatter(FuncFormatter(_pct))
    ax_twin.yaxis.set_major_formatter(FuncFormatter(_pct))
    ax_rolling.grid(True, linestyle="--", alpha=GRID_ALPHA)
    ax_rolling.tick_params(labelsize=8)
    ax_twin.tick_params(labelsize=8)
    ax_rolling.set_xlim(rolling_return.index[0], rolling_return.index[-1])

    lines1, lbl1 = ax_rolling.get_legend_handles_labels()
    lines2, lbl2 = ax_twin.get_legend_handles_labels()
    ax_rolling.legend(lines1 + lines2, lbl1 + lbl2,
                       loc="upper right", fontsize=8)

    # ── save ─────────────────────────────────────────────────────────────── #
    plt.savefig(output_path, dpi=dpi, bbox_inches="tight",
                facecolor=REPORT_BG)
    plt.close(fig)
    print(f"Backtest report saved to: {output_path}")
    return output_path


# ─────────────────────────────────────────────────── CLI entry-point ──────── #

if __name__ == "__main__":
    import sys
    from investing_algorithm_framework import PortfolioConfiguration, \
        BacktestDateRange
    from app import app

    def _parse_date(s):
        try:
            return datetime.strptime(s, "%Y-%m-%d")
        except ValueError:
            print(f"Invalid date format '{s}'. Use YYYY-MM-DD.")
            sys.exit(1)

    if len(sys.argv) != 3:
        print("Usage: python plot.py <start_date> <end_date>")
        print("Example: python plot.py 2023-01-01 2023-12-30")
        sys.exit(1)

    app.add_portfolio_configuration(
        PortfolioConfiguration(
            market="BITVAVO",
            trading_symbol="EUR",
            initial_balance=400,
        )
    )

    backtest = app.run_backtest(
        backtest_date_range=BacktestDateRange(
            start_date=_parse_date(sys.argv[1]),
            end_date=_parse_date(sys.argv[2]),
        ),
        show_progress=True,
    )

    plot_backtest(backtest, output_path="backtest_report.png")

