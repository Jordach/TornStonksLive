from math import floor
import json
import requests
import sqlite3
import math
from datetime import datetime
import time
import os
import re
from urllib.request import pathname2url

def get_tornsy_candles(ticker, interval, limit, to="NONE", timeout=30):
	ohlc_address = "https://tornsy.com/api/" + ticker + "?interval=" + interval + "&limit=" + limit

	# If a timestamp was specified, add that to the call
	if to != "NONE":
		ohlc_address = ohlc_address + "&to=" + str(to)

	try:
		ohlc_req = requests.get(ohlc_address, timeout=timeout)
	except requests.RequestException:
		return False
	if ohlc_req.status_code == 200:
		ohlc_data = json.loads(ohlc_req.text)
		return ohlc_data
	else:
		return False

# Tables that exist in each stock DB. Interval names are spliced into SQL as table
# names, so anything outside this list must be rejected.
_DB_INTERVALS = {"m1", "m5", "m15", "m30", "h1", "h2", "h4", "h6", "h12", "d1"}
_TICKER_PATTERN = re.compile(r"^[a-z]{2,6}$")

def get_stock_from_db(ticker, interval, limit=-1):
	# Translate between local SQL db and expected formatting:
	name = ticker.lower()
	interval = interval.lower()
	# Tickers become file names and intervals become table names, so validate both
	if not _TICKER_PATTERN.match(name):
		raise ValueError("Invalid ticker: " + repr(ticker))
	if interval not in _DB_INTERVALS:
		raise ValueError("Invalid interval: " + repr(interval))

	# Read-only so an unknown ticker raises instead of creating an empty DB file
	path = os.path.join(os.getcwd(), "db", "db_" + name + ".db")
	con = sqlite3.connect("file:" + pathname2url(path) + "?mode=ro", uri=True)

	ohlc_data = []

	query = "SELECT * FROM " + interval + " ORDER BY date DESC LIMIT ?"
	try:
		for row in con.execute(query, (int(limit) if limit > 0 else 4000,)):
			ohlc_data.append(row)
	finally:
		con.close()

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

def get_stock_df(ticker, interval):
	"""Full candle history as a DataFrame with integer epoch `date` and lowercase OHLC columns."""
	import pandas as pd
	name = ticker.lower()
	interval = interval.lower()
	if not _TICKER_PATTERN.match(name):
		raise ValueError("Invalid ticker: " + repr(ticker))
	if interval not in _DB_INTERVALS:
		raise ValueError("Invalid interval: " + repr(interval))

	path = os.path.join(os.getcwd(), "db", "db_" + name + ".db")
	con = sqlite3.connect("file:" + pathname2url(path) + "?mode=ro", uri=True)
	try:
		df = pd.read_sql_query("SELECT date, open, high, low, close FROM " + interval + " ORDER BY date ASC", con)
	finally:
		con.close()
	return df.astype({"date": "int64", "open": "float64", "high": "float64", "low": "float64", "close": "float64"})

def fill_daily_gaps_from_tornsy(ticker, limit=2000, timeout=10):
	"""
	Fill missing completed d1 candles from Tornsy's own daily history. The m1-based
	backfill only reaches back a day or so, so any downtime leaves holes in d1 that
	break longer-term indicators. Existing rows are never overwritten.
	Returns the number of days added, or -1 if Tornsy could not be reached.
	"""
	name = ticker.lower()
	if not _TICKER_PATTERN.match(name):
		raise ValueError("Invalid ticker: " + repr(ticker))
	ohlc = get_tornsy_candles(name, "d1", str(int(limit)), timeout=timeout)
	if not ohlc or "data" not in ohlc:
		return -1

	now = int(time.time())
	today = now - (now % 86400)
	rows = []
	for item in ohlc["data"]:
		ts = int(item[0])
		# Skip the day still in progress; the live feed owns that candle
		if ts >= today:
			continue
		rows.append((ts, float(item[1]), float(item[2]), float(item[3]), float(item[4])))

	con = sqlite3.connect(os.path.join(os.getcwd(), "db", "db_" + name + ".db"))
	try:
		con.execute("CREATE TABLE IF NOT EXISTS d1 (date integer PRIMARY KEY UNIQUE, open real, high real, low real, close real)")
		before = con.total_changes
		con.executemany("INSERT OR IGNORE INTO d1 (date, open, high, low, close) VALUES (?, ?, ?, ?, ?)", rows)
		con.commit()
		return con.total_changes - before
	finally:
		con.close()

def import_from_tornsy(ticker, intervals, limit=-1):
	pwd = os.getcwd()
	name = ticker.lower()

	ohlc_data = get_tornsy_candles(ticker, "m1", "2000")
	if not ohlc_data:
		return

	con = sqlite3.connect(pwd + "/db/db_" + name + ".db")
	cur = con.cursor()

	dt = {"date":[], "Open":[], "High":[], "Low":[], "Close":[]}

	# Only grab previous entries if there are exactly 1440 m1 entries corresponding to one day.
	# Or limit >= 1
	max_items = 1440
	if len(ohlc_data["data"]) == max_items and limit > 0:
		cdate = str(ohlc_data["data"][0][0])
		ohlcs = []
		
		lim = 0
		while True:
			ohlc = get_tornsy_candles(ticker, "m1", str(max_items), cdate)
			if not ohlc:
				# Keep whatever history was fetched before the failure
				break

			cdate = str(ohlc["data"][0][0])
			ohlcs.insert(0, ohlc)
			# Don't grab another set because Tornsy lacks history
			# or if we hit the cap on importing data
			if len(ohlc["data"]) < max_items or lim == limit:
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
				con.commit()
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

			# Newly listed stocks have no tables yet; without this the insert raises
			cur.execute("CREATE TABLE IF NOT EXISTS " + interval + " (date integer PRIMARY KEY UNIQUE, open real, high real, low real, close real)")

			price = float(data["price"])
			cmd = "INSERT INTO " + interval + "(date, open, high, low, close) VALUES (?, ?, ?, ?, ?) "
			cmd += "ON CONFLICT(date) DO UPDATE SET "
			cmd += "high=IIF(excluded.high > high, excluded.high, high), "
			cmd += "low=IIF(excluded.low < low, excluded.low, low), "
			cmd += "close=excluded.close"
			cur.execute(cmd, (timestamp, price, price, price, price))

		con.commit()
		con.close()

## Suggestion tracking

_SUGGESTION_SCHEMA = (
	"CREATE TABLE IF NOT EXISTS suggestions ("
	"id integer PRIMARY KEY AUTOINCREMENT, "
	"horizon text NOT NULL, direction text NOT NULL DEFAULT 'up', ticker text NOT NULL, as_of integer NOT NULL, "
	"entry real NOT NULL, target real NOT NULL, probability real NOT NULL, "
	"closed_hit integer, touched_hit integer, final_return real, best_return real, "
	"UNIQUE(horizon, direction, ticker, as_of))"
)

def _suggestion_db():
	con = sqlite3.connect(os.path.join(os.getcwd(), "db", "db_suggestions.db"))
	con.execute(_SUGGESTION_SCHEMA)
	cols = [row[1] for row in con.execute("PRAGMA table_info(suggestions)")]
	if "direction" not in cols:
		# Pre-downswing table: rebuild so the unique key includes direction.
		# Every existing row was an upswing pick.
		con.execute("ALTER TABLE suggestions RENAME TO suggestions_old")
		con.execute(_SUGGESTION_SCHEMA)
		con.execute(
			"INSERT INTO suggestions (id, horizon, direction, ticker, as_of, entry, target, probability, closed_hit, touched_hit, final_return, best_return) "
			"SELECT id, horizon, 'up', ticker, as_of, entry, target, probability, closed_hit, touched_hit, final_return, best_return FROM suggestions_old"
		)
		con.execute("DROP TABLE suggestions_old")
		con.commit()
	return con

def suggestion_record(horizon, direction, ticker, as_of, entry, target, probability):
	"""Store a posted suggestion. Re-posting the same pick for the same day is ignored."""
	con = _suggestion_db()
	con.execute(
		"INSERT OR IGNORE INTO suggestions (horizon, direction, ticker, as_of, entry, target, probability) VALUES (?, ?, ?, ?, ?, ?, ?)",
		(str(horizon), str(direction), str(ticker).upper(), int(as_of), float(entry), float(target), float(probability)),
	)
	con.commit()
	con.close()

def suggestion_get_open():
	"""Suggestions that have not been graded yet."""
	con = _suggestion_db()
	rows = con.execute("SELECT id, horizon, direction, ticker, as_of, entry, target FROM suggestions WHERE closed_hit IS NULL").fetchall()
	con.close()
	return rows

def suggestion_set_outcome(row_id, closed_hit, touched_hit, final_return, best_return):
	con = _suggestion_db()
	con.execute(
		"UPDATE suggestions SET closed_hit = ?, touched_hit = ?, final_return = ?, best_return = ? WHERE id = ?",
		(int(closed_hit), int(touched_hit), float(final_return), float(best_return), int(row_id)),
	)
	con.commit()
	con.close()

def suggestion_get_record(horizon, direction, since=0):
	"""Graded and open suggestions for a horizon and direction, newest first."""
	con = _suggestion_db()
	rows = con.execute(
		"SELECT ticker, as_of, entry, target, probability, closed_hit, touched_hit, final_return, best_return "
		"FROM suggestions WHERE horizon = ? AND direction = ? AND as_of >= ? ORDER BY as_of DESC, probability DESC",
		(str(horizon), str(direction), int(since)),
	).fetchall()
	con.close()
	return rows
