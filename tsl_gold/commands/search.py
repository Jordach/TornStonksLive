import discord
from discord import app_commands

import tsl_core.functions as tsl_lib
import tsl_config.config as config

client = config.client

# Valid intervals for pattern scanning (excludes minute-level candles)
SCAN_INTERVALS = ["h1", "h2", "h4", "h6", "h12", "d1"]

async def ticker_autocomplete(interaction: discord.Interaction, current: str):
	# Include "all" as a special option at the top
	options = ["ALL"] + [t for t in tsl_lib.stock_lut]
	return [
		app_commands.Choice(name=t, value=t)
		for t in options
		if current.upper() in t.upper()
	][:25]


async def timeframe_autocomplete(interaction: discord.Interaction, current: str):
	return [
		app_commands.Choice(name=t, value=t)
		for t in SCAN_INTERVALS
		if current.lower() in t.lower()
	][:25]


@client.tree.command(name="search", description="Scan for candlestick patterns and oscillator signals.")
@app_commands.describe(
	ticker="Stock Ticker (IOU, SYM, ...) or ALL to scan every stock.",
	timeframe="Candle Interval (h1, h2, h4, h6, h12, d1)",
	mode="Type of pattern search to run."
)
@app_commands.choices(mode=[
	app_commands.Choice(name="Bullish Patterns", value="bullish"),
	app_commands.Choice(name="Bearish Patterns", value="bearish"),
	app_commands.Choice(name="Oscillators (RSI, STOCH, MACD)", value="osc"),
	app_commands.Choice(name="All Patterns & Oscillators", value="all"),
])
@app_commands.autocomplete(ticker=ticker_autocomplete, timeframe=timeframe_autocomplete)
async def search(interaction: discord.Interaction, ticker: str, timeframe: str = "d1", mode: str = "all"):
	await interaction.response.defer()

	# Search for stocks
	try:
		pattern_results = ""
		if ticker.lower() == "all":
			for stock in tsl_lib.stock_lut:
				scan_res = tsl_lib.analysis.search(stock.lower(), timeframe.lower(), mode.lower(), config.json_data, all_mode=True)
				if scan_res:
					pattern_results += scan_res
		else:
			result = tsl_lib.analysis.search(ticker.lower(), timeframe.lower(), mode.lower(), config.json_data)
			if result:
				pattern_results = result
	except Exception as e:
		tsl_lib.util.write_log(
			"[ERROR] SEARCH ERROR: /search " + ticker + " " + timeframe + " " + mode + " | " + str(e),
			tsl_lib.util.current_date()
		)
		err_embed = discord.Embed(title="SEARCH ERROR:")
		err_embed.color = discord.Color.red()
		err_embed.set_thumbnail(url=config.notstonks_png)
		client.set_author_interaction(interaction, err_embed)
		err_embed.add_field(
			name="Details:",
			value="Something went wrong running the pattern scan.\nCommand used:\n\n```/search " + ticker + " " + timeframe + " " + mode + "```"
		)
		await interaction.followup.send(embed=err_embed)
		return

	# Build title and URLs
	mode_labels = {"bearish": "Bearish", "bullish": "Bullish", "osc": "Oscillators", "all": "All"}
	mode_label = mode_labels.get(mode.lower(), mode)

	embed_url = None
	if ticker.lower() == "all":
		title_text = "Search Results for All Stocks - " + mode_label
	else:
		stock_name = ticker.upper()
		for stock in config.json_data["data"]:
			if stock["stock"] == ticker.upper():
				stock_name = stock["name"]
				break
		title_text = "Search Results for " + stock_name + " - " + mode_label
		embed_url = "https://www.torn.com/page.php?sid=stocks&stockID=" + tsl_lib.util.lut_stock_id(ticker.upper()) + "&tab=owned"

	# No results found
	if not pattern_results:
		embed = discord.Embed(title=title_text, url=embed_url)
		embed.color = discord.Color.blue()
		client.set_author_interaction(interaction, embed)
		if ticker.lower() != "all":
			embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/" + ticker.upper() + ".png")
		embed.add_field(name="Results:", value="No candlestick patterns matched your criteria.")
		await interaction.followup.send(embed=embed)
		return

	# Build embed(s) with overflow handling
	chunks = _split_results(pattern_results)
	embeds = []
	current_embed = discord.Embed(title=title_text, url=embed_url)
	current_embed.color = discord.Color.blue()
	client.set_author_interaction(interaction, current_embed)
	if ticker.lower() != "all":
		current_embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/" + ticker.upper() + ".png")

	embed_char_count = len(title_text)
	field_num = 1

	for chunk in chunks:
		field_name = "Results:" if field_num == 1 else "Results (cont.):"

		if embed_char_count + len(chunk) + len(field_name) > 5800 or field_num > 25:
			embeds.append(current_embed)
			current_embed = discord.Embed(title=title_text + " (cont.)")
			current_embed.color = discord.Color.blue()
			client.set_author_interaction(interaction, current_embed)
			embed_char_count = len(title_text) + 10
			field_num = 1
			field_name = "Results:"

		current_embed.add_field(name=field_name, value=chunk, inline=False)
		embed_char_count += len(chunk) + len(field_name)
		field_num += 1

	embeds.append(current_embed)

	# Send first embed as the followup, rest as regular messages
	first = True
	for emb in embeds:
		if first:
			await interaction.followup.send(embed=emb)
			first = False
		else:
			await interaction.channel.send(embed=emb)


def _split_results(text, limit=1024):
	"""
	Split a long result string into chunks that fit within
	Discord embed field value limits.  Splits on double-newlines
	(stock boundaries) first, then single newlines.
	"""
	if len(text) <= limit:
		return [text]

	chunks = []
	current = ""

	sections = text.split("\n\n")
	for section in sections:
		section = section.strip()
		if not section:
			continue

		candidate = current + ("\n\n" if current else "") + section
		if len(candidate) <= limit:
			current = candidate
		else:
			if current:
				chunks.append(current)
			if len(section) > limit:
				lines = section.split("\n")
				current = ""
				for line in lines:
					line_candidate = current + ("\n" if current else "") + line
					if len(line_candidate) <= limit:
						current = line_candidate
					else:
						if current:
							chunks.append(current)
						current = line[:limit] if len(line) > limit else line
			else:
				current = section

	if current:
		chunks.append(current)

	return chunks if chunks else [text[:limit]]