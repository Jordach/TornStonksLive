"""
Automated longer-term suggestions: daily (+0.5% after 3 days) and weekly
(+1% after 7 days) upswing picks. The analysis lives in
tsl_core/analysis/upswing.py; this module turns it into Discord embeds, posts
scheduled picks and grades past picks so the bot keeps an honest track record.
"""
import asyncio
import math
import time
from datetime import datetime, timezone

import discord

import tsl_core.functions as tsl_lib
import tsl_config.config as config

upswing = tsl_lib.analysis.upswing


def _tct(ts):
	return datetime.fromtimestamp(int(ts), timezone.utc).strftime("%d/%m/%y")


def _pct(val, signed=True):
	if val is None or (isinstance(val, float) and math.isnan(val)):
		return "n/a"
	return ("{:+.2f}" if signed else "{:.1f}").format(val * 100) + "%"


def _live_stock(ticker):
	"""(name, live price) from the Tornsy feed, falling back to the ticker if missing."""
	try:
		for data in config.json_data["data"]:
			if data["stock"] == ticker.upper():
				return data["name"], float(data["price"])
	except (TypeError, KeyError):
		pass
	return ticker.upper(), None


def run_scan(horizon, top_n=3):
	"""CPU heavy (training once a day) - call from a worker thread, not the event loop."""
	return upswing.scan(horizon, tsl_lib.stock_lut, top_n=top_n)


def grade_open_suggestions():
	"""Fill in outcomes for any posted suggestion whose window has closed."""
	graded = 0
	for row_id, horizon, ticker, as_of, entry, target in tsl_lib.db.suggestion_get_open():
		try:
			res = upswing.outcome(ticker, as_of, horizon, entry, target)
		except Exception:
			continue
		if res is None:
			continue
		tsl_lib.db.suggestion_set_outcome(row_id, *res)
		graded += 1
	return graded


def record_picks(result):
	for pick in result["picks"]:
		tsl_lib.db.suggestion_record(result["horizon"], pick["ticker"], result["as_of"], pick["close"], pick["target"], pick["probability"])


def build_picks_embed(result, ranking=False):
	"""Embed for a scan result. ranking=True lists every stock instead of only qualifying picks."""
	hz = upswing.HORIZONS[result["horizon"]]
	base = result["base_rate"]

	embed = discord.Embed(
		title=hz["label"] + " Upswing Suggestions",
		description=(
			"Target: **" + hz["desc"] + "** from the **" + _tct(result["as_of"]) + "** daily close.\n"
			"Window closes: **00:00 " + _tct(result["expires"]) + " TCT**\n"
			"Base rate (any stock hitting this): **" + _pct(base, False) + "**"
		),
	)
	embed.color = discord.Color.blue()
	embed.set_thumbnail(url=config.stonks_png)

	if ranking:
		lines = []
		for i, r in enumerate(result["ranking"]):
			flag = " ✅" if r["lift"] >= result["min_lift"] else ""
			lines.append("`" + str(i + 1).rjust(2) + "` **" + r["ticker"] + "** " + _pct(r["probability"], False) + " ({:.2f}×)".format(r["lift"]) + flag)
		# Embed fields cap at 1024 chars; 35 stocks fit comfortably in two columns
		half = (len(lines) + 1) // 2
		embed.add_field(name="Chance of Target:", value="\n".join(lines[:half]) or "-", inline=True)
		embed.add_field(name="​", value="\n".join(lines[half:]) or "-", inline=True)
	elif result["picks"]:
		for i, pick in enumerate(result["picks"]):
			name, live = _live_stock(pick["ticker"])
			value = "Entry (close): **$" + "{:,.2f}".format(pick["close"]) + "**"
			if live is not None:
				value += " · Now: **$" + "{:,.2f}".format(live) + "**"
			value += "\nTarget: **$" + "{:,.2f}".format(pick["target"]) + "**"
			if live is not None and live >= pick["target"]:
				value += " (already reached)"
			value += "\nChance: **" + _pct(pick["probability"], False) + "** ({:.1f}× base)".format(pick["lift"])
			value += " · ATR: " + "{:.2f}".format(pick["atr_pct"]) + "%"
			value += "\n*" + pick["notes"] + "*"
			embed.add_field(name=str(i + 1) + ". " + name + " (" + pick["ticker"] + ")", value=value, inline=False)
	else:
		closest = result["ranking"][0] if result["ranking"] else None
		msg = "No stock is at least **{:.1f}×** more likely than the base rate today, so nothing is being suggested.".format(result["min_lift"])
		if closest:
			msg += "\nClosest: **" + closest["ticker"] + "** at " + _pct(closest["probability"], False) + " ({:.2f}×).".format(closest["lift"])
		embed.add_field(name="No Strong Setups:", value=msg, inline=False)

	stats = result.get("stats")
	if stats:
		embed.add_field(
			name="Model Backtest (" + stats["from"] + " - " + stats["to"] + ", unseen data):",
			value=(
				"Top 3 picks each day hit target **" + _pct(stats["top3_precision"], False) + "** of the time vs **" + _pct(stats["base_rate"], False) + "** for any stock.\n"
				"Avg return at window close: **" + _pct(stats["top3_avg_return"]) + "** vs **" + _pct(stats["base_avg_return"]) + "** · "
				"Finished higher: **" + _pct(stats["top3_win_rate"], False) + "** · Touched target at some point: **" + _pct(stats["top3_touch_rate"], False) + "**"
			),
			inline=False,
		)
	embed.set_footer(text="Picks are measured at the close of the window, not intraday spikes. Use /suggest record to see how past picks did. This bot is not sound advice.")
	return embed


def build_record_embed(horizon, days=90):
	hz = upswing.HORIZONS[horizon]
	since = int(time.time()) - days * 86400
	rows = tsl_lib.db.suggestion_get_record(horizon, since)

	embed = discord.Embed(title=hz["label"] + " Suggestions: Track Record", description="Target: **" + hz["desc"] + "** · last **" + str(days) + "** days")
	embed.color = discord.Color.purple()
	embed.set_thumbnail(url=config.stonks_png)

	graded = [r for r in rows if r[5] is not None]
	open_rows = [r for r in rows if r[5] is None]
	if not rows:
		embed.add_field(name="No History Yet:", value="No suggestions have been posted for this horizon in that period.", inline=False)
		return embed

	if graded:
		n = len(graded)
		closed = sum(r[5] for r in graded)
		touched = sum(r[6] for r in graded)
		avg_ret = sum(r[7] for r in graded) / n
		wins = sum(1 for r in graded if r[7] > 0)
		embed.add_field(
			name="Summary (" + str(n) + " graded):",
			value=(
				"Closed at target: **" + str(closed) + "/" + str(n) + "** (" + _pct(closed / n, False) + ")\n"
				"Touched target: **" + str(touched) + "/" + str(n) + "** (" + _pct(touched / n, False) + ")\n"
				"Finished higher: **" + _pct(wins / n, False) + "** · Avg return: **" + _pct(avg_ret) + "**"
			),
			inline=False,
		)
		lines = []
		for ticker, as_of, entry, target, prob, closed_hit, touched_hit, final_ret, best_ret in graded[:12]:
			icon = "✅" if closed_hit else ("🟡" if touched_hit else "❌")
			lines.append(icon + " " + _tct(as_of) + " **" + ticker + "** " + _pct(final_ret) + " (best " + _pct(best_ret) + ")")
		embed.add_field(name="Recent Results:", value="\n".join(lines), inline=False)

	if open_rows:
		lines = []
		for ticker, as_of, entry, target, prob, *_ in open_rows[:10]:
			_, live = _live_stock(ticker)
			now = (" · now " + _pct(live / entry - 1)) if live else ""
			lines.append("⏳ " + _tct(as_of) + " **" + ticker + "** $" + "{:,.2f}".format(entry) + " → $" + "{:,.2f}".format(target) + now)
		embed.add_field(name="Still Open:", value="\n".join(lines), inline=False)

	embed.set_footer(text="✅ closed at/above target · 🟡 touched target but closed below · ❌ missed")
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
	scan, optionally record the new picks, and build the embed. Shared by the
	scheduler and /force_suggestions so a forced run tests the real path.
	CPU heavy - call from a worker thread.
	"""
	grade_open_suggestions()
	result = run_scan(horizon)
	if record:
		record_picks(result)
	return result, build_picks_embed(result)


def make_suggestions(self, horizon):
	"""
	Scheduled entry point. Runs on the scheduler thread since training is CPU
	heavy, then hands the embed to the bot loop to post.
	"""
	_, embed = prepare_suggestions(horizon, record=True)
	asyncio.run_coroutine_threadsafe(self.post_suggestions(embed), self.loop)
