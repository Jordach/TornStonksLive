import discord
from discord import app_commands
import re
import requests
import json
import tsl_config.config as config
import tsl_core.functions as tsl_func

client = config.client

# Torn API keys are 16 alphanumeric characters
_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9]{16}$")


@client.tree.command(name="apikey", description="Add, change, or remove your personal Torn API key.")
@app_commands.describe(
	action="What you want to do with your API key.",
	key="Your 16-character Torn API key (required for set/change, ignored for remove/view).",
)
@app_commands.choices(action=[
	app_commands.Choice(name="Set or change my key", value="set"),
	app_commands.Choice(name="Remove my key", value="remove"),
	app_commands.Choice(name="Check if I have a key stored", value="view"),
])
async def apikey(interaction: discord.Interaction, action: app_commands.Choice[str], key: str = None):
	# Always respond ephemerally so the key is never visible to others
	dm_state = True

	discord_id = str(interaction.user.id)

	# ---- SET / CHANGE ----
	if action.value == "set":
		if key is None or key.strip() == "":
			await interaction.response.send_message(
				":no_entry_sign: You need to provide your 16-character Torn API key.\n\n"
				"Example: `/apikey action:Set or change my key key:YOUR_KEY_HERE`",
				ephemeral=dm_state,
			)
			return

		clean_key = key.strip()

		# Basic format validation
		if not _KEY_PATTERN.match(clean_key):
			await interaction.response.send_message(
				":no_entry_sign: That doesn't look like a valid Torn API key. "
				"Keys are exactly 16 alphanumeric characters.",
				ephemeral=dm_state,
			)
			return

		# Defer because the Torn API call may take a moment
		await interaction.response.defer(ephemeral=dm_state)

		# Validate the key against Torn's API
		try:
			api = requests.get(
				"https://api.torn.com/user/?selections=basic&key=" + clean_key,
				timeout=10,
			)
		except requests.RequestException:
			await interaction.followup.send(
				"Torn API failed to respond in time. Please try again shortly.",
				ephemeral=dm_state,
			)
			return

		if api.status_code != 200:
			await interaction.followup.send(
				"Torn's API returned an unexpected status. Please try again shortly.",
				ephemeral=dm_state,
			)
			return

		data = json.loads(api.text)
		if "error" in data:
			error_code = int(data["error"]["code"])
			if error_code < len(tsl_func.torn_api_error_codes):
				msg = tsl_func.torn_api_error_codes[error_code][0]
			else:
				msg = data["error"]["error"]
			await interaction.followup.send(
				":no_entry_sign: Torn API rejected the key: " + msg,
				ephemeral=dm_state,
			)
			return

		# Key is valid — store it encrypted
		torn_name = data.get("name", "Unknown")
		torn_id = data.get("player_id", "?")
		config.save_user_key(discord_id, clean_key)

		await interaction.followup.send(
			":white_check_mark: API key saved and encrypted for **"
			+ str(torn_name) + "** [" + str(torn_id) + "].\n\n"
			"Your key is stored securely and will be used for commands that need it. "
			"You can change or remove it at any time with `/apikey`.",
			ephemeral=dm_state,
		)

	# ---- REMOVE ----
	elif action.value == "remove":
		existed = config.remove_user_key(discord_id)
		if existed:
			await interaction.response.send_message(
				":white_check_mark: Your API key has been removed.",
				ephemeral=dm_state,
			)
		else:
			await interaction.response.send_message(
				"You don't have an API key stored — nothing to remove.",
				ephemeral=dm_state,
			)

	# ---- VIEW ----
	elif action.value == "view":
		has_key = config.has_user_key(discord_id)
		if has_key:
			await interaction.response.send_message(
				":white_check_mark: You have an API key stored. Use `/apikey action:Remove my key` to delete it, "
				"or `/apikey action:Set or change my key` to replace it.",
				ephemeral=dm_state,
			)
		else:
			await interaction.response.send_message(
				"You don't have an API key stored yet. Use `/apikey action:Set or change my key key:YOUR_KEY` to add one.",
				ephemeral=dm_state,
			)