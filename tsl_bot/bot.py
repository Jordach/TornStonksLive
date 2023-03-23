import discord
from discord import app_commands

import tsl_core.functions as tsl_lib
import tsl_config.config as config

import tsl_bot.functions.author as author
import tsl_bot.functions.whales as bot_whales
import tsl_bot.functions.volatility as bot_volatility
import tsl_bot.functions.suggest as bot_suggest
import tsl_bot.commands.price_alert as price_alert
import tsl_bot.commander as bot_commands

class Bot(discord.Client):
	# Whale watching
	alert_roles = bot_whales.alert_roles
	process_stockdata = bot_whales.process_stockdata
	
	# !up/down/loss ping checks
	alert_user = price_alert.alert_user

	# Volatility Checks
	post_volatility = bot_volatility.post_volatility
	process_volatility = bot_volatility.process_volatility
	process_daily_volatility = bot_volatility.process_daily_volatility
	process_weekly_volatility = bot_volatility.process_weekly_volatility

	# Suggestions
	post_recommendations = bot_suggest.post_recommendations
	post_single_recommendation = bot_suggest.post_single_recommendation
	make_suggestions = bot_suggest.make_suggestions

	# Set the profile thing
	set_author = author.set_author
	set_author_notif = author.set_author_notif

	# Slash command handling
	def __init__(self, *, intents: config.intents):
		super().__init__(intents=intents)
		self.tree = app_commands.CommandTree(self)
		
	
	async def on_ready(self):
		await self.wait_until_ready()
		#await self.tree.sync()

		await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Torn City Stocks"))
		if config.enable_suggestions:
			for key in range(0, len(config.suggestion_channels["id"])):
				channel = await self.fetch_channel(config.suggestion_channels["id"][key])
				pred_message = await channel.history(limit=1).flatten()
				three = "3️⃣"
				global not_more
				# Avoid trying to get messages from completely empty channels
				if len(pred_message) == 0:
					continue
				elif len(pred_message[0].reactions) == 0:
					continue
				if pred_message[0].reactions[0] == three:
					not_more = True
				else:
					not_more = False
				global last_pred_id
				last_pred_id = []
				last_pred_id.append(pred_message[0])
		tsl_lib.util.write_log("[STARTUP] TornStonks Live started.", tsl_lib.util.current_date())
		config.bot_started = True

	#async def on_raw_reaction_add(self, payload):
		#await bot_suggest.suggest_react_add(self, payload)
	
	#async def on_raw_reaction_remove(self, payload):
		#await bot_suggest.suggest_react_remove(self, payload)

	async def on_message(self, message):
		# The bot should never respond to itself, ever
		if message.author == self.user:
			return

		# Ignore noisy bots
		if message.author.bot:
			return

		# Only respond in our designated channels to not shit up the place
		# This includes DMs
		if not int(message.channel.id) in config.command_channels["id"] and message.guild:
			return
		
		# Default for DMs, but not in servers
		cmd_prefix = "!"
		if message.guild:
			for key in range(0, len(config.command_channels["id"])):
				# Are we in a valid command channel?
				if int(message.channel.id) == config.command_channels["id"][key]:
					# Get the prefix for that channel
					cmd_prefix = config.command_channels["prefix"][key]
					break
		
		for command in bot_commands.commands:
			if message.content.startswith(cmd_prefix+command[0]):
				if command[2]:
					await command[1](self, message, cmd_prefix)
					break
				else:
					command[1](self, message, cmd_prefix)