# Trader profile: questionnaire, defaults, storage, and how it shapes the analysis

Look for a saved profile first: memory file `/topics/trading-style.md` (if memory tools exist), else `trading_profile.json` in a connected folder or the working dir.

- **Found** → apply silently; mention it only in the dashboard's "fit" section.
- **Not found** → run the questionnaire below, save, then do the analysis. If the user clearly wants a quick answer now, analyse with stated defaults (swing, 1% risk, max position by risk tier below, no leverage) and ask the questionnaire at the end.
- "我现在偏长线了 / update my profile" → update storage, confirm in one line.
- Profile info stated in the message itself overrides the stored one for that request.

## Questionnaire (8 questions; AskUserQuestion tool if available — max 4 per call, so two calls; else numbered text so they can reply "1B 2A…")

1. 持仓周期 — 日内 · 短线波段(2天–3周) · 中线(1–6个月) · 长线(6个月+)
2. 单笔风险 — 保守 0.5% · 稳健 1% · 进取 2% · 激进 3%+（单笔最多亏组合的%）
3. 分析偏好 — 技术面为主 · 基本面为主 · 技术+基本面 · 消息/动量驱动
4. 品种(多选) — 美股 · 加股 TSX · ETF(含杠杆ETF?) · 加密货币
5. 单只最大仓位 — ≤5% · 5–10% · 10–20% · >20%
6. 看盘频率 — 全天 · 每天几次 · 只在收盘后 · 每周一次
7. 杠杆/做空/期权 — 都不用 · 偶尔做空或期权 · 常用保证金/杠杆
8. 主要目标 — 跑赢大盘 · 稳定现金流 · 高增长高风险 · 保值避险

Optional free text → `rules` (e.g. "不碰中概", "TFSA 账户").

**Defaults when a field is missing** (say which you assumed): horizon swing; risk 1%; max single position by risk tier — 0.5%→5%, 1%→10%, 2%→15%, 3%+→20% (crypto counts as one position); no leverage; technical+fundamental.

## Storage

1. Memory tool: `/topics/trading-style.md` (read first for the version token; frontmatter per the memory system; lines tagged `[stated]`). Store style facts only — horizon, risk %, caps, preferences, instruments, rules, watchlist tickers. **Never** store account balances, dollar P&L, or position dollar amounts.
2. Else `trading_profile.json` in a connected folder; else the working dir (tell the user it lasts this session only).

Never ask for portfolio dollar size — sizing is in % of portfolio.

## How the profile changes the analysis

| Field | Effect |
|---|---|
| intraday | `--interval 15m --period 5d` + daily context. Weights: technicals 50, flow/news 30, today's macro calendar 20. Stops 0.5–1× intraday ATR; VWAP, opening range, pre-market gaps. |
| swing | Daily 1y + weekly. Technicals 40, catalysts/news 25, macro/policy 20, fundamentals 15. Stops 1.5–2× ATR beyond structure. Earnings date inside window is mandatory to check. |
| position (months) | Daily + weekly 2y. Fundamentals/valuation 35, trend 25, macro/policy 25, news 15. Stops 2.5–3× ATR or below weekly structure; scale in. |
| long_term | Weekly 5y. Fundamentals/moat 50, secular macro 25, valuation timing 25. Entry zones + tranche/DCA rather than tight stops. |
| risk % | position % = risk % ÷ stop distance %, capped at max position. Show the arithmetic; if the cap binds, say so and state actual risk. |
| style | technical → lead with structure; fundamental → lead with business/valuation, technicals for timing; momentum/news → catalysts, relative strength, volume, time stops. |
| screen time after-close/weekly | Closing-basis stops ("收盘跌破X") + a resting catastrophe stop order; limit entries; no intraday setups. |
| no leverage | No shorts/options/leveraged ETFs; bearish = 减仓/卖出/观望. |
| leverage ok | May mention hedges (puts, inverse ETFs) with their risks (decay, margin calls). |
| cash-flow goal | Dividend yield, ex-div, payout sustainability, covered calls. |
| rules | Hard filters — flag conflicts before analysing. |
