"""
Glossary / guidebook for terms the bot uses, searchable by partial text the
same way the ticker autocomplete works. Served by /glossary.

Chart-signal entries are keyed by the column names in
tsl_core/analysis/swing.py (BULL_SIGNALS / BEAR_SIGNALS), so a definition
always describes exactly what the scoring code checks. Hit rates quoted are
from the full daily history (Apr 2021 - Nov 2026, 35 stocks): how often a
0.5% rise within 3 days followed, against a 28.4% base rate for any stock-day.

To add a term, append an entry to ENTRIES: key (unique, lowercase), title,
category (one of CATEGORIES), aliases (extra search words), body (plain
language, Discord markdown allowed, under ~900 characters) and related (keys).
"""
import difflib

CATEGORIES = ["Suggestions", "Chart signals", "Drop signs", "Indicators", "Other"]

# Hit rates and backtest figures quoted below were measured at this point;
# suggestion posts carry the live, daily-refreshed backtest
FIGURES_AS_OF = "Nov 2026"

ENTRIES = [
	# ── Suggestions ─────────────────────────────────────────────
	{
		"key": "upswing", "title": "Upswing", "category": "Suggestions",
		"aliases": ["upswing pick", "rise", "buy now"],
		"body": "A stock the bot expects to **rise soon**: at least 0.5% by the close 3 days later (daily) "
			"or 1% by the close 7 days later (weekly).\n\nA daily pick needs both a high enough **chance** "
			"and at least **2 chart signals** agreeing (weekly needs 1). Measured at the close, so a brief "
			"spike that falls back doesn't count.\n\nOn the unseen past year, daily upswing picks reached "
			"their target 42% of the time, against 22% for a random stock.",
		"related": ["chart signals", "chance", "watchlist", "track record"],
	},
	{
		"key": "buy the dip", "title": "Buy the Dip", "category": "Suggestions",
		"aliases": ["dip", "dip buy", "downswing", "drop then recover"],
		"body": "A stock the bot expects to **drop a little soon, then recover**. Instead of buying now, set a "
			"buy order at the **buy price** (0.5% below the close for daily picks, 1% for weekly) and hold "
			"for the **recovery target**.\n\nThe dip only comes about 1 in 3 times; if it doesn't, you never "
			"buy and lose nothing. When it did come on the unseen past year, buying it averaged +0.99% "
			"(82% in profit), against +0.22% for buying any stock's dip.",
		"related": ["buy price", "recovery target", "drop signs", "chance"],
	},
	{
		"key": "watchlist", "title": "Watchlist", "category": "Suggestions",
		"aliases": ["not a pick yet", "near miss", "eyes"],
		"body": "Marked 👀. When no stock meets the bar for a pick, the bot shows the two closest instead, so "
			"a quiet day still tells you what is nearly there.\n\nEach watchlist entry says what it is "
			"missing, e.g. *needs 2 chart signals (has 1)* or *needs a chance of at least 34% (has 32%)*. "
			"These are **not recommendations**; the backtest results only cover real picks (✅).",
		"related": ["upswing", "buy the dip", "chance", "chart signals"],
	},
	{
		"key": "chance", "title": "Chance (vs a random stock)", "category": "Suggestions",
		"aliases": ["probability", "confidence", "confidence bar", "random stock", "lift"],
		"body": "The model's estimated chance that the move happens, e.g. *35% chance (a random stock: 22%)*. "
			"The random-stock figure is how often the move happens anyway, so it shows how much better "
			"than luck the pick is.\n\nPicks need a chance well above the random-stock figure: 1.5x for "
			"daily upswings, 2x weekly, 1.75x daily dips and 2.25x weekly dips. Those bars were tuned on "
			"past data to give about one pick a day.",
		"related": ["upswing", "buy the dip", "backtest"],
	},
	{
		"key": "buy price", "title": "Buy price (buy zone)", "category": "Suggestions",
		"aliases": ["buy zone", "buy order", "limit order", "entry"],
		"body": "On a Buy the Dip pick, the price to set a buy order at: 0.5% below the close (daily) or 1% "
			"below (weekly). Keep the order until the date shown; after that the dip is no longer expected.",
		"related": ["buy the dip", "recovery target"],
	},
	{
		"key": "recovery target", "title": "Recovery target", "category": "Suggestions",
		"aliases": ["target", "recover", "take profit"],
		"body": "On a Buy the Dip pick, the price the stock is expected to recover to if the dip fills: 0.5% "
			"above the close the pick was based on (daily, within 14 days) or 1% above (weekly, within 30 days).",
		"related": ["buy the dip", "buy price"],
	},
	{
		"key": "track record", "title": "Track record", "category": "Suggestions",
		"aliases": ["results", "history", "past picks", "graded"],
		"body": "Every pick posted to the suggestion channels is saved and graded once its window closes. "
			"See it with `/suggest view:Track Record`.\n\n📈 ✅ closed at target · 🟡 touched it but closed "
			"short · ❌ missed\n📉 ✅ dip bought and recovered · 🟡 in profit · ❌ loss · ⏭️ the dip never came",
		"related": ["backtest", "upswing", "buy the dip"],
	},
	{
		"key": "backtest", "title": "Backtest (unseen data)", "category": "Suggestions",
		"aliases": ["past year", "how these picks did", "holdout", "unseen"],
		"body": "Each day the model is also trained on everything except the most recent year, then scored on "
			"that year using the exact picking rules. The *How these picks did over the past year* line "
			"is that score, so it is not the model grading data it already memorised. Past results don't "
			"guarantee future ones.",
		"related": ["chance", "track record"],
	},

	# ── Chart signals (counted towards upswing picks) ───────────
	{
		"key": "chart signals", "title": "Chart signals (the five counted)", "category": "Chart signals",
		"aliases": ["ta signals", "signals", "technical analysis", "the five", "confirming signals"],
		"body": "Leading signals that often show up **before** an upswing. A daily upswing pick needs at least "
			"2 (weekly: 1):\n\n"
			"• **RSI turning up from oversold**\n"
			"• **Stochastic bullish cross**\n"
			"• **MACD momentum turning up**\n"
			"• **At the lower Bollinger band**\n"
			"• **Bullish RSI divergence**\n\n"
			"Each beat the 28.4% base rate on its own in the daily history (31-37%). Candle patterns are "
			"shown but not counted, as they barely beat it.",
		"related": ["b_rsi_turn", "b_stoch_cross", "b_macd_turn", "b_lower_band", "b_divergence", "candle patterns"],
	},
	{
		"key": "b_rsi_turn", "title": "RSI turning up from oversold", "category": "Chart signals",
		"aliases": ["rsi turn", "oversold", "rsi turning up"],
		"body": "**Checks:** the 14-day RSI is below 40 and higher than the day before.\n\n"
			"**Means:** selling pressure is easing after a fall, often the first sign of a bounce.\n\n"
			"**History:** a 0.5%+ rise within 3 days followed 37.3% of the time (base 28.4%), the strongest "
			"of the five.",
		"related": ["rsi", "chart signals"],
	},
	{
		"key": "b_stoch_cross", "title": "Stochastic bullish cross", "category": "Chart signals",
		"aliases": ["stoch cross", "stochastic cross", "%k %d"],
		"body": "**Checks:** the stochastic %K line (14, 3, 3) crossed above %D while %D was below 30, today or "
			"yesterday.\n\n**Means:** price is starting to close nearer the top of its recent range after "
			"being pinned at the bottom.\n\n**History:** 35.0% followed by a 0.5%+ rise within 3 days (base 28.4%).",
		"related": ["stochastic", "chart signals"],
	},
	{
		"key": "b_macd_turn", "title": "MACD momentum turning up", "category": "Chart signals",
		"aliases": ["macd turn", "macd histogram", "momentum"],
		"body": "**Checks:** the MACD histogram (12, 26, 9) is still negative but has risen two days in a row.\n\n"
			"**Means:** the downtrend is losing speed before it turns. Earlier than waiting for a full MACD "
			"crossover (which on Torn did no better than chance, so it isn't counted).\n\n"
			"**History:** 33.4% followed by a 0.5%+ rise within 3 days (base 28.4%).",
		"related": ["macd", "chart signals"],
	},
	{
		"key": "b_lower_band", "title": "At the lower Bollinger band", "category": "Chart signals",
		"aliases": ["lower band", "bollinger low", "bb low"],
		"body": "**Checks:** the close is in the bottom 20% of the 20-day Bollinger band.\n\n"
			"**Means:** the price is stretched low compared with its recent average and volatility, and "
			"tends to snap back.\n\n**History:** 35.7% followed by a 0.5%+ rise within 3 days (base 28.4%).",
		"related": ["bollinger bands", "chart signals"],
	},
	{
		"key": "b_divergence", "title": "Bullish RSI divergence", "category": "Chart signals",
		"aliases": ["divergence", "rsi divergence", "bullish divergence"],
		"body": "**Checks:** the price is at (or within 0.2% of) a new 10-day low, but RSI is above its own "
			"10-day low.\n\n**Means:** price made a lower low but momentum didn't, so sellers are running "
			"out of steam.\n\n**History:** 31.6% followed by a 0.5%+ rise within 3 days (base 28.4%).",
		"related": ["rsi", "chart signals"],
	},

	# ── Drop signs (shown on Buy the Dip picks) ─────────────────
	{
		"key": "drop signs", "title": "Signs of a short-term drop", "category": "Drop signs",
		"aliases": ["bearish signals", "drop signals", "sell signals"],
		"body": "Shown on Buy the Dip picks when present; the mirror image of the chart signals. They are "
			"context only: the dip model relies more on volatility and how stretched the price is.\n\n"
			"• **RSI rolling over from overbought**\n• **Stochastic bearish cross**\n"
			"• **MACD momentum fading**\n• **At the upper Bollinger band**\n• **Bearish RSI divergence**",
		"related": ["s_rsi_turn", "s_stoch_cross", "s_macd_turn", "s_upper_band", "s_divergence", "buy the dip"],
	},
	{
		"key": "s_rsi_turn", "title": "RSI rolling over from overbought", "category": "Drop signs",
		"aliases": ["overbought", "rsi rolling over"],
		"body": "**Checks:** the 14-day RSI is above 60 and lower than the day before.\n\n"
			"**Means:** buying pressure is fading after a run up.",
		"related": ["rsi", "drop signs"],
	},
	{
		"key": "s_stoch_cross", "title": "Stochastic bearish cross", "category": "Drop signs",
		"aliases": ["stoch bearish", "bearish cross"],
		"body": "**Checks:** the stochastic %K line crossed below %D while %D was above 70, today or yesterday.\n\n"
			"**Means:** price is starting to close lower in its recent range after riding near the top.",
		"related": ["stochastic", "drop signs"],
	},
	{
		"key": "s_macd_turn", "title": "MACD momentum fading", "category": "Drop signs",
		"aliases": ["macd fading"],
		"body": "**Checks:** the MACD histogram is still positive but has fallen two days in a row.\n\n"
			"**Means:** the uptrend is losing speed.",
		"related": ["macd", "drop signs"],
	},
	{
		"key": "s_upper_band", "title": "At the upper Bollinger band", "category": "Drop signs",
		"aliases": ["upper band", "bollinger high", "bb high"],
		"body": "**Checks:** the close is in the top 20% of the 20-day Bollinger band.\n\n"
			"**Means:** the price is stretched high compared with its recent average and volatility.",
		"related": ["bollinger bands", "drop signs"],
	},
	{
		"key": "s_divergence", "title": "Bearish RSI divergence", "category": "Drop signs",
		"aliases": ["bearish divergence"],
		"body": "**Checks:** the price is at (or within 0.2% of) a new 10-day high, but RSI is below its own "
			"10-day high.\n\n**Means:** price made a higher high but momentum didn't.",
		"related": ["rsi", "drop signs"],
	},

	# ── Indicators ──────────────────────────────────────────────
	{
		"key": "rsi", "title": "RSI (Relative Strength Index)", "category": "Indicators",
		"aliases": ["relative strength", "short-term rsi", "rsi 7", "rsi 14"],
		"body": "A 0-100 gauge of recent gains vs losses. Below 30 is usually called **oversold**, above 70 "
			"**overbought**. The bot uses the 14-day RSI for chart signals; *short-term RSI* on dip picks "
			"is the faster 7-day version.",
		"related": ["b_rsi_turn", "b_divergence", "s_rsi_turn"],
	},
	{
		"key": "stochastic", "title": "Stochastic oscillator", "category": "Indicators",
		"aliases": ["stoch", "%k", "%d"],
		"body": "Shows where the close sits within the last 14 days' high-low range (0-100). %K is the fast "
			"line and %D its 3-day average; their crossings near the extremes (below 30 / above 70) are "
			"the signals the bot watches.",
		"related": ["b_stoch_cross", "s_stoch_cross"],
	},
	{
		"key": "macd", "title": "MACD", "category": "Indicators",
		"aliases": ["moving average convergence divergence", "macd histogram", "macd crossover"],
		"body": "The gap between a fast (12-day) and slow (26-day) exponential moving average. The histogram "
			"is that gap minus its own 9-day average, so it shows whether momentum is speeding up or "
			"slowing down.",
		"related": ["b_macd_turn", "s_macd_turn"],
	},
	{
		"key": "bollinger bands", "title": "Bollinger bands", "category": "Indicators",
		"aliases": ["bollinger", "bands", "bb"],
		"body": "Lines two standard deviations above and below the 20-day average. They widen when the price "
			"is volatile and narrow when calm; a close near either edge means the price is stretched.",
		"related": ["b_lower_band", "s_upper_band"],
	},
	{
		"key": "moving averages", "title": "Moving averages (20, 100-day)", "category": "Indicators",
		"aliases": ["20-day average", "100-day average", "sma", "average", "long-term uptrend", "uptrend"],
		"body": "The average closing price over the last N days. *Below its 20-day average* means the price "
			"has dipped short-term. *Long-term uptrend* means the price is above its 100-day average and "
			"the 50-day average is above the 100-day one.",
		"related": ["buy the dip"],
	},
	{
		"key": "candle patterns", "title": "Candle patterns (shown, not counted)", "category": "Indicators",
		"aliases": ["hammer", "inverted hammer", "harami", "doji", "engulfing", "candlestick", "patterns"],
		"body": "Named shapes of recent daily candles, like **Hammer** or **Inverted Hammer**, shown on picks as "
			"context.\n\nThey are **not counted** as chart signals: across the daily history the best "
			"(Hammer 29.5%, Inverted Hammer 29.4%) barely beat the 28.4% base rate, and counting them "
			"lowered the backtested hit rate of daily picks (42.2% to 41.7%). Some classic patterns did worse "
			"than chance on Torn.",
		"related": ["chart signals"],
	},
	{
		"key": "typical daily move", "title": "Typical daily move", "category": "Indicators",
		"aliases": ["moves about", "atr", "average true range", "volatility"],
		"body": "*Moves about ±0.55% a day* is the stock's average daily trading range over the last 14 days "
			"(ATR). It helps judge how quickly a target could be reached, and how far it might swing "
			"against you meanwhile.",
		"related": ["upswing", "buy the dip"],
	},

	# ── Other ───────────────────────────────────────────────────
	{
		"key": "tct", "title": "TCT (Torn City Time)", "category": "Other",
		"aliases": ["torn city time", "utc", "timezone", "close", "daily close"],
		"body": "Torn's clock, the same as UTC+0. A *daily close* is the last price before 00:00 TCT. "
			"Suggestion deadlines are shown as Discord timestamps, which display in your own timezone.",
		"related": ["upswing", "buy the dip"],
	},
]

_BY_KEY = {e["key"]: e for e in ENTRIES}


def get(key):
	return _BY_KEY.get(str(key).lower())


def search(query, limit=25):
	"""
	Entries whose title, key or any alias contains `query` (case-insensitive),
	best matches first: exact, then prefix, then word-start, then anywhere.
	Blank query lists everything in category order.
	"""
	q = str(query or "").strip().lower()
	if not q:
		# Category order, then the order entries are written in (overviews first)
		return sorted(ENTRIES, key=lambda e: (CATEGORIES.index(e["category"]), ENTRIES.index(e)))[:limit]
	scored = []
	for e in ENTRIES:
		best = None
		for text in [e["title"], e["key"]] + e["aliases"]:
			t = text.lower()
			if t == q:
				rank = 0
			elif t.startswith(q):
				rank = 1
			elif (" " + q) in (" " + t) or ("(" + q) in t:
				rank = 2
			elif q in t:
				rank = 3
			else:
				continue
			best = rank if best is None else min(best, rank)
		if best is not None:
			scored.append((best, e["title"], e))
	scored.sort(key=lambda s: (s[0], s[1]))
	return [s[2] for s in scored[:limit]]


def suggest(query, n=5):
	"""Close spellings for a query that matched nothing."""
	names = {}
	for e in ENTRIES:
		for text in [e["title"]] + e["aliases"]:
			names[text.lower()] = e
	close = difflib.get_close_matches(str(query).lower(), list(names), n=n * 2, cutoff=0.65)
	seen, out = set(), []
	for c in close:
		e = names[c]
		if e["key"] not in seen:
			seen.add(e["key"])
			out.append(e)
	return out[:n]
