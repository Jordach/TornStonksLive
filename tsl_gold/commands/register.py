import asyncio
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
		if 0 <= error_code < len(tsl_func.torn_api_error_codes):
			msg, key_is_bad = tsl_func.torn_api_error_codes[error_code]
		else:
			msg, key_is_bad = str(data["error"].get("error", "Unknown Torn API error.")), False
		await interaction.followup.send(msg, ephemeral=dm_state)
		if key_is_bad:
			# Never log the key itself; the last 4 characters are enough to identify it
			tsl_lib_log("[WARNING] Verification key ending in ..." + key[-4:] + " returned error code " + str(error_code))
		return
	elif data.get("discord", {}).get("discordID", "") == "":
		await interaction.followup.send("Torn API reports this account hasn't been linked to your Discord account. Join the Torn Discord and verify there:\n\nhttps://torn.com/discord", ephemeral=dm_state)
		return
	else:
		await interaction.followup.send("Verified that you own the two accounts; https://www.torn.com/profiles.php?XID=" + str(data["player_id"]) + " - but the backend isn't done yet.", ephemeral=dm_state)
		return


def tsl_lib_log(msg):
	tsl_func.util.write_log(msg, tsl_func.util.current_date())
