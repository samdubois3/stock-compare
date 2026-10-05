# Stock Return Compare

A one-page site: pick a stock, compare it to indices or other stocks, set a dollar
amount and a time period, and see what each would be worth today.

- `index.html` — the whole site (no build step).
- `tickers.txt` — the "Popular" list shown first in the picker, plus extras that
  aren't exchange-listed (e.g. mutual funds). Every stock and ETF on NYSE, NASDAQ,
  NYSE American, NYSE Arca and Cboe is included automatically.
- `data/` — price history (not stored in git). Every weekday evening
  `.github/workflows/update-data.yml` pulls the current list of listed symbols from
  nasdaqtrader.com, downloads full daily history for all of them from Yahoo Finance
  (~15 min), and publishes it with the page. No API keys.

## One-time setup

1. Create a new **public** repo on GitHub (e.g. `stock-compare`) and push this folder to it.
2. In the repo: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. **Actions** tab → "Update data and publish site" → **Run workflow**.
   After ~2 minutes the site is live at `https://<your-username>.github.io/stock-compare/`.

## Adding something that isn't listed

New listings appear on their own the next evening. To feature a symbol at the top
of the picker or add a mutual fund, open `tickers.txt` on GitHub, click the pencil,
add a line like `FCNTX, Fidelity Contrafund`, and commit.

## Run locally

    python3 -m http.server 8000     # then open http://localhost:8000
    pip install yfinance pandas && python scripts/fetch_data.py --limit 300   # sample of the data
