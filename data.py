import base64
import json
from pathlib import Path

import pandas as pd
import yfinance as yf

WATCHLIST_PATH = Path(__file__).parent / "watchlist.json"


def load_watchlist() -> list[str]:
    with open(WATCHLIST_PATH) as f:
        return json.load(f)


def save_watchlist(tickers: list[str]) -> None:
    with open(WATCHLIST_PATH, "w") as f:
        json.dump(tickers, f, indent=2)
        f.write("\n")


def _fmt_volume_millions(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    return f"{float(value) / 1e6:.2f}M"


def _moving_average(history: pd.DataFrame, window: int) -> float | None:
    if history is None or history.empty or len(history) < window:
        return None
    return float(history["Close"].tail(window).mean())


def _rsi(history: pd.DataFrame, period: int = 14) -> float | None:
    if history is None or history.empty:
        return None

    closes = history["Close"].dropna()
    if len(closes) < period + 1:
        return None

    delta = closes.diff().dropna()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = gains.tail(period).mean()
    avg_loss = losses.tail(period).mean()

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return float(100 - (100 / (1 + rs)))


def _target_upside_pct(price: float | None, target: float | None) -> float | None:
    if price is None or target is None or price == 0:
        return None
    return ((target - price) / price) * 100


def _sparkline_svg(prices: list[float], width: int = 130, height: int = 36) -> str:
    if len(prices) < 2:
        return ""

    min_price = min(prices)
    max_price = max(prices)
    span = max_price - min_price or 1
    padding = 2
    plot_width = width - 2 * padding
    plot_height = height - 2 * padding

    coords = []
    for i, price in enumerate(prices):
        x = padding + (i / (len(prices) - 1)) * plot_width
        y = padding + plot_height - ((price - min_price) / span) * plot_height
        coords.append(f"{x:.2f},{y:.2f}")

    path = "M" + " L".join(coords)
    color = "#16a34a" if prices[-1] >= prices[0] else "#dc2626"

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.5" '
        f'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )


def _chart_image_uri(prices: list[float]) -> str:
    svg = _sparkline_svg(prices)
    if not svg:
        return ""
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def fetch_stock_metrics(tickers: list[str] | None = None) -> pd.DataFrame:
    if tickers is None:
        tickers = load_watchlist()

    rows = []
    for ticker in tickers:
        row = {"Ticker": ticker}
        try:
            stock = yf.Ticker(ticker)
            info = stock.info or {}
            history = stock.history(period="1y")
            closes = [float(price) for price in history["Close"].dropna().tail(200).tolist()]

            price = info.get("currentPrice") or info.get("regularMarketPrice")
            prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
            avg_target = info.get("targetMeanPrice") or info.get("targetMedianPrice")

            change_pct = None
            if price is not None and prev_close:
                change_pct = ((price - prev_close) / prev_close) * 100

            row.update(
                {
                    "Price": price,
                    "Avg Target": avg_target,
                    "Target %": _target_upside_pct(price, avg_target),
                    "Chart": _chart_image_uri(closes),
                    "Change %": change_pct,
                    "Volume": info.get("volume") or info.get("regularMarketVolume"),
                    "Avg Volume": info.get("averageVolume")
                    or info.get("averageDailyVolume3Month"),
                    "MA 50": _moving_average(history, 50),
                    "MA 100": _moving_average(history, 100),
                    "MA 200": _moving_average(history, 200),
                    "RSI": _rsi(history, 14),
                    "52W High": info.get("fiftyTwoWeekHigh"),
                    "52W Low": info.get("fiftyTwoWeekLow"),
                    "P/E": info.get("trailingPE"),
                    "Fwd P/E": info.get("forwardPE"),
                    "EPS": info.get("trailingEps"),
                    "Status": "OK",
                }
            )
        except Exception as exc:
            row.update({"Chart": "", "Status": f"Error: {exc}"})

        rows.append(row)

    df = pd.DataFrame(rows)

    display_cols = {
        "Price": lambda v: f"${v:,.2f}" if pd.notna(v) else "—",
        "Avg Target": lambda v: f"${v:,.2f}" if pd.notna(v) else "—",
        "Target %": lambda v: f"{v:+.1f}%" if pd.notna(v) else "—",
        "Change %": lambda v: f"{v:+.2f}%" if pd.notna(v) else "—",
        "Volume": _fmt_volume_millions,
        "Avg Volume": _fmt_volume_millions,
        "MA 50": lambda v: f"${v:,.2f}" if pd.notna(v) else "—",
        "MA 100": lambda v: f"${v:,.2f}" if pd.notna(v) else "—",
        "MA 200": lambda v: f"${v:,.2f}" if pd.notna(v) else "—",
        "RSI": lambda v: f"{v:.1f}" if pd.notna(v) else "—",
        "52W High": lambda v: f"${v:,.2f}" if pd.notna(v) else "—",
        "52W Low": lambda v: f"${v:,.2f}" if pd.notna(v) else "—",
        "P/E": lambda v: f"{v:.2f}" if pd.notna(v) else "—",
        "Fwd P/E": lambda v: f"{v:.2f}" if pd.notna(v) else "—",
        "EPS": lambda v: f"${v:,.2f}" if pd.notna(v) else "—",
    }

    for col, formatter in display_cols.items():
        if col in df.columns:
            df[f"{col} (display)"] = df[col].apply(formatter)

    return df
