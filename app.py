from datetime import datetime
from html import escape
import importlib
import json

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import data as data_module
from data import fetch_stock_metrics, load_watchlist, save_watchlist

st.set_page_config(page_title="Stock Dashboard", page_icon="📈", layout="wide")

DISPLAY_COLUMNS = [
    "Ticker",
    "Price (display)",
    "Avg Target (display)",
    "Target % (display)",
    "RSI (display)",
    "Chart",
    "Change % (display)",
    "Volume (display)",
    "Avg Volume (display)",
    "MA 50 (display)",
    "MA 100 (display)",
    "MA 200 (display)",
    "52W High (display)",
    "52W Low (display)",
    "P/E (display)",
    "Fwd P/E (display)",
    "EPS (display)",
    "Signal (display)",
]

METRICS_SCHEMA_VERSION = 11

COLUMN_DEFINITIONS = {
    "Ticker": "Stock symbol on Yahoo Finance. Use the left handle to drag and reorder rows.",
    "Price": "Latest market price from Yahoo Finance.",
    "Avg Target": "Average analyst price target (mean or median).",
    "Target %": "Upside to the avg target: (target − price) / price. Green = positive upside, red = trading above target.",
    "RSI": "14-day Relative Strength Index (momentum). Green ≤ 30 = oversold, orange ≥ 70 = overbought.",
    "200D": "Sparkline of the last 200 trading days. Green line = price up over the period, red = down.",
    "Change %": "Daily change versus the previous close. Green = up, red = down.",
    "Volume": "Today's trading volume, shown in millions of shares.",
    "Avg Volume": "Average daily volume over about 3 months, in millions of shares.",
    "MA 50": "50-day moving average of the close. Green = price below MA, orange = price above MA.",
    "MA 100": "100-day moving average of the close. Green = price below MA, orange = price above MA.",
    "MA 200": "200-day moving average of the close. Green = price below MA, orange = price above MA.",
    "52W High": "Highest traded price over the last 52 weeks.",
    "52W Low": "Lowest traded price over the last 52 weeks.",
    "P/E": "Trailing price-to-earnings ratio (price divided by past earnings).",
    "Fwd P/E": "Forward price-to-earnings ratio (price divided by expected earnings).",
    "EPS": "Trailing earnings per share.",
    "Signal": (
        "Buy / Hold / Sell score from Target %, RSI, and MA 50/100/200 "
        "(+1 bullish, −1 bearish each). Buy if net score ≥ 2 with 2+ bullish signals; "
        "Sell if net score ≤ −2 with 2+ bearish; otherwise Hold."
    ),
}


@st.cache_data(ttl=300)
def load_metrics(
    tickers: tuple[str, ...],
    schema_version: int = METRICS_SCHEMA_VERSION,
) -> pd.DataFrame:
    return fetch_stock_metrics(list(tickers))


def ensure_metrics_columns(df: pd.DataFrame, tickers: tuple[str, ...]) -> pd.DataFrame:
    missing = [col for col in DISPLAY_COLUMNS if col not in df.columns]
    if not missing:
        return df

    load_metrics.clear()
    fresh_df = data_module.fetch_stock_metrics(list(tickers))
    still_missing = [col for col in DISPLAY_COLUMNS if col not in fresh_df.columns]
    if still_missing:
        st.error(f"Missing dashboard columns: {', '.join(still_missing)}")
        st.stop()
    return fresh_df


def to_display_df(df: pd.DataFrame) -> pd.DataFrame:
    return df[DISPLAY_COLUMNS].rename(
        columns={col: col.replace(" (display)", "") for col in DISPLAY_COLUMNS}
    )


def _price_vs_ma_class(price, ma_value) -> str | None:
    if pd.isna(price) or pd.isna(ma_value):
        return None
    if price < ma_value:
        return "rsi-low"
    if price > ma_value:
        return "rsi-high"
    return None


def _signal_class(signal: str) -> str | None:
    if signal == "Buy":
        return "change-up"
    if signal == "Sell":
        return "change-down"
    return None


def _header_cell(label: str, *, frozen: bool = False) -> str:
    definition = COLUMN_DEFINITIONS.get(label, "")
    frozen_class = " frozen-col" if frozen else ""
    if not definition:
        return f"<th class='{frozen_class.strip()}'>{escape(label)}</th>"

    escaped_definition = escape(definition, quote=True)
    return (
        f"<th class='col-help{frozen_class}' "
        f'data-definition="{escaped_definition}" '
        f'title="{escaped_definition}">'
        f"{escape(label)}</th>"
    )


def handle_watchlist_order_param() -> None:
    order_param = st.query_params.get("watchlist_order")
    if not order_param:
        return

    new_order = [t.strip().upper() for t in order_param.split(",") if t.strip()]
    current = [t.upper() for t in load_watchlist()]
    if not new_order or new_order == current or set(new_order) != set(current):
        del st.query_params["watchlist_order"]
        st.rerun()
        return

    order_key = ",".join(new_order)
    if st.session_state.get("last_saved_order") != order_key:
        save_watchlist(new_order)
        st.session_state["last_saved_order"] = order_key
        load_metrics.clear()

    del st.query_params["watchlist_order"]
    st.rerun()


def render_html_table(display_df: pd.DataFrame, raw_df: pd.DataFrame) -> None:
    headers = [
        "<th class='frozen-col drag-col' title='Drag rows to reorder your watchlist' "
        "aria-label='Reorder'></th>"
    ]
    for col in display_df.columns:
        label = "200D" if col == "Chart" else col
        headers.append(_header_cell(label, frozen=(col == "Ticker")))

    rows = []
    for idx, row in display_df.iterrows():
        ticker = str(row["Ticker"])
        change = raw_df.loc[idx, "Change %"]
        target_pct = raw_df.loc[idx, "Target %"]
        rsi = raw_df.loc[idx, "RSI"]
        price = raw_df.loc[idx, "Price"]
        chart_uri = str(row["Chart"])

        cells = [
            "<td class='frozen-col drag-col drag-handle' title='Drag to reorder'>"
            "<span aria-hidden='true'>&#8942;&#8942;</span></td>"
        ]

        for col in display_df.columns:
            value = row[col]
            classes = []

            if col == "Ticker":
                classes.append("frozen-col")
            elif col == "Chart":
                classes.append("chart-cell")
            elif col == "Change %":
                if pd.notna(change):
                    classes.append("change-up" if change >= 0 else "change-down")
            elif col == "Target %":
                if pd.notna(target_pct):
                    classes.append("change-up" if target_pct >= 0 else "change-down")
            elif col == "RSI":
                if pd.notna(rsi):
                    if rsi >= 70:
                        classes.append("rsi-high")
                    elif rsi <= 30:
                        classes.append("rsi-low")
            elif col in {"MA 50", "MA 100", "MA 200"}:
                ma_class = _price_vs_ma_class(price, raw_df.loc[idx, col])
                if ma_class:
                    classes.append(ma_class)
            elif col == "Signal":
                sig_class = _signal_class("" if pd.isna(value) else str(value))
                if sig_class:
                    classes.append(sig_class)

            class_attr = f" class=\"{' '.join(classes)}\"" if classes else ""

            if col == "Chart" and chart_uri:
                cell_html = (
                    f"<img src=\"{escape(chart_uri, quote=True)}\" "
                    f"alt=\"{escape(ticker)} 200 day chart\" />"
                )
            else:
                cell_html = escape("" if pd.isna(value) else str(value))

            cells.append(f"<td{class_attr}>{cell_html}</td>")

        rows.append(f"<tr data-ticker=\"{escape(ticker)}\">{''.join(cells)}</tr>")

    table_height = max(250, 44 * (len(display_df) + 1) + 36)
    default_definition = "Hover or click a column title to see what it means."
    table_html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.2/Sortable.min.js"></script>
  <style>
    html, body {{
      margin: 0;
      padding: 0;
      background: transparent;
      color: #fafafa;
      font-family: "Source Sans Pro", sans-serif;
    }}
    .stock-table-wrap {{
      overflow-x: auto;
      width: 100%;
      border: 1px solid rgba(128, 128, 128, 0.25);
      border-radius: 0.5rem;
    }}
    .stock-table {{
      border-collapse: separate;
      border-spacing: 0;
      width: max-content;
      min-width: 100%;
      font-size: 0.875rem;
    }}
    .stock-table th,
    .stock-table td {{
      padding: 0.55rem 0.85rem;
      text-align: left;
      border-bottom: 1px solid rgba(128, 128, 128, 0.2);
      white-space: nowrap;
      vertical-align: middle;
      background-color: rgb(14, 17, 23);
      color: #fafafa;
    }}
    .stock-table thead th {{
      position: sticky;
      top: 0;
      z-index: 2;
      background-color: rgb(38, 39, 48);
      color: #fafafa;
      font-weight: 600;
    }}
    .stock-table th.col-help {{
      cursor: help;
    }}
    .stock-table th.col-help:hover {{
      background-color: rgb(48, 49, 58);
    }}
    .stock-table th.col-help.is-active {{
      background-color: rgb(55, 56, 68);
      box-shadow: inset 0 -2px 0 #3b82f6;
    }}
    .definition-bar {{
      padding: 0.45rem 0.85rem;
      font-size: 0.8rem;
      line-height: 1.35;
      color: #d1d5db;
      background-color: rgb(24, 27, 36);
      border-bottom: 1px solid rgba(128, 128, 128, 0.25);
      min-height: 2rem;
    }}
    .definition-bar.is-pinned {{
      color: #fafafa;
      background-color: rgb(30, 41, 59);
      border-bottom-color: rgba(59, 130, 246, 0.45);
    }}
    .stock-table .frozen-col {{
      position: sticky;
      z-index: 1;
      box-shadow: 2px 0 4px rgba(0, 0, 0, 0.25);
    }}
    .stock-table thead .frozen-col {{
      z-index: 3;
      background-color: rgb(38, 39, 48);
    }}
    .stock-table tbody .frozen-col {{
      background-color: rgb(14, 17, 23);
    }}
    .stock-table .drag-col {{
      left: 0;
      width: 2rem;
      min-width: 2rem;
      max-width: 2rem;
      padding-left: 0.45rem;
      padding-right: 0.45rem;
      text-align: center;
    }}
    .stock-table .frozen-col:not(.drag-col) {{
      left: 2rem;
      font-weight: 600;
    }}
    .stock-table .drag-handle {{
      cursor: grab;
      color: #9ca3af;
      user-select: none;
    }}
    .stock-table .drag-handle:active {{
      cursor: grabbing;
    }}
    .stock-table .change-up {{ color: #16a34a; }}
    .stock-table .change-down {{ color: #dc2626; }}
    .stock-table .rsi-high {{ color: #f97316; }}
    .stock-table .rsi-low {{ color: #16a34a; }}
    .stock-table .chart-cell {{
      padding-top: 0.25rem;
      padding-bottom: 0.25rem;
    }}
    .stock-table .chart-cell img {{
      display: block;
      height: 34px;
      width: 128px;
    }}
    .sortable-ghost {{
      opacity: 0.45;
      background: rgba(59, 130, 246, 0.12) !important;
    }}
  </style>
</head>
<body>
  <div class="stock-table-wrap">
    <div id="definition-bar" class="definition-bar">{escape(default_definition)}</div>
    <table class="stock-table">
      <thead><tr>{''.join(headers)}</tr></thead>
      <tbody id="stock-tbody">{''.join(rows)}</tbody>
    </table>
  </div>
  <script>
    const definitionBar = document.getElementById("definition-bar");
    const defaultDefinition = {json.dumps(default_definition)};
    let pinnedHeader = null;

    function setDefinition(text, pinned) {{
      definitionBar.textContent = text;
      definitionBar.classList.toggle("is-pinned", pinned);
    }}

    function clearPinnedHeader() {{
      if (!pinnedHeader) {{
        return;
      }}
      pinnedHeader.classList.remove("is-active");
      pinnedHeader = null;
      setDefinition(defaultDefinition, false);
    }}

    document.querySelectorAll("th.col-help").forEach((header) => {{
      const definition = header.dataset.definition;
      header.addEventListener("mouseenter", () => {{
        if (!pinnedHeader) {{
          setDefinition(definition, false);
        }}
      }});
      header.addEventListener("mouseleave", () => {{
        if (!pinnedHeader) {{
          setDefinition(defaultDefinition, false);
        }}
      }});
      header.addEventListener("click", (event) => {{
        event.stopPropagation();
        if (pinnedHeader === header) {{
          clearPinnedHeader();
          return;
        }}
        if (pinnedHeader) {{
          pinnedHeader.classList.remove("is-active");
        }}
        pinnedHeader = header;
        header.classList.add("is-active");
        setDefinition(definition, true);
      }});
    }});

    document.addEventListener("click", clearPinnedHeader);

    const tbody = document.getElementById("stock-tbody");
    if (tbody && typeof Sortable !== "undefined") {{
      new Sortable(tbody, {{
        handle: ".drag-handle",
        animation: 150,
        ghostClass: "sortable-ghost",
        onEnd: function () {{
          const order = Array.from(tbody.querySelectorAll("tr"))
            .map((row) => row.dataset.ticker)
            .filter(Boolean);
          if (!order.length) {{
            return;
          }}
          const url = new URL(window.parent.location.href);
          url.searchParams.set("watchlist_order", order.join(","));
          window.parent.location.href = url.toString();
        }},
      }});
    }}
  </script>
</body>
</html>
"""

    components.html(table_html, height=table_height, scrolling=False)


def add_ticker(ticker: str) -> str | None:
    ticker = ticker.strip().upper()
    if not ticker:
        return None

    current = [t.upper() for t in load_watchlist()]
    if ticker in current:
        return "duplicate"

    save_watchlist(current + [ticker])
    return ticker


def render_add_ticker_row() -> None:
    st.markdown(
        """
        <style>
            .add-ticker-label {
                color: #9ca3af;
                font-style: italic;
                font-size: 0.875rem;
                padding-top: 0.45rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.form("add_ticker_form", clear_on_submit=True, enter_to_submit=True, border=True):
        ticker_col, btn_col, _ = st.columns([1.2, 1, 8], vertical_alignment="bottom")
        with ticker_col:
            st.markdown('<div class="add-ticker-label">Ticker</div>', unsafe_allow_html=True)
            new_ticker = st.text_input(
                "Add ticker",
                placeholder="e.g. TSLA",
                label_visibility="collapsed",
            )
        with btn_col:
            submitted = st.form_submit_button("Add", type="primary", use_container_width=True)

    if submitted:
        result = add_ticker(new_ticker)
        if result == "duplicate":
            st.warning(f"{new_ticker.strip().upper()} is already in your watchlist.")
        elif result:
            load_metrics.clear()
            st.rerun()
        else:
            st.warning("Enter a ticker symbol.")


handle_watchlist_order_param()

if st.session_state.get("metrics_schema_version") != METRICS_SCHEMA_VERSION:
    importlib.reload(data_module)
    load_metrics.clear()
    st.session_state["metrics_schema_version"] = METRICS_SCHEMA_VERSION

watchlist = load_watchlist()
if "last_saved_order" not in st.session_state:
    st.session_state["last_saved_order"] = ",".join(t.upper() for t in watchlist)

st.title("Stock Dashboard")
st.caption(
    f"Tracking {len(watchlist)} tickers · drag the handle in the table to reorder · "
    "add new tickers in the row at the bottom"
)

col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    if st.button("Refresh data", type="primary"):
        load_metrics.clear()
        st.rerun()
with col2:
    auto_refresh = st.toggle("Auto-refresh (5 min)", value=False)
with col3:
    st.write(f"Last updated: **{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}**")

if auto_refresh:
    st.markdown('<meta http-equiv="refresh" content="300">', unsafe_allow_html=True)

with st.spinner("Fetching stock data..."):
    df = ensure_metrics_columns(
        load_metrics(tuple(watchlist), METRICS_SCHEMA_VERSION),
        tuple(watchlist),
    )

errors = df[df["_load_error"].notna()]
if not errors.empty:
    st.warning(
        "Some tickers could not be loaded: "
        + ", ".join(f"{r.Ticker} ({r._load_error})" for _, r in errors.iterrows())
    )

display_df = to_display_df(df)
render_html_table(display_df, df)

render_add_ticker_row()

st.caption(
    "Hover or click column titles in the table for definitions. "
    "Signal scores Target %, RSI, and the 3 MAs (+1 bullish, -1 bearish each): "
    "Buy if net score >= 2 with 2+ bullish signals; Sell if net score <= -2 with 2+ bearish; else Hold."
)
