import json
import random
import discord
from datetime import datetime, timezone
import tsl_core.functions as tsl_lib
import tsl_config.config as config

async def post_recommendations(self, up, down, stoch):
	current_time = int(datetime.now(timezone.utc).timestamp()) + 14400
	time = datetime.utcfromtimestamp(current_time).strftime('%H:%M:%S - %d/%m/%y')

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
	
	embed.add_field(name=":one: Stock Predicted For Gains For:", value=up_name, inline=False)
	up_high = "SVM: **$" + "{:.2f}".format(up["svm"]["high"]) + "**\n"
	up_high = up_high + "SVML: **$" + "{:.2f}".format(up["svml"]["high"]) + "**\n"
	up_high = up_high + "LR: **$" + "{:.2f}".format(up["lr"]["high"]) + "**\n"
	up_high = up_high + "Avg: **$" + "{:.2f}".format(up["avg"]["high"]) + "**\n"
	embed.add_field(name="High:", value=up_high, inline=True)
	
	up_low = "SVM: **$" + "{:.2f}".format(up["svm"]["low"]) + "**\n"
	up_low = up_low + "SVML: **$" + "{:.2f}".format(up["svml"]["low"]) + "**\n"
	up_low = up_low + "LR: **$" + "{:.2f}".format(up["lr"]["low"]) + "**\n"
	up_low = up_low + "Avg: **$" + "{:.2f}".format(up["avg"]["low"]) + "**\n"
	embed.add_field(name="Low:", value=up_low, inline=True)

	up_vola = "SVM: **" + "{:.2f}".format(up["svm"]["actual"]) + "%**\n"
	up_vola = up_vola + "SVML: **" + "{:.2f}".format(up["svml"]["actual"]) + "%**\n"
	up_vola = up_vola + "LR: **" + "{:.2f}".format(up["lr"]["actual"]) + "%**\n"
	up_vola = up_vola + "Avg: **" + "{:.2f}".format(up["avg"]["actual"]) + "%**\n"
	embed.add_field(name="Volatility:", value=up_vola, inline=True)
	
	embed.add_field(name=":two: Stock Predicted For Losses For:", value=down_name, inline=False)
	down_high = "SVM: **$" + "{:.2f}".format(down["svm"]["high"]) + "**\n"
	down_high = down_high + "SVML: **$" + "{:.2f}".format(down["svml"]["high"]) + "**\n"
	down_high = down_high + "LR: **$" + "{:.2f}".format(down["lr"]["high"]) + "**\n"
	down_high = down_high + "Avg: **$" + "{:.2f}".format(down["avg"]["high"]) + "**\n"
	embed.add_field(name="High:", value=down_high, inline=True)

	down_low = "SVM: **$" + "{:.2f}".format(down["svm"]["low"]) + "**\n"
	down_low = down_low + "SVML: **$" + "{:.2f}".format(down["svml"]["low"]) + "**\n"
	down_low = down_low + "LR: **$" + "{:.2f}".format(down["lr"]["low"]) + "**\n"
	down_low = down_low + "Avg: **$" + "{:.2f}".format(down["avg"]["low"]) + "**\n"
	embed.add_field(name="Low:", value=down_low, inline=True)
	
	down_vola = "SVM: **" + "{:.2f}".format(down["svm"]["actual"]) + "%**\n"
	down_vola = down_vola + "SVML: **" + "{:.2f}".format(down["svml"]["actual"]) + "%**\n"
	down_vola = down_vola + "LR: **" + "{:.2f}".format(down["lr"]["actual"]) + "%**\n"
	down_vola = down_vola + "Avg: **" + "{:.2f}".format(down["avg"]["actual"]) + "%**\n"
	embed.add_field(name="Volatility:", value=down_vola, inline=True)
	
	embed.add_field(name=":three: Random Stock Pick:", value=stoch_name, inline=False)
	stoch_high = "SVM: **$" + "{:.2f}".format(stoch["svm"]["high"]) + "**\n"
	stoch_high = stoch_high + "SVML: **$" + "{:.2f}".format(stoch["svml"]["high"]) + "**\n"
	stoch_high = stoch_high + "LR: **$" + "{:.2f}".format(stoch["lr"]["high"]) + "**\n"
	stoch_high = stoch_high + "Avg: **$" + "{:.2f}".format(stoch["avg"]["high"]) + "**\n"
	embed.add_field(name="High:", value=stoch_high, inline=True)

	stoch_low = "SVM: **$" + "{:.2f}".format(stoch["svm"]["low"]) + "**\n"
	stoch_low = stoch_low + "SVML: **$" + "{:.2f}".format(stoch["svml"]["low"]) + "**\n"
	stoch_low = stoch_low + "LR: **$" + "{:.2f}".format(stoch["lr"]["low"]) + "**\n"
	stoch_low = stoch_low + "Avg: **$" + "{:.2f}".format(stoch["avg"]["low"]) + "**\n"
	embed.add_field(name="Low:", value=stoch_low, inline=True)

	stoch_vola = "SVM: **" + "{:.2f}".format(stoch["svm"]["actual"]) + "%**\n"
	stoch_vola = stoch_vola + "SVML: **" + "{:.2f}".format(stoch["svml"]["actual"]) + "%**\n"
	stoch_vola = stoch_vola + "LR: **" + "{:.2f}".format(stoch["lr"]["actual"]) + "%**\n"
	stoch_vola = stoch_vola + "Avg: **" + "{:.2f}".format(stoch["avg"]["actual"]) + "%**\n"
	embed.add_field(name="Volatility:", value=stoch_vola, inline=True)

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

	for data in config.json_data["data"]:
		if stoch["ticker"].upper() == data["stock"]:
			stoch_name = data["name"] + ", $" + data["price"]

	embed = discord.Embed(title="Suggested Stock Picks:", description="Valid Until: **" + time + " TCT**")
	embed.set_footer(text="Suggestions are picked from 80% or higher confidence predictions, but use them as a starting point for investing.")
	embed.set_thumbnail(url=config.stonks_png)
	embed.color = discord.Color.blue()
	embed.add_field(name="Notice:", value="Due to a lack of suitable values - only random is available.")	

	embed.add_field(name=":three: Random Stock Pick:", value=stoch_name, inline=False)
	stoch_high = "SVM: **$" + "{:.2f}".format(stoch["svm"]["high"]) + "**\n"
	stoch_high = stoch_high + "SVML: **$" + "{:.2f}".format(stoch["svml"]["high"]) + "**\n"
	stoch_high = stoch_high + "LR: **$" + "{:.2f}".format(stoch["lr"]["high"]) + "**\n"
	stoch_high = stoch_high + "Avg: **$" + "{:.2f}".format(stoch["avg"]["high"]) + "**\n"
	embed.add_field(name="High:", value=stoch_high, inline=True)

	stoch_low = "SVM: **$" + "{:.2f}".format(stoch["svm"]["low"]) + "**\n"
	stoch_low = stoch_low + "SVML: **$" + "{:.2f}".format(stoch["svml"]["low"]) + "**\n"
	stoch_low = stoch_low + "LR: **$" + "{:.2f}".format(stoch["lr"]["low"]) + "**\n"
	stoch_low = stoch_low + "Avg: **$" + "{:.2f}".format(stoch["avg"]["low"]) + "**\n"
	embed.add_field(name="Low:", value=stoch_low, inline=True)

	stoch_vola = "SVM: **" + "{:.2f}".format(stoch["svm"]["actual"]) + "%**\n"
	stoch_vola = stoch_vola + "SVML: **" + "{:.2f}".format(stoch["svml"]["actual"]) + "%**\n"
	stoch_vola = stoch_vola + "LR: **" + "{:.2f}".format(stoch["lr"]["actual"]) + "%**\n"
	stoch_vola = stoch_vola + "Avg: **" + "{:.2f}".format(stoch["avg"]["actual"]) + "%**\n"
	embed.add_field(name="Volatility:", value=stoch_vola, inline=True)

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

		# Only add stocks that pass this criteria
		if hlvc["svm"]["confidence"] >= 0.8 or hlvc["lr"]["confidence"] >= 0.8 or hlvc["svml"]["confidence"] >= 0.8:
			stock_data[ticker] = data[1]

	# Find the top three of each
	stocks = [*stock_data.keys()]
	global best_gain
	global best_loss
	global best_rand
	global not_more

	if len(stocks) >= 5:
		not_more = False
		up_tick = ""
		down_tick = ""
		up = 0
		down = 0
		# Handle best gain and loss separately to avoid duplicates
		for k in range(len(stocks)):
			ticker = stocks[k]

			svm = stock_data[ticker]["svm"]["actual"]
			lr = stock_data[ticker]["lr"]["actual"]
			svml = stock_data[ticker]["svml"]["actual"]
			avg = stock_data[ticker]["avg"]["actual"]

			if svm > up:
				up = svm
				up_tick = ticker
			elif lr > up:
				up = lr
				up_tick = ticker
			elif svml > up:
				up = svml
				up_tick = ticker
			elif avg > up:
				up = avg
				up_tick = ticker

		best_up = stock_data[up_tick]
		# Global memory
		best_gain = stock_data[up_tick]
			
		# Remove old entries from the list 
		if up_tick in stock_data:
			del stock_data[up_tick]

		stocks = [*stock_data.keys()]
		for k in range(len(stocks)):
			ticker = stocks[k]

			svm = stock_data[ticker]["svm"]["actual"]
			lr = stock_data[ticker]["lr"]["actual"]
			svml = stock_data[ticker]["svml"]["actual"]
			avg = stock_data[ticker]["avg"]["actual"]

			if svm < down:
				down = svm
				down_tick = ticker
			elif lr < down:
				down = lr
				down_tick = ticker
			elif svml < down:
				down = svml
				down_tick = ticker
			elif avg < down:
				down = avg
				down_tick = ticker

		best_down = stock_data[down_tick]
		# Global memory
		best_loss = stock_data[down_tick]			
	
		# Remove old entries from the list 
		if down_tick in stock_data:
			del stock_data[down_tick]

		# Pick a random stock to ensure a less apparent bias
		stocks = [*stock_data.keys()]
		stoch_tick = stocks[random.randint(0, len(stocks))]
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
		# Pick a random stock since we have < 3
		stocks = [*stock_data.keys()]
		stoch_tick = stocks[random.randint(0, len(stocks))]
		best_rand = stock_data[stoch_tick]
		with open("best_gain.json", "w") as file:
			json.dump(best_rand, file)
		with open("best_loss.json", "w") as file:
			json.dump(best_rand, file)
		with open("best_rand.json", "w") as file:
			json.dump(best_rand, file)
		self.loop.create_task(self.post_single_recommendation(best_rand))

async def suggest_react_add(self, payload):
	user = await self.fetch_user(payload.user_id)
	# The bot should add itself to the userdata list
	if user == self.user:
		return

	# Ignore noisy bots or terrible bots
	if user.bot:
		return

	one = "1️⃣"
	two = "2️⃣"
	three = "3️⃣"
	global last_pred_id
	message_id = int(payload.message_id)
	for message in last_pred_id:
		if message_id == int(message.id):
			global not_more
			if payload.emoji.name == one and not not_more:
				lowest_perc = 10000
				if best_gain["svm"]["actual"] > 0:
					lowest_perc = best_gain["svm"]["actual"]
				if best_gain["svml"]["actual"] < lowest_perc and best_gain["svml"]["actual"] > 0:
					lowest_perc = best_gain["svml"]["actual"]
				if best_gain["lr"]["actual"] < lowest_perc and best_gain["lr"]["actual"] > 0:
					lowest_perc = best_gain["lr"]["actual"]
				if best_gain["avg"]["actual"] < lowest_perc and best_gain["avg"]["actual"] > 0:
					lowest_perc = best_gain["avg"]["actual"]
				for data in config.json_data["data"]:
					if data["stock"] == best_gain["ticker"].upper():
						config.userdata["id"].append(int(payload.user_id))
						config.userdata["type"].append("up_react")
						config.userdata["stock"].append(str(best_gain["ticker"].lower()))
						config.userdata["value"].append(best_gain["price"] * (1 + (lowest_perc / 100)))
						config.write_user_alerts()
						break
			elif payload.emoji.name == two and not not_more:
				lowest_perc = -10000
				if best_loss["svm"]["actual"] < 0:
					lowest_perc = best_loss["svm"]["actual"]
				if best_loss["svml"]["actual"] > lowest_perc and best_loss["svml"]["actual"] < 0:
					lowest_perc = best_loss["svml"]["actual"]
				if best_loss["lr"]["actual"] > lowest_perc and best_loss["lr"]["actual"] < 0:
					lowest_perc = best_loss["lr"]["actual"]
				if best_loss["avg"]["actual"] > lowest_perc and best_loss["avg"]["actual"] < 0:
					lowest_perc = best_loss["avg"]["actual"]
				for data in config.json_data["data"]:
					if data["stock"] == best_loss["ticker"].upper():
						config.userdata["id"].append(int(payload.user_id))
						config.userdata["type"].append("down_react")
						config.userdata["stock"].append(best_loss["ticker"].lower())
						config.userdata["value"].append(best_loss["price"] * (1 + (lowest_perc / 100)))
						config.write_user_alerts()
						break
			elif payload.emoji.name == three:
				# Use the average to determine an up or down setting
				lowest_perc = 0
				if best_rand["avg"]["actual"] < 0:
					lowest_perc = -10000
					if best_rand["svm"]["actual"] > lowest_perc and best_rand["svm"]["actual"] < 0:
						lowest_perc = best_rand["svm"]["actual"]
					if best_rand["svml"]["actual"] > lowest_perc and best_rand["svml"]["actual"] < 0:
						lowest_perc = best_rand["svml"]["actual"]
					if best_rand["lr"]["actual"] > lowest_perc and best_rand["lr"]["actual"] < 0:
						lowest_perc = best_rand["lr"]["actual"]
					if best_rand["avg"]["actual"] > lowest_perc and best_rand["avg"]["actual"] < 0:
						lowest_perc = best_rand["avg"]["actual"]
					for data in config.json_data["data"]:
						if data["stock"] == best_rand["ticker"].upper():
							config.userdata["id"].append(int(payload.user_id))
							config.userdata["type"].append("down_react")
							config.userdata["stock"].append(best_rand["ticker"].lower())
							config.userdata["value"].append(best_rand["price"] * (1 + (lowest_perc / 100)))
							config.write_user_alerts()
							break
				else:
					lowest_perc = 10000
					if best_rand["svm"]["actual"] < lowest_perc and best_rand["svm"]["actual"] > 0:
						lowest_perc = best_gain["svm"]["actual"]
					if best_rand["svml"]["actual"] < lowest_perc and best_rand["svml"]["actual"] > 0:
						lowest_perc = best_gain["svml"]["actual"]
					if best_rand["lr"]["actual"] < lowest_perc and best_rand["lr"]["actual"] > 0:
						lowest_perc = best_gain["lr"]["actual"]
					if best_rand["avg"]["actual"] < lowest_perc and best_rand["avg"]["actual"] > 0:
						lowest_perc = best_gain["avg"]["actual"]
					for data in config.json_data["data"]:
						if data["stock"] == best_rand["ticker"].upper():
							config.userdata["id"].append(int(payload.user_id))
							config.userdata["type"].append("up_react")
							config.userdata["stock"].append(best_rand["ticker"].lower())
							config.userdata["value"].append(best_rand["price"] * (1 + (lowest_perc / 100)))
							config.write_user_alerts()
							break
	
async def suggest_react_remove(self, payload):
	user = await self.fetch_user(payload.user_id)
	# The bot should add itself to the userdata list
	if user == self.user:
		return

	# Ignore noisy bots or terrible bots
	if user.bot:
		return

	global last_pred_id
	one = "1️⃣"
	two = "2️⃣"
	three = "3️⃣"
	global last_pred_id
	message_id = int(payload.message_id)

	for message in last_pred_id:
		if message_id == int(message.id):
			if int(payload.user_id) in config.userdata["id"]:
				for key in range(len(config.userdata["id"])-1, -1, -1):
					if int(user.id) == config.userdata["id"][key]:
						rem_str = ""
						if payload.emoji.name == one and not not_more:
							rem_str = "up_react"
						elif payload.emoji.name == two and not not_more:
							rem_str = "down_react"
						elif payload.emoji.name == three:
							if best_rand["avg"]["actual"] < 0:
								rem_str = "down_react"
							else:
								rem_str = "up_react"
						
						if rem_str == config.userdata["type"][key]:
							tsl_lib.util.write_log("[NOTICE]: " + user.display_name + " deleted notification: " + str(config.userdata["id"][key]) + "," + config.userdata["type"][key] + "," + config.userdata["stock"][key] + "," + str(config.userdata["value"][key]), tsl_lib.util.current_date())
							del config.userdata["id"][key]
							del config.userdata["type"][key]
							del config.userdata["stock"][key]
							del config.userdata["value"][key]
							config.write_user_alerts()
							break