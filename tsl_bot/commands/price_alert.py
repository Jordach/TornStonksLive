import discord
import tsl_core.functions as tsl_lib
import tsl_config.config as config

# calling async from sync env is like lighting a match at a
# petrol station, seriously NOT recommended
async def alert_user(self, item, id, type, stock, value, data):
	if "up" in type:
		embed = discord.Embed(title=data["name"] + " Above Target Price", url="https://www.torn.com/page.php?sid=stocks&stockID="+tsl_lib.util.lut_stock_id(stock)+"&tab=owned")
		embed.color = discord.Color.orange()
		embed.add_field(name="Stonks!", value=data["name"] + " has reached or exceeded your target price of: $" + "{:,}".format(value) + ".")
		embed.set_thumbnail(url=config.stonks_png)
		user = await self.fetch_user(id)
		self.set_author_notif(user, embed)
		await user.send(embed=embed)
	elif "down" in type:
		embed = discord.Embed(title=data["name"] + " Below Target Price", url="https://www.torn.com/page.php?sid=stocks&stockID="+tsl_lib.util.lut_stock_id(stock)+"&tab=owned")
		embed.color = discord.Color.orange()
		embed.add_field(name="Stonks!", value=data["name"] + " has reached or fallen under your target price of: $" + "{:,}".format(value) + ".")
		embed.set_thumbnail(url=config.stonks_png)
		user = await self.fetch_user(id)
		self.set_author_notif(user, embed)
		await user.send(embed=embed)
	elif type == "loss":
		embed = discord.Embed(title=data["name"] + " Below Stop Loss Price", url="https://www.torn.com/page.php?sid=stocks&stockID="+tsl_lib.util.lut_stock_id(stock)+"&tab=owned")
		embed.color = discord.Color.red()
		embed.add_field(name="Not Stonks!", value=data["name"] + " has reached or fallen below your stop loss price of: $" + "{:,}".format(value) + ".")
		embed.set_thumbnail(url=config.notstonks_png)
		user = await self.fetch_user(id)
		self.set_author_notif(user, embed)
		await user.send(embed=embed)

async def alerts(self, message, prefix):
	command = message.content.split(" ")

	# Check our command entry since we also use that to note the type of alert
	command[0] = str(command[0]).replace(prefix, "")
	types = ["up", "down", "loss"]
	if command[0] not in types and len(command) >= 1:
		err_embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
		err_embed.color = discord.Color.red()
		self.set_author(message, err_embed)
		err_embed.add_field(name="Details:", value="Invalid command. Example command: `![up/down/loss] sym 150.53` or `![up/down/loss] sym 1%`")
		await message.channel.send(embed=err_embed, mention_author=False, reference=message)
		return

	# Argument length check
	if len(command) < 3:
		err_embed = discord.Embed(title=":no_entry_sign: Invalid Arguments :no_entry_sign:")
		err_embed.color = discord.Color.red()
		self.set_author(message, err_embed)
		err_embed.add_field(name="Details:", value="Not enough arguments. Example command: `![up/down/loss] sym 150.53` or `![up/down/loss] sym 1%`")
		await message.channel.send(embed=err_embed, mention_author=False, reference=message)
		return

	# Check if the stock exists;
	if command[1].upper() not in tsl_lib.stock_lut:
		err_embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
		err_embed.color = discord.Color.red()
		self.set_author(message, err_embed)
		err_embed.add_field(name="Details:", value="Stock ticker not found. Example command: `![up/down/loss] sym 150.53` or `![up/down/loss] sym 1%`")
		await message.channel.send(embed=err_embed, mention_author=False, reference=message)
		return

	# Process whether we're a price to reach or a percentage
	is_percentage = False
	if "%" not in command[2]:
		try:
			command[2] = float(command[2])
		except:
			err_embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
			err_embed.color = discord.Color.red()
			self.set_author(message, err_embed)
			err_embed.add_field(name="Details:", value="Numeric argument contains non numeric characters. Example command: `![up/down/loss] sym 150.53` or `![up/down/loss] sym 1%`")
			await message.channel.send(embed=err_embed, mention_author=False, reference=message)
			return
	else:
		command[2] = str(command[2]).replace("%", "")
		try:
			is_percentage = True
			command[2] = float(command[2])
		except:
			err_embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
			err_embed.color = discord.Color.red()
			self.set_author(message, err_embed)
			err_embed.add_field(name="Details:", value="Numeric argument contains non numeric characters. Example command: `![up/down/loss] sym 150.53` or `![up/down/loss] sym 1%`")
			await message.channel.send(embed=err_embed, mention_author=False, reference=message)
			return
	
	# Process if we have four arguments and the previous value isn't containing a percentage sign
	# We can fail softly since it's not needed
	if len(command) >= 4 and not is_percentage:
		if command[3] == "%":
			is_percentage = True
		else:
			err_embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
			err_embed.color = discord.Color.red()
			self.set_author(message, err_embed)
			err_embed.add_field(name="Details:", value="Percentage sign not found. Example command: `![up/down/loss] sym 150.53` or `![up/down/loss] sym 1%`")
			await message.channel.send(embed=err_embed, mention_author=False, reference=message)
			return
	
	# Since we passed input validation - add the entry and save to disk:
	config.userdata["id"].append(int(message.author.id))
	config.userdata["type"].append(command[0].lower())
	config.userdata["stock"].append(command[1].lower())
	if is_percentage:
		for data in config.json_data["data"]:
			if data["stock"] == command[1].upper():
				config.userdata["value"].append(float(data["price"]) * (1 + (command[2] / 100)))
				break
	else:
		config.userdata["value"].append(command[2])
	config.write_user_alerts()

	embed = discord.Embed(title=":white_check_mark: Will send you a DM when the criteria is reached. :white_check_mark:")
	embed.color = discord.Color.dark_green()
	self.set_author(message, embed)
	await message.channel.send(embed=embed, mention_author=False, reference=message)

undo_list = ["undo", "fuck", "f**k", "shit", "ohno", "oops"]
undo_help = [True, False, False, False, False, False]
async def forget(self, message, prefix):
	if message.content == prefix+"forgetme":
		if int(message.author.id) in config.userdata["id"]:
			for key in range(len(config.userdata["id"])-1, -1, -1):
				if int(message.author.id) == config.userdata["id"][key]:
					tsl_lib.util.write_log("[NOTICE]: " + message.author.display_name + " deleted notification: " + str(config.userdata["id"][key]) + "," + config.userdata["type"][key] + "," + config.userdata["stock"][key] + "," + str(config.userdata["value"][key]), tsl_lib.util.current_date())
					del config.userdata["id"][key]
					del config.userdata["type"][key]
					del config.userdata["stock"][key]
					del config.userdata["value"][key]
			
			config.write_user_alerts()
			embed = discord.Embed(title="")
			embed.color = discord.Color.red()
			self.set_author(message, embed)
			embed.add_field(name="All of your pending notifications deleted.", value="Thank you for using TornStonks Live; have a nice day. :wave:")
			await message.channel.send(embed=embed, mention_author=False, reference=message)
		else:
			embed = discord.Embed(title="")
			embed.color = discord.Color.dark_green()
			self.set_author(message, embed)
			embed.add_field(name="No Notifications Pending!", value="Thank you for using TornStonks Live; have a nice day. :wave:")
			await message.channel.send(embed=embed, mention_author=False, reference=message)
	else:
		command = message.content.split(" ", 3)
		c_len = len(command)
		if c_len > 1:
			# Anti idiot security
			if c_len >= 3:
				known_types = ["up", "down", "loss", "up_react", "down_react"]
				if command[2].lower() not in known_types:
					embed = discord.Embed(title=":no_entry_sign: Invalid Argument: :no_entry_sign:")
					embed.color = discord.Color.red()
					self.set_author(message, embed)
					embed.add_field(name="Details:", value='Command argument after stock ticker must be "up", "down", "loss", "up_react" or "down_react.')
					await message.channel.send(embed=embed, mention_author=False, reference=message)
					return
				
			if c_len == 4:
				command[3] = self.strip_commas(command[3])
				if not command[3].isdigit():
					embed = discord.Embed(title=":no_entry_sign: Invalid Argument: :no_entry_sign:")
					embed.color = discord.Color.red()
					self.set_author(message, embed)
					embed.add_field(name="Details:", value='Command argument after notification type must be a number, argument example: `123.45`')
					await message.channel.send(embed=embed, mention_author=False, reference=message)
					return

			# Remove pending items if we have some
			if int(message.author.id) in config.userdata["id"]:
				for key in range(len(config.userdata["id"])-1, -1, -1):
					if int(message.author.id) == config.userdata["id"][key]:
						if c_len == 4:
							if command[1].lower() == config.userdata["stock"][key] and command[2].lower() == config.userdata["type"][key] and float(command[3]) == config.userdata["value"][key]:
								tsl_lib.util.write_log("[NOTICE]: " + message.author.display_name + " deleted notification: " + str(config.userdata["id"][key]) + "," + config.userdata["type"][key] + "," + config.userdata["stock"][key] + "," + str(config.userdata["value"][key]), tsl_lib.util.current_date())
								del config.userdata["id"][key]
								del config.userdata["type"][key]
								del config.userdata["stock"][key]
								del config.userdata["value"][key]
						elif c_len == 3:
							if command[1].lower() == config.userdata["stock"][key] and command[2].lower() == config.userdata["type"][key]:
								tsl_lib.util.write_log("[NOTICE]: " + message.author.display_name + " deleted notification: " + str(config.userdata["id"][key]) + "," + config.userdata["type"][key] + "," + config.userdata["stock"][key] + "," + str(config.userdata["value"][key]), tsl_lib.util.current_date())
								del config.userdata["id"][key]
								del config.userdata["type"][key]
								del config.userdata["stock"][key]
								del config.userdata["value"][key]
						elif c_len == 2:
							if command[1].lower() == config.userdata["stock"][key]:
								tsl_lib.util.write_log("[NOTICE]: " + message.author.display_name + " deleted notification: " + str(config.userdata["id"][key]) + "," + config.userdata["type"][key] + "," + config.userdata["stock"][key] + "," + str(config.userdata["value"][key]), tsl_lib.util.current_date())
								del config.userdata["id"][key]
								del config.userdata["type"][key]
								del config.userdata["stock"][key]
								del config.userdata["value"][key]
				config.write_user_alerts()
				embed = discord.Embed(title="")
				embed.color = discord.Color.red()
				self.set_author(message, embed)
				embed.add_field(name="Specified Pending Notification(s) Deleted!",  value="Thank you for using TornStonks Live; have a nice day. :wave:")
				await message.channel.send(embed=embed, mention_author=False, reference=message)
			else:
				embed = discord.Embed(title="")
				embed.color = discord.Color.dark_green()
				self.set_author(message, embed)
				embed.add_field(name="No Notifications Pending!", value="Thank you for using TornStonks Live; have a nice day. :wave:")
				await message.channel.send(embed=embed, mention_author=False, reference=message)
		else:
			embed = discord.Embed(title=":no_entry_sign: Invalid Arguments: :no_entry_sign:")
			embed.color = discord.Color.red()
			self.set_author(message, embed)
			embed.add_field(name="Details:", value="Missing the stock ticker. Example commands: `!forget sym` `!forget sym up` `!forget sym up 700`")
			await message.channel.send(embed=embed, mention_author=False, reference=message)

async def notifications(self, message, prefix):
	command = message.content.split(" ", 3)
	if command[0] == prefix+"notifications" or command[0] == prefix+"alerts":
		if len(command) >= 2:
			if command[1].lower() != "up" and command[1].lower() != "down":
				embed = discord.Embed(title=":no_entry_sign: Invalid Argument: :no_entry_sign:")
				embed.color = discord.Color.red()
				self.set_author(message, embed)
				embed.add_field(name="Details:", value='Command argument after stock ticker must be exactly "up" or "down".')
				await message.channel.send(embed=embed, mention_author=False, reference=message)
				return

		if int(message.author.id) in config.userdata["id"]:
			known_alerts = ""
			for key in range(0, len(config.userdata["id"])):
				if int(message.author.id) == config.userdata["id"][key]:
					if len(command) == 3:
						if command[1] == config.userdata["type"][key] and command[2] == config.userdata["stock"][key]:
							known_alerts = known_alerts + "`!" + config.userdata["type"][key] + " " + config.userdata["stock"][key] + " " + "{:,.2f}".format(config.userdata["value"][key]) + "`\n"
					elif len(command) == 2:
						if command[1] == config.userdata["type"][key]:
							known_alerts = known_alerts + "`!" + config.userdata["type"][key] + " " + config.userdata["stock"][key] + " " + "{:,.2f}".format(config.userdata["value"][key]) + "`\n"
					else:
						known_alerts = known_alerts + "`!" + config.userdata["type"][key] + " " + config.userdata["stock"][key] + " " + "{:,.2f}".format(config.userdata["value"][key]) + "`\n"

			if known_alerts != "":
				embed = discord.Embed(title="")
				embed.color = discord.Color.blue()
				self.set_author(message, embed)
				embed.add_field(name="Pending Notifications:", value=known_alerts)
				user = await self.fetch_user(message.author.id)
				await user.send(embed=embed)
			else:
				embed = discord.Embed(title="")
				embed.color = discord.Color.dark_green()
				self.set_author(message, embed)
				embed.add_field(name="No Notifications Pending!", value="Thank you for using TornStonks Live; have a nice day. :wave:")
				await message.channel.send(embed=embed, mention_author=False, reference=message)
		else:
			embed = discord.Embed(title="")
			embed.color = discord.Color.dark_green()
			self.set_author(message, embed)
			embed.add_field(name="No Notifications Pending!", value="Thank you for using TornStonks Live; have a nice day. :wave:")
			await message.channel.send(embed=embed, mention_author=False, reference=message)

async def undo(self, message, prefix):
	if int(message.author.id) in config.userdata["id"]:
		for key in range(len(config.userdata["id"])-1, -1, -1):
			if int(message.author.id) == config.userdata["id"][key]:
				tsl_lib.util.write_log("[NOTICE]: " + message.author.display_name + " deleted notification: " + str(config.userdata["id"][key]) + "," + config.userdata["type"][key] + "," + config.userdata["stock"][key] + "," + str(config.userdata["value"][key]), tsl_lib.util.current_date())
				notice = "!" + config.userdata["type"][key] + " " + config.userdata["stock"][key] + " " + "{:,.2f}".format(config.userdata["value"][key])
				del config.userdata["id"][key]
				del config.userdata["type"][key]
				del config.userdata["stock"][key]
				del config.userdata["value"][key]
				config.write_user_alerts()
				embed = discord.Embed(title="")
				embed.color = discord.Color.red()
				self.set_author(message, embed)
				# Please note this emoji only works on the offical bot;
				# Will find a way to replace this line with one of your choosing
				embed.add_field(name="Mistake Erased.",  value="Try not to make a mess of the channel history next time. <:thonk:721869856508477460>", inline=False)
				embed.add_field(name="Command Undone:", value="```"+notice+"```", inline=False)
				await message.channel.send(embed=embed, mention_author=False, reference=message)
				return
	else:
		embed = discord.Embed(title="")
		embed.color = discord.Color.dark_green()
		self.set_author(message, embed)
		embed.add_field(name="Nothing to Undo!", value="Thank you for using TornStonks Live; have a nice day. :wave:")
		await message.channel.send(embed=embed, mention_author=False, reference=message)