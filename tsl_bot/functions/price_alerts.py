import discord
import tsl_core.functions as tsl_lib
import tsl_config.config as config

# calling async from sync env is like lighting a match at a
# petrol station, seriously NOT recommended
async def alert_user(self, item, id, type, stock, value, data):
	if "up" in type:
		embed = discord.Embed(title=data["name"] + " Above Target Price", url="https://www.torn.com/page.php?sid=stocks&stockID="+tsl_lib.util.lut_stock_id(stock)+"&tab=owned")
		embed.color = discord.Color.orange()
		embed.add_field(name="Stonks!", value=data["name"] + " has reached or exceeded your target price of: $" + "{:,.2f}".format(value) + ".")
		embed.set_thumbnail(url=config.stonks_png)
		user = await self.fetch_user(id)
		self.set_author_notif(user, embed)
		await user.send(embed=embed)
	elif "down" in type:
		embed = discord.Embed(title=data["name"] + " Below Target Price", url="https://www.torn.com/page.php?sid=stocks&stockID="+tsl_lib.util.lut_stock_id(stock)+"&tab=owned")
		embed.color = discord.Color.orange()
		embed.add_field(name="Stonks!", value=data["name"] + " has reached or fallen under your target price of: $" + "{:,.2f}".format(value) + ".")
		embed.set_thumbnail(url=config.stonks_png)
		user = await self.fetch_user(id)
		self.set_author_notif(user, embed)
		await user.send(embed=embed)
	elif type == "loss":
		embed = discord.Embed(title=data["name"] + " Below Stop Loss Price", url="https://www.torn.com/page.php?sid=stocks&stockID="+tsl_lib.util.lut_stock_id(stock)+"&tab=owned")
		embed.color = discord.Color.red()
		embed.add_field(name="Not Stonks!", value=data["name"] + " has reached or fallen below your stop loss price of: $" + "{:,.2f}".format(value) + ".")
		embed.set_thumbnail(url=config.notstonks_png)
		user = await self.fetch_user(id)
		self.set_author_notif(user, embed)
		await user.send(embed=embed)
