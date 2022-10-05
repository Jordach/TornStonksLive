import discord
import json
from datetime import datetime

import tsl_core.functions as tsl_lib
import tsl_config.config as config

async def portfolio(self, message, prefix):
	# Do not allow API handling in public
	if message.guild:
		embed = discord.Embed(title=":no_entry_sign: API handling commands not allowed in public channels. :no_entry_sign:")
		embed.add_field(name="Details:", value="Commands that use your personal API key(s) are only allowed in Direct Messages to the bot.")
		self.set_author(message, embed)
		embed.color = discord.Color.red()
		await message.channel.send(embed=embed)

		user = await self.fetch_user(message.author.id)
		await user.send("Hi, it appears you used a Torn API key command in a public channel - these commands only work here, in your Direct Messages. I'm sending this message to you so you, can try it here.\n\n Your previous command was: ```\n" + message.content + "```")
	else:
		command = message.content.split(" ", 4)
		if len(command) > 1:
			torn_req = tsl_lib.util.get_torn_stock_data(command[1])
			# Make people less paranoid by deleting the key after use
			# Python will delete the contents of this function once it returns to the main thread
			message.content = command[0] + command[2] + command[3]
			command[1] = "there_was_an_api_key_here_now_there_isnt"
			if torn_req.status_code == 200:
				torn_json = json.loads(torn_req.text)
				if "error" in torn_json:
					embed = discord.Embed(title="")
					embed.color = discord.Color.red()
					self.set_author(message, embed)
					embed.add_field(name="Details:", value=torn_json["error"]["error"])
					await message.channel.send(embed=embed, mention_author=False, reference=message)
				else:
					embed = discord.Embed(title="Torn Stock Portfolio:", url="https://www.torn.com/page.php?sid=stocks")
					self.set_author(message, embed)
					embed.color = discord.Color.blue()
					# Add a thumbnail for filtered portfolios only.
					if len(command) >= 3:
						embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+command[2].upper()+".png")
					if len(command) == 4:
						if not command[3].isdigit():
							err_embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
							self.set_author(message, err_embed)
							err_embed.color = discord.Color.red()
							err_embed.add_field(name="Details:", value="The numeric argument for number of transactions to list is not a number. Example command: `!portfolio api_key sym 1`")
							await message.channel.send(embed=err_embed, mention_author=False, reference=message)
							return
					emb_value = ""
					for stock in torn_json["stocks"]:
						if len(command) >= 3:
							if tsl_lib.stock_lut[int(stock)-1] == command[2].upper():
								index = 0
								for data in config.json_data["data"]:
									for transaction in torn_json["stocks"][stock]["transactions"]:
										if tsl_lib.stock_lut[int(stock)-1] == data["stock"]:
											if len(command) == 4:
												if index == int(command[3]):
													break
											price_perc = float((float(data["price"]) - torn_json["stocks"][stock]["transactions"][transaction]["bought_price"]) / torn_json["stocks"][stock]["transactions"][transaction]["bought_price"]) * 100
											timestamp = datetime.utcfromtimestamp(int(torn_json["stocks"][stock]["transactions"][transaction]["time_bought"])).strftime('%H:%M:%S - %d/%m/%y TCT')
											emb_value = emb_value + "**" + timestamp + ":**\n"
											emb_value = emb_value + "Purchase Price: $" + str(torn_json["stocks"][stock]["transactions"][transaction]["bought_price"]) + ", (" + "{:,.2f}".format(price_perc) + "%)\n"
											emb_value = emb_value + "Shares: " "{:,}".format(torn_json["stocks"][stock]["transactions"][transaction]["shares"]) + "\n\n"
											index += 1
						else:
							for data in config.json_data["data"]:
								for transaction in torn_json["stocks"][stock]["transactions"]:
									if tsl_lib.stock_lut[int(stock)-1] == data["stock"]:
										price_perc = float((float(data["price"]) - torn_json["stocks"][stock]["transactions"][transaction]["bought_price"]) / torn_json["stocks"][stock]["transactions"][transaction]["bought_price"]) * 100
										timestamp = datetime.utcfromtimestamp(int(torn_json["stocks"][stock]["transactions"][transaction]["time_bought"])).strftime('%H:%M:%S - %d/%m/%y TCT')
										emb_value = emb_value + "**" + timestamp + ":**\n"
										emb_value = emb_value + "Purchase Price: $" + str(torn_json["stocks"][stock]["transactions"][transaction]["bought_price"]) + ", (" + "{:,.2f}".format(price_perc) + "%)\n"
										emb_value = emb_value + "Shares: " "{:,}".format(torn_json["stocks"][stock]["transactions"][transaction]["shares"]) + "\n\n"
						for data in config.json_data["data"]:
							if len(command) >= 3:
								if tsl_lib.stock_lut[int(stock)-1] == command[2].upper() and tsl_lib.stock_lut[int(stock)-1] == data["stock"]:
									embed.add_field(name=data["name"] + " ($" + str(data["price"]) + ")", value=emb_value, inline=False)
									emb_value = ""
							elif tsl_lib.stock_lut[int(stock)-1] == data["stock"] and len(command) == 2:
								embed.add_field(name=data["name"] + " ($" + str(data["price"]) + "):", value=emb_value, inline=False)
								emb_value = ""
					await message.channel.send(embed=embed, mention_author=False, reference=message)	
			else:
				print("Networking issue used in !portfolio")
		else:
			embed = discord.Embed(title=":no_entry_sign: Invalid Arguments :no_entry_sign:")
			embed.color = discord.Color.red()
			self.set_author(message, embed)
			embed.add_field(name="Details:", value="The command arguments are either missing the Torn API key, or too few/too many arguments, try the following example in a DM:\n\n`!portfolio API_key_here sym`")
			await message.channel.send(embed=embed, mention_author=False, reference=message)