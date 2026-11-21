import asyncio
import discord
from discord import app_commands

import tsl_core.functions as tsl_lib
import tsl_config.config as config
import tsl_bot.functions.suggest as suggest

client = config.client


@client.tree.command(name="suggest", description="Stocks likely to swing up or down over the next few days (daily) or week (weekly).")
@app_commands.describe(
	horizon="Daily: a 0.5% move after 3 days. Weekly: a 1% move after 7 days.",
	direction="Upswings (likely to rise), downswings (likely to fall), or both.",
	view="Current picks, stocks ranked by chance, or how past picks performed.",
	days="Track record only: how many days of history to include.",
)
@app_commands.choices(
	horizon=[
		app_commands.Choice(name="Daily (0.5% move after 3 days)", value="daily"),
		app_commands.Choice(name="Weekly (1% move after 7 days)", value="weekly"),
	],
	direction=[
		app_commands.Choice(name="Both", value="both"),
		app_commands.Choice(name="Upswings (likely to rise)", value="up"),
		app_commands.Choice(name="Downswings (likely to fall)", value="down"),
	],
	view=[
		app_commands.Choice(name="Picks", value="picks"),
		app_commands.Choice(name="Full Ranking", value="ranking"),
		app_commands.Choice(name="Track Record", value="record"),
	],
)
async def suggest_cmd(interaction: discord.Interaction, horizon: str = "daily", direction: str = "both", view: str = "picks", days: int = 90):
	await interaction.response.defer()

	used = "/suggest " + horizon + " " + direction + " " + view
	try:
		if view == "record":
			days = max(1, min(days, 3650))
			# Grading reads the stock DBs; keep it off the event loop
			await asyncio.to_thread(suggest.grade_open_suggestions)
			embed = suggest.build_record_embed(horizon, direction, days)
		else:
			# First call each day retrains the models (~20s), later calls are instant
			results = await asyncio.to_thread(suggest.run_scan, horizon, direction)
			embed = suggest.build_picks_embed(results, ranking=(view == "ranking"))
	except tsl_lib.analysis.swing.StaleDataError as e:
		embed = discord.Embed(title=":warning: Suggestions Unavailable :warning:")
		embed.color = discord.Color.orange()
		embed.add_field(name="Details:", value=str(e) + "\nTornsy may be unreachable; try again later.")
	except Exception as e:
		tsl_lib.util.write_log("[ERROR] SUGGEST ERROR: " + used + " | " + repr(e), tsl_lib.util.current_date())
		embed = discord.Embed(title="SUGGEST ERROR:")
		embed.color = discord.Color.red()
		embed.set_thumbnail(url=config.notstonks_png)
		embed.add_field(name="Details:", value="Something went wrong generating suggestions.\nCommand used:\n\n```" + used + "```")

	client.set_author_interaction(interaction, embed)
	await interaction.followup.send(embed=embed)
