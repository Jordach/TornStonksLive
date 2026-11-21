import discord
from discord import app_commands
import json
from datetime import datetime

import tsl_core.functions as tsl_func
import tsl_config.config as config

client = config.client


async def ticker_autocomplete(interaction: discord.Interaction, current: str):
	return [
		app_commands.Choice(name=t, value=t)
		for t in tsl_func.stock_lut
		if current.upper() in t.upper()
	][:25]


@client.tree.command(name="portfolio", description="View your Torn stock portfolio.")
@app_commands.describe(
	ticker="Optional: Filter to a specific stock ticker.",
	limit="Optional: Maximum number of transactions to show per stock.",
)
@app_commands.autocomplete(ticker=ticker_autocomplete)
async def portfolio(interaction: discord.Interaction, ticker: str = None, limit: int = None):
	discord_id = str(interaction.user.id)

	# Retrieve the user's stored key
	api_key = config.get_user_key(discord_id)
	if api_key is None:
		await interaction.response.send_message(
			":no_entry_sign: You don't have a Torn API key stored. "
			"Use `/apikey` to save one first.",
			ephemeral=True,
		)
		return

	# Validate the limit argument early if provided
	if limit is not None and limit < 1:
		await interaction.response.send_message(
			":no_entry_sign: The transaction limit must be at least 1.",
			ephemeral=True,
		)
		return

	# Defer — the Torn API call may take a moment
	await interaction.response.defer()

	# Fetch portfolio from Torn
	torn_req = tsl_func.util.get_torn_stock_data(api_key)

	if torn_req.status_code != 200:
		await interaction.followup.send(
			"Torn API failed to respond in time, or has an error. Blame Ched, then try again shortly."
		)
		return

	torn_json = json.loads(torn_req.text)

	if "error" in torn_json:
		error_code = int(torn_json["error"]["code"])
		if error_code < len(tsl_func.torn_api_error_codes):
			msg = tsl_func.torn_api_error_codes[error_code][0]
		else:
			msg = torn_json["error"]["error"]
		await interaction.followup.send(":no_entry_sign: Torn API error: " + msg)
		return

	# Build the embed
	embed = discord.Embed(
		title="Torn Stock Portfolio:",
		url="https://www.torn.com/page.php?sid=stocks",
	)
	client.set_author_interaction(interaction, embed)
	embed.color = discord.Color.blue()

	# Set thumbnail when filtering to a single ticker
	if ticker is not None:
		ticker = ticker.upper()
		embed.set_thumbnail(
			url="https://www.torn.com/images/v2/stock-market/logos/" + ticker + ".png"
		)

	# Current price data from Tornsy (cached in config.json_data)
	price_lookup = {}
	if config.json_data and "data" in config.json_data:
		for data in config.json_data["data"]:
			price_lookup[data["stock"]] = data

	has_stocks = False

	for stock_id in torn_json.get("stocks", {}):
		stock_idx = int(stock_id) - 1
		if stock_idx < 0 or stock_idx >= len(tsl_func.stock_lut):
			continue
		stock_ticker = tsl_func.stock_lut[stock_idx]

		# If filtering by ticker, skip non-matching stocks
		if ticker is not None and stock_ticker != ticker:
			continue

		market_data = price_lookup.get(stock_ticker)
		if market_data is None:
			continue

		current_price = float(market_data["price"])
		transactions = torn_json["stocks"][stock_id].get("transactions", {})

		emb_value = ""
		index = 0
		for txn_id in transactions:
			if limit is not None and index >= limit:
				break

			txn = transactions[txn_id]
			bought_price = float(txn["bought_price"])
			shares = int(txn["shares"])
			time_bought = int(txn["time_bought"])

			price_perc = ((current_price - bought_price) / bought_price) * 100
			timestamp = datetime.utcfromtimestamp(time_bought).strftime("%H:%M:%S - %d/%m/%y TCT")

			emb_value += "**" + timestamp + ":**\n"
			emb_value += "Purchase Price: $" + str(bought_price) + ", (" + "{:,.2f}".format(price_perc) + "%)\n"
			emb_value += "Shares: " + "{:,}".format(shares) + "\n"

			orig_value = bought_price * shares
			curr_value = current_price * shares
			change = curr_value - orig_value

			if change < 0:
				emb_value += "Change: -$" + "{:,.2f}".format(abs(change)) + "\n\n"
			elif change > 0:
				emb_value += "Change: +$" + "{:,.2f}".format(abs(change)) + "\n\n"
			else:
				emb_value += "Change: $" + "{:,.2f}".format(abs(change)) + "\n\n"

			index += 1

		if emb_value != "":
			has_stocks = True
			embed.add_field(
				name=market_data["name"] + " ($" + str(market_data["price"]) + ")",
				value=emb_value,
				inline=False,
			)

	if not has_stocks:
		if ticker is not None:
			embed.add_field(
				name="No Holdings",
				value="You don't appear to own any **" + ticker + "** shares.",
				inline=False,
			)
		else:
			embed.add_field(
				name="No Holdings",
				value="You don't appear to own any stocks.",
				inline=False,
			)

	await interaction.followup.send(embed=embed)