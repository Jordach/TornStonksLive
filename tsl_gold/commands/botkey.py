import asyncio
import json
import re
import discord
from discord import app_commands
import requests

import tsl_core.functions as tsl_lib
import tsl_config.config as config
from tsl_gold.commands.admin import _is_admin, _deny

client = config.client

# Torn API keys are 16 alphanumeric characters
_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9]{16}$")

# Torn's key access levels (key/?selections=info access_level)
_ACCESS_NAMES = {1: "Public", 2: "Minimal", 3: "Limited", 4: "Full"}
_KINDS = {
	# kind: (label, used for, lowest access level that works)
	"public": ("Public key", "/benefit, and live prices when Tornsy is down", 1),
	"event": ("Events key", "live prices when Tornsy is down and there's no public key", 1),
}


def _key_info(api_key):
	"""(access level, access type) of a key, or raise ValueError with a user-facing reason."""
	req = requests.get("https://api.torn.com/key/?selections=info&key=" + api_key, timeout=10)
	if req.status_code != 200:
		raise ValueError("Torn's API returned HTTP " + str(req.status_code) + ".")
	data = json.loads(req.text)
	if "error" in data:
		code = int(data["error"].get("code", 0))
		if code < len(tsl_lib.torn_api_error_codes):
			raise ValueError(tsl_lib.torn_api_error_codes[code][0])
		raise ValueError(str(data["error"].get("error", "Unknown error")))
	level = int(data.get("access_level", 0))
	return level, str(data.get("access_type") or _ACCESS_NAMES.get(level, "Unknown"))


def _status_embed(interaction):
	embed = discord.Embed(title="Bot Torn API Keys")
	embed.color = discord.Color.blurple()
	client.set_author_interaction(interaction, embed)
	for kind, (label, used_for, _) in _KINDS.items():
		stored = config.get_bot_key(kind) is not None
		embed.add_field(name=label, value=(":white_check_mark: Stored" if stored else ":x: Not set") + "\nUsed for " + used_for + ".", inline=False)
	source = {"tornsy": "Tornsy", "torn": "Torn's API (Tornsy is down)", None: "No update yet"}.get(config.live_source, str(config.live_source))
	embed.add_field(name="Live prices from", value=source, inline=False)
	return embed


@client.tree.command(name="botkey", description="Set, check or remove the bot's own Torn API keys (admins only).")
@app_commands.default_permissions(administrator=True)
@app_commands.describe(
	action="What to do.",
	which="Which of the bot's keys. Not needed to check.",
	key="The 16-character Torn API key (only for set).",
)
@app_commands.choices(
	action=[
		app_commands.Choice(name="Check which keys are stored", value="view"),
		app_commands.Choice(name="Set or change a key", value="set"),
		app_commands.Choice(name="Remove a key", value="remove"),
	],
	which=[
		app_commands.Choice(name="Public key (/benefit, Tornsy fallback)", value="public"),
		app_commands.Choice(name="Events key (second Tornsy fallback)", value="event"),
	],
)
async def botkey(interaction: discord.Interaction, action: str, which: str = None, key: str = None):
	# Ephemeral throughout so a key typed here is never shown to anyone else
	await interaction.response.defer(ephemeral=True)

	if not _is_admin(interaction):
		await _deny(interaction)
		return

	if action == "view":
		await interaction.followup.send(embed=_status_embed(interaction), ephemeral=True)
		return

	if which not in _KINDS:
		await interaction.followup.send(":no_entry_sign: Choose which key with the `which` option.", ephemeral=True)
		return
	label, _, min_level = _KINDS[which]

	if action == "remove":
		removed = config.remove_bot_key(which)
		if removed:
			tsl_lib.util.write_log("[ADMIN] " + label + " removed by " + interaction.user.display_name + ".", tsl_lib.util.current_date())
		await interaction.followup.send((":white_check_mark: " + label + " removed.") if removed else ("No " + label.lower() + " was stored."), ephemeral=True)
		return

	# set
	clean_key = (key or "").strip()
	if not _KEY_PATTERN.match(clean_key):
		await interaction.followup.send(":no_entry_sign: Give the key with the `key` option: exactly 16 letters and numbers.", ephemeral=True)
		return
	try:
		level, access_type = await asyncio.to_thread(_key_info, clean_key)
	except requests.RequestException:
		await interaction.followup.send("Torn's API didn't respond in time. Try again shortly.", ephemeral=True)
		return
	except ValueError as err:
		await interaction.followup.send(":no_entry_sign: Torn rejected the key: " + str(err), ephemeral=True)
		return
	if level < min_level:
		await interaction.followup.send(":no_entry_sign: That key's access (" + access_type + ") is too low for the " + label.lower() + ".", ephemeral=True)
		return

	config.set_bot_key(which, clean_key)
	tsl_lib.util.write_log("[ADMIN] " + label + " set by " + interaction.user.display_name + " (" + access_type + " access).", tsl_lib.util.current_date())
	note = ""
	if level > 3:
		note = "\n:warning: This is a Full Access key. The bot only needs Public access for this, so a lower-access key is safer."
	await interaction.followup.send(":white_check_mark: " + label + " saved and encrypted (" + access_type + " access)." + note, ephemeral=True)
