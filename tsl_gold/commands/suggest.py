import asyncio
import discord
from discord import app_commands

import tsl_core.functions as tsl_lib
import tsl_config.config as config
import tsl_bot.functions.suggest as suggest

client = config.client


@client.tree.command(name="suggest", description="Longer-term upswing picks at daily (+0.5% / 3d) and weekly (+1% / 7d) scales.")
@app_commands.describe(
	horizon="Daily: +0.5% after 3 days. Weekly: +1% after 7 days.",
	view="Current picks, every stock ranked, or how past picks performed.",
	days="Track record only: how many days of history to include.",
)
@app_commands.choices(
	horizon=[
		app_commands.Choice(name="Daily (+0.5% after 3 days)", value="daily"),
		app_commands.Choice(name="Weekly (+1% after 7 days)", value="weekly"),
	],
	view=[
		app_commands.Choice(name="Picks", value="picks"),
		app_commands.Choice(name="Full Ranking", value="ranking"),
		app_commands.Choice(name="Track Record", value="record"),
	],
)
async def suggest_cmd(interaction: discord.Interaction, horizon: str = "daily", view: str = "picks", days: int = 90):
	await interaction.response.defer()

	try:
		if view == "record":
			days = max(1, min(days, 3650))
			# Grading reads the stock DBs; keep it off the event loop
			await asyncio.to_thread(suggest.grade_open_suggestions)
			embed = suggest.build_record_embed(horizon, days)
		else:
			# First call each day retrains the models (~15s), later calls are instant
			result = await asyncio.to_thread(suggest.run_scan, horizon)
			embed = suggest.build_picks_embed(result, ranking=(view == "ranking"))
	except tsl_lib.analysis.upswing.StaleDataError as e:
		embed = discord.Embed(title=":warning: Suggestions Unavailable :warning:")
		embed.color = discord.Color.orange()
		embed.add_field(name="Details:", value=str(e) + "\nTornsy may be unreachable; try again later.")
	except Exception as e:
		tsl_lib.util.write_log("[ERROR] SUGGEST ERROR: /suggest " + horizon + " " + view + " | " + repr(e), tsl_lib.util.current_date())
		embed = discord.Embed(title="SUGGEST ERROR:")
		embed.color = discord.Color.red()
		embed.set_thumbnail(url=config.notstonks_png)
		embed.add_field(name="Details:", value="Something went wrong generating suggestions.\nCommand used:\n\n```/suggest " + horizon + " " + view + "```")

	client.set_author_interaction(interaction, embed)
	await interaction.followup.send(embed=embed)
