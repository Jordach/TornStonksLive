import asyncio
import discord
from discord import app_commands
import random
import requests
import json
import tsl_config.config as config
import tsl_core.functions as tsl_func
client = config.client

@client.tree.command(name="verify", description="Checks if you've bound your Discord account with your Torn account.")
async def verify(interaction: discord.Interaction):
	dm_state = True
	if interaction.channel.type == discord.ChannelType.private:
		dm_state = False

	# Defer first: the Torn API call can take longer than Discord's 3 second window
	await interaction.response.defer(ephemeral=dm_state)

	key = random.choice(config.verification_keys)
	try:
		api = await asyncio.to_thread(
			requests.get,
			"https://api.torn.com/user/" + str(interaction.user.id) + "?key=" + key,
			timeout=10,
		)
	except requests.RequestException:
		api = None

	if api is None or api.status_code != 200:
		await interaction.followup.send("Torn API failed to respond in time, or has an error. Blame Ched, then try again shortly.", ephemeral=dm_state)
		return

	data = json.loads(api.text)
	if "error" in data:
		error_code = int(data["error"]["code"])
		# Torn returns code 6 (incorrect ID) when no Torn account is linked to this Discord ID;
		# anything else is a real API problem and shouldn't be reported as "not linked".
		if error_code == 6:
			msg = "Torn API reports this account hasn't been linked to your Discord account. Join the Torn Discord and verify there:\n\nhttps://torn.com/discord"
		elif 0 <= error_code < len(tsl_func.torn_api_error_codes):
			msg = tsl_func.torn_api_error_codes[error_code][0]
		else:
			msg = str(data["error"].get("error", "Unknown Torn API error."))
		await interaction.followup.send(msg, ephemeral=dm_state)
		return
	else:
		await interaction.followup.send("Verified that you own the two accounts; https://www.torn.com/profiles.php?XID=" + str(data["player_id"]) + " - but the backend isn't done yet.\n\n**Note: TSL Gold during Beta will be free to use until officially launched.**", ephemeral=dm_state)
		return
