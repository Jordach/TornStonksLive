import json
import random
import discord
from datetime import datetime, timezone
import tsl_core.functions as tsl_lib
import tsl_config.config as config

async def post_recommendations(self, up, down, stoch):
	current_time = int(datetime.now(timezone.utc).timestamp()) + 14400
	time = datetime.utcfromtimestamp(current_time).strftime('%H:%M:%S - %d/%m/%y')

	up_name = ""
	down_name = ""
	stoch_name = ""
	for data in config.json_data["data"]:
		if up["ticker"].upper() == data["stock"]:
			up_name = data["name"] + ", $" + data["price"]
		if down["ticker"].upper() == data["stock"]:
			down_name = data["name"] + ", $" + data["price"]
		if stoch["ticker"].upper() == data["stock"]:
			stoch_name = data["name"] + ", $" + data["price"]

	embed = discord.Embed(title="Suggested Stock Picks:", description="Valid Until: **" + time + " TCT**")
	embed.set_footer(text="Suggestions are picked from 80% or higher confidence predictions, but use them as a starting point for investing.")
	embed.set_thumbnail(url=config.stonks_png)
	embed.color = discord.Color.blue()
	
	# ── Gains pick ──
	embed.add_field(name=":one: Stock Predicted For Gains:", value=up_name, inline=False)
	embed.add_field(name="High:", value="**$" + "{:.2f}".format(up["high"]) + "**", inline=True)
	embed.add_field(name="Low:", value="**$" + "{:.2f}".format(up["low"]) + "**", inline=True)
	embed.add_field(name="Volatility:", value="**" + "{:+.2f}".format(up["actual"]) + "%**", inline=True)

	# ── Loss pick ──
	embed.add_field(name=":two: Stock Predicted For Losses:", value=down_name, inline=False)
	embed.add_field(name="High:", value="**$" + "{:.2f}".format(down["high"]) + "**", inline=True)
	embed.add_field(name="Low:", value="**$" + "{:.2f}".format(down["low"]) + "**", inline=True)
	embed.add_field(name="Volatility:", value="**" + "{:+.2f}".format(down["actual"]) + "%**", inline=True)

	# ── Random pick ──
	embed.add_field(name=":three: Random Stock Pick:", value=stoch_name, inline=False)
	embed.add_field(name="High:", value="**$" + "{:.2f}".format(stoch["high"]) + "**", inline=True)
	embed.add_field(name="Low:", value="**$" + "{:.2f}".format(stoch["low"]) + "**", inline=True)
	embed.add_field(name="Volatility:", value="**" + "{:+.2f}".format(stoch["actual"]) + "%**", inline=True)

	global last_pred_id
	last_pred_id = []
	for key in range(0, len(config.suggestion_channels["id"])):
		channel = await self.fetch_channel(config.suggestion_channels["id"][key])
		last_pred_id.append(await channel.send(embed=embed))
		await last_pred_id[key].add_reaction("1️⃣")
		await last_pred_id[key].add_reaction("2️⃣")
		await last_pred_id[key].add_reaction("3️⃣")


async def post_single_recommendation(self, stoch):
	current_time = int(datetime.now(timezone.utc).timestamp()) + 14400
	time = datetime.utcfromtimestamp(current_time).strftime('%H:%M:%S - %d/%m/%y')

	stoch_name = ""
	for data in config.json_data["data"]:
		if stoch["ticker"].upper() == data["stock"]:
			stoch_name = data["name"] + ", $" + data["price"]

	embed = discord.Embed(title="Suggested Stock Picks:", description="Valid Until: **" + time + " TCT**")
	embed.set_footer(text="Suggestions are picked from 80% or higher confidence predictions, but use them as a starting point for investing.")
	embed.set_thumbnail(url=config.stonks_png)
	embed.color = discord.Color.blue()
	embed.add_field(name="Notice:", value="Due to a lack of suitable values - only random is available.")

	embed.add_field(name=":three: Random Stock Pick:", value=stoch_name, inline=False)
	embed.add_field(name="High:", value="**$" + "{:.2f}".format(stoch["high"]) + "**", inline=True)
	embed.add_field(name="Low:", value="**$" + "{:.2f}".format(stoch["low"]) + "**", inline=True)
	embed.add_field(name="Volatility:", value="**" + "{:+.2f}".format(stoch["actual"]) + "%**", inline=True)

	global last_pred_id
	last_pred_id = []
	for key in range(0, len(config.suggestion_channels["id"])):
		channel = await self.fetch_channel(config.suggestion_channels["id"][key])
		last_pred_id.append(await channel.send(embed=embed))
		await last_pred_id[key].add_reaction("3️⃣")


def make_suggestions(self):
	stock_data = {}
	for i in range(len(tsl_lib.stock_lut)):
		ticker = tsl_lib.stock_lut[i].lower()
		data = tsl_lib.analysis.predict_stock(ticker, "m5", 48, False, config.json_data)
		hlvc = data[1]

		# Only add stocks that pass the confidence threshold
		if hlvc["confidence"] >= 0.8:
			stock_data[ticker] = hlvc

	# Find the top three picks
	stocks = [*stock_data.keys()]
	global best_gain
	global best_loss
	global best_rand
	global not_more

	if len(stocks) >= 5:
		not_more = False

		# Find biggest predicted gain
		up_tick = ""
		up = 0
		for ticker in stocks:
			if stock_data[ticker]["actual"] > up:
				up = stock_data[ticker]["actual"]
				up_tick = ticker

		best_up = stock_data[up_tick]
		best_gain = stock_data[up_tick]

		if up_tick in stock_data:
			del stock_data[up_tick]

		# Find biggest predicted loss
		stocks = [*stock_data.keys()]
		down_tick = ""
		down = 0
		for ticker in stocks:
			if stock_data[ticker]["actual"] < down:
				down = stock_data[ticker]["actual"]
				down_tick = ticker

		best_down = stock_data[down_tick]
		best_loss = stock_data[down_tick]

		if down_tick in stock_data:
			del stock_data[down_tick]

		# Random pick from remaining
		stocks = [*stock_data.keys()]
		stoch_tick = stocks[random.randint(0, len(stocks) - 1)]
		best_rand = stock_data[stoch_tick]

		with open("best_gain.json", "w") as file:
			json.dump(best_gain, file)
		with open("best_loss.json", "w") as file:
			json.dump(best_loss, file)
		with open("best_rand.json", "w") as file:
			json.dump(best_rand, file)

		self.loop.create_task(self.post_recommendations(best_up, best_down, best_rand))
	else:
		not_more = True
		stocks = [*stock_data.keys()]
		if len(stocks) > 0:
			stoch_tick = stocks[random.randint(0, len(stocks) - 1)]
			best_rand = stock_data[stoch_tick]
			self.loop.create_task(self.post_single_recommendation(best_rand))