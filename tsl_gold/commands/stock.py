import asyncio
import re
import discord
from discord import app_commands
import requests
import json
import datetime
import tsl_config.config as config
import tsl_core.functions as tsl_func
import tsl_core.db as tsl_db
client = config.client

async def ticker_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=t, value=t)
        for t in tsl_func.stock_lut
        if current.upper() in t.upper()
    ][:25]  # Discord caps at 25 choices

async def timeframe_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=t, value=t)
        for t in tsl_func.intervals
        if current.lower() in t.lower()
    ][:25]

@client.tree.command(name="stock", description = "View Stock Information")
@app_commands.describe(
    ticker="Stock Ticker Symbol (IOU, SYM, ...)",
    timeframe="Time Range (m1, m5, h1, d1, ...)"
)
@app_commands.autocomplete(ticker=ticker_autocomplete, timeframe=timeframe_autocomplete)
async def stock(interaction: discord.Interaction, ticker: str, timeframe: str = "m1"):
    await interaction.response.defer(ephemeral=config.private_reply(interaction))

    ticker = ticker.upper()
    timestamp = timeframe.strip().lower()

    # Accept either an interval name (m1, h1, d1, w1, ...) or a unix timestamp.
    # Anything else is rejected so it can't be smuggled into the Tornsy URL.
    if not re.fullmatch(r"[a-z]\d{1,3}|\d{1,12}", timestamp):
        await _stock_error(interaction, "Invalid Timeframe", "Use an interval such as `m5`, `h1`, `d1`, `w1`, or a unix timestamp.")
        return

    nicename = timestamp
    if timestamp.isdigit():
        nicename = datetime.datetime.fromtimestamp(int(timestamp), datetime.timezone.utc).strftime('%H:%M:%S - %d/%m/%y TCT')

    try:
        tornsy = await asyncio.to_thread(requests.get, "https://tornsy.com/api/stocks?interval=" + timestamp, timeout=15)
    except requests.RequestException:
        tornsy = None

    if tornsy is not None and tornsy.status_code == 200:
        jsond = json.loads(tornsy.text)
        for data in jsond["data"]:
            if data["stock"] == ticker:
                if timestamp not in data.get("interval", {}):
                    await _stock_error(interaction, "Invalid Timeframe", "Tornsy has no data for the `" + timestamp + "` timeframe.")
                    return
                price = float(data["price"])
                price_h = float(data["interval"][timestamp]["price"])
                perc_price = _pct_change(price, price_h)
                shares = int(data["total_shares"])
                shares_h = int(data["interval"][timestamp]["total_shares"])
                perc_shares = _pct_change(shares, shares_h)
                investors = int(data["investors"])
                embed = discord.Embed(title=data["name"], url="https://www.torn.com/page.php?sid=stocks&stockID="+tsl_func.util.lut_stock_id(data["stock"])+"&tab=owned")
                embed.color = discord.Color.blue()
                client.set_author_interaction(interaction, embed)
                embed.add_field(name=":money_with_wings: Current Price:", value="$"+str(data["price"]), inline=False)
                if timestamp != "m1":
                    embed.add_field(name=":money_with_wings: Historic Price (" + nicename + "):", value="$"+str(data["interval"][timestamp]["price"]) + " (" + str("{:,.2f}".format(perc_price)) + "%)", inline=False)
                embed.add_field(name=":handshake: Shares Owned:", value="{:,}".format(data["total_shares"]), inline=False)
                if timestamp != "m1":
                    embed.add_field(name=":handshake: Historic Shares Owned (" + nicename + "):", value="{:,}".format(data["interval"][timestamp]["total_shares"]) + " (" + str("{:,.2f}".format(perc_shares)) + "%)", inline=False)
                embed.add_field(name=":crown: Investors:", value="{:,}".format(data["investors"]), inline=False)
                if timestamp != "m1":
                    if data["interval"][timestamp]["investors"]:
                        investors_h = int(data["interval"][timestamp]["investors"])
                        perc_investors = _pct_change(investors, investors_h)
                        embed.add_field(name=":crown: Historic Investors (" + nicename + "):", value="{:,}".format(data["interval"][timestamp]["investors"]) + " (" + str("{:,.2f}".format(perc_investors)) + "%)", inline=False)
                    else:
                        embed.add_field(name=":crown: Historic Investors (" + nicename + "):", value="N/A for time period.", inline=False)
                embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+data["stock"]+".png")
                await interaction.followup.send(embed=embed, ephemeral=config.private_reply(interaction))
                return
        # Always answer the interaction, otherwise Discord shows "thinking..." forever
        await _stock_error(interaction, "Unknown Stock", "The stock `" + ticker + "` cannot be found.")
        return
    else:
        embed = discord.Embed(title=":no_entry_sign: Unable to connect to Tornsy. :no_entry_sign:")
        embed.color = discord.Color.red()
        embed.add_field(name="Details:", value="The Tornsy API service might be down.")
        await interaction.followup.send(embed=embed, ephemeral=config.private_reply(interaction))
        return


def _pct_change(now, then):
    """Percentage change from `then` to `now`; 0 when there is no baseline."""
    if not then:
        return 0.0
    return float((now - then) / then) * 100


async def _stock_error(interaction: discord.Interaction, title: str, details: str):
    embed = discord.Embed(title=":no_entry_sign: " + title + " :no_entry_sign:")
    embed.color = discord.Color.red()
    client.set_author_interaction(interaction, embed)
    embed.add_field(name="Details:", value=details)
    await interaction.followup.send(embed=embed, ephemeral=config.private_reply(interaction))