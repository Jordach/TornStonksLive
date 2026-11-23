import math
import discord
from discord import app_commands

import tsl_core.functions as tsl_lib
import tsl_core.numerics as numerics
import tsl_config.config as config

client = config.client

# Torn charges a 0.1% fee when selling shares
SELL_TAX = 0.999


async def ticker_autocomplete(interaction: discord.Interaction, current: str):
	return [
		app_commands.Choice(name=t, value=t)
		for t in tsl_lib.stock_lut
		if current.upper() in t.upper()
	][:25]  # Discord caps at 25 choices


def _find_stock(ticker: str):
	"""Return the cached Tornsy entry for a ticker, or None if unknown."""
	if not config.json_data or "data" not in config.json_data:
		return None
	for data in config.json_data["data"]:
		if data["stock"] == ticker.upper():
			return data
	return None


def _stock_embed(interaction: discord.Interaction, data) -> discord.Embed:
	"""Base embed shared by buy/sell: stock name, Torn link, logo."""
	embed = discord.Embed(
		title=data["name"],
		url="https://www.torn.com/page.php?sid=stocks&stockID=" + tsl_lib.util.lut_stock_id(data["stock"]) + "&tab=owned",
	)
	embed.color = discord.Color.blue()
	client.set_author_interaction(interaction, embed)
	embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/" + data["stock"] + ".png")
	return embed


async def _unknown_stock(interaction: discord.Interaction):
	embed = discord.Embed(title=":no_entry_sign: Invalid Arguments :no_entry_sign:")
	embed.color = discord.Color.red()
	client.set_author_interaction(interaction, embed)
	embed.add_field(name="Details:", value="The stock specified cannot be found.")
	await interaction.response.send_message(embed=embed, ephemeral=True)


async def _bad_number(interaction: discord.Interaction, err: numerics.NumericParseError):
	embed = discord.Embed(title=":no_entry_sign: Invalid Arguments :no_entry_sign:")
	embed.color = discord.Color.red()
	client.set_author_interaction(interaction, embed)
	embed.add_field(name="Details:", value=str(err))
	await interaction.response.send_message(embed=embed, ephemeral=True)


paper = app_commands.Group(name="paper", description="Simulate buying or selling Torn shares at the current price.")


@paper.command(name="buy", description="How many shares can a given amount of cash buy?")
@app_commands.describe(
	cash="Cash on hand to spend (1000000, 1,000,000, 500k, 1.5b, ...)",
	ticker="Stock Ticker (IOU, SYM, ...)",
)
@app_commands.autocomplete(ticker=ticker_autocomplete)
async def paper_buy(interaction: discord.Interaction, cash: str, ticker: str):
	try:
		cash = numerics.parse_int(cash, minimum=1)
	except numerics.NumericParseError as err:
		await _bad_number(interaction, err)
		return

	data = _find_stock(ticker)
	if data is None:
		await _unknown_stock(interaction)
		return

	price = float(data["price"])
	total_shares = math.floor(cash / price)
	total_money = total_shares * price
	money_remainder = cash - total_money

	embed = _stock_embed(interaction, data)
	embed.add_field(name=":handshake: Purchaseable Shares:", value="{:,.0f}".format(total_shares) + " @ $" + str(data["price"]) + " per share.", inline=False)
	embed.add_field(name=":credit_card: Money Spent:", value="$" + "{:,.0f}".format(total_money), inline=False)
	embed.add_field(name=":dollar: Money Leftover:", value="$" + "{:,.0f}".format(money_remainder), inline=False)
	await interaction.response.send_message(embed=embed, ephemeral=config.private_reply(interaction))


@paper.command(name="sell", description="What would a number of shares sell for, before and after tax?")
@app_commands.describe(
	shares="Number of shares to sell (1000000, 1,000,000, 250k, 1.2m, ...)",
	ticker="Stock Ticker (IOU, SYM, ...)",
)
@app_commands.autocomplete(ticker=ticker_autocomplete)
async def paper_sell(interaction: discord.Interaction, shares: str, ticker: str):
	try:
		shares = numerics.parse_int(shares, minimum=1)
	except numerics.NumericParseError as err:
		await _bad_number(interaction, err)
		return

	data = _find_stock(ticker)
	if data is None:
		await _unknown_stock(interaction)
		return

	pre_tax = shares * float(data["price"])
	post_tax = pre_tax * SELL_TAX

	embed = _stock_embed(interaction, data)
	embed.add_field(name=':handshake: Shares "Sold":', value="{:,}".format(shares) + " @ $" + str(data["price"]) + " per share.", inline=False)
	embed.add_field(name=":dollar: Value of Shares Pre Tax:", value="$" + "{:,.0f}".format(pre_tax), inline=False)
	embed.add_field(name=":money_with_wings: Value of Shares Post Tax:", value="$" + "{:,.0f}".format(post_tax), inline=False)
	await interaction.response.send_message(embed=embed, ephemeral=config.private_reply(interaction))


client.tree.add_command(paper)
