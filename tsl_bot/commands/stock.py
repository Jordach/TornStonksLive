import requests
import json
import discord
from datetime import datetime
import tsl_core.functions as tsl_lib
import tsl_config.config as config

async def stock_cmd(self, message, prefix):
	command = message.content.split(" ", 2)
	if len(command) == 3:
		timestamp = str(command[2].lower())
		nicename = timestamp
		if timestamp.isdigit():
			nicename = datetime.utcfromtimestamp(int(timestamp)).strftime('%H:%M:%S - %d/%m/%y TCT')
		tornsy = requests.get("https://tornsy.com/api/stocks?interval=" + timestamp)
		if tornsy.status_code == 200:
			jsond = json.loads(tornsy.text)
			for data in jsond["data"]:
				if data["stock"] == command[1].upper():
					price = float(data["price"])
					price_h = float(data["interval"][timestamp]["price"])
					perc_price = float((price - price_h) / price_h) * 100
					shares = int(data["total_shares"])
					shares_h = int(data["interval"][timestamp]["total_shares"])
					perc_shares = float((shares - shares_h) / shares_h) * 100
					investors = int(data["investors"])
					embed = discord.Embed(title=data["name"], url="https://www.torn.com/page.php?sid=stocks&stockID="+tsl_lib.util.lut_stock_id(data["stock"])+"&tab=owned")
					embed.color = discord.Color.blue()
					self.set_author(message, embed)
					embed.add_field(name=":money_with_wings: Current Price:", value="$"+str(data["price"]), inline=False)
					embed.add_field(name=":money_with_wings: Historic Price (" + nicename + "):", value="$"+str(data["interval"][timestamp]["price"]) + " (" + str("{:,.2f}".format(perc_price)) + "%)", inline=False)
					embed.add_field(name=":handshake: Shares Owned:", value="{:,}".format(data["total_shares"]), inline=False)
					embed.add_field(name=":handshake: Historic Shares Owned (" + nicename + "):", value="{:,}".format(data["interval"][timestamp]["total_shares"]) + " (" + str("{:,.2f}".format(perc_shares)) + "%)", inline=False)
					embed.add_field(name=":crown: Investors:", value="{:,}".format(data["investors"]), inline=False)
					if data["interval"][timestamp]["investors"]:
						investors_h = int(data["interval"][timestamp]["investors"])
						perc_investors = float((investors - investors_h) / investors_h) * 100
						embed.add_field(name=":crown: Historic Investors (" + nicename + "):", value="{:,}".format(data["interval"][timestamp]["investors"]) + " (" + str("{:,.2f}".format(perc_investors)) + "%)", inline=False)
					else:
						embed.add_field(name=":crown: Historic Investors (" + nicename + "):", value="N/A for time period.", inline=False)
					embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+data["stock"]+".png")
					await message.channel.send(embed=embed, mention_author=False, reference=message)
					return
		else:
			embed = discord.Embed(title=":no_entry_sign: Unable to connect to Tornsy. :no_entry_sign:")
			embed.color = discord.Color.red()
			embed.add_field(name="Details:", value="Either Tornsy API is down or the timestamp provided is invalid.")
			await message.channel.send(embed=embed, mention_author=False, reference=message)
			return
	if len(command) == 2:
		if command[1].upper() == "CHD" or command[1].upper() == "CHED":
			embed = discord.Embed(title="<:thonk:721869856508477460> Invalid Argument? <:thonk:721869856508477460>")
			embed.add_field(name="Details:", value="I wonder what Ched's account balance looks like after Uncle's donor bender.")
			self.set_author(message, embed)
			embed.color = discord.Color.red()
			await message.channel.send(embed=embed, mention_author=False, reference=message)
			return

		for data in config.json_data["data"]:
			if data["stock"] == command[1].upper():
				price = float(data["price"])
				price_h = float(data["interval"]["h1"]["price"])
				price_d = float(data["interval"]["d1"]["price"])
				price_w = float(data["interval"]["w1"]["price"])
				price_n = float(data["interval"]["n1"]["price"])
				perc_price_h = float((price - price_h) / price_h) * 100
				perc_price_d = float((price - price_d) / price_d) * 100
				perc_price_w = float((price - price_w) / price_w) * 100
				perc_price_n = float((price - price_n) / price_n) * 100

				shares = int(data["total_shares"])
				shares_h = int(data["interval"]["h1"]["total_shares"])
				shares_d = int(data["interval"]["d1"]["total_shares"])
				shares_w = int(data["interval"]["w1"]["total_shares"])
				shares_n = int(data["interval"]["n1"]["total_shares"])
				perc_shares_h = float((shares - shares_h) / shares_h) * 100
				perc_shares_d = float((shares - shares_d) / shares_d) * 100
				perc_shares_w = float((shares - shares_w) / shares_w) * 100
				perc_shares_n = float((shares - shares_n) / shares_n) * 100

				investors = int(data["investors"])
				investors_h = int(data["interval"]["h1"]["investors"])
				investors_d = int(data["interval"]["d1"]["investors"])
				investors_w = int(data["interval"]["w1"]["investors"])
				investors_n = "N/A"
				if data["interval"]["n1"]["investors"]:
					investors_n = int(data["interval"]["n1"]["investors"])
				perc_investors_h = float((investors - investors_h) / investors_h) * 100
				perc_investors_d = float((investors - investors_d) / investors_d) * 100
				perc_investors_w = float((investors - investors_w) / investors_w) * 100
				perc_investors_n = "N/A"
				if data["interval"]["n1"]["investors"]:
					perc_investors_n = float((investors - investors_n) / investors_n) * 100
				
				embed = discord.Embed(title=data["name"], url="https://www.torn.com/page.php?sid=stocks&stockID="+tsl_lib.util.lut_stock_id(data["stock"])+"&tab=owned")
				embed.color = discord.Color.blue()
				self.set_author(message, embed)
				embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+data["stock"]+".png")
				price_str = "$"+"{:,.2f}".format(price) + "\n"
				price_str = price_str + "$"+"{:,.2f}".format(price_h) + " (" + "{:,.2f}".format(perc_price_h) + "%, h1)\n"
				price_str = price_str + "$"+"{:,.2f}".format(price_d) + " (" + "{:,.2f}".format(perc_price_d) + "%, d1)\n"
				price_str = price_str + "$"+"{:,.2f}".format(price_w) + " (" + "{:,.2f}".format(perc_price_w) + "%, w1)\n"
				price_str = price_str + "$"+"{:,.2f}".format(price_n) + " (" + "{:,.2f}".format(perc_price_n) + "%, n1)"
				embed.add_field(name=":money_with_wings: Price:", value=price_str, inline=False)
				
				shares_str = "{:,}".format(shares) + "\n"
				shares_str = shares_str + "{:,}".format(shares_h) + " (" + "{:,.2f}".format(perc_shares_h) + "%, h1)\n"
				shares_str = shares_str + "{:,}".format(shares_d) + " (" + "{:,.2f}".format(perc_shares_d) + "%, d1)\n"
				shares_str = shares_str + "{:,}".format(shares_w) + " (" + "{:,.2f}".format(perc_shares_w) + "%, w1)\n"
				shares_str = shares_str + "{:,}".format(shares_n) + " (" + "{:,.2f}".format(perc_shares_n) + "%, n1)"
				embed.add_field(name=":handshake: Shares Owned:", value=shares_str, inline=False)

				investors_str = "{:,}".format(investors) + "\n"
				investors_str = investors_str + "{:,}".format(investors_h) + " (" + "{:,.2f}".format(perc_investors_h) + "%, h1)\n"
				investors_str = investors_str + "{:,}".format(investors_d) + " (" + "{:,.2f}".format(perc_investors_d) + "%, d1)\n"
				investors_str = investors_str + "{:,}".format(investors_w) + " (" + "{:,.2f}".format(perc_investors_w) + "%, w1)\n"
				if data["interval"]["n1"]["investors"]:
					investors_str = investors_str + "{:,}".format(investors_n) + " (" + "{:,.2f}".format(perc_investors_n) + "%, n1)"
				else:
					investors_str = investors_str + investors_n + " (n1)"
				embed.add_field(name=":crown: Investors:", value=investors_str, inline=False)
				await message.channel.send(embed=embed, mention_author=False, reference=message)
				return
		embed = discord.Embed(title=":no_entry_sign: Stock not found. :no_entry_sign:")
		embed.color = discord.Color.red()
		await message.channel.send(embed=embed, mention_author=False, reference=message)
	else:
		embed = discord.Embed(title=":no_entry_sign: Missing the three letter short name. :no_entry_sign:")
		embed.color = discord.Color.red()
		await message.channel.send(embed=embed, mention_author=False, reference=message)