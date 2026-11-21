"""
Automated longer-term suggestions at daily and weekly scales:

	📈 Upswing     - TA-backed stocks expected to rise soon (buy now).
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


def _tct(ts):
	return datetime.fromtimestamp(int(ts), timezone.utc).strftime("%d/%m/%y")


def _short_date(ts):
	return datetime.fromtimestamp(int(ts), timezone.utc).strftime("%d/%m")


def _pct(val, signed=True):
	if val is None or (isinstance(val, float) and math.isnan(val)):
		return "n/a"
	return ("{:+.2f}" if signed else "{:.0f}").format(val * 100) + "%"


def _money(val):
	return "$" + "{:,.2f}".format(val)


def _lift(val):
	"""Truncate rather than round, so a 1.749x stock never shows as meeting a 1.75x bar."""
	return "{:.2f}×".format(math.floor(val * 100) / 100)


def _signals(n):
	return str(n) + (" signal" if n == 1 else " signals")


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


def _up_value(pick, result):
	_, live = _live_stock(pick["ticker"])
	value = _stock_heading(pick["ticker"])
	value += "\nBuy near **" + _money(pick["close"]) + "** → target **" + _money(pick["target"]) + "** by " + _short_date(result["expires"])
	if live is not None:
		value += "\nNow " + _money(live) + " (" + _pct(live / pick["close"] - 1) + ")"
		if live >= pick["target"]:
			value += " · target already reached"
	value += "\n**" + str(pick["bull_score"]) + "/" + str(len(swing.BULL_SIGNALS)) + " TA signals:** " + " · ".join(pick["signals"])
	if pick["context"]:
		value += "\nContext: " + " · ".join(pick["context"])
	value += "\nChance **" + _pct(pick["probability"], False) + "** (" + _lift(pick["lift"]) + " usual)"
	value += " · typical day ±" + "{:.2f}".format(pick["atr_pct"]) + "%"
	return value


def _dip_value(pick, result):
	_, live = _live_stock(pick["ticker"])
	value = _stock_heading(pick["ticker"])
	value += "\nBuy order at **" + _money(pick["buy_zone"]) + "** (" + _pct(pick["buy_zone"] / pick["close"] - 1) + ") until " + _short_date(result["dip_deadline"])
	value += "\nRecovery target **" + _money(pick["target"]) + "** by " + _short_date(result["expires"])
	if live is not None:
		value += "\nNow " + _money(live)
		if live <= pick["buy_zone"]:
			value += " · ✅ in the buy zone"
		else:
			value += " · " + "{:.2f}".format((live / pick["buy_zone"] - 1) * 100) + "% above the buy zone"
	if pick["signals"]:
		value += "\nDrop signs: " + " · ".join(pick["signals"])
	value += "\nSetup: " + " · ".join(pick["context"])
	value += "\nChance of dip + recovery **" + _pct(pick["probability"], False) + "** (" + _lift(pick["lift"]) + " usual)"
	return value


def _ranking_lines(result, limit):
	lines = []
	for i, r in enumerate(result["ranking"][:limit]):
		line = "`" + str(i + 1).rjust(2) + "` **" + r["ticker"] + "** " + _pct(r["probability"], False) + " (" + _lift(r["lift"]) + ")"
		if result["direction"] == "up":
			line += " " + str(r["bull_score"]) + "sig"
		if r["qualifies"]:
			line += " ✅"
		lines.append(line)
	return lines


def _stat_line(direction, stats):
	icon = swing.DIRECTIONS[direction]["icon"]
	if direction == "up":
		return (icon + " Picks hit **" + _pct(stats["precision"], False) + "** vs **" + _pct(stats["base_rate"], False) + "** usual"
			+ " · avg **" + _pct(stats["avg_return"]) + "** vs " + _pct(stats["base_avg_return"])
			+ " · closed higher " + _pct(stats["closed_higher"], False))
	return (icon + " Dip came **" + _pct(stats["fill_rate"], False) + "** of the time; bought there: avg **" + _pct(stats["dip_return"]) + "**, "
		+ "**" + _pct(stats["dip_win_rate"], False) + "** in profit by the recovery day (buying any stock's dip: "
		+ _pct(stats["base_dip_return"]) + ", " + _pct(stats["base_dip_win_rate"], False) + ")")


def build_picks_embed(results, ranking=False):
	"""
	Embed for {direction: scan result}. ranking=True lists stocks by chance
	instead of only the qualifying picks.
	"""
	first = next(iter(results.values()))
	horizon = first["horizon"]
	hz = swing.HORIZONS[horizon]
	dirs = list(results)

	if len(dirs) == 1:
		info = swing.DIRECTIONS[dirs[0]]
		title = info["icon"] + " " + hz["label"] + " " + info["label"] + " Suggestions"
	else:
		title = "📊 " + hz["label"] + " Swing Suggestions"

	desc = "From the **" + _tct(first["as_of"]) + "** daily close\n"
	for d in dirs:
		info = swing.DIRECTIONS[d]
		desc += info["icon"] + " **" + info["label"] + "**: " + swing.describe(horizon, d)
		if d == "up" and results[d]["min_signals"]:
			desc += ", backed by " + str(results[d]["min_signals"]) + "+ TA signals"
		desc += " (usually " + _pct(results[d]["base_rate"], False) + " of stocks)\n"

	embed = discord.Embed(title=title, description=desc.strip())
	embed.color = discord.Color.blue()
	embed.set_thumbnail(url=config.stonks_png)

	if ranking:
		if len(dirs) == 1:
			# One kind: every stock across two columns
			lines = _ranking_lines(results[dirs[0]], len(results[dirs[0]]["ranking"]))
			half = (len(lines) + 1) // 2
			embed.add_field(name="Chance:", value="\n".join(lines[:half]) or "-", inline=True)
			embed.add_field(name="​", value="\n".join(lines[half:]) or "-", inline=True)
		else:
			for d in dirs:
				info = swing.DIRECTIONS[d]
				embed.add_field(name=info["icon"] + " " + info["label"] + " (top 15):", value="\n".join(_ranking_lines(results[d], 15)) or "-", inline=True)
	else:
		for d in dirs:
			info = swing.DIRECTIONS[d]
			result = results[d]
			if result["picks"]:
				for i, pick in enumerate(result["picks"]):
					value = _up_value(pick, result) if d == "up" else _dip_value(pick, result)
					title = info["icon"] + " " + info["label"] + " #" + str(i + 1) + " · " + pick["ticker"]
					name = _stock_name(pick["ticker"])
					if name != pick["ticker"]:
						title += " · " + name
					embed.add_field(name=title, value=value, inline=False)
			else:
				need = "**" + _lift(result["min_lift"]) + "** the usual chance"
				if d == "up" and result["min_signals"]:
					need += " and " + str(result["min_signals"]) + "+ TA signals"
				msg = "Nothing qualifies today (needs " + need + ")."
				if result["ranking"]:
					closest = result["ranking"][0]
					msg += "\nClosest: " + _stock_heading(closest["ticker"]) + " · " + _pct(closest["probability"], False) + " (" + _lift(closest["lift"])
					msg += (", " + _signals(closest["bull_score"]) + ")" if d == "up" else ")")
				embed.add_field(name=info["icon"] + " " + info["label"] + ":", value=msg, inline=False)

	stat_lines = []
	period = None
	for d in dirs:
		stats = results[d].get("stats")
		if stats and stats.get("n_picks"):
			period = stats["from"] + " - " + stats["to"]
			stat_lines.append(_stat_line(d, stats))
	if stat_lines:
		embed.add_field(name="Backtest on unseen data (" + period + "):", value="\n".join(stat_lines), inline=False)

	tips = []
	if "up" in dirs:
		tips.append("📈 Upswings: TA-backed buys at today's price.")
	if "dip" in dirs:
		tips.append("📉 Buy the Dip: set a buy order at the buy zone; the dip only comes about 1 in 3 times, so if it doesn't, skip it.")
	tips.append("Results are measured at the close, not intraday spikes. /suggest view:Track Record shows past picks. This bot is not sound advice.")
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
			"\nAvg return from buy zone: **" + _pct(avg_ret) + "**")
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

	label = "Swing" if len(dirs) > 1 else swing.DIRECTIONS[dirs[0]]["label"]
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
				line = "⏳" + icon + " " + _tct(as_of) + " **" + ticker + "** buy zone " + _money(target)
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
