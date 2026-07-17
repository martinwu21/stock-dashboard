# Stock Dashboard

A personal Streamlit dashboard to track price and fundamental metrics for your stock watchlist.

## Watchlist

Edit `watchlist.json` or use the dashboard:

- **Reorder:** click and hold a ticker, drag it up or down, then release
- **Add:** type a Yahoo Finance symbol in the blank bottom row and press Enter

Use Yahoo Finance symbols (e.g. `AAPL` for Apple).

## Setup

```bash
cd Projects/stock-dashboard
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

Opens at http://localhost:8501

## Metrics

- **Price:** current price, average analyst price target, target upside %, 200-day sparkline, daily change %, volume, average volume (in millions)
- **Technical:** 50-day MA, 100-day MA, 200-day MA, RSI (14), 52-week high/low
- **Fundamentals:** P/E, forward P/E, EPS

Data is fetched from Yahoo Finance via [yfinance](https://github.com/ranaroussi/yfinance). Some fields may be missing for certain tickers.

## Publish online (Streamlit Community Cloud)

No domain required. You get a free URL like `https://stock-dashboard.streamlit.app`.

### 1. Push this project to GitHub

In PowerShell, from this folder:

```powershell
cd C:\Users\marti\Projects\stock-dashboard
git init
git add .
git commit -m "Initial stock dashboard"
```

On [github.com](https://github.com), click **New repository**, name it (e.g. `stock-dashboard`), leave it empty (no README), then:

```powershell
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/stock-dashboard.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your GitHub username.

### 2. Deploy on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. Click **Create app** (or **New app**).
3. Choose your `stock-dashboard` repo, branch `main`, main file `app.py`.
4. Click **Deploy**.

After a minute or two, your app is live at a public `*.streamlit.app` URL you can share.

### Notes for the hosted app

- **Default watchlist:** comes from `watchlist.json` in the repo. Edit that file and push to change the starting list for everyone.
- **Add/reorder in the browser:** works while the app is running, but on Streamlit Cloud those changes may **reset** when the app restarts or redeploys. For a stable shared list, update `watchlist.json` in GitHub instead.
- **No API keys** are needed for this app.
