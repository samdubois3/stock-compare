# Stock Return Compare

A one-page site: pick a stock, compare it to indices or other stocks, set a dollar
amount and a time period, and see what each would be worth today.

- `index.html` — the whole site (no build step).
- `tickers.txt` — the investments the site offers. **Edit this to add more.**
- `data/` — price history (not stored in git). Downloaded fresh by
  `.github/workflows/update-data.yml` every weekday evening and published with the site.

## One-time setup

1. Create a new **public** repo on GitHub (e.g. `stock-compare`) and push this folder to it.
2. In the repo: **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. **Actions** tab → "Update data and publish site" → **Run workflow**.
   After ~2 minutes the site is live at `https://<your-username>.github.io/stock-compare/`.

## Adding a stock

Open `tickers.txt` on GitHub, click the pencil icon, add a line like
`NFLX, Netflix`, and click **Commit changes**. The site updates in a few minutes.
Use Yahoo Finance symbols (`BRK-B`, not `BRK.B`).

## Run locally

    python3 -m http.server 8000     # then open http://localhost:8000
    pip install yfinance pandas && python scripts/fetch_data.py   # refresh data
