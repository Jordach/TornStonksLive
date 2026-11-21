"""
Automated longer-term suggestions at daily (0.5% move after 3 days) and weekly
(1% move after 7 days) scales, in both directions: upswings for stocks likely
to rise and downswings for stocks likely to fall. The analysis lives in
tsl_core/analysis/swing.py; this module turns it into Discord embeds, posts
scheduled picks and grades past picks so the bot keeps an honest track record.
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


def _directions(direction):
	return list(swing.DIRECTIONS) if direction in (None, "both") else [direction]


def run_scan(horizon, direction="both", top_n=3):
	"""
	{direction: scan result} for one or both directions. CPU heavy (training
	once a day) - call from a worker thread, not the event loop.
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
			tsl_lib.db.suggestion_record(result["horizon"], result["direction"], pick["ticker"], result["as_of"], pick["close"], pick["target"], pick["probability"])


def _pick_value(pick):
	name, live = _live_stock(pick["ticker"])
	value = _money(pick["close"]) + " → target **" + _money(pick["target"]) + "**"
	if live is not None:
		value += "\nNow " + _money(live) + " (" + _pct(live / pick["close"] - 1) + ")"
		reached = (live >= pick["target"]) if pick["target"] > pick["close"] else (live <= pick["target"])
		if reached:
			value += " · target already reached"
	value += "\nChance **" + _pct(pick["probability"], False) + "** ({:.1f}× usual)".format(pick["lift"])
	value += " · typical day ±" + "{:.2f}".format(pick["atr_pct"]) + "%"
	value += "\n*" + pick["notes"] + "*"
	return name, value


def _ranking_lines(result, limit):
	lines = []
	for i, r in enumerate(result["ranking"][:limit]):
		flag = " ✅" if r["lift"] >= result["min_lift"] else ""
		lines.append("`" + str(i + 1).rjust(2) + "` **" + r["ticker"] + "** " + _pct(r["probability"], False) + " ({:.2f}×)".format(r["lift"]) + flag)
	return lines


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
		title = swing.DIRECTIONS[dirs[0]]["icon"] + " " + hz["label"] + " " + swing.DIRECTIONS[dirs[0]]["label"] + " Suggestions"
	else:
		title = "📊 " + hz["label"] + " Swing Suggestions"

	desc = "From the **" + _tct(first["as_of"]) + "** daily close · window ends **00:00 " + _tct(first["expires"]) + " TCT**\n"
	for d in dirs:
		info = swing.DIRECTIONS[d]
		desc += info["icon"] + " " + info["label"] + ": close **" + swing.describe(horizon, d) + "**"
		desc += " (usually " + _pct(results[d]["base_rate"], False) + " of stocks)\n"

	embed = discord.Embed(title=title, description=desc.strip())
	embed.color = discord.Color.blue()
	embed.set_thumbnail(url=config.stonks_png)

	if ranking:
		if len(dirs) == 1:
			# One direction: every stock across two columns
			lines = _ranking_lines(results[dirs[0]], len(results[dirs[0]]["ranking"]))
			half = (len(lines) + 1) // 2
			embed.add_field(name="Chance of Move:", value="\n".join(lines[:half]) or "-", inline=True)
			embed.add_field(name="​", value="\n".join(lines[half:]) or "-", inline=True)
		else:
			# Both: the top of each list side by side
			for d in dirs:
				info = swing.DIRECTIONS[d]
				embed.add_field(name=info["icon"] + " Most Likely " + info["label"] + "s:", value="\n".join(_ranking_lines(results[d], 15)) or "-", inline=True)
	else:
		for d in dirs:
			info = swing.DIRECTIONS[d]
			result = results[d]
			if result["picks"]:
				for i, pick in enumerate(result["picks"]):
					name, value = _pick_value(pick)
					embed.add_field(name=info["icon"] + " " + str(i + 1) + ". " + name + " (" + pick["ticker"] + ")", value=value, inline=False)
			else:
				msg = "Nothing stands out today (needs **{:.2f}×** the usual chance).".format(result["min_lift"])
				if result["ranking"]:
					closest = result["ranking"][0]
					msg += "\nClosest: **" + closest["ticker"] + "** " + _pct(closest["probability"], False) + " ({:.2f}×)".format(closest["lift"])
				embed.add_field(name=info["icon"] + " " + info["label"] + "s:", value=msg, inline=False)

	stat_lines = []
	period = None
	for d in dirs:
		stats = results[d].get("stats")
		if not stats:
			continue
		period = stats["from"] + " - " + stats["to"]
		moved = "higher" if swing.DIRECTIONS[d]["sign"] > 0 else "lower"
		stat_lines.append(
			swing.DIRECTIONS[d]["icon"] + " Top picks hit **" + _pct(stats["top3_precision"], False) + "** vs **" + _pct(stats["base_rate"], False) + "** usual"
			+ " · avg **" + _pct(stats["top3_avg_return"]) + "**"
			+ " · closed " + moved + " " + _pct(stats["top3_direction_rate"], False)
		)
	if stat_lines:
		embed.add_field(name="Backtest on unseen data (" + period + "):", value="\n".join(stat_lines), inline=False)

	footer = "Measured at the close of the window, not intraday spikes."
	if "up" in dirs and "down" in dirs:
		footer = "📈 Upswings: candidates to buy. 📉 Downswings: consider selling, or wait to buy cheaper. " + footer
	footer += " See /suggest view:Track Record for past results. This bot is not sound advice."
	embed.set_footer(text=footer)
	return embed


def _record_summary(graded, direction):
	n = len(graded)
	closed = sum(r[5] for r in graded)
	touched = sum(r[6] for r in graded)
	sign = swing.DIRECTIONS[direction]["sign"]
	right_way = sum(1 for r in graded if r[7] * sign > 0)
	avg_ret = sum(r[7] for r in graded) / n
	moved = "higher" if sign > 0 else "lower"
	return (
		"Closed at target: **" + str(closed) + "/" + str(n) + "** (" + _pct(closed / n, False) + ")\n"
		"Touched target: **" + str(touched) + "/" + str(n) + "** (" + _pct(touched / n, False) + ")\n"
		"Closed " + moved + ": **" + _pct(right_way / n, False) + "** · Avg return: **" + _pct(avg_ret) + "**"
	)


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
		info = swing.DIRECTIONS[d]
		if graded:
			embed.add_field(name=info["icon"] + " " + info["label"] + "s (" + str(len(graded)) + " graded, target " + swing.describe(horizon, d) + "):", value=_record_summary(graded, d), inline=False)

	if not graded_all and not open_all:
		embed.add_field(name="No History Yet:", value="No suggestions have been posted for this horizon in that period.", inline=False)
		return embed

	if graded_all:
		graded_all.sort(key=lambda x: x[1][1], reverse=True)
		lines = []
		for d, (ticker, as_of, entry, target, prob, closed_hit, touched_hit, final_ret, best_ret) in graded_all[:12]:
			icon = "✅" if closed_hit else ("🟡" if touched_hit else "❌")
			lines.append(icon + swing.DIRECTIONS[d]["icon"] + " " + _tct(as_of) + " **" + ticker + "** " + _pct(final_ret) + " (best " + _pct(best_ret) + ")")
		embed.add_field(name="Recent Results:", value="\n".join(lines), inline=False)

	if open_all:
		open_all.sort(key=lambda x: x[1][1], reverse=True)
		lines = []
		for d, (ticker, as_of, entry, target, prob, *_) in open_all[:10]:
			_, live = _live_stock(ticker)
			now = (" · now " + _pct(live / entry - 1)) if live else ""
			lines.append("⏳" + swing.DIRECTIONS[d]["icon"] + " " + _tct(as_of) + " **" + ticker + "** " + _money(entry) + " → " + _money(target) + now)
		embed.add_field(name="Still Open:", value="\n".join(lines), inline=False)

	embed.set_footer(text="✅ closed at/past target · 🟡 touched target but closed short · ❌ missed")
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
	scan both directions, optionally record the new picks, and build the embed.
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
