# Torn City Stock Pricing Mechanics: Per-Minute Noise ("Fuzz") and Underlying Trend

Research note scope: the post-April-2021 "Stocks 3.0" market. Access caveat: torn.com/forums.php and wiki.torn.com both returned HTTP 403 to direct fetches, so findings from those pages come from search-engine snippets and summaries of them, not from reading the full pages. Treat exact wording as approximate. Tornsy.com's page also came back with no usable content.

## 1. Update cadence and price precision

### Takeaway
Since Stocks 3.0 (6 April 2021), prices update every minute instead of every 15 minutes. Chedburn's announcement and the official wiki both confirm this. Every community tracker samples once a minute. I found no authoritative statement on decimal precision.

### Cited Findings
- Developer-confirmed (Chedburn announcement, quoted on the wiki and in forums): "Price movements are now every minute (instead of every 15 minutes)". The same text says prices are based on real-world stocks in the same industries as Torn's. — [Torn Wiki: Stock Market](https://wiki.torn.com/wiki/Stock_Market); [Forum: Guide to Stocks 3.0](https://www.torn.com/forums.php?p=threads&f=61&t=16220358&b=0&a=0&start=0&to=21410794)
- Stocks 3.0 went live on 6 April 2021. Before that date shares could be traded between players, and the update ended that. — [Torn Wiki: Trade](https://wiki.torn.com/wiki/Trade)
- Under 3.0, buying and selling happen instantly against the exchange at the current price. A guide records a 0.1% fee on all sales from 20 April 2021. — [Forum: Guide to Stocks 3.0](https://www.torn.com/forums.php?p=threads&f=61&t=16220358&b=0&a=0&start=0&to=21410794); [Torn Wiki: Stock Market](https://wiki.torn.com/wiki/Stock_Market)
- The API gained 'torn' -> 'stocks' and 'user' -> 'stocks' selections for the new market. — [Torn Wiki: Stock](https://wiki.torn.com/wiki/Stock)
- Third-party tools sample at 1 minute. Kokomo Exchange: "Prices are recorded from the Torn API every minute, with older history from tornsy.com". It lists 35 stocks and offers chart timeframes from 1 minute to 1 year. — [Kokomo Exchange](https://kokomo-data.kokomoexchange.workers.dev/)
- TornCharts advertises "real-time data updated every minute". — [TornCharts](https://torncharts.com/)
- The Torn Stock Advisor userscript polls every 60 seconds and uses Tornsy hourly candles, which it refreshes every 10 minutes. — [Greasy Fork: Torn Stock Advisor](https://greasyfork.org/en/scripts/569769-torn-stock-advisor)
- A community script's sample API record shows `"current_price": 11418.811`, which has three decimals, next to fields `market_cap`, `total_shares`, `available_shares`, `forecast`, `demand` and `benefit`. This is a third-party script, and the record may come from an older API version. — [Greasy Fork: StockX code](https://greasyfork.org/en/scripts/445393-stockx/code)
- Tornsy has URL-addressed timeframes such as `/tcse/m30`, `/tcse/h2`, `/tcse/h6` and `/tcse/y1`, and shows the TCSE index to 2 decimals (e.g. "TCSE 16,435.90"). — [Tornsy](https://tornsy.com/); [Tornsy TCSE m30](https://tornsy.com/tcse/m30)

### Inferences
- "Every minute" most likely means one server tick per minute. Whether that tick falls exactly on the minute boundary was not stated anywhere I could reach. Pollers at 60 s that are not phase-locked to the tick will sometimes double-sample or skip a tick.
- Prices may be stored internally with more than 2 decimals (the 11418.811 sample) while the in-game UI rounds them. Check against current raw API output before assuming 2-decimal granularity.

### Gaps
- No official statement on decimal precision or exact tick alignment (the seconds offset), and the current v2 API schema could not be fetched.
- No confirmation of whether `forecast` and `demand` are still returned by the current API or are legacy fields.

## 2. Deliberate per-minute random noise and mean reversion

### Takeaway
I found no developer statement that describes a "fuzz" or noise term explicitly. The strongest evidence that the engine produces short-horizon mean-reverting jitter is the November 2023 "Stock Market - Volatility Update". In it, staff said they had been monitoring "very short-term rebounding" of prices and changed the engine to reduce it. Short-term swings were to be dampened while direction and mid- and long-term trends were kept. That points to an oscillating noise component layered on a separate trend process.

### Cited Findings
- Developer-confirmed (Torn staff announcement, November 2023, Stock Market forum, around 803 replies). From search summaries of the post, not a full read:
  - The change would reduce "very short-term rebounding" of stock prices, which staff had been monitoring on the engine.
  - It works in both directions: a spike would no longer "rebound" back as easily.
  - Short-term swings would be dampened, but the direction of moves would stay the same.
  - Volatility would come back over a few days.
  - Mid- and long-term trends should be "mostly unaffected".
  - The TCSE had drifted about $60 above the sum of all stock prices, and the update also corrected that.
  - Sources: [Forum: Stock Market - Volatility Update](https://www.torn.com/forums.php?p=threads&t=16341610) (403 on direct fetch; content via search snippets)
- Community opinion: a 2023 forum thread says movement is "limited and so small it's almost invisible". Another player in the same thread says active trading can beat bank interest. — [Forum: Stock market (2023)](https://www.torn.com/forums.php?p=threads&f=2&t=16374371&b=0&a=0)
- Kokomo Exchange markets itself on spotting "potential 1–2% moves", which suggests short swings of that size are tradeable. It does not describe its method. — [Kokomo Exchange](https://kokomo-data.kokomoexchange.workers.dev/)

### Inferences
- **Speculation.** Before November 2023, the "rebounding" pattern (a move followed by a quick reversal) fits a noise term that does not accumulate, or is negatively autocorrelated. One example would be price = hidden trend + i.i.d. jitter each minute, which shows up as negative lag-1 autocorrelation in 1-minute returns. Another would be a strongly mean-reverting process such as Ornstein-Uhlenbeck around a hidden "true" price. The fix kept the direction of moves and dampened the reversals, which is consistent with lowering the jitter amplitude or lowering the reversion strength.
- **Speculation.** The $60 gap between TCSE and the summed prices could come from rounding or noise being applied to each displayed price separately from the index calculation. That would fit per-stock jitter on the displayed price that the index did not include. Staff gave no cause.
- "Volatility would come back over a few days" suggests volatility is itself a slowly adapting state, perhaps rolling or EWMA-driven, rather than a fixed constant.
- A practical test: the variance of k-minute returns grows like k for a random walk. If it stays roughly flat at short lags (a variance ratio below 1), that indicates additive noise. Compare windows before and after November 2023.

### Gaps
- No source gave the jitter's magnitude (absolute cents versus a percentage), its distribution, or an explicit formula. The full text and any staff replies in the November 2023 thread could not be read because of the 403.
- No community statistical analysis of 1-minute return autocorrelation was found.

## 3. Drivers of genuine price movement (trends, forecast, demand, benefit blocks, staff statements)

### Takeaway
Developer-confirmed: since 3.0, prices are loosely linked to real-world stocks in the same industries. The wiki says prices are expected to rise about 10% per year on average, with no guarantee, and some stocks are very volatile. The older pre-2021 system ran on internal algorithms with cyclical, fairly predictable ranges. The legacy `forecast` and `demand` fields come from that era. Players widely regard the current engine as opaque.

### Cited Findings
- Developer-confirmed: prices are "based on real-world stocks in the same industries as Torn's". — [Torn Wiki: Stock Market](https://wiki.torn.com/wiki/Stock_Market)
- The wiki says stock prices are expected to increase by an average of about 10% per year, with no guarantees. Some stocks can be "incredibly volatile", doubling within a month or crashing significantly. — [Torn Wiki: Stock Market](https://wiki.torn.com/wiki/Stock_Market) (via search snippets)
- Community analysis from 2021 (Andyman): 3.0 favours investing over trading. The old system was different in that stocks "moved cyclically within fairly predictable ranges". — [Forum: Preliminary Andyman Analysis - Stocks 3.0](https://www.torn.com/forums.php?p=threads&f=2&t=16220141&b=0&a=0)
- Community opinion (technical analysis thread):
  - Before 3.0, prices were driven by internal algorithms. From 3.0 onward they track real-life stocks "to some degree".
  - "Nobody knows the code". The only observed pattern is that all stocks combined seem to move only upward, so classic technical analysis does not work.
  - One post says Torn stock trends "are not real" and forecasting is not possible.
  - Source: [Forum: Technical analysis](https://www.torn.com/forums.php?p=threads&f=11&t=16300787&b=0&a=0)
- Legacy fields: a third-party script's stock records include `forecast` and `demand` next to `benefit`. A third-party tracker still lists an "investment forecast" alert, which suggests a forecast figure existed at some point. — [Greasy Fork: StockX code](https://greasyfork.org/en/scripts/445393-stockx/code); [Forum: THT - Torn Helper & Tracker](https://www.torn.com/forums.php?p=threads&f=67&t=16177400&b=0&a=0)
- Benefit blocks: community tools rank stocks by benefit-block ROI, profit per day and next block cost. They treat blocks as the main reason to invest, separate from price swings. — [Greasy Fork: Torn Stock Analyzer](https://greasyfork.org/scripts/570460-torn-stock-analyzer)
- 2022 community report (Torn City Newspaper blog):
  - Price data goes back to 6 April 2021.
  - The author measured from 30 July 2021, once two new stocks had settled.
  - Only 7 of 32 companies were below their July 2021 price, and the average change was +6.62%.
  - Source: [Torn City Newspaper: 2022 Stock Market Report](https://torncitynewspaper.blogspot.com/2022/05/2022-stock-market-report.html)
- An older newspaper post (2018, pre-3.0) says the in-game market has "tweaks and alterations that suit Torn life" and that there is no data to predict prices. — [Torn City Newspaper: 2018](https://torncitynewspaper.blogspot.com/2018/01/panic-as-stock-market-goes-crazy.html)

### Inferences
- **Speculation.** A plausible generative model is: a slow drift per stock (positive on average, about 10% a year), plus regime-like trends (possibly loosely tied to a real-world industry proxy), plus short-horizon jitter. The jitter's rebound behaviour was dampened in November 2023.
- No evidence was found that player trading volume, investor counts or total shares move prices under 3.0. Trades execute instantly against the exchange at the current price, which suggests prices are exogenous to player orders. This is unconfirmed.

### Gaps
- No developer description of how the "real-world" link works: which tickers, what lag, or what scaling.
- Unclear whether `forecast` and `demand` still mean anything after 3.0.
- No evidence either way on whether investor count or market cap feeds into prices.

## 4. Community tool analyses (Tornsy, TornStats, YATA, trackers, Reddit)

### Takeaway
Community tools (Tornsy, TornCharts, Kokomo Exchange, Torn Stock Advisor and Analyzer userscripts, the TornCity-Stock-Tool Android app) collect 1-minute or hourly data and apply standard technical indicators. None of the ones I could reach publish a noise-structure analysis, a cross-stock correlation study or a "true trend" extraction method.

### Cited Findings
- Tornsy offers stock charts. Its forum thread said hourly candles were offered first and longer intervals waited until enough data had built up (about two months of data at that point). It is the de facto historical data source for other tools. — [Forum: [Site] Tornsy.com](https://www.torn.com/forums.php?p=threads&f=67&t=16230392&b=0&a=0); [Kokomo Exchange](https://kokomo-data.kokomoexchange.workers.dev/)
- Kokomo Exchange uses RSI, MACD, Stoch RSI, ADX, trend lines and Fibonacci levels. It discloses no signal method and gives no analysis of noise, cycles or correlation. — [Kokomo Exchange](https://kokomo-data.kokomoexchange.workers.dev/)
- Torn Stock Advisor uses RSI, SMA7/SMA20 and weekly and monthly trends on Tornsy hourly candles. It says nothing about filtering noise. — [Greasy Fork: Torn Stock Advisor](https://greasyfork.org/en/scripts/569769-torn-stock-advisor)
- Torn Stock Analyzer scores 35 stocks using 19 price intervals from Tornsy and splits holdings into swing-trade and benefit-block groups. — [Greasy Fork: Torn Stock Analyzer](https://greasyfork.org/scripts/570460-torn-stock-analyzer)
- The TornCity Stock Tool Android app queries the API periodically for price triggers. — [GitHub: ashwingur/TornCity-Stock-Tool](https://github.com/ashwingur/TornCity-Stock-Tool)
- Torn Profit Checker has a stock checker page. — [Torn Profit Checker: Stocks](https://www.tornprofitchecker.com/stocks/)

### Inferences
- Most tools use hourly candles, which would average away much of the per-minute jitter. That may explain why no one has published a minute-level noise analysis.

### Gaps
- Searches turned up nothing relevant from Reddit r/torncity, YATA or TornStats on stock noise.
- Found no published study of whether per-minute moves are shared across stocks or independent per stock.

## 5. Daily or hourly cycles, resets, and synchronised events across stocks

### Takeaway
No source documents daily or hourly cycles or market-wide synchronised resets. The only synchronised, market-wide event confirmed is the November 2023 engine change itself, which dampened volatility on all stocks at once. Volatility then returned over several days.

### Cited Findings
- November 2023 engine change: applied market-wide, with volatility "returning over a few days" and a TCSE/sum-of-prices discrepancy of about $60 corrected. — [Forum: Stock Market - Volatility Update](https://www.torn.com/forums.php?p=threads&t=16341610)
- TCSE is an index showing the total value of all stocks. It cannot usefully be invested in. — [Forum: Mat's stock "guide"](https://www.torn.com/forums.php?p=threads&f=61&t=15930753&b=0&a=0rh%3D78)
- Community observation: all stocks combined "seem to only move upward". — [Forum: Technical analysis](https://www.torn.com/forums.php?p=threads&f=11&t=16300787&b=0&a=0)

### Inferences
- **Speculation.** If jitter were a single shared random draw applied to all stocks, the sum of prices (TCSE) would be about as noisy as the individual stocks. If draws were independent per stock, the index would be much smoother. Data could test this directly: compare the index's 1-minute return variance with the variance expected from a weighted sum of independent returns, or look at the cross-sectional correlation of 1-minute residuals.
- The TCSE/sum gap might have built up from per-stock noise or rounding that the index did not account for. That would be mild evidence for per-stock rather than shared noise, but it is unconfirmed.
- Torn has daily server events at 00:00 TCT (UTC). Whether stock prices show any discontinuity at that time is untested. No source found.

### Gaps
- No evidence on intraday or daily seasonality, on behaviour around TCT midnight, or on cross-stock correlation of minute-level moves. All of these are open questions that need direct empirical analysis of 1-minute data, for example from the project's own collected history or Tornsy.
