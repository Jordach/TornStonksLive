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
    await interaction.response.defer()

    timestamp = timeframe
    nicename = timestamp
    if timestamp.isdigit():
        nicename = datetime.utcfromtimestamp(int(timestamp)).strftime('%H:%M:%S - %d/%m/%y TCT')
    
    tornsy = requests.get("https://tornsy.com/api/stocks?interval=" + timestamp)
    if tornsy.status_code == 200:
        jsond = json.loads(tornsy.text)
        for data in jsond["data"]:
            if data["stock"] == ticker:
                price = float(data["price"])
                price_h = float(data["interval"][timestamp]["price"])
                perc_price = float((price - price_h) / price_h) * 100
                shares = int(data["total_shares"])
                shares_h = int(data["interval"][timestamp]["total_shares"])
                perc_shares = float((shares - shares_h) / shares_h) * 100
                investors = int(data["investors"])
                embed = discord.Embed(title=data["name"], url="https://www.torn.com/page.php?sid=stocks&stockID="+tsl_func.util.lut_stock_id(data["stock"])+"&tab=owned")
                embed.color = discord.Color.blue()
                client.set_author_interaction(interaction, embed)
                embed.add_field(name=":money_with_wings: Current Price:", value="$"+str(data["price"]), inline=False)
                if timeframe != "m1":
                    embed.add_field(name=":money_with_wings: Historic Price (" + nicename + "):", value="$"+str(data["interval"][timestamp]["price"]) + " (" + str("{:,.2f}".format(perc_price)) + "%)", inline=False)
                embed.add_field(name=":handshake: Shares Owned:", value="{:,}".format(data["total_shares"]), inline=False)
                if timeframe != "m1":
                    embed.add_field(name=":handshake: Historic Shares Owned (" + nicename + "):", value="{:,}".format(data["interval"][timestamp]["total_shares"]) + " (" + str("{:,.2f}".format(perc_shares)) + "%)", inline=False)
                embed.add_field(name=":crown: Investors:", value="{:,}".format(data["investors"]), inline=False)
                if timeframe != "m1":
                    if data["interval"][timestamp]["investors"]:
                        investors_h = int(data["interval"][timestamp]["investors"])
                        perc_investors = float((investors - investors_h) / investors_h) * 100
                        embed.add_field(name=":crown: Historic Investors (" + nicename + "):", value="{:,}".format(data["interval"][timestamp]["investors"]) + " (" + str("{:,.2f}".format(perc_investors)) + "%)", inline=False)
                    else:
                        embed.add_field(name=":crown: Historic Investors (" + nicename + "):", value="N/A for time period.", inline=False)
                embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+data["stock"]+".png")
                await interaction.followup.send(embed=embed)
                return
    else:
        embed = discord.Embed(title=":no_entry_sign: Unable to connect to Tornsy. :no_entry_sign:")
        embed.color = discord.Color.red()
        embed.add_field(name="Details:", value="The Tornsy API service might be down.")
        await interaction.followup.send(embed=embed)
        return