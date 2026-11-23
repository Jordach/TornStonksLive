import asyncio
import discord
from io import BytesIO

import tsl_core.functions as tsl_lib
import tsl_config.config as config

from discord import app_commands

client = config.client

MAX_PREDICTIONS = 200
_predict_lock = asyncio.Lock()

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
	await interaction.response.defer(ephemeral=config.private_reply(interaction))

	ticker = ticker.strip().upper()
	timeframe = timeframe.strip().lower()
	if ticker not in tsl_lib.stock_lut or timeframe not in tsl_lib.intervals:
		err_embed = discord.Embed(title=":no_entry_sign: Invalid Arguments :no_entry_sign:")
		err_embed.color = discord.Color.red()
		client.set_author_interaction(interaction, err_embed)
		err_embed.add_field(name="Details:", value="Unknown stock or timeframe.\nSupported timeframes:\n`" + " ".join(tsl_lib.intervals) + "`")
		await interaction.followup.send(embed=err_embed, ephemeral=config.private_reply(interaction))
		return

	# Longer horizons need more history for training and backtests, so cap them
	predictions = max(1, min(predictions, MAX_PREDICTIONS))

	graph_return = ""
	try:
		# Training is CPU heavy: run it off the event loop so the bot stays responsive,
		# one at a time since XGBoost already uses every core.
		async with _predict_lock:
			graph_return = await asyncio.to_thread(tsl_lib.analysis.predict_stock, ticker.lower(), timeframe, predictions, True, config.json_data, samples)
	except Exception:
		tsl_lib.util.write_log("[ERROR] PREDICT ERROR: " + f"/predict {ticker} {timeframe} {predictions} {samples}", tsl_lib.util.current_date())
		err_embed = discord.Embed(title="PREDICT ERROR:")
		err_embed.set_thumbnail(url=config.notstonks_png)
		client.set_author_interaction(interaction, err_embed)
		err_embed.add_field(name="Details:", value="Something went wrong with generating prediction data.\nCommand used:\n\n```" + f"/predict {ticker} {timeframe} {predictions} {samples}" + "```")
		err_embed.color = discord.Color.red()
		await interaction.followup.send(embed=err_embed, ephemeral=config.private_reply(interaction))
		return

	hlvc = graph_return[1]
	ticks = graph_return[3]

	embed = discord.Embed(title="Predictions For " + graph_return[2], url="https://www.torn.com/page.php?sid=stocks&stockID=" + tsl_lib.util.lut_stock_id(ticker.upper()) + "&tab=owned")
	embed.color = discord.Color.blue()
	embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/" + ticker.upper() + ".png")
	client.set_author_interaction(interaction, embed)

	embed.add_field(name="Current Price:", value="**$" + "{:.2f}".format(hlvc["price"]) + "**", inline=True)

	price = hlvc["price"]
	exp_str = "**$" + "{:.2f}".format(hlvc["expected"]) + "** (" + "{:+.2f}".format((hlvc["expected"] / price - 1) * 100) + "%)"
	embed.add_field(name="Expected Close:", value=exp_str, inline=True)

	if hlvc["band_low"] is not None:
		level = int(hlvc["band_level"] * 100)
		range_str = "**$" + "{:.2f}".format(hlvc["band_low"]) + " – $" + "{:.2f}".format(hlvc["band_high"]) + "**\n"
		range_str += "(" + "{:+.1f}".format((hlvc["band_low"] / price - 1) * 100) + "% to " + "{:+.1f}".format((hlvc["band_high"] / price - 1) * 100) + "%)\n"
		range_str += "Backtest hit rate: **" + "{:.0f}".format(hlvc["band_coverage"] * 100) + "%**"
		range_str += " (" + str(hlvc["band_windows"]) + " independent periods)"
		embed.add_field(name="Likely Close Range (" + str(level) + "%):", value=range_str, inline=True)

	skill_str = "**" + hlvc["skill_label"] + "** (" + "{:+.1f}".format(hlvc["skill"] * 100) + "%)"
	if hlvc["skill"] < 0.01:
		skill_str += " :warning:"
	skill_str += "\nDirection hit: **" + "{:.0f}".format(hlvc["direction_accuracy"] * 100) + "%**"
	skill_str += " (baseline " + "{:.0f}".format(hlvc["direction_baseline"] * 100) + "%)"
	embed.add_field(name="Backtested Skill:", value=skill_str, inline=True)

	embed.add_field(name="Time Scale:", value="From: **" + ticks[0] + " TCT**\nTo: **" + ticks[8] + " TCT**", inline=True)

	embed.add_field(name="Model:", value="XGBoost on log returns, direct multi-horizon\n(momentum, volatility, RSI, MACD, Bollinger, ATR, range position)", inline=False)
	embed.add_field(name="Notes:", value="The **likely close range** is where the price should end up about " + str(int(hlvc["band_level"] * 100)) + "% of the time; the hit rate shows how often that held on recent history. The shaded area on the chart is that range over time.\n\n**Skill** is measured on " + str(hlvc["folds"]) + " walk-forward backtests: how much smaller the model's error was than simply assuming the price stays put. 0% or below means **no edge**, which is normal for Torn prices, so the expected close often sits near today's price.\n\n~~Gamble~~ Invest responsibly. **This bot is not sound advice.**", inline=False)

	if isinstance(graph_return[0], BytesIO):
		await interaction.followup.send(embed=embed, file=discord.File(graph_return[0], filename="prediction_graph.png"), ephemeral=config.private_reply(interaction))
	else:
		await interaction.followup.send(embed=embed, ephemeral=config.private_reply(interaction))
	return