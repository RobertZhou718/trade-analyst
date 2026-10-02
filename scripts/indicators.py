#!/usr/bin/env python3
"""Compute a technical snapshot from an OHLCV CSV.

Usage:
  python indicators.py data/AAPL.csv [--bench data/SPY.csv] [--chart-bars 120] > data/AAPL.ta.json

The CSV needs Date + Open/High/Low/Close (+ Volume, optional). Column names are
matched case-insensitively, so exports from brokers, TradingView, Yahoo or a
hand-built CSV from the browser fallback all work.

Output JSON = numbers + plain-language signal tags. The tags are hints, not
verdicts: the model using the skill weighs them against the trader's style.
"""
import argparse, json, sys
import numpy as np
import pandas as pd

def load(path):
    df = pd.read_csv(path)
    cols = {c.lower().strip(): c for c in df.columns}
    def pick(*names):
        for n in names:
            if n in cols:
                return cols[n]
        return None
    m = {"Date": pick("date", "datetime", "time", "timestamp"),
         "Open": pick("open"), "High": pick("high"), "Low": pick("low"),
         "Close": pick("close", "adj close", "price"), "Volume": pick("volume", "vol")}
    if not all(m[k] for k in ["Date", "Open", "High", "Low", "Close"]):
        sys.exit(f"CSV missing columns; found {list(df.columns)}")
    out = pd.DataFrame({k: df[v] for k, v in m.items() if v})
    out["Date"] = pd.to_datetime(out["Date"], utc=True, errors="coerce")
    out = out.dropna(subset=["Date", "Close"]).sort_values("Date").set_index("Date")
    for c in ["Open", "High", "Low", "Close", "Volume"]:
        if c in out:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out

def ema(s, n): return s.ewm(span=n, adjust=False).mean()

def rsi(c, n=14):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1/n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1/n, adjust=False).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)

def atr(df, n=14):
    pc = df["Close"].shift()
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - pc).abs(), (df["Low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/n, adjust=False).mean()

def adx(df, n=14):
    up = df["High"].diff(); dn = -df["Low"].diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    ndm = np.where((dn > up) & (dn > 0), dn, 0.0)
    a = atr(df, n)
    pdi = 100 * pd.Series(pdm, index=df.index).ewm(alpha=1/n, adjust=False).mean() / a
    ndi = 100 * pd.Series(ndm, index=df.index).ewm(alpha=1/n, adjust=False).mean() / a
    dx = 100 * (pdi - ndi).abs() / (pdi + ndi).replace(0, np.nan)
    return dx.ewm(alpha=1/n, adjust=False).mean(), pdi, ndi

def pivots(df, w=5, lookback=250):
    """Swing highs/lows -> clustered support/resistance levels."""
    d = df.tail(lookback)
    hi, lo = d["High"].values, d["Low"].values
    lv = []
    for i in range(w, len(d) - w):
        if hi[i] == hi[i-w:i+w+1].max(): lv.append(hi[i])
        if lo[i] == lo[i-w:i+w+1].min(): lv.append(lo[i])
    if not lv: return []
    lv = sorted(lv)
    tol = float(atr(df).iloc[-1]) * 0.6
    clusters = [[lv[0]]]
    for x in lv[1:]:
        if x - clusters[-1][-1] <= tol: clusters[-1].append(x)
        else: clusters.append([x])
    return sorted([(float(np.mean(c)), len(c)) for c in clusters], key=lambda t: t[0])

def r(x, n=2):
    try:
        return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)
    except Exception:
        return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--bench", help="benchmark CSV for relative strength (SPY, XIU.TO, BTC-USD...)")
    ap.add_argument("--chart-bars", type=int, default=120)
    a = ap.parse_args()
    df = load(a.csv)
    if len(df) < 30:
        sys.exit("Need at least 30 bars for meaningful indicators")
    c = df["Close"]
    last = float(c.iloc[-1])

    sma = {n: c.rolling(n).mean() for n in (20, 50, 200)}
    e12, e26 = ema(c, 12), ema(c, 26)
    macd = e12 - e26; sig = ema(macd, 9); hist = macd - sig
    rs = rsi(c)
    at = atr(df)
    adx_, pdi, ndi = adx(df)
    bb_mid = c.rolling(20).mean(); bb_sd = c.rolling(20).std()
    bb_up, bb_lo = bb_mid + 2 * bb_sd, bb_mid - 2 * bb_sd
    bb_width = (bb_up - bb_lo) / bb_mid
    vol = df.get("Volume")

    tags = []
    s20, s50, s200 = (float(sma[n].iloc[-1]) if not np.isnan(sma[n].iloc[-1]) else None for n in (20, 50, 200))
    if s50 and s200:
        if last > s50 > s200: tags.append("uptrend: price > SMA50 > SMA200")
        elif last < s50 < s200: tags.append("downtrend: price < SMA50 < SMA200")
        else: tags.append("mixed trend / transition")
        cross = np.sign(sma[50] - sma[200]).diff().tail(20)
        if (cross > 0).any(): tags.append("golden cross within last 20 bars")
        if (cross < 0).any(): tags.append("death cross within last 20 bars")
    rv = float(rs.iloc[-1])
    if rv >= 70: tags.append(f"RSI overbought ({rv:.0f})")
    elif rv <= 30: tags.append(f"RSI oversold ({rv:.0f})")
    if hist.iloc[-1] > 0 and hist.iloc[-2] <= 0: tags.append("MACD bullish cross (latest bar)")
    if hist.iloc[-1] < 0 and hist.iloc[-2] >= 0: tags.append("MACD bearish cross (latest bar)")
    # simple divergence check over last 30 bars
    w = 30
    if len(c) > w + 5:
        seg_c, seg_r = c.tail(w), rs.tail(w)
        if seg_c.iloc[-1] >= seg_c.max() * 0.995 and seg_r.iloc[-1] < seg_r.max() - 5:
            tags.append("possible bearish RSI divergence (new price high, weaker RSI)")
        if seg_c.iloc[-1] <= seg_c.min() * 1.005 and seg_r.iloc[-1] > seg_r.min() + 5:
            tags.append("possible bullish RSI divergence (new price low, stronger RSI)")
    ax = float(adx_.iloc[-1])
    tags.append(f"ADX {ax:.0f}: " + ("strong trend" if ax >= 25 else "weak/no trend (range-bound)"))
    bw_pct = float((bb_width.rank(pct=True)).iloc[-1])
    if bw_pct < 0.15: tags.append("Bollinger squeeze (volatility compressed, breakout risk)")
    if last > bb_up.iloc[-1]: tags.append("closed above upper Bollinger band")
    if last < bb_lo.iloc[-1]: tags.append("closed below lower Bollinger band")
    vol_ratio = None
    if vol is not None and vol.notna().sum() > 25 and vol.tail(20).mean() > 0:
        vol_ratio = float(vol.iloc[-1] / vol.tail(21).iloc[:-1].mean())
        if vol_ratio > 1.8: tags.append(f"volume spike {vol_ratio:.1f}x 20-bar avg")
        elif vol_ratio < 0.5: tags.append("very light volume")

    lv = pivots(df)
    supports = [{"price": r(p), "touches": n} for p, n in lv if p < last][-3:][::-1]
    resist = [{"price": r(p), "touches": n} for p, n in lv if p > last][:3]
    if not resist:
        tags.append("no overhead resistance in data (at/near highs) - use measured move / ATR multiples / round numbers for targets")
    if len(df) < 200:
        tags.append(f"only {len(df)} bars: SMA200/52w missing - fill from a quote page, don't leave blank")

    yr = df.tail(252)
    perf = {}
    for k, n in {"1w": 5, "1m": 21, "3m": 63, "6m": 126, "1y": 252}.items():
        if len(c) > n: perf[k] = r((last / c.iloc[-n-1] - 1) * 100, 1)
    rel = None
    if a.bench:
        b = load(a.bench)["Close"]
        j = pd.concat([c, b], axis=1, keys=["s", "b"]).dropna()
        rel = {k: r(((j.s.iloc[-1]/j.s.iloc[-n-1]) / (j.b.iloc[-1]/j.b.iloc[-n-1]) - 1) * 100, 1)
               for k, n in {"1m": 21, "3m": 63, "6m": 126}.items() if len(j) > n} or None

    daily_ret = c.pct_change().dropna()
    out = {
        "last_bar": str(df.index[-1]), "bars": len(df), "last_close": r(last, 4),
        "change_pct_last_bar": r((last / c.iloc[-2] - 1) * 100),
        "sma": {"20": r(s20), "50": r(s50), "200": r(s200)},
        "ema": {"12": r(e12.iloc[-1]), "26": r(e26.iloc[-1])},
        "rsi14": r(rv, 1),
        "macd": {"macd": r(macd.iloc[-1], 3), "signal": r(sig.iloc[-1], 3), "hist": r(hist.iloc[-1], 3)},
        "adx14": r(ax, 1), "di_plus": r(pdi.iloc[-1], 1), "di_minus": r(ndi.iloc[-1], 1),
        "atr14": r(at.iloc[-1], 4), "atr_pct": r(at.iloc[-1] / last * 100),
        "bollinger": {"upper": r(bb_up.iloc[-1]), "mid": r(bb_mid.iloc[-1]), "lower": r(bb_lo.iloc[-1]),
                      "width_percentile": r(bw_pct * 100, 0)},
        "volume_ratio_vs_20": r(vol_ratio),
        "range_52w": ({"high": r(yr["High"].max()), "low": r(yr["Low"].min()),
                      "pct_from_high": r((last / yr["High"].max() - 1) * 100, 1)} if len(df) >= 240 else
                      {"high": None, "low": None, "pct_from_high": None,
                       "note": f"only {len(df)} bars - take 52w range from a quote page"}),
        "realized_vol_annual_pct": r(daily_ret.tail(20).std() * np.sqrt(252) * 100, 1),
        "performance_pct": perf, "relative_strength_vs_bench_pct": rel,
        "supports": supports, "resistances": resist,
        "signals": tags,
        "chart": {
            "dates": [str(d.date()) if hasattr(d, "date") else str(d) for d in df.index[-a.chart_bars:]],
            "ohlc": [[r(o, 4), r(h, 4), r(l, 4), r(cl, 4)] for o, h, l, cl in
                     df[["Open", "High", "Low", "Close"]].tail(a.chart_bars).values],
            "sma20": [r(x, 4) for x in sma[20].tail(a.chart_bars)],
            "sma50": [r(x, 4) for x in sma[50].tail(a.chart_bars)],
            "sma200": [r(x, 4) for x in sma[200].tail(a.chart_bars)],
        },
    }
    print(json.dumps(out, indent=1))

if __name__ == "__main__":
    main()
