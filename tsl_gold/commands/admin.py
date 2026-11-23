import asyncio
import datetime
import time
import discord
from discord import app_commands
import tsl_core.functions as tsl_lib
import tsl_config.config as config

client = config.client


def _is_admin(interaction: discord.Interaction) -> bool:
	"""Check if the invoking user is in the bot_admins list."""
	return int(interaction.user.id) in config.bot_admins


async def _deny(interaction: discord.Interaction):
	"""Send a permission-denied ephemeral response."""
	embed = discord.Embed(title=":no_entry_sign: Permission Required :no_entry_sign:")
	embed.color = discord.Color.red()
	client.set_author_interaction(interaction, embed)
	embed.add_field(name="Details:", value="You are not authorised to use this command.")
	await interaction.followup.send(embed=embed, ephemeral=True)


@client.tree.command(name="stop", description="Gracefully shuts down the bot.")
@app_commands.default_permissions(administrator=True)
async def stop(interaction: discord.Interaction):
	await interaction.response.defer(ephemeral=True)

	if not _is_admin(interaction):
		await _deny(interaction)
		return

	config.write_user_alerts()
	tsl_lib.util.stop_run_continously.set()

	embed = discord.Embed(title="")
	embed.color = discord.Color.orange()
	client.set_author_interaction(interaction, embed)
	embed.add_field(name="Shutting Down", value="User alerts saved. Goodbye! :wave:")
	await interaction.followup.send(embed=embed, ephemeral=True)

	tsl_lib.util.write_log("[ADMIN] Bot stopped by " + interaction.user.display_name + ".", tsl_lib.util.current_date())
	await client.close()


@client.tree.command(name="sync", description="Syncs the slash command tree to Discord.")
@app_commands.default_permissions(administrator=True)
async def sync(interaction: discord.Interaction):
	await interaction.response.defer(ephemeral=True)

	if not _is_admin(interaction):
		await _deny(interaction)
		return

	await client.tree.sync()

	embed = discord.Embed(title="")
	embed.color = discord.Color.green()
	client.set_author_interaction(interaction, embed)
	embed.add_field(name="Commands Synced", value="Slash command tree has been synced to Discord.")
	await interaction.followup.send(embed=embed, ephemeral=True)

	tsl_lib.util.write_log("[ADMIN] Command tree synced by " + interaction.user.display_name + ".", tsl_lib.util.current_date())
	print("Synced slash command tree to Discord.")

@client.tree.command(name="force_suggestions", description="Run the scheduled swing suggestions now, privately, here, or to the suggestion channels.")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
	horizon="Which scheduled post to run.",
	destination="Where to send it. Preview and This Channel are tests and are not tracked by default.",
	record="Save the picks to the track record. Defaults to on only for Suggestion Channels.",
)
@app_commands.choices(
	horizon=[
		app_commands.Choice(name="Daily (0.5% move after 3 days)", value="daily"),
		app_commands.Choice(name="Weekly (1% move after 7 days)", value="weekly"),
	],
	destination=[
		app_commands.Choice(name="Preview (only you can see it)", value="preview"),
		app_commands.Choice(name="This Channel", value="here"),
		app_commands.Choice(name="Suggestion Channels (live post)", value="channels"),
	],
)
async def force_suggestions(interaction: discord.Interaction, horizon: str = "daily", destination: str = "preview", record: bool = None):
	await interaction.response.defer(ephemeral=True)

	if not _is_admin(interaction):
		await _deny(interaction)
		return

	import tsl_bot.functions.suggest as suggest

	live = destination == "channels"
	# Outside the command channels a reply stays private, so "This Channel" becomes a preview
	downgraded = destination == "here" and config.private_reply(interaction)
	if downgraded:
		destination = "preview"
	if record is None:
		# Test runs shouldn't skew the track record unless explicitly asked to
		record = live

	status = discord.Embed(title="")
	client.set_author_interaction(interaction, status)
	try:
		# Same function the 00:05 TCT scheduler job uses
		results, picks_embed = await asyncio.to_thread(suggest.prepare_suggestions, horizon, record)
		if not live:
			picks_embed.title = "[Test] " + picks_embed.title

		if destination == "preview":
			await interaction.followup.send(embed=picks_embed, ephemeral=True)
			where = "you (preview" + ("; this isn't a command channel" if downgraded else "") + ")"
		elif destination == "here":
			await interaction.channel.send(embed=picks_embed)
			where = "this channel"
		else:
			sent = await client.post_suggestions(picks_embed)
			where = str(sent) + "/" + str(len(config.suggestion_channels["id"])) + " suggestion channel(s)"

		counts = ", ".join(str(len(r["picks"])) + " " + d for d, r in results.items())
		status.color = discord.Color.green()
		status.add_field(
			name="Suggestions Sent",
			value=horizon.capitalize() + " picks (" + counts + ") sent to " + where + ".\nTrack record: **" + ("recorded" if record else "not recorded") + "**",
		)
	except tsl_lib.analysis.swing.StaleDataError as e:
		status.color = discord.Color.orange()
		status.add_field(name="Data Not Ready", value=str(e)[:1000])
	except Exception as e:
		status.color = discord.Color.red()
		status.add_field(name="Failed", value=repr(e)[:1000])
	await interaction.followup.send(embed=status, ephemeral=True)

	tsl_lib.util.write_log("[ADMIN] " + horizon + " suggestions forced to " + destination + " (record=" + str(record) + ") by " + interaction.user.display_name + ".", tsl_lib.util.current_date())


def _utc(ts, fmt="%Y-%m-%d %H:%M"):
	return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime(fmt) if ts is not None else "-"


def _span(seconds):
	seconds = int(max(0, seconds))
	if seconds < 3600:
		return str(seconds // 60) + "m " + str(seconds % 60) + "s"
	return str(seconds // 3600) + "h " + str(seconds % 3600 // 60) + "m"


def _backfill_rows():
	"""(ticker, first_m1, last_m1, pending, error) for every stock. Runs off the event loop."""
	rows = []
	for ticker in tsl_lib.stock_lut:
		try:
			rows.append((ticker,) + tuple(tsl_lib.db.backfill_summary(ticker)) + (None,))
		except Exception as e:
			rows.append((ticker, None, None, [], repr(e)))
	return rows


def _backfill_embed(rows, state, enabled, now):
	"""Build the /backfill report from per-stock summaries and the backfill thread's state."""
	pending_stocks = [r[0] for r in rows if r[3]]
	embed = discord.Embed(title=":hourglass: Price History Backfill")

	if not enabled:
		embed.color = discord.Color.light_grey()
		status = "Off: `backfill=false` in features.conf, so missed prices aren't fetched from Tornsy."
	elif state.get("scanning"):
		embed.color = discord.Color.orange()
		status = "Checking stored history for gaps: stock " + str(state["position"]) + "/" + str(state["total"]) + " **" + str(state["ticker"]) + "**."
	elif state["running"]:
		embed.color = discord.Color.orange()
		status = "Running: stock " + str(state["position"]) + "/" + str(state["total"]) + " **" + str(state["ticker"]) + "**"
		if state["oldest"] is not None:
			status += ", " + "{:,}".format(state["minutes"]) + " minutes fetched, back to " + _utc(state["oldest"], "%Y-%m-%d")
		status += " (" + _span(now - state["stock_started"]) + " on this stock, " + _span(now - state["started"]) + " in all)."
	elif state["paused"]:
		embed.color = discord.Color.red()
		status = "Paused, Tornsy isn't responding: " + ", ".join(state["paused"]) + "."
		if state["retry_at"] is not None:
			status += " Retrying <t:" + str(int(state["retry_at"])) + ":R>."
	elif pending_stocks:
		embed.color = discord.Color.orange()
		status = "Not running; " + str(len(pending_stocks)) + " stock(s) still have missing minutes. They resume at the daily 03:30 UTC run or the next restart."
	else:
		embed.color = discord.Color.green()
		status = "Idle: no missing minutes."
		if state["finished"] is not None:
			status += " Last pass finished <t:" + str(int(state["finished"])) + ":R>."
	embed.add_field(name="Background backfill", value=status, inline=False)

	stored = [r for r in rows if r[1] is not None]
	if stored:
		def who(value, column):
			names = [r[0] for r in stored if r[column] == value]
			return ", ".join(names) if len(names) <= 4 else str(len(names)) + " stocks"
		earliest = min(r[1] for r in stored)
		latest_start = max(r[1] for r in stored)
		stalest = min(r[2] for r in stored)
		overview = (
			"Earliest first minute: **" + _utc(earliest) + "** (" + who(earliest, 1) + ")\n"
			"Latest first minute: **" + _utc(latest_start) + "** (" + who(latest_start, 1) + ")\n"
			"Oldest last minute: **" + _utc(stalest) + "** (" + who(stalest, 2) + ")"
		)
		missing = [r[0] for r in rows if r[1] is None and not r[4]]
		if missing:
			overview += "\nNo minutes stored yet: " + ", ".join(missing)
		embed.add_field(name="History (UTC)", value=overview, inline=False)

	lines = ["Stock".ljust(5) + " " + "First m1".ljust(10) + " " + "Last m1".ljust(16) + " Pending"]
	for ticker, first, last, pending, error in rows:
		if error:
			detail = "error: " + error
		elif not pending:
			detail = "-"
		else:
			ranges = [("start" if lo is None else _utc(lo, "%Y-%m-%d")) + ">" + ("now" if hi is None else _utc(hi, "%Y-%m-%d")) for lo, hi in pending]
			detail = ", ".join(ranges) if len(ranges) <= 2 else str(len(ranges)) + " ranges"
		lines.append(ticker.ljust(5) + " " + _utc(first, "%Y-%m-%d").ljust(10) + " " + _utc(last).ljust(16) + " " + detail)
	table = "\n".join(lines)
	if len(table) > 4080:
		table = table[:4077] + "..."
	embed.description = "```\n" + table + "\n```"
	return embed


@client.tree.command(name="backfill", description="Shows the price history backfill and each stock's first and last stored minute.")
@app_commands.default_permissions(administrator=True)
async def backfill(interaction: discord.Interaction):
	await interaction.response.defer(ephemeral=True)

	if not _is_admin(interaction):
		await _deny(interaction)
		return

	rows = await asyncio.to_thread(_backfill_rows)
	embed = _backfill_embed(rows, dict(config.backfill_state), config.features["backfill"], time.time())
	client.set_author_interaction(interaction, embed)
	await interaction.followup.send(embed=embed, ephemeral=True)
