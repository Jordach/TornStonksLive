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
	con = sqlite3.connect("file:" + pathname2url(path) + "?mode=ro", uri=True, timeout=_BUSY_TIMEOUT)

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
	con = sqlite3.connect("file:" + pathname2url(path) + "?mode=ro", uri=True, timeout=_BUSY_TIMEOUT)
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

	con = sqlite3.connect(os.path.join(os.getcwd(), "db", "db_" + name + ".db"), timeout=_BUSY_TIMEOUT)
	try:
		con.execute("CREATE TABLE IF NOT EXISTS d1 (date integer PRIMARY KEY UNIQUE, open real, high real, low real, close real)")
		before = con.total_changes
		con.executemany("INSERT OR IGNORE INTO d1 (date, open, high, low, close) VALUES (?, ?, ?, ?, ?)", rows)
		con.commit()
		return con.total_changes - before
	finally:
		con.close()

def _last_stored_m1(path):
	"""Newest m1 timestamp already in a stock's DB, or None for a new/empty DB."""
	if not os.path.exists(path):
		return None
	con = sqlite3.connect(path, timeout=_BUSY_TIMEOUT)
	try:
		return con.execute("SELECT MAX(date) FROM m1").fetchone()[0]
	except sqlite3.OperationalError:
		return None
	finally:
		con.close()

# Seconds per candle; a candle starts at floor(timestamp / seconds) * seconds.
# Every interval divides a day, so a day always holds whole candles of each.
INTERVAL_SECONDS = {
	"m1": 60, "m5": 300, "m15": 900, "m30": 1800,
	"h1": 3600, "h2": 7200, "h4": 14400, "h6": 21600, "h12": 43200,
	"d1": 86400,
}

# Tornsy returns at most one day of minutes per request
_TORNSY_M1_PAGE = 1440

# The background backfill and the every-minute live update write to the same stock
# files from different threads; wait this long for the other to finish
_BUSY_TIMEOUT = 60

_CANDLE_SCHEMA = "CREATE TABLE IF NOT EXISTS {0} (date integer PRIMARY KEY UNIQUE, open real, high real, low real, close real)"

# Minute ranges still to fetch from Tornsy: lo <= date < hi. A NULL lo means back to
# the start of Tornsy's history; a NULL hi means up to the newest minute Tornsy has
# (Tornsy was down at startup, so the live feed couldn't fill those minutes either).
_PENDING_SCHEMA = "CREATE TABLE IF NOT EXISTS backfill_pending (lo integer, hi integer)"

# m1 keeps the live feed's merge: a re-fetched minute keeps its open and takes Tornsy's final close
_M1_UPSERT = (
	"INSERT INTO m1 (date, open, high, low, close) VALUES (?, ?, ?, ?, ?) "
	"ON CONFLICT(date) DO UPDATE SET "
	"high=MAX(high, excluded.high), low=MIN(low, excluded.low), close=excluded.close"
)

# Other intervals are rebuilt from m1, so a rebuilt candle replaces the stored one
_CANDLE_REPLACE = (
	"INSERT INTO {0} (date, open, high, low, close) VALUES (?, ?, ?, ?, ?) "
	"ON CONFLICT(date) DO UPDATE SET "
	"open=excluded.open, high=excluded.high, low=excluded.low, close=excluded.close"
)

def _stock_name(ticker, intervals):
	name = ticker.lower()
	if not _TICKER_PATTERN.match(name):
		raise ValueError("Invalid ticker: " + repr(ticker))
	for interval in intervals:
		if interval not in INTERVAL_SECONDS:
			raise ValueError("Invalid interval: " + repr(interval))
	return name

def _stock_path(name):
	return os.path.join(os.getcwd(), "db", "db_" + name + ".db")

def _fetch_m1_page(name, to=None):
	"""Up to a day of Tornsy minutes ending at `to` (default: now), as (timestamps, prices) arrays; None if unreachable."""
	import numpy as np
	ohlc = get_tornsy_candles(name, "m1", str(_TORNSY_M1_PAGE), "NONE" if to is None else str(int(to)))
	if not ohlc or "data" not in ohlc:
		return None
	page = ohlc["data"]
	return (
		np.array([int(r[0]) for r in page], dtype=np.int64),
		np.array([float(r[1]) for r in page], dtype=np.float64),
	)

def _merge_pages(pages):
	"""Pages of (timestamps, prices) in any order -> one ascending array pair, one price per timestamp."""
	import numpy as np
	ts = np.concatenate([p[0] for p in pages])
	price = np.concatenate([p[1] for p in pages])
	order = np.argsort(ts, kind="stable")
	ts, price = ts[order], price[order]
	keep = np.r_[ts[1:] != ts[:-1], True] if len(ts) else np.zeros(0, dtype=bool)
	return ts[keep], price[keep]

def _write_minutes(con, ts, price, intervals):
	"""
	Store minutes (ascending, unique) in m1, then rebuild from m1 every candle of the
	other intervals that holds one of them, the way Tornsy derives its intervals.
	Rebuilding rather than merging makes write order irrelevant, so older history can
	be filled in after newer minutes are already stored. Call inside a transaction.
	"""
	import numpy as np
	minutes = (ts // 60) * 60
	con.execute(_CANDLE_SCHEMA.format("m1"))
	values = price.tolist()
	con.executemany(_M1_UPSERT, zip(minutes.tolist(), values, values, values, values))

	others = [i for i in intervals if i != "m1"]
	if not others or len(minutes) == 0:
		return
	# Read the stored minutes of every whole day touched, which covers every candle touched
	lo = int(minutes[0]) // 86400 * 86400
	hi = int(minutes[-1]) // 86400 * 86400 + 86400
	rows = np.array(con.execute("SELECT date, open, high, low, close FROM m1 WHERE date >= ? AND date < ? ORDER BY date", (lo, hi)).fetchall(), dtype=np.float64)
	dates = rows[:, 0].astype(np.int64)
	for interval in others:
		seconds = INTERVAL_SECONDS[interval]
		con.execute(_CANDLE_SCHEMA.format(interval))
		buckets = dates // seconds * seconds
		starts = np.flatnonzero(np.r_[True, buckets[1:] != buckets[:-1]])
		ends = np.r_[starts[1:], len(dates)] - 1
		highs = np.maximum.reduceat(rows[:, 2], starts)
		lows = np.minimum.reduceat(rows[:, 3], starts)
		# Only candles holding a new minute; the rest of those days is left as stored
		touched = np.isin(buckets[starts], np.unique(minutes // seconds * seconds))
		con.executemany(_CANDLE_REPLACE.format(interval), zip(
			buckets[starts][touched].tolist(),
			rows[starts, 1][touched].tolist(),
			highs[touched].tolist(),
			lows[touched].tolist(),
			rows[ends, 4][touched].tolist(),
		))

def load_recent(ticker, intervals, minutes=1440):
	"""
	Startup load, before the bot connects: Tornsy's newest minutes back to the newest
	stored one, or at least `minutes` of them for a new stock or after a longer outage.
	Anything older still missing is recorded in backfill_pending for backfill_pending().

	Returns (minutes_written, older_history_pending), or None if Tornsy could not be
	reached (the whole gap is then left pending).
	"""
	name = _stock_name(ticker, intervals)
	path = _stock_path(name)
	newest_stored = _last_stored_m1(path)
	now = int(time.time()) // 60 * 60
	# Back to the newest stored minute if that's recent, otherwise just the last `minutes`
	stop_at = newest_stored if newest_stored is not None and newest_stored >= now - minutes * 60 else now - minutes * 60

	pages = []
	to = None
	history_ended = False
	while True:
		page = _fetch_m1_page(name, to)
		if page is None:
			if not pages:
				con = sqlite3.connect(path, timeout=_BUSY_TIMEOUT)
				try:
					with con:
						con.execute(_PENDING_SCHEMA)
						con.execute("INSERT INTO backfill_pending (lo, hi) VALUES (?, NULL)", (newest_stored,))
				finally:
					con.close()
				return None
			break  # keep what was fetched; the rest is left pending below
		ts, price = page
		if newest_stored is not None:
			keep = ts >= newest_stored  # that minute again, as it may still have been forming
			ts, price = ts[keep], price[keep]
		if len(ts):
			pages.append((ts, price))
		if len(page[0]) < _TORNSY_M1_PAGE:
			history_ended = True
			break
		if len(ts) == 0 or int(page[0][0]) <= stop_at:
			break
		to = int(page[0][0])
		time.sleep(0.05)

	ts, price = _merge_pages(pages) if pages else (None, None)
	oldest = int(ts[0]) if ts is not None and len(ts) else now
	reached_stored = newest_stored is not None and oldest <= newest_stored
	pending = not reached_stored and not history_ended

	con = sqlite3.connect(path, timeout=_BUSY_TIMEOUT)
	try:
		with con:
			if ts is not None and len(ts):
				_write_minutes(con, ts, price, intervals)
			con.execute(_PENDING_SCHEMA)
			if pending:
				con.execute("INSERT INTO backfill_pending (lo, hi) VALUES (?, ?)", (newest_stored, oldest))
	finally:
		con.close()
	return (0 if ts is None else len(ts), pending)

def has_pending_backfill(ticker):
	"""Whether a stock has minute ranges left for backfill_pending()."""
	path = _stock_path(_stock_name(ticker, []))
	if not os.path.exists(path):
		return False
	con = sqlite3.connect(path, timeout=_BUSY_TIMEOUT)
	try:
		con.execute(_PENDING_SCHEMA)
		return con.execute("SELECT 1 FROM backfill_pending LIMIT 1").fetchone() is not None
	finally:
		con.close()

def backfill_pending(ticker, intervals, progress=None, chunk_minutes=30 * 1440):
	"""
	Fill the ranges load_recent() left pending, newest first, walking back through Tornsy
	a day per request. Safe to run while the live feed writes. Each chunk of about
	`chunk_minutes` is committed together with the range shrunk to what's left, so an
	interrupted backfill resumes where it stopped on the next start.

	`progress(minutes_written_or_held, oldest_timestamp)` is called after each page.
	Returns the minutes written, or None if Tornsy stopped responding (what was written
	is kept and the rest stays pending).
	"""
	import numpy as np
	name = _stock_name(ticker, intervals)
	path = _stock_path(name)
	if not os.path.exists(path):
		return 0
	con = sqlite3.connect(path, timeout=_BUSY_TIMEOUT)
	try:
		with con:
			con.execute(_PENDING_SCHEMA)
		gaps = con.execute("SELECT rowid, lo, hi FROM backfill_pending ORDER BY hi IS NULL DESC, hi DESC").fetchall()
		written = 0
		for rowid, lo, hi in gaps:
			pages, held = [], 0
			while True:
				# Everything below `upper` is still to fetch (None: up to the newest minute)
				upper = hi if not pages else int(pages[-1][0][0])
				page = _fetch_m1_page(name, upper)
				done = False
				if page is None:
					if pages:
						written += _commit_chunk(con, rowid, pages, intervals, done=False)
					return None
				ts, price = page
				keep = ts < upper if upper is not None else np.ones(len(ts), dtype=bool)
				if lo is not None:
					keep &= ts >= lo
				if keep.any():
					pages.append((ts[keep], price[keep]))
					held += int(keep.sum())
				# History ran out, the range is filled, or nothing new came back
				if len(page[0]) < _TORNSY_M1_PAGE or not keep.any() or (lo is not None and int(page[0][0]) <= lo):
					done = True
				if progress is not None and pages:
					progress(written + held, int(pages[-1][0][0]))
				if done or held >= chunk_minutes:
					if pages:
						written += _commit_chunk(con, rowid, pages, intervals, done)
						hi = int(pages[-1][0][0])
					elif done:
						with con:
							con.execute("DELETE FROM backfill_pending WHERE rowid = ?", (rowid,))
					pages, held = [], 0
					if done:
						break
				time.sleep(0.05)
		return written
	finally:
		con.close()

def _commit_chunk(con, rowid, pages, intervals, done):
	"""Write a chunk of backfilled minutes and shrink (or clear) its pending range in one transaction."""
	ts, price = _merge_pages(pages)
	with con:
		_write_minutes(con, ts, price, intervals)
		if done:
			con.execute("DELETE FROM backfill_pending WHERE rowid = ?", (rowid,))
		else:
			con.execute("UPDATE backfill_pending SET hi = ? WHERE rowid = ?", (int(ts[0]), rowid))
	return len(ts)

def update_from_tornsy(json_data, intervals):
	pwd = os.getcwd()
	for data in json_data["data"]:
		# Deny TCSE usage
		if data["stock"] == "TCSE":
			continue

		name = data["stock"].lower()
		con = sqlite3.connect(pwd + "/db/db_" + name + ".db", timeout=_BUSY_TIMEOUT)
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
