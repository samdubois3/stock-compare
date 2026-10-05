"""Download full daily price history for every ticker in tickers.txt.

Writes data/<SYMBOL>.json (dates, close, adjusted close) and data/index.json
(the list the web page offers). Run by the GitHub Action; can also be run locally:
    pip install yfinance pandas && python scripts/fetch_data.py
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def read_tickers():
    out = []
    for line in (ROOT / "tickers.txt").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        sym, _, name = line.partition(",")
        sym = sym.strip().upper()
        out.append((sym, name.strip() or sym))
    return out


def fetch(sym):
    df = yf.download(sym, period="max", interval="1d", auto_adjust=False,
                     progress=False, threads=False)
    if df.empty:
        return None
    if hasattr(df.columns, "levels"):  # newer yfinance returns (field, ticker) columns
        df.columns = df.columns.get_level_values(0)
    df = df[["Close", "Adj Close"]].dropna()
    return {
        "d": [ts.strftime("%Y-%m-%d") for ts in df.index],
        "c": [round(float(x), 4) for x in df["Close"]],
        "a": [round(float(x), 4) for x in df["Adj Close"]],
    }


def previous_copy(sym):
    """Last published data for sym from the live site, or None."""
    base = os.environ.get("PREVIOUS_SITE", "").rstrip("/")
    if not base:
        return None
    try:
        with urllib.request.urlopen(f"{base}/data/{sym}.json", timeout=30) as r:
            return json.loads(r.read())
    except Exception:
        return None


def main():
    DATA.mkdir(exist_ok=True)
    index, failed = [], []
    for sym, name in read_tickers():
        try:
            series = fetch(sym)
        except Exception as e:  # keep going; one bad symbol shouldn't sink the run
            print(f"{sym}: error {e}")
            series = None
        path = DATA / f"{sym}.json"
        if not series and not path.exists():
            series = previous_copy(sym)
            if series:
                print(f"{sym}: download failed, reusing data from the live site")
        if series:
            path.write_text(json.dumps(series, separators=(",", ":")))
            print(f"{sym}: {len(series['d'])} days, {series['d'][0]} -> {series['d'][-1]}")
        elif path.exists():
            print(f"{sym}: download failed, keeping previous data")
        else:
            failed.append(sym)
            continue
        first = json.loads(path.read_text())["d"][0]
        index.append({"symbol": sym, "name": name, "since": first})
    (DATA / "index.json").write_text(json.dumps(index, indent=1))
    if failed:
        print("No data for:", ", ".join(failed), "(check the symbol on finance.yahoo.com)")
    if not index:
        sys.exit(1)


if __name__ == "__main__":
    main()
