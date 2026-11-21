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

	import asyncio
	import tsl_bot.functions.suggest as suggest

	live = destination == "channels"
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
			where = "you (preview)"
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
