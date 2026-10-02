#!/usr/bin/env python3
"""Fetch OHLCV history + quote snapshot + recent headlines for one symbol.

Usage:
  python fetch_data.py AAPL --period 1y --interval 1d --out data/AAPL
  python fetch_data.py SHOP.TO            # TSX (use .TO; TSX Venture uses .V)
  python fetch_data.py BTC-USD            # crypto (Yahoo style)
  python fetch_data.py QQQ --interval 15m --period 5d   # intraday

Writes  <out>.csv  (Date,Open,High,Low,Close,Volume)
        <out>.meta.json  (quote snapshot, fundamentals, headlines, source, fetched_at)

Exit code 0 on success, 2 when every source failed (so the caller knows to fall
back to the browser / web search path described in SKILL.md).

Sources tried in order:
  1. yfinance (stocks, ETFs, TSX, crypto)  -> pip install yfinance
  2. Coinbase / Kraken public candles (crypto only, no key needed)
"""
import argparse, json, sys, os, datetime as dt

def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

def try_yfinance(sym, period, interval):
    try:
        import yfinance as yf
    except ImportError:
        os.system(f"{sys.executable} -m pip install -q yfinance --break-system-packages >/dev/null 2>&1 || "
                  f"{sys.executable} -m pip install -q yfinance >/dev/null 2>&1")
        import yfinance as yf
    t = yf.Ticker(sym)
    h = t.history(period=period, interval=interval, auto_adjust=False)
    if h is None or h.empty:
        raise RuntimeError("yfinance returned no rows")
    h = h[["Open", "High", "Low", "Close", "Volume"]].copy()
    h.index.name = "Date"
    meta = {"source": "yfinance", "symbol": sym}
    try:
        fi = t.fast_info
        meta["quote"] = {k: _safe(getattr(fi, k, None)) for k in
                         ["last_price", "previous_close", "open", "day_high", "day_low",
                          "year_high", "year_low", "market_cap", "currency", "exchange",
                          "fifty_day_average", "two_hundred_day_average", "last_volume",
                          "three_month_average_volume"]}
    except Exception as e:
        meta["quote_error"] = str(e)
    try:
        info = t.info or {}
        keep = ["shortName", "longName", "sector", "industry", "quoteType", "trailingPE", "forwardPE",
                "priceToBook", "pegRatio", "dividendYield", "beta", "shortPercentOfFloat",
                "targetMeanPrice", "recommendationKey", "numberOfAnalystOpinions",
                "earningsTimestamp", "exDividendDate", "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
                "preMarketPrice", "postMarketPrice", "regularMarketTime"]
        meta["info"] = {k: _safe(info.get(k)) for k in keep if info.get(k) is not None}
    except Exception as e:
        meta["info_error"] = str(e)
    try:
        cal = t.calendar
        if cal:
            meta["calendar"] = {k: _safe(v) for k, v in dict(cal).items()}
    except Exception:
        pass
    try:
        news = []
        for n in (t.news or [])[:12]:
            c = n.get("content", n)
            news.append({
                "title": c.get("title"),
                "publisher": (c.get("provider") or {}).get("displayName") if isinstance(c.get("provider"), dict) else c.get("publisher"),
                "time": c.get("pubDate") or c.get("providerPublishTime"),
                "url": ((c.get("canonicalUrl") or {}).get("url") if isinstance(c.get("canonicalUrl"), dict) else c.get("link")),
            })
        meta["news"] = news
    except Exception as e:
        meta["news_error"] = str(e)
    return h, meta

def try_crypto_public(sym, interval):
    """Coinbase Exchange candles; sym like BTC-USD."""
    import urllib.request, pandas as pd
    gran = {"1d": 86400, "1h": 3600, "15m": 900, "5m": 300}.get(interval, 86400)
    url = f"https://api.exchange.coinbase.com/products/{sym}/candles?granularity={gran}"
    req = urllib.request.Request(url, headers={"User-Agent": "trade-analyst/1.0"})
    rows = json.load(urllib.request.urlopen(req, timeout=15))
    if not rows:
        raise RuntimeError("coinbase empty")
    df = pd.DataFrame(rows, columns=["t", "Low", "High", "Open", "Close", "Volume"])
    df["Date"] = pd.to_datetime(df["t"], unit="s", utc=True)
    df = df.sort_values("Date").set_index("Date")[["Open", "High", "Low", "Close", "Volume"]]
    return df, {"source": "coinbase", "symbol": sym}

def _safe(v):
    try:
        json.dumps(v)
        return v
    except Exception:
        return str(v)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("symbol")
    ap.add_argument("--period", default="1y")
    ap.add_argument("--interval", default="1d")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    sym = a.symbol.upper()
    out = a.out or os.path.join("data", sym.replace("/", "_"))
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)

    errors = []
    attempts = [lambda: try_yfinance(sym, a.period, a.interval)]
    if "-USD" in sym or "-USDT" in sym or "-CAD" in sym:
        attempts.append(lambda: try_crypto_public(sym, a.interval))
    for f in attempts:
        try:
            df, meta = f()
            df.to_csv(out + ".csv")
            meta.update({"fetched_at_utc": _now(), "rows": len(df),
                         "first": str(df.index[0]), "last": str(df.index[-1]),
                         "interval": a.interval})
            json.dump(meta, open(out + ".meta.json", "w"), indent=2, default=str)
            print(json.dumps({"ok": True, "csv": out + ".csv", "meta": out + ".meta.json",
                              "source": meta["source"], "rows": len(df), "last_bar": str(df.index[-1]),
                              "last_close": float(df["Close"].iloc[-1])}))
            return
        except Exception as e:
            errors.append(f"{type(e).__name__}: {str(e)[:200]}")
    print(json.dumps({"ok": False, "errors": errors,
                      "hint": "Network blocked or symbol wrong. Use the browser / web-page / web-search tiers in SKILL.md."}))
    sys.exit(2)

if __name__ == "__main__":
    main()
