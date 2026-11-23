import discord
import tsl_core.functions as tsl_lib
import tsl_config.config as config

# calling async from sync env is like lighting a match at a
# petrol station, seriously NOT recommended
async def alert_user(self, item, id, type, stock, value, data):
	price = "$" + "{:,.2f}".format(value)
	if "up" in type:
		title = data["name"] + " Above Target Price"
		color, heading, thumbnail = discord.Color.orange(), "Stonks!", config.stonks_png
		text = data["name"] + " has reached or exceeded your target price of: " + price + "."
	elif "down" in type:
		title = data["name"] + " Below Target Price"
		color, heading, thumbnail = discord.Color.orange(), "Stonks!", config.stonks_png
		text = data["name"] + " has reached or fallen under your target price of: " + price + "."
	elif type == "loss":
		title = data["name"] + " Below Stop Loss Price"
		color, heading, thumbnail = discord.Color.red(), "Not Stonks!", config.notstonks_png
		text = data["name"] + " has reached or fallen below your stop loss price of: " + price + "."
	else:
		return

	embed = discord.Embed(title=title, url="https://www.torn.com/page.php?sid=stocks&stockID="+tsl_lib.util.lut_stock_id(stock)+"&tab=owned")
	embed.color = color
	embed.add_field(name=heading, value=text)
	embed.set_thumbnail(url=thumbnail)

	# The alert is already removed, so a failed DM (DMs closed, account gone) is logged
	# rather than retried every minute
	try:
		user = await self.fetch_user(id)
		self.set_author_notif(user, embed)
		await user.send(embed=embed)
	except discord.HTTPException as err:
		tsl_lib.util.write_log(
			"[WARNING] Could not DM alert to user " + str(id) + " (" + type + " " + stock.upper() + " " + price + "): " + str(err),
			tsl_lib.util.current_date(),
		)
