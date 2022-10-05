import discord
import tsl_core.functions as tsl_lib
import tsl_config.config as config

async def alert_roles(self, embed, value, type, ticker):
		tag_type = ""
		if type == "buy":
			tag_type = "[BUY] "
		elif type == "sell":
			tag_type = "[SELL] "
		
		tick = "[" + ticker + "]"
		tsl_lib.util.write_log(tag_type + tick + ": $" + "{:,.3f}".format(value/1000000000) + "bn", tsl_lib.util.current_date())
		for key in range(0, len(config.alert_channels["id"])):
			channel = await self.fetch_channel(config.alert_channels["id"][key])
			sml = "<@&"+str(config.alert_channels["small"][key])+">"
			med = "<@&"+str(config.alert_channels["medium"][key])+">"
			lrg = "<@&"+str(config.alert_channels["large"][key])+">"
			tiny = "<@&"+str(config.alert_channels["tiny"][key])+">"
			# Only send an alert if the channel ID is not zero
			if config.alert_channels["tiny"][key] > 0 and value < (150 * 1000000000):
				await channel.send(tag_type + tick + " - " + tiny, embed=embed)
			else:
				if value >= (750 * 1000000000):
					await channel.send(tag_type + tick + " - " + sml + ", " + med + ", " + lrg, embed=embed)
				elif value >= (450 * 1000000000):
					await channel.send(tag_type + tick + " - " + sml + ", " + med, embed=embed)
				elif value >= (150 * 1000000000):
					await channel.send(tag_type + tick + " - " + sml, embed=embed)
				
def process_stockdata(self):
	# Handle user up and down settings
	for data in config.json_data["data"]:
		# Handle user alerts
		remove_entries = []
		for item in range(0, len(config.userdata["id"])):
			if config.userdata["stock"][item].upper() == data["stock"]:
				if "up" in config.userdata["type"][item]:
					if float(data["price"]) >= config.userdata["value"][item]:
						self.loop.create_task(self.alert_user(item, config.userdata["id"][item], config.userdata["type"][item], config.userdata["stock"][item], config.userdata["value"][item], data))
						remove_entries.append(item)
				elif "down" in config.userdata["type"][item]:
					if float(data["price"]) <= config.userdata["value"][item]:
						self.loop.create_task(self.alert_user(item, config.userdata["id"][item], config.userdata["type"][item], config.userdata["stock"][item], config.userdata["value"][item], data))
						remove_entries.append(item)
				elif config.userdata["type"][item] == "loss":
					if float(data["price"]) <= config.userdata["value"][item]:
						self.loop.create_task(self.alert_user(item, config.userdata["id"][item], config.userdata["type"][item], config.userdata["stock"][item], config.userdata["value"][item], data))
						remove_entries.append(item)

		# Don't bother removing entries when there's no real need to
		if len(remove_entries) > 0:
			for key in range(len(config.userdata["id"])-1, -1, -1):
				if key in remove_entries:
					del config.userdata["id"][key]
					del config.userdata["type"][key]
					del config.userdata["stock"][key]
					del config.userdata["value"][key]
			config.write_user_alerts()
		
		# Detect sudden market changes, such as massive buys >100bn worth of shares and >500bn worth of shares
		total_shares = float(data["total_shares"])
		total_shares_m1 = float(data["interval"]["m1"]["total_shares"])
		investors = int(data["investors"])
		investors_m1 = int(data["interval"]["m1"]["investors"])
		diff_shares = abs(int(total_shares - total_shares_m1))
		price = float(data["price"])
		value_total = diff_shares * price
		price_bn = float(value_total) / 1000000000

		perc_shares = ((total_shares - total_shares_m1) / total_shares_m1) * 100
		diff_investor = int(investors - investors_m1)
		perc_investor = ((investors - investors_m1) / investors_m1) * 100

		# Sell event
		if total_shares < total_shares_m1 and data["stock"] != "TCSE":
			if value_total >= (50 * 1000000000):
				embed = discord.Embed(title= "Large Sell Off: " + data["name"], url="https://www.torn.com/page.php?sid=stocks&stockID="+tsl_lib.util.lut_stock_id(data["stock"])+"&tab=owned")
				embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+data["stock"]+".png")
				embed.color = discord.Color.red()
				embed.add_field(name=":handshake: Change in Shares:", value="-"+"{:,}".format(diff_shares) + " (" + "{:,.2f}".format(perc_shares) + "%)", inline=False)
				embed.add_field(name=":crown: Change in Investors:", value="{:,}".format(diff_investor) + " (" + "{:,.2f}".format(perc_investor) + "%)", inline=False)
				if value_total >= (1000 * 1000000000):
					embed.add_field(name=":moneybag: Sale Info:", value="$"+"{:,.2f}".format(value_total) + " ($" + "{:.3f}".format(price_bn / 1000) + "tn)", inline=False)
				else:
					embed.add_field(name=":moneybag: Sale Info:", value="$"+"{:,.2f}".format(value_total) + " ($" + "{:.3f}".format(price_bn) + "bn)", inline=False)
				embed.add_field(name=":money_with_wings: Share Price:", value="$"+str(data["price"]), inline=False)
				self.loop.create_task(self.alert_roles(embed, value_total, "sell", data["stock"]))
		# Buy event
		elif total_shares > total_shares_m1 and data["stock"] != "TCSE":
			if value_total >= (50 * 1000000000):
				embed = discord.Embed(title="Large Buy In: " + data["name"], url="https://www.torn.com/page.php?sid=stocks&stockID="+tsl_lib.util.lut_stock_id(data["stock"])+"&tab=owned")
				embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+data["stock"]+".png")
				embed.color = discord.Color.green()
				embed.add_field(name=":handshake: Change in Shares:", value="+"+"{:,}".format(diff_shares) + " (" + "{:,.2f}".format(perc_shares) + "%)", inline=False)
				embed.add_field(name=":crown: Change in Investors:", value="{:,}".format(diff_investor) + " (" + "{:,.2f}".format(perc_investor) + "%)", inline=False)
				if value_total >= (1000 * 1000000000):
					embed.add_field(name=":moneybag: Purchase Info:", value="$"+"{:,.2f}".format(value_total) + " ($" + "{:.3f}".format(price_bn / 1000) + "tn)", inline=False)
				else:
					embed.add_field(name=":moneybag: Purchase Info:", value="$"+"{:,.2f}".format(value_total) + " ($" + "{:.3f}".format(price_bn) + "bn)", inline=False)
				embed.add_field(name=":money_with_wings: Share Price:", value="$"+str(data["price"]), inline=False)
				self.loop.create_task(self.alert_roles(embed, value_total, "buy", data["stock"]))