from math import floor
import json
import requests
import sqlite3
from datetime import datetime
import time
import os

def get_tornsy_candles(ticker, interval, limit, to="NONE"):
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

	dt = {"date":[], "Open":[], "High":[], "Low":[], "Close":[], "sma":[]}
	
	if interval == "m1":
		for item in ohlc_data:
			dt["date"].append(datetime.utcfromtimestamp(int(item[0])).strftime('%H:%M:%S %d/%m/%y'))
			dt["Open"].append(float(item[1]))
			dt["High"].append(float(item[1]))
			dt["Low"].append(float(item[1]))
			dt["Close"].append(float(item[1]))
			dt["sma"].append(float(item[1]))
	else:
		for item in ohlc_data:
			dt["date"].append(datetime.utcfromtimestamp(int(item[0])).strftime('%H:%M:%S %d/%m/%y'))
			dt["Open"].append(float(item[1]))
			dt["High"].append(float(item[2]))
			dt["Low"].append(float(item[3]))
			dt["Close"].append(float(item[4]))
			dt["sma"].append(float(item[4]))
	return dt

def import_from_tornsy(ticker, intervals, limit=-1):
	pwd = os.getcwd()
	name = ticker.lower()
	con = sqlite3.connect(pwd + "/db/db_" + name + ".db")
	cur = con.cursor()

	ohlc_data = get_tornsy_candles(ticker, "m1", "2000")
	if not ohlc_data:
		return
	
	dt = {"date":[], "Open":[], "High":[], "Low":[], "Close":[]}

	# Only grab previous entries if there are exactly 2000 entries.
	# Or limit >= 1
	if len(ohlc_data["data"]) == 2000 and limit > 0:
		cdate = str(ohlc_data["data"][0][0])
		ohlcs = []
		
		lim = 0
		while True:
			ohlc = get_tornsy_candles(ticker, "m1", str(2000), cdate)
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
				dt["Open"].append((ohlcs[k]["data"][i][1]))
				dt["High"].append((ohlcs[k]["data"][i][1]))
				dt["Low"].append((ohlcs[k]["data"][i][1]))
				dt["Close"].append((ohlcs[k]["data"][i][1]))

		for item in ohlc_data["data"]:
			dt["date"].append((item[0]))
			dt["Open"].append((item[1]))
			dt["High"].append((item[1]))
			dt["Low"].append((item[1]))
			dt["Close"].append((item[1]))

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
			cmd += str(dt["Open"][i]) + ", "
			cmd += str(dt["High"][i]) + ", "
			cmd += str(dt["Low"][i]) + ", "
			cmd += str(dt["Close"][i]) + ") "
			cmd += "ON CONFLICT(date) DO UPDATE SET "
			cmd += "high=IIF(" + str(dt["High"][i]) + " > high, " + str(dt["High"][i]) + ", high), "
			cmd += "low=IIF(" + str(dt["Low"][i]) + " < low, " + str(dt["Low"][i]) + ", low), "
			cmd += "close=" + str(dt["Close"][i])
			try:
				cur.execute(cmd)
			except:
				print(cmd)

	con.commit()
	con.close()

def update_from_tornsy(json_data, intervals):
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