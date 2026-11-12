# MarketPilot Ultra — Free Web App

Mobile-friendly research dashboard for Indian and global markets built with Streamlit, Python, yfinance, and Plotly. No subscriptions or paid AI credits needed. Free feeds can be stale, delayed, blocked, or rate-limited, so nothing here is a guaranteed live trade signal.

## Free deployment

1. Go to https://share.streamlit.io and sign in using GitHub.
2. Click **Create app**, choose repository `arghajyotimalakar/marketpilot-ultra-free`, branch `main`, and app file `app.py`.
3. Click **Deploy**. Streamlit provides a shareable browser URL for your phone and laptop.

## Modules

- Macro Pulse: India / US benchmarks, yield, FX, oil, gold, and simple risk regime.
- Trade Scanner: sample of 37 large Indian stocks, EMA/MACD/RSI/RVOL/ATR technical scoring and conditional trade plans; this is *not* the full current Nifty 100.
- Chart & Trade Plan: 200-day EMA, momentum, candlesticks, ATR levels, 1% risk sizing.
- Fundamentals: heuristic quality/value score on available company financial data.
- Backtest: 3-year historical trend test with next-day fills and transaction cost assumption.
- News: latest accessible RSS headlines with *heuristic* sentiment, not a trained historical news-impact predictor.
- Risk Calculator: stop-loss based size and partial exit levels.
- CSV Lab: read and analyze your own price history.

## Run locally

`pip install -r requirements.txt`

`streamlit run app.py`

## Important

The GitHub version is designed as a lightweight free deployment. News-prediction ML and automated WhatsApp alerts are **not included**; those require real training archives and a messaging integration. This app is for paper/research only; it never submits trades. It does not promise realtime data, forecast accuracy or returns.

## Scheduled research snapshots (free GitHub Actions)

Workflow: [.github/workflows/scheduled-market.yml](.github/workflows/scheduled-market.yml)

Requested in India Standard Time (Asia/Kolkata): **07:00 daily** (including weekend news); **09:30**, **10:00**, **13:00**, **14:00**, **15:30** (market close), and **16:30** (end-of-day consolidation) on weekdays.

GitHub scheduled workflows can run late, occasionally be skipped, or be disabled after extended repository inactivity. A scheduled run does not deliver exchange-grade live market data and does not adjust for special market holidays. Data is saved to data/latest.json and data/reports/YYYY-MM-DD/HHMM.json after a successful workflow.

**Enable and test:**
1. Open the repository's **Actions** tab and enable workflows if prompted.
2. Select **Free scheduled market research** and choose **Run workflow** for the initial run.
3. Check **Settings → Actions → General → Workflow permissions**; the workflow needs **Read and write permissions** to commit public report JSON files.
4. Inspect Actions logs for feed failures or runtime errors.

The collector rotates about 125 symbols per run and reuses earlier observations. Even if 2,000+ directory entries exist, **not every share receives fresh data each run**. Fundamental data is checked for just a few names per run because free endpoints restrict high-volume access. Simple twenty-day excess return is labeled alpha_20d_pct; it is NOT regression/CAPM alpha. Vendor beta and P/E may be unavailable or stale. Financial headlines are keyword-matched, not a causal news-prediction model. The end-of-day outlook is conditional, not a forecast guarantee.

The new Streamlit page **Scheduled Market Reports** reads latest saved snapshots and shows actual data timestamps.
