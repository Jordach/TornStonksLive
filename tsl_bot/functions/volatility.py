from datetime import datetime, timezone
import discord
import tsl_core.functions as tsl_lib
import tsl_config.config as config

async def post_volatility(self, stocks, timestr, limit, timestart, perc):
	current_time = int(datetime.now(timezone.utc).timestamp())
	last_frame = current_time - timestart
	time = datetime.utcfromtimestamp(last_frame).strftime('%H:%M:%S - %d/%m/%y') + " TCT"
	embed = discord.Embed(title="Stocks Over "+ perc + "% Volatility:")
	embed_str = ""
	for i in range(len(stocks)):
		if i == limit:
			break
		ticker = stocks[i][0]
		name = ""
		for data in config.json_data["data"]:
			if ticker.upper() == data["stock"]:
				name = data["name"]
				break
		embed_str = embed_str + name + " (" + stocks[i][0].upper() + "): **" + "{:,.2f}".format(stocks[i][2]) + "%**\n"
	embed.color = discord.Color.orange()
	embed.set_thumbnail(url=config.stonks_png)
	embed.add_field(name="Volatility for the last " + timestr + time, value=embed_str)
	for key in range(0, len(config.alert_channels["id"])):
		channel = await self.fetch_channel(config.alert_channels["id"][key])
		await channel.send(embed=embed)

def process_volatility(self):
	stock_data = []
	for i in range(len(tsl_lib.util.stock_lut)):
		ticker = tsl_lib.util.stock_lut[i].lower()
		try:
			ohlc = tsl_lib.db.get_stock_from_db(ticker, "m30", limit=2)
			vola_real = ((ohlc["Low"][0] - ohlc["High"][0]) / ohlc["High"][0]) * 100
			volatility = abs(vola_real)

			if ohlc["Close"][0] > ohlc["Open"][0]:
				vola_real *= -1
			if volatility >= 0.25:
				stock_data.append((ticker, volatility, vola_real))
		except:
			tsl_lib.util.write_log("[WARNING] Local DB potentially unavailable? " + ticker, tsl_lib.util.current_date())
	
	if len(stock_data) > 0:
		stock_data.sort(key=lambda tup: tup[2], reverse=True)
		self.loop.create_task(self.post_volatility(stock_data, "30 minutes: ", 15, 60 * 30, "0.25"))
	else:
		tsl_lib.util.write_log("[NOTICE] No stocks to post.", tsl_lib.util.current_date())

def process_daily_volatility(self):
	stock_data = []
	for i in range(len(tsl_lib.util.stock_lut)):
		ticker = tsl_lib.util.stock_lut[i].lower()
		try:
			ohlc = tsl_lib.db.get_stock_from_db(ticker, "d1", limit=2)
			vola_real = ((ohlc["Low"][0] - ohlc["High"][0]) / ohlc["High"][0]) * 100
			volatility = abs(vola_real)
			if ohlc["Close"][0] > ohlc["Open"][0]:
				vola_real *= -1
			if volatility >= 0.75:
				stock_data.append((ticker, volatility, vola_real))
		except:
			tsl_lib.util.write_log("[WARNING] Local DB potentially unavailable? " + ticker, tsl_lib.util.current_date())
	
	if len(stock_data) > 0:
		stock_data.sort(key=lambda tup: tup[2], reverse=True)
		self.loop.create_task(self.post_volatility(stock_data, "day: ", 20, 60*60*24, "0.75"))
	else:
		tsl_lib.util.write_log("[NOTICE] No stocks to post. " + ticker, tsl_lib.util.current_date())

def process_weekly_volatility(self):
	stock_data = []
	for i in range(len(tsl_lib.util.stock_lut)):
		ticker = tsl_lib.util.stock_lut[i].lower()
		try:
			# This runs once a week, I think we'll be fine
			ohlc = tsl_lib.db.get_tornsy_candlesticks(ticker, "w1", "2")
			volatility = abs((float(ohlc["data"][0][3]) - float(ohlc["data"][0][2])) / float(ohlc["data"][0][2])) * 100
			vola_real = (float(ohlc["data"][0][3]) - float(ohlc["data"][0][2])) / float(ohlc["data"][0][2]) * 100
			if ohlc["data"][0][1] < ohlc["data"][0][4]:
				vola_real *= -1
			if volatility >= 1.25:
				stock_data.append((ticker, volatility, vola_real))
		except:
			tsl_lib.util.write_log("[WARNING] Local DB potentially unavailable?", tsl_lib.util.current_date())
	
	if len(stock_data) > 0:
		stock_data.sort(key=lambda tup: tup[2], reverse=True)
		self.loop.create_task(self.post_volatility(stock_data, "week: ", 25, 60*60*24*7, "1.25"))
	else:
		tsl_lib.util.write_log("[NOTICE] No stocks to post.", tsl_lib.util.current_date())