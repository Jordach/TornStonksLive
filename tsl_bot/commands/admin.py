import discord
import tsl_core.functions as tsl_lib
import tsl_config.config as config

async def cmd_stop(self, message, prefix):
	if int(message.author.id) in config.bot_admins:
		config.write_user_alerts()
		tsl_lib.util.stop_run_continously.set()
		await self.close()
		return
	else:
		embed = discord.Embed(title=":no_entry_sign: Permission Required :no_entry_sign:")
		embed.color = discord.Color.red()
		self.set_author(message, embed)
		embed.add_field(name="Details:", value="You are not authorised to stop the bot.")
		await message.channel.send(embed=embed, mention_author=False, reference=message)

def force_suggestions(self, message, prefix):
	if int(message.author.id) in config.bot_admins:
		print("Suggestions forced.")
		self.process_suggestions()

def force_volatility(self, message, prefix):
	if int(message.author.id) in config.bot_admins:
		print("Volatility forced.")
		self.process_volatility()

async def system_message(self, message, prefix):
	if int(message.author.id) in config.bot_admins:
		new_msg = message.content.replace(prefix+"system_message ", "")
		for key in range(0, len(config.alert_channels["id"])):
			channel = await self.fetch_channel(config.alert_channels["id"][key])
			await channel.send(new_msg)

async def sync_commands(self, message, prefix):
	if int(message.author.id) in config.bot_admins:
		await config.client.tree.sync()
		print("Synced slash command tree to Discord.")