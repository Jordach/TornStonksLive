import discord
import asyncio
import tsl_core.functions as tsl_lib
import tsl_config.config as config

from discord import app_commands
client = config.client

async def ticker_autocomplete(interaction: discord.Interaction, current: str):
	return [
		app_commands.Choice(name=t, value=t)
		for t in tsl_lib.stock_lut
		if current.upper() in t.upper()
	][:25]  # Discord caps at 25 choices

@client.tree.command(name="alert", description="Set an alert for a stock based on price criteria.")
@app_commands.describe(
	mode="Type of Alert (Up, Down, Loss)",
	ticker="Stock Ticker (IOU, SYM, ...)",
	value="Value or Percentage Change (123.45, 1.23%)"
)
@app_commands.choices(mode=[
	app_commands.Choice(name="Up", value="up"),
	app_commands.Choice(name="Down", value="down"),
	app_commands.Choice(name="Loss", value="loss")
])
@app_commands.autocomplete(ticker=ticker_autocomplete)
async def alerts(interaction: discord.Interaction, mode: str, ticker: str, value: str):
	await interaction.response.defer()

	is_percentage = False
	_value = 0
	if "%" not in value:
		try:
			_value = float(value)
		except:
			err_embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
			err_embed.color = discord.Color.red()
			client.set_author_interaction(interaction, err_embed)
			err_embed.add_field(name="Details:", value="Numeric argument contains non numeric characters.")
			await interaction.followup.send(embed=err_embed)
			return
	else:
		r_value = str(value.replace("%", ""))
		try:
			_value = float(r_value)
			is_percentage = True
		except:
			err_embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
			err_embed.color = discord.Color.red()
			client.set_author_interaction(interaction, err_embed)
			err_embed.add_field(name="Details:", value="Numeric argument contains non numeric characters.")
			await interaction.followup.send(embed=err_embed)
			return
	
	config.userdata["id"].append(int(interaction.user.id))
	config.userdata["type"].append(mode)
	config.userdata["stock"].append(ticker.lower())
	if is_percentage:
		for data in config.json_data["data"]:
			if data["stock"] == ticker:
				config.userdata["value"].append(float(data["price"]) * (1 + (_value / 100)))
				break
	else:
		config.userdata["value"].append(_value)

	await asyncio.get_event_loop().run_in_executor(None, config.write_user_alerts)

	embed = discord.Embed(title=":white_check_mark: Will send you a DM when the criteria is reached. :white_check_mark:")
	embed.color = discord.Color.dark_green()
	client.set_author_interaction(interaction, embed)
	await interaction.followup.send(embed=embed)

@client.tree.command(name="notifications", description="Lists your pending notifcations.")
@app_commands.describe(
	mode="Type of Alert (Up, Down, Loss, All)",
	ticker="Stock Ticker (IOU, SYM, ...)"
)
@app_commands.choices(mode=[
	app_commands.Choice(name="All", value="all"),
	app_commands.Choice(name="Up", value="up"),
	app_commands.Choice(name="Down", value="down"),
	app_commands.Choice(name="Loss", value="loss")
])
@app_commands.autocomplete(ticker=ticker_autocomplete)
async def list_alerts(interaction: discord.Interaction, mode: str = "all", ticker: str = "NO_TICKER"):
	await interaction.response.defer()
	if int(interaction.user.id) in config.userdata["id"]:
		known_alerts = ""
		for key in range(0, len(config.userdata["id"])):
			if int(interaction.user.id) == config.userdata["id"][key]:
				if ticker != "NO_TICKER":
					if mode == config.userdata["type"][key] and ticker.lower() == config.userdata["stock"][key]:
						known_alerts += f'`{config.userdata["type"][key]} {config.userdata["stock"][key]} {config.userdata["value"][key]}`\n'
					elif mode == config.userdata["type"][key] and mode != "all":
						known_alerts += f'`{config.userdata["type"][key]} {config.userdata["stock"][key]} {config.userdata["value"][key]}`\n'
					elif mode == "all":
						known_alerts += f'`{config.userdata["type"][key]} {config.userdata["stock"][key]} {config.userdata["value"][key]}`\n'
				else:
					if mode == config.userdata["type"][key] and mode != "all":
						known_alerts += f'`{config.userdata["type"][key]} {config.userdata["stock"][key]} {config.userdata["value"][key]}`\n'
					elif mode == "all":
						known_alerts += f'`{config.userdata["type"][key]} {config.userdata["stock"][key]} {config.userdata["value"][key]}`\n'
			
			if known_alerts != "":
				embed = discord.Embed(title="")
				embed.color = discord.Color.blue()
				client.set_author_interaction(interaction, embed)
				embed.add_field(name="Pending Notifications:", value=known_alerts)
				user = await client.fetch_user(interaction.user.id)
				await user.send(embed=embed)
				break
			else:
				embed = discord.Embed(title="")
				embed.color = discord.Color.dark_green()
				client.set_author_interaction(interaction, embed)
				embed.add_field(name="No Notifications Pending!", value="Thank you for using TornStonks Live; have a nice day. :wave:")
				user = await client.fetch_user(interaction.user.id)
				await user.send(embed=embed)
				break
	else:
		embed = discord.Embed(title="")
		embed.color = discord.Color.dark_green()
		client.set_author_interaction(interaction, embed)
		embed.add_field(name="No Notifications Pending!", value="Thank you for using TornStonks Live; have a nice day. :wave:")
		user = await client.fetch_user(interaction.user.id)
		await user.send(embed=embed)
	
	# Send dummy message
	await interaction.followup.send(
        "Sent as DM!", 
        ephemeral=True
    )

@client.tree.command(name="undo", description="Undoes your last added notification, useful in case of a mistake.")
async def undo(interaction: discord.Interaction):
	await interaction.response.defer()

	if int(interaction.user.id) in config.userdata["id"]:
		for key in range(len(config.userdata["id"])-1, -1, -1):
			if int(interaction.user.id) == config.userdata["id"][key]:
				tsl_lib.util.write_log("[NOTICE]: " + interaction.user.display_name + " deleted notification: " + str(config.userdata["id"][key]) + "," + config.userdata["type"][key] + "," + config.userdata["stock"][key] + "," + str(config.userdata["value"][key]), tsl_lib.util.current_date())
				notice = "`/alert " + config.userdata["type"][key] + " " + config.userdata["stock"][key] + " " + "{:,.2f}".format(config.userdata["value"][key]) + "`"
				del config.userdata["id"][key]
				del config.userdata["type"][key]
				del config.userdata["stock"][key]
				del config.userdata["value"][key]
				await asyncio.get_event_loop().run_in_executor(None, config.write_user_alerts)
				embed = discord.Embed(title="")
				embed.color = discord.Color.red()
				client.set_author_interaction(interaction, embed)
				embed.add_field(name="Mistake Erased.",  value="Try not to make a mess of the channel history next time.", inline=False)
				embed.add_field(name="Command Undone:", value="```"+notice+"```", inline=False)
				await interaction.followup.send(embed=embed, ephemeral=True)
				return
			
@client.tree.command(name="clear", description="Clears all of your notifications.")
async def forget_me(interaction: discord.Interaction):
	await interaction.response.defer()

	if int(interaction.user.id) in config.userdata["id"]:
		for key in range(len(config.userdata["id"])-1, -1, -1):
			if int(interaction.user.id) == config.userdata["id"]:
				tsl_lib.util.write_log("[NOTICE]: " + interaction.user.display_name + " deleted notification: " + str(config.userdata["id"][key]) + "," + config.userdata["type"][key] + "," + config.userdata["stock"][key] + "," + str(config.userdata["value"][key]), tsl_lib.util.current_date())
				del config.userdata["id"][key]
				del config.userdata["type"][key]
				del config.userdata["stock"][key]
				del config.userdata["value"][key]
		
		await asyncio.get_event_loop().run_in_executor(None, config.write_user_alerts)
		embed = discord.Embed(title="")
		embed.color = discord.Color.red()
		client.set_author_interaction(interaction, embed)
		embed.add_field(name="All of your pending notifications deleted.", value="Thank you for using TornStonks Live; have a nice day. :wave:")
		await interaction.followup.send(embed=embed)
	else:
		embed = discord.Embed(title="")
		embed.color = discord.Color.dark_green()
		client.set_author_interaction(interaction, embed)
		embed.add_field(name="No Notifications Pending!", value="Thank you for using TornStonks Live; have a nice day. :wave:")
		await interaction.followup.send(embed=embed)

@client.tree.command(name="forget", description="Clears a specific or multiple of the specified notifications.")
@app_commands.autocomplete(ticker=ticker_autocomplete)
@app_commands.choices(mode=[
	app_commands.Choice(name="Up", value="up"),
	app_commands.Choice(name="Down", value="down"),
	app_commands.Choice(name="Loss", value="loss"),
	app_commands.Choice(name="Up (Reaction)", value="up_react"),
	app_commands.Choice(name="Down (Reaction)", value="down_react")
])
async def forget(interaction: discord.Interaction, ticker: str, mode: str = "_OPTIONAL", value: float = -1000069420.67):
	await interaction.response.defer()

	if int(interaction.user.id) in config.userdata["id"]:
		for key in range(len(config.userdata["id"])-1, -1, -1):
			if int(interaction.user.id) == config.userdata["id"][key]:
				if value !=	-1000069420.67:
					if ticker.lower() == config.userdata["stock"][key] and mode == config.userdata["type"][key] and value == config.userdata["value"][key]:
						tsl_lib.util.write_log("[NOTICE]: " + interaction.user.display_name + " deleted notification: " + str(config.userdata["id"][key]) + "," + config.userdata["type"][key] + "," + config.userdata["stock"][key] + "," + str(config.userdata["value"][key]), tsl_lib.util.current_date())
						del config.userdata["id"][key]
						del config.userdata["type"][key]
						del config.userdata["stock"][key]
						del config.userdata["value"][key]
					elif mode != "_OPTIONAL":
						if ticker.lower() == config.userdata["stock"][key] and mode == config.userdata["type"][key]:
							tsl_lib.util.write_log("[NOTICE]: " + interaction.user.display_name + " deleted notification: " + str(config.userdata["id"][key]) + "," + config.userdata["type"][key] + "," + config.userdata["stock"][key] + "," + str(config.userdata["value"][key]), tsl_lib.util.current_date())
							del config.userdata["id"][key]
							del config.userdata["type"][key]
							del config.userdata["stock"][key]
							del config.userdata["value"][key]
					else:
						if ticker.lower() == config.userdata["stock"][key]:
							tsl_lib.util.write_log("[NOTICE]: " + interaction.user.display_name + " deleted notification: " + str(config.userdata["id"][key]) + "," + config.userdata["type"][key] + "," + config.userdata["stock"][key] + "," + str(config.userdata["value"][key]), tsl_lib.util.current_date())
							del config.userdata["id"][key]
							del config.userdata["type"][key]
							del config.userdata["stock"][key]
							del config.userdata["value"][key]
		
		await asyncio.get_event_loop().run_in_executor(None, config.write_user_alerts)
		embed = discord.Embed(title="")
		embed.color = discord.Color.red()
		client.set_author_interaction(interaction, embed)
		embed.add_field(name="Specified Pending Notification(s) Deleted!",  value="Thank you for using TornStonks Live; have a nice day. :wave:")
		await interaction.followup.send(embed=embed)
	else:
		embed = discord.Embed(title="")
		embed.color = discord.Color.dark_green()
		client.set_author_interaction(interaction, embed)
		embed.add_field(name="No Notifications Pending!", value="Thank you for using TornStonks Live; have a nice day. :wave:")
		await interaction.followup.send(embed=embed)