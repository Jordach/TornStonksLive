import discord

import tsl_core.functions as tsl_lib
import tsl_config.config as config

async def search(self, message, prefix):		
	command = message.content.split(" ")
	if len(command) == 1:
		embed = discord.Embed(title="Help for Pattern Search:")
		self.set_author(message, embed)
		embed.color = discord.Color.purple()
		embed.add_field(name="Syntax:", value="Optional command arguments that have a set default will be marked in `[square brackets]`.", inline=False)
		embed.add_field(name="Example Command:", value="```!search sym d1 bullish```", inline=False)
		embed.add_field(name="Ticker Argument:", value="Ticker of the stock you want to search for. Use `all` to search all stocks.", inline=False)
		embed.add_field(name="Time Argument:", value="The amount of time contained within a candlestick.\n`m1`, `m5`, `m15` and `m30` are not supported.")
		embed.add_field(name="Type Argument:", value="The type of search you want to execute:\n\n`bullish` for stocks that are going to rise.\n`bearish` for stocks that are going to fall.\n`osc` For RSI and STOCH oscillators in oversold and overbought conditions.\n`all` for all parameters.", inline=False)

		await message.channel.send(embed=embed, mention_author=False, reference=message)
	elif len(command) == 4:
		if command[1].upper() not in tsl_lib.stock_lut and command[1].lower() != "all":
			embed = discord.Embed(title="Error:")
			self.set_author(message, embed)
			embed.color = discord.Color.red()
			embed.add_field(name="Details:", value="Invalid ticker.")
			await message.channel.send(embed=embed, mention_author=False, reference=message)
			return

		valid_times = ["h1", "h2", "h4", "h6", "h12", "d1"]
		if command[2].lower() not in valid_times:
			embed = discord.Embed(title="Error:")
			self.set_author(message, embed)
			embed.color = discord.Color.red()
			embed.add_field(name="Details:", value="Interval not supported.\n`m1`, `m5`, `m15` and `m30` are not supported.")
			await message.channel.send(embed=embed, mention_author=False, reference=message)
			return

		if command[3].lower() not in ["bearish", "bullish", "osc", "all"]:
			embed = discord.Embed(title="Error:")
			self.set_author(message, embed)
			embed.color = discord.Color.red()
			embed.add_field(name="Details:", value="Type of pattern search not supported.")
			await message.channel.send(embed=embed, mention_author=False, reference=message)
			return

		pattern_results = ""
		if command[1] == "all":
			for stock in tsl_lib.stock_lut:
				scan_res = tsl_lib.analysis.search(stock.lower(), command[2].lower(), command[3].lower(), config.json_data, all_mode=True)
				if scan_res != False:
					if len(pattern_results + scan_res) >= 1024:
						break
					else:
						pattern_results += scan_res
		else:
			pattern_results = tsl_lib.analysis.search(command[1].lower(), command[2].lower(), command[3].lower(), config.json_data)

		title_text = "Search Results for "
		if command[1].lower() == "all":
			title_text += "All Stocks - "
		else:
			for stock in config.json_data["data"]:
				if stock["stock"] == command[1].upper():
					title_text += stock["name"] + " - "
					break

		title_text += command[3].lower()

		embed = discord.Embed(title=title_text)
		self.set_author(message, embed)
		embed.color = discord.Color.blue()
		emb_text = ""
		if pattern_results == "" or pattern_results == False:
			emb_text = "No candlestick patterns matched your criteria."
		else:
			emb_text = pattern_results
		embed.add_field(name="Results:", value=emb_text)
		await message.channel.send(embed=embed, mention_author=False, reference=message)
	else:
		embed = discord.Embed(title="Error:")
		self.set_author(message, embed)
		embed.color = discord.Color.red()
		embed.add_field(name="Details:", value="Missing required arguments.")
		await message.channel.send(embed=embed, mention_author=False, reference=message)
		return