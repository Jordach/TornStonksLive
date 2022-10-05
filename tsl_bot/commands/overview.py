import discord

import tsl_core.functions as tsl_lib
import tsl_config.config as config

async def overview(self, message, prefix):
	command = message.content.split(" ")

	for key in range(0, len(config.command_channels["id"])):
		if int(message.channel.id) == config.command_channels["id"][key]:
			if config.command_channels["predict"][key] == "dm" and int(message.author.id) not in config.bot_admins:
				embed = discord.Embed(title=":no_entry_sign: Not Allowed In This Channel :no_entry_sign:")
				embed.add_field(name="Details:", value="Overview discussion must be relegated to it's own channel, or in Direct Messages.")
				self.set_author(message, embed)
				embed.color = discord.Color.red()
				await message.channel.send(embed=embed, mention_author=False, reference=message)
				return

	if len(command) < 3 or len(command) > 4:
		print(len(command))
		embed = discord.Embed(title=":no_entry_sign: Invalid Arguments :no_entry_sign:")
		embed.add_field(name="Details:", value="Too few/many arguments. Example command:\n```!overview d1 31 [up/down]```")
		self.set_author(message, embed)
		embed.color = discord.Color.red()
		await message.channel.send(embed=embed, mention_author=False, reference=message)
		return

	ohlc_time = str(command[1].lower())
	if ohlc_time not in tsl_lib.intervals:
		embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
		embed.add_field(name="Details:", value="Specified time period is not supported. Supported intervals:\n`m1 m5 m15 m30 h1 h2 h4 h6 h12 d1`")
		self.set_author(message, embed)
		embed.color = discord.Color.red()
		await message.channel.send(embed=embed, mention_author=False, reference=message)
		return
	elif ohlc_time == "n1" or ohlc_time == "y1":
		embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
		embed.add_field(name="Details:", value="Specified time period is **currently** not supported. Supported intervals:\n`m1 m5 m15 m30 h1 h2 h4 h6 h12 d1`")
		self.set_author(message, embed)
		embed.color = discord.Color.red()
		await message.channel.send(embed=embed, mention_author=False, reference=message)
		return

	try:
		command[2] = int(command[2])
	except:
		embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
		embed.add_field(name="Details:", value="The multiples of your specified time period is not a number.")
		self.set_author(message, embed)
		embed.color = discord.Color.red()
		await message.channel.send(embed=embed, mention_author=False, reference=message)
		return
	
	if len(command) == 4:
		if command[3] not in ["up", "down"]:
			embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
			embed.add_field(name="Details:", value="The the optional argument must be up or down.")
			self.set_author(message, embed)
			embed.color = discord.Color.red()
			await message.channel.send(embed=embed, mention_author=False, reference=message)
			return

	await message.add_reaction("✅")
	stock_data = []
	time_ticks = 1234
	for i in range(len(tsl_lib.stock_lut)):
		ticker = tsl_lib.stock_lut[i].lower()
		try:
			graph_return = tsl_lib.analysis.predict_stock(ticker, command[1].lower(), command[2], False, config.json_data)
			hlvc = graph_return[1]
			m1_price = 0
			for data in config.json_data["data"]:
				if ticker.upper() == data["stock"]:
					m1_price = float(data["price"])
					break
			# perc_price = float((price - price_h) / price_h) * 100
			low_perc = float((m1_price - hlvc["avg"]["low"]) / hlvc["avg"]["low"]) * -100
			high_perc = float((m1_price - hlvc["avg"]["high"]) / hlvc["avg"]["high"]) * -100
			if time_ticks == 1234:
				time_ticks = graph_return[3][8]

			if len(command) == 4:
				if command[3] == "up" and high_perc >= 0:		
					stock_data.append((ticker.upper(), m1_price, hlvc["avg"]["low"], low_perc, hlvc["avg"]["high"], high_perc, abs(low_perc) + abs(high_perc), hlvc["avg"]["confidence"] * 100))
				elif command[3] == "down" and high_perc < 0:
					stock_data.append((ticker.upper(), m1_price, hlvc["avg"]["low"], low_perc, hlvc["avg"]["high"], high_perc, abs(low_perc) + abs(high_perc), hlvc["avg"]["confidence"] * 100))
			else:
				stock_data.append((ticker.upper(), m1_price, hlvc["avg"]["low"], low_perc, hlvc["avg"]["high"], high_perc, abs(low_perc) + abs(high_perc), hlvc["avg"]["confidence"] * 100))
		except:
			tsl_lib.util.write_log("[WARNING] Something went wrong with the overview generation.", tsl_lib.util.current_date())
			await message.add_reaction("❌")
		
	# Abandon efforts if there's no stocks
	if len(stock_data) == 0:
		return

	stock_data.sort(key=lambda tup: tup[5], reverse=True)

	embed_str = ""
	for tup in range(8):
		# Abandon adding things if we have less entries than 8
		if len(stock_data) == tup:
			break
		#if i == 8:
			#break
		embed_str = embed_str + stock_data[tup][0] + " ($" + "{:,.2f}".format(stock_data[tup][1]) + "):\nLow: $" + "{:,.2f}".format(stock_data[tup][2]) + " (" + "{:.2f}".format(stock_data[tup][3]) + "%), High: $" + "{:,.2f}".format(stock_data[tup][4]) + " (" + "{:.2f}".format(stock_data[tup][5]) + "%)\nVolatility: " + "{:.2f}".format(stock_data[tup][6]) + "%, Confidence: " + "{:.2f}".format(stock_data[tup][7]) + "%\n\n"
	embed = discord.Embed(title="Overview Valid Until: " + time_ticks + " TCT", )
	embed.color = discord.Color.blue()
	embed.add_field(name=time_ticks + " TCT", value=embed_str)
	self.set_author(message, embed)
	await message.channel.send(embed=embed, mention_author=False, reference=message)