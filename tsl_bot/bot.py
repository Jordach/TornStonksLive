import discord
from discord import app_commands

import tsl_core.functions as tsl_lib
import tsl_config.config as config

import tsl_bot.functions.author as author
import tsl_bot.functions.whales as bot_whales
import tsl_bot.functions.volatility as bot_volatility
import tsl_bot.functions.suggest as bot_suggest
import tsl_bot.functions.price_alerts as price_alert

class Bot(discord.Client):
	# Whale watching
	alert_roles = bot_whales.alert_roles
	process_stockdata = bot_whales.process_stockdata
	
	# /alert price notifications
	alert_user = price_alert.alert_user

	# Volatility Checks
	post_volatility = bot_volatility.post_volatility
	process_volatility = bot_volatility.process_volatility
	process_daily_volatility = bot_volatility.process_daily_volatility
	process_weekly_volatility = bot_volatility.process_weekly_volatility

	# Suggestions
	post_suggestions = bot_suggest.post_suggestions
	make_suggestions = bot_suggest.make_suggestions

	# Set the profile thing
	set_author_interaction = author.set_author_interaction
	set_author_notif = author.set_author_notif

	# Slash command handling
	def __init__(self, *, intents: discord.Intents):
		super().__init__(intents=intents)
		self.tree = app_commands.CommandTree(self)
		
	
	async def on_ready(self):
		await self.wait_until_ready()
		# await self.tree.sync() The /sync slash command now makes this easier at runtime

		await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Torn City Stocks"))
		tsl_lib.util.write_log("[STARTUP] TornStonks Live started.", tsl_lib.util.current_date())
		config.bot_started = True
