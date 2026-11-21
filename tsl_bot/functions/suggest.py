"""
Automated longer-term suggestions at daily and weekly scales:

	📈 Upswing     - stocks expected to rise soon, confirmed by chart signals (buy now).
	📉 Buy the Dip - stocks expected to drop soon and then recover: set a buy
	                 order at the dip price and hold for the upswing.

The analysis lives in tsl_core/analysis/swing.py; this module turns it into
Discord embeds, posts scheduled picks and grades past picks so the bot keeps an
honest track record.
"""
import asyncio
import math
import time
from datetime import datetime, timezone

import discord

import tsl_core.functions as tsl_lib
import tsl_config.config as config

swing = tsl_lib.analysis.swing


def _dt(ts):
	return datetime.fromtimestamp(int(ts), timezone.utc)


def _tct(ts):
	return _dt(ts).strftime("%d/%m/%y")


def _day(ts):
	"""e.g. "Mon 23/11" - weekday helps on a 24/7 market where dates blur together."""
	return _dt(ts).strftime("%a %d/%m")


def _deadline(day_ts):
	"""
	The close of a Torn day as a fixed TCT time plus a live Discord countdown,
	e.g. "**Fri 27/11 23:59 TCT** (in 6 days)". Discord timestamps always render
	in the viewer's own timezone, so the absolute time stays written in TCT and
	only the timezone-independent relative form uses <t:...:R>. Timestamps only
	render in descriptions and field values, not titles, names or footers.
	"""
	close = int(day_ts) + 86399
	return "**" + _day(day_ts) + " 23:59 TCT** (<t:" + str(close) + ":R>)"


def _pct(val, signed=True):
	if val is None or (isinstance(val, float) and math.isnan(val)):
		return "n/a"
	return ("{:+.2f}" if signed else "{:.0f}").format(val * 100) + "%"


def _money(val):
	return "$" + "{:,.2f}".format(val)


def _live_stock(ticker):
	"""(name, live price) from the Tornsy feed, falling back to the ticker if missing."""
	try:
		for data in config.json_data["data"]:
			if data["stock"] == ticker.upper():
				return data["name"], float(data["price"])
	except (TypeError, KeyError):
		pass
	return ticker.upper(), None


def _stock_name(ticker):
	name, _ = _live_stock(ticker)
	return name if name.upper() != ticker.upper() else ticker.upper()


def _stock_link(ticker):
	return "https://www.torn.com/page.php?sid=stocks&stockID=" + tsl_lib.util.lut_stock_id(ticker) + "&tab=owned"


def _stock_heading(ticker):
	"""Bold, linked full name plus ticker, e.g. **[Torn City Investments](...)** · `TCI`."""
	name = _stock_name(ticker)
	if name == ticker.upper():
		return "**[" + ticker.upper() + "](" + _stock_link(ticker) + ")**"
	return "**[" + name + "](" + _stock_link(ticker) + ")** · `" + ticker.upper() + "`"


def _heading_block(ticker):
	"""
	The stock's name line set apart by a blank line above and below, ending in
	a colon. Discord trims leading blank lines from a field, so a zero-width
	space keeps the gap when this opens the field.
	"""
	return "​\n" + _stock_heading(ticker) + ":\n\n"


def _stock_label(ticker):
	"""Plain "Full Name (TCK)" for places links don't render, like field titles."""
	name = _stock_name(ticker)
	return ticker.upper() if name == ticker.upper() else name + " (" + ticker.upper() + ")"


def _directions(direction):
	return list(swing.DIRECTIONS) if direction in (None, "both") else [direction]


def run_scan(horizon, direction="both", top_n=3):
	"""
	{direction: scan result} for one or both kinds of pick. CPU heavy
	(training once a day) - call from a worker thread, not the event loop.
	"""
	return {d: swing.scan(horizon, d, tsl_lib.stock_lut, top_n=top_n) for d in _directions(direction)}


def grade_open_suggestions():
	"""Fill in outcomes for any posted suggestion whose window has closed."""
	graded = 0
	for row_id, horizon, direction, ticker, as_of, entry, target in tsl_lib.db.suggestion_get_open():
		try:
			res = swing.outcome(ticker, as_of, horizon, direction, entry, target)
		except Exception:
			continue
		if res is None:
			continue
		tsl_lib.db.suggestion_set_outcome(row_id, *res)
		graded += 1
	return graded


def record_picks(results):
	for result in results.values():
		for pick in result["picks"]:
			# For dips the tracked target is the buy zone; the recovery target is derived when grading
			target = pick["buy_zone"] if result["direction"] == "dip" else pick["target"]
			tsl_lib.db.suggestion_record(result["horizon"], result["direction"], pick["ticker"], result["as_of"], pick["close"], target, pick["probability"])


def _chance(pick, result):
	return "**" + _pct(pick["probability"], False) + "** chance (a random stock: " + _pct(result["base_rate"], False) + ")"


def _up_value(pick, result):
	_, live = _live_stock(pick["ticker"])
	value = _heading_block(pick["ticker"])
	value += "Buy around **" + _money(pick["close"]) + "**, target **" + _money(pick["target"]) + "** by " + _deadline(result["target_day"])
	if live is not None:
		value += "\nNow " + _money(live) + " (" + _pct(live / pick["close"] - 1) + " since the close)"
		if live >= pick["target"]:
			value += ", target already reached"
	n = pick["bull_score"]
	if n:
		value += "\n**" + str(n) + " of " + str(len(swing.BULL_SIGNALS)) + " chart signals:** " + ", ".join(pick["signals"])
	else:
		value += "\n**No chart signals yet**"
	if pick["context"]:
		value += "\nAlso: " + ", ".join(pick["context"])
	value += "\n" + _chance(pick, result) + " · moves about ±" + "{:.2f}".format(pick["atr_pct"]) + "% a day"
	return value


def _dip_value(pick, result):
	_, live = _live_stock(pick["ticker"])
	value = _heading_block(pick["ticker"])
	value += "Set a buy order at **" + _money(pick["buy_zone"]) + "** (" + _pct(pick["buy_zone"] / pick["close"] - 1) + "), keep it until " + _deadline(result["target_day"])
	value += "\nIf it fills, expect **" + _money(pick["target"]) + "** or better by " + _deadline(result["recover_day"])
	if live is not None:
		value += "\nNow " + _money(live)
		if live <= pick["buy_zone"]:
			value += ", ✅ already at the buy price"
		else:
			value += ", " + "{:.2f}".format((live / pick["buy_zone"] - 1) * 100) + "% above the buy price"
	if pick["signals"]:
		value += "\nSigns of a short-term drop: " + ", ".join(pick["signals"])
	value += "\nWhy: " + ", ".join(pick["context"])
	value += "\n" + _chance(pick, result) + " of the dip and recovery"
	return value


def _ranking_lines(result, limit):
	lines = []
	for i, r in enumerate(result["ranking"][:limit]):
		line = "`" + str(i + 1).rjust(2) + "` **" + r["ticker"] + "** " + _pct(r["probability"], False)
		if result["direction"] == "up":
			line += " · " + str(r["bull_score"]) + " sig"
		if r["qualifies"]:
			line += " ✅"
		lines.append(line)
	return lines


def _stat_line(direction, stats):
	icon = swing.DIRECTIONS[direction]["icon"]
	if direction == "up":
		return (icon + " Upswing picks reached their target **" + _pct(stats["precision"], False) + "** of the time (a random stock: " + _pct(stats["base_rate"], False) + "), "
			+ "averaging **" + _pct(stats["avg_return"]) + "** each.")
	return (icon + " The dip came **" + _pct(stats["fill_rate"], False) + "** of the time. When it did, buying it averaged **" + _pct(stats["dip_return"]) + "** "
		+ "and **" + _pct(stats["dip_win_rate"], False) + "** ended in profit (buying any stock's dip: " + _pct(stats["base_dip_return"]) + ", " + _pct(stats["base_dip_win_rate"], False) + ").")


def _verdict(direction, result):
	"""
	One line per section naming the stocks: the picks if any qualify, otherwise
	the nearest candidates flagged as watchlist-only. Never just "none".
	"""
	info = swing.DIRECTIONS[direction]
	if result["picks"]:
		names = ", ".join("**" + _stock_label(p["ticker"]) + "**" for p in result["picks"])
		return info["icon"] + " " + info["label"] + ": ✅ " + names
	if result["watchlist"]:
		names = ", ".join("**" + _stock_label(w["ticker"]) + "**" for w in result["watchlist"])
		return info["icon"] + " " + info["label"] + ": 👀 " + names + " *(watchlist, below the confidence bar)*"
	return info["icon"] + " " + info["label"] + ": no candidates"


def build_picks_embed(results, ranking=False):
	"""
	Embed for {direction: scan result}. ranking=True lists stocks by chance
	instead of the picks and watchlist.
	"""
	first = next(iter(results.values()))
	horizon = first["horizon"]
	hz = swing.HORIZONS[horizon]
	dirs = list(results)
	pct = "{:.1f}".format(hz["threshold"] * 100) + "%"

	if len(dirs) == 1:
		info = swing.DIRECTIONS[dirs[0]]
		title = info["icon"] + " " + hz["label"] + " " + info["label"] + " Suggestions"
	else:
		title = "📊 " + hz["label"] + " Stock Suggestions"

	def _subject(d, named):
		"""("TCI and TGP are", note) naming the section's stocks, or a generic subject."""
		r = results[d]
		stocks = r["picks"] or r["watchlist"]
		if not named or not stocks:
			return ("Picks", "are", "")
		labels = ["**" + _stock_label(s["ticker"]) + "**" for s in stocks]
		joined = labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " and " + labels[-1]
		note = "" if r["picks"] else " *(watchlist only, below the confidence bar)*"
		return (joined, "is" if len(labels) == 1 else "are", note)

	def _meaning(named):
		"""What each section means, tied to the close the analysis was run on."""
		lines = []
		if "up" in dirs:
			r = results["up"]
			who, verb, note = _subject("up", named)
			line = "📈 **Upswing**: " + who + " " + verb + " expected to rise at least " + pct + " by " + _deadline(r["target_day"])
			# Watchlist stocks are there precisely because they lack the signals
			if r["min_signals"] and (r["picks"] or not named):
				line += ", confirmed by " + str(r["min_signals"]) + "+ chart signals"
			lines.append(line + "." + note)
		if "dip" in dirs:
			r = results["dip"]
			who, verb, note = _subject("dip", named)
			lines.append("📉 **Buy the Dip**: " + who + " " + verb + " expected to fall " + pct + " by " + _deadline(r["target_day"])
				+ ", then recover above the " + _day(first["as_of"]) + " close by " + _deadline(r["recover_day"]) + "." + note)
		return "\n".join(lines)

	meaning = _meaning(named=not ranking)

	if ranking:
		desc = "Based on closing prices on **" + _day(first["as_of"]) + "**.\n" + meaning
	else:
		# Actionable picks first; the closing-day context goes to the bottom
		desc = "**Today's picks:**\n" + "\n".join(_verdict(d, results[d]) for d in dirs)
	embed = discord.Embed(title=title, description=desc.strip())
	embed.color = discord.Color.blue()
	embed.set_thumbnail(url=config.stonks_png)

	if ranking:
		if len(dirs) == 1:
			# One kind: every stock across two columns
			lines = _ranking_lines(results[dirs[0]], len(results[dirs[0]]["ranking"]))
			half = (len(lines) + 1) // 2
			embed.add_field(name="Chance of the move:", value="\n".join(lines[:half]) or "-", inline=True)
			embed.add_field(name="​", value="\n".join(lines[half:]) or "-", inline=True)
		else:
			for d in dirs:
				info = swing.DIRECTIONS[d]
				embed.add_field(name=info["icon"] + " " + info["label"] + " (top 15):", value="\n".join(_ranking_lines(results[d], 15)) or "-", inline=True)
	else:
		for d in dirs:
			info = swing.DIRECTIONS[d]
			result = results[d]
			# Trailing zero-width line separates entries; Discord trims plain trailing newlines
			render = lambda item, res, f=(_up_value if d == "up" else _dip_value): f(item, res) + "\n​"
			for i, pick in enumerate(result["picks"]):
				embed.add_field(name=info["icon"] + " " + info["label"] + " #" + str(i + 1) + ": " + _stock_label(pick["ticker"]), value=render(pick, result), inline=False)
			if not result["picks"]:
				for item in result["watchlist"]:
					# The shortfall note replaces the zero-width spacer above the name line
					value = "*Not a recommendation yet: " + "; ".join(item["shortfall"]) + ".*\n" + render(item, result).replace("​\n", "\n", 1)
					embed.add_field(name="👀 " + info["label"] + " watchlist: " + _stock_label(item["ticker"]), value=value, inline=False)
		embed.add_field(name="Based on the " + _day(first["as_of"]) + " close:", value=meaning, inline=False)

	stat_lines = []
	period = None
	for d in dirs:
		stats = results[d].get("stats")
		if stats and stats.get("n_picks"):
			period = stats["from"] + " to " + stats["to"]
			stat_lines.append(_stat_line(d, stats))
	if stat_lines:
		embed.add_field(name="How these picks did over the past year (" + period + "):", value="\n".join(stat_lines), inline=False)

	tips = []
	if "up" in dirs:
		tips.append("📈 Upswing: a buy at today's price.")
	if "dip" in dirs:
		tips.append("📉 Buy the Dip: set a buy order at the buy price; the dip only comes about 1 in 3 times, so if it doesn't, skip it.")
	tips.append("Watchlist stocks are close but don't meet the bar. /suggest view:Track Record shows how past picks did. This bot is not sound advice.")
	embed.set_footer(text=" ".join(tips))
	return embed


def _up_summary(graded):
	n = len(graded)
	closed = sum(r[5] for r in graded)
	touched = sum(r[6] for r in graded)
	higher = sum(1 for r in graded if r[7] > 0)
	avg_ret = sum(r[7] for r in graded) / n
	return (
		"Closed at target: **" + str(closed) + "/" + str(n) + "** (" + _pct(closed / n, False) + ")\n"
		"Touched target: **" + str(touched) + "/" + str(n) + "** (" + _pct(touched / n, False) + ")\n"
		"Closed higher: **" + _pct(higher / n, False) + "** · Avg return: **" + _pct(avg_ret) + "**"
	)


def _dip_summary(graded):
	n = len(graded)
	filled = [r for r in graded if r[6]]
	value = "Dip came: **" + str(len(filled)) + "/" + str(n) + "** (" + _pct(len(filled) / n, False) + ")"
	if filled:
		recovered = sum(r[5] for r in filled)
		profit = sum(1 for r in filled if r[7] > 0)
		avg_ret = sum(r[7] for r in filled) / len(filled)
		value += ("\nOf those, recovered to target: **" + str(recovered) + "/" + str(len(filled)) + "** · in profit: **" + _pct(profit / len(filled), False) + "**"
			"\nAvg return from the buy price: **" + _pct(avg_ret) + "**")
	return value


def _result_line(direction, row):
	ticker, as_of, entry, target, prob, closed_hit, touched_hit, final_ret, best_ret = row
	icon = swing.DIRECTIONS[direction]["icon"]
	if direction == "up":
		mark = "✅" if closed_hit else ("🟡" if touched_hit else "❌")
		return mark + icon + " " + _tct(as_of) + " **" + ticker + "** " + _pct(final_ret) + " (best " + _pct(best_ret) + ")"
	if not touched_hit:
		return "⏭️" + icon + " " + _tct(as_of) + " **" + ticker + "** no dip, skipped (" + _pct(final_ret) + " from close)"
	mark = "✅" if closed_hit else ("🟡" if final_ret > 0 else "❌")
	return mark + icon + " " + _tct(as_of) + " **" + ticker + "** bought " + _money(target) + " → " + _pct(final_ret)


def build_record_embed(horizon, direction="both", days=90):
	hz = swing.HORIZONS[horizon]
	dirs = _directions(direction)
	since = int(time.time()) - days * 86400

	label = "Stock" if len(dirs) > 1 else swing.DIRECTIONS[dirs[0]]["label"]
	embed = discord.Embed(title=hz["label"] + " " + label + " Suggestions: Track Record", description="Last **" + str(days) + "** days")
	embed.color = discord.Color.purple()
	embed.set_thumbnail(url=config.stonks_png)

	graded_all = []
	open_all = []
	for d in dirs:
		rows = tsl_lib.db.suggestion_get_record(horizon, d, since)
		graded = [r for r in rows if r[5] is not None]
		graded_all += [(d, r) for r in graded]
		open_all += [(d, r) for r in rows if r[5] is None]
		if graded:
			info = swing.DIRECTIONS[d]
			summary = _up_summary(graded) if d == "up" else _dip_summary(graded)
			embed.add_field(name=info["icon"] + " " + info["label"] + " (" + str(len(graded)) + " graded):", value=summary, inline=False)

	if not graded_all and not open_all:
		embed.add_field(name="No History Yet:", value="No suggestions have been posted for this horizon in that period.", inline=False)
		return embed

	if graded_all:
		graded_all.sort(key=lambda x: x[1][1], reverse=True)
		embed.add_field(name="Recent Results:", value="\n".join(_result_line(d, r) for d, r in graded_all[:12]), inline=False)

	if open_all:
		open_all.sort(key=lambda x: x[1][1], reverse=True)
		lines = []
		for d, (ticker, as_of, entry, target, prob, *_) in open_all[:10]:
			_, live = _live_stock(ticker)
			icon = swing.DIRECTIONS[d]["icon"]
			if d == "up":
				line = "⏳" + icon + " " + _tct(as_of) + " **" + ticker + "** " + _money(entry) + " → " + _money(target)
			else:
				line = "⏳" + icon + " " + _tct(as_of) + " **" + ticker + "** buy price " + _money(target)
			if live:
				line += " · now " + _money(live)
			lines.append(line)
		embed.add_field(name="Still Open:", value="\n".join(lines), inline=False)

	embed.set_footer(text="📈 ✅ closed at target · 🟡 touched it · ❌ missed | 📉 ✅ dip bought and recovered · 🟡 in profit · ❌ loss · ⏭️ no dip")
	return embed


async def post_suggestions(self, embed):
	"""Send to every configured suggestion channel. Returns how many succeeded."""
	sent = 0
	for channel_id in config.suggestion_channels["id"]:
		try:
			channel = await self.fetch_channel(channel_id)
			await channel.send(embed=embed)
			sent += 1
		except discord.DiscordException:
			tsl_lib.util.write_log("[WARNING] Could not post suggestions to channel " + str(channel_id), tsl_lib.util.current_date())
	return sent


def prepare_suggestions(horizon, record=True):
	"""
	Everything the scheduled post does short of sending it: grade old picks,
	scan both kinds, optionally record the new picks, and build the embed.
	Shared by the scheduler and /force_suggestions so a forced run tests the
	real path. CPU heavy - call from a worker thread.
	"""
	grade_open_suggestions()
	results = run_scan(horizon, "both")
	if record:
		record_picks(results)
	return results, build_picks_embed(results)


def make_suggestions(self, horizon):
	"""
	Scheduled entry point. Runs on the scheduler thread since training is CPU
	heavy, then hands the embed to the bot loop to post.
	"""
	_, embed = prepare_suggestions(horizon, record=True)
	asyncio.run_coroutine_threadsafe(self.post_suggestions(embed), self.loop)
