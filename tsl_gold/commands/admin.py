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