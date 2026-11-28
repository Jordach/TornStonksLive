import asyncio
import json
import time
import discord
from discord import app_commands
import requests

import tsl_core.functions as tsl_func
import tsl_core.benefits as benefits
import tsl_config.config as config

client = config.client

# Torn data is shared by everyone using /benefit; the item list alone is ~800 KB,
# so it's fetched at most once per CACHE_SECONDS
CACHE_SECONDS = 300
_cache = {"time": 0.0, "stocks": None, "items": None, "point_price": None}
_cache_lock = asyncio.Lock()

# Lines in the per-block breakdown before it's cut short (keeps the field under 1024 chars)
MAX_BREAKDOWN_LINES = 10


class TornError(Exception):
	"""User-facing reason the Torn data couldn't be loaded."""


def _get_json(url):
	req = requests.get(url, timeout=20)
	if req.status_code != 200:
		raise TornError("Torn's API returned HTTP " + str(req.status_code) + ".")
	data = json.loads(req.text)
	if "error" in data:
		code = int(data["error"].get("code", 0))
		if code < len(tsl_func.torn_api_error_codes):
			raise TornError(tsl_func.torn_api_error_codes[code][0])
		raise TornError(str(data["error"].get("error", "Unknown error")))
	return data


def _fetch_torn(api_key):
	"""Stocks with their benefits, every item's market value, and the cheapest point price."""
	data = _get_json("https://api.torn.com/torn/?selections=stocks,items&key=" + api_key)
	point_price = None
	try:
		market = _get_json("https://api.torn.com/market/?selections=pointsmarket&key=" + api_key)
		costs = [listing["cost"] for listing in (market.get("pointsmarket") or {}).values()]
		point_price = min(costs) if costs else None
	except (TornError, requests.RequestException, ValueError):
		# Only the points reward needs it; everything else can still be valued
		pass
	return data.get("stocks") or {}, data.get("items") or {}, point_price


async def _torn_data():
	async with _cache_lock:
		if _cache["stocks"] is None or time.time() - _cache["time"] > CACHE_SECONDS:
			api_key = config.get_public_key()
			if api_key is None:
				raise TornError("The bot has no public Torn API key stored, so it can't look up rewards.")
			try:
				stocks, items, point_price = await asyncio.to_thread(_fetch_torn, api_key)
			except requests.RequestException:
				raise TornError("Torn's API didn't respond in time. Try again shortly.")
			_cache.update(time=time.time(), stocks=stocks, items=items, point_price=point_price)
		return _cache["stocks"], _cache["items"], _cache["point_price"]


def _money(value):
	return "$" + "{:,.0f}".format(value)


def _pct(value):
	"""Percentage with enough places that small returns don't read as 0.0%."""
	if value >= 1:
		return "{:,.1f}".format(value) + "%"
	if value >= 0.01:
		return "{:.2f}".format(value) + "%"
	return "<0.01%" if value > 0 else "0%"


def _days(days):
	if days < benefits.DAYS_PER_YEAR:
		return "{:,}".format(days) + " days"
	return "{:,}".format(days) + " days (~" + "{:,.1f}".format(days / benefits.DAYS_PER_YEAR) + " years)"


async def ticker_autocomplete(interaction: discord.Interaction, current: str):
	return [
		app_commands.Choice(name=t, value=t)
		for t in tsl_func.stock_lut
		if current.upper() in t.upper()
	][:25]


@client.tree.command(name="benefit", description="Shares and cost for a stock's benefit blocks, the reward's value and its return.")
@app_commands.describe(
	ticker="Stock Ticker Symbol (PTS, SYM, ...)",
	number_of_blocks="How many benefit blocks to hold (each one doubles the shares needed). Default 1.",
	nerve_bar="Your max nerve, to compare nerve rewards with a nerve refill.",
)
@app_commands.autocomplete(ticker=ticker_autocomplete)
async def benefit(
	interaction: discord.Interaction,
	ticker: str,
	number_of_blocks: app_commands.Range[int, 1, benefits.MAX_BLOCKS] = 1,
	nerve_bar: app_commands.Range[int, 1, 1000] = None,
):
	ticker = ticker.strip().upper()
	if ticker not in tsl_func.stock_lut:
		await interaction.response.send_message(":no_entry_sign: The stock `" + ticker + "` cannot be found.", ephemeral=True)
		return

	await interaction.response.defer(ephemeral=config.private_reply(interaction))
	try:
		stocks, items, point_price = await _torn_data()
	except TornError as err:
		await _error(interaction, "Unable to reach Torn", str(err))
		return

	stock = next((s for s in stocks.values() if s.get("acronym") == ticker), None)
	if stock is None or not stock.get("benefit"):
		await _error(interaction, "No Benefit Found", "Torn didn't return a benefit for `" + ticker + "`.")
		return

	await interaction.followup.send(embed=_benefit_embed(interaction, stock, items, point_price, number_of_blocks, nerve_bar), ephemeral=config.private_reply(interaction))


def _benefit_embed(interaction, stock, items, point_price, blocks, nerve_bar=None):
	info = stock["benefit"]
	requirement = int(info["requirement"])
	frequency = int(info.get("frequency") or 0)
	passive = info.get("type") == "passive"
	price = float(stock["current_price"])
	ticker = stock["acronym"]

	notes = []
	if passive and blocks > 1:
		notes.append("Passive benefits don't stack, so only one block is worth holding; showing 1 block.")
		blocks = 1

	shares = benefits.shares_for_blocks(requirement, blocks)
	cost = shares * price

	embed = discord.Embed(
		title=stock["name"] + " (" + ticker + ") benefit",
		url="https://www.torn.com/page.php?sid=stocks&stockID=" + str(stock["stock_id"]) + "&tab=owned",
	)
	embed.color = discord.Color.blue()
	client.set_author_interaction(interaction, embed)
	embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/" + ticker + ".png")

	if passive:
		embed.description = "**Passive:** " + info["description"] + " while you hold the shares."
	else:
		embed.description = "**Active:** " + _combined_reward(info["description"], blocks) + " every " + str(frequency) + " days" + \
			(" (" + info["description"] + " per block)." if blocks > 1 else ".")

	block_word = " block" if blocks == 1 else " blocks"
	embed.add_field(
		name=":handshake: Shares needed (" + str(blocks) + block_word + "):",
		value="{:,}".format(shares) + " shares" +
			("" if blocks == 1 else "\n(" + "{:,}".format(requirement) + " for the first block, doubling each block after)"),
		inline=False,
	)
	embed.add_field(
		name=":money_with_wings: Cost:",
		value=_money(cost) + " at $" + "{:,.2f}".format(price) + " per share",
		inline=False,
	)
	total_shares = int(stock.get("total_shares") or 0)
	if total_shares and shares > total_shares:
		notes.append("That's more shares than exist (" + "{:,}".format(total_shares) + " in circulation).")

	if passive:
		embed.add_field(
			name=":chart_with_upwards_trend: Return on investment:",
			value="Passive perks have no payout to value, so there's no return to work out. "
				"You can sell the shares again (less Torn's 0.1% fee).",
			inline=False,
		)
		_add_footer(embed, notes)
		return embed

	reward = benefits.parse_reward(info["description"])
	value, basis, references = benefits.value_reward(reward, items, point_price, nerve_bar)

	if value is None:
		embed.add_field(name=":gift: Payout value:", value="Can't be valued: " + basis + ".", inline=False)
	else:
		per_year = benefits.payouts_in(benefits.DAYS_PER_YEAR, frequency) * value * blocks
		embed.add_field(
			name=":gift: Payout value:",
			value=_money(value) + " per block each payout (" + basis + ")\n" +
				_money(value * blocks) + " every " + str(frequency) + " days, about " + _money(per_year) + " a year",
			inline=False,
		)

	if references:
		if reward["kind"] == "points":
			heading = ":scales: Relative value (as energy, " + str(benefits.REFILL_POINTS) + " points = " + str(benefits.REFILL_ENERGY) + " E refill):"
		else:
			heading = ":scales: Relative value (" + info["description"] + " bought another way):"
		lines = ["• " + benefits.format_count(count) + "× " + label + ": " + _money(ref_value) for label, ref_value, count in references]
		assumption = _stat_assumptions(reward, nerve_bar)
		if assumption:
			lines.append("*" + assumption + "*")
		embed.add_field(name=heading, value="\n".join(lines), inline=False)

	if value is not None and value > 0:
		lines = []
		for years, payouts, earned, pct in benefits.roi(cost, value, blocks, frequency):
			year_word = " year" if years == 1 else " years"
			lines.append("**" + str(years) + year_word + ":** " + _money(earned) + " (" + _pct(pct) + " of cost, " + str(payouts) + " payouts)")
		days = benefits.break_even_days(cost, value, blocks, frequency)
		if days is not None:
			lines.append("Pays for itself after " + _days(days) + ".")
		embed.add_field(name=":chart_with_upwards_trend: Return on investment:", value="\n".join(lines), inline=False)

		if blocks > 1:
			rows = benefits.block_breakdown(requirement, blocks, price, value, frequency)
			lines = []
			for b, block_shares, block_cost, pct in rows[:MAX_BREAKDOWN_LINES]:
				lines.append("Block " + str(b) + ": +" + "{:,}".format(block_shares) + " shares, " + _money(block_cost) + ", " + _pct(pct) + "/yr")
			if len(rows) > MAX_BREAKDOWN_LINES:
				lines.append("… each further block costs double again for the same payout.")
			embed.add_field(name=":bricks: Per block (each pays the same):", value="\n".join(lines), inline=False)

	_add_footer(embed, notes)
	return embed


def _stat_assumptions(reward, nerve_bar):
	"""The player setup energy/nerve comparisons assume, or None for other rewards."""
	refill = str(benefits.REFILL_POINTS) + " point refill"
	if reward["kind"] == "points" or (reward["kind"] == "stat" and reward["name"] == "energy"):
		drinks = "{:g}".format((benefits.ENERGY_DRINK_BOOST - 1) * 100)
		setup = "Assumes a " + str(benefits.REFILL_ENERGY) + " E donator bar (" + refill + ") and faction perks: energy drinks +" + drinks + "%. "
		revive = _money(benefits.REVIVE_PRICE) + " per contracted revive (ranked war hits earn " + \
			_money(benefits.RW_HIT_RANGE[0]) + "-" + _money(benefits.RW_HIT_RANGE[1]) + " depending on activity)."
		if reward["kind"] == "points":
			return setup + "Revives are valued at " + revive
		return setup + "Energy is valued as reviving income: " + revive
	if reward["kind"] == "stat" and reward["name"] == "nerve":
		text = "Assumes faction perks: alcohol gives " + "{:g}".format(benefits.ALCOHOL_BOOST) + "× nerve."
		if nerve_bar:
			return text + " The " + refill + " fills your " + str(nerve_bar) + " nerve bar."
		return text + " Give `nerve_bar` to compare with a " + refill + "."
	return None


def _combined_reward(description, blocks):
	"""What all the blocks pay together, e.g. 3 blocks of "1x Drug Pack" -> "3x Drug Pack"."""
	reward = benefits.parse_reward(description)
	total = reward["amount"] * blocks
	if reward["kind"] == "cash":
		return _money(total)
	if reward["kind"] == "item":
		return str(total) + "x " + reward["name"]
	if reward["kind"] == "stat":
		return "{:,}".format(total) + " " + reward["name"]
	if reward["kind"] == "points":
		return "{:,}".format(total) + " points"
	return description


def _add_footer(embed, notes):
	footer = "Returns count payouts only; share price moves and Torn's 0.1% sell fee aren't included. Item values are Torn market values."
	embed.set_footer(text="\n".join(notes + [footer]))


async def _error(interaction, title, details):
	embed = discord.Embed(title=":no_entry_sign: " + title + " :no_entry_sign:")
	embed.color = discord.Color.red()
	client.set_author_interaction(interaction, embed)
	embed.add_field(name="Details:", value=details)
	await interaction.followup.send(embed=embed, ephemeral=config.private_reply(interaction))
