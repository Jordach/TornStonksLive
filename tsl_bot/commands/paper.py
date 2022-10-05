import discord

import tsl_core.functions as tsl_lib
import tsl_config.config as config

async def buy(self, message, prefix):
	command = message.content.split(" ", 3)
	if len(command) == 3:
		command[1] = self.strip_commas(command[1])
		if command[1].isdigit():
			for data in config.json_data["data"]:
				if data["stock"] == command[2].upper():
					money_remainder = float(command[1]) % float(data["price"])
					total_money = float(command[1]) - money_remainder
					total_shares = total_money / float(data["price"])
					
					embed = discord.Embed(title=data["name"], url="https://www.torn.com/page.php?sid=stocks&stockID="+tsl_lib.util.lut_stock_id(data["stock"])+"&tab=owned")
					embed.color = discord.Color.blue()
					self.set_author(message, embed)
					embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+data["stock"]+".png")
					embed.add_field(name=":handshake: Purchaseable Shares:", value="{:,.0f}".format(total_shares) + " @ $" +str(data["price"] + " per share."), inline=False)
					embed.add_field(name=":credit_card: Money Spent:", value="$"+"{:,.0f}".format(total_money), inline=False)
					embed.add_field(name=":dollar: Money Leftover:", value="$"+"{:,.0f}".format(money_remainder), inline=False)
					await message.channel.send(embed=embed, mention_author=False, reference=message)
					return

			embed = discord.Embed(title=":no_entry_sign: Invalid Arguments :no_entry_sign:")
			embed.color = discord.Color.red()
			self.set_author(message, embed)
			embed.add_field(name="Details:", value="The stock specified cannot be found.")
			await message.channel.send(embed=embed, mention_author=False, reference=message)
			return
		else:
			embed = discord.Embed(title=":no_entry_sign: Invalid Arguments :no_entry_sign:")
			embed.color = discord.Color.red()
			self.set_author(message, embed)
			embed.add_field(name="Details:", value="The argument for cash on hand is invalid, ensure it's a number with no commas, dollar signs, or letters.")
			await message.channel.send(embed=embed, mention_author=False, reference=message)
	else:
		embed = discord.Embed(title=":no_entry_sign: Invalid Command :no_entry_sign:")
		embed.color = discord.Color.red()
		self.set_author(message, embed)
		embed.add_field(name="Details:", value="The command arguments are either missing the company or value, or too few or too many arguments, try the following example:\n\n`!buy 1000000000 iou`")
		await message.channel.send(embed=embed, mention_author=False, reference=message)

async def sell(self, message, prefix):
	command = message.content.split(" ", 3)
	if len(command) == 3:
		command[1] = self.strip_commas(command[1])
		if command[1].isdigit():
			for data in config.json_data["data"]:
				if data["stock"] == command[2].upper():
					pre_tax = int(command[1]) * float(data["price"])
					pos_tax = pre_tax * 0.999
					embed = discord.Embed(title=data["name"], url="https://www.torn.com/page.php?sid=stocks&stockID="+tsl_lib.util.lut_stock_id(data["stock"])+"&tab=owned")
					embed.color = discord.Color.blue()
					self.set_author(message, embed)
					embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+data["stock"]+".png")
					embed.add_field(name=':handshake: Shares "Sold":', value="{:,}".format(int(command[1])) + " @ $" + data["price"] + " per share.", inline=False)
					embed.add_field(name=":dollar: Value of Shares Pre Tax:", value="$"+"{:,.0f}".format(pre_tax), inline=False)
					embed.add_field(name=":money_with_wings: Value of Shares Post Tax:", value="$"+"{:,.0f}".format(pos_tax), inline=False)
					await message.channel.send(embed=embed, mention_author=False, reference=message)
					return
			embed = discord.Embed(title=":no_entry_sign: Invalid Arguments :no_entry_sign:")
			embed.color = discord.Color.red()
			self.set_author(message, embed)
			embed.add_field(name="Details:", value="The stock specified cannot be found.")
			await message.channel.send(embed=embed, mention_author=False, reference=message)
			return
		else:
			embed = discord.Embed(title=":no_entry_sign: Invalid Arguments :no_entry_sign:")
			embed.color = discord.Color.red()
			self.set_author(message, embed)
			embed.add_field(name="Details:", value="The argument for number of shares is invalid, ensure it's a number with no commas, or letters.")
			await message.channel.send(embed=embed, mention_author=False, reference=message)
	else:
		embed = discord.Embed(title=":no_entry_sign: Invalid Command :no_entry_sign:")
		embed.color = discord.Color.red()
		self.set_author(message, embed)
		embed.add_field(name="Details:", value="The command arguments are either missing the company or number of shares, or too few or too many arguments, try the following example:\n\n`!sell 1000000 iou`")
		await message.channel.send(embed=embed, mention_author=False, reference=message)