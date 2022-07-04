from math import floor
from matplotlib.lines import Line2D
import requests
import json
import schedule
import time
import threading
import pprint
import os
import numpy as np
import pandas as pd
import random
from datetime import datetime, date, timezone
from sklearn.preprocessing import MinMaxScaler
from sklearn.linear_model import LinearRegression
from sklearn.svm import SVR, LinearSVR
from sklearn.model_selection import train_test_split
import matplotlib.pyplot as plt
import discord
import sqlite3

# Basic maths stuff

def remap(val, val_min, val_max, map_min, map_max):
	return (val-val_min) / (val_max-val_min) * (map_max-map_min) + map_min

def clamp_(val, min, max):
	if val <= min:
		return min
	elif val >= max:
		return max
	else:
		return val
	

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
		print(time_string+log_text)

notstonks_png = "https://cdn.discordapp.com/attachments/315121916199305218/976306803900022814/tornnotstonks.png"
stonks_png = "https://cdn.discordapp.com/attachments/315121916199305218/976306804176863293/tornstonks.png"

bot_token = ""
tornsy_recursive_limit = -1
with open("settings.conf", "r") as system_config:
	config_lines = system_config.readlines()
	count = 0
	for line in config_lines:
		count += 1
		if count == 1:
			bot_token = line.strip()
		if count == 2:
			tornsy_recursive_limit = int(line.strip())
		else:
			break

if bot_token == "":
	with open("settings.conf") as file:
		file.write("")
	raise Exception("Bot token is missing")

command_channels = {"id":[], "prefix":[], "predict":[]}
with open("command_channels.conf", "r") as channel_config:
	lines = channel_config.readlines()
	for line in lines:
		# Handle comments
		if line.strip().startswith("#"):
			continue

		data = line.strip().split(",")
		if len(data) == 3:
			command_channels["id"].append(int(data[0]))
			command_channels["prefix"].append(str(data[1]))
			command_channels["predict"].append(str(data[2]))
		else:
			write_notification_to_log("[WARNING] command_channels.conf has incorrect data, skipping the malformed line.")

if len(command_channels["id"]) == 0:
	with open("command_channels.conf", "w") as file:
		file.write("")
	raise Exception("No channels to send/receive commands to - command_channels.conf created.")

# Automated suggestions:
suggestion_channels = {"id":[]}
with open("suggestion_channels.conf", "r") as suggest_config:
	lines = suggest_config.readlines()
	for line in lines:
		# Handle comments
		if line.strip().startswith("#"):
			continue

		data = line.strip().split(",")
		if len(data) == 1:
			suggestion_channels["id"].append(int(data[0]))
		else:
			write_notification_to_log("[WARNING] suggestion_channels.conf has incorrect data, skipping the malformed line.")

if len(suggestion_channels["id"]) == 0:
	with open("suggestion_channels.conf", "w") as file:
		file.write("")
	raise Exception("No channels to send automated analysis to - suggestion_channels.conf created.")

# Alerts and notifications
alert_channels = {"id":[], "small":[], "medium":[], "large":[], "tiny":[]}
with open("alert_channels.conf", "r") as alert_config:
	lines = alert_config.readlines()
	for line in lines:
		# Handle comments
		if line.strip().startswith("#"):
			continue

		data = line.strip().split(",")
		if len(data) == 5:
			alert_channels["id"].append(int(data[0]))
			alert_channels["tiny"].append(int(data[1]))
			alert_channels["small"].append(int(data[2]))
			alert_channels["medium"].append(int(data[3]))
			alert_channels["large"].append(int(data[4]))
		else:
			write_notification_to_log("[WARNING] alert_channels.conf has incorrect data, skipping the malformed line.")

if len(alert_channels["id"]) == 0:
	with open("alert_channels.conf", "w") as file:
		file.write("")
	raise Exception("No channels to send automated notifications to - alert_channels.conf created.")

# Read admins out
bot_admins = []
with open("admins.conf", "r") as admin_config:
	lines = admin_config.readlines()
	for line in lines:
		# Handle comments
		if line.strip().startswith("#"):
			continue

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
tornsy_data =""
try:
	tornsy_data = requests.get(tornsy_api_address)
except:
	raise Exception("Tornsy probably timed out.")

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
	"ASS"
]

def lut_stock_id(name):
	id=1
	for item in stock_lut:
		if name == item:
			break
		id+=1
	return str(id)

# Utils
json_data = ""
intervals = ["m1", "m5", "m15", "m30", "h1", "h2", "h4", "h6", "h12", "d1"]

def get_tornsy_candlesticks(ticker, interval, limit, to="NONE"):
	ohlc_address = "https://tornsy.com/api/" + ticker + "?interval=" + interval + "&limit=" + limit

	# If a timestamp was specified, add that to the call
	if to != "NONE":
		ohlc_address = ohlc_address + "&to=" + str(to)

	ohlc_req = requests.get(ohlc_address)
	if ohlc_req.status_code == 200:
		ohlc_data = json.loads(ohlc_req.text)
		return ohlc_data
	else:
		return False

def get_stock_from_db(ticker, interval, limit=-1):
	# Translate between local SQL db and expected formatting:
	pwd = os.getcwd()
	name = ticker.lower()
	con = sqlite3.connect(pwd + "/db/db_" + name + ".db")
	cur = con.cursor()

	ohlc_data = []

	query = "SELECT * FROM " + interval.lower() + " ORDER BY date DESC"
	if limit > 0:
		query += " LIMIT " + str(limit)
	else:
		query += " LIMIT 4000"

	for row in cur.execute(query):
		ohlc_data.append(row)
	
	# Fix inverse sort
	ohlc_data.sort(key=lambda tup: tup[0])

	dt = {"date":[], "open":[], "high":[], "low":[], "close":[], "sma":[]}
	
	if interval == "m1":
		for item in ohlc_data:
			dt["date"].append(datetime.utcfromtimestamp(int(item[0])).strftime('%H:%M:%S %d/%m/%y'))
			dt["open"].append(float(item[1]))
			dt["high"].append(float(item[1]))
			dt["low"].append(float(item[1]))
			dt["close"].append(float(item[1]))
			dt["sma"].append(float(item[1]))
	else:
		for item in ohlc_data:
			dt["date"].append(datetime.utcfromtimestamp(int(item[0])).strftime('%H:%M:%S %d/%m/%y'))
			dt["open"].append(float(item[1]))
			dt["high"].append(float(item[2]))
			dt["low"].append(float(item[3]))
			dt["close"].append(float(item[4]))
			dt["sma"].append(float(item[4]))
	return dt

def update_from_tornsy():
	pwd = os.getcwd()
	for data in json_data["data"]:
		# Deny TCSE usage
		if data["stock"] == "TCSE":
			continue

		name = data["stock"].lower()
		con = sqlite3.connect(pwd + "/db/db_" + name + ".db")
		cur = con.cursor()

		for interval in intervals:
			dat = int(json_data["timestamp"])
			timestamp = 0
			if interval == "m5":
				timestamp = floor(dat / 300) * 300
			elif interval == "m15":
				timestamp = floor(dat / 900) * 900
			elif interval == "m30":
				timestamp = floor(dat / 1800) * 1800
			elif interval == "h1":
				timestamp = floor(dat / 3600) * 3600
			elif interval == "h2":
				timestamp = floor(dat / 7200) * 7200
			elif interval == "h4":
				timestamp = floor(dat / 14400) * 14400
			elif interval == "h6":
				timestamp = floor(dat / 21600) * 21600
			elif interval == "h12":
				timestamp = floor(dat / 43200) * 43200
			elif interval == "d1":
				timestamp = floor(dat / 86400) * 86400
			else: # == "m1"
				timestamp = floor(dat / 60) * 60
			timestamp = int(timestamp)

			cmd = "INSERT INTO " + interval + "(date, open, high, low, close) VALUES "
			cmd += "(" + str(timestamp) + ", "
			cmd += data["price"] + ", "
			cmd += data["price"] + ", "
			cmd += data["price"] + ", "
			cmd += data["price"] + ") "
			cmd += "ON CONFLICT(date) DO UPDATE SET "
			cmd += "high=IIF(" + data["price"] + " > high, " + data["price"] + ", high), "
			cmd += "low=IIF(" + data["price"] + " < low, " + data["price"] + ", low), "
			cmd += "close=" + data["price"]
			cur.execute(cmd)

		con.commit()
		con.close()

def import_from_tornsy(ticker, limit=-1):
	pwd = os.getcwd()
	name = ticker.lower()
	con = sqlite3.connect(pwd + "/db/db_" + name + ".db")
	cur = con.cursor()

	ohlc_data = get_tornsy_candlesticks(ticker, "m1", str(2000))
	if not ohlc_data:
		return
	
	dt = {"date":[], "open":[], "high":[], "low":[], "close":[]}

	# Only grab previous entries if there are exactly 2000 entries.
	# Or limit >= 1
	if len(ohlc_data["data"]) == 2000 and limit > 0:
		cdate = str(ohlc_data["data"][0][0])
		ohlcs = []
		
		lim = 0
		while True:
			ohlc = get_tornsy_candlesticks(ticker, "m1", str(2000), cdate)
			if not ohlc:
				return

			cdate = str(ohlc["data"][0][0])
			ohlcs.insert(0, ohlc)
			# Don't grab another set because Tornsy lacks history
			# or if we hit the cap on importing data
			if len(ohlc["data"]) < 2000 or lim == limit:
				break
			lim += 1
			time.sleep(0.05)

		# Append all the data 
		for k in range(len(ohlcs)):
			for i in range(len(ohlcs[k]["data"])):
				dt["date"].append((ohlcs[k]["data"][i][0]))
				dt["open"].append((ohlcs[k]["data"][i][1]))
				dt["high"].append((ohlcs[k]["data"][i][1]))
				dt["low"].append((ohlcs[k]["data"][i][1]))
				dt["close"].append((ohlcs[k]["data"][i][1]))

		for item in ohlc_data["data"]:
			dt["date"].append((item[0]))
			dt["open"].append((item[1]))
			dt["high"].append((item[1]))
			dt["low"].append((item[1]))
			dt["close"].append((item[1]))

	write_notification_to_log("[INFO]: " + ticker.lower() + " downloading completed.")

	for i in range(len(dt["date"])):
		for interval in intervals:
			try:
				cur.execute("CREATE TABLE " + interval + " (date integer PRIMARY KEY UNIQUE, open real, high real, low real, close real)")
			except:
				pass

			timestamp = 0
			dt_time = int(dt["date"][i])
			if interval == "m5":
				timestamp = floor(dt_time / 300) * 300
			elif interval == "m15":
				timestamp = floor(dt_time / 900) * 900
			elif interval == "m30":
				timestamp = floor(dt_time / 1800) * 1800
			elif interval == "h1":
				timestamp = floor(dt_time / 3600) * 3600
			elif interval == "h2":
				timestamp = floor(dt_time / 7200) * 7200
			elif interval == "h4":
				timestamp = floor(dt_time / 14400) * 14400
			elif interval == "h6":
				timestamp = floor(dt_time / 21600) * 21600
			elif interval == "h12":
				timestamp = floor(dt_time / 43200) * 43200
			elif interval == "d1":
				timestamp = floor(dt_time / 86400) * 86400
			else: # == "m1"
				timestamp = floor(dt_time / 60) * 60

			cmd = "INSERT INTO " + interval + "(date, open, high, low, close) VALUES "
			cmd += "(" + str(timestamp) + ", "
			cmd += str(dt["open"][i]) + ", "
			cmd += str(dt["high"][i]) + ", "
			cmd += str(dt["low"][i]) + ", "
			cmd += str(dt["close"][i]) + ") "
			cmd += "ON CONFLICT(date) DO UPDATE SET "
			cmd += "high=IIF(" + str(dt["high"][i]) + " > high, " + str(dt["high"][i]) + ", high), "
			cmd += "low=IIF(" + str(dt["low"][i]) + " < low, " + str(dt["low"][i]) + ", low), "
			cmd += "close=" + str(dt["close"][i])
			try:
				cur.execute(cmd)
			except:
				print(cmd)

	con.commit()
	con.close()

for ticker in stock_lut:
	write_notification_to_log("[INFO]: Downloading " + ticker + ".")
	import_from_tornsy(ticker)
	write_notification_to_log("[INFO]: " + ticker + " added to DB.")

def get_latest_stocks():
	update_date()
	global tornsy_data
	try:
		tornsy_data = requests.get(tornsy_api_address)
	except:
		write_notification_to_log("[WARNING] Tornsy appears to be having issues")
		return

	if tornsy_data.status_code == 200:
		global json_data
		json_data = json.loads(tornsy_data.text)
		update_from_tornsy()
		global bot_started
		if bot_started:
			TornStonksLive.process_stockdata(client)
	else:
		write_notification_to_log("[WARNING] Server returned error code: " + str(tornsy_data.status_code))


# Get initial data
get_latest_stocks()

def get_torn_stock_data(api_key):
	return requests.get("https://api.torn.com/user/?selections=stocks&key=" + api_key)

def predict_stocks_v2(ticker, interval, forecast, render_graphs, samples=2000):
	nsamples = clamp_(samples, 300, 16000)
	dt = get_stock_from_db(ticker, interval, nsamples)

	df = pd.DataFrame(data=dt)
	df = df[["close"]]
	df["prediction"] = df[["close"]].shift(-(forecast+1))

	x = np.array(df.drop(["prediction"], axis=1))
	x = x[:-(forecast+1)]
	
	y = np.array(df["prediction"])
	y = y[:-(forecast+1)]
	
	test_size = 0.2
	test_size = remap(len(dt["close"]), 1000, 16000, 0.4, 0.025)
	test_size = clamp_(test_size, 0.025, 0.2)

	x_train, x_test, y_train, y_test = train_test_split(x, y, test_size=test_size)

	# Train and setup prediction engines
	svr_rbf = SVR(kernel='rbf', C=250, gamma=0.1) 
	svr_rbf.fit(x_train, y_train)
	svm_confidence = svr_rbf.score(x_test, y_test)

	lr = LinearRegression()
	lr.fit(x_train, y_train)
	lr_confidence = lr.score(x_test, y_test)

	svr_l = LinearSVR(max_iter=12000, loss="squared_epsilon_insensitive", C=4.2, dual=False)
	svr_l.fit(x_train, y_train)
	svr_l_confidence = svr_l.score(x_test, y_test)

	x_forecast = np.array(df.drop(["prediction"], axis=1))[-(forecast+1):]
	svm_prediction = svr_rbf.predict(x_forecast)
	lr_prediction = lr.predict(x_forecast)
	svm_l_prediction = svr_l.predict(x_forecast)
	avg_confidence = (svm_confidence + lr_confidence + svr_l_confidence) / 3
	
	price = 0
	name = ""
	for stock in json_data["data"]:
		if stock["stock"] == ticker.upper():
			price = float(stock["price"])
			name = stock["name"]
			break

	# Pull prices downwards to fix mysterious invalid prices
	diff_svm = svm_prediction[0] - price
	diff_lr = lr_prediction[0] - price
	diff_svml = svm_l_prediction[0] - price

	# High, Low, average, confidence
	hlvc = {}
	hlvc["price"] = price
	hlvc["ticker"] = ticker
	hlvc["svm"] = {}
	hlvc["svm"]["high"] = 0
	hlvc["svm"]["low"] = 10000
	hlvc["svm"]["volatility"] = 0
	hlvc["svm"]["actual"] = 0
	hlvc["svm"]["confidence"] = svm_confidence

	hlvc["lr"] = {}
	hlvc["lr"]["high"] = 0
	hlvc["lr"]["low"] = 10000
	hlvc["lr"]["volatility"] = 0
	hlvc["lr"]["actual"] = 0
	hlvc["lr"]["confidence"] = lr_confidence

	hlvc["svml"] = {}
	hlvc["svml"]["high"] = 0
	hlvc["svml"]["low"] = 10000
	hlvc["svml"]["volatility"] = 0
	hlvc["svml"]["actual"] = 0
	hlvc["svml"]["confidence"] = svr_l_confidence

	hlvc["avg"] = {}
	hlvc["avg"]["high"] = 0
	hlvc["avg"]["low"] = 10000
	hlvc["avg"]["volatility"] = 0
	hlvc["avg"]["actual"] = 0
	hlvc["avg"]["confidence"] = avg_confidence

	avg_prediction = []
	# Post process and normalise values
	for key in range(0, len(svm_prediction)):
		svm_prediction[key] -= diff_svm
		lr_prediction[key] -= diff_lr
		svm_l_prediction[key] -= diff_svml
		avg = float(svm_prediction[key] + lr_prediction[key] + svm_l_prediction[key]) / 3
		avg_prediction.append(avg)
		dt["sma"].append(avg)

		# Find highs and lows for all predicts, including the average:
		svm = svm_prediction[key]
		if svm > hlvc["svm"]["high"]:
			hlvc["svm"]["high"] = svm
		if svm < hlvc["svm"]["low"]:
			hlvc["svm"]["low"] = svm
		perc = abs(float((price - svm) / svm) * 100)
		aperc = float((price - svm) / svm) * -100
		if perc > hlvc["svm"]["volatility"]:
			hlvc["svm"]["volatility"] = perc
			hlvc["svm"]["actual"] = aperc
		
		lr = lr_prediction[key]
		if lr > hlvc["lr"]["high"]:
			hlvc["lr"]["high"] = lr
		if lr < hlvc["lr"]["low"]:
			hlvc["lr"]["low"] = lr
		perc = abs(float((price - lr) / lr) * 100)
		aperc = float((price - lr) / lr) * -100
		if perc > hlvc["lr"]["volatility"]:
			hlvc["lr"]["volatility"] = perc
			hlvc["lr"]["actual"] = aperc

		svml = svm_l_prediction[key]
		if svml > hlvc["svml"]["high"]:
			hlvc["svml"]["high"] = svml
		if svml < hlvc["svml"]["low"]:
			hlvc["svml"]["low"] = svml
		perc = abs(float((price - svml) / svml) * 100)
		aperc = float((price - svml) / svml) * -100
		if perc > hlvc["svml"]["volatility"]:
			hlvc["svml"]["volatility"] = perc
			hlvc["svml"]["actual"] = aperc

		if avg > hlvc["avg"]["high"]:
			hlvc["avg"]["high"] = avg
		if avg < hlvc["avg"]["low"]:
			hlvc["avg"]["low"] = avg
		perc = abs(float((price - avg) / avg) * 100)
		aperc = float((price - avg) / avg) * -100
		if perc > hlvc["avg"]["volatility"]:
			hlvc["avg"]["volatility"] = perc
			hlvc["avg"]["actual"] = aperc

	# Figure out timestamps
	period = int(int ( ''.join(filter(str.isdigit, interval) ) ))
	period_ticks = []
	current_time = int(datetime.now(timezone.utc).timestamp())
	period_ticks.append(datetime.utcfromtimestamp(current_time).strftime('%H:%M:%S %d/%m/%y'))
	for i in range(2, 10):
		if interval[0] == "m":
			period_ticks.append(datetime.utcfromtimestamp(current_time + int(((60 * (period * forecast)) / 9) * i)).strftime('%H:%M:%S %d/%m/%y'))
		elif interval[0] == "h":
			period_ticks.append(datetime.utcfromtimestamp(current_time + int(((3600 * (period * forecast)) / 9) * i)).strftime('%H:%M:%S %d/%m/%y'))
		elif interval[0] == "d":
			period_ticks.append(datetime.utcfromtimestamp(current_time + int(((86400 * (period * forecast)) / 9) * i)).strftime('%H:%M:%S %d/%m/%y'))
		elif interval[0] == "w":
			period_ticks.append(datetime.utcfromtimestamp(current_time + int(((604800 * (period * forecast)) / 9) * i)).strftime('%H:%M:%S %d/%m/%y'))
		elif interval[0] == "n":
			period_ticks.append(datetime.utcfromtimestamp(current_time + int(((26355200 * (period * forecast)) / 9) * i)).strftime('%H:%M:%S %d/%m/%y'))
		elif interval[0] == "y":
			period_ticks.append(datetime.utcfromtimestamp(current_time + int(((31536000 * (period * forecast)) / 9) * i)).strftime('%H:%M:%S %d/%m/%y'))
	# Set PNG file name
	file = os.getcwd()+"/graphs/"+ticker+" "+interval+" "+str(forecast)+" "+str(period_ticks[0].replace("/", "-").replace(":", "-")+".png")
	
	# Render the PNG graph
	if render_graphs:
		# Create SMA graph line
		sma_avg = []
		sma_amt = 15
		sma_len = (len(dt["sma"])) - (forecast + sma_amt)
		sma_len_b = len(dt["close"]) + 1
		for f in range(forecast+1):
			sma_val = 0
			for i in range(sma_len+f, sma_len_b+f):
				sma_val += float(dt["sma"][i])
			sma_avg.append(sma_val/(sma_amt))

		# Make x-axis timestamps not suck
		xticks = []
		xticks.append(0)
		for i in range(1, 9):
			xticks.append(float(forecast / 8) * i)

		plt.style.use("ggplot")
		fig, ax = plt.subplots()
		ax.plot(sma_avg, color="#ff8a00", linewidth=2.5, zorder=-10, alpha=0.3)
		ax.plot(svm_prediction, linewidth=12, alpha=0.05, color="red", zorder=-8)
		ax.plot(lr_prediction, linewidth=12, alpha=0.05, color="blue", zorder=-7)
		ax.plot(svm_l_prediction, linewidth=12, alpha=0.05, color="purple", zorder=-6)
		#ax.plot(avg_prediction, linewidth=12, alpha=0.1, color="green", zorder=-5)
		ax.plot(svm_prediction, label="SVM", alpha=0.15, linewidth=1.5, color="red", zorder=-4)
		ax.plot(lr_prediction, label="LR", alpha=0.15, linewidth=1.5, color="blue", zorder=-3)
		ax.plot(svm_l_prediction, label="SVM Linear", alpha=0.15, linewidth=1.5, color="purple", zorder=-2)
		#ax.plot(avg_prediction, label="Average", linewidth=1.5, color="green", zorder=-1)
		ax.plot(sma_avg, label="Trend", alpha=0.9, color="#ff8a00", linewidth=1.5, linestyle="--", zorder=-9, dashes=(5, 2))
		plt.title(name + " Price Prediction (" + interval + ", " + str(forecast) + ")")
		ax.yaxis.set_major_formatter('${x:1.2f}')
		ax.set_xticks(xticks)
		ax.set_xticklabels(period_ticks)
		plt.xticks(rotation=45, horizontalalignment="right")
		plt.legend()
		plt.tight_layout()
		plt.grid(color = 'black', linestyle = '--', linewidth = 0.5)
		if not os.path.isdir(os.getcwd()+"/graphs"):
			os.mkdir(os.getcwd()+"/graphs")

		plt.savefig(file)
		plt.close()
	return [file, hlvc, name, period_ticks]

def get_stoch_osc(df, k, t):
	copy = df.copy()

	high_roll = copy["high"].rolling(k).max()
	low_roll = copy["low"].rolling(k).min()
	
	# Fast osc
	num = copy["close"] - low_roll
	denom = high_roll - low_roll
	copy["k"] = (num / denom) * 100

	# Slow osc
	copy["d"] = copy["k"].rolling(t).mean()
	return copy

def get_stoch(ticker, interval, render_graphs=True, k=14, t=3, limit=2000, profit_perc=0.1):
	dt = get_stock_from_db(ticker, interval, limit)
	df = pd.DataFrame(data=dt)

	stoch = get_stoch_osc(df, k, t)
	buy_price = []
	sell_price = []
	stoch_signal = []
	signal = 0
	sig_price = dt["close"][0]
	perc_gain = 0
	n_buys = 0
	n_sells = 0

	for i in range(len(stoch["k"])):
		if stoch["k"][i] < 20 and stoch["d"][i] < 20 and stoch["k"][i] < stoch["d"][i]:
			if signal != 1:
				buy_price.append(dt["close"][i])
				sell_price.append(np.nan)
				signal = 1
				sig_price = dt["close"][i]
				stoch_signal.append(signal)
				n_buys += 1
			else:
				buy_price.append(np.nan)
				sell_price.append(np.nan)
				stoch_signal.append(0)
		#elif stoch["k"][i] > 80 and stoch["d"][i] > 80 and stoch["k"][i] > stoch["d"][i]:
		elif stoch["k"][i] > 80 and stoch["d"][i] > 80 and stoch["k"][i] > stoch["d"][i] and (sig_price * (1 + (profit_perc / 100))) < dt["close"][i]:
			if signal != -1:
				buy_price.append(np.nan)
				sell_price.append(dt["close"][i])
				signal = -1
				perc = (float((dt["close"][i] - sig_price) / sig_price) * 100)
				perc_gain += perc
				sig_price = dt["close"][i]
				stoch_signal.append(signal)
				n_sells += 1
			else:
				buy_price.append(np.nan)
				sell_price.append(np.nan)
				stoch_signal.append(0)
		else:
			buy_price.append(np.nan)
			sell_price.append(np.nan)
			stoch_signal.append(0)

	position = []
	for i in range(len(stoch_signal)):
		if stoch_signal[i] > 1:
			position.append(0)
		else:
			position.append(1)

	for i in range(len(dt["close"])):
		if stoch_signal[i] == 1:
			position[i] = 1
		elif stoch_signal[i] == -1:
			position[i] = 0
		else:
			position[i] = position[i-1]

	# Figure out timestamps
	len_div = int(len(dt["date"])/6)
	period_ticks = []
	period_ticks.append(dt["date"][0])
	period_ticks.append(dt["date"][(len_div*1)-1-k])
	period_ticks.append(dt["date"][(len_div*2)-1-k])
	period_ticks.append(dt["date"][(len_div*3)-1-k])
	period_ticks.append(dt["date"][(len_div*4)-1-k])
	period_ticks.append(dt["date"][(len_div*5)-1-k])
	period_ticks.append(dt["date"][len(dt["date"])-1-k])

	current_time = int(datetime.now(timezone.utc).timestamp())
	current_time = datetime.utcfromtimestamp(current_time).strftime('%H:%M:%S %d/%m/%y')
	
	# Set PNG file name
	file = os.getcwd()+"/graphs/stoch "+ticker+" "+interval+" " + str(k) + ", " + str(t) + " "+str(current_time.replace("/", "-").replace(":", "-")+".png")
	
	# Render the PNG graph
	if render_graphs:
		# Make x-axis timestamps not suck
		xticks = []
		xticks.append(0)
		for i in range(1, 7):
			xticks.append(float(len(dt["date"]) / 6) * i)

		plt.style.use("ggplot")
		fig, ax = plt.subplots(nrows=2, ncols=1, sharex=True, figsize=(6,6))
		ax[0].plot(dt["close"], color="skyblue", linewidth=0.75, label="Price")
		ax[0].plot(df.index, buy_price, marker="^", color="green", markersize=3, linewidth=0, label="Buy")
		ax[0].plot(df.index, sell_price, marker="v", color="red", markersize=3, linewidth=0, label="Sell")
		plt.title("STOCH " + ticker.upper() + " (" + interval + ")")
		ax[0].yaxis.set_major_formatter('${x:1.2f}')
		# ax[1].set_title(f"{ticker} Stochastic Oscillator ({k}-day period), {interval}")
		ax[1].set_ylim(-10, 110)
		ax[1].plot(stoch["k"], color="tab:blue", linewidth=0.75)
		ax[1].plot(stoch["d"], color="tab:orange", linewidth=0.75)
		ax[1].axhline(80, color="tab:red", ls="--")
		ax[1].axhline(20, color="tab:green", ls="--")
		custom_lines = [
			Line2D([0], [0], color="tab:blue", lw=2),
			Line2D([0], [0], color="tab:orange", lw=2),
			Line2D([0], [0], color="tab:red", lw=2),
			Line2D([0], [0], color="tab:green", lw=2),
		]
		ax[1].legend(custom_lines, ["%K", "%D", "Overbought", "Oversold"], loc="best")
		ax[0].set_xticks(xticks)
		ax[1].set_xticks(xticks)
		ax[1].set_xticklabels(period_ticks)
		plt.xticks(rotation=45, horizontalalignment="right")
		ax[0].legend()
		plt.tight_layout()
		ax[0].grid(color = 'black', linestyle = '--', linewidth = 0.5)
		plt.grid(color = 'black', linestyle = '--', linewidth = 0.5)
		if not os.path.isdir(os.getcwd()+"/stoch"):
			os.mkdir(os.getcwd()+"/stoch")

		plt.savefig(file)
		plt.close()
	return [file, period_ticks, n_buys, n_sells, perc_gain]

intent = discord.Intents(messages=True, guilds=True, reactions=True, dm_messages=True, dm_reactions=True, members=True)

undo_list = []
undo_list.append("undo")
undo_list.append("fuck")
undo_list.append("f**k")
undo_list.append("shit")
undo_list.append("ohno")
undo_list.append("oops")

def check_volatility():
	if bot_started:
		try:
			TornStonksLive.process_volatility(client)
		except:
			write_notification_to_log("[WARNING] Potential problem with volatiltity checks.")

def check_daily_volatility():
	if bot_started:
		try:
			TornStonksLive.process_daily_volatility(client)
		except:
			write_notification_to_log("[WARNING] Potential problem with volatiltity checks.")

def check_weekly_volatility():
	if bot_started:
		try:
			TornStonksLive.process_weekly_volatility(client)
		except:
			write_notification_to_log("[WARNING] Potential problem with volatiltity checks.")


def suggests():
	if bot_started:
		try:
			TornStonksLive.process_suggestions(client)
		except:
			write_notification_to_log("[WARNING] Potential problem with suggestion predictions.")

# Initiate background thread and jobs
enable_suggestions = True
if enable_suggestions:
	schedule.every().day.at("01:01:20").do(suggests)
	schedule.every().day.at("05:01:20").do(suggests)
	schedule.every().day.at("09:01:20").do(suggests)
	schedule.every().day.at("13:01:20").do(suggests)
	schedule.every().day.at("17:01:20").do(suggests)
	schedule.every().day.at("21:01:20").do(suggests)

enable_volatility = False
if enable_volatility:
	schedule.every().hour.at("00:45").do(check_volatility)
	schedule.every().hour.at("30:45").do(check_volatility)
	schedule.every().day.at("01:00:45").do(check_daily_volatility)
	schedule.every().monday.at("01:00:45").do(check_weekly_volatility)

schedule.every().minute.at(":15").do(get_latest_stocks)
stop_run_continuously = run_continuously()

best_gain = ""
if os.path.exists("best_gain.json"):
	with open("best_gain.json") as file:
		best_gain = json.load(file)
else:
	write_notification_to_log("[WARNING] best_gain.json not found - ignoring")

best_loss = ""
if os.path.exists("best_loss.json"):
	with open("best_loss.json") as file:
		best_loss = json.load(file)
else:
	write_notification_to_log("[WARNING] best_loss.json not found - ignoring")

best_rand = ""
if os.path.exists("best_rand.json"):
	with open("best_rand.json") as file:
		best_rand = json.load(file)
else:
	write_notification_to_log("[WARNING] best_rand.json not found - ignoring")
not_more = False
last_pred_id = []

class TornStonksLive(discord.Client):
	async def on_ready(self):
		#print("Bot logged on as {0}!".format(self.user))
		await self.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="Torn City Stocks"))
		global bot_started
		bot_started = True

		for key in range(0, len(suggestion_channels["id"])):
			channel = await client.fetch_channel(suggestion_channels["id"][key])
			pred_message = await channel.history(limit=1).flatten()
			three = "3️⃣"
			global not_more
			# Avoid trying to get messages from completely empty channels
			if len(pred_message) == 0:
				continue
			elif len(pred_message[0].reactions) == 0:
				continue
			if pred_message[0].reactions[0] == three:
				not_more = True
			else:
				not_more = False
			global last_pred_id
			last_pred_id = []
			last_pred_id.append(pred_message[0])
		write_notification_to_log("[STARTUP] " + app_name + " started.")

	def strip_commas(self, value):
		return value.replace(",", "")

	async def alert_roles(self, embed, value, type, ticker):
		tag_type = ""
		if type == "buy":
			tag_type = "[BUY] "
		elif type == "sell":
			tag_type = "[SELL] "
		
		tick = "[" + ticker + "]"
		write_notification_to_log(tag_type + tick + ": $" + "{:,.3f}".format(value/1000000000) + "bn")
		for key in range(0, len(alert_channels["id"])):
			channel = await client.fetch_channel(alert_channels["id"][key])
			sml = "<@&"+str(alert_channels["small"][key])+">"
			med = "<@&"+str(alert_channels["medium"][key])+">"
			lrg = "<@&"+str(alert_channels["large"][key])+">"
			tiny = "<@&"+str(alert_channels["tiny"][key])+">"
			# Only send an alert if the channel ID is not zero
			if alert_channels["tiny"][key] > 0 and value < (150 * 1000000000):
				await channel.send(tag_type + tick + " - " + tiny, embed=embed)
			else:
				if value >= (750 * 1000000000):
					await channel.send(tag_type + tick + " - " + sml + ", " + med + ", " + lrg, embed=embed)
				elif value >= (450 * 1000000000):
					await channel.send(tag_type + tick + " - " + sml + ", " + med, embed=embed)
				elif value >= (150 * 1000000000):
					await channel.send(tag_type + tick + " - " + sml, embed=embed)

	async def post_recommendations(self, up, down, stoch):
		current_time = int(datetime.now(timezone.utc).timestamp()) + 14400
		time = datetime.utcfromtimestamp(current_time).strftime('%H:%M:%S - %d/%m/%y')

		for data in json_data["data"]:
			if up["ticker"].upper() == data["stock"]:
				up_name = data["name"] + ", $" + data["price"]
			if down["ticker"].upper() == data["stock"]:
				down_name = data["name"] + ", $" + data["price"]
			if stoch["ticker"].upper() == data["stock"]:
				stoch_name = data["name"] + ", $" + data["price"]

		embed = discord.Embed(title="Suggested Stock Picks:", description="Valid Until: **" + time + " TCT**")
		embed.set_footer(text="Suggestions are picked from 80% or higher confidence predictions, but use them as a starting point for investing.")
		embed.set_thumbnail(url=stonks_png)
		embed.color = discord.Color.blue()
		
		embed.add_field(name=":one: Stock Predicted For Gains For:", value=up_name, inline=False)
		up_high = "SVM: **$" + "{:.2f}".format(up["svm"]["high"]) + "**\n"
		up_high = up_high + "SVML: **$" + "{:.2f}".format(up["svml"]["high"]) + "**\n"
		up_high = up_high + "LR: **$" + "{:.2f}".format(up["lr"]["high"]) + "**\n"
		up_high = up_high + "Avg: **$" + "{:.2f}".format(up["avg"]["high"]) + "**\n"
		embed.add_field(name="High:", value=up_high, inline=True)
		
		up_low = "SVM: **$" + "{:.2f}".format(up["svm"]["low"]) + "**\n"
		up_low = up_low + "SVML: **$" + "{:.2f}".format(up["svml"]["low"]) + "**\n"
		up_low = up_low + "LR: **$" + "{:.2f}".format(up["lr"]["low"]) + "**\n"
		up_low = up_low + "Avg: **$" + "{:.2f}".format(up["avg"]["low"]) + "**\n"
		embed.add_field(name="Low:", value=up_low, inline=True)

		up_vola = "SVM: **" + "{:.2f}".format(up["svm"]["actual"]) + "%**\n"
		up_vola = up_vola + "SVML: **" + "{:.2f}".format(up["svml"]["actual"]) + "%**\n"
		up_vola = up_vola + "LR: **" + "{:.2f}".format(up["lr"]["actual"]) + "%**\n"
		up_vola = up_vola + "Avg: **" + "{:.2f}".format(up["avg"]["actual"]) + "%**\n"
		embed.add_field(name="Volatility:", value=up_vola, inline=True)
		
		embed.add_field(name=":two: Stock Predicted For Losses For:", value=down_name, inline=False)
		down_high = "SVM: **$" + "{:.2f}".format(down["svm"]["high"]) + "**\n"
		down_high = down_high + "SVML: **$" + "{:.2f}".format(down["svml"]["high"]) + "**\n"
		down_high = down_high + "LR: **$" + "{:.2f}".format(down["lr"]["high"]) + "**\n"
		down_high = down_high + "Avg: **$" + "{:.2f}".format(down["avg"]["high"]) + "**\n"
		embed.add_field(name="High:", value=down_high, inline=True)

		down_low = "SVM: **$" + "{:.2f}".format(down["svm"]["low"]) + "**\n"
		down_low = down_low + "SVML: **$" + "{:.2f}".format(down["svml"]["low"]) + "**\n"
		down_low = down_low + "LR: **$" + "{:.2f}".format(down["lr"]["low"]) + "**\n"
		down_low = down_low + "Avg: **$" + "{:.2f}".format(down["avg"]["low"]) + "**\n"
		embed.add_field(name="Low:", value=down_low, inline=True)
		
		down_vola = "SVM: **" + "{:.2f}".format(down["svm"]["actual"]) + "%**\n"
		down_vola = down_vola + "SVML: **" + "{:.2f}".format(down["svml"]["actual"]) + "%**\n"
		down_vola = down_vola + "LR: **" + "{:.2f}".format(down["lr"]["actual"]) + "%**\n"
		down_vola = down_vola + "Avg: **" + "{:.2f}".format(down["avg"]["actual"]) + "%**\n"
		embed.add_field(name="Volatility:", value=down_vola, inline=True)
		
		embed.add_field(name=":three: Random Stock Pick:", value=stoch_name, inline=False)
		stoch_high = "SVM: **$" + "{:.2f}".format(stoch["svm"]["high"]) + "**\n"
		stoch_high = stoch_high + "SVML: **$" + "{:.2f}".format(stoch["svml"]["high"]) + "**\n"
		stoch_high = stoch_high + "LR: **$" + "{:.2f}".format(stoch["lr"]["high"]) + "**\n"
		stoch_high = stoch_high + "Avg: **$" + "{:.2f}".format(stoch["avg"]["high"]) + "**\n"
		embed.add_field(name="High:", value=stoch_high, inline=True)

		stoch_low = "SVM: **$" + "{:.2f}".format(stoch["svm"]["low"]) + "**\n"
		stoch_low = stoch_low + "SVML: **$" + "{:.2f}".format(stoch["svml"]["low"]) + "**\n"
		stoch_low = stoch_low + "LR: **$" + "{:.2f}".format(stoch["lr"]["low"]) + "**\n"
		stoch_low = stoch_low + "Avg: **$" + "{:.2f}".format(stoch["avg"]["low"]) + "**\n"
		embed.add_field(name="Low:", value=stoch_low, inline=True)

		stoch_vola = "SVM: **" + "{:.2f}".format(stoch["svm"]["actual"]) + "%**\n"
		stoch_vola = stoch_vola + "SVML: **" + "{:.2f}".format(stoch["svml"]["actual"]) + "%**\n"
		stoch_vola = stoch_vola + "LR: **" + "{:.2f}".format(stoch["lr"]["actual"]) + "%**\n"
		stoch_vola = stoch_vola + "Avg: **" + "{:.2f}".format(stoch["avg"]["actual"]) + "%**\n"
		embed.add_field(name="Volatility:", value=stoch_vola, inline=True)

		global last_pred_id
		last_pred_id = []
		for key in range(0, len(suggestion_channels["id"])):
			channel = await client.fetch_channel(suggestion_channels["id"][key])
			last_pred_id.append(await channel.send(embed=embed))
			await last_pred_id[key].add_reaction("1️⃣")
			await last_pred_id[key].add_reaction("2️⃣")
			await last_pred_id[key].add_reaction("3️⃣")

	async def post_single_recommendation(self, stoch):
		current_time = int(datetime.now(timezone.utc).timestamp()) + 14400
		time = datetime.utcfromtimestamp(current_time).strftime('%H:%M:%S - %d/%m/%y')

		for data in json_data["data"]:
			if stoch["ticker"].upper() == data["stock"]:
				stoch_name = data["name"] + ", $" + data["price"]

		embed = discord.Embed(title="Suggested Stock Picks:", description="Valid Until: **" + time + " TCT**")
		embed.set_footer(text="Suggestions are picked from 80% or higher confidence predictions, but use them as a starting point for investing.")
		embed.set_thumbnail(url=stonks_png)
		embed.color = discord.Color.blue()
		embed.add_field(name="Notice:", value="Due to a lack of suitable values - only random is available.")	
	
		embed.add_field(name=":three: Random Stock Pick:", value=stoch_name, inline=False)
		stoch_high = "SVM: **$" + "{:.2f}".format(stoch["svm"]["high"]) + "**\n"
		stoch_high = stoch_high + "SVML: **$" + "{:.2f}".format(stoch["svml"]["high"]) + "**\n"
		stoch_high = stoch_high + "LR: **$" + "{:.2f}".format(stoch["lr"]["high"]) + "**\n"
		stoch_high = stoch_high + "Avg: **$" + "{:.2f}".format(stoch["avg"]["high"]) + "**\n"
		embed.add_field(name="High:", value=stoch_high, inline=True)

		stoch_low = "SVM: **$" + "{:.2f}".format(stoch["svm"]["low"]) + "**\n"
		stoch_low = stoch_low + "SVML: **$" + "{:.2f}".format(stoch["svml"]["low"]) + "**\n"
		stoch_low = stoch_low + "LR: **$" + "{:.2f}".format(stoch["lr"]["low"]) + "**\n"
		stoch_low = stoch_low + "Avg: **$" + "{:.2f}".format(stoch["avg"]["low"]) + "**\n"
		embed.add_field(name="Low:", value=stoch_low, inline=True)

		stoch_vola = "SVM: **" + "{:.2f}".format(stoch["svm"]["actual"]) + "%**\n"
		stoch_vola = stoch_vola + "SVML: **" + "{:.2f}".format(stoch["svml"]["actual"]) + "%**\n"
		stoch_vola = stoch_vola + "LR: **" + "{:.2f}".format(stoch["lr"]["actual"]) + "%**\n"
		stoch_vola = stoch_vola + "Avg: **" + "{:.2f}".format(stoch["avg"]["actual"]) + "%**\n"
		embed.add_field(name="Volatility:", value=stoch_vola, inline=True)

		global last_pred_id
		last_pred_id = []
		for key in range(0, len(suggestion_channels["id"])):
			channel = await client.fetch_channel(suggestion_channels["id"][key])
			last_pred_id.append(await channel.send(embed=embed))
			await last_pred_id[key].add_reaction("3️⃣")
	
	async def post_volatility(self, stocks, timestr, limit, timestart, perc):
		current_time = int(datetime.now(timezone.utc).timestamp())
		last_frame = current_time - timestart
		time = datetime.utcfromtimestamp(last_frame).strftime('%H:%M:%S - %d/%m/%y') + " TCT"
		embed = discord.Embed(title="Stocks Over "+ perc + "% Volatility:")
		embed_str = ""
		for i in range(len(stocks)):
			if i == limit:
				break
			ticker = stocks[i][0]
			name = ""
			for data in json_data["data"]:
				if ticker.upper() == data["stock"]:
					name = data["name"]
					break
			embed_str = embed_str + name + " (" + stocks[i][0].upper() + "): **" + "{:,.2f}".format(stocks[i][2]) + "%**\n"
		embed.color = discord.Color.orange()
		embed.set_thumbnail(url=stonks_png)
		embed.add_field(name="Volatility for the last " + timestr + time, value=embed_str)
		for key in range(0, len(alert_channels["id"])):
			channel = await client.fetch_channel(alert_channels["id"][key])
			await channel.send(embed=embed)

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
		if "up" in type:
			embed = discord.Embed(title=data["name"] + " Above Target Price", url="https://www.torn.com/page.php?sid=stocks&stockID="+lut_stock_id(stock)+"&tab=owned")
			embed.color = discord.Color.orange()
			embed.add_field(name="Stonks!", value=data["name"] + " has reached or exceeded your target price of: $" + "{:,}".format(value) + ".")
			embed.set_thumbnail(url=stonks_png)
			user = await self.fetch_user(id)
			self.set_author_notif(user, embed)
			await user.send(embed=embed)
		elif "down" in type:
			embed = discord.Embed(title=data["name"] + " Below Target Price", url="https://www.torn.com/page.php?sid=stocks&stockID="+lut_stock_id(stock)+"&tab=owned")
			embed.color = discord.Color.orange()
			embed.add_field(name="Stonks!", value=data["name"] + " has reached or fallen under your target price of: $" + "{:,}".format(value) + ".")
			embed.set_thumbnail(url=stonks_png)
			user = await self.fetch_user(id)
			self.set_author_notif(user, embed)
			await user.send(embed=embed)
		elif type == "loss":
			embed = discord.Embed(title=data["name"] + " Below Stop Loss Price", url="https://www.torn.com/page.php?sid=stocks&stockID="+lut_stock_id(stock)+"&tab=owned")
			embed.color = discord.Color.red()
			embed.add_field(name="Not Stonks!", value=data["name"] + " has reached or fallen below your stop loss price of: $" + "{:,}".format(value) + ".")
			embed.set_thumbnail(url=notstonks_png)
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
					if "up" in userdata["type"][item]:
						if float(data["price"]) >= userdata["value"][item]:
							client.loop.create_task(self.alert_user(item, userdata["id"][item], userdata["type"][item], userdata["stock"][item], userdata["value"][item], data))
							remove_entries.append(item)
					elif "down" in userdata["type"][item]:
						if float(data["price"]) <= userdata["value"][item]:
							client.loop.create_task(self.alert_user(item, userdata["id"][item], userdata["type"][item], userdata["stock"][item], userdata["value"][item], data))
							remove_entries.append(item)
					elif userdata["type"][item] == "loss":
						if float(data["price"]) <= userdata["value"][item]:
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
				if value_total >= (50 * 1000000000):
					embed = discord.Embed(title= "Large Sell Off: " + data["name"], url="https://www.torn.com/page.php?sid=stocks&stockID="+lut_stock_id(data["stock"])+"&tab=owned")
					embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+data["stock"]+".png")
					embed.color = discord.Color.red()
					embed.add_field(name=":handshake: Change in Shares:", value="-"+"{:,}".format(diff_shares) + " (" + "{:,.2f}".format(perc_shares) + "%)", inline=False)
					embed.add_field(name=":crown: Change in Investors:", value="{:,}".format(diff_investor) + " (" + "{:,.2f}".format(perc_investor) + "%)", inline=False)
					if value_total >= (1000 * 1000000000):
						embed.add_field(name=":moneybag: Sale Info:", value="$"+"{:,.2f}".format(value_total) + " ($" + "{:.3f}".format(price_bn / 1000) + "tn)", inline=False)
					else:
						embed.add_field(name=":moneybag: Sale Info:", value="$"+"{:,.2f}".format(value_total) + " ($" + "{:.3f}".format(price_bn) + "bn)", inline=False)
					embed.add_field(name=":money_with_wings: Share Price:", value="$"+str(data["price"]), inline=False)
					client.loop.create_task(self.alert_roles(embed, value_total, "sell", data["stock"]))
			# Buy event
			elif total_shares > total_shares_m1 and data["stock"] != "TCSE":
				if value_total >= (50 * 1000000000):
					embed = discord.Embed(title="Large Buy In: " + data["name"], url="https://www.torn.com/page.php?sid=stocks&stockID="+lut_stock_id(data["stock"])+"&tab=owned")
					embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+data["stock"]+".png")
					embed.color = discord.Color.green()
					embed.add_field(name=":handshake: Change in Shares:", value="+"+"{:,}".format(diff_shares) + " (" + "{:,.2f}".format(perc_shares) + "%)", inline=False)
					embed.add_field(name=":crown: Change in Investors:", value="{:,}".format(diff_investor) + " (" + "{:,.2f}".format(perc_investor) + "%)", inline=False)
					if value_total >= (1000 * 1000000000):
						embed.add_field(name=":moneybag: Purchase Info:", value="$"+"{:,.2f}".format(value_total) + " ($" + "{:.3f}".format(price_bn / 1000) + "tn)", inline=False)
					else:
						embed.add_field(name=":moneybag: Purchase Info:", value="$"+"{:,.2f}".format(value_total) + " ($" + "{:.3f}".format(price_bn) + "bn)", inline=False)
					embed.add_field(name=":money_with_wings: Share Price:", value="$"+str(data["price"]), inline=False)
					client.loop.create_task(self.alert_roles(embed, value_total, "buy", data["stock"]))

	def process_suggestions(self):
		stock_data = {}
		for i in range(len(stock_lut)):
			ticker = stock_lut[i].lower()
			data = predict_stocks_v2(ticker, "m5", 48, False)
			hlvc = data[1]

			# Only add stocks that pass this criteria
			if hlvc["svm"]["confidence"] >= 0.8 or hlvc["lr"]["confidence"] >= 0.8 or hlvc["svml"]["confidence"] >= 0.8:
				stock_data[ticker] = data[1]

		# Find the top three of each
		stocks = [*stock_data.keys()]
		global best_gain
		global best_loss
		global best_rand
		global not_more

		if len(stocks) >= 5:
			not_more = False
			up_tick = ""
			down_tick = ""
			up = 0
			down = 0
			# Handle best gain and loss separately to avoid duplicates
			for k in range(len(stocks)):
				ticker = stocks[k]

				svm = stock_data[ticker]["svm"]["actual"]
				lr = stock_data[ticker]["lr"]["actual"]
				svml = stock_data[ticker]["svml"]["actual"]
				avg = stock_data[ticker]["avg"]["actual"]

				if svm > up:
					up = svm
					up_tick = ticker
				elif lr > up:
					up = lr
					up_tick = ticker
				elif svml > up:
					up = svml
					up_tick = ticker
				elif avg > up:
					up = avg
					up_tick = ticker

			best_up = stock_data[up_tick]
			# Global memory
			best_gain = stock_data[up_tick]
				
			# Remove old entries from the list 
			if up_tick in stock_data:
				del stock_data[up_tick]

			stocks = [*stock_data.keys()]
			for k in range(len(stocks)):
				ticker = stocks[k]

				svm = stock_data[ticker]["svm"]["actual"]
				lr = stock_data[ticker]["lr"]["actual"]
				svml = stock_data[ticker]["svml"]["actual"]
				avg = stock_data[ticker]["avg"]["actual"]

				if svm < down:
					down = svm
					down_tick = ticker
				elif lr < down:
					down = lr
					down_tick = ticker
				elif svml < down:
					down = svml
					down_tick = ticker
				elif avg < down:
					down = avg
					down_tick = ticker

			best_down = stock_data[down_tick]
			# Global memory
			best_loss = stock_data[down_tick]			
		
			# Remove old entries from the list 
			if down_tick in stock_data:
				del stock_data[down_tick]

			# Pick a random stock to ensure a less apparent bias
			stocks = [*stock_data.keys()]
			stoch_tick = stocks[random.randint(0, len(stocks))]
			best_rand = stock_data[stoch_tick]
			with open("best_gain.json", "w") as file:
				json.dump(best_gain, file)
			with open("best_loss.json", "w") as file:
				json.dump(best_loss, file)
			with open("best_rand.json", "w") as file:
				json.dump(best_rand, file)
			client.loop.create_task(self.post_recommendations(best_up, best_down, best_rand))
		else:
			not_more = True
			# Pick a random stock since we have < 3
			stocks = [*stock_data.keys()]
			stoch_tick = stocks[random.randint(0, len(stocks))]
			best_rand = stock_data[stoch_tick]
			with open("best_gain.json", "w") as file:
				json.dump(best_rand, file)
			with open("best_loss.json", "w") as file:
				json.dump(best_rand, file)
			with open("best_rand.json", "w") as file:
				json.dump(best_rand, file)
			#client.loop.create_task(client.change_presence(status=discord.Status.online))
			client.loop.create_task(self.post_single_recommendation(best_rand))
	
	def process_volatility(self):
		stock_data = []
		for i in range(len(stock_lut)):
			ticker = stock_lut[i].lower()
			try:
				ohlc = get_stock_from_db(ticker, "m30", 2)
				vola_real = ((ohlc["low"][0] - ohlc["high"][0]) / ohlc["high"][0]) * 100
				volatility = abs(vola_real)

				if ohlc["data"][0][1] < ohlc["data"][0][4]:
					vola_real *= -1
				if volatility >= 0.25:
					stock_data.append((ticker, volatility, vola_real))
			except:
				write_notification_to_log("[WARNING] Tornsy API potentially unavailable?")
		
		if len(stock_data) > 0:
			stock_data.sort(key=lambda tup: tup[1], reverse=True)
			client.loop.create_task(self.post_volatility(stock_data, "30 minutes: ", 15, 60 * 30, "0.25"))
		else:
			write_notification_to_log("[NOTICE] No stocks to post.")

	def process_daily_volatility(self):
		stock_data = []
		for i in range(len(stock_lut)):
			ticker = stock_lut[i].lower()
			try:
				ohlc = get_tornsy_candlesticks(ticker, "d1", 2)
				volatility = abs((ohlc["low"][0] - ohlc["high"][0]) / ohlc["high"][0]) * 100
				vola_real = ((ohlc["low"][0] - ohlc["high"][0]) / ohlc["high"][0]) * 100
				if ohlc["data"][0][1] < ohlc["data"][0][4]:
					vola_real *= -1
				if volatility >= 0.75:
					stock_data.append((ticker, volatility, vola_real))
			except:
				write_notification_to_log("[WARNING] Tornsy API potentially unavailable?")
		
		if len(stock_data) > 0:
			stock_data.sort(key=lambda tup: tup[1], reverse=True)
			client.loop.create_task(self.post_volatility(stock_data, "day: ", 20, 60*60*24, "0.75"))
		else:
			write_notification_to_log("[NOTICE] No stocks to post.")

	def process_weekly_volatility(self):
		stock_data = []
		for i in range(len(stock_lut)):
			ticker = stock_lut[i].lower()
			try:
				# This runs once a week, I think we'll be fine
				ohlc = get_tornsy_candlesticks(ticker, "w1", "2")
				volatility = abs((float(ohlc["data"][0][3]) - float(ohlc["data"][0][2])) / float(ohlc["data"][0][2])) * 100
				vola_real = (float(ohlc["data"][0][3]) - float(ohlc["data"][0][2])) / float(ohlc["data"][0][2]) * 100
				if ohlc["data"][0][1] < ohlc["data"][0][4]:
					vola_real *= -1
				if volatility >= 1.25:
					stock_data.append((ticker, volatility, vola_real))
			except:
				write_notification_to_log("[WARNING] Tornsy API potentially unavailable?")
		
		if len(stock_data) > 0:
			stock_data.sort(key=lambda tup: tup[1], reverse=True)
			client.loop.create_task(self.post_volatility(stock_data, "week: ", 25, 60*60*24*7, "1.25"))
		else:
			write_notification_to_log("[NOTICE] No stocks to post.")

	async def help(self, message, prefix):
		if message.content.startswith(prefix+"help"):
			if message.content == prefix+"help":
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

	async def stock(self, message, prefix):
		if message.content.startswith(prefix+"stock"):
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
				if command[1].upper() == "CHD" or command[1].upper() == "CHED":
					embed = discord.Embed(title="<:thonk:721869856508477460> Invalid Argument? <:thonk:721869856508477460>")
					embed.add_field(name="Details:", value="I wonder what Ched's account balance looks like after Uncle's donor bender.")
					self.set_author(message, embed)
					embed.color = discord.Color.red()
					await message.channel.send(embed=embed, mention_author=False, reference=message)
					return

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
							investors_str = investors_str + investors_n + " (n1)"
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

	async def alerts(self, message, prefix):
		if message.content.startswith(prefix+"up") or message.content.startswith(prefix+"down") or message.content.startswith(prefix+"loss"):
			command = message.content.split(" ")

			# Check our command entry since we also use that to note the type of alert
			command[0] = str(command[0]).replace(prefix, "")
			types = ["up", "down", "loss"]
			if command[0] not in types and len(command) >= 1:
				err_embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
				err_embed.color = discord.Color.red()
				self.set_author(message, err_embed)
				err_embed.add_field(name="Details:", value="Invalid command. Example command: `![up/down/loss] sym 150.53` or `![up/down/loss] sym 1%`")
				await message.channel.send(embed=err_embed, mention_author=False, reference=message)
				return

			# Argument length check
			if len(command) < 3:
				err_embed = discord.Embed(title=":no_entry_sign: Invalid Arguments :no_entry_sign:")
				err_embed.color = discord.Color.red()
				self.set_author(message, err_embed)
				err_embed.add_field(name="Details:", value="Not enough arguments. Example command: `![up/down/loss] sym 150.53` or `![up/down/loss] sym 1%`")
				await message.channel.send(embed=err_embed, mention_author=False, reference=message)
				return

			# Check if the stock exists;
			if command[1].upper() not in stock_lut:
				err_embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
				err_embed.color = discord.Color.red()
				self.set_author(message, err_embed)
				err_embed.add_field(name="Details:", value="Stock ticker not found. Example command: `![up/down/loss] sym 150.53` or `![up/down/loss] sym 1%`")
				await message.channel.send(embed=err_embed, mention_author=False, reference=message)
				return

			# Process whether we're a price to reach or a percentage
			is_percentage = False
			if "%" not in command[2]:
				try:
					command[2] = float(command[2])
				except:
					err_embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
					err_embed.color = discord.Color.red()
					self.set_author(message, err_embed)
					err_embed.add_field(name="Details:", value="Numeric argument contains non numeric characters. Example command: `![up/down/loss] sym 150.53` or `![up/down/loss] sym 1%`")
					await message.channel.send(embed=err_embed, mention_author=False, reference=message)
					return
			else:
				command[2] = str(command[2]).replace("%", "")
				try:
					is_percentage = True
					command[2] = float(command[2])
				except:
					err_embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
					err_embed.color = discord.Color.red()
					self.set_author(message, err_embed)
					err_embed.add_field(name="Details:", value="Numeric argument contains non numeric characters. Example command: `![up/down/loss] sym 150.53` or `![up/down/loss] sym 1%`")
					await message.channel.send(embed=err_embed, mention_author=False, reference=message)
					return
			
			# Process if we have four arguments and the previous value isn't containing a percentage sign
			# We can fail softly since it's not needed
			if len(command) >= 4 and not is_percentage:
				if command[3] == "%":
					is_percentage = True
				else:
					err_embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
					err_embed.color = discord.Color.red()
					self.set_author(message, err_embed)
					err_embed.add_field(name="Details:", value="Percentage sign not found. Example command: `![up/down/loss] sym 150.53` or `![up/down/loss] sym 1%`")
					await message.channel.send(embed=err_embed, mention_author=False, reference=message)
					return
			
			# Since we passed input validation - add the entry and save to disk:
			userdata["id"].append(int(message.author.id))
			userdata["type"].append(command[0].lower())
			userdata["stock"].append(command[1].lower())
			if is_percentage:
				for data in json_data["data"]:
					if data["stock"] == command[1].upper():
						userdata["value"].append(float(data["price"]) * (1 + (command[2] / 100)))
						break
			else:
				userdata["value"].append(command[2])
			write_user_alerts()

			embed = discord.Embed(title=":white_check_mark: Will send you a DM when the criteria is reached. :white_check_mark:")
			embed.color = discord.Color.dark_green()
			self.set_author(message, embed)
			await message.channel.send(embed=embed, mention_author=False, reference=message)

	async def buy(self, message, prefix):
		if message.content.startswith(prefix+"buy"):
			command = message.content.split(" ", 3)
			if len(command) == 3:
				command[1] = self.strip_commas(command[1])
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

	async def sell(self, message, prefix):
		if message.content.startswith(prefix+"sell"):
			command = message.content.split(" ", 3)
			if len(command) == 3:
				command[1] = self.strip_commas(command[1])
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

	async def stop(self, message, prefix):
		if message.content == prefix+"stop":
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

	async def forget(self, message, prefix):
		if message.content.startswith(prefix+"forget"):
			if message.content == prefix+"forgetme":
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
						known_types = ["up", "down", "loss", "up_react", "down_react"]
						if command[2].lower() not in known_types:
							embed = discord.Embed(title=":no_entry_sign: Invalid Argument: :no_entry_sign:")
							embed.color = discord.Color.red()
							self.set_author(message, embed)
							embed.add_field(name="Details:", value='Command argument after stock ticker must be "up", "down", "loss", "up_react" or "down_react.')
							await message.channel.send(embed=embed, mention_author=False, reference=message)
							return
						
					if c_len == 4:
						command[3] = self.strip_commas(command[3])
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
	
	async def notifications(self, message, prefix):
		if message.content.startswith(prefix+"notifications") or message.content.startswith(prefix+"alerts"):
			command = message.content.split(" ", 3)
			if command[0] == prefix+"notifications" or command[0] == prefix+"alerts":
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
									known_alerts = known_alerts + "`!" + userdata["type"][key] + " " + userdata["stock"][key] + " " + "{:,.2f}".format(userdata["value"][key]) + "`\n"
							elif len(command) == 2:
								if command[1] == userdata["type"][key]:
									known_alerts = known_alerts + "`!" + userdata["type"][key] + " " + userdata["stock"][key] + " " + "{:,.2f}".format(userdata["value"][key]) + "`\n"
							else:
								known_alerts = known_alerts + "`!" + userdata["type"][key] + " " + userdata["stock"][key] + " " + "{:,.2f}".format(userdata["value"][key]) + "`\n"
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

	async def undo(self, message, prefix):
		# Find the command in the list
		command_found = False
		for key in range(0, len(undo_list)):
			if message.content.startswith(prefix+undo_list[key]):
				command_found = True
				break

		if command_found:
			if int(message.author.id) in userdata["id"]:
				for key in range(len(userdata["id"])-1, -1, -1):
					if int(message.author.id) == userdata["id"][key]:
						write_notification_to_log("[NOTICE]: " + message.author.display_name + " deleted notification: " + str(userdata["id"][key]) + "," + userdata["type"][key] + "," + userdata["stock"][key] + "," + str(userdata["value"][key]))
						notice = "!"+userdata["type"][key] + " " + userdata["stock"][key] + " " + "{:,.2f}".format(userdata["value"][key])
						del userdata["id"][key]
						del userdata["type"][key]
						del userdata["stock"][key]
						del userdata["value"][key]
						write_user_alerts()
						embed = discord.Embed(title="")
						embed.color = discord.Color.red()
						self.set_author(message, embed)
						# Please note this emoji only works on the offical bot;
						# Will find a way to replace this line with one of your choosing
						embed.add_field(name="Mistake Erased.",  value="Try not to make a mess of the channel history next time. <:thonk:721869856508477460>", inline=False)
						embed.add_field(name="Command Undone:", value="```"+notice+"```", inline=False)
						await message.channel.send(embed=embed, mention_author=False, reference=message)
						return
			else:
				embed = discord.Embed(title="")
				embed.color = discord.Color.dark_green()
				self.set_author(message, embed)
				embed.add_field(name="Nothing to Undo!", value="Thank you for using TornStonks Live; have a nice day. :wave:")
				await message.channel.send(embed=embed, mention_author=False, reference=message)		
			
	async def portfolio(self, message, prefix):
		# Do not allow API handling in 
		if message.content.startswith(prefix+"portfolio"):
			if message.guild:
				embed = discord.Embed(title=":no_entry_sign: API handling commands not allowed in public channels. :no_entry_sign:")
				embed.add_field(name="Details:", value="Commands that use your personal API key(s) are only allowed in Direct Messages to the bot.")
				self.set_author(message, embed)
				embed.color = discord.Color.red()
				await message.channel.send(embed=embed)

				user = await client.fetch_user(message.author.id)
				await user.send("Hi, it appears you used a Torn API key command in a public channel - these commands only work here, in your Direct Messages. I'm sending this message to you so you, can try it here.\n\n Your previous command was: ```\n" + message.content + "```")
			else:
				command = message.content.split(" ", 4)
				if len(command) > 1:
					torn_req = get_torn_stock_data(command[1])
					# Make people less paranoid
					command[1] = "there_was_an_api_key_here_now_there_isnt"
					if torn_req.status_code == 200:
						torn_json = json.loads(torn_req.text)
						if "error" in torn_json:
							embed = discord.Embed(title="")
							embed.color = discord.Color.red()
							self.set_author(message, embed)
							embed.add_field(name="Details:", value=torn_json["error"]["error"])
							await message.channel.send(embed=embed, mention_author=False, reference=message)
						else:
							embed = discord.Embed(title="Torn Stock Portfolio:", url="https://www.torn.com/page.php?sid=stocks")
							self.set_author(message, embed)
							embed.color = discord.Color.blue()
							# Add a thumbnail for filtered portfolios only.
							if len(command) >= 3:
								embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+command[2].upper()+".png")
							if len(command) == 4:
								if not command[3].isdigit():
									err_embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
									self.set_author(message, err_embed)
									err_embed.color = discord.Color.red()
									err_embed.add_field(name="Details:", value="The numeric argument for number of transactions to list is not a number. Example command: `!portfolio api_key sym 1`")
									await message.channel.send(embed=err_embed, mention_author=False, reference=message)
									return
							emb_value = ""
							for stock in torn_json["stocks"]:
								if len(command) >= 3:
									if stock_lut[int(stock)-1] == command[2].upper():
										index = 0
										for data in json_data["data"]:
											for transaction in torn_json["stocks"][stock]["transactions"]:
												if stock_lut[int(stock)-1] == data["stock"]:
													if len(command) == 4:
														if index == int(command[3]):
															break
													price_perc = float((float(data["price"]) - torn_json["stocks"][stock]["transactions"][transaction]["bought_price"]) / torn_json["stocks"][stock]["transactions"][transaction]["bought_price"]) * 100
													timestamp = datetime.utcfromtimestamp(int(torn_json["stocks"][stock]["transactions"][transaction]["time_bought"])).strftime('%H:%M:%S - %d/%m/%y TCT')
													emb_value = emb_value + "**" + timestamp + ":**\n"
													emb_value = emb_value + "Purchase Price: $" + str(torn_json["stocks"][stock]["transactions"][transaction]["bought_price"]) + ", (" + "{:,.2f}".format(price_perc) + "%)\n"
													emb_value = emb_value + "Shares: " "{:,}".format(torn_json["stocks"][stock]["transactions"][transaction]["shares"]) + "\n\n"
													index += 1
								else:
									for data in json_data["data"]:
										for transaction in torn_json["stocks"][stock]["transactions"]:
											if stock_lut[int(stock)-1] == data["stock"]:
												price_perc = float((float(data["price"]) - torn_json["stocks"][stock]["transactions"][transaction]["bought_price"]) / torn_json["stocks"][stock]["transactions"][transaction]["bought_price"]) * 100
												timestamp = datetime.utcfromtimestamp(int(torn_json["stocks"][stock]["transactions"][transaction]["time_bought"])).strftime('%H:%M:%S - %d/%m/%y TCT')
												emb_value = emb_value + "**" + timestamp + ":**\n"
												emb_value = emb_value + "Purchase Price: $" + str(torn_json["stocks"][stock]["transactions"][transaction]["bought_price"]) + ", (" + "{:,.2f}".format(price_perc) + "%)\n"
												emb_value = emb_value + "Shares: " "{:,}".format(torn_json["stocks"][stock]["transactions"][transaction]["shares"]) + "\n\n"
								for data in json_data["data"]:
									if len(command) >= 3:
										if stock_lut[int(stock)-1] == command[2].upper() and stock_lut[int(stock)-1] == data["stock"]:
											embed.add_field(name=data["name"] + " ($" + str(data["price"]) + ")", value=emb_value, inline=False)
											emb_value = ""
									elif stock_lut[int(stock)-1] == data["stock"] and len(command) == 2:
										embed.add_field(name=data["name"] + " ($" + str(data["price"]) + "):", value=emb_value, inline=False)
										emb_value = ""
							await message.channel.send(embed=embed, mention_author=False, reference=message)	
					else:
						print("Networking issue?")
				else:
					embed = discord.Embed(title=":no_entry_sign: Invalid Arguments :no_entry_sign:")
					embed.color = discord.Color.red()
					self.set_author(message, embed)
					embed.add_field(name="Details:", value="The command arguments are either missing the Torn API key, or too few/too many arguments, try the following example in a DM:\n\n`!portfolio API_key_here sym`")
					await message.channel.send(embed=embed, mention_author=False, reference=message)

	async def credits(self, message, prefix):
		if message.content == prefix+"credits":
			thanks_str = ""
			with open("thanks.md", "r") as thanks:
				lines = thanks.readlines()
				for line in lines:
					thanks_str = thanks_str + line

			thanks_str = thanks_str + "\n\nThank you truly, for using TornStonks Live! :thumbsup:"

			embed = discord.Embed(title="")
			embed.color = discord.Color.purple()
			self.set_author(message, embed)
			embed.add_field(name="Many Thanks To:", value=thanks_str)

			await message.channel.send(embed=embed, mention_author=False, reference=message)

	async def predict(self, message, prefix):
		if message.content.startswith(prefix+"predict"):
			command = message.content.split(" ")

			for key in range(0, len(command_channels["id"])):
				if int(message.channel.id) == command_channels["id"][key]:
					if command_channels["predict"][key] == "dm" and int(message.author.id) not in bot_admins:
						embed = discord.Embed(title=":no_entry_sign: Not Allowed In This Channel :no_entry_sign:")
						embed.add_field(name="Details:", value="Prediction discussion must be relegated to it's own channel, or in Direct Messages.")
						self.set_author(message, embed)
						embed.color = discord.Color.red()
						await message.channel.send(embed=embed, mention_author=False, reference=message)
						return

			if len(command) < 4:
				embed = discord.Embed(title=":no_entry_sign: Invalid Arguments :no_entry_sign:")
				embed.add_field(name="Details:", value="Too few arguments. Example command:\n```!predict sym d1 31```")
				self.set_author(message, embed)
				embed.color = discord.Color.red()
				await message.channel.send(embed=embed, mention_author=False, reference=message)
				return

			test_lut = str(command[1].upper())
			if test_lut == "CHD" or test_lut == "CHED":
				embed = discord.Embed(title="<:thonk:721869856508477460> Invalid Argument? <:thonk:721869856508477460>")
				embed.add_field(name="Details:", value="Unless you can read Chedburn's mind or have source code access, we're not predicting anything.")
				self.set_author(message, embed)
				embed.color = discord.Color.red()
				await message.channel.send(embed=embed, mention_author=False, reference=message)
				return
			elif test_lut not in stock_lut:
				embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
				embed.add_field(name="Details:", value="Stock ticker is not found.")
				self.set_author(message, embed)
				embed.color = discord.Color.red()
				await message.channel.send(embed=embed, mention_author=False, reference=message)
				return
			ohlc_time = str(command[2].lower())
			if ohlc_time not in intervals:
				embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
				embed.add_field(name="Details:", value="Specified time period is not supported. Supported intervals:\n`m1 m5 m15 m30 h1 h2 h4 h6 h12 d1`")
				self.set_author(message, embed)
				embed.color = discord.Color.red()
				await message.channel.send(embed=embed, mention_author=False, reference=message)
				return
			elif ohlc_time == "n1" or ohlc_time == "y1":
				embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
				embed.add_field(name="Details:", value="Specified time period is **currently** not supported. Supported intervals:\n`m1 m5 m15 m30 h1 h2 h4 h6 h12 d1 w1`")
				self.set_author(message, embed)
				embed.color = discord.Color.red()
				await message.channel.send(embed=embed, mention_author=False, reference=message)
				return

			try:
				command[3] = int(command[3])
			except:
				embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
				embed.add_field(name="Details:", value="The multiples of your specified time period is not a number.")
				self.set_author(message, embed)
				embed.color = discord.Color.red()
				await message.channel.send(embed=embed, mention_author=False, reference=message)
				return

			if len(command) == 5:
				try:
					command[4] = int(command[4])
				except:
					command[4] = 2000

			await message.add_reaction("✅")
			# TODO: Allow the command to turn graphs on and off
			graph_return = ""
			try:
				if len(command) == 5:
					graph_return = predict_stocks_v2(command[1].lower(), command[2].lower(), int(command[3]), True, samples=command[4])
				else:
					graph_return = predict_stocks_v2(command[1].lower(), command[2].lower(), int(command[3]), True)

			except:
				write_notification_to_log("[ERROR] PREDICT ERROR: " + message.content)
				err_embed = discord.Embed(title="PREDICT ERROR:")
				err_embed.set_thumbnail(url=notstonks_png)
				self.set_author(message, err_embed)
				err_embed.add_field(name="Details:", value="Something went wrong with generating prediction data.\nCommand used:\n\n```" + message.content + "```")
				err_embed.color = discord.Color.red()
				await message.channel.send(embed=embed, mention_author=False, reference=message)
				return
			hlvc = graph_return[1]
			ticks = graph_return[3]

			embed = discord.Embed(title="Predictions For " + graph_return[2], url="https://www.torn.com/page.php?sid=stocks&stockID="+lut_stock_id(test_lut)+"&tab=owned")
			embed.color = discord.Color.blue()
			embed.set_thumbnail(url="https://www.torn.com/images/v2/stock-market/logos/"+command[1].upper()+".png")
			self.set_author(message, embed)

			high_str = "SVM: **$" + "{:.2f}".format(hlvc["svm"]["high"]) + "**\n"
			high_str = high_str + "SVML: **$" + "{:.2f}".format(hlvc["svml"]["high"]) + "**\n"
			high_str = high_str + "LR: **$" + "{:.2f}".format(hlvc["lr"]["high"]) + "**\n"
			high_str = high_str + "Avg: **$" + "{:.2f}".format(hlvc["avg"]["high"]) + "**"
			embed.add_field(name="High:", value=high_str)
			low_str = "SVM: **$" + "{:.2f}".format(hlvc["svm"]["low"]) + "**\n"
			low_str = low_str + "SVML: **$" + "{:.2f}".format(hlvc["svml"]["low"]) + "**\n"
			low_str = low_str + "LR: **$" + "{:.2f}".format(hlvc["lr"]["low"]) + "**\n"
			low_str = low_str + "Avg: **$" + "{:.2f}".format(hlvc["avg"]["low"]) + "**"
			embed.add_field(name="Low:", value=low_str)
			vola_str = "SVM: ±**" + "{:.2f}".format(hlvc["svm"]["volatility"]) + "%**\n"
			vola_str = vola_str + "SVML: ±**" + "{:.2f}".format(hlvc["svml"]["volatility"]) + "%**\n"
			vola_str = vola_str + "LR: ±**" + "{:.2f}".format(hlvc["lr"]["volatility"]) + "%**\n"
			vola_str = vola_str + "Avg: ±**" + "{:.2f}".format(hlvc["avg"]["volatility"]) + "%**\n"
			embed.add_field(name="Volatility:", value=vola_str)
			conf_str = "SVM: **" + "{:.2f}".format(hlvc["svm"]["confidence"] * 100) + "%**"
			if hlvc["svm"]["confidence"] * 100 < 35:
				conf_str = conf_str + " :warning:"
			conf_str = conf_str + "\n"
			conf_str = conf_str + "SVML: **" + "{:.2f}".format(hlvc["svml"]["confidence"] * 100) + "%**"
			if hlvc["svml"]["confidence"] * 100 < 35:
				conf_str = conf_str + " :warning:"
			conf_str = conf_str + "\n"
			conf_str = conf_str + "LR: **" + "{:.2f}".format(hlvc["lr"]["confidence"] * 100) + "%**"
			if hlvc["lr"]["confidence"] * 100 < 35:
				conf_str = conf_str + " :warning:"
			conf_str = conf_str + "\n"
			conf_str = conf_str + "Avg: **" + "{:.2f}".format(hlvc["avg"]["confidence"] * 100) + "%**"
			if hlvc["avg"]["confidence"] * 100 < 35:
				conf_str = conf_str + " :warning:"
			embed.add_field(name="Confidence:", value=conf_str)
			embed.add_field(name="Time Scale:", value="From: **"+ticks[0] + " TCT**\nTo: **" + ticks[8] + " TCT**")
			embed.add_field(name="Notes:", value="The closer confidence is to 100% the more likely it's predictions are mostly accurate from current data. ~~Gamble~~ Invest responsibly.\n\nGraphs are for visual aid, not sound advice.", inline=False)
			await message.channel.send(embed=embed, mention_author=False, reference=message)
			await message.channel.send(file=discord.File(graph_return[0]))
			return

	async def overview(self, message, prefix):
		if message.content.startswith(prefix+"overview"):
			command = message.content.split(" ")

			for key in range(0, len(command_channels["id"])):
				if int(message.channel.id) == command_channels["id"][key]:
					if command_channels["predict"][key] == "dm" and int(message.author.id) not in bot_admins:
						embed = discord.Embed(title=":no_entry_sign: Not Allowed In This Channel :no_entry_sign:")
						embed.add_field(name="Details:", value="Overview discussion must be relegated to it's own channel, or in Direct Messages.")
						self.set_author(message, embed)
						embed.color = discord.Color.red()
						await message.channel.send(embed=embed, mention_author=False, reference=message)
						return

			if len(command) < 3 or len(command) > 4:
				print(len(command))
				embed = discord.Embed(title=":no_entry_sign: Invalid Arguments :no_entry_sign:")
				embed.add_field(name="Details:", value="Too few/many arguments. Example command:\n```!overview d1 31 [up/down]```")
				self.set_author(message, embed)
				embed.color = discord.Color.red()
				await message.channel.send(embed=embed, mention_author=False, reference=message)
				return

			ohlc_time = str(command[1].lower())
			if ohlc_time not in intervals:
				embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
				embed.add_field(name="Details:", value="Specified time period is not supported. Supported intervals:\n`m1 m5 m15 m30 h1 h2 h4 h6 h12 d1 w1`")
				self.set_author(message, embed)
				embed.color = discord.Color.red()
				await message.channel.send(embed=embed, mention_author=False, reference=message)
				return
			elif ohlc_time == "n1" or ohlc_time == "y1":
				embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
				embed.add_field(name="Details:", value="Specified time period is **currently** not supported. Supported intervals:\n`m1 m5 m15 m30 h1 h2 h4 h6 h12 d1 w1`")
				self.set_author(message, embed)
				embed.color = discord.Color.red()
				await message.channel.send(embed=embed, mention_author=False, reference=message)
				return

			try:
				command[2] = int(command[2])
			except:
				embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
				embed.add_field(name="Details:", value="The multiples of your specified time period is not a number.")
				self.set_author(message, embed)
				embed.color = discord.Color.red()
				await message.channel.send(embed=embed, mention_author=False, reference=message)
				return
			
			if len(command) == 4:
				if command[3] not in ["up", "down"]:
					embed = discord.Embed(title=":no_entry_sign: Invalid Argument :no_entry_sign:")
					embed.add_field(name="Details:", value="The the optional argument must be up or down.")
					self.set_author(message, embed)
					embed.color = discord.Color.red()
					await message.channel.send(embed=embed, mention_author=False, reference=message)
					return

			await message.add_reaction("✅")
			stock_data = []
			time_ticks = 1234
			for i in range(len(stock_lut)):
				ticker = stock_lut[i].lower()
				try:
					graph_return = predict_stocks_v2(ticker, command[1].lower(), command[2], False)
					hlvc = graph_return[1]
					m1_price = 0
					for data in json_data["data"]:
						if ticker.upper() == data["stock"]:
							m1_price = float(data["price"])
							break
					# perc_price = float((price - price_h) / price_h) * 100
					low_perc = float((m1_price - hlvc["avg"]["low"]) / hlvc["avg"]["low"]) * -100
					high_perc = float((m1_price - hlvc["avg"]["high"]) / hlvc["avg"]["high"]) * -100
					if time_ticks == 1234:
						time_ticks = graph_return[3][8]

					if len(command) == 4:
						if command[3] == "up" and high_perc >= 0:		
							stock_data.append((ticker.upper(), m1_price, hlvc["avg"]["low"], low_perc, hlvc["avg"]["high"], high_perc, abs(low_perc) + abs(high_perc), hlvc["avg"]["confidence"] * 100))
						elif command[3] == "down" and high_perc < 0:
							stock_data.append((ticker.upper(), m1_price, hlvc["avg"]["low"], low_perc, hlvc["avg"]["high"], high_perc, abs(low_perc) + abs(high_perc), hlvc["avg"]["confidence"] * 100))
					else:
						stock_data.append((ticker.upper(), m1_price, hlvc["avg"]["low"], low_perc, hlvc["avg"]["high"], high_perc, abs(low_perc) + abs(high_perc), hlvc["avg"]["confidence"] * 100))
				except:
					write_notification_to_log("[WARNING] Tornsy API potentially unavailable?")
				
			# Abandon efforts if there's no stocks
			if len(stock_data) == 0:
				return

			stock_data.sort(key=lambda tup: tup[5], reverse=True)

			embed_str = ""
			for tup in range(8):
				# Abandon adding things if we have less entries than 8
				if len(stock_data) == tup:
					break
				#if i == 8:
					#break
				embed_str = embed_str + stock_data[tup][0] + " ($" + "{:,.2f}".format(stock_data[tup][1]) + "):\nLow: $" + "{:,.2f}".format(stock_data[tup][2]) + " (" + "{:.2f}".format(stock_data[tup][3]) + "%), High: $" + "{:,.2f}".format(stock_data[tup][4]) + " (" + "{:.2f}".format(stock_data[tup][5]) + "%)\nVolatility: " + "{:.2f}".format(stock_data[tup][6]) + "%, Confidence: " + "{:.2f}".format(stock_data[tup][7]) + "%\n\n"
			embed = discord.Embed(title="Overview Valid Until: " + time_ticks + " TCT", )
			embed.color = discord.Color.blue()
			embed.add_field(name=time_ticks + " TCT", value=embed_str)
			self.set_author(message, embed)
			await message.channel.send(embed=embed, mention_author=False, reference=message)
	
	def test_suggestions(self, message, prefix):
		if message.content == prefix+"suggest":
			global bot_admins
			if int(message.author.id) in bot_admins:
				print("will make suggestions")
				self.process_suggestions()
			else:
				print("will not make suggestions")
		elif message.content == prefix+"volatility":
			if int(message.author.id) in bot_admins:
				self.process_volatility()

	async def chedded(self, message, prefix):
		if message.content.startswith(prefix+"chedded"):
			await message.channel.send("If #chedded doesn't work, have we tried #blamebogie?", mention_author=False, reference=message)
		elif message.content.startswith(prefix+"ched"):
			await message.channel.send("The hidden hand strikes again in your misfortune; maybe it's a hint to buy DPs.", mention_author=False, reference=message)

	async def system_message(self, message, prefix):
		if message.content.startswith(prefix+"system_message"):
			if int(message.author.id) in bot_admins:
				new_msg = message.content.replace(prefix+"system_message ", "")
				for key in range(0, len(alert_channels["id"])):
					channel = await client.fetch_channel(alert_channels["id"][key])
					await channel.send(new_msg)

	async def backtest(self, message, prefix):
		if message.content.startswith(prefix+"backtest"):
			command = message.content.split(" ")
			if command[1].lower() == "stoch":
				if len(command) == 2:
					embed = discord.Embed(title="Backtest Help for STOCH:")
					self.set_author(message, embed)
					embed.color = discord.Color.purple()
					embed.add_field(name="Syntax:", value="Optional command arguments that have a set default will be marked in `[square brackets]`.", inline=False)
					embed.add_field(name="Example Command:", value="```\n!backtest stoch sym m15 2000 14 3 0.1 [true/false]\n```", inline=False)
					embed.add_field(name="Ticker Argument:", value="Ticker of the stock you want to backtest against.", inline=False)
					embed.add_field(name="Time Argument:", value="Time frame for the scale of.", inline=False)
					embed.add_field(name="History Argument:", value="Number of previous candlesticks to load.\nDefault: `2000`", inline=False)
					embed.add_field(name="K Argument:", value="Number of closed positions to use.\nDefault: `14`", inline=False)
					embed.add_field(name="D Argument:", value="Number of previous K values to smooth. Cannot exceed the value of K.\nDefault: `3`", inline=False)
					embed.add_field(name="Profit Percentage Argument:", value="Percentage to sell at when K and T reach their triggers.\nDefault: `0.1`", inline=False)
					embed.add_field(name="Show Graph Argument:", value="Whether to display the backtesting graph.\nValid Values: `true / false`\nDefault: `true`", inline=False)
					await message.channel.send(embed=embed, mention_author=False, reference=message)
				elif len(command) < 8:
					embed = discord.Embed(title="Error:")
					self.set_author(message, embed)
					embed.color = discord.Color.red()
					embed.add_field(inline=False, name="Details:", value="Invalid number of arguments, try the built in help: ```\n!backtest stoch\n```")
					await message.channel.send(embed=embed, mention_author=False, reference=message)
				else:
					# Error handler
					if command[2].upper() not in stock_lut:
						embed = discord.Embed(title="Invalid Argument:")
						self.set_author(message, embed)
						embed.color = discord.Color.red()
						embed.add_field(inline=False, name="Details:", value="Stock ticker not found.")
						await message.channel.send(embed=embed, mention_author=False, reference=message)
						return

					if command[3].lower() not in intervals:
						embed = discord.Embed(title="Invalid Argument:")
						self.set_author(message, embed)
						embed.color = discord.Color.red()
						embed.add_field(inline=False, name="Details:", value="Interval not supported.\nSupported intervals:\n`m1 m5 m15 m30 h1 h2 h4 h6 h12 d1`")
						await message.channel.send(embed=embed, mention_author=False, reference=message)
						return
					
					try:
						command[4] = int(command[4])
					except:
						command[4] = 2000
					
					try:
						command[5] = int(command[5])
					except:
						command[5] = 14

					try:
						command[6] = int(command[6])
					except:
						command[6] = 3
					
					# Prevent exceeding the value of K
					if command[6] >= command[5]:
						command[6] = 3
					
					try:
						command[7] = float(command[7])
					except:
						command[7] = 0.1
					if command[7] < 0:
						command[7] = 0

					await message.add_reaction("✅")
					stoch_output = []
					try:
						if len(command) == 9:
							if command[8].lower() == "false":
								stoch_output = get_stoch(command[2].lower(), command[3].lower(), limit=command[4], k=command[5], t=command[6], profit_perc=command[7], render_graphs=False)
						else:
							stoch_output = get_stoch(command[2].lower(), command[3].lower(), limit=command[4], k=command[5], t=command[6], profit_perc=command[7], render_graphs=True)
					except:
						await message.add_reaction("❌")
						return

					embed = discord.Embed(title="Backtesting Results For STOCH:")
					self.set_author(message, embed)
					embed.color = discord.Color.blue()
					time_str = "From: **" + stoch_output[1][0] + " TCT**\n" + "To: **" + stoch_output[1][6] + " TCT **"
					embed.add_field(name="Time Range:", value=time_str, inline=False)
					setting_str = "Ticker: " + command[2].upper() + "\n"
					setting_str += "Time: " + str(command[4]) + " x " + command[3] + "\n"
					setting_str += "Sell Threshold: " + str(command[7]) + "%\n"
					setting_str += "K: " + str(command[5]) + "\n"
					setting_str += "D: " + str(command[6]) + "\n"
					embed.add_field(name="Settings:", value=setting_str, inline=False)
					misc_stats = "Percentage Gained: " + "{:.2f}".format(stoch_output[4]) + "%\n"
					misc_stats += "Times Bought: " + "{:,}".format(stoch_output[2] + 1) + "\n"
					misc_stats += "Times Sold: " + "{:,}".format(stoch_output[3]) + "\n"
					embed.add_field(name="Misc Stats:", value=misc_stats, inline=False)
					await message.channel.send(embed=embed, mention_author=False, reference=message)
					if len(command) == 9:
						if command[8].lower() == "true":
							await message.channel.send(file=discord.File(stoch_output[0]))
					else:
						await message.channel.send(file=discord.File(stoch_output[0]))


	async def on_message(self, message):
		# The bot should never respond to itself, ever
		if message.author == self.user:
			return

		# Ignore noisy bots
		if message.author.bot:
			return

		# Only respond in our designated channels to not shit up the place
		# This includes DMs
		if not int(message.channel.id) in command_channels["id"] and message.guild:
			return
		
		# Default for DMs, but not in servers
		cmd_prefix = "!"
		if message.guild:
			for key in range(0, len(command_channels["id"])):
				if int(message.channel.id) == command_channels["id"][key]:
					cmd_prefix = command_channels["prefix"][key]
					break
		
		# Our command list (find a better system for this)
		await self.help(message, cmd_prefix)
		await self.stock(message, cmd_prefix)
		await self.alerts(message, cmd_prefix)
		await self.buy(message, cmd_prefix)
		await self.sell(message, cmd_prefix)
		await self.forget(message, cmd_prefix)
		await self.undo(message, cmd_prefix)
		await self.notifications(message, cmd_prefix)
		await self.portfolio(message, cmd_prefix)
		await self.credits(message, cmd_prefix)
		await self.predict(message, cmd_prefix)
		await self.overview(message, cmd_prefix)
		self.test_suggestions(message, cmd_prefix)
		await self.system_message(message, cmd_prefix)
		await self.chedded(message, cmd_prefix)
		await self.backtest(message, cmd_prefix)
		await self.stop(message, cmd_prefix)

	# Listen for automated reactions on suggestions
	async def on_raw_reaction_add(self, payload):
		user = await client.fetch_user(payload.user_id)
		# The bot should add itself to the userdata list
		if user == self.user:
			return

		# Ignore noisy bots or terrible bots
		if user.bot:
			return

		one = "1️⃣"
		two = "2️⃣"
		three = "3️⃣"
		global last_pred_id
		message_id = int(payload.message_id)
		for message in last_pred_id:
			if message_id == int(message.id):
				global not_more
				if payload.emoji.name == one and not not_more:
					lowest_perc = 10000
					if best_gain["svm"]["actual"] > 0:
						lowest_perc = best_gain["svm"]["actual"]
					if best_gain["svml"]["actual"] < lowest_perc and best_gain["svml"]["actual"] > 0:
						lowest_perc = best_gain["svml"]["actual"]
					if best_gain["lr"]["actual"] < lowest_perc and best_gain["lr"]["actual"] > 0:
						lowest_perc = best_gain["lr"]["actual"]
					if best_gain["avg"]["actual"] < lowest_perc and best_gain["avg"]["actual"] > 0:
						lowest_perc = best_gain["avg"]["actual"]
					for data in json_data["data"]:
						if data["stock"] == best_gain["ticker"].upper():
							userdata["id"].append(int(payload.user_id))
							userdata["type"].append("up_react")
							userdata["stock"].append(str(best_gain["ticker"].lower()))
							userdata["value"].append(best_gain["price"] * (1 + (lowest_perc / 100)))
							write_user_alerts()
							break
				elif payload.emoji.name == two and not not_more:
					lowest_perc = -10000
					if best_loss["svm"]["actual"] < 0:
						lowest_perc = best_loss["svm"]["actual"]
					if best_loss["svml"]["actual"] > lowest_perc and best_loss["svml"]["actual"] < 0:
						lowest_perc = best_loss["svml"]["actual"]
					if best_loss["lr"]["actual"] > lowest_perc and best_loss["lr"]["actual"] < 0:
						lowest_perc = best_loss["lr"]["actual"]
					if best_loss["avg"]["actual"] > lowest_perc and best_loss["avg"]["actual"] < 0:
						lowest_perc = best_loss["avg"]["actual"]
					for data in json_data["data"]:
						if data["stock"] == best_loss["ticker"].upper():
							userdata["id"].append(int(payload.user_id))
							userdata["type"].append("down_react")
							userdata["stock"].append(best_loss["ticker"].lower())
							userdata["value"].append(best_loss["price"] * (1 + (lowest_perc / 100)))
							write_user_alerts()
							break
				elif payload.emoji.name == three:
					# Use the average to determine an up or down setting
					lowest_perc = 0
					if best_rand["avg"]["actual"] < 0:
						lowest_perc = -10000
						if best_rand["svm"]["actual"] > lowest_perc and best_rand["svm"]["actual"] < 0:
							lowest_perc = best_rand["svm"]["actual"]
						if best_rand["svml"]["actual"] > lowest_perc and best_rand["svml"]["actual"] < 0:
							lowest_perc = best_rand["svml"]["actual"]
						if best_rand["lr"]["actual"] > lowest_perc and best_rand["lr"]["actual"] < 0:
							lowest_perc = best_rand["lr"]["actual"]
						if best_rand["avg"]["actual"] > lowest_perc and best_rand["avg"]["actual"] < 0:
							lowest_perc = best_rand["avg"]["actual"]
						for data in json_data["data"]:
							if data["stock"] == best_rand["ticker"].upper():
								userdata["id"].append(int(payload.user_id))
								userdata["type"].append("down_react")
								userdata["stock"].append(best_rand["ticker"].lower())
								userdata["value"].append(best_rand["price"] * (1 + (lowest_perc / 100)))
								write_user_alerts()
								break
					else:
						lowest_perc = 10000
						if best_rand["svm"]["actual"] < lowest_perc and best_rand["svm"]["actual"] > 0:
							lowest_perc = best_gain["svm"]["actual"]
						if best_rand["svml"]["actual"] < lowest_perc and best_rand["svml"]["actual"] > 0:
							lowest_perc = best_gain["svml"]["actual"]
						if best_rand["lr"]["actual"] < lowest_perc and best_rand["lr"]["actual"] > 0:
							lowest_perc = best_gain["lr"]["actual"]
						if best_rand["avg"]["actual"] < lowest_perc and best_rand["avg"]["actual"] > 0:
							lowest_perc = best_gain["avg"]["actual"]
						for data in json_data["data"]:
							if data["stock"] == best_rand["ticker"].upper():
								userdata["id"].append(int(payload.user_id))
								userdata["type"].append("up_react")
								userdata["stock"].append(best_rand["ticker"].lower())
								userdata["value"].append(best_rand["price"] * (1 + (lowest_perc / 100)))
								write_user_alerts()
								break
				
	async def on_raw_reaction_remove(self, payload):
		user = await client.fetch_user(payload.user_id)
		# The bot should add itself to the userdata list
		if user == self.user:
			return

		# Ignore noisy bots or terrible bots
		if user.bot:
			return

		global last_pred_id
		one = "1️⃣"
		two = "2️⃣"
		three = "3️⃣"
		global last_pred_id
		message_id = int(payload.message_id)

		for message in last_pred_id:
			if message_id == int(message.id):
				if int(payload.user_id) in userdata["id"]:
					for key in range(len(userdata["id"])-1, -1, -1):
						if int(user.id) == userdata["id"][key]:
							rem_str = ""
							if payload.emoji.name == one and not not_more:
								rem_str = "up_react"
							elif payload.emoji.name == two and not not_more:
								rem_str = "down_react"
							elif payload.emoji.name == three:
								if best_rand["avg"]["actual"] < 0:
									rem_str = "down_react"
								else:
									rem_str = "up_react"
							
							if rem_str == userdata["type"][key]:
								write_notification_to_log("[NOTICE]: " + user.display_name + " deleted notification: " + str(userdata["id"][key]) + "," + userdata["type"][key] + "," + userdata["stock"][key] + "," + str(userdata["value"][key]))
								del userdata["id"][key]
								del userdata["type"][key]
								del userdata["stock"][key]
								del userdata["value"][key]
								write_user_alerts()
								break
			

client = TornStonksLive(intents=intent)
client.run(bot_token)
# Code written below this comment will never be executed