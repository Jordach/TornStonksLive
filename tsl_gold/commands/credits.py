import discord

import tsl_config.config as config

client = config.client

THANKS_PATH = "thanks.md"


@client.tree.command(name="credits", description="The people who have helped TornStonks Live along the way.")
async def credits(interaction: discord.Interaction):
	try:
		with open(THANKS_PATH, "r", encoding="utf-8") as thanks:
			thanks_str = thanks.read().strip()
	except OSError:
		thanks_str = ""

	thanks_str += "\n\nThank you truly, for using TornStonks Live! :thumbsup:"

	# The description holds up to 4096 characters, unlike a field's 1024
	embed = discord.Embed(title="Many Thanks To:", description=thanks_str[-4096:])
	embed.color = discord.Color.purple()
	client.set_author_interaction(interaction, embed)
	await interaction.response.send_message(embed=embed, ephemeral=config.private_reply(interaction))
