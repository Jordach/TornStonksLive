import discord
import tsl_core.functions as tsl_lib
import tsl_config.config as config

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
				command[3] = command[3].replace(",", "")
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