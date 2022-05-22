import requests
import json
import schedule
import time
import threading
import pprint

from datetime import datetime, date
import discord

app_name = "TornStonks Live"
bot_started = False

current_day = ""
def update_date():
	today = date.today()

	global current_day
	current_day = today.strftime("%d_%m_%Y")
update_date()

def write_notification_to_log(log_text):
	ctime = datetime.now()
	time_string = ctime.strftime("[%H:%M:%S] ")
	with open(current_day+".log", "a+") as file:
		file.seek(0)
		contents = file.read(100)
		if len(contents) > 0:
			file.write("\n")
		file.write(time_string+log_text)

notstonks_png = "https://cdn.discordapp.com/attachments/315121916199305218/976306803900022814/tornnotstonks.png"
stonks_png = "https://cdn.discordapp.com/attachments/315121916199305218/976306804176863293/tornstonks.png"

bot_token = ""
channel_id = 0
stockwatch_role = 0
opportunity_role = 0

with open("settings.conf", "r") as system_config:
	config_lines = system_config.readlines()
	count = 0
	for line in config_lines:
		count += 1
		if count == 1:
			bot_token = line.strip()
		elif count == 2:
			channel_id = int(line.strip())
		elif count == 3:
			movement_role = int(line.strip())
		elif count == 4:
			opportunity_role = int(line.strip())
		else:
			break

bot_admins = []
with open("admins.conf", "r") as admin_config:
	lines = admin_config.readlines()
	for line in lines:
		bot_admins.append(int(line.strip()))

userdata = {"id":[], "type":[], "stock":[], "value":[]}
def read_user_alerts():
	with open("userdata.csv", "r") as file:
		lines = file.readlines()
		ln = 1
		global userdata
		for line in lines:
			if ln == 1:
				# Ignore malformed files entirely (even though they'd probably work otherwise)
				if line.strip() != "id,type,stock,value":
					write_notification_to_log("[WARNING] userdata.csv is in an incorrect format, skipping loading.")
					return
				ln+=1
			else:
				data = line.strip().split(",",3)
				if len(data) == 4:
					userdata["id"].append(int(data[0]))
					userdata["type"].append((str(data[1])))
					userdata["stock"].append(str(data[2]))
					userdata["value"].append(float(data[3]))
				else:
					write_notification_to_log("[WARNING] userdata has incorrect data, skipping the malformed line.")
read_user_alerts()

def write_user_alerts():
	global userdata
	id = len(userdata["id"])
	ty = len(userdata["type"])
	st = len(userdata["stock"])
	vl = len(userdata["value"])
	
	if id == ty and id == st and id == vl:
		with open("userdata.csv", "w") as file:
			out = "id,type,stock,value\n"
			for item in range(0, len(userdata["id"])):
				out = out + str(userdata["id"][item]) + ","
				out = out + str(userdata["type"][item]) + ","
				out = out + str(userdata["stock"][item]) + "," 
				out = out + str(userdata["value"][item])
				if item != len(userdata["id"]) - 1:
					out = out + "\n"
			file.write(out)
	else:
		write_notification_to_log("[FATAL] userdata memory corrupted or invalid, restart bot immediately.")

pp = pprint.PrettyPrinter(indent=4)

tornsy_api_address = "https://tornsy.com/api/stocks?interval=m1,m30"
tornsy_data = requests.get(tornsy_api_address)

# Nicked from https://schedule.readthedocs.io/en/stable/background-execution.html
# But I don't think many will actually care.
def run_continuously(interval=1):
	"""Continuously run, while executing pending jobs at each
	elapsed time interval.
	@return cease_continuous_run: threading. Event which can
	be set to cease continuous run. Please note that it is
	*intended behavior that run_continuously() does not run
	missed jobs*. For example, if you've registered a job that
	should run every minute and you set a continuous run
	interval of one hour then your job won't be run 60 times
	at each interval but only once.
	"""
	cease_continuous_run = threading.Event()

	class ScheduleThread(threading.Thread):
		@classmethod
		def run(cls):
			while not cease_continuous_run.is_set():
				schedule.run_pending()
				time.sleep(interval)

	continuous_thread = ScheduleThread()
	continuous_thread.start()
	return cease_continuous_run

json_data = ""
def get_latest_stocks():
	update_date()
	global tornsy_data
	tornsy_data = requests.get(tornsy_api_address)

	if tornsy_data.status_code == 200:
		global json_data
		json_data = json.loads(tornsy_data.text)
		global bot_started
		if bot_started:
			TornStonksLive.process_stockdata(client)
	else:
		write_notification_to_log("[WARNING] Server returned error code: " + tornsy_data.status_code)

# Get initial data
get_latest_stocks()

# Initiate background thread
schedule.every().minute.at(":15").do(get_latest_stocks)
stop_run_continuously = run_continuously()

# Quickly converts between name and ID
stock_lut = [
	"TSB",
	"TCI",
	"SYS",
	"LAG",
	"IOU",
	"GRN",
	"THS",
	"YAZ",
	"TCT",
	"CNC",
	"MSG",
	"TMI",
	"TCP",
	"IIL",
	"FHG",
	"SYM",
	"LSC",
	"PRN",
	"EWM",
	"TCM",
	"ELT",
	"HRG",
	"TGP",
	"MUN",
	"WSU",
	"IST",
	"BAG",
	"EVL",
	"MCS",
	"WLT",
	"TCC",
	"ASS",
]

def lut_stock_id(name):
	id=1
	for item in stock_lut:
		if name == item:
			break
		id+=1
	return str(id)

intent = discord.Intents(messages=True, guilds=True, reactions=True, dm_messages=True, dm_reactions=True, members=True)

class TornStonksLive(discord.Client):
	async def on_ready(self):
		print("Bot logged on as {0}!".format(self.user))
		await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Torn City Stocks"))
		global bot_started
		bot_started = True

	# This is like running with scissors, not going to lie one bit
	# calling async from sync env is like lighting a match at a
	# petrol station, seriously NOT recommended
	async def alert_user(self, item, id, type, stock, value, data):
		global stonks_png
		if type == "up":
			embed = discord.Embed(title=data["name"] + " Above Target Price", url="https://www.torn.com/page.php?sid=stocks&stockID="+lut_stock_id(stock)+"&tab=owned")
			embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+stock+".png")
			embed.color = discord.Color.orange()
			embed.add_field(name="Stonks!", value=data["name"] + " has reached or exceeded your target price of: $" + "{:,}".format(value) + ".")
			embed.set_thumbnail(url=stonks_png)
			user = await self.fetch_user(id)
			embed.set_author(name=user.name, icon_url="https://cdn.discordapp.com/avatars/"+str(id)+"/"+user.avatar+".png")
			await user.send(embed=embed)
		elif type == "down":
			embed = discord.Embed(title=data["name"] + " Below Target Price", url="https://www.torn.com/page.php?sid=stocks&stockID="+lut_stock_id(stock)+"&tab=owned")
			embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+stock+".png")
			embed.color = discord.Color.orange()
			embed.add_field(name="Stonks!", value=data["name"] + " has reached or fallen under your target price of: $" + "{:,}".format(value) + ".")
			embed.set_thumbnail(url=stonks_png)
			user = await self.fetch_user(id)
			embed.set_author(name=user.name, icon_url="https://cdn.discordapp.com/avatars/"+str(id)+"/"+user.avatar+".png")
			await user.send(embed=embed)

	async def alert_opportunity(sel, embed, message):
		channel = await client.fetch_channel(channel_id)
		await channel.send("<@&"+str(opportunity_role)+"> " + message, embed=embed)

	async def alert_opportunity_shares(self, embed):
		channel = await client.fetch_channel(channel_id)
		await channel.send("<@&"+str(opportunity_role)+">", embed=embed)

	async def alert_stockwatch(self, embed):
		channel = await client.fetch_channel(channel_id)
		await channel.send("<@&"+str(stockwatch_role)+">", embed=embed)

	def process_stockdata(self):
		# Handle user up and down settings6
		global json_data
		for data in json_data["data"]:
			# Handle user alerts
			remove_entries = []
			for item in range(0, len(userdata["id"])):
				if userdata["stock"][item].upper() == data["stock"]:
					if userdata["type"][item] == "up":
						if float(data["price"]) >= float(userdata["value"][item]):
							client.loop.create_task(self.alert_user(item, userdata["id"][item], userdata["type"][item], userdata["stock"][item], userdata["value"][item], data))
							remove_entries.append(item)
					elif userdata["type"][item] == "down":
						if float(data["price"]) <= float(userdata["value"][item]):
							client.loop.create_task(self.alert_user(item, userdata["id"][item], userdata["type"][item], userdata["stock"][item], userdata["value"][item], data))
							remove_entries.append(item)
			# Don't bother removing entries when there's no real need to
			if len(remove_entries) > 0:
				for key in range(len(userdata["id"]), -1, -1):
					if key in remove_entries:
						del userdata["id"][key]
						del userdata["type"][key]
						del userdata["stock"][key]
						del userdata["value"][key]
				write_user_alerts()
			
			# Detect sudden market changes, such as massive buys >100bn worth of shares and >500bn worth of shares
			total_shares = float(data["total_shares"])
			total_shares_m1 = float(data["interval"]["m1"]["total_shares"])
			investors = int(data["investors"])
			investors_m1 = int(data["interval"]["m1"]["investors"])
			price = float(data["price"])

			diff_shares = abs(int(total_shares - total_shares_m1))
			perc_shares = ((total_shares - total_shares_m1) / total_shares_m1) * 100
			value_total = diff_shares * price
			diff_investor = abs(int(investors - investors_m1))
			perc_investor = ((investors - investors_m1) / investors_m1) * 100

			# Sell event
			if total_shares < total_shares_m1 and data["stock"] != "TCSE":
				if value_total >= 500000000000:
					embed = discord.Embed(title=data["name"] + " SOLD OFF!", url="https://www.torn.com/page.php?sid=stocks&stockID="+lut_stock_id(data["stock"])+"&tab=owned")
					embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+data["stock"]+".png")
					embed.color = discord.Color.red()
					embed.add_field(name=":handshake: Change in Shares:", value="-"+"{:,}".format(diff_shares) + " (" + "{:,.2f}".format(perc_shares) + "%)", inline=False)
					embed.add_field(name=":crown: Change in Investors:", value="{:,}".format(diff_investor) + " (" + "{:,.2f}".format(perc_investor) + "%)", inline=False)
					embed.add_field(name=":money_with_wings: Sale Info:", value="$"+"{:,}".format(value_total), inline=False)
					client.loop.create_task(self.alert_stockwatch(embed))
				elif value_total >= 100000000000:
					embed = discord.Embed(title=data["name"] + " Sold!", url="https://www.torn.com/page.php?sid=stocks&stockID="+lut_stock_id(data["stock"])+"&tab=owned")
					embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+data["stock"]+".png")
					embed.color = discord.Color.red()
					embed.add_field(name=":handshake: Change in Shares:", value="-"+"{:,}".format(diff_shares) + " (" + "{:,.2f}".format(perc_shares) + "%)", inline=False)
					embed.add_field(name=":crown: Change in Investors:", value="{:,}".format(diff_investor) + " (" + "{:,.2f}".format(perc_investor) + "%)", inline=False)
					embed.add_field(name=":money_with_wings: Sale Info:", value="$"+"{:,}".format(value_total), inline=False)
					client.loop.create_task(self.alert_opportunity_shares(embed))
			# Buy event
			elif total_shares > total_shares_m1 and data["stock"] != "TCSE":
				if value_total >= 500000000000:
					embed = discord.Embed(title=data["name"] + " BOUGHT!", url="https://www.torn.com/page.php?sid=stocks&stockID="+lut_stock_id(data["stock"])+"&tab=owned")
					embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+data["stock"]+".png")
					embed.color = discord.Color.green()
					embed.add_field(name=":handshake: Change in Shares:", value="+"+"{:,}".format(diff_shares) + " (" + "{:,.2f}".format(perc_shares) + "%)", inline=False)
					embed.add_field(name=":crown: Change in Investors:", value="{:,}".format(diff_investor) + " (" + "{:,.2f}".format(perc_investor) + "%)", inline=False)
					embed.add_field(name=":money_with_wings: Purchase Info:", value="$"+"{:,}".format(value_total), inline=False)
					client.loop.create_task(self.alert_stockwatch(embed))
				elif value_total >= 100000000000:
					embed = discord.Embed(title=data["name"] + " Bought!", url="https://www.torn.com/page.php?sid=stocks&stockID="+lut_stock_id(data["stock"])+"&tab=owned")
					embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+data["stock"]+".png")
					embed.color = discord.Color.green()
					embed.add_field(name=":handshake: Change in Shares:", value="+"+"{:,}".format(diff_shares) + " (" + "{:,.2f}".format(perc_shares) + "%)", inline=False)
					embed.add_field(name=":crown: Change in Investors:", value="{:,}".format(diff_investor) + " (" + "{:,.2f}".format(perc_investor) + "%)", inline=False)
					embed.add_field(name=":money_with_wings: Purchase Info:", value="$"+"{:,}".format(value_total), inline=False)
					client.loop.create_task(self.alert_opportunity_shares(embed))
				
	async def on_message(self, message):
		# The bot should never respond to itself, ever
		if message.author == self.user:
			return

		# Only respond in our designated channel to not shit up the place
		if message.channel.id != channel_id and message.guild:
			return

		global json_data
		# Yes, we know this kind of shit is dirty
		if message.content.startswith("!help"):
			if message.content == "!help":
				await message.channel.send("The command reference for this bot can be located at: https://github.com/Jordach/TornStonksLive#command-reference :zap:")
			else:
				command = message.content.split(" ", 2)
				if len(command) > 1:
					await message.channel.send("You've used an extra argument for specific command help, sorry, but that's currently being worked on. In the meantime, use the command reference here: https://github.com/Jordach/TornStonksLive#command-reference :zap:")
				else:
					embed = discord.Embed(title=":no_entry_sign: Invalid Command :no_entry_sign:")
					embed.color = discord.Color.red()
					embed.set_author(name=message.author.display_name, icon_url="https://cdn.discordapp.com/avatars/"+str(message.author.id)+"/"+message.author.avatar+".png")
					embed.add_field(name="Details:", value="The command arguments are either missing or the command is not found.")
					await message.channel.send(embed=embed)
		elif message.content.startswith("!stock"):
			command = message.content.split(" ", 2)
			if len(command) > 2:
				timestamp = str(command[2].lower())
				nicename = timestamp
				if timestamp.isdigit():
					nicename = datetime.utcfromtimestamp(int(timestamp)).strftime('%H:%M:%S - %d/%m/%y TCT')
				tornsy = requests.get("https://tornsy.com/api/stocks?interval=" + timestamp)
				if tornsy.status_code == 200:
					jsond = json.loads(tornsy.text)
					for data in jsond["data"]:
						if data["stock"] == command[1].upper():
							price = float(data["price"])
							price_h = float(data["interval"][timestamp]["price"])
							perc_price = float((price - price_h) / price_h) * 100
							shares = int(data["total_shares"])
							shares_h = int(data["interval"][timestamp]["total_shares"])
							perc_shares = float((shares - shares_h) / shares_h) * 100
							investors = int(data["investors"])
							embed = discord.Embed(title=data["name"], url="https://www.torn.com/page.php?sid=stocks&stockID="+lut_stock_id(data["stock"])+"&tab=owned")
							embed.color = discord.Color.blue()
							embed.set_author(name=message.author.display_name, icon_url="https://cdn.discordapp.com/avatars/"+str(message.author.id)+"/"+message.author.avatar+".png")
							embed.add_field(name=":money_with_wings: Current Price:", value="$"+str(data["price"]), inline=False)
							embed.add_field(name=":money_with_wings: Historic Price (" + nicename + "):", value="$"+str(data["interval"][timestamp]["price"]) + " (" + str("{:,.2f}".format(perc_price)) + "%)", inline=False)
							embed.add_field(name=":handshake: Shares Owned:", value="{:,}".format(data["total_shares"]), inline=False)
							embed.add_field(name=":handshake: Historic Shares Owned (" + nicename + "):", value="{:,}".format(data["interval"][timestamp]["total_shares"]) + " (" + str("{:,.2f}".format(perc_shares)) + "%)", inline=False)
							embed.add_field(name=":crown: Investors:", value="{:,}".format(data["investors"]), inline=False)
							if data["interval"][timestamp]["investors"]:
								investors_h = int(data["interval"][timestamp]["investors"])
								perc_investors = float((investors - investors_h) / investors_h) * 100
								embed.add_field(name=":crown: Historic Investors (" + nicename + "):", value="{:,}".format(data["interval"][timestamp]["investors"]) + " (" + str("{:,.2f}".format(perc_investors)) + "%)", inline=False)
							else:
								embed.add_field(name=":crown: Historic Investors (" + nicename + "):", value="N/A for time period.", inline=False)
							embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+data["stock"]+".png")
							await message.channel.send(embed=embed)
							return
				else:
					embed = discord.Embed(title=":no_entry_sign: Unable to connect to Tornsy. :no_entry_sign:")
					embed.color = discord.Color.red()
					await message.channel.send(embed=embed)
			if len(command) > 1:
				for data in json_data["data"]:
					if data["stock"] == command[1].upper():
						price = float(data["price"])
						price_h = float(data["interval"]["m30"]["price"])
						perc_price = float((price - price_h) / price_h) * 100
						shares = int(data["total_shares"])
						shares_h = int(data["interval"]["m30"]["total_shares"])
						perc_shares = float((shares - shares_h) / shares_h) * 100
						investors = int(data["investors"])
						investors_h = int(data["interval"]["m30"]["investors"])
						perc_investors = float((investors - investors_h) / investors_h) * 100
						embed = discord.Embed(title=data["name"], url="https://www.torn.com/page.php?sid=stocks&stockID="+lut_stock_id(data["stock"])+"&tab=owned")
						embed.color = discord.Color.blue()
						embed.set_author(name=message.author.display_name, icon_url="https://cdn.discordapp.com/avatars/"+str(message.author.id)+"/"+message.author.avatar+".png")
						embed.add_field(name=":money_with_wings: Current Price:", value="$"+str(data["price"]), inline=False)
						embed.add_field(name=":money_with_wings: Historic Price (m30):", value="$"+str(data["interval"]["m30"]["price"]) + " (" + str("{:,.2f}".format(perc_price)) + "%)", inline=False)
						embed.add_field(name=":handshake: Shares Owned:", value="{:,}".format(data["total_shares"]), inline=False)
						embed.add_field(name=":handshake: Historic Shares Owned (m30):", value="{:,}".format(data["interval"]["m30"]["total_shares"]) + " (" + str("{:,.2f}".format(perc_shares)) + "%)", inline=False)
						embed.add_field(name=":crown: Investors:", value=str("{:,}".format(data["investors"])), inline=False)
						embed.add_field(name=":crown: Historic Investors (m30):", value="{:,}".format(data["interval"]["m30"]["investors"]) + " (" + str("{:,.2f}".format(perc_investors)) + "%)", inline=False)
						embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+data["stock"]+".png")
						await message.channel.send(embed=embed)
						return
				embed = discord.Embed(title=":no_entry_sign: Stock not found. :no_entry_sign:")
				embed.color = discord.Color.red()
				await message.channel.send(embed=embed)
			else:
				embed = discord.Embed(title=":no_entry_sign: Missing the three letter short name. :no_entry_sign:")
				embed.color = discord.Color.red()
				await message.channel.send(embed=embed)
		elif message.content.startswith("!up"):
			command = message.content.split(" ", 3)
			if len(command) == 3:
				userdata["id"].append(int(message.author.id))
				userdata["type"].append("up")
				userdata["stock"].append(command[1].lower())
				userdata["value"].append(float(command[2]))
				write_user_alerts()
				embed = discord.Embed(title=":white_check_mark: Will send you a DM when the criteria is reached. :white_check_mark:")
				embed.color = discord.Color.dark_green()
				await message.channel.send(embed=embed)
			else:
				embed = discord.Embed(title=":no_entry_sign: Invalid Command :no_entry_sign:")
				embed.color = discord.Color.red()
				embed.set_author(name=message.author.display_name, icon_url="https://cdn.discordapp.com/avatars/"+str(message.author.id)+"/"+message.author.avatar+".png")
				embed.add_field(name="Details:", value="The command arguments are either missing the company or value, or too few or too many arguments, try the following example:\n\n`!up sym 123.45`")
				await message.channel.send(embed=embed)
		elif message.content.startswith("!down"):
			command = message.content.split(" ", 3)
			if len(command) == 3:
				userdata["id"].append(int(message.author.id))
				userdata["type"].append("up")
				userdata["stock"].append(command[1].lower())
				userdata["value"].append(float(command[2]))
				write_user_alerts()
				await message.channel.send("Will automatically DM you when your stock reaches it's specified price.")
			else:
				embed = discord.Embed(title=":no_entry_sign: Invalid Command :no_entry_sign:")
				embed.color = discord.Color.red()
				embed.set_author(name=message.author.display_name, icon_url="https://cdn.discordapp.com/avatars/"+str(message.author.id)+"/"+message.author.avatar+".png")
				embed.add_field(name="Details:", value="The command arguments are either missing the company or value, or too few or too many arguments, try the following example:\n\n`!down sym 123.45`")
				await message.channel.send(embed=embed)
		elif message.content == "!stop":
			global bot_admins
			if int(message.author.id) in bot_admins:
				write_user_alerts()
				stop_run_continuously.set()
				await client.close()
				return
			else:
				embed = discord.Embed(title=":no_entry_sign: Permission Required :no_entry_sign:")
				embed.color = discord.Color.red()
				embed.set_author(name=message.author.display_name, icon_url="https://cdn.discordapp.com/avatars/"+str(message.author.id)+"/"+message.author.avatar+".png")
				embed.add_field(name="Details:", value="You are not authorised to stop the bot.")
				await message.channel.send(embed=embed)
		#elif message.content.startswith("!test"):
			#user = await self.fetch_user(message.author.id)
			#pp.pprint(user)
			#await user.send("test 2")
			#await message.author.send("test")
			#pp.pprint(message.guild.members)


client = TornStonksLive(intents=intent)
client.run(bot_token)
write_notification_to_log("[STARTUP] " + app_name + " started.")