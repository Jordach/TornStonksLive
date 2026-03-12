import discord
from io import BytesIO

import tsl_core.functions as tsl_lib
import tsl_config.config as config

from discord import app_commands

client = config.client

async def ticker_autocomplete(interaction: discord.Interaction, current: str):
	return [
		app_commands.Choice(name=t, value=t)
		for t in tsl_lib.stock_lut
		if current.upper() in t.upper()
	][:25]  # Discord caps at 25 choices

async def timeframe_autocomplete(interaction: discord.Interaction, current: str):
	return [
		app_commands.Choice(name=t, value=t)
		for t in tsl_lib.intervals
		if current.lower() in t.lower()
	][:25]

@client.tree.command(name="predict", description="Predict a stock's performance.")
@app_commands.describe(
	ticker="Stock Ticker (IOU, SYM, ...)",
	timeframe="Time Interval (m1, m5, h1, d1, ...)",
	predictions="The number of future predicted intervals.",
	samples="How many previous closing prices of prior intervals should be used to train the prediction model?"
)
@app_commands.autocomplete(ticker=ticker_autocomplete, timeframe=timeframe_autocomplete)
async def predict(interaction: discord.Interaction, ticker: str, timeframe: str, predictions: int, samples: int = 2000):
	await interaction.response.defer()

	graph_return = ""
	try:
		graph_return = tsl_lib.analysis.predict_stock(ticker.lower(), timeframe.lower(), predictions, True, config.json_data, samples)
	except:
		tsl_lib.util.write_log("[ERROR] PREDICT ERROR: " + f"/predict {ticker} {timeframe} {predictions} {samples}", tsl_lib.util.current_date())
		err_embed = discord.Embed(title="PREDICT ERROR:")
		err_embed.set_thumbnail(url=config.notstonks_png)
		client.set_author_interaction(interaction, err_embed)
		err_embed.add_field(name="Details:", value="Something went wrong with generating prediction data.\nCommand used:\n\n```" + f"/predict {ticker} {timeframe} {predictions} {samples}" + "```")
		err_embed.color = discord.Color.red()
		await interaction.followup.send(embed=err_embed)
		return

	hlvc = graph_return[1]
	ticks = graph_return[3]

	embed = discord.Embed(title="Predictions For " + graph_return[2], url="https://www.torn.com/page.php?sid=stocks&stockID=" + tsl_lib.util.lut_stock_id(ticker.upper()) + "&tab=owned")
	embed.color = discord.Color.blue()
	embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/" + ticker.upper() + ".png")
	client.set_author_interaction(interaction, embed)

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
	embed.add_field(name="Notes:", value="The closer confidence is to 100% the more likely the predictions are mostly accurate from current data. ~~Gamble~~ Invest responsibly.\n\nSmaller intervals are more prone to incorrect outcomes, try h1, h6 or d1 for improved results.\n\n**This bot is not sound advice.**", inline=False)

	if isinstance(graph_return[0], BytesIO):
		await interaction.followup.send(embed=embed, file=discord.File(graph_return[0], filename="prediction_graph.png"))
	else:
		await interaction.followup.send(embed=embed)
	return