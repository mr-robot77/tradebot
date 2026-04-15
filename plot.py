"""
Visualization module for backtest results.

Generates a multi-panel performance report similar to standard quantitative
finance reporting, including:
  - Strategy performance (normalized equity curve)
  - Monthly returns heatmap
  - Yearly returns bar chart
  - Distribution of monthly returns
  - Normal distribution Q-Q plot
  - Rolling statistics (6-month rolling return and volatility)
"""

import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.colors as mcolors
from matplotlib.ticker import FuncFormatter
from scipy import stats

# Number of trading days used for the 6-month rolling window (~126 = 252 / 2)
ROLLING_WINDOW_TRADING_DAYS = 126

# Approximate number of trading days in a year used to annualise volatility
TRADING_DAYS_PER_YEAR = 252

# Divisor applied to the number of monthly return data points when
# calculating histogram bin count (keeps bins readable for small datasets)
HISTOGRAM_BIN_DIVISOR = 3


def _percent_fmt(x, pos=None):
    return f"{x * 100:.1f}%"


def _build_equity_series(equity_curve):
    """Convert equity_curve list of (value, datetime) to a pandas Series."""
    values = [v for v, _ in equity_curve]
    dates = [d for _, d in equity_curve]
    series = pd.Series(values, index=pd.DatetimeIndex(dates))
    series.sort_index(inplace=True)
    return series


def _build_monthly_returns_table(monthly_returns):
    """
    Convert monthly_returns list of (return_pct, datetime) to a
    DataFrame with years as rows and months (1-12) as columns.
    """
    rows = {}
    for ret, dt in monthly_returns:
        year = dt.year
        month = dt.month
        if year not in rows:
            rows[year] = {}
        rows[year][month] = ret

    df = pd.DataFrame(rows).T
    df = df.reindex(columns=range(1, 13))
    df.index.name = "Year"
    return df


def _build_yearly_returns(yearly_returns):
    """Convert yearly_returns list of (return_pct, date) to a Series."""
    years = [d.year for _, d in yearly_returns]
    values = [v for v, _ in yearly_returns]
    return pd.Series(values, index=years)


def plot_backtest(backtest, output_path="backtest_report.png", strategy_name="Golden Cross Strategy"):
    """
    Generate a multi-panel backtest performance report and save to a file.

    Args:
        backtest: Backtest object returned by app.run_backtest().
        output_path (str): Path to save the output image.
        strategy_name (str): Name of the strategy shown in the report title.
    """
    if not backtest.backtest_runs:
        raise ValueError("Backtest contains no runs.")

    run = backtest.backtest_runs[0]
    metrics = run.backtest_metrics

    if metrics is None:
        raise ValueError("Backtest run contains no metrics.")

    equity_curve = metrics.equity_curve
    monthly_returns = metrics.monthly_returns
    yearly_returns = metrics.yearly_returns

    if not equity_curve:
        raise ValueError("Equity curve is empty.")

    # ------------------------------------------------------------------ #
    # Build data structures                                                #
    # ------------------------------------------------------------------ #
    equity_series = _build_equity_series(equity_curve)
    # Normalize equity to start at 1
    equity_norm = equity_series / equity_series.iloc[0]

    monthly_ret_table = _build_monthly_returns_table(monthly_returns)
    yearly_ret_series = _build_yearly_returns(yearly_returns)

    # Daily returns for distribution and rolling stats
    daily_returns = equity_series.pct_change().dropna()

    # 6-month rolling return and volatility
    rolling_return = daily_returns.rolling(ROLLING_WINDOW_TRADING_DAYS).apply(
        lambda x: (1 + x).prod() - 1
    )
    rolling_vol = (
        daily_returns.rolling(ROLLING_WINDOW_TRADING_DAYS).std()
        * math.sqrt(TRADING_DAYS_PER_YEAR)
    )

    # Monthly returns as a flat list for histogram
    monthly_ret_values = [r for r, _ in monthly_returns]

    # ------------------------------------------------------------------ #
    # Build figure layout                                                  #
    # ------------------------------------------------------------------ #
    fig = plt.figure(figsize=(14, 20))
    fig.patch.set_facecolor("white")

    outer = gridspec.GridSpec(5, 1, figure=fig, hspace=0.5,
                              top=0.93, bottom=0.05)

    # Row 0: equity curve (full width)
    ax_equity = fig.add_subplot(outer[0])

    # Row 1: monthly heatmap (left) + yearly bar (right)
    inner1 = gridspec.GridSpecFromSubplotSpec(
        1, 2, subplot_spec=outer[1], wspace=0.35
    )
    ax_monthly = fig.add_subplot(inner1[0])
    ax_yearly = fig.add_subplot(inner1[1])

    # Row 2: distribution histogram (left) + Q-Q plot (right)
    inner2 = gridspec.GridSpecFromSubplotSpec(
        1, 2, subplot_spec=outer[2], wspace=0.35
    )
    ax_dist = fig.add_subplot(inner2[0])
    ax_qq = fig.add_subplot(inner2[1])

    # Row 3: rolling statistics (full width)
    ax_rolling = fig.add_subplot(outer[3])

    # ------------------------------------------------------------------ #
    # Header                                                               #
    # ------------------------------------------------------------------ #
    start_str = run.backtest_start_date.strftime("%Y-%m-%d")
    end_str = run.backtest_end_date.strftime("%Y-%m-%d")
    header_text = (
        f"Backtest Report  ·  {strategy_name}  ·  "
        f"{start_str} → {end_str}"
    )
    fig.suptitle(header_text, fontsize=13, fontweight="bold", y=0.97)

    # ------------------------------------------------------------------ #
    # Panel 1 – Strategy Performance                                       #
    # ------------------------------------------------------------------ #
    ax_equity.plot(
        equity_norm.index,
        equity_norm.values,
        color="#1f6fb2",
        linewidth=1.2,
        label=strategy_name,
    )
    ax_equity.axhline(1.0, color="grey", linewidth=0.7, linestyle="--")
    ax_equity.set_title("Strategy Performance", fontweight="bold")
    ax_equity.set_ylabel("Normalized Value")
    ax_equity.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.2f}"))
    ax_equity.legend(loc="upper left", fontsize=9)
    ax_equity.grid(axis="y", linestyle="--", alpha=0.4)

    # ------------------------------------------------------------------ #
    # Panel 2 – Monthly Returns heatmap                                    #
    # ------------------------------------------------------------------ #
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    if not monthly_ret_table.empty:
        heat_data = monthly_ret_table.values.astype(float)
        vmax = max(abs(np.nanmax(heat_data)), abs(np.nanmin(heat_data)), 0.01)
        cmap = mcolors.LinearSegmentedColormap.from_list(
            "rg", ["#d73027", "white", "#1a9850"]
        )
        im = ax_monthly.imshow(
            heat_data,
            cmap=cmap,
            vmin=-vmax,
            vmax=vmax,
            aspect="auto",
        )
        ax_monthly.set_xticks(range(12))
        ax_monthly.set_xticklabels(month_names, fontsize=7)
        ax_monthly.set_yticks(range(len(monthly_ret_table.index)))
        ax_monthly.set_yticklabels(monthly_ret_table.index, fontsize=7)
        ax_monthly.set_title("Monthly Returns", fontweight="bold")

        for i in range(heat_data.shape[0]):
            for j in range(heat_data.shape[1]):
                val = heat_data[i, j]
                if not np.isnan(val):
                    ax_monthly.text(
                        j, i, f"{val * 100:.1f}",
                        ha="center", va="center", fontsize=5.5,
                        color="black"
                    )
    else:
        ax_monthly.text(0.5, 0.5, "No monthly data",
                        ha="center", va="center", transform=ax_monthly.transAxes)
        ax_monthly.set_title("Monthly Returns", fontweight="bold")

    # ------------------------------------------------------------------ #
    # Panel 3 – Yearly Returns bar chart                                   #
    # ------------------------------------------------------------------ #
    if not yearly_ret_series.empty:
        colors = ["#1a9850" if v >= 0 else "#d73027"
                  for v in yearly_ret_series.values]
        ax_yearly.barh(
            [str(y) for y in yearly_ret_series.index],
            yearly_ret_series.values,
            color=colors,
            edgecolor="white",
        )
        mean_val = yearly_ret_series.mean()
        ax_yearly.axvline(mean_val, color="grey", linestyle="--",
                          linewidth=1, label=f"Mean: {mean_val * 100:.1f}%")
        ax_yearly.xaxis.set_major_formatter(FuncFormatter(_percent_fmt))
        ax_yearly.set_title("Yearly Returns", fontweight="bold")
        ax_yearly.legend(fontsize=8)
        ax_yearly.grid(axis="x", linestyle="--", alpha=0.4)

        for i, (year, val) in enumerate(yearly_ret_series.items()):
            ax_yearly.text(
                val + (0.002 if val >= 0 else -0.002),
                i,
                f"{val * 100:.1f}%",
                va="center",
                ha="left" if val >= 0 else "right",
                fontsize=7,
            )
    else:
        ax_yearly.text(0.5, 0.5, "No yearly data",
                       ha="center", va="center", transform=ax_yearly.transAxes)
        ax_yearly.set_title("Yearly Returns", fontweight="bold")

    # ------------------------------------------------------------------ #
    # Panel 4 – Distribution of Monthly Returns                            #
    # ------------------------------------------------------------------ #
    if monthly_ret_values:
        ax_dist.hist(
            monthly_ret_values,
            bins=max(8, len(monthly_ret_values) // HISTOGRAM_BIN_DIVISOR),
            color="#1f6fb2",
            edgecolor="white",
            alpha=0.85,
        )
        mean_m = np.mean(monthly_ret_values)
        ax_dist.axvline(mean_m, color="grey", linestyle="--",
                        linewidth=1.2, label=f"Mean: {mean_m * 100:.2f}%")
        ax_dist.xaxis.set_major_formatter(FuncFormatter(_percent_fmt))
        ax_dist.set_title("Distribution of Monthly Returns", fontweight="bold")
        ax_dist.set_xlabel("Returns")
        ax_dist.set_ylabel("Occurrences")
        ax_dist.legend(fontsize=8)
    else:
        ax_dist.text(0.5, 0.5, "No monthly data",
                     ha="center", va="center", transform=ax_dist.transAxes)
        ax_dist.set_title("Distribution of Monthly Returns", fontweight="bold")

    # ------------------------------------------------------------------ #
    # Panel 5 – Normal Distribution Q-Q plot                               #
    # ------------------------------------------------------------------ #
    if monthly_ret_values and len(monthly_ret_values) >= 4:
        (osm, osr), (slope, intercept, _) = stats.probplot(
            monthly_ret_values, dist="norm"
        )
        ax_qq.scatter(osm, osr, color="#1f6fb2", s=18, alpha=0.8, zorder=3)
        line_x = np.array([min(osm), max(osm)])
        ax_qq.plot(
            line_x,
            slope * line_x + intercept,
            color="grey",
            linewidth=1.2,
        )
        ax_qq.set_title("Normal Distribution Q-Q", fontweight="bold")
        ax_qq.set_xlabel("Normal Distribution Quantile")
        ax_qq.set_ylabel("Observed Quantile")
        ax_qq.grid(linestyle="--", alpha=0.4)
    else:
        ax_qq.text(0.5, 0.5, "Insufficient data",
                   ha="center", va="center", transform=ax_qq.transAxes)
        ax_qq.set_title("Normal Distribution Q-Q", fontweight="bold")

    # ------------------------------------------------------------------ #
    # Panel 6 – Rolling Statistics (6 months)                              #
    # ------------------------------------------------------------------ #
    ax_rolling.plot(
        rolling_return.index,
        rolling_return.values,
        color="#1f6fb2",
        linewidth=1,
        label="Rolling Return",
    )
    ax_rolling_twin = ax_rolling.twinx()
    ax_rolling_twin.plot(
        rolling_vol.index,
        rolling_vol.values,
        color="#555555",
        linewidth=1,
        linestyle="--",
        label="Rolling Volatility",
    )
    ax_rolling.axhline(0, color="grey", linewidth=0.7, linestyle="--")
    ax_rolling.set_title("Rolling Statistics [6 Months]", fontweight="bold")
    ax_rolling.set_ylabel("Rolling Return")
    ax_rolling_twin.set_ylabel("Rolling Volatility (ann.)")
    ax_rolling.yaxis.set_major_formatter(FuncFormatter(_percent_fmt))
    ax_rolling_twin.yaxis.set_major_formatter(FuncFormatter(_percent_fmt))
    ax_rolling.grid(axis="y", linestyle="--", alpha=0.4)

    # Combined legend
    lines1, labels1 = ax_rolling.get_legend_handles_labels()
    lines2, labels2 = ax_rolling_twin.get_legend_handles_labels()
    ax_rolling.legend(lines1 + lines2, labels1 + labels2,
                      loc="upper right", fontsize=9)

    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Backtest report saved to: {output_path}")
    return output_path


if __name__ == "__main__":
    import sys
    from datetime import datetime

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
            initial_balance=400
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
