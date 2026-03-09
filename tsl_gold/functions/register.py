import discord
from discord import app_commands
import random
import requests
import json
import tsl_config.config as config
import tsl_core.functions as tsl_func
import tsl_core.db as tsl_db
client = config.client

@client.tree.command(name="register", description="Register your Discord and Torn ID for TornStonks usage.")
async def verify(interaction: discord.Interaction):
	dm_state = True
	if interaction.channel.type == discord.ChannelType.private:
		dm_state = False

	key = random.choice(config.verification_keys)
	api = requests.get("https://api.torn.com/user/" + str(interaction.user.id) + "?key=" + key)

	if api.status_code != 200:
		await interaction.response.send_message("Torn API failed to respond in time, or has an error. Blame Ched, then try again shortly.", ephemeral=dm_state)
		return

	data = json.loads(api.text)
	if "error" in data:
		await interaction.response.send_message(tsl_func.torn_api_error_codes[int(data["error"]["code"])][0], ephemeral=dm_state)
		if tsl_func.torn_api_error_codes[int(data["error"]["code"])][1]:
			print(f"bad key: {key}")
		return
	elif data["discord"]["discordID"] == "":
		await interaction.response.send_message("Torn API reports this account hasn't been linked to your Discord account. Join the Torn Discord and verify there:\n\nhttps://torn.com/discord", ephemeral=dm_state)
		return
	else:
		await interaction.response.send_message("Verified that you own the two accounts; https://www.torn.com/profiles.php?XID=" + str(data["player_id"]) + " - but the backend isn't done yet.", ephemeral=dm_state)
		return
