#!/usr/bin/env python3
"""Render an analysis JSON into a self-contained HTML dashboard.

Usage:
  python build_dashboard.py analysis.json -o trade-AAPL.html            # fragment for the Artifact tool
  python build_dashboard.py analysis.json -o trade-AAPL.html --standalone  # full HTML document

No external scripts or fonts; the chart is inline SVG. Light + dark themes via
CSS tokens. Input schema: SKILL.md section 5.
"""
import argparse, json, html, math

L = {
 "zh": dict(verdict="结论", conf="置信度", horizon="周期", plan="交易计划", entry="入场区间", stop="止损",
            targets="目标位", rr="盈亏比", size="仓位建议", invalid="失效条件", scores="多因子评分",
            tech="技术面", news="新闻与事件", macro="宏观 / 政策 / 政治", cat="未来催化剂", bull="看多理由",
            bear="看空理由", fit="与你交易风格的匹配", src="数据来源", asof="数据时间", quality="数据质量",
            perf="区间涨跌", levels="关键价位", sup="支撑", res="阻力", disc="免责声明",
            dq={"live": "实时/近实时", "delayed": "延迟行情", "approx": "网页搜索近似值"}),
 "en": dict(verdict="Verdict", conf="Confidence", horizon="Horizon", plan="Trade plan", entry="Entry zone", stop="Stop",
            targets="Targets", rr="Reward:Risk", size="Position size", invalid="Invalidation", scores="Factor scorecard",
            tech="Technicals", news="News & events", macro="Macro / policy / politics", cat="Upcoming catalysts",
            bull="Bull case", bear="Bear case", fit="Fit with your trading style", src="Source", asof="As of",
            quality="Data quality", perf="Performance", levels="Key levels", sup="Support", res="Resistance",
            disc="Disclaimer", dq={"live": "live / near-live", "delayed": "delayed", "approx": "approx. from web search"}),
}

def e(x): return html.escape("" if x is None else str(x))

def fmt(x, d=2):
    if x is None: return "—"
    if isinstance(x, (int, float)):
        if abs(x) >= 1000: return f"{x:,.{0 if abs(x) >= 100000 else d}f}"
        return f"{x:.{d}f}" if abs(x) >= 1 else f"{x:.4g}"
    return e(x)

def action_class(a):
    a = (a or "").lower()
    if any(k in a for k in ["买", "加仓", "buy", "add", "long"]): return "pos"
    if any(k in a for k in ["卖", "减仓", "清仓", "sell", "trim", "short", "exit"]): return "neg"
    return "neu"

def svg_chart(ch, sup, res, stop=None, targets=None):
    ohlc = [x for x in ch.get("ohlc", []) if x and None not in x]
    if len(ohlc) < 5: return ""
    n = len(ohlc); W, H, pl, pr, pt, pb = 760, 300, 8, 56, 10, 22
    lines = [ch.get(k) or [] for k in ("sma20", "sma50", "sma200")]
    extra = [s.get("price") for s in sup + res if s.get("price")] + ([stop] if isinstance(stop, (int, float)) else []) \
            + [t for t in (targets or []) if isinstance(t, (int, float))]
    mav = [v for ln in lines for v in ln[-n:] if v is not None]
    lo = min([x[2] for x in ohlc] + extra + mav); hi = max([x[1] for x in ohlc] + extra + mav)
    pad = (hi - lo) * 0.04; lo -= pad; hi += pad
    y = lambda p: pt + (hi - p) / (hi - lo) * (H - pt - pb)
    cw = (W - pl - pr) / n; x = lambda i: pl + cw * (i + 0.5)
    g = []
    for k in range(5):
        p = lo + (hi - lo) * k / 4
        g.append(f'<line x1="{pl}" x2="{W-pr}" y1="{y(p):.1f}" y2="{y(p):.1f}" class="grid"/>'
                 f'<text x="{W-pr+4}" y="{y(p)+4:.1f}" class="ax">{fmt(p)}</text>')
    used = []
    def hline(p, cls, label):
        lx = pl + 4
        while any(abs(y(p) - uy) < 11 and abs(lx - ux) < 80 for ux, uy in used): lx += 84
        used.append((lx, y(p)))
        return (f'<line x1="{pl}" x2="{W-pr}" y1="{y(p):.1f}" y2="{y(p):.1f}" class="{cls}"/>'
                f'<text x="{lx}" y="{y(p)-3:.1f}" class="lbl {cls}t">{e(label)} {fmt(p)}</text>')
    for s in sup: g.append(hline(s["price"], "sup", "S"))
    for s in res: g.append(hline(s["price"], "res", "R"))
    if isinstance(stop, (int, float)): g.append(hline(stop, "stp", "Stop"))
    for t in (targets or []):
        if isinstance(t, (int, float)): g.append(hline(t, "tgt", "T"))
    bw = max(1.0, cw * 0.62)
    for i, (o, h, l, c) in enumerate(ohlc):
        cls = "up" if c >= o else "dn"
        g.append(f'<line x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{y(h):.1f}" y2="{y(l):.1f}" class="wick {cls}"/>'
                 f'<rect x="{x(i)-bw/2:.1f}" y="{y(max(o,c)):.1f}" width="{bw:.1f}" height="{max(1,abs(y(o)-y(c))):.1f}" class="{cls}"/>')
    for vals, cls in zip(lines, ("m20", "m50", "m200")):
        vals = vals[-n:]
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals) if v is not None)
        if pts: g.append(f'<polyline points="{pts}" class="ma {cls}"/>')
    d = ch.get("dates", [])[-n:]
    for i, anc in ((0, "start"), (n // 2, "middle"), (n - 1, "end")):
        if i < len(d): g.append(f'<text x="{x(i):.1f}" y="{H-6}" class="ax" text-anchor="{anc}">{e(d[i])}</text>')
    legend = ('<div class="legend"><span class="k m20"></span>SMA20<span class="k m50"></span>SMA50'
              '<span class="k m200"></span>SMA200</div>')
    return f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="price chart">{"".join(g)}</svg>{legend}'

CSS = """
:root{--bg:#f7f7f5;--card:#fff;--ink:#1b1d21;--mute:#6b7078;--line:#e4e4e0;--pos:#1a7f4b;--neg:#c2352b;--neu:#8a6d1c;
--posbg:#e6f4ec;--negbg:#fbeae8;--neubg:#f7f0dc;--m20:#2f6fdf;--m50:#d08a12;--m200:#8a4fd0;--accent:#2f6fdf}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#121316;--card:#1b1d22;--ink:#e8e9ec;--mute:#9aa0aa;
--line:#2c2f36;--pos:#4cc38a;--neg:#ff6b5e;--neu:#e0b84f;--posbg:#16301f;--negbg:#3a1a17;--neubg:#33290f;--m20:#6aa0ff;--m50:#f0aa3a;--m200:#b48cff}}
:root[data-theme="dark"]{--bg:#121316;--card:#1b1d22;--ink:#e8e9ec;--mute:#9aa0aa;--line:#2c2f36;--pos:#4cc38a;--neg:#ff6b5e;
--neu:#e0b84f;--posbg:#16301f;--negbg:#3a1a17;--neubg:#33290f;--m20:#6aa0ff;--m50:#f0aa3a;--m200:#b48cff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:20px 16px 40px}
header{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 16px;margin-bottom:14px}
h1{font-size:26px;margin:0}.sub{color:var(--mute);font-size:13px}.px{font-size:26px;font-weight:650;font-variant-numeric:tabular-nums}
.chg.pos{color:var(--pos)}.chg.neg{color:var(--neg)}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;min-width:0}
.card h2{font-size:13px;letter-spacing:.04em;text-transform:uppercase;color:var(--mute);margin:0 0 10px}
.hero{display:flex;flex-wrap:wrap;gap:16px;align-items:center;margin-bottom:14px}
.badge{font-size:22px;font-weight:700;padding:8px 18px;border-radius:10px}
.badge.pos{background:var(--posbg);color:var(--pos)}.badge.neg{background:var(--negbg);color:var(--neg)}.badge.neu{background:var(--neubg);color:var(--neu)}
.meta{display:flex;gap:18px;flex-wrap:wrap;color:var(--mute);font-size:13px}.meta b{color:var(--ink);font-weight:600}
.summary{flex:1 1 320px;margin:0}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}td,th{padding:6px 4px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
th{color:var(--mute);font-weight:500;font-size:13px;width:38%}
.bar{position:relative;height:8px;background:var(--line);border-radius:4px;min-width:90px}
.bar i{position:absolute;top:0;bottom:0;border-radius:4px}.bar .c{position:absolute;left:50%;top:-2px;bottom:-2px;width:1px;background:var(--mute)}
.sc{font-weight:650;width:34px;text-align:right}.pos{color:var(--pos)}.neg{color:var(--neg)}.neu{color:var(--mute)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:10px}
.tile{border:1px solid var(--line);border-radius:10px;padding:10px}.tile .v{font-size:18px;font-weight:650;font-variant-numeric:tabular-nums}.tile .k{font-size:12px;color:var(--mute)}
.chart{width:100%;height:auto;display:block}.chart .grid{stroke:var(--line)}.chart .ax{fill:var(--mute);font-size:11px}
.chart .up{fill:var(--pos);stroke:var(--pos)}.chart .dn{fill:var(--neg);stroke:var(--neg)}.chart .wick{stroke-width:1}
.chart .ma{fill:none;stroke-width:1.6}.chart .m20{stroke:var(--m20)}.chart .m50{stroke:var(--m50)}.chart .m200{stroke:var(--m200)}
.chart .sup{stroke:var(--pos);stroke-dasharray:4 4;opacity:.7}.chart .res{stroke:var(--neg);stroke-dasharray:4 4;opacity:.7}
.chart .stp{stroke:var(--neg);stroke-width:1.5}.chart .tgt{stroke:var(--accent);stroke-dasharray:6 3}
.chart .lbl{font-size:10px}.chart .supt{fill:var(--pos)}.chart .rest,.chart .stpt{fill:var(--neg)}.chart .tgtt{fill:var(--accent)}
.legend{display:flex;gap:6px 14px;align-items:center;font-size:12px;color:var(--mute);flex-wrap:wrap;margin-top:4px}
.legend .k{display:inline-block;width:14px;height:3px;margin-right:4px;vertical-align:middle}
.legend .m20{background:var(--m20)}.legend .m50{background:var(--m50)}.legend .m200{background:var(--m200)}
ul{margin:0;padding-left:18px}li{margin:4px 0}.tag{display:inline-block;font-size:12px;padding:2px 8px;border-radius:999px;border:1px solid var(--line);margin:2px 4px 2px 0;color:var(--mute)}
.imp{font-weight:700;margin-right:6px}a{color:var(--accent)}
.full{grid-column:1/-1}.foot{color:var(--mute);font-size:12px;margin-top:18px}
.warn{background:var(--neubg);color:var(--neu);border-radius:8px;padding:8px 12px;font-size:13px;margin-bottom:12px}
"""

def score_rows(scores):
    out = []
    for s in scores:
        v = s.get("score", 0) or 0
        v = max(-2, min(2, v))
        w = abs(v) / 2 * 50
        left = 50 if v >= 0 else 50 - w
        col = "var(--pos)" if v > 0 else ("var(--neg)" if v < 0 else "var(--mute)")
        cls = "pos" if v > 0 else ("neg" if v < 0 else "neu")
        wt = f' <span class="sub">×{s["weight"]}</span>' if s.get("weight") is not None else ""
        out.append(f'<tr><th>{e(s.get("factor"))}{wt}</th><td><div class="bar"><span class="c"></span>'
                   f'<i style="left:{left}%;width:{w}%;background:{col}"></i></div>'
                   f'<div class="sub" style="margin-top:4px">{e(s.get("note"))}</div></td>'
                   f'<td class="sc {cls}">{v:+g}</td></tr>')
    return "".join(out)

def imp(x):
    x = str(x or "0")
    if x.startswith("+") or x in ("pos", "positive", "利好"): return '<span class="imp pos">▲</span>'
    if x.startswith("-") or x in ("neg", "negative", "利空"): return '<span class="imp neg">▼</span>'
    return '<span class="imp neu">●</span>'

def build(a):
    t = L.get(a.get("lang", "zh"), L["zh"])
    ta = a.get("technical") or {}
    pr = a.get("price") or {}
    last = pr.get("last", ta.get("last_close")); chg = pr.get("change_pct", ta.get("change_pct_last_bar"))
    v = a.get("verdict") or {}; p = a.get("plan") or {}
    dq = a.get("data_quality", "live")
    parts = [f'<title>{e(a.get("symbol"))} 交易分析</title>' if a.get("lang", "zh") == "zh"
             else f'<title>{e(a.get("symbol"))} Trade Analysis</title>', f"<style>{CSS}</style><div class='wrap'>"]
    parts.append(f'<header><h1>{e(a.get("symbol"))}</h1><span class="sub">{e(a.get("name"))} · {e(a.get("market"))} · {e(a.get("currency"))}</span>'
                 f'<span class="px">{fmt(last)}</span>'
                 + (f'<span class="chg {"pos" if (chg or 0) >= 0 else "neg"}">{chg:+.2f}%</span>' if isinstance(chg, (int, float)) else "")
                 + '</header>')
    parts.append(f'<div class="meta" style="margin-bottom:12px"><span>{t["asof"]}: <b>{e(a.get("as_of"))}</b></span>'
                 f'<span>{t["src"]}: <b>{e(a.get("data_source"))}</b></span><span>{t["quality"]}: <b>{e(t["dq"].get(dq, dq))}</b></span></div>')
    if dq != "live" or a.get("data_warning"):
        parts.append(f'<div class="warn">{e(a.get("data_warning") or t["dq"].get(dq, dq))}</div>')
    parts.append(f'<div class="card hero"><span class="badge {action_class(v.get("action"))}">{e(v.get("action"))}</span>'
                 f'<div class="meta"><span>{t["conf"]}: <b>{e(v.get("confidence"))}</b></span><span>{t["horizon"]}: <b>{e(v.get("horizon"))}</b></span></div>'
                 f'<p class="summary">{e(v.get("summary"))}</p></div>')
    parts.append('<div class="grid2">')
    # plan
    tg = p.get("targets") or []
    rows = [(t["entry"], p.get("entry")), (t["stop"], p.get("stop")),
            (t["targets"], " / ".join(fmt(x) for x in tg) if tg else None), (t["rr"], p.get("risk_reward")),
            (t["size"], p.get("position_size")), (t["invalid"], p.get("invalidation"))]
    parts.append(f'<div class="card"><h2>{t["plan"]}</h2><table>' +
                 "".join(f"<tr><th>{k}</th><td>{fmt(val) if isinstance(val,(int,float)) else e(val) if val else '—'}</td></tr>" for k, val in rows) +
                 "</table></div>")
    if a.get("scores"):
        parts.append(f'<div class="card"><h2>{t["scores"]}</h2><table>{score_rows(a["scores"])}</table></div>')
    # chart
    if ta.get("chart"):
        stop = p.get("stop") if isinstance(p.get("stop"), (int, float)) else None
        parts.append(f'<div class="card full"><h2>{t["tech"]}</h2>'
                     + svg_chart(ta["chart"], ta.get("supports", []), ta.get("resistances", []), stop,
                                 [x for x in tg if isinstance(x, (int, float))]) + '</div>')
    if ta:
        tiles = [("RSI14", ta.get("rsi14")), ("MACD hist", (ta.get("macd") or {}).get("hist")), ("ADX14", ta.get("adx14")),
                 ("ATR14", f'{fmt(ta.get("atr14"))} ({fmt(ta.get("atr_pct"))}%)'), ("SMA50", (ta.get("sma") or {}).get("50")),
                 ("SMA200", (ta.get("sma") or {}).get("200")), ("Vol ×20d", ta.get("volume_ratio_vs_20")),
                 ("52w high", f'{fmt((ta.get("range_52w") or {}).get("high"))} ({fmt((ta.get("range_52w") or {}).get("pct_from_high"),1)}%)')]
        perf = ta.get("performance_pct") or {}
        parts.append(f'<div class="card full"><div class="tiles">' +
                     "".join(f'<div class="tile"><div class="k">{k}</div><div class="v">{fmt(val) if not isinstance(val,str) else e(val)}</div></div>' for k, val in tiles) +
                     "</div>" + (f'<div style="margin-top:10px">{"".join(f"<span class=tag>{e(k)} {val:+.1f}%</span>" for k,val in perf.items() if val is not None)}</div>' if perf else "") +
                     (f'<div style="margin-top:6px">{"".join(f"<span class=tag>{e(s)}</span>" for s in ta.get("signals", []))}</div>') + "</div>")
    def lst(title, items, render):
        if not items: return ""
        return f'<div class="card"><h2>{title}</h2><ul>' + "".join(f"<li>{render(i)}</li>" for i in items) + "</ul></div>"
    parts.append(lst(t["news"], a.get("news"), lambda n: imp(n.get("impact")) +
                     (f'<a href="{e(n.get("url"))}" target="_blank" rel="noopener">{e(n.get("title"))}</a>' if n.get("url") else e(n.get("title"))) +
                     f' <span class="sub">{e(n.get("source"))} {e(n.get("date"))}</span>' + (f'<div class="sub">{e(n.get("note"))}</div>' if n.get("note") else "")))
    parts.append(lst(t["macro"], a.get("macro"), lambda m: imp(m.get("impact")) + f'<b>{e(m.get("factor"))}</b> — {e(m.get("note"))}'))
    parts.append(lst(t["cat"], a.get("catalysts"), lambda c: f'<b>{e(c.get("date"))}</b> {e(c.get("event"))} <span class="sub">{e(c.get("note"))}</span>'))
    parts.append(lst(t["bull"], a.get("bull_case"), e))
    parts.append(lst(t["bear"], a.get("bear_case"), e))
    if a.get("profile_fit"):
        parts.append(f'<div class="card full"><h2>{t["fit"]}</h2><p style="margin:0">{e(a["profile_fit"])}</p></div>')
    parts.append("</div>")
    parts.append(f'<p class="foot">{t["disc"]}: {e(a.get("disclaimer") or ("本页为基于公开数据的分析与教育用途，不构成投资建议；市场有风险，决策与盈亏由你自行承担。" if a.get("lang","zh")=="zh" else "Analysis for informational purposes only, not investment advice."))}</p></div>')
    return "".join(parts)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("analysis"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--standalone", action="store_true")
    a = ap.parse_args()
    data = json.load(open(a.analysis, encoding="utf-8"))
    body = build(data)
    if a.standalone:
        body = ('<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                + body.replace("<style>", "</head><body><style>", 1) + "</body></html>")
    open(a.out, "w", encoding="utf-8").write(body)
    print(a.out)

if __name__ == "__main__":
    main()
