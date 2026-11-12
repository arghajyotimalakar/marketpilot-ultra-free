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
