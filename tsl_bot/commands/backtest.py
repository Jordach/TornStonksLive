import discord

import tsl_core.functions as tsl_lib
import tsl_config.config as config

async def backtest(self, message, prefix):
	command = message.content.split(" ")
	if command[1].lower() == "stoch":
		if len(command) == 2:
			embed = discord.Embed(title="Backtest Help for STOCH:")
			self.set_author(message, embed)
			embed.color = discord.Color.purple()
			embed.add_field(name="Syntax:", value="Optional command arguments that have a set default will be marked in `[square brackets]`.", inline=False)
			embed.add_field(name="Example Command:", value="```\n!backtest stoch sym m15 2000 14 3 0.1 [true/false]\n```", inline=False)
			embed.add_field(name="Ticker Argument:", value="Ticker of the stock you want to backtest against.", inline=False)
			embed.add_field(name="Time Argument:", value="Time frame for the scale of.", inline=False)
			embed.add_field(name="History Argument:", value="Number of previous candlesticks to load.\nDefault: `2000`", inline=False)
			embed.add_field(name="K Argument:", value="Number of closed positions to use.\nDefault: `14`", inline=False)
			embed.add_field(name="D Argument:", value="Number of previous K values to smooth. Cannot exceed the value of K.\nDefault: `3`", inline=False)
			embed.add_field(name="Profit Percentage Argument:", value="Percentage to sell at when K and T reach their triggers.\nDefault: `0.1`", inline=False)
			embed.add_field(name="Show Graph Argument:", value="Whether to display the backtesting graph.\nValid Values: `true / false`\nDefault: `true`", inline=False)
			await message.channel.send(embed=embed, mention_author=False, reference=message)
		elif len(command) < 8:
			embed = discord.Embed(title="Error:")
			self.set_author(message, embed)
			embed.color = discord.Color.red()
			embed.add_field(inline=False, name="Details:", value="Invalid number of arguments, try the built in help: ```\n!backtest stoch\n```")
			await message.channel.send(embed=embed, mention_author=False, reference=message)
		else:
			# Error handler
			if command[2].upper() not in tsl_lib.stock_lut:
				embed = discord.Embed(title="Invalid Argument:")
				self.set_author(message, embed)
				embed.color = discord.Color.red()
				embed.add_field(inline=False, name="Details:", value="Stock ticker not found.")
				await message.channel.send(embed=embed, mention_author=False, reference=message)
				return

			if command[3].lower() not in tsl_lib.intervals:
				embed = discord.Embed(title="Invalid Argument:")
				self.set_author(message, embed)
				embed.color = discord.Color.red()
				embed.add_field(inline=False, name="Details:", value="Interval not supported.\nSupported intervals:\n`m1 m5 m15 m30 h1 h2 h4 h6 h12 d1`")
				await message.channel.send(embed=embed, mention_author=False, reference=message)
				return
			
			try:
				command[4] = int(command[4])
			except:
				command[4] = 2000
			
			try:
				command[5] = int(command[5])
			except:
				command[5] = 14

			try:
				command[6] = int(command[6])
			except:
				command[6] = 3
			
			# Prevent exceeding the value of K
			if command[6] >= command[5]:
				command[6] = 3
			
			try:
				command[7] = float(command[7])
			except:
				command[7] = 0.1
			if command[7] < 0:
				command[7] = 0

			await message.add_reaction("✅")
			stoch_output = []
			try:
				if len(command) == 9:
					if command[8].lower() == "false":
						stoch_output = tsl_lib.analysis.get_stoch(command[2].lower(), command[3].lower(), limit=command[4], k=command[5], t=command[6], profit_perc=command[7], render_graphs=False)
				else:
					stoch_output = tsl_lib.analysis.get_stoch(command[2].lower(), command[3].lower(), limit=command[4], k=command[5], t=command[6], profit_perc=command[7], render_graphs=True)
			except:
				await message.add_reaction("❌")
				return

			embed = discord.Embed(title="Backtesting Results For STOCH:")
			self.set_author(message, embed)
			embed.color = discord.Color.blue()
			time_str = "From: **" + stoch_output[1][0] + " TCT**\n" + "To: **" + stoch_output[1][6] + " TCT **"
			embed.add_field(name="Time Range:", value=time_str, inline=False)
			setting_str = "Ticker: " + command[2].upper() + "\n"
			setting_str += "Time: " + str(command[4]) + " x " + command[3] + "\n"
			setting_str += "Sell Threshold: " + str(command[7]) + "%\n"
			setting_str += "K: " + str(command[5]) + "\n"
			setting_str += "D: " + str(command[6]) + "\n"
			embed.add_field(name="Settings:", value=setting_str, inline=False)
			misc_stats = "Percentage Gained: " + "{:.2f}".format(stoch_output[4]) + "%\n"
			misc_stats += "Times Bought: " + "{:,}".format(stoch_output[2] + 1) + "\n"
			misc_stats += "Times Sold: " + "{:,}".format(stoch_output[3]) + "\n"
			embed.add_field(name="Misc Stats:", value=misc_stats, inline=False)
			await message.channel.send(embed=embed, mention_author=False, reference=message)
			if len(command) == 9:
				if command[8].lower() == "true":
					await message.channel.send(file=discord.File(stoch_output[0]))
			else:
				await message.channel.send(file=discord.File(stoch_output[0]))
	elif command[1].lower() == "ulcer":
		if len(command) == 2:
			embed = discord.Embed(title="Backtest Help for Ulcer Index:")
			self.set_author(message, embed)
			embed.color = discord.Color.purple()
			embed.add_field(name="Syntax:", value="Optional command arguments that have a set default will be marked in `[square brackets]`.", inline=False)
			embed.add_field(name="Example Command:", value="```\n!backtest ulcer sym h1 2400 14\n```", inline=False)
			embed.add_field(name="Ticker Argument:", value="Ticker of the stock you want to backtest against.", inline=False)
			embed.add_field(name="Time Argument:", value="Time frame for the scale of.", inline=False)
			embed.add_field(name="History Argument:", value="Number of previous candlesticks to load.\nDefault: `2000`", inline=False)
			embed.add_field(name="Window:", value="Number of closed positions to use.\nDefault: `14`", inline=False)
			await message.channel.send(embed=embed, mention_author=False, reference=message)
		elif len(command) < 6:
			embed = discord.Embed(title="Error:")
			self.set_author(message, embed)
			embed.color = discord.Color.red()
			embed.add_field(inline=False, name="Details:", value="Invalid number of arguments, try the built in help: ```\n!backtest ulcer\n```")
			await message.channel.send(embed=embed, mention_author=False, reference=message)
		else:
			# Error handler
			if command[2].upper() not in tsl_lib.stock_lut:
				embed = discord.Embed(title="Invalid Argument:")
				self.set_author(message, embed)
				embed.color = discord.Color.red()
				embed.add_field(inline=False, name="Details:", value="Stock ticker not found.")
				await message.channel.send(embed=embed, mention_author=False, reference=message)
				return

			if command[3].lower() not in tsl_lib.intervals:
				embed = discord.Embed(title="Invalid Argument:")
				self.set_author(message, embed)
				embed.color = discord.Color.red()
				embed.add_field(inline=False, name="Details:", value="Interval not supported.\nSupported intervals:\n`m1 m5 m15 m30 h1 h2 h4 h6 h12 d1`")
				await message.channel.send(embed=embed, mention_author=False, reference=message)
				return
			
			try:
				command[4] = int(command[4])
			except:
				command[4] = 2000
			
			try:
				command[5] = int(command[5])
			except:
				command[5] = 14

			await message.add_reaction("✅")
			ulcer_output = []
			try:
				ulcer_output = tsl_lib.analysis.get_ulcer(command[2].lower(), command[3].lower(), limit=command[4], window=command[5], render_graphs=True)
			except:
				await message.add_reaction("❌")
				return

			await message.channel.send(file=discord.File(ulcer_output[0]), mention_author=False, reference=message)