"""Download daily price history for every US-listed stock and ETF.

The symbol universe is every common stock and ETF listed on NASDAQ, NYSE,
NYSE American, NYSE Arca and Cboe (from nasdaqtrader.com's daily symbol
directory), plus anything in tickers.txt (which also sets the "Popular" list
and friendly names shown first in the picker).

Output, compact so ~12k files fit comfortably on GitHub Pages:
  data/<SYMBOL>.json  {"s": first date, "g": day gaps between rows,
                       "p": log-price x 1e4, first absolute then deltas,
                       "v": [[row, dividend], ...]}
  data/symbols.json   [[symbol, name, kind], ...]   kind: P=popular, E=ETF, S=stock

Run by the GitHub Action; can also be run locally:
    pip install yfinance pandas && python scripts/fetch_data.py [--limit N]
"""
import json
import math
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PREVIOUS_SITE = os.environ.get("PREVIOUS_SITE", "").rstrip("/")
SYMDIR = "https://www.nasdaqtrader.com/dynamic/SymDir/"
BATCH = 150

# Security types we leave out of the picker
SKIP_NAME = re.compile(r"\b(warrants?|rights?|units?|preferred|notes? due|subordinated|"
                       r"debentures?|depositary shares? representing|%)", re.I)
# Boilerplate trimmed from exchange security names
TRIM_NAME = re.compile(r"\s*[-,]?\s*(class [a-c] )?(common stock|common shares|ordinary shares|"
                       r"shares of beneficial interest|american depositary shares).*$", re.I)


def get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "stock-compare/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode()


def popular():
    out = {}
    for line in (ROOT / "tickers.txt").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            sym, _, name = line.partition(",")
            out[sym.strip().upper()] = name.strip() or sym.strip().upper()
    return out


def exchange_listed():
    """{symbol: (name, is_etf)} for listed common stocks and ETFs."""
    out = {}
    for fname, sym_col, etf_col, test_col in [("nasdaqlisted.txt", 0, 6, 3),
                                              ("otherlisted.txt", 0, 4, 6)]:
        lines = get(SYMDIR + fname).splitlines()
        width = len(lines[0].split("|"))
        for line in lines[1:]:
            f = line.split("|")
            if len(f) != width or f[test_col] == "Y":
                continue
            sym, name = f[sym_col], f[1]
            if not re.fullmatch(r"[A-Z]{1,5}(\.[A-C])?", sym) or SKIP_NAME.search(name):
                continue
            clean = TRIM_NAME.sub("", name).strip(" -,") or name
            out[sym.replace(".", "-")] = (clean, f[etf_col] == "Y")
    if len(out) < 5000:
        raise RuntimeError(f"symbol directory looks truncated ({len(out)} symbols)")
    return out


def encode(df):
    """Compact JSON-ready dict from a frame with Close and Dividends columns."""
    pending, divs, rows = 0.0, [], []
    for ts, close, div in zip(df.index, df["Close"], df["Dividends"].fillna(0)):
        pending += float(div)
        if not close > 0:  # also skips NaN
            continue
        if pending > 0 and rows:  # a dividend on a row without a price moves to the next priced row
            divs.append([len(rows), round(pending, 6)])
        pending = 0.0
        rows.append((ts, float(close)))
    if len(rows) < 2:
        return None
    logp = [round(math.log(c) * 1e4) for _, c in rows]
    return {
        "s": rows[0][0].strftime("%Y-%m-%d"),
        "g": [0] + [(rows[i][0] - rows[i - 1][0]).days for i in range(1, len(rows))],
        "p": [logp[0]] + [logp[i] - logp[i - 1] for i in range(1, len(logp))],
        "v": divs,
    }


def download(symbols):
    """{symbol: encoded} for the symbols Yahoo returned data for."""
    got = {}
    for i in range(0, len(symbols), BATCH):
        batch = symbols[i:i + BATCH]
        try:
            df = yf.download(batch, period="max", interval="1d", auto_adjust=False, actions=True,
                             group_by="ticker", progress=False, threads=True)
        except Exception as e:
            print(f"batch {i // BATCH}: error {e}")
            continue
        present = set(df.columns.get_level_values(0)) if len(df.columns) else set()
        for sym in batch:
            if sym in present and "Dividends" in df[sym]:
                enc = encode(df[sym])
                if enc:
                    got[sym] = enc
        print(f"  {min(i + BATCH, len(symbols))}/{len(symbols)} requested, {len(got)} with data", flush=True)
    return got


def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    pop = popular()
    try:
        listed = exchange_listed()
    except Exception as e:
        print(f"Symbol directory unavailable ({e}); using last published list")
        try:
            prev = json.loads(get(f"{PREVIOUS_SITE}/data/symbols.json"))
        except Exception:
            prev = []
        listed = {s: (n, k == "E") for s, n, k in prev if k != "P"}
    universe = list(pop) + sorted(s for s in listed if s not in pop)
    if limit:
        universe = universe[:limit]
    print(f"Downloading {len(universe)} symbols")

    got = download(universe)
    missing = [s for s in universe if s not in got]
    if missing:
        print(f"Retrying {len(missing)} symbols")
        time.sleep(30)
        got.update(download(missing))

    if len(got) < 0.5 * len(universe):
        # Something is badly wrong upstream; fail so the current site stays up unchanged
        sys.exit(f"Only {len(got)}/{len(universe)} symbols downloaded; not publishing")

    DATA.mkdir(exist_ok=True)
    for old in DATA.glob("*.json"):
        old.unlink()
    reused = 0
    symbols = []
    for sym in universe:
        enc = got.get(sym)
        if not enc and PREVIOUS_SITE and reused < 500:
            try:  # keep yesterday's copy rather than dropping the symbol
                enc = json.loads(get(f"{PREVIOUS_SITE}/data/{sym}.json", timeout=20))
                reused += 1
            except Exception:
                enc = None
        if not enc:
            continue
        (DATA / f"{sym}.json").write_text(json.dumps(enc, separators=(",", ":")))
        if sym in pop:
            symbols.append([sym, pop[sym], "P"])
        else:
            name, etf = listed[sym]
            symbols.append([sym, name, "E" if etf else "S"])
    (DATA / "symbols.json").write_text(json.dumps(symbols, separators=(",", ":")))
    print(f"Wrote {len(symbols)} symbols ({reused} reused from the live site)")


if __name__ == "__main__":
    main()
