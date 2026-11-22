"""
Glossary / guidebook for the bot's slash commands and the terms it uses,
searchable by partial text the same way the ticker autocomplete works.
Served by /glossary.

Chart-signal entries are keyed by the column names in
tsl_core/analysis/swing.py (BULL_SIGNALS / BEAR_SIGNALS), so a definition
always describes exactly what the scoring code checks. Hit rates quoted are
from the full daily history (Apr 2021 - Nov 2026, 35 stocks): how often a
0.5% rise within 3 days followed, against a 28.4% base rate for any stock-day.

Candle-pattern entries mirror the pattern lists in tsl_core/analysis/search.py
(what /search reports); keep the two in step when a pattern is added.

To add a term, append an entry to ENTRIES: key (unique, lowercase), title,
category (one of CATEGORIES), aliases (extra search words), body (plain
language, Discord markdown allowed, under ~900 characters) and related (keys).
A long entry can give body as a list of pages (each under ~2000 characters);
/glossary shows one embed per page and splits them over several messages.
"""
import difflib

CATEGORIES = [
	"Trader's guide", "Commands", "Suggestions", "Chart signals", "Drop signs", "Indicators",
	"Bullish candles", "Bearish candles", "Two-way candles", "Other",
]
# Hit rates and backtest figures quoted below were measured in Nov 2026;
# refresh them by hand if they drift (suggestion posts carry the live backtest)



def _candle(key, title, category, aliases, looks, means, related=None):
	"""A candle-pattern entry in the same Looks like / Means layout as the chart signals."""
	return {
		"key": key, "title": title, "category": category, "aliases": aliases,
		"body": "**Looks like:** " + looks + "\n\n**Means:** " + means,
		"related": (related or []) + ["candle patterns", "/search"],
	}


_BULL, _BEAR, _TWO = "Bullish candles", "Bearish candles", "Two-way candles"

ENTRIES = [
	# ── Trader's guide (multi-page: body is a list, one embed per page) ──
	# Figures measured from the bot's price history in Nov 2026 (Apr 2021 - Nov 2026,
	# 35 stocks; minute figures from the past year). Refresh by hand if they drift.
	{
		"key": "guide", "title": "New trader's guide: start here", "category": "Trader's guide",
		"aliases": ["new trader", "beginner", "beginners guide", "start here", "how stocks work", "basics",
			"trader's guide", "benefit block", "new player"],
		"body": [
			"Torn's stock market is one of the steadier ways to grow money in the game. This guide covers how "
			"it works, why patient traders rarely lose big, and how the bot can help.\n\n"
			"**The basics**\n"
			"• There are 35 stocks plus the TCSE index, each with a ticker such as `IOU` or `SYM`.\n"
			"• You buy and sell instantly at the current price. There's no order book and no waiting for "
			"another player to take the other side.\n"
			"• Prices update every minute, around the clock, every day of the week.\n"
			"• Selling costs **0.1%** of the sale.\n"
			"• Holding enough shares of a stock earns its **benefit block**. The number of shares needed and "
			"the reward differ per stock; check the stock's page in Torn.\n"
			"• Times are in TCT (Torn City Time, the same as UTC).",

			"**Chapters** (search any of them in `/glossary`)\n"
			"1. **Why Torn stocks are resilient**: the short version\n"
			"2. **Composite pricing**: where prices come from\n"
			"3. **Baseline minimum price**: the floor under every stock\n"
			"4. **Per-minute noise**: why the minute chart jitters\n"
			"5. **Trading with resilience in mind**: what to do, and what not to\n"
			"6. **Using the bot as a new trader**: a simple routine\n\n"
			"Figures in this guide come from the bot's own price history (April 2021 to November 2026, 35 "
			"stocks). Past behaviour is a guide, not a promise.",
		],
		"related": ["resilience", "composite pricing", "minimum price", "per-minute noise",
			"trading with resilience", "bot routine"],
	},
	{
		"key": "resilience", "title": "Why Torn stocks are resilient", "category": "Trader's guide",
		"aliases": ["resilient", "safe", "safety", "risk", "crash", "why stocks are safe"],
		"body": [
			"Real shares can lose most of their value overnight when a company fails. Torn stocks are built "
			"differently, and three parts of the design keep them steady:\n\n"
			"• **Composite pricing**: each price is blended from real-world stocks in the same industry, so no "
			"single company, and no single player, can sink it.\n"
			"• **Baseline minimum price**: every stock has a floor it won't fall through, so a price can't "
			"spiral towards zero.\n"
			"• **Per-minute noise**: small random moves every minute disguise which real stocks a price "
			"follows, so nobody can copy a real exchange and trade ahead of everyone else.\n\n"
			"Torn doesn't publish the details. Its own guidance is that prices follow real-world stocks in the "
			"same industries and should rise about 10% a year on average, with no guarantees.",

			"**What the price history shows**\n"
			"• Every stock is worth more today than when the bot started tracking it. The typical gain is "
			"**6.6% a year**, from 0.3% (SYM) to 13.8% (TCP).\n"
			"• The deepest any stock has ever fallen from a high is **29.5%**; a typical stock's worst fall "
			"is about 16%.\n"
			"• Of 338 times a stock fell 10% below a high, **88%** later climbed back to it, typically within "
			"about 7 months.\n"
			"• 29 of the 35 all-time lows were set in 2021, and no stock has set a new all-time low since "
			"April 2023.\n"
			"• Stocks barely move together, so there has never been a market-wide crash.\n\n"
			"Resilient isn't risk-free: see *Trading with resilience in mind*.",
		],
		"related": ["composite pricing", "minimum price", "per-minute noise", "trading with resilience", "guide"],
	},
	{
		"key": "composite pricing", "title": "Composite pricing", "category": "Trader's guide",
		"aliases": ["composite", "how prices work", "price source", "real world stocks", "industry",
			"manipulation", "pump and dump"],
		"body": [
			"**What it is**\n"
			"A Torn stock isn't a real company with its own share price. Torn says each stock's movement is "
			"based on real-world stocks in the same industry, blended into one price, so no single company "
			"decides it.\n\n"
			"**Why it makes stocks resilient**\n"
			"• **Spread risk.** If one company in the mix crashes, it's only part of the blend, so the Torn "
			"price dips rather than collapses. A typical Torn stock moves about 0.7% a day.\n"
			"• **No company risk.** There are no earnings misses, scandals or bankruptcies in Torn to wipe a "
			"stock out.\n"
			"• **Players don't set the price.** Trades happen instantly at the current price rather than "
			"through an order book, so the price follows its sources, not buying and selling in Torn. A big "
			"holder selling up can't start a crash, and a group can't pump a stock and dump it on latecomers.",

			"**What it means for you**\n"
			"• A blend softens shocks; it doesn't stop trends. An industry having a bad few months can still "
			"carry a stock down for a while.\n"
			"• Each stock follows its own sources, so stocks barely move together. Across the whole history "
			"the typical correlation between two stocks' daily moves is **0.00**, and the closest pair is only "
			"0.13. Holding several stocks spreads your risk well.\n"
			"• News about one real-world company tells you little about a Torn stock.",
		],
		"related": ["resilience", "minimum price", "per-minute noise"],
	},
	{
		"key": "minimum price", "title": "Baseline minimum price", "category": "Trader's guide",
		"aliases": ["floor", "price floor", "baseline", "minimum", "all-time low", "bottom", "zero"],
		"body": [
			"**What it is**\n"
			"Each stock has a baseline price underneath it that it isn't allowed to fall through. Torn doesn't "
			"publish the levels, but the floor means a Torn stock can't go the way of a bankrupt company and "
			"drift towards zero.\n\n"
			"**Why it makes stocks resilient**\n"
			"• **Losses are capped.** However bad a run gets, a price can only fall so far, and the further it "
			"falls the less room is left below.\n"
			"• **Lows hold.** 29 of the 35 all-time lows date from 2021, the first months of the current "
			"market, and no stock has set a new all-time low since April 2023.\n"
			"• **Falls are shallow.** The deepest drop any stock has had from a high is 29.5% (SYM); no stock "
			"has ever fallen 30%.",

			"**What it means for you**\n"
			"• A stock well below its recent high has historically been worth a look rather than a trap: of "
			"338 falls of 10%, 88% later regained the old high.\n"
			"• The floor protects against collapse, not against slow years. Some stocks have barely grown "
			"(SYM 0.3% a year, EWM 1.5%).\n"
			"• Deeper falls recover slowly. Of 81 falls of 20%, only 37% have regained their high so far, "
			"and those took around two years.\n"
			"• The floor levels aren't published, so use `/overview mode:Near Recent Lows` and the Buy the Dip "
			"picks to spot stocks near the bottom of their range.",
		],
		"related": ["resilience", "composite pricing", "buy the dip", "/overview"],
	},
	{
		"key": "per-minute noise", "title": "Per-minute noise", "category": "Trader's guide",
		"aliases": ["noise", "minute noise", "jitter", "random", "obfuscation", "minute chart", "m1 chart"],
		"body": [
			"**What it is**\n"
			"On top of its real-world sources, every price gets small random moves each minute. If Torn prices "
			"simply copied real shares, anyone watching the right exchange could see moves coming and trade "
			"ahead of everyone else. The noise, together with the blending, hides which real stocks a price "
			"follows.\n\n"
			"**What the price history shows**\n"
			"• A typical minute moves about **0.006%**, roughly 2 cents on a $300 stock, and about 1 minute in "
			"5 doesn't change at all.\n"
			"• When the price does move, the next minute goes the other way 43% of the time; the jitter partly "
			"undoes itself.\n"
			"• Prices move just as much at weekends and outside US trading hours as during them, while real "
			"markets are shut. The minute-by-minute movement isn't a live copy of any exchange.",

			"**Why it makes stocks resilient**\n"
			"• **No insider edge.** Nobody can read Torn's next move off a real exchange, so no group can "
			"steadily drain money from everyone else.\n"
			"• **Nothing to target.** Blended, disguised sources leave no single real price to watch or "
			"exploit.\n\n"
			"**What it means for you**\n"
			"• Don't make decisions from the minute chart. Minute moves are mostly noise, and over a day they "
			"add up to little more than a random walk.\n"
			"• Trading minute moves can't pay: the 0.1% selling fee is about 17 typical minute moves, so a "
			"trade has to gain that much just to break even.\n"
			"• Use hourly or daily candles (`h1` to `d1`) with `/search` and `/overview`. The bot's picks use "
			"daily closes for the same reason.",
		],
		"related": ["resilience", "composite pricing", "timeframes", "/search"],
	},
	{
		"key": "trading with resilience", "title": "Trading with resilience in mind", "category": "Trader's guide",
		"aliases": ["tips", "do and don't", "dos and donts", "strategy", "panic sell", "hold", "long term"],
		"body": [
			"**Do**\n"
			"• **Think in weeks and months, not minutes.** The steady upward drift (6.6% a year typically) "
			"rewards holding.\n"
			"• **Buy weakness, not strength.** Falls have usually recovered, so a stock below its recent high "
			"is often better value than one that has just spiked.\n"
			"• **Spread your money** over several stocks; they rarely fall together.\n"
			"• **Hold benefit blocks** where you can, so you earn the benefit while you wait for prices to move.\n"
			"• **Let the bot watch for you**: `/alert` for target prices, `/paper` to check a trade before "
			"making it.",

			"**Don't**\n"
			"• **Panic-sell a dip.** Selling locks in the loss and costs 0.1%, and most dips have come back.\n"
			"• **Chase a spike.** Buying right after a sharp rise often means buying a short-term high.\n"
			"• **Trade the minute chart.** The noise is bigger than any pattern, and the fee eats small gains.\n"
			"• **Treat it as free money.** Resilient isn't risk-free:\n"
			"  – Recoveries can take months, and around two years after a 20% fall.\n"
			"  – Money in a slow stock misses gains elsewhere (SYM has grown 0.3% a year).\n"
			"  – Typical growth (6.6% a year) has been below Torn's 10% expectation.\n"
			"  – Torn can change how the market works, as it did when it relaunched it in 2021.",
		],
		"related": ["resilience", "minimum price", "per-minute noise", "bot routine", "buy the dip"],
	},
	{
		"key": "bot routine", "title": "Using the bot as a new trader", "category": "Trader's guide",
		"aliases": ["routine", "workflow", "getting started", "how to use the bot", "first steps"],
		"body": [
			"A simple routine:\n\n"
			"1. **Check the picks.** `/suggest` shows today's Upswing and Buy the Dip picks with the reasons "
			"behind them; the watchlist shows what's nearly there.\n"
			"2. **Look closer.** `/stock` for a stock's price and investors over time, `/search` on `d1` for "
			"chart signals, `/overview mode:Near Recent Lows` for stocks near the bottom of their range.\n"
			"3. **Plan the trade.** `/paper buy` shows how many shares your cash buys; `/paper sell` what "
			"you'd get back after the fee.\n"
			"4. **Let the bot watch.** `/alert` DMs you at a target price, and *Loss* alerts work as stop-loss "
			"reminders. `/notifications` lists them.\n"
			"5. **Track how you're doing.** Save your Torn API key with `/apikey`, then `/portfolio` shows how "
			"each purchase is doing.\n"
			"6. **Learn as you go.** Any term you don't recognise is in `/glossary`.\n\n"
			"The bot gives information, not financial advice. Even Torn money is yours to risk.",
		],
		"related": ["guide", "/suggest", "/alert", "/paper", "/portfolio"],
	},

	# ── Commands ────────────────────────────────────────────────
	{
		"key": "/stock", "title": "/stock: price, shares and investors", "category": "Commands",
		"aliases": ["stock", "price", "stock info"],
		"body": "Shows a stock's current price, total shares held and number of investors.\n\n"
			"Give a **timeframe** such as `h1`, `d1`, `w1` or `n1` to compare each figure with that long ago "
			"(with the % change), or a unix timestamp to compare with an exact moment. The default `m1` "
			"shows the current figures only.",
		"related": ["timeframes", "/overview"],
	},
	{
		"key": "/overview", "title": "/overview: scan every stock", "category": "Commands",
		"aliases": ["overview", "movers", "lows", "highs", "scan"],
		"body": "Checks every stock at once over the last N candles:\n\n"
			"• **Movers**: the biggest price changes\n"
			"• **Near Recent Lows**: stocks trading close to the period's lowest price\n"
			"• **Near Recent Highs**: stocks trading close to the period's highest price\n\n"
			"Pick the candle size (`m5` to `d1`, default `d1`) and how many candles to look back over "
			"(2-4000, default 7, so a week of daily candles).",
		"related": ["timeframes", "/search", "/stock"],
	},
	{
		"key": "/search", "title": "/search: candle patterns and oscillators", "category": "Commands",
		"aliases": ["search", "pattern search", "scan patterns"],
		"body": "Looks at a stock's last three candles for named **candle patterns** (bullish, bearish or both) "
			"and **oscillator** readings (RSI and Stochastic oversold/overbought, MACD crossovers). Use the "
			"ticker `ALL` to scan every stock.\n\nCandle size `h1` to `d1` (default `d1`). Every pattern it "
			"can report has its own glossary entry. Treat results as leads to look into, not picks: on Torn "
			"most candle patterns barely beat chance.",
		"related": ["candle patterns", "oversold", "macd crossover", "timeframes"],
	},
	{
		"key": "/suggest", "title": "/suggest: today's picks and track record", "category": "Commands",
		"aliases": ["suggest", "suggestions", "picks", "ranking"],
		"body": "The bot's TA-backed picks.\n\n"
			"• **horizon**: Daily (0.5% moves over a few days) or Weekly (1% over a week or more)\n"
			"• **direction**: Upswings, Buy the Dip, or both\n"
			"• **view**: current **Picks**, a **Full Ranking** of every stock by chance, or the **Track Record** "
			"of past posted picks (with **days** setting how far back)",
		"related": ["upswing", "buy the dip", "watchlist", "track record"],
	},
	{
		"key": "/predict", "title": "/predict: price forecast chart", "category": "Commands",
		"aliases": ["predict", "prediction", "forecast", "xgboost"],
		"body": "Trains a model (XGBoost) on a stock's past closing prices at the chosen candle size and charts "
			"where it projects the next **predictions** candles (up to 200). **samples** is how many past "
			"candles it learns from (default 2000).\n\nA rough projection that gets less reliable the further "
			"out it goes. For backtested picks, use `/suggest`.",
		"related": ["timeframes", "/suggest"],
	},
	{
		"key": "/alert", "title": "/alert: price alerts by DM", "category": "Commands",
		"aliases": ["alert", "alerts", "up", "down", "loss", "stop loss", "price alert"],
		"body": "The bot DMs you when a stock reaches a price.\n\n"
			"• **Up**: at or above the value\n• **Down**: at or below it\n"
			"• **Loss**: a stop-loss reminder, at or below it\n\n"
			"The value can be a price (`123.45`) or a percentage from the current price (`5%`). Percentages "
			"follow the alert's direction, so *Down 5%* means 5% below the current price. Your DMs need to be "
			"open to the bot.",
		"related": ["/notifications", "/forget", "/undo", "/clear"],
	},
	{
		"key": "/notifications", "title": "/notifications: list your alerts", "category": "Commands",
		"aliases": ["notifications", "my alerts", "list alerts", "pending"],
		"body": "Lists your pending alerts, optionally only one type (Up, Down, Loss) or one stock. Sent by DM "
			"when it can be, otherwise as a reply only you can see.",
		"related": ["/alert", "/forget"],
	},
	{
		"key": "/forget", "title": "/forget: remove alerts for a stock", "category": "Commands",
		"aliases": ["forget", "remove alert", "delete alert"],
		"body": "Removes your alerts for one stock. Optionally narrow it to one type (Up, Down, Loss) and/or "
			"one price (matched to 2 decimal places).",
		"related": ["/alert", "/undo", "/clear"],
	},
	{
		"key": "/undo", "title": "/undo: remove your last alert", "category": "Commands",
		"aliases": ["undo", "oops", "mistake"],
		"body": "Removes the alert you added most recently, for when one was set up wrong.",
		"related": ["/alert", "/forget"],
	},
	{
		"key": "/clear", "title": "/clear: remove all your alerts", "category": "Commands",
		"aliases": ["clear", "forget me", "clear alerts"],
		"body": "Removes every alert you have pending.",
		"related": ["/alert", "/forget"],
	},
	{
		"key": "/paper", "title": "/paper buy & sell: trade calculator", "category": "Commands",
		"aliases": ["paper", "paper buy", "paper sell", "calculator", "buy", "sell", "tax", "sell fee"],
		"body": "Works out a trade at the current price without making it.\n\n"
			"• **/paper buy**: how many shares a sum of cash buys, and the change left over\n"
			"• **/paper sell**: what a number of shares is worth before and after Torn's 0.1% selling fee",
		"related": ["amounts", "/portfolio"],
	},
	{
		"key": "/portfolio", "title": "/portfolio: your Torn holdings", "category": "Commands",
		"aliases": ["portfolio", "holdings", "my stocks", "transactions"],
		"body": "Lists the stocks you own in Torn, each purchase with how its price has changed since. Filter "
			"to one stock, and limit how many purchases are shown per stock.\n\nNeeds your Torn API key, "
			"saved with `/apikey`. Only you can see the reply.",
		"related": ["/apikey", "/paper"],
	},
	{
		"key": "/apikey", "title": "/apikey: save your Torn API key", "category": "Commands",
		"aliases": ["apikey", "api key", "key", "torn api"],
		"body": "Saves, replaces, removes or checks your personal 16-character Torn API key. It is stored "
			"encrypted and only used for your own commands, such as `/portfolio`.",
		"related": ["/portfolio"],
	},
	{
		"key": "/glossary", "title": "/glossary: this guidebook", "category": "Commands",
		"aliases": ["glossary", "help", "guidebook", "commands", "what does"],
		"body": "Search the bot's commands and terms. Start typing in `term:` and pick from the list; partial "
			"words work (e.g. `boll`, `hammer`, `alert`). Leave it blank to list everything.",
		"related": ["/suggest", "/search", "chart signals"],
	},
	{
		"key": "admin commands", "title": "Admin commands", "category": "Commands",
		"aliases": ["admin", "stop", "sync", "force_suggestions", "force suggestions"],
		"body": "Only bot admins can use these.\n\n"
			"• **/stop**: shuts the bot down cleanly\n"
			"• **/sync**: pushes the slash command list to Discord after commands change\n"
			"• **/force_suggestions**: runs the daily or weekly suggestion post now, as a private preview, in "
			"the current channel, or live to the suggestion channels",
		"related": ["/suggest"],
	},

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
		"aliases": ["moving average convergence divergence", "macd histogram"],
		"body": "The gap between a fast (12-day) and slow (26-day) exponential moving average. The histogram "
			"is that gap minus its own 9-day average, so it shows whether momentum is speeding up or "
			"slowing down.",
		"related": ["b_macd_turn", "s_macd_turn", "macd crossover"],
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
		"aliases": ["candlestick", "candlesticks", "patterns", "candles"],
		"body": "Named shapes of recent daily candles, like **Hammer** or **Inverted Hammer**, shown on picks as "
			"context.\n\nThey are **not counted** as chart signals: across the daily history the best "
			"(Hammer 29.5%, Inverted Hammer 29.4%) barely beat the 28.4% base rate, and counting them "
			"lowered the backtested hit rate of daily picks (42.2% to 41.7%). Some classic patterns did worse "
			"than chance on Torn.\n\nEach pattern `/search` can report has its own entry under Bullish, Bearish and "
			"Two-way candles.",
		"related": ["chart signals", "/search", "p_hammer", "p_engulfing"],
	},
	{
		"key": "typical daily move", "title": "Typical daily move", "category": "Indicators",
		"aliases": ["moves about", "atr", "average true range", "volatility"],
		"body": "*Moves about ±0.55% a day* is the stock's average daily trading range over the last 14 days "
			"(ATR). It helps judge how quickly a target could be reached, and how far it might swing "
			"against you meanwhile.",
		"related": ["upswing", "buy the dip"],
	},

	{
		"key": "oversold", "title": "Oversold / overbought (/search)", "category": "Indicators",
		"aliases": ["overbought", "oversold position", "overbought position", "oscillators"],
		"body": "How `/search` reports oscillators on the latest candle:\n\n"
			"📈 **Oversold**: RSI below 30, or Stochastic %K and %D both below 20 with %K under %D\n"
			"📉 **Overbought**: RSI above 70, or %K and %D both above 80 with %K over %D\n\n"
			"Oversold means the price has fallen hard and fast and may bounce; overbought is the reverse. "
			"Either can last a while in a strong trend.",
		"related": ["rsi", "stochastic", "/search"],
	},
	{
		"key": "macd crossover", "title": "MACD crossover", "category": "Indicators",
		"aliases": ["macd cross", "bullish crossover", "bearish crossover", "signal line"],
		"body": "Reported by `/search` when the MACD line crossed its 9-period signal line on the latest candle: "
			"📈 upwards is bullish, 📉 downwards bearish.\n\nIt is a lagging signal. On Torn's daily "
			"history it did no better than chance, so suggestion picks watch the earlier *MACD momentum "
			"turning up* instead.",
		"related": ["macd", "b_macd_turn", "/search"],
	},

	# ── Bullish candles (after a fall; /search Bullish) ─────────
	_candle("p_hammer", "Hammer", _BULL, ["hammer candle"],
		"after a fall, one candle with a small body near the top and a lower wick at least twice as long as the body.",
		"sellers pushed the price well down but buyers took it back by the close. One of the two best patterns on Torn, though still only just above chance.",
		["p_hanging_man", "p_inverted_hammer"]),
	_candle("p_inverted_hammer", "Inverted Hammer", _BULL, [],
		"after a fall, a small body near the bottom of the candle with a long upper wick.",
		"buyers tried to push higher. A reversal needs the next candle to follow through.",
		["p_shooting_star", "p_hammer"]),
	_candle("p_piercing", "Piercing", _BULL, ["piercing line", "piercing pattern"],
		"a long falling candle, then a rising one that opens below its low and closes above the middle of its body.",
		"buyers won back more than half of the previous candle's loss.",
		["p_dark_cloud_cover"]),
	_candle("p_morningstar", "Morningstar", _BULL, ["morning star"],
		"three candles: a long fall, a small candle gapping lower (the star), then a long rise closing well into the first candle's body.",
		"the fall stalled on the middle candle and buyers took over.",
		["p_morning_doji_star", "p_eveningstar"]),
	_candle("p_morning_doji_star", "Morning Doji Star", _BULL, [],
		"a Morningstar whose middle candle is a doji (opens and closes at almost the same price).",
		"as Morningstar, with clearer indecision at the bottom.",
		["p_morningstar", "p_doji"]),
	_candle("p_three_white_soldiers", "Three White Soldiers", _BULL, ["3 white soldiers", "soldiers"],
		"three long rising candles in a row, each opening inside the previous body and closing near its high.",
		"steady buying over three periods; a strong reversal after a fall.",
		["p_three_black_crows"]),
	_candle("p_breakaway", "Breakaway", _BULL, [],
		"five candles: a gap down that starts a fall lasting three candles, then a long rise that closes inside the gap.",
		"the selling ran out of steam. /search only reports the bullish version.",
		[]),
	_candle("p_mat_hold", "Mat Hold", _BULL, [],
		"in a rise, a long rising candle, a gap up, three small falling candles that stay above the first candle's low, then a long rise to a new high.",
		"a pause in an uptrend that then carries on.",
		["p_tasuki_gap"]),
	_candle("p_homing_pigeon", "Homing Pigeon", _BULL, [],
		"two falling candles, the second's body entirely inside the first's.",
		"the selling is shrinking.",
		["p_harami"]),
	_candle("p_unique_three_river", "Unique Three River", _BULL, ["unique 3 river"],
		"a long fall; a second falling candle that makes a new low but has a smaller body; then a small rising candle closing below the second's close.",
		"a rare sign that a bottom is forming.",
		[]),
	_candle("p_kicking", "Kicking", _BULL, ["kicker"],
		"a falling candle with no wicks, then a rising candle with no wicks that gaps above it.",
		"an abrupt switch from sellers to buyers. /search only reports the bullish version.",
		["p_marubozu"]),
	_candle("p_ladder_bottom", "Ladder Bottom", _BULL, [],
		"three falling candles each opening and closing lower, a fourth falling candle with an upper wick, then a rise opening above the fourth's body.",
		"a reversal at the end of a long fall.",
		[]),
	_candle("p_abandoned_baby", "Abandoned Baby", _BULL, [],
		"a long fall, a doji that gaps below it with no overlap, then a rise that gaps above the doji.",
		"a rare, sharp reversal. /search only reports the bullish version.",
		["p_morningstar", "p_doji"]),
	_candle("p_tri_star", "Tri-Star", _BULL, ["tristar"],
		"three dojis in a row, the middle one gapping below the other two.",
		"repeated indecision after a fall, which can mark a turn. /search only reports the bullish version.",
		["p_doji"]),
	_candle("p_stick_sandwich", "Stick Sandwich", _BULL, [],
		"a falling candle, a rising candle, then a falling candle that closes at the same price as the first.",
		"that price held as a floor twice.",
		[]),
	_candle("p_three_stars_in_south", "Three Stars in South", _BULL, ["three stars in the south", "3 stars in south"],
		"three falling candles, each smaller than the last and with a higher low.",
		"the selling is drying up.",
		[]),

	# ── Bearish candles (after a rise; /search Bearish) ─────────
	_candle("p_hanging_man", "Hanging Man", _BEAR, [],
		"the Hammer shape (small body at the top, long lower wick) but after a rise.",
		"sellers showed up during the uptrend. Needs the next candle to confirm.",
		["p_hammer"]),
	_candle("p_shooting_star", "Shooting Star", _BEAR, [],
		"after a rise, a small body near the bottom of the candle with a long upper wick.",
		"buyers pushed higher but the price was knocked back by the close.",
		["p_inverted_hammer"]),
	_candle("p_eveningstar", "Eveningstar", _BEAR, ["evening star"],
		"three candles: a long rise, a small candle gapping higher, then a long fall closing well into the first candle's body.",
		"the rise stalled on the middle candle and sellers took over.",
		["p_evening_doji_star", "p_morningstar"]),
	_candle("p_evening_doji_star", "Evening Doji Star", _BEAR, [],
		"an Eveningstar whose middle candle is a doji.",
		"as Eveningstar, with clearer indecision at the top.",
		["p_eveningstar", "p_doji"]),
	_candle("p_three_black_crows", "Three Black Crows", _BEAR, ["3 black crows", "crows"],
		"three long falling candles in a row, each opening inside the previous body and closing near its low.",
		"steady selling over three periods; a strong reversal after a rise.",
		["p_three_white_soldiers", "p_identical_three_crows"]),
	_candle("p_dark_cloud_cover", "Dark Cloud Cover", _BEAR, ["dark cloud"],
		"a long rising candle, then one that opens above its high and closes below the middle of its body.",
		"sellers wiped out more than half of the previous candle's gain.",
		["p_piercing"]),
	_candle("p_advance_block", "Advance Block", _BEAR, [],
		"three rising candles with shrinking bodies and growing upper wicks.",
		"the rise is still going but losing strength.",
		["p_three_white_soldiers"]),
	_candle("p_two_crows", "Two Crows", _BEAR, ["2 crows"],
		"a long rise; a falling candle that gaps up; then another falling candle that opens inside the second and closes inside the first's body.",
		"the gap up failed and sellers are pushing back.",
		[]),
	_candle("p_identical_three_crows", "Identical Three Crows", _BEAR, ["identical 3 crows"],
		"three falling candles, each opening at about the previous close.",
		"relentless selling with no bounce between candles.",
		["p_three_black_crows"]),
	_candle("p_on_neck", "On-Neck", _BEAR, ["on neck"],
		"in a fall, a long falling candle, then a rising candle that opens lower and closes only at about the first's low.",
		"the bounce was weak, so the fall is likely to continue.",
		[]),

	# ── Two-way candles (/search reports either direction) ──────
	_candle("p_three_inside", "Three Inside Up / Down", _TWO, ["three inside", "three inside up", "three inside down"],
		"a Harami (big candle then a small one inside it) followed by a third candle that closes beyond the first candle's body.",
		"**Up** after a fall (bullish), **Down** after a rise (bearish); a Harami that the next candle confirmed.",
		["p_harami", "p_three_outside"]),
	_candle("p_three_outside", "Three Outside Up / Down", _TWO, ["three outside", "three outside up", "three outside down"],
		"an Engulfing pair followed by a third candle that continues in the same direction.",
		"**Up** is bullish, **Down** bearish; an Engulfing that the next candle confirmed.",
		["p_engulfing", "p_three_inside"]),
	_candle("p_harami", "Harami", _TWO, ["bullish harami", "bearish harami", "inside bar"],
		"a long candle, then a small candle whose body sits entirely inside the first's body.",
		"the move is stalling. **Bullish** after a fall, **Bearish** after a rise.",
		["p_harami_cross", "p_three_inside"]),
	_candle("p_harami_cross", "Harami Cross", _TWO, ["bullish harami cross", "bearish harami cross"],
		"a Harami whose second candle is a doji.",
		"as Harami, with stronger indecision.",
		["p_harami", "p_doji"]),
	_candle("p_marubozu", "Marubozu", _TWO, ["white marubozu", "black marubozu"],
		"a long candle with little or no wick at either end.",
		"one side was in control the whole period: **White** opened at the low and closed at the high (buyers), **Black** the reverse (sellers).",
		["p_belt_hold"]),
	_candle("p_counterattack", "Counterattack", _TWO, ["bullish counterattack", "bearish counterattack", "counterattack lines"],
		"two long candles of opposite colour that close at about the same price.",
		"the second candle fought all the way back to the first's close. **Bullish** after a fall, **Bearish** after a rise.",
		[]),
	_candle("p_engulfing", "Engulfing", _TWO, ["bullish engulfing", "bearish engulfing"],
		"a candle whose body completely covers the previous, opposite-coloured body.",
		"the other side took over decisively. **Bullish** (rising candle engulfs a falling one) after a fall, **Bearish** after a rise.",
		["p_three_outside", "p_piercing", "p_dark_cloud_cover"]),
	_candle("p_doji", "Doji", _TWO, ["bullish doji", "bearish doji", "cross"],
		"a candle that opens and closes at almost the same price, so the body is a thin line.",
		"indecision between buyers and sellers. TA-Lib doesn't give a doji a direction, so `/search` always lists it as *Bullish Doji*; read it against the trend before it.",
		["p_spinning_top", "p_harami_cross"]),
	_candle("p_spinning_top", "Spinning Top", _TWO, ["bullish spinning top", "bearish spinning top"],
		"a small body with wicks on both sides; bullish or bearish by the body's colour.",
		"neither side won the period. Mostly a sign of indecision rather than direction.",
		["p_doji"]),
	_candle("p_belt_hold", "Belt Hold", _TWO, ["bullish belt hold", "bearish belt hold"],
		"a long candle that opens at its extreme against the trend: a rising candle opening at its low after a fall, or a falling one opening at its high after a rise.",
		"a sharp push against the trend from the very start of the period.",
		["p_marubozu"]),
	_candle("p_tasuki_gap", "Tasuki Gap", _TWO, ["upside tasuki gap", "downside tasuki gap"],
		"a gap in the direction of the trend, then a candle the other way that partly fills the gap but doesn't close it.",
		"the trend is likely to continue. **Upside** is bullish, **Downside** bearish.",
		["p_mat_hold"]),
	_candle("p_separating_lines", "Separating Lines", _TWO, ["bull separating lines", "bear separating lines"],
		"a candle against the trend, then a trend candle that opens at the same price and moves away from it.",
		"the counter-move was rejected and the trend carries on. **Bull** in a rise, **Bear** in a fall.",
		[]),

	# ── Other ───────────────────────────────────────────────────
	{
		"key": "tct", "title": "TCT (Torn City Time)", "category": "Other",
		"aliases": ["torn city time", "utc", "timezone", "close", "daily close"],
		"body": "Torn's clock, the same as UTC+0. A *daily close* is the last price before 00:00 TCT. "
			"Suggestion deadlines are shown as Discord timestamps, which display in your own timezone.",
		"related": ["upswing", "buy the dip"],
	},
	{
		"key": "timeframes", "title": "Timeframes (m5, h1, d1, ...)", "category": "Other",
		"aliases": ["timeframe", "interval", "intervals", "candle size", "m1", "m5", "h1", "d1", "w1", "n1"],
		"body": "The candle size or look-back period a command works on: **m** minutes, **h** hours, **d** days, "
			"**w** weeks, **n** months.\n\n"
			"• Candle sizes: `m1 m5 m15 m30 h1 h2 h4 h6 h12 d1`\n"
			"• `/stock` also takes `w1` and `n1` (or a unix timestamp)\n"
			"• `/overview` starts at `m5`; `/search` uses `h1` to `d1`",
		"related": ["/stock", "/overview", "/search", "/predict"],
	},
	{
		"key": "amounts", "title": "Amounts (500k, 1.5m, 2b)", "category": "Other",
		"aliases": ["numbers", "shorthand", "k", "m", "b", "1,000,000"],
		"body": "Number fields accept shorthand: `500k` = 500,000, `1.5m` = 1,500,000, `2b` = 2,000,000,000 "
			"and `1t` = one trillion. Commas are fine too (`1,000,000`).",
		"related": ["/paper", "/alert"],
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
