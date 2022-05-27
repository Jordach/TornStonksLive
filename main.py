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
with open("settings.conf", "r") as system_config:
	config_lines = system_config.readlines()
	count = 0
	for line in config_lines:
		count += 1
		if count == 1:
			bot_token = line.strip()
		else:
			break

if bot_token == "":
	with open() as file:
		file.write("")
	raise Exception("Bot token is missing")

channels = {"id":[], "small":[], "medium":[], "large":[]}
with open("channels.conf", "r") as channel_config:
	lines = channel_config.readlines()
	for line in lines:
		data = line.strip().split(",", 3)
		if len(data) == 4:
			channels["id"].append(int(data[0]))
			channels["small"].append(int(data[1]))
			channels["medium"].append(int(data[2]))
			channels["large"].append(int(data[3]))
		else:
			write_notification_to_log("[WARNING] channels.conf has incorrect data, skipping the malformed line.")

if len(channels["id"]) == 0:
	with open("channels.conf", "w") as file:
		file.write("")
	raise Exception("No channels to send/receive messages to - channels.conf created.")

bot_admins = []
with open("admins.conf", "r") as admin_config:
	lines = admin_config.readlines()
	for line in lines:
		bot_admins.append(int(line.strip()))

if len(bot_admins) == 0:
	with open("admins.conf", "w") as file:
		file.write("")
	raise Exception("No admins registered to control admin features - admins.conf created.")

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

tornsy_api_address = "https://tornsy.com/api/stocks?interval=m1,h1,d1,w1,n1"
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
		write_notification_to_log("[WARNING] Server returned error code: " + str(tornsy_data.status_code))

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

	async def alert_roles(self, embed, value):
		for key in range(0, len(channels["id"])):
			channel = await client.fetch_channel(channels["id"][key])
			sml = "<@&"+str(channels["small"][key])+">"
			med = "<@&"+str(channels["medium"][key])+">"
			lrg = "<@&"+str(channels["large"][key])+">"
			if value >= (750 * 1000000000):
				await channel.send(sml + ", " + med + ", " + lrg, embed=embed)
			elif value >= (450 * 1000000000):
				await channel.send(sml + ", " + med, embed=embed)
			else:
				await channel.send(sml, embed=embed)

	def set_author(self, message, embed):
		if message.author.avatar:
			embed.set_author(name=message.author.display_name, icon_url="https://cdn.discordapp.com/avatars/"+str(message.author.id)+"/"+message.author.avatar+".png")
		else:
			embed.set_author(name=message.author.display_name)

	def set_author_notif(self, user, embed):
		if user.avatar:
			embed.set_author(name=user.name, icon_url="https://cdn.discordapp.com/avatars/"+str(user.id)+"/"+user.avatar+".png")
		else:
			embed.set_author(name=user.name)

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
			self.set_author_notif(user, embed)
			await user.send(embed=embed)
		elif type == "down":
			embed = discord.Embed(title=data["name"] + " Below Target Price", url="https://www.torn.com/page.php?sid=stocks&stockID="+lut_stock_id(stock)+"&tab=owned")
			embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+stock+".png")
			embed.color = discord.Color.orange()
			embed.add_field(name="Stonks!", value=data["name"] + " has reached or fallen under your target price of: $" + "{:,}".format(value) + ".")
			embed.set_thumbnail(url=stonks_png)
			user = await self.fetch_user(id)
			self.set_author_notif(user, embed)
			await user.send(embed=embed)

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
				for key in range(len(userdata["id"])-1, -1, -1):
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
			diff_shares = abs(int(total_shares - total_shares_m1))
			price = float(data["price"])
			value_total = diff_shares * price
			price_bn = float(value_total) / 1000000000

			perc_shares = ((total_shares - total_shares_m1) / total_shares_m1) * 100
			diff_investor = int(investors - investors_m1)
			perc_investor = ((investors - investors_m1) / investors_m1) * 100

			# Sell event
			if total_shares < total_shares_m1 and data["stock"] != "TCSE":
				if value_total >= (150 * 1000000000):
					embed = discord.Embed(title= "Large Sell Off: " + data["name"], url="https://www.torn.com/page.php?sid=stocks&stockID="+lut_stock_id(data["stock"])+"&tab=owned")
					embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+data["stock"]+".png")
					embed.color = discord.Color.red()
					embed.add_field(name=":handshake: Change in Shares:", value="-"+"{:,}".format(diff_shares) + " (" + "{:,.2f}".format(perc_shares) + "%)", inline=False)
					embed.add_field(name=":crown: Change in Investors:", value="{:,}".format(diff_investor) + " (" + "{:,.2f}".format(perc_investor) + "%)", inline=False)
					embed.add_field(name=":moneybag: Sale Info:", value="$"+"{:,}".format(value_total) + " ($" + "{:.3f}".format(price_bn) + "bn)", inline=False)
					embed.add_field(name=":money_with_wings: Share Price:", value="$"+str(data["price"]), inline=False)
					client.loop.create_task(self.alert_roles(embed, value_total))
			# Buy event
			elif total_shares > total_shares_m1 and data["stock"] != "TCSE":
				if value_total >= (150 * 1000000000):
					embed = discord.Embed(title="Large Buy In: " + data["name"] + " Bought!", url="https://www.torn.com/page.php?sid=stocks&stockID="+lut_stock_id(data["stock"])+"&tab=owned")
					embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+data["stock"]+".png")
					embed.color = discord.Color.green()
					embed.add_field(name=":handshake: Change in Shares:", value="+"+"{:,}".format(diff_shares) + " (" + "{:,.2f}".format(perc_shares) + "%)", inline=False)
					embed.add_field(name=":crown: Change in Investors:", value="{:,}".format(diff_investor) + " (" + "{:,.2f}".format(perc_investor) + "%)", inline=False)
					embed.add_field(name=":moneybag: Purchase Info:", value="$"+"{:,}".format(value_total) + " ($" + "{:.3f}".format(price_bn) + "bn)", inline=False)
					embed.add_field(name=":money_with_wings: Share Price:", value="$"+str(data["price"]), inline=False)
					client.loop.create_task(self.alert_roles(embed, value_total))

	async def help(self, message):
		if message.content.startswith("!help"):
			if message.content == "!help":
				embed = discord.Embed(title="https://github.com/Jordach/TornStonksLive#command-reference", url="https://github.com/Jordach/TornStonksLive#command-reference")
				embed.color = discord.Color.purple()
				self.set_author(message, embed)
				await message.channel.send(embed=embed, mention_author=False, reference=message)
			else:
				command = message.content.split(" ", 2)
				if len(command) > 1:
					embed = discord.Embed(title="https://github.com/Jordach/TornStonksLive#command-reference", url="https://github.com/Jordach/TornStonksLive#command-reference")
					embed.color = discord.Color.purple()
					self.set_author(message, embed)
					await message.channel.send("You've used an extra argument for specific command help, sorry, but that's currently being worked on. In the meantime, use the command reference here:", embed=embed, mention_author=False, reference=message)
				else:
					embed = discord.Embed(title=":no_entry_sign: Invalid Command :no_entry_sign:")
					embed.color = discord.Color.red()
					self.set_author(message, embed)
					embed.add_field(name="Details:", value="The command arguments are either missing or the specified command is not found.")
					await message.channel.send(embed=embed, mention_author=False, reference=message)

	async def stock(self, message):
		if message.content.startswith("!stock"):
			command = message.content.split(" ", 2)
			if len(command) == 3:
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
							self.set_author(message, embed)
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
							await message.channel.send(embed=embed, mention_author=False, reference=message)
							return
				else:
					embed = discord.Embed(title=":no_entry_sign: Unable to connect to Tornsy. :no_entry_sign:")
					embed.color = discord.Color.red()
					embed.add_field(name="Details:", value="Either Tornsy API is down or the timestamp provided is invalid.")
					await message.channel.send(embed=embed, mention_author=False, reference=message)
					return
			if len(command) == 2:
				for data in json_data["data"]:
					if data["stock"] == command[1].upper():
						price = float(data["price"])
						price_h = float(data["interval"]["h1"]["price"])
						price_d = float(data["interval"]["d1"]["price"])
						price_w = float(data["interval"]["w1"]["price"])
						price_n = float(data["interval"]["n1"]["price"])
						perc_price_h = float((price - price_h) / price_h) * 100
						perc_price_d = float((price - price_d) / price_d) * 100
						perc_price_w = float((price - price_w) / price_w) * 100
						perc_price_n = float((price - price_n) / price_n) * 100

						shares = int(data["total_shares"])
						shares_h = int(data["interval"]["h1"]["total_shares"])
						shares_d = int(data["interval"]["d1"]["total_shares"])
						shares_w = int(data["interval"]["w1"]["total_shares"])
						shares_n = int(data["interval"]["n1"]["total_shares"])
						perc_shares_h = float((shares - shares_h) / shares_h) * 100
						perc_shares_d = float((shares - shares_d) / shares_d) * 100
						perc_shares_w = float((shares - shares_w) / shares_w) * 100
						perc_shares_n = float((shares - shares_n) / shares_n) * 100

						investors = int(data["investors"])
						investors_h = int(data["interval"]["h1"]["investors"])
						investors_d = int(data["interval"]["d1"]["investors"])
						investors_w = int(data["interval"]["w1"]["investors"])
						investors_n = "N/A"
						if data["interval"]["n1"]["investors"]:
							investors_n = int(data["interval"]["n1"]["investors"])
						perc_investors_h = float((investors - investors_h) / investors_h) * 100
						perc_investors_d = float((investors - investors_d) / investors_d) * 100
						perc_investors_w = float((investors - investors_w) / investors_w) * 100
						perc_investors_n = "N/A"
						if data["interval"]["n1"]["investors"]:
							perc_investors_n = float((investors - investors_n) / investors_n) * 100
						
						embed = discord.Embed(title=data["name"], url="https://www.torn.com/page.php?sid=stocks&stockID="+lut_stock_id(data["stock"])+"&tab=owned")
						embed.color = discord.Color.blue()
						self.set_author(message, embed)
						embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+data["stock"]+".png")
						price_str = "$"+"{:,.2f}".format(price) + "\n"
						price_str = price_str + "$"+"{:,.2f}".format(price_h) + " (" + "{:,.2f}".format(perc_price_h) + "%, h1)\n"
						price_str = price_str + "$"+"{:,.2f}".format(price_d) + " (" + "{:,.2f}".format(perc_price_d) + "%, d1)\n"
						price_str = price_str + "$"+"{:,.2f}".format(price_w) + " (" + "{:,.2f}".format(perc_price_w) + "%, w1)\n"
						price_str = price_str + "$"+"{:,.2f}".format(price_n) + " (" + "{:,.2f}".format(perc_price_n) + "%, n1)"
						embed.add_field(name=":money_with_wings: Price:", value=price_str, inline=False)
						
						shares_str = "{:,}".format(shares) + "\n"
						shares_str = shares_str + "{:,}".format(shares_h) + " (" + "{:,.2f}".format(perc_shares_h) + "%, h1)\n"
						shares_str = shares_str + "{:,}".format(shares_d) + " (" + "{:,.2f}".format(perc_shares_d) + "%, d1)\n"
						shares_str = shares_str + "{:,}".format(shares_w) + " (" + "{:,.2f}".format(perc_shares_w) + "%, w1)\n"
						shares_str = shares_str + "{:,}".format(shares_n) + " (" + "{:,.2f}".format(perc_shares_n) + "%, n1)"
						embed.add_field(name=":handshake: Shares Owned:", value=shares_str, inline=False)

						investors_str = "{:,}".format(investors) + "\n"
						investors_str = investors_str + "{:,}".format(investors_h) + " (" + "{:,.2f}".format(perc_investors_h) + "%, h1)\n"
						investors_str = investors_str + "{:,}".format(investors_d) + " (" + "{:,.2f}".format(perc_investors_d) + "%, d1)\n"
						investors_str = investors_str + "{:,}".format(investors_w) + " (" + "{:,.2f}".format(perc_investors_w) + "%, w1)\n"
						if data["interval"]["n1"]["investors"]:
							investors_str = investors_str + "{:,}".format(investors_n) + " (" + "{:,.2f}".format(perc_investors_n) + "%, n1)"
						else:
							investors_str = investors_str + " (n1)"
						embed.add_field(name=":crown: Investors:", value=investors_str, inline=False)
						await message.channel.send(embed=embed, mention_author=False, reference=message)
						return
				embed = discord.Embed(title=":no_entry_sign: Stock not found. :no_entry_sign:")
				embed.color = discord.Color.red()
				await message.channel.send(embed=embed, mention_author=False, reference=message)
			else:
				embed = discord.Embed(title=":no_entry_sign: Missing the three letter short name. :no_entry_sign:")
				embed.color = discord.Color.red()
				await message.channel.send(embed=embed, mention_author=False, reference=message)

	async def alerts(self, message):
		if message.content.startswith("!up"):
			command = message.content.split(" ", 3)
			if len(command) == 3:
				userdata["id"].append(int(message.author.id))
				userdata["type"].append("up")
				userdata["stock"].append(command[1].lower())
				userdata["value"].append(float(command[2]))
				write_user_alerts()
				embed = discord.Embed(title=":white_check_mark: Will send you a DM when the criteria is reached. :white_check_mark:")
				embed.color = discord.Color.dark_green()
				await message.channel.send(embed=embed, mention_author=False, reference=message)
			else:
				embed = discord.Embed(title=":no_entry_sign: Invalid Command :no_entry_sign:")
				embed.color = discord.Color.red()
				self.set_author(message, embed)
				embed.add_field(name="Details:", value="The command arguments are either missing the company or value, or too few or too many arguments, try the following example:\n\n`!up sym 123.45`")
				await message.channel.send(embed=embed, mention_author=False, reference=message)
		elif message.content.startswith("!down"):
			command = message.content.split(" ", 3)
			if len(command) == 3:
				userdata["id"].append(int(message.author.id))
				userdata["type"].append("down")
				userdata["stock"].append(command[1].lower())
				userdata["value"].append(float(command[2]))
				write_user_alerts()
				embed = discord.Embed(title=":white_check_mark: Will send you a DM when the criteria is reached. :white_check_mark:")
				embed.color = discord.Color.dark_green()
				await message.channel.send(embed=embed, mention_author=False, reference=message)
			else:
				embed = discord.Embed(title=":no_entry_sign: Invalid Command :no_entry_sign:")
				embed.color = discord.Color.red()
				self.set_author(message, embed)
				embed.add_field(name="Details:", value="The command arguments are either missing the company or value, or too few or too many arguments, try the following example:\n\n`!down sym 123.45`")
				await message.channel.send(embed=embed, mention_author=False, reference=message)

	async def buy(self, message):
		if message.content.startswith("!buy"):
			command = message.content.split(" ", 3)
			if len(command) == 3:
				if command[1].isdigit():
					for data in json_data["data"]:
						if data["stock"] == command[2].upper():
							money_remainder = float(command[1]) % float(data["price"])
							total_money = float(command[1]) - money_remainder
							total_shares = total_money / float(data["price"])
							
							embed = discord.Embed(title=data["name"], url="https://www.torn.com/page.php?sid=stocks&stockID="+lut_stock_id(data["stock"])+"&tab=owned")
							embed.color = discord.Color.blue()
							self.set_author(message, embed)
							embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+data["stock"]+".png")
							embed.add_field(name=":handshake: Purchaseable Shares:", value="{:,.0f}".format(total_shares) + " @ $" +str(data["price"] + " per share."), inline=False)
							embed.add_field(name=":credit_card: Money Spent:", value="$"+"{:,.0f}".format(total_money), inline=False)
							embed.add_field(name=":dollar: Money Leftover:", value="$"+"{:,.0f}".format(money_remainder), inline=False)
							await message.channel.send(embed=embed, mention_author=False, reference=message)
							return

					embed = discord.Embed(title=":no_entry_sign: Invalid Arguments :no_entry_sign:")
					embed.color = discord.Color.red()
					self.set_author(message, embed)
					embed.add_field(name="Details:", value="The stock specified cannot be found.")
					await message.channel.send(embed=embed, mention_author=False, reference=message)
					return
				else:
					embed = discord.Embed(title=":no_entry_sign: Invalid Arguments :no_entry_sign:")
					embed.color = discord.Color.red()
					self.set_author(message, embed)
					embed.add_field(name="Details:", value="The argument for cash on hand is invalid, ensure it's a number with no commas, dollar signs, or letters.")
					await message.channel.send(embed=embed, mention_author=False, reference=message)
			else:
				embed = discord.Embed(title=":no_entry_sign: Invalid Command :no_entry_sign:")
				embed.color = discord.Color.red()
				self.set_author(message, embed)
				embed.add_field(name="Details:", value="The command arguments are either missing the company or value, or too few or too many arguments, try the following example:\n\n`!buy 1000000000 iou`")
				await message.channel.send(embed=embed, mention_author=False, reference=message)

	async def sell(self, message):
		if message.content.startswith("!sell"):
			command = message.content.split(" ", 3)
			if len(command) == 3:
				if command[1].isdigit():
					for data in json_data["data"]:
						if data["stock"] == command[2].upper():
							pre_tax = int(command[1]) * float(data["price"])
							pos_tax = pre_tax * 0.999
							embed = discord.Embed(title=data["name"], url="https://www.torn.com/page.php?sid=stocks&stockID="+lut_stock_id(data["stock"])+"&tab=owned")
							embed.color = discord.Color.blue()
							self.set_author(message, embed)
							embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+data["stock"]+".png")
							embed.add_field(name=':handshake: Shares "Sold":', value="{:,}".format(int(command[1])) + " @ $" + data["price"] + " per share.", inline=False)
							embed.add_field(name=":dollar: Value of Shares Pre Tax:", value="$"+"{:,.0f}".format(pre_tax), inline=False)
							embed.add_field(name=":money_with_wings: Value of Shares Post Tax:", value="$"+"{:,.0f}".format(pos_tax), inline=False)
							await message.channel.send(embed=embed, mention_author=False, reference=message)
							return
					embed = discord.Embed(title=":no_entry_sign: Invalid Arguments :no_entry_sign:")
					embed.color = discord.Color.red()
					self.set_author(message, embed)
					embed.add_field(name="Details:", value="The stock specified cannot be found.")
					await message.channel.send(embed=embed, mention_author=False, reference=message)
					return
				else:
					embed = discord.Embed(title=":no_entry_sign: Invalid Arguments :no_entry_sign:")
					embed.color = discord.Color.red()
					self.set_author(message, embed)
					embed.add_field(name="Details:", value="The argument for number of shares is invalid, ensure it's a number with no commas, or letters.")
					await message.channel.send(embed=embed, mention_author=False, reference=message)
			else:
				embed = discord.Embed(title=":no_entry_sign: Invalid Command :no_entry_sign:")
				embed.color = discord.Color.red()
				self.set_author(message, embed)
				embed.add_field(name="Details:", value="The command arguments are either missing the company or number of shares, or too few or too many arguments, try the following example:\n\n`!sell 1000000 iou`")
				await message.channel.send(embed=embed, mention_author=False, reference=message)

	async def stop(self, message):
		if message.content == "!stop":
			global bot_admins
			if int(message.author.id) in bot_admins:
				write_user_alerts()
				stop_run_continuously.set()
				await client.close()
				return
			else:
				embed = discord.Embed(title=":no_entry_sign: Permission Required :no_entry_sign:")
				embed.color = discord.Color.red()
				self.set_author(message, embed)
				embed.add_field(name="Details:", value="You are not authorised to stop the bot.")
				await message.channel.send(embed=embed, mention_author=False, reference=message)

	async def forget(self, message):
		if message.content.startswith("!forget"):
			if message.content == "!forgetme":
				if int(message.author.id) in userdata["id"]:
					for key in range(len(userdata["id"])-1, -1, -1):
						if int(message.author.id) == userdata["id"][key]:
							write_notification_to_log("[NOTICE]: " + message.author.display_name + " deleted notification: " + str(userdata["id"][key]) + "," + userdata["type"][key] + "," + userdata["stock"][key] + "," + str(userdata["value"][key]))
							del userdata["id"][key]
							del userdata["type"][key]
							del userdata["stock"][key]
							del userdata["value"][key]
					
					write_user_alerts()
					embed = discord.Embed(title="")
					embed.color = discord.Color.red()
					self.set_author(message, embed)
					embed.add_field(name="All of your pending notifications deleted.", value="Thank you for using TornStonks Live; have a nice day. :wave:")
					await message.channel.send(embed=embed, mention_author=False, reference=message)
				else:
					embed = discord.Embed(title="")
					embed.color = discord.Color.dark_green()
					self.set_author(message, embed)
					embed.add_field(name="No Notifications Pending!", value="Thank you for using TornStonks Live; have a nice day. :wave:")
					await message.channel.send(embed=embed, mention_author=False, reference=message)
			else:
				command = message.content.split(" ", 3)
				c_len = len(command)
				if c_len > 1:
					# Anti idiot security
					if c_len >= 3:
						if command[2].lower() != "up" and command[2].lower() != "down":
							embed = discord.Embed(title=":no_entry_sign: Invalid Argument: :no_entry_sign:")
							embed.color = discord.Color.red()
							self.set_author(message, embed)
							embed.add_field(name="Details:", value='Command argument after stock ticker must be exactly "up" or "down".')
							await message.channel.send(embed=embed, mention_author=False, reference=message)
							return
						
					if c_len == 4:
						if not command[3].isdigit():
							embed = discord.Embed(title=":no_entry_sign: Invalid Argument: :no_entry_sign:")
							embed.color = discord.Color.red()
							self.set_author(message, embed)
							embed.add_field(name="Details:", value='Command argument after notification type must be a number, argument example: `123.45`')
							await message.channel.send(embed=embed, mention_author=False, reference=message)
							return
					# Remove pending items if we have some
					if int(message.author.id) in userdata["id"]:
						for key in range(len(userdata["id"])-1, -1, -1):
							if int(message.author.id) == userdata["id"][key]:
								if c_len == 4:
									if command[1].lower() == userdata["stock"][key] and command[2].lower() == userdata["type"][key] and float(command[3]) == userdata["value"][key]:
										write_notification_to_log("[NOTICE]: " + message.author.display_name + " deleted notification: " + str(userdata["id"][key]) + "," + userdata["type"][key] + "," + userdata["stock"][key] + "," + str(userdata["value"][key]))
										del userdata["id"][key]
										del userdata["type"][key]
										del userdata["stock"][key]
										del userdata["value"][key]
								elif c_len == 3:
									if command[1].lower() == userdata["stock"][key] and command[2].lower() == userdata["type"][key]:
										write_notification_to_log("[NOTICE]: " + message.author.display_name + " deleted notification: " + str(userdata["id"][key]) + "," + userdata["type"][key] + "," + userdata["stock"][key] + "," + str(userdata["value"][key]))
										del userdata["id"][key]
										del userdata["type"][key]
										del userdata["stock"][key]
										del userdata["value"][key]
								elif c_len == 2:
									if command[1].lower() == userdata["stock"][key]:
										write_notification_to_log("[NOTICE]: " + message.author.display_name + " deleted notification: " + str(userdata["id"][key]) + "," + userdata["type"][key] + "," + userdata["stock"][key] + "," + str(userdata["value"][key]))
										del userdata["id"][key]
										del userdata["type"][key]
										del userdata["stock"][key]
										del userdata["value"][key]
						write_user_alerts()
						embed = discord.Embed(title="")
						embed.color = discord.Color.red()
						self.set_author(message, embed)
						embed.add_field(name="Specified Pending Notification(s) Deleted!",  value="Thank you for using TornStonks Live; have a nice day. :wave:")
						await message.channel.send(embed=embed, mention_author=False, reference=message)
					else:
						embed = discord.Embed(title="")
						embed.color = discord.Color.dark_green()
						self.set_author(message, embed)
						embed.add_field(name="No Notifications Pending!", value="Thank you for using TornStonks Live; have a nice day. :wave:")
						await message.channel.send(embed=embed, mention_author=False, reference=message)
				else:
					embed = discord.Embed(title=":no_entry_sign: Invalid Arguments: :no_entry_sign:")
					embed.color = discord.Color.red()
					self.set_author(message, embed)
					embed.add_field(name="Details:", value="Missing the stock ticker. Example commands: `!forget sym` `!forget sym up` `!forget sym up 700`")
					await message.channel.send(embed=embed, mention_author=False, reference=message)
	
	async def notifications(self, message):
		if message.content.startswith("!notifications") or message.content.startswith("!alerts"):
			command = message.content.split(" ", 3)
			if command[0] == "!notifications" or command[0] == "!alerts":
				if len(command) >= 2:
					if command[1].lower() != "up" and command[1].lower() != "down":
						embed = discord.Embed(title=":no_entry_sign: Invalid Argument: :no_entry_sign:")
						embed.color = discord.Color.red()
						self.set_author(message, embed)
						embed.add_field(name="Details:", value='Command argument after stock ticker must be exactly "up" or "down".')
						await message.channel.send(embed=embed, mention_author=False, reference=message)
						return

				if int(message.author.id) in userdata["id"]:
					known_alerts = ""
					for key in range(0, len(userdata["id"])):
						if int(message.author.id) == userdata["id"][key]:
							if len(command) == 3:
								if command[1] == userdata["type"][key] and command[2] == userdata["stock"][key]:
									known_alerts = known_alerts + "`!" + userdata["type"][key] + " " + userdata["stock"][key] + " " + str(userdata["value"][key]) + "`\n"
							elif len(command) == 2:
								if command[1] == userdata["type"][key]:
									known_alerts = known_alerts + "`!" + userdata["type"][key] + " " + userdata["stock"][key] + " " + str(userdata["value"][key]) + "`\n"
							else:
								known_alerts = known_alerts + "`!" + userdata["type"][key] + " " + userdata["stock"][key] + " " + str(userdata["value"][key]) + "`It\n"
					if known_alerts != "":
						embed = discord.Embed(title="")
						embed.color = discord.Color.blue()
						self.set_author(message, embed)
						embed.add_field(name="Pending Notifications:", value=known_alerts)
						user = await client.fetch_user(message.author.id)
						await user.send(embed=embed)
					else:
						embed = discord.Embed(title="")
						embed.color = discord.Color.dark_green()
						self.set_author(message, embed)
						embed.add_field(name="No Notifications Pending!", value="Thank you for using TornStonks Live; have a nice day. :wave:")
						await message.channel.send(embed=embed, mention_author=False, reference=message)
				else:
					embed = discord.Embed(title="")
					embed.color = discord.Color.dark_green()
					self.set_author(message, embed)
					embed.add_field(name="No Notifications Pending!", value="Thank you for using TornStonks Live; have a nice day. :wave:")
					await message.channel.send(embed=embed, mention_author=False, reference=message)

	async def on_message(self, message):
		# The bot should never respond to itself, ever
		if message.author == self.user:
			return

		global channels
		# Only respond in our designated channels to not shit up the place
		if not int(message.channel.id) in channels["id"] and message.guild:
			return
		
		await self.help(message)
		await self.stock(message)
		await self.alerts(message)
		await self.buy(message)
		await self.sell(message)
		await self.forget(message)
		await self.notifications(message)
		await self.stop(message)

client = TornStonksLive(intents=intent)
client.run(bot_token)
write_notification_to_log("[STARTUP] " + app_name + " started.")