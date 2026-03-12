import discord

import tsl_core.functions as tsl_lib
import tsl_config.config as config

async def predict(self, message, prefix):
	command = message.content.split(" ")

	for key in range(0, len(config.command_channels["id"])):
		if int(message.channel.id) == config.command_channels["id"][key]:
			if config.command_channels["predict"][key] == "dm" and int(message.author.id) not in config.bot_admins:
				embed = discord.Embed(title=":no_entry_sign: Not Allowed In This Channel :no_entry_sign:")
				embed.add_field(name="Details:", value="Prediction discussion must be relegated to it's own channel, or in Direct Messages.")
				self.set_author(message, embed)
				embed.color = discord.Color.red()
				await message.channel.send(embed=embed, mention_author=False, reference=message)
				return

	if len(command) < 4:
		embed = discord.Embed(title=":no_entry_sign: Invalid Arguments :no_entry_sign:")
		embed.add_field(name="Details:", value="Too few arguments. Example command:\n```!predict sym d1 31```")
		self.set_author(message, embed)
		embed.color = discord.Color.red()
		await message.channel.send(embed=embed, mention_author=False, reference=message)
		return

	test_lut = str(command[1].upper())
	if test_lut == "CHD" or test_lut == "CHED":
		embed = discord.Embed(title="<:thonk:721869856508477460> Invalid Argument? <:thonk:721869856508477460>")
		embed.add_field(name="Details:", value="Unless you can read Chedburn's mind or have source code access, we're not predicting anything.")
		self.set_author(message, embed)
		embed.color = discord.Color.red()
		await message.channel.send(embed=embed, mention_author=False, reference=message)
		return
	elif test_lut not in tsl_lib.stock_lut:
		embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
		embed.add_field(name="Details:", value="Stock ticker is not found.")
		self.set_author(message, embed)
		embed.color = discord.Color.red()
		await message.channel.send(embed=embed, mention_author=False, reference=message)
		return
	ohlc_time = str(command[2].lower())
	if ohlc_time not in tsl_lib.util.intervals:
		embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
		embed.add_field(name="Details:", value="Specified time period is not supported. Supported intervals:\n`m1 m5 m15 m30 h1 h2 h4 h6 h12 d1`")
		self.set_author(message, embed)
		embed.color = discord.Color.red()
		await message.channel.send(embed=embed, mention_author=False, reference=message)
		return
	elif ohlc_time == "n1" or ohlc_time == "y1":
		embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
		embed.add_field(name="Details:", value="Specified time period is **currently** not supported. Supported intervals:\n`m1 m5 m15 m30 h1 h2 h4 h6 h12 d1 w1`")
		self.set_author(message, embed)
		embed.color = discord.Color.red()
		await message.channel.send(embed=embed, mention_author=False, reference=message)
		return

	try:
		command[3] = int(command[3])
	except:
		embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
		embed.add_field(name="Details:", value="The multiples of your specified time period is not a number.")
		self.set_author(message, embed)
		embed.color = discord.Color.red()
		await message.channel.send(embed=embed, mention_author=False, reference=message)
		return

	if len(command) == 5:
		try:
			command[4] = int(command[4])
		except:
			command[4] = 2000

	await message.add_reaction("✅")
	graph_return = ""
	try:
		if len(command) == 5:
			graph_return = tsl_lib.analysis.predict_stock(command[1].lower(), command[2].lower(), int(command[3]), True, config.json_data, samples=command[4])
		else:
			graph_return = tsl_lib.analysis.predict_stock(command[1].lower(), command[2].lower(), int(command[3]), True, config.json_data)

	except:
		tsl_lib.util.write_log("[ERROR] PREDICT ERROR: " + message.content, tsl_lib.util.current_date())
		err_embed = discord.Embed(title="PREDICT ERROR:")
		err_embed.set_thumbnail(url=config.notstonks_png)
		self.set_author(message, err_embed)
		err_embed.add_field(name="Details:", value="Something went wrong with generating prediction data.\nCommand used:\n\n```" + message.content + "```")
		err_embed.color = discord.Color.red()
		await message.channel.send(embed=err_embed, mention_author=False, reference=message)
		await message.add_reaction("❌")
		return

	hlvc = graph_return[1]
	ticks = graph_return[3]

	embed = discord.Embed(title="Predictions For " + graph_return[2], url="https://www.torn.com/page.php?sid=stocks&stockID=" + tsl_lib.util.lut_stock_id(test_lut) + "&tab=owned")
	embed.color = discord.Color.blue()
	embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/" + command[1].upper() + ".png")
	self.set_author(message, embed)

	embed.add_field(name="Current Price:", value="**$" + "{:.2f}".format(hlvc["price"]) + "**", inline=True)

	embed.add_field(name="Predicted High:", value="**$" + "{:.2f}".format(hlvc["high"]) + "**", inline=True)

	embed.add_field(name="Predicted Low:", value="**$" + "{:.2f}".format(hlvc["low"]) + "**", inline=True)

	vola_str = "Max Swing: ±**" + "{:.2f}".format(hlvc["volatility"]) + "%**\n"
	vola_str += "Direction: **" + "{:+.2f}".format(hlvc["actual"]) + "%**"
	embed.add_field(name="Volatility:", value=vola_str, inline=True)

	conf_val = hlvc["confidence"] * 100
	conf_str = "**" + "{:.2f}".format(conf_val) + "%**"
	if conf_val < 35:
		conf_str += " :warning:"
	elif conf_val >= 80:
		conf_str += " :white_check_mark:"
	embed.add_field(name="Confidence:", value=conf_str, inline=True)

	embed.add_field(name="Time Scale:", value="From: **" + ticks[0] + " TCT**\nTo: **" + ticks[8] + " TCT**", inline=True)

	embed.add_field(name="Model:", value="XGBoost w/ technical indicators\n(SMA, EMA, RSI, MACD, Bollinger, ATR, ROC)", inline=False)
	embed.add_field(name="Notes:", value="The closer confidence is to 100% the more likely the predictions are mostly accurate from current data. ~~Gamble~~ Invest responsibly.\n\nSmaller timeframes are more prone to incorrect outcomes.\n\n**Graphs are for visual aid, not sound advice.**", inline=False)

	await message.channel.send(embed=embed, mention_author=False, reference=message)
	await message.channel.send(file=discord.File(graph_return[0]))
	return